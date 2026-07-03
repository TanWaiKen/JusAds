"""
Quick standalone test for the video agent.
Run from backend/: python test_video_agent.py
"""
import asyncio
import sys

# Load env before anything else
from config import VERTEX_PROJECT_ID

print(f"VERTEX_PROJECT_ID: {'SET' if VERTEX_PROJECT_ID else 'NOT SET'}")

if not VERTEX_PROJECT_ID:
    print("ERROR: VERTEX_PROJECT_ID not set in .env. Cannot test Veo.")
    sys.exit(1)

from jusads_generation.agents.video_agent import generate


async def main():
    print("\n--- Testing Video Agent (Veo 3.0) ---\n")

    result = await generate(
        brief="A refreshing bubble tea being poured into a glass with ice on a sunny day",
        project_id="test-project-id",
        task_id="test-task-id",
        platform="tiktok",
        rules={
            "aspect_ratio": "9:16",
            "max_duration_seconds": 8,
            "max_dimension": 1080,
        },
        reference_parts=[],
    )

    print("\n--- RESULT ---")
    print(f"Status: {result['status']}")
    print(f"Media type: {result['media_type']}")
    print(f"Platform: {result['platform']}")
    print(f"S3 key: {result.get('s3_media_key')}")
    print(f"Public URL: {result.get('public_url')}")
    print(f"Error: {result.get('error')}")
    print(f"Ad ID: {result.get('ad_id')}")

    if result["status"] == "completed":
        print("\n✅ VIDEO GENERATION PASSED")
    else:
        print(f"\n❌ VIDEO GENERATION FAILED: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
