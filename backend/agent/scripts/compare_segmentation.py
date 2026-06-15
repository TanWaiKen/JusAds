#!/usr/bin/env python3
"""
compare_segmentation.py
───────────────────────
Compare ALL segmentation approaches for violation detection:
1. CLIPSeg (text → heatmap)
2. OWLv2 + SAM 2 (text → boxes → masks)
3. Gemini bbox + SAM 2 (LLM → boxes → masks)
4. YOLO-World + SAM 2 (fast detector → masks)

CPU-only. Output: assets/results/comparison_all.png

Usage:
    cd backend
    pip install ultralytics
    python -m agent.scripts.compare_segmentation
"""

import sys
import time
import json as json_mod
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

import torch

# ── Config ────────────────────────────────────────────────────────────────────
IMAGE_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "images" / "noncompliant_armpit_ad.png"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "results"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPTS = ["armpit", "bare shoulder", "sleeveless top"]
DEVICE = "cpu"
COLORS = [(255, 50, 50, 150), (50, 200, 50, 150), (50, 100, 255, 150), (255, 165, 0, 150), (255, 0, 255, 150)]


# ══════════════════════════════════════════════════════════════════════════════
# Shared: SAM 2 mask refinement
# ══════════════════════════════════════════════════════════════════════════════

_sam2_processor = None
_sam2_model = None

def get_sam2():
    """Lazy-load SAM 2 (shared across methods)."""
    global _sam2_processor, _sam2_model
    if _sam2_model is None:
        from transformers import Sam2Processor, Sam2Model
        print("    Loading SAM 2 (tiny)...")
        _sam2_processor = Sam2Processor.from_pretrained("facebook/sam2-hiera-tiny")
        _sam2_model = Sam2Model.from_pretrained("facebook/sam2-hiera-tiny")
        _sam2_model.to(DEVICE)
    return _sam2_processor, _sam2_model


