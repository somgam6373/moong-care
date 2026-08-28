# front-ui를 "보조 디스플레이"로 재설계 — Pi 연동

날짜: 2026-08-29
관련 문서: [2026-08-29-front-ui-design.md](2026-08-29-front-ui-design.md) (기존 설계, 아래 내용으로 4~11절 대체)

## 1. 배경 / 문제

현재 front-ui는 자체적으로 마이크 녹음 → `voice/analyze` → `tts` 재생까지 수행하는 **독립된 대화 클라이언트**다.
그런데 실제 대화는 라즈베리파이(`pi/main.py`)가 이미 전담하고 있다 — 파이가 녹음 → `POST /api/v1/care/turn`
(STT+감정분류+답변+TTS 한 번에 처리) → 스피커 재생 + LED 색 표시까지 다 함. front-ui와 Pi는 지금
서로 완전히 분리된 별개의 대화 세션을 만든다.

원하는 구조: **front-ui는 대화를 직접 하지 않는다.** Pi가 만든 턴 결과(감정 텍스트 + 케어 색상)를
화면에 띄워주고, 대화 종료 시 일기(편지)를 보여주는 **보조 디스플레이**로 축소한다. 단, 대화
시작/종료는 Pi의 물리 버튼뿐 아니라 front-ui에서도 트리거할 수 있어야 한다.

## 2. 핵심 결정 사항 (사용자 확정)

- **전달 방식**: WebSocket/SSE 아님. front-ui가 `GET /api/v1/session/live`를 1.5초 간격으로 폴링.
- **세션 모델**: 기기 1대 전제, "현재 세션" 하나만 서버가 전역으로 추적. front/Pi 둘 다 이 하나의
  세션을 보고 조작한다 (세션 ID를 이중으로 관리하지 않음).
- **버튼 역할**: front-ui의 시작/종료 버튼은 화면 전환용 로컬 UI가 아니라 실제로 백엔드를 호출한다.
  Pi 물리 버튼과 동등한 자격.
- **동시 사용 레이스는 무시한다**: Pi와 front가 동시에 시작/종료를 누르는 경쟁 상태는 설계에서
  다루지 않는다 (실사용 시나리오상 발생 가능성 낮음, 발생해도 "마지막에 이긴 쪽" 그대로 둔다).

## 3. 백엔드 변경

### 3.1 새 모듈: `services/session_state.py`

`emotion_session.py`의 인메모리 딕셔너리(`SESSIONS`)와 같은 패턴 — DB 아님, 프로세스 전역 변수 하나.

```python
_current_session_id: str | None = None

def start_session() -> str:
    global _current_session_id
    _current_session_id = uuid.uuid4().hex
    return _current_session_id

def get_current() -> str | None:
    return _current_session_id

def adopt(session_id: str) -> None:
    """Pi가 /care/turn을 호출한 session_id를 현재 세션으로 자동 채택한다."""
    global _current_session_id
    _current_session_id = session_id

def clear() -> None:
    global _current_session_id
    _current_session_id = None
```

`adopt()`가 핵심이다 — **Pi 쪽 코드는 한 줄도 안 바꾼다.** Pi가 어떤 session_id로 `/care/turn`을
치든, 그 요청이 들어오는 순간 그 id가 "현재 세션"이 된다. front가 `/session/start`로 새 id를 만들어도,
Pi의 다음 턴이 들어오면 자동으로 Pi의 session_id로 다시 맞춰진다 (2절의 "레이스 무시" 결정과 일치).

### 3.2 `routers/care.py` 수정 — 1줄 추가

`turn()` 핸들러에서 `emotion_session.add_assistant_turn(...)` 직후:
```python
session_state.adopt(session_id)
```

### 3.3 `routers/session.py` 수정 — 엔드포인트 2개 추가

- `POST /api/v1/session/start` (신규, body 없음) → `session_state.start_session()` 호출, `{"session_id": ...}` 리턴.
- `GET /api/v1/session/live` (신규) → 아래 3.4 스냅샷 리턴.
- 기존 `POST /api/v1/session/end`는 **그대로 유지** (요청 바디 `session_id` 그대로 받음 — front는
  `/live` 응답에서 현재 session_id를 알아내 그걸 넘긴다). 추가로 `session_state.clear()` 한 줄만
  끝에 넣어서, 종료 후에는 "현재 세션 없음" 상태가 되게 한다 (Pi가 다음 턴을 보내면 다시 adopt됨).

### 3.4 `services/emotion_session.py`에 헬퍼 하나 추가

```python
def get_latest_snapshot(session_id: str) -> dict | None:
    """가장 최근 턴의 감정/색/답변 스냅샷. 폴링용 — turn_count를 버전 삼아 변경 감지."""
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

`care_emotion_label`(한글 라벨)은 안 보낸다 — front가 이미 `constants/careEmotions.ts`에
코드→라벨 매핑을 갖고 있으므로 중복 소스 금지 (기존 설계 문서 8절 원칙 유지).

### 3.5 `GET /api/v1/session/live` 응답 모델

`models/emotion.py`에 추가 (기존 `SessionEndRequest/Response`가 있는 파일, 관례 유지):

```python
class SessionStartResponse(BaseModel):
    session_id: str

class SessionLiveResponse(BaseModel):
    session_id: str | None
    has_session: bool
    ended: bool
    turn_count: int
    transcript: str | None = None
    care_emotion: str | None = None
    care_confidence: float | None = None
    care_color: CareColor | None = None
    reply_text: str | None = None
