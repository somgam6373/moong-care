import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.letter_repository import get_letter, list_letters
from models.letter import LetterDetail, LetterListItem

router = APIRouter(prefix="/api/v1/letter", tags=["letter"])


@router.get("", response_model=list[LetterListItem])
async def list_letter(session_id: str | None = None, db: Session = Depends(get_db)):
    letters = list_letters(db, session_id)
    return [
        LetterListItem(
            id=letter.id,
            session_id=letter.session_id,
            diary_id=letter.diary_id,
            summary=letter.summary,
            dominant_emotion=letter.dominant_emotion,
            created_at=letter.created_at,
        )
        for letter in letters
    ]


@router.get("/{letter_id}", response_model=LetterDetail)
async def get_letter_detail(letter_id: int, db: Session = Depends(get_db)):
    letter = get_letter(db, letter_id)
    if letter is None:
        raise HTTPException(status_code=404, detail="letter not found")

    return LetterDetail(
        id=letter.id,
        session_id=letter.session_id,
        diary_id=letter.diary_id,
        letter_text=letter.letter_text,
        summary=letter.summary,
        dominant_emotion=letter.dominant_emotion,
        sleep_color=json.loads(letter.sleep_color) if letter.sleep_color else None,
        created_at=letter.created_at,
    )
