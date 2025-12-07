"""API routes for the Grok Rap Battle application."""

import asyncio
import json
import logging
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app_gradio_fastapi.helpers import session_logger
from app_gradio_fastapi.config.style_presets import STYLE_PRESETS, CUSTOM_UPLOAD_LABEL
from app_gradio_fastapi.services.battle_manager import BattleManager, BattleConfig
from app_gradio_fastapi.services.lyric_api import generate_all_verses


router = APIRouter()


@router.get("/health")
@session_logger.set_uuid_logging
def health() -> str:
    """Health check endpoint."""
    try:
        logging.info("health check")
        return json.dumps({"msg": "ok"})
    except Exception as e:
        logging.error(f"exception:{e}.")
        return json.dumps({"msg": "request failed"})


@router.get("/api/presets/styles")
async def get_style_presets():
    """Get available voice style presets."""
    presets = [
        {"value": key, "label": key.upper().replace("(", "- ").replace(")", "")}
        for key in STYLE_PRESETS.keys()
    ]
    presets.append({"value": "custom", "label": "CUSTOM VOICE..."})
    return {"presets": presets}


@router.post("/api/lyrics/generate")
async def generate_lyrics(
    fighter_a_name: Annotated[str, Form()],
    fighter_b_name: Annotated[str, Form()],
    theme: Annotated[str, Form()],
    fighter_a_twitter: Annotated[str, Form()] = "",
    fighter_b_twitter: Annotated[str, Form()] = "",
    fighter_a_description: Annotated[str, Form()] = "",
    fighter_b_description: Annotated[str, Form()] = "",
    fighter_a_style: Annotated[str, Form()] = "UK Grime 1 (Stormzy)",
    fighter_b_style: Annotated[str, Form()] = "West Coast (Kendrick)",
    beat_style: Annotated[str, Form()] = "trap",
    beat_bpm: Annotated[int, Form()] = 140,
):
    """Generate rap battle lyrics using Twitter context."""
    try:
        logging.info(f"Starting lyrics generation for {fighter_a_name} vs {fighter_b_name}")

        # Run blocking API calls in thread pool
        verses, status = await asyncio.to_thread(
            generate_all_verses,
            char1_name=fighter_a_name,
            char1_twitter=fighter_a_twitter or None,
            char2_name=fighter_b_name,
            char2_twitter=fighter_b_twitter or None,
            topic=theme,
            description=f"{fighter_a_description} vs {fighter_b_description}",
            scene_description="An intense rap battle arena with a hyped crowd",
            char1_rap_style=fighter_a_style,
            char2_rap_style=fighter_b_style,
            beat_style=beat_style,
            beat_bpm=beat_bpm,
        )

        logging.info(f"Lyrics generation complete: {status}")

        if not verses:
            raise HTTPException(status_code=500, detail=status)

        # Combine verses for each fighter (verses 0,2 for A, verses 1,3 for B)
        fighter_a_lyrics = "\n\n".join([verses[0], verses[2]]) if len(verses) >= 3 else verses[0] if verses else ""
        fighter_b_lyrics = "\n\n".join([verses[1], verses[3]]) if len(verses) >= 4 else verses[1] if len(verses) > 1 else ""

        return {
            "fighter_a_lyrics": fighter_a_lyrics,
            "fighter_b_lyrics": fighter_b_lyrics,
            "all_verses": verses,
            "status": status
        }

    except Exception as e:
        logging.error(f"Failed to generate lyrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/battle/start")
