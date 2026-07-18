from types import SimpleNamespace

from services import diary_service
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


def test_generate_diary_includes_conversation_and_emotion(monkeypatch):
    fake_client = _FakeClient("오늘은 발표를 해서 뿌듯했다.")
    monkeypatch.setattr(diary_service, "get_client", lambda: fake_client)

    history = [
        TurnRecord(role="user", text="오늘 발표가 잘 됐어요", emotions={"happy": 0.8}),
        TurnRecord(role="assistant", text="정말 잘했네!", emotions=None),
    ]
    diary_text = diary_service.generate_diary(history, {"happy": 0.8, "neutral": 0.2})

    assert diary_text == "오늘은 발표를 해서 뿌듯했다."
    sent_prompt = fake_client.messages.last_kwargs["messages"][-1]["content"]
    assert "오늘 발표가 잘 됐어요" in sent_prompt
    assert "happy" in sent_prompt
