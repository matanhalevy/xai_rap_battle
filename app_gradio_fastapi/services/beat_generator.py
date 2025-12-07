"""
Beat generation service - synthesizes audio from JSON beat patterns.
"""

import json
import os
import tempfile
from pathlib import Path

from pydub import AudioSegment

from app_gradio_fastapi.models.beat_schemas import (
    BeatPattern,
    DURATION_MAP,
)


# Map sound codes to sample files
SAMPLE_FILES: dict[str, str] = {
    "K": "kick-drum-263837.mp3",
    "S": "snare-drum-341273.mp3",
    "H": "hi-hat-231042.mp3",
    "B": "808-bass-drum-421219.mp3",
    "C": "clap-375693.mp3",
    "O": "open-hi-hat-431740.mp3",
    "X": "tr808-crash-cymbal-241377.mp3",
    "P": "shaker-drum-434902.mp3",
}

SOUNDS_DIR = Path("Sounds")


class BeatGenerator:
    """Generates audio from beat pattern JSON."""

    def __init__(self, sounds_dir: Path = SOUNDS_DIR):
        self.sounds_dir = sounds_dir
        self.samples: dict[str, AudioSegment] = {}
        self._load_samples()

    def _load_samples(self) -> None:
        """Load all available sound samples into memory."""
        for code, filename in SAMPLE_FILES.items():
            path = self.sounds_dir / filename
            if path.exists():
                self.samples[code] = AudioSegment.from_mp3(str(path))

    def _beat_to_ms(self, beat: float, bpm: int) -> int:
        """Convert beat position (1-indexed) to milliseconds."""
        ms_per_beat = 60000 / bpm
        # beat 1 = 0ms, beat 2 = ms_per_beat, etc.
        return int((beat - 1) * ms_per_beat)

    def synthesize(self, pattern: BeatPattern, loops: int = 1) -> AudioSegment:
        """
        Convert beat pattern to audio.

        Args:
            pattern: The parsed beat pattern
            loops: Number of times to loop the pattern

        Returns:
            AudioSegment with the synthesized beat
        """
        bpm = pattern.metadata.bpm
        num_bars = pattern.metadata.bars
        beats_per_bar = pattern.metadata.time_signature[0]

        # Calculate total duration for one loop
        total_beats = num_bars * beats_per_bar
        ms_per_beat = 60000 / bpm
        total_ms = int(total_beats * ms_per_beat)

        # Create silent base track
        output = AudioSegment.silent(duration=total_ms)

        # Overlay each sound event
        for bar in pattern.pattern:
            bar_offset_beats = (bar.bar - 1) * beats_per_bar

            for position in bar.beats:
                absolute_beat = bar_offset_beats + position.beat
                position_ms = self._beat_to_ms(absolute_beat, bpm)

                for event in position.events:
                    # Skip rests
                    if event.sound == "-":
                        continue

                    # Skip sounds we don't have samples for
                    if event.sound not in self.samples:
                        continue

                    sample = self.samples[event.sound]
                    output = output.overlay(sample, position=position_ms)

        # Loop if requested
        if loops > 1:
            output = output * loops

        return output

    def generate_from_json(
        self, json_str: str, loops: int = 4
    ) -> tuple[str, BeatPattern]:
        """
        Parse JSON string and generate audio file.

        Args:
            json_str: JSON string containing beat pattern
            loops: Number of times to loop the pattern

        Returns:
            Tuple of (output_file_path, parsed_pattern)
        """
        data = json.loads(json_str)
        pattern = BeatPattern(**data)

        audio = self.synthesize(pattern, loops=loops)

        # Ensure output directory exists
        output_dir = Path("outputs")
        output_dir.mkdir(exist_ok=True)

        # Export to temp file
        output_file = tempfile.NamedTemporaryFile(
            suffix=".mp3",
            dir=output_dir,
            delete=False,
        )
        output_file.close()

        audio.export(output_file.name, format="mp3")

        return output_file.name, pattern


# Singleton instance
_generator: BeatGenerator | None = None


def get_generator() -> BeatGenerator:
    """Get or create the beat generator singleton."""
    global _generator
    if _generator is None:
        _generator = BeatGenerator()
    return _generator
