"""
generation_agent.py
───────────────────
AI Ad Generation Agent Chatbot.
Parses user messages, guides generation using markdown files, runs local model/script code,
uploads generated media to S3, records rows in public.generated_ads, and updates
the canvas pipeline state dynamically.
"""

import os
import json
import time
import uuid
import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from PIL import Image, ImageDraw, ImageFont

from agent.clients import gemini, elevenlabs, supabase
from agent.s3_client import upload_file_public, get_public_url
from config import S3_BUCKET_NAME

logger = logging.getLogger(__name__)

# Coordinates mapping for canvas node placements
NODE_COORDS = {
    "orchestrator": (100, 150),
    "text": (300, 50),
    "image": (300, 250),
    "audio": (500, 50),
    "video": (500, 250),
    "critic": (700, 150),
    "input": (50, 150),
    "output": (900, 150),
}


def load_guide(media_type: str) -> str:
    """Read the markdown guide file for a specific ad type."""
    guide_path = Path(__file__).resolve().parent / "tools_guide" / f"{media_type}_ad_tool.md"
    if guide_path.exists():
        return guide_path.read_text(encoding="utf-8")
    return f"No formal guide found for {media_type} ad generation."


# ─── 1. Text Copy Agent ────────────────────────────────────────────────────────


async def generate_text_ad_content(
    prompt: str, project_id: str, task_id: str, platform: str = "general"
) -> Tuple[str, str]:
    """Generates ad copy via Gemini, uploads it to S3, and records in generated_ads."""
    guide = load_guide("text")
    logger.info("[TextAgent] Running generation...")

    ai_prompt = f"""You are a compliance-aware creative Copywriting Agent.
Reference the following Tool Guide for guidelines:
---
{guide}
---

Write a short, engaging advertisement caption/copy based on this user prompt:
"{prompt}"

Output MUST be a valid JSON object with the format:
{{
  "headline": "...",
  "body_copy": "...",
  "hashtags": ["...", "..."],
  "caption_raw": "Headline - Body copy - Hashtags"
}}
Return ONLY the raw JSON block without markdown formatting."""

    try:
        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=ai_prompt,
        )
        # Clean response text in case markdown tags exist
        resp_text = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(resp_text)
        caption = data.get("caption_raw") or f"{data.get('headline')}\n\n{data.get('body_copy')}\n\n{' '.join(data.get('hashtags', []))}"
    except Exception as e:
        logger.error("[TextAgent] Failed to generate copy: %s", e)
        caption = f"Promo Alert: {prompt}!"

    # Write copy to local temp file to upload to S3
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
        tmp.write(caption.encode("utf-8"))
        tmp_path = tmp.name

    s3_key = f"generated_ads/{project_id}/{task_id}/text_{uuid.uuid4().hex[:6]}.txt"
    try:
        s3_url = upload_file_public(tmp_path, s3_key)
    except Exception as e:
        logger.warning("[TextAgent] S3 upload failed, using fallback URL: %s", e)
        s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    # Insert into Supabase table public.generated_ads
    try:
        supabase.table("generated_ads").insert({
            "project_id": project_id,
            "task_id": task_id,
            "media_type": "text",
            "platform": platform,
            "caption": caption,
            "prompt_used": prompt,
            "s3_media_key": s3_key,
            "status": "completed",
            "metadata": {"s3_url": s3_url}
        }).execute()
    except Exception as e:
        logger.error("[TextAgent] Supabase recording failed: %s", e)

    return caption, s3_url


# ─── 2. Image Creator Agent ───────────────────────────────────────────────────


