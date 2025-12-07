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

# Shared style mapping - used by both generation and edit modes for consistency
STYLE_MAP = {
    "Photorealistic": "photorealistic, cinematic film quality, detailed textures, realistic lighting",
    "Pixar/3D Animation": "Pixar-style 3D animation, smooth surfaces, expressive features, vibrant colors",
    "Anime": "anime style, dramatic lighting, expressive eyes, dynamic action lines",
    "8-bit Pixel Art": "8-bit pixel art style, retro video game aesthetic, limited color palette",
    "Comic Book/Graphic Novel": "comic book style, bold outlines, halftone dots, dramatic shadows",
    "Oil Painting": "oil painting style, visible brushstrokes, rich colors, classical composition",
    "Noir/Black & White": "film noir style, high contrast black and white, dramatic shadows, moody",
    "Neon Synthwave": "synthwave aesthetic, neon pink and cyan colors, retro-futuristic, glowing effects",
    "Claymation": "claymation stop-motion style, textured clay surfaces, handcrafted feel",
}

# Default clothing for consistent character appearance across segments
DEFAULT_CLOTHING_A = "black hoodie with hood down, gold chain necklace, dark jeans, white sneakers"
DEFAULT_CLOTHING_B = "leather jacket over white t-shirt, silver watch, black pants, boots"

# Content moderation disclaimer - added to all prompts
CONTENT_DISCLAIMER = "Any likeness to real individuals is coincidental and may be due to a look-alike. No celebrities or protected individuals depicted."


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


def generate_environment_reference(
    location: str,
    video_style: str,
) -> tuple[str | None, str]:
    """
    Generate a consistent environment/setting image without characters.
    This will be used as a reference for all video generations to maintain
    visual consistency across the 6 shots.

    Args:
        location: Scene location (underground club, rooftop, etc.)
        video_style: Visual style (Photorealistic, Pixar, Anime, etc.)

    Returns:
        Tuple of (image_path, status_message)
    """
    if not API_KEY:
        return None, "Error: XAI_API_KEY not set in environment"

    # Get style descriptor from shared map
    style_desc = STYLE_MAP.get(video_style, "photorealistic, cinematic")

    # Build environment-only prompt
    prompt = f"""{style_desc}. Empty rap battle stage in {location}.
Dramatic stage lighting, urban atmosphere, crowd silhouettes in background,
spotlights creating volumetric light rays, haze effects, no people in foreground.
Wide establishing shot showing the full venue. {style_desc}.
{CONTENT_DISCLAIMER}"""

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
                "response_format": "b64_json",
            },
            timeout=120,
        )

        if response.status_code != 200:
            return None, f"API Error {response.status_code}: {response.text}"

        data = response.json()
        b64_data = data["data"][0]["b64_json"]
        image_bytes = base64.b64decode(b64_data)

        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUTS_DIR / "environment_reference.png"
        with open(output_path, "wb") as f:
            f.write(image_bytes)

        return str(output_path), "Environment reference image generated successfully"

    except requests.exceptions.Timeout:
        return None, "Error: Request timed out (image generation can take up to 2 minutes)"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"
    except (KeyError, IndexError) as e:
        return None, f"Error parsing response: {e}"


