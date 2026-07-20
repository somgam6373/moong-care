from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base, get_db
from database.diary_repository import save_diary
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
    return app, TestSessionLocal


def test_generate_returns_404_when_session_missing():
    emotion_session.SESSIONS.clear()
    app, _ = _build_app()
    client = TestClient(app)
    response = client.post("/api/v1/diary/generate", json={"session_id": "missing"})
    assert response.status_code == 404


def test_generate_creates_diary_and_clears_session(monkeypatch):
    emotion_session.SESSIONS.clear()
    emotion_session.add_user_turn("s1", "오늘 발표가 잘 됐어요", {"happy": 0.8, "neutral": 0.2})

    monkeypatch.setattr(diary_router.diary_service, "generate_diary", lambda history, average: "오늘은 발표를 잘해서 기뻤다.")
    monkeypatch.setattr(diary_router.summary_service, "summarize_diary", lambda diary_text: "발표 성공으로 뿌듯한 하루")

    app, _ = _build_app()
    client = TestClient(app)
    response = client.post("/api/v1/diary/generate", json={"session_id": "s1"})

    assert response.status_code == 200
    body = response.json()
    assert body["diary_text"] == "오늘은 발표를 잘해서 기뻤다."
    assert body["summary"] == "발표 성공으로 뿌듯한 하루"
    assert body["dominant_emotion"] == "happy"
    assert emotion_session.get_session("s1") is None


def test_get_diary_detail_returns_404_when_missing():
    app, _ = _build_app()
    client = TestClient(app)
    response = client.get("/api/v1/diary/999")
    assert response.status_code == 404


def test_get_diary_detail_returns_diary():
    app, SessionLocal = _build_app()
    db = SessionLocal()
    diary = save_diary(db, session_id="s1", diary_text="오늘은 좋은 하루였다.", summary="좋은 하루", dominant_emotion="happy", average_emotions={"happy": 0.9})
    db.close()

    client = TestClient(app)
    response = client.get(f"/api/v1/diary/{diary.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == diary.id
    assert body["diary_text"] == "오늘은 좋은 하루였다."
    assert body["average_emotions"] == {"happy": 0.9}


def test_list_diary_filters_by_session_id():
    app, SessionLocal = _build_app()
    db = SessionLocal()
    save_diary(db, session_id="s1", diary_text="a", summary="a", dominant_emotion="happy", average_emotions={"happy": 1.0})
    save_diary(db, session_id="s2", diary_text="b", summary="b", dominant_emotion="sad", average_emotions={"sad": 1.0})
    db.close()

    client = TestClient(app)

    response = client.get("/api/v1/diary")
    assert response.status_code == 200
    assert len(response.json()) == 2

    response = client.get("/api/v1/diary", params={"session_id": "s1"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["session_id"] == "s1"
