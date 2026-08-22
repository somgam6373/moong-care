# moong-care 라즈베리파이 연동 계획서

작성 시점 기준 브랜치: `main` (`eae1d79`)
이 문서는 **무엇을 만들지에 대한 계획**이며, 아직 어떤 코드도 작성/수정하지 않았습니다.

---

## 0. 한 줄 요약

라즈베리파이가 버튼 → 녹음 → 서버 1회 호출 → 감정색 LED + 답변 재생 → 대기를 반복한다.
서버에는 기존 파이프라인을 순서대로 묶어주는 **엔드포인트 1개**만 추가한다.
친구분이 만든 GPT 감정 분류기와 색상표는 **한 줄도 고치지 않고 그대로 호출**한다.

---

## 1. 지금 서버에 이미 있는 것 (main 브랜치)

이 부분은 **새로 만들 필요가 전혀 없습니다.** 확인 결과 아래는 전부 구현되어 있습니다.

### 1.1 감정 분류 (친구분 작성)

`services/emotion_classifier_service.py`

```
classify_realtime_emotion(
    transcript,            # STT 결과 문자열
    voice_emotion_scores,  # emotion2vec 9개 확률 dict
    pitch_mean,
    pitch_std,
    recent_context,        # 최근 대화 4턴
) -> CareEmotionResult
```

`CareEmotionResult` 필드: `care_emotion`, `care_emotion_label`, `confidence`, `reason`, `fallback`

동작 방식:

- 위 5개를 JSON으로 묶어 GPT에 넘기고, 14개 중 하나를 고르게 함
- `temperature=0`, `response_format={"type":"json_object"}` 로 출력 고정
- 허용 목록 밖 감정이 오거나 JSON 파싱 실패 시 `calm` 으로 폴백
- 전사가 2글자 미만이면 GPT 호출 없이 바로 `calm` 폴백
- 후처리 보정 `_adjust_result()` 가 추가로 돌아감
  - `"끝났"`, `"마쳤"` 등 부담 종료 문맥 + 명시적 슬픔 표현 없음 + `sad` 원점수 0.8 이상
    → `sadness` 대신 `fatigue`(피곤 신호 있으면) 또는 `relief`
  - 같은 문맥에서 `happy` 원점수 0.8 이상 → `joy` 로 승격

### 1.2 색상표 (친구분 작성)

`services/color_care_service.py`

- `CARE_EMOTION_LABELS` — 14개 한글 라벨
- `REALTIME_COLORS` — 14개 `CareColor(hex, brightness, transition_ms)`
- `SLEEP_COLORS` — 수면용 4개 (이번 작업에서는 안 씀)
- `get_realtime_color(care_emotion) -> CareColor`
- `get_care_emotion_label(care_emotion) -> str`

`models/care.py` 에 `CareColor`, `MoodLightPayload` 정의됨.

### 1.3 이미 감정색을 반환하는 엔드포인트

`POST /api/v1/voice/analyze` 응답 (`models/voice.py: VoiceAnalyzeResponse`)

```json
{
  "transcript": "오늘 좀 힘들었어",
  "emotions": { "happy": 0.05, "sad": 0.62, "neutral": 0.33 },
  "pitch_mean": 142.3,
  "pitch_std": 18.7,
  "care_emotion": "sadness",
  "care_emotion_label": "슬픔",
  "care_confidence": 0.81,
  "care_color": { "hex": "#F2B6A0", "brightness": 0.38, "transition_ms": 2200 }
}
```

기획서에 있던 그 JSON이 이미 그대로 나옵니다.

### 1.4 나머지 기존 기능

| 파일 | 함수 | 역할 |
|---|---|---|
| `services/voice_service.py` | `analyze_voice(app_state, wav_path)` | STT·SER·피치를 asyncio.gather 로 동시 실행 |
| `services/chat_service.py` | `get_reply(history, transcript, emotions, style)` | 뭉이 답변 생성. style은 `empathetic`/`realistic` |
| `services/tts_service.py` | `resolve_instructions(session_id)`, `synthesize(text, voice, instructions)` | 직전 감정에 맞춘 말투로 음성 합성, wav bytes 반환 |
| `services/emotion_session.py` | `add_user_turn(...)`, `add_assistant_turn(...)`, `get_recent_context(...)`, `get_care_timeline(...)` | 세션별 대화·감정 누적 |
| `utils/audio_converter.py` | `webm_to_wav(in, out)` | ffmpeg로 16kHz mono wav 변환 |

