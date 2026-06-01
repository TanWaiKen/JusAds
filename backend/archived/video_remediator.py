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
from jusads_video_compliance.video_assembler import VideoAssembler

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
            
            # Step 2: Edit video segments for each prompt using Veo
            edit_prompts = result.get("video_edit_prompts", [])
            generated_edits = []
            
            if edit_prompts:
                logger.info(f"Found {len(edit_prompts)} Edit prompts. Inpainting clips with Veo...")
                for edit in edit_prompts:
                    prompt_text = edit.get("prompt")
                    timestamp = edit.get("timestamp", "")
                    
                    if prompt_text:
                        duration = self._parse_duration(timestamp)
                        
                        edited_video_path = self.step2_generate_video_broll(
                            prompt=prompt_text, 
                            duration_seconds=duration
                        )
                        if edited_video_path:
                            edit["generated_video_path"] = edited_video_path
                            generated_edits.append(edited_video_path)
            
            result["generated_brolls"] = generated_edits # Keep key for compatibility with video_assembler
            
            # Step 3: Generate Localized Voiceover using ElevenLabs
            script = result.get("rewritten_script")
            audio_path = None
            if script:
                audio_gen = AudioGenerator()
                audio_path = audio_gen.generate_audio(script, market=market)
                result["generated_voiceover_path"] = audio_path
                
            # Step 4: Final Video Assembly
            if audio_path and generated_edits:
                assembler = VideoAssembler()
                # assembler expects `broll_prompts` key, so we pass `edit_prompts`
                final_path = assembler.assemble_video(video_path, edit_prompts, audio_path)
                result["final_video_path"] = final_path
                
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
2. A list of **video_edit_prompts** for Veo. For each flagged timestamp, write an exact, highly-detailed text-to-video generation prompt for a **B-Roll replacement shot**. 
   - **CRITICAL:** Do NOT include any people, actors, or body parts in these prompts! To avoid jarring jump-cuts and morphing, we are replacing non-compliant scenes with pure cinematic B-Roll (e.g., "A cinematic close-up of the deodorant bottle on a marble counter", "A beautiful sunny beach with palm trees").
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
4. For the `video_edit_prompts`, provide EXACT timestamps matching the `high_risk_indicator` timestamps (e.g., "[00:05-00:08]"). Be extremely descriptive in the `prompt` field about the B-Roll scene needed, ensuring absolutely NO PEOPLE are present.

## OUTPUT FORMAT
Return ONLY a JSON object:
{{
  "rewritten_script": "The full corrected voiceover script...",
  "video_edit_prompts": [
    {{
      "timestamp": "[00:00-00:05]",
      "prompt": "A cinematic, sunny beach with gentle waves crashing. Beautiful 4k lifestyle shot, bright lighting, empty beach.",
      "reason": "Replaced non-compliant scene with lifestyle environmental B-Roll."
    }}
  ],
  "changes_made": [
    "Replaced 'gynecologists' reference with 'dermatologists recommend'",
    "Replaced non-compliant scenes with product and environmental B-Rolls without actors."
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
                "video_edit_prompts": [],
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
            # Veo API fails on very short clips (e.g. 1s). Clamp between 4 and 8 seconds.
            return max(4, min(8, duration))
        return 8

    def step2_generate_video_broll(self, prompt: str, duration_seconds: int = 8) -> str | None:
        """Step 2: Generate a variable length B-Roll video using Veo Text-to-Video."""
        try:
            logger.info(f"Generating {duration_seconds}s Veo B-Roll for prompt: {prompt[:50]}...")
            
            source = types.GenerateVideosSource(prompt=prompt)

            config = types.GenerateVideosConfig(
                aspect_ratio="16:9",
                number_of_videos=1,
                duration_seconds=duration_seconds,
                person_generation="dont_allow", # Ensure no people are generated!
                generate_audio=False,
                resolution="720p",
            )

            operation = client.models.generate_videos(
                model="veo-3.1-lite-generate-001", source=source, config=config
            )

            while not operation.done:
                logger.info("Video edit is processing. Check again in 10 seconds...")
                time.sleep(10)
                operation = client.operations.get(operation)

            response = operation.result
            if not response:
                logger.error("Error occurred while generating video edit.")
                return None

            generated_videos = response.generated_videos
            if not generated_videos:
                logger.error("No video edits were generated.")
                return None

            generated_video = generated_videos[0]
            if generated_video.video:
                output_dir = os.path.join("backend", "assets", "remediated")
                os.makedirs(output_dir, exist_ok=True)
                filename = f"edit_{uuid.uuid4().hex[:8]}.mp4"
                file_path = os.path.join(output_dir, filename)
                
                with open(file_path, "wb") as f:
                    f.write(generated_video.video.video_bytes)
                
                logger.info(f"Saved Veo generated video to {file_path}")
                return file_path
            
            return None
            
        except Exception as e:
            logger.error(f"Veo video generation failed: {e}")
            return None
