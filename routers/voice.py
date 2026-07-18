import os
import uuid

from fastapi import APIRouter, Form, Request, UploadFile

from models.voice import VoiceAnalyzeResponse
from services import emotion_session, voice_service
from utils.audio_converter import webm_to_wav

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")


@router.post("/analyze", response_model=VoiceAnalyzeResponse)
async def analyze(request: Request, session_id: str = Form(...), audio: UploadFile = None):
    file_id = uuid.uuid4().hex
    webm_path = os.path.join(TEMP_DIR, f"{file_id}.webm")
    wav_path = os.path.join(TEMP_DIR, f"{file_id}.wav")

    with open(webm_path, "wb") as f:
        f.write(await audio.read())

    try:
        webm_to_wav(webm_path, wav_path)
        transcript, emotions, pitch_mean, pitch_std = await voice_service.analyze_voice(request.app.state, wav_path)
        emotion_session.add_user_turn(session_id, transcript, emotions)
        return VoiceAnalyzeResponse(
            transcript=transcript,
            emotions=emotions,
            pitch_mean=pitch_mean,
            pitch_std=pitch_std,
        )
    finally:
        for path in (webm_path, wav_path):
            if os.path.exists(path):
                os.remove(path)
