import asyncio

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from funasr import AutoModel as FunASRAutoModel

from config import settings
from database.connection import init_db
from routers import care, chat, diary, letter, session, tts, voice
from utils.audio_converter import ensure_ffmpeg_available


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_ffmpeg_available()
    init_db()

    app.state.stt_model = FunASRAutoModel(model=settings.STT_MODEL_DIR, device="cuda:0")
    app.state.ser_model = FunASRAutoModel(model=settings.SER_MODEL_DIR, device="cuda:0")

    app.state.stt_lock = asyncio.Lock()
    app.state.ser_lock = asyncio.Lock()

    yield


app = FastAPI(title="MoongCare Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    # care/turn 응답의 X-Care-* 헤더를 브라우저 JS에서도 읽을 수 있도록 노출한다.
    # (라즈베리파이의 requests 클라이언트는 CORS의 영향을 받지 않으므로 필수는 아니지만,
    #  나중에 웹에서 같은 엔드포인트를 쓸 때를 대비해 미리 열어둔다.)
    expose_headers=["*"],
)

app.include_router(voice.router)
app.include_router(chat.router)
app.include_router(tts.router)
app.include_router(session.router)
app.include_router(diary.router)
app.include_router(letter.router)
app.include_router(care.router)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
