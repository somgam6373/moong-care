from types import SimpleNamespace

from services import letter_service
from services.emotion_session import TurnRecord


class _FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        message = SimpleNamespace(content=self.content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeClient:
    def __init__(self, content):
        self.chat = SimpleNamespace(completions=_FakeCompletions(content))


def _generate(fake_client):
    return letter_service.generate_letter(
        [TurnRecord(role="user", text="발표 때문에 긴장됐어", emotions={"fearful": 0.8})],
        {"fearful": 0.8},
        "tension",
        [{"care_emotion": "tension", "confidence": 0.7}],
        {"hex": "#C9785A", "brightness": 0.16, "transition_ms": 6000},
    )


def test_generate_letter_returns_korean_and_english_from_json(monkeypatch):
    fake_client = _FakeClient(
        '{"letter_ko": "오늘 네 이야기를 들으며 마음이 쓰였어.", "letter_en": "Hearing about your day today touched my heart."}'
    )
    monkeypatch.setattr(letter_service, "get_client", lambda: fake_client)

    letter_ko, letter_en = _generate(fake_client)

    assert letter_ko == "오늘 네 이야기를 들으며 마음이 쓰였어."
    assert letter_en == "Hearing about your day today touched my heart."
    assert fake_client.chat.completions.last_kwargs["response_format"] == {"type": "json_object"}
    user_payload = fake_client.chat.completions.last_kwargs["messages"][-1]["content"]
    assert "발표 때문에 긴장됐어" in user_payload
    assert "tension" in user_payload
    assert "#C9785A" in user_payload


def test_generate_letter_falls_back_to_raw_content_on_invalid_json(monkeypatch):
    fake_client = _FakeClient("그냥 평범한 텍스트야, JSON 아님.")
    monkeypatch.setattr(letter_service, "get_client", lambda: fake_client)

    letter_ko, letter_en = _generate(fake_client)

    assert letter_ko == "그냥 평범한 텍스트야, JSON 아님."
    assert letter_en == "그냥 평범한 텍스트야, JSON 아님."
