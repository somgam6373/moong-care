import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.diary_repository import get_diary, list_diaries, save_diary
from database.letter_repository import save_letter
from models.diary import (
    DiaryDetail,
    DiaryGenerateRequest,
    DiaryGenerateResponse,
    DiaryListItem,
)
from services import (
    color_care_service,
    diary_service,
    emotion_session,
    letter_service,
    sleep_color_service,
    summary_service,
)

router = APIRouter(prefix="/api/v1/diary", tags=["diary"])


@router.post("/generate", response_model=DiaryGenerateResponse)
async def generate(payload: DiaryGenerateRequest, db: Session = Depends(get_db)):
    session = emotion_session.get_session(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    try:
        _, average = emotion_session.compute_average(payload.session_id)
        dominant = emotion_session.compute_dominant_care_emotion(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session has no turns")

    diary_text = diary_service.generate_diary(session.turns, average, dominant)
    summary = summary_service.summarize_diary(diary_text)

    care_timeline = emotion_session.get_care_timeline(payload.session_id)
    _, sleep_color = emotion_session.get_sleep_result(payload.session_id)
    if sleep_color is None:
        sleep_profile = sleep_color_service.sleep_profile_for_emotion(dominant)
        sleep_color = color_care_service.get_sleep_color(sleep_profile).model_dump()
        emotion_session.set_sleep_result(payload.session_id, sleep_profile, sleep_color)

    letter_text = letter_service.generate_letter(session.turns, average, dominant, care_timeline, sleep_color)
    diary = save_diary(db, payload.session_id, diary_text, summary, dominant, average)
    letter = save_letter(db, payload.session_id, diary.id, letter_text, summary, dominant, sleep_color)
    emotion_session.clear_session(payload.session_id)

    return DiaryGenerateResponse(
        diary_id=diary.id,
        letter_id=letter.id,
        diary_text=diary_text,
        letter_text=letter_text,
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
