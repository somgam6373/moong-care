import io
from types import SimpleNamespace

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
    pushed_payloads = []

    async def fake_analyze_voice(app_state, wav_path):
        return "오늘 발표가 잘 됐어요", {"happy": 0.65, "sad": 0.10, "neutral": 0.20, "angry": 0.05}, 187.3, 24.1

    monkeypatch.setattr(voice_router.voice_service, "analyze_voice", fake_analyze_voice)
    monkeypatch.setattr(
        voice_router.emotion_classifier_service,
        "classify_and_reply",
        lambda transcript, emotions, pitch_mean, pitch_std, history, style: SimpleNamespace(
            care_emotion="joy",
            care_emotion_label="기쁨/만족",
            confidence=0.82,
            reason="발표 성공",
            fallback=False,
            reply_text="발표 잘 끝났다니 다행이다!",
        ),
    )
    monkeypatch.setattr(voice_router.mood_light_client, "push_color", lambda payload: pushed_payloads.append(payload))

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
    assert body["care_emotion"] == "joy"
    assert body["care_emotion_label"] == "기쁨/만족"
    assert body["care_confidence"] == 0.82
    assert body["care_color"] == {"hex": "#F6C66D", "brightness": 0.5, "transition_ms": 1200}
    assert body["reply_text"] == "발표 잘 끝났다니 다행이다!"
    session = emotion_session.get_session("s1")
    assert session.turn_count == 1
    assert session.turns[0].care_emotion == "joy"
    assert session.turns[1].role == "assistant"
    assert session.turns[1].text == "발표 잘 끝났다니 다행이다!"
    assert pushed_payloads == [
        {
            "mode": "realtime",
            "emotion": "joy",
            "hex": "#F6C66D",
            "brightness": 0.5,
            "transition_ms": 1200,
        }
    ]
