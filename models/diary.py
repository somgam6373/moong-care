from datetime import datetime

from pydantic import BaseModel


class DiaryGenerateRequest(BaseModel):
    session_id: str


class DiaryGenerateResponse(BaseModel):
    diary_id: int
    diary_text: str
    summary: str
    dominant_emotion: str


class DiaryListItem(BaseModel):
    id: int
    session_id: str
    summary: str
    dominant_emotion: str
    created_at: datetime


class DiaryDetail(BaseModel):
    id: int
    session_id: str
    diary_text: str
    summary: str
    dominant_emotion: str
    average_emotions: dict[str, float]
    created_at: datetime
