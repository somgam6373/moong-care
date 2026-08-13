# 감정 케어 무드등 실제 개발 문서

날짜: 2026-08-13

관련 계획 문서:

- `docs/prompts_Engineering/2026-08-13-emotion-care-mood-light-development-plan.md`

## 목적

이 문서는 실제 코드 수정 전에 **어떤 파일을 어떻게 바꿀지 검토하기 위한 개발 문서**다.
구현은 이 문서가 승인된 뒤 진행한다.

핵심 변경은 다음 네 가지다.

1. emotion2vec top-1 대신 LLM이 14개 MoongCare 감정 분류 중 하나를 판단한다.
2. 감정별 고정 색상 테이블로 실시간 케어 색상을 정하고 라즈베리 파이에 HTTP push한다.
3. `session/end`에서 세션 전체 흐름을 기반으로 수면등 색상을 반환하고 push한다.
4. 기존 `diaries` 테이블은 유지하고, 뭉이 편지는 새 `letters` 전용 테이블에 저장한다.

---

## 1. 확정된 정책

### 1.1 감정 분류

허용 감정은 14개로 고정한다.

```python
ALLOWED_CARE_EMOTIONS = {
    "calm",
    "joy",
    "excitement",
    "relief",
    "sadness",
    "loneliness",
    "anxiety",
    "tension",
    "anger",
    "stress",
    "fatigue",
    "helplessness",
    "confusion",
    "shame_guilt",
}
```

LLM은 이 목록 밖의 감정을 반환할 수 없다. 반환하면 실패로 간주한다.

### 1.2 fallback

다음 상황에서는 모두 `calm`으로 fallback한다.

- transcript가 비어 있거나 실질 텍스트가 너무 짧은 경우
- OpenAI 호출 실패
- OpenAI 응답이 JSON이 아닌 경우
- JSON은 맞지만 `care_emotion`이 허용 목록 밖인 경우
- confidence가 숫자가 아니거나 파싱 불가한 경우

fallback 시에도 API는 정상 응답한다. 실시간 무드등에는 `calm` 색상 `#A7CDBD`를 보낸다.

### 1.3 색상 생성

LLM은 색상을 만들지 않는다.

- LLM 역할: `care_emotion` 판단
- 서버 역할: `care_emotion -> CareColor` 매핑
- 라즈베리 파이 역할: 서버가 보낸 `hex/brightness/transition_ms` 표시

### 1.4 라즈베리 파이 push 실패

- `MOOD_LIGHT_ENDPOINT`가 비어 있으면 no-op
- 연결 실패/timeout은 warning log만 남김
- API 응답은 실패시키지 않음
- 초기 버전에서는 재시도/큐잉 없음

---

## 2. 새 파일 추가

### 2.1 `models/care.py`

공통 Pydantic 모델을 둔다. `voice`, `session`, mood light push에서 재사용한다.

```python
from typing import Literal

from pydantic import BaseModel


class CareColor(BaseModel):
    hex: str
    brightness: float
    transition_ms: int


class MoodLightPayload(BaseModel):
    mode: Literal["realtime", "sleep"]
    emotion: str
    hex: str
    brightness: float
    transition_ms: int
```

검증은 `color_care_service`에서 먼저 수행하고, Pydantic은 API 직렬화 형태를 고정하는 용도로 쓴다.

### 2.2 `models/letter.py`

편지 목록/상세 조회 모델을 분리한다.

```python
from datetime import datetime

from pydantic import BaseModel

from models.care import CareColor


class LetterListItem(BaseModel):
    id: int
    session_id: str
    diary_id: int | None
    summary: str
    dominant_emotion: str
    created_at: datetime


class LetterDetail(BaseModel):
    id: int
    session_id: str
    diary_id: int | None
    letter_text: str
    summary: str
    dominant_emotion: str
    sleep_color: CareColor | None
    created_at: datetime
```

### 2.3 `database/letter_repository.py`

