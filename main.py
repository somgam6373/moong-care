import asyncio
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from funasr import AutoModel as FunASRAutoModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_DIR, "CosyVoice"))
sys.path.append(os.path.join(BASE_DIR, "CosyVoice", "third_party", "Matcha-TTS"))

from cosyvoice.cli.cosyvoice import AutoModel as CosyVoiceAutoModel  # noqa: E402

from config import settings  # noqa: E402
from database.connection import init_db  # noqa: E402
from routers import chat, diary, session, tts, voice  # noqa: E402
from services.tts_service import register_moong_speaker  # noqa: E402
from utils.audio_converter import ensure_ffmpeg_available  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_ffmpeg_available()
    init_db()

    app.state.stt_model = FunASRAutoModel(model=settings.STT_MODEL_DIR, device="cuda:0")
    app.state.ser_model = FunASRAutoModel(model=settings.SER_MODEL_DIR, device="cuda:0")
    app.state.tts_model = CosyVoiceAutoModel(model_dir=settings.TTS_MODEL_DIR)
    register_moong_speaker(app.state.tts_model)

    app.state.stt_lock = asyncio.Lock()
    app.state.ser_lock = asyncio.Lock()
    app.state.tts_lock = asyncio.Lock()

    yield


app = FastAPI(title="MoongCare Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voice.router)
app.include_router(chat.router)
app.include_router(tts.router)
app.include_router(session.router)
app.include_router(diary.router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
