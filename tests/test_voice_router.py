import io

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import voice as voice_router
from services import emotion_session


def _build_app():
    app = FastAPI()
    app.include_router(voice_router.router)
    return app


def test_analyze_endpoint_returns_transcript_emotions_and_pitch(monkeypatch):
    emotion_session.SESSIONS.clear()
    monkeypatch.setattr(voice_router, "webm_to_wav", lambda src, dst: open(dst, "wb").close())

    async def fake_analyze_voice(app_state, wav_path):
        return "오늘 발표가 잘 됐어요", {"happy": 0.65, "sad": 0.10, "neutral": 0.20, "angry": 0.05}, 187.3, 24.1

    monkeypatch.setattr(voice_router.voice_service, "analyze_voice", fake_analyze_voice)

    client = TestClient(_build_app())
    response = client.post(
        "/api/v1/voice/analyze",
        data={"session_id": "s1"},
        files={"audio": ("test.webm", io.BytesIO(b"fake webm bytes"), "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "오늘 발표가 잘 됐어요"
    assert body["emotions"]["happy"] == 0.65
    assert body["pitch_mean"] == 187.3
    assert body["pitch_std"] == 24.1
    assert emotion_session.get_session("s1").turn_count == 1