async def start_battle(
    fighter_a_name: Annotated[str, Form()],
    fighter_b_name: Annotated[str, Form()],
    video_style: Annotated[str, Form()] = "Photorealistic",
    location: Annotated[str, Form()] = "underground hip-hop club",
    beat_style: Annotated[str, Form()] = "trap",
    test_mode: Annotated[bool, Form()] = True,
    audio_only: Annotated[bool, Form()] = True,
    fighter_a_description: Annotated[str, Form()] = "",
    fighter_a_style: Annotated[str, Form()] = "UK Grime 1 (Stormzy)",
    fighter_a_lyrics: Annotated[str, Form()] = "",
    fighter_a_twitter: Annotated[str, Form()] = "",
    fighter_b_description: Annotated[str, Form()] = "",
    fighter_b_style: Annotated[str, Form()] = "West Coast (Kendrick)",
    fighter_b_lyrics: Annotated[str, Form()] = "",
    fighter_b_twitter: Annotated[str, Form()] = "",
    time_period: Annotated[str, Form()] = "present day",
    fighter_a_image: Annotated[UploadFile | None, File()] = None,
    fighter_a_voice: Annotated[UploadFile | None, File()] = None,
    fighter_b_image: Annotated[UploadFile | None, File()] = None,
    fighter_b_voice: Annotated[UploadFile | None, File()] = None,
):
    """Start a new rap battle and return the battle ID."""
    try:
        # Save uploaded files to temp locations
        fighter_a_image_path = None
        fighter_a_voice_path = None
        fighter_b_image_path = None
        fighter_b_voice_path = None

        if fighter_a_image:
            fighter_a_image_path = await _save_upload(fighter_a_image, "image")

        if fighter_a_voice:
            fighter_a_voice_path = await _save_upload(fighter_a_voice, "audio")

        if fighter_b_image:
            fighter_b_image_path = await _save_upload(fighter_b_image, "image")

        if fighter_b_voice:
            fighter_b_voice_path = await _save_upload(fighter_b_voice, "audio")

        # Create battle config (BPM is auto-detected from rap audio)
        config = BattleConfig(
            video_style=video_style,
            location=location,
            time_period=time_period,
            beat_style=beat_style,
            test_mode=test_mode,
            audio_only=audio_only,
            fighter_a_name=fighter_a_name,
            fighter_a_description=fighter_a_description,
            fighter_a_style=fighter_a_style,
            fighter_a_lyrics=fighter_a_lyrics,
            fighter_b_name=fighter_b_name,
            fighter_b_description=fighter_b_description,
            fighter_b_style=fighter_b_style,
            fighter_b_lyrics=fighter_b_lyrics,
            fighter_a_image_path=fighter_a_image_path,
            fighter_a_voice_path=fighter_a_voice_path,
            fighter_b_image_path=fighter_b_image_path,
            fighter_b_voice_path=fighter_b_voice_path,
            fighter_a_twitter=fighter_a_twitter or None,
            fighter_b_twitter=fighter_b_twitter or None,
        )

        # Start battle
        battle_id = await BattleManager.create_battle(config)

        return {"battle_id": battle_id, "status": "started"}

    except Exception as e:
        logging.error(f"Failed to start battle: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/battle/{battle_id}/status")
async def get_battle_status(battle_id: str):
    """Stream battle progress via Server-Sent Events (SSE)."""
    state = BattleManager.get_battle(battle_id)
    if not state:
        raise HTTPException(status_code=404, detail="Battle not found")

    return StreamingResponse(
        BattleManager.stream_progress(battle_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/api/battle/{battle_id}/result")
async def get_battle_result(battle_id: str):
    """Get the result of a completed battle."""
    state = BattleManager.get_battle(battle_id)
    if not state:
        raise HTTPException(status_code=404, detail="Battle not found")

    return {
        "battle_id": battle_id,
        "status": state.stage.value,
        "video_url": state.video_url,
        "error": state.error
    }


@router.post("/api/upload/voice")
async def upload_voice(file: UploadFile = File(...)):
    """Upload a voice sample file."""
    if not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="File must be an audio file")

    file_path = await _save_upload(file, "audio")
    return {"file_path": file_path, "filename": file.filename}


@router.post("/api/upload/image")
async def upload_image(file: UploadFile = File(...)):
    """Upload a portrait image file."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image file")

    file_path = await _save_upload(file, "image")
    return {"file_path": file_path, "filename": file.filename}


async def _save_upload(upload: UploadFile, file_type: str) -> str:
    """Save an uploaded file to a temporary location."""
    # Determine file extension
    ext = Path(upload.filename).suffix if upload.filename else ""
    if not ext:
        if file_type == "audio":
            ext = ".mp3"
        elif file_type == "image":
            ext = ".png"

    # Create temp file
    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=ext,
        prefix=f"battle_{file_type}_"
    ) as tmp:
        content = await upload.read()
        tmp.write(content)
        return tmp.name
