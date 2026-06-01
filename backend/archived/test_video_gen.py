"""Simple test: Generate a video with Veo 3.1 Lite using a start image and last_frame."""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import VERTEX_PROJECT_ID
from google import genai
from google.genai import types


def main():
    if not VERTEX_PROJECT_ID:
        print("ERROR: VERTEX_PROJECT_ID not set in .env")
        sys.exit(1)

    # Use remediated frames as start and end images
    start_image_path = "assets/remediated/regen_329703f3.png"
    end_image_path = "assets/remediated/regen_2a8933a0.png"

    if not os.path.exists(start_image_path):
        print(f"ERROR: Start image not found: {start_image_path}")
        sys.exit(1)
    if not os.path.exists(end_image_path):
        print(f"ERROR: End image not found: {end_image_path}")
        sys.exit(1)

    # Read start image
    with open(start_image_path, "rb") as f:
        start_image_bytes = f.read()

    start_ext = os.path.splitext(start_image_path)[1].lower()
    start_mime = "image/png" if start_ext == ".png" else "image/jpeg"

    print(f"Start image: {start_image_path} ({len(start_image_bytes)} bytes, {start_mime})")

    # Initialize client (Veo requires us-central1, must use vertexai=True)
    client = genai.Client(
        vertexai=True,
        project=VERTEX_PROJECT_ID,
        location="us-central1",
    )

    # Build source with start image
    source = types.GenerateVideosSource(
        image=types.Image(
            image_bytes=start_image_bytes,
            mime_type=start_mime,
        ),
        prompt=(
            "Smooth cinematic motion, maintaining visual consistency "
            "and natural movement. Keep the same style and lighting."
        ),
    )

    # Build config (no generate_audio — not supported in Developer API mode)
    with open(end_image_path, "rb") as f:
        end_image_bytes = f.read()
    end_ext = os.path.splitext(end_image_path)[1].lower()
    end_mime = "image/png" if end_ext == ".png" else "image/jpeg"
    print(f"Last frame: {end_image_path} ({len(end_image_bytes)} bytes, {end_mime})")

    config = types.GenerateVideosConfig(
        aspect_ratio="16:9",
        number_of_videos=1,
        duration_seconds=8,
        person_generation="allow_all",
        generate_audio=False,
        resolution="720p",
        last_frame=types.Image(
            image_bytes=end_image_bytes,
            mime_type=end_mime,
        ),
    )

    # Submit video generation request
    print(f"\nSubmitting Veo 3.1 Lite generation request...")
    print(f"  Model: veo-3.1-lite-generate-001")
    print(f"  Duration: 8s")
    print(f"  Resolution: 720p")
    print(f"  Aspect ratio: 16:9")
    print(f"  Last frame: enabled")
    print()

    operation = client.models.generate_videos(
        model="veo-3.1-lite-generate-001",
        source=source,
        config=config,
    )

    # Poll for completion
    elapsed = 0
    poll_interval = 10
    max_wait = 300

    while not operation.done:
        if elapsed >= max_wait:
            print(f"\nERROR: Timed out after {max_wait} seconds.")
            sys.exit(1)
        print(f"  Waiting... ({elapsed}s elapsed)")
        time.sleep(poll_interval)
        operation = client.operations.get(operation)
        elapsed += poll_interval

    # Check result
    response = operation.result
    if not response:
        print("\nERROR: Video generation completed but returned no result.")
        # Print the full operation for debugging
        print(f"Operation details: {operation}")
        sys.exit(1)

    generated_videos = response.generated_videos
    if not generated_videos:
        print("\nERROR: No videos were generated.")
        print(f"Full response: {response}")
        # Check if there's a blocked reason or error
        if hasattr(response, 'rai_media_filtered_count'):
            print(f"RAI filtered count: {response.rai_media_filtered_count}")
        if hasattr(response, 'rai_media_filtered_reasons'):
            print(f"RAI filtered reasons: {response.rai_media_filtered_reasons}")
        sys.exit(1)

    print(f"\nSuccess! Generated {len(generated_videos)} video(s).")

    # Save the generated video(s)
    os.makedirs("assets/test_output", exist_ok=True)
    for i, generated_video in enumerate(generated_videos):
        if generated_video.video and generated_video.video.video_bytes:
            output_path = f"assets/test_output/veo_test_{i}.mp4"
            with open(output_path, "wb") as f:
                f.write(generated_video.video.video_bytes)
            print(f"  Saved: {output_path} ({len(generated_video.video.video_bytes)} bytes)")
        else:
            print(f"  Video {i}: No video bytes available")

    print("\nDone!")


if __name__ == "__main__":
    main()
