"""
Grok Image API integration for storyboard generation.
Uses xAI's grok-2-image model for image generation and editing.
"""

import os
import requests
import base64
import mimetypes
from pathlib import Path
from dotenv import load_dotenv

from app_gradio_fastapi.services.script_parser import BattleSegment, Speaker

load_dotenv()  # Load .env
load_dotenv(".env.local")  # Override with .env.local if present

API_KEY = os.environ.get("XAI_API_KEY")
API_BASE = "https://api.x.ai/v1"
OUTPUTS_DIR = Path("outputs/storyboards")


def image_to_base64_data_url(image_path: str) -> str:
    """Convert a local image file to a base64 data URL for the API."""
    path = Path(image_path)
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type is None:
        mime_type = "image/png"  # Default fallback

    with open(path, "rb") as f:
        image_bytes = f.read()

    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{b64_data}"


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


def build_edit_prompt(
    segment: BattleSegment,
    theme: str,
) -> str:
    """
    Build a transformation prompt for the Image Edit API.

    This focuses on SCENE TRANSFORMATION while preserving the person's identity.
    The face/identity comes from the source image - we only change the environment.

    Args:
        segment: The battle segment to visualize
        theme: Visual theme (medieval, space, cyberpunk, etc.)
    """
    # Extract mood from lyrics
    verse_hint = segment.verse_summary[:100] if segment.verses else ""

    # CRITICAL: Identity preservation instruction FIRST
    identity = "Keep this person's face, features, and identity exactly the same."

    # Scene/environment transformation (not person transformation)
    scene = f"Place them in an epic {theme} rap battle arena with dramatic stage lighting, urban atmosphere, crowd silhouettes in background."

    # Mood from lyrics (if available)
    if verse_hint and verse_hint != "...":
        mood = f"The energy captures the vibe of: '{verse_hint}'"
    else:
        mood = "The energy is intense and competitive."

    # Subtle pose suggestion based on speaker
    if segment.speaker == Speaker.PERSON_A:
        pose = "They have a confident, commanding stance with a microphone."
    elif segment.speaker == Speaker.PERSON_B:
        pose = "They stand with swagger, arms expressing emphasis."
    else:  # Conclusion
        pose = "Triumphant pose with arms raised in victory."

    # Camera/composition varies by segment index
    cameras = {
        0: "Low angle hero shot, spotlights from above.",
        1: "Dynamic angle, dramatic rim lighting.",
        2: "Medium shot with intense expression.",
        3: "Wide angle showing stage presence.",
        4: "Epic wide shot, split lighting, crowd erupting."
    }
    camera = cameras.get(segment.index, "Cinematic composition.")

    # Combine - identity preservation FIRST, then scene, pose, camera, mood
    prompt = f"{identity} {scene} {pose} {camera} {mood} Photorealistic, cinematic, 8 Mile style."

    return prompt


def edit_storyboard_image(
    source_image_path: str,
    transformation_prompt: str,
    output_path: Path | None = None,
) -> tuple[str | None, str]:
    """
    Transform a source image into a rap battle scene using xAI Image Edit API.

    This preserves the face/identity from the source image while applying
    the scene transformation described in the prompt.

    Args:
        source_image_path: Path to the source image (headshot/reference)
        transformation_prompt: Prompt describing the scene transformation
        output_path: Where to save the output image

    Returns:
        Tuple of (image_path_or_url, status_message)
    """
    if not API_KEY:
        return None, "Error: XAI_API_KEY not set in environment"

    try:
        # Convert local image to base64 data URL
        image_data_url = image_to_base64_data_url(source_image_path)

        response = requests.post(
            f"{API_BASE}/images/edits",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "grok-imagine-v0p9",
                "prompt": transformation_prompt,
                "image": {
                    "url": image_data_url,
                },
                "n": 1,
                "response_format": "url",
            },
            timeout=120,
        )

        if response.status_code != 200:
            return None, f"API Error {response.status_code}: {response.text}"

        data = response.json()
        image_url = data["data"][0]["url"]

        # Download the image from URL
        img_response = requests.get(image_url, timeout=60)
        if img_response.status_code != 200:
            return None, f"Failed to download image: {img_response.status_code}"

        if output_path is None:
            OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
            output_path = OUTPUTS_DIR / f"edited_{hash(transformation_prompt) % 10000}.png"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(img_response.content)

        return str(output_path), "Image edited and saved successfully"

    except requests.exceptions.Timeout:
        return None, "Error: Request timed out (image editing can take up to 2 minutes)"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"
    except (KeyError, IndexError) as e:
        return None, f"Error parsing response: {e}"


def edit_all_storyboards(
    segments: list[BattleSegment],
    theme: str,
    speaker_a_image: str,
    speaker_b_image: str,
) -> tuple[list[str], str]:
    """
    Generate storyboard images using the Image Edit API with reference photos.

    This transforms the speaker photos into rap battle scenes while preserving
    their faces/identities.

    Args:
        segments: List of battle segments
        theme: Visual theme
        speaker_a_image: Path to Person A's reference photo
        speaker_b_image: Path to Person B's reference photo

    Returns:
        Tuple of (list of image paths, status message)
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    image_paths = []
    for i, segment in enumerate(segments):
        # Select source image based on speaker
        if segment.speaker == Speaker.PERSON_A:
            source_image = speaker_a_image
        elif segment.speaker == Speaker.PERSON_B:
            source_image = speaker_b_image
        else:  # Conclusion - use Person A as default
            source_image = speaker_a_image

        prompt = build_edit_prompt(segment, theme)
        output_path = OUTPUTS_DIR / f"segment_{i}_{segment.speaker.name.lower()}_edited.png"

        path, status = edit_storyboard_image(source_image, prompt, output_path)
        if path is None:
            return image_paths, f"Failed at segment {i}: {status}"
        image_paths.append(path)

    return image_paths, f"Generated {len(image_paths)} storyboard images from reference photos"