### 1.5 안 쓸 것: mood_light_client

`services/mood_light_client.py` 의 `push_color()` 는 **서버가 파이로 POST를 쏘는** 구조입니다.
`config.MOOD_LIGHT_ENDPOINT` 에 파이 주소를 넣으면 동작합니다.

이번 설계에서는 **쓰지 않습니다.** 파이가 직접 서버를 호출하므로 응답에 이미 색이 들어있고,
push까지 켜면 같은 색이 두 번 적용됩니다.

`MOOD_LIGHT_ENDPOINT` 를 빈 문자열로 두면 `push_color()` 는 아무 일도 안 하고 즉시 `False` 를
반환하도록 이미 짜여 있습니다. **기본값이 빈 문자열이므로 아무것도 안 해도 됩니다.**

나중에 웹/앱에서 녹음하고 파이는 조명만 담당하는 시나리오가 생기면 그때 켜면 됩니다.

---

## 2. 최종 파이프라인

### 2.1 한 턴의 전체 흐름

```
[사용자]                [라즈베리파이]                    [서버]
   │
   │ 버튼 1번째 누름
   ├──────────────────▶ 상태: READY → RECORDING
   │                    LED: 무지개 회전 → VU 미터
   │                    마이크 스트림 시작 (16kHz mono)
   │
   │ "오늘 좀 힘들었어"
   ├──────────────────▶ 음량을 실시간으로 LED에 반영
   │
   │ 버튼 2번째 누름
   ├──────────────────▶ 상태: RECORDING → PROCESSING
   │                    LED: 무지개 혜성 + 반짝임
   │                    /tmp/moong_input.wav 저장
   │
   │                    POST /api/v1/care/turn ─────────▶ ① wav 수신
   │                    (multipart: audio, session_id)    ② 16k mono면 변환 생략
   │                                                      ③ analyze_voice()
   │                                                         STT + SER + pitch
   │                                                      ④ classify_realtime_emotion()
   │                                                         GPT가 14개 중 선택
   │                                                      ⑤ get_realtime_color()
   │                                                      ⑥ add_user_turn() 세션 기록
   │                                                      ⑦ get_reply() 뭉이 답변
   │                                                      ⑧ add_assistant_turn()
   │                                                      ⑨ synthesize() TTS
   │                    ◀──────────────────────────────── 헤더: 감정/색/전사/답변
   │                                                      본문: 답변 wav 바이너리
   │
   │                    상태: PROCESSING → SPEAKING
   │                    LED: care_color 단색 호흡 (#F2B6A0)
   │ ◀────────────────  aplay 로 답변 재생
   │  답변 듣기
   │
   │                    재생 끝 → 상태: SPEAKING → READY
   │                    LED: 다시 무지개 회전
   │
   │ 다시 버튼 누르면 반복
```

### 2.2 타이밍 예상

| 구간 | 예상 시간 |
|---|---|
| wav 업로드 (5초 녹음 = 약 160KB, 같은 Wi-Fi) | 0.1초 미만 |
| STT + SER + pitch (GPU, 동시 실행) | 1 ~ 2초 |
| GPT 감정 분류 | 0.5 ~ 1.5초 |
| GPT 답변 생성 | 1 ~ 2초 |
| TTS | 1 ~ 3초 |
| **합계 (PROCESSING 상태 지속 시간)** | **약 4 ~ 8초** |

이 4~8초 동안 LED가 계속 반짝여야 하는 이유입니다. 정지 화면이면 고장으로 보입니다.

### 2.3 왜 3번 호출을 1번으로 합치는가

속도 때문이 아닙니다. 같은 공유기 안이라 왕복 오버헤드는 수 ms 수준이고, 위 표처럼 시간은
전부 모델이 먹습니다.

합치는 이유는 세 가지입니다.

1. **실패 지점이 3개 → 1개.** 분리 호출이면 analyze는 성공했는데 tts에서 타임아웃 나는 상황이
   생기고, 그러면 파이는 답변 텍스트는 있는데 소리를 못 내는 어중간한 상태가 됩니다.
   세션에는 이미 그 턴이 기록된 뒤라 되돌리기도 애매합니다.
2. **파이 상태머신이 단순해짐.** 성공 아니면 실패, 둘 중 하나입니다.
3. **파이가 순수 입출력 장치가 됨.** 판단은 전부 서버가 합니다.

