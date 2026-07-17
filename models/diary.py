from pydantic import BaseModel


class DiaryGenerateRequest(BaseModel):
    session_id: str


class DiaryGenerateResponse(BaseModel):
    diary_id: int
    diary_text: str
    summary: str
    dominant_emotion: str
