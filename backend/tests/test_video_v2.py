"""
Quick standalone test for Video V2 (multi-scene storyboard).

Run from backend/:
    python test_video_v2.py          # Plan only (keyframes — no Veo needed)
    python test_video_v2.py --full   # Plan + Execute (requires Veo + ffmpeg)

Tests the two-phase flow:
  Phase 1 (plan_video): Director → keyframes → S3 upload. Fast, uses image quota only.
  Phase 2 (execute_video_plan): Downloads keyframes → Veo clips → subtitles → transitions → VO. Slow.
"""
import asyncio
import json
import sys
import time

# Load env before anything else
from config import VERTEX_PROJECT_ID

print(f"VERTEX_PROJECT_ID: {'SET' if VERTEX_PROJECT_ID else 'NOT SET'}")

if not VERTEX_PROJECT_ID:
    print("ERROR: VERTEX_PROJECT_ID not set in .env. Cannot test Video V2.")
    sys.exit(1)

from jusads_generation.agents.video_v2 import plan_video, execute_video_plan, generate

FULL_MODE = "--full" in sys.argv

TEST_BRIEF = "A young Malaysian Chinese woman discovers a new iced kopi drink at a trendy kopitiam, takes a sip, and smiles"
TEST_PROJECT = "test-video-v2-project"
TEST_TASK = "test-video-v2-task"
TEST_PLATFORM = "tiktok"
TEST_RULES = {
    "aspect_ratio": "9:16",
    "max_duration_seconds": 30,
    "max_dimension": 1080,
}


async def test_plan():
    """Phase 1: Plan the storyboard + keyframes (no Veo)."""
    print("\n" + "=" * 60)
    print("PHASE 1: plan_video (Director + Keyframes)")
    print("=" * 60 + "\n")

    start = time.time()
    try:
        plan = await plan_video(
            brief=TEST_BRIEF,
            project_id=TEST_PROJECT,
            task_id=TEST_TASK,
            platform=TEST_PLATFORM,
            rules=TEST_RULES,
            reference_parts=[],
            target_ethnicity="chinese",
        )
    except Exception as e:
        print(f"\n❌ PLAN FAILED: {e}")
        return None

    elapsed = time.time() - start
    scenes = plan.get("scenes") or []

    print(f"✅ Plan created in {elapsed:.1f}s")
    print(f"   Plan ID: {plan.get('plan_id')}")
    print(f"   Scenes: {len(scenes)}")
    print(f"   Aspect: {plan.get('aspect_ratio')}")
    print(f"   Ethnicity: {plan.get('target_ethnicity')}")
    print()

    for i, scene in enumerate(scenes):
        print(f"   Scene {i}:")
        print(f"     Shot: {scene.get('shot_type', '?')}")
        print(f"     Camera: {scene.get('camera_movement', '?')}")
        print(f"     Description: {scene.get('description', '')[:80]}...")
        print(f"     Subtitle: {scene.get('subtitle', '(none)')}")
        print(f"     Script: {scene.get('script', '(none)')}")
        print(f"     SFX: {scene.get('sfx', '(none)')}")
        print(f"     Duration: {scene.get('duration')}s")
        print(f"     Keyframe URL: {scene.get('keyframe_url', '(missing)')[:60]}...")
        print()

    if not scenes:
        print("❌ No scenes in plan!")
        return None

    missing_keyframes = [s for s in scenes if not s.get("keyframe_url")]
    if missing_keyframes:
        print(f"⚠️  {len(missing_keyframes)} scene(s) have no keyframe URL")

    print(f"✅ PHASE 1 PASSED ({len(scenes)} scenes planned, {elapsed:.1f}s)")
    return plan


async def test_execute(plan: dict):
    """Phase 2: Execute the plan (Veo + ffmpeg + VO). SLOW."""
    print("\n" + "=" * 60)
    print("PHASE 2: execute_video_plan (Veo + ffmpeg + voiceover)")
    print("=" * 60 + "\n")
    print("⏳ This is SLOW (each scene = one Veo API call, 30s–2min each)...\n")

    start = time.time()
    try:
        result = await execute_video_plan(
            plan=plan,
            project_id=TEST_PROJECT,
            task_id=TEST_TASK,
            platform=TEST_PLATFORM,
        )
    except Exception as e:
        print(f"\n❌ EXECUTE FAILED: {e}")
        return

    elapsed = time.time() - start

    print(f"\n--- RESULT ---")
    print(f"Status: {result['status']}")
    print(f"Media type: {result['media_type']}")
    print(f"Platform: {result['platform']}")
    print(f"S3 key: {result.get('s3_media_key')}")
    print(f"Public URL: {result.get('public_url')}")
    print(f"Error: {result.get('error')}")
    print(f"Ad ID: {result.get('ad_id')}")
    print(f"Time: {elapsed:.1f}s")

    if result["status"] == "completed":
        print(f"\n✅ PHASE 2 PASSED (video rendered in {elapsed:.1f}s)")
        print(f"   Watch it: {result.get('public_url')}")
    else:
        print(f"\n❌ PHASE 2 FAILED: {result.get('error')}")


async def test_oneshot():
    """Alternative: full one-shot generate() (plan + execute in one call)."""
    print("\n" + "=" * 60)
    print("ONE-SHOT: generate() (full pipeline, no human approval)")
    print("=" * 60 + "\n")
    print("⏳ Running full pipeline...\n")

    start = time.time()
    result = await generate(
        brief=TEST_BRIEF,
        project_id=TEST_PROJECT,
        task_id=TEST_TASK,
        platform=TEST_PLATFORM,
        rules=TEST_RULES,
        reference_parts=[],
        target_ethnicity="chinese",
        gender="female",
    )
    elapsed = time.time() - start

    print(f"\n--- RESULT ---")
    print(f"Status: {result['status']}")
    print(f"Public URL: {result.get('public_url')}")
    print(f"Error: {result.get('error')}")
    print(f"Time: {elapsed:.1f}s")

    if result["status"] == "completed":
        print(f"\n✅ ONE-SHOT PASSED ({elapsed:.1f}s)")
    else:
        print(f"\n❌ ONE-SHOT FAILED: {result.get('error')}")


async def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║   Video V2 Test — Multi-Scene Storyboard        ║")
    print(f"║   Mode: {'FULL (plan + execute)' if FULL_MODE else 'PLAN ONLY (no Veo render)'}   ║")
    print("╚══════════════════════════════════════════════════╝")

    # Always test planning (fast, image quota only)
    plan = await test_plan()

    if plan and FULL_MODE:
        # Only run the expensive Veo step if --full is passed
        await test_execute(plan)
    elif not FULL_MODE:
        print("\n" + "-" * 60)
        print("ℹ️  Skipping Phase 2 (Veo render). Run with --full to test execution.")
        print("    python test_video_v2.py --full")
        print("-" * 60)

    print("\n🏁 Done.")


if __name__ == "__main__":
    asyncio.run(main())
