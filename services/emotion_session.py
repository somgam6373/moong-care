from dataclasses import dataclass

EMOTION_CLASSES = [
    "angry", "disgusted", "fearful", "happy",
    "neutral", "other", "sad", "surprised", "unknown",
]
FALLBACK_CARE_EMOTION = "calm"


@dataclass
class TurnRecord:
    role: str  # "user" or "assistant"
    text: str
    emotions: dict[str, float] | None = None
    pitch_mean: float | None = None
    pitch_std: float | None = None
    care_emotion: str | None = None
    care_confidence: float | None = None
    care_color: dict | None = None


class SessionState:
    def __init__(self) -> None:
        self.turns: list[TurnRecord] = []
        self.emotion_sums: dict[str, float] = {c: 0.0 for c in EMOTION_CLASSES}
        self.turn_count: int = 0
        self.sleep_profile: str | None = None
        self.sleep_color: dict | None = None


SESSIONS: dict[str, SessionState] = {}


def _get_or_create(session_id: str) -> SessionState:
    if session_id not in SESSIONS:
        SESSIONS[session_id] = SessionState()
    return SESSIONS[session_id]


def add_user_turn(
    session_id: str,
    transcript: str,
    emotions: dict[str, float],
    pitch_mean: float | None = None,
    pitch_std: float | None = None,
    care_emotion: str | None = None,
    care_confidence: float | None = None,
    care_color: dict | None = None,
) -> None:
    state = _get_or_create(session_id)
    state.turns.append(
        TurnRecord(
            role="user",
            text=transcript,
            emotions=emotions,
            pitch_mean=pitch_mean,
            pitch_std=pitch_std,
            care_emotion=care_emotion,
            care_confidence=care_confidence,
            care_color=care_color,
        )
    )
    for cls in EMOTION_CLASSES:
        state.emotion_sums[cls] += emotions.get(cls, 0.0)
    state.turn_count += 1


def add_assistant_turn(session_id: str, reply_text: str) -> None:
    state = _get_or_create(session_id)
    state.turns.append(TurnRecord(role="assistant", text=reply_text, emotions=None))


def get_session(session_id: str) -> SessionState | None:
    return SESSIONS.get(session_id)


def get_last_user_emotion(session_id: str) -> dict[str, float] | None:
    state = SESSIONS.get(session_id)
    if state is None:
        return None
    for turn in reversed(state.turns):
        if turn.role == "user":
            return turn.emotions
    return None


def get_last_user_care_emotion(session_id: str) -> str | None:
    state = SESSIONS.get(session_id)
    if state is None:
        return None
    for turn in reversed(state.turns):
        if turn.role == "user" and turn.care_emotion is not None:
            return turn.care_emotion
    return None


def get_recent_context(session_id: str, limit: int = 4) -> list[dict]:
    state = SESSIONS.get(session_id)
    if state is None:
        return []

    context = []
    for turn in state.turns[-limit:]:
        item = {"role": turn.role, "text": turn.text}
        if turn.care_emotion is not None:
            item["care_emotion"] = turn.care_emotion
        context.append(item)
    return context


def get_care_timeline(session_id: str) -> list[dict]:
    state = SESSIONS.get(session_id)
    if state is None:
        return []

    timeline = []
    for turn in state.turns:
        if turn.role != "user" or turn.care_emotion is None:
            continue
        timeline.append({
            "transcript": turn.text,
            "care_emotion": turn.care_emotion,
            "confidence": turn.care_confidence,
            "care_color": turn.care_color,
        })
    return timeline


def set_sleep_result(session_id: str, sleep_profile: str, sleep_color: dict) -> None:
    state = _get_or_create(session_id)
    state.sleep_profile = sleep_profile
    state.sleep_color = sleep_color


def get_sleep_result(session_id: str) -> tuple[str | None, dict | None]:
    state = SESSIONS.get(session_id)
    if state is None:
        return None, None
    return state.sleep_profile, state.sleep_color


def compute_average(session_id: str) -> tuple[str, dict[str, float]]:
    state = SESSIONS.get(session_id)
    if state is None or state.turn_count == 0:
        raise KeyError(session_id)
    average = {cls: state.emotion_sums[cls] / state.turn_count for cls in EMOTION_CLASSES}
    dominant = max(average, key=average.get)
    return dominant, average


def compute_dominant_care_emotion(session_id: str) -> str:
    state = SESSIONS.get(session_id)
    if state is None or state.turn_count == 0:
        raise KeyError(session_id)

    scores: dict[str, float] = {}
    for turn in state.turns:
        if turn.role != "user" or turn.care_emotion is None:
            continue
        scores[turn.care_emotion] = scores.get(turn.care_emotion, 0.0) + (
            turn.care_confidence if turn.care_confidence is not None else 1.0
        )

    if not scores:
        return FALLBACK_CARE_EMOTION
    return max(scores, key=scores.get)


def clear_session(session_id: str) -> None:
    SESSIONS.pop(session_id, None)
