"""
compliance_tools.py
───────────────────
Compliance checking tools for text, image, audio, and video ads.
Queries rules and personas from Supabase (direct DB queries).
"""

import os
import json
import logging
from pathlib import Path

from google.genai import types
from langchain_core.tools import tool

from shared.clients import gemini
from shared.config import MODEL_TEXT
from jusads_compliance.rules_client import get_all_rules_and_persona
from jusads_compliance.prompts import (
    UNIFIED_OUTPUT_TEMPLATE,
    IMAGE_PRESCAN_PROMPT,
    VIDEO_PRESCAN_PROMPT,
    TEXT_COMPLIANCE_PROMPT,
    IMAGE_COMPLIANCE_PROMPT,
    AUDIO_COMPLIANCE_PROMPT,
    VIDEO_COMPLIANCE_PROMPT,
    SEGMENTATION_PROMPT,
)

logger = logging.getLogger(__name__)


def _get_all_rules(query: str, market: str, platform: str, ethnicity: str, age_group: str, top_k: int = None) -> dict:
    """Fetch rules and persona from Supabase.

    The 'query' and 'top_k' params are kept for API compatibility but ignored
    since we now fetch all matching rules directly from the DB.
    """
    return get_all_rules_and_persona(
        market=market,
        platform=platform,
        ethnicity=ethnicity,
        age_group=age_group,
    )


def _build_rules_context(rules_data: dict) -> tuple[str, str]:
    """Format rules and persona into prompt text."""
    rules_text = json.dumps(rules_data.get("rules", []), indent=2)
    persona_text = json.dumps(rules_data.get("persona", {}), indent=2)
    return rules_text, persona_text


@tool
def check_text_compliance(text: str, market: str, platform: str, ethnicity: str, age_group: str):
    """Check ad text against regulatory + platform rules using Gemini."""
    rules_data = _get_all_rules(text, market, platform, ethnicity, age_group)
    rules_text, persona_text = _build_rules_context(rules_data)

    prompt = TEXT_COMPLIANCE_PROMPT.format(
        market=market.title(),
        platform=platform.title(),
        text=text,
        rules_text=rules_text,
        persona_text=persona_text,
        output_template=UNIFIED_OUTPUT_TEMPLATE,
    )

    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Text compliance check failed: {e}")
        return {"error": str(e)}


@tool
def check_image_compliance(image_path: str, market: str, platform: str, ethnicity: str, age_group: str):
    """Check ad image against regulatory + platform rules using Gemini multimodal."""
    import mimetypes

    with open(image_path, "rb") as f:
        image_bytes = f.read()
    mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"

    # Pre-scan: describe the image content
    prescan = gemini.models.generate_content(
        model=MODEL_TEXT,
        contents=[types.Content(role="user", parts=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            types.Part.from_text(text=IMAGE_PRESCAN_PROMPT),
        ])],
    )
    description = prescan.text.strip()

    rules_data = _get_all_rules(description, market, platform, ethnicity, age_group)
    rules_text, persona_text = _build_rules_context(rules_data)

    prompt = IMAGE_COMPLIANCE_PROMPT.format(
        market=market.title(),
        platform=platform.title(),
        rules_text=rules_text,
        persona_text=persona_text,
        output_template=UNIFIED_OUTPUT_TEMPLATE,
    )

    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=[types.Content(role="user", parts=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(text=prompt),
            ])],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Image compliance check failed: {e}")
        return {"error": str(e)}


