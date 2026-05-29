import logging
import os
import uuid
import requests
from config import ELEVENLABS_API_KEY

logger = logging.getLogger(__name__)

class AudioGenerator:
    """
    Handles generation of localized voiceovers using ElevenLabs TTS.
    """
    
    # Mapping of target markets to specific ElevenLabs Voice IDs.
    # These IDs can be customized to fit the exact persona desired for each market.
    VOICE_MAPPING = {
        "malaysia": "cgSgspJ2msm6clMCkdW9",  # Example ID for a suitable Asian/Malaysian accented voice
        "singapore": "cgSgspJ2msm6clMCkdW9", 
        "indonesia": "ThT5KcBeYPX3keUQqHPh",
        "default": "21m00Tcm4TlvDq8ikWAM",   # Default (Rachel)
    }

    def __init__(self):
        self.api_key = ELEVENLABS_API_KEY
        if not self.api_key:
            logger.warning("ELEVENLABS_API_KEY is missing. Audio generation will fail unless it is provided.")

    def get_voice_id(self, market: str) -> str:
        """Returns the appropriate voice ID for the market."""
        return self.VOICE_MAPPING.get(market.lower(), self.VOICE_MAPPING["default"])

    def generate_audio(self, text: str, market: str = "default") -> str | None:
        """
        Generates TTS audio using ElevenLabs and saves it to a local mp3 file.
        Returns the path to the saved audio file, or None if it fails.
        """
        if not self.api_key:
            logger.error("Cannot generate audio: ELEVENLABS_API_KEY is not set in environment.")
            return None
            
        if not text.strip():
            logger.warning("Empty script provided to AudioGenerator.")
            return None

        voice_id = self.get_voice_id(market)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }
        
        try:
            logger.info(f"Generating ElevenLabs audio for market: {market} (Voice ID: {voice_id})")
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code != 200:
                logger.error(f"ElevenLabs API Error {response.status_code}: {response.text}")
                return None
                
            output_dir = os.path.join("backend", "assets", "remediated")
            os.makedirs(output_dir, exist_ok=True)
            filename = f"voiceover_{uuid.uuid4().hex[:8]}.mp3"
            file_path = os.path.join(output_dir, filename)
            
            with open(file_path, "wb") as f:
                f.write(response.content)
                
            logger.info(f"Saved generated audio to {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Failed to generate audio: {e}")
            return None