새 `letters` 테이블과 저장/조회 함수를 추가한다.

초기 스키마:

| column | type | nullable | 설명 |
|---|---|---:|---|
| `id` | Integer PK | N | letter id |
| `session_id` | String(64) | N | 원본 세션 id |
| `diary_id` | Integer | Y | 같은 세션에서 생성된 diary id |
| `letter_text` | Text | N | 뭉이 편지 전문 |
| `summary` | String(255) | N | 편지 요약 |
| `dominant_emotion` | String(32) | N | 세션 대표 감정 |
| `sleep_color` | Text | Y | JSON 문자열 |
| `created_at` | DateTime | N | 생성 시각 |

초기에는 `diary_id`에 DB foreign key를 걸지 않는다. 기존 테스트와 로컬 MySQL 환경에서 migration 없이
안전하게 추가하기 위함이다.

함수:

```python
def save_letter(
    db: Session,
    session_id: str,
    diary_id: int | None,
    letter_text: str,
    summary: str,
    dominant_emotion: str,
    sleep_color: dict | None,
) -> Letter:
    ...


def get_letter(db: Session, letter_id: int) -> Letter | None:
    ...


def list_letters(db: Session, session_id: str | None = None) -> list[Letter]:
    ...
```

### 2.4 `services/emotion_classifier_service.py`

LLM 감정 분류 전용 서비스다.

책임:

- prompt 구성
- OpenAI 호출
- JSON 파싱
- 허용 감정 검증
- 실패 시 `calm` fallback

예상 인터페이스:

```python
from dataclasses import dataclass


FALLBACK_CARE_EMOTION = "calm"


@dataclass
class CareEmotionResult:
    care_emotion: str
    care_emotion_label: str
    confidence: float
    reason: str
    fallback: bool = False


def classify_realtime_emotion(
    transcript: str,
    voice_emotion_scores: dict[str, float],
    pitch_mean: float,
    pitch_std: float,
    recent_context: list[dict],
) -> CareEmotionResult:
    ...
```

구현 원칙:

- `temperature=0`으로 호출한다.
- `response_format={"type": "json_object"}` 사용을 우선한다.
- SDK/모델 문제로 `response_format`이 실패하면 기존 Chat Completions 방식으로 fallback하지 않고
  해당 호출 실패를 `calm` fallback으로 처리한다. 즉 코드 경로를 복잡하게 늘리지 않는다.
- `reason`은 내부 디버깅용이며 API 응답에는 노출하지 않는다.

### 2.5 `services/color_care_service.py`

고정 색상 매핑 전용 서비스다.

예상 인터페이스:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CareColor:
    hex: str
    brightness: float
    transition_ms: int


def get_realtime_color(care_emotion: str) -> CareColor:
    ...


def get_sleep_color(sleep_profile: str) -> CareColor:
    ...
```

`care_emotion`이 허용 목록 밖이면 `calm` 색상으로 fallback한다.
`sleep_profile`이 허용 목록 밖이면 `warm_dim`으로 fallback한다.

### 2.6 `services/mood_light_client.py`

라즈베리 파이에 HTTP POST를 보내는 클라이언트다.

새 dependency를 추가하지 않기 위해 Python 표준 라이브러리 `urllib.request`를 사용한다.

예상 인터페이스:

```python
def push_color(payload: dict) -> bool:
    ...
```

동작:

- endpoint 미설정: `False` 반환, 로그 없음 또는 debug log
- 성공: `True` 반환
- 실패/timeout: warning log 후 `False` 반환
- 예외를 route 밖으로 던지지 않는다.

### 2.7 `services/sleep_color_service.py`

세션 전체 care emotion timeline을 수면 프로필로 요약한다. 초기 버전은 LLM을 쓰지 않고 규칙 기반으로 한다.

예상 인터페이스:

```python
def choose_sleep_profile(care_timeline: list[dict]) -> str:
    ...
