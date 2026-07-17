import json
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import Session

from database.connection import Base


class Diary(Base):
    __tablename__ = "diaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False)
    diary_text = Column(Text, nullable=False)
    summary = Column(String(255), nullable=False)
    dominant_emotion = Column(String(32), nullable=False)
    average_emotions = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def save_diary(
    db: Session,
    session_id: str,
    diary_text: str,
    summary: str,
    dominant_emotion: str,
    average_emotions: dict[str, float],
) -> Diary:
    diary = Diary(
        session_id=session_id,
        diary_text=diary_text,
        summary=summary,
        dominant_emotion=dominant_emotion,
        average_emotions=json.dumps(average_emotions),
    )
    db.add(diary)
    db.commit()
    db.refresh(diary)
    return diary


def get_diary(db: Session, diary_id: int) -> Diary | None:
    return db.get(Diary, diary_id)
