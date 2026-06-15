"""
JusAds Compliance LangGraph API
=================================
Single entry point: POST /api/compliance/check

The graph auto-routes based on media type:
  text  → text_check
  image → image_check
  audio → transcribe → text_check
  video → video_check → parse_violations → extract_clips

Usage:
  pip install fastapi uvicorn python-multipart langgraph
  python -m uvicorn langgraph_api:app --reload --port 8000
"""

import json
import logging
import mimetypes
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Literal, TypedDict

from dotenv import load_dotenv

# Load .env from backend/ directory (picks up LangSmith + all other keys)
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent))

from langgraph.graph import StateGraph, END

from jusads_text_compliance.text_checker import TextComplianceChecker
from jusads_image_compliance.image_checker import ImageComplianceChecker
from jusads_video_compliance.step1_compliance_check import check_compliance as video_check_compliance
from jusads_video_compliance.step2_parse_violations import parse_violations
from jusads_transcription.transcriber import Transcriber
from jusads_remix_pipeline.api import remix_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="JusAds Compliance LangGraph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register remix pipeline router
app.include_router(remix_router, prefix="/remix", tags=["remix"])

# Directories
UPLOAD_DIR = Path("assets/uploads")
CLIPS_DIR = Path("assets/clips")
RESULTS_DIR = Path("assets/results")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/clips", StaticFiles(directory=str(CLIPS_DIR)), name="clips")

FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
SIMPLE_FRONTEND = Path(__file__).parent / "frontend"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UNIFIED STATE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ComplianceState(TypedDict):
    # Input
    check_id: str
    media_type: str  # "text" | "image" | "audio" | "video"
    file_path: str
    filename: str
    text_input: str
    market: str
    ethnicity: str
    age_group: str
    # Intermediate
    transcript: str
    violations: list[dict]
    violation_clips: list[dict]
    # Output
    result: dict


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NODES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def node_router(state: ComplianceState) -> dict:
    """Detect media type — already set by the API endpoint."""
    logger.info(f"[Router] Media type: {state['media_type']}")
    return {}


def node_transcribe(state: ComplianceState) -> dict:
    """Transcribe audio/video to text using AWS Transcribe."""
    logger.info(f"[Transcribe] Processing {state['file_path']}...")
    transcriber = Transcriber()
    transcript = transcriber.transcribe_media(state["file_path"])
    logger.info(f"[Transcribe] Got {len(transcript)} chars")
    return {"transcript": transcript}


def node_text_check(state: ComplianceState) -> dict:
    """Run text compliance check."""
    text = state["text_input"] or state["transcript"]
    logger.info(f"[TextCheck] Checking {len(text)} chars...")
    checker = TextComplianceChecker()
    result = checker.check_compliance(
        ad_text=text,
        market=state["market"],
        ethnicity=state["ethnicity"],
        age_group=state["age_group"],
    )
    if state["transcript"]:
        result["transcript_used"] = state["transcript"]
    return {"result": result}


def node_image_check(state: ComplianceState) -> dict:
    """Run image compliance check."""
    logger.info(f"[ImageCheck] Checking {state['file_path']}...")
    checker = ImageComplianceChecker()
    result = checker.check_compliance(
        image_path=state["file_path"],
        market=state["market"],
        ethnicity=state["ethnicity"],
        age_group=state["age_group"],
    )
    return {"result": result}


def node_video_check(state: ComplianceState) -> dict:
    """Run video compliance check (multimodal: visual + audio)."""
    logger.info(f"[VideoCheck] Checking {state['file_path']}...")
    result = video_check_compliance(
        state["file_path"], state["market"], state["ethnicity"], state["age_group"]
    )
    return {"result": result}


def node_parse_violations(state: ComplianceState) -> dict:
    """Parse violations from compliance result."""
    logger.info("[ParseViolations] Extracting timestamps...")
    violations = parse_violations(state["result"])
    return {"violations": violations}


