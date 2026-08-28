# front-ui 보조 디스플레이 전환 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** front-ui가 자체 녹음/TTS 대화 루프를 도는 대신, 라즈베리파이(Pi)가 처리한 턴 결과를 폴링으로
받아 감정 텍스트 + 케어 색상만 표시하고, 대화 종료 시 일기(편지)를 보여주는 보조 디스플레이로
바꾼다. 대화 시작/종료는 front-ui 버튼으로도 실제 백엔드를 호출할 수 있다.

**Architecture:** 백엔드에 "현재 세션 하나"를 전역으로 추적하는 `session_state` 모듈을 추가한다.
Pi가 `/api/v1/care/turn`을 호출할 때마다 그 session_id를 자동으로 "현재 세션"으로 채택하므로
**Pi 쪽 코드는 전혀 수정하지 않는다.** front-ui는 새 `GET /api/v1/session/live`를 1.5초 간격으로
폴링해서 화면을 자동 전환하고(Intro→Conversation→Ending), 마이크/TTS 관련 코드는 전부 제거한다.

**Tech Stack:** 백엔드 FastAPI + pytest (기존과 동일, 새 파일 없이 기존 패턴 확장). 프론트 React +
TypeScript + Vite + Vitest/RTL (기존과 동일).

**Spec:** `docs/superpowers/specs/2026-08-29-front-ui-passive-display-redesign.md`

## Global Constraints

- Pi 쪽 코드(`pi/`)는 한 줄도 수정하지 않는다 — `session_state.adopt()`가 `/care/turn` 안에서
  자동으로 처리한다.
- 세션 상태는 기존 `services/emotion_session.py`와 같은 패턴으로 **인메모리**로 관리한다 (DB 아님).
- `care_emotion_label`(한글 라벨) 같은 표시용 텍스트는 백엔드가 다시 보내지 않는다 — front가 이미
  `constants/careEmotions.ts`에 코드→라벨 매핑을 갖고 있다 (색상 로직 이중 관리 금지 원칙 유지).
- `EndingScreen.tsx`의 `endSession → generateDiary` 순서 호출 로직은 **변경하지 않는다**.
- 동시 사용 레이스 컨디션(Pi와 front가 동시에 시작/종료)은 처리하지 않는다 (스펙 2절 확정 사항).

---

## Task 1: 백엔드 — `session_state` 모듈 (현재 세션 추적)

**Files:**
- Create: `services/session_state.py`
- Test: `tests/test_session_state.py`

**Interfaces:**
- Produces: `session_state.start_session() -> str`, `session_state.get_current() -> str | None`,
  `session_state.adopt(session_id: str) -> None`, `session_state.clear() -> None`. Task 3, 4, 5가
  이 함수들을 그대로 가져다 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_session_state.py`:
```python
import pytest

from services import session_state


@pytest.fixture(autouse=True)
def reset_state():
    session_state.clear()
    yield
    session_state.clear()


def test_get_current_starts_as_none():
    assert session_state.get_current() is None


def test_start_session_sets_and_returns_current():
    session_id = session_state.start_session()
    assert session_state.get_current() == session_id
    assert isinstance(session_id, str) and len(session_id) > 0


def test_start_session_generates_a_different_id_each_call():
    first = session_state.start_session()
    second = session_state.start_session()
    assert first != second
    assert session_state.get_current() == second


def test_adopt_overwrites_current():
    session_state.start_session()
    session_state.adopt("pi-session-1")
    assert session_state.get_current() == "pi-session-1"


def test_clear_resets_to_none():
    session_state.start_session()
    session_state.clear()
    assert session_state.get_current() is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_session_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.session_state'`

- [ ] **Step 3: 최소 구현 작성**

`services/session_state.py`:
```python
"""현재 활성 세션 하나를 전역으로 추적한다 (기기 1대 전제, DB 아님).

Pi가 /api/v1/care/turn 을 호출할 때마다 adopt()로 그 session_id 를 "현재 세션"으로
자동 채택한다 — 그래서 Pi 쪽 코드는 이 개념을 몰라도 된다. front-ui 는 이 모듈을 통해
front 버튼(시작/종료)으로도 같은 "현재 세션"을 조작할 수 있다.
"""

import uuid

_current_session_id: str | None = None


def start_session() -> str:
    global _current_session_id
    _current_session_id = uuid.uuid4().hex
    return _current_session_id


def get_current() -> str | None:
    return _current_session_id


def adopt(session_id: str) -> None:
    global _current_session_id
    _current_session_id = session_id


def clear() -> None:
    global _current_session_id
    _current_session_id = None
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_session_state.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: 커밋**

```bash
git add services/session_state.py tests/test_session_state.py
git commit -m "feat: add session_state module to track the current active session"
```

---

## Task 2: 백엔드 — `emotion_session.get_latest_snapshot`

**Files:**
- Modify: `services/emotion_session.py`
- Test: `tests/test_emotion_session.py`

**Interfaces:**
- Consumes: 기존 `SESSIONS`, `TurnRecord`, `add_user_turn`, `add_assistant_turn` (변경 없음).
- Produces: `get_latest_snapshot(session_id: str) -> dict | None`. 반환 dict 키:
  `turn_count, transcript, care_emotion, care_confidence, care_color, reply_text`. Task 4가
  이 함수를 그대로 가져다 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_emotion_session.py` 상단 import에 `get_latest_snapshot` 추가:
```python
from services.emotion_session import (
    add_user_turn, add_assistant_turn, get_session,
    compute_average, clear_session, get_last_user_emotion, SESSIONS,
    get_recent_context, get_care_timeline, set_sleep_result, get_sleep_result,
    get_last_user_care_emotion, compute_dominant_care_emotion,
    get_latest_snapshot,
)
```

