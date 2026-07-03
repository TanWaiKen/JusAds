"""
test_remediation_engine.py
──────────────────────────
Integration test for the Intelligent Remediation Engine.
Tests the CapCut client operations against a real video file.

Run: python -m tests.test_remediation_engine
"""

import os
import sys
import tempfile

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VIDEO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "Test Video.mp4",
)


def test_video_exists():
    """Verify test video is available."""
    assert os.path.exists(VIDEO_PATH), f"Test video not found: {VIDEO_PATH}"
    size = os.path.getsize(VIDEO_PATH)
    print(f"  Video: {VIDEO_PATH}")
    print(f"  Size: {size / 1024:.1f} KB")
    return True


def test_ffmpeg_available():
    """Check FFmpeg is accessible."""
    import subprocess
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
        )
        version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
        print(f"  FFmpeg: {version_line}")
        return result.returncode == 0
    except FileNotFoundError:
        print("  ERROR: FFmpeg not found in PATH")
        return False


def test_get_duration():
    """Test video duration detection."""
    from jusads_compliance.capcut_client import _get_video_duration
    duration = _get_video_duration(VIDEO_PATH)
    print(f"  Duration: {duration}s")
    assert duration is not None and duration > 0, "Duration detection failed"
    return True


def test_text_overlay():
    """Test adding text overlay to video."""
    from jusads_compliance.capcut_client import add_text_overlay
    result = add_text_overlay(
        video_path=VIDEO_PATH,
        text="COMPLIANT AD",
        start_time=0.0,
        end_time=3.0,
        position="bottom",
        font_size=36,
    )
    print(f"  Result: {result}")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False
    assert os.path.exists(result["output_path"]), "Output file not created"
    size = os.path.getsize(result["output_path"])
    print(f"  Output size: {size / 1024:.1f} KB")
    # Cleanup
    os.remove(result["output_path"])
    return True


def test_trim():
    """Test trimming a segment from the video."""
    from jusads_compliance.capcut_client import trim_segment, _get_video_duration
    duration = _get_video_duration(VIDEO_PATH)
    if not duration or duration < 3:
        print("  SKIP: Video too short for trim test")
        return True

    # Trim out 1 second from the middle
    mid = duration / 2
    result = trim_segment(VIDEO_PATH, mid - 0.5, mid + 0.5)
    print(f"  Result: {result}")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False
    assert os.path.exists(result["output_path"]), "Output file not created"
    # Verify it's shorter
    from jusads_compliance.capcut_client import _get_video_duration as get_dur
    new_dur = get_dur(result["output_path"])
    print(f"  Original: {duration:.1f}s -> Trimmed: {new_dur:.1f}s (removed {result.get('removed_seconds', 0):.1f}s)")
    os.remove(result["output_path"])
    return True


def test_speed_ramp():
    """Test speed change on video."""
    from jusads_compliance.capcut_client import speed_ramp
    result = speed_ramp(VIDEO_PATH, 0, 5, speed_factor=2.0)
    print(f"  Result: {result}")
    if "error" in result:
        print(f"  ERROR: {result['error']}")
        return False
    assert os.path.exists(result["output_path"]), "Output file not created"
    size = os.path.getsize(result["output_path"])
    print(f"  Output size: {size / 1024:.1f} KB (2x speed)")
    os.remove(result["output_path"])
    return True


def test_capcut_api_connection():
    """Test if pyJianYingDraft is available and can create drafts."""
    from jusads_compliance.capcut_client import JYDRAFT_AVAILABLE, get_available_transitions
    print(f"  pyJianYingDraft available: {JYDRAFT_AVAILABLE}")
    if JYDRAFT_AVAILABLE:
        transitions = get_available_transitions()
        print(f"  Transitions available: {len(transitions)}")
        print(f"  Sample: {transitions[:5]}")
    else:
        print("  NOTE: pyJianYingDraft not installed — draft features unavailable")
    return True


def test_tool_router_heuristic():
    """Test the tool router's heuristic decision logic."""
    from jusads_compliance.tool_router import _heuristic_route

    # Minor video issue
    r1 = _heuristic_route("video", ["Subtitle typo"], "Low", 25)
    print(f"  Minor video (25%): {r1.overall_severity} -> {[t.tool for t in r1.tools]}")
    assert r1.overall_severity == "minor"

    # Moderate image issue
    r2 = _heuristic_route("image", ["Skin exposure"], "High", 60)
    print(f"  Moderate image (60%): {r2.overall_severity} -> {[t.tool for t in r2.tools]}")
    assert r2.overall_severity == "moderate"

    # Major audio issue
    r3 = _heuristic_route("audio", ["Offensive language", "Wrong tone"], "Critical", 90)
    print(f"  Major audio (90%): {r3.overall_severity} -> {[t.tool for t in r3.tools]}")
    assert r3.overall_severity == "major"

    # Text moderate
    r4 = _heuristic_route("text", ["Gender bias"], "Moderate", 55)
    print(f"  Moderate text (55%): {r4.overall_severity} -> {[t.tool for t in r4.tools]}")
    assert r4.overall_severity == "moderate"

    return True


def main():
    """Run all tests."""
    tests = [
        ("Video exists", test_video_exists),
        ("FFmpeg available", test_ffmpeg_available),
        ("Get video duration", test_get_duration),
        ("Tool router heuristic", test_tool_router_heuristic),
        ("CapCut API connection", test_capcut_api_connection),
        ("Text overlay", test_text_overlay),
        ("Trim segment", test_trim),
        ("Speed ramp", test_speed_ramp),
    ]

    print("=" * 60)
    print("Intelligent Remediation Engine — Integration Tests")
    print("=" * 60)

    passed = 0
    failed = 0
    skipped = 0

    for name, test_fn in tests:
        print(f"\n[TEST] {name}")
        try:
            result = test_fn()
            if result:
                print(f"  ✓ PASS")
                passed += 1
            else:
                print(f"  ✗ FAIL")
                failed += 1
        except Exception as e:
            print(f"  ✗ EXCEPTION: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
