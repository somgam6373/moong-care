import asyncio

from services import voice_service, stt_service, ser_service


class _FakeAppState:
    def __init__(self):
        self.stt_model = object()
        self.ser_model = object()
        self.stt_lock = asyncio.Lock()
        self.ser_lock = asyncio.Lock()


def test_analyze_voice_runs_stt_and_ser_and_combines_results(monkeypatch):
    monkeypatch.setattr(stt_service, "transcribe", lambda model, path: "오늘 발표가 잘 됐어요")
    monkeypatch.setattr(ser_service, "analyze_emotion", lambda model, path: {"happy": 0.7, "neutral": 0.3})

    transcript, emotions = asyncio.run(voice_service.analyze_voice(_FakeAppState(), "dummy.wav"))

    assert transcript == "오늘 발표가 잘 됐어요"
    assert emotions == {"happy": 0.7, "neutral": 0.3}