```

규칙 초안:

1. `shame_guilt` 비중이 가장 높거나 충분히 높으면 `low_rose`
2. `anxiety`, `tension`, `anger`, `stress`, `confusion` 그룹이 가장 강하면 `deep_amber`
3. `sadness`, `loneliness`, `fatigue`, `helplessness` 그룹이 가장 강하면 `soft_peach`
4. 그 외는 `warm_dim`

### 2.8 `services/letter_service.py`

뭉이 편지 생성 전용 OpenAI 서비스다.

예상 인터페이스:

```python
def generate_letter(
    history: list[TurnRecord],
    average_emotions: dict[str, float],
    care_timeline: list[dict],
    sleep_color: dict | None,
) -> str:
    ...
```

프롬프트 원칙:

- 뭉이가 사용자에게 직접 보내는 편지 형식
- 사용자가 말한 구체적 사건을 반영
- 감정 진단/치료 표현 금지
- 마지막에 수면 전 무드등 색상을 부드럽게 언급
- 5~8문장 정도

### 2.9 `routers/letter.py`

편지 조회용 라우터를 추가한다. 생성은 `diary/generate`에서 수행한다.

```python
router = APIRouter(prefix="/api/v1/letter", tags=["letter"])

@router.get("", response_model=list[LetterListItem])
async def list_letter(session_id: str | None = None, db: Session = Depends(get_db)):
    ...

@router.get("/{letter_id}", response_model=LetterDetail)
async def get_letter_detail(letter_id: int, db: Session = Depends(get_db)):
    ...
```

---

## 3. 기존 파일 수정

### 3.1 `config.py`

추가:

```python
MOOD_LIGHT_ENDPOINT: str = ""
MOOD_LIGHT_TIMEOUT_SECONDS: float = 2.0
```

`.env.example`에도 같은 키를 추가한다.

### 3.2 `database/connection.py`

`init_db()`에서 `letter_repository`도 import해 `letters` 테이블이 생성되게 한다.

```python
def init_db() -> None:
    from database import diary_repository  # noqa: F401
    from database import letter_repository  # noqa: F401
    Base.metadata.create_all(bind=engine)
```

### 3.3 `services/emotion_session.py`

`TurnRecord`를 확장한다. 기존 호출이 깨지지 않도록 모든 새 필드는 기본값을 둔다.

```python
@dataclass
class TurnRecord:
    role: str
    text: str
    emotions: dict[str, float] | None = None
    pitch_mean: float | None = None
    pitch_std: float | None = None
    care_emotion: str | None = None
    care_confidence: float | None = None
    care_color: dict | None = None
```

`SessionState`에 수면등 결과를 저장한다.

```python
self.sleep_profile: str | None = None
self.sleep_color: dict | None = None
```

함수 변경/추가:

```python
def add_user_turn(
    session_id: str,
    transcript: str,
    emotions: dict[str, float],
    pitch_mean: float | None = None,
    pitch_std: float | None = None,
    care_emotion: str | None = None,
    care_confidence: float | None = None,
    care_color: dict | None = None,
) -> None:
    ...


def get_recent_context(session_id: str, limit: int = 4) -> list[dict]:
    ...


def get_care_timeline(session_id: str) -> list[dict]:
    ...


def set_sleep_result(session_id: str, sleep_profile: str, sleep_color: dict) -> None:
    ...


def get_sleep_result(session_id: str) -> tuple[str | None, dict | None]:
    ...
```

기존 `compute_average()`는 emotion2vec raw scores 기준으로 그대로 유지한다.

### 3.4 `models/voice.py`

`VoiceAnalyzeResponse`에 필드를 추가한다.

```python
class VoiceAnalyzeResponse(BaseModel):
    transcript: str
    emotions: dict[str, float]
    pitch_mean: float
    pitch_std: float
    care_emotion: str
    care_emotion_label: str
    care_confidence: float
    care_color: CareColor
