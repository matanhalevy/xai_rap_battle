"""Lyric alignment service using ForceAlign for word-level timestamps."""

import logging
from pathlib import Path

# Lazy import to avoid startup issues
ForceAlign = None


def _ensure_forcealign():
    """Lazy load ForceAlign and ensure NLTK data is available."""
    global ForceAlign
    if ForceAlign is not None:
        return True

    try:
        # Ensure NLTK data is downloaded
        import nltk
        try:
            nltk.data.find('corpora/cmudict')
        except LookupError:
            logging.info("Downloading NLTK cmudict for ForceAlign...")
            nltk.download('cmudict', quiet=True)

        # Now import ForceAlign
        from forcealign import ForceAlign as FA
        ForceAlign = FA
        return True
    except Exception as e:
        logging.error(f"Failed to initialize ForceAlign: {e}")
        return False


def align_lyrics_to_audio(
    audio_path: str,
    lyrics: str,
    fighter: str = "A",
) -> list[dict]:
    """
    Align lyrics to audio and return line-level timing.

    Args:
        audio_path: Path to the audio file (mp3 or wav)
        lyrics: The lyrics text with newlines separating lines
        fighter: Fighter identifier ("A" or "B")

    Returns:
        List of dicts with: {text, start, end, fighter}
    """
    if not Path(audio_path).exists():
        logging.error(f"Audio file not found: {audio_path}")
        return []

    logging.info(f"Aligning lyrics for fighter {fighter}: {audio_path}")

    # Clean lyrics - remove empty lines
    lines = [line.strip() for line in lyrics.split("\n") if line.strip()]

    if not lines:
        logging.warning("No lyrics lines to align")
        return []

    # Ensure ForceAlign is loaded
    if not _ensure_forcealign():
        logging.warning("ForceAlign not available, using estimation")
        return _estimate_line_timing(audio_path, lines, fighter)

    try:
        # Run forced alignment
        align = ForceAlign(audio_file=audio_path, transcript=lyrics)
        words = align.inference()

        if not words:
            logging.warning("ForceAlign returned no words, using estimation")
            return _estimate_line_timing(audio_path, lines, fighter)

        # Group words into lines and compute timing
        result = _group_words_into_lines(words, lines, fighter)
        logging.info(f"Aligned {len(result)} lines for fighter {fighter}")
        return result

    except Exception as e:
        logging.error(f"ForceAlign failed: {e}, falling back to estimation")
        return _estimate_line_timing(audio_path, lines, fighter)


def _group_words_into_lines(
    words: list,
    lines: list[str],
    fighter: str,
) -> list[dict]:
    """Group aligned words back into lines with start/end times."""
    result = []
    word_index = 0
    word_texts = [w.word.lower() for w in words]

    for line in lines:
        line_words = line.lower().split()
        if not line_words:
            continue

        # Find start of this line in aligned words
        line_start = None
        line_end = None
        matched_words = 0

        # Search for line words in aligned words
        for i in range(word_index, len(words)):
            word = words[i]
            word_clean = word.word.lower().strip(".,!?\"'")

            # Check if this word matches any word in the line
            for lw in line_words:
                lw_clean = lw.strip(".,!?\"'")
                if word_clean == lw_clean or lw_clean in word_clean:
                    if line_start is None:
                        line_start = word.time_start
                    line_end = word.time_end
                    matched_words += 1
                    word_index = i + 1
                    break

            # If we've matched enough words, move on
            if matched_words >= len(line_words) * 0.5:
                break

        # Fallback if no timing found
        if line_start is None:
            if result:
                line_start = result[-1]["end"]
            else:
                line_start = 0.0
            line_end = line_start + 2.0  # Default 2 seconds per line

        result.append({
            "text": line,
            "start": round(line_start, 2),
            "end": round(line_end, 2),
            "fighter": fighter,
        })

    return result


def _estimate_line_timing(
    audio_path: str,
    lines: list[str],
    fighter: str,
) -> list[dict]:
    """Fallback: estimate line timing from audio duration."""
    from pydub import AudioSegment

    try:
        audio = AudioSegment.from_file(audio_path)
        duration_sec = len(audio) / 1000.0
    except Exception:
        duration_sec = len(lines) * 2.5  # Assume 2.5 sec per line

    time_per_line = duration_sec / len(lines)

    result = []
    for i, line in enumerate(lines):
        result.append({
            "text": line,
            "start": round(i * time_per_line, 2),
            "end": round((i + 1) * time_per_line, 2),
            "fighter": fighter,
        })

    return result


def align_battle_verses(
    audio_clips: list[str],
    verses: list[str],
    fighter_order: list[str] = None,
) -> dict:
    """
    Align all verses in a battle to their audio clips.

    Args:
        audio_clips: List of audio file paths (one per verse)
        verses: List of verse lyrics
        fighter_order: Order of fighters ["A", "B", "A", "B"] or auto-generated

    Returns:
        {
            "lines": [...],  # All lines with timing and fighter
            "verse_breaks": [0, N, ...]  # Line indices where verses start
        }
    """
    if fighter_order is None:
        fighter_order = ["A", "B", "A", "B"][:len(verses)]

    all_lines = []
    verse_breaks = []
    cumulative_offset = 0.0

    for i, (audio_path, verse_lyrics, fighter) in enumerate(
        zip(audio_clips, verses, fighter_order)
    ):
        if not audio_path or not verse_lyrics:
            continue

        verse_breaks.append(len(all_lines))

        # Get timing for this verse
        verse_lines = align_lyrics_to_audio(audio_path, verse_lyrics, fighter)

        # Offset times by cumulative duration
        for line in verse_lines:
            line["start"] += cumulative_offset
            line["end"] += cumulative_offset
            all_lines.append(line)

        # Update offset for next verse
        if verse_lines:
            cumulative_offset = verse_lines[-1]["end"]

    return {
        "lines": all_lines,
        "verse_breaks": verse_breaks,
    }