기존 3개 엔드포인트는 **지우지 않습니다.** 웹에서 "전사 텍스트 먼저 띄우고 답변은 나중에"
같은 걸 하려면 단계별 호출이 필요하기 때문입니다.

---

## 3. 서버에 추가할 파일

### 3.1 새 파일 1개

#### `routers/care.py` (신규, 약 90줄)

```
POST /api/v1/care/turn
```

**요청** (multipart/form-data)

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `audio` | 파일 | O | 16kHz mono wav 권장. 다른 포맷도 ffmpeg로 변환됨 |
| `session_id` | 문자열 | O | 파이는 부팅 시 생성한 값을 계속 재사용 |
| `style` | 문자열 | X | `empathetic`(기본) / `realistic` |
| `voice` | 문자열 | X | 기본 `nova` |

**처리 순서**

1. 업로드 파일을 `temp/{uuid}` 로 저장
2. 16kHz mono wav인지 확인 → 맞으면 변환 생략, 아니면 `webm_to_wav()` 호출
3. `voice_service.analyze_voice()` → transcript, emotions, pitch_mean, pitch_std
4. `emotion_session.get_recent_context(session_id)` → 최근 4턴
5. `emotion_classifier_service.classify_realtime_emotion(...)` → CareEmotionResult
   - GPT 호출이라 블로킹이므로 `run_in_threadpool` 로 감쌈 (기존 voice.py와 동일)
6. `color_care_service.get_realtime_color(care_emotion)` → CareColor
7. `emotion_session.add_user_turn(...)` — care 필드까지 전부 넘김
8. `chat_service.get_reply(session.turns, transcript, emotions, style)` → reply_text
9. `emotion_session.add_assistant_turn(session_id, reply_text)`
10. `tts_service.resolve_instructions()` + `synthesize()` → wav bytes
11. temp 파일 정리 (finally)
12. `Response(content=wav_bytes, media_type="audio/wav", headers=...)` 반환

**응답 헤더**

| 헤더 | 예시 | 비고 |
|---|---|---|
| `X-Care-Emotion` | `sadness` | 영문 14개 중 하나 |
| `X-Care-Label` | `%EC%8A%AC%ED%94%94` | 한글이라 percent-encoding 필수 |
| `X-Care-Confidence` | `0.81` | |
| `X-Care-Hex` | `#F2B6A0` | |
| `X-Care-Brightness` | `0.38` | |
| `X-Care-Transition-Ms` | `2200` | |
| `X-Care-Fallback` | `0` 또는 `1` | 1이면 GPT 실패해서 calm으로 떨어진 것 |
| `X-Transcript` | percent-encoded | 파이 로그용 |
| `X-Reply-Text` | percent-encoded | 파이 로그용 |
| `X-Timing` | `analyze=1.82,care=0.91,reply=1.34,tts=2.20,total=6.27` | 병목 파악용 |

**응답 본문**: 답변 음성 wav 바이너리 (`audio/wav`)

**왜 헤더에 넣는가** — 소리(바이너리)와 감정값(구조화 데이터)을 한 응답에 담아야 하는데,
세 가지 방법 중 헤더가 가장 단순합니다.

| 방법 | 장점 | 단점 |
|---|---|---|
| **헤더 + wav 본문** | 파이가 `r.headers[...]`, `r.content` 두 줄로 끝. 스트리밍 저장 가능 | 한글 percent-encoding 필요 |
| JSON + base64 audio | 다루기 쉬움 | 용량 33% 증가, 메모리에 전부 올려야 함 |
| multipart/mixed | 표준적 | 파이썬 클라이언트에서 파싱이 번거로움 |

**한글 인코딩 주의** — HTTP 헤더는 사실상 latin-1이라 한글을 그대로 넣으면 서버가
`UnicodeEncodeError` 를 냅니다. `urllib.parse.quote()` 로 감싸고 파이에서 `unquote()` 로 풉니다.

**예외 처리**

- 전사가 비어있거나 너무 짧으면 → 분류기가 `calm` 폴백, `chat_service` 가
  `"음... 잘 못 들었어. 다시 한 번 말해줄래?"` 를 반환. **정상 200 응답으로 처리**합니다.
  파이는 이걸 그대로 재생하면 되므로 별도 분기가 필요 없습니다.
