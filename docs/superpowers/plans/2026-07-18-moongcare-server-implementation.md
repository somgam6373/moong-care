# MoongCare Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend that powers a voice conversation with the "뭉이" character — STT + SER on each recorded turn, an OpenAI-driven reply, CosyVoice2 TTS playback, and an end-of-session diary + one-line summary saved to MySQL.

**Architecture:** One FastAPI app with model singletons (SenseVoice, emotion2vec, CosyVoice2) loaded once at startup via `lifespan`, an in-memory per-`session_id` conversation/emotion store, and MySQL only for finished diary entries. Routers are thin — they validate input, call one service function, and return a pydantic model.

**Tech Stack:** Python 3.10, FastAPI, funasr (SenseVoice + emotion2vec), CosyVoice2 (zero-shot), OpenAI Python SDK, SQLAlchemy + PyMySQL, pytest.

## Global Constraints

- Single venv, relaxed pins: install `torch==2.3.1`/`torchaudio==2.3.1` (cu121) for CosyVoice, but keep the already-installed `transformers==5.14.1` — do not downgrade to CosyVoice's pinned `4.51.3`.
- ffmpeg must be on `PATH`; server fails fast at startup if missing (`shutil.which("ffmpeg") is None`).
- DB is MySQL, local instance, host default `localhost` (demo/presentation environment, no remote DB).
- `session_id` is a client-generated UUID string sent on every request; there is no `/session/start` endpoint.
- Session state (turns + emotion sums) lives in a process-global in-memory dict (`services/emotion_session.py`); it is NOT cleared by `/session/end`, only by `/diary/generate`.
- GPU is a single 8GB card — STT/SER/TTS inference each go through their own `asyncio.Lock` on `app.state` to serialize GPU use.
- CosyVoice2-0.5B has no built-in SFT speaker; use zero-shot with a placeholder reference (`CosyVoice/asset/zero_shot_prompt.wav`) registered once at startup under `zero_shot_spk_id="moong"`. Swap the file later when a real "뭉이" voice sample exists.
- All response/request shapes match `docs/superpowers/specs/2026-07-18-moongcare-server-design.md`.

---

## File Structure

```
moongcare-server/
├── main.py                        # FastAPI app, lifespan model loading, router registration
├── config.py                      # pydantic-settings Settings
├── .env.example
├── requirements.txt
├── routers/
│   ├── __init__.py
│   ├── voice.py                   # POST /api/v1/voice/analyze
│   ├── chat.py                    # POST /api/v1/chat/reply
│   ├── tts.py                     # POST /api/v1/tts
│   ├── session.py                 # POST /api/v1/session/end
│   └── diary.py                   # POST /api/v1/diary/generate
├── services/
│   ├── __init__.py
│   ├── stt_service.py
│   ├── ser_service.py
│   ├── voice_service.py
│   ├── tts_service.py
│   ├── openai_client.py
│   ├── chat_service.py
│   ├── diary_service.py
│   ├── summary_service.py
│   └── emotion_session.py
├── models/
│   ├── __init__.py
│   ├── voice.py
│   ├── chat.py
│   ├── tts.py
│   ├── diary.py
│   └── emotion.py
├── database/
│   ├── __init__.py
│   ├── connection.py
│   └── diary_repository.py
├── utils/
│   ├── __init__.py
│   ├── audio_converter.py
│   └── text_parser.py
├── tests/
│   ├── __init__.py
│   ├── test_main_health.py
│   ├── test_text_parser.py
│   ├── test_audio_converter.py
│   ├── test_models.py
│   ├── test_diary_repository.py
│   ├── test_emotion_session.py
│   ├── test_ser_service.py
│   ├── test_stt_service.py
│   ├── test_voice_service.py
│   ├── test_tts_service.py
│   ├── test_chat_service.py
│   ├── test_diary_service.py
│   ├── test_summary_service.py
│   ├── test_voice_router.py
│   ├── test_chat_router.py
│   ├── test_tts_router.py
│   ├── test_session_router.py
│   └── test_diary_router.py
├── scripts/
│   └── manual_e2e_check.md
└── temp/                           # already exists (has .gitkeep)
```

Router tests build their own minimal `FastAPI()` app with just the router under test included (not `from main import app`), so they never trigger `main.py`'s real GPU model loading. `main.py`'s lifespan is only exercised manually in Task 19/20.

---

### Task 1: Environment setup (torch/CosyVoice deps, ffmpeg)

**Files:**
- Create: `requirements.txt`

**Interfaces:**
- Produces: a working venv with `torch`, `torchaudio`, CosyVoice's non-conflicting deps, and `ffmpeg` on `PATH`. All later tasks assume this.

- [ ] **Step 1: Install torch/torchaudio (cu121) into the existing venv**

Run (PowerShell, venv activated):
```
.venv\Scripts\pip install torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121
```
Expected: install succeeds, no dependency resolution error.

- [ ] **Step 2: Verify CUDA is visible to torch**

Run:
```
.venv\Scripts\python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```
Expected output: `2.3.1+cu121 True`

- [ ] **Step 3: Write `requirements.txt`**

```
fastapi
uvicorn[standard]
python-multipart
pydantic-settings
python-dotenv
sqlalchemy
pymysql
cryptography
openai
funasr
modelscope
torch==2.3.1
torchaudio==2.3.1
onnxruntime==1.18.0
HyperPyYAML==1.2.3
conformer==0.3.2
diffusers==0.29.0
lightning==2.2.4
inflect==7.3.1
wetext==0.0.4
gdown==5.1.0
x-transformers==2.11.24
pytest
```

- [ ] **Step 4: Install remaining requirements**

