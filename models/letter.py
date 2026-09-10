from datetime import datetime

from pydantic import BaseModel

from models.care import CareColor


class LetterListItem(BaseModel):
    id: int
    session_id: str
    diary_id: int | None
    summary: str
    dominant_emotion: str
    created_at: datetime


class LetterDetail(BaseModel):
    id: int
    session_id: str
    diary_id: int | None
    letter_text: str
    letter_text_en: str = ""
    summary: str
    dominant_emotion: str
    sleep_color: CareColor | None
    created_at: datetime
