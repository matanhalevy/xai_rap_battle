"""
ElevenLabs API service for voice cloning and speech-to-speech transformation.

Used for the Style Transfer feature to combine voice identity with delivery style.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import requests
from dotenv import load_dotenv

# Find project root and load env files
PROJECT_ROOT = Path(__file__).parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")  # Load base first
load_dotenv(PROJECT_ROOT / ".env.local", override=True)  # Local overrides with priority

ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
BASE_URL = "https://api.elevenlabs.io/v1"


def clone_voice(name: str, audio_file: str, description: str = "") -> tuple[str | None, str]:
    """
    Clone a voice from an audio sample.

    Args:
        name: Name for the cloned voice
        audio_file: Path to audio file (voice identity source)
        description: Optional description for the voice

    Returns:
        Tuple of (voice_id, status_message)
    """
    # Debug: Print what key we're using
    key_preview = f"{ELEVENLABS_API_KEY[:10]}...{ELEVENLABS_API_KEY[-5:]}" if ELEVENLABS_API_KEY else "None"
    print(f"DEBUG clone_voice: API key = {key_preview}")

    if not ELEVENLABS_API_KEY:
        return None, "Error: ELEVENLABS_API_KEY not set in environment"

    if not os.path.exists(audio_file):
        return None, f"Error: Audio file not found: {audio_file}"

    url = f"{BASE_URL}/voices/add"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    try:
        with open(audio_file, "rb") as f:
            files = {"files": (os.path.basename(audio_file), f, "audio/mpeg")}
            data = {
                "name": name,
                "description": description or f"Cloned voice: {name}",
            }

            response = requests.post(url, headers=headers, files=files, data=data, timeout=60)

        if response.status_code == 200:
            voice_id = response.json().get("voice_id")
            return voice_id, f"Voice cloned successfully: {name}"
        else:
            return None, f"Clone error {response.status_code}: {response.text}"

    except requests.exceptions.Timeout:
        return None, "Error: Request timed out"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"


def speech_to_speech(
    source_audio: str,
    voice_id: str,
    model_id: str = "eleven_multilingual_sts_v2",
    remove_noise: bool = True,
    output_dir: str | None = None,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    use_speaker_boost: bool = True,
) -> tuple[str | None, str]:
    """
    Transform audio from one voice to another while preserving delivery style.

    Args:
        source_audio: Path to source audio file (style/delivery source)
        voice_id: Target voice ID (from clone_voice or list_voices)
        model_id: ElevenLabs model to use
        remove_noise: Whether to remove background noise
        output_dir: Directory for output file (default: outputs/)
        stability: Voice stability (0-1). Higher = more consistent, lower = more expressive
        similarity_boost: How much to match target voice (0-1). Higher = more like target voice
        style: Style exaggeration (0-1). Keep at 0 for best stability
        use_speaker_boost: Boost similarity to original speaker

    Returns:
        Tuple of (output_file_path, status_message)
    """
    import json

    if not ELEVENLABS_API_KEY:
        return None, "Error: ELEVENLABS_API_KEY not set in environment"

    if not os.path.exists(source_audio):
        return None, f"Error: Source audio not found: {source_audio}"

    url = f"{BASE_URL}/speech-to-speech/{voice_id}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    # Voice settings to control output characteristics
    voice_settings = {
        "stability": stability,
        "similarity_boost": similarity_boost,
        "style": style,
        "use_speaker_boost": use_speaker_boost,
    }

    try:
        with open(source_audio, "rb") as f:
            files = {"audio": (os.path.basename(source_audio), f, "audio/mpeg")}
            data = {
                "model_id": model_id,
                "remove_background_noise": str(remove_noise).lower(),
                "voice_settings": json.dumps(voice_settings),
            }

            response = requests.post(
                url, headers=headers, files=files, data=data, stream=True, timeout=120
            )

        if response.status_code == 200:
            # Save output to file
            if output_dir is None:
                output_dir = Path("outputs/style_transfer")
            else:
                output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            output_file = tempfile.NamedTemporaryFile(
                suffix=".mp3", dir=output_dir, delete=False, prefix="s2s_"
            )

            for chunk in response.iter_content(chunk_size=8192):
                output_file.write(chunk)
            output_file.close()

            return output_file.name, "Speech-to-speech transformation complete"
        else:
            return None, f"S2S error {response.status_code}: {response.text}"

    except requests.exceptions.Timeout:
        return None, "Error: Request timed out"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"


def list_voices() -> tuple[list[dict], str]:
    """
    List all available voices (including cloned voices).

    Returns:
        Tuple of (voices_list, status_message)
    """
    if not ELEVENLABS_API_KEY:
        return [], "Error: ELEVENLABS_API_KEY not set in environment"

    url = f"{BASE_URL}/voices"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    try:
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            voices = response.json().get("voices", [])
            return voices, f"Found {len(voices)} voices"
        else:
            return [], f"List error {response.status_code}: {response.text}"

    except requests.exceptions.RequestException as e:
        return [], f"Request error: {e}"


def delete_voice(voice_id: str) -> tuple[bool, str]:
    """
    Delete a cloned voice.

    Args:
        voice_id: The voice ID to delete

    Returns:
        Tuple of (success, status_message)
    """
    if not ELEVENLABS_API_KEY:
        return False, "Error: ELEVENLABS_API_KEY not set in environment"

    url = f"{BASE_URL}/voices/{voice_id}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    try:
        response = requests.delete(url, headers=headers, timeout=30)

        if response.status_code == 200:
            return True, "Voice deleted successfully"
        else:
            return False, f"Delete error {response.status_code}: {response.text}"

    except requests.exceptions.RequestException as e:
        return False, f"Request error: {e}"


def pitch_shift_audio(
    input_path: str,
    pitch_factor: float = 0.88,
    tempo_factor: float = 1.1,
    output_path: str | None = None,
) -> tuple[str | None, str]:
    """
    Apply pitch and tempo transformation using ffmpeg.

    Used for Celebrity Voice Mode to evade voice fingerprint detection.

    Args:
        input_path: Path to input audio file
        pitch_factor: Pitch multiplier (0.88 = 12% lower, 1.136 = ~14% higher)
        tempo_factor: Tempo multiplier (1.1 = 10% faster, 0.909 = ~10% slower)
        output_path: Optional output path (creates temp file if None)

    Returns:
        Tuple of (output_file_path, status_message)
    """
    if not os.path.exists(input_path):
        return None, f"Error: Input file not found: {input_path}"

    if not shutil.which("ffmpeg"):
        return None, "Error: ffmpeg not found in PATH"

    if output_path is None:
        output_dir = Path("outputs/pitch_shifted")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = tempfile.NamedTemporaryFile(
            suffix=".mp3", dir=output_dir, delete=False, prefix="pitch_"
        )
        output_path = output_file.name
        output_file.close()

    filter_str = f"asetrate=44100*{pitch_factor},aresample=44100,atempo={tempo_factor}"

    cmd = ["ffmpeg", "-y", "-i", input_path, "-af", filter_str, output_path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return output_path, "Pitch shift complete"
        else:
            return None, f"ffmpeg error: {result.stderr}"
    except subprocess.TimeoutExpired:
        return None, "Error: ffmpeg timed out"
    except Exception as e:
        return None, f"Error: {e}"


def create_style_reference(
    voice_identity_file: str,
    style_source_file: str,
    reference_name: str = "custom_voice",
    celebrity_mode: bool = False,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
) -> tuple[str | None, str | None, str]:
    """
    Create a voice+style reference in one step.

    This combines voice cloning and speech-to-speech transformation:
    1. Clones the voice identity (e.g., Elon's voice)
    2. Transforms the style source (e.g., Stormzy's rap) to the cloned voice

    If celebrity_mode is True:
    1. Pitch-shifts the voice identity file DOWN before cloning (evades detection)
    2. After S2S, pitch-shifts the output back UP to restore natural voice

    Args:
        voice_identity_file: Path to voice identity audio (who to sound like)
        style_source_file: Path to style source audio (delivery/cadence to copy)
        reference_name: Name for the cloned voice
        celebrity_mode: Apply pitch shifting to evade celebrity voice detection
        stability: Voice stability (0-1). Higher = more consistent
        similarity_boost: Target voice similarity (0-1). Higher = more like voice identity

    Returns:
        Tuple of (output_file_path, voice_id, status_message)
    """
    working_voice_file = voice_identity_file

    # Step 0: If celebrity mode, pitch-shift input down to evade detection
    if celebrity_mode:
        print("Celebrity mode enabled: applying pitch shift to input...")
        shifted_path, shift_status = pitch_shift_audio(
            voice_identity_file,
            pitch_factor=0.88,  # 12% lower pitch
            tempo_factor=1.1,  # 10% faster to preserve duration
        )
        if not shifted_path:
            return None, None, f"Pitch shift failed: {shift_status}"
        working_voice_file = shifted_path
        print(f"Pitch-shifted input saved to: {shifted_path}")

    # Step 1: Clone the voice identity
    voice_id, status = clone_voice(reference_name, working_voice_file)
    if not voice_id:
        return None, None, f"Clone failed: {status}"

    # Step 2: Transform style source to cloned voice
    print(f"S2S with stability={stability}, similarity_boost={similarity_boost}")
    output_path, status = speech_to_speech(
        style_source_file,
        voice_id,
        stability=stability,
        similarity_boost=similarity_boost,
    )
    if not output_path:
        return None, voice_id, f"S2S failed: {status}"

    # Step 3: If celebrity mode, reverse the pitch shift on output
    if celebrity_mode:
        print("Celebrity mode: reversing pitch shift on output...")
        corrected_path, correct_status = pitch_shift_audio(
            output_path,
            pitch_factor=1.136,  # Reverse: 1/0.88 ≈ 1.136
            tempo_factor=0.909,  # Reverse: 1/1.1 ≈ 0.909
        )
        if not corrected_path:
            # Return raw output with warning if correction fails
            return output_path, voice_id, f"Style reference created (pitch correction failed: {correct_status})"
        output_path = corrected_path
        print(f"Pitch-corrected output saved to: {corrected_path}")

    return output_path, voice_id, f"Style reference created: {reference_name}"
