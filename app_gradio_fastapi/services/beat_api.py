"""
Grok API integration for beat pattern generation.
"""

import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("XAI_API_KEY")
API_BASE = "https://api.x.ai/v1"


BEAT_PROMPT_TEMPLATE = '''You are a professional hip-hop producer. Generate a beat pattern for a {style} rap beat.

OUTPUT FORMAT: Return ONLY valid JSON. No explanations, no markdown code blocks, just raw JSON.

SCHEMA:
{{
  "metadata": {{
    "title": "<creative beat name>",
    "style": "{style}",
    "bpm": {bpm},
    "time_signature": [4, 4],
    "bars": {bars},
    "loopable": true
  }},
  "tracks": {{
    "K": {{ "name": "kick", "file": "kick-drum-263837.mp3" }},
    "S": {{ "name": "snare", "file": "snare-drum-341273.mp3" }},
    "H": {{ "name": "hi-hat", "file": "hi-hat-231042.mp3" }},
    "B": {{ "name": "808-bass", "file": "808-bass-drum-421219.mp3" }},
    "C": {{ "name": "clap", "file": "clap-375693.mp3" }},
    "O": {{ "name": "open-hat", "file": "open-hi-hat-431740.mp3" }},
    "X": {{ "name": "crash", "file": "tr808-crash-cymbal-241377.mp3" }},
    "P": {{ "name": "perc", "file": "shaker-drum-434902.mp3" }}
  }},
  "pattern": [
    {{
      "bar": 1,
      "beats": [
        {{ "beat": 1, "events": [{{"sound": "K", "duration": "q"}}, {{"sound": "B", "duration": "q"}}] }},
        {{ "beat": 1.5, "events": [{{"sound": "H", "duration": "e"}}] }},
        {{ "beat": 2, "events": [{{"sound": "H", "duration": "e"}}] }},
        {{ "beat": 3, "events": [{{"sound": "S", "duration": "q"}}] }}
      ]
    }}
  ]
}}

NOTATION RULES:
- Sound codes: K=kick, S=snare, H=hi-hat(closed), B=808-bass, C=clap, O=open-hat, X=crash, P=perc/shaker, "-"=rest(silence)
- Duration codes: w=whole(4 beats), h=half(2), q=quarter(1), e=eighth(0.5), s=sixteenth(0.25)
- Beat positions: 1, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 2.75, 3, 3.25, 3.5, 3.75, 4, 4.25, 4.5, 4.75
- Multiple sounds can play simultaneously (list in "events" array)
- Omit beat positions that have no events (implicit rest)
- Use "-" explicitly when you want to emphasize a rest in the notation

STYLE GUIDE:
- trap: 130-150 BPM, heavy 808s on beat 1, rolling hi-hats (s duration), claps layered with snares on beat 3, syncopated kicks, open hats for accents
- boom bap: 85-95 BPM, punchy kicks on 1+3, snares on 2+4, sparse hi-hats (e duration), classic swing feel
- west coast: 90-105 BPM, bouncy g-funk kicks, layered with 808, claps on 2+4, open hats for groove
- drill: 140-150 BPM, sliding 808 patterns, aggressive triplet hi-hats, hard snares+claps, open hats for tension

Generate a {bars}-bar loopable {style} beat pattern. Make it groove!'''


def generate_beat_pattern(
    style: str = "trap",
    bpm: int = 140,
    bars: int = 4,
) -> tuple[str | None, str]:
    """
    Call Grok API to generate a beat pattern JSON.

    Args:
        style: Beat style (trap, boom bap, west coast, drill)
        bpm: Tempo in beats per minute
        bars: Number of bars in the pattern

    Returns:
        Tuple of (json_string, status_message)
    """
    if not API_KEY:
        return None, "Error: XAI_API_KEY not set in environment"

    prompt = BEAT_PROMPT_TEMPLATE.format(style=style, bpm=bpm, bars=bars)

    try:
        response = requests.post(
            f"{API_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-2-latest",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 4000,
            },
            timeout=60,
        )

        if response.status_code != 200:
            return None, f"API Error {response.status_code}: {response.text}"

        content = response.json()["choices"][0]["message"]["content"]

        # Strip markdown code blocks if present
        content = content.strip()
        if content.startswith("```"):
            # Remove opening fence
            content = re.sub(r"^```(?:json)?\s*\n?", "", content)
            # Remove closing fence
            content = re.sub(r"\n?```\s*$", "", content)

        return content.strip(), "Beat pattern generated successfully"

    except requests.exceptions.Timeout:
        return None, "Error: Request timed out"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"
    except (KeyError, IndexError) as e:
        return None, f"Error parsing response: {e}"
