"""
run_video_demo.py
─────────────────
Generates actual video output files from the remediation engine.
Output is saved to backend/assets/results/ so you can view them.

Run: python -m tests.run_video_demo
"""

import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jusads_compliance.capcut_client import (
    add_text_overlay,
    trim_segment,
    speed_ramp,
    JYDRAFT_AVAILABLE,
)

VIDEO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "Test Video.mp4",
)

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "results",
)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def main():
    print("=" * 50)
    print("Remediation Engine — Video Demo Output")
    print("=" * 50)
    print(f"Source: {VIDEO}")
    print(f"Output dir: {OUTPUT_DIR}")
    print(f"pyJianYingDraft available: {JYDRAFT_AVAILABLE}")
    print()

    # 1. Text overlay
    print("[1/3] Adding text overlay...")
    r1 = add_text_overlay(VIDEO, "COMPLIANT AD - JusAds", 0.0, 5.0, "bottom", 42)
    if "output_path" in r1:
        dest = os.path.join(OUTPUT_DIR, "demo_text_overlay.mp4")
        shutil.copy2(r1["output_path"], dest)
        print(f"  -> {dest} ({os.path.getsize(dest) / 1024:.0f} KB)")
    else:
        print(f"  ERROR: {r1.get('error')}")

    # 2. Trim (remove 2 seconds from middle)
    print("[2/3] Trimming segment (7s-9s removed)...")
    r2 = trim_segment(VIDEO, 7.0, 9.0)
    if "output_path" in r2:
        dest = os.path.join(OUTPUT_DIR, "demo_trimmed.mp4")
        shutil.copy2(r2["output_path"], dest)
        print(f"  -> {dest} ({os.path.getsize(dest) / 1024:.0f} KB)")
    else:
        print(f"  ERROR: {r2.get('error')}")

    # 3. Speed ramp (2x)
    print("[3/3] Speed ramp (2x faster)...")
    r3 = speed_ramp(VIDEO, 0, 10, 2.0)
    if "output_path" in r3:
        dest = os.path.join(OUTPUT_DIR, "demo_speed_2x.mp4")
        shutil.copy2(r3["output_path"], dest)
        print(f"  -> {dest} ({os.path.getsize(dest) / 1024:.0f} KB)")
    else:
        print(f"  ERROR: {r3.get('error')}")

    print()
    print("Done! Open the files in assets/results/ to view.")


if __name__ == "__main__":
    main()
