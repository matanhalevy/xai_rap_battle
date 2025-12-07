"""
Video composer for combining video segments with audio.
Uses moviepy for video editing operations.
"""

from pathlib import Path
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
)

OUTPUTS_DIR = Path("outputs/final")


def parse_segment_timings(timing_str: str) -> list[float]:
    """
    Parse segment timing string into list of durations.

    Format: "10,15,12,18,5" (duration in seconds for each segment)
    Or: "0:10,0:25,0:37,0:55,1:00" (end timestamps)

    Returns list of durations in seconds.
    """
    if not timing_str.strip():
        return []

    parts = [p.strip() for p in timing_str.split(",")]
    durations = []

    # Check if using timestamp format (contains ":")
    if ":" in parts[0]:
        # Timestamp format - convert to durations
        prev_time = 0
        for part in parts:
            mins, secs = part.split(":")
            total_secs = int(mins) * 60 + float(secs)
            durations.append(total_secs - prev_time)
            prev_time = total_secs
    else:
        # Direct duration format
        durations = [float(p) for p in parts]

    return durations


def trim_or_loop_video(clip: VideoFileClip, target_duration: float) -> VideoFileClip:
    """
    Adjust video clip to match target duration.

    If video is shorter, loop it. If longer, trim it.
    """
    current_duration = clip.duration

    if abs(current_duration - target_duration) < 0.1:
        return clip

    if current_duration > target_duration:
        # Trim
        return clip.subclip(0, target_duration)
    else:
        # Loop to fill duration
        loops_needed = int(target_duration / current_duration) + 1
        looped = concatenate_videoclips([clip] * loops_needed)
        return looped.subclip(0, target_duration)


def compose_battle_video(
    video_paths: list[str],
    audio_path: str,
    output_path: Path | None = None,
    crossfade_duration: float = 0.5,
    segment_durations: list[float] | None = None,
) -> tuple[str | None, str]:
    """
    Compose the final battle video from segments with audio overlay.

    Args:
        video_paths: List of video segment paths (5 videos)
        audio_path: Path to the MP3 audio file
        output_path: Where to save the final video
        crossfade_duration: Duration of crossfade between segments
        segment_durations: Optional list of target durations for each segment

    Returns:
        Tuple of (final_video_path, status_message)
    """
    if not video_paths:
        return None, "Error: No video paths provided"

    if output_path is None:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUTS_DIR / "rap_battle_final.mp4"

    clips = []
    try:
        # Load all video clips
        for i, path in enumerate(video_paths):
            clip = VideoFileClip(path)

            # Adjust duration if specified
            if segment_durations and i < len(segment_durations):
                target_duration = segment_durations[i]
                clip = trim_or_loop_video(clip, target_duration)

            clips.append(clip)

        # Concatenate with crossfade
        if crossfade_duration > 0 and len(clips) > 1:
            final_video = concatenate_videoclips(
                clips,
                method="compose",
                padding=-crossfade_duration,
            )
        else:
            final_video = concatenate_videoclips(clips)

        # Load and set audio
        audio = AudioFileClip(audio_path)

        # Match video duration to audio or vice versa
        video_duration = final_video.duration
        audio_duration = audio.duration

        if audio_duration > video_duration:
            # Trim audio to match video
            audio = audio.subclipped(0, video_duration)
        elif video_duration > audio_duration:
            # Video is longer - we could loop audio or leave silence
            # For now, keep as is (silence at end)
            pass

        # Set the audio
        final_video = final_video.with_audio(audio)

        # Export
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset="medium",
            threads=4,
        )

        return str(output_path), f"Final video created: {output_path}"

    except Exception as e:
        return None, f"Error composing video: {e}"

    finally:
        # Clean up clips
        for clip in clips:
            try:
                clip.close()
            except:
                pass


