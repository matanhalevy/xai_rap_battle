"""BPM detection from audio files using librosa."""

import logging
from pathlib import Path

import librosa
import numpy as np


def detect_bpm(audio_path: str) -> float:
    """
    Detect BPM from an audio file.

    Args:
        audio_path: Path to audio file (MP3, WAV, etc.)

    Returns:
        Detected BPM as float, rounded to nearest integer for beat generation.
    """
    logging.info(f"Detecting BPM from: {audio_path}")

    try:
        # Load audio file
        y, sr = librosa.load(audio_path, sr=None)

        # Detect tempo (BPM)
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)

        # librosa returns tempo as numpy array in newer versions
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0])
        else:
            tempo = float(tempo)

        logging.info(f"Detected BPM: {tempo:.1f}")
        return tempo

    except Exception as e:
        logging.error(f"BPM detection failed: {e}")
        # Return a default BPM if detection fails
        return 120.0


def detect_bpm_from_multiple(audio_paths: list[str]) -> float:
    """
    Detect BPM from multiple audio files and return the average.

    Useful for getting consistent BPM across multiple rap verses.

    Args:
        audio_paths: List of paths to audio files

    Returns:
        Average detected BPM
    """
    if not audio_paths:
        return 120.0

    bpms = []
    for path in audio_paths:
        if path and Path(path).exists():
            bpm = detect_bpm(path)
            bpms.append(bpm)

    if not bpms:
        return 120.0

    avg_bpm = sum(bpms) / len(bpms)
    logging.info(f"Average BPM from {len(bpms)} files: {avg_bpm:.1f}")
    return avg_bpm


def snap_bpm_to_common(bpm: float) -> int:
    """
    Snap detected BPM to common hip-hop tempos.

    Hip-hop typically uses these BPM ranges:
    - Boom bap: 85-95 BPM
    - West coast: 90-105 BPM
    - Trap: 130-150 BPM (or half-time at 65-75)
    - Drill: 140-150 BPM

    Args:
        bpm: Detected BPM

    Returns:
        Snapped BPM as integer
    """
    common_bpms = [85, 90, 95, 100, 105, 110, 120, 130, 140, 145, 150]

    # Find closest common BPM
    closest = min(common_bpms, key=lambda x: abs(x - bpm))
    logging.info(f"Snapped BPM {bpm:.1f} to {closest}")
    return closest