Run:
```
.venv\Scripts\pip install -r requirements.txt
```
Expected: install succeeds. `transformers` stays at `5.14.1` (not in this file, so pip won't touch it).

- [ ] **Step 5: Verify funasr and CosyVoice import cleanly**

Run:
```
.venv\Scripts\python -c "from funasr import AutoModel; print('funasr ok')"
.venv\Scripts\python -c "import sys; sys.path.append('CosyVoice'); sys.path.append('CosyVoice/third_party/Matcha-TTS'); from cosyvoice.cli.cosyvoice import AutoModel; print('cosyvoice ok')"
```
Expected: both print their `ok` line with no `ImportError`.

- [ ] **Step 6: Install ffmpeg and verify it's on PATH**

Run:
```
winget install --id Gyan.FFmpeg -e
```
Restart the shell, then run:
```
ffmpeg -version
```
Expected: version banner prints (no "not recognized" error).

- [ ] **Step 7: Commit**

```bash
git add requirements.txt
git commit -m "chore: pin dependencies for torch/CosyVoice stack"
```

---

### Task 2: Project scaffolding — config, .env.example, health-check main.py

**Files:**
- Create: `config.py`
- Create: `.env.example`
- Create: `main.py`
- Create: `tests/__init__.py`
- Create: `tests/test_main_health.py`

**Interfaces:**
- Produces: `config.settings` (a `Settings` instance) with fields `OPENAI_API_KEY`, `OPENAI_MODEL`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`, `STT_MODEL_DIR`, `SER_MODEL_DIR`, `TTS_MODEL_DIR`. Every later task that needs config imports `from config import settings`.

- [ ] **Step 1: Write `config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "moongcare"

    STT_MODEL_DIR: str = "iic/SenseVoiceSmall"
    SER_MODEL_DIR: str = "iic/emotion2vec_plus_large"
    TTS_MODEL_DIR: str = "pretrained_models/CosyVoice2-0.5B"

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **Step 2: Write `.env.example`**

```
OPENAI_API_KEY=sk-xxxx
OPENAI_MODEL=gpt-4o-mini
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DB=moongcare
STT_MODEL_DIR=iic/SenseVoiceSmall
SER_MODEL_DIR=iic/emotion2vec_plus_large
TTS_MODEL_DIR=pretrained_models/CosyVoice2-0.5B
```

- [ ] **Step 3: Write `tests/__init__.py`** (empty file)

- [ ] **Step 4: Write the failing test `tests/test_main_health.py`**

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 5: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_main_health.py -v`
Expected: FAIL — `main.py` does not exist yet (`ModuleNotFoundError`).

- [ ] **Step 6: Write minimal `main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="MoongCare Server")


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_main_health.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add config.py .env.example main.py tests/__init__.py tests/test_main_health.py
git commit -m "feat: add config, health check endpoint, and test scaffolding"
```

---

### Task 3: `utils/text_parser.py` — SenseVoice tag stripping

**Files:**
- Create: `utils/__init__.py`
- Create: `utils/text_parser.py`
- Test: `tests/test_text_parser.py`

**Interfaces:**
- Produces: `strip_sensevoice_tags(raw: str) -> str`. Used by `services/stt_service.py` (Task 9).

- [ ] **Step 1: Write `utils/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test**

```python
from utils.text_parser import strip_sensevoice_tags


def test_strip_sensevoice_tags_removes_all_tags():
    raw = "<|ko|><|NEUTRAL|><|Speech|><|woitn|>오늘 발표가 잘 됐어요"
    assert strip_sensevoice_tags(raw) == "오늘 발표가 잘 됐어요"


def test_strip_sensevoice_tags_handles_no_tags():
    assert strip_sensevoice_tags("안녕하세요") == "안녕하세요"


def test_strip_sensevoice_tags_handles_empty_string():
    assert strip_sensevoice_tags("") == ""
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_text_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.text_parser'`

- [ ] **Step 4: Write `utils/text_parser.py`**

```python
import re

_TAG_RE = re.compile(r"<\|.*?\|>")


def strip_sensevoice_tags(raw: str) -> str:
    return _TAG_RE.sub("", raw).strip()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_text_parser.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add utils/__init__.py utils/text_parser.py tests/test_text_parser.py
git commit -m "feat: add SenseVoice tag stripping util"
```

---

### Task 4: `utils/audio_converter.py` — webm→wav via ffmpeg

**Files:**
- Create: `utils/audio_converter.py`
- Test: `tests/test_audio_converter.py`

**Interfaces:**
- Consumes: ffmpeg on `PATH` (Task 1).
- Produces: `ensure_ffmpeg_available() -> None` (raises `RuntimeError` if missing) and `webm_to_wav(input_path: str, output_path: str) -> None`. Used by `main.py` (Task 19, startup check) and `routers/voice.py` (Task 14).

- [ ] **Step 1: Write the failing test**

```python
import os
import subprocess

import pytest
import soundfile as sf

from utils.audio_converter import ensure_ffmpeg_available, webm_to_wav


@pytest.fixture(scope="module")
def sample_webm(tmp_path_factory):
    out = tmp_path_factory.mktemp("audio") / "sample.webm"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
         "-t", "1", "-c:a", "libopus", str(out)],
        check=True, capture_output=True,
    )
    return str(out)


def test_ensure_ffmpeg_available_does_not_raise():
    ensure_ffmpeg_available()


def test_webm_to_wav_converts_to_16k_mono(sample_webm, tmp_path):
    out_path = str(tmp_path / "sample.wav")
    webm_to_wav(sample_webm, out_path)

    assert os.path.exists(out_path)
    info = sf.info(out_path)
    assert info.samplerate == 16000
    assert info.channels == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_audio_converter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.audio_converter'`

- [ ] **Step 3: Write `utils/audio_converter.py`**

```python
import shutil
import subprocess


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install ffmpeg and add it to PATH before starting the server."
        )


def webm_to_wav(input_path: str, output_path: str) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr.decode(errors='ignore')}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_audio_converter.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add utils/audio_converter.py tests/test_audio_converter.py
git commit -m "feat: add webm to wav conversion util"
```

---

### Task 5: `models/` — pydantic request/response schemas

**Files:**
- Create: `models/__init__.py`
- Create: `models/voice.py`
- Create: `models/chat.py`
- Create: `models/tts.py`
- Create: `models/emotion.py`
- Create: `models/diary.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `VoiceAnalyzeResponse{transcript, emotions}`, `ChatReplyRequest{session_id, transcript, emotions}` / `ChatReplyResponse{reply_text}`, `TTSRequest{text}`, `SessionEndRequest{session_id}` / `SessionEndResponse{dominant_emotion, average_emotions}`, `DiaryGenerateRequest{session_id}` / `DiaryGenerateResponse{diary_id, diary_text, summary, dominant_emotion}`. Used by every router (Tasks 14–18).

- [ ] **Step 1: Write `models/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test**

```python
from models.voice import VoiceAnalyzeResponse
from models.chat import ChatReplyRequest, ChatReplyResponse
from models.tts import TTSRequest
from models.emotion import SessionEndRequest, SessionEndResponse
from models.diary import DiaryGenerateRequest, DiaryGenerateResponse


def test_voice_analyze_response_roundtrip():
    resp = VoiceAnalyzeResponse(transcript="안녕", emotions={"happy": 0.5, "neutral": 0.5})
    assert resp.model_dump() == {"transcript": "안녕", "emotions": {"happy": 0.5, "neutral": 0.5}}


def test_chat_reply_models():
    req = ChatReplyRequest(session_id="s1", transcript="안녕", emotions={"happy": 1.0})
    assert req.session_id == "s1"
    resp = ChatReplyResponse(reply_text="반가워")
    assert resp.reply_text == "반가워"


def test_tts_request():
    assert TTSRequest(text="hello").text == "hello"


def test_session_end_models():
    req = SessionEndRequest(session_id="s1")
    resp = SessionEndResponse(dominant_emotion="happy", average_emotions={"happy": 0.9})
    assert req.session_id == "s1"
    assert resp.dominant_emotion == "happy"


def test_diary_models():
    req = DiaryGenerateRequest(session_id="s1")
    resp = DiaryGenerateResponse(diary_id=1, diary_text="오늘은...", summary="좋은 하루", dominant_emotion="happy")
    assert req.session_id == "s1"
    assert resp.diary_id == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.voice'`

- [ ] **Step 4: Write `models/voice.py`**

```python
from pydantic import BaseModel


class VoiceAnalyzeResponse(BaseModel):
    transcript: str
    emotions: dict[str, float]
```

- [ ] **Step 5: Write `models/chat.py`**

