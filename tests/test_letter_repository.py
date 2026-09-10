import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.letter_repository import get_letter, list_letters, save_letter


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)
    session = TestSessionLocal()
    yield session
    session.close()


def test_save_and_get_letter(db_session):
    letter = save_letter(
        db_session,
        session_id="s1",
        diary_id=10,
        letter_text="오늘 네 이야기를 들었어.",
        summary="긴장한 하루",
        dominant_emotion="tension",
        sleep_color={"hex": "#C9785A", "brightness": 0.16, "transition_ms": 6000},
    )

    fetched = get_letter(db_session, letter.id)

    assert fetched is not None
    assert fetched.session_id == "s1"
    assert fetched.diary_id == 10
    assert json.loads(fetched.sleep_color)["hex"] == "#C9785A"


def test_save_and_get_letter_stores_english_text(db_session):
    letter = save_letter(
        db_session,
        session_id="s1",
        diary_id=10,
        letter_text="오늘 네 이야기를 들었어.",
        summary="긴장한 하루",
        dominant_emotion="tension",
        sleep_color=None,
        letter_text_en="I heard about your day today.",
    )

    fetched = get_letter(db_session, letter.id)

    assert fetched.letter_text_en == "I heard about your day today."


def test_get_letter_returns_none_for_missing_id(db_session):
    assert get_letter(db_session, 999) is None


def test_list_letters_filters_by_session_id(db_session):
    save_letter(db_session, "s1", None, "a", "a", "joy", None)
    save_letter(db_session, "s2", None, "b", "b", "sadness", None)

    assert len(list_letters(db_session)) == 2
    s1_letters = list_letters(db_session, session_id="s1")
    assert len(s1_letters) == 1
    assert s1_letters[0].session_id == "s1"


def test_list_letters_orders_newest_first(db_session):
    first = save_letter(db_session, "s1", None, "a", "a", "joy", None)
    second = save_letter(db_session, "s1", None, "b", "b", "sadness", None)

    letters = list_letters(db_session)

    assert letters[0].id == second.id
    assert letters[1].id == first.id