@tool
def check_audio_compliance(audio_path: str, market: str, platform: str, ethnicity: str, age_group: str):
    """Check audio ad against regulatory + platform rules.
    Step 1: AWS Transcribe for transcription (auto language detection)
    Step 2: Gemini compliance check based on transcript."""
    import mimetypes
    import time
    import uuid
    import urllib.request
    from shared.clients import s3, transcribe
    from config import S3_BUCKET_NAME

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()
    mime_type = mimetypes.guess_type(audio_path)[0] or "audio/mpeg"

    # Step 1: AWS Transcribe (auto language detection)
    transcript = ""
    language = "unknown"
    s3_key = None
    try:
        # Upload audio to S3 for Transcribe to access
        s3_key = f"transcribe-tmp/{uuid.uuid4()}{os.path.splitext(audio_path)[1] or '.mp3'}"
        s3.put_object(Bucket=S3_BUCKET_NAME, Key=s3_key, Body=audio_bytes, ContentType=mime_type)
        s3_uri = f"s3://{S3_BUCKET_NAME}/{s3_key}"

        job_name = f"jusads-{uuid.uuid4().hex}"
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": s3_uri},
            IdentifyLanguage=True,
        )

        # Poll until the job completes (max 120 s)
        for _ in range(40):
            time.sleep(3)
            status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status["TranscriptionJob"]["TranscriptionJobStatus"]
            if job_status == "COMPLETED":
                break
            if job_status == "FAILED":
                raise RuntimeError(status["TranscriptionJob"].get("FailureReason", "Transcription job failed"))

        if job_status != "COMPLETED":
            raise TimeoutError("AWS Transcribe job timed out after 120 s")

        # Fetch transcript JSON from the result URI
        transcript_uri = status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        with urllib.request.urlopen(transcript_uri) as resp:
            transcript_json = json.loads(resp.read().decode())

        transcript = transcript_json.get("results", {}).get("transcripts", [{}])[0].get("transcript", "")
        language = status["TranscriptionJob"].get("LanguageCode", "unknown")
        logger.info(f"[AudioCompliance] AWS Transcribe: language={language}, length={len(transcript)}")

    except Exception as e:
        logger.warning(f"[AudioCompliance] AWS Transcribe failed, falling back to Gemini: {e}")
        # Fallback: use Gemini for transcription
        try:
            transcribe_response = gemini.models.generate_content(
                model=MODEL_TEXT,
                contents=[types.Content(role="user", parts=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                    types.Part.from_text(text=(
                        "Transcribe this audio. Return JSON: "
                        '{"language": "detected language", "transcript": "exact transcription"}'
                    )),
                ])],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            transcript_data = json.loads(transcribe_response.text)
            transcript = transcript_data.get("transcript", "")
            language = transcript_data.get("language", "unknown")
        except Exception as fallback_e:
            logger.error(f"[AudioCompliance] Fallback transcription also failed: {fallback_e}")
            transcript = "(transcription unavailable)"
    finally:
        # Clean up the temporary S3 object regardless of outcome
        if s3_key:
            try:
                from shared.clients import s3 as _s3
                from config import S3_BUCKET_NAME as _bucket
                _s3.delete_object(Bucket=_bucket, Key=s3_key)
            except Exception:
                pass

    if not transcript:
        transcript = "(no speech detected)"

    # Step 2: Get rules and check compliance using transcript
    query = transcript if len(transcript) > 10 else "audio advertisement content"
    rules_data = _get_all_rules(query, market, platform, ethnicity, age_group)
    rules_text, persona_text = _build_rules_context(rules_data)

    prompt = AUDIO_COMPLIANCE_PROMPT.format(
        market=market.title(),
        platform=platform.title(),
        transcript=transcript,
        language=language,
        rules_text=rules_text,
        persona_text=persona_text,
        output_template=UNIFIED_OUTPUT_TEMPLATE,
    )

    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=[types.Content(role="user", parts=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                types.Part.from_text(text=prompt),
            ])],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        result = json.loads(response.text)
        result["_transcript"] = {"language": language, "transcript": transcript}
        return result
    except Exception as e:
        logger.error(f"Audio compliance check failed: {e}")
        return {"error": str(e)}


