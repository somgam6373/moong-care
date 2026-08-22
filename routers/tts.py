from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

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
    audio_stream = tts_service.synthesize_stream(payload.text, voice, instructions)
    return StreamingResponse(audio_stream, media_type="audio/wav")
