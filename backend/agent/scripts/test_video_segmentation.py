#!/usr/bin/env python3
"""
test_video_segmentation.py
──────────────────────────
Test: Gemini keyframe bbox + SAM 2 Video Predictor (proper video tracking).

Uses `samv2` package (CPU-compatible fork of official SAM 2).
Install: pip install samv2

Flow:
1. Gemini watches video → violation timestamps
2. FFmpeg extracts frames for the violation duration
3. Gemini gives bbox on first frame
4. SAM 2 Video Predictor: prompt on frame 0 → propagates across ALL frames
5. Save masked frames as GIF

Usage:
    cd backend
    python -m agent.scripts.test_video_segmentation
"""

import os
import sys
import json
import time
import subprocess
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import torch

# ── Config ────────────────────────────────────────────────────────────────────
VIDEO_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "Test Video.mp4"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "results" / "video_seg"
FRAMES_DIR = OUTPUT_DIR / "frames"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FRAMES_DIR.mkdir(parents=True, exist_ok=True)

DEVICE = "cpu"
FPS_EXTRACT = 5
MAX_FRAMES = 15


# ══════════════════════════════════════════════════════════════════════════════
# Step 1: Gemini finds violation timestamps
# ══════════════════════════════════════════════════════════════════════════════

def get_violations(video_path: str) -> list[dict]:
    """Gemini analyzes video for violations."""
    from agent.clients import gemini
    from google.genai import types as genai_types

    print("Step 1: Gemini analyzing video...")
    start = time.time()

    with open(video_path, "rb") as f:
        video_bytes = f.read()

    prompt = """Watch this video and find visually non-compliant elements for Malaysian advertising.
Focus on: exposed skin (armpits, shoulders, midriff, thighs), immodest clothing.

Return JSON array:
[{"description": "exposed armpit", "start_seconds": 2.0, "end_seconds": 5.0}]

Rules:
- Only include violations with CLEAR start and end times (not 0.0-0.0)
- start_seconds must be > 0
- end_seconds must be > start_seconds
- Be specific about body part"""

    response = gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=[genai_types.Content(role="user", parts=[
            genai_types.Part.from_bytes(data=video_bytes, mime_type="video/mp4"),
            genai_types.Part.from_text(text=prompt),
        ])],
        config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
    )

    violations = json.loads(response.text)
    # Filter out invalid entries
    violations = [v for v in violations if v.get("end_seconds", 0) > v.get("start_seconds", 0)]

    elapsed = time.time() - start
    print(f"  Done ({elapsed:.1f}s) — {len(violations)} violations")
    for v in violations:
        print(f"    [{v['start_seconds']:.1f}s - {v['end_seconds']:.1f}s] {v['description']}")
    return violations


# ══════════════════════════════════════════════════════════════════════════════
# Step 2: Extract frames
# ══════════════════════════════════════════════════════════════════════════════

def extract_frames(video_path: str, start_sec: float, duration: float) -> list[Path]:
    """Extract frames using FFmpeg."""
    num_frames = min(int(duration * FPS_EXTRACT), MAX_FRAMES)
    print(f"\nStep 2: Extracting {num_frames} frames from {start_sec:.1f}s...")

    # Clear old frames
    for f in FRAMES_DIR.glob("*.jpg"):
        f.unlink()

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-i", str(video_path),
        "-vf", f"fps={FPS_EXTRACT}",
        "-frames:v", str(num_frames),
        "-q:v", "2",
        str(FRAMES_DIR / "%05d.jpg"),
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)

    frames = sorted(FRAMES_DIR.glob("*.jpg"))
    print(f"  Got {len(frames)} frames")
    return frames


# ══════════════════════════════════════════════════════════════════════════════
# Step 3: Gemini bbox on first frame
# ══════════════════════════════════════════════════════════════════════════════