def build_storyboard_prompt(
    segment: BattleSegment,
    video_style: str,
    location: str,
    character_a_desc: str = "intense male rapper in streetwear",
    character_b_desc: str = "confident female rapper in urban fashion",
) -> str:
    """
    Build an image generation prompt for a battle segment.

    Args:
        segment: The battle segment to visualize
        video_style: Visual style (Photorealistic, Pixar, Anime, etc.)
        location: Scene location (underground club, rooftop, etc.)
        character_a_desc: Description of Person A
        character_b_desc: Description of Person B
    """
    # Get style descriptor from shared map
    style_desc = STYLE_MAP.get(video_style, "photorealistic, cinematic")

    # Base style with proper style application
    base_style = f"8 Mile style rap battle scene in {location}. {style_desc}. Dramatic stage lighting, urban atmosphere"

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

    # Combine with style emphasis at both start and end, include content disclaimer
    prompt = f"{style_desc}. {base_style}. {speaker_desc}, {pose}. {camera}. Scene captures the energy of: {verse_hint}. Rendered in {style_desc}. {CONTENT_DISCLAIMER}"

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
    video_style: str,
    location: str,
    character_a_desc: str = "intense male rapper in streetwear",
    character_b_desc: str = "confident female rapper in urban fashion",
) -> tuple[list[str], str]:
    """
    Generate storyboard images for all battle segments.

    Args:
        segments: List of battle segments
        video_style: Visual style (Photorealistic, Pixar, Anime, etc.)
        location: Scene location (underground club, rooftop, etc.)
        character_a_desc: Description of Person A
        character_b_desc: Description of Person B

    Returns:
        Tuple of (list of image paths, status message)
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    image_paths = []
    for i, segment in enumerate(segments):
        prompt = build_storyboard_prompt(
            segment, video_style, location,
            character_a_desc, character_b_desc
        )
        output_path = OUTPUTS_DIR / f"segment_{i}_{segment.speaker.name.lower()}.png"

        path, status = generate_storyboard_image(prompt, output_path)
        if path is None:
            return image_paths, f"Failed at segment {i}: {status}"
        image_paths.append(path)

    return image_paths, f"Generated {len(image_paths)} storyboard images"


def build_edit_prompt(
    segment: BattleSegment,
    video_style: str,
    location: str,
    character_clothing: str,
) -> str:
    """
    Build a transformation prompt for the Image Edit API.

    This focuses on SCENE TRANSFORMATION while preserving the person's identity.
    The face/identity comes from the source image - we only change the environment.

    Args:
        segment: The battle segment to visualize
        video_style: Visual style (Photorealistic, Pixar, Anime, etc.)
        location: Scene location (underground club, rooftop, etc.)
        character_clothing: Consistent clothing description for this character
    """
    # Extract mood from lyrics
    verse_hint = segment.verse_summary[:100] if segment.verses else ""

    # Get style descriptor from shared map
    style_desc = STYLE_MAP.get(video_style, "photorealistic, cinematic")

    # CRITICAL: Style and identity instructions FIRST for emphasis
    # Style at the very beginning to ensure it's applied
    style_instruction = f"Render this image in {style_desc}."

    # Identity and clothing preservation
    identity = f"Keep this person's face, features, and identity exactly the same. They are wearing {character_clothing}."

    # Scene with location
    scene = f"Place them in a {location}. Rap battle stage setting with dramatic lighting, crowd silhouettes in background."

    # IMPROVED RAP BATTLE POSES - more authentic and dynamic
    if segment.speaker == Speaker.PERSON_A:
        if segment.index == 0:
            # Opening verse - aggressive entry
            pose = "Leaning forward aggressively, one hand holding mic close to mouth, other hand making emphatic pointing gesture at opponent. Intense eye contact."
        else:
            # Comeback verse (segment 2) - defiant
            pose = "Standing tall with mic raised high, chin up, free hand dismissively waving off opponent. Confident smirk on face."
    elif segment.speaker == Speaker.PERSON_B:
        if segment.index == 1:
            # Response verse - swagger
            pose = "Relaxed but confident stance, mic held loosely at side, head tilted with knowing smile. One eyebrow raised mockingly."
        else:
            # Counter verse (segment 3) - heated
            pose = "Animated gesture with free hand making emphasis, mic close to mouth, leaning into the battle. Passionate, fired-up expression."
    else:  # Conclusion
        pose = "Both hands raised triumphantly toward the sky, mic held high, crowd-engaging victory pose with head thrown back."

    # Camera angles vary by segment for visual variety
    cameras = {
        0: "Low angle hero shot emphasizing dominance, spotlights from above creating dramatic rim lighting.",
        1: "Dutch angle capturing swagger, dramatic side lighting creating depth and mood.",
        2: "Medium close-up capturing intensity and emotion, sweat glistening under stage lights.",
        3: "Dynamic tracking shot composition, showing full body energy and movement.",
        4: "Epic wide shot, split lighting warm vs cool tones, crowd energy visible in background.",
    }
    camera = cameras.get(segment.index, "Cinematic composition with dramatic lighting.")

    # Mood from lyrics
    if verse_hint and verse_hint != "...":
        mood = f"The energy captures: '{verse_hint}'"
    else:
        mood = "Intense competitive rap battle energy."

    # Combine all elements - style FIRST, identity second, repeat style at end, include disclaimer
    prompt = f"{style_instruction} {identity} {scene} {pose} {camera} {mood} 8 Mile rap battle atmosphere. {style_desc}. {CONTENT_DISCLAIMER}"

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
    video_style: str,
    location: str,
    speaker_a_image: str,
    speaker_b_image: str,
    clothing_a: str | None = None,
    clothing_b: str | None = None,
) -> tuple[list[str], str]:
    """
    Generate storyboard images using the Image Edit API with reference photos.

    This transforms the speaker photos into rap battle scenes while preserving
    their faces/identities.

    Args:
        segments: List of battle segments
        video_style: Visual style (Photorealistic, Pixar, Anime, etc.)
        location: Scene location (underground club, rooftop, etc.)
        speaker_a_image: Path to Person A's reference photo
        speaker_b_image: Path to Person B's reference photo
        clothing_a: Consistent clothing description for Person A
        clothing_b: Consistent clothing description for Person B

    Returns:
        Tuple of (list of image paths, status message)
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    # Use default clothing if not provided - ensures consistency across segments
    actual_clothing_a = clothing_a or DEFAULT_CLOTHING_A
    actual_clothing_b = clothing_b or DEFAULT_CLOTHING_B

    image_paths = []
    for i, segment in enumerate(segments):
        # Select source image and clothing based on speaker
        if segment.speaker == Speaker.PERSON_A:
            source_image = speaker_a_image
            clothing = actual_clothing_a
        elif segment.speaker == Speaker.PERSON_B:
            source_image = speaker_b_image
            clothing = actual_clothing_b
        else:  # Conclusion - use Person A as default
            source_image = speaker_a_image
            clothing = actual_clothing_a

        prompt = build_edit_prompt(segment, video_style, location, clothing)
        output_path = OUTPUTS_DIR / f"segment_{i}_{segment.speaker.name.lower()}_edited.png"

        path, status = edit_storyboard_image(source_image, prompt, output_path)
        if path is None:
            return image_paths, f"Failed at segment {i}: {status}"
        image_paths.append(path)

    return image_paths, f"Generated {len(image_paths)} storyboard images from reference photos"