파일 끝에 추가:
```python
def test_get_latest_snapshot_missing_session_returns_none():
    assert get_latest_snapshot("does-not-exist") is None


def test_get_latest_snapshot_no_user_turns_returns_none():
    add_assistant_turn("new-id", "안녕!")
    assert get_latest_snapshot("new-id") is None


def test_get_latest_snapshot_returns_latest_user_and_assistant_text():
    add_user_turn(
        "s1", "t1", {"happy": 1.0}, care_emotion="joy", care_confidence=0.9,
        care_color={"hex": "#F6C66D", "brightness": 0.5, "transition_ms": 1200},
    )
    add_assistant_turn("s1", "reply1")
    add_user_turn(
        "s1", "t2", {"sad": 1.0}, care_emotion="fatigue", care_confidence=0.7,
        care_color={"hex": "#7DCAC3", "brightness": 0.4, "transition_ms": 1600},
    )
    add_assistant_turn("s1", "reply2")

    snapshot = get_latest_snapshot("s1")

    assert snapshot == {
        "turn_count": 2,
        "transcript": "t2",
        "care_emotion": "fatigue",
        "care_confidence": 0.7,
        "care_color": {"hex": "#7DCAC3", "brightness": 0.4, "transition_ms": 1600},
        "reply_text": "reply2",
    }
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_emotion_session.py -v -k get_latest_snapshot`
Expected: FAIL — `ImportError: cannot import name 'get_latest_snapshot'`

- [ ] **Step 3: 최소 구현 작성**

`services/emotion_session.py` 끝에 추가 (기존 `clear_session` 함수 뒤):
```python
def get_latest_snapshot(session_id: str) -> dict | None:
    """가장 최근 턴의 감정/색/답변 스냅샷. /session/live 폴링용.

    turn_count 를 버전 번호처럼 써서, front 는 이 값이 바뀌었는지로 새 턴이
    왔는지 감지한다 (별도 타임스탬프 불필요).
    """
    state = SESSIONS.get(session_id)
    if state is None or state.turn_count == 0:
        return None
    reply_text = next((t.text for t in reversed(state.turns) if t.role == "assistant"), None)
    user_turn = next((t for t in reversed(state.turns) if t.role == "user"), None)
    return {
        "turn_count": state.turn_count,
        "transcript": user_turn.text if user_turn else None,
        "care_emotion": user_turn.care_emotion if user_turn else None,
        "care_confidence": user_turn.care_confidence if user_turn else None,
        "care_color": user_turn.care_color if user_turn else None,
        "reply_text": reply_text,
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_emotion_session.py -v`
Expected: PASS (기존 테스트 포함 전체)

- [ ] **Step 5: 커밋**

```bash
git add services/emotion_session.py tests/test_emotion_session.py
git commit -m "feat: add get_latest_snapshot for polling the most recent turn"
```

---

## Task 3: 백엔드 — `/session/start`, `/session/live` 엔드포인트 + `end()` 수정

**Files:**
- Modify: `models/emotion.py`
- Modify: `routers/session.py`
- Test: `tests/test_session_router.py`

**Interfaces:**
- Consumes: Task 1의 `session_state.start_session/get_current/adopt/clear`, Task 2의
  `emotion_session.get_latest_snapshot`, 기존 `emotion_session.get_sleep_result`.
- Produces: `POST /api/v1/session/start` → `{"session_id": str}`. `GET /api/v1/session/live` →
  `{"session_id": str|null, "has_session": bool, "ended": bool, "turn_count": int,
  "transcript": str|null, "care_emotion": str|null, "care_confidence": float|null,
  "care_color": {"hex","brightness","transition_ms"}|null, "reply_text": str|null}`. Task 8의
  front `fetchLive()`가 이 응답 모양을 그대로 소비한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`models/emotion.py`에 먼저 응답 모델을 추가한다 (테스트가 이 모델의 필드를 검증하므로):
```python
from pydantic import BaseModel

from models.care import CareColor


class SessionEndRequest(BaseModel):
    session_id: str


class SessionEndResponse(BaseModel):
    dominant_emotion: str
    average_emotions: dict[str, float]
    sleep_color: CareColor


class SessionStartResponse(BaseModel):
    session_id: str


class SessionLiveResponse(BaseModel):
    session_id: str | None
    has_session: bool
    ended: bool
    turn_count: int = 0
    transcript: str | None = None
    care_emotion: str | None = None
    care_confidence: float | None = None
    care_color: CareColor | None = None
    reply_text: str | None = None
```

`tests/test_session_router.py` 상단에 import 추가:
```python
from services import emotion_session, session_state
```
(기존 `from services import emotion_session` 줄을 이걸로 교체한다.)

파일 끝에 추가:
```python
@pytest.fixture(autouse=True)
def reset_session_state():
    session_state.clear()
    yield
    session_state.clear()


def test_start_creates_and_returns_new_current_session():
    client = TestClient(_build_app())
    response = client.post("/api/v1/session/start")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_state.get_current()
    assert body["session_id"]


def test_live_returns_no_session_when_none_current():
    client = TestClient(_build_app())
    response = client.get("/api/v1/session/live")
    assert response.status_code == 200
    assert response.json() == {
        "session_id": None, "has_session": False, "ended": False,
        "turn_count": 0, "transcript": None, "care_emotion": None,
        "care_confidence": None, "care_color": None, "reply_text": None,
    }


def test_live_returns_latest_turn_snapshot_for_current_session():
    emotion_session.SESSIONS.clear()
    session_state.adopt("s1")
    emotion_session.add_user_turn(
        "s1", "안녕", {"happy": 1.0}, care_emotion="joy", care_confidence=0.8,
        care_color={"hex": "#F6C66D", "brightness": 0.5, "transition_ms": 1200},
    )
    emotion_session.add_assistant_turn("s1", "반가워!")

    client = TestClient(_build_app())
    response = client.get("/api/v1/session/live")

    assert response.status_code == 200
    body = response.json()
    assert body["has_session"] is True
    assert body["ended"] is False
    assert body["session_id"] == "s1"
    assert body["transcript"] == "안녕"
    assert body["care_emotion"] == "joy"
    assert body["reply_text"] == "반가워!"


def test_live_marks_ended_after_session_end_called():
    emotion_session.SESSIONS.clear()
    session_state.adopt("s1")
    emotion_session.add_user_turn("s1", "안녕", {"happy": 1.0}, care_emotion="joy")

    client = TestClient(_build_app())
    client.post("/api/v1/session/end", json={"session_id": "s1"})

    # end()가 current 포인터를 지우므로, ended 플래그 자체를 확인하려면 다시 adopt해서 본다.
    session_state.adopt("s1")
    response = client.get("/api/v1/session/live")
    assert response.json()["ended"] is True


def test_end_clears_current_session_pointer():
    emotion_session.SESSIONS.clear()
    session_state.adopt("s1")
    emotion_session.add_user_turn("s1", "안녕", {"happy": 1.0}, care_emotion="joy")

    client = TestClient(_build_app())
    client.post("/api/v1/session/end", json={"session_id": "s1"})

    assert session_state.get_current() is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_session_router.py -v`
