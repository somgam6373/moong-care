from types import SimpleNamespace

from services import chat_service
from services.emotion_session import TurnRecord


class _FakeMessages:
    def __init__(self, reply_text):
        self.reply_text = reply_text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply_text)])


class _FakeClient:
    def __init__(self, reply_text):
        self.messages = _FakeMessages(reply_text)


def test_build_messages_includes_history_and_current_emotion():
    history = [TurnRecord(role="user", text="안녕", emotions={"happy": 1.0})]
    messages = chat_service.build_messages(history, "오늘 힘들었어", {"sad": 0.8, "neutral": 0.2})

    assert messages[0] == {"role": "user", "content": "안녕"}
    assert "sad" in messages[-1]["content"]
    assert "오늘 힘들었어" in messages[-1]["content"]


def test_get_reply_calls_anthropic_client_and_returns_text(monkeypatch):
    fake_client = _FakeClient("힘든 하루였겠다, 오늘도 애썼어.")
    monkeypatch.setattr(chat_service, "get_client", lambda: fake_client)

    reply = chat_service.get_reply([], "오늘 힘들었어", {"sad": 0.8})

    assert reply == "힘든 하루였겠다, 오늘도 애썼어."
    kwargs = fake_client.messages.last_kwargs
    assert kwargs["system"] == chat_service.MOONG_SYSTEM_PROMPT
    assert kwargs["messages"][-1]["content"].endswith("오늘 힘들었어")
