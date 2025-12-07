"""
Storyboard pipeline orchestrating the full rap battle video generation flow.

Full Pipeline (6-shot structure):
1. Parse script → 4 verse segments
2. Generate environment reference image (Grok) for consistency
3. Generate 6 storyboard images (Grok) - opening, 4 verses, closing
4. Generate 6 videos with lip sync (Runway Act-Two)
5. Compose final video with audio

Legacy Pipeline (5 segments):
1. Parse script → 5 segments
2. Generate storyboard images (Grok)
3. Animate images to video (Runway)
4. Lip sync each video with vocal audio segment (Sync Labs) - OPTIONAL
5. Compose all videos with continuous beat track
"""

from pathlib import Path
from dataclasses import dataclass, field

from pydub import AudioSegment

from app_gradio_fastapi.services.script_parser import (
    parse_rap_script,
    ensure_five_segments,
    ensure_three_segments,
    BattleSegment,
    Speaker,
    ShotType,
    StoryboardShot,
    create_storyboard_shots,
)
from app_gradio_fastapi.services.grok_image_api import (
    generate_all_storyboards,
    edit_all_storyboards,
    generate_environment_reference,
)
from app_gradio_fastapi.services.runway_api import (
    generate_all_videos,
    generate_6shot_videos,
)
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
    video_style: str,
    location: str,
    audio_clips: list[str],
    beat_path: str | None = None,
    speaker_a_name: str = "",
    speaker_b_name: str = "",
    speaker_a_image: str | None = None,
    speaker_b_image: str | None = None,
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
        video_style: Visual style (Photorealistic, Pixar, Anime, etc.)
        location: Scene location (underground club, rooftop, etc.)
        audio_clips: List of audio files (4 for full, 2 for test_mode)
        beat_path: Optional path to the beat/instrumental track (continuous underneath)
        speaker_a_name: Name of speaker A as it appears in script (e.g., "Elon Musk")
        speaker_b_name: Name of speaker B as it appears in script (e.g., "Sam Altman")
        speaker_a_image: Reference photo for speaker A (enables edit mode for face preservation)
        speaker_b_image: Reference photo for speaker B (enables edit mode for face preservation)
        character_a_desc: Visual description of speaker A for image generation (ignored if speaker_a_image provided)
        character_b_desc: Visual description of speaker B for image generation (ignored if speaker_b_image provided)
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
    # Use edit mode (Image Edit API) if reference photos provided, otherwise use generation mode
    use_reference_photos = speaker_a_image and speaker_b_image

    # Build theme string for video generation (used by Runway)
    theme = f"{video_style} style, {location}"

    if use_reference_photos:
        status_messages.append("Generating storyboards from reference photos (Edit API)...")
        storyboard_images, img_status = edit_all_storyboards(
            segments=segments,
            video_style=video_style,
            location=location,
            speaker_a_image=speaker_a_image,
            speaker_b_image=speaker_b_image,
        )
    else:
        status_messages.append("Generating storyboard images with Grok...")
        storyboard_images, img_status = generate_all_storyboards(
            segments=segments,
            video_style=video_style,
            location=location,
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
    video_style: str,
    location: str,
    character_a_desc: str = "intense male rapper in streetwear",
    character_b_desc: str = "confident female rapper in urban fashion",
    speaker_a_image: str | None = None,
    speaker_b_image: str | None = None,
) -> tuple[list[str], list[str]]:
    """
    Run only the storyboard image generation (no video/audio).

    Useful for quick previews.

    Args:
        script: The rap battle script
        video_style: Visual style (Photorealistic, Pixar, Anime, etc.)
        location: Scene location (underground club, rooftop, etc.)
        character_a_desc: Visual description for speaker A (ignored if speaker_a_image provided)
        character_b_desc: Visual description for speaker B (ignored if speaker_b_image provided)
        speaker_a_image: Reference photo for speaker A (enables edit mode)
        speaker_b_image: Reference photo for speaker B (enables edit mode)

    Returns:
        Tuple of (image_paths, status_messages)
    """
    status_messages = []

    segments = parse_rap_script(script)
    segments = ensure_five_segments(segments)
    status_messages.append(f"Parsed {len(segments)} segments")

    # Use edit mode if reference photos provided
    use_reference_photos = speaker_a_image and speaker_b_image

    if use_reference_photos:
        status_messages.append("Using reference photos (Edit API)...")
        storyboard_images, img_status = edit_all_storyboards(
            segments=segments,
            video_style=video_style,
            location=location,
            speaker_a_image=speaker_a_image,
            speaker_b_image=speaker_b_image,
        )
    else:
        # For non-reference photo mode, pass individual style parameters
        storyboard_images, img_status = generate_all_storyboards(
            segments=segments,
            video_style=video_style,
            location=location,
            character_a_desc=character_a_desc,
            character_b_desc=character_b_desc,
        )
    status_messages.append(img_status)

    return storyboard_images, status_messages