def run_sam2_on_boxes(image: Image.Image, boxes: list[list[float]]) -> np.ndarray:
    """Given bounding boxes, produce pixel-perfect masks via SAM 2."""
    if not boxes:
        return np.array([])

    w, h = image.size
    processor, model = get_sam2()

    inputs = processor(images=image, input_boxes=[boxes], return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        outputs = model(**inputs)

    pred_masks = outputs.pred_masks.squeeze(0)

    # Take best mask per box
    if hasattr(outputs, "iou_scores") and outputs.iou_scores is not None:
        iou_scores = outputs.iou_scores.squeeze(0)
        best_idx = iou_scores.argmax(dim=-1)
        masks = torch.stack([pred_masks[i, best_idx[i]] for i in range(len(best_idx))])
    else:
        masks = pred_masks[:, 0]

    masks_resized = torch.nn.functional.interpolate(
        masks.unsqueeze(1).float(), size=(h, w), mode="bilinear", align_corners=False,
    ).squeeze(1)

    return (masks_resized > 0).cpu().numpy()


# ══════════════════════════════════════════════════════════════════════════════
# Method 1: CLIPSeg
# ══════════════════════════════════════════════════════════════════════════════

def run_clipseg(image: Image.Image, prompts: list[str]) -> dict:
    """CLIPSeg: text → segmentation heatmap."""
    from transformers import CLIPSegProcessor, CLIPSegForImageSegmentation

    print("  [CLIPSeg] Loading...")
    processor = CLIPSegProcessor.from_pretrained("CIDAS/clipseg-rd64-refined")
    model = CLIPSegForImageSegmentation.from_pretrained("CIDAS/clipseg-rd64-refined")
    model.to(DEVICE)

    start = time.time()
    inputs = processor(text=prompts, images=[image] * len(prompts), return_tensors="pt", padding=True).to(DEVICE)
    with torch.no_grad():
        outputs = model(**inputs)
    masks = torch.sigmoid(outputs.logits).cpu().numpy()
    elapsed = time.time() - start

    print(f"  [CLIPSeg] Done: {elapsed:.2f}s, {len(masks)} masks")
    return {"masks": masks, "labels": prompts, "time": elapsed, "method": "CLIPSeg"}


# ══════════════════════════════════════════════════════════════════════════════
# Method 2: OWLv2 + SAM 2
# ══════════════════════════════════════════════════════════════════════════════

def run_owlv2_sam2(image: Image.Image, prompts: list[str]) -> dict:
    """OWLv2 detection → SAM 2 masks."""
    from transformers import Owlv2Processor, Owlv2ForObjectDetection

    w, h = image.size

    print("  [OWLv2] Loading...")
    processor = Owlv2Processor.from_pretrained("google/owlv2-base-patch16-ensemble")
    model = Owlv2ForObjectDetection.from_pretrained("google/owlv2-base-patch16-ensemble")
    model.to(DEVICE)

    start = time.time()
    inputs = processor(text=[prompts], images=image, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits[0]
    boxes = outputs.pred_boxes[0]
    scores, label_indices = logits.sigmoid().max(dim=-1)

    # Filter + top 1 per prompt
    keep = scores > 0.15
    from collections import defaultdict
    per_prompt = defaultdict(list)
    for box, score, label_idx in zip(boxes[keep], scores[keep], label_indices[keep]):
        cx, cy, bw, bh = box.tolist()
        pixel_box = [(cx - bw/2)*w, (cy - bh/2)*h, (cx + bw/2)*w, (cy + bh/2)*h]
        per_prompt[prompts[label_idx.item()]].append({"box": pixel_box, "score": score.item()})

    detections = []
    for label, dets in per_prompt.items():
        dets.sort(key=lambda x: x["score"], reverse=True)
        detections.append({"box": dets[0]["box"], "label": label})

    owl_time = time.time() - start
    print(f"  [OWLv2] {owl_time:.2f}s, {len(detections)} boxes")

    # SAM 2
    if detections:
        print("  [OWLv2→SAM2] Refining...")
        sam_start = time.time()
        mask_array = run_sam2_on_boxes(image, [d["box"] for d in detections])
        sam_time = time.time() - sam_start
    else:
        mask_array = np.array([])
        sam_time = 0

    total = owl_time + sam_time
    print(f"  [OWLv2+SAM2] Total: {total:.2f}s")
    return {"masks": mask_array, "labels": [d["label"] for d in detections], "time": total, "method": "OWLv2+SAM2"}


# ══════════════════════════════════════════════════════════════════════════════
# Method 3: Gemini bbox + SAM 2
# ══════════════════════════════════════════════════════════════════════════════

def run_gemini_sam2(image: Image.Image, prompts: list[str]) -> dict:
    """Gemini bounding box detection → SAM 2 masks."""
    from agent.clients import gemini
    from google.genai import types as genai_types

    w, h = image.size

    print("  [Gemini] Detecting bboxes...")
    start = time.time()

    # Save temp image
    temp_path = OUTPUT_DIR / "_temp_input.png"
    image.save(temp_path)
    with open(temp_path, "rb") as f:
        image_bytes = f.read()

    bbox_prompt = f"""Look at this image carefully. Find the exact bounding boxes for these objects:
{', '.join(prompts)}

The image is {w}x{h} pixels.

Return a JSON array where each item has:
- "label": which object (one of: {', '.join(prompts)})
- "box": [x1, y1, x2, y2] as pixel coordinates (integers, top-left origin)

Rules:
- x1,y1 = top-left corner of the object
- x2,y2 = bottom-right corner
- Values must be 0 to {w} for x, 0 to {h} for y
- Include each instance (e.g. left armpit AND right armpit)
- Only include objects clearly visible
- Return [] if nothing found

Example: [{{"label": "armpit", "box": [350, 180, 420, 280]}}]"""

    response = gemini.models.generate_content(
        model="gemini-2.5-flash",
        contents=[genai_types.Content(role="user", parts=[
            genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            genai_types.Part.from_text(text=bbox_prompt),
        ])],
        config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
    )

    gemini_time = time.time() - start
    temp_path.unlink(missing_ok=True)

    # Parse response
    detections = []
    try:
        raw = json_mod.loads(response.text)
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
                detections.append({"box": box, "label": d["label"]})
    except Exception as e:
        print(f"  [Gemini] Parse error: {e}")
        print(f"    Raw: {response.text[:200]}")

    print(f"  [Gemini] {gemini_time:.2f}s, {len(detections)} boxes")
    for d in detections:
        print(f"    - {d['label']}: [{int(d['box'][0])},{int(d['box'][1])},{int(d['box'][2])},{int(d['box'][3])}]")

    # SAM 2
    if detections:
        print("  [Gemini→SAM2] Refining...")
        sam_start = time.time()
        mask_array = run_sam2_on_boxes(image, [d["box"] for d in detections])
        sam_time = time.time() - sam_start
    else:
        mask_array = np.array([])
        sam_time = 0

    total = gemini_time + sam_time
    print(f"  [Gemini+SAM2] Total: {total:.2f}s")
    return {"masks": mask_array, "labels": [d["label"] for d in detections], "time": total, "method": "Gemini+SAM2"}


# ══════════════════════════════════════════════════════════════════════════════
# Method 4: YOLO-World + SAM 2
# ══════════════════════════════════════════════════════════════════════════════

def run_yolo_sam2(image: Image.Image, prompts: list[str]) -> dict:
    """YOLO-World open-vocabulary detection → SAM 2 masks."""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("  [YOLO] Not installed. Run: pip install ultralytics")
        return {"masks": np.array([]), "labels": [], "time": 0, "method": "YOLO+SAM2"}

    w, h = image.size

    print("  [YOLO-World] Loading...")
    start = time.time()

    model = YOLO("yolov8s-worldv2.pt")
    model.set_classes(prompts)

    # Run inference
    results = model.predict(source=np.array(image), conf=0.1, verbose=False)
    yolo_time = time.time() - start

    detections = []
    if results and results[0].boxes:
        for box, cls_id, conf in zip(results[0].boxes.xyxy, results[0].boxes.cls, results[0].boxes.conf):
            detections.append({
                "box": box.cpu().numpy().tolist(),
                "label": prompts[int(cls_id.item())],
                "score": conf.item(),
            })

    print(f"  [YOLO-World] {yolo_time:.2f}s, {len(detections)} boxes")
    for d in detections:
        print(f"    - {d['label']} ({d['score']:.2f}): [{int(d['box'][0])},{int(d['box'][1])},{int(d['box'][2])},{int(d['box'][3])}]")

    # SAM 2
    if detections:
        print("  [YOLO→SAM2] Refining...")
        sam_start = time.time()
        mask_array = run_sam2_on_boxes(image, [d["box"] for d in detections])
        sam_time = time.time() - sam_start
    else:
        mask_array = np.array([])
        sam_time = 0

    total = yolo_time + sam_time
    print(f"  [YOLO+SAM2] Total: {total:.2f}s")
    return {"masks": mask_array, "labels": [d["label"] for d in detections], "time": total, "method": "YOLO+SAM2"}


# ══════════════════════════════════════════════════════════════════════════════
# Visualization
# ══════════════════════════════════════════════════════════════════════════════

def overlay_masks(image: Image.Image, result: dict) -> Image.Image:
    """Overlay colored segmentation masks on image."""
    w, h = image.size
    overlay = image.convert("RGBA").copy()

    masks = result.get("masks", np.array([]))
    labels = result.get("labels", [])

    for i, mask in enumerate(masks):
        if mask.shape != (h, w):
            mask_img = Image.fromarray((mask * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
            mask = (np.array(mask_img) > 64).astype(np.uint8)
        else:
            mask = mask.astype(np.uint8)

        color = COLORS[i % len(COLORS)]
        color_array = np.zeros((h, w, 4), dtype=np.uint8)
        color_array[mask > 0] = color
        overlay = Image.alpha_composite(overlay, Image.fromarray(color_array, "RGBA"))

    draw = ImageDraw.Draw(overlay)
    for i, label in enumerate(labels[:len(COLORS)]):
        color = tuple(COLORS[i % len(COLORS)][:3]) + (255,)
        draw.text((10, 10 + i * 18), f"■ {label}", fill=color)

    method = result.get("method", "")
    draw.text((10, h - 22), f"{method} | {result['time']:.1f}s", fill=(255, 255, 255, 255))
    return overlay


def create_comparison_grid(image: Image.Image, results: list[dict]) -> Image.Image:
    """Create grid comparison: original + all methods."""
    w, h = image.size
    n = len(results) + 1  # +1 for original

    canvas = Image.new("RGBA", (w * n + (n-1) * 5, h + 30), (20, 20, 20, 255))

    # Original
    canvas.paste(image.convert("RGBA"), (0, 30))
    draw = ImageDraw.Draw(canvas)
    draw.text((w // 2 - 25, 8), "Original", fill=(255, 255, 255, 255))

    # Each method
    for i, result in enumerate(results):
        vis = overlay_masks(image, result)
        x_offset = (i + 1) * (w + 5)
        canvas.paste(vis, (x_offset, 30))
        draw.text((x_offset + w // 2 - 30, 8), result["method"], fill=(255, 255, 255, 255))

    return canvas


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"Image: {IMAGE_PATH.name}")
    print(f"Prompts: {PROMPTS}")
    print(f"Device: {DEVICE}\n")

    if not IMAGE_PATH.exists():
        print(f"❌ Image not found: {IMAGE_PATH}")
        sys.exit(1)

    image = Image.open(IMAGE_PATH).convert("RGB")
    print(f"Size: {image.size}\n")

    results = []

    # 1. CLIPSeg
    print("━━━ 1. CLIPSeg ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    results.append(run_clipseg(image, PROMPTS))
    print()

    # 2. OWLv2 + SAM 2
    print("━━━ 2. OWLv2 + SAM 2 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    results.append(run_owlv2_sam2(image, PROMPTS))
    print()

    # 3. Gemini + SAM 2
    print("━━━ 3. Gemini + SAM 2 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    results.append(run_gemini_sam2(image, PROMPTS))
    print()

    # 4. YOLO-World + SAM 2
    print("━━━ 4. YOLO-World + SAM 2 ━━━━━━━━━━━━━━━━━━━━━━━━━")
    results.append(run_yolo_sam2(image, PROMPTS))
    print()

    # Save individual results
    print("━━━ Saving ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for r in results:
        if len(r["masks"]) > 0:
            vis = overlay_masks(image, r)
            fname = f"seg_{r['method'].lower().replace('+', '_')}.png"
            vis.save(OUTPUT_DIR / fname)
            print(f"  ✅ {fname}")

    # Grid comparison
    comparison = create_comparison_grid(image, results)
    comparison.save(OUTPUT_DIR / "comparison_all.png")
    print(f"  ✅ comparison_all.png")

    # Summary table
    print(f"\n{'━' * 55}")
    print(f"  {'Method':<18} {'Time':>6} {'Masks':>6} {'Labels'}")
    print(f"  {'─' * 50}")
    for r in results:
        masks = r.get("masks", np.array([]))
        n_masks = len(masks) if len(masks) > 0 else 0
        labels = ', '.join(r.get('labels', [])[:3])
        print(f"  {r['method']:<18} {r['time']:>5.1f}s {n_masks:>5}  {labels}")
    print(f"{'━' * 55}")


if __name__ == "__main__":
    main()
