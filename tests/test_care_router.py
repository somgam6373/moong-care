import io
import urllib.parse
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import care as care_router
from services import emotion_session


def _build_app():
    app = FastAPI()
    app.include_router(care_router.router)
    return app


def _patch_happy_path(monkeypatch, *, transcript="오늘 발표가 잘 됐어요", fallback=False):
    async def fake_analyze_voice(app_state, wav_path):
        return transcript, {"happy": 0.65, "sad": 0.10, "neutral": 0.20, "angry": 0.05}, 187.3, 24.1

    monkeypatch.setattr(care_router.voice_service, "analyze_voice", fake_analyze_voice)
    monkeypatch.setattr(
        care_router.emotion_classifier_service,
        "classify_and_reply",
        lambda transcript, emotions, pitch_mean, pitch_std, history, style: SimpleNamespace(
            care_emotion="joy",
            care_emotion_label="기쁨/만족",
            confidence=0.82,
            reason="발표 성공",
            fallback=fallback,
            reply_text="우와 정말 잘됐다!",
        ),
    )
    monkeypatch.setattr(care_router.tts_service, "resolve_instructions", lambda session_id: "warm")
    monkeypatch.setattr(
        care_router.tts_service,
        "synthesize_stream",
        lambda text, voice, instructions: iter([b"FAKE-WAV-BYTES"]),
    )


def _post(client, filename="input.wav", session_id="s1"):
    return client.post(
        "/api/v1/care/turn",
        data={"session_id": session_id},
        files={"audio": (filename, io.BytesIO(b"fake audio bytes"), "audio/wav")},
    )


def test_turn_returns_wav_body_and_care_headers(monkeypatch, tmp_path):
    emotion_session.SESSIONS.clear()
    monkeypatch.setattr(care_router, "TEMP_DIR", str(tmp_path))
    # 업로드 바이트가 진짜 16kHz mono wav가 아니므로 wave.open이 실패하고
    # webm_to_wav 경로로 빠진다. 이 테스트에서는 그 변환 자체를 모킹한다.
    monkeypatch.setattr(care_router, "ensure_wav_16k_mono", lambda inp, out: inp)
    _patch_happy_path(monkeypatch)

    client = TestClient(_build_app())
    response = _post(client)

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"FAKE-WAV-BYTES"

    assert response.headers["x-care-emotion"] == "joy"
    assert urllib.parse.unquote(response.headers["x-care-label"]) == "기쁨/만족"
    assert response.headers["x-care-confidence"] == "0.82"
    assert response.headers["x-care-fallback"] == "0"
    assert response.headers["x-care-hex"] == "#F2C66D"
    assert response.headers["x-care-brightness"] == "0.5"
    assert response.headers["x-care-transition-ms"] == "1200"
    assert urllib.parse.unquote(response.headers["x-transcript"]) == "오늘 발표가 잘 됐어요"
    assert urllib.parse.unquote(response.headers["x-reply-text"]) == "우와 정말 잘됐다!"

    timing = dict(part.split("=") for part in response.headers["x-timing"].split(","))
    assert set(timing) == {"convert", "analyze", "care_reply", "tts_setup", "total"}


def test_turn_records_session_turns(monkeypatch, tmp_path):
    emotion_session.SESSIONS.clear()
    monkeypatch.setattr(care_router, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(care_router, "ensure_wav_16k_mono", lambda inp, out: inp)
    _patch_happy_path(monkeypatch)

    client = TestClient(_build_app())
    _post(client, session_id="s2")

    session = emotion_session.get_session("s2")
    assert session.turn_count == 1
    assert session.turns[0].role == "user"
    assert session.turns[0].care_emotion == "joy"
    assert session.turns[1].role == "assistant"
    assert session.turns[1].text == "우와 정말 잘됐다!"


def test_turn_passes_session_history_to_classifier(monkeypatch, tmp_path):
    """세션에 쌓인 이전 turn 기록이 분류+응답 생성 호출까지 전달되는지 확인한다."""
    emotion_session.SESSIONS.clear()
    monkeypatch.setattr(care_router, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(care_router, "ensure_wav_16k_mono", lambda inp, out: inp)
    _patch_happy_path(monkeypatch)

    captured = {}

    def fake_classify_and_reply(transcript, emotions, pitch_mean, pitch_std, history, style):
        captured["history_len"] = len(history)
        return SimpleNamespace(
            care_emotion="joy",
            care_emotion_label="기쁨/만족",
            confidence=0.82,
            reason="발표 성공",
            fallback=False,
            reply_text="우와 정말 잘됐다!",
        )

    monkeypatch.setattr(care_router.emotion_classifier_service, "classify_and_reply", fake_classify_and_reply)

    client = TestClient(_build_app())
    _post(client, session_id="s6")
    _post(client, session_id="s6")

    assert captured["history_len"] == 2


def test_turn_reports_fallback_header_when_classifier_falls_back(monkeypatch, tmp_path):
    emotion_session.SESSIONS.clear()
    monkeypatch.setattr(care_router, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(care_router, "ensure_wav_16k_mono", lambda inp, out: inp)
    _patch_happy_path(monkeypatch, transcript="", fallback=True)

    client = TestClient(_build_app())
    response = _post(client, session_id="s3")

    assert response.status_code == 200
    assert response.headers["x-care-fallback"] == "1"


def test_turn_cleans_up_temp_files(monkeypatch, tmp_path):
    emotion_session.SESSIONS.clear()
    monkeypatch.setattr(care_router, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(care_router, "ensure_wav_16k_mono", lambda inp, out: inp)
    _patch_happy_path(monkeypatch)

    client = TestClient(_build_app())
    _post(client, session_id="s4")

    assert list(tmp_path.iterdir()) == []


def test_turn_requires_audio_field():
    client = TestClient(_build_app())
    response = client.post("/api/v1/care/turn", data={"session_id": "s5"})
    assert response.status_code == 422