```python
from pydantic import BaseModel


class ChatReplyRequest(BaseModel):
    session_id: str
    transcript: str
    emotions: dict[str, float]


class ChatReplyResponse(BaseModel):
    reply_text: str
```

- [ ] **Step 6: Write `models/tts.py`**

```python
from pydantic import BaseModel


class TTSRequest(BaseModel):
    text: str
```

- [ ] **Step 7: Write `models/emotion.py`**

```python
from pydantic import BaseModel


class SessionEndRequest(BaseModel):
    session_id: str


class SessionEndResponse(BaseModel):
    dominant_emotion: str
    average_emotions: dict[str, float]
```

- [ ] **Step 8: Write `models/diary.py`**

```python
from pydantic import BaseModel


class DiaryGenerateRequest(BaseModel):
    session_id: str


class DiaryGenerateResponse(BaseModel):
    diary_id: int
    diary_text: str
    summary: str
    dominant_emotion: str
```

- [ ] **Step 9: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_models.py -v`
Expected: PASS (5 passed)

- [ ] **Step 10: Commit**

```bash
git add models/ tests/test_models.py
git commit -m "feat: add pydantic request/response schemas"
```

---

### Task 6: `database/connection.py` + `database/diary_repository.py`

**Files:**
- Create: `database/__init__.py`
- Create: `database/connection.py`
- Create: `database/diary_repository.py`
- Test: `tests/test_diary_repository.py`

**Interfaces:**
- Consumes: `config.settings` (Task 2).
- Produces: `Base`, `engine`, `SessionLocal`, `init_db() -> None`, `get_db()` (FastAPI dependency generator) from `connection.py`; `Diary` model + `save_diary(db, session_id, diary_text, summary, dominant_emotion, average_emotions) -> Diary` + `get_diary(db, diary_id) -> Diary | None` from `diary_repository.py`. Used by `routers/diary.py` (Task 18) and `main.py` (Task 19).

- [ ] **Step 1: Write `database/__init__.py`** (empty file)

- [ ] **Step 2: Write `database/connection.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import settings

engine = create_engine(
    f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
    f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}"
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def init_db() -> None:
    from database import diary_repository  # noqa: F401  (registers Diary model)
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: Write the failing test**

```python
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database.diary_repository import save_diary, get_diary


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)
    session = TestSessionLocal()
    yield session
    session.close()


def test_save_and_get_diary(db_session):
    diary = save_diary(
        db_session,
        session_id="s1",
        diary_text="오늘은 좋은 하루였다.",
        summary="좋은 하루",
        dominant_emotion="happy",
        average_emotions={"happy": 0.7, "neutral": 0.3},
    )
    assert diary.id is not None

    fetched = get_diary(db_session, diary.id)
    assert fetched is not None
    assert fetched.session_id == "s1"
    assert json.loads(fetched.average_emotions) == {"happy": 0.7, "neutral": 0.3}


def test_get_diary_returns_none_for_missing_id(db_session):
    assert get_diary(db_session, 999) is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_diary_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'database.diary_repository'`

- [ ] **Step 5: Write `database/diary_repository.py`**

```python
import json
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import Session

from database.connection import Base


class Diary(Base):
    __tablename__ = "diaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False)
    diary_text = Column(Text, nullable=False)
    summary = Column(String(255), nullable=False)
    dominant_emotion = Column(String(32), nullable=False)
    average_emotions = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def save_diary(
    db: Session,
    session_id: str,
    diary_text: str,
    summary: str,
    dominant_emotion: str,
    average_emotions: dict[str, float],
) -> Diary:
    diary = Diary(
        session_id=session_id,
        diary_text=diary_text,
        summary=summary,
        dominant_emotion=dominant_emotion,
        average_emotions=json.dumps(average_emotions),
    )
    db.add(diary)
    db.commit()
    db.refresh(diary)
    return diary


def get_diary(db: Session, diary_id: int) -> Diary | None:
    return db.get(Diary, diary_id)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_diary_repository.py -v`
Expected: PASS (2 passed)

- [ ] **Step 7: Commit**

```bash
git add database/ tests/test_diary_repository.py
git commit -m "feat: add MySQL connection and diary repository"
```

---

### Task 7: `services/emotion_session.py` — in-memory session store

**Files:**
- Create: `services/__init__.py`
- Create: `services/emotion_session.py`
- Test: `tests/test_emotion_session.py`

**Interfaces:**
- Produces: `EMOTION_CLASSES: list[str]`, `TurnRecord(role, text, emotions)` dataclass, `SessionState` (`.turns`, `.emotion_sums`, `.turn_count`), `SESSIONS: dict[str, SessionState]`, `add_user_turn(session_id, transcript, emotions) -> None`, `add_assistant_turn(session_id, reply_text) -> None`, `get_session(session_id) -> SessionState | None`, `compute_average(session_id) -> tuple[str, dict[str, float]]` (raises `KeyError` if session missing or has 0 turns), `clear_session(session_id) -> None`. Used by every router (Tasks 14–18) and by `chat_service`/`diary_service` (Tasks 12–13) via the `TurnRecord` type.

- [ ] **Step 1: Write `services/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test**

```python
import pytest

from services.emotion_session import (
    add_user_turn, add_assistant_turn, get_session,
    compute_average, clear_session, SESSIONS,
)


@pytest.fixture(autouse=True)
def clean_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def test_add_user_turn_accumulates_emotions():
    add_user_turn("s1", "안녕", {"happy": 0.8, "sad": 0.2})
    add_user_turn("s1", "잘가", {"happy": 0.4, "sad": 0.6})

    session = get_session("s1")
    assert session.turn_count == 2
    assert session.emotion_sums["happy"] == pytest.approx(1.2)
    assert session.emotion_sums["sad"] == pytest.approx(0.8)


def test_add_assistant_turn_does_not_affect_emotion_sums():
    add_user_turn("s1", "안녕", {"happy": 1.0})
    add_assistant_turn("s1", "반가워!")

    session = get_session("s1")
    assert len(session.turns) == 2
    assert session.turns[1].role == "assistant"
    assert session.emotion_sums["happy"] == pytest.approx(1.0)


def test_compute_average_returns_dominant_and_average():
    add_user_turn("s1", "t1", {"happy": 0.8, "sad": 0.2, "neutral": 0.0})
    add_user_turn("s1", "t2", {"happy": 0.4, "sad": 0.6, "neutral": 0.0})

    dominant, average = compute_average("s1")
    assert dominant == "happy"
    assert average["happy"] == pytest.approx(0.6)
    assert average["sad"] == pytest.approx(0.4)


def test_compute_average_missing_session_raises_keyerror():
    with pytest.raises(KeyError):
        compute_average("does-not-exist")


def test_clear_session_removes_state():
    add_user_turn("s1", "t1", {"happy": 1.0})
    clear_session("s1")
    assert get_session("s1") is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_emotion_session.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.emotion_session'`

- [ ] **Step 4: Write `services/emotion_session.py`**

