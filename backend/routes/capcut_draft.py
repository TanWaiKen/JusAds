"""
routes/capcut_draft.py
──────────────────────
CapCut draft generation API — creates exportable CapCut/JianYing drafts
that users can import into CapCut desktop app.

Supports:
  - Video + image overlay (image layer on top of video)
  - Transitions (fade, dissolve, etc.)
  - Downloadable draft ZIP for import into CapCut
"""

import logging
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/capcut", tags=["capcut-draft"])

# ── pycapcut import ───────────────────────────────────────────────────────────
try:
    import pycapcut as cc
    CAPCUT_AVAILABLE = True
    logger.info("[CapCutDraft] pycapcut loaded")
except ImportError:
    try:
        import pyJianYingDraft as cc
        CAPCUT_AVAILABLE = True
        logger.info("[CapCutDraft] pyJianYingDraft loaded as fallback")
    except ImportError:
        CAPCUT_AVAILABLE = False
        cc = None
        logger.warning("[CapCutDraft] No CapCut library available")

# ── Config ────────────────────────────────────────────────────────────────────
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
DRAFTS_DIR = Path(tempfile.gettempdir()) / "jusads_capcut_drafts"
DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

# FFmpeg for duration detection
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")


def _get_media_duration(file_path: str) -> Optional[float]:
    """Get media duration in seconds using ffprobe."""
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip()) if result.returncode == 0 else None
    except Exception:
        return None


@router.get("/status")
async def capcut_status() -> JSONResponse:
    """Check if CapCut draft generation is available."""
    capcut_drafts_path = _find_capcut_drafts_folder()
    return JSONResponse({
        "available": CAPCUT_AVAILABLE,
        "library": "pycapcut" if CAPCUT_AVAILABLE else None,
        "drafts_dir": str(DRAFTS_DIR),
        "capcut_drafts_folder": capcut_drafts_path,
        "capcut_installed": capcut_drafts_path is not None,
    })


@router.post("/generate-draft")
async def generate_draft(
    video: UploadFile = File(...),
    image: UploadFile = File(...),
    draft_name: str = Form(default="tiger_sugar_promo"),
    transition_type: str = Form(default="fade"),
    image_duration_sec: float = Form(default=3.0),
    image_start_sec: float = Form(default=0.0),
    width: int = Form(default=1080),
    height: int = Form(default=1920),
    fps: int = Form(default=30),
) -> JSONResponse:
    """Generate a CapCut draft with video + image overlay + transition.

    The image is placed as a layer on top of the video.
    A transition is added between the image intro and the main video.

    Returns a JSON with download URL for the draft ZIP.
    """
    if not CAPCUT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="CapCut draft generation unavailable. Install pycapcut: pip install pycapcut"
        )

    # Save uploaded files to temp
    temp_dir = Path(tempfile.mkdtemp(prefix="capcut_upload_"))
    video_path = temp_dir / video.filename
    image_path = temp_dir / image.filename

    try:
        with open(video_path, "wb") as f:
            content = await video.read()
            f.write(content)

        with open(image_path, "wb") as f:
            content = await image.read()
            f.write(content)

        # Generate the draft
        result = _create_image_overlay_draft(
            video_path=str(video_path),
            image_path=str(image_path),
            draft_name=draft_name,
            transition_type=transition_type,
            image_duration_sec=image_duration_sec,
            image_start_sec=image_start_sec,
            width=width,
            height=height,
            fps=fps,
        )

        if not result:
            raise HTTPException(status_code=500, detail="Draft generation failed")

        return JSONResponse({
            "success": True,
            "draft_name": draft_name,
            "download_url": f"/api/capcut/download/{draft_name}",
            "instructions": _get_import_instructions(),
            **result,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error("[CapCutDraft] Generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Draft generation failed: {str(e)}")


@router.post("/generate-draft-local")
async def generate_draft_from_local(
    draft_name: str = Form(default="tiger_sugar_promo"),
    transition_type: str = Form(default="fade"),
    image_duration_sec: float = Form(default=3.0),
    image_start_sec: float = Form(default=0.0),
    width: int = Form(default=1080),
    height: int = Form(default=1920),
    fps: int = Form(default=30),
) -> JSONResponse:
    """Generate a CapCut draft using the local test assets (Test Video.mp4 + Boba Infographic.jpg).

    Convenience endpoint for testing without file uploads.
    """
    if not CAPCUT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="CapCut draft generation unavailable. Install pycapcut: pip install pycapcut"
        )

    video_path = str(ASSETS_DIR / "Test Video.mp4")
    image_path = str(ASSETS_DIR / "images" / "Tiger Sugar Boba" / "Boba Infographic.jpg")

    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Test video not found: {video_path}")
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail=f"Test image not found: {image_path}")

    result = _create_image_overlay_draft(
        video_path=video_path,
        image_path=image_path,
        draft_name=draft_name,
        transition_type=transition_type,
        image_duration_sec=image_duration_sec,
        image_start_sec=image_start_sec,
        width=width,
        height=height,
        fps=fps,
    )

    if not result:
        raise HTTPException(status_code=500, detail="Draft generation failed")

    return JSONResponse({
        "success": True,
        "draft_name": draft_name,
        "download_url": f"/api/capcut/download/{draft_name}",
        "instructions": _get_import_instructions(),
        **result,
    })