def node_extract_clips(state: ComplianceState) -> dict:
    """Extract video clips for each violation."""
    logger.info(f"[ExtractClips] {len(state['violations'])} clips...")
    check_id = state["check_id"]
    clips = []

    for i, v in enumerate(state["violations"]):
        clip_filename = f"{check_id}_violation_{i}.mp4"
        clip_path = str(CLIPS_DIR / clip_filename)
        extracted = _extract_clip(state["file_path"], v["start"], v["end"], clip_path)
        clips.append({
            "index": i,
            "start": v["start"],
            "end": v["end"],
            "type": v["type"],
            "category": v["category"],
            "severity": v["severity"],
            "description": v["description"],
            "clip_url": f"/clips/{clip_filename}" if extracted else None,
        })

    return {"violation_clips": clips}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ROUTING LOGIC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def route_by_media_type(state: ComplianceState) -> str:
    """Conditional edge: route to the correct branch based on media_type."""
    media = state["media_type"]
    if media == "text":
        return "text_check"
    elif media == "image":
        return "image_check"
    elif media == "audio":
        return "transcribe"
    elif media == "video":
        return "video_check"
    return "text_check"


def route_after_video_check(state: ComplianceState) -> str:
    """After video check, always parse violations."""
    return "parse_violations"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BUILD THE GRAPH
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

workflow = StateGraph(ComplianceState)

# Add all nodes
workflow.add_node("router", node_router)
workflow.add_node("text_check", node_text_check)
workflow.add_node("image_check", node_image_check)
workflow.add_node("transcribe", node_transcribe)
workflow.add_node("video_check", node_video_check)
workflow.add_node("parse_violations", node_parse_violations)
workflow.add_node("extract_clips", node_extract_clips)

# Entry point
workflow.set_entry_point("router")

# Router → branch by media type
workflow.add_conditional_edges("router", route_by_media_type, {
    "text_check": "text_check",
    "image_check": "image_check",
    "transcribe": "transcribe",
    "video_check": "video_check",
})

# Text/Image → END
workflow.add_edge("text_check", END)
workflow.add_edge("image_check", END)

# Audio: transcribe → text_check → END
workflow.add_edge("transcribe", "text_check")

# Video: video_check → parse_violations → extract_clips → END
workflow.add_edge("video_check", "parse_violations")
workflow.add_edge("parse_violations", "extract_clips")
workflow.add_edge("extract_clips", END)

