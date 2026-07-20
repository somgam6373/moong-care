# OpenAI gpt-4o-mini-tts + 감정 Instruction 마이그레이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/api/v1/tts`가 로컬 CosyVoice3 대신 OpenAI `gpt-4o-mini-tts`를 호출하고, 세션의 최근 사용자 감정에 맞춰 `instructions`로 톤을 조절하며, 목소리 preset은 클라이언트가 고르게 한다.

**Architecture:** `emotion_session`에 최근 user turn의 감정을 조회하는 헬퍼를 추가하고, `tts_service`가 그 감정을 instruction 문장으로 매핑한 뒤 OpenAI Audio Speech API를 호출한다. `routers/tts.py`는 voice 검증만 담당하고 GPU 모델/락 의존성을 모두 제거한다. `main.py`에서 CosyVoice 모델 로딩 코드를 제거한다.

**Tech Stack:** FastAPI, pydantic, OpenAI Python SDK (`services/openai_client.get_client`), pytest + monkeypatch.

## Global Constraints

- OpenAI TTS 모델명은 정확히 `"gpt-4o-mini-tts"` 문자열 리터럴로 하드코딩한다 (config 항목 아님).
- 허용 voice 목록: `{"alloy", "echo", "fable", "onyx", "nova", "shimmer"}`. 기본값: `"nova"`.
- 감정 클래스는 `services/emotion_session.EMOTION_CLASSES` 9개
  (`angry, disgusted, fearful, happy, neutral, other, sad, surprised, unknown`)와 정확히 일치해야 한다.
- session_id 없음/존재하지 않음/user turn 없음 → 에러 없이 `neutral` instruction으로 fallback. 이 경로는 절대 예외를 던지지 않는다.
- `voice`가 허용 목록 밖이면 `HTTPException(400)`.
- `CosyVoice/`, `pretrained_models/`, `requirements.txt`의 관련 의존성 정리는 이번 계획 범위 밖 — 건드리지 않는다.
- 참고 spec: `docs/superpowers/specs/2026-07-20-openai-tts-emotion-design.md`

---

### Task 1: `emotion_session`에 최근 user 감정 조회 헬퍼 추가

**Files:**
- Modify: `services/emotion_session.py:45-47` (기존 `get_session` 함수 바로 뒤)
- Test: `tests/test_emotion_session.py`

**Interfaces:**
- Consumes: 기존 `SESSIONS: dict[str, SessionState]`, `TurnRecord(role, text, emotions)`.
- Produces: `get_last_user_emotion(session_id: str) -> dict[str, float] | None` — Task 3(`tts_service.resolve_instructions`)이 이 함수를 가져다 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_emotion_session.py`의 import 줄을 다음으로 교체:

```python
from services.emotion_session import (
    add_user_turn, add_assistant_turn, get_session,
    compute_average, clear_session, get_last_user_emotion, SESSIONS,
)
```

파일 끝에 다음 테스트 추가:

```python
def test_get_last_user_emotion_returns_most_recent_user_turn():
    add_user_turn("s1", "t1", {"happy": 0.8, "sad": 0.2})
    add_assistant_turn("s1", "반가워")
    add_user_turn("s1", "t2", {"sad": 0.9, "happy": 0.1})

    assert get_last_user_emotion("s1") == {"sad": 0.9, "happy": 0.1}


def test_get_last_user_emotion_missing_session_returns_none():
    assert get_last_user_emotion("does-not-exist") is None