@router.get("/download/{draft_name}")
async def download_draft(draft_name: str) -> FileResponse:
    """Download the generated CapCut draft as a ZIP file.

    The user extracts this into their CapCut Drafts folder.
    """
    draft_folder = DRAFTS_DIR / draft_name
    zip_path = DRAFTS_DIR / f"{draft_name}.zip"

    if not draft_folder.exists():
        raise HTTPException(status_code=404, detail=f"Draft '{draft_name}' not found")

    # Create ZIP of the draft folder
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(draft_folder):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(DRAFTS_DIR)
                zf.write(file_path, arcname)

    return FileResponse(
        path=str(zip_path),
        filename=f"{draft_name}.zip",
        media_type="application/zip",
    )


@router.get("/draft-files/{draft_name}")
async def get_draft_files(draft_name: str) -> JSONResponse:
    """Return draft files as JSON key-value pairs (filename → content).

    Used by the frontend File System Access API to write files directly
    into the user's CapCut Drafts folder without needing a ZIP extraction step.
    Works even when the backend is hosted on a remote server.
    """
    draft_folder = DRAFTS_DIR / draft_name

    if not draft_folder.exists():
        raise HTTPException(status_code=404, detail=f"Draft '{draft_name}' not found")

    files: dict[str, str] = {}
    for file_path in draft_folder.iterdir():
        if file_path.is_file() and file_path.suffix == ".json":
            files[file_path.name] = file_path.read_text(encoding="utf-8")

    if not files:
        raise HTTPException(status_code=404, detail="No draft files found")

    return JSONResponse(files)


@router.get("/instructions")
async def get_instructions() -> JSONResponse:
    """Get instructions on how to import the draft into CapCut."""
    return JSONResponse({
        "instructions": _get_import_instructions(),
        "capcut_drafts_folder": _find_capcut_drafts_folder(),
    })


