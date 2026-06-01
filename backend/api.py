"""
JusAds Video Compliance API
==============================
FastAPI server for the video compliance pipeline.

Endpoints:
  POST /api/check       — Upload video, run compliance check, extract violation clips
  GET  /api/results/:id — Get results for a previous check
  GET  /clips/:filename — Serve extracted clip files

Usage:
  uvicorn api:app --reload --port 8000
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent))

from jusads_video_compliance.step1_compliance_check import check_compliance
from jusads_video_compliance.step2_parse_violations import parse_violations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="JusAds Video Compliance API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
UPLOAD_DIR = Path("assets/uploads")
CLIPS_DIR = Path("assets/clips")
RESULTS_DIR = Path("assets/results")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Serve clips as static files
app.mount("/clips", StaticFiles(directory=str(CLIPS_DIR)), name="clips")


def extract_clip(video_path: str, start: float, end: float, output_path: str) -> bool:
    """Extract a clip from video using FFmpeg."""
    duration = end - start
    if duration <= 0:
        duration = 2.0

    try:
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", video_path,
            "-t", str(duration),
            "-c:v", "libx264",
            "-c:a", "aac",
            "-movflags", "+faststart",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        logger.error(f"Clip extraction failed: {e}")
        return False


@app.post("/api/check")
async def check_video(
    video: UploadFile = File(...),
    market: str = Form("malaysia"),
    ethnicity: str = Form("malay"),
    age_group: str = Form("all_ages"),
):
    """
    Upload a video and run compliance check.
    Returns violations with extracted clips and persona info.
    """
    # Save uploaded video
    check_id = uuid.uuid4().hex[:8]
    video_filename = f"{check_id}_{video.filename}"
    video_path = str(UPLOAD_DIR / video_filename)

    with open(video_path, "wb") as f:
        content = await video.read()
        f.write(content)

    logger.info(f"Video uploaded: {video_path} ({len(content)} bytes)")

    # Run compliance check
    start_time = time.time()
    result = check_compliance(video_path, market, ethnicity, age_group)
    check_time = time.time() - start_time

    # Parse violations
    violations = parse_violations(result)

    # Extract clips for each violation
    violation_clips = []
    for i, v in enumerate(violations):
        clip_filename = f"{check_id}_violation_{i}.mp4"
        clip_path = str(CLIPS_DIR / clip_filename)

        clip_extracted = extract_clip(video_path, v["start"], v["end"], clip_path)

        violation_clips.append({
            "index": i,
            "start": v["start"],
            "end": v["end"],
            "type": v["type"],
            "category": v["category"],
            "severity": v["severity"],
            "description": v["description"],
            "clip_url": f"/clips/{clip_filename}" if clip_extracted else None,
        })

    # Build response
    response = {
        "check_id": check_id,
        "video_filename": video.filename,
        "market": market,
        "ethnicity": ethnicity,
        "age_group": age_group,
        "score": result.get("score", 0),
        "risk_level": result.get("risk_level", "Unknown"),
        "explanation": result.get("explanation", ""),
        "suggestion": result.get("suggestion", ""),
        "localization": result.get("localization", {}),
        "persona": _parse_persona(result.get("persona_used", "")),
        "violations": violation_clips,
        "processing_time_seconds": round(check_time, 1),
    }

    # Save result
    result_path = RESULTS_DIR / f"{check_id}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(response, f, indent=2, ensure_ascii=False)

    return JSONResponse(content=response)


@app.get("/api/results/{check_id}")
async def get_results(check_id: str):
    """Get results for a previous compliance check."""
    result_path = RESULTS_DIR / f"{check_id}.json"
    if not result_path.exists():
        return JSONResponse(status_code=404, content={"error": "Not found"})

    with open(result_path, "r", encoding="utf-8") as f:
        return JSONResponse(content=json.load(f))


def _parse_persona(persona_str: str) -> dict | None:
    """Parse persona JSON string into a dict for the frontend."""
    if not persona_str or persona_str == "No specific persona (ethnicity: all)":
        return None
    try:
        return json.loads(persona_str)
    except (json.JSONDecodeError, TypeError):
        return {"raw": persona_str}


# Serve frontend (must be LAST — catches all unmatched routes)
FRONTEND_DIR = Path(__file__).parent / "frontend"
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