@tool
def check_video_compliance(video_path: str, market: str, platform: str, ethnicity: str, age_group: str):
    """Check video ad against regulatory + platform rules using Gemini multimodal."""
    import mimetypes

    with open(video_path, "rb") as f:
        video_bytes = f.read()
    mime_type = mimetypes.guess_type(video_path)[0] or "video/mp4"

    # Pre-scan: describe the video content
    prescan = gemini.models.generate_content(
        model=MODEL_TEXT,
        contents=[types.Content(role="user", parts=[
            types.Part.from_bytes(data=video_bytes, mime_type=mime_type),
            types.Part.from_text(text=VIDEO_PRESCAN_PROMPT),
        ])],
    )
    description = prescan.text.strip()

    rules_data = _get_all_rules(description, market, platform, ethnicity, age_group)
    rules_text, persona_text = _build_rules_context(rules_data)

    prompt = VIDEO_COMPLIANCE_PROMPT.format(
        market=market.title(),
        platform=platform.title(),
        rules_text=rules_text,
        persona_text=persona_text,
        output_template=UNIFIED_OUTPUT_TEMPLATE,
    )

    try:
        response = gemini.models.generate_content(
            model=MODEL_TEXT,
            contents=[types.Content(role="user", parts=[
                types.Part.from_bytes(data=video_bytes, mime_type=mime_type),
                types.Part.from_text(text=prompt),
            ])],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Video compliance check failed: {e}")
        return {"error": str(e)}


@tool
def segment_violations(image_path: str, high_risk_indicators: list):
    """Segment non-compliant regions using Gemini bounding boxes + SAM 2 masks.
    Gemini identifies violation regions, SAM 2 refines to pixel-perfect masks."""
    import torch
    import numpy as np
    from transformers import Sam2Processor, Sam2Model
    from PIL import Image, ImageDraw

    if not high_risk_indicators:
        return {"error": "No violations to segment"}

    image = Image.open(image_path).convert("RGB")
    w, h = image.size

    # Step 1: Gemini detects bounding boxes for violations
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    import mimetypes
    mime_type = mimetypes.guess_type(image_path)[0] or "image/png"

    bbox_prompt = SEGMENTATION_PROMPT.format(
        violations=json.dumps(high_risk_indicators),
        width=w,
        height=h,
    )

    response = gemini.models.generate_content(
        model="gemini-3-flash-preview",
        contents=[types.Content(role="user", parts=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            types.Part.from_text(text=bbox_prompt),
        ])],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )

    # Parse bounding boxes
    detections = []
    try:
        raw = json.loads(response.text)
        for d in raw:
            box = None
            if "box" in d and isinstance(d["box"], list) and len(d["box"]) == 4:
                box = [float(x) for x in d["box"]]
            elif "box_2d" in d and isinstance(d["box_2d"], list) and len(d["box_2d"]) == 4:
                box = [float(x) for x in d["box_2d"]]
            elif "box_3d" in d and isinstance(d["box_3d"], list) and len(d["box_3d"]) >= 4:
                coords = [float(x) for x in d["box_3d"][:4]]
                if all(0 <= c <= 1000 for c in coords):
                    y1, x1, y2, x2 = coords
                    box = [x1*w/1000, y1*h/1000, x2*w/1000, y2*h/1000]
                else:
                    box = coords
            if box and d.get("label"):
                # Clamp to image bounds
                box = [max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3])]
                detections.append({"box": box, "label": d["label"]})
    except Exception as e:
        logger.error(f"Gemini bbox parse error: {e}")
        return {"error": f"Failed to parse bounding boxes: {e}"}

    if not detections:
        return {"error": "No violation regions detected by Gemini"}

    logger.info(f"Gemini detected {len(detections)} violation regions")

    # Step 2: SAM 2 refines to pixel-perfect masks
    sam_processor = Sam2Processor.from_pretrained("facebook/sam2-hiera-tiny")
    sam_model = Sam2Model.from_pretrained("facebook/sam2-hiera-tiny")
    sam_model.to("cpu")

    pixel_boxes = [d["box"] for d in detections]
    sam_inputs = sam_processor(images=image, input_boxes=[pixel_boxes], return_tensors="pt")

    with torch.no_grad():
        sam_outputs = sam_model(**sam_inputs)

    pred_masks = sam_outputs.pred_masks.squeeze(0)

    # Take best mask per box
    if hasattr(sam_outputs, "iou_scores") and sam_outputs.iou_scores is not None:
        iou_scores = sam_outputs.iou_scores.squeeze(0)
        best_idx = iou_scores.argmax(dim=-1)
        masks = torch.stack([pred_masks[i, best_idx[i]] for i in range(len(best_idx))])
    else:
        masks = pred_masks[:, 0]

    # Resize masks to original image size
    masks_resized = torch.nn.functional.interpolate(
        masks.unsqueeze(1).float(), size=(h, w), mode="bilinear", align_corners=False,
    ).squeeze(1)
    mask_arrays = (masks_resized > 0).cpu().numpy()

    # Step 3: Create overlay visualization
    overlay = image.convert("RGBA").copy()
    colors = [(255, 0, 0, 130), (0, 200, 0, 130), (0, 100, 255, 130), (255, 165, 0, 130), (255, 0, 255, 130)]

    for i, (mask, det) in enumerate(zip(mask_arrays, detections)):
        color = colors[i % len(colors)]
        color_array = np.zeros((h, w, 4), dtype=np.uint8)
        color_array[mask > 0] = color
        overlay = Image.alpha_composite(overlay, Image.fromarray(color_array, "RGBA"))

    draw = ImageDraw.Draw(overlay)
    for i, det in enumerate(detections):
        label_color = tuple(colors[i % len(colors)][:3]) + (255,)
        draw.text((10, 10 + i * 18), f"â–  {det['label']}", fill=label_color)

    os.makedirs("assets/results", exist_ok=True)
    # Always save as PNG since the overlay is RGBA (JPEG doesn't support transparency)
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    output_path = f"assets/results/segmented_{base_name}.png"
    overlay.save(output_path, format="PNG")

    logger.info(f"Segmentation saved to {output_path}")
    return {
        "segmented_image_path": output_path,
        "detections": [{"label": d["label"], "box": d["box"]} for d in detections],
        "num_masks": len(mask_arrays),
    }


