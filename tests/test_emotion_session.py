import pytest

from services.emotion_session import (
    add_user_turn, add_assistant_turn, get_session,
    compute_average, clear_session, get_last_user_emotion, SESSIONS,
)


@pytest.fixture(autouse=True)
def clean_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def test_add_user_turn_accumulates_emotions():
    add_user_turn("s1", "안녕", {"happy": 0.8, "sad": 0.2})
    add_user_turn("s1", "잘가", {"happy": 0.4, "sad": 0.6})

    session = get_session("s1")
    assert session.turn_count == 2
    assert session.emotion_sums["happy"] == pytest.approx(1.2)
    assert session.emotion_sums["sad"] == pytest.approx(0.8)


def test_add_assistant_turn_does_not_affect_emotion_sums():
    add_user_turn("s1", "안녕", {"happy": 1.0})
    add_assistant_turn("s1", "반가워!")

    session = get_session("s1")
    assert len(session.turns) == 2
    assert session.turns[1].role == "assistant"
    assert session.emotion_sums["happy"] == pytest.approx(1.0)


def test_compute_average_returns_dominant_and_average():
    add_user_turn("s1", "t1", {"happy": 0.8, "sad": 0.2, "neutral": 0.0})
    add_user_turn("s1", "t2", {"happy": 0.4, "sad": 0.6, "neutral": 0.0})

    dominant, average = compute_average("s1")
    assert dominant == "happy"
    assert average["happy"] == pytest.approx(0.6)
    assert average["sad"] == pytest.approx(0.4)


def test_compute_average_missing_session_raises_keyerror():
    with pytest.raises(KeyError):
        compute_average("does-not-exist")


def test_clear_session_removes_state():
    add_user_turn("s1", "t1", {"happy": 1.0})
    clear_session("s1")
    assert get_session("s1") is None


def test_add_assistant_turn_lazy_creates_session():
    # First call is add_assistant_turn on a brand-new session id
    add_assistant_turn("new-id", "안녕!")

    session = get_session("new-id")
    assert session.turn_count == 0
    assert len(session.turns) == 1
    assert session.turns[0].role == "assistant"


def test_compute_average_raises_keyerror_with_only_assistant_turns():
    # Session exists but turn_count is 0 (only assistant turns, no user turns)
    add_assistant_turn("new-id", "안녕!")

    with pytest.raises(KeyError):
        compute_average("new-id")


def test_clear_session_idempotent_on_never_created_session():
    # Calling clear_session on a session id that never existed should not raise
    clear_session("never-existed")


def test_get_last_user_emotion_returns_most_recent_user_turn():
    add_user_turn("s1", "t1", {"happy": 0.8, "sad": 0.2})
    add_assistant_turn("s1", "반가워")
    add_user_turn("s1", "t2", {"sad": 0.9, "happy": 0.1})

    assert get_last_user_emotion("s1") == {"sad": 0.9, "happy": 0.1}


def test_get_last_user_emotion_missing_session_returns_none():
    assert get_last_user_emotion("does-not-exist") is None


def test_get_last_user_emotion_no_user_turns_returns_none():
    add_assistant_turn("new-id", "안녕!")
    assert get_last_user_emotion("new-id") is None
