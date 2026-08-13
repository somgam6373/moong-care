from pydantic import BaseModel

from models.care import CareColor


class SessionEndRequest(BaseModel):
    session_id: str


class SessionEndResponse(BaseModel):
    dominant_emotion: str
    average_emotions: dict[str, float]
    sleep_color: CareColor