@router.post("/install-to-capcut/{draft_name}")
async def install_to_capcut(draft_name: str) -> JSONResponse:
    """Copy the generated draft directly into CapCut's local Drafts folder.

    This automates the manual step of extracting the ZIP.
    After calling this, just open/restart CapCut and the draft appears.
    """
    capcut_folder = _find_capcut_drafts_folder()
    if not capcut_folder:
        raise HTTPException(
            status_code=404,
            detail="CapCut Drafts folder not found on this machine. Install CapCut desktop first."
        )

    source = DRAFTS_DIR / draft_name
    if not source.exists():
        raise HTTPException(status_code=404, detail=f"Draft '{draft_name}' not found. Generate it first.")

    target = Path(capcut_folder) / draft_name

    try:
        # Copy draft folder to CapCut's drafts directory
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)

        logger.info("[CapCutDraft] Installed draft '%s' to CapCut: %s", draft_name, target)
        return JSONResponse({
            "success": True,
            "message": f"Draft '{draft_name}' installed to CapCut. Open CapCut and find it in your projects list.",
            "installed_path": str(target),
            "next_steps": [
                "1. Open CapCut desktop app.",
                "2. The draft should appear on your Home/Projects screen.",
                "3. If not visible, close and reopen CapCut to refresh.",
                "4. Click the draft to open — your video + image overlay is ready to edit!",
            ]
        })
    except Exception as e:
        logger.error("[CapCutDraft] Install failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to install draft: {str(e)}")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _create_image_overlay_draft(
    video_path: str,
    image_path: str,
    draft_name: str,
    transition_type: str,
    image_duration_sec: float,
    image_start_sec: float,
    width: int,
    height: int,
    fps: int,
) -> Optional[dict]:
    """Create a CapCut draft with an image overlaid on top of the video with a transition."""
    try:
        drafts_path = str(DRAFTS_DIR)
        draft_folder = cc.DraftFolder(drafts_path)

        # Create the draft project
        script = draft_folder.create_draft(draft_name, width, height, fps, allow_replace=True)

        # ── Track 1: Main video (background layer) ────────────────────────────
        script.add_track(cc.TrackType.video, "main_video", relative_index=1)

        video_duration = _get_media_duration(video_path)
        video_dur_us = int((video_duration or 10) * 1_000_000)

        video_seg = cc.VideoSegment(
            video_path,
            cc.Timerange(0, video_dur_us),
        )
        script.add_segment(video_seg, "main_video")

        # ── Track 2: Image overlay (foreground layer, on top of video) ────────
        script.add_track(cc.TrackType.video, "image_overlay", relative_index=2)

        image_start_us = int(image_start_sec * 1_000_000)
        image_dur_us = int(image_duration_sec * 1_000_000)

        # Create image segment with optional opacity/scale settings
        image_seg = cc.VideoSegment(
            image_path,
            cc.Timerange(image_start_us, image_dur_us),
            clip_settings=cc.ClipSettings(alpha=0.9),  # Slightly transparent
        )

        # Add intro animation to the image overlay (fade-in effect)
        try:
            image_seg.add_animation(cc.IntroType.渐显)  # Fade in
        except (AttributeError, Exception) as e:
            logger.warning("[CapCutDraft] Could not add image intro animation: %s", e)

        script.add_segment(image_seg, "image_overlay")

        # ── Add transition between segments on main video track ───────────────
        # Transitions in pycapcut are added between consecutive segments.
        # We split the video into two parts and add a transition between them.
        # Instead, add a transition effect on the image overlay segment.
        try:
            transition_map = {
                "fade": "淡化",
                "dissolve": "溶解",
                "wipeleft": "向左擦除",
                "wiperight": "向右擦除",
                "slide": "推移",
                "zoom": "放大",
            }
            # Try to get the transition type enum
            trans_name = transition_map.get(transition_type, "淡化")
            trans_type = getattr(cc.TransitionType, trans_name, None)

            if trans_type:
                # Add transition to the main video track
                # pycapcut transitions go between segments — so we need 2 segments
                # Let's split video into 2 parts with transition between them
                split_point_us = video_dur_us // 2
                half1_dur = split_point_us
                half2_dur = video_dur_us - split_point_us

                # Remove the single video segment and add two segments with transition
                # Re-create the track approach
                script.add_track(cc.TrackType.video, "video_with_transition", relative_index=1)

                seg1 = cc.VideoSegment(
                    video_path,
                    cc.Timerange(0, half1_dur),
                    source_timerange=cc.Timerange(0, half1_dur),
                )
                seg2 = cc.VideoSegment(
                    video_path,
                    cc.Timerange(0, half2_dur),
                    source_timerange=cc.Timerange(half1_dur, half2_dur),
                )

                script.add_segment(seg1, "video_with_transition")
                script.add_segment(seg2, "video_with_transition", transition=trans_type)

                logger.info("[CapCutDraft] Added '%s' transition at video midpoint", transition_type)
            else:
                logger.warning("[CapCutDraft] Transition type '%s' not found, skipping", transition_type)

        except Exception as e:
            logger.warning("[CapCutDraft] Could not add transition: %s", e)

        # ── Save the draft ────────────────────────────────────────────────────
        script.save()

        logger.info("[CapCutDraft] Draft '%s' created successfully at: %s", draft_name, drafts_path)
        return {
            "draft_folder": drafts_path,
            "video_duration_sec": video_duration,
            "image_duration_sec": image_duration_sec,
            "image_start_sec": image_start_sec,
            "transition": transition_type,
            "canvas": f"{width}x{height}",
        }

    except Exception as e:
        logger.error("[CapCutDraft] Draft creation failed: %s", e, exc_info=True)
        return None