Expected: FAIL — 새 테스트들이 404 (엔드포인트 없음) 또는 `AttributeError`로 실패. 기존 테스트 3개는
여전히 통과해야 한다.

- [ ] **Step 3: 최소 구현 작성**

`routers/session.py` 전체를 아래로 교체:
```python
from fastapi import APIRouter, BackgroundTasks, HTTPException

from models.emotion import (
    SessionEndRequest,
    SessionEndResponse,
    SessionLiveResponse,
    SessionStartResponse,
)
from services import color_care_service, emotion_session, mood_light_client, session_state, sleep_color_service

router = APIRouter(prefix="/api/v1/session", tags=["session"])


@router.post("/start", response_model=SessionStartResponse)
async def start():
    session_id = session_state.start_session()
    return SessionStartResponse(session_id=session_id)


@router.get("/live", response_model=SessionLiveResponse)
async def live():
    session_id = session_state.get_current()
    if session_id is None:
        return SessionLiveResponse(session_id=None, has_session=False, ended=False)

    _, sleep_color = emotion_session.get_sleep_result(session_id)
    ended = sleep_color is not None
    snapshot = emotion_session.get_latest_snapshot(session_id) or {}
    return SessionLiveResponse(
        session_id=session_id,
        has_session=True,
        ended=ended,
        turn_count=snapshot.get("turn_count", 0),
        transcript=snapshot.get("transcript"),
        care_emotion=snapshot.get("care_emotion"),
        care_confidence=snapshot.get("care_confidence"),
        care_color=snapshot.get("care_color"),
        reply_text=snapshot.get("reply_text"),
    )


@router.post("/end", response_model=SessionEndResponse)
async def end(payload: SessionEndRequest, background_tasks: BackgroundTasks):
    try:
        _, average = emotion_session.compute_average(payload.session_id)
        dominant = emotion_session.compute_dominant_care_emotion(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")

    sleep_profile = sleep_color_service.sleep_profile_for_emotion(dominant)
    sleep_color = color_care_service.get_sleep_color(sleep_profile)
    sleep_color_dict = sleep_color.model_dump()
    emotion_session.set_sleep_result(payload.session_id, sleep_profile, sleep_color_dict)

    background_tasks.add_task(
        mood_light_client.push_color,
        {
            "mode": "sleep",
            "emotion": "settled",
            **sleep_color_dict,
        },
    )

    session_state.clear()

    return SessionEndResponse(
        dominant_emotion=dominant,
        average_emotions=average,
        sleep_color=sleep_color,
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_session_router.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 커밋**

```bash
git add models/emotion.py routers/session.py tests/test_session_router.py
git commit -m "feat: add /session/start and /session/live endpoints"
```

---

## Task 4: 백엔드 — `/care/turn`이 session_id를 자동 채택

**Files:**
- Modify: `routers/care.py`
- Test: `tests/test_care_router.py`

**Interfaces:**
- Consumes: Task 1의 `session_state.adopt`.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_care_router.py` 상단 import 교체:
```python
from services import emotion_session, session_state
```
(기존 `from services import emotion_session` 줄을 이걸로 교체)

파일 끝에 추가:
```python
def test_turn_adopts_session_id_as_current_session(monkeypatch, tmp_path):
    session_state.clear()
    emotion_session.SESSIONS.clear()
    monkeypatch.setattr(care_router, "TEMP_DIR", str(tmp_path))
    monkeypatch.setattr(care_router, "ensure_wav_16k_mono", lambda inp, out: inp)
    _patch_happy_path(monkeypatch)

    client = TestClient(_build_app())
    _post(client, session_id="s7")

    assert session_state.get_current() == "s7"
    session_state.clear()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `pytest tests/test_care_router.py -v -k adopts_session_id`
Expected: FAIL — `assert None == 's7'` (아직 adopt 호출 안 함)

- [ ] **Step 3: 최소 구현 작성**

`routers/care.py`의 import 블록 수정:
```python
from services import (
    color_care_service,
    emotion_classifier_service,
    emotion_session,
    session_state,
    tts_service,
    voice_service,
)
```

`turn()` 함수 안 `emotion_session.add_assistant_turn(session_id, reply_text)` 바로 다음 줄에 추가:
```python
        emotion_session.add_assistant_turn(session_id, reply_text)
        session_state.adopt(session_id)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `pytest tests/test_care_router.py -v`
Expected: PASS (전체)

- [ ] **Step 5: 전체 백엔드 테스트 확인 + 커밋**

Run: `pytest tests/ -q`
Expected: PASS (전체, Task 1~4에서 추가/수정한 모든 테스트 포함). `tests/`로 범위를 좁히는 이유:
저장소 루트에서 `pytest -q`를 그냥 돌리면 `CosyVoice/` 서브모듈까지 수집하려다
`ModuleNotFoundError: No module named 'tensorrt_llm'`로 죽는다 (이 플랜과 무관한 기존 환경 이슈).

```bash
git add routers/care.py tests/test_care_router.py
git commit -m "feat: auto-adopt session_id as current session on /care/turn"
```

---

## Task 5: 프론트 — API 계층 (`types.ts`, `client.ts`)

**Files:**
- Modify: `front-ui/src/api/types.ts`
- Modify: `front-ui/src/api/client.ts`

