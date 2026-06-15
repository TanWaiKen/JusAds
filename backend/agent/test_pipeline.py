#!/usr/bin/env python3
"""
test_pipeline.py
────────────────
Integration tests for the compliance pipeline.
Tests all 4 media types: text, image, audio, video.

Since the pipeline has human-in-the-loop (interrupt), we test by:
1. Running the full pipeline with a checkpointer
2. The pipeline will pause at human_review
3. We inspect the state at that point

Run from backend/: python -m agent.test_pipeline
"""

import os
import sys
import json
import traceback

# Setup path and env
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from langgraph.checkpoint.memory import MemorySaver
from agent.data_model import ComplianceState
from agent.pipeline import _graph


# Compile with checkpointer for interrupt support
memory = MemorySaver()
test_pipeline = _graph.compile(checkpointer=memory)


def run_test(name: str, state: ComplianceState, thread_id: str):
    """Run a single pipeline test. Pipeline will interrupt at human_review."""
    print(f"\n{'=' * 60}")
    print(f"TEST: {name}")
    print(f"  Media: {state.media_type}, Market: {state.market}, Platform: {state.platform}")
    if state.media_type == "text":
        print(f"  Input: {state.text_input[:80]}...")
    else:
        print(f"  File: {state.input_path}")
    print(f"{'=' * 60}")

    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Run until interrupt (human_review node)
        result = test_pipeline.invoke(state, config)

        # Check state
        if isinstance(result, dict):
            status = result.get("status", "unknown")
            compliance_result = result.get("result", {})
        else:
            status = result.status
            compliance_result = result.result

        print(f"\n  ✅ Reached: {status}")
        print(f"  Risk: {compliance_result.get('risk_percentage', '?')}% ({compliance_result.get('risk_level', '?')})")

        indicators = compliance_result.get("high_risk_indicator", [])
        if indicators:
            print(f"  Violations: {indicators[:3]}{'...' if len(indicators) > 3 else ''}")

        verification = compliance_result.get("verification", {})
        if verification:
            print(f"  Verification: {verification.get('confirmed_ratio', '?')} confirmed ({verification.get('confidence', '?')})")

        evaluation = compliance_result.get("evaluation", {})
        if evaluation:
            print(f"  Bias detected: {evaluation.get('bias_detected', '?')}")
            print(f"  Hallucination score: {evaluation.get('hallucination_score', '?')}/5")
            print(f"  Overall pass: {evaluation.get('overall_pass', '?')}")

        if compliance_result.get("error"):
            print(f"  ⚠️  Error: {compliance_result['error']}")

        return True

    except Exception as e:
        print(f"\n  ❌ Failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        return False


def main():
    results = []

    # Test 1: Text compliance
    results.append(run_test(
        "Text Ad (non-compliant)",
        ComplianceState(
            session_id="test_text",
            media_type="text",
            input_path="",
            text_input="Try our skin whitening cream! 4 out of 5 gynecologists recommend it. From your pits to your private areas, stay fresh all day!",
            market="malaysia",
            platform="tiktok",
            ethnicity="malay",
            age_group="gen_z",
        ),
        thread_id="test_text_001",
    ))

    # Test 2: Image compliance
    image_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "images", "noncompliant_armpit_ad.png")
    if os.path.exists(image_path):
        results.append(run_test(
            "Image Ad (non-compliant armpit)",
            ComplianceState(
                session_id="test_image",
                media_type="image",
                input_path=image_path,
                text_input="",
                market="malaysia",
                platform="meta",
                ethnicity="malay",
                age_group="millennial",
            ),
            thread_id="test_image_001",
        ))
    else:
        print(f"\n⚠️  Skipping image test — file not found: {image_path}")

    # Test 3: Audio compliance
    audio_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "audio_ads_aws", "output", "vo", "vo_scene_1.mp3")
    if os.path.exists(audio_path):
        results.append(run_test(
            "Audio Ad (voice-over)",
            ComplianceState(
                session_id="test_audio",
                media_type="audio",
                input_path=audio_path,
                text_input="",
                market="malaysia",
                platform="tiktok",
                ethnicity="chinese",
                age_group="gen_z",
            ),
            thread_id="test_audio_001",
        ))
    else:
        print(f"\n⚠️  Skipping audio test — file not found: {audio_path}")

    # Test 4: Video compliance
    video_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Test Video.mp4")
    if os.path.exists(video_path):
        results.append(run_test(
            "Video Ad (test video)",
            ComplianceState(
                session_id="test_video",
                media_type="video",
                input_path=video_path,
                text_input="",
                market="malaysia",
                platform="tiktok",
                ethnicity="malay",
                age_group="gen_z",
            ),
            thread_id="test_video_001",
        ))
    else:
        print(f"\n⚠️  Skipping video test — file not found: {video_path}")

    # Summary
    print(f"\n{'=' * 60}")
    passed = sum(1 for r in results if r)
    print(f"Results: {passed}/{len(results)} tests passed")
    print(f"{'=' * 60}")

    if not all(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
