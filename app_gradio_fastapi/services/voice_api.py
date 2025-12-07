"""
Voice API service for Grok TTS.

Adapted from voice-demo-hackathon/demo.py for rap voice generation.
"""

import base64
import os
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("XAI_API_KEY")
BASE_URL = "https://us-east-4.api.x.ai/voice-staging"
TTS_ENDPOINT = f"{BASE_URL}/api/v1/text-to-speech/generate"

MAX_INPUT_LENGTH = 4096


def file_to_base64(file_path: str) -> str:
    """Convert a file to base64 string."""
    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")


def generate_rap_voice(
    lyrics: str,
    style_instructions: str = "aggressive hip-hop rapper with rhythmic flow",
    voice_file: str | None = None,
    temperature: float = 1.0,
) -> tuple[str | None, str]:
    """
    Generate rap audio from lyrics using Grok Voice API.

    Args:
        lyrics: The rap lyrics to convert to speech
        style_instructions: Style/vibe instructions for the voice
        voice_file: Optional path to voice sample for cloning
        temperature: Sampling temperature (higher = more variation)

    Returns:
        Tuple of (audio_file_path, status_message)
    """
    if not API_KEY:
        return None, "Error: XAI_API_KEY not set in environment"

    if not lyrics.strip():
        return None, "Error: No lyrics provided"

    # Prepare voice cloning if file provided
    voice_base64 = None
    if voice_file and os.path.exists(voice_file):
        try:
            voice_base64 = file_to_base64(voice_file)
        except Exception as e:
            return None, f"Error reading voice file: {e}"

    # Truncate lyrics if too long
    lyrics = lyrics[:MAX_INPUT_LENGTH]

    payload = {
        "model": "grok-voice",
        "input": lyrics,
        "response_format": "mp3",
        "instructions": style_instructions,
        "voice": voice_base64 or "None",
        "sampling_params": {
            "max_new_tokens": 512,
            "temperature": temperature,
            "min_p": 0.01,
        },
    }

    try:
        response = requests.post(
            TTS_ENDPOINT,
            json=payload,
            stream=True,
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=120,
        )

        if response.status_code == 200:
            # Save to temp file
            output_dir = Path("outputs")
            output_dir.mkdir(exist_ok=True)

            # Create unique filename
            output_file = tempfile.NamedTemporaryFile(
                suffix=".mp3",
                dir=output_dir,
                delete=False,
            )

            for chunk in response.iter_content(chunk_size=8192):
                output_file.write(chunk)
            output_file.close()

            return output_file.name, f"Audio generated successfully"
        else:
            return None, f"API Error {response.status_code}: {response.text}"

    except requests.exceptions.Timeout:
        return None, "Error: Request timed out"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"
