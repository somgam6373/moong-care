from fastapi import APIRouter, HTTPException, Response
from fastapi.concurrency import run_in_threadpool

from config import settings
from models.tts import TTSRequest
from services import tts_service

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])


@router.post("")
async def synthesize(payload: TTSRequest):
    voice = payload.voice or settings.TTS_DEFAULT_VOICE
    if voice not in settings.TTS_ALLOWED_VOICES:
        raise HTTPException(status_code=400, detail=f"unsupported voice: {voice}")

    instructions = tts_service.resolve_instructions(payload.session_id)
    audio_bytes = await run_in_threadpool(tts_service.synthesize, payload.text, voice, instructions)
    return Response(content=audio_bytes, media_type="audio/wav")
