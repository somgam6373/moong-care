"""라즈베리파이 전용 통합 엔드포인트.

voice/analyze 와 동일하게 care 감정분류+응답생성을 LLM 호출 1번으로 묶고,
TTS는 스트리밍으로 응답 본문에 흘려보낸다.

응답은 답변 음성(wav 바이너리)을 본문에 싣고, 감정/색/전사/타이밍 같은
구조화된 값은 헤더에 실어 보낸다. HTTP 헤더는 latin-1만 허용하므로
한글이 들어가는 값(라벨, 전사, 답변 텍스트)은 percent-encoding 한다.
"""

import os
import time
import urllib.parse
import uuid

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from services import (
    color_care_service,
    emotion_classifier_service,
    emotion_session,
    tts_service,
    voice_service,
)
from utils.audio_converter import ensure_wav_16k_mono

router = APIRouter(prefix="/api/v1/care", tags=["care"])

TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")


def _quote(value: str) -> str:
    """HTTP 헤더는 latin-1만 허용하므로 한글 등은 percent-encoding 한다."""
    return urllib.parse.quote(value, safe="")


@router.post("/turn")
async def turn(
    request: Request,
    session_id: str = Form(...),
    style: str = Form("empathetic"),
    voice: str | None = Form(None),
    audio: UploadFile = None,
):
    if audio is None:
        raise HTTPException(status_code=422, detail="audio file is required")

    file_id = uuid.uuid4().hex
    input_path = os.path.join(TEMP_DIR, f"{file_id}_input")
    wav_path = os.path.join(TEMP_DIR, f"{file_id}.wav")

    with open(input_path, "wb") as f:
        f.write(await audio.read())

    timing: dict[str, float] = {}
    t_total = time.monotonic()

    def _mark(key: str, started: float) -> None:
        timing[key] = round(time.monotonic() - started, 2)

    try:
        # 1) 이미 16kHz mono wav 면 변환 생략 (파이는 항상 이 형태로 보냄)
        t = time.monotonic()
        resolved_wav = await run_in_threadpool(ensure_wav_16k_mono, input_path, wav_path)
        _mark("convert", t)

        # 2) STT + SER + pitch
        t = time.monotonic()
        transcript, emotions, pitch_mean, pitch_std = await voice_service.analyze_voice(
            request.app.state, resolved_wav
        )
        _mark("analyze", t)

        # 3) 9개 -> 14개 care_emotion + 답변 텍스트를 LLM 호출 1번으로 (voice/analyze와 동일)
        t = time.monotonic()
        session = emotion_session.get_session(session_id)
        history = session.turns if session else []
        care_result = await run_in_threadpool(
            emotion_classifier_service.classify_and_reply,
            transcript,
            emotions,
            pitch_mean,
            pitch_std,
            history,
            style,
        )
        care_color = color_care_service.get_realtime_color(care_result.care_emotion)
        care_color_dict = care_color.model_dump()
        reply_text = care_result.reply_text
        _mark("care_reply", t)

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
        emotion_session.add_assistant_turn(session_id, reply_text)

        # 4) 답변 음성 — 스트리밍이라 실제 합성 시간은 응답 전송 중에 겹쳐 흐른다
        t = time.monotonic()
        resolved_voice = voice or "nova"
        instructions = tts_service.resolve_instructions(session_id)
        audio_stream = tts_service.synthesize_stream(reply_text, resolved_voice, instructions)
        _mark("tts_setup", t)

        timing["total"] = round(time.monotonic() - t_total, 2)

        dominant = max(emotions, key=emotions.get) if emotions else "neutral"
        print(
            f'[care] "{transcript}" | raw={dominant} care={care_result.care_emotion} '
            f'({care_result.confidence:.2f}) fallback={care_result.fallback} | {timing}'
        )

        headers = {
            "X-Care-Emotion": care_result.care_emotion,
            "X-Care-Label": _quote(care_result.care_emotion_label),
            "X-Care-Confidence": str(care_result.confidence),
            "X-Care-Fallback": "1" if care_result.fallback else "0",
            "X-Care-Hex": care_color_dict["hex"],
            "X-Care-Brightness": str(care_color_dict["brightness"]),
            "X-Care-Transition-Ms": str(care_color_dict["transition_ms"]),
            "X-Transcript": _quote(transcript),
            "X-Reply-Text": _quote(reply_text),
            "X-Timing": ",".join(f"{k}={v}" for k, v in timing.items()),
        }
        return StreamingResponse(audio_stream, media_type="audio/wav", headers=headers)
    finally:
        # wav_path 는 변환이 실제로 일어났을 때만 생성된다 (건너뛴 경우 존재하지 않음).
        for path in (input_path, wav_path):
            if os.path.exists(path):
                os.remove(path)
