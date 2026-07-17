# 뭉케어(MoongCare) FastAPI 백엔드 서버 설계

날짜: 2026-07-18

## 개요

'뭉이' 캐릭터와 음성으로 대화하며 감정을 분석하고, 대화 종료 시 일기를 자동
생성해주는 FastAPI 백엔드. STT(SenseVoice), SER(emotion2vec), TTS(CosyVoice2),
대화/일기 생성(OpenAI Chat Completions)을 하나의 파이프라인으로 묶는다.

## 기술 스택

- STT: SenseVoice (`iic/SenseVoiceSmall`, funasr)
- SER: emotion2vec (`iic/emotion2vec_plus_large`, funasr)
- TTS: CosyVoice2 (`CosyVoice2-0.5B`, zero-shot 모드)
- LLM: OpenAI Chat Completions (대화 응답 + 일기 생성/요약)
- DB: MySQL (로컬 인스턴스, 발표/데모 환경)
- 환경: Python 3.10, FastAPI, Windows, GPU(GTX 1070Ti 8GB)

## 환경/의존성 결정 사항

- 기존 venv에 funasr/openai/fastapi 등 설치되어 있고 `transformers==5.14.1`.
  CosyVoice 요구사항은 `transformers==4.51.3`, `torch==2.3.1`을 명시하지만
  **버전 충돌을 피하기 위해 단일 venv에서 pin을 완화**한다. torch/torchaudio는
  CosyVoice 요구 버전(cu121)으로 설치하되, transformers는 기존 5.x를 유지한다.
  (문제 발생 시 개별 대응)
- ffmpeg는 시스템에 설치되어 있지 않음 — 서버 기동 시 `shutil.which("ffmpeg")`로
  체크하여 없으면 즉시 기동 실패시킨다(fail-fast).
- CosyVoice2-0.5B는 자체 SFT 화자가 없어 zero-shot 방식만 가능. '뭉이' 전용
  레퍼런스 wav+스크립트가 아직 없으므로, 우선 `CosyVoice/asset/zero_shot_prompt.wav`
  샘플을 플레이스홀더로 등록해 두고 실제 목소리 준비되면 파일만 교체한다.

## 핵심 플로우

```
Client (webm 녹음)
  -> POST /api/v1/voice/analyze (session_id, audio)
     [webm->wav(ffmpeg)] -> [STT ‖ SER 병렬] -> 세션 메모리에 turn 추가
     응답: { transcript, emotions }
  -> POST /api/v1/chat/reply (session_id, transcript, emotions)
     세션 히스토리 로드 -> OpenAI 호출(감정 반영 프롬프트) -> assistant turn 기록
     응답: { reply_text }
  -> POST /api/v1/tts (text=reply_text)
     CosyVoice2 zero-shot 추론 -> wav 바이너리 스트리밍
  (위 3단계 N회 반복)
  -> POST /api/v1/session/end (session_id)
     세션 메모리의 감정 스코어 누적평균 + dominant_emotion 계산 (메모리는 유지)
     응답: { dominant_emotion, average_emotions }
  -> POST /api/v1/diary/generate (session_id)
     세션 메모리에서 히스토리+평균감정 재조회 -> OpenAI로 일기+한줄요약 생성
     -> MySQL 저장 -> 세션 메모리 정리(pop)
     응답: { diary_id, diary_text, summary, dominant_emotion }
```

## 세션 상태 관리

- `session_id`: 클라이언트가 UUID 생성하여 매 요청에 실어 보낸다. 별도
  session/start 엔드포인트 없음.
- 저장 위치: 프로세스 전역 in-memory dict (`services/emotion_session.py`).
  서버 재시작 시 세션 유실되지만 로컬 단일 프로세스 데모 환경이라 문제 없음.
- 구조:
  ```python
  SESSIONS: dict[str, SessionState] = {}

  class SessionState:
      turns: list[TurnRecord]          # {role, transcript, emotions}
      emotion_sums: dict[str, float]   # 감정별 누적합 (user turn만 집계)
      turn_count: int
  ```
- `voice/analyze` 처리 후 사용자 turn 추가 + 감정 누적.
- `chat/reply` 처리 후 assistant turn(응답 텍스트만) 히스토리에 추가. 감정
  누적 대상에서는 제외.
