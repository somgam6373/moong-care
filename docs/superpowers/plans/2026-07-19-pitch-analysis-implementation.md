# 음성 피치(pitch) 분석 추가 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `voice/analyze` 응답에 피치 평균(`pitch_mean`)과 표준편차(`pitch_std`, 떨림 근사치)를 Hz 단위로 추가한다. 감정 판단 로직에는 관여하지 않는 순수 부가 정보다.

**Architecture:** `pyworld`(이미 설치된 의존성)로 F0를 프레임 단위 추출해 유성음 구간만 평균/표준편차를 계산하는 신규 서비스(`pitch_service.py`)를 만들고, 기존 STT/SER와 함께 `asyncio.gather`로 병렬 실행한다.

**Tech Stack:** Python 3.10, `pyworld`, `soundfile`, `numpy` (모두 기존 설치됨, 신규 의존성 없음).

## Global Constraints

- 새 의존성 추가 없음 — `pyworld`, `soundfile`, `numpy` 모두 이미 venv에 설치되어 있음 (`requirements.txt` 수정 불필요).
- `pitch_service.py`는 GPU를 쓰지 않는 순수 CPU 신호처리이므로 `asyncio.Lock`을 쓰지 않는다.
- 유성음 프레임이 하나도 없으면(완전 무음) `pitch_mean=0.0`, `pitch_std=0.0`을 반환한다 (예외를 던지지 않는다).
- 세션 누적 평균(`emotion_session.py`), `chat/reply`, `diary/generate`는 피치 값을 참고하지 않는다 — API 응답에만 노출한다.
- 전체 스펙: `docs/superpowers/specs/2026-07-19-pitch-analysis-design.md`.

---

## File Structure

```
services/
└── pitch_service.py        # 신규 — analyze_pitch(wav_path) -> tuple[float, float]
services/voice_service.py   # 수정 — pitch 분석을 STT/SER와 병렬 실행하도록 확장
models/voice.py             # 수정 — VoiceAnalyzeResponse에 pitch_mean/pitch_std 추가
routers/voice.py            # 수정 — analyze_voice()의 4-tuple을 응답에 채움
tests/
├── test_pitch_service.py   # 신규
├── test_voice_service.py   # 수정
├── test_voice_router.py    # 수정
└── test_models.py          # 수정
```

---

### Task 1: `services/pitch_service.py` — pyworld 피치 분석

**Files:**
- Create: `services/pitch_service.py`
- Test: `tests/test_pitch_service.py`

**Interfaces:**
- Produces: `analyze_pitch(wav_path: str) -> tuple[float, float]` (mean, std, 단위 Hz). Used by `services/voice_service.py` (Task 2).

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import soundfile as sf

from services.pitch_service import analyze_pitch


def test_analyze_pitch_returns_mean_near_input_frequency(tmp_path):
    sr = 16000
    duration = 1.0
    freq = 220.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * freq * t)
    wav_path = str(tmp_path / "tone.wav")
    sf.write(wav_path, audio, sr)

    pitch_mean, pitch_std = analyze_pitch(wav_path)

    assert 180.0 < pitch_mean < 260.0
    assert pitch_std < 15.0


def test_analyze_pitch_returns_zero_for_silence(tmp_path):
    sr = 16000
    audio = np.zeros(sr)
    wav_path = str(tmp_path / "silence.wav")
    sf.write(wav_path, audio, sr)

    pitch_mean, pitch_std = analyze_pitch(wav_path)

    assert pitch_mean == 0.0
    assert pitch_std == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_pitch_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.pitch_service'`

- [ ] **Step 3: Write `services/pitch_service.py`**

```python
import numpy as np
import pyworld as pw
import soundfile as sf


def analyze_pitch(wav_path: str) -> tuple[float, float]:
    audio, sr = sf.read(wav_path)
    audio = audio.astype(np.float64)

    f0, t = pw.dio(audio, sr)
    f0 = pw.stonemask(audio, f0, t, sr)

    voiced = f0[f0 > 0]
    if len(voiced) == 0:
        return 0.0, 0.0
    return float(voiced.mean()), float(voiced.std())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_pitch_service.py -v`
