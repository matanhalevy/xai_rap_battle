"""
Grok Image API integration for storyboard generation.
Uses xAI's grok-2-image model for image generation.
"""

import os
import requests
import base64
from pathlib import Path
from dotenv import load_dotenv

from app_gradio_fastapi.services.script_parser import BattleSegment, Speaker

load_dotenv()

API_KEY = os.environ.get("XAI_API_KEY")
API_BASE = "https://api.x.ai/v1"
OUTPUTS_DIR = Path("outputs/storyboards")


def build_storyboard_prompt(
    segment: BattleSegment,
    theme: str,
    character_a_desc: str = "intense male rapper in streetwear",
    character_b_desc: str = "confident female rapper in urban fashion",
) -> str:
    """
    Build an image generation prompt for a battle segment.

    Args:
        segment: The battle segment to visualize
        theme: Visual theme (medieval, space, cyberpunk, etc.)
        character_a_desc: Description of Person A
        character_b_desc: Description of Person B
    """
    # Base style
    base_style = f"8 Mile style rap battle scene, {theme} aesthetic, dramatic stage lighting, urban atmosphere, photorealistic, cinematic composition"

    # Speaker-specific framing
    if segment.speaker == Speaker.PERSON_A:
        speaker_desc = character_a_desc
        pose = "aggressive stance, pointing at opponent, commanding the stage"
        if segment.index == 0:
            camera = "low angle shot looking up at rapper, crowd silhouettes in background"
        else:
            camera = "medium close-up, intense facial expression, sweat glistening under spotlights"
    elif segment.speaker == Speaker.PERSON_B:
        speaker_desc = character_b_desc
        pose = "confident swagger, arms crossed or mic raised high"
        if segment.index == 1:
            camera = "dutch angle shot, rapper entering the frame with confidence"
        else:
            camera = "tracking shot composition, rapper in motion, dynamic energy"
    else:  # Conclusion
        speaker_desc = f"{character_a_desc} and {character_b_desc}"
        pose = "both rappers facing each other in final standoff"
        camera = "wide shot showing both contenders, split lighting warm vs cool, crowd erupting"

    # Verse context hint
    verse_hint = segment.verse_summary[:100] if segment.verses else ""

    prompt = f"{base_style}. {speaker_desc}, {pose}. {camera}. Scene captures the energy of: {verse_hint}"

    return prompt


def generate_storyboard_image(
    prompt: str,
    output_path: Path | None = None,
    response_format: str = "b64_json",
) -> tuple[str | None, str]:
    """
    Generate a storyboard image using Grok Image API.

    Args:
        prompt: The image generation prompt
        output_path: Where to save the image (if response_format is b64_json)
        response_format: "url" or "b64_json"

    Returns:
        Tuple of (image_path_or_url, status_message)
    """
    if not API_KEY:
        return None, "Error: XAI_API_KEY not set in environment"

    try:
        response = requests.post(
            f"{API_BASE}/images/generations",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-2-image",
                "prompt": prompt,
                "n": 1,
                "response_format": response_format,
            },
            timeout=120,
        )

        if response.status_code != 200:
            return None, f"API Error {response.status_code}: {response.text}"

        data = response.json()

        if response_format == "url":
            image_url = data["data"][0]["url"]
            return image_url, "Image generated successfully"
        else:
            # b64_json - decode and save
            b64_data = data["data"][0]["b64_json"]
            image_bytes = base64.b64decode(b64_data)

            if output_path is None:
                OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
                output_path = OUTPUTS_DIR / f"storyboard_{hash(prompt) % 10000}.png"

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(image_bytes)

            return str(output_path), "Image generated and saved successfully"

    except requests.exceptions.Timeout:
        return None, "Error: Request timed out (image generation can take up to 2 minutes)"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"
    except (KeyError, IndexError) as e:
        return None, f"Error parsing response: {e}"


def generate_all_storyboards(
    segments: list[BattleSegment],
    theme: str,
    character_a_desc: str = "intense male rapper in streetwear",
    character_b_desc: str = "confident female rapper in urban fashion",
) -> tuple[list[str], str]:
    """
    Generate storyboard images for all battle segments.

    Args:
        segments: List of battle segments
        theme: Visual theme
        character_a_desc: Description of Person A
        character_b_desc: Description of Person B

    Returns:
        Tuple of (list of image paths, status message)
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    image_paths = []
    for i, segment in enumerate(segments):
        prompt = build_storyboard_prompt(segment, theme, character_a_desc, character_b_desc)
        output_path = OUTPUTS_DIR / f"segment_{i}_{segment.speaker.name.lower()}.png"

        path, status = generate_storyboard_image(prompt, output_path)
        if path is None:
            return image_paths, f"Failed at segment {i}: {status}"
        image_paths.append(path)

    return image_paths, f"Generated {len(image_paths)} storyboard images"
