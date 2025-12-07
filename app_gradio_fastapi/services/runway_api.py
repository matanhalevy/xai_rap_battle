"""
Runway API integration for video generation.
Uses Runway's gen4_turbo model for image-to-video animation.
Supports Act-Two model for lip sync with audio.
"""

import os
import time
import base64
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

RUNWAY_API_SECRET = os.environ.get("RUNWAYML_API_SECRET")
API_BASE = "https://api.dev.runwayml.com/v1"
API_VERSION = "2024-11-06"
OUTPUTS_DIR = Path("outputs/videos")

# Content moderation disclaimer
CONTENT_DISCLAIMER = "Any likeness to real individuals is coincidental and may be due to a look-alike. No celebrities or protected individuals depicted."

# Legacy 5-shot camera directions (kept for backward compatibility)
CAMERA_DIRECTIONS = {
    0: "Cinematic low-angle push-in, performer spreads arms wide then points toward camera, head nodding to rhythm, expressive face, shoulders moving, dramatic rim lighting, atmospheric haze, passionate delivery",
    1: "Dutch angle tracking shot, performer walks into frame with confidence, arms crossed then opening to gesture, head tilting with knowing smile, stepping forward, jewelry catching light, stylish cross-lighting",
    2: "Extreme close-up pulling back as performer leans forward with intensity, hand gesturing toward camera, focused expression, then steps back with arms spread in confident pose, dramatic lighting",
    3: "Steadicam arc shot, performer turning with arms extended then stopping to place hand on chest, mic hand raised then lowering to point down, head moving with energy, body grooving to beat",
    4: "Wide crane shot, both performers step toward center stage, building tension, one raises hand while other stands confident, dramatic pause then celebration - winner jumps with arms raised, confetti falling, crowd cheering",
}

# New 6-shot camera directions for the updated storyboard structure
CAMERA_DIRECTIONS_6SHOT = {
    0: "Cinematic crane shot panning across crowd, revealing both performers on stage, building anticipation, slow zoom toward center stage, atmospheric haze, dramatic spotlight beams",
    1: "Low-angle push-in, performer A spreads arms wide then points at camera, head nodding to rhythm, dramatic rim lighting, passionate delivery, expressive face",
    2: "Dutch angle tracking shot, performer B walks into frame with swagger, confident gestures, stylish cross-lighting, jewelry catching light, head tilting with knowing smile",
    3: "Medium shot showing both performers, focus on speaker A delivering bars while opponent B visible reacting in background, tension building, split lighting",
    4: "Dynamic arc shot around performer B, quick cut showing A's surprised reaction, then back to B's triumphant delivery, energetic camera movement",
    5: "Epic wide crane pullback, both performers step toward center, crowd erupting, confetti falling, triumphant finale, celebration atmosphere",
}


def build_video_prompt(segment_index: int, theme: str, speaker: str, use_6shot: bool = False) -> str:
    """
    Build a director-style video generation prompt.

    Args:
        segment_index: 0-4 for five segments, or 0-5 for six shots
        theme: Visual theme (medieval, space, cyberpunk, etc.)
        speaker: "Person A", "Person B", or "Both"
        use_6shot: If True, use 6-shot camera directions
    """
    if use_6shot:
        camera_direction = CAMERA_DIRECTIONS_6SHOT.get(segment_index, CAMERA_DIRECTIONS_6SHOT[0])
    else:
        camera_direction = CAMERA_DIRECTIONS.get(segment_index, CAMERA_DIRECTIONS[0])
    return f"{camera_direction}, {theme} aesthetic, 8 Mile rap battle atmosphere, {speaker} performing with intensity, cinematic color grading, 24fps film look. {CONTENT_DISCLAIMER}"