def _get_import_instructions() -> dict:
    """Return user-friendly instructions for importing the draft into CapCut."""
    capcut_folder = _find_capcut_drafts_folder()
    return {
        "title": "How to Import Your Draft into CapCut",
        "steps": [
            "1. Download the draft ZIP file using the download button below.",
            "2. Open CapCut desktop application.",
            "3. Go to Settings (gear icon) → find 'Drafts Location' — this shows your CapCut Drafts folder path.",
            "4. Extract the downloaded ZIP file directly into that Drafts folder.",
            "5. Go back to CapCut → on the Home screen, your new draft should appear in the project list.",
            "6. If it doesn't appear immediately, close and reopen CapCut, or open any existing project and go back to refresh the list.",
            "7. Open the draft — you'll see the video with image overlay and transition ready to edit!",
        ],
        "tips": [
            f"Your CapCut Drafts folder: {capcut_folder}" if capcut_folder else "The typical CapCut Drafts folder is: C:\\Users\\<YourName>\\AppData\\Local\\CapCut\\User Data\\Projects\\com.lveditor.draft",
            "On Mac: ~/Library/Application Support/CapCut/User Data/Projects/com.lveditor.draft",
            "Make sure you extract the folder (not just the ZIP) into the Drafts directory.",
            "The draft includes the image as an overlay layer — you can adjust its position, duration, and opacity in CapCut.",
        ],
        "note": "You do NOT need to open CapCut programmatically. Just place the draft folder in the right location and CapCut picks it up automatically.",
        "auto_install_available": capcut_folder is not None,
    }


def _find_capcut_drafts_folder() -> Optional[str]:
    """Auto-detect the CapCut Drafts folder on Windows/Mac."""
    import platform

    if platform.system() == "Windows":
        # Standard Windows path
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            candidate = os.path.join(local_appdata, "CapCut", "User Data", "Projects", "com.lveditor.draft")
            if os.path.isdir(candidate):
                return candidate
    elif platform.system() == "Darwin":
        # macOS
        home = os.path.expanduser("~")
        candidate = os.path.join(home, "Library", "Application Support", "CapCut", "User Data", "Projects", "com.lveditor.draft")
        if os.path.isdir(candidate):
            return candidate

    return None


# ── Dual Output: Draft + Rendered Video (Task 9) ──────────────────────────────


def _render_video_ffmpeg(
    video_path: str,
    image_path: str,
    output_path: str,
    image_duration_sec: float = 3.0,
    image_start_sec: float = 0.0,
    transition_type: str = "fade",
    width: int = 1080,
    height: int = 1920,
) -> Optional[str]:
    """Render the final video using ffmpeg with image overlay and transition.

    Overlays the image on top of the video for the specified duration,
    with a fade-in/fade-out transition effect.

    Args:
        video_path: Path to the source video.
        image_path: Path to the overlay image.
        output_path: Where to write the rendered video.
        image_duration_sec: How long the image overlay is visible.
        image_start_sec: When the image overlay starts.
        transition_type: Transition effect (fade, dissolve).
        width: Output width.
        height: Output height.

    Returns:
        Path to rendered file on success, None on failure.
    """
    import subprocess

    try:
        # Build ffmpeg filter complex for image overlay with fade
        fade_in_duration = min(0.5, image_duration_sec / 4)
        fade_out_start = image_start_sec + image_duration_sec - fade_in_duration

        filter_complex = (
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black@0,"
            f"fade=in:st={image_start_sec}:d={fade_in_duration}:alpha=1,"
            f"fade=out:st={fade_out_start}:d={fade_in_duration}:alpha=1[overlay];"
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2[base];"
            f"[base][overlay]overlay=0:0:enable='between(t,{image_start_sec},{image_start_sec + image_duration_sec})'"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", image_path,
            "-filter_complex", filter_complex,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            "-movflags", "+faststart",
            output_path,
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=120)

        if result.returncode == 0 and os.path.exists(output_path):
            logger.info("[CapCutDraft] Rendered video: %s", output_path)
            return output_path
        else:
            logger.error("[CapCutDraft] ffmpeg render failed: %s", result.stderr.decode()[:500])
            return None

    except Exception as e:
        logger.error("[CapCutDraft] Render failed: %s", e)
        return None


