import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import session as session_router
from services import emotion_session, session_state


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
    assert body["sleep_color"] == {"hex": "#B86E49", "brightness": 0.16, "transition_ms": 6000}


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
            "hex": "#993F31",
            "brightness": 0.12,
            "transition_ms": 8000,
        }
    ]


@pytest.fixture(autouse=True)
def reset_session_state():
    session_state.clear()
    yield
    session_state.clear()


def test_start_creates_and_returns_new_current_session():
    client = TestClient(_build_app())
    response = client.post("/api/v1/session/start")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_state.get_current()
    assert body["session_id"]


def test_live_returns_no_session_when_none_current():
    client = TestClient(_build_app())
    response = client.get("/api/v1/session/live")
    assert response.status_code == 200
    assert response.json() == {
        "session_id": None, "has_session": False, "ended": False,
        "turn_count": 0, "transcript": None, "care_emotion": None,
        "care_confidence": None, "care_color": None, "reply_text": None,
    }


def test_live_returns_latest_turn_snapshot_for_current_session():
    emotion_session.SESSIONS.clear()
    session_state.adopt("s1")
    emotion_session.add_user_turn(
        "s1", "안녕", {"happy": 1.0}, care_emotion="joy", care_confidence=0.8,
        care_color={"hex": "#F6C66D", "brightness": 0.5, "transition_ms": 1200},
    )
    emotion_session.add_assistant_turn("s1", "반가워!")

    client = TestClient(_build_app())
    response = client.get("/api/v1/session/live")

    assert response.status_code == 200
    body = response.json()
    assert body["has_session"] is True
    assert body["ended"] is False
    assert body["session_id"] == "s1"
    assert body["transcript"] == "안녕"
    assert body["care_emotion"] == "joy"
    assert body["reply_text"] == "반가워!"


def test_live_marks_ended_after_session_end_called():
    emotion_session.SESSIONS.clear()
    session_state.adopt("s1")
    emotion_session.add_user_turn("s1", "안녕", {"happy": 1.0}, care_emotion="joy")

    client = TestClient(_build_app())
    client.post("/api/v1/session/end", json={"session_id": "s1"})

    # end()가 current 포인터를 지우므로, ended 플래그 자체를 확인하려면 다시 adopt해서 본다.
    session_state.adopt("s1")
    response = client.get("/api/v1/session/live")
    assert response.json()["ended"] is True


def test_end_clears_current_session_pointer():
    emotion_session.SESSIONS.clear()
    session_state.adopt("s1")
    emotion_session.add_user_turn("s1", "안녕", {"happy": 1.0}, care_emotion="joy")

    client = TestClient(_build_app())
    client.post("/api/v1/session/end", json={"session_id": "s1"})

    assert session_state.get_current() is None
