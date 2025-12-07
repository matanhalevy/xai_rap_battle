"""
Script parser for rap battle scripts.
Extracts Person A / Person B turns and verses.
"""

import re
from dataclasses import dataclass
from enum import Enum


class Speaker(Enum):
    PERSON_A = "Person A"
    PERSON_B = "Person B"
    BOTH = "Both"


class ShotType(Enum):
    """Type of shot in the 6-shot storyboard structure."""
    OPENING = "opening"      # Shot 1: Panning crowd, both characters, setting the scene
    VERSE = "verse"          # Shots 2-5: Single speaker focus with verse delivery
    REACTION = "reaction"    # Variant for shots 4-5: Both in frame with reaction
    CLOSING = "closing"      # Shot 6: Final standoff, crowd reaction, fade out


@dataclass
class BattleSegment:
    """A segment of the rap battle (one turn)."""
    index: int
    speaker: Speaker
    verses: list[str]
    raw_text: str
    is_conclusion: bool = False

    @property
    def verse_summary(self) -> str:
        """Get a brief summary of the verses for image prompting."""
        combined = " ".join(self.verses)
        # Truncate to first 200 chars for prompt
        if len(combined) > 200:
            return combined[:200] + "..."
        return combined


def parse_rap_script(script: str, speaker_a_name: str = "", speaker_b_name: str = "") -> list[BattleSegment]:
    """
    Parse a rap battle script into segments.

    Expected format:
    - "[Person A]" or "Person A:" or custom name like "Elon Musk"
    - "[Person B]" or "Person B:" or custom name like "Sam Altman"
    - "[Conclusion]" or "[Both]" for finale

    Args:
        script: The rap battle script
        speaker_a_name: Optional custom name for speaker A (auto-detected if empty)
        speaker_b_name: Optional custom name for speaker B (auto-detected if empty)

    Returns:
        List of BattleSegment objects (typically 5: A, B, A, B, Conclusion)
    """
    segments = []
    lines = script.strip().split("\n")

    # Auto-detect speaker names if not provided
    if not speaker_a_name or not speaker_b_name:
        detected_names = _detect_speaker_names(lines)
        if not speaker_a_name and len(detected_names) > 0:
            speaker_a_name = detected_names[0]
        if not speaker_b_name and len(detected_names) > 1:
            speaker_b_name = detected_names[1]

    current_speaker = None
    current_verses = []
    current_raw = []
    segment_index = 0

    def save_current_segment():
        nonlocal current_speaker, current_verses, current_raw, segment_index
        if current_speaker and current_verses:
            segments.append(BattleSegment(
                index=segment_index,
                speaker=current_speaker,
                verses=current_verses.copy(),
                raw_text="\n".join(current_raw),
                is_conclusion=(current_speaker == Speaker.BOTH),
            ))
            segment_index += 1
        current_verses = []
        current_raw = []

    def check_speaker(line: str) -> Speaker | None:
        """Check if line is a speaker marker."""
        line_lower = line.lower().strip()

        # Check for conclusion/both
        if re.match(r"^\[?\s*(conclusion|both|finale)\s*\]?:?\s*$", line_lower):
            return Speaker.BOTH

        # Check for Person A/B
        if re.match(r"^\[?\s*person\s*a\s*\]?:?\s*$", line_lower):
            return Speaker.PERSON_A
        if re.match(r"^\[?\s*person\s*b\s*\]?:?\s*$", line_lower):
            return Speaker.PERSON_B

        # Check for custom speaker names
        if speaker_a_name:
            pattern_a = rf"^\[?\s*{re.escape(speaker_a_name)}\s*\]?:?\s*$"
            if re.match(pattern_a, line, re.IGNORECASE):
                return Speaker.PERSON_A

        if speaker_b_name:
            pattern_b = rf"^\[?\s*{re.escape(speaker_b_name)}\s*\]?:?\s*$"
            if re.match(pattern_b, line, re.IGNORECASE):
                return Speaker.PERSON_B

        return None

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Check for speaker markers
        new_speaker = check_speaker(line_stripped)

        if new_speaker is not None:
            save_current_segment()
            current_speaker = new_speaker
        elif current_speaker:
            # It's a verse line
            current_verses.append(line_stripped)
            current_raw.append(line)

    # Save final segment
    save_current_segment()

    # If no markers found, try to split by empty lines or create single segment
    if not segments and script.strip():
        segments.append(BattleSegment(
            index=0,
            speaker=Speaker.PERSON_A,
            verses=script.strip().split("\n"),
            raw_text=script.strip(),
            is_conclusion=False,
        ))

    return segments