@tool
def segment_violations_clipseg(image_path: str, high_risk_indicators: list):
    """Segment non-compliant regions using CLIPSeg (text-to-segmentation).

    Flow:
      1. Gemini converts high_risk_indicators → short visual prompts for CLIPSeg
      2. CLIPSeg segments the image using all prompts
      3. Union all prompt masks into a single binary mask
      4. Save overlay visualization

    Args:
        image_path: Path to the source image.
        high_risk_indicators: List of violation descriptions from compliance result.

    Returns:
        Dict with segmented_image_path, mask_path, visual_prompts, coverage_percent.
    """
    import torch
    import numpy as np
    from transformers import CLIPSegProcessor, CLIPSegForImageSegmentation
    from PIL import Image, ImageDraw

    if not high_risk_indicators:
        return {"error": "No violations to segment"}

    image = Image.open(image_path).convert("RGB")
    w, h = image.size

    # Step 1: Gemini converts indicators -> visual prompts
    prompt_text = f"""Convert these compliance violation indicators into short visual descriptions
that a segmentation model can use to find the violating regions in an image.

INDICATORS:
{json.dumps(high_risk_indicators, indent=2)}

RULES:
- Output 8-15 prompts (max 6 words each)
- Mix specific AND broad prompts:
  - Specific: "woman in bra", "bare legs", "alcohol bottle"
  - Broad: "person", "exposed body", "revealing clothing"
- The broad prompts help catch the FULL area of the violation
- Use concrete visible things only
- Include "person" or "woman" as one of the prompts

Return ONLY a JSON array: ["prompt 1", "prompt 2", ...]"""

    response = gemini.models.generate_content(
        model=MODEL_TEXT,
        contents=prompt_text,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    visual_prompts = json.loads(response.text)
    if not any("person" in p.lower() or "woman" in p.lower() or "man" in p.lower() for p in visual_prompts):
        visual_prompts.append("person")

    logger.info(f"Visual prompts ({len(visual_prompts)}): {visual_prompts}")

    # Step 2: CLIPSeg segmentation
    processor = CLIPSegProcessor.from_pretrained("CIDAS/clipseg-rd64-refined")
    model = CLIPSegForImageSegmentation.from_pretrained("CIDAS/clipseg-rd64-refined")

    inputs = processor(
        text=visual_prompts,
        images=[image] * len(visual_prompts),
        padding=True,
        return_tensors="pt",
    )

    with torch.no_grad():
        outputs = model(**inputs)

    # Resize to original image size
    logits = outputs.logits
    masks_resized = torch.nn.functional.interpolate(
        logits.unsqueeze(1), size=(h, w), mode="bilinear", align_corners=False
    ).squeeze(1)

    # Union all prompt masks with threshold 0.2
    probs = torch.sigmoid(masks_resized)
    union_mask = (probs.max(dim=0).values > 0.2).numpy().astype(np.uint8) * 255

    # Step 3: Save binary mask
    os.makedirs("assets/results", exist_ok=True)
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    mask_path = f"assets/results/mask_{base_name}.png"
    Image.fromarray(union_mask, mode="L").save(mask_path)

    # Step 4: Create overlay visualization
    overlay = image.convert("RGBA").copy()
    red_overlay = np.zeros((h, w, 4), dtype=np.uint8)
    red_overlay[union_mask > 0] = (255, 0, 0, 130)
    overlay = Image.alpha_composite(overlay, Image.fromarray(red_overlay, "RGBA"))

    output_path = f"assets/results/segmented_{base_name}.png"
    overlay.save(output_path, format="PNG")

    coverage = (union_mask > 0).sum() / union_mask.size * 100
    logger.info(f"CLIPSeg segmentation: {coverage:.1f}% coverage, saved to {output_path}")

    return {
        "segmented_image_path": output_path,
        "mask_path": mask_path,
        "visual_prompts": visual_prompts,
        "coverage_percent": round(coverage, 1),
    }


@tool
def extract_violation_clips(video_path: str, violations_timeline: list):
    """Extract video clips for violations. Merges overlapping/close timestamps into single clips.
    violations_timeline: list of {start_seconds, end_seconds, type, description}
    OR list of strings like "[00:03-00:08] exposed shoulders" (auto-parsed)."""
    import subprocess
    import re

    if not violations_timeline:
        return {"error": "No violations to extract"}

    # Parse if raw string indicators
    parsed = []
    for v in violations_timeline:
        if isinstance(v, str):
            # Parse "[SS-SS] description" or "[MM:SS-MM:SS] description"
            sec_match = re.search(r"\[(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)\]", v)
            mmss_match = re.search(r"\[(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})\]", v)
            if mmss_match:
                start = int(mmss_match.group(1)) * 60 + int(mmss_match.group(2))
                end = int(mmss_match.group(3)) * 60 + int(mmss_match.group(4))
                desc = v[mmss_match.end():].strip().lstrip("- ")
            elif sec_match:
                start = float(sec_match.group(1))
                end = float(sec_match.group(2))
                desc = v[sec_match.end():].strip().lstrip("- ")
            else:
                continue  # Skip if no timestamp found
            parsed.append({"start_seconds": start, "end_seconds": end, "description": desc, "type": "visual"})
        elif isinstance(v, dict):
            parsed.append(v)

    if not parsed:
        return {"error": "No valid timestamps found in violations"}

    # Sort by start time
    parsed.sort(key=lambda x: x.get("start_seconds", 0))

    # Merge overlapping or close segments (within 1.5s gap)
    MERGE_GAP = 1.5
    merged = [parsed[0].copy()]
    for seg in parsed[1:]:
        last = merged[-1]
        if seg["start_seconds"] <= last["end_seconds"] + MERGE_GAP:
            # Merge: extend end time, combine descriptions
            last["end_seconds"] = max(last["end_seconds"], seg["end_seconds"])
            last_desc = last.get("description", "")
            new_desc = seg.get("description", "")
            if new_desc and new_desc not in last_desc:
                last["description"] = f"{last_desc}; {new_desc}"[:300]
        else:
            merged.append(seg.copy())

    # Extract one clip per merged segment
    os.makedirs("assets/clips", exist_ok=True)
    clips = []

    for i, v in enumerate(merged):
        start = v.get("start_seconds", 0)
        end = v.get("end_seconds", start + 3)
        # Add 0.5s padding before/after for context
        padded_start = max(0, start - 0.5)
        duration = (end - start) + 1.0  # +1s for padding
        clip_path = f"assets/clips/violation_{i}_{int(start)}s_{int(end)}s.mp4"

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(padded_start),
            "-i", video_path,
            "-t", str(duration),
            "-c", "copy",
            clip_path,
        ]

        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
            if os.path.exists(clip_path):
                clips.append({
                    "index": i,
                    "start": start,
                    "end": end,
                    "type": v.get("type", "visual"),
                    "description": v.get("description", ""),
                    "clip_path": clip_path,
                })
        except Exception as e:
            logger.error(f"Failed to extract clip {i}: {e}")

    logger.info(f"Merged {len(parsed)} violations → {len(merged)} segments → {len(clips)} clips")
    return {"clips": clips, "merged_count": len(merged), "original_count": len(parsed)}


@tool
def verify_violations(violations: list, market: str, platform: str):
    """Verify flagged violations are based on real regulations using Tavily search."""
    from shared.clients import tavily

    if tavily is None:
        return {"error": "Tavily client not available"}

    verified = []
    for v in violations[:5]:
        result = tavily.search(
            f"{market} {platform} advertising regulation: {v}",
            max_results=3,
            search_depth="basic",
        )
        sources = [r["url"] for r in result.get("results", [])]
        verified.append({
            "violation": v,
            "confirmed": len(sources) > 0,
            "sources": sources[:2],
        })

    confirmed_count = sum(1 for v in verified if v["confirmed"])
    return {
        "verified": verified,
        "confidence": "high" if confirmed_count == len(verified) else "medium",
        "confirmed_ratio": f"{confirmed_count}/{len(verified)}",
    }