compliance_graph = workflow.compile()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SINGLE API ENDPOINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@app.post("/api/compliance/check")
async def check_compliance(
    file: UploadFile = File(None),
    text: str = Form(None),
    market: str = Form("malaysia"),
    ethnicity: str = Form("malay"),
    age_group: str = Form("all_ages"),
):
    """
    Single entry point for all compliance checks.
    The graph auto-routes based on input:
      - text field provided → text compliance
      - file is image → image compliance
      - file is audio → transcribe → text compliance
      - file is video → video compliance → parse → extract clips

    Returns SSE stream with node status updates + final result.
    """
    check_id = uuid.uuid4().hex[:8]

    # Determine media type
    if text and not file:
        media_type = "text"
        file_path = ""
        filename = ""
    elif file:
        filename = file.filename or "upload"
        mime, _ = mimetypes.guess_type(filename)
        mime = mime or "application/octet-stream"

        # Save file
        upload_filename = f"{check_id}_{filename}"
        file_path = str(UPLOAD_DIR / upload_filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Detect type from MIME
        if mime.startswith("image/"):
            media_type = "image"
        elif mime.startswith("audio/"):
            media_type = "audio"
        elif mime.startswith("video/"):
            media_type = "video"
        else:
            media_type = "text"
            text = ""  # fallback
    else:
        return JSONResponse(status_code=400, content={"error": "Provide either 'text' or 'file'"})

    logger.info(f"[API] check_id={check_id}, media_type={media_type}, file={filename}")

    def generate_events():
        state: ComplianceState = {
            "check_id": check_id,
            "media_type": media_type,
            "file_path": file_path,
            "filename": filename,
            "text_input": text or "",
            "market": market,
            "ethnicity": ethnicity,
            "age_group": age_group,
            "transcript": "",
            "violations": [],
            "violation_clips": [],
            "result": {},
        }

        node_descriptions = {
            "router": "Detecting media type...",
            "text_check": "Running text compliance check...",
            "image_check": "Running image compliance check...",
            "transcribe": "Transcribing audio (AWS Transcribe)...",
            "video_check": "Analyzing video compliance (Gemini + RAG)...",
            "parse_violations": "Parsing violations...",
            "extract_clips": "Extracting violation clips (FFmpeg)...",
        }

        # Stream through LangGraph
        final_state = state
        for event in compliance_graph.stream(state, stream_mode="updates"):
            for node_name, node_output in event.items():
                desc = node_descriptions.get(node_name, node_name)
                sse = json.dumps({
                    "type": "node_status",
                    "node": node_name,
                    "status": "completed",
                    "description": desc,
                })
                yield f"data: {sse}\n\n"
                if node_output:
                    final_state.update(node_output)

        # Build final response
        result = final_state.get("result", {})
        response = {
            "check_id": check_id,
            "media_type": media_type,
            "filename": filename,
            "market": market,
            "ethnicity": ethnicity,
            "age_group": age_group,
            "risk_percentage": result.get("risk_percentage", result.get("RISK_PERCENTAGE", 50)),
            "risk_band": result.get("risk_band", result.get("RISK_BAND", "Moderate")),
            "confidence": result.get("confidence", result.get("CONFIDENCE", "low")),
            "score": result.get("score", 100 - result.get("risk_percentage", result.get("RISK_PERCENTAGE", 50))),
            "risk_level": result.get("risk_band", result.get("RISK_BAND", "Moderate")),
            "explanation": result.get("explanation", ""),
            "suggestion": result.get("suggestion", ""),
            "localization": result.get("localization", {}),
            "persona": _parse_persona(result.get("persona_used", "")),
            "transcript": final_state.get("transcript", ""),
            "violations": final_state.get("violation_clips", []),
            "high_risk_indicators": result.get("high_risk_indicators", result.get("high_risk_indicator", [])),
            "processing_time_seconds": result.get("processing_time_ms", 0) / 1000,
        }

        # Convert high_risk_indicators to violations format for image/text/audio
        # Each media type has its own violation structure
        if not response["violations"] and response.get("high_risk_indicators"):
            if media_type == "text":
                response["violations"] = [
                    {
                        "index": i,
                        "type": "text",
                        "phrase": indicator,
                        "severity": "error" if response.get("risk_level") == "High" else "warning",
                        "reason": "",
                        "suggested_replacement": "",
                    }
                    for i, indicator in enumerate(response["high_risk_indicators"])
                ]
            elif media_type == "image":
                response["violations"] = [
                    {
                        "index": i,
                        "type": "visual",
                        "component": indicator,
                        "severity": "error" if response.get("risk_level") == "High" else "warning",
                        "location_description": "",
                        "edit_prompt": "",
                    }
                    for i, indicator in enumerate(response["high_risk_indicators"])
                ]
            elif media_type == "audio":
                response["violations"] = [
                    {
                        "index": i,
                        "type": "audio",
                        "spoken_phrase": indicator,
                        "severity": "error" if response.get("risk_level") == "High" else "warning",
                        "reason": "",
                        "suggested_replacement": "",
                        "voice_gender": "",
                    }
                    for i, indicator in enumerate(response["high_risk_indicators"])
                ]

        _save_result(check_id, response)
        yield f"data: {json.dumps({'type': 'result', 'data': response})}\n\n"

        # If risk > 30%, suggest remix
        risk_pct = response.get("risk_percentage", 0)
        if risk_pct > 30 and media_type in ("video", "image", "audio"):
            yield f"data: {json.dumps({'type': 'ask_user', 'action': 'remix', 'message': f'Your content has {risk_pct}% risk of cultural backlash. Would you like to auto-remix it to reduce risk?', 'check_id': check_id})}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/compliance/{check_id}")
async def get_results(check_id: str):
    """Get results for a previous compliance check."""
    result_path = RESULTS_DIR / f"{check_id}.json"
    if not result_path.exists():
        return JSONResponse(status_code=404, content={"error": "Not found"})
    with open(result_path, "r", encoding="utf-8") as f:
        return JSONResponse(content=json.load(f))


