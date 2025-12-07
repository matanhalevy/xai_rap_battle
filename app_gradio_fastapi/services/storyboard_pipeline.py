"""
Storyboard pipeline orchestrating the full rap battle video generation flow.

Full Pipeline:
1. Parse script → 5 segments
2. Generate storyboard images (Grok)
3. Animate images to video (Runway)
4. Lip sync each video with vocal audio segment (Sync Labs) - OPTIONAL
5. Compose all videos with continuous beat track
"""

from pathlib import Path
from dataclasses import dataclass, field

from app_gradio_fastapi.services.script_parser import (
    parse_rap_script,
    ensure_five_segments,
    ensure_three_segments,
    BattleSegment,
    Speaker,
)
from app_gradio_fastapi.services.grok_image_api import generate_all_storyboards
from app_gradio_fastapi.services.runway_api import generate_all_videos
from app_gradio_fastapi.services.sync_labs_api import (
    upload_files_for_lipsync,
    lipsync_all_segments,
)
from app_gradio_fastapi.services.video_composer import (
    compose_battle_video,
    compose_with_continuous_beat,
    compose_with_audio_clips,
    parse_segment_timings,
    split_audio_into_segments,
)


@dataclass
class PipelineResult:
    """Result of the storyboard pipeline."""
    success: bool
    segments: list[BattleSegment]
    storyboard_images: list[str]
    video_segments: list[str]
    lipsynced_videos: list[str] = field(default_factory=list)
    final_video: str | None = None
    status_messages: list[str] = field(default_factory=list)