**Interfaces:**
- Produces: `startSession(): Promise<SessionStartResponse>`,
  `fetchLive(): Promise<SessionLiveResponse>`. Task 6의 `useLivePolling`과 Task 9의
  `IntroScreen`이 이 함수들을 가져다 쓴다.
- 제거: `analyzeVoice`, `synthesizeSpeech`, `VoiceAnalyzeResponse` (front-ui가 더 이상 녹음/TTS를
  하지 않으므로 사용처가 없어짐).

이 태스크는 순수 타입/fetch 래퍼라 별도 유닛 테스트 없이 진행한다 (Task 6, 7의 훅/리듀서 테스트가
간접적으로 계약을 검증한다). 대신 각 단계 후 `npx tsc -b --noEmit`으로 타입 에러가 없는지 확인한다.

- [ ] **Step 1: `types.ts`에서 `VoiceAnalyzeResponse` 제거, 새 타입 추가**

`front-ui/src/api/types.ts`의 `VoiceAnalyzeResponse` interface 블록(9~19줄)을 삭제하고 그 자리에:
```ts
// Mirrors models/emotion.py SessionStartResponse
export interface SessionStartResponse {
  session_id: string
}

// Mirrors models/emotion.py SessionLiveResponse
export interface SessionLiveResponse {
  session_id: string | null
  has_session: boolean
  ended: boolean
  turn_count: number
  transcript: string | null
  care_emotion: string | null
  care_confidence: number | null
  care_color: CareColor | null
  reply_text: string | null
}
```

- [ ] **Step 2: `client.ts`에서 `analyzeVoice`/`synthesizeSpeech` 제거, `startSession`/`fetchLive` 추가**

`front-ui/src/api/client.ts` 상단 import를:
```ts
import type { CareColor, DiaryGenerateResponse, SessionEndResponse, SessionLiveResponse, SessionStartResponse } from './types'
```
로 교체하고, `analyzeVoice`와 `synthesizeSpeech` 함수 전체(22~55줄)를 삭제한 뒤 그 자리에:
```ts
export async function startSession(): Promise<SessionStartResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/session/start`, { method: 'POST' })
  return handleResponse<SessionStartResponse>(res)
}

export async function fetchLive(): Promise<SessionLiveResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/session/live`)
  return handleResponse<SessionLiveResponse>(res)
}
```

- [ ] **Step 3: 타입 체크**

Run: `cd front-ui && npx tsc -b --noEmit`
Expected: 이 시점에는 `ConversationScreen.tsx` 등이 아직 `analyzeVoice`를 참조하고 있어 에러가 남 —
정상이다 (Task 8에서 해소됨). `types.ts`/`client.ts` 자체에는 에러가 없어야 한다.

- [ ] **Step 4: 커밋**

```bash
git add front-ui/src/api/types.ts front-ui/src/api/client.ts
git commit -m "feat: replace voice/tts API calls with session start/live polling calls"
```

---

## Task 6: 프론트 — 녹음/TTS 관련 코드 제거

**Files:**
- Delete: `front-ui/src/hooks/useAudioRecorder.ts`
- Delete: `front-ui/src/hooks/useMicWaveform.ts`
- Delete: `front-ui/src/components/PitchWaveform.tsx`
- Modify: `front-ui/src/components/MoongFace.tsx`

**Interfaces:**
- Produces: `MoongFace()` — **props 없음** (기존엔 `{ audioElement, isSpeaking }`를 받았음). Task 9의
  `ConversationScreen`이 `<MoongFace />`로 호출한다.

- [ ] **Step 1: 사용처가 이 셋뿐인지 재확인**

Run: `grep -rn "useAudioRecorder\|useMicWaveform\|PitchWaveform" front-ui/src`
Expected: `ConversationScreen.tsx`에서만 나옴 (그 파일은 Task 9에서 다시 씀). 다른 곳에서 나오면 이
태스크를 멈추고 그 사용처부터 확인한다.

- [ ] **Step 2: 파일 삭제**

```bash
rm front-ui/src/hooks/useAudioRecorder.ts front-ui/src/hooks/useMicWaveform.ts front-ui/src/components/PitchWaveform.tsx
```

- [ ] **Step 3: `MoongFace.tsx`에서 오디오 진폭 로직 제거**

`front-ui/src/components/MoongFace.tsx` 전체를 아래로 교체 (눈 깜빡임만 남기고, 입은 항상 중립
상태로 고정 — 재생할 TTS 오디오가 front에 더 이상 없으므로):
```tsx
import { useEffect, useState } from 'react'

function useBlinking(): boolean {
  const [eyesOpen, setEyesOpen] = useState(true)
  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout>
    const scheduleNext = () => {
      const delay = 2000 + Math.random() * 4000
      timeout = setTimeout(() => {
        setEyesOpen(false)
        timeout = setTimeout(() => {
          setEyesOpen(true)
          scheduleNext()
        }, 150)
      }, delay)
    }
    scheduleNext()
    return () => clearTimeout(timeout)
  }, [])
  return eyesOpen
}

export function MoongFace() {
  const eyesOpen = useBlinking()
  const eyeScaleY = eyesOpen ? 1 : 0.08

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 64 64"
      width={220}
      height={220}
      aria-label="뭉이"
      style={{ filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.12))' }}
    >
      <circle cx="32" cy="32" r="32" fill="#f3cdb9" />
      <path
        d="M30,8 C42,8 52,16 54,28 C62,30 62,42 54,46 C54,56 44,60 34,58 C26,62 14,58 12,50 C4,48 4,36 12,32 C12,20 20,8 30,8 Z"
        fill="#fffdf8"
        stroke="#221f1c"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <circle cx="20" cy="36" r="1.8" fill="#f3cdb9" />
      <circle cx="44" cy="36" r="1.8" fill="#f3cdb9" />
      <circle
        cx="25" cy="30" r="2" fill="#221f1c"
        style={{ transform: `scaleY(${eyeScaleY})`, transformOrigin: '25px 30px', transition: 'transform 80ms ease' }}
      />
      <circle
        cx="39" cy="30" r="2" fill="#221f1c"
        style={{ transform: `scaleY(${eyeScaleY})`, transformOrigin: '39px 30px', transition: 'transform 80ms ease' }}
      />
      <path
        d="M28 38 q4 4 8 0"
        fill="none"
        stroke="#221f1c"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  )
}
```

