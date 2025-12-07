"""
Runway API integration for video generation.
Uses Runway's gen4_turbo model for image-to-video animation.
"""

import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

RUNWAY_API_SECRET = os.environ.get("RUNWAYML_API_SECRET")
API_BASE = "https://api.dev.runwayml.com/v1"
API_VERSION = "2024-11-06"
OUTPUTS_DIR = Path("outputs/videos")

# Director-style prompts with dynamic character movement
CAMERA_DIRECTIONS = {
    0: "Cinematic low-angle push-in, performer spreads arms wide then points toward camera, head nodding to rhythm, expressive face, shoulders moving, dramatic rim lighting, atmospheric haze, passionate delivery",
    1: "Dutch angle tracking shot, performer walks into frame with confidence, arms crossed then opening to gesture, head tilting with knowing smile, stepping forward, jewelry catching light, stylish cross-lighting",
    2: "Extreme close-up pulling back as performer leans forward with intensity, hand gesturing toward camera, focused expression, then steps back with arms spread in confident pose, dramatic lighting",
    3: "Steadicam arc shot, performer turning with arms extended then stopping to place hand on chest, mic hand raised then lowering to point down, head moving with energy, body grooving to beat",
    4: "Wide crane shot, both performers step toward center stage, building tension, one raises hand while other stands confident, dramatic pause then celebration - winner jumps with arms raised, confetti falling, crowd cheering",
}


def build_video_prompt(segment_index: int, theme: str, speaker: str) -> str:
    """
    Build a director-style video generation prompt.

    Args:
        segment_index: 0-4 for the five segments
        theme: Visual theme (medieval, space, cyberpunk, etc.)
        speaker: "Person A", "Person B", or "Both"
    """
    camera_direction = CAMERA_DIRECTIONS.get(segment_index, CAMERA_DIRECTIONS[0])
    return f"{camera_direction}, {theme} aesthetic, 8 Mile rap battle atmosphere, {speaker} performing with intensity, cinematic color grading, 24fps film look"


def generate_video_from_image(
    image_path: str,
    prompt_text: str,
    output_path: Path | None = None,
    duration: int = 10,
    ratio: str = "1280:720",
    model: str = "gen4_turbo",
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

    # If image_path is a local file, we need to read and base64 encode it
    # or upload it first. For now, assume it could be a URL or local path
    if image_path.startswith("http"):
        prompt_image = image_path
    else:
        # Read local file and convert to data URI
        import base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        # Determine mime type
        ext = Path(image_path).suffix.lower()
        mime_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
        mime_type = mime_types.get(ext, "image/png")
        prompt_image = f"data:{mime_type};base64,{image_data}"

    try:
        # Create the task
        response = requests.post(
            f"{API_BASE}/image_to_video",
            headers=headers,
            json={
                "model": model,
                "promptImage": prompt_image,
                "promptText": prompt_text,
                "ratio": ratio,
                "duration": duration,
            },
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