- GPT/TTS 예외 → 500. 파이는 ERROR LED 후 READY 복귀.

#### `tests/test_care_router.py` (신규)

기존 `tests/test_voice_router.py` 와 같은 패턴으로 작성. 모델은 전부 mock.

- 정상 요청 시 200 + `audio/wav` + 헤더 9개가 전부 붙는지
- 한글 라벨이 percent-encoded 되어 헤더에 들어가는지
- 전사가 빈 문자열일 때 500이 아니라 200 + fallback 헤더가 오는지
- 분류기가 폴백일 때 `X-Care-Fallback: 1` 인지
- temp 파일이 정리되는지

### 3.2 수정할 파일 2개

#### `main.py` (2줄 추가)

```
from routers import care, chat, diary, session, tts, voice   # care 추가
...
app.include_router(care.router)                              # 등록
```

#### `utils/audio_converter.py` (함수 1개 추가)

```
ensure_wav_16k_mono(input_path, output_path) -> str
```

`wave` 모듈로 헤더만 읽어서 이미 16000Hz / 1채널 / 16bit wav이면 **변환 없이 원본 경로를 그대로
반환**하고, 아니면 기존 `webm_to_wav()` 를 태웁니다.

- 기존 `webm_to_wav()` 는 **그대로 둡니다.** 기존 `routers/voice.py` 가 쓰고 있으므로 건드리지 않습니다.
- 파이는 처음부터 16k mono로 녹음하므로 ffmpeg 프로세스 실행(약 100~300ms)이 통째로 생략됩니다.
- 브라우저에서 webm이 오면 기존대로 변환됩니다.

#### `tests/test_audio_converter.py` (테스트 추가)

- 16k mono wav를 넣으면 변환이 일어나지 않고 입력 경로가 그대로 나오는지
- 44.1kHz stereo wav를 넣으면 변환이 일어나는지

### 3.3 서버에서 안 건드리는 것

명확히 해둡니다. 아래는 **읽기만 하고 수정하지 않습니다.**

```
services/emotion_classifier_service.py   ← 친구분 GPT 분류기
services/color_care_service.py           ← 친구분 색상표
services/voice_service.py
services/chat_service.py
services/tts_service.py
services/emotion_session.py
models/care.py
routers/voice.py    routers/chat.py    routers/tts.py
routers/session.py  routers/diary.py   routers/letter.py
```

---

## 4. 라즈베리파이에 만들 파일

파이의 `~/moong-care-pi/` 폴더에 들어갑니다. **서버 저장소와 별개**로 관리해도 되고,
저장소 안 `pi/` 폴더에 두고 파이로 복사해도 됩니다.

### 4.1 파일 목록

| 파일 | 줄 수(예상) | 역할 |
|---|---|---|
| `main.py` | 약 130 | 상태머신. 버튼 → 녹음 → 서버 → 재생 루프 |
| `led_controller.py` | 약 250 | WS2812 렌더러. 별도 스레드에서 60fps |
| `audio_io.py` | 약 100 | sounddevice 녹음(+음량 측정), aplay 재생 |
| `server_client.py` | 약 70 | `/care/turn` 호출 + 헤더 파싱 |
| `config.py` | 약 50 | 서버 주소, 핀 번호, 타임아웃 |
| `requirements.txt` | 5 | |
| `README.md` | | 배선/설치/문제해결 |

### 4.2 각 파일 상세

#### `config.py`

전부 환경변수로 덮어쓸 수 있게 합니다.

| 항목 | 기본값 | 비고 |
|---|---|---|
| `SERVER_BASE` | `http://192.168.0.10:8000` | PC의 `ipconfig` 주소 |
| `SESSION_ID` | `pi-<hostname>` | 프로세스 재시작 전까지 유지 |
| `CHAT_STYLE` | `empathetic` | |
| `TTS_VOICE` | `nova` | |
| `TIMEOUT_TURN` | `(5, 120)` | (연결, 응답). 5단계가 한 번에 도니 넉넉히 |
| `BUTTON_PIN` | `17` | **물리 11번 핀 = BCM 17** |
| `LED_PIN` | `12` | **물리 32번 핀 = BCM 12** (PWM0) |
| `LED_COUNT` | `24` | |
| `LED_FPS` | `60` | |
| `SAMPLE_RATE` | `16000` | 서버 STT 입력과 동일하게 |
| `MIN_RECORD_S` | `0.6` | 이보다 짧으면 오녹음으로 보고 버림 |
| `MAX_RECORD_S` | `30.0` | 버튼을 안 눌러도 자동 종료 |