def compose_with_continuous_beat(
    lipsynced_video_paths: list[str],
    beat_path: str,
    output_path: Path | None = None,
    crossfade_duration: float = 0.3,
    beat_volume: float = 0.7,
) -> tuple[str | None, str]:
    """
    Compose lip-synced video segments with a continuous beat track underneath.

    The lip-synced videos already have vocals; we add the beat track
    at a lower volume to create the final mix.

    Args:
        lipsynced_video_paths: List of lip-synced video paths (each has vocals)
        beat_path: Path to the continuous beat/instrumental track
        output_path: Where to save the final video
        crossfade_duration: Duration of crossfade between segments
        beat_volume: Volume level for beat (0.0-1.0), vocals stay at 1.0

    Returns:
        Tuple of (final_video_path, status_message)
    """
    from moviepy import CompositeAudioClip

    if not lipsynced_video_paths:
        return None, "Error: No video paths provided"

    if output_path is None:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUTS_DIR / "rap_battle_final.mp4"

    clips = []
    try:
        # Load all lip-synced video clips
        for path in lipsynced_video_paths:
            clip = VideoFileClip(path)
            clips.append(clip)

        # Concatenate videos with crossfade
        if crossfade_duration > 0 and len(clips) > 1:
            final_video = concatenate_videoclips(
                clips,
                method="compose",
                padding=-crossfade_duration,
            )
        else:
            final_video = concatenate_videoclips(clips)

        video_duration = final_video.duration

        # Get the vocal audio from the concatenated video
        vocal_audio = final_video.audio

        # Load the continuous beat track
        beat_audio = AudioFileClip(beat_path)

        # Trim or loop beat to match video duration
        if beat_audio.duration < video_duration:
            # Loop the beat
            loops_needed = int(video_duration / beat_audio.duration) + 1
            beat_clips = [beat_audio] * loops_needed
            beat_audio = concatenate_videoclips(beat_clips)  # This works for audio too
        beat_audio = beat_audio.subclipped(0, video_duration)

        # Adjust beat volume
        beat_audio = beat_audio.with_volume_scaled(beat_volume)

        # Mix vocal audio with beat
        if vocal_audio:
            mixed_audio = CompositeAudioClip([vocal_audio, beat_audio])
        else:
            mixed_audio = beat_audio

        # Set the mixed audio on the video
        final_video = final_video.with_audio(mixed_audio)

        # Export
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset="medium",
            threads=4,
        )

        return str(output_path), f"Final video with continuous beat: {output_path}"

    except Exception as e:
        return None, f"Error composing video: {e}"

    finally:
        for clip in clips:
            try:
                clip.close()
            except:
                pass


def compose_with_audio_clips(
    video_paths: list[str],
    audio_clips: list[str],
    beat_path: str | None = None,
    output_path: Path | None = None,
    video_crossfade: float = 0.0,
    beat_volume: float = 0.6,
) -> tuple[str | None, str]:
    """
    Compose 5 video segments with 4 audio clips + optional continuous beat.

    IMPORTANT: Audio clips are assumed to be perfectly beat-synced with no gaps.
    They will be concatenated seamlessly with NO crossfade or gaps.
    Videos will be adjusted to match exact audio durations.

    Args:
        video_paths: List of 5 video segment paths
        audio_clips: List of 4 audio clips (one per battle turn, beat-synced)
        beat_path: Optional separate beat track (if vocals are isolated)
        output_path: Where to save the final video
        video_crossfade: Visual crossfade between video segments (0 = hard cut)
        beat_volume: Volume level for separate beat track (0.0-1.0)

    Returns:
        Tuple of (final_video_path, status_message)
    """
    from moviepy import CompositeAudioClip, concatenate_audioclips

    if len(video_paths) != 5:
        return None, f"Error: Expected 5 videos, got {len(video_paths)}"
    if len(audio_clips) != 4:
        return None, f"Error: Expected 4 audio clips, got {len(audio_clips)}"

    if output_path is None:
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUTS_DIR / "rap_battle_final.mp4"

    video_clips = []
    loaded_audio = []

    try:
        # Step 1: Load all audio clips first to get exact durations
        audio_durations = []
        for audio_path in audio_clips:
            audio = AudioFileClip(audio_path)
            loaded_audio.append(audio)
            audio_durations.append(audio.duration)

        # Step 2: Concatenate audio clips seamlessly (NO gaps, NO crossfade)
        # This preserves the perfect beat sync
        combined_audio = concatenate_audioclips(loaded_audio)
        total_audio_duration = combined_audio.duration

        # Step 3: Load and adjust video clips to match audio durations exactly
        for i, video_path in enumerate(video_paths):
            video = VideoFileClip(video_path)

            if i < 4:
                # Match video to exact audio duration
                target_duration = audio_durations[i]
                video = trim_or_loop_video(video, target_duration)
            else:
                # 5th video (conclusion) - use a reasonable duration
                # Default to 5 seconds or keep original if shorter
                conclusion_duration = min(video.duration, 5.0)
                video = trim_or_loop_video(video, conclusion_duration)

            video_clips.append(video)

        # Step 4: Concatenate videos
        # Use hard cuts (no crossfade) to stay in sync with audio
        if video_crossfade > 0:
            final_video = concatenate_videoclips(
                video_clips,
                method="compose",
                padding=-video_crossfade,
            )
        else:
            # Hard cuts - perfect sync with audio
            final_video = concatenate_videoclips(video_clips, method="chain")

        # Step 5: Set the combined audio on the video
        # Trim or extend to match video duration
        video_duration = final_video.duration

        if combined_audio.duration < video_duration:
            # Audio is shorter (conclusion has no audio) - that's fine
            # Pad with silence or just let it end
            pass
        elif combined_audio.duration > video_duration:
            # Trim audio to match video
            combined_audio = combined_audio.subclipped(0, video_duration)

        # Step 6: If separate beat track provided, mix it underneath
        if beat_path:
            beat_audio = AudioFileClip(beat_path)

            # Loop beat to match video duration
            if beat_audio.duration < video_duration:
                loops_needed = int(video_duration / beat_audio.duration) + 1
                beat_segments = [AudioFileClip(beat_path) for _ in range(loops_needed)]
                beat_audio = concatenate_audioclips(beat_segments)
            beat_audio = beat_audio.subclipped(0, video_duration)

            # Adjust beat volume
            beat_audio = beat_audio.with_volume_scaled(beat_volume)

            # Mix vocals + beat
            mixed_audio = CompositeAudioClip([combined_audio, beat_audio])
            final_video = final_video.with_audio(mixed_audio)
        else:
            # Just use the combined audio clips (already has beat in them)
            final_video = final_video.with_audio(combined_audio)

        # Step 7: Export
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_video.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset="medium",
            threads=4,
        )

        return str(output_path), f"Final video created: {output_path} (total: {video_duration:.1f}s)"

    except Exception as e:
        return None, f"Error composing video: {e}"

    finally:
        for clip in video_clips:
            try:
                clip.close()
            except:
                pass
        for audio in loaded_audio:
            try:
                audio.close()
            except:
                pass


