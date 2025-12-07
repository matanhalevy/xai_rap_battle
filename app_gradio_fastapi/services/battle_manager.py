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
from app_gradio_fastapi.services.audio_mixer import mix_rap_and_beat, generate_waveform_data
from app_gradio_fastapi.services.lyric_aligner import align_battle_verses
from app_gradio_fastapi.services.runway_api import generate_video_from_image
from app_gradio_fastapi.services.sync_labs_api import lipsync_video, upload_to_temp_host
from app_gradio_fastapi.config.style_presets import get_preset_path, get_style_instructions
from app_gradio_fastapi.services.elevenlabs_api import create_style_reference


class BattleStage(str, Enum):
    """Pipeline stages for battle generation."""
    QUEUED = "queued"
    PARSING = "parsing"
    STYLE_REF_A = "style_ref_a"
    STYLE_REF_B = "style_ref_b"
    VOICE_A = "voice_a"
    VOICE_B = "voice_b"
    BPM_DETECT = "bpm_detect"
    BEAT_GEN = "beat_gen"
    MIXING = "mixing"
    TALKHEAD = "talkhead"        # Generate base videos (Runway) - parallel
    LIPSYNC_HEADS = "lipsync_heads"  # Apply lip sync (Sync Labs) - parallel
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class BattleConfig:
    """Configuration for a rap battle."""
    video_style: str
    location: str
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
    time_period: str = "present day"
    fighter_a_image_path: str | None = None
    fighter_a_voice_path: str | None = None
    fighter_b_image_path: str | None = None
    fighter_b_voice_path: str | None = None
    fighter_a_twitter: str | None = None
    fighter_b_twitter: str | None = None
    fighter_a_voice_recorded: bool = False  # True if recorded via REC, False if uploaded
    fighter_b_voice_recorded: bool = False  # True if recorded via REC, False if uploaded


