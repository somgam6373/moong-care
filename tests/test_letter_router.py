from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database.connection import Base, get_db
from database.letter_repository import save_letter
from routers import letter as letter_router


def _build_app():
    app = FastAPI()
    app.include_router(letter_router.router)

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


def test_get_letter_detail_returns_404_when_missing():
    app, _ = _build_app()
    client = TestClient(app)

    response = client.get("/api/v1/letter/999")

    assert response.status_code == 404


def test_get_letter_detail_returns_letter():
    app, SessionLocal = _build_app()
    db = SessionLocal()
    letter = save_letter(
        db,
        session_id="s1",
        diary_id=2,
        letter_text="오늘 네 이야기를 들었어.",
        summary="긴장한 하루",
        dominant_emotion="tension",
        sleep_color={"hex": "#C9785A", "brightness": 0.16, "transition_ms": 6000},
    )
    db.close()

    client = TestClient(app)
    response = client.get(f"/api/v1/letter/{letter.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == letter.id
    assert body["letter_text"] == "오늘 네 이야기를 들었어."
    assert body["sleep_color"] == {"hex": "#C9785A", "brightness": 0.16, "transition_ms": 6000}


def test_list_letter_filters_by_session_id():
    app, SessionLocal = _build_app()
    db = SessionLocal()
    save_letter(db, "s1", None, "a", "a", "joy", None)
    save_letter(db, "s2", None, "b", "b", "sadness", None)
    db.close()

    client = TestClient(app)

    response = client.get("/api/v1/letter")
    assert response.status_code == 200
    assert len(response.json()) == 2

    response = client.get("/api/v1/letter", params={"session_id": "s1"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["session_id"] == "s1"