# ============================================================================
# Audio Extraction Functions (for 6-shot structure)
# ============================================================================

OUTPUTS_DIR = Path("outputs")


def extract_beat_intro(beat_path: str, duration: float = 5.0) -> tuple[str | None, str]:
    """
    Extract the first N seconds of beat for the opening shot.

    Args:
        beat_path: Path to the beat audio file
        duration: Duration in seconds to extract

    Returns:
        Tuple of (extracted_path, status_message)
    """
    try:
        audio = AudioSegment.from_file(beat_path)
        intro = audio[: int(duration * 1000)]  # pydub works in milliseconds

        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUTS_DIR / "beat_intro.mp3"
        intro.export(str(output_path), format="mp3")

        return str(output_path), f"Extracted {duration}s intro from beat"
    except Exception as e:
        return None, f"Error extracting beat intro: {e}"


def extract_beat_outro(beat_path: str, duration: float = 5.0) -> tuple[str | None, str]:
    """
    Extract the last N seconds of beat for the closing shot.

    Args:
        beat_path: Path to the beat audio file
        duration: Duration in seconds to extract

    Returns:
        Tuple of (extracted_path, status_message)
    """
    try:
        audio = AudioSegment.from_file(beat_path)
        outro = audio[-int(duration * 1000):]  # Last N seconds

        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUTS_DIR / "beat_outro.mp3"
        outro.export(str(output_path), format="mp3")

        return str(output_path), f"Extracted {duration}s outro from beat"
    except Exception as e:
        return None, f"Error extracting beat outro: {e}"


def get_audio_duration(audio_path: str) -> float:
    """Get the duration of an audio file in seconds."""
    try:
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0  # Convert ms to seconds
    except Exception:
        return 10.0  # Default duration if we can't read the file


# ============================================================================
# 6-Shot Pipeline
# ============================================================================


@dataclass
class SixShotPipelineResult:
    """Result of the 6-shot storyboard pipeline."""
    success: bool
    shots: list[StoryboardShot]
    environment_image: str | None
    storyboard_images: list[str]
    video_segments: list[str]
    final_video: str | None
    status_messages: list[str] = field(default_factory=list)


