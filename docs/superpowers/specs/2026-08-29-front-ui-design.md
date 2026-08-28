# MoongCare 프론트엔드 (front-ui) 설계

날짜: 2026-08-29

## 1. 개요

'뭉이: 음성 대화를 통한 감정 치유와 수면 케어를 제공하는 스마트 무드등' 서비스의 웹 프론트엔드를
`front-ui/` 디렉토리에 새로 만든다. 기존 백엔드(`routers/`, `services/`, `models/`, `database/` 등)는
**한 줄도 수정하지 않는다** — `docs/api-spec.md`와 실제 라우터/pydantic 모델 코드를 직접 읽어 확인한
요청/응답 스키마에 맞춰 프론트에서 호출만 한다. 백엔드는 CORS가 전체 허용(`allow_origins=["*"]`)
되어 있어 별도 프록시 없이 브라우저에서 바로 fetch 가능하다.

핵심 경험은 세 화면이다: 대화 시작 → **음성 대화(턴 반복)** → 대화 종료 후 뭉이의 편지 리빌.
대화 화면이 서비스의 핵심 UI이며, 턴마다 사용자의 감정을 분석해 그 감정을 완화하는 색을 화면
전체에 반영하고, 뭉이가 그 색과 이유를 함께 설명해준다.

## 2. 범위 밖 (Non-goals)

- **일기(diary_text) 표시** — `diary/generate` 응답에 포함되지만 화면에는 노출하지 않는다. DB 저장은
  서버가 알아서 하므로 프론트 입장에서는 그냥 안 쓰는 필드다.
- **과거 일기/편지 아카이브 화면** — `GET /diary`, `GET /letter` 목록/상세 API는 있지만 이번 범위에서
  안 만든다. 나중에 필요하면 별도 스펙으로 추가.
- **표정 인식(FER, 카메라)** — `docs/fer.md`에 따르면 아직 백엔드에 통합되지 않은 기능이다. "뭉이 얼굴"은
  캐릭터 아바타를 뜻하며, 사용자 웹캠을 쓰는 기능이 아니다.
- **reply_text/letter_text 자체의 번역** — 백엔드가 한국어로만 생성한다. ko/en 토글은 UI 크롬(버튼,
  라벨, 감정명)에만 적용되고, 뭉이가 실제로 한 말은 항상 한국어 그대로 노출한다.
- **음성/스타일 선택 UI** — voice(`nova` 등), style(`empathetic`/`realistic`) 파라미터는 기본값만 쓰고
  선택 UI는 만들지 않는다 (요청 범위 밖, 필요하면 나중에 추가).
- **라즈베리파이 전용 스트리밍 엔드포인트(`/api/v1/care/turn`)** — 파이 하드웨어 전용이므로 웹
  프론트는 `voice/analyze` + `tts`를 각각 호출하는 기존 `manual_test.html` 방식을 따른다.

## 3. 기술 스택 & 프로젝트 구조

- **React 18 + TypeScript + Vite**. 저장소의 `.claude/launch.json`이 이미 `moong-care-frontend` 설정으로
  vite(5173 포트) 실행을 기대하고 있어 그대로 맞춘다 (경로만 실제 `front-ui`로 갱신).
- `front-ui/`는 백엔드 저장소(`moong-care`, remote `hyun-sai/moong-care.git`) 안쪽에 둔다
  (`moong-care/front-ui/`) — 별도 홈 디렉토리에 걸쳐있던 엉뚱한 git 저장소 문제를 피하고, 프론트/백엔드를
  한 저장소로 관리하기 위함.
- API 베이스 URL: `VITE_API_BASE_URL` 환경변수 (기본값 `http://localhost:8000`), `.env.example` 제공.
- 상태관리: React Context + `useReducer`. 화면이 3개뿐이고 상태 전이가 단순해 외부 상태관리 라이브러리는
  과함(YAGNI).
- 폴더 구조:

