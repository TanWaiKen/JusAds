import sys
import logging
from pathlib import Path

# Add backend directory to sys.path so config can be imported
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from jusads_transcription.transcriber import Transcriber

logging.basicConfig(level=logging.INFO)

def test_transcription():
    mp3_path = str(Path(__file__).parent.parent / "assets" / "Test Video.mp4")
    print(f"Testing transcription for: {mp3_path}")
    
    transcriber = Transcriber()
    try:
        result = transcriber.transcribe_media(mp3_path)
        print("\n--- Transcription Result ---")
        print(result)
        print("----------------------------\n")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    test_transcription()