def _detect_speaker_names(lines: list[str]) -> list[str]:
    """
    Auto-detect speaker names from script.
    Looks for lines that appear to be speaker markers (short lines, possibly with brackets/colons).
    """
    potential_speakers = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip if too long (likely a verse, not a name)
        if len(line) > 50:
            continue

        # Check if it looks like a speaker marker
        # Short line, possibly with brackets or colon
        if re.match(r"^\[?[A-Za-z\s]+\]?:?\s*$", line):
            # Clean the name
            name = re.sub(r"[\[\]:]+", "", line).strip()

            # Skip common non-name markers
            skip_words = ["verse", "chorus", "hook", "bridge", "intro", "outro", "conclusion", "both", "finale"]
            if name.lower() in skip_words:
                continue

            if name and name not in potential_speakers:
                potential_speakers.append(name)

            # Stop after finding 2 unique speakers
            if len(potential_speakers) >= 2:
                break

    return potential_speakers


def ensure_three_segments(segments: list[BattleSegment]) -> list[BattleSegment]:
    """
    Ensure we have exactly 3 segments for test mode: A, B, Conclusion.
    """
    if len(segments) >= 3:
        # Take first 2 and make 3rd the conclusion
        result = segments[:2]
        if len(segments) >= 3:
            conclusion = segments[2] if segments[2].speaker == Speaker.BOTH else BattleSegment(
                index=2,
                speaker=Speaker.BOTH,
                verses=segments[2].verses if len(segments) > 2 else ["..."],
                raw_text=segments[2].raw_text if len(segments) > 2 else "...",
                is_conclusion=True,
            )
        else:
            conclusion = BattleSegment(
                index=2, speaker=Speaker.BOTH, verses=["..."], raw_text="...", is_conclusion=True
            )
        conclusion.index = 2
        conclusion.is_conclusion = True
        result.append(conclusion)
        return result

    # Pad if less than 3
    expected = [Speaker.PERSON_A, Speaker.PERSON_B, Speaker.BOTH]
    result = segments.copy()
    while len(result) < 3:
        idx = len(result)
        result.append(BattleSegment(
            index=idx, speaker=expected[idx], verses=["..."], raw_text="...", is_conclusion=(idx == 2)
        ))
    return result


def ensure_five_segments(segments: list[BattleSegment]) -> list[BattleSegment]:
    """
    Ensure we have exactly 5 segments for the standard battle format:
    A, B, A, B, Conclusion

    If we have more/fewer, adjust accordingly.
    """
    if len(segments) == 5:
        return segments

    if len(segments) < 5:
        # Pad with empty segments
        expected_speakers = [Speaker.PERSON_A, Speaker.PERSON_B, Speaker.PERSON_A, Speaker.PERSON_B, Speaker.BOTH]
        result = segments.copy()
        while len(result) < 5:
            idx = len(result)
            result.append(BattleSegment(
                index=idx,
                speaker=expected_speakers[idx],
                verses=["..."],
                raw_text="...",
                is_conclusion=(idx == 4),
            ))
        return result

    # More than 5 - keep first 4 and merge rest into conclusion
    result = segments[:4]
    conclusion_verses = []
    conclusion_raw = []
    for seg in segments[4:]:
        conclusion_verses.extend(seg.verses)
        conclusion_raw.append(seg.raw_text)
    result.append(BattleSegment(
        index=4,
        speaker=Speaker.BOTH,
        verses=conclusion_verses,
        raw_text="\n".join(conclusion_raw),
        is_conclusion=True,
    ))
    return result


@dataclass
class StoryboardShot:
    """
    A single shot in the 6-shot storyboard structure.
    Maps verses to cinematic shots with camera directions.
    """
    index: int                    # 0-5 for 6 shots
    shot_type: ShotType           # OPENING, VERSE, REACTION, CLOSING
    primary_speaker: Speaker      # Main character in shot
    show_reaction: bool           # Whether to show other character reacting
    verse_index: int | None       # Which verse (0-3) if applicable, None for opening/closing
    camera_direction: str         # Camera movement description
    audio_source: str             # "intro", "verse_0", "verse_1", etc., "outro"
    verse_text: str = ""          # The actual verse lyrics (for prompting)

    @property
    def needs_lipsync(self) -> bool:
        """Whether this shot needs lip sync (verse shots only)."""
        return self.shot_type == ShotType.VERSE or self.shot_type == ShotType.REACTION