```
front-ui/
├── src/
│   ├── api/            # voice.ts, tts.ts, session.ts, diary.ts — fetch 래퍼, 백엔드 스키마와 1:1 타입
│   ├── assets/          # 뭉이 일러스트 (플레이스홀더 → 실제 파일 교체 예정)
│   ├── components/
│   │   ├── MoongFace/    # 캐릭터 얼굴 (눈 깜빡임 + 입 움직임)
│   │   ├── PitchWaveform/ # 실시간 녹음 파형 캔버스
│   │   ├── SpeechBubble/  # "고민 중" 로딩 ↔ reply_text
│   │   ├── EmotionColorBar/ # "사용자의 감정: X" / "X의 색상: Y (밝기) — 이유"
│   │   ├── EmotionAtmosphere/ # 전체 배경 그라데이션 (care_color/sleep_color 반영)
│   │   └── LetterCard/    # 편지지 UI + 타이프라이터 리빌
│   ├── screens/
│   │   ├── IntroScreen.tsx
│   │   ├── ConversationScreen.tsx
│   │   └── EndingScreen.tsx
│   ├── state/            # ConversationContext, reducer, 타입
│   ├── i18n/              # ko/en 사전 + useTranslation 훅
│   ├── constants/          # careEmotions.ts (14개 감정 라벨/색이름/케어이유, ko+en)
│   └── App.tsx
├── .env.example
├── index.html
├── package.json
└── vite.config.ts
```

## 4. 화면 흐름 (상태머신)

```
Intro → (대화 시작 클릭) → Conversation ⟲(턴 반복) → (대화 종료 클릭) → Ending → (새 대화 시작) → Intro
```

- **Intro**: 뭉이 인사 문구 + "대화 시작" 버튼. 클릭 시 `crypto.randomUUID()`로 `session_id` 발급 후
  Conversation으로 전환.
- **Conversation**: 핵심 화면 (5절 참고). "대화 종료" 버튼은 턴이 1개 이상 성공적으로 끝난 뒤에만
  활성화된다 (턴이 0개인 상태로 `session/end`를 부르면 404가 나기 때문 — `routers/session.py`의
  `compute_average`가 `KeyError` → 404).
- **Ending**: `session/end` → `diary/generate` 순서로 호출 후 편지 리빌 (6절 참고).

## 5. 대화 화면 — 턴 하나의 UI/데이터 흐름

**레이아웃**: 화면 중앙에 뭉이 얼굴(크게) → 그 아래 실시간 음성 파형 → 그 아래 녹음 버튼. 말풍선은
뭉이 위쪽에 붙는다. 감정/색상 정보 바는 말풍선 아래(또는 옆)에 위치. 배경 전체는
`EmotionAtmosphere`가 은은한 그라데이션으로 덮는다.

```
[버튼 클릭] 녹음 시작
  └ getUserMedia({audio:true}) + MediaRecorder(webm/opus)
  └ AnalyserNode로 실시간 입력 파형을 캔버스에 그림 (PitchWaveform)
[버튼 다시 클릭] 녹음 정지 → 즉시 전송
  └ 말풍선: "답변 고민 중..." (로딩 점 애니메이션, SpeechBubble의 loading 상태)
  └ POST /api/v1/voice/analyze  (multipart/form-data: session_id, style="empathetic", audio=blob)
       → VoiceAnalyzeResponse {
           transcript, emotions, pitch_mean, pitch_std,
           care_emotion, care_emotion_label, care_confidence,
           care_color: { hex, brightness, transition_ms },
           reply_text
         }
  └ 말풍선 내용을 reply_text로 교체 (SpeechBubble → reply 상태)
  └ EmotionColorBar 갱신:
       왼쪽: "사용자의 감정: {care_emotion_label}"
       오른쪽: "{care_emotion_label}의 색상: {색이름} ({밝기표현}) — {케어 이유}"
       (색이름/케어이유는 constants/careEmotions.ts에서 care_emotion 코드로 lookup,
        밝기표현은 API가 준 brightness 숫자를 기준으로 그때그때 계산: >=0.4 "환하게",
        0.3~0.4 "포근하게", <0.3 "은은하게" — 하드코딩하지 않고 실제 값 기반)
  └ EmotionAtmosphere: 배경을 care_color.hex로 전환, transition은 transition_ms를 그대로 CSS
     transition-duration에 사용해 부드럽게 넘어감
  └ POST /api/v1/tts  (JSON: { text: reply_text, session_id })
       → audio/wav blob
       → <audio> 재생 시작과 SpeechBubble의 reply_text 표시를 동시에 트리거
       → MoongFace: 재생 중 AnalyserNode로 음량 진폭을 매 프레임 뽑아 입 오버레이 height에 매핑
         (뻥긋뻥긋 — 실제 립싱크 아닌 음량 기반 근사)
       → 재생 종료 시 입 자동으로 닫힘 복귀. 눈 깜빡임은 이 흐름과 무관하게 랜덤 인터벌(2~6초)로
         항상 별도로 돎.
```

