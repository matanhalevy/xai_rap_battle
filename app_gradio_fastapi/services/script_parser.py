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


def parse_rap_script(script: str) -> list[BattleSegment]:
    """
    Parse a rap battle script into segments.

    Expected format:
    - "[Person A]" or "Person A:" markers
    - "[Person B]" or "Person B:" markers
    - "[Conclusion]" or "[Both]" for finale

    Returns:
        List of BattleSegment objects (typically 5: A, B, A, B, Conclusion)
    """
    segments = []
    lines = script.strip().split("\n")

    current_speaker = None
    current_verses = []
    current_raw = []
    segment_index = 0

    # Patterns for speaker markers
    speaker_patterns = [
        (r"^\[?\s*Person\s*A\s*\]?:?\s*$", Speaker.PERSON_A),
        (r"^\[?\s*Person\s*B\s*\]?:?\s*$", Speaker.PERSON_B),
        (r"^\[?\s*(Conclusion|Both|Finale)\s*\]?:?\s*$", Speaker.BOTH),
        (r"^Person\s*A\s*[-–—:]", Speaker.PERSON_A),
        (r"^Person\s*B\s*[-–—:]", Speaker.PERSON_B),
    ]

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

    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue

        # Check for speaker markers
        new_speaker = None
        for pattern, speaker in speaker_patterns:
            if re.match(pattern, line_stripped, re.IGNORECASE):
                new_speaker = speaker
                break

        if new_speaker:
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