def get_initial_bbox(frame_path: Path, description: str) -> list[float]:
    """Gemini locates violation on the first frame."""
    from agent.clients import gemini
    from google.genai import types as genai_types

    print(f"\nStep 3: Gemini locating '{description}'...")

    image = Image.open(frame_path)
    w, h = image.size

    with open(frame_path, "rb") as f:
        img_bytes = f.read()

    prompt = f"""Find the TIGHT bounding box for: "{description}"

Image is {w}x{h} pixels. Return JSON: {{"box": [x1, y1, x2, y2]}}

Rules:
- Tight box around ONLY the specific body part (not whole person)
- For shoulder: box just the shoulder area (~100-200px)
- For armpit: just the armpit area (~80-150px)
- For midriff: just the belly/waist area
- x1,y1 = top-left, x2,y2 = bottom-right (pixels)"""

    response = gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=[genai_types.Content(role="user", parts=[
            genai_types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
            genai_types.Part.from_text(text=prompt),
        ])],
        config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
    )

    result = json.loads(response.text)
    box = None
    if "box" in result and len(result["box"]) == 4:
        box = [float(x) for x in result["box"]]
    elif "box_2d" in result:
        box = [float(x) for x in result["box_2d"]]
    elif "box_3d" in result and len(result["box_3d"]) >= 4:
        coords = [float(x) for x in result["box_3d"][:4]]
        if all(0 <= c <= 1000 for c in coords):
            y1, x1, y2, x2 = coords
            box = [x1*w/1000, y1*h/1000, x2*w/1000, y2*h/1000]
        else:
            box = coords

    if box:
        box = [max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3])]
        print(f"  Box: [{int(box[0])}, {int(box[1])}, {int(box[2])}, {int(box[3])}]")
    return box


# ══════════════════════════════════════════════════════════════════════════════
# Step 4: SAM 2 Video Predictor (proper tracking)
# ══════════════════════════════════════════════════════════════════════════════

def track_with_sam2_video(frames_dir: Path, initial_box: list[float], frame_count: int) -> list[np.ndarray]:
    """Use SAM 2 Video Predictor for proper multi-frame tracking."""
    print(f"\nStep 4: SAM 2 Video tracking ({frame_count} frames)...")
    start = time.time()

    try:
        from sam2 import load_model
        # Try official sam2 package first
        predictor = load_model(variant="tiny", ckpt_path=None, device=DEVICE)
        print("  Using official sam2 package")
        return _track_official_sam2(predictor, frames_dir, initial_box, frame_count)
    except ImportError:
        pass

    try:
        from samv2 import load_model
        print("  Using samv2 (CPU fork)...")
        # samv2 needs checkpoint path - download if not exists
        ckpt_dir = Path.home() / ".cache" / "sam2"
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        ckpt_path = ckpt_dir / "sam2_hiera_tiny.pt"

        if not ckpt_path.exists():
            print("  Downloading SAM 2 tiny checkpoint...")
            import urllib.request
            url = "https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_tiny.pt"
            urllib.request.urlretrieve(url, str(ckpt_path))
            print(f"  Downloaded to {ckpt_path}")

        model = load_model(variant="tiny", ckpt_path=str(ckpt_path), device=DEVICE)
        return _track_samv2(model, frames_dir, initial_box, frame_count, start)
    except ImportError:
        pass

    # Fallback: use HF transformers Sam2Model per-frame (what we had before but better)
    print("  Fallback: HF Transformers per-frame tracking")
    return _track_hf_per_frame(frames_dir, initial_box, frame_count, start)


def _track_samv2(model, frames_dir, initial_box, frame_count, start_time):
    """Track using samv2 package."""
    from sam2.sam2_video_predictor import SAM2VideoPredictor

    predictor = SAM2VideoPredictor(model)

    # Initialize with video frames directory
    state = predictor.init_state(video_path=str(frames_dir))

    # Add prompt on frame 0
    box = np.array(initial_box, dtype=np.float32)
    _, _, masks = predictor.add_new_points_or_box(
        inference_state=state,
        frame_idx=0,
        obj_id=1,
        box=box,
    )

    # Propagate through all frames
    all_masks = {}
    for frame_idx, obj_ids, masks in predictor.propagate_in_video(state):
        all_masks[frame_idx] = (masks[0] > 0.0).cpu().numpy().squeeze()

    elapsed = time.time() - start_time
    print(f"  Tracking done ({elapsed:.1f}s) — {len(all_masks)} frames")

    # Return ordered masks
    result = []
    for i in range(frame_count):
        if i in all_masks:
            result.append(all_masks[i])
        else:
            result.append(np.zeros_like(list(all_masks.values())[0]))
    return result


def _track_official_sam2(predictor, frames_dir, initial_box, frame_count):
    """Track using official sam2 package."""
    # Similar to samv2 but different API
    return _track_samv2(predictor, frames_dir, initial_box, frame_count, time.time())