- `session/end`: 누적합/turn_count로 평균 계산, `dominant_emotion = max(average_emotions)`.
  메모리는 삭제하지 않는다 (diary/generate에서 재사용).
- `diary/generate`: 세션 히스토리 전체 + 평균감정으로 프롬프트 구성 후 생성,
  DB 저장, 이후 `SESSIONS.pop(session_id)`로 정리.

## 동시성 / GPU 자원 관리

- GPU가 1개(8GB VRAM)이므로 모델별 `asyncio.Lock` 3개(`stt_lock`, `ser_lock`,
  `tts_lock`)를 `app.state`에 두어 추론 구간을 직렬화, 메모리 경합/OOM 방지.
- 모델 로딩은 FastAPI `lifespan`에서 1회 수행 (싱글톤), 라우터/서비스는
  `request.app.state.xxx_model`로 접근.
- blocking 추론 호출은 `run_in_threadpool`로 감싸 이벤트 루프를 막지 않는다.

## 에러 처리 원칙

- STT 결과가 빈 문자열이어도 200 정상 응답 (침묵 구간도 유효 턴으로 처리).
- OpenAI 호출 실패(타임아웃/레이트리밋) -> 502.
- 존재하지 않는 session_id로 chat/reply, session/end, diary/generate 호출 -> 404.
- 오디오 변환 실패 -> 422.
- 모델 추론 중 예외 -> 500 + 로그. 락은 `try/finally`로 항상 해제.

## API 응답 스펙

`voice/analyze`:
```json
{ "transcript": "오늘 발표가 잘 됐어요", "emotions": {"happy": 0.65, "sad": 0.10, "neutral": 0.20, "angry": 0.05} }
```

`session/end`:
```json
{ "dominant_emotion": "happy", "average_emotions": {"happy": 0.52, "sad": 0.18, "neutral": 0.24, "angry": 0.06} }
```

`chat/reply`: `{ "reply_text": "..." }` (요청: `session_id, transcript, emotions`)

`tts`: 요청 `{ "text": "..." }` -> `audio/wav` 바이너리 스트리밍 응답.

`diary/generate`: 요청 `{ "session_id": "..." }` ->
`{ "diary_id", "diary_text", "summary", "dominant_emotion" }`

## 파일별 역할

- `routers/*.py`: 각 엔드포인트, 요청 검증 후 services 호출.
- `services/stt_service.py`: SenseVoice 추론 + `utils/text_parser.py`로 태그 제거.
- `services/ser_service.py`: emotion2vec 추론, 감정 스코어 dict 반환.
- `services/voice_service.py`: STT/SER를 `asyncio.gather`로 병렬 실행.
- `services/tts_service.py`: CosyVoice2 zero-shot 추론, wav 바이트 반환.
- `services/chat_service.py`: OpenAI 호출, 뭉이 페르소나 시스템 프롬프트 +
  세션 히스토리 + 현재 turn 감정을 컨텍스트로 포함.
- `services/diary_service.py` / `summary_service.py`: OpenAI로 1인칭 일기,
  한 줄 요약 생성.
- `services/emotion_session.py`: 세션 메모리 CRUD, 누적평균 계산.
- `utils/audio_converter.py`: ffmpeg subprocess로 webm(16kHz mono)->wav 변환.
- `utils/text_parser.py`: SenseVoice 태그(`<|ko|><|NEUTRAL|>...`) 정규식 제거.
- `database/connection.py`: SQLAlchemy engine(MySQL, pymysql), `init_db()`.
- `database/diary_repository.py`: `Diary` 모델 + `save_diary`/`get_diary`.

## 테스트 계획

1. `utils/audio_converter.py`: 샘플 webm -> wav 변환 결과 존재/샘플레이트 확인.
2. `utils/text_parser.py`: 태그 제거 unit test.
3. `services/emotion_session.py`: 누적합/평균 계산 로직 unit test (모델 불필요).
4. 라우터 happy-path: 모델 로딩이 무거워 pytest 자동화 대신 서버 기동 후
   curl로 전체 플로우(analyze -> chat -> tts -> session/end -> diary/generate)
   1회 수동 실행하여 응답 스펙 일치 확인.