@dataclass
class BattleState:
    """Current state of a battle."""
    battle_id: str
    config: BattleConfig
    stage: BattleStage = BattleStage.QUEUED
    progress: float = 0.0
    message: str = "Battle queued"
    audio_url: str | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.now)

    # Generated assets
    audio_clips: list[str] = field(default_factory=list)
    detected_bpm: float | None = None
    beat_path: str | None = None
    mixed_audio_path: str | None = None

    # Battle arena data
    timing_data: dict | None = None
    waveform: list[float] = field(default_factory=list)
    talking_head_a: str | None = None
    talking_head_b: str | None = None


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
        result = {
            'battle_id': state.battle_id,
            'stage': state.stage.value,
            'progress': state.progress,
            'message': state.message,
            'status': 'complete' if state.stage == BattleStage.COMPLETE else
                      'failed' if state.stage == BattleStage.FAILED else 'in_progress',
            'audio_url': state.audio_url,
            'detected_bpm': state.detected_bpm,
            'error': state.error
        }
        # Include arena data for audio-only battles
        if state.timing_data:
            result['timing_data'] = state.timing_data
        if state.waveform:
            result['waveform'] = state.waveform
        if state.talking_head_a:
            result['talking_head_a_url'] = f"/outputs/{Path(state.talking_head_a).name}"
        if state.talking_head_b:
            result['talking_head_b_url'] = f"/outputs/{Path(state.talking_head_b).name}"
        return result

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

            # Stage 2: Create Style Reference A (ElevenLabs voice + style transfer)
            await cls._emit_update(
                battle_id,
                stage=BattleStage.STYLE_REF_A,
                progress=4.0,
                message=f"Creating style reference for {config.fighter_a_name}..."
            )

            # Get voice identity (user's upload) and style source (preset clip)
            voice_identity_a = config.fighter_a_voice_path
            style_source_a = get_preset_path(config.fighter_a_style)

            if voice_identity_a and style_source_a:
                # Combine voice identity + style via ElevenLabs speech-to-speech
                # celebrity_mode=True pitch shifts to evade voice detection, then reverses after
                # BUT: disable celebrity_mode if user recorded their own voice (not a celebrity)
                use_celebrity_mode_a = not config.fighter_a_voice_recorded
                style_ref_a, voice_id_a, status_a = await asyncio.to_thread(
                    create_style_reference,
                    voice_identity_file=voice_identity_a,
                    style_source_file=style_source_a,
                    reference_name=f"{config.fighter_a_name}_style",
                    celebrity_mode=use_celebrity_mode_a,
                    stability=0.5,
                    similarity_boost=0.85,
                )
                if not style_ref_a:
                    logging.warning(f"Style transfer failed for {config.fighter_a_name}: {status_a}, falling back")
                    style_ref_a = voice_identity_a or style_source_a
            else:
                # Fallback: use whichever is available
                style_ref_a = voice_identity_a or style_source_a

            await cls._emit_update(
                battle_id,
                progress=10.0,
                message=f"{config.fighter_a_name} style reference ready"
            )

            # Stage 3: Create Style Reference B (ElevenLabs voice + style transfer)
            await cls._emit_update(
                battle_id,
                stage=BattleStage.STYLE_REF_B,
                progress=12.0,
                message=f"Creating style reference for {config.fighter_b_name}..."
            )

            voice_identity_b = config.fighter_b_voice_path
            style_source_b = get_preset_path(config.fighter_b_style)

            if voice_identity_b and style_source_b:
                # Combine voice identity + style via ElevenLabs speech-to-speech
                # celebrity_mode=True pitch shifts to evade voice detection, then reverses after
                # BUT: disable celebrity_mode if user recorded their own voice (not a celebrity)
                use_celebrity_mode_b = not config.fighter_b_voice_recorded
                style_ref_b, voice_id_b, status_b = await asyncio.to_thread(
                    create_style_reference,
                    voice_identity_file=voice_identity_b,
                    style_source_file=style_source_b,
                    reference_name=f"{config.fighter_b_name}_style",
                    celebrity_mode=use_celebrity_mode_b,
                    stability=0.5,
                    similarity_boost=0.85,
                )
                if not style_ref_b:
                    logging.warning(f"Style transfer failed for {config.fighter_b_name}: {status_b}, falling back")
                    style_ref_b = voice_identity_b or style_source_b
            else:
                # Fallback: use whichever is available
                style_ref_b = voice_identity_b or style_source_b

            await cls._emit_update(
                battle_id,
                progress=18.0,
                message=f"{config.fighter_b_name} style reference ready"
            )

            # Stage 4: Generate Fighter A voice (Grok with style reference)
            await cls._emit_update(
                battle_id,
                stage=BattleStage.VOICE_A,
                progress=20.0,
                message=f"Generating voice for {config.fighter_a_name}..."
            )

            audio_a, gen_status_a = await asyncio.to_thread(
                generate_rap_voice,
                lyrics=config.fighter_a_lyrics,
                style_instructions=get_style_instructions(config.fighter_a_style) or f"aggressive battle rapper, {config.fighter_a_name} style",
                voice_file=style_ref_a
            )

            if not audio_a:
                raise Exception(f"Failed to generate voice for {config.fighter_a_name}: {gen_status_a}")

            await cls._emit_update(
                battle_id,
                progress=26.0,
                message=f"{config.fighter_a_name} voice complete"
            )

            # Stage 5: Generate Fighter B voice (Grok with style reference)
            await cls._emit_update(
                battle_id,
                stage=BattleStage.VOICE_B,
                progress=28.0,
                message=f"Generating voice for {config.fighter_b_name}..."
            )

            audio_b, gen_status_b = await asyncio.to_thread(
                generate_rap_voice,
                lyrics=config.fighter_b_lyrics,
                style_instructions=get_style_instructions(config.fighter_b_style) or f"aggressive battle rapper, {config.fighter_b_name} style",
                voice_file=style_ref_b
            )

            if not audio_b:
                raise Exception(f"Failed to generate voice for {config.fighter_b_name}: {gen_status_b}")

            state.audio_clips = [audio_a, audio_b]

            await cls._emit_update(
                battle_id,
                progress=34.0,
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

            # If audio_only mode, generate arena data and complete
            if config.audio_only:
                # === STAGE: TALKHEAD (Runway) - Generate base videos in PARALLEL ===
                base_video_a = None
                base_video_b = None

                if config.fighter_a_image_path or config.fighter_b_image_path:
                    await cls._emit_update(
                        battle_id,
                        stage=BattleStage.TALKHEAD,
                        progress=52.0,
                        message="Generating talking head videos (Runway)..."
                    )

                    # Run both Runway video generations in parallel
                    async def gen_video_a():
                        if config.fighter_a_image_path:
                            return await asyncio.to_thread(
                                generate_video_from_image,
                                image_path=config.fighter_a_image_path,
                                prompt_text="person rapping, subtle head movement, looking at camera, hip hop energy",
                                duration=5
                            )
                        return None, "No image"

                    async def gen_video_b():
                        if config.fighter_b_image_path:
                            return await asyncio.to_thread(
                                generate_video_from_image,
                                image_path=config.fighter_b_image_path,
                                prompt_text="person rapping, subtle head movement, looking at camera, hip hop energy",
                                duration=5
                            )
                        return None, "No image"

                    results = await asyncio.gather(gen_video_a(), gen_video_b())
                    base_video_a, vid_status_a = results[0] if results[0] else (None, "No image")
                    base_video_b, vid_status_b = results[1] if results[1] else (None, "No image")

                    if base_video_a:
                        logging.info(f"Runway video A generated: {base_video_a}")
                    else:
                        logging.warning(f"Runway video A failed: {vid_status_a}")

                    if base_video_b:
                        logging.info(f"Runway video B generated: {base_video_b}")
                    else:
                        logging.warning(f"Runway video B failed: {vid_status_b}")

                # === STAGE: LIPSYNC_HEADS (Sync Labs) - Apply lip sync in PARALLEL ===
                if base_video_a or base_video_b:
                    await cls._emit_update(
                        battle_id,
                        stage=BattleStage.LIPSYNC_HEADS,
                        progress=65.0,
                        message="Applying lip sync (Sync Labs)..."
                    )

                    async def lipsync_a():
                        if not base_video_a:
                            return None, "No base video"
                        # Upload to temp host
                        video_url, _ = await asyncio.to_thread(upload_to_temp_host, base_video_a)
                        audio_url, _ = await asyncio.to_thread(upload_to_temp_host, audio_a)
                        if not video_url or not audio_url:
                            return None, "Upload failed"
                        # Lip sync
                        output_path = str(output_dir / f"talkhead_a_{battle_id[:8]}.mp4")
                        return await asyncio.to_thread(
                            lipsync_video,
                            video_path=video_url,
                            audio_path=audio_url,
                            output_path=Path(output_path),
                            model="lipsync-2",
                            sync_mode="loop"
                        )

                    async def lipsync_b():
                        if not base_video_b:
                            return None, "No base video"
                        # Upload to temp host
                        video_url, _ = await asyncio.to_thread(upload_to_temp_host, base_video_b)
                        audio_url, _ = await asyncio.to_thread(upload_to_temp_host, audio_b)
                        if not video_url or not audio_url:
                            return None, "Upload failed"
                        # Lip sync
                        output_path = str(output_dir / f"talkhead_b_{battle_id[:8]}.mp4")
                        return await asyncio.to_thread(
                            lipsync_video,
                            video_path=video_url,
                            audio_path=audio_url,
                            output_path=Path(output_path),
                            model="lipsync-2",
                            sync_mode="loop"
                        )

                    sync_results = await asyncio.gather(lipsync_a(), lipsync_b())
                    talking_head_a, sync_status_a = sync_results[0] if sync_results[0] else (None, "Skipped")
                    talking_head_b, sync_status_b = sync_results[1] if sync_results[1] else (None, "Skipped")

                    if talking_head_a:
                        state.talking_head_a = talking_head_a
                        logging.info(f"Talking head A complete: {talking_head_a}")
                    else:
                        logging.warning(f"Lip sync A failed: {sync_status_a}")

                    if talking_head_b:
                        state.talking_head_b = talking_head_b
                        logging.info(f"Talking head B complete: {talking_head_b}")
                    else:
                        logging.warning(f"Lip sync B failed: {sync_status_b}")

                await cls._emit_update(
                    battle_id,
                    progress=80.0,
                    message="Generating battle arena data..."
                )

                # Generate waveform visualization data
                waveform_data = await asyncio.to_thread(
                    generate_waveform_data,
                    mixed_audio,
                    100  # 100 bars for visualization
                )
                state.waveform = waveform_data

                await cls._emit_update(
                    battle_id,
                    progress=90.0,
                    message="Aligning lyrics to audio..."
                )

                # Align lyrics to audio for synchronized display
                verses = [config.fighter_a_lyrics, config.fighter_b_lyrics]
                timing_data = await asyncio.to_thread(
                    align_battle_verses,
                    audio_clips=state.audio_clips,
                    verses=verses,
                    fighter_order=["A", "B"]
                )
                state.timing_data = timing_data

                await cls._emit_update(
                    battle_id,
                    stage=BattleStage.COMPLETE,
                    progress=100.0,
                    message="Battle complete!",
                    audio_url=audio_url
                )
                return

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
