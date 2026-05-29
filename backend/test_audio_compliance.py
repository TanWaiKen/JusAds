import sys
import json
import logging
from pathlib import Path

# Setup logging to see the process
logging.basicConfig(level=logging.INFO)

# Import the new tool
from jusads_text_compliance.tools import check_audio_compliance

def test_audio_culture_compliance():
    # Use the test mp3 we successfully transcribed earlier
    mp3_path = str(Path(__file__).parent / "assets" / "cantonese_ad_test.mp3")
    print(f"\n--- Starting Audio Culture Compliance Check ---")
    print(f"Target file: {mp3_path}")
    print("Market: malaysia | Ethnicity: chinese | Age Group: all_ages\n")
    
    # The LangChain @tool can be invoked directly
    result_json = check_audio_compliance.invoke({
        "media_path": mp3_path,
        "market": "malaysia",
        "ethnicity": "chinese",
        "age_group": "all_ages"
    })
    
    print("\n--- Final Compliance Output ---")
    # Pretty print the resulting JSON
    try:
        parsed = json.loads(result_json)
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Raw output:")
        print(result_json)
        print(f"\nError parsing JSON: {e}")

if __name__ == "__main__":
    test_audio_culture_compliance()
