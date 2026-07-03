# NIMBUS Automated Ads Generation Pipeline Handoff Documentation

This document maps the requirements from the **NIMBUS Automated Ads Generation Pipeline** architecture diagram to the current codebase, highlights the architectural gap in video generation (using FFMPEG stitching vs. Google Veo 3.1), and provides an integration blueprint for migrating to true Google Veo video synthesis.

---

## 1. NIMBUS Pipeline Architecture & Requirements Mapping

Based on the NIMBUS system diagram, the pipeline consists of 5 core phases:

| Phase | Component in Diagram | Current Codebase Mapping | Status |
| :--- | :--- | :--- | :--- |
| **System Input (Blue)** | Requirements Scoping & Data Validation | Tasks table & Onboarding Profile | `Implemented` |
| **Text Gen (Orange)** | Ad Script Writing / Storyboard planning | Copywriting Text Agent via Gemini | `Implemented` |
| **System Guardrails (Red)** | Brand & Cultural Compliance Auditor | Custom guide checks & compliance routes | `Implemented` |
| **Asset Rendering (Green)** | Media Generation Orchestration: <br>- Narrative Voice Gen <br>- Audio Gen (Sound effects) <br>- Video Gen | - ElevenLabs v3 TTS for voice <br>- ElevenLabs SFX/Local bed fallback <br>- **FFMPEG Image + Audio Stitching** | `Alternative Implemented` (Needs Veo Upgrade) |
| **Integrations (Black)** | External APIs (Gemini, ElevenLabs, S3, Supabase) and target platforms | Boto3 (S3), Supabase Client, google-genai | `Implemented` |

---

## 2. The Video Generation Gap: FFMPEG vs. Google Veo 3.1

### Current Implementation:
Currently, both `backend/agent/generation_agent.py` and `backend/jusads_generation/agents/video_agent.py` perform pseudo-video generation:
1.  They call Gemini to refine a visual prompt.
2.  They generate a static key-frame image (using Imagen 4.0 or PIL fallback).
3.  They generate audio/voiceover (using ElevenLabs Multilingual v3).
4.  They call `ffmpeg` locally to stitch the static image and audio track together:
    ```bash
    ffmpeg -y -loop 1 -i image.png -i voice.mp3 -c:v libx264 -tune stillimage -c:a aac -pix_fmt yuv420p -shortest video.mp4
    ```

### Architectural Goal:
The NIMBUS specifications require **True Video Generation** using **Google Veo 3.1** via Google Vertex AI to create dynamic 5-second video scenes rather than simple static-frame slideshows.

---

## 3. Migration Blueprint: Integrating Google Veo 3.1

Google's newest `google-genai` SDK supports video generation using Veo models (such as `veo-2.0-generate-001` or `veo-3.1`). Here is the blueprint to transition the video agent.

### A. Veo 3.1 API Reference Call
To generate dynamic videos directly from text prompts using the Google GenAI SDK:
```python
from google import genai
from google.genai import types

client = genai.Client()

def generate_veo_video(prompt: str, aspect_ratio: str = "9:16", duration_seconds: int = 5) -> bytes:
    """Generate a dynamic MP4 video file from a prompt using Google Veo."""
    response = client.models.generate_videos(
        model="veo-3.0-generate-001", # Target Veo production model
        prompt=prompt,
        config=types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio, # e.g. "9:16" or "16:9"
            duration_seconds=duration_seconds, # Bounded by Rules (Req 7.1)
            person_generation="allow_adult",
            video_format="mp4"
        )
    )
    # The API returns the raw video bytes
    if not response.generated_videos:
        raise RuntimeError("Veo API completed but returned no video output.")
        
    return response.generated_videos[0].video.video_bytes
```

