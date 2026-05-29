"""
Image Remediator — Takes compliance results and generates a compliant image prompt.
"""

import json
import logging
import mimetypes
from typing import Any

from google import genai
from google.genai import types

from config import VERTEX_PROJECT_ID, VERTEX_LOCATION

logger = logging.getLogger(__name__)

client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)


class ImageRemediator:
    """Generates a compliant image prompt based on compliance issues."""

    def remediate(
        self,
        image_path: str,
        compliance_result: dict[str, Any],
        market: str = "malaysia",
        ethnicity: str = "all",
        age_group: str = "all_ages",
    ) -> dict[str, Any]:
        """Analyze a non-compliant image and produce a compliant redesign prompt and image.

        Args:
            image_path: Path to the original image.
            compliance_result: The output from ImageComplianceChecker.check_compliance().
            market: Target market.
            ethnicity: Target ethnicity.
            age_group: Target age group.

        Returns:
            Dict with compliant_image_prompt, changes_suggested, and generated_image_path.
        """
        # Step 1: Generate the compliant image prompt
        result = self.step1_generate_prompt(image_path, compliance_result, market, ethnicity)
        
        # Step 2: Generate the image using Imagen 3
        compliant_prompt = result.get("compliant_image_prompt")
        if compliant_prompt:
            combined_prompt = compliant_prompt + "\n\nChanges Suggested:\n"
            for change in result.get("changes_suggested", []):
                combined_prompt += f"  - {change}\n"
                
            image_generation_result = self.step2_generate_image(combined_prompt, image_path)
            result.update(image_generation_result)
            
        return result

    def step1_generate_prompt(
        self,
        image_path: str,
        compliance_result: dict[str, Any],
        market: str,
        ethnicity: str,
    ) -> dict[str, Any]:
        """Step 1: Use Gemini to analyze the image and generate a compliant prompt."""
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type:
                mime_type = "image/jpeg"
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            return {
                "compliant_image_prompt": "",
                "changes_suggested": [f"Failed to load image: {e}"],
            }

        prompt = self._build_prompt(compliance_result, market, ethnicity)

        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    ],
                )
            ]

            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=0.4,
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
            return self._parse_response(response.text)
        except Exception as e:
            logger.error(f"Image prompt generation failed: {e}")
            return {
                "compliant_image_prompt": "",
                "changes_suggested": [f"Remediation failed: {e}"],
            }

    def step2_generate_image(self, compliant_prompt: str, original_image_path: str) -> dict[str, str]:
        """Step 2: Generate the compliant image using Vertex AI Imagen 3 using original as reference."""
        try:
            import os
            import uuid
            import vertexai
            from vertexai.preview.vision_models import (
                Image,
                ImageGenerationModel,
                RawReferenceImage
            )

            logger.info("Generating compliant image using Imagen 3 (Vertex AI)...")
            
            # Ensure vertexai is initialized
            vertexai.init(project=VERTEX_PROJECT_ID, location="us-central1")
            
            generation_model = ImageGenerationModel.from_pretrained("imagen-3.0-capability-001")
            
            with open(original_image_path, "rb") as f:
                orig_bytes = f.read()

            reference_images = [
                RawReferenceImage(
                    reference_id=1,
                    image=Image(image_bytes=orig_bytes)
                )
            ]

            images = generation_model._generate_images(
                prompt=compliant_prompt,
                number_of_images=1,
                aspect_ratio="1:1",  # Reverted to 1:1 for social media
                person_generation="allow_all",
                reference_images=reference_images
            )
            
            if images:
                generated_image = images[0]
                output_dir = os.path.join("backend", "assets", "remediated")
                os.makedirs(output_dir, exist_ok=True)
                
                filename = f"remediated_{uuid.uuid4().hex[:8]}.png"
                file_path = os.path.join(output_dir, filename)
                
                generated_image.save(location=file_path, include_generation_parameters=False)
                    
                logger.info(f"Successfully generated and saved image to {file_path}")
                return {"generated_image_path": file_path}
            
            return {"generated_image_error": "No image returned by the model."}
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {"generated_image_error": str(e)}

    def _build_prompt(
        self,
        compliance_result: dict[str, Any],
        market: str,
        ethnicity: str,
    ) -> str:
        indicators = compliance_result.get("high_risk_indicators", [])
        explanation = compliance_result.get("explanation", "")
        suggestion = compliance_result.get("suggestion", "")

        return f"""You are an expert advertising art director specializing in culturally compliant visual design for {market.title()} audiences (target ethnicity: {ethnicity}).

                    ## TASK
                    Look at the attached image advertisement. It has been flagged for cultural compliance issues. Your job is to produce:
                    1. A detailed **image generation prompt** that describes a compliant version of this ad — fixing all flagged issues while preserving the product, brand identity, and marketing intent.
                    2. A list of specific changes you made.

                    ## COMPLIANCE ISSUES DETECTED
                    **High Risk Indicators:**
                    {json.dumps(indicators, indent=2, ensure_ascii=False)}

                    **Explanation:**
                    {explanation}

                    **Suggestion:**
                    {suggestion}

                    ## RULES
                    1. Fix every flagged visual issue (clothing, poses, symbols, colors, text).
                    2. Preserve the product being advertised and its core benefit.
                    3. Preserve the overall composition style (photo-realistic, illustrated, etc.).
                    4. The prompt must be detailed enough for an AI image generator (e.g., DALL-E, Imagen, Midjourney) to recreate the ad.
                    5. Include specific details: clothing description, pose, background, text overlays, color palette.
                    6. The subject MUST clearly be described as a Malay woman (or target ethnicity).
                    7. Translate and adapt any text overlays from the original image into casual, natural "Manglish" (Malaysian English slang) to better resonate with the local market.

                    ## OUTPUT FORMAT
                    Return ONLY a JSON object:
                    {{
                    "compliant_image_prompt": "A detailed image generation prompt describing the compliant version...",
                    "changes_suggested": [
                        "Changed sleeveless top to long-sleeved modest blouse",
                        "Removed exposed midriff by adjusting pose"
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
            logger.error(f"Failed to parse image remediation JSON: {e}")
            return {
                "compliant_image_prompt": "",
                "changes_suggested": [f"Parse error: {e}"],
            }