```python
from dataclasses import dataclass

EMOTION_CLASSES = [
    "angry", "disgusted", "fearful", "happy",
    "neutral", "other", "sad", "surprised", "unknown",
]


@dataclass
class TurnRecord:
    role: str  # "user" or "assistant"
    text: str
    emotions: dict[str, float] | None = None


class SessionState:
    def __init__(self) -> None:
        self.turns: list[TurnRecord] = []
        self.emotion_sums: dict[str, float] = {c: 0.0 for c in EMOTION_CLASSES}
        self.turn_count: int = 0


SESSIONS: dict[str, SessionState] = {}


def _get_or_create(session_id: str) -> SessionState:
    if session_id not in SESSIONS:
        SESSIONS[session_id] = SessionState()
    return SESSIONS[session_id]


def add_user_turn(session_id: str, transcript: str, emotions: dict[str, float]) -> None:
    state = _get_or_create(session_id)
    state.turns.append(TurnRecord(role="user", text=transcript, emotions=emotions))
    for cls in EMOTION_CLASSES:
        state.emotion_sums[cls] += emotions.get(cls, 0.0)
    state.turn_count += 1


def add_assistant_turn(session_id: str, reply_text: str) -> None:
    state = _get_or_create(session_id)
    state.turns.append(TurnRecord(role="assistant", text=reply_text, emotions=None))


def get_session(session_id: str) -> SessionState | None:
    return SESSIONS.get(session_id)


def compute_average(session_id: str) -> tuple[str, dict[str, float]]:
    state = SESSIONS.get(session_id)
    if state is None or state.turn_count == 0:
        raise KeyError(session_id)
    average = {cls: state.emotion_sums[cls] / state.turn_count for cls in EMOTION_CLASSES}
    dominant = max(average, key=average.get)
    return dominant, average


def clear_session(session_id: str) -> None:
    SESSIONS.pop(session_id, None)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_emotion_session.py -v`
Expected: PASS (5 passed)

- [ ] **Step 6: Commit**

```bash
git add services/__init__.py services/emotion_session.py tests/test_emotion_session.py
git commit -m "feat: add in-memory session/emotion accumulation store"
```

---

### Task 8: `services/ser_service.py` — emotion2vec wrapper

**Files:**
- Create: `services/ser_service.py`
- Test: `tests/test_ser_service.py`

**Interfaces:**
- Produces: `parse_emotion2vec_output(raw_result: list[dict]) -> dict[str, float]`, `analyze_emotion(model, wav_path: str) -> dict[str, float]`. Used by `services/voice_service.py` (Task 10).
- Real emotion2vec output shape (funasr `AutoModel.generate(wav_path, granularity="utterance", extract_embedding=False)`): `[{"key": ..., "labels": ["生气/angry", "开心/happy", ..., "<unk>"], "scores": [0.05, 0.65, ...]}]`.

- [ ] **Step 1: Write the failing test**

```python
from services.ser_service import parse_emotion2vec_output, analyze_emotion


def test_parse_emotion2vec_output_maps_labels_to_english():
    raw_result = [{
        "key": "sample",
        "labels": ["生气/angry", "开心/happy", "中立/neutral", "<unk>"],
        "scores": [0.05, 0.65, 0.20, 0.10],
    }]
    emotions = parse_emotion2vec_output(raw_result)
    assert emotions == {"angry": 0.05, "happy": 0.65, "neutral": 0.20, "unknown": 0.10}


class _FakeSERModel:
    def generate(self, wav_path, granularity, extract_embedding):
        return [{
            "labels": ["开心/happy", "中立/neutral"],
            "scores": [0.7, 0.3],
        }]


def test_analyze_emotion_calls_model_and_parses_result():
    emotions = analyze_emotion(_FakeSERModel(), "dummy.wav")
    assert emotions == {"happy": 0.7, "neutral": 0.3}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_ser_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.ser_service'`

- [ ] **Step 3: Write `services/ser_service.py`**

```python
def parse_emotion2vec_output(raw_result: list[dict]) -> dict[str, float]:
    labels = raw_result[0]["labels"]
    scores = raw_result[0]["scores"]
    emotions: dict[str, float] = {}
    for label, score in zip(labels, scores):
        key = label.split("/")[-1] if "/" in label else "unknown"
        emotions[key] = float(score)
    return emotions


def analyze_emotion(model, wav_path: str) -> dict[str, float]:
    raw_result = model.generate(wav_path, granularity="utterance", extract_embedding=False)
    return parse_emotion2vec_output(raw_result)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_ser_service.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add services/ser_service.py tests/test_ser_service.py
git commit -m "feat: add emotion2vec SER wrapper"
```

---

### Task 9: `services/stt_service.py` — SenseVoice wrapper

**Files:**
- Create: `services/stt_service.py`
- Test: `tests/test_stt_service.py`

**Interfaces:**
- Consumes: `strip_sensevoice_tags` from `utils/text_parser.py` (Task 3).
- Produces: `transcribe(model, wav_path: str) -> str`. Used by `services/voice_service.py` (Task 10).

- [ ] **Step 1: Write the failing test**

```python
from services.stt_service import transcribe


class _FakeSTTModel:
    def generate(self, input, cache, language, use_itn):
        return [{"text": "<|ko|><|NEUTRAL|><|Speech|><|woitn|>오늘 발표가 잘 됐어요"}]


def test_transcribe_strips_tags():
    text = transcribe(_FakeSTTModel(), "dummy.wav")
    assert text == "오늘 발표가 잘 됐어요"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_stt_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.stt_service'`

- [ ] **Step 3: Write `services/stt_service.py`**

```python
from utils.text_parser import strip_sensevoice_tags


def transcribe(model, wav_path: str) -> str:
    raw_result = model.generate(input=wav_path, cache={}, language="auto", use_itn=True)
    raw_text = raw_result[0]["text"]
    return strip_sensevoice_tags(raw_text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_stt_service.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add services/stt_service.py tests/test_stt_service.py
git commit -m "feat: add SenseVoice STT wrapper"
```

---

### Task 10: `services/voice_service.py` — parallel STT + SER

**Files:**
- Create: `services/voice_service.py`
- Test: `tests/test_voice_service.py`

**Interfaces:**
- Consumes: `services.stt_service.transcribe`, `services.ser_service.analyze_emotion` (Tasks 8–9). Expects an `app_state` object with `.stt_model`, `.ser_model`, `.stt_lock` (`asyncio.Lock`), `.ser_lock` (`asyncio.Lock`) — this matches `FastAPI().state` shape set up in `main.py` (Task 19).
- Produces: `async def analyze_voice(app_state, wav_path: str) -> tuple[str, dict[str, float]]`. Used by `routers/voice.py` (Task 14).

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_voice_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.voice_service'`

- [ ] **Step 3: Write `services/voice_service.py`**

```python
import asyncio

from fastapi.concurrency import run_in_threadpool

from services import ser_service, stt_service


async def analyze_voice(app_state, wav_path: str) -> tuple[str, dict[str, float]]:
    async def run_stt():
        async with app_state.stt_lock:
            return await run_in_threadpool(stt_service.transcribe, app_state.stt_model, wav_path)

    async def run_ser():
        async with app_state.ser_lock:
            return await run_in_threadpool(ser_service.analyze_emotion, app_state.ser_model, wav_path)

    transcript, emotions = await asyncio.gather(run_stt(), run_ser())
    return transcript, emotions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_voice_service.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add services/voice_service.py tests/test_voice_service.py
git commit -m "feat: run STT and SER in parallel with GPU locks"
```