@router.post("/generate-dual")
async def generate_draft_with_render(
    video: UploadFile = File(...),
    image: UploadFile = File(...),
    draft_name: str = Form(default="dual_output_promo"),
    transition_type: str = Form(default="fade"),
    image_duration_sec: float = Form(default=3.0),
    image_start_sec: float = Form(default=0.0),
    width: int = Form(default=1080),
    height: int = Form(default=1920),
    fps: int = Form(default=30),
) -> JSONResponse:
    """Generate BOTH a CapCut draft file AND a rendered MP4 video.

    Produces two outputs:
    1. CapCut draft ZIP (importable into CapCut desktop)
    2. Rendered MP4 via ffmpeg (ready to use immediately)

    If CapCut draft fails, rendered video is still produced (and vice versa).
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="capcut_dual_"))
    video_path = temp_dir / video.filename
    image_path = temp_dir / image.filename

    try:
        with open(video_path, "wb") as f:
            f.write(await video.read())
        with open(image_path, "wb") as f:
            f.write(await image.read())

        results = {
            "draft": None,
            "rendered": None,
            "draft_status": "skipped",
            "render_status": "skipped",
        }

        # 1. Generate CapCut draft
        if CAPCUT_AVAILABLE:
            try:
                draft_result = _create_image_overlay_draft(
                    video_path=str(video_path),
                    image_path=str(image_path),
                    draft_name=draft_name,
                    transition_type=transition_type,
                    image_duration_sec=image_duration_sec,
                    image_start_sec=image_start_sec,
                    width=width,
                    height=height,
                    fps=fps,
                )
                if draft_result:
                    results["draft"] = {
                        "download_url": f"/api/capcut/download/{draft_name}",
                        **draft_result,
                    }
                    results["draft_status"] = "completed"
                else:
                    results["draft_status"] = "failed"
            except Exception as e:
                logger.error("[CapCutDraft] Draft generation failed: %s", e)
                results["draft_status"] = "failed"
        else:
            results["draft_status"] = "unavailable"

        # 2. Render via ffmpeg
        try:
            render_output = str(temp_dir / f"{draft_name}_rendered.mp4")
            rendered_path = _render_video_ffmpeg(
                video_path=str(video_path),
                image_path=str(image_path),
                output_path=render_output,
                image_duration_sec=image_duration_sec,
                image_start_sec=image_start_sec,
                transition_type=transition_type,
                width=width,
                height=height,
            )
            if rendered_path:
                # Upload to S3
                from shared.s3_client import upload_file_public
                import uuid

                s3_key = f"capcut_renders/{draft_name}/{uuid.uuid4().hex[:6]}_rendered.mp4"
                try:
                    s3_url = upload_file_public(rendered_path, s3_key)
                    results["rendered"] = {
                        "s3_key": s3_key,
                        "s3_url": s3_url,
                    }
                    results["render_status"] = "completed"
                except Exception as s3_err:
                    logger.warning("[CapCutDraft] S3 upload failed: %s", s3_err)
                    results["render_status"] = "upload_failed"
            else:
                results["render_status"] = "render_failed"
        except Exception as e:
            logger.error("[CapCutDraft] Render step failed: %s", e)
            results["render_status"] = "failed"

        return JSONResponse({
            "success": results["draft_status"] == "completed" or results["render_status"] == "completed",
            "draft_name": draft_name,
            **results,
        })

    except Exception as e:
        logger.error("[CapCutDraft] Dual generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Dual output generation failed: {str(e)}")
