"""Audio mixing utilities for combining rap vocals with beats."""

import logging
import tempfile
from pathlib import Path

from pydub import AudioSegment


def mix_rap_and_beat(
    rap_clips: list[str],
    beat_path: str,
    beat_volume_db: float = -10.0,
    output_path: str | None = None,
) -> str:
    """
    Mix rap vocal clips with a beat track.

    Args:
        rap_clips: List of paths to rap audio files (in order)
        beat_path: Path to beat track
        beat_volume_db: Volume adjustment for beat in dB (negative = quieter)
        output_path: Optional output path, generates temp file if not provided

    Returns:
        Path to mixed audio file
    """
    logging.info(f"Mixing {len(rap_clips)} rap clips with beat")

    # Load and concatenate rap clips
    combined_rap = AudioSegment.empty()
    for clip_path in rap_clips:
        if clip_path and Path(clip_path).exists():
            clip = AudioSegment.from_file(clip_path)
            combined_rap += clip
            logging.info(f"Added clip: {clip_path} ({len(clip)}ms)")

    if len(combined_rap) == 0:
        raise ValueError("No valid rap clips provided")

    total_duration_ms = len(combined_rap)
    logging.info(f"Total rap duration: {total_duration_ms}ms")

    # Load beat and loop to match rap duration
    beat = AudioSegment.from_file(beat_path)
    beat_duration = len(beat)

    if beat_duration < total_duration_ms:
        # Loop beat to match rap duration
        loops_needed = (total_duration_ms // beat_duration) + 1
        beat = beat * loops_needed
        logging.info(f"Looped beat {loops_needed} times")

    # Trim beat to exact rap duration
    beat = beat[:total_duration_ms]

    # Adjust beat volume
    beat = beat + beat_volume_db

    # Overlay rap on beat
    mixed = beat.overlay(combined_rap)

    # Export
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mp3", prefix="battle_mix_")

    mixed.export(output_path, format="mp3")
    logging.info(f"Mixed audio exported to: {output_path}")

    return output_path


def concatenate_audio_clips(
    audio_paths: list[str],
    gap_ms: int = 0,
    output_path: str | None = None,
) -> str:
    """
    Concatenate multiple audio files into one.

    Args:
        audio_paths: List of paths to audio files
        gap_ms: Milliseconds of silence between clips
        output_path: Optional output path

    Returns:
        Path to concatenated audio file
    """
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=gap_ms) if gap_ms > 0 else None

    for i, path in enumerate(audio_paths):
        if path and Path(path).exists():
            clip = AudioSegment.from_file(path)
            if i > 0 and silence:
                combined += silence
            combined += clip

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mp3", prefix="concat_")

    combined.export(output_path, format="mp3")
    return output_path


def adjust_audio_tempo(
    audio_path: str,
    original_bpm: float,
    target_bpm: float,
    output_path: str | None = None,
) -> str:
    """
    Adjust audio tempo by changing playback speed.

    Note: This changes pitch. For pitch-preserving tempo change,
    use librosa or rubberband.

    Args:
        audio_path: Path to audio file
        original_bpm: Original BPM of the audio
        target_bpm: Target BPM
        output_path: Optional output path

    Returns:
        Path to tempo-adjusted audio file
    """
    speed_factor = target_bpm / original_bpm
    logging.info(f"Adjusting tempo: {original_bpm} -> {target_bpm} (factor: {speed_factor:.2f})")

    audio = AudioSegment.from_file(audio_path)

    # Change speed by altering frame rate
    # This also changes pitch proportionally
    new_frame_rate = int(audio.frame_rate * speed_factor)
    adjusted = audio._spawn(audio.raw_data, overrides={"frame_rate": new_frame_rate})
    adjusted = adjusted.set_frame_rate(audio.frame_rate)

    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mp3", prefix="tempo_adj_")

    adjusted.export(output_path, format="mp3")
    return output_path


def get_audio_duration_ms(audio_path: str) -> int:
    """Get duration of audio file in milliseconds."""
    audio = AudioSegment.from_file(audio_path)
    return len(audio)
