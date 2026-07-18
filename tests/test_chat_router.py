from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import chat as chat_router
from services import emotion_session


def _build_app():
    app = FastAPI()
    app.include_router(chat_router.router)
    return app


def test_reply_returns_404_when_session_missing():
    emotion_session.SESSIONS.clear()
    client = TestClient(_build_app())
    response = client.post(
        "/api/v1/chat/reply",
        json={"session_id": "missing", "transcript": "안녕", "emotions": {"happy": 1.0}},
    )
    assert response.status_code == 404


def test_reply_returns_text_and_records_assistant_turn(monkeypatch):
    emotion_session.SESSIONS.clear()
    emotion_session.add_user_turn("s1", "안녕", {"happy": 1.0})
    monkeypatch.setattr(chat_router.chat_service, "get_reply", lambda history, transcript, emotions: "반가워!")

    client = TestClient(_build_app())
    response = client.post(
        "/api/v1/chat/reply",
        json={"session_id": "s1", "transcript": "안녕", "emotions": {"happy": 1.0}},
    )

    assert response.status_code == 200
    assert response.json() == {"reply_text": "반가워!"}
    assert emotion_session.get_session("s1").turns[-1].role == "assistant"