```

### 3.5 `models/emotion.py`

`SessionEndResponse`에 수면등 색상을 추가한다.

```python
class SessionEndResponse(BaseModel):
    dominant_emotion: str
    average_emotions: dict[str, float]
    sleep_color: CareColor
```

### 3.6 `models/diary.py`

`DiaryGenerateResponse`에 편지 id/text를 추가한다.

```python
class DiaryGenerateResponse(BaseModel):
    diary_id: int
    letter_id: int
    diary_text: str
    letter_text: str
    summary: str
    dominant_emotion: str
```

기존 `DiaryListItem`, `DiaryDetail`은 우선 변경하지 않는다.

### 3.7 `routers/voice.py`

변경 흐름:

1. 기존처럼 webm 저장
2. wav 변환
3. `voice_service.analyze_voice()`로 `transcript/emotions/pitch` 획득
4. `emotion_session.get_recent_context(session_id)` 조회
5. `emotion_classifier_service.classify_realtime_emotion(...)` 호출
6. `color_care_service.get_realtime_color(care_emotion)` 호출
7. 확장된 `emotion_session.add_user_turn(...)`에 raw score와 care 결과 저장
8. `BackgroundTasks`로 `mood_light_client.push_color(...)` 등록
9. 확장된 `VoiceAnalyzeResponse` 반환

라우터 signature는 다음처럼 바뀐다.

```python
async def analyze(
    request: Request,
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    audio: UploadFile = None,
):
    ...
```

OpenAI 호출은 동기 SDK이므로 `run_in_threadpool`로 감싼다.

### 3.8 `routers/session.py`

변경 흐름:

1. 기존 `compute_average(session_id)` 유지
2. `emotion_session.get_care_timeline(session_id)` 조회
3. `sleep_color_service.choose_sleep_profile(...)` 호출
4. `color_care_service.get_sleep_color(profile)` 호출
5. `emotion_session.set_sleep_result(...)` 저장
6. `BackgroundTasks`로 sleep mode payload push
7. `sleep_color` 포함 응답 반환

라우터 signature:

```python
async def end(payload: SessionEndRequest, background_tasks: BackgroundTasks):
    ...
```

### 3.9 `routers/diary.py`

`generate()`는 기존 diary 저장을 유지하면서 letter 저장을 추가한다.

변경 흐름:

1. 세션 조회
2. 기존 `compute_average()` 수행
3. 기존 `diary_service.generate_diary()` 수행
4. 기존 `summary_service.summarize_diary()` 수행
5. 세션의 `sleep_color`가 있으면 사용, 없으면 `sleep_color_service`로 즉시 계산
6. `letter_service.generate_letter(...)` 수행
7. 기존 `save_diary()` 수행
8. `letter_repository.save_letter(...)` 수행
9. diary와 letter가 모두 저장된 뒤 세션 clear
10. `diary_id`, `letter_id`, `diary_text`, `letter_text` 반환

주의:

- letter 생성 실패 시 diary만 저장하고 세션을 지우는 일을 피하기 위해, letter text 생성은 DB 저장 전에 수행한다.
- 초기 구현은 트랜잭션 복잡도를 줄이기 위해 **letter 생성 실패 시 API 500, 세션 유지, diary 미저장**으로 한다.
- DB commit은 repository 함수 단위로 되어 있으므로 장기적으로는 트랜잭션 묶기를 검토한다.

### 3.10 `main.py`

새 라우터 등록:

```python
from routers import chat, diary, letter, session, tts, voice

