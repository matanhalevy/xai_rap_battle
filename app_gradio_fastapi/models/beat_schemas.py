"""
Pydantic models for beat pattern JSON schema.
"""

from typing import Literal
from pydantic import BaseModel, Field


# Duration codes: w=whole(4), h=half(2), q=quarter(1), e=eighth(0.5), s=sixteenth(0.25)
DurationCode = Literal["w", "h", "q", "e", "s"]

# Sound codes mapped to sample files ("-" = rest/silence)
SoundCode = Literal["K", "S", "H", "B", "C", "O", "X", "P", "-"]

# Duration in beats
DURATION_MAP: dict[str, float] = {
    "w": 4.0,   # whole
    "h": 2.0,   # half
    "q": 1.0,   # quarter
    "e": 0.5,   # eighth
    "s": 0.25,  # sixteenth
}


class BeatEvent(BaseModel):
    """A single sound event at a beat position."""
    sound: SoundCode
    duration: DurationCode = "q"


class BeatPosition(BaseModel):
    """Events occurring at a specific beat position within a bar."""
    beat: float = Field(ge=1.0, le=4.75)
    events: list[BeatEvent]


class Bar(BaseModel):
    """A single bar/measure of the pattern."""
    bar: int = Field(ge=1)
    beats: list[BeatPosition]


class TrackInfo(BaseModel):
    """Metadata for a sound track."""
    name: str
    file: str


class BeatMetadata(BaseModel):
    """Metadata for the beat pattern."""
    title: str
    style: str
    bpm: int = Field(ge=60, le=200)
    time_signature: tuple[int, int] = (4, 4)
    bars: int = Field(ge=1, le=16)
    loopable: bool = True


class BeatPattern(BaseModel):
    """Complete beat pattern with metadata and pattern data."""
    metadata: BeatMetadata
    tracks: dict[str, TrackInfo]
    pattern: list[Bar]
