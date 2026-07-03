# Video Ad Generation Guide

## Introduction
The Video Ad Generation tool stitches visual elements (images) with auditory elements (voiceover, sound effects, or music) using `ffmpeg` local command line tools to compile a final 3-10 second video advertisement.

## Steps for Generation
1. **Inputs**: The tool requires an image URL/file path and an audio URL/file path.
2. **Local Assembly**:
   - Download the image and audio locally if they are URLs.
   - Run `ffmpeg` to merge them:
     `ffmpeg -loop 1 -i {image_path} -i {audio_path} -c:v libx264 -tune stillimage -c:a aac -b:a 192k -pix_fmt yuv420p -shortest {output_path}`
3. **S3 Upload**: Upload the compiled video (.mp4) to AWS S3 under `generated_ads/{project_id}/{task_id}/{filename}.mp4`.
4. **Supabase Record**: Insert a new record into `public.generated_ads` with type `video` and update the canvas node state.
