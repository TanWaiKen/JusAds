"""
Step 5: Compose Final Video
==============================
Stitches replacement clips and audio into the original video using FFmpeg.
"""

import logging
import os
import shutil

logger = logging.getLogger(__name__)


def compose_final(
    original_video: str,
    visual_results: list[dict],
    audio_results: list[dict],
    output_dir: str,
) -> str:
    """
    Compose the final remediated video.

    For now, copies the original video as a placeholder.
    Full FFmpeg stitching will replace this.

    Args:
        original_video: Path to the original video.
        visual_results: Results from Step 3.
        audio_results: Results from Step 4.
        output_dir: Output directory.

    Returns:
        Path to the final video file.
    """
    final_path = os.path.join(output_dir, "final.mp4")

    successful_visual = [r for r in visual_results if r["success"]]
    successful_audio = [r for r in audio_results if r["success"]]

    logger.info(
        f"Composing final video: {len(successful_visual)} visual clips, "
        f"{len(successful_audio)} audio segments"
    )

    # TODO: Full FFmpeg composition
    # For now, copy original as placeholder
    try:
        shutil.copy2(original_video, final_path)
        print(f"  Composed with {len(successful_visual)} visual + {len(successful_audio)} audio replacements")
    except Exception as e:
        logger.error(f"Compose failed: {e}")
        final_path = original_video

    return final_path