@app.post("/api/compliance/{check_id}/remix")
async def remix_content(check_id: str):
    """
    Trigger remediation for a previously checked asset.
    Called when user confirms "Yes, remix it".
    Streams SSE with remediation node status updates.
    """
    # Load previous result
    result_path = RESULTS_DIR / f"{check_id}.json"
    if not result_path.exists():
        return JSONResponse(status_code=404, content={"error": "Check not found"})

    with open(result_path, "r", encoding="utf-8") as f:
        prev_result = json.load(f)

    media_type = prev_result.get("media_type", "")
    file_path = str(UPLOAD_DIR / f"{check_id}_{prev_result.get('filename', '')}")

    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"error": "Original file not found"})

    logger.info(f"[Remix] Starting remediation for {check_id} ({media_type})")

    def generate_remix_events():
        # Step 1: Signal start
        yield f"data: {json.dumps({'type': 'node_status', 'node': 'remix_start', 'status': 'completed', 'description': 'Starting content remediation...'})}\n\n"

        if media_type == "video":
            # Import video remediation steps
            import asyncio
            from jusads_video_compliance.step3_visual_remediation import remediate_visual
            from jusads_video_compliance.step4_audio_remediation import remediate_audio
            from jusads_video_compliance.step5_compose_final import compose_final

            violations = prev_result.get("violations", [])
            visual_violations = [v for v in violations if v.get("type") == "visual"]
            audio_violations = [v for v in violations if v.get("type") == "audio"]
            market = prev_result.get("market", "malaysia")
            ethnicity = prev_result.get("ethnicity", "malay")

            output_dir = str(RESULTS_DIR / check_id)
            os.makedirs(output_dir, exist_ok=True)

            # Visual remediation
            if visual_violations:
                yield f"data: {json.dumps({'type': 'node_status', 'node': 'visual_remediation', 'status': 'running', 'description': f'Remediating {len(visual_violations)} visual violations (Gemini + Veo)...'})}\n\n"
                try:
                    visual_results = asyncio.run(remediate_visual(file_path, visual_violations, output_dir))
                    fixed = sum(1 for r in visual_results if r["success"])
                    yield f"data: {json.dumps({'type': 'node_status', 'node': 'visual_remediation', 'status': 'completed', 'description': f'Visual: {fixed}/{len(visual_violations)} fixed'})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'node_status', 'node': 'visual_remediation', 'status': 'error', 'description': str(e)})}\n\n"
                    visual_results = []
            else:
                visual_results = []

            # Audio remediation
            if audio_violations:
                yield f"data: {json.dumps({'type': 'node_status', 'node': 'audio_remediation', 'status': 'running', 'description': f'Remediating {len(audio_violations)} audio violations (ElevenLabs)...'})}\n\n"
                try:
                    audio_results = asyncio.run(remediate_audio(file_path, audio_violations, output_dir, market, ethnicity, "ms"))
                    fixed = sum(1 for r in audio_results if r["success"])
                    yield f"data: {json.dumps({'type': 'node_status', 'node': 'audio_remediation', 'status': 'completed', 'description': f'Audio: {fixed}/{len(audio_violations)} fixed'})}\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'type': 'node_status', 'node': 'audio_remediation', 'status': 'error', 'description': str(e)})}\n\n"
                    audio_results = []
            else:
                audio_results = []

            # Compose final
            yield f"data: {json.dumps({'type': 'node_status', 'node': 'compose_final', 'status': 'running', 'description': 'Composing final video...'})}\n\n"
            final_path = compose_final(file_path, visual_results, audio_results, output_dir)
            yield f"data: {json.dumps({'type': 'node_status', 'node': 'compose_final', 'status': 'completed', 'description': f'Final video: {final_path}'})}\n\n"

            remix_result = {
                "check_id": check_id,
                "status": "remixed",
                "final_video": final_path,
                "visual_fixed": sum(1 for r in visual_results if r["success"]),
                "audio_fixed": sum(1 for r in audio_results if r["success"]),
            }

        elif media_type == "image":
            # Image remediation
            yield f"data: {json.dumps({'type': 'node_status', 'node': 'image_remediation', 'status': 'running', 'description': 'Regenerating compliant image (Gemini Flash Image)...'})}\n\n"
            try:
                from jusads_image_compliance.image_remediator import ImageRemediator
                remediator = ImageRemediator()
                remed_result = remediator.remediate(
                    image_path=file_path,
                    compliance_result=prev_result,
                    market=prev_result.get("market", "malaysia"),
                    ethnicity=prev_result.get("ethnicity", "malay"),
                )
                yield f"data: {json.dumps({'type': 'node_status', 'node': 'image_remediation', 'status': 'completed', 'description': 'Image remediated successfully'})}\n\n"
                remix_result = {"check_id": check_id, "status": "remixed", **remed_result}
            except Exception as e:
                yield f"data: {json.dumps({'type': 'node_status', 'node': 'image_remediation', 'status': 'error', 'description': str(e)})}\n\n"
                remix_result = {"check_id": check_id, "status": "error", "error": str(e)}

        elif media_type == "audio":
            # Audio: re-generate compliant script via text remediator
            yield f"data: {json.dumps({'type': 'node_status', 'node': 'text_remediation', 'status': 'running', 'description': 'Generating compliant script...'})}\n\n"
            try:
                from jusads_text_compliance.text_remediator import TextRemediator
                remediator = TextRemediator()
                transcript = prev_result.get("transcript", "")
                remed_result = remediator.remediate(
                    ad_text=transcript,
                    compliance_result=prev_result,
                    market=prev_result.get("market", "malaysia"),
                    ethnicity=prev_result.get("ethnicity", "malay"),
                )
                yield f"data: {json.dumps({'type': 'node_status', 'node': 'text_remediation', 'status': 'completed', 'description': 'Compliant script generated'})}\n\n"
                remix_result = {"check_id": check_id, "status": "remixed", **remed_result}
            except Exception as e:
                yield f"data: {json.dumps({'type': 'node_status', 'node': 'text_remediation', 'status': 'error', 'description': str(e)})}\n\n"
                remix_result = {"check_id": check_id, "status": "error", "error": str(e)}

        else:
            # Text: re-generate compliant copy
            yield f"data: {json.dumps({'type': 'node_status', 'node': 'text_remediation', 'status': 'running', 'description': 'Rewriting compliant copy...'})}\n\n"
            try:
                from jusads_text_compliance.text_remediator import TextRemediator
                remediator = TextRemediator()
                remed_result = remediator.remediate(
                    ad_text=prev_result.get("transcript", ""),
                    compliance_result=prev_result,
                    market=prev_result.get("market", "malaysia"),
                    ethnicity=prev_result.get("ethnicity", "malay"),
                )
                yield f"data: {json.dumps({'type': 'node_status', 'node': 'text_remediation', 'status': 'completed', 'description': 'Compliant copy generated'})}\n\n"
                remix_result = {"check_id": check_id, "status": "remixed", **remed_result}
            except Exception as e:
                yield f"data: {json.dumps({'type': 'node_status', 'node': 'text_remediation', 'status': 'error', 'description': str(e)})}\n\n"
                remix_result = {"check_id": check_id, "status": "error", "error": str(e)}

        # Save remix result
        remix_path = RESULTS_DIR / f"{check_id}_remix.json"
        with open(remix_path, "w", encoding="utf-8") as f_out:
            json.dump(remix_result, f_out, indent=2, ensure_ascii=False)

        yield f"data: {json.dumps({'type': 'remix_result', 'data': remix_result})}\n\n"

    return StreamingResponse(
        generate_remix_events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _save_result(check_id: str, data: dict):
    result_path = RESULTS_DIR / f"{check_id}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _extract_clip(video_path: str, start: float, end: float, output_path: str) -> bool:
    duration = end - start
    if duration <= 0:
        duration = 2.0
    try:
        cmd = [
            "ffmpeg", "-y", "-ss", str(start), "-i", video_path,
            "-t", str(duration), "-c:v", "libx264", "-c:a", "aac",
            "-movflags", "+faststart", output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception as e:
        logger.error(f"Clip extraction failed: {e}")
        return False


def _parse_persona(persona_str: str) -> dict | None:
    if not persona_str or persona_str == "No specific persona (ethnicity: all)":
        return None
    try:
        return json.loads(persona_str)
    except (json.JSONDecodeError, TypeError):
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STATIC MOUNTS (must be LAST)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if FRONTEND_DIST.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

if SIMPLE_FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(SIMPLE_FRONTEND), html=True), name="simple-frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