- `POST /api/v1/tts` 실패는 대화를 막지 않는다 — 이미 말풍선에 텍스트는 떠 있으므로 오디오만
  best-effort로 재생 시도하고 실패하면 조용히 무시(콘솔 경고만).
- `chat/reply`는 부르지 않는다 (`voice/analyze`가 이미 `reply_text`까지 반환하므로 API 명세서의
  2026-08-22 변경사항과 일치).

## 6. 대화 종료 화면

```
[버튼] 대화 종료
  └ POST /api/v1/session/end  (JSON: { session_id })
       → SessionEndResponse { dominant_emotion, average_emotions, sleep_color }
       → EmotionAtmosphere 배경을 sleep_color로 전환
  └ POST /api/v1/diary/generate  (JSON: { session_id })
       → DiaryGenerateResponse { diary_id, letter_id, diary_text, letter_text, summary,
                                   dominant_emotion }
       → diary_text는 응답에 오지만 화면엔 렌더링하지 않음 (DB 저장은 서버가 알아서 함)
       → 서버가 session/end에서 캐싱한 sleep_color를 diary/generate에서 재사용하므로
         반드시 end → generate 순서로 호출 (services/diary_service.py의 캐시 재사용 로직)
  └ LetterCard: 귀여운 편지지 배경(크림색 종이 질감 + 봉투/도장 느낌) 안에
       상단: "오늘의 감정: {dominant_emotion 라벨}" 태그
       본문: letter_text 타이프라이터 리빌
  └ "새 대화 시작" 버튼 → 새 session_id 발급, Intro로 전환
       (서버 세션은 diary/generate 호출 시점에 이미 clear됨 — services/emotion_session.py의
        clear_session, 프론트가 별도로 정리할 상태는 없음)
```

## 7. 뭉이 캐릭터 (MoongFace)

- 정적 일러스트(현재는 플레이스홀더, 실제 파일 전달되면 `src/assets/`로 교체) 위에 눈/입 위치에
  절대좌표 오버레이(타원)를 얹어 `height` 0~100%로 애니메이션한다. 오버레이 좌표는
  `constants/moongFaceOverlay.ts`에 상수로 분리해 실제 이미지에 맞춰 조정 가능하게 한다.
- **눈 깜빡임**: 랜덤 인터벌(2~6초)로 트리거, 150ms 왕복 (뜬 상태 → 감은 상태 → 뜬 상태).
- **입 움직임**: TTS 오디오 재생 중에만 활성. `AnalyserNode.getByteFrequencyData`로 프레임마다 음량을
  뽑아 입 높이(%)로 매핑. 재생 종료 시 닫힌 상태로 복귀.
- 실제 일러스트 파일이 아직 없으므로, 우선 CSS로 그린 플레이스홀더 원형 캐릭터로 개발/테스트하고
  파일이 오면 이미지 교체 + 오버레이 좌표만 조정하면 되는 구조로 만든다 (컴포넌트 로직 변경 불필요).

## 8. 감정 케어 색상 시스템

- `constants/careEmotions.ts`에 **14개 감정 코드 → {label_ko, label_en, colorName_ko, colorName_en,
  careReason_ko, careReason_en}** 표를 프론트에 둔다. 실제 `hex`/`brightness`/`transition_ms`는 항상
  백엔드 응답값을 그대로 쓴다 (색상 로직 이중 관리 금지 — `services/color_care_service.py`가 유일한
  진실 소스).