def run_6shot_pipeline(
    script: str,
    video_style: str,
    location: str,
    audio_clips: list[str],
    beat_path: str | None = None,
    speaker_a_name: str = "",
    speaker_b_name: str = "",
    speaker_a_image: str | None = None,
    speaker_b_image: str | None = None,
    character_a_desc: str = "intense male rapper in streetwear, hood up, gold chains",
    character_b_desc: str = "confident female rapper in urban fashion, braids, bold makeup",
    generate_env_reference: bool = True,
    enable_lipsync: bool = True,
    intro_duration: float = 5.0,
    outro_duration: float = 5.0,
) -> SixShotPipelineResult:
    """
    Run the 6-shot storyboard pipeline.

    Creates 6 videos:
    - Shot 0: Opening (panning crowd, both characters)
    - Shots 1-4: 4 verses with lip sync
    - Shot 5: Closing (finale)

    Args:
        script: The rap battle script with speaker markers
        video_style: Visual style (Photorealistic, Pixar, Anime, etc.)
        location: Scene location (underground club, rooftop, etc.)
        audio_clips: List of 4 verse audio files
        beat_path: Path to the beat/instrumental track
        speaker_a_name: Name of speaker A as it appears in script
        speaker_b_name: Name of speaker B as it appears in script
        speaker_a_image: Reference photo for speaker A
        speaker_b_image: Reference photo for speaker B
        character_a_desc: Visual description of speaker A
        character_b_desc: Visual description of speaker B
        generate_env_reference: Whether to generate environment reference image
        enable_lipsync: Whether to use Act-Two for lip sync
        intro_duration: Duration of opening shot in seconds
        outro_duration: Duration of closing shot in seconds

    Returns:
        SixShotPipelineResult with all outputs
    """
    status_messages = []

    # Validate audio clips - need exactly 4 for verses
    if len(audio_clips) != 4:
        status_messages.append(f"Error: Expected 4 audio clips for verses, got {len(audio_clips)}")
        return SixShotPipelineResult(
            success=False,
            shots=[],
            environment_image=None,
            storyboard_images=[],
            video_segments=[],
            final_video=None,
            status_messages=status_messages,
        )

    # Step 1: Parse the script
    status_messages.append("Parsing rap script...")
    segments = parse_rap_script(script, speaker_a_name, speaker_b_name)

    # Ensure we have at least 4 segments for the 4 verses
    while len(segments) < 4:
        idx = len(segments)
        expected = [Speaker.PERSON_A, Speaker.PERSON_B, Speaker.PERSON_A, Speaker.PERSON_B]
        segments.append(BattleSegment(
            index=idx,
            speaker=expected[idx] if idx < 4 else Speaker.BOTH,
            verses=["..."],
            raw_text="...",
            is_conclusion=False,
        ))

    status_messages.append(f"Parsed {len(segments)} segments")

    # Step 2: Create 6-shot structure
    shots = create_storyboard_shots(segments[:4])  # Use first 4 segments for verses
    status_messages.append("Created 6-shot storyboard structure")

    # Step 3: Generate environment reference image (optional)
    environment_image = None
    if generate_env_reference:
        status_messages.append("Generating environment reference image...")
        environment_image, env_status = generate_environment_reference(
            location=location,
            video_style=video_style,
        )
        status_messages.append(env_status)

    # Step 4: Generate 6 storyboard images
    status_messages.append("Generating 6 storyboard images...")
    storyboard_images = []

    # Use reference photos if provided
    use_reference_photos = speaker_a_image and speaker_b_image

    for shot in shots:
        # Determine character description/image for this shot
        if shot.primary_speaker == Speaker.PERSON_A:
            char_desc = character_a_desc
            ref_image = speaker_a_image
        elif shot.primary_speaker == Speaker.PERSON_B:
            char_desc = character_b_desc
            ref_image = speaker_b_image
        else:  # BOTH
            char_desc = f"{character_a_desc} and {character_b_desc}"
            ref_image = speaker_a_image  # Use A for both shots

        # Create segment for this shot
        shot_segment = BattleSegment(
            index=shot.index,
            speaker=shot.primary_speaker,
            verses=[shot.verse_text] if shot.verse_text else ["..."],
            raw_text=shot.verse_text or "...",
            is_conclusion=(shot.shot_type == ShotType.CLOSING),
        )

        # Generate image
        if use_reference_photos and ref_image:
            from app_gradio_fastapi.services.grok_image_api import edit_storyboard_image, build_edit_prompt
            prompt = build_edit_prompt(shot_segment, video_style, location, char_desc)
            img_path, img_status = edit_storyboard_image(ref_image, prompt)
        else:
            from app_gradio_fastapi.services.grok_image_api import generate_storyboard_image, build_storyboard_prompt
            prompt = build_storyboard_prompt(shot_segment, video_style, location, char_desc, char_desc)
            img_path, img_status = generate_storyboard_image(prompt)

        if img_path is None:
            status_messages.append(f"Failed at shot {shot.index}: {img_status}")
            return SixShotPipelineResult(
                success=False,
                shots=shots,
                environment_image=environment_image,
                storyboard_images=storyboard_images,
                video_segments=[],
                final_video=None,
                status_messages=status_messages,
            )
        storyboard_images.append(img_path)

    status_messages.append(f"Generated {len(storyboard_images)} storyboard images")

    # Step 5: Extract intro/outro from beat
    intro_audio = None
    outro_audio = None
    if beat_path:
        status_messages.append("Extracting intro/outro from beat track...")
        intro_audio, intro_status = extract_beat_intro(beat_path, intro_duration)
        status_messages.append(intro_status)
        outro_audio, outro_status = extract_beat_outro(beat_path, outro_duration)
        status_messages.append(outro_status)

    # Step 6: Generate 6 videos with lip sync
    status_messages.append("Generating videos with Runway...")

    # Build theme and speakers lists
    theme = f"{video_style} style, {location}"
    speakers = [shot.primary_speaker.value for shot in shots]
    verse_contexts = [shot.verse_text for shot in shots]

    video_segments, vid_status = generate_6shot_videos(
        image_paths=storyboard_images,
        theme=theme,
        speakers=speakers,
        verse_contexts=verse_contexts,
        audio_paths=audio_clips,  # 4 verse audios for shots 1-4
        duration=10,  # Default duration, will be adjusted by audio
        enable_lipsync=enable_lipsync,
        environment_ref=environment_image,  # Pass environment reference for style consistency
    )
    status_messages.append(vid_status)

    if len(video_segments) != 6:
        return SixShotPipelineResult(
            success=False,
            shots=shots,
            environment_image=environment_image,
            storyboard_images=storyboard_images,
            video_segments=video_segments,
            final_video=None,
            status_messages=status_messages,
        )

    # Step 7: Compose final video with audio
    status_messages.append("Composing final video...")

    # Build audio list: intro + 4 verses + outro
    all_audio = []
    if intro_audio:
        all_audio.append(intro_audio)
    else:
        # Use first 5 seconds of first verse as fallback intro
        all_audio.append(audio_clips[0])
    all_audio.extend(audio_clips)  # 4 verse audios
    if outro_audio:
        all_audio.append(outro_audio)
    else:
        # Use last 5 seconds of last verse as fallback outro
        all_audio.append(audio_clips[-1])

    final_video, compose_status = compose_with_audio_clips(
        video_paths=video_segments,
        audio_clips=all_audio,
        beat_path=beat_path,
    )
    status_messages.append(compose_status)

    return SixShotPipelineResult(
        success=(final_video is not None),
        shots=shots,
        environment_image=environment_image,
        storyboard_images=storyboard_images,
        video_segments=video_segments,
        final_video=final_video,
        status_messages=status_messages,
    )