def _track_hf_per_frame(frames_dir, initial_box, frame_count, start_time):
    """Fallback: per-frame SAM 2 via HF transformers with bbox propagation."""
    from transformers import Sam2Processor, Sam2Model

    processor = Sam2Processor.from_pretrained("facebook/sam2-hiera-tiny")
    model = Sam2Model.from_pretrained("facebook/sam2-hiera-tiny")
    model.to(DEVICE)

    frames = sorted(Path(frames_dir).glob("*.jpg"))[:frame_count]
    all_masks = []
    current_box = initial_box

    for i, frame_path in enumerate(frames):
        image = Image.open(frame_path).convert("RGB")
        w, h = image.size

        inputs = processor(images=image, input_boxes=[[current_box]], return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            outputs = model(**inputs)

        pred_masks = outputs.pred_masks.squeeze(0)
        if hasattr(outputs, "iou_scores") and outputs.iou_scores is not None:
            best_idx = outputs.iou_scores.squeeze(0).argmax(dim=-1)
            mask = pred_masks[0, best_idx[0]]
        else:
            mask = pred_masks[0, 0]

        mask_resized = torch.nn.functional.interpolate(
            mask.unsqueeze(0).unsqueeze(0).float(), size=(h, w), mode="bilinear", align_corners=False
        ).squeeze()
        mask_np = (mask_resized > 0).cpu().numpy().astype(np.uint8)
        all_masks.append(mask_np)

        # Update box from mask for next frame
        ys, xs = np.where(mask_np > 0)
        if len(xs) > 10:
            pad = 10
            current_box = [
                max(0, float(xs.min()) - pad),
                max(0, float(ys.min()) - pad),
                min(w, float(xs.max()) + pad),
                min(h, float(ys.max()) + pad),
            ]

        if (i + 1) % 5 == 0:
            print(f"    Frame {i+1}/{len(frames)} — pixels: {mask_np.sum()}")

    elapsed = time.time() - start_time
    print(f"  Done ({elapsed:.1f}s)")
    return all_masks


# ══════════════════════════════════════════════════════════════════════════════
# Step 5: Save visualization
# ══════════════════════════════════════════════════════════════════════════════

def save_results(frames_dir: Path, masks: list[np.ndarray], label: str) -> Path:
    """Save overlay GIF + individual frames."""
    print(f"\nStep 5: Saving...")

    frames = sorted(Path(frames_dir).glob("*.jpg"))[:len(masks)]
    overlay_frames = []

    for frame_path, mask in zip(frames, masks):
        image = Image.open(frame_path).convert("RGBA")
        w, h = image.size

        # Resize mask if needed
        if mask.shape != (h, w):
            mask_img = Image.fromarray((mask * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
            mask = (np.array(mask_img) > 128).astype(np.uint8)

        # Red overlay on violation area
        color_array = np.zeros((h, w, 4), dtype=np.uint8)
        color_array[mask > 0] = (255, 0, 0, 140)
        overlay = Image.alpha_composite(image, Image.fromarray(color_array, "RGBA"))

        draw = ImageDraw.Draw(overlay)
        draw.text((10, 10), f"■ {label}", fill=(255, 50, 50, 255))
        overlay_frames.append(overlay.convert("RGB"))

    # Save GIF
    gif_path = OUTPUT_DIR / "tracked_violation.gif"
    if overlay_frames:
        overlay_frames[0].save(
            gif_path, save_all=True, append_images=overlay_frames[1:],
            duration=200, loop=0,
        )
        overlay_frames[0].save(OUTPUT_DIR / "frame_first.png")
        overlay_frames[-1].save(OUTPUT_DIR / "frame_last.png")
        print(f"  ✅ {gif_path}")
        print(f"  ✅ frame_first.png, frame_last.png")

    return gif_path


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"Video: {VIDEO_PATH.name}")
    print(f"Device: {DEVICE}")
    print()

    if not VIDEO_PATH.exists():
        print(f"❌ Video not found: {VIDEO_PATH}")
        sys.exit(1)

    # Step 1
    violations = get_violations(str(VIDEO_PATH))
    if not violations:
        print("No violations found.")
        return

    # Pick best violation (first with valid duration)
    violation = violations[0]
    duration = violation["end_seconds"] - violation["start_seconds"]
    print(f"\n→ Target: '{violation['description']}' ({violation['start_seconds']:.1f}s - {violation['end_seconds']:.1f}s)")

    # Step 2
    frames = extract_frames(str(VIDEO_PATH), violation["start_seconds"], duration)
    if not frames:
        print("❌ No frames extracted")
        return

    # Step 3
    bbox = get_initial_bbox(frames[0], violation["description"])
    if not bbox:
        print("❌ Could not locate violation")
        return

    # Step 4
    masks = track_with_sam2_video(FRAMES_DIR, bbox, len(frames))

    # Step 5
    if masks:
        save_results(FRAMES_DIR, masks, violation["description"])

    # Summary
    print(f"\n{'━' * 50}")
    print(f"  Violation: {violation['description']}")
    print(f"  Tracked: {len(masks)} frames")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'━' * 50}")


if __name__ == "__main__":
    main()
