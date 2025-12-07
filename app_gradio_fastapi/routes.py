"""API routes for the Grok Rap Battle application."""

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


@router.post("/api/battle/start")
async def start_battle(
    theme: Annotated[str, Form()],
    beat_style: Annotated[str, Form()],
    test_mode: Annotated[bool, Form()],
    audio_only: Annotated[bool, Form()],
    fighter_a_name: Annotated[str, Form()],
    fighter_a_description: Annotated[str, Form()] = "",
    fighter_a_style: Annotated[str, Form()] = "UK Grime 1 (Stormzy)",
    fighter_a_lyrics: Annotated[str, Form()] = "",
    fighter_a_twitter: Annotated[str, Form()] = "",
    fighter_b_name: Annotated[str, Form()] = "",
    fighter_b_description: Annotated[str, Form()] = "",
    fighter_b_style: Annotated[str, Form()] = "West Coast (Kendrick)",
    fighter_b_lyrics: Annotated[str, Form()] = "",
    fighter_b_twitter: Annotated[str, Form()] = "",
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
            theme=theme,
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
