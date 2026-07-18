import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import tts as tts_router


def _build_app():
    app = FastAPI()
    app.include_router(tts_router.router)
    app.state.tts_model = object()
    app.state.tts_lock = asyncio.Lock()
    return app


def test_synthesize_returns_wav_bytes(monkeypatch):
    monkeypatch.setattr(tts_router.tts_service, "synthesize", lambda model, text: b"RIFF....WAVEfmt ")

    client = TestClient(_build_app())
    response = client.post("/api/v1/tts", json={"text": "안녕하세요"})

    assert response.status_code == 200
    assert response.content == b"RIFF....WAVEfmt "
    assert response.headers["content-type"] == "audio/wav"
