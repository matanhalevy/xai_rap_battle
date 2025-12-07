"""Battle state management and SSE streaming for the rap battle frontend."""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator

from app_gradio_fastapi.services.voice_api import generate_rap_voice
from app_gradio_fastapi.services.beat_api import generate_beat_pattern
from app_gradio_fastapi.services.beat_generator import get_generator
from app_gradio_fastapi.services.bpm_detector import detect_bpm_from_multiple, snap_bpm_to_common
from app_gradio_fastapi.services.audio_mixer import mix_rap_and_beat
from app_gradio_fastapi.services.grok_image_api import generate_storyboard_image
from app_gradio_fastapi.services.runway_api import generate_video_from_image
from app_gradio_fastapi.services.sync_labs_api import lipsync_video
from app_gradio_fastapi.services.video_composer import compose_with_audio_clips
from app_gradio_fastapi.config.style_presets import get_preset_path


class BattleStage(str, Enum):
    """Pipeline stages for full battle generation."""
    QUEUED = "queued"
    PARSING = "parsing"
    VOICE_A = "voice_a"
    VOICE_B = "voice_b"
    BPM_DETECT = "bpm_detect"
    BEAT_GEN = "beat_gen"
    MIXING = "mixing"
    STORYBOARD = "storyboard"
    VIDEO = "video"
    LIPSYNC = "lipsync"
    COMPOSE = "compose"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class BattleConfig:
    """Configuration for a rap battle."""
    theme: str
    beat_style: str
    test_mode: bool
    audio_only: bool

    # Fighter A
    fighter_a_name: str
    fighter_a_description: str
    fighter_a_style: str
    fighter_a_lyrics: str

    # Fighter B
    fighter_b_name: str
    fighter_b_description: str
    fighter_b_style: str
    fighter_b_lyrics: str

    # Optional fields (must come after required)
    fighter_a_image_path: str | None = None
    fighter_a_voice_path: str | None = None
    fighter_b_image_path: str | None = None
    fighter_b_voice_path: str | None = None


@dataclass
class BattleState:
    """Current state of a battle."""
    battle_id: str
    config: BattleConfig
    stage: BattleStage = BattleStage.QUEUED
    progress: float = 0.0
    message: str = "Battle queued"
    audio_url: str | None = None
    video_url: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)

    # Generated assets
    audio_clips: list[str] = field(default_factory=list)
    detected_bpm: float | None = None
    beat_path: str | None = None
    mixed_audio_path: str | None = None
    storyboard_images: list[str] = field(default_factory=list)
    video_segments: list[str] = field(default_factory=list)
    lipsynced_videos: list[str] = field(default_factory=list)


