from pydantic import BaseModel

from models.care import CareColor


class SessionEndRequest(BaseModel):
    session_id: str


class SessionEndResponse(BaseModel):
    dominant_emotion: str
    average_emotions: dict[str, float]
    sleep_color: CareColor


class SessionStartResponse(BaseModel):
    session_id: str


class SessionLiveResponse(BaseModel):
    session_id: str | None
    has_session: bool
    ended: bool
    turn_count: int = 0
    transcript: str | None = None
    care_emotion: str | None = None
    care_confidence: float | None = None
    care_color: CareColor | None = None
    reply_text: str | None = None
