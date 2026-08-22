from types import SimpleNamespace

from services import chat_service, emotion_classifier_service
from services.emotion_session import TurnRecord


class _FakeCompletions:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self.error:
            raise self.error
        message = SimpleNamespace(content=self.content)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeClient:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)


def _classify():
    return emotion_classifier_service.classify_realtime_emotion(
        "오늘 발표 때문에 긴장돼",
        {"fearful": 0.42, "neutral": 0.30},
        211.4,
        38.2,
        [{"role": "user", "text": "내일 발표가 있어", "care_emotion": "tension"}],
    )


def test_classify_realtime_emotion_parses_valid_json(monkeypatch):
    completions = _FakeCompletions('{"care_emotion":"tension","confidence":0.74,"reason":"발표 전 압박"}')
    fake_client = _FakeClient(completions)
    monkeypatch.setattr(emotion_classifier_service, "get_client", lambda: fake_client)

    result = _classify()

    assert result.care_emotion == "tension"
    assert result.care_emotion_label == "긴장"
    assert result.confidence == 0.74
    assert result.fallback is False
    assert completions.last_kwargs["temperature"] == 0
    assert completions.last_kwargs["response_format"] == {"type": "json_object"}


def test_classify_realtime_emotion_falls_back_on_openai_error(monkeypatch):
    fake_client = _FakeClient(_FakeCompletions(error=RuntimeError("boom")))
    monkeypatch.setattr(emotion_classifier_service, "get_client", lambda: fake_client)

    result = _classify()

    assert result.care_emotion == "calm"
    assert result.fallback is True


def test_classify_realtime_emotion_falls_back_when_client_creation_fails(monkeypatch):
    def _boom():
        raise RuntimeError("client boom")

    monkeypatch.setattr(emotion_classifier_service, "get_client", _boom)

    result = _classify()

    assert result.care_emotion == "calm"
    assert result.fallback is True


def test_classify_realtime_emotion_falls_back_on_invalid_json(monkeypatch):
    fake_client = _FakeClient(_FakeCompletions("not json"))
    monkeypatch.setattr(emotion_classifier_service, "get_client", lambda: fake_client)

    result = _classify()

    assert result.care_emotion == "calm"
    assert result.fallback is True


def test_classify_realtime_emotion_falls_back_on_unsupported_emotion(monkeypatch):
    fake_client = _FakeClient(_FakeCompletions('{"care_emotion":"panic","confidence":0.9,"reason":"x"}'))
    monkeypatch.setattr(emotion_classifier_service, "get_client", lambda: fake_client)

    result = _classify()

    assert result.care_emotion == "calm"
    assert result.fallback is True


def test_classify_realtime_emotion_short_transcript_skips_openai(monkeypatch):
    def _boom():
        raise AssertionError("get_client should not be called")

    monkeypatch.setattr(emotion_classifier_service, "get_client", _boom)

    result = emotion_classifier_service.classify_realtime_emotion(".", {"neutral": 1.0}, 0.0, 0.0, [])

    assert result.care_emotion == "calm"
    assert result.fallback is True


def test_classify_realtime_emotion_adjusts_sad_completed_burden_to_fatigue(monkeypatch):
    completions = _FakeCompletions('{"care_emotion":"sadness","confidence":0.997,"reason":"sad score is highest"}')
    fake_client = _FakeClient(completions)
    monkeypatch.setattr(emotion_classifier_service, "get_client", lambda: fake_client)

    result = emotion_classifier_service.classify_realtime_emotion(
        "하 나 오늘 발표 끝났어.",
        {
            "angry": 0.00002,
            "fearful": 0.001,
            "happy": 0.0002,
            "neutral": 0.0002,
            "sad": 0.997,
        },
        98.6,
        24.2,
        [],
    )

    assert result.care_emotion == "fatigue"
    assert result.care_emotion_label == "피로"
    assert result.confidence == 0.78
    assert result.fallback is False


def test_classify_realtime_emotion_keeps_explicit_sadness(monkeypatch):
    completions = _FakeCompletions('{"care_emotion":"sadness","confidence":0.86,"reason":"explicit sadness"}')
    fake_client = _FakeClient(completions)
    monkeypatch.setattr(emotion_classifier_service, "get_client", lambda: fake_client)

    result = emotion_classifier_service.classify_realtime_emotion(
        "발표 끝났는데 너무 속상하고 마음이 가라앉아.",
        {"sad": 0.91, "neutral": 0.05},
        110.0,
        20.0,
        [],
    )

    assert result.care_emotion == "sadness"
    assert result.fallback is False


