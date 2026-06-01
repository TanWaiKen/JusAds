import logging
import os
import re
import subprocess
import tempfile
import uuid

logger = logging.getLogger(__name__)

class VideoAssembler:
    """
    Assembles a final compliant video using FFmpeg.
    It takes the original video, splices in the Veo B-Rolls at the correct timestamps,
    and replaces the entire audio track with the ElevenLabs voiceover.
    """

    def _parse_timestamp(self, timestamp: str) -> tuple[int, int]:
        """Parses a timestamp like '[00:03-00:08]' into start and end seconds."""
        match = re.search(r'\[(\d+):(\d+)-(\d+):(\d+)\]', timestamp)
        if match:
            m1, s1, m2, s2 = map(int, match.groups())
            return (m1 * 60 + s1), (m2 * 60 + s2)
        return 0, 0

    def _get_video_duration(self, video_path: str) -> float:
        """Gets the duration of a video using ffprobe."""
        try:
            cmd = [
                'ffprobe', '-v', 'error', '-show_entries',
                'format=duration', '-of',
                'default=noprint_wrappers=1:nokey=1', video_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            logger.error(f"Failed to get video duration for {video_path}: {e}")
            return 30.0 # fallback

    def assemble_video(self, original_video: str, broll_prompts: list[dict], audio_path: str) -> str | None:
        """
        Assembles the final video by slicing the original video and inserting the generated B-Rolls.
        """
        try:
            logger.info("Starting final video assembly using FFmpeg...")
            
            # 1. Parse and sort the B-Roll timestamps
            edits = []
            for broll in broll_prompts:
                vid_path = broll.get("generated_video_path")
                ts = broll.get("timestamp")
                if vid_path and ts and os.path.exists(vid_path):
                    start_sec, end_sec = self._parse_timestamp(ts)
                    edits.append({"start": start_sec, "end": end_sec, "path": vid_path})
            
            edits.sort(key=lambda x: x["start"])
            
            orig_duration = self._get_video_duration(original_video)
            
            # We will generate a list of video segments to concatenate
            # To ensure compatibility, we re-encode and scale all segments to 1280x720, 30fps
            segment_files = []
            
            temp_dir = tempfile.mkdtemp(prefix="langhub_assemble_")
            
            current_time = 0.0
            
            for idx, edit in enumerate(edits):
                # If there's a gap between current_time and the start of this edit, extract that from the original video
                if edit["start"] > current_time:
                    seg_out = os.path.join(temp_dir, f"seg_{idx}_orig.mp4")
                    dur = edit["start"] - current_time
                    cmd = [
                        'ffmpeg', '-y', '-ss', str(current_time), '-t', str(dur), '-i', original_video,
                        '-vf', 'scale=1280:720,setsar=1,fps=30', '-c:v', 'libx264', '-an', seg_out
                    ]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    segment_files.append(seg_out)
                
                # Now process the B-Roll edit. Since Veo generates at least 4s, we MUST trim it
                # to the exact duration of the edit (end - start) so it doesn't push the timeline out of sync.
                broll_out = os.path.join(temp_dir, f"seg_{idx}_broll.mp4")
                edit_duration = float(edit["end"] - edit["start"])
                cmd = [
                    'ffmpeg', '-y', '-i', edit["path"], '-t', str(edit_duration),
                    '-vf', 'scale=1280:720,setsar=1,fps=30', '-c:v', 'libx264', '-an', broll_out
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                segment_files.append(broll_out)
                
                # Move current time to the end of this edit
                current_time = float(edit["end"])

            # After the last edit, if there's still original video left, extract the tail
            if current_time < orig_duration:
                seg_out = os.path.join(temp_dir, f"seg_tail_orig.mp4")
                dur = orig_duration - current_time
                cmd = [
                    'ffmpeg', '-y', '-ss', str(current_time), '-t', str(dur), '-i', original_video,
                    '-vf', 'scale=1280:720,setsar=1,fps=30', '-c:v', 'libx264', '-an', seg_out
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                segment_files.append(seg_out)
            
            # If there are no edits, just scale the original video
            if not segment_files:
                seg_out = os.path.join(temp_dir, "seg_full_orig.mp4")
                cmd = [
                    'ffmpeg', '-y', '-i', original_video,
                    '-vf', 'scale=1280:720,setsar=1,fps=30', '-c:v', 'libx264', '-an', seg_out
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                segment_files.append(seg_out)

            # Create concat list
            concat_list_path = os.path.join(temp_dir, "concat_list.txt")
            with open(concat_list_path, "w") as f:
                for seg in segment_files:
                    # Escape path for FFmpeg
                    clean_path = seg.replace('\\', '/')
                    f.write(f"file '{clean_path}'\n")

            # Concat the videos and add the audio
            output_dir = os.path.join("backend", "assets", "remediated")
            os.makedirs(output_dir, exist_ok=True)
            final_filename = f"final_{uuid.uuid4().hex[:8]}.mp4"
            final_path = os.path.join(output_dir, final_filename)

            concat_cmd = [
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_list_path,
                '-i', audio_path,
                '-c:v', 'copy', '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
                '-shortest', # Truncate to whichever is shorter
                final_path
            ]
            
            logger.info("Concatenating segments and merging audio...")
            subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            logger.info(f"Final video successfully assembled at: {final_path}")
            return final_path

        except Exception as e:
            logger.error(f"Video assembly failed: {e}")
            return None