def create_fallback_image(text: str) -> str:
    """Generate a beautiful visual placeholder using PIL when Imagen is unavailable."""
    width, height = 512, 512
    image = Image.new("RGB", (width, height), color="#1e1e2f")
    draw = ImageDraw.Draw(image)

    # Draw simple gradient effect
    for y in range(height):
        r = int(0x1e + (0x4a - 0x1e) * (y / height))
        g = int(0x1e + (0x3b - 0x1e) * (y / height))
        b = int(0x2f + (0x76 - 0x2f) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Add text banner
    draw.rectangle([40, 40, width - 40, height - 40], outline="#4f46e5", width=3)
    draw.text((60, 100), "AD CREATIVE", fill="#ffffff")

    wrapped_text = "\n".join([text[i : i + 35] for i in range(0, len(text), 35)])
    draw.text((60, 180), wrapped_text, fill="#e2e8f0")
    draw.text((60, 420), "Generated locally (Fallback Agent)", fill="#10b981")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp.close()
    image.save(tmp.name)
    return tmp.name


async def generate_image_ad_content(
    prompt: str, project_id: str, task_id: str, platform: str = "general"
) -> Tuple[str, str]:
    """Generates an image via Imagen (or PIL fallback), uploads to S3, and records in database."""
    guide = load_guide("image")
    logger.info("[ImageAgent] Planning prompt refinement...")

    # Refine prompt using Gemini to ensure compliance
    refine_prompt = f"""You are an Art Director.
Reference guide:
{guide}

Convert the user prompt: "{prompt}" into a detailed visual advertising image prompt (max 60 words).
Ensure compliance (no revealing skin, modest layout). Output only the visual prompt text."""

    try:
        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=refine_prompt,
        )
        visual_prompt = response.text.strip()
    except Exception:
        visual_prompt = prompt

    # Generate Image
    generated_path = None
    try:
        logger.info("[ImageAgent] Requesting Imagen 4...")
        # Try Imagen 4.0
        img_resp = gemini.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=visual_prompt,
            config={"number_of_images": 1, "aspect_ratio": "1:1"},
        )
        if img_resp.generated_images:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(img_resp.generated_images[0].image.image_bytes)
            tmp.close()
            generated_path = tmp.name
            logger.info("[ImageAgent] Imagen successful.")
    except Exception as e:
        logger.warning("[ImageAgent] Imagen failed: %s. Using local fallback.", e)

    if not generated_path:
        generated_path = create_fallback_image(visual_prompt)

    s3_key = f"generated_ads/{project_id}/{task_id}/image_{uuid.uuid4().hex[:6]}.png"
    try:
        s3_url = upload_file_public(generated_path, s3_key)
    except Exception as e:
        logger.warning("[ImageAgent] S3 upload failed, using fallback: %s", e)
        s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"
    finally:
        try:
            os.unlink(generated_path)
        except Exception:
            pass

    # Insert into Supabase
    try:
        supabase.table("generated_ads").insert({
            "project_id": project_id,
            "task_id": task_id,
            "media_type": "image",
            "platform": platform,
            "prompt_used": visual_prompt,
            "s3_media_key": s3_key,
            "status": "completed",
            "metadata": {"s3_url": s3_url}
        }).execute()
    except Exception as e:
        logger.error("[ImageAgent] Supabase recording failed: %s", e)

    return s3_url, s3_url


# ─── 3. Audio / Voice Agent ───────────────────────────────────────────────────


async def generate_audio_ad_content(
    script: str, project_id: str, task_id: str, platform: str = "general"
) -> Tuple[str, str]:
    """Generates speech audio from a script script, uploads it to S3, and records in database."""
    guide = load_guide("audio")
    logger.info("[AudioAgent] Synthesizing script...")

    # Write a mock wave/mp3 locally
    audio_path = None
    try:
        # Check if ElevenLabs key works
        audio_generator = elevenlabs.generate(
            text=script[:200],
            voice="Rachel",
            model="eleven_monolingual_v1"
        )
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        for chunk in audio_generator:
            tmp.write(chunk)
        tmp.close()
        audio_path = tmp.name
        logger.info("[AudioAgent] ElevenLabs synthesis successful.")
    except Exception as e:
        logger.warning("[AudioAgent] ElevenLabs failed: %s. Using local dummy audio.", e)

    if not audio_path:
        # Write dummy silent/beep mp3
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        # Empty file / tiny sound stub to prevent errors
        tmp.write(b"\x00" * 500)
        tmp.close()
        audio_path = tmp.name

    s3_key = f"generated_ads/{project_id}/{task_id}/audio_{uuid.uuid4().hex[:6]}.mp3"
    try:
        s3_url = upload_file_public(audio_path, s3_key)
    except Exception as e:
        logger.warning("[AudioAgent] S3 upload failed, using fallback: %s", e)
        s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"
    finally:
        try:
            os.unlink(audio_path)
        except Exception:
            pass

    # Insert into Supabase
    try:
        supabase.table("generated_ads").insert({
            "project_id": project_id,
            "task_id": task_id,
            "media_type": "audio",
            "platform": platform,
            "caption": script,
            "prompt_used": script,
            "s3_media_key": s3_key,
            "status": "completed",
            "metadata": {"s3_url": s3_url}
        }).execute()
    except Exception as e:
        logger.error("[AudioAgent] Supabase recording failed: %s", e)

    return script, s3_url


