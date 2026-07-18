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


def test_end_returns_dominant_and_average_emotions():
    emotion_session.SESSIONS.clear()
    emotion_session.add_user_turn("s1", "t1", {"happy": 0.8, "sad": 0.2})
    emotion_session.add_user_turn("s1", "t2", {"happy": 0.4, "sad": 0.6})

    client = TestClient(_build_app())
    response = client.post("/api/v1/session/end", json={"session_id": "s1"})

    assert response.status_code == 200
    body = response.json()
    assert body["dominant_emotion"] == "happy"
    assert body["average_emotions"]["happy"] == pytest.approx(0.6)