- [ ] **Step 4: 커밋**

```bash
git add -A front-ui/src/hooks front-ui/src/components
git commit -m "chore: remove mic recording and TTS playback code from front-ui"
```

---

## Task 7: 프론트 — `useLivePolling` 훅

**Files:**
- Create: `front-ui/src/hooks/useLivePolling.ts`
- Test: `front-ui/src/hooks/useLivePolling.test.ts`

**Interfaces:**
- Consumes: Task 5의 `fetchLive()`.
- Produces: `useLivePolling(): { data: SessionLiveResponse | null; consecutiveFailures: number }`.
  Task 8의 `useLiveSync`가 이 훅을 그대로 가져다 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

`front-ui/src/hooks/useLivePolling.test.ts`:
```ts
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { useLivePolling } from './useLivePolling'

const sample = {
  session_id: 's1', has_session: true, ended: false, turn_count: 1,
  transcript: '안녕', care_emotion: 'joy', care_confidence: 0.8,
  care_color: { hex: '#F6C66D', brightness: 0.5, transition_ms: 1200 },
  reply_text: '반가워!',
}

describe('useLivePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('fetches immediately on mount and stores the result', async () => {
    vi.spyOn(client, 'fetchLive').mockResolvedValue(sample)

    const { result } = renderHook(() => useLivePolling())
    await act(async () => {
      await Promise.resolve()
    })

    expect(result.current.data).toEqual(sample)
    expect(result.current.consecutiveFailures).toBe(0)
  })

  it('counts consecutive failures without discarding the last good data', async () => {
    vi.spyOn(client, 'fetchLive').mockResolvedValueOnce(sample).mockRejectedValue(new Error('network error'))

    const { result } = renderHook(() => useLivePolling())
    await act(async () => {
      await Promise.resolve()
    })
    expect(result.current.data).toEqual(sample)

    await act(async () => {
      vi.advanceTimersByTime(1500)
      await Promise.resolve()
    })
    expect(result.current.consecutiveFailures).toBe(1)
    expect(result.current.data).toEqual(sample)

    await act(async () => {
      vi.advanceTimersByTime(1500)
      await Promise.resolve()
    })
    expect(result.current.consecutiveFailures).toBe(2)
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd front-ui && npx vitest run src/hooks/useLivePolling.test.ts`
Expected: FAIL — 모듈 `./useLivePolling`이 없어서 에러

- [ ] **Step 3: 최소 구현 작성**

`front-ui/src/hooks/useLivePolling.ts`:
```ts
import { useEffect, useState } from 'react'
import { fetchLive } from '../api/client'
import type { SessionLiveResponse } from '../api/types'

const POLL_INTERVAL_MS = 1500

export interface LivePollingState {
  data: SessionLiveResponse | null
  consecutiveFailures: number
}

export function useLivePolling(): LivePollingState {
  const [state, setState] = useState<LivePollingState>({ data: null, consecutiveFailures: 0 })

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const result = await fetchLive()
        if (cancelled) return
        setState({ data: result, consecutiveFailures: 0 })
      } catch {
        if (cancelled) return
        setState((prev) => ({ data: prev.data, consecutiveFailures: prev.consecutiveFailures + 1 }))
      }
    }

    poll()
    const id = setInterval(poll, POLL_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [])

  return state
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd front-ui && npx vitest run src/hooks/useLivePolling.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 5: 커밋**

```bash
git add front-ui/src/hooks/useLivePolling.ts front-ui/src/hooks/useLivePolling.test.ts
git commit -m "feat: add useLivePolling hook for session/live polling"
```

---

## Task 8: 프론트 — `ConversationContext` 재구성 (녹음 상태 제거, 실시간 턴/연결 상태 추가)

**Files:**
- Modify: `front-ui/src/state/ConversationContext.tsx`
- Test: `front-ui/src/state/ConversationContext.test.ts`

**Interfaces:**
- Produces (변경된 부분만): `ConversationState`에서 `recordingStatus`, `turnCount`,
  `turnErrorMessage` 제거, `connectionIssue: boolean` 추가. `ConversationAction`에서
  `RECORDING_STARTED`, `RECORDING_STOPPED_ANALYZING`, `TURN_SUCCESS`, `TURN_ERROR` 제거,
  `LIVE_TURN { turn: TurnResult }`와 `CONNECTION_ISSUE { hasIssue: boolean }` 추가.
  `START_CONVERSATION { sessionId }`, `END_REQUESTED`, `SESSION_ENDED`, `DIARY_READY`,
  `ENDING_ERROR`, `RESET`은 시그니처 그대로 유지. Task 9(`LiveSync`)와 Task 10(화면들)이 이 상태를
  가져다 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

`front-ui/src/state/ConversationContext.test.ts`:
```ts
import { describe, expect, it } from 'vitest'
import { conversationReducer, initialConversationState, type ConversationState } from './ConversationContext'

const color = { hex: '#F6C66D', brightness: 0.5, transition_ms: 1200 }

