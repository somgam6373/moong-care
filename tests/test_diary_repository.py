import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.diary_repository import save_diary, get_diary


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)
    session = TestSessionLocal()
    yield session
    session.close()


def test_save_and_get_diary(db_session):
    diary = save_diary(
        db_session,
        session_id="s1",
        diary_text="오늘은 좋은 하루였다.",
        summary="좋은 하루",
        dominant_emotion="happy",
        average_emotions={"happy": 0.7, "neutral": 0.3},
    )
    assert diary.id is not None

    fetched = get_diary(db_session, diary.id)
    assert fetched is not None
    assert fetched.session_id == "s1"
    assert json.loads(fetched.average_emotions) == {"happy": 0.7, "neutral": 0.3}


def test_get_diary_returns_none_for_missing_id(db_session):
    assert get_diary(db_session, 999) is None