Expected: PASS (2 passed). 검증된 실측값: 220Hz 사인파 입력 시 mean≈219.8, std≈1.2 — 위 assertion 범위 안에 들어옴.

- [ ] **Step 5: Commit**

```bash
git add services/pitch_service.py tests/test_pitch_service.py
git commit -m "feat: add pyworld-based pitch analysis service"
```

---

### Task 2: `services/voice_service.py` — pitch 분석을 STT/SER와 병렬 실행

**Files:**
- Modify: `services/voice_service.py`
- Test: `tests/test_voice_service.py`

**Interfaces:**
- Consumes: `services.pitch_service.analyze_pitch` (Task 1).
- Produces: `async def analyze_voice(app_state, wav_path: str) -> tuple[str, dict[str, float], float, float]` (기존 2-tuple에서 4-tuple로 변경 — transcript, emotions, pitch_mean, pitch_std). Used by `routers/voice.py` (Task 4).

- [ ] **Step 1: Write the failing test (기존 테스트를 4-tuple 기준으로 교체)**

```python
import asyncio

from services import voice_service, stt_service, ser_service, pitch_service


class _FakeAppState:
    def __init__(self):
        self.stt_model = object()
        self.ser_model = object()
        self.stt_lock = asyncio.Lock()
        self.ser_lock = asyncio.Lock()


def test_analyze_voice_runs_stt_ser_pitch_and_combines_results(monkeypatch):
    monkeypatch.setattr(stt_service, "transcribe", lambda model, path: "오늘 발표가 잘 됐어요")
    monkeypatch.setattr(ser_service, "analyze_emotion", lambda model, path: {"happy": 0.7, "neutral": 0.3})
    monkeypatch.setattr(pitch_service, "analyze_pitch", lambda path: (187.3, 24.1))

    transcript, emotions, pitch_mean, pitch_std = asyncio.run(
        voice_service.analyze_voice(_FakeAppState(), "dummy.wav")
    )

    assert transcript == "오늘 발표가 잘 됐어요"
    assert emotions == {"happy": 0.7, "neutral": 0.3}
    assert pitch_mean == 187.3
    assert pitch_std == 24.1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_voice_service.py -v`
Expected: FAIL — `ValueError: not enough values to unpack (expected 4, got 2)` (기존 `analyze_voice`가 아직 2-tuple만 반환하기 때문)

- [ ] **Step 3: Modify `services/voice_service.py`**

```python
import asyncio

from fastapi.concurrency import run_in_threadpool

from services import pitch_service, ser_service, stt_service


async def analyze_voice(app_state, wav_path: str) -> tuple[str, dict[str, float], float, float]:
    async def run_stt():
        async with app_state.stt_lock:
            return await run_in_threadpool(stt_service.transcribe, app_state.stt_model, wav_path)

    async def run_ser():
        async with app_state.ser_lock:
            return await run_in_threadpool(ser_service.analyze_emotion, app_state.ser_model, wav_path)

    async def run_pitch():
        return await run_in_threadpool(pitch_service.analyze_pitch, wav_path)

    transcript, emotions, (pitch_mean, pitch_std) = await asyncio.gather(run_stt(), run_ser(), run_pitch())
    return transcript, emotions, pitch_mean, pitch_std
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_voice_service.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add services/voice_service.py tests/test_voice_service.py
git commit -m "feat: run pitch analysis alongside STT/SER in voice pipeline"
```

---

### Task 3: `models/voice.py` — `VoiceAnalyzeResponse`에 피치 필드 추가