def build_6shot_video_prompt(shot_index: int, theme: str, speaker: str, verse_context: str = "") -> str:
    """
    Build a video prompt for the 6-shot storyboard structure.

    Args:
        shot_index: 0-5 for the six shots
        theme: Visual theme
        speaker: Primary speaker in shot
        verse_context: Optional verse text for context

    Returns:
        Formatted prompt string
    """
    camera_direction = CAMERA_DIRECTIONS_6SHOT.get(shot_index, CAMERA_DIRECTIONS_6SHOT[0])

    # Build context-aware prompt
    base_prompt = f"{camera_direction}, {theme} aesthetic, 8 Mile rap battle atmosphere"

    if shot_index == 0:
        # Opening shot - establishing
        base_prompt += ", crowd anticipation, both performers visible, building energy"
    elif shot_index == 5:
        # Closing shot - finale
        base_prompt += ", triumphant conclusion, crowd erupting, victory moment"
    else:
        # Verse shots
        base_prompt += f", {speaker} performing with intensity"
        if verse_context:
            base_prompt += f", energy capturing: {verse_context[:100]}"

    base_prompt += f", cinematic color grading, 24fps film look. {CONTENT_DISCLAIMER}"
    return base_prompt


def generate_video_from_image(
    image_path: str,
    prompt_text: str,
    output_path: Path | None = None,
    duration: int = 10,
    ratio: str = "1280:720",
    model: str = "gen4_turbo",
    reference_image: str | None = None,
) -> tuple[str | None, str]:
    """
    Generate a video from an image using Runway's image-to-video API.

    Args:
        image_path: Path to the source image
        prompt_text: Director-style prompt for video generation
        output_path: Where to save the output video
        duration: Video duration in seconds (5 or 10)
        ratio: Output aspect ratio
        model: Model to use (gen4_turbo or gen3a_turbo)
        reference_image: Optional path to reference image for style/character consistency

    Returns:
        Tuple of (video_path, status_message)
    """
    if not RUNWAY_API_SECRET:
        return None, "Error: RUNWAYML_API_SECRET not set in environment"

    headers = {
        "Authorization": f"Bearer {RUNWAY_API_SECRET}",
        "Content-Type": "application/json",
        "X-Runway-Version": API_VERSION,
    }

    # Helper to convert image path to data URI
    def to_data_uri(path: str) -> str:
        if path.startswith("http"):
            return path
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        ext = Path(path).suffix.lower()
        mime_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
        mime_type = mime_types.get(ext, "image/png")
        return f"data:{mime_type};base64,{data}"

    # Convert source image to data URI
    prompt_image = to_data_uri(image_path)

    # Build request payload
    payload = {
        "model": model,
        "promptImage": prompt_image,
        "promptText": prompt_text,
        "ratio": ratio,
        "duration": duration,
    }

    # Add reference image if provided (for style/character consistency)
    if reference_image:
        ref_uri = to_data_uri(reference_image)
        payload["references"] = [{"type": "image", "uri": ref_uri}]

    try:
        # Create the task
        response = requests.post(
            f"{API_BASE}/image_to_video",
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.status_code not in [200, 201]:
            return None, f"API Error {response.status_code}: {response.text}"

        task_data = response.json()
        task_id = task_data.get("id")

        if not task_id:
            return None, f"No task ID in response: {task_data}"

        # Poll for completion
        video_url, status = poll_task_completion(task_id, headers)

        if video_url is None:
            return None, status

        # Download the video
        if output_path is None:
            OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
            output_path = OUTPUTS_DIR / f"video_{task_id}.mp4"

        download_status = download_video(video_url, output_path)
        if "Error" in download_status:
            return None, download_status

        return str(output_path), f"Video generated: {output_path}"

    except requests.exceptions.Timeout:
        return None, "Error: Request timed out"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"
    except Exception as e:
        return None, f"Error: {e}"


def poll_task_completion(
    task_id: str,
    headers: dict,
    max_wait: int = 300,
    poll_interval: int = 5,
) -> tuple[str | None, str]:
    """
    Poll for task completion.

    Args:
        task_id: The Runway task ID
        headers: Request headers
        max_wait: Maximum seconds to wait
        poll_interval: Seconds between polls

    Returns:
        Tuple of (video_url, status_message)
    """
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            response = requests.get(
                f"{API_BASE}/tasks/{task_id}",
                headers=headers,
                timeout=30,
            )

            if response.status_code != 200:
                return None, f"Poll Error {response.status_code}: {response.text}"

            task_data = response.json()
            status = task_data.get("status", "UNKNOWN")

            if status == "SUCCEEDED":
                # Get the output URL
                output = task_data.get("output", [])
                if output and len(output) > 0:
                    return output[0], "Task completed successfully"
                return None, "Task completed but no output found"

            elif status == "FAILED":
                error = task_data.get("failure", "Unknown error")
                return None, f"Task failed: {error}"

            elif status in ["PENDING", "RUNNING"]:
                time.sleep(poll_interval)
                continue

            else:
                return None, f"Unknown status: {status}"

        except Exception as e:
            return None, f"Poll error: {e}"

    return None, f"Timeout: Task did not complete within {max_wait} seconds"


def download_video(url: str, output_path: Path) -> str:
    """Download video from URL to local path."""
    try:
        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return f"Downloaded to {output_path}"
    except Exception as e:
        return f"Error downloading video: {e}"


def generate_all_videos(
    image_paths: list[str],
    theme: str,
    speakers: list[str],
    duration: int = 10,
) -> tuple[list[str], str]:
    """
    Generate videos for all storyboard images.

    Args:
        image_paths: List of image file paths
        theme: Visual theme
        speakers: List of speaker names for each segment
        duration: Video duration in seconds (5 or 10)

    Returns:
        Tuple of (list of video paths, status message)
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    video_paths = []
    for i, (image_path, speaker) in enumerate(zip(image_paths, speakers)):
        prompt = build_video_prompt(i, theme, speaker)
        output_path = OUTPUTS_DIR / f"segment_{i}.mp4"

        video_path, status = generate_video_from_image(
            image_path=image_path,
            prompt_text=prompt,
            output_path=output_path,
            duration=duration,
        )

        if video_path is None:
            return video_paths, f"Failed at segment {i}: {status}"
        video_paths.append(video_path)

    return video_paths, f"Generated {len(video_paths)} videos"


def generate_video_with_lipsync(
    image_path: str,
    audio_path: str,
    prompt_text: str,
    output_path: Path | None = None,
    duration: int = 10,
    reference_image: str | None = None,
) -> tuple[str | None, str]:
    """
    Generate a video with lip sync using Runway's Act-Two model.

    Args:
        image_path: Path to the source image
        audio_path: Path to the audio file for lip sync
        prompt_text: Director-style prompt for video generation
        output_path: Where to save the output video
        duration: Video duration in seconds
        reference_image: Optional path to reference image for style/character consistency

    Returns:
        Tuple of (video_path, status_message)
    """
    if not RUNWAY_API_SECRET:
        return None, "Error: RUNWAYML_API_SECRET not set in environment"

    headers = {
        "Authorization": f"Bearer {RUNWAY_API_SECRET}",
        "Content-Type": "application/json",
        "X-Runway-Version": API_VERSION,
    }

    # Helper to convert image path to data URI
    def to_data_uri(path: str) -> str:
        if path.startswith("http"):
            return path
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        ext = Path(path).suffix.lower()
        mime_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
        mime_type = mime_types.get(ext, "image/png")
        return f"data:{mime_type};base64,{data}"

    # Convert image to data URI
    prompt_image = to_data_uri(image_path)

    # Convert audio to data URI
    if audio_path.startswith("http"):
        audio_uri = audio_path
    else:
        with open(audio_path, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode("utf-8")
        ext = Path(audio_path).suffix.lower()
        audio_mime_types = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/m4a"}
        audio_mime_type = audio_mime_types.get(ext, "audio/mpeg")
        audio_uri = f"data:{audio_mime_type};base64,{audio_data}"

    try:
        # Build request payload
        payload = {
            "model": "act_two",
            "promptImage": prompt_image,
            "promptText": prompt_text,
            "audio": audio_uri,
            "ratio": "1280:720",
            "duration": duration,
        }

        # Add reference image if provided (for style/character consistency)
        if reference_image:
            ref_uri = to_data_uri(reference_image)
            payload["references"] = [{"type": "image", "uri": ref_uri}]

        # Act-Two API call
        # Note: The exact API structure may need adjustment based on actual Runway API docs
        response = requests.post(
            f"{API_BASE}/act_two",
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.status_code not in [200, 201]:
            # Fallback to regular image-to-video if Act-Two fails
            return None, f"Act-Two API Error {response.status_code}: {response.text}. Consider using regular video generation."

        task_data = response.json()
        task_id = task_data.get("id")

        if not task_id:
            return None, f"No task ID in response: {task_data}"

        # Poll for completion
        video_url, status = poll_task_completion(task_id, headers)

        if video_url is None:
            return None, status

        # Download the video
        if output_path is None:
            OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
            output_path = OUTPUTS_DIR / f"lipsync_{task_id}.mp4"

        download_status = download_video(video_url, output_path)
        if "Error" in download_status:
            return None, download_status

        return str(output_path), f"Video with lip sync generated: {output_path}"

    except requests.exceptions.Timeout:
        return None, "Error: Request timed out"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"
    except Exception as e:
        return None, f"Error: {e}"


def generate_6shot_videos(
    image_paths: list[str],
    theme: str,
    speakers: list[str],
    verse_contexts: list[str] | None = None,
    audio_paths: list[str] | None = None,
    duration: int = 10,
    enable_lipsync: bool = True,
    environment_ref: str | None = None,
) -> tuple[list[str], str]:
    """
    Generate videos for the 6-shot storyboard structure.

    Args:
        image_paths: List of 6 image file paths
        theme: Visual theme
        speakers: List of speaker names for each shot
        verse_contexts: Optional list of verse text for context (6 items, empty for intro/outro)
        audio_paths: Optional list of audio paths for lip sync (4 items for verses)
        duration: Video duration in seconds
        enable_lipsync: Whether to use Act-Two for lip sync on verse shots
        environment_ref: Optional path to environment reference image for style consistency

    Returns:
        Tuple of (list of video paths, status message)
    """
    if len(image_paths) != 6:
        return [], f"Expected 6 images, got {len(image_paths)}"

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    video_paths = []
    verse_contexts = verse_contexts or [""] * 6

    for i, (image_path, speaker) in enumerate(zip(image_paths, speakers)):
        verse_context = verse_contexts[i] if i < len(verse_contexts) else ""
        prompt = build_6shot_video_prompt(i, theme, speaker, verse_context)
        output_path = OUTPUTS_DIR / f"shot_{i}.mp4"

        # Use lip sync for verse shots (1-4) if enabled and audio provided
        is_verse_shot = 1 <= i <= 4
        audio_index = i - 1  # Map shot 1-4 to audio 0-3

        if enable_lipsync and is_verse_shot and audio_paths and audio_index < len(audio_paths):
            # Try Act-Two for lip sync
            video_path, status = generate_video_with_lipsync(
                image_path=image_path,
                audio_path=audio_paths[audio_index],
                prompt_text=prompt,
                output_path=output_path,
                duration=duration,
                reference_image=environment_ref,
            )

            # Fallback to regular generation if lip sync fails
            if video_path is None and "Act-Two API Error" in status:
                video_path, status = generate_video_from_image(
                    image_path=image_path,
                    prompt_text=prompt,
                    output_path=output_path,
                    duration=duration,
                    reference_image=environment_ref,
                )
        else:
            # Regular video generation for opening/closing shots
            video_path, status = generate_video_from_image(
                image_path=image_path,
                prompt_text=prompt,
                output_path=output_path,
                duration=duration,
                reference_image=environment_ref,
            )

        if video_path is None:
            return video_paths, f"Failed at shot {i}: {status}"
        video_paths.append(video_path)

    return video_paths, f"Generated {len(video_paths)} videos (6-shot structure)"