app.include_router(letter.router)
```

---

## 4. API 응답 최종 형태

### 4.1 `POST /api/v1/voice/analyze`

```json
{
  "transcript": "오늘 발표 때문에 너무 긴장돼",
  "emotions": {
    "fearful": 0.42,
    "neutral": 0.3
  },
  "pitch_mean": 211.4,
  "pitch_std": 38.2,
  "care_emotion": "tension",
  "care_emotion_label": "긴장",
  "care_confidence": 0.74,
  "care_color": {
    "hex": "#7DCAC3",
    "brightness": 0.38,
    "transition_ms": 1800
  }
}
```

### 4.2 `POST /api/v1/session/end`

```json
{
  "dominant_emotion": "fearful",
  "average_emotions": {
    "fearful": 0.31,
    "neutral": 0.29
  },
  "sleep_color": {
    "hex": "#C9785A",
    "brightness": 0.16,
    "transition_ms": 6000
  }
}
```

### 4.3 `POST /api/v1/diary/generate`

```json
{
  "diary_id": 1,
  "letter_id": 1,
  "diary_text": "오늘은 발표 때문에 긴장했지만 끝나고 나서 조금 후련했다.",
  "letter_text": "오늘 네 이야기를 들으면서 발표 전의 긴장이 꽤 크게 느껴졌어...",
  "summary": "발표 전 긴장과 끝난 뒤의 안도감",
  "dominant_emotion": "fearful"
}
```

### 4.4 `GET /api/v1/letter`

```json
[
  {
    "id": 1,
    "session_id": "s1",
    "diary_id": 1,
    "summary": "발표 전 긴장과 끝난 뒤의 안도감",
    "dominant_emotion": "fearful",
    "created_at": "2026-08-13T12:00:00Z"
  }
]
```

### 4.5 `GET /api/v1/letter/{letter_id}`

```json
{
  "id": 1,
  "session_id": "s1",
  "diary_id": 1,
  "letter_text": "오늘 네 이야기를 들으면서...",
  "summary": "발표 전 긴장과 끝난 뒤의 안도감",
  "dominant_emotion": "fearful",
  "sleep_color": {
    "hex": "#C9785A",
    "brightness": 0.16,
    "transition_ms": 6000
  },
  "created_at": "2026-08-13T12:00:00Z"
}
```

---

## 5. 테스트 수정/추가 계획

### 5.1 새 테스트 파일

추가:

- `tests/test_color_care_service.py`
- `tests/test_emotion_classifier_service.py`
- `tests/test_mood_light_client.py`
- `tests/test_sleep_color_service.py`
- `tests/test_letter_service.py`
- `tests/test_letter_repository.py`
- `tests/test_letter_router.py`

### 5.2 기존 테스트 수정

수정:

- `tests/test_models.py`
  - `CareColor`
  - 확장된 `VoiceAnalyzeResponse`
  - 확장된 `SessionEndResponse`
  - 확장된 `DiaryGenerateResponse`
  - `LetterListItem`, `LetterDetail`

- `tests/test_voice_router.py`
  - 감정 분류 service mock
  - 색상 service mock 또는 고정 매핑 사용
  - mood light push mock
  - 응답에 `care_emotion`, `care_color` 검증

- `tests/test_session_router.py`
  - `sleep_color` 응답 검증
  - sleep mode push 검증

- `tests/test_diary_router.py`
  - `letter_service.generate_letter` mock
  - `letter_repository` 저장 확인
  - 응답의 `letter_id`, `letter_text` 검증

- `tests/test_emotion_session.py`
  - 확장 필드 저장
  - care timeline 조회
  - sleep result 저장/조회
  - 기존 평균 감정 계산 회귀

### 5.3 주요 테스트 케이스

`emotion_classifier_service`:

- 정상 JSON 응답을 `CareEmotionResult`로 변환
- OpenAI 호출 실패 시 `calm`, `fallback=True`
- JSON 파싱 실패 시 `calm`, `fallback=True`
- 허용 목록 밖 감정 시 `calm`, `fallback=True`
- 짧은 transcript는 OpenAI 호출 없이 `calm`

`color_care_service`:

- 14개 감정 모두 색상 매핑 존재
- sleep profile 4개 모두 색상 매핑 존재
- 알 수 없는 감정은 calm 색상
- 알 수 없는 sleep profile은 warm_dim 색상

`mood_light_client`:

- endpoint 비어 있으면 no-op
- 정상 endpoint면 JSON POST body가 맞는지
- timeout/connection error가 예외로 전파되지 않는지

`letter_repository`:

- 저장 후 조회
- session_id 필터 목록
- newest-first 정렬
- sleep_color JSON round-trip

---

## 6. 구현 순서

TDD 순서로 진행한다.

1. `models/care.py`, `models/voice.py`, `models/emotion.py`, `models/diary.py`, `models/letter.py`
2. `services/color_care_service.py`
3. `services/emotion_session.py` 확장
4. `services/emotion_classifier_service.py`
5. `services/mood_light_client.py`
6. `services/sleep_color_service.py`
7. `database/letter_repository.py`, `database/connection.py`
8. `services/letter_service.py`
9. `routers/voice.py`
10. `routers/session.py`
11. `routers/diary.py`
12. `routers/letter.py`, `main.py`
13. 전체 `pytest tests -q`

각 단계는 테스트 작성 또는 기존 테스트 수정 후 구현한다.

---

## 7. 변경하지 않는 것

초기 구현에서 의도적으로 건드리지 않는다.

- STT/SER/pitch 추론 자체
- `voice_service.analyze_voice()`의 병렬 실행 구조
- `chat/reply` 프롬프트
- `tts_service.resolve_instructions()`의 기존 raw emotion 기반 톤 매핑
- 기존 `diaries` 테이블 구조
- 기존 `GET /api/v1/diary`, `GET /api/v1/diary/{diary_id}` 응답 구조

---

## 8. 검토 포인트

구현 전 확인하면 좋은 지점:

1. `GET /api/v1/letter`, `GET /api/v1/letter/{letter_id}`를 이번 범위에 포함할지
2. `diary/generate`에서 letter 생성 실패 시 전체 실패로 둘지
3. `tts_service`도 raw emotion이 아니라 `care_emotion` 기반 톤으로 바꿀지
4. `session/end`의 `sleep_color`에 `sleep_profile`도 응답으로 노출할지

현재 문서의 기본안은 다음과 같다.

- letter 조회 endpoint는 포함한다.
- letter 생성 실패 시 `diary/generate` 전체를 실패시키고 세션은 유지한다.
- TTS는 이번 범위에서 바꾸지 않는다.
- `sleep_profile`은 API 응답에 노출하지 않고 내부 판단값으로만 저장한다.

---

## 9. 개발 후 후속 과제

이번 구현은 감정 케어 무드등 기능을 정확히 붙이는 것이 1차 목표다. 기능이 붙은 뒤에는 시연 안정성을 위해
응답 시간과 네트워크 의존성을 별도 과제로 다룬다.

### 9.1 응답 시간 개선

현재 한 턴은 여러 단계를 거친다.

```text
webm 업로드
  -> ffmpeg 변환
  -> SenseVoice STT
  -> emotion2vec SER
  -> pitch 분석
  -> LLM 감정 재분류
  -> chat/reply LLM
  -> TTS
  -> 라즈베리 파이 색상 push
