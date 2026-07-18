from types import SimpleNamespace

from services import chat_service
from services.emotion_session import TurnRecord


class _FakeCompletions:
    def __init__(self, reply_text):
        self.reply_text = reply_text
        self.last_messages = None

    def create(self, model, messages):
        self.last_messages = messages
        message = SimpleNamespace(content=self.reply_text)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeClient:
    def __init__(self, reply_text):
        self.chat = SimpleNamespace(completions=_FakeCompletions(reply_text))


def test_build_messages_includes_history_and_current_emotion():
    history = [TurnRecord(role="user", text="안녕", emotions={"happy": 1.0})]
    messages = chat_service.build_messages(history, "오늘 힘들었어", {"sad": 0.8, "neutral": 0.2})

    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "안녕"}
    assert "sad" in messages[-1]["content"]
    assert "오늘 힘들었어" in messages[-1]["content"]


def test_get_reply_calls_openai_client_and_returns_text(monkeypatch):
    fake_client = _FakeClient("힘든 하루였겠다, 오늘도 애썼어.")
    monkeypatch.setattr(chat_service, "get_client", lambda: fake_client)

    reply = chat_service.get_reply([], "오늘 힘들었어", {"sad": 0.8})

    assert reply == "힘든 하루였겠다, 오늘도 애썼어."
    assert fake_client.chat.completions.last_messages[-1]["content"].endswith("오늘 힘들었어")


def test_get_reply_returns_fallback_for_near_empty_transcript(monkeypatch):
    def _boom():
        raise AssertionError("get_client should not be called for near-empty transcript")

    monkeypatch.setattr(chat_service, "get_client", _boom)

    for transcript in ["", ".", "I.", "   ", "!?"]:
        reply = chat_service.get_reply([], transcript, {"neutral": 1.0})
        assert reply == chat_service.FALLBACK_REPLY


def test_get_reply_calls_client_for_short_but_real_transcript(monkeypatch):
    fake_client = _FakeClient("그랬구나!")
    monkeypatch.setattr(chat_service, "get_client", lambda: fake_client)

    reply = chat_service.get_reply([], "안녕", {"happy": 1.0})

    assert reply == "그랬구나!"