**Files:**
- Modify: `models/voice.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `VoiceAnalyzeResponse{transcript, emotions, pitch_mean, pitch_std}`. Used by `routers/voice.py` (Task 4).

- [ ] **Step 1: Write the failing test (기존 round-trip 테스트를 새 필드 포함으로 교체)**

`tests/test_models.py`에서 `test_voice_analyze_response_roundtrip`만 아래로 교체 (다른 테스트 함수는 그대로 둠):

```python
def test_voice_analyze_response_roundtrip():
    resp = VoiceAnalyzeResponse(
        transcript="안녕",
        emotions={"happy": 0.5, "neutral": 0.5},
        pitch_mean=187.3,
        pitch_std=24.1,
    )
    assert resp.model_dump() == {
        "transcript": "안녕",
        "emotions": {"happy": 0.5, "neutral": 0.5},
        "pitch_mean": 187.3,
        "pitch_std": 24.1,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_models.py::test_voice_analyze_response_roundtrip -v`
Expected: FAIL — `pydantic.ValidationError` (unexpected keyword arguments `pitch_mean`, `pitch_std`)

- [ ] **Step 3: Modify `models/voice.py`**

```python
from pydantic import BaseModel


class VoiceAnalyzeResponse(BaseModel):
    transcript: str
    emotions: dict[str, float]
    pitch_mean: float
    pitch_std: float
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_models.py -v`
Expected: PASS (5 passed — 전체 test_models.py 기준)

- [ ] **Step 5: Commit**

```bash
git add models/voice.py tests/test_models.py
git commit -m "feat: add pitch_mean/pitch_std fields to VoiceAnalyzeResponse"
```

---

### Task 4: `routers/voice.py` — 라우터에서 4-tuple 반영

**Files:**
- Modify: `routers/voice.py`
- Test: `tests/test_voice_router.py`

**Interfaces:**
- Consumes: `services.voice_service.analyze_voice` (Task 2, 이제 4-tuple 반환), `models.voice.VoiceAnalyzeResponse` (Task 3).

- [ ] **Step 1: Write the failing test (fake_analyze_voice와 assertion을 4-tuple 기준으로 교체)**

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


def test_analyze_endpoint_returns_transcript_emotions_and_pitch(monkeypatch):
    emotion_session.SESSIONS.clear()
    monkeypatch.setattr(voice_router, "webm_to_wav", lambda src, dst: open(dst, "wb").close())

    async def fake_analyze_voice(app_state, wav_path):
        return "오늘 발표가 잘 됐어요", {"happy": 0.65, "sad": 0.10, "neutral": 0.20, "angry": 0.05}, 187.3, 24.1

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
    assert body["pitch_mean"] == 187.3
    assert body["pitch_std"] == 24.1
    assert emotion_session.get_session("s1").turn_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_voice_router.py -v`
Expected: FAIL — `ValueError: not enough values to unpack (expected 4, got 2)` (라우터가 아직 2개만 unpack하기 때문)

- [ ] **Step 3: Modify `routers/voice.py`**

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
        transcript, emotions, pitch_mean, pitch_std = await voice_service.analyze_voice(request.app.state, wav_path)
        emotion_session.add_user_turn(session_id, transcript, emotions)
        return VoiceAnalyzeResponse(
            transcript=transcript,
            emotions=emotions,
            pitch_mean=pitch_mean,
            pitch_std=pitch_std,
        )
    finally:
        for path in (webm_path, wav_path):
            if os.path.exists(path):
                os.remove(path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_voice_router.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Run full test suite to confirm nothing else broke**

Run: `.venv\Scripts\pytest tests/ -v`
Expected: 모든 테스트 PASS (Task 1~4 이전 기준 39개 + 이번에 추가/교체된 것 포함).

- [ ] **Step 6: Commit**

```bash
git add routers/voice.py tests/test_voice_router.py
git commit -m "feat: expose pitch_mean/pitch_std in voice/analyze response"
```

---

### Task 5: 수동 확인 (실제 서버로 검증)

**Files:** 없음 (코드 변경 없음, 수동 검증만)

- [ ] **Step 1: 서버 기동 후 `scripts/manual_test.html` 또는 curl로 `voice/analyze` 호출**

기존 `scripts/manual_e2e_check.md` 2번 단계와 동일하게 호출하되, 응답에
`pitch_mean`/`pitch_std` 필드가 실제 녹음 오디오에서도 합리적인 범위
(사람 목소리 기준 대략 70~400Hz)로 나오는지 눈으로 확인한다. 별도 자동
테스트는 없음 — Task 1의 합성 사인파 테스트로 로직 정확성은 이미 검증됨.