# Camera directions for each of the 6 shots
SHOT_CAMERA_DIRECTIONS = {
    0: "Cinematic crane shot panning across crowd, revealing both performers on stage, building anticipation, slow zoom toward center stage",
    1: "Low-angle push-in, performer spreads arms wide then points at camera, dramatic rim lighting, passionate delivery",
    2: "Dutch angle tracking shot, performer walks into frame with swagger, confident gestures, stylish cross-lighting",
    3: "Medium shot showing both performers, focus on speaker delivering bars while opponent visible reacting in background, tension building",
    4: "Dynamic arc shot around performer, quick cut showing opponent's surprised reaction, then back to triumphant delivery",
    5: "Epic wide crane pullback, both performers step toward center, crowd erupting, confetti falling, triumphant finale",
}


def create_storyboard_shots(segments: list[BattleSegment]) -> list[StoryboardShot]:
    """
    Create 6-shot storyboard structure from battle segments.

    Maps 4 verses (A, B, A, B) to 6 shots:
    - Shot 0: Opening (intro with beat)
    - Shot 1: Verse 1 - Person A
    - Shot 2: Verse 2 - Person B
    - Shot 3: Verse 3 - Person A (with B reaction in frame)
    - Shot 4: Verse 4 - Person B (with A reaction, quick cuts)
    - Shot 5: Closing (outro with beat)

    Args:
        segments: List of BattleSegment objects (should have 4 verse segments)

    Returns:
        List of 6 StoryboardShot objects
    """
    shots = []

    # Shot 0: Opening
    shots.append(StoryboardShot(
        index=0,
        shot_type=ShotType.OPENING,
        primary_speaker=Speaker.BOTH,
        show_reaction=False,
        verse_index=None,
        camera_direction=SHOT_CAMERA_DIRECTIONS[0],
        audio_source="intro",
        verse_text="",
    ))

    # Shot 1: Verse 1 - Person A
    verse_1_text = segments[0].verse_summary if len(segments) > 0 else ""
    shots.append(StoryboardShot(
        index=1,
        shot_type=ShotType.VERSE,
        primary_speaker=Speaker.PERSON_A,
        show_reaction=False,
        verse_index=0,
        camera_direction=SHOT_CAMERA_DIRECTIONS[1],
        audio_source="verse_0",
        verse_text=verse_1_text,
    ))

    # Shot 2: Verse 2 - Person B
    verse_2_text = segments[1].verse_summary if len(segments) > 1 else ""
    shots.append(StoryboardShot(
        index=2,
        shot_type=ShotType.VERSE,
        primary_speaker=Speaker.PERSON_B,
        show_reaction=False,
        verse_index=1,
        camera_direction=SHOT_CAMERA_DIRECTIONS[2],
        audio_source="verse_1",
        verse_text=verse_2_text,
    ))

    # Shot 3: Verse 3 - Person A with B reaction (both in frame)
    verse_3_text = segments[2].verse_summary if len(segments) > 2 else ""
    shots.append(StoryboardShot(
        index=3,
        shot_type=ShotType.REACTION,
        primary_speaker=Speaker.PERSON_A,
        show_reaction=True,  # Show Person B reacting
        verse_index=2,
        camera_direction=SHOT_CAMERA_DIRECTIONS[3],
        audio_source="verse_2",
        verse_text=verse_3_text,
    ))

    # Shot 4: Verse 4 - Person B with quick cut to A reaction
    verse_4_text = segments[3].verse_summary if len(segments) > 3 else ""
    shots.append(StoryboardShot(
        index=4,
        shot_type=ShotType.REACTION,
        primary_speaker=Speaker.PERSON_B,
        show_reaction=True,  # Show Person A reacting with quick cuts
        verse_index=3,
        camera_direction=SHOT_CAMERA_DIRECTIONS[4],
        audio_source="verse_3",
        verse_text=verse_4_text,
    ))

    # Shot 5: Closing
    shots.append(StoryboardShot(
        index=5,
        shot_type=ShotType.CLOSING,
        primary_speaker=Speaker.BOTH,
        show_reaction=False,
        verse_index=None,
        camera_direction=SHOT_CAMERA_DIRECTIONS[5],
        audio_source="outro",
        verse_text="",
    ))

    return shots
