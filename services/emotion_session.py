from dataclasses import dataclass

EMOTION_CLASSES = [
    "angry", "disgusted", "fearful", "happy",
    "neutral", "other", "sad", "surprised", "unknown",
]


@dataclass
class TurnRecord:
    role: str  # "user" or "assistant"
    text: str
    emotions: dict[str, float] | None = None


class SessionState:
    def __init__(self) -> None:
        self.turns: list[TurnRecord] = []
        self.emotion_sums: dict[str, float] = {c: 0.0 for c in EMOTION_CLASSES}
        self.turn_count: int = 0


SESSIONS: dict[str, SessionState] = {}


def _get_or_create(session_id: str) -> SessionState:
    if session_id not in SESSIONS:
        SESSIONS[session_id] = SessionState()
    return SESSIONS[session_id]


def add_user_turn(session_id: str, transcript: str, emotions: dict[str, float]) -> None:
    state = _get_or_create(session_id)
    state.turns.append(TurnRecord(role="user", text=transcript, emotions=emotions))
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


def compute_average(session_id: str) -> tuple[str, dict[str, float]]:
    state = SESSIONS.get(session_id)
    if state is None or state.turn_count == 0:
        raise KeyError(session_id)
    average = {cls: state.emotion_sums[cls] / state.turn_count for cls in EMOTION_CLASSES}
    dominant = max(average, key=average.get)
    return dominant, average


def clear_session(session_id: str) -> None:
    SESSIONS.pop(session_id, None)
