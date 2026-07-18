from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from models.tts import TTSRequest
from services import tts_service

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])


@router.post("")
async def synthesize(request: Request, payload: TTSRequest):
    async with request.app.state.tts_lock:
        audio_bytes = await run_in_threadpool(tts_service.synthesize, request.app.state.tts_model, payload.text)
    return Response(content=audio_bytes, media_type="audio/wav")
