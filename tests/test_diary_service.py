from types import SimpleNamespace

from services import diary_service
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


def test_generate_diary_includes_conversation_and_emotion(monkeypatch):
    fake_client = _FakeClient("오늘은 발표를 해서 뿌듯했다.")
    monkeypatch.setattr(diary_service, "get_client", lambda: fake_client)

    history = [
        TurnRecord(role="user", text="오늘 발표가 잘 됐어요", emotions={"happy": 0.8}),
        TurnRecord(role="assistant", text="정말 잘했네!", emotions=None),
    ]
    diary_text = diary_service.generate_diary(history, {"happy": 0.8, "neutral": 0.2})

    assert diary_text == "오늘은 발표를 해서 뿌듯했다."
    sent_prompt = fake_client.chat.completions.last_messages[-1]["content"]
    assert "오늘 발표가 잘 됐어요" in sent_prompt
    assert "happy" in sent_prompt
