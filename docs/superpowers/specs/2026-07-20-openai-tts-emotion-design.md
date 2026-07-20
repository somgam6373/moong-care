# TTS를 OpenAI gpt-4o-mini-tts + 감정 instruction으로 교체하는 설계

날짜: 2026-07-20

## 개요

현재 TTS는 로컬 CosyVoice3(zero-shot voice clone, GPU 상주 모델)를 쓴다.
이를 OpenAI `gpt-4o-mini-tts` API 호출로 교체한다. 대신 커스텀 목소리
clone(moong 캐릭터 전용 목소리)은 포기하고, OpenAI가 제공하는 preset
목소리 중 클라이언트가 고른 것을 쓴다. 그 대신 `gpt-4o-mini-tts`의
`instructions` 파라미터로 사용자의 최근 감정에 공감하는 톤을 자연어로
지시한다.

## 범위

- **포함**: `/api/v1/tts` 엔드포인트를 OpenAI API 호출로 교체, 세션의
  최근 user 감정을 읽어 톤 instruction으로 매핑, voice를 클라이언트가
  선택.
- **제외**: CosyVoice3 관련 파일(`CosyVoice/`, `pretrained_models/`)과
  `requirements.txt`의 관련 의존성 정리는 이번 작업 범위 밖 — STT/SER이
  같은 의존성을 쓰는지 불확실하므로 그대로 둔다. 필요하면 후속 작업으로
  별도 진행.

## 아키텍처 / 데이터 흐름

```
voice/analyze (STT+SER)
  → emotion_session.add_user_turn(session_id, transcript, emotions)
chat/reply
  → reply_text 생성 (세션 emotion과 무관, 기존 로직 그대로)
클라이언트: POST /api/v1/tts { text: reply_text, session_id, voice }
  → emotion_session.get_last_user_emotion(session_id)로 최근 user 감정 조회
  → dominant emotion 계산 → EMOTION_INSTRUCTIONS 매핑 → instruction 문장
  → OpenAI gpt-4o-mini-tts 호출 (voice, instructions, input=text)
  → wav bytes 응답
```

## 컴포넌트별 변경

### `models/tts.py`
`TTSRequest`에 필드 추가:
- `session_id: str | None = None`
- `voice: str | None = None`

### `config.py`
- `TTS_MODEL_DIR` 삭제.
- `TTS_DEFAULT_VOICE: str = "nova"` 추가.
- `TTS_ALLOWED_VOICES: set[str] = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}` 추가.

### `services/emotion_session.py`
`get_last_user_emotion(session_id: str) -> dict[str, float] | None` 추가.
`SESSIONS`에 session_id 없거나, 있어도 role="user"인 turn이 하나도 없으면
`None` 반환. 내부 상태(`SESSIONS`, `TurnRecord`)를 tts_service가 직접
들여다보지 않도록 캡슐화하는 목적.

### `services/tts_service.py` (전면 재작성)
- `EMOTION_INSTRUCTIONS: dict[str, str]` — `emotion_session.EMOTION_CLASSES`
  (angry/disgusted/fearful/happy/neutral/other/sad/surprised/unknown) 전체를
  key로 갖는 영어 instruction 문장 매핑. 예:
  - `sad`: "Speak in a warm, gentle, comforting tone, as if empathizing with someone who's feeling sad."
  - `happy`: "Speak in a bright, cheerful, warm tone."
  - `angry`: "Speak in a calm, soothing, de-escalating tone."
  - `fearful`: "Speak in a reassuring, steady, gentle tone."
  - `surprised`: "Speak in an animated, curious, engaged tone."
  - `disgusted`: "Speak in a calm, neutral, non-judgmental tone."
  - `neutral`: "Speak in a natural, warm, conversational tone."
  - `other`: "Speak in a natural, warm, conversational tone."
  - `unknown`: "Speak in a natural, warm, conversational tone."
