"""
Grok API integration for rap battle lyric generation.
"""

import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("XAI_API_KEY")
API_BASE = "https://api.x.ai/v1"


VERSE_PROMPT_TEMPLATE = '''You are a legendary battle rapper known for devastating punchlines, clever wordplay, and authentic flow.

BATTLE TOPIC: {topic}
{description}
{beat_context}

CURRENT RAPPER: {rapper_name}
OPPONENT: {opponent_name}
{personality_context}

ATMOSPHERE: {scene_description}

{tweet_context}

VERSE NUMBER: {verse_number} of 4
{verse_context}

{previous_verses_section}

INSTRUCTIONS:
1. Write a SHORT verse (4-6 bars, ~15 seconds when rapped) for {rapper_name}
2. Each bar should be on its own line
3. Use clever wordplay, metaphors, and punchlines
4. Focus lyrics on the BATTLE TOPIC and dissing your OPPONENT
5. {verse_specific_instruction}
6. Make it sound authentic to battle rap culture
7. Include internal rhymes and multisyllabic rhyme schemes
8. Use character NAMES in lyrics, NEVER use Twitter handles or @ symbols
9. The scene/venue can be referenced ONCE across all verses, but don't repeat it - focus on the opponent and topic
10. Match your flow and cadence to the beat style and tempo

OUTPUT FORMAT: Return ONLY the verse lyrics, one bar per line. No explanations, no labels, just the raw lyrics.'''


def _build_previous_verses_section(previous_verses: list[dict]) -> str:
    """Build the previous verses context section."""
    if not previous_verses:
        return ""

    lines = ["PREVIOUS VERSES IN THIS BATTLE:"]
    for i, verse_data in enumerate(previous_verses, 1):
        rapper = verse_data.get("rapper", f"Rapper {i}")
        verse = verse_data.get("verse", "")
        lines.append(f"\n[Verse {i} - {rapper}]")
        lines.append(verse)

    return "\n".join(lines)


def _get_verse_specific_instruction(verse_number: int) -> str:
    """Get verse-specific instructions based on verse number."""
    instructions = {
        1: "This is the OPENING verse - establish dominance, introduce yourself, and set the tone",
        2: "This is a RESPONSE verse - directly respond to the previous verse, counter their points, and attack",
        3: "This is a COMEBACK verse - escalate the battle, reference earlier disses, and hit harder",
        4: "This is the CLOSING verse - deliver your most devastating bars, end with a knockout punchline",
    }
    return instructions.get(verse_number, "Deliver hard-hitting bars")


def _get_verse_context(verse_number: int) -> str:
    """Get context about the verse position."""
    contexts = {
        1: "You're opening the battle. No previous verses yet.",
        2: "You're responding to your opponent's opening verse.",
        3: "The battle is heating up. Both rappers have delivered one verse each.",
        4: "This is the final verse. Time to close out and win the battle.",
    }
    return contexts.get(verse_number, "")


def _get_beat_flow_guidance(style: str | None, bpm: int | None) -> str:
    """Generate flow guidance based on beat parameters."""
    if not style or not bpm:
        return ""

    guidance = {
        "trap": f"Rolling hi-hats at {bpm} BPM. Use triplet flows, ad-libs (yeah, what, uh). Leave room for 808 drops.",
        "boom bap": f"Classic {bpm} BPM groove. Head-nodding pocket flow, emphasize beats 2 and 4. Old school cadence.",
        "west coast": f"Bouncy g-funk at {bpm} BPM. Smooth, laid-back delivery. Syncopated, melodic phrases.",
        "drill": f"Aggressive {bpm} BPM. Sliding 808s, menacing tone. Triplet patterns, staccato delivery.",
    }
    flow_text = guidance.get(style.lower(), f"Rap at {bpm} BPM tempo.")
    return f"\nBEAT: {style} at {bpm} BPM\nFLOW GUIDANCE: {flow_text}"


