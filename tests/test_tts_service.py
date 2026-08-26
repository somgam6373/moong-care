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


class _FakeStreamedResponse:
    def __init__(self, chunks):
        self._chunks = chunks

    def iter_bytes(self):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class _FakeStreamingSpeech:
    def __init__(self, chunks):
        self.last_call = None
        self._chunks = chunks

    def create(self, model, voice, input, instructions, response_format):
        self.last_call = {
            "model": model,
            "voice": voice,
            "input": input,
            "instructions": instructions,
            "response_format": response_format,
        }
        return _FakeStreamedResponse(self._chunks)


class _FakeClient:
    def __init__(self, chunks=(b"RIFF", b"....WAVEfmt ")):
        self.audio = SimpleNamespace(speech=SimpleNamespace(with_streaming_response=_FakeStreamingSpeech(chunks)))


def test_synthesize_stream_calls_openai_with_expected_params_and_yields_chunks(monkeypatch):
    fake_client = _FakeClient(chunks=(b"RIFF", b"....WAVEfmt "))
    monkeypatch.setattr(tts_service, "get_client", lambda: fake_client)

    chunks = list(tts_service.synthesize_stream("안녕하세요", "nova", "Speak warmly."))

    assert chunks == [b"RIFF", b"....WAVEfmt "]
    assert fake_client.audio.speech.with_streaming_response.last_call == {
        "model": "gpt-4o-mini-tts",
        "voice": "nova",
        "input": "안녕하세요",
        "instructions": "Speak warmly.",
        "response_format": "wav",
    }
