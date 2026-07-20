from types import SimpleNamespace

import pytest

from services import tts_service
from services.emotion_session import SESSIONS, add_assistant_turn, add_user_turn


@pytest.fixture(autouse=True)
def clean_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def test_resolve_instructions_uses_dominant_emotion_of_last_user_turn():
    add_user_turn("s1", "오늘 힘들었어", {"sad": 0.8, "neutral": 0.2})

    result = tts_service.resolve_instructions("s1")

    assert result == tts_service.EMOTION_INSTRUCTIONS["sad"]


def test_resolve_instructions_ignores_assistant_turn_after_user_turn():
    add_user_turn("s1", "오늘 힘들었어", {"sad": 0.8, "neutral": 0.2})
    add_assistant_turn("s1", "힘들었겠다")

    result = tts_service.resolve_instructions("s1")

    assert result == tts_service.EMOTION_INSTRUCTIONS["sad"]


def test_resolve_instructions_falls_back_to_neutral_for_missing_session():
    result = tts_service.resolve_instructions("does-not-exist")
    assert result == tts_service.EMOTION_INSTRUCTIONS["neutral"]


def test_resolve_instructions_falls_back_to_neutral_for_none_session_id():
    assert tts_service.resolve_instructions(None) == tts_service.EMOTION_INSTRUCTIONS["neutral"]


def test_resolve_instructions_falls_back_to_neutral_when_no_user_turn_yet():
    add_assistant_turn("s1", "안녕!")
    assert tts_service.resolve_instructions("s1") == tts_service.EMOTION_INSTRUCTIONS["neutral"]


class _FakeSpeechResponse:
    def read(self):
        return b"RIFF....WAVEfmt "


class _FakeSpeech:
    def __init__(self):
        self.last_call = None

    def create(self, model, voice, input, instructions):
        self.last_call = {"model": model, "voice": voice, "input": input, "instructions": instructions}
        return _FakeSpeechResponse()


class _FakeClient:
    def __init__(self):
        self.audio = SimpleNamespace(speech=_FakeSpeech())


def test_synthesize_calls_openai_with_expected_params_and_returns_bytes(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(tts_service, "get_client", lambda: fake_client)

    audio_bytes = tts_service.synthesize("안녕하세요", "nova", "Speak warmly.")

    assert audio_bytes == b"RIFF....WAVEfmt "
    assert fake_client.audio.speech.last_call == {
        "model": "gpt-4o-mini-tts",
        "voice": "nova",
        "input": "안녕하세요",
        "instructions": "Speak warmly.",
    }
