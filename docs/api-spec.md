# MoongCare Server API 명세서

Base URL: `http://<host>:8000`
모든 요청/응답 바디는 JSON (음성 업로드 제외: `multipart/form-data`, TTS 응답: `audio/wav`).

---

## 목차

1. [Health](#health)
2. [Voice](#voice)
3. [Chat](#chat)
4. [TTS](#tts)
5. [Session](#session)
6. [Diary](#diary)
7. [Letter](#letter)
8. [공통 타입](#공통-타입)

---

## Health

### `GET /health`

서버 상태 확인.

**Response `200`**
```json
{ "status": "ok" }
```

---

## Voice

### `POST /api/v1/voice/analyze`

음성 파일 업로드 → STT 변환, 감정 인식(SER), care 감정 분류 + AI 응답 생성(단일 LLM 호출), mood-light 색상 push까지 한 번에 처리. 세션 turn(user+assistant)에도 자동 기록됨. `emotions`는 emotion2vec 점수 분포이고, 실제 서비스 판단에 쓰는 감정 라벨은 `care_emotion`이다.

> **2026-08-22 변경**: 기존엔 이 엔드포인트가 감정분류만 하고, 텍스트 응답은 별도 `POST /api/v1/chat/reply` 호출로 받아야 했음(LLM 호출 2회, 왕복 2회). 지금은 감정분류+응답생성을 한 번의 LLM 호출로 합쳐서 `reply_text`를 이 응답에 바로 포함함 — 정상 플로우에서는 `chat/reply`를 더 호출할 필요 없음. **프론트 연동 변경 필요**: 녹음 직후 이 응답의 `reply_text`를 바로 써서 TTS 요청하면 됨.

**Request** `multipart/form-data`

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `session_id` | string (form) | Y | 세션 식별자 |
| `style` | string (form) | N (기본 `"empathetic"`) | 응답 스타일, `"empathetic"` \| `"realistic"` |
| `audio` | file (webm) | Y | 녹음 오디오 (webm, 서버가 wav로 변환) |

**Response `200`** `VoiceAnalyzeResponse`
```json
{
  "transcript": "오늘 좀 힘들었어",
  "emotions": { "happy": 0.05, "sad": 0.62, "neutral": 0.33 },
  "pitch_mean": 142.3,
  "pitch_std": 18.7,
  "care_emotion": "sadness",
  "care_emotion_label": "슬픔",
  "care_confidence": 0.81,
  "care_color": {
    "hex": "#F2B6A0",
    "brightness": 0.38,
    "transition_ms": 2200
  },
  "reply_text": "많이 힘들었겠다... 오늘 하루는 어땠어?"
}
```

- 처리 중 `emotion_classifier_service.classify_and_reply`로 realtime care 감정 분류 + AI 응답 생성을 한 번의 LLM 호출로 처리, `color_care_service`로 색상 매핑.
- 응답 생성 후 세션에 user turn과 assistant turn이 함께 저장됨 (`chat/reply`를 별도로 안 불러도 대화 맥락 유지됨).
- `mood_light_client.push_color`가 백그라운드 태스크로 실시간 색상을 무드등 디바이스에 전송 (`mode: "realtime"`).
- 임시 webm/wav 파일은 처리 후 삭제됨.

---

## Chat

### `POST /api/v1/chat/reply`

> **2026-08-22 변경**: 정상 플로우(녹음→응답)에서는 더 이상 필요 없음 — `voice/analyze`가 `reply_text`를 이미 반환함. 이 엔드포인트는 **같은 turn을 다른 스타일로 재생성하고 싶을 때**(예: "다른 톤으로 다시" 버튼) 수동으로 호출하는 용도로만 남겨둠. 호출 시 세션에 assistant turn이 추가로 쌓이니 유의.

세션의 대화 맥락(turns)과 `care_emotion`을 바탕으로 AI 응답 생성. 생성된 응답은 세션에 assistant turn으로 자동 저장. 대화 LLM은 emotion2vec 최고 점수 라벨을 직접 쓰지 않고, care 분류 결과인 `care_emotion`을 감정 맥락으로 사용한다.

**Request** `ChatReplyRequest`
```json
{
  "session_id": "abc123",
  "transcript": "오늘 좀 힘들었어",
  "emotions": { "sad": 0.62, "neutral": 0.33 },
  "care_emotion": "sadness",
  "style": "empathetic"
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `session_id` | string | Y | 세션 식별자 |
| `transcript` | string | Y | 사용자 발화 텍스트 |
| `emotions` | dict[string, float] | Y | emotion2vec 감정별 확률/점수. 대화 대표 감정 선택에는 직접 사용하지 않음 |
| `care_emotion` | string \| null | N | 대화 LLM에 전달할 케어 감정. 미지정 시 세션의 최신 user turn에 저장된 `care_emotion` 사용 |
| `style` | `"empathetic"` \| `"realistic"` | N (기본 `"empathetic"`) | 응답 스타일 |

**Response `200`** `ChatReplyResponse`
```json
{ "reply_text": "많이 힘들었겠다... 오늘 하루는 어땠어?" }
```

**Errors**
- `404` — 세션 없음 (`session not found`)

---

## TTS

### `POST /api/v1/tts`

텍스트를 음성(wav)으로 합성.

**Request** `TTSRequest`
```json
{
  "text": "안녕하세요, 오늘 하루는 어땠나요?",
  "session_id": "abc123",
  "voice": "nova"
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `text` | string | Y | 합성할 텍스트 |
| `session_id` | string \| null | N | 세션별 instructions 반영용 |
| `voice` | string \| null | N | 미지정 시 기본 보이스(`TTS_DEFAULT_VOICE`) 사용 |

**Response `200`** — `audio/wav` 바이너리

**Errors**
- `400` — 허용되지 않은 voice (`unsupported voice: {voice}`). 허용 목록: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

---

## Session

### `POST /api/v1/session/end`

세션 종료. emotion2vec 평균 점수 계산, `care_emotion` 기준 대표 감정 도출, 수면 컬러 프로필 산출, mood-light에 sleep 색상 push.

**Request** `SessionEndRequest`
```json
{ "session_id": "abc123" }
```

**Response `200`** `SessionEndResponse`
```json
{
  "dominant_emotion": "sadness",
  "average_emotions": { "happy": 0.1, "sad": 0.55, "neutral": 0.35 },
  "sleep_color": {
    "hex": "#D18461",
    "brightness": 0.14,
    "transition_ms": 7000
  }
}
```

- `mood_light_client.push_color`가 백그라운드 태스크로 sleep 색상 전송 (`mode: "sleep"`, `emotion: "settled"`).
- 세션의 sleep 결과는 이후 diary 생성 시 재사용됨.

**Errors**
- `404` — 세션 없음 (`session not found`)

---

## Diary

### `POST /api/v1/diary/generate`

세션 대화 기록으로 일기(diary) + 편지(letter) 생성 및 DB 저장. 생성 후 세션은 초기화(clear)됨.

**Request** `DiaryGenerateRequest`
```json
{ "session_id": "abc123" }
```

**Response `200`** `DiaryGenerateResponse`
```json
{
  "diary_id": 1,
  "letter_id": 1,
  "diary_text": "오늘은...",
  "letter_text": "사랑하는 너에게...",
  "summary": "힘든 하루를 보냈지만...",
  "dominant_emotion": "sadness"
}
```

- sleep_color가 세션에 이미 있으면 재사용, 없으면 새로 산출.
- 생성된 diary/letter는 DB에 저장되고 `session_id`로 연결됨.
- `dominant_emotion`은 emotion2vec 평균 최고값이 아니라 세션의 `care_emotion`들을 집계한 대표 케어 감정.

**Errors**
- `404` — 세션 없음 (`session not found`)
- `404` — 세션에 turn 없음 (`session has no turns`)

---

### `GET /api/v1/diary`

일기 목록 조회.

**Query Parameters**

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `session_id` | string | N | 지정 시 해당 세션 일기만 필터링 |

**Response `200`** `DiaryListItem[]`
```json
[
  {
    "id": 1,
    "session_id": "abc123",
    "summary": "힘든 하루를 보냈지만...",
    "dominant_emotion": "sadness",
    "created_at": "2026-08-13T21:00:00"
  }
]
```

---

### `GET /api/v1/diary/{diary_id}`

일기 상세 조회.

**Response `200`** `DiaryDetail`
```json
{
  "id": 1,
  "session_id": "abc123",
  "diary_text": "오늘은...",
  "summary": "힘든 하루를 보냈지만...",
  "dominant_emotion": "sadness",
  "average_emotions": { "happy": 0.1, "sad": 0.55, "neutral": 0.35 },
  "created_at": "2026-08-13T21:00:00"
}
```

**Errors**
- `404` — 일기 없음 (`diary not found`)

---

## Letter

### `GET /api/v1/letter`

편지 목록 조회.

**Query Parameters**

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `session_id` | string | N | 지정 시 해당 세션 편지만 필터링 |

**Response `200`** `LetterListItem[]`
```json
[
  {
    "id": 1,
    "session_id": "abc123",
    "diary_id": 1,
    "summary": "힘든 하루를 보냈지만...",
    "dominant_emotion": "sadness",
    "created_at": "2026-08-13T21:00:00"
  }
]
```

---

### `GET /api/v1/letter/{letter_id}`

편지 상세 조회.

**Response `200`** `LetterDetail`
```json
{
  "id": 1,
  "session_id": "abc123",
  "diary_id": 1,
  "letter_text": "사랑하는 너에게...",
  "summary": "힘든 하루를 보냈지만...",
  "dominant_emotion": "sadness",
  "sleep_color": {
    "hex": "#D18461",
    "brightness": 0.14,
    "transition_ms": 7000
  },
  "created_at": "2026-08-13T21:00:00"
}
```

**Errors**
- `404` — 편지 없음 (`letter not found`)

---

## 공통 타입

### `CareColor`

무드등에 반영되는 색상 정보. `voice/analyze`(realtime), `session/end`·`letter`(sleep)에서 공통 사용.

| 필드 | 타입 | 설명 |
|---|---|---|
| `hex` | string | 색상 hex 코드 (`#RRGGBB`) |
| `brightness` | float | 밝기 (0.0 ~ 1.0) |
| `transition_ms` | int | 전환 시간(ms) |

### 감정 관련 공통 개념

- `emotions`: emotion2vec/SER 모델이 산출한 raw 감정 확률 분포 (예: `happy`, `sad`, `angry`, `neutral` 등). 역할은 감정을 0~1 점수로 수치화하는 것.
- `care_emotion`: `emotions` 점수, 발화 텍스트, pitch, 최근 맥락을 종합해 서비스 로직이 고른 케어 감정 라벨. 대화 LLM, 실시간 색상, 수면 색상, 편지 생성에 사용.
- `dominant_emotion`: 세션의 `care_emotion`들을 집계해 도출한 최종 대표 케어 감정. emotion2vec 평균 점수의 최고 라벨이 아님.
- 세션(`session_id`) 단위로 turn들이 메모리에 누적되며, `session/end` 또는 `diary/generate` 호출 시 소비/초기화됨.