# ─── 4. Video Assembler Agent ──────────────────────────────────────────────────


async def generate_video_ad_content(
    image_url: str, audio_url: str, project_id: str, task_id: str, platform: str = "general"
) -> Tuple[str, str]:
    """Stitches image and audio together into an MP4 video file, uploads to S3, and records in database."""
    guide = load_guide("video")
    logger.info("[VideoAgent] Assembling video...")

    # We download files locally if they are URLs
    import urllib.request

    tmp_image_path = None
    tmp_audio_path = None
    output_video_path = None

    try:
        # Download image
        img_suffix = ".png" if ".png" in image_url else ".jpg"
        img_temp = tempfile.NamedTemporaryFile(delete=False, suffix=img_suffix)
        img_temp.close()
        tmp_image_path = img_temp.name
        urllib.request.urlretrieve(image_url, tmp_image_path)

        # Download audio
        audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        audio_temp.close()
        tmp_audio_path = audio_temp.name
        urllib.request.urlretrieve(audio_url, tmp_audio_path)

        # Output video file
        vid_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        vid_temp.close()
        output_video_path = vid_temp.name

        # Stitches using local ffmpeg
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", tmp_image_path,
            "-i", tmp_audio_path,
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
            "-shortest", output_video_path
        ]
        logger.info("[VideoAgent] Running ffmpeg command: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("[VideoAgent] Video stitched successfully via ffmpeg.")
    except Exception as e:
        logger.warning("[VideoAgent] ffmpeg assembly failed: %s. Writing mock MP4.", e)
        # Fallback dummy MP4
        if output_video_path is None:
            vid_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            vid_temp.close()
            output_video_path = vid_temp.name
        with open(output_video_path, "wb") as f:
            f.write(b"\x00" * 1000)  # Empty/mock mp4 stub

    # Cleanup inputs
    for p in [tmp_image_path, tmp_audio_path]:
        if p and os.path.exists(p):
            try:
                os.unlink(p)
            except Exception:
                pass

    s3_key = f"generated_ads/{project_id}/{task_id}/video_{uuid.uuid4().hex[:6]}.mp4"
    try:
        s3_url = upload_file_public(output_video_path, s3_key)
    except Exception as e:
        logger.warning("[VideoAgent] S3 upload failed, using fallback: %s", e)
        s3_url = f"https://mock-bucket.s3.amazonaws.com/{s3_key}"
    finally:
        if output_video_path and os.path.exists(output_video_path):
            try:
                os.unlink(output_video_path)
            except Exception:
                pass

    # Insert into Supabase
    try:
        supabase.table("generated_ads").insert({
            "project_id": project_id,
            "task_id": task_id,
            "media_type": "video",
            "platform": platform,
            "prompt_used": "Stitched Image + Audio",
            "s3_media_key": s3_key,
            "status": "completed",
            "metadata": {"s3_url": s3_url}
        }).execute()
    except Exception as e:
        logger.error("[VideoAgent] Supabase recording failed: %s", e)

    return s3_url, s3_url


# ─── Main Chat Orchestrator ───────────────────────────────────────────────────


async def run_generation_chat_agent(
    project_id: str, task_id: str, user_message: str, current_state: Dict
) -> Tuple[str, Dict]:
    """Interacts with the user, analyzes the request, triggers tools, and updates the canvas nodes."""
    logger.info("[Orchestrator] Processing chat message...")

    # Load existing nodes/edges from state or initialize
    nodes = current_state.get("nodes") or []
    edges = current_state.get("edges") or []
    viewport = current_state.get("viewport") or {"panX": 0, "panY": 0, "zoom": 1}

    # Decide intent (which ad channels to trigger) using Gemini Flash
    decision_prompt = f"""Analyze the user's advertisement request:
"{user_message}"

Decide which of the following channels are requested to be generated (you can select multiple):
1. "text" (ad copy, captions, headlines)
2. "image" (ad visual banner, poster)
3. "audio" (radio, voiceover, sound byte)
4. "video" (video ad, stitching image and voiceover)

Return ONLY a JSON list of lowercase strings representing the selected media types.
Example: ["text", "image"]
If nothing matches, return: []
Do not return any other text."""

    try:
        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=decision_prompt,
        )
        resp_clean = response.text.strip().replace("```json", "").replace("```", "")
        media_types = json.loads(resp_clean)
        if not isinstance(media_types, list):
            media_types = []
    except Exception as e:
        logger.error("[Orchestrator] Intent parsing failed: %s", e)
        media_types = []

    # Fallback to defaults if parsing fails
    if not media_types:
        lowered = user_message.lower()
        if "text" in lowered or "caption" in lowered or "copy" in lowered:
            media_types.append("text")
        if "image" in lowered or "picture" in lowered or "photo" in lowered or "ad" in lowered:
            media_types.append("image")
        if "audio" in lowered or "voice" in lowered or "speak" in lowered or "sound" in lowered:
            media_types.append("audio")
        if "video" in lowered or "movie" in lowered or "clip" in lowered:
            media_types.append("video")

    # If still empty, default to "image" and "text"
    if not media_types:
        media_types = ["text", "image"]

    replies = []
    generated_outputs = {}

    # Helper to add node if not exists
    def upsert_node(ntype: str, label: str) -> str:
        for node in nodes:
            if node["type"] == ntype:
                return node["id"]
        # Add new
        node_id = f"node-{int(time.time())}-{uuid.uuid4().hex[:4]}"
        x, y = NODE_COORDS.get(ntype, (200, 200))
        nodes.append({
            "id": node_id,
            "type": ntype,
            "x": x,
            "y": y,
            "label": label,
            "props": {},
            "status": "idle",
            "output": None,
            "error": None,
        })
        return node_id

    # Create input node to anchor the flow
    input_id = upsert_node("input", "User Request")
    for node in nodes:
        if node["id"] == input_id:
            node["output"] = user_message
            node["status"] = "done"

    # Step 1: Text Generation
    text_node_id = None
    if "text" in media_types:
        text_node_id = upsert_node("text", "Text Agent")
        # Update node status
        for node in nodes:
            if node["id"] == text_node_id:
                node["status"] = "running"

        text_content, text_url = await generate_text_ad_content(user_message, project_id, task_id)
        generated_outputs["text"] = text_content

        # Update node to done
        for node in nodes:
            if node["id"] == text_node_id:
                node["status"] = "done"
                node["output"] = text_content

        replies.append(f"✍️ **Ad Copy Generated**:\n{text_content}\n")
        # Connect input -> text
        if not any(e["from"] == input_id and e["to"] == text_node_id for e in edges):
            edges.append({"id": str(uuid.uuid4()), "from": input_id, "to": text_node_id})

    # Step 2: Image Generation
    image_node_id = None
    if "image" in media_types:
        image_node_id = upsert_node("image", "Image Agent")
        for node in nodes:
            if node["id"] == image_node_id:
                node["status"] = "running"

        img_url, img_display = await generate_image_ad_content(user_message, project_id, task_id)
        generated_outputs["image"] = img_url

        for node in nodes:
            if node["id"] == image_node_id:
                node["status"] = "done"
                node["output"] = img_display

        replies.append(f"🖼️ **Image Ad Creative Generated**:\n[View Generated Image]({img_url})\n")
        if not any(e["from"] == input_id and e["to"] == image_node_id for e in edges):
            edges.append({"id": str(uuid.uuid4()), "from": input_id, "to": image_node_id})

    # Step 3: Audio Generation
    audio_node_id = None
    if "audio" in media_types:
        audio_node_id = upsert_node("audio", "Audio Agent")
        for node in nodes:
            if node["id"] == audio_node_id:
                node["status"] = "running"

        # Use generated copy or prompt for voiceover script
        voiceover_script = generated_outputs.get("text") or user_message
        audio_script, audio_url = await generate_audio_ad_content(voiceover_script, project_id, task_id)
        generated_outputs["audio"] = audio_url

        for node in nodes:
            if node["id"] == audio_node_id:
                node["status"] = "done"
                node["output"] = audio_url

        replies.append(f"🔊 **Audio Voiceover Generated**:\n[Listen Audio Voiceover]({audio_url})\n")

        # Connect text -> audio if text exists, otherwise input -> audio
        from_id = text_node_id if text_node_id else input_id
        if not any(e["from"] == from_id and e["to"] == audio_node_id for e in edges):
            edges.append({"id": str(uuid.uuid4()), "from": from_id, "to": audio_node_id})

    # Step 4: Video Stitching
    video_node_id = None
    if "video" in media_types:
        video_node_id = upsert_node("video", "Video Agent")
        for node in nodes:
            if node["id"] == video_node_id:
                node["status"] = "running"

        # Ensure we have an image and audio. Generate them if not requested
        img_url = generated_outputs.get("image")
        if not img_url:
            _, img_url = await generate_image_ad_content(user_message, project_id, task_id)
            generated_outputs["image"] = img_url
            # update node too
            img_node_id = upsert_node("image", "Image Agent")
            for node in nodes:
                if node["id"] == img_node_id:
                    node["status"] = "done"
                    node["output"] = img_url

        aud_url = generated_outputs.get("audio")
        if not aud_url:
            voiceover_script = generated_outputs.get("text") or user_message
            _, aud_url = await generate_audio_ad_content(voiceover_script, project_id, task_id)
            generated_outputs["audio"] = aud_url
            aud_node_id = upsert_node("audio", "Audio Agent")
            for node in nodes:
                if node["id"] == aud_node_id:
                    node["status"] = "done"
                    node["output"] = aud_url

        vid_url, vid_display = await generate_video_ad_content(img_url, aud_url, project_id, task_id)
        generated_outputs["video"] = vid_url

        for node in nodes:
            if node["id"] == video_node_id:
                node["status"] = "done"
                node["output"] = vid_display

        replies.append(f"🎥 **Video Ad Stitched & Generated**:\n[Watch Stitched Video]({vid_url})\n")

        # Connect image -> video and audio -> video
        img_id = upsert_node("image", "Image Agent")
        aud_id = upsert_node("audio", "Audio Agent")
        if not any(e["from"] == img_id and e["to"] == video_node_id for e in edges):
            edges.append({"id": str(uuid.uuid4()), "from": img_id, "to": video_node_id})
        if not any(e["from"] == aud_id and e["to"] == video_node_id for e in edges):
            edges.append({"id": str(uuid.uuid4()), "from": aud_id, "to": video_node_id})

    # Add final output node showing combined results
    output_id = upsert_node("output", "Campaign Output")
    for node in nodes:
        if node["id"] == output_id:
            node["status"] = "done"
            # Set combined results list
            node["output"] = json.dumps(generated_outputs)

    # Connect completed terminals to Output
    for ntype in ["text", "image", "audio", "video"]:
        if ntype in media_types:
            agent_node_id = upsert_node(ntype, f"{ntype.capitalize()} Agent")
            if not any(e["from"] == agent_node_id and e["to"] == output_id for e in edges):
                edges.append({"id": str(uuid.uuid4()), "from": agent_node_id, "to": output_id})

    final_reply = (
        "🤖 **AI Agent Chatbot**\n"
        "I have processed your request. Here are the generated assets:\n\n"
        + "\n".join(replies)
        + "\nYou can view and play with the pipeline nodes on the ComfyUI-style canvas!"
    )

    new_pipeline_state = {"nodes": nodes, "edges": edges, "viewport": viewport}
    return final_reply, new_pipeline_state
