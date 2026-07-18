from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base, get_db
from routers import diary as diary_router
from services import emotion_session


def _build_app():
    app = FastAPI()
    app.include_router(diary_router.router)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app


def test_generate_returns_404_when_session_missing():
    emotion_session.SESSIONS.clear()
    client = TestClient(_build_app())
    response = client.post("/api/v1/diary/generate", json={"session_id": "missing"})
    assert response.status_code == 404


def test_generate_creates_diary_and_clears_session(monkeypatch):
    emotion_session.SESSIONS.clear()
    emotion_session.add_user_turn("s1", "오늘 발표가 잘 됐어요", {"happy": 0.8, "neutral": 0.2})

    monkeypatch.setattr(diary_router.diary_service, "generate_diary", lambda history, average: "오늘은 발표를 잘해서 기뻤다.")
    monkeypatch.setattr(diary_router.summary_service, "summarize_diary", lambda diary_text: "발표 성공으로 뿌듯한 하루")

    client = TestClient(_build_app())
    response = client.post("/api/v1/diary/generate", json={"session_id": "s1"})

    assert response.status_code == 200
    body = response.json()
    assert body["diary_text"] == "오늘은 발표를 잘해서 기뻤다."
    assert body["summary"] == "발표 성공으로 뿌듯한 하루"
    assert body["dominant_emotion"] == "happy"
    assert emotion_session.get_session("s1") is None