#### `led_controller.py`

**설계 핵심: LED는 반드시 별도 스레드에서 돌아야 합니다.**

메인 스레드는 HTTP 응답을 최대 120초까지 기다립니다. 같은 스레드에서 LED를 그리면
그동안 화면이 완전히 멈춥니다. 그래서 구조를 이렇게 잡습니다.

```
메인 스레드                     LED 스레드 (daemon, 60fps 무한루프)
   │                                │
   │ set_state("processing") ──────▶ 상태 변수만 갱신 (lock)
   │                                │
   │ requests.post(...)  ← 8초 블로킹   그동안 계속 프레임을 그림
   │                                │
   │ set_care_color(...)  ─────────▶ 상태 변경
```

메인 스레드가 부르는 함수는 3개뿐입니다.

- `set_state(name, **params)` — 상태 전환
- `set_level(0.0~1.0)` — 녹음 중 음량 (마이크 콜백에서 호출)
- `set_care_color({hex, brightness, transition_ms})` — 감정색으로 전환

내부 구조:

- `PixelStrip` 을 `rpi_ws281x` 에서 import. **없으면 자동으로 콘솔 목업으로 대체** →
  PC에서도 로직 테스트가 됩니다.
- 프레임마다 상태별 함수가 24개 픽셀의 RGB 배열을 만들고, 이전 프레임과 선형 보간해서
  출력합니다. 상태가 바뀔 때 색이 뚝 끊기지 않고 부드럽게 넘어갑니다.
- 보간 속도는 `transition_ms` 로 조절. 상태 전환은 300ms, 감정색은 표의 값을 씁니다.

#### `audio_io.py`

`Recorder` 클래스:

- `start()` — `sounddevice.InputStream` 시작. 콜백에서 두 가지를 동시에 함
  1. 프레임을 리스트에 쌓음
  2. RMS를 계산해서 `led.set_level()` 로 넘김 → 링이 목소리 크기만큼 차오름
- `stop(path)` — 스트림 종료, numpy로 합쳐서 int16 wav 저장, `(경로, 길이초)` 반환
- `abort()` — 저장 없이 버림

`play_wav(path)` — `aplay -q` 를 `subprocess.run` 으로 블로킹 실행.

- **왜 aplay인가**: USB 스피커에서 sounddevice보다 말썽이 적고, 재생이 끝나야 리턴하므로
  "재생 끝 → READY" 전환을 별도 처리 없이 잡을 수 있습니다.

#### `server_client.py`

```
care_turn(wav_path, out_path) -> dict
```

- `POST {SERVER_BASE}/api/v1/care/turn` 에 multipart 업로드
- 응답 본문을 `out_path` 에 저장
- 헤더를 파싱해서 dict 반환:
  `{care_emotion, care_emotion_label, confidence, fallback, care_color{hex,brightness,transition_ms}, transcript, reply_text, timing, audio_path}`
- 한글 헤더는 `urllib.parse.unquote()` 로 복원
- `health()` — 부팅 시 서버 연결 확인용 `GET /health`

#### `main.py`

```
class MoongCare:
    run()                  메인 루프
    _to_ready()            상태 전환 + 버튼 큐 비우기
    _wait_press()          READY에서 버튼 대기
    _record()              RECORDING. 버튼 or 30초까지
    _process_and_speak()   PROCESSING → SPEAKING
    shutdown()             LED 끄고 정리
```

**버튼 처리 방식** — `gpiozero.Button` 의 `when_pressed` 콜백은 별도 스레드에서 불립니다.
콜백에서 직접 상태를 바꾸면 경쟁 상태가 생기므로, **콜백은 `queue.Queue` 에 타임스탬프만 넣고**
메인 루프가 꺼내 씁니다. `bounce_time=0.08` 로 채터링을 막습니다.

**상태 전환 시 큐 비우기** — READY 진입할 때 그동안 쌓인 버튼 입력을 버립니다.
안 그러면 답변 재생 중에 누른 게 다음 턴에서 즉시 발동합니다.

---

## 5. LED 색 정의

### 5.0 전제: 링을 눕히고 위에 확산 커버를 씌운다

이 전제가 색 설계를 크게 바꿉니다.

**커버 밑에서 사라지는 것**