def test_get_last_user_emotion_no_user_turns_returns_none():
    add_assistant_turn("new-id", "안녕!")
    assert get_last_user_emotion("new-id") is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_emotion_session.py -v`
Expected: `ImportError: cannot import name 'get_last_user_emotion'`

- [ ] **Step 3: 최소 구현 작성**

`services/emotion_session.py`의 `get_session` 함수(45-46번 줄) 바로 뒤에 추가:

```python
def get_last_user_emotion(session_id: str) -> dict[str, float] | None:
    state = SESSIONS.get(session_id)
    if state is None:
        return None
    for turn in reversed(state.turns):
        if turn.role == "user":
            return turn.emotions
    return None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_emotion_session.py -v`
Expected: 전체 PASS (기존 테스트 포함 10개)

- [ ] **Step 5: 커밋**

```bash
git add services/emotion_session.py tests/test_emotion_session.py
git commit -m "feat: add get_last_user_emotion helper to emotion_session"
```

---

### Task 2: `TTSRequest`에 `session_id`/`voice` 필드, `config.py`에 voice 설정 추가

**Files:**
- Modify: `models/tts.py`
- Modify: `config.py:16`
- Modify: `tests/test_models.py:32-33` (`test_tts_request`)

**Interfaces:**
- Produces: `TTSRequest(text, session_id=None, voice=None)`, `settings.TTS_DEFAULT_VOICE: str`, `settings.TTS_ALLOWED_VOICES: set[str]` — Task 3(`tts_service`)와 Task 4(`routers/tts.py`)가 사용.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_models.py`의 `test_tts_request`를 다음으로 교체:

```python
def test_tts_request():
    req = TTSRequest(text="hello")
    assert req.text == "hello"
    assert req.session_id is None
    assert req.voice is None

    req_full = TTSRequest(text="hello", session_id="s1", voice="nova")
    assert req_full.session_id == "s1"
    assert req_full.voice == "nova"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_models.py::test_tts_request -v`
Expected: FAIL — `session_id`/`voice` 필드가 없어서 `AttributeError` 또는 pydantic이 extra field로 처리해도 `req.session_id`가 존재하지 않아 `AttributeError`.

- [ ] **Step 3: 최소 구현 작성**

`models/tts.py` 전체를 다음으로 교체:

```python
from pydantic import BaseModel


class TTSRequest(BaseModel):
    text: str
    session_id: str | None = None
    voice: str | None = None
```

`config.py:16`의 `TTS_MODEL_DIR: str = "pretrained_models/CosyVoice2-0.5B"` 줄을 다음으로 교체:

```python
    TTS_DEFAULT_VOICE: str = "nova"
    TTS_ALLOWED_VOICES: set[str] = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_models.py -v`
Expected: 전체 PASS

- [ ] **Step 5: 커밋**

```bash
git add models/tts.py config.py tests/test_models.py
git commit -m "feat: add session_id/voice fields to TTSRequest, voice settings to config"
```

---

### Task 3: `services/tts_service.py`를 OpenAI 호출로 전면 재작성

**Files:**
- Modify: `services/tts_service.py` (전체 교체)
- Test: `tests/test_tts_service.py` (전체 교체)

**Interfaces:**
- Consumes: `services.emotion_session.get_last_user_emotion(session_id) -> dict[str, float] | None` (Task 1), `services.openai_client.get_client()` (기존).
- Produces: `EMOTION_INSTRUCTIONS: dict[str, str]`, `resolve_instructions(session_id: str | None) -> str`, `synthesize(text: str, voice: str, instructions: str) -> bytes` — Task 4(`routers/tts.py`)가 이 세 개를 사용.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_tts_service.py` 전체를 다음으로 교체:

```python
from types import SimpleNamespace

import pytest

from services import tts_service
from services.emotion_session import SESSIONS, add_assistant_turn, add_user_turn


@pytest.fixture(autouse=True)
def clean_sessions():
    SESSIONS.clear()
    yield
    SESSIONS.clear()


def test_resolve_instructions_uses_dominant_emotion_of_last_user_turn():
    add_user_turn("s1", "오늘 힘들었어", {"sad": 0.8, "neutral": 0.2})

    result = tts_service.resolve_instructions("s1")

    assert result == tts_service.EMOTION_INSTRUCTIONS["sad"]


def test_resolve_instructions_ignores_assistant_turn_after_user_turn():
    add_user_turn("s1", "오늘 힘들었어", {"sad": 0.8, "neutral": 0.2})
    add_assistant_turn("s1", "힘들었겠다")

    result = tts_service.resolve_instructions("s1")

    assert result == tts_service.EMOTION_INSTRUCTIONS["sad"]


def test_resolve_instructions_falls_back_to_neutral_for_missing_session():
    result = tts_service.resolve_instructions("does-not-exist")
    assert result == tts_service.EMOTION_INSTRUCTIONS["neutral"]


def test_resolve_instructions_falls_back_to_neutral_for_none_session_id():
    assert tts_service.resolve_instructions(None) == tts_service.EMOTION_INSTRUCTIONS["neutral"]