- `resolve_instructions(session_id: str | None) -> str`:
  - `session_id`가 None이거나 `get_last_user_emotion`이 None 반환 →
    `EMOTION_INSTRUCTIONS["neutral"]` 반환 (에러 없음).
  - 있으면 `max(emotions, key=emotions.get)`으로 dominant emotion 계산 →
    매핑값 반환.
- `synthesize(text: str, voice: str, instructions: str) -> bytes`:
  - `openai_client.get_client().audio.speech.create(model="gpt-4o-mini-tts", voice=voice, input=text, instructions=instructions)`
  - 반환값의 `.read()`로 bytes 획득.
- 삭제: `register_moong_speaker`, `SPK_ID`, `PLACEHOLDER_PROMPT_WAV`,
  `PLACEHOLDER_PROMPT_TEXT`.

### `routers/tts.py`
- `request.app.state.tts_model` / `tts_lock` 의존 제거.
- `payload.voice`가 있으면 `config.settings.TTS_ALLOWED_VOICES`에 있는지
  검증 — 없으면 `HTTPException(400)`. 없으면(생략) `TTS_DEFAULT_VOICE` 사용.
- `tts_service.resolve_instructions(payload.session_id)` 호출.
- `run_in_threadpool(tts_service.synthesize, payload.text, voice, instructions)`
  호출 (OpenAI SDK가 동기 블로킹이라 threadpool은 유지, GPU 아니므로 lock은
  제거).

### `main.py`
- `from cosyvoice.cli.cosyvoice import AutoModel as CosyVoiceAutoModel` 삭제.
- `sys.path.append(os.path.join(BASE_DIR, "CosyVoice"))`,
  `sys.path.append(os.path.join(BASE_DIR, "CosyVoice", "third_party", "Matcha-TTS"))` 삭제.
- `app.state.tts_model = CosyVoiceAutoModel(...)`,
  `register_moong_speaker(app.state.tts_model)` 삭제.
- `app.state.tts_lock = asyncio.Lock()` 삭제.
- `from services.tts_service import register_moong_speaker` import 삭제.

## API 요청/응답 예시

```
POST /api/v1/tts
{
  "text": "오늘 힘든 하루였겠다, 나는 항상 네 편이야.",
  "session_id": "abc123",
  "voice": "nova"
}
```
→ `audio/wav` bytes (기존과 동일한 응답 형식 유지).

## 에러 처리

- session 없음 / 잘못된 session_id / user turn 아직 없음 →
  에러 내지 않고 neutral instruction으로 fallback (음성 출력은 항상 보장).
- `voice`가 `TTS_ALLOWED_VOICES` 밖 → 400.
- OpenAI API 호출 자체가 실패(네트워크/인증 등) → 별도 처리 없이 예외
  propagate → FastAPI 기본 500 (chat_service의 OpenAI 호출과 동일한 원칙,
  재시도/래핑 추가하지 않음).

## 테스트 계획

- `tests/test_tts_service.py`: OpenAI client를 monkeypatch/mock.
  - `resolve_instructions`가 각 감정 클래스별로 올바른 문구를 반환하는지.
  - session_id=None, 존재하지 않는 session_id, user turn 없는 session
    각각 neutral fallback 확인.
  - `synthesize`가 mock client에 올바른 model/voice/input/instructions로
    호출하는지, 반환 bytes를 그대로 넘기는지.
- `tests/test_tts_router.py`: `tts_service.resolve_instructions`/`synthesize`
  mock.
  - 정상 요청 시 200 + `audio/wav`.
  - 잘못된 `voice` 값 → 400.
  - `voice` 생략 시 기본값(`nova`) 사용 확인.
- `tests/test_emotion_session.py`가 있다면 `get_last_user_emotion` 케이스
  추가(정상/session 없음/user turn 없음).
- `tests/test_models.py`: `TTSRequest`에 `session_id`/`voice` optional
  필드 round-trip 확인.
