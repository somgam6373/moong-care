from types import SimpleNamespace

from services import letter_service
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


def test_generate_letter_includes_conversation_emotions_and_sleep_color(monkeypatch):
    fake_client = _FakeClient("오늘 네 이야기를 들으며 마음이 쓰였어.")
    monkeypatch.setattr(letter_service, "get_client", lambda: fake_client)

    letter = letter_service.generate_letter(
        [TurnRecord(role="user", text="발표 때문에 긴장됐어", emotions={"fearful": 0.8})],
        {"fearful": 0.8},
        [{"care_emotion": "tension", "confidence": 0.7}],
        {"hex": "#C9785A", "brightness": 0.16, "transition_ms": 6000},
    )

    assert letter == "오늘 네 이야기를 들으며 마음이 쓰였어."
    user_payload = fake_client.chat.completions.last_messages[-1]["content"]
    assert "발표 때문에 긴장됐어" in user_payload
    assert "tension" in user_payload
    assert "#C9785A" in user_payload