- 개별 픽셀이 뭉개져 하나의 빛 덩어리가 됩니다 → 점 단위 표현은 전부 안 보입니다
  (흰색 피크 점, 픽셀별 반짝임, 얇은 꼬리)
- 눕혀놨으니 위아래가 없습니다 → "12시에서 차오른다" 같은 방향성이 의미를 잃습니다

**커버 밑에서도 확실히 살아남는 것 세 가지**

1. 전체 밝기
2. 색
3. 굵은 덩어리의 회전

이 셋만 써서 설계합니다.

### 5.1 구분 규칙

```
움직임(회전) 있음 + 채도 높음   =  기계의 상태
회전 없음 + 파스텔 단색 호흡     =  사람의 감정
```

표의 14색이 전부 채도 낮은 파스텔이라, 상태색은 **채도를 최대로 올리고 회전을 넣어**
헷갈리지 않게 합니다. 감정색은 반대로 회전을 완전히 멈추고 제자리에서 숨만 쉽니다.
커버를 씌우면 점이 안 보이고 색과 움직임만 남으므로 이 규칙이 오히려 더 선명해집니다.

### 5.2 상태 5가지

| 상태 | 색 | 밝기 | 애니메이션 |
|---|---|---|---|
| `ready` (질문 가능) | 무지개 전체 | 0.28 | 링 전체가 무지개. **8초에 한 바퀴** 아주 느리게 회전 + 4초 주기 밝기 호흡 |
| `recording` (녹음 중) | 앰버 → 주황빨강 | 0.10 ~ 0.72 | **방향 없음.** 링 전체 밝기가 음량을 그대로 따라감. 색상(hue)도 음량이 커지면 앰버에서 주황빨강 쪽으로 이동. 조용할 때도 굵은 파동 2개가 0.35Hz로 천천히 회전해 정지 화면이 안 됨 |
| `processing` (계산 중) | 무지개 | 0.55 | 링 전체가 무지개인 채로 **0.55초에 한 바퀴** 빠르게 회전. 밝기 파동 3개가 함께 돌아 확산돼도 움직임이 뚜렷함 |
| `error` (오류) | 빨강 ↔ 흰색 | 0.70 | 초당 4회, 빨강과 흰색을 **번갈아** 깜빡. 2초 후 자동 READY 복귀 |
| `boot` (부팅) | 무지개 | 0.35 | 12시부터 한 바퀴 무지개가 채워짐. 1.2초 1회. 커버를 벗기면 배선 순서 확인용으로도 쓸 수 있음 |

**커버 밑에서 서로 안 헷갈리는가**

| | 움직임 | 색 | 속도 |
|---|---|---|---|
| ready | 무지개 띠가 은은하게 회전 | 무지개 | 8.0초/바퀴 |
| recording | 전체가 목소리 따라 불규칙하게 출렁 | 앰버~주황빨강 | 말하는 대로 |
| processing | 무지개가 파동과 함께 빠르게 회전 | 무지개 | 0.55초/바퀴 |
| speaking | **회전 없음.** 제자리 호흡만 | 파스텔 단색 | 2.4~5.6초/호흡 |

무지개가 둘(ready·processing)이지만 **속도가 14배 차이**라 구분됩니다.

**왜 녹음 상태를 음량 연동으로 하는가** — 그냥 켜두면 마이크가 실제로 잡히고 있는지
알 수 없습니다. 목소리에 반응해서 밝기가 출렁이면 "내 말이 들어가고 있다"가 즉시 보이고,
마이크가 죽었을 때도 바로 알 수 있습니다. 디버깅 도구를 겸합니다.

**설계 검증** — `pi/led-preview.html` 을 브라우저로 열면 실제 계산식 그대로 애니메이션이
돌아갑니다. 생 LED와 커버 씌운 모습을 나란히 보여주고, 확산 강도 슬라이더로 실제 커버
두께·재질에 맞춰볼 수 있습니다. 값을 바꾸려면 이 파일에서 먼저 확인하고 옮기면 됩니다.

### 5.3 감정 14색 (친구분 `color_care_service.py` 값 그대로)

파이는 이 표를 **가지고 있지 않습니다.** 서버 응답 헤더로 받은 값을 그대로 씁니다.
표가 바뀌면 서버만 고치면 됩니다.