```

응답 시간 개선은 다음 순서로 진행한다.

1. **계측 먼저 추가**
   - 각 단계별 소요 시간을 로그로 남긴다.
   - 최소 측정 항목: `audio_convert_ms`, `stt_ms`, `ser_ms`, `pitch_ms`, `emotion_llm_ms`,
     `chat_llm_ms`, `tts_ms`, `mood_light_push_ms`, `total_ms`.
   - 개선 전에 병목이 STT/SER인지 OpenAI 호출인지 먼저 확인한다.

2. **실시간 경로와 후처리 경로 분리**
   - `voice/analyze`는 실시간 색상 표시가 핵심이므로 최대한 짧게 유지한다.
   - 편지 생성, 요약, 장기 리포트는 대화 종료 후 처리한다.
   - 라즈베리 push는 현재 계획처럼 API 응답을 막지 않는 background 작업으로 둔다.

3. **LLM 호출 수 줄이기 검토**
   - 현재 계획은 `voice/analyze`에서 감정 재분류 LLM, `chat/reply`에서 대화 LLM이 따로 돈다.
   - 개발 후에는 두 호출을 합칠 수 있는지 검토한다.
   - 예: `chat/reply`가 `reply_text`와 `care_emotion`을 함께 JSON으로 반환하게 만들기.
   - 단, 실시간 무드등 색상이 채팅 응답보다 먼저 필요하면 분리 유지가 낫다.

4. **TTS 지연 완화**
   - TTS는 사용자 체감 지연이 크므로 응답 생성 직후 바로 비동기로 요청한다.
   - 같은 문장 재생 가능성이 있으면 캐시를 검토한다.
   - 시연용 고정 문구가 있다면 사전 생성 음성 파일을 준비하는 fallback도 가능하다.

5. **모델 warm-up**
   - 서버 시작 후 첫 요청은 모델 lazy path 때문에 느릴 수 있다.
   - 기동 직후 짧은 샘플 wav로 STT/SER/pitch warm-up을 수행하는 endpoint 또는 startup task를 검토한다.

### 9.2 느린/없는 와이파이 환경 대책

시연 공간의 와이파이가 느리거나 제공되지 않을 수 있으므로, 외부 인터넷 의존도를 낮추는 대책을 준비한다.

1. **로컬 네트워크 구성**
   - 노트북과 라즈베리 파이를 같은 휴대용 공유기 또는 휴대폰 핫스팟에 연결한다.
   - 서버는 노트북에서 실행하고 라즈베리 파이는 `MOOD_LIGHT_ENDPOINT`로 노트북 서버의 색상 push를 받는다.
   - 시연 전 라즈베리 고정 IP 또는 mDNS 이름을 정한다.

2. **인터넷 불가 fallback**
   - SenseVoice, emotion2vec, pitch는 로컬에서 동작하므로 인터넷 없이도 음성 분석 일부는 가능하다.
   - OpenAI 기반 감정 재분류, chat, TTS, letter 생성은 인터넷이 필요하다.
   - 인터넷이 없으면 다음 fallback을 검토한다.
     - 감정 재분류: emotion2vec 점수 기반 규칙으로 `care_emotion` 임시 결정
     - chat/reply: 사전 준비한 뭉이 응답 템플릿 사용
     - TTS: 사전 생성 wav 파일 사용 또는 TTS 생략
     - letter: 시연 종료 후 생성하거나 샘플 letter 사용

3. **시연 모드 추가 검토**
   - `.env`에 `DEMO_OFFLINE_MODE=true` 같은 플래그를 둘 수 있다.
   - 이 모드에서는 OpenAI 호출을 하지 않고 로컬 규칙/샘플 응답으로 전체 플로우를 끊기지 않게 한다.
   - 실제 서비스 모드와 시연 모드를 코드에서 명확히 분리한다.

4. **사전 준비물**
   - 모델 가중치 캐시 확인: SenseVoice, emotion2vec이 시연 장소에서 다운로드를 시도하지 않도록 미리 받아둔다.
   - OpenAI API가 필요한 경우 휴대폰 테더링 백업 준비.
   - 라즈베리 endpoint 연결 테스트용 mock 또는 health endpoint 준비.
   - 샘플 오디오, 샘플 응답, 샘플 TTS 파일을 `scripts/` 또는 `temp/` 아래 준비하되 git 추적 여부는 별도 결정한다.

### 9.3 후속 문서화

기능 개발이 끝나면 별도 문서로 분리한다.

- `docs/prompts_Engineering/latency-optimization-plan.md`
- `docs/prompts_Engineering/demo-network-fallback-plan.md`

이 두 문서는 실제 측정 로그와 시연 장소 네트워크 조건이 확인된 뒤 작성한다.