describe('conversationReducer', () => {
  it('START_CONVERSATION resets state, sets the session, and clears connectionIssue', () => {
    const dirty: ConversationState = { ...initialConversationState, connectionIssue: true }
    const next = conversationReducer(dirty, { type: 'START_CONVERSATION', sessionId: 's1' })
    expect(next.screen).toBe('conversation')
    expect(next.sessionId).toBe('s1')
    expect(next.connectionIssue).toBe(false)
  })

  it('LIVE_TURN updates the current turn without changing the screen', () => {
    const state: ConversationState = { ...initialConversationState, screen: 'conversation', sessionId: 's1' }
    const turn = { transcript: '안녕', careEmotion: 'joy', careColor: color, replyText: '반가워!' }
    const next = conversationReducer(state, { type: 'LIVE_TURN', turn })
    expect(next.currentTurn).toEqual(turn)
    expect(next.screen).toBe('conversation')
  })

  it('CONNECTION_ISSUE sets the flag', () => {
    const next = conversationReducer(initialConversationState, { type: 'CONNECTION_ISSUE', hasIssue: true })
    expect(next.connectionIssue).toBe(true)
  })

  it('END_REQUESTED moves to the ending screen in a loading state', () => {
    const state: ConversationState = { ...initialConversationState, screen: 'conversation', sessionId: 's1' }
    const next = conversationReducer(state, { type: 'END_REQUESTED' })
    expect(next.screen).toBe('ending')
    expect(next.ending.status).toBe('loading')
  })

  it('RESET returns to the initial state', () => {
    const state: ConversationState = { ...initialConversationState, screen: 'ending', sessionId: 's1', connectionIssue: true }
    expect(conversationReducer(state, { type: 'RESET' })).toEqual(initialConversationState)
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd front-ui && npx vitest run src/state/ConversationContext.test.ts`
Expected: FAIL — `LIVE_TURN`/`CONNECTION_ISSUE` 액션이 없어서 타입/런타임 에러

- [ ] **Step 3: 최소 구현 작성**

`front-ui/src/state/ConversationContext.tsx` 전체를 아래로 교체:
```tsx
import { createContext, useContext, useReducer, type Dispatch, type ReactNode } from 'react'
import type { CareColor } from '../api/types'

export type Screen = 'intro' | 'conversation' | 'ending'
export type EndingStatus = 'idle' | 'loading' | 'done' | 'error'

export interface TurnResult {
  transcript: string
  careEmotion: string
  careColor: CareColor
  replyText: string
}

export interface EndingState {
  status: EndingStatus
  dominantEmotion: string | null
  sleepColor: CareColor | null
  letterText: string | null
  errorMessage: string | null
}

export interface ConversationState {
  screen: Screen
  sessionId: string | null
  currentTurn: TurnResult | null
  connectionIssue: boolean
  ending: EndingState
}

export type ConversationAction =
  | { type: 'START_CONVERSATION'; sessionId: string }
  | { type: 'LIVE_TURN'; turn: TurnResult }
  | { type: 'CONNECTION_ISSUE'; hasIssue: boolean }
  | { type: 'END_REQUESTED' }
  | { type: 'SESSION_ENDED'; dominantEmotion: string; sleepColor: CareColor }
  | { type: 'DIARY_READY'; letterText: string }
  | { type: 'ENDING_ERROR'; message: string }
  | { type: 'RESET' }

export const initialConversationState: ConversationState = {
  screen: 'intro',
  sessionId: null,
  currentTurn: null,
  connectionIssue: false,
  ending: { status: 'idle', dominantEmotion: null, sleepColor: null, letterText: null, errorMessage: null },
}

export function conversationReducer(state: ConversationState, action: ConversationAction): ConversationState {
  switch (action.type) {
    case 'START_CONVERSATION':
      return { ...initialConversationState, screen: 'conversation', sessionId: action.sessionId }
    case 'LIVE_TURN':
      return { ...state, currentTurn: action.turn }
    case 'CONNECTION_ISSUE':
      return { ...state, connectionIssue: action.hasIssue }
    case 'END_REQUESTED':
      return { ...state, screen: 'ending', ending: { ...initialConversationState.ending, status: 'loading' } }
    case 'SESSION_ENDED':
      return {
        ...state,
        ending: { ...state.ending, dominantEmotion: action.dominantEmotion, sleepColor: action.sleepColor },
      }
    case 'DIARY_READY':
      return { ...state, ending: { ...state.ending, status: 'done', letterText: action.letterText } }
    case 'ENDING_ERROR':
      return { ...state, ending: { ...state.ending, status: 'error', errorMessage: action.message } }
    case 'RESET':
      return initialConversationState
    default:
      return state
  }
}

interface ConversationContextValue {
  state: ConversationState
  dispatch: Dispatch<ConversationAction>
}

const ConversationContext = createContext<ConversationContextValue | null>(null)

export function ConversationProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(conversationReducer, initialConversationState)
  return <ConversationContext.Provider value={{ state, dispatch }}>{children}</ConversationContext.Provider>
}

export function useConversation(): ConversationContextValue {
  const ctx = useContext(ConversationContext)
  if (!ctx) throw new Error('useConversation must be used within a ConversationProvider')
  return ctx
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd front-ui && npx vitest run src/state/ConversationContext.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 5: 커밋**

```bash
git add front-ui/src/state/ConversationContext.tsx front-ui/src/state/ConversationContext.test.ts
git commit -m "refactor: replace recording state with live-turn and connection-issue state"
```

---

## Task 9: 프론트 — `LiveSync` (폴링 → 화면 자동 전환)

**Files:**
- Create: `front-ui/src/state/LiveSync.tsx`
- Test: `front-ui/src/state/LiveSync.test.tsx`

**Interfaces:**
- Consumes: Task 7의 `useLivePolling()`, Task 8의 `useConversation()`/액션들.
- Produces: `<LiveSync />` — 렌더링 결과 없는(`null`) 컴포넌트. Task 11에서 `App.tsx`에
  마운트한다.

**핵심 전환 규칙** (한 곳에서만 화면 전환을 결정한다):
- `screen === 'intro'`이고 폴링 결과 `has_session`이 true면 → `START_CONVERSATION`.
- `screen === 'conversation'`인데 현재 세션이 더 이상 "그 세션이 진행 중"이 아니면(= `has_session`이
  false거나, 폴링이 준 `session_id`가 지금 화면이 들고 있는 `sessionId`와 다르거나, `ended`가
  true) → `END_REQUESTED`. (참고: `POST /session/end`가 성공하면 서버의 "현재 세션" 포인터를 지우기
  때문에, 종료 직후엔 `has_session`이 먼저 false로 바뀔 수 있다 — 그래서 `ended` 플래그 하나만 보면
  안 되고 "더 이상 이 세션이 진행 중이 아니다"를 폭넓게 잡아야 한다.)
- 그 외엔(진행 중) 턴 스냅샷이 다 채워져 있으면 `LIVE_TURN`.

- [ ] **Step 1: 실패하는 테스트 작성**

`front-ui/src/state/LiveSync.test.tsx`:
```tsx
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { ConversationProvider, useConversation } from './ConversationContext'
import { LiveSync } from './LiveSync'

function ScreenProbe() {
  const { state } = useConversation()
  return <div data-testid="screen">{state.screen}</div>
}

function renderApp() {
  return render(
    <ConversationProvider>
      <LiveSync />
      <ScreenProbe />
    </ConversationProvider>,
  )
}

describe('LiveSync', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('moves from intro to conversation once a session becomes active', async () => {
    vi.spyOn(client, 'fetchLive').mockResolvedValue({
      session_id: 's1', has_session: true, ended: false, turn_count: 0,
      transcript: null, care_emotion: null, care_confidence: null, care_color: null, reply_text: null,
    })

    renderApp()
    await act(async () => {
      await Promise.resolve()
    })

    expect(screen.getByTestId('screen').textContent).toBe('conversation')
  })

  it('moves to ending once the current session reports ended', async () => {
    vi.spyOn(client, 'fetchLive').mockResolvedValue({
      session_id: 's1', has_session: true, ended: false, turn_count: 0,
      transcript: null, care_emotion: null, care_confidence: null, care_color: null, reply_text: null,
    })
    renderApp()
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByTestId('screen').textContent).toBe('conversation')

    vi.spyOn(client, 'fetchLive').mockResolvedValue({
      session_id: 's1', has_session: true, ended: true, turn_count: 1,
      transcript: '안녕', care_emotion: 'joy', care_confidence: 0.8,
      care_color: { hex: '#F6C66D', brightness: 0.5, transition_ms: 1200 }, reply_text: '반가워!',
    })
    await act(async () => {
      vi.advanceTimersByTime(1500)
      await Promise.resolve()
    })

    expect(screen.getByTestId('screen').textContent).toBe('ending')
  })

  it('moves to ending when the session pointer disappears (end() already cleared it)', async () => {
    vi.spyOn(client, 'fetchLive').mockResolvedValue({
      session_id: 's1', has_session: true, ended: false, turn_count: 0,
      transcript: null, care_emotion: null, care_confidence: null, care_color: null, reply_text: null,
    })
    renderApp()
    await act(async () => {
      await Promise.resolve()
    })
    expect(screen.getByTestId('screen').textContent).toBe('conversation')

    vi.spyOn(client, 'fetchLive').mockResolvedValue({
      session_id: null, has_session: false, ended: false, turn_count: 0,
      transcript: null, care_emotion: null, care_confidence: null, care_color: null, reply_text: null,
    })
    await act(async () => {
      vi.advanceTimersByTime(1500)
      await Promise.resolve()
    })

    expect(screen.getByTestId('screen').textContent).toBe('ending')
  })
})
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd front-ui && npx vitest run src/state/LiveSync.test.tsx`
Expected: FAIL — 모듈 `./LiveSync`가 없어서 에러

- [ ] **Step 3: 최소 구현 작성**

`front-ui/src/state/LiveSync.tsx`:
```tsx
import { useEffect } from 'react'
import { useLivePolling } from '../hooks/useLivePolling'
import { useConversation } from './ConversationContext'

export function useLiveSync(): void {
  const live = useLivePolling()
  const { state, dispatch } = useConversation()

  useEffect(() => {
    dispatch({ type: 'CONNECTION_ISSUE', hasIssue: live.consecutiveFailures >= 3 })
  }, [live.consecutiveFailures, dispatch])

  useEffect(() => {
    const data = live.data
    if (!data) return

    if (state.screen === 'intro') {
      if (data.has_session && data.session_id) {
        dispatch({ type: 'START_CONVERSATION', sessionId: data.session_id })
      }
      return
    }

    if (state.screen === 'conversation') {
      const stillOngoing = data.has_session && data.session_id === state.sessionId && !data.ended
      if (!stillOngoing) {
        dispatch({ type: 'END_REQUESTED' })
        return
      }
      if (data.transcript && data.care_emotion && data.care_color && data.reply_text) {
        dispatch({
          type: 'LIVE_TURN',
          turn: {
            transcript: data.transcript,
            careEmotion: data.care_emotion,
            careColor: data.care_color,
            replyText: data.reply_text,
          },
        })
      }
    }
  }, [live.data, state.screen, state.sessionId, dispatch])
}

export function LiveSync() {
  useLiveSync()
  return null
}
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd front-ui && npx vitest run src/state/LiveSync.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: 커밋**

```bash
git add front-ui/src/state/LiveSync.tsx front-ui/src/state/LiveSync.test.tsx
git commit -m "feat: add LiveSync to drive screen transitions from session/live polling"
```

---

## Task 10: 프론트 — `IntroScreen`/`ConversationScreen` 재작성

**Files:**
- Modify: `front-ui/src/screens/IntroScreen.tsx`
- Modify: `front-ui/src/screens/ConversationScreen.tsx`

**Interfaces:**
- Consumes: Task 5의 `startSession()`, Task 6의 `<MoongFace />` (props 없음), Task 8의
  `ConversationState`/액션들.
- `EndingScreen.tsx`는 **수정하지 않는다** — `state.sessionId`/`state.ending` 필드가 그대로 있고
  `SESSION_ENDED`/`DIARY_READY`/`ENDING_ERROR` 액션 시그니처도 안 바뀌었으므로 컴파일/동작 그대로
  유지된다.

- [ ] **Step 1: `IntroScreen.tsx` — 시작 버튼이 실제로 `/session/start`를 호출하도록 수정**

`front-ui/src/screens/IntroScreen.tsx` 전체를 아래로 교체:
```tsx
import { useState } from 'react'
import { startSession } from '../api/client'
import { useTranslation } from '../i18n/LanguageContext'
import { useConversation } from '../state/ConversationContext'

export function IntroScreen() {
  const { t } = useTranslation()
  const { dispatch } = useConversation()
  const [error, setError] = useState(false)

  async function handleStart() {
    setError(false)
    try {
      const { session_id } = await startSession()
      dispatch({ type: 'START_CONVERSATION', sessionId: session_id })
    } catch {
      setError(true)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 20 }}>
      <h1>{t('appTitle')}</h1>
      <p>{t('introGreeting')}</p>
      <button
        style={{ padding: '12px 28px', borderRadius: 999, border: 'none', background: '#A7CDBD', fontSize: 16 }}
        onClick={handleStart}
      >
        {t('startConversationButton')}
      </button>
      {error && <p role="alert">{t('networkErrorRetry')}</p>}
    </div>
  )
}
```

- [ ] **Step 2: `ConversationScreen.tsx` — 녹음/TTS 제거, 폴링 데이터만 표시**

`front-ui/src/screens/ConversationScreen.tsx` 전체를 아래로 교체:
```tsx
import { EmotionAtmosphere } from '../components/EmotionAtmosphere'
import { EmotionColorBar } from '../components/EmotionColorBar'
import { MoongFace } from '../components/MoongFace'
import { SpeechBubble } from '../components/SpeechBubble'
import { useTranslation } from '../i18n/LanguageContext'
import { useConversation } from '../state/ConversationContext'

export function ConversationScreen() {
  const { t } = useTranslation()
  const { state, dispatch } = useConversation()

  return (
    <EmotionAtmosphere color={state.currentTurn?.careColor ?? null}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: 24, minHeight: '100vh' }}>
        <button
          onClick={() => dispatch({ type: 'END_REQUESTED' })}
          disabled={!state.currentTurn}
          style={{ alignSelf: 'flex-end', marginTop: 48, padding: '8px 16px', borderRadius: 999, border: '1px solid #ccc', background: '#fff' }}
        >
          {t('endConversationButton')}
        </button>

        <SpeechBubble status={state.currentTurn ? 'reply' : 'idle'} text={state.currentTurn?.replyText} />

        <MoongFace />

        {state.connectionIssue && <p role="alert">{t('networkErrorRetry')}</p>}

        {state.currentTurn && (
          <EmotionColorBar careEmotion={state.currentTurn.careEmotion} brightness={state.currentTurn.careColor.brightness} />
        )}
      </div>
    </EmotionAtmosphere>
  )
}
```

- [ ] **Step 3: 타입 체크**

Run: `cd front-ui && npx tsc -b --noEmit`
Expected: 에러 없음 (Task 5~10을 거치며 모든 참조가 새 API/상태 모양과 일치해야 한다)

- [ ] **Step 4: 커밋**

```bash
git add front-ui/src/screens/IntroScreen.tsx front-ui/src/screens/ConversationScreen.tsx
git commit -m "refactor: make IntroScreen/ConversationScreen passive displays driven by polling"
```

---

## Task 11: 프론트 — `App.tsx`에 `LiveSync` 연결 + 전체 테스트 통과 확인

**Files:**
- Modify: `front-ui/src/App.tsx`
- Modify: `front-ui/src/App.test.tsx`

**Interfaces:**
- Consumes: Task 9의 `<LiveSync />`.

- [ ] **Step 1: `App.tsx`에 `LiveSync` 마운트**

`front-ui/src/App.tsx`의 import 목록에 추가:
```tsx
import { LiveSync } from './state/LiveSync'
```
`App()` 컴포넌트의 반환문을 아래로 교체:
```tsx
export default function App() {
  return (
    <LanguageProvider>
      <ConversationProvider>
        <LiveSync />
        <LanguageToggle />
        <Screens />
      </ConversationProvider>
    </LanguageProvider>
  )
}
```

- [ ] **Step 2: `App.test.tsx`에서 폴링이 실제 네트워크를 치지 않도록 `fetch` 스텁 추가**

`front-ui/src/App.test.tsx` 전체를 아래로 교체:
```tsx
import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('network disabled in tests'))))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the MoongCare app shell', () => {
    render(<App />)
    expect(screen.getByText('뭉이')).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: 프론트 전체 테스트 통과 확인**