---

### Task 11: `services/tts_service.py` — CosyVoice2 zero-shot wrapper

**Files:**
- Create: `services/tts_service.py`
- Test: `tests/test_tts_service.py`

**Interfaces:**
- Produces: `SPK_ID = "moong"`, `register_moong_speaker(tts_model) -> None`, `synthesize(tts_model, text: str) -> bytes` (WAV bytes). Used by `main.py` (Task 19, calls `register_moong_speaker` at startup) and `routers/tts.py` (Task 16).

- [ ] **Step 1: Write the failing test**

```python
import torch

from services.tts_service import synthesize, register_moong_speaker


class _FakeTTSModel:
    sample_rate = 16000

    def inference_zero_shot(self, text, prompt_text, prompt_wav, zero_shot_spk_id):
        yield {"tts_speech": torch.zeros(1, 1600)}

    def add_zero_shot_spk(self, prompt_text, prompt_wav, spk_id):
        self.registered_spk_id = spk_id
        return True

    def save_spkinfo(self):
        self.saved = True


def test_synthesize_returns_wav_bytes():
    audio_bytes = synthesize(_FakeTTSModel(), "안녕하세요")
    assert isinstance(audio_bytes, bytes)
    assert audio_bytes[:4] == b"RIFF"


def test_register_moong_speaker_calls_add_and_save():
    model = _FakeTTSModel()
    register_moong_speaker(model)
    assert model.registered_spk_id == "moong"
    assert model.saved is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_tts_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.tts_service'`

- [ ] **Step 3: Write `services/tts_service.py`**

```python
import io
import os

import torchaudio

SPK_ID = "moong"
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACEHOLDER_PROMPT_WAV = os.path.join(_BASE_DIR, "CosyVoice", "asset", "zero_shot_prompt.wav")
PLACEHOLDER_PROMPT_TEXT = "希望你以后能够做的比我还好呦。"


def register_moong_speaker(tts_model) -> None:
    tts_model.add_zero_shot_spk(PLACEHOLDER_PROMPT_TEXT, PLACEHOLDER_PROMPT_WAV, SPK_ID)
    tts_model.save_spkinfo()


def synthesize(tts_model, text: str) -> bytes:
    for result in tts_model.inference_zero_shot(text, "", "", zero_shot_spk_id=SPK_ID):
        buffer = io.BytesIO()
        torchaudio.save(buffer, result["tts_speech"], tts_model.sample_rate, format="wav")
        return buffer.getvalue()
    raise RuntimeError("TTS produced no audio output")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_tts_service.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add services/tts_service.py tests/test_tts_service.py
git commit -m "feat: add CosyVoice2 zero-shot TTS wrapper"
```

---

### Task 12: `services/openai_client.py` + `services/chat_service.py`

**Files:**
- Create: `services/openai_client.py`
- Create: `services/chat_service.py`
- Test: `tests/test_chat_service.py`

**Interfaces:**
- Consumes: `config.settings` (Task 2), `services.emotion_session.TurnRecord` (Task 7).
- Produces: `get_client() -> OpenAI` (from `openai_client.py`, reused by Task 13); `build_messages(history: list[TurnRecord], transcript: str, emotions: dict[str, float]) -> list[dict]`, `get_reply(history, transcript, emotions) -> str` (from `chat_service.py`). Used by `routers/chat.py` (Task 15).

- [ ] **Step 1: Write `services/openai_client.py`**

```python
from openai import OpenAI

from config import settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client
```

- [ ] **Step 2: Write the failing test**

```python
from types import SimpleNamespace

from services import chat_service
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


def test_build_messages_includes_history_and_current_emotion():
    history = [TurnRecord(role="user", text="안녕", emotions={"happy": 1.0})]
    messages = chat_service.build_messages(history, "오늘 힘들었어", {"sad": 0.8, "neutral": 0.2})

    assert messages[0]["role"] == "system"
    assert messages[1] == {"role": "user", "content": "안녕"}
    assert "sad" in messages[-1]["content"]
    assert "오늘 힘들었어" in messages[-1]["content"]


def test_get_reply_calls_openai_client_and_returns_text(monkeypatch):
    fake_client = _FakeClient("힘든 하루였겠다, 오늘도 애썼어.")
    monkeypatch.setattr(chat_service, "get_client", lambda: fake_client)

    reply = chat_service.get_reply([], "오늘 힘들었어", {"sad": 0.8})

    assert reply == "힘든 하루였겠다, 오늘도 애썼어."
    assert fake_client.chat.completions.last_messages[-1]["content"].endswith("오늘 힘들었어")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_chat_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.chat_service'`

- [ ] **Step 4: Write `services/chat_service.py`**

```python
from services.emotion_session import TurnRecord
from services.openai_client import get_client
from config import settings

MOONG_SYSTEM_PROMPT = (
    "너는 '뭉이'라는 이름의 따뜻하고 다정한 감정 케어 캐릭터야. "
    "사용자의 하루 이야기를 들어주고 공감하며, 짧고 자연스러운 구어체로 응답해. "
    "사용자의 현재 감정 상태를 참고해서 그 감정에 맞는 위로나 반응을 보여줘. "
    "한 번에 2~3문장 이내로 짧게 대답해."
)


def build_messages(
    history: list[TurnRecord], transcript: str, emotions: dict[str, float]
) -> list[dict]:
    messages = [{"role": "system", "content": MOONG_SYSTEM_PROMPT}]
    for turn in history:
        role = "user" if turn.role == "user" else "assistant"
        messages.append({"role": role, "content": turn.text})
    dominant = max(emotions, key=emotions.get) if emotions else "neutral"
    messages.append({
        "role": "user",
        "content": f"[현재 감정: {dominant}] {transcript}",
    })
    return messages


def get_reply(history: list[TurnRecord], transcript: str, emotions: dict[str, float]) -> str:
    client = get_client()
    messages = build_messages(history, transcript, emotions)
    response = client.chat.completions.create(model=settings.OPENAI_MODEL, messages=messages)
    return response.choices[0].message.content
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_chat_service.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add services/openai_client.py services/chat_service.py tests/test_chat_service.py
git commit -m "feat: add OpenAI-backed chat reply service"
```

---

### Task 13: `services/diary_service.py` + `services/summary_service.py`

**Files:**
- Create: `services/diary_service.py`
- Create: `services/summary_service.py`
- Test: `tests/test_diary_service.py`
- Test: `tests/test_summary_service.py`

**Interfaces:**
- Consumes: `services.openai_client.get_client` (Task 12), `services.emotion_session.TurnRecord` (Task 7), `config.settings` (Task 2).
- Produces: `generate_diary(history: list[TurnRecord], average_emotions: dict[str, float]) -> str`, `summarize_diary(diary_text: str) -> str`. Used by `routers/diary.py` (Task 18).

- [ ] **Step 1: Write the failing test for diary generation**

