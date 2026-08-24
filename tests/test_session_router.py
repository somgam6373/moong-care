import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import session as session_router
from services import emotion_session


def _build_app():
    app = FastAPI()
    app.include_router(session_router.router)
    return app


def test_end_returns_404_for_missing_session():
    emotion_session.SESSIONS.clear()
    client = TestClient(_build_app())
    response = client.post("/api/v1/session/end", json={"session_id": "missing"})
    assert response.status_code == 404


def test_end_returns_dominant_care_emotion_and_average_voice_emotions():
    emotion_session.SESSIONS.clear()
    emotion_session.add_user_turn("s1", "t1", {"happy": 0.8, "sad": 0.2}, care_emotion="joy")
    emotion_session.add_user_turn("s1", "t2", {"happy": 0.4, "sad": 0.6}, care_emotion="sadness")

    client = TestClient(_build_app())
    response = client.post("/api/v1/session/end", json={"session_id": "s1"})

    assert response.status_code == 200
    body = response.json()
    assert body["dominant_emotion"] == "joy"
    assert body["average_emotions"]["happy"] == pytest.approx(0.6)
    # sleep_color는 이제 세션 전체 다수결이 아니라 대표 감정("joy") 하나에 대응되는 색.
    # joy는 수면색 4버킷 중 어디에도 안 걸리므로 기본값(warm_dim).
    assert body["sleep_color"] == {"hex": "#C9785A", "brightness": 0.16, "transition_ms": 6000}


def test_end_pushes_sleep_color(monkeypatch):
    emotion_session.SESSIONS.clear()
    emotion_session.add_user_turn("s1", "t1", {"fearful": 1.0}, care_emotion="anxiety")
    pushed_payloads = []
    monkeypatch.setattr(session_router.mood_light_client, "push_color", lambda payload: pushed_payloads.append(payload))

    client = TestClient(_build_app())
    response = client.post("/api/v1/session/end", json={"session_id": "s1"})

    assert response.status_code == 200
    assert pushed_payloads == [
        {
            "mode": "sleep",
            "emotion": "settled",
            "hex": "#B85A3D",
            "brightness": 0.12,
            "transition_ms": 8000,
        }
    ]