def test_resolve_instructions_falls_back_to_neutral_when_no_user_turn_yet():
    add_assistant_turn("s1", "안녕!")
    assert tts_service.resolve_instructions("s1") == tts_service.EMOTION_INSTRUCTIONS["neutral"]


class _FakeSpeechResponse:
    def read(self):
        return b"RIFF....WAVEfmt "


class _FakeSpeech:
    def __init__(self):
        self.last_call = None

    def create(self, model, voice, input, instructions):
        self.last_call = {"model": model, "voice": voice, "input": input, "instructions": instructions}
        return _FakeSpeechResponse()


class _FakeClient:
    def __init__(self):
        self.audio = SimpleNamespace(speech=_FakeSpeech())


def test_synthesize_calls_openai_with_expected_params_and_returns_bytes(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(tts_service, "get_client", lambda: fake_client)

    audio_bytes = tts_service.synthesize("안녕하세요", "nova", "Speak warmly.")

    assert audio_bytes == b"RIFF....WAVEfmt "
    assert fake_client.audio.speech.last_call == {
        "model": "gpt-4o-mini-tts",
        "voice": "nova",
        "input": "안녕하세요",
        "instructions": "Speak warmly.",
    }
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_tts_service.py -v`
Expected: FAIL — `resolve_instructions`/`EMOTION_INSTRUCTIONS`가 아직 없어서 `AttributeError`.

- [ ] **Step 3: 최소 구현 작성**

`services/tts_service.py` 전체를 다음으로 교체:

```python
from services.emotion_session import get_last_user_emotion
from services.openai_client import get_client

TTS_MODEL = "gpt-4o-mini-tts"

EMOTION_INSTRUCTIONS: dict[str, str] = {
    "angry": "Speak in a calm, soothing, de-escalating tone.",
    "disgusted": "Speak in a calm, neutral, non-judgmental tone.",
    "fearful": "Speak in a reassuring, steady, gentle tone.",
    "happy": "Speak in a bright, cheerful, warm tone.",
    "neutral": "Speak in a natural, warm, conversational tone.",
    "other": "Speak in a natural, warm, conversational tone.",
    "sad": "Speak in a warm, gentle, comforting tone, as if empathizing with someone who's feeling sad.",
    "surprised": "Speak in an animated, curious, engaged tone.",
    "unknown": "Speak in a natural, warm, conversational tone.",
}


def resolve_instructions(session_id: str | None) -> str:
    emotions = get_last_user_emotion(session_id) if session_id else None
    if not emotions:
        return EMOTION_INSTRUCTIONS["neutral"]
    dominant = max(emotions, key=emotions.get)
    return EMOTION_INSTRUCTIONS.get(dominant, EMOTION_INSTRUCTIONS["neutral"])


def synthesize(text: str, voice: str, instructions: str) -> bytes:
    client = get_client()
    response = client.audio.speech.create(
        model=TTS_MODEL,
        voice=voice,
        input=text,
        instructions=instructions,
    )
    return response.read()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_tts_service.py -v`
Expected: 전체 PASS (8개)

- [ ] **Step 5: 커밋**

```bash
git add services/tts_service.py tests/test_tts_service.py
git commit -m "feat: replace CosyVoice TTS with OpenAI gpt-4o-mini-tts + emotion instructions"
```

---

### Task 4: `routers/tts.py`를 voice 검증 + OpenAI 경로로 재작성

**Files:**
- Modify: `routers/tts.py` (전체 교체)
- Test: `tests/test_tts_router.py` (전체 교체)

**Interfaces:**
- Consumes: `models.tts.TTSRequest` (Task 2), `services.tts_service.resolve_instructions`/`synthesize` (Task 3), `config.settings.TTS_DEFAULT_VOICE`/`TTS_ALLOWED_VOICES` (Task 2).
- Produces: `POST /api/v1/tts` — `audio/wav` 응답, 없어진 `app.state.tts_model`/`tts_lock` 의존성.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_tts_router.py` 전체를 다음으로 교체:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_tts_router.py -v`
Expected: FAIL — 기존 `routers/tts.py`가 `payload.text` 하나만 받는 `tts_service.synthesize(model, text)` 시그니처를 호출해서 `TypeError`, 400 테스트는 항상 200 반환해서 실패.

- [ ] **Step 3: 최소 구현 작성**

`routers/tts.py` 전체를 다음으로 교체:

```python
from fastapi import APIRouter, HTTPException, Response
from fastapi.concurrency import run_in_threadpool

from config import settings
from models.tts import TTSRequest
from services import tts_service

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])