def split_audio_into_segments(
    audio_path: str,
    segment_durations: list[float],
    output_dir: Path | None = None,
) -> tuple[list[str], str]:
    """
    Split an audio file into segments based on durations.

    Args:
        audio_path: Path to the audio file
        segment_durations: List of durations for each segment
        output_dir: Directory to save segment files

    Returns:
        Tuple of (list of segment file paths, status message)
    """
    if output_dir is None:
        output_dir = OUTPUTS_DIR / "audio_segments"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        audio = AudioFileClip(audio_path)
        segment_paths = []
        current_time = 0

        for i, duration in enumerate(segment_durations):
            end_time = current_time + duration

            # Don't exceed audio length
            if current_time >= audio.duration:
                break

            end_time = min(end_time, audio.duration)
            segment = audio.subclipped(current_time, end_time)

            segment_path = output_dir / f"segment_{i}.mp3"
            segment.write_audiofile(str(segment_path))
            segment_paths.append(str(segment_path))

            current_time = end_time

        audio.close()
        return segment_paths, f"Split audio into {len(segment_paths)} segments"

    except Exception as e:
        return [], f"Error splitting audio: {e}"


def adjust_segment_durations(
    video_paths: list[str],
    audio_path: str,
    segment_timings: list[float] | None = None,
) -> tuple[list[str], str]:
    """
    Adjust video segment durations to match audio timing.

    Args:
        video_paths: List of video paths
        audio_path: Path to audio file
        segment_timings: Optional list of end times for each segment

    Returns:
        Tuple of (adjusted video paths, status)
    """
    if segment_timings is None:
        # Equal distribution across audio duration
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration
        audio.close()

        segment_duration = total_duration / len(video_paths)
        segment_timings = [segment_duration * (i + 1) for i in range(len(video_paths))]

    adjusted_paths = []
    prev_time = 0

    for i, (path, end_time) in enumerate(zip(video_paths, segment_timings)):
        duration = end_time - prev_time
        prev_time = end_time

        try:
            clip = VideoFileClip(path)
            original_duration = clip.duration

            if abs(original_duration - duration) > 0.1:
                # Need to adjust speed
                speed_factor = original_duration / duration
                adjusted_clip = clip.fx(lambda c: c.speedx(speed_factor))

                # Save adjusted clip
                adjusted_path = Path(path).parent / f"adjusted_{Path(path).name}"
                adjusted_clip.write_videofile(
                    str(adjusted_path),
                    codec="libx264",
                    fps=24,
                    preset="fast",
                )
                adjusted_paths.append(str(adjusted_path))
                adjusted_clip.close()
            else:
                adjusted_paths.append(path)

            clip.close()

        except Exception as e:
            return adjusted_paths, f"Error adjusting segment {i}: {e}"

    return adjusted_paths, "Segments adjusted successfully"


def add_title_card(
    video_path: str,
    title_text: str,
    duration: float = 3.0,
) -> tuple[str | None, str]:
    """
    Add a title card to the beginning of the video.

    Args:
        video_path: Path to the video
        title_text: Text to display
        duration: Duration of title card

    Returns:
        Tuple of (new video path, status)
    """
    try:
        from moviepy.editor import TextClip, ColorClip

        video = VideoFileClip(video_path)

        # Create title card
        title_bg = ColorClip(
            size=video.size,
            color=(0, 0, 0),
            duration=duration,
        )

        title = TextClip(
            title_text,
            fontsize=60,
            color="white",
            font="Arial-Bold",
            size=video.size,
            method="caption",
        ).set_duration(duration)

        title_card = CompositeVideoClip([title_bg, title.set_position("center")])

        # Concatenate
        final = concatenate_videoclips([title_card, video])

        output_path = Path(video_path).parent / f"titled_{Path(video_path).name}"
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            fps=24,
        )

        video.close()
        return str(output_path), "Title card added"

    except Exception as e:
        return None, f"Error adding title: {e}"