def test_classify_realtime_emotion_adjusts_happy_completed_burden_to_joy(monkeypatch):
    completions = _FakeCompletions('{"care_emotion":"relief","confidence":0.9,"reason":"presentation ended"}')
    fake_client = _FakeClient(completions)
    monkeypatch.setattr(emotion_classifier_service, "get_client", lambda: fake_client)

    result = emotion_classifier_service.classify_realtime_emotion(
        "나 발표 끝났어.",
        {
            "happy": 0.9997,
            "surprised": 0.0002,
            "sad": 0.0001,
            "neutral": 0.0,
        },
        138.6,
        56.6,
        [],
    )

    assert result.care_emotion == "joy"
    assert result.care_emotion_label == "기쁨/만족"
    assert result.confidence == 0.95
    assert result.fallback is False


def _classify_and_reply(history=None):
    return emotion_classifier_service.classify_and_reply(
        "오늘 발표 때문에 긴장돼",
        {"fearful": 0.42, "neutral": 0.30},
        211.4,
        38.2,
        history or [],
        "empathetic",
    )


def test_classify_and_reply_parses_care_emotion_and_reply_in_one_call(monkeypatch):
    completions = _FakeCompletions(
        '{"care_emotion":"tension","confidence":0.74,"reason":"발표 전 압박","reply_text":"긴장되겠다, 잘할 수 있어."}'
    )
    fake_client = _FakeClient(completions)
    monkeypatch.setattr(emotion_classifier_service, "get_client", lambda: fake_client)

    result = _classify_and_reply()

    assert result.care_emotion == "tension"
    assert result.confidence == 0.74
    assert result.reply_text == "긴장되겠다, 잘할 수 있어."
    assert result.fallback is False
    assert completions.last_kwargs["response_format"] == {"type": "json_object"}
    assert "temperature" not in completions.last_kwargs


def test_classify_and_reply_includes_persona_and_history_in_messages(monkeypatch):
    completions = _FakeCompletions(
        '{"care_emotion":"tension","confidence":0.7,"reason":"x","reply_text":"괜찮아."}'
    )
    fake_client = _FakeClient(completions)
    monkeypatch.setattr(emotion_classifier_service, "get_client", lambda: fake_client)

    history = [TurnRecord(role="user", text="어제 발표 준비했어", care_emotion="tension")]
    _classify_and_reply(history)

    messages = completions.last_kwargs["messages"]
    assert chat_service.EMPATHETIC_SYSTEM_PROMPT in messages[0]["content"]
    assert emotion_classifier_service.CLASSIFIER_SYSTEM_PROMPT in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "[케어 감정: tension] 어제 발표 준비했어"}
    assert "reply_text" in messages[-1]["content"]


def test_classify_and_reply_falls_back_on_openai_error(monkeypatch):
    fake_client = _FakeClient(_FakeCompletions(error=RuntimeError("boom")))
    monkeypatch.setattr(emotion_classifier_service, "get_client", lambda: fake_client)

    result = _classify_and_reply()

    assert result.care_emotion == "calm"
    assert result.fallback is True
    assert result.reply_text == chat_service.FALLBACK_REPLY


def test_classify_and_reply_short_transcript_skips_openai(monkeypatch):
    def _boom():
        raise AssertionError("get_client should not be called")

    monkeypatch.setattr(emotion_classifier_service, "get_client", _boom)

    result = emotion_classifier_service.classify_and_reply(".", {"neutral": 1.0}, 0.0, 0.0, [])

    assert result.care_emotion == "calm"
    assert result.fallback is True
    assert result.reply_text == chat_service.FALLBACK_REPLY


def test_classify_and_reply_adjustment_preserves_reply_text(monkeypatch):
    completions = _FakeCompletions(
        '{"care_emotion":"sadness","confidence":0.997,"reason":"sad score is highest",'
        '"reply_text":"오늘 하루도 고생 많았어."}'
    )
    fake_client = _FakeClient(completions)
    monkeypatch.setattr(emotion_classifier_service, "get_client", lambda: fake_client)

    result = emotion_classifier_service.classify_and_reply(
        "하 나 오늘 발표 끝났어.",
        {
            "angry": 0.00002,
            "fearful": 0.001,
            "happy": 0.0002,
            "neutral": 0.0002,
            "sad": 0.997,
        },
        98.6,
        24.2,
        [],
    )

    assert result.care_emotion == "fatigue"
    assert result.reply_text == "오늘 하루도 고생 많았어."