Run: `cd front-ui && npm run test`
Expected: PASS — 전체 스위트(기존 `careEmotions.test.ts`, `brightness.test.ts` 포함) 통과

- [ ] **Step 4: 백엔드 전체 테스트 통과 확인**

Run: `pytest tests/ -q`
Expected: PASS — 전체 스위트 통과 (Task 1~4에서 건드린 파일들 포함). 저장소 루트에서 범위 없이
`pytest -q`를 돌리면 `CosyVoice/` 서브모듈까지 수집하려다 `tensorrt_llm` 누락으로 깨진다 (기존
환경 이슈, 이 플랜과 무관 — 그래서 `tests/`로 범위를 좁힌다).

- [ ] **Step 5: 수동 확인 (dev 서버로 실제 흐름 확인)**

1. 백엔드 실행: `uvicorn main:app --reload` (localhost:8000)
2. 프론트 실행: `cd front-ui && npm run dev` (localhost:5173), 브라우저로 열기
3. Intro 화면에서 "대화 시작" 클릭 → Conversation 화면으로 전환되는지 확인 (콘솔 네트워크 탭에서
   `POST /api/v1/session/start` 호출 확인)
4. 다른 터미널에서 Pi 대신 curl로 턴 하나를 흉내낸다 (샘플 wav 파일 필요 — 예:
   `scripts/manual_test.html`이 만든 파일이나 아무 짧은 wav):
   ```bash
   curl -X POST http://localhost:8000/api/v1/care/turn \
     -F "session_id=<3단계에서 받은 session_id>" \
     -F "audio=@sample.wav;type=audio/wav" \
     -o /tmp/reply.wav
   ```
5. 2초 안에 브라우저 Conversation 화면에 감정 텍스트 + 배경색이 바뀌는지 확인 (폴링 확인)
6. "대화 종료" 클릭 → Ending 화면 전환 + 편지(letter_text) 표시 확인
7. "새 대화 시작" 클릭 → Intro로 복귀 확인

- [ ] **Step 6: 커밋**

```bash
git add front-ui/src/App.tsx front-ui/src/App.test.tsx
git commit -m "feat: wire LiveSync into App and stub fetch in App tests"
```
