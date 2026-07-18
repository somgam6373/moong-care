from services.stt_service import transcribe


class _FakeSTTModel:
    def generate(self, input, cache, language, use_itn):
        return [{"text": "<|ko|><|NEUTRAL|><|Speech|><|woitn|>오늘 발표가 잘 됐어요"}]


def test_transcribe_strips_tags():
    text = transcribe(_FakeSTTModel(), "dummy.wav")
    assert text == "오늘 발표가 잘 됐어요"
