"""
Video Remediator — Takes compliance results and produces a compliant script + visual edit guide.
"""

import json
import logging
import mimetypes
import os
import re
import time
import uuid
from typing import Any

from google import genai
from google.genai import types

from config import VERTEX_PROJECT_ID, VERTEX_LOCATION
from jusads_video_compliance.audio_generator import AudioGenerator

logger = logging.getLogger(__name__)

client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)


class VideoRemediator:
    """Produces a compliant rewrite of a video ad (script + visual edit guide)."""

    def remediate(
        self,
        video_path: str,
        compliance_result: dict[str, Any],
        market: str = "malaysia",
        ethnicity: str = "all",
        age_group: str = "all_ages",
    ) -> dict[str, Any]:
        """Generate a compliant script and visual edit guide for a flagged video.

        Args:
            video_path: Path to the original video.
            compliance_result: The output from VideoComplianceChecker.check_compliance().
            market: Target market.
            ethnicity: Target ethnicity.
            age_group: Target age group.

        Returns:
            Dict with rewritten_script, visual_edit_guide, and changes_made.
        """
        # Load original video bytes so Gemini can reference the visuals
        try:
            with open(video_path, "rb") as f:
                video_bytes = f.read()
            mime_type, _ = mimetypes.guess_type(video_path)
            if not mime_type:
                mime_type = "video/mp4"
        except Exception as e:
            logger.error(f"Failed to load video: {e}")
            return {
                "rewritten_script": "",
                "visual_edit_guide": [],
                "changes_made": [f"Failed to load video: {e}"],
            }

        prompt = self._build_prompt(compliance_result, market, ethnicity)

        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=video_bytes, mime_type=mime_type),
                    ],
                )
            ]

            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=8192,
                    safety_settings=[
                        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
                    ],
                    thinking_config=types.ThinkingConfig(thinking_level="MEDIUM"),
                ),
            )
            result = self._parse_response(response.text)
            
            # Step 2: Generate B-Roll clips for each prompt using Veo
            broll_prompts = result.get("video_broll_prompts", [])
            generated_brolls = []
            
            if broll_prompts:
                logger.info(f"Found {len(broll_prompts)} B-Roll prompts. Generating clips with Veo...")
                for broll in broll_prompts:
                    prompt_text = broll.get("prompt")
                    timestamp = broll.get("timestamp", "")
                    
                    if prompt_text:
                        duration = self._parse_duration(timestamp)
                        video_path = self.step2_generate_video_broll(prompt_text, duration_seconds=duration)
                        if video_path:
                            broll["generated_video_path"] = video_path
                            generated_brolls.append(video_path)
            
            result["generated_brolls"] = generated_brolls
            
            # Step 3: Generate Localized Voiceover using ElevenLabs
            script = result.get("rewritten_script")
            if script:
                audio_gen = AudioGenerator()
                audio_path = audio_gen.generate_audio(script, market=market)
                result["generated_voiceover_path"] = audio_path
                
            return result
        except Exception as e:
            logger.error(f"Video remediation failed: {e}")
            return {
                "rewritten_script": "",
                "video_broll_prompts": [],
                "changes_made": [f"Remediation failed: {e}"],
            }

    def _build_prompt(
        self,
        compliance_result: dict[str, Any],
        market: str,
        ethnicity: str,
    ) -> str:
        transcript = compliance_result.get("transcript_used", "")
        indicators = compliance_result.get("high_risk_indicators", [])
        explanation = compliance_result.get("explanation", "")
        suggestion = compliance_result.get("suggestion", "")

        return f"""You are an expert video advertising director specializing in culturally compliant commercials for {market.title()} audiences (target ethnicity: {ethnicity}).

## TASK
Watch the attached video advertisement. It has been flagged for cultural compliance issues. Produce:
1. A **rewritten spoken script** that fixes all flagged audio/dialogue issues while preserving the product pitch.
2. A list of **video_broll_prompts** for Veo. For each flagged timestamp, write an exact, highly-detailed text-to-video generation prompt that describes the new compliant scene (max 8 seconds long). Include details about the environment, the actor's compliant clothing (e.g. long sleeves, hijab), and the action.
3. A summary of all changes made.

## ORIGINAL TRANSCRIPT
{transcript}

## COMPLIANCE ISSUES DETECTED
**High Risk Indicators:**
{json.dumps(indicators, indent=2, ensure_ascii=False)}

**Explanation:**
{explanation}

**Suggestion:**
{suggestion}

## RULES
1. Fix every flagged issue (both audio and visual).
2. Preserve the core product pitch and brand identity.
3. Keep the rewritten script roughly the same duration as the original.
4. For the `video_broll_prompts`, provide EXACT timestamps matching the `high_risk_indicator` timestamps (e.g., "[00:05-00:08]"). Be extremely descriptive in the `prompt` field, as it will be fed directly into a text-to-video model (Veo) to generate a replacement clip.

## OUTPUT FORMAT
Return ONLY a JSON object:
{{
  "rewritten_script": "The full corrected voiceover script...",
  "video_broll_prompts": [
    {{
      "timestamp": "[00:00-00:05]",
      "prompt": "A high-quality commercial video shot: A beautiful young Malay woman wearing a modest long-sleeved pastel blue athletic blouse and a neatly styled hijab, standing confidently on a sunny beach with clear blue skies, smiling naturally. Cinematic lighting, 4k.",
      "reason": "Modesty standards require covered shoulders and hair."
    }}
  ],
  "changes_made": [
    "Replaced 'gynecologists' reference with 'dermatologists recommend'",
    "Changed wardrobe to modest long-sleeved clothing and hijab throughout"
  ]
}}
"""

    def _parse_response(self, text: str) -> dict[str, Any]:
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        try:
            return json.loads(clean.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse video remediation JSON: {e}")
            return {
                "rewritten_script": "",
                "video_broll_prompts": [],
                "changes_made": [f"Parse error: {e}"],
            }

    def _parse_duration(self, timestamp: str) -> int:
        """Parses a timestamp like '[00:03-00:08]' into a duration in seconds. Defaults to 8."""
        match = re.search(r'\[(\d+):(\d+)-(\d+):(\d+)\]', timestamp)
        if match:
            m1, s1, m2, s2 = map(int, match.groups())
            start_sec = m1 * 60 + s1
            end_sec = m2 * 60 + s2
            duration = end_sec - start_sec
            # Clamp between 1 and 8 seconds for Veo
            return max(1, min(8, duration))
        return 8

    def step2_generate_video_broll(self, prompt: str, duration_seconds: int = 8) -> str | None:
        """Step 2: Generate a variable length B-Roll video using Veo."""
        try:
            logger.info(f"Generating {duration_seconds}s Veo video for prompt: {prompt[:50]}...")
            
            source = types.GenerateVideosSource(
                prompt=prompt,
            )

            config = types.GenerateVideosConfig(
                aspect_ratio="16:9",
                number_of_videos=1,
                duration_seconds=duration_seconds,
                person_generation="allow_all",
                generate_audio=False,
                resolution="720p",
            )

            operation = client.models.generate_videos(
                model="veo-3.1-lite-generate-001", source=source, config=config
            )

            while not operation.done:
                logger.info("Video has not been generated yet. Check again in 10 seconds...")
                time.sleep(10)
                operation = client.operations.get(operation)

            response = operation.result
            if not response:
                logger.error("Error occurred while generating video.")
                return None

            generated_videos = response.generated_videos
            if not generated_videos:
                logger.error("No videos were generated.")
                return None

            generated_video = generated_videos[0]
            if generated_video.video:
                output_dir = os.path.join("backend", "assets", "remediated")
                os.makedirs(output_dir, exist_ok=True)
                filename = f"broll_{uuid.uuid4().hex[:8]}.mp4"
                file_path = os.path.join(output_dir, filename)
                
                with open(file_path, "wb") as f:
                    f.write(generated_video.video.video_bytes)
                
                logger.info(f"Saved Veo generated video to {file_path}")
                return file_path
            
            return None
            
        except Exception as e:
            logger.error(f"Veo video generation failed: {e}")
            return None
