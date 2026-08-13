import json
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import Session

from database.connection import Base


class Letter(Base):
    __tablename__ = "letters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False)
    diary_id = Column(Integer, nullable=True)
    letter_text = Column(Text, nullable=False)
    summary = Column(String(255), nullable=False)
    dominant_emotion = Column(String(32), nullable=False)
    sleep_color = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def save_letter(
    db: Session,
    session_id: str,
    diary_id: int | None,
    letter_text: str,
    summary: str,
    dominant_emotion: str,
    sleep_color: dict | None,
) -> Letter:
    letter = Letter(
        session_id=session_id,
        diary_id=diary_id,
        letter_text=letter_text,
        summary=summary,
        dominant_emotion=dominant_emotion,
        sleep_color=json.dumps(sleep_color) if sleep_color is not None else None,
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)
    return letter


def get_letter(db: Session, letter_id: int) -> Letter | None:
    return db.get(Letter, letter_id)


def list_letters(db: Session, session_id: str | None = None) -> list[Letter]:
    query = db.query(Letter)
    if session_id is not None:
        query = query.filter(Letter.session_id == session_id)
    return query.order_by(Letter.created_at.desc(), Letter.id.desc()).all()