- `colorName_*`은 `services/color_care_service.py`의 `REALTIME_COLORS` hex 값을 보고 사람이 읽을 수
  있는 이름으로 붙인다 (예: `joy` `#F6C66D` → "따뜻한 골드").
- `careReason_*`은 `docs/prompts_Engineering/2026-08-13-emotion-care-mood-light-development-plan.md`의
  "케어 방향" 컬럼 문구를 그대로 가져와 ko 작성, en은 간단히 의역한다.
- 수면 색(4개 프로필)은 API가 프로필 이름을 안 주므로(`SessionEndResponse`에 `sleep_color`만 있고
  프로필 코드는 없음), 종료 화면 라벨은 `dominant_emotion`의 라벨을 그대로 재사용한다.

## 9. 언어 지원 (ko/en 토글)

- `i18n/dict.ts`에 UI 문자열 + 14개 감정 라벨/색이름/케어이유만 ko/en 두 세트로 관리.
- 토글 버튼은 상단 고정 위치. 전환 시 뭉이의 실제 발화(reply_text/letter_text/summary)는 항상
  한국어 그대로 노출됨을 작은 안내 문구로 명시.

## 10. API 연동 계약 (실제 코드 기준)

프론트가 호출하는 엔드포인트와 정확한 스키마 — `models/*.py`, `routers/*.py`를 직접 읽어 확인함:

| 호출 시점 | 엔드포인트 | 요청 | 응답 |
|---|---|---|---|
| 턴마다 | `POST /api/v1/voice/analyze` | multipart: `session_id`, `style`, `audio`(webm) | `VoiceAnalyzeResponse` (models/voice.py) |
| reply_text 받은 직후 | `POST /api/v1/tts` | JSON `TTSRequest`: `text`, `session_id` | `audio/wav` 바이너리 |
| 대화 종료 | `POST /api/v1/session/end` | JSON `SessionEndRequest`: `session_id` | `SessionEndResponse` (models/emotion.py) |
| 종료 직후 | `POST /api/v1/diary/generate` | JSON `DiaryGenerateRequest`: `session_id` | `DiaryGenerateResponse` (models/diary.py) |

프론트 `api/` 레이어는 이 4개 함수만 있으면 되고, 각 함수의 반환 타입은 위 pydantic 모델 필드와
1:1로 맞춘 TypeScript 인터페이스로 정의한다.

## 11. 에러 처리

- 마이크 권한 거부 → 안내 배너, 녹음 버튼 비활성화 상태 유지.
- `voice/analyze` 네트워크 실패 → 토스트 표시, 말풍선은 "고민 중" 상태에서 원상복구(재녹음 유도),
  이전 턴 상태(배경색 등) 유지.
- `tts` 실패 → 콘솔 경고만, 대화 흐름 막지 않음 (10절 참고).
- `session/end`/`diary/generate` 실패(404 등) → 에러 배너 + "다시 시도" 버튼, Conversation 화면으로
  롤백 가능하게.

## 12. 테스트 전략

- **Vitest + React Testing Library**: reducer(상태 전이), `careEmotions` 매핑, i18n 사전 lookup,
  밝기 표현 계산 함수 등 순수 로직 단위 테스트.
- **API 레이어**: fetch mock으로 요청 바디 형태와 응답 파싱이 스펙과 일치하는지 계약 테스트.
- **수동 확인**: 실제 백엔드 서버(`uvicorn main:app`)를 띄운 상태에서 `npm run dev`로 브라우저 확인
  (마이크 필요 — 기존 `scripts/manual_test.html`과 동일하게 `localhost`인 secure context에서만 동작).

## 13. 향후 확장 (지금은 안 함)

- 일기/편지 아카이브 목록·상세 화면 (`GET /diary`, `GET /letter` 활용).
- 실제 뭉이 일러스트 다중 상태 프레임으로 교체.
- voice/style 선택 UI.