| care_emotion | 라벨 | hex | brightness | transition_ms |
|---|---|---|---|---|
| calm | 평온 | #A7CDBD | 0.42 | 1600 |
| joy | 기쁨/만족 | #F6C66D | 0.50 | 1200 |
| excitement | 설렘/들뜸 | #BFD8FF | 0.44 | 1800 |
| relief | 안도 | #B8E0C8 | 0.42 | 1800 |
| sadness | 슬픔 | #F2B6A0 | 0.38 | 2200 |
| loneliness | 외로움 | #E8B7D4 | 0.35 | 2400 |
| anxiety | 불안 | #8DB7D9 | 0.36 | 2000 |
| tension | 긴장 | #7DCAC3 | 0.38 | 1800 |
| anger | 분노/짜증 | #86BFA6 | 0.32 | 2500 |
| stress | 스트레스/과부하 | #91B7A8 | 0.34 | 2200 |
| fatigue | 피로 | #F0B06A | 0.30 | 2800 |
| helplessness | 무기력 | #D9B8A6 | 0.32 | 2800 |
| confusion | 혼란/당황 | #B6B4D8 | 0.34 | 2200 |
| shame_guilt | 자책/민망함 | #D8A6A1 | 0.32 | 2600 |

**호흡 주기 = `transition_ms` × 2** 로 씁니다. 피로(2800ms)는 5.6초에 한 번,
기쁨(1200ms)은 2.4초에 한 번 숨을 쉽니다. 느린 감정일수록 LED도 느리게 움직입니다.

밝기는 최대치의 60~100% 사이를 오갑니다. 0까지 떨어뜨리면 꺼진 것처럼 보입니다.

---

## 6. 배선

| 부품 | 연결 |
|---|---|
| WS2812 링 | 눕혀서 고정, 위에 확산 커버 (`config.LED_PIN = 12`) |
| WS2812 DIN | **물리 32번 핀 (BCM 12)** |
| WS2812 5V | **별도 5V 어댑터** (파이 5V 핀 아님) |
| WS2812 GND | 어댑터 GND + 파이 GND 공통 연결 |
| 택트 스위치 | **물리 11번 핀 (BCM 17)** ↔ GND (`config.BUTTON_PIN = 17`) |
| 마이크 | USB |
| 스피커 | USB |

**전원 주의** — 24구 × 최대밝기는 약 1.4A입니다. 파이 5V 핀에서 끌어오면 전압강하로
재부팅이 걸립니다. 이 설계의 밝기(0.28~0.60)면 실사용은 0.5A 이하지만, 부팅 시
무지개 스윕에서 순간적으로 튀므로 별도 어댑터가 안전합니다.

**GND 공통 연결 필수** — 어댑터와 파이의 GND를 묶지 않으면 데이터 신호의 기준 전압이
달라져서 LED가 엉뚱한 색을 내거나 아예 안 켜집니다.

**sudo 필요** — `rpi_ws281x` 가 PWM/DMA 레지스터를 직접 씁니다.
`sudo -E` 로 실행해야 환경변수(`MOONG_SERVER` 등)가 유지됩니다.

**PWM 충돌** — 파이 내장 아날로그 오디오가 PWM을 점유합니다. USB 오디오만 쓰면 상관없지만
문제가 생기면 `/boot/firmware/config.txt` 에서 `dtparam=audio=off`.

---

## 7. 작업 순서

### 1단계 — 브랜치 정리 ✅ 완료

`main` 브랜치로 전환 완료. `services/emotion_classifier_service.py` 확인됨.

### 2단계 — 서버 코드 ✅ 완료

1. ✅ `utils/audio_converter.py` 에 `ensure_wav_16k_mono()` 추가
2. ✅ `routers/care.py` 작성
3. ✅ `main.py` 에 라우터 등록 (+ CORS `expose_headers`)
4. ✅ `tests/test_care_router.py`, `tests/test_audio_converter.py` 작성
5. ✅ `pytest` 통과 확인 (신규 11개 + 기존 `test_voice_router.py`)

### 3단계 — 서버 단독 검증 (다음 할 일 — 실제 하드웨어에서)

파이 없이 PC에서 먼저 확인합니다.

```
uvicorn main:app --host 0.0.0.0 --port 8000
```

`sample.wav` (16kHz mono, 3~5초 한국어 발화) 준비 후

```
curl -X POST http://localhost:8000/api/v1/care/turn ^
  -F "session_id=test-1" -F "audio=@sample.wav;type=audio/wav" ^
  -D headers.txt --output reply.wav
```

