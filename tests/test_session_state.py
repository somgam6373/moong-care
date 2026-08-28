import pytest

from services import session_state


@pytest.fixture(autouse=True)
def reset_state():
    session_state.clear()
    yield
    session_state.clear()


def test_get_current_starts_as_none():
    assert session_state.get_current() is None


def test_start_session_sets_and_returns_current():
    session_id = session_state.start_session()
    assert session_state.get_current() == session_id
    assert isinstance(session_id, str) and len(session_id) > 0


def test_start_session_generates_a_different_id_each_call():
    first = session_state.start_session()
    second = session_state.start_session()
    assert first != second
    assert session_state.get_current() == second


def test_adopt_overwrites_current():
    session_state.start_session()
    session_state.adopt("pi-session-1")
    assert session_state.get_current() == "pi-session-1"


def test_clear_resets_to_none():
    session_state.start_session()
    session_state.clear()
    assert session_state.get_current() is None