```

핸들러 로직:
```python
session_id = session_state.get_current()
if session_id is None:
    return SessionLiveResponse(session_id=None, has_session=False, ended=False, turn_count=0)

_, sleep_color = emotion_session.get_sleep_result(session_id)
ended = sleep_color is not None   # session/end가 호출되면 sleep_color가 채워짐 — 별도 플래그 불필요
snapshot = emotion_session.get_latest_snapshot(session_id) or {}
return SessionLiveResponse(session_id=session_id, has_session=True, ended=ended, turn_count=snapshot.get("turn_count", 0), **snapshot 나머지 필드)
```

`ended` 판정에 기존 `sleep_color` 필드를 재사용한다 — 새 상태 플래그를 따로 안 만듦 (YAGNI).

## 4. front-ui 변경

### 4.1 제거

- `hooks/useAudioRecorder.ts`, `hooks/useMicWaveform.ts` — 더 이상 녹음 안 함.
- `components/PitchWaveform.tsx` — 녹음 파형 UI, 필요 없음.
- `api/client.ts`의 `analyzeVoice`, `synthesizeSpeech` — 대신 `startSession`, `fetchLive` 추가.
- `MoongFace`의 오디오 진폭 기반 입모양 애니메이션 로직 — front가 TTS 오디오를 더 이상 안 받으므로
  재생할 오디오가 없음. 눈 깜빡임만 유지, 입은 항상 닫힌 정적 상태로 단순화.

### 4.2 유지 (거의 그대로)

- `EmotionAtmosphere`, `EmotionColorBar`, `SpeechBubble`, `LetterCard`, `constants/careEmotions.ts`,
  `i18n/`, `useTypewriter` — 전부 그대로 재사용.
- `EndingScreen.tsx`의 `endSession → generateDiary` 순서 호출 로직 — **변경 없음**, 그대로 유지.

### 4.3 폴링 — 앱 전역에서 한 곳 (`ConversationProvider` 또는 새 훅 `useLivePolling`)

1.5초 간격 `GET /session/live` 폴링해서 상태를 디스패치. 화면(`screen`)은 폴링 결과로 대부분 자동
전환된다:

| 폴링 결과 | 화면 |
|---|---|
| `has_session: false` | Intro (대기, "시작" 버튼) |
| `has_session: true, ended: false` | Conversation (감정 텍스트 + care_color 배경 표시) |
| `has_session: true, ended: true` | Ending (diary/generate 호출 → 편지 표시) |

### 4.4 버튼 동작

- **IntroScreen "대화 시작"**: `crypto.randomUUID()` 로컬 생성 제거 → `POST /session/start` 호출,
  응답의 `session_id`로 `START_CONVERSATION` 디스패치.
- **ConversationScreen "대화 종료"**: `END_REQUESTED` 디스패치로 Ending 화면 전환 — **기존과 동일**,
  실제 `session/end` 호출은 그대로 `EndingScreen`의 기존 useEffect가 담당한다 (변경 없음).
  `routers/session.py`의 `end()`는 재호출해도 안전하다 (같은 세션 턴들로 `sleep_color`를 다시
  계산해 덮어쓸 뿐, 에러 조건은 "턴이 하나도 없을 때"뿐이고 이미 최소 1턴 있는 상태에서만 진입하므로
  해당 없음) — 그래서 Pi가 물리 버튼으로 이미 끝낸 세션이든, front 버튼으로 끝낸 세션이든
  `EndingScreen` 진입 시 호출이 중복돼도 문제없다.
- Pi가 물리 버튼으로 종료한 경우: front는 버튼을 누른 적 없어도 폴링으로 `ended:true` 감지 →
  자동으로 `END_REQUESTED` 디스패치 (4.3 표 참고), 이후 흐름은 위와 동일.

### 4.5 `ConversationContext` 변경

- `sessionId`는 이제 폴링 결과가 단일 소스. `START_CONVERSATION`은 폴링이 처음 세션을 감지했을 때도
  트리거될 수 있어야 함 (front 버튼 없이 Pi가 먼저 시작한 경우 대응).
- `TURN_SUCCESS`류 액션은 폴링 스냅샷 반영으로 대체 (녹음 관련 상태 `recordingStatus` 제거).

## 5. 에러 처리

- 폴링 실패(네트워크 끊김) — 조용히 다음 tick 재시도, 3회 연속 실패 시에만 배너 표시 (매번 토스트
  띄우면 폴링 특성상 스팸이 됨).
- `session/start`, `session/end` 실패 — 기존과 동일하게 에러 배너 + 재시도 버튼.

## 6. 테스트

- `emotion_session.get_latest_snapshot` 단위 테스트 (턴 0개/여러 개/assistant만 있는 엣지 케이스).
- `session_state` 모듈 단위 테스트 (`start`→`get_current`, `adopt`가 덮어쓰는지, `clear`).
- `routers/session.py`의 `/start`, `/live` 계약 테스트 (기존 `tests/test_session_router.py` 확장).
- front: `careEmotions`/reducer 테스트는 기존 유지, 폴링 훅은 fetch mock으로 상태 전이 테스트.

## 7. 범위 밖

- Pi 코드 변경 없음 (3.2의 `adopt()` 자동 채택 덕분에 불필요).
- 동시성/레이스 컨디션 처리 (2절 결정).
- 과거 세션 이력 화면, 다중 기기 지원 — 여전히 범위 밖 (원 설계 문서 13절과 동일).