def run_storyboard_pipeline(
    script: str,
    theme: str,
    audio_clips: list[str],
    beat_path: str | None = None,
    speaker_a_name: str = "",
    speaker_b_name: str = "",
    character_a_desc: str = "intense male rapper in streetwear, hood up, gold chains",
    character_b_desc: str = "confident female rapper in urban fashion, braids, bold makeup",
    skip_video_generation: bool = False,
    enable_lipsync: bool = False,
    test_mode: bool = False,
) -> PipelineResult:
    """
    Run the full storyboard pipeline.

    Args:
        script: The rap battle script with speaker name markers
        theme: Visual theme (medieval, space, cyberpunk, etc.)
        audio_clips: List of audio files (4 for full, 2 for test_mode)
        beat_path: Optional path to the beat/instrumental track (continuous underneath)
        speaker_a_name: Name of speaker A as it appears in script (e.g., "Elon Musk")
        speaker_b_name: Name of speaker B as it appears in script (e.g., "Sam Altman")
        character_a_desc: Visual description of speaker A for image generation
        character_b_desc: Visual description of speaker B for image generation
        skip_video_generation: If True, only generate images (faster for testing)
        enable_lipsync: If True, use Sync Labs for lip sync (requires URL hosting)
        test_mode: If True, only generate 3 segments (A, B, conclusion) to save credits

    Returns:
        PipelineResult with all outputs and status
    """
    status_messages = []

    # Validate audio clips
    expected_clips = 2 if test_mode else 4
    if len(audio_clips) != expected_clips:
        status_messages.append(f"Error: Expected {expected_clips} audio clips, got {len(audio_clips)}")
        return PipelineResult(
            success=False,
            segments=[],
            storyboard_images=[],
            video_segments=[],
            status_messages=status_messages,
        )

    # Step 1: Parse the script
    status_messages.append("Parsing rap script...")
    if test_mode:
        status_messages.append("TEST MODE: Only generating 3 segments (A, B, Conclusion)")
    if speaker_a_name or speaker_b_name:
        status_messages.append(f"Speaker names: {speaker_a_name or 'auto'} vs {speaker_b_name or 'auto'}")
    segments = parse_rap_script(script, speaker_a_name, speaker_b_name)
    segments = ensure_three_segments(segments) if test_mode else ensure_five_segments(segments)
    status_messages.append(f"Parsed {len(segments)} segments")

    for seg in segments:
        status_messages.append(f"  - {seg.speaker.value}: {len(seg.verses)} verses")

    # Step 2: Generate storyboard images
    status_messages.append("Generating storyboard images with Grok...")
    storyboard_images, img_status = generate_all_storyboards(
        segments=segments,
        theme=theme,
        character_a_desc=character_a_desc,
        character_b_desc=character_b_desc,
    )
    status_messages.append(img_status)

    if len(storyboard_images) != len(segments):
        return PipelineResult(
            success=False,
            segments=segments,
            storyboard_images=storyboard_images,
            video_segments=[],
            status_messages=status_messages,
        )

    if skip_video_generation:
        status_messages.append("Skipping video generation (test mode)")
        return PipelineResult(
            success=True,
            segments=segments,
            storyboard_images=storyboard_images,
            video_segments=[],
            status_messages=status_messages,
        )

    # Step 3: Generate videos from storyboards
    status_messages.append("Generating videos from storyboards with Runway...")
    speakers = [seg.speaker.value for seg in segments]
    video_segments, vid_status = generate_all_videos(
        image_paths=storyboard_images,
        theme=theme,
        speakers=speakers,
    )
    status_messages.append(vid_status)

    if len(video_segments) != len(segments):
        return PipelineResult(
            success=False,
            segments=segments,
            storyboard_images=storyboard_images,
            video_segments=video_segments,
            status_messages=status_messages,
        )

    # Step 4: Lip sync with Sync Labs
    lipsynced_videos = []
    if enable_lipsync:
        status_messages.append("Uploading files for lip sync...")

        # Only lip sync the non-conclusion videos (first N-1 segments)
        videos_to_sync = video_segments[:-1]  # All except conclusion
        audios_to_sync = audio_clips  # All audio clips

        # Upload to temp hosting
        video_urls, audio_urls, upload_status = upload_files_for_lipsync(
            video_paths=videos_to_sync,
            audio_paths=audios_to_sync,
        )
        status_messages.append(upload_status)

        if len(video_urls) != len(videos_to_sync) or len(audio_urls) != len(audios_to_sync):
            status_messages.append("Upload failed - falling back to audio overlay")
            lipsynced_videos = video_segments
        else:
            # Run lip sync
            status_messages.append("Running lip sync with Sync Labs...")
            synced_paths, sync_status = lipsync_all_segments(
                video_urls=video_urls,
                audio_urls=audio_urls,
            )
            status_messages.append(sync_status)

            if len(synced_paths) == len(videos_to_sync):
                # Add conclusion video (no lip sync needed)
                lipsynced_videos = synced_paths + [video_segments[-1]]
                status_messages.append(f"Lip synced {len(synced_paths)} segments")
            else:
                status_messages.append("Lip sync failed - falling back to audio overlay")
                lipsynced_videos = video_segments
    else:
        lipsynced_videos = video_segments

    # Step 5: Compose final video with audio clips and beat
    status_messages.append("Composing final video...")

    # Compose videos with their corresponding audio clips + continuous beat
    final_video, compose_status = compose_with_audio_clips(
        video_paths=lipsynced_videos,
        audio_clips=audio_clips,
        beat_path=beat_path,
    )

    status_messages.append(compose_status)

    return PipelineResult(
        success=(final_video is not None),
        segments=segments,
        storyboard_images=storyboard_images,
        video_segments=video_segments,
        lipsynced_videos=lipsynced_videos,
        final_video=final_video,
        status_messages=status_messages,
    )


def run_storyboard_only(
    script: str,
    theme: str,
    character_a_desc: str = "intense male rapper in streetwear",
    character_b_desc: str = "confident female rapper in urban fashion",
) -> tuple[list[str], list[str]]:
    """
    Run only the storyboard image generation (no video/audio).

    Useful for quick previews.

    Returns:
        Tuple of (image_paths, status_messages)
    """
    status_messages = []

    segments = parse_rap_script(script)
    segments = ensure_five_segments(segments)
    status_messages.append(f"Parsed {len(segments)} segments")

    storyboard_images, img_status = generate_all_storyboards(
        segments=segments,
        theme=theme,
        character_a_desc=character_a_desc,
        character_b_desc=character_b_desc,
    )
    status_messages.append(img_status)

    return storyboard_images, status_messages
