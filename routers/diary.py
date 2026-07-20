import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.diary_repository import get_diary, list_diaries, save_diary
from models.diary import (
    DiaryDetail,
    DiaryGenerateRequest,
    DiaryGenerateResponse,
    DiaryListItem,
)
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


@router.get("", response_model=list[DiaryListItem])
async def list_diary(session_id: str | None = None, db: Session = Depends(get_db)):
    diaries = list_diaries(db, session_id)
    return [
        DiaryListItem(
            id=d.id,
            session_id=d.session_id,
            summary=d.summary,
            dominant_emotion=d.dominant_emotion,
            created_at=d.created_at,
        )
        for d in diaries
    ]


@router.get("/{diary_id}", response_model=DiaryDetail)
async def get_diary_detail(diary_id: int, db: Session = Depends(get_db)):
    diary = get_diary(db, diary_id)
    if diary is None:
        raise HTTPException(status_code=404, detail="diary not found")

    return DiaryDetail(
        id=diary.id,
        session_id=diary.session_id,
        diary_text=diary.diary_text,
        summary=diary.summary,
        dominant_emotion=diary.dominant_emotion,
        average_emotions=json.loads(diary.average_emotions),
        created_at=diary.created_at,
    )
