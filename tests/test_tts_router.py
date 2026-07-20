from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import tts as tts_router


def _build_app():
    app = FastAPI()
    app.include_router(tts_router.router)
    return app


def test_synthesize_returns_wav_bytes_with_default_voice(monkeypatch):
    calls = {}

    def fake_resolve_instructions(session_id):
        calls["session_id"] = session_id
        return "Speak in a natural, warm, conversational tone."

    def fake_synthesize(text, voice, instructions):
        calls["synthesize"] = {"text": text, "voice": voice, "instructions": instructions}
        return b"RIFF....WAVEfmt "

    monkeypatch.setattr(tts_router.tts_service, "resolve_instructions", fake_resolve_instructions)
    monkeypatch.setattr(tts_router.tts_service, "synthesize", fake_synthesize)

    client = TestClient(_build_app())
    response = client.post("/api/v1/tts", json={"text": "안녕하세요"})

    assert response.status_code == 200
    assert response.content == b"RIFF....WAVEfmt "
    assert response.headers["content-type"] == "audio/wav"
    assert calls["synthesize"]["voice"] == "nova"


def test_synthesize_uses_requested_voice(monkeypatch):
    monkeypatch.setattr(tts_router.tts_service, "resolve_instructions", lambda session_id: "neutral tone")
    monkeypatch.setattr(tts_router.tts_service, "synthesize", lambda text, voice, instructions: b"RIFF")

    client = TestClient(_build_app())
    response = client.post("/api/v1/tts", json={"text": "hi", "voice": "shimmer"})

    assert response.status_code == 200


def test_synthesize_rejects_unsupported_voice(monkeypatch):
    monkeypatch.setattr(tts_router.tts_service, "resolve_instructions", lambda session_id: "neutral tone")

    def _boom(text, voice, instructions):
        raise AssertionError("synthesize should not be called for invalid voice")

    monkeypatch.setattr(tts_router.tts_service, "synthesize", _boom)

    client = TestClient(_build_app())
    response = client.post("/api/v1/tts", json={"text": "hi", "voice": "not-a-real-voice"})

    assert response.status_code == 400


def test_synthesize_passes_session_id_to_resolve_instructions(monkeypatch):
    captured = {}

    def fake_resolve_instructions(session_id):
        captured["session_id"] = session_id
        return "neutral tone"

    monkeypatch.setattr(tts_router.tts_service, "resolve_instructions", fake_resolve_instructions)
    monkeypatch.setattr(tts_router.tts_service, "synthesize", lambda text, voice, instructions: b"RIFF")

    client = TestClient(_build_app())
    client.post("/api/v1/tts", json={"text": "hi", "session_id": "s1"})

    assert captured["session_id"] == "s1"
