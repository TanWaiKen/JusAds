import json
import logging
import mimetypes
import os
import re
import uuid
from typing import Any

from google import genai
from google.genai import types

from config import VERTEX_PROJECT_ID, VERTEX_LOCATION
from jusads_video_compliance.audio_generator import AudioGenerator
from jusads_video_compliance.video_assembler import VideoAssembler
from jusads_video_compliance.kling_generator import KlingGenerator

logger = logging.getLogger(__name__)

client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)

class VideoRemediatorKling:
    """Produces a compliant rewrite of a video ad using Kling AI for Video-to-Video inpainting."""

    def remediate(
        self,
        video_path: str,
        compliance_result: dict[str, Any],
        market: str = "malaysia",
        ethnicity: str = "all",
        age_group: str = "all_ages",
    ) -> dict[str, Any]:
        """Generate a compliant script and Kling visual edit guide."""
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
                "video_edit_prompts": [],
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
                ),
            )
            result = self._parse_response(response.text)
            
            # Step 2: Edit video segments for each prompt using Kling AI
            edit_prompts = result.get("video_edit_prompts", [])
            generated_edits = []
            
            if edit_prompts:
                logger.info(f"Found {len(edit_prompts)} Edit prompts. Inpainting clips with Kling AI...")
                kling = KlingGenerator()
                
                for edit in edit_prompts:
                    prompt_text = edit.get("prompt")
                    timestamp = edit.get("timestamp", "")
                    
                    if prompt_text:
                        duration = self._parse_duration(timestamp)
                        edited_video_path = kling.generate_video_broll(
                            prompt=prompt_text,
                            duration_seconds=duration
                        )
                    if edited_video_path:
                        edit["generated_video_path"] = edited_video_path
                        generated_edits.append(edited_video_path)
            
            result["generated_brolls"] = generated_edits 
            
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
                final_path = assembler.assemble_video(video_path, edit_prompts, audio_path)
                result["final_video_path"] = final_path
                
            return result
        except Exception as e:
            logger.error(f"Video remediation failed: {e}")
            return {
                "rewritten_script": "",
                "video_edit_prompts": [],
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
2. A list of **video_edit_prompts** for KIE Kling (a powerful Text-to-Video model). For each flagged timestamp, write an exact, highly-detailed prompt describing a **B-Roll replacement shot**. 
   - **CRITICAL:** Do NOT include any people, actors, or body parts in these prompts! To avoid jarring jump-cuts and morphing, we are replacing non-compliant scenes with pure cinematic B-Roll (e.g., "A cinematic close-up of the deodorant bottle on a marble counter", "A beautiful sunny beach with palm trees").
3. A summary of all changes made.

## ORIGINAL TRANSCRIPT
{transcript}

## COMPLIANCE ISSUES DETECTED
**High Risk Indicators:**
{json.dumps(indicators, indent=2, ensure_ascii=False)}

## RULES
1. Fix every flagged issue (both audio and visual).
2. For the `video_edit_prompts`, provide EXACT timestamps matching the `high_risk_indicator` timestamps (e.g., "[00:05-00:08]"). Be extremely descriptive in the `prompt` field about the B-Roll scene needed, ensuring absolutely NO PEOPLE are present.

## OUTPUT FORMAT
Return ONLY a JSON object:
{{
  "rewritten_script": "...",
  "video_edit_prompts": [
    {{
      "timestamp": "[00:00-00:05]",
      "prompt": "A cinematic, sunny beach with gentle waves crashing. Beautiful 4k lifestyle shot, bright lighting, empty beach.",
      "reason": "Replaced non-compliant scene with lifestyle environmental B-Roll."
    }}
  ],
  "changes_made": []
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
            return {
                "rewritten_script": "",
                "video_edit_prompts": [],
                "changes_made": [f"Parse error: {e}"],
            }



    def _parse_duration(self, timestamp: str) -> int:
        match = re.search(r'\[(\d+):(\d+)-(\d+):(\d+)\]', timestamp)
        if match:
            m1, s1, m2, s2 = map(int, match.groups())
            start_sec = m1 * 60 + s1
            end_sec = m2 * 60 + s2
            duration = end_sec - start_sec
            # Kling AI can take up to 5s or 10s. Defaulting to exact duration.
            return max(1, duration)
        return 5