def generate_verse(
    rapper_name: str,
    rapper_twitter: str | None,
    opponent_name: str,
    opponent_twitter: str | None,
    topic: str,
    description: str,
    scene_description: str,
    previous_verses: list[dict],
    verse_number: int,
    beat_style: str | None = None,
    beat_bpm: int | None = None,
    tweet_context: str = "",
) -> tuple[str | None, str]:
    """
    Call Grok API to generate a battle rap verse.

    Args:
        rapper_name: Name of the current rapper
        rapper_twitter: Optional Twitter handle for personality context
        opponent_name: Name of the opponent
        opponent_twitter: Optional Twitter handle for opponent
        topic: Battle topic
        description: Battle description
        scene_description: Scene setting description
        previous_verses: List of previous verses [{"rapper": "name", "verse": "text"}, ...]
        verse_number: Which verse (1-4)
        beat_style: Optional beat style (trap, boom bap, west coast, drill)
        beat_bpm: Optional tempo in BPM
        tweet_context: Pre-fetched tweet context for both fighters

    Returns:
        Tuple of (verse_text, status_message)
    """
    if not API_KEY:
        return None, "Error: XAI_API_KEY not set in environment"

    if not rapper_name or not opponent_name:
        return None, "Error: Both rapper and opponent names are required"

    if not topic:
        return None, "Error: Battle topic is required"

    # Build personality context from Twitter handles (for research, not for lyrics)
    personality_lines = []
    if rapper_twitter:
        handle = rapper_twitter if rapper_twitter.startswith("@") else f"@{rapper_twitter}"
        personality_lines.append(f"Research {rapper_name}'s personality from their Twitter ({handle}) for authentic voice, but do NOT use the handle in lyrics")
    if opponent_twitter:
        handle = opponent_twitter if opponent_twitter.startswith("@") else f"@{opponent_twitter}"
        personality_lines.append(f"Research {opponent_name}'s personality from their Twitter ({handle}) for context, but do NOT use the handle in lyrics")
    personality_context = "\n".join(personality_lines) if personality_lines else ""

    # Build tweet context section if provided
    tweet_context_section = ""
    if tweet_context:
        tweet_context_section = f"""REAL-TIME X/TWITTER INTEL:
{tweet_context}

Use this intel to make your bars PERSONAL and CURRENT. Reference their real tweets, opinions, and any beef between them!"""

    # Build the prompt
    prompt = VERSE_PROMPT_TEMPLATE.format(
        topic=topic,
        description=description or "An epic rap battle",
        beat_context=_get_beat_flow_guidance(beat_style, beat_bpm),
        scene_description=scene_description or "A packed venue with an electric crowd",
        rapper_name=rapper_name,
        opponent_name=opponent_name,
        personality_context=personality_context,
        tweet_context=tweet_context_section,
        verse_number=verse_number,
        verse_context=_get_verse_context(verse_number),
        previous_verses_section=_build_previous_verses_section(previous_verses),
        verse_specific_instruction=_get_verse_specific_instruction(verse_number),
    )

    try:
        response = requests.post(
            f"{API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-4-1-fast-reasoning",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "max_tokens": 1000,
            },
            timeout=60,
        )

        if response.status_code != 200:
            return None, f"API Error {response.status_code}: {response.text}"

        content = response.json()["choices"][0]["message"]["content"]

        # Clean up the response
        content = content.strip()
        # Remove any markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:\w*)\s*\n?", "", content)
            content = re.sub(r"\n?```\s*$", "", content)

        return content.strip(), f"Verse {verse_number} generated successfully"

    except requests.exceptions.Timeout:
        return None, "Error: Request timed out"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"
    except (KeyError, IndexError) as e:
        return None, f"Error parsing response: {e}"


def generate_all_verses(
    char1_name: str,
    char1_twitter: str | None,
    char2_name: str,
    char2_twitter: str | None,
    topic: str,
    description: str,
    scene_description: str,
    beat_style: str | None = None,
    beat_bpm: int | None = None,
) -> tuple[list[str], str]:
    """
    Generate all 4 verses for a complete rap battle.

    Order: char1 verse 1 -> char2 verse 1 -> char1 verse 2 -> char2 verse 2

    Args:
        char1_name: Name of character 1
        char1_twitter: Optional Twitter handle for character 1
        char2_name: Name of character 2
        char2_twitter: Optional Twitter handle for character 2
        topic: Battle topic
        description: Battle description
        scene_description: Scene setting description
        beat_style: Optional beat style (trap, boom bap, west coast, drill)
        beat_bpm: Optional tempo in BPM

    Returns:
        Tuple of (list of 4 verses, status_message)
    """
    verses = []
    previous_verses = []

    # Fetch tweet context if handles are provided
    tweet_context = ""
    if char1_twitter or char2_twitter:
        from app_gradio_fastapi.services.twitter_api import get_tweet_context_for_battle
        tweet_context, tweet_status = get_tweet_context_for_battle(
            char1_handle=char1_twitter,
            char2_handle=char2_twitter,
        )
        # Log tweet fetch status (context will be empty string if fetch failed)
        if tweet_context:
            print(f"Tweet context fetched: {tweet_status}")

    # Define the verse order: (rapper_name, rapper_twitter, opponent_name, opponent_twitter)
    verse_order = [
        (char1_name, char1_twitter, char2_name, char2_twitter),  # Verse 1: char1
        (char2_name, char2_twitter, char1_name, char1_twitter),  # Verse 2: char2
        (char1_name, char1_twitter, char2_name, char2_twitter),  # Verse 3: char1
        (char2_name, char2_twitter, char1_name, char1_twitter),  # Verse 4: char2
    ]

    for verse_num, (rapper, rapper_tw, opponent, opponent_tw) in enumerate(verse_order, 1):
        verse_text, status = generate_verse(
            rapper_name=rapper,
            rapper_twitter=rapper_tw,
            opponent_name=opponent,
            opponent_twitter=opponent_tw,
            topic=topic,
            description=description,
            scene_description=scene_description,
            previous_verses=previous_verses,
            verse_number=verse_num,
            beat_style=beat_style,
            beat_bpm=beat_bpm,
            tweet_context=tweet_context,
        )

        if verse_text is None:
            return verses, f"Failed at verse {verse_num}: {status}"

        verses.append(verse_text)
        previous_verses.append({"rapper": rapper, "verse": verse_text})

    return verses, "All 4 verses generated successfully"
