import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.diary_repository import save_diary, get_diary, list_diaries


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


def test_list_diaries_filters_by_session_id(db_session):
    save_diary(db_session, session_id="s1", diary_text="a", summary="a", dominant_emotion="happy", average_emotions={"happy": 1.0})
    save_diary(db_session, session_id="s2", diary_text="b", summary="b", dominant_emotion="sad", average_emotions={"sad": 1.0})

    all_diaries = list_diaries(db_session)
    assert len(all_diaries) == 2

    s1_diaries = list_diaries(db_session, session_id="s1")
    assert len(s1_diaries) == 1
    assert s1_diaries[0].session_id == "s1"


def test_list_diaries_orders_newest_first(db_session):
    first = save_diary(db_session, session_id="s1", diary_text="a", summary="a", dominant_emotion="happy", average_emotions={"happy": 1.0})
    second = save_diary(db_session, session_id="s1", diary_text="b", summary="b", dominant_emotion="sad", average_emotions={"sad": 1.0})

    diaries = list_diaries(db_session)
    assert diaries[0].id == second.id
    assert diaries[1].id == first.id
