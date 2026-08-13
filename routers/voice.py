import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from models.voice import VoiceAnalyzeResponse
from services import (
    color_care_service,
    emotion_classifier_service,
    emotion_session,
    mood_light_client,
    voice_service,
)
from utils.audio_converter import webm_to_wav

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")


@router.post("/analyze", response_model=VoiceAnalyzeResponse)
async def analyze(
    request: Request,
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    audio: UploadFile = None,
):
    file_id = uuid.uuid4().hex
    webm_path = os.path.join(TEMP_DIR, f"{file_id}.webm")
    wav_path = os.path.join(TEMP_DIR, f"{file_id}.wav")

    with open(webm_path, "wb") as f:
        f.write(await audio.read())

    try:
        webm_to_wav(webm_path, wav_path)
        transcript, emotions, pitch_mean, pitch_std = await voice_service.analyze_voice(request.app.state, wav_path)
        recent_context = emotion_session.get_recent_context(session_id)
        care_result = await run_in_threadpool(
            emotion_classifier_service.classify_realtime_emotion,
            transcript,
            emotions,
            pitch_mean,
            pitch_std,
            recent_context,
        )
        care_color = color_care_service.get_realtime_color(care_result.care_emotion)
        care_color_dict = care_color.model_dump()

        emotion_session.add_user_turn(
            session_id,
            transcript,
            emotions,
            pitch_mean=pitch_mean,
            pitch_std=pitch_std,
            care_emotion=care_result.care_emotion,
            care_confidence=care_result.confidence,
            care_color=care_color_dict,
        )

        background_tasks.add_task(
            mood_light_client.push_color,
            {
                "mode": "realtime",
                "emotion": care_result.care_emotion,
                **care_color_dict,
            },
        )

        dominant = max(emotions, key=emotions.get) if emotions else "neutral"
        print(
            f'[voice] 인식된 말: "{transcript}" | raw 감정: {dominant} '
            f'({emotions.get(dominant, 0):.2f}) | care 감정: {care_result.care_emotion}'
        )

        return VoiceAnalyzeResponse(
            transcript=transcript,
            emotions=emotions,
            pitch_mean=pitch_mean,
            pitch_std=pitch_std,
            care_emotion=care_result.care_emotion,
            care_emotion_label=care_result.care_emotion_label,
            care_confidence=care_result.confidence,
            care_color=care_color,
        )
    finally:
        for path in (webm_path, wav_path):
            if os.path.exists(path):
                os.remove(path)