Another Sample
```python
async def generate_replacement_clip(
    start_image_path: str,
    end_image_path: str,
    duration_seconds: float,
) -> str:
    """Generate a video clip from two images using Google Veo.

    Uses Google Veo (via Vertex AI) to generate a video that transitions
    from the start image to the end image over the specified duration.
    Enforces a minimum duration of 4.0 seconds (Veo API constraint).

    Args:
        start_image_path: Path to the start reference image (PNG/JPEG).
        end_image_path: Path to the end reference image (PNG/JPEG).
        duration_seconds: Desired clip duration in seconds. Will be clamped
            to at least 4.0 seconds (Veo minimum).

    Returns:
        Path to the generated MP4 clip.

    Raises:
        RuntimeError: If the Google Veo API call fails.

    Validates: Requirements 2.3, 2.4, 2.8
    """
    if not VERTEX_PROJECT_ID:
        raise RuntimeError(
            "VERTEX_PROJECT_ID environment variable is not set"
        )

    if not os.path.exists(start_image_path):
        raise RuntimeError(
            f"Start image not found: {start_image_path}"
        )
    if not os.path.exists(end_image_path):
        raise RuntimeError(
            f"End image not found: {end_image_path}"
        )

    # Enforce Veo minimum duration of 4.0 seconds
    veo_duration = max(VEO_MIN_DURATION_SECONDS, duration_seconds)

    # Round to nearest integer for Veo API (accepts integer seconds)
    veo_duration_int = int(round(veo_duration))
    # Ensure at least 4 seconds after rounding
    veo_duration_int = max(4, veo_duration_int)

    try:
        # Initialize the Vertex AI client for Veo (requires us-central1)
        veo_client = genai.Client(
            vertexai=True,
            project=VERTEX_PROJECT_ID,
            location="us-central1",
        )

        # Read the reference images
        with open(start_image_path, "rb") as f:
            start_image_bytes = f.read()
        with open(end_image_path, "rb") as f:
            end_image_bytes = f.read()

        # Determine MIME types
        start_ext = os.path.splitext(start_image_path)[1].lower()
        end_ext = os.path.splitext(end_image_path)[1].lower()
        start_mime = "image/png" if start_ext == ".png" else "image/jpeg"
        end_mime = "image/png" if end_ext == ".png" else "image/jpeg"

        # Create the image references for Veo
        start_image = types.Image(
            image_bytes=start_image_bytes,
            mime_type=start_mime,
        )
        last_frame_image = types.Image(
            image_bytes=end_image_bytes,
            mime_type=end_mime,
        )

        # Configure Veo generation:
        # - image (first frame) goes in GenerateVideosSource
        # - last_frame goes in GenerateVideosConfig
        source = types.GenerateVideosSource(
            image=start_image,
            prompt=(
                "Smooth cinematic transition maintaining visual consistency, "
                "natural motion, and scene continuity."
            ),
        )

        config = types.GenerateVideosConfig(
            aspect_ratio="16:9",
            number_of_videos=1,
            duration_seconds=veo_duration_int,
            person_generation="allow_all",
            generate_audio=False,
            resolution="720p",
            last_frame=last_frame_image,
        )

        # Submit the video generation request
        logger.info(
            f"Submitting Veo generation request: "
            f"duration={veo_duration_int}s, "
            f"start_image={start_image_path}, "
            f"end_image={end_image_path}"
        )

        operation = veo_client.models.generate_videos(
            model="veo-3.1-lite-generate-001",
            source=source,
            config=config,
        )

        # Poll for completion
        while not operation.done:
            logger.info("Video has not been generated yet. Check again in 10 seconds...")
            time.sleep(10)
            operation = veo_client.operations.get(operation)

        response = operation.result
        if not response:
            raise RuntimeError("Error occurred while generating video.")

        generated_videos = response.generated_videos
        if not generated_videos:
            raise RuntimeError("No videos were generated.")

        generated_video = generated_videos[0]
        if not generated_video.video or not generated_video.video.video_bytes:
            raise RuntimeError("Veo generated video has no video bytes")

        # Save the generated clip
        output_dir = os.path.dirname(start_image_path)
        output_filename = f"veo_clip_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.join(output_dir, output_filename)

        with open(output_path, "wb") as f:
            f.write(generated_video.video.video_bytes)

        logger.info(
            f"Veo generated clip saved to {output_path} "
            f"(requested {veo_duration_int}s)"
        )
        return output_path

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Google Veo clip generation failed: {e}"
        ) from e


def build_compliance_prompt(category: str, description: str) -> str:
    """Build a compliance-specific prompt for Nano Banana frame regeneration.

    Constructs a prompt that instructs the image generation model to produce
    a compliant version of the frame, addressing the specific violation.

    Args:
        category: The violation category (e.g., "Sexual/Explicit").
        description: Human-readable description of the violation.

    Returns:
        A prompt string for the Nano Banana API.
    """
    return (
        f"Regenerate this image to be culturally and regulatory compliant. "
        f"Remove or replace content that violates the '{category}' guideline. "
        f"Specifically address: {description}. "
        f"Maintain the overall composition, lighting, and style while ensuring "
        f"the output is appropriate for all audiences."
    )
```


### B. Updated Video Agent Workflow (With Veo + Voiceover Merge)
Instead of stitching a static image, the upgraded `video_agent.py` will:
1.  **Generate Dynamic Video**: Call the Veo model with the refined visual prompt.
2.  **Generate Narrative Voice**: Call ElevenLabs for the voiceover audio track.
3.  **Merge dynamic video + voiceover via FFMPEG**:
    ```bash
    ffmpeg -y -i veo_video.mp4 -i voiceover.mp3 -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 output.mp4
    ```

---

## 4. Human-In-The-Loop Approval Gate

As shown in the red box of the NIMBUS diagram, advertisements must go through a **Human Approval** stage.
*   The generated ad is initially stored with `status = "draft"` or `"completed"`.
*   The project owner can inspect the output on the Generation Canvas.
*   Once reviewed, the owner clicks **"Publish"** (Human approval), which updates the record `status = "published"` in Supabase and triggers the distribution hooks to TikTok, YouTube, or Shopee APIs.
