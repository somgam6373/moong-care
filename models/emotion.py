from pydantic import BaseModel


class SessionEndRequest(BaseModel):
    session_id: str


class SessionEndResponse(BaseModel):
    dominant_emotion: str
    average_emotions: dict[str, float]