```python
from types import SimpleNamespace

from services import diary_service
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


def test_generate_diary_includes_conversation_and_emotion(monkeypatch):
    fake_client = _FakeClient("오늘은 발표를 해서 뿌듯했다.")
    monkeypatch.setattr(diary_service, "get_client", lambda: fake_client)

    history = [
        TurnRecord(role="user", text="오늘 발표가 잘 됐어요", emotions={"happy": 0.8}),
        TurnRecord(role="assistant", text="정말 잘했네!", emotions=None),
    ]
    diary_text = diary_service.generate_diary(history, {"happy": 0.8, "neutral": 0.2})

    assert diary_text == "오늘은 발표를 해서 뿌듯했다."
    sent_prompt = fake_client.chat.completions.last_messages[-1]["content"]
    assert "오늘 발표가 잘 됐어요" in sent_prompt
    assert "happy" in sent_prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_diary_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.diary_service'`

- [ ] **Step 3: Write `services/diary_service.py`**

```python
from services.emotion_session import TurnRecord
from services.openai_client import get_client
from config import settings

DIARY_SYSTEM_PROMPT = (
    "너는 사용자 본인이 되어 오늘 하루를 되돌아보는 1인칭 일기를 쓰는 작가야. "
    "아래 대화 내용과 감정 데이터를 참고해서, 사용자가 직접 쓴 것처럼 자연스러운 "
    "1인칭 일기를 3~5문장으로 작성해."
)


def _format_conversation(history: list[TurnRecord]) -> str:
    lines = []
    for turn in history:
        speaker = "나" if turn.role == "user" else "뭉이"
        lines.append(f"{speaker}: {turn.text}")
    return "\n".join(lines)


def generate_diary(history: list[TurnRecord], average_emotions: dict[str, float]) -> str:
    client = get_client()
    conversation = _format_conversation(history)
    dominant = max(average_emotions, key=average_emotions.get) if average_emotions else "neutral"
    user_prompt = (
        f"오늘의 대화:\n{conversation}\n\n"
        f"오늘의 대표 감정: {dominant}\n"
        f"감정 평균 점수: {average_emotions}"
    )
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": DIARY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_diary_service.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Write the failing test for summary generation**

```python
from types import SimpleNamespace

from services import summary_service


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


def test_summarize_diary_returns_one_line(monkeypatch):
    fake_client = _FakeClient("발표를 성공적으로 마쳐서 뿌듯한 하루였다.")
    monkeypatch.setattr(summary_service, "get_client", lambda: fake_client)

    summary = summary_service.summarize_diary("오늘은 발표를 해서 뿌듯했다. 친구들도 칭찬해줬다.")

    assert summary == "발표를 성공적으로 마쳐서 뿌듯한 하루였다."
    assert fake_client.chat.completions.last_messages[-1]["content"] == "오늘은 발표를 해서 뿌듯했다. 친구들도 칭찬해줬다."
```

- [ ] **Step 6: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_summary_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.summary_service'`

- [ ] **Step 7: Write `services/summary_service.py`**

```python
from services.openai_client import get_client
from config import settings

SUMMARY_SYSTEM_PROMPT = "아래 일기를 한 문장으로 요약해. 반드시 한 줄로만 답해."


def summarize_diary(diary_text: str) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": diary_text},
        ],
    )
    return response.choices[0].message.content
```

- [ ] **Step 8: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_summary_service.py -v`
Expected: PASS (1 passed)

- [ ] **Step 9: Commit**

```bash
git add services/diary_service.py services/summary_service.py tests/test_diary_service.py tests/test_summary_service.py
git commit -m "feat: add OpenAI-backed diary and summary generation"
```

---

### Task 14: `routers/voice.py` — POST /api/v1/voice/analyze

**Files:**
- Create: `routers/__init__.py`
- Create: `routers/voice.py`
- Test: `tests/test_voice_router.py`

**Interfaces:**
- Consumes: `services.voice_service.analyze_voice` (Task 10), `services.emotion_session.add_user_turn` (Task 7), `utils.audio_converter.webm_to_wav` (Task 4), `models.voice.VoiceAnalyzeResponse` (Task 5).
- Produces: `router = APIRouter(...)` with `POST /api/v1/voice/analyze` accepting multipart form (`session_id: str`, `audio: UploadFile`), returning `VoiceAnalyzeResponse`. Registered in `main.py` (Task 19).

- [ ] **Step 1: Write `routers/__init__.py`** (empty file)

- [ ] **Step 2: Write the failing test**

```python
import io

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import voice as voice_router
from services import emotion_session


def _build_app():
    app = FastAPI()
    app.include_router(voice_router.router)
    return app


def test_analyze_endpoint_returns_transcript_and_emotions(monkeypatch):
    emotion_session.SESSIONS.clear()
    monkeypatch.setattr(voice_router, "webm_to_wav", lambda src, dst: open(dst, "wb").close())

    async def fake_analyze_voice(app_state, wav_path):
        return "오늘 발표가 잘 됐어요", {"happy": 0.65, "sad": 0.10, "neutral": 0.20, "angry": 0.05}

    monkeypatch.setattr(voice_router.voice_service, "analyze_voice", fake_analyze_voice)

    client = TestClient(_build_app())
    response = client.post(
        "/api/v1/voice/analyze",
        data={"session_id": "s1"},
        files={"audio": ("test.webm", io.BytesIO(b"fake webm bytes"), "audio/webm")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "오늘 발표가 잘 됐어요"
    assert body["emotions"]["happy"] == 0.65
    assert emotion_session.get_session("s1").turn_count == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_voice_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'routers.voice'`

- [ ] **Step 4: Write `routers/voice.py`**

```python
import os
import uuid

from fastapi import APIRouter, Form, Request, UploadFile

from models.voice import VoiceAnalyzeResponse
from services import emotion_session, voice_service
from utils.audio_converter import webm_to_wav

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])

TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp")


@router.post("/analyze", response_model=VoiceAnalyzeResponse)
async def analyze(request: Request, session_id: str = Form(...), audio: UploadFile = None):
    file_id = uuid.uuid4().hex
    webm_path = os.path.join(TEMP_DIR, f"{file_id}.webm")
    wav_path = os.path.join(TEMP_DIR, f"{file_id}.wav")

    with open(webm_path, "wb") as f:
        f.write(await audio.read())

    try:
        webm_to_wav(webm_path, wav_path)
        transcript, emotions = await voice_service.analyze_voice(request.app.state, wav_path)
        emotion_session.add_user_turn(session_id, transcript, emotions)
        return VoiceAnalyzeResponse(transcript=transcript, emotions=emotions)
    finally:
        for path in (webm_path, wav_path):
            if os.path.exists(path):
                os.remove(path)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_voice_router.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Commit**

```bash
git add routers/__init__.py routers/voice.py tests/test_voice_router.py
git commit -m "feat: add voice/analyze router"
```

---

### Task 15: `routers/chat.py` — POST /api/v1/chat/reply

**Files:**
- Create: `routers/chat.py`
- Test: `tests/test_chat_router.py`