@router.post("")
async def synthesize(payload: TTSRequest):
    voice = payload.voice or settings.TTS_DEFAULT_VOICE
    if voice not in settings.TTS_ALLOWED_VOICES:
        raise HTTPException(status_code=400, detail=f"unsupported voice: {voice}")

    instructions = tts_service.resolve_instructions(payload.session_id)
    audio_bytes = await run_in_threadpool(tts_service.synthesize, payload.text, voice, instructions)
    return Response(content=audio_bytes, media_type="audio/wav")
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_tts_router.py -v`
Expected: 전체 PASS (4개)

- [ ] **Step 5: 커밋**

```bash
git add routers/tts.py tests/test_tts_router.py
git commit -m "feat: validate voice and drop GPU model/lock deps in tts router"
```

---

### Task 5: `main.py`에서 CosyVoice 모델 로딩 제거

**Files:**
- Modify: `main.py` (전체 교체)

**Interfaces:**
- Consumes: 없음 (Task 3/4가 이미 OpenAI 경로로 전환 완료된 상태).
- Produces: 없음 — 앱 시작 시 CosyVoice/GPU TTS 모델을 더 이상 로딩하지 않음.

- [ ] **Step 1: 회귀 테스트로 쓸 기존 테스트 확인**

Run: `pytest tests/test_main_health.py -v`
Expected: 현재 상태에서 PASS (수정 전 baseline 확인용).

- [ ] **Step 2: `main.py` 수정**

`main.py` 전체를 다음으로 교체:

```python
import asyncio

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from funasr import AutoModel as FunASRAutoModel

from config import settings
from database.connection import init_db
from routers import chat, diary, session, tts, voice
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
```

- [ ] **Step 3: 회귀 테스트 재확인**

Run: `pytest tests/test_main_health.py -v`
Expected: PASS (동작 변화 없음 — `TestClient(app)`는 context manager로 안 쓰여서 lifespan이 실행되지 않으므로 CosyVoice 제거와 무관하게 그대로 통과)

- [ ] **Step 4: 전체 테스트 스위트 실행**

Run: `pytest -v`
Expected: 전체 PASS. `services/tts_service.py`, `routers/tts.py`, `models/tts.py`, `config.py`, `services/emotion_session.py`를 import하는 어떤 테스트도 `cosyvoice`/`CosyVoiceAutoModel`을 더 이상 참조하지 않음을 확인.

- [ ] **Step 5: 커밋**

```bash
git add main.py
git commit -m "refactor: remove CosyVoice TTS model loading from app startup"
```

---

## Self-Review Notes

- **Spec coverage**: 아키텍처/데이터 흐름(Task 1+3+4), `TTSRequest` 필드(Task 2), `EMOTION_INSTRUCTIONS` 9개 전체(Task 3), voice 검증+기본값(Task 2+4), 에러 처리 3가지 케이스(neutral fallback: Task 3, 400: Task 4, 500 propagate: Task 3에서 별도 처리 안 함으로 구현됨), `main.py` 정리(Task 5), 테스트 계획 4개 파일 전부(Task 1/2/3/4) — 모두 매핑됨. CosyVoice 폴더/requirements 정리는 스펙에서도 범위 밖으로 명시했으므로 태스크 없음.
- **Placeholder scan**: 없음 — 모든 스텝에 실행 가능한 전체 코드 포함.
- **Type consistency**: `resolve_instructions(session_id: str | None) -> str`가 Task 3 정의와 Task 4 호출부에서 동일. `synthesize(text: str, voice: str, instructions: str) -> bytes` 시그니처가 Task 3 정의/테스트, Task 4 호출부에서 동일. `get_last_user_emotion(session_id: str) -> dict[str, float] | None`이 Task 1 정의와 Task 3 사용처에서 동일.