- `headers.txt` 에 `X-Care-Emotion` 등 9개 헤더가 있는지
- `reply.wav` 가 재생되는지
- `X-Timing` 으로 어느 단계가 느린지

### 4단계 — 파이 코드 ✅ 완료 (하드웨어 확인만 남음)

1. ✅ `config.py`, `led_controller.py` 작성 (커버 씌운 기준, BCM12/BCM17 반영)
2. `sudo -E python3 led_controller.py` 로 **LED만 단독 확인** — 실제 파이에서 진행 필요
   → 부팅 스윕 / 무지개 회전 / 음량 연동 / 무지개 빠른 회전 / 빨강흰색 / 감정색 호흡 데모 포함
3. ✅ `audio_io.py` 그대로 사용 (변경 없음). `python3 audio_io.py` 로 장치 목록 확인은 파이에서
4. ✅ `server_client.py` — `/care/turn` 하나로 재작성, 헤더 파싱 로직 완료
5. ✅ `main.py` — 상태머신 완료, gpiozero mock으로 전 구간 검증 완료 (README 참고)

### 5단계 — 통합 확인

| 확인 항목 | 기대 |
|---|---|
| 부팅 | 무지개 스윕 후 느린 회전 |
| 버튼 1번 | 즉시 VU 미터로 전환, 말하면 링이 출렁 |
| 버튼 2번 | 즉시 혜성 애니메이션 |
| 4~8초 후 | 감정색 단색 호흡 + 답변 재생 |
| 재생 끝 | 다시 무지개 회전 |
| 서버 끔 | 빨강/흰색 3회 후 무지개 복귀 |
| 0.3초만 녹음 | 무시하고 바로 READY |
| 30초 방치 | 자동 종료 후 정상 처리 |

### 6단계 — 자동 시작 (선택)

`systemd` 유닛으로 부팅 시 자동 실행. `Restart=always` 로 죽어도 살아나게.

---

## 8. 결정이 필요한 것

| 항목 | 기본값(제안) | 비고 |
|---|---|---|
| 세션을 언제 끊을지 | 프로세스가 살아있는 동안 유지 | 하루 단위로 끊고 `/session/end` + `/diary/generate` 를 부를지 |
| 답변 재생 중 버튼 | 무시 (큐에서 버림) | "말 끊기"로 쓸지 |
| `style` | `empathetic` 고정 | 버튼 길게 누르기로 전환할지 |
| 오프라인 | ERROR 표시만 | 녹음을 쌓아뒀다 나중에 보낼지 |
| 파이 코드 위치 | 저장소 `pi/` 폴더 | 별도 저장소로 뺄지 |

---

## 9. 지금 상태 정리 (완료)

| | 상태 |
|---|---|
| 서버 `main` 브랜치 | 감정 분류기 + 색상표 완성됨 (친구분) — 로컬 브랜치 `main` 으로 전환 완료 |
| 서버 통합 엔드포인트 | **완료.** `routers/care.py` (`POST /api/v1/care/turn`) + `main.py` 등록 + `utils/audio_converter.py` 에 `ensure_wav_16k_mono()` 추가 |
| 서버 테스트 | **완료.** `tests/test_care_router.py`, `tests/test_audio_converter.py` 신규 11개 + 기존 `test_voice_router.py` 포함 전부 통과 확인 |
| 파이 코드 | **완료.** `pi/` 폴더 전체를 `/care/turn` 기준으로 작성. `care_map.py`(중복 로직)는 `pi/_to_delete/`로 이동 |
| 파이 상태머신 검증 | **완료.** gpiozero mock 백엔드로 READY→RECORDING→PROCESSING→SPEAKING→READY 전 구간 + 최소 녹음길이 스킵 로직 실행 검증 |
| LED 렌더링 검증 | **완료.** 커버 씌운 기준 5개 상태 + 감정색 전부 밝기 범위(0~255) 검증, `pi/led-preview.html` 과 동일한 계산식으로 코드 이식 |

**남은 것** — 실제 하드웨어(마이크·스피커·WS2812·택트 스위치)에서의 물리적 확인은
클라우드 환경에서 할 수 없으므로 파이에서 직접 진행해야 합니다. 7장의 3~5단계를
그대로 따라가면 됩니다. `pi/_to_delete/` 는 확인 후 지우셔도 됩니다.
