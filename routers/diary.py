from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.diary_repository import save_diary
from models.diary import DiaryGenerateRequest, DiaryGenerateResponse
from services import diary_service, emotion_session, summary_service

router = APIRouter(prefix="/api/v1/diary", tags=["diary"])


@router.post("/generate", response_model=DiaryGenerateResponse)
async def generate(payload: DiaryGenerateRequest, db: Session = Depends(get_db)):
    session = emotion_session.get_session(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    try:
        dominant, average = emotion_session.compute_average(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session has no turns")

    diary_text = diary_service.generate_diary(session.turns, average)
    summary = summary_service.summarize_diary(diary_text)
    diary = save_diary(db, payload.session_id, diary_text, summary, dominant, average)
    emotion_session.clear_session(payload.session_id)

    return DiaryGenerateResponse(
        diary_id=diary.id,
        diary_text=diary_text,
        summary=summary,
        dominant_emotion=dominant,
    )
