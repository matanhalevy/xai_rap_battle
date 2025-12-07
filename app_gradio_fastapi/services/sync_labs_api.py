"""
Sync Labs API integration for lip sync video generation.
Uses sync.so API to sync lip movements in videos to match audio.
"""

import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SYNC_API_KEY = os.environ.get("SYNC_API_KEY")
API_BASE = "https://api.sync.so/v2"
OUTPUTS_DIR = Path("outputs/lipsynced")


def create_lipsync_generation(
    video_url: str,
    audio_url: str,
    model: str = "lipsync-2",
    sync_mode: str = "loop",
    webhook_url: str | None = None,
) -> tuple[str | None, str]:
    """
    Create a lip sync generation job.

    Args:
        video_url: URL to the source video
        audio_url: URL to the audio file to sync
        model: Model to use (lipsync-2, lipsync-1.9.0-beta, lipsync-2-pro)
        sync_mode: How to handle length mismatch (bounce, loop, cut_off, silence, remap)
        webhook_url: Optional webhook for completion notification

    Returns:
        Tuple of (generation_id, status_message)
    """
    if not SYNC_API_KEY:
        return None, "Error: SYNC_API_KEY not set in environment"

    headers = {
        "x-api-key": SYNC_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "input": [
            {"type": "video", "url": video_url},
            {"type": "audio", "url": audio_url},
        ],
        "options": {
            "sync_mode": sync_mode,
        },
    }

    if webhook_url:
        payload["webhookUrl"] = webhook_url

    try:
        response = requests.post(
            f"{API_BASE}/generate",
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.status_code not in [200, 201]:
            return None, f"API Error {response.status_code}: {response.text}"

        data = response.json()
        generation_id = data.get("id")

        if not generation_id:
            return None, f"No generation ID in response: {data}"

        return generation_id, f"Lip sync job created: {generation_id}"

    except requests.exceptions.Timeout:
        return None, "Error: Request timed out"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"
    except Exception as e:
        return None, f"Error: {e}"


def get_generation_status(generation_id: str) -> tuple[dict | None, str]:
    """
    Get the status of a lip sync generation job.

    Returns:
        Tuple of (generation_data, status_message)
    """
    if not SYNC_API_KEY:
        return None, "Error: SYNC_API_KEY not set"

    headers = {
        "x-api-key": SYNC_API_KEY,
    }

    try:
        response = requests.get(
            f"{API_BASE}/generate/{generation_id}",
            headers=headers,
            timeout=30,
        )

        if response.status_code != 200:
            return None, f"API Error {response.status_code}: {response.text}"

        return response.json(), "Status retrieved"

    except Exception as e:
        return None, f"Error: {e}"


def poll_generation_completion(
    generation_id: str,
    max_wait: int = 600,
    poll_interval: int = 10,
) -> tuple[str | None, str]:
    """
    Poll for generation completion and return the output URL.

    Args:
        generation_id: The generation job ID
        max_wait: Maximum seconds to wait
        poll_interval: Seconds between polls

    Returns:
        Tuple of (output_url, status_message)
    """
    start_time = time.time()

    while time.time() - start_time < max_wait:
        data, status = get_generation_status(generation_id)

        if data is None:
            return None, status

        job_status = data.get("status", "UNKNOWN")

        if job_status == "COMPLETED":
            output_url = data.get("outputUrl")
            if output_url:
                return output_url, "Lip sync completed successfully"
            return None, "Completed but no output URL"

        elif job_status == "FAILED":
            error = data.get("error", "Unknown error")
            error_code = data.get("error_code", "")
            return None, f"Lip sync failed: {error} ({error_code})"

        elif job_status == "REJECTED":
            return None, "Lip sync job was rejected"

        elif job_status in ["PENDING", "PROCESSING"]:
            time.sleep(poll_interval)
            continue

        else:
            return None, f"Unknown status: {job_status}"

    return None, f"Timeout: Job did not complete within {max_wait} seconds"


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
        return f"Error downloading: {e}"


def lipsync_video(
    video_path: str,
    audio_path: str,
    output_path: Path | None = None,
    model: str = "lipsync-2",
    sync_mode: str = "loop",
) -> tuple[str | None, str]:
    """
    Lip sync a video with audio.

    Note: This requires the video and audio to be accessible via URL.
    For local files, you'll need to upload them to a hosting service first.

    Args:
        video_path: Path or URL to the source video
        audio_path: Path or URL to the audio file
        output_path: Where to save the output video
        model: Sync Labs model to use
        sync_mode: How to handle length mismatch

    Returns:
        Tuple of (output_video_path, status_message)
    """
    # Check if paths are URLs or local files
    if not video_path.startswith("http"):
        return None, "Error: video_path must be a URL (Sync Labs requires URLs)"
    if not audio_path.startswith("http"):
        return None, "Error: audio_path must be a URL (Sync Labs requires URLs)"

    # Create the generation job
    gen_id, status = create_lipsync_generation(
        video_url=video_path,
        audio_url=audio_path,
        model=model,
        sync_mode=sync_mode,
    )

    if gen_id is None:
        return None, status

    # Poll for completion
    output_url, status = poll_generation_completion(gen_id)

    if output_url is None:
        return None, status

    # Download the result
    if output_path is None:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUTS_DIR / f"lipsynced_{gen_id}.mp4"

    download_status = download_video(output_url, output_path)
    if "Error" in download_status:
        return None, download_status

    return str(output_path), f"Lip synced video saved: {output_path}"


def lipsync_all_segments(
    video_urls: list[str],
    audio_urls: list[str],
    model: str = "lipsync-2",
    sync_mode: str = "cut_off",
) -> tuple[list[str], str]:
    """
    Lip sync all video segments with their corresponding audio.

    Args:
        video_urls: List of video URLs
        audio_urls: List of audio URLs (same length as video_urls)
        model: Sync Labs model
        sync_mode: How to handle length mismatch

    Returns:
        Tuple of (list of output URLs, status message)
    """
    if len(video_urls) != len(audio_urls):
        return [], f"Error: video and audio counts don't match ({len(video_urls)} vs {len(audio_urls)})"

    output_urls = []
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    for i, (video_url, audio_url) in enumerate(zip(video_urls, audio_urls)):
        output_path = OUTPUTS_DIR / f"segment_{i}_lipsynced.mp4"

        result_path, status = lipsync_video(
            video_path=video_url,
            audio_path=audio_url,
            output_path=output_path,
            model=model,
            sync_mode=sync_mode,
        )

        if result_path is None:
            return output_urls, f"Failed at segment {i}: {status}"

        output_urls.append(result_path)

    return output_urls, f"Lip synced {len(output_urls)} segments"
