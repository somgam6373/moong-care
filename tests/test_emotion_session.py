import pytest

from services.emotion_session import (
    add_user_turn, add_assistant_turn, get_session,
    compute_average, clear_session, get_last_user_emotion, SESSIONS,
    get_recent_context, get_care_timeline, set_sleep_result, get_sleep_result,
    get_last_user_care_emotion, compute_dominant_care_emotion,
    get_latest_snapshot,
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


def test_get_last_user_care_emotion_returns_most_recent_care_label():
    add_user_turn("s1", "t1", {"happy": 1.0}, care_emotion="joy")
    add_assistant_turn("s1", "좋았겠다")
    add_user_turn("s1", "t2", {"fearful": 1.0}, care_emotion="tension")

    assert get_last_user_care_emotion("s1") == "tension"


def test_get_last_user_care_emotion_missing_or_no_care_returns_none():
    assert get_last_user_care_emotion("missing") is None
    add_user_turn("s1", "t1", {"happy": 1.0})
    assert get_last_user_care_emotion("s1") is None


def test_compute_dominant_care_emotion_uses_care_confidence_scores():
    add_user_turn("s1", "t1", {"happy": 0.9}, care_emotion="joy", care_confidence=0.6)
    add_user_turn("s1", "t2", {"sad": 0.9}, care_emotion="fatigue", care_confidence=0.8)
    add_user_turn("s1", "t3", {"happy": 0.9}, care_emotion="joy", care_confidence=0.1)

    assert compute_dominant_care_emotion("s1") == "fatigue"


def test_compute_dominant_care_emotion_falls_back_when_no_care_labels():
    add_user_turn("s1", "t1", {"happy": 1.0})

    assert compute_dominant_care_emotion("s1") == "calm"


def test_compute_dominant_care_emotion_missing_session_raises_keyerror():
    with pytest.raises(KeyError):
        compute_dominant_care_emotion("missing")


def test_add_user_turn_stores_care_fields():
    add_user_turn(
        "s1",
        "오늘 발표가 긴장돼",
        {"fearful": 0.7},
        pitch_mean=211.4,
        pitch_std=38.2,
        care_emotion="tension",
        care_confidence=0.74,
        care_color={"hex": "#7DCAC3", "brightness": 0.38, "transition_ms": 1800},
    )

    turn = get_session("s1").turns[0]
    assert turn.pitch_mean == 211.4
    assert turn.pitch_std == 38.2
    assert turn.care_emotion == "tension"
    assert turn.care_confidence == 0.74
    assert turn.care_color["hex"] == "#7DCAC3"


def test_get_recent_context_includes_care_emotion():
    add_user_turn("s1", "t1", {"happy": 1.0}, care_emotion="joy")
    add_assistant_turn("s1", "좋았겠다")
    add_user_turn("s1", "t2", {"fearful": 1.0}, care_emotion="tension")

    context = get_recent_context("s1", limit=2)

    assert context == [
        {"role": "assistant", "text": "좋았겠다"},
        {"role": "user", "text": "t2", "care_emotion": "tension"},
    ]


def test_get_care_timeline_returns_user_care_turns_only():
    add_user_turn("s1", "t1", {"happy": 1.0}, care_emotion="joy", care_confidence=0.8)
    add_assistant_turn("s1", "좋았겠다")
    add_user_turn("s1", "t2", {"fearful": 1.0})

    timeline = get_care_timeline("s1")

    assert timeline == [
        {
            "transcript": "t1",
            "care_emotion": "joy",
            "confidence": 0.8,
            "care_color": None,
        }
    ]


def test_sleep_result_roundtrip():
    set_sleep_result("s1", "warm_dim", {"hex": "#C9785A", "brightness": 0.16, "transition_ms": 6000})

    profile, color = get_sleep_result("s1")

    assert profile == "warm_dim"
    assert color["hex"] == "#C9785A"


def test_get_latest_snapshot_missing_session_returns_none():
    assert get_latest_snapshot("does-not-exist") is None


def test_get_latest_snapshot_no_user_turns_returns_none():
    add_assistant_turn("new-id", "안녕!")
    assert get_latest_snapshot("new-id") is None


def test_get_latest_snapshot_returns_latest_user_and_assistant_text():
    add_user_turn(
        "s1", "t1", {"happy": 1.0}, care_emotion="joy", care_confidence=0.9,
        care_color={"hex": "#F6C66D", "brightness": 0.5, "transition_ms": 1200},
    )
    add_assistant_turn("s1", "reply1")
    add_user_turn(
        "s1", "t2", {"sad": 1.0}, care_emotion="fatigue", care_confidence=0.7,
        care_color={"hex": "#7DCAC3", "brightness": 0.4, "transition_ms": 1600},
    )
    add_assistant_turn("s1", "reply2")

    snapshot = get_latest_snapshot("s1")

    assert snapshot == {
        "turn_count": 2,
        "transcript": "t2",
        "care_emotion": "fatigue",
        "care_confidence": 0.7,
        "care_color": {"hex": "#7DCAC3", "brightness": 0.4, "transition_ms": 1600},
        "reply_text": "reply2",
    }