**Interfaces:**
- Consumes: `services.chat_service.get_reply` (Task 12), `services.emotion_session.get_session`/`add_assistant_turn` (Task 7), `models.chat.ChatReplyRequest`/`ChatReplyResponse` (Task 5).
- Produces: `router` with `POST /api/v1/chat/reply` returning `404` if `session_id` unknown, else `ChatReplyResponse`. Registered in `main.py` (Task 19).

- [ ] **Step 1: Write the failing test**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import chat as chat_router
from services import emotion_session


def _build_app():
    app = FastAPI()
    app.include_router(chat_router.router)
    return app


def test_reply_returns_404_when_session_missing():
    emotion_session.SESSIONS.clear()
    client = TestClient(_build_app())
    response = client.post(
        "/api/v1/chat/reply",
        json={"session_id": "missing", "transcript": "안녕", "emotions": {"happy": 1.0}},
    )
    assert response.status_code == 404


def test_reply_returns_text_and_records_assistant_turn(monkeypatch):
    emotion_session.SESSIONS.clear()
    emotion_session.add_user_turn("s1", "안녕", {"happy": 1.0})
    monkeypatch.setattr(chat_router.chat_service, "get_reply", lambda history, transcript, emotions: "반가워!")

    client = TestClient(_build_app())
    response = client.post(
        "/api/v1/chat/reply",
        json={"session_id": "s1", "transcript": "안녕", "emotions": {"happy": 1.0}},
    )

    assert response.status_code == 200
    assert response.json() == {"reply_text": "반가워!"}
    assert emotion_session.get_session("s1").turns[-1].role == "assistant"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_chat_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'routers.chat'`

- [ ] **Step 3: Write `routers/chat.py`**

```python
from fastapi import APIRouter, HTTPException