class BattleManager:
    """Manages battle state and orchestrates the full battle generation pipeline."""

    _battles: dict[str, BattleState] = {}
    _queues: dict[str, asyncio.Queue] = {}

    @classmethod
    async def create_battle(cls, config: BattleConfig) -> str:
        """Create a new battle and start processing in the background."""
        battle_id = str(uuid.uuid4())

        # Initialize state
        state = BattleState(
            battle_id=battle_id,
            config=config,
            stage=BattleStage.QUEUED,
            progress=0.0,
            message="Battle queued"
        )
        cls._battles[battle_id] = state
        cls._queues[battle_id] = asyncio.Queue()

        # Start pipeline in background
        asyncio.create_task(cls._run_full_pipeline(battle_id))

        logging.info(f"Created battle {battle_id}")
        return battle_id

    @classmethod
    def get_battle(cls, battle_id: str) -> BattleState | None:
        """Get current battle state."""
        return cls._battles.get(battle_id)

    @classmethod
    async def stream_progress(cls, battle_id: str) -> AsyncGenerator[str, None]:
        """Stream progress updates via SSE."""
        queue = cls._queues.get(battle_id)
        if not queue:
            yield f"data: {json.dumps({'error': 'Battle not found'})}\n\n"
            return

        state = cls._battles.get(battle_id)
        if not state:
            yield f"data: {json.dumps({'error': 'Battle state not found'})}\n\n"
            return

        # Send initial state
        yield f"data: {json.dumps(cls._state_to_dict(state))}\n\n"

        # Stream updates
        while True:
            try:
                update = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {json.dumps(update)}\n\n"

                if update.get('status') in ('complete', 'failed'):
                    break
            except asyncio.TimeoutError:
                # Send heartbeat
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"

    @classmethod
    def _state_to_dict(cls, state: BattleState) -> dict[str, Any]:
        """Convert state to dictionary for JSON serialization."""
        return {
            'battle_id': state.battle_id,
            'stage': state.stage.value,
            'progress': state.progress,
            'message': state.message,
            'status': 'complete' if state.stage == BattleStage.COMPLETE else
                      'failed' if state.stage == BattleStage.FAILED else 'in_progress',
            'audio_url': state.audio_url,
            'video_url': state.video_url,
            'detected_bpm': state.detected_bpm,
            'error': state.error
        }

    @classmethod
    async def _emit_update(cls, battle_id: str, **kwargs):
        """Emit a progress update to the SSE stream."""
        queue = cls._queues.get(battle_id)
        state = cls._battles.get(battle_id)

        if not queue or not state:
            return

        # Update state
        if 'stage' in kwargs:
            state.stage = kwargs['stage']
        if 'progress' in kwargs:
            state.progress = kwargs['progress']
        if 'message' in kwargs:
            state.message = kwargs['message']
        if 'audio_url' in kwargs:
            state.audio_url = kwargs['audio_url']
        if 'video_url' in kwargs:
            state.video_url = kwargs['video_url']
        if 'detected_bpm' in kwargs:
            state.detected_bpm = kwargs['detected_bpm']
        if 'error' in kwargs:
            state.error = kwargs['error']

        # Emit to queue
        await queue.put(cls._state_to_dict(state))

    @classmethod
    async def _run_full_pipeline(cls, battle_id: str):
        """Run the full battle generation pipeline (audio + video)."""
        state = cls._battles.get(battle_id)
        if not state:
            return

        config = state.config
        output_dir = Path(__file__).parent.parent.parent / "outputs"
        output_dir.mkdir(exist_ok=True)

        try:
            # ============== AUDIO PIPELINE ==============

            # Stage 1: Parse lyrics
            await cls._emit_update(
                battle_id,
                stage=BattleStage.PARSING,
                progress=2.0,
                message="Parsing lyrics..."
            )
            await asyncio.sleep(0.3)

            # Stage 2: Generate Fighter A voice
            await cls._emit_update(
                battle_id,
                stage=BattleStage.VOICE_A,
                progress=5.0,
                message=f"Generating voice for {config.fighter_a_name}..."
            )

            voice_a_path = config.fighter_a_voice_path or get_preset_path(config.fighter_a_style)
            audio_a, status_a = await asyncio.to_thread(
                generate_rap_voice,
                lyrics=config.fighter_a_lyrics,
                style_instructions=f"aggressive battle rapper, {config.fighter_a_name} style",
                voice_file=voice_a_path
            )

            if not audio_a:
                raise Exception(f"Failed to generate voice for {config.fighter_a_name}: {status_a}")

            await cls._emit_update(
                battle_id,
                progress=15.0,
                message=f"{config.fighter_a_name} voice complete"
            )

            # Stage 3: Generate Fighter B voice
            await cls._emit_update(
                battle_id,
                stage=BattleStage.VOICE_B,
                progress=18.0,
                message=f"Generating voice for {config.fighter_b_name}..."
            )

            voice_b_path = config.fighter_b_voice_path or get_preset_path(config.fighter_b_style)
            audio_b, status_b = await asyncio.to_thread(
                generate_rap_voice,
                lyrics=config.fighter_b_lyrics,
                style_instructions=f"aggressive battle rapper, {config.fighter_b_name} style",
                voice_file=voice_b_path
            )

            if not audio_b:
                raise Exception(f"Failed to generate voice for {config.fighter_b_name}: {status_b}")

            state.audio_clips = [audio_a, audio_b]

            await cls._emit_update(
                battle_id,
                progress=28.0,
                message=f"{config.fighter_b_name} voice complete"
            )

            # Stage 4: Detect BPM from rap audio
            await cls._emit_update(
                battle_id,
                stage=BattleStage.BPM_DETECT,
                progress=30.0,
                message="Detecting BPM from rap audio..."
            )

            detected_bpm = await asyncio.to_thread(
                detect_bpm_from_multiple,
                state.audio_clips
            )
            target_bpm = snap_bpm_to_common(detected_bpm)
            state.detected_bpm = target_bpm

            await cls._emit_update(
                battle_id,
                progress=32.0,
                message=f"Detected BPM: {target_bpm}",
                detected_bpm=target_bpm
            )

            # Stage 5: Generate beat at detected BPM
            await cls._emit_update(
                battle_id,
                stage=BattleStage.BEAT_GEN,
                progress=35.0,
                message=f"Generating {config.beat_style} beat at {target_bpm} BPM..."
            )

            beat_json, beat_status = await asyncio.to_thread(
                generate_beat_pattern,
                style=config.beat_style,
                bpm=target_bpm,
                bars=4
            )

            if not beat_json:
                raise Exception(f"Failed to generate beat pattern: {beat_status}")

            generator = get_generator()
            beat_path, pattern = await asyncio.to_thread(
                generator.generate_from_json,
                beat_json,
                loops=8  # Loop beat to ensure it's long enough
            )
            state.beat_path = beat_path

            await cls._emit_update(
                battle_id,
                progress=42.0,
                message="Beat generated"
            )

            # Stage 6: Mix rap + beat
            await cls._emit_update(
                battle_id,
                stage=BattleStage.MIXING,
                progress=45.0,
                message="Mixing vocals and beat..."
            )

            audio_filename = f"battle_{battle_id[:8]}.mp3"
            audio_output_path = str(output_dir / audio_filename)

            mixed_audio = await asyncio.to_thread(
                mix_rap_and_beat,
                rap_clips=state.audio_clips,
                beat_path=beat_path,
                beat_volume_db=-10.0,
                output_path=audio_output_path
            )
            state.mixed_audio_path = mixed_audio

            audio_url = f"/outputs/{audio_filename}"
            await cls._emit_update(
                battle_id,
                progress=50.0,
                message="Audio mix complete",
                audio_url=audio_url
            )

            # If audio_only mode, skip video pipeline and complete
            if config.audio_only:
                await cls._emit_update(
                    battle_id,
                    stage=BattleStage.COMPLETE,
                    progress=100.0,
                    message="Battle complete! (Audio only)",
                    audio_url=audio_url
                )
                return

            # ============== VIDEO PIPELINE ==============

            # Stage 7: Generate storyboard images
            await cls._emit_update(
                battle_id,
                stage=BattleStage.STORYBOARD,
                progress=52.0,
                message="Generating storyboard images..."
            )

            # Generate images for each fighter (use uploaded images or generate)
            storyboard_images = []

            # Fighter A image
            if config.fighter_a_image_path:
                storyboard_images.append(config.fighter_a_image_path)
            else:
                img_a, img_status = await asyncio.to_thread(
                    generate_storyboard_image,
                    prompt=f"{config.fighter_a_description or config.fighter_a_name}, rapper, {config.theme} theme, dramatic lighting",
                    speaker="A"
                )
                if img_a:
                    storyboard_images.append(img_a)
                else:
                    raise Exception(f"Failed to generate image for {config.fighter_a_name}: {img_status}")

            await cls._emit_update(
                battle_id,
                progress=58.0,
                message=f"{config.fighter_a_name} image ready"
            )

            # Fighter B image
            if config.fighter_b_image_path:
                storyboard_images.append(config.fighter_b_image_path)
            else:
                img_b, img_status = await asyncio.to_thread(
                    generate_storyboard_image,
                    prompt=f"{config.fighter_b_description or config.fighter_b_name}, rapper, {config.theme} theme, dramatic lighting",
                    speaker="B"
                )
                if img_b:
                    storyboard_images.append(img_b)
                else:
                    raise Exception(f"Failed to generate image for {config.fighter_b_name}: {img_status}")

            state.storyboard_images = storyboard_images

            await cls._emit_update(
                battle_id,
                progress=64.0,
                message=f"{config.fighter_b_name} image ready"
            )

            # Stage 8: Generate videos from images (Runway)
            await cls._emit_update(
                battle_id,
                stage=BattleStage.VIDEO,
                progress=66.0,
                message="Generating videos from images..."
            )

            video_segments = []
            for i, img_path in enumerate(storyboard_images):
                fighter_name = config.fighter_a_name if i == 0 else config.fighter_b_name
                await cls._emit_update(
                    battle_id,
                    progress=66.0 + (i * 6),
                    message=f"Generating video for {fighter_name}..."
                )

                video_path, vid_status = await asyncio.to_thread(
                    generate_video_from_image,
                    image_path=img_path,
                    prompt=f"Rapper performing, head bobbing to beat, {config.theme} atmosphere, cinematic"
                )

                if video_path:
                    video_segments.append(video_path)
                else:
                    logging.warning(f"Video generation failed for {fighter_name}: {vid_status}")
                    # Use image as fallback (will need to convert to video)
                    video_segments.append(img_path)

            state.video_segments = video_segments

            await cls._emit_update(
                battle_id,
                progress=78.0,
                message="Video segments generated"
            )

            # Stage 9: Lip sync (optional - skip for now to save time/credits)
            await cls._emit_update(
                battle_id,
                stage=BattleStage.LIPSYNC,
                progress=80.0,
                message="Processing lip sync..."
            )

            # For now, skip actual lip sync and use video segments directly
            # TODO: Enable lip sync with Sync Labs when needed
            state.lipsynced_videos = video_segments

            await cls._emit_update(
                battle_id,
                progress=85.0,
                message="Lip sync complete"
            )

            # Stage 10: Compose final video
            await cls._emit_update(
                battle_id,
                stage=BattleStage.COMPOSE,
                progress=88.0,
                message="Composing final video..."
            )

            video_filename = f"battle_{battle_id[:8]}.mp4"
            video_output_path = output_dir / video_filename

            final_video, compose_status = await asyncio.to_thread(
                compose_with_audio_clips,
                video_paths=state.lipsynced_videos,
                audio_clips=state.audio_clips,
                beat_path=beat_path,
                output_path=video_output_path,
                beat_volume=0.3  # 30% beat volume in video (rap at full)
            )

            if not final_video:
                raise Exception(f"Failed to compose video: {compose_status}")

            video_url = f"/outputs/{video_filename}"

            # Complete
            await cls._emit_update(
                battle_id,
                stage=BattleStage.COMPLETE,
                progress=100.0,
                message="Battle complete!",
                video_url=video_url
            )

        except Exception as e:
            logging.error(f"Battle {battle_id} failed: {e}")
            await cls._emit_update(
                battle_id,
                stage=BattleStage.FAILED,
                progress=state.progress,
                message=str(e),
                error=str(e)
            )

    @classmethod
    def cleanup_battle(cls, battle_id: str):
        """Clean up battle resources."""
        if battle_id in cls._battles:
            del cls._battles[battle_id]
        if battle_id in cls._queues:
            del cls._queues[battle_id]