from models.chat import ChatReplyRequest, ChatReplyResponse
from services import chat_service, emotion_session

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/reply", response_model=ChatReplyResponse)
async def reply(payload: ChatReplyRequest):
    session = emotion_session.get_session(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    reply_text = chat_service.get_reply(session.turns, payload.transcript, payload.emotions)
    emotion_session.add_assistant_turn(payload.session_id, reply_text)
    return ChatReplyResponse(reply_text=reply_text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_chat_router.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add routers/chat.py tests/test_chat_router.py
git commit -m "feat: add chat/reply router"
```

---

### Task 16: `routers/tts.py` — POST /api/v1/tts

**Files:**
- Create: `routers/tts.py`
- Test: `tests/test_tts_router.py`

**Interfaces:**
- Consumes: `services.tts_service.synthesize` (Task 11), `models.tts.TTSRequest` (Task 5). Expects `request.app.state.tts_model` and `request.app.state.tts_lock` (`asyncio.Lock`).
- Produces: `router` with `POST /api/v1/tts` returning raw `audio/wav` bytes. Registered in `main.py` (Task 19).

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_tts_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'routers.tts'`

- [ ] **Step 3: Write `routers/tts.py`**

```python
from fastapi import APIRouter, Request, Response
from fastapi.concurrency import run_in_threadpool

from models.tts import TTSRequest
from services import tts_service

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])


@router.post("")
async def synthesize(request: Request, payload: TTSRequest):
    async with request.app.state.tts_lock:
        audio_bytes = await run_in_threadpool(tts_service.synthesize, request.app.state.tts_model, payload.text)
    return Response(content=audio_bytes, media_type="audio/wav")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_tts_router.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add routers/tts.py tests/test_tts_router.py
git commit -m "feat: add tts router"
```

---

### Task 17: `routers/session.py` — POST /api/v1/session/end

**Files:**
- Create: `routers/session.py`
- Test: `tests/test_session_router.py`

**Interfaces:**
- Consumes: `services.emotion_session.compute_average` (Task 7), `models.emotion.SessionEndRequest`/`SessionEndResponse` (Task 5).
- Produces: `router` with `POST /api/v1/session/end` returning `404` if session missing/empty, else `SessionEndResponse`. Registered in `main.py` (Task 19).

- [ ] **Step 1: Write the failing test**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import session as session_router
from services import emotion_session


def _build_app():
    app = FastAPI()
    app.include_router(session_router.router)
    return app


def test_end_returns_404_for_missing_session():
    emotion_session.SESSIONS.clear()
    client = TestClient(_build_app())
    response = client.post("/api/v1/session/end", json={"session_id": "missing"})
    assert response.status_code == 404


def test_end_returns_dominant_and_average_emotions():
    emotion_session.SESSIONS.clear()
    emotion_session.add_user_turn("s1", "t1", {"happy": 0.8, "sad": 0.2})
    emotion_session.add_user_turn("s1", "t2", {"happy": 0.4, "sad": 0.6})

    client = TestClient(_build_app())
    response = client.post("/api/v1/session/end", json={"session_id": "s1"})

    assert response.status_code == 200
    body = response.json()
    assert body["dominant_emotion"] == "happy"
    assert body["average_emotions"]["happy"] == 0.6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_session_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'routers.session'`

- [ ] **Step 3: Write `routers/session.py`**

```python
from fastapi import APIRouter, HTTPException

from models.emotion import SessionEndRequest, SessionEndResponse
from services import emotion_session

router = APIRouter(prefix="/api/v1/session", tags=["session"])


@router.post("/end", response_model=SessionEndResponse)
async def end(payload: SessionEndRequest):
    try:
        dominant, average = emotion_session.compute_average(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionEndResponse(dominant_emotion=dominant, average_emotions=average)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_session_router.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add routers/session.py tests/test_session_router.py
git commit -m "feat: add session/end router"
```

---

### Task 18: `routers/diary.py` — POST /api/v1/diary/generate

**Files:**
- Create: `routers/diary.py`
- Test: `tests/test_diary_router.py`

**Interfaces:**
- Consumes: `services.diary_service.generate_diary`, `services.summary_service.summarize_diary` (Task 13), `services.emotion_session.get_session`/`compute_average`/`clear_session` (Task 7), `database.connection.get_db` (Task 6), `database.diary_repository.save_diary` (Task 6), `models.diary.DiaryGenerateRequest`/`DiaryGenerateResponse` (Task 5).
- Produces: `router` with `POST /api/v1/diary/generate` returning `404` if session missing/empty, else `DiaryGenerateResponse`; clears the session on success. Registered in `main.py` (Task 19).

- [ ] **Step 1: Write the failing test**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base, get_db
from routers import diary as diary_router
from services import emotion_session


def _build_app():
    app = FastAPI()
    app.include_router(diary_router.router)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return app


def test_generate_returns_404_when_session_missing():
    emotion_session.SESSIONS.clear()
    client = TestClient(_build_app())
    response = client.post("/api/v1/diary/generate", json={"session_id": "missing"})
    assert response.status_code == 404


def test_generate_creates_diary_and_clears_session(monkeypatch):
    emotion_session.SESSIONS.clear()
    emotion_session.add_user_turn("s1", "오늘 발표가 잘 됐어요", {"happy": 0.8, "neutral": 0.2})

    monkeypatch.setattr(diary_router.diary_service, "generate_diary", lambda history, average: "오늘은 발표를 잘해서 기뻤다.")
    monkeypatch.setattr(diary_router.summary_service, "summarize_diary", lambda diary_text: "발표 성공으로 뿌듯한 하루")

    client = TestClient(_build_app())
    response = client.post("/api/v1/diary/generate", json={"session_id": "s1"})

    assert response.status_code == 200
    body = response.json()
    assert body["diary_text"] == "오늘은 발표를 잘해서 기뻤다."
    assert body["summary"] == "발표 성공으로 뿌듯한 하루"
    assert body["dominant_emotion"] == "happy"
    assert emotion_session.get_session("s1") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_diary_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'routers.diary'`

- [ ] **Step 3: Write `routers/diary.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.diary_repository import save_diary
from models.diary import DiaryGenerateRequest, DiaryGenerateResponse
from services import diary_service, emotion_session, summary_service

router = APIRouter(prefix="/api/v1/diary", tags=["diary"])


@router.post("/generate", response_model=DiaryGenerateResponse)
async def generate(payload: DiaryGenerateRequest, db: Session = Depends(get_db)):
    session = emotion_session.get_session(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    try:
        dominant, average = emotion_session.compute_average(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session has no turns")

    diary_text = diary_service.generate_diary(session.turns, average)
    summary = summary_service.summarize_diary(diary_text)
    diary = save_diary(db, payload.session_id, diary_text, summary, dominant, average)
    emotion_session.clear_session(payload.session_id)

    return DiaryGenerateResponse(
        diary_id=diary.id,
        diary_text=diary_text,
        summary=summary,
        dominant_emotion=dominant,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_diary_router.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add routers/diary.py tests/test_diary_router.py
git commit -m "feat: add diary/generate router"
```

---

### Task 19: Wire everything into `main.py` (real model loading)

**Files:**
- Modify: `main.py`

**Interfaces:**
- Consumes: all routers (Tasks 14–18), `services.tts_service.register_moong_speaker` (Task 11), `utils.audio_converter.ensure_ffmpeg_available` (Task 4), `database.connection.init_db` (Task 6), `config.settings` (Task 2).
- Produces: the real running app — `app.state.stt_model`, `app.state.ser_model`, `app.state.tts_model`, `app.state.stt_lock`, `app.state.ser_lock`, `app.state.tts_lock` all populated at startup.

No automated test here — loading SenseVoice/emotion2vec/CosyVoice2 takes real GPU memory and time (first run also downloads weights). Verified manually.

- [ ] **Step 1: Replace `main.py` with the full wiring**

```python
import asyncio
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
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

app.include_router(voice.router)
app.include_router(chat.router)
app.include_router(tts.router)
app.include_router(session.router)
app.include_router(diary.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Confirm `pretrained_models/CosyVoice2-0.5B` exists**

CosyVoice2-0.5B weights must already be downloaded to `pretrained_models/CosyVoice2-0.5B` (per repo's own README instructions — `modelscope`/`git-lfs` clone) before this step, since `main.py` loads it eagerly at startup. If missing, download it there first.

- [ ] **Step 3: Start the server**

Run:
```
.venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000
```
Expected: log lines showing SenseVoice/emotion2vec/CosyVoice2 loading (first run also shows model download progress for the funasr models), ending with `Application startup complete.` and no traceback.

- [ ] **Step 4: Verify health check**

Run (separate terminal):
```
curl http://localhost:8000/health
```
Expected: `{"status":"ok"}`

- [ ] **Step 5: Stop the server, then run the full test suite once more to confirm nothing broke**

Run: `.venv\Scripts\pytest -v`
Expected: all tests from Tasks 2–18 still PASS (none of them import `main.py`'s heavy model loading — router tests build their own minimal app).

- [ ] **Step 6: Commit**

```bash
git add main.py
git commit -m "feat: wire real STT/SER/TTS models and all routers into main.py"
```

---

### Task 20: Manual end-to-end verification script

**Files:**
- Create: `scripts/manual_e2e_check.md`

**Interfaces:**
- Produces: a runnable checklist a human follows once, with real audio, a real OpenAI key, and the real MySQL instance, to confirm the full flow from the spec matches actual behavior. This is the final acceptance check for the whole plan.

- [ ] **Step 1: Write `scripts/manual_e2e_check.md`**

```markdown
# 수동 End-to-End 확인

전제: 서버가 `uvicorn main:app --port 8000`으로 떠 있고, `.env`에 유효한
`OPENAI_API_KEY`와 로컬 MySQL 접속 정보가 채워져 있음. `sample.webm`은 직접
녹음한 3~5초 분량의 한국어 발화 파일로 교체할 것.

1. session_id 생성 (PowerShell):
   ```
   $sessionId = [guid]::NewGuid().ToString()
   echo $sessionId
   ```

2. 음성 분석:
   ```
   curl -X POST http://localhost:8000/api/v1/voice/analyze `
     -F "session_id=$sessionId" `
     -F "audio=@sample.webm;type=audio/webm"
   ```
   확인: `transcript`가 실제 발화 내용과 비슷한지, `emotions`에 9개 감정 키가
   있고 합이 대략 1에 가까운지.

3. 대화 응답 (2번 응답의 transcript/emotions를 그대로 넣기):
   ```
   curl -X POST http://localhost:8000/api/v1/chat/reply `
     -H "Content-Type: application/json" `
     -d "{\"session_id\": \"$sessionId\", \"transcript\": \"<2번 transcript>\", \"emotions\": <2번 emotions>}"
   ```
   확인: `reply_text`가 '뭉이' 톤으로 자연스러운지.

4. TTS (3번 응답의 reply_text를 그대로 넣기):
   ```
   curl -X POST http://localhost:8000/api/v1/tts `
     -H "Content-Type: application/json" `
     -d "{\"text\": \"<3번 reply_text>\"}" `
     --output reply.wav
   ```
   확인: `reply.wav`를 재생했을 때 음성이 들리는지 (플레이스홀더 화자 목소리).

5. 2~4번을 2~3회 반복해서 여러 턴 쌓기.

6. 세션 종료:
   ```
   curl -X POST http://localhost:8000/api/v1/session/end `
     -H "Content-Type: application/json" `
     -d "{\"session_id\": \"$sessionId\"}"
   ```
   확인: `dominant_emotion`과 `average_emotions`가 지금까지 턴들의 감정과
   대략 일치하는지.

7. 일기 생성:
   ```
   curl -X POST http://localhost:8000/api/v1/diary/generate `
     -H "Content-Type: application/json" `
     -d "{\"session_id\": \"$sessionId\"}"
   ```
   확인: `diary_text`가 1인칭 일기 형식인지, `summary`가 한 줄인지, MySQL의
   `diaries` 테이블에 실제로 row가 생겼는지 (`SELECT * FROM diaries ORDER BY
   id DESC LIMIT 1;`).

8. 같은 session_id로 6번을 다시 호출 → `404` 확인 (diary/generate가 세션을
   정리했는지 검증).
```

- [ ] **Step 2: Run through the checklist once for real**

Follow every step above with an actual recorded `sample.webm`, a real `OPENAI_API_KEY`, and the local MySQL instance running. Confirm each numbered check passes.

- [ ] **Step 3: Commit**

```bash
git add scripts/manual_e2e_check.md
git commit -m "docs: add manual end-to-end verification checklist"
```
