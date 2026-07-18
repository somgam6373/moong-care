# MoongCare Server

'뭉이' 캐릭터와 음성으로 대화하며 감정을 분석하고, 대화 종료 시 자동으로
일기를 생성해주는 FastAPI 백엔드. STT(SenseVoice) → SER(emotion2vec) →
LLM 대화(OpenAI) → TTS(CosyVoice2) → 일기 생성(OpenAI) 파이프라인을
하나의 서버로 묶는다.

---

## 아키텍처 한 줄 요약

FastAPI 앱 하나, 모델(STT/SER/TTS)은 서버 시작 시(`lifespan`) 한 번만
GPU에 로드해서 싱글톤으로 재사용. 대화 상태(턴 기록 + 감정 누적)는
`session_id`별로 **프로세스 메모리**에만 들고 있다가, 일기 생성 시점에만
MySQL에 최종 저장한다. 라우터는 얇게 — 입력 검증하고 service 함수 하나
호출해서 pydantic 모델로 응답하는 게 전부.

```
클라이언트
  └─ POST /api/v1/voice/analyze (session_id, webm 오디오)
       webm→wav(ffmpeg) → [STT ‖ SER ‖ pitch 분석 병렬 실행] → 세션 메모리에 turn 추가
       응답: { transcript, emotions, pitch_mean, pitch_std }
  └─ POST /api/v1/chat/reply (session_id, transcript, emotions)
       세션 히스토리 로드 → OpenAI 호출(감정 반영 프롬프트) → assistant turn 기록
       응답: { reply_text }
  └─ POST /api/v1/tts (text)
       CosyVoice2 zero-shot 추론 → wav 바이너리
  (위 3단계를 대화 턴 수만큼 반복)
  └─ POST /api/v1/session/end (session_id)
       누적 감정 평균 + dominant_emotion 계산 (세션은 안 지움)
       응답: { dominant_emotion, average_emotions }
  └─ POST /api/v1/diary/generate (session_id)
       세션 히스토리+평균감정으로 OpenAI가 1인칭 일기 + 한줄요약 생성
       → MySQL 저장 → 세션 메모리 정리(여기서만 세션이 삭제됨)
       응답: { diary_id, diary_text, summary, dominant_emotion }
```

---

## 기술 스택

| 영역 | 사용 기술 |
|---|---|
| STT | SenseVoice (`iic/SenseVoiceSmall`, funasr) |
| SER (감정분석) | emotion2vec (`iic/emotion2vec_plus_large`, funasr) |
| TTS | CosyVoice2 (`iic/CosyVoice2-0.5B`, zero-shot 모드) |
| LLM | OpenAI Chat Completions (대화 응답 + 일기/요약 생성) |
| DB | MySQL (로컬 인스턴스) |
| 웹 프레임워크 | FastAPI + uvicorn |
| 환경 | Python 3.10, Windows, GPU 8GB (torch cu121) |

---

## 왜 이렇게 만들었나 (설계 결정)

**GPU를 쓰는 이유**
실시간 대화 앱이라 한 턴마다 STT+SER+TTS를 돌려야 한다. CPU로 추론하면
합쳐서 5~10초 이상 걸려 대화 UX로 못 쓴다. GPU면 1~2초대로 줄어든다.
GPU가 8GB 카드 한 장뿐이라 세 모델이 자원을 두고 충돌하지 않도록
`asyncio.Lock`(`stt_lock`/`ser_lock`/`tts_lock`)을 `app.state`에 두고
추론 구간을 직렬화한다. blocking 추론 호출은 `run_in_threadpool`로
감싸서 이벤트 루프가 막히지 않게 한다.

**STT 결과를 후처리(태그 제거)하는 이유**
SenseVoice raw 출력은 `<|ko|><|NEUTRAL|><|Speech|><|woitn|>오늘 발표가
잘 됐어요` 처럼 언어/감정/이벤트/ITN 태그가 문장 앞에 그대로 붙어서
나온다. 이걸 그대로 GPT 프롬프트에 넣으면 응답 품질이 떨어지고, API
응답이나 일기에도 지저분하게 노출된다. `utils/text_parser.py`의
`strip_sensevoice_tags`(정규식 `<\|.*?\|>`)로 순수 텍스트만 남긴다.
(funasr가 제공하는 `rich_transcription_postprocess`는 태그를 이모지로
바꿔치기하는 함수라 우리 목적과 안 맞아서 안 씀 — 우리는 이모지 없이
그냥 태그만 지우면 됨.)

**SER 결과를 후처리하는 이유**
emotion2vec raw 출력은 `labels: ["生气/angry", "开心/happy", ...]`,
`scores: [0.05, 0.65, ...]` 형태의 병렬 배열이고 라벨에 중국어가 섞여
있다. 이걸 그대로 못 쓰는 이유:
- API 응답 스펙이 `{"angry": 0.05, ...}` 형태의 dict를 요구함
- `services/emotion_session.py`가 턴마다 감정을 누적 합산하는데
  (`emotion_sums[cls] += ...`), 이게 되려면 클래스 이름이 매 턴 동일한
  영어 키로 고정돼 있어야 함

그래서 `services/ser_service.py`의 `parse_emotion2vec_output`이
`"生气/angry"`에서 영어 부분만 뽑아 고정된 영어 키 dict로 변환한다.

**피치(pitch) 분석을 추가한 이유**
emotion2vec 감정 점수만으로는 "이 판단을 얼마나 믿을 수 있나"를 알기 어렵다.
`voice/analyze` 응답에 `pitch_mean`/`pitch_std`(발화 구간 F0 평균/표준편차,
Hz 단위)를 추가해서 사람이 참고할 수 있는 보조 지표로 노출한다 — 서버 판단
로직(감정 선택, 챗 응답, 일기 생성)에는 관여하지 않는 순수 부가 정보다.
`pitch_std`는 정식 jitter/shimmer 지표가 아니라 발화 전체의 억양 기복을
"떨림" 근사치로 쓰는 것뿐이다. 계산은 이미 설치돼 있던 `pyworld`(CosyVoice가
내부적으로 씀)로 하기 때문에 새 의존성이 없다. `services/pitch_service.py`
가 담당하고, GPU를 안 쓰는 순수 CPU 연산이라 STT/SER와 함께
`asyncio.gather`로 병렬 실행된다. (실측 사례: transcript가 `"."`처럼
STT가 못 알아들은 경우에도 `pitch_mean`이 정상 범위로 나오면 "소리는
났는데 인식만 실패한 것"과 "진짜 무음"을 구분하는 데 도움이 된다.)

**세션을 DB가 아니라 메모리에 두는 이유**
데모/발표용 로컬 단일 프로세스 환경이라 서버 재시작 시 세션이 날아가도
문제없다는 전제. 매 턴마다 DB를 왕복하는 대신 메모리에 두고, 대화가
끝나서 일기로 확정될 때만 MySQL에 쓴다. `session/end`는 세션을 지우지
않고(재조회 가능해야 하니까), `diary/generate`가 끝나야 비로소
`SESSIONS.pop(session_id)`로 정리한다.

**무음/의미없는 발화 가드**
STT가 침묵이나 잡음을 두고 `"I."`, `"."` 같은 의미 없는 텍스트를
만들어내는(hallucination) 경우가 실제로 있었다. 이런 짧은 transcript로
LLM을 부르면 토큰 낭비고, LLM이 근거 없이 "힘들었구나" 식으로 넘겨짚는
이상한 응답을 만든다. `services/chat_service.py`에 가드를 추가해서
(구두점 제거 후 길이 2 미만이면) OpenAI 호출 자체를 스킵하고
`"음... 잘 못 들었어. 다시 한 번 말해줄래?"` 고정 응답을 반환한다.

**CORS를 열어둔 이유**
`scripts/manual_test.html` 같은 로컬 테스트 페이지에서 브라우저 fetch로
직접 API를 호출할 수 있어야 해서 `main.py`에 `CORSMiddleware`를 넣어
모든 origin을 허용해뒀다. 로컬 개발/데모용 설정이고, 배포 환경에서는
좁혀야 한다.

**LLM 프로바이더는 OpenAI**
한 번 Claude API로 바꿔봤다가 크레딧 문제로 다시 OpenAI로 되돌렸다.
`services/openai_client.py`가 OpenAI SDK를 감싸고,
`chat_service`/`diary_service`/`summary_service` 세 곳에서 이걸 통해
`client.chat.completions.create(...)`를 호출한다. 프로바이더를 바꾸고
싶으면 이 네 파일만 건드리면 된다 (`config.py`의 `OPENAI_API_KEY`/
`OPENAI_MODEL`도 함께).

---

## 프로젝트 구조

```
moongcare-server/
├── main.py                    # FastAPI 앱, lifespan에서 모델 로딩, 라우터 등록, CORS
├── config.py                  # pydantic-settings, .env 값 읽기
├── routers/                   # 엔드포인트 5개 (voice/chat/tts/session/diary)
├── services/
│   ├── stt_service.py         # SenseVoice 추론 + 태그 제거
│   ├── ser_service.py         # emotion2vec 추론 + dict 변환
│   ├── voice_service.py       # STT/SER/pitch 병렬 실행 (asyncio.gather)
│   ├── pitch_service.py       # pyworld로 피치(F0) 평균/표준편차 계산
│   ├── tts_service.py         # CosyVoice2 zero-shot 추론
│   ├── openai_client.py       # OpenAI 클라이언트 싱글톤
│   ├── chat_service.py        # 대화 응답 생성 (+ 무음 가드)
│   ├── diary_service.py       # 1인칭 일기 생성
│   ├── summary_service.py     # 일기 한줄요약
│   └── emotion_session.py     # 세션 메모리 CRUD, 감정 누적/평균
├── models/                    # pydantic 요청/응답 스키마
├── database/                  # SQLAlchemy 연결 + Diary 테이블
├── utils/
│   ├── audio_converter.py     # ffmpeg로 webm→wav 변환
│   └── text_parser.py         # SenseVoice 태그 제거
├── tests/                     # pytest, 각 모듈 단위 테스트
├── scripts/
│   ├── manual_e2e_check.md    # curl로 전체 플로우 수동 확인하는 체크리스트
│   └── manual_test.html       # 브라우저에서 직접 녹음→대화→TTS 테스트하는 페이지
└── CosyVoice/                 # CosyVoice2 원본 레포 통째로 vendoring (gitignore됨)
```

---

## 시작하기 (포크 후 셋업)

### 0. 사전 준비물

- Python 3.10
- NVIDIA GPU + CUDA (torch cu121 기준, 8GB VRAM 이상 권장). GPU 없으면
  `main.py`의 `device="cuda:0"`를 `"cpu"`로 바꿔야 하는데 그러면 위에
  적은 것처럼 응답이 매우 느려짐.
- ffmpeg (PATH에 등록돼 있어야 함 — 없으면 서버가 기동 시점에 fail-fast)
- 로컬 MySQL 인스턴스
- OpenAI API 키

### 1. 가상환경 & 의존성

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

torch/torchaudio는 cu121 빌드가 필요하면 별도로:
```powershell
.venv\Scripts\pip install torch==2.3.1 torchaudio==2.3.1 --index-url https://download.pytorch.org/whl/cu121
```

`requirements.txt`에 CosyVoice/Matcha-TTS 서브모듈이 import 시점에
요구하는 부가 패키지(`setuptools<81`, `matplotlib`, `wget`, `grpcio`,
`onnx`, `pyarrow`, `pyworld`, `tensorboard`)도 이미 포함돼 있다 —
CosyVoice 공식 requirements엔 없지만 실제로 돌려보니 빠져있던 것들.

### 2. CosyVoice 코드 받기

`CosyVoice/` 폴더는 `.gitignore`돼 있어서 이 저장소를 클론해도 안 딸려
온다. 직접 받아야 함:
```powershell
git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git
```
프로젝트 루트에 `CosyVoice/`로 위치시킬 것.

### 3. `.env` 설정

`.env.example`을 `.env`로 복사하고 값 채우기:
```
OPENAI_API_KEY=sk-...        # 본인 키
OPENAI_MODEL=gpt-4o-mini
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=...           # 본인 로컬 MySQL 비번
MYSQL_DB=moongcare
STT_MODEL_DIR=iic/SenseVoiceSmall
SER_MODEL_DIR=iic/emotion2vec_plus_large
TTS_MODEL_DIR=pretrained_models/CosyVoice2-0.5B
```

STT/SER는 이 ID 그대로 두면 funasr가 첫 실행 때 ModelScope에서 자동
다운로드한다 — 별도 작업 불필요.

### 4. CosyVoice2 가중치 받기 (TTS, 수동 다운로드 필요)

```powershell
.venv\Scripts\python -c "from modelscope import snapshot_download; snapshot_download('iic/CosyVoice2-0.5B', local_dir='pretrained_models/CosyVoice2-0.5B')"
```
5GB 정도 됨. `TTS_MODEL_DIR`이 `.env`에서 이 경로를 가리켜야 한다
(C드라이브 공간 부족하면 다른 드라이브 절대경로로 지정해도 됨).

> **디스크 공간 팁**: STT/SER/TTS 가중치를 합치면 수 GB인데 기본
> 캐시 경로가 `C:\Users\<user>\.cache\modelscope`라 C드라이브가
> 작으면 꽉 찰 수 있음. 환경변수 `MODELSCOPE_CACHE`를 다른 드라이브
> 경로로 설정해두면 그쪽으로 받는다. (이미 열려있는 터미널은 이
> 환경변수를 못 받으니 설정 후 새 터미널에서 실행할 것.)

### 5. MySQL 준비

`.env`에 적은 `MYSQL_DB` 이름으로 데이터베이스만 미리 만들어두면 됨
(테이블은 서버가 시작할 때 `init_db()`가 자동 생성):
```sql
CREATE DATABASE moongcare;
```

### 6. 서버 실행

```powershell
.venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000
```
또는 IDE에서 `main.py` 재생 버튼으로도 실행 가능 (`if __name__ ==
"__main__"` 진입점 있음).

첫 실행은 모델 다운로드 때문에 오래 걸림. 로그 마지막에
`Application startup complete.` / `Uvicorn running on
http://0.0.0.0:8000` 뜨면 정상.

`http://localhost:8000/health` 호출해서 `{"status":"ok"}` 뜨면 확인
끝.

### 7. 테스트

```powershell
.venv\Scripts\pytest tests/
```
전부 통과해야 정상 (모델 로딩 없이 fake로 돌아가서 빠름).

브라우저에서 실제 플로우 눈으로 확인하려면 `scripts/manual_test.html`을
로컬 웹서버로 띄워서 열면 됨 (마이크 권한은 `localhost`/`file://`처럼
secure context에서만 뜬다):
```powershell
cd scripts
python -m http.server 8081
```
→ `http://localhost:8081/manual_test.html`

curl 기반 체크리스트는 `scripts/manual_e2e_check.md` 참고.

---

## 이 프로젝트를 만든 방식 (Claude Code / Superpowers)

이 서버는 Claude Code + `superpowers` 플러그인 스킬 세트로 개발했다.
과정을 그대로 남겨두면 나중에 비슷한 작업 할 때 참고가 될 것 같아 정리함.

### 1단계 — 설계 (별도 세션)

코드를 짜기 전에 **superpowers:brainstorming** → **superpowers:writing-plans**
스킬로 먼저 설계부터 했다. 결과물이 저장소에 그대로 남아있음:

- `docs/superpowers/specs/2026-07-18-moongcare-server-design.md`
  — 요구사항을 정리한 설계 스펙 (API 응답 형태, 세션 상태 관리 방식,
  동시성 처리, 에러 처리 원칙 등을 코드 짜기 전에 문서로 먼저 확정)
- `docs/superpowers/plans/2026-07-18-moongcare-server-implementation.md`
  — 위 스펙을 20개 태스크로 쪼갠 구현 계획. 태스크마다 "실패하는 테스트
  작성 → 구현 → 테스트 통과 확인 → 커밋" 순서가 미리 못박혀 있음(TDD).

이렇게 설계를 먼저 문서로 굳혀두면, 실제 구현 단계에서 "이걸 왜
이렇게 만들었더라"를 다시 고민할 필요 없이 계획대로 순서대로 짜면 됨.

### 2단계 — 구현 (이 세션)

Task 9부터 이어서 진행하면서 **superpowers:executing-plans**와
**superpowers:subagent-driven-development** 스킬을 로드해서 검토했다.
다만 subagent-driven-development는 태스크마다 별도 서브에이전트를
띄워 병렬로 구현시키는 방식인데, 이 프로젝트는 태스크끼리 서로
import하는 구조라(예: `routers/*.py`가 `services/*.py`를, 그게 다시
`emotion_session.py`를 참조) 병렬로 나눠서 시키기엔 결합도가 너무
높다고 판단해서 — 서브에이전트 없이 계획서에 적힌 순서 그대로 한
태스크씩 직접 TDD로 구현했다 (테스트 작성 → 실행해서 실패 확인 →
구현 → 통과 확인 → 그 태스크만 커밋, 다음 태스크로).

각 태스크가 끝날 때마다 커밋을 나눴기 때문에 git 로그를 보면
Task 1~20이 거의 그대로 커밋 단위로 남아있다 (`feat: add SenseVoice
STT wrapper`, `feat: add voice/analyze router` 등).

### 3단계 — 기능 추가 (피치 분석, 같은 세션 안에서 풀 사이클로 진행)

Task 1~20이 끝난 뒤 "감정 신뢰도 보조지표로 피치/떨림 수치를 추가하고
싶다"는 요청이 들어왔을 때는, 태스크 이어서 하기가 아니라 **완전히
새로운 기능이라 브레인스토밍부터 다시 시작**했다:

1. **superpowers:brainstorming** — 한 번에 하나씩 질문하며 범위를 좁힘
   ("떨림 수치를 API에 그냥 노출만 할 건지, 서버 판단 로직에 반영할
   건지" 등). 합의된 설계를 `docs/superpowers/specs/2026-07-19-pitch-analysis-design.md`에 문서화.
2. **superpowers:writing-plans** — 위 스펙을 5개 태스크(TDD 단계 포함)로
   쪼갠 계획을 `docs/superpowers/plans/2026-07-19-pitch-analysis-implementation.md`에 작성. 이때 계획에 적을 기대값(사인파 220Hz 입력 시 피치 평균이
   실제로 얼마나 나오는지)을 미리 스크립트로 돌려서 검증한 뒤 계획에
   반영함 — 계획 문서에 근거 없는 숫자를 적지 않기 위함.
3. **superpowers:executing-plans** — 계획대로 태스크 5개를 순서대로
   TDD로 구현.

이 사이클(브레인스토밍 → 계획 → 실행)이 새 기능을 추가할 때의 기본
패턴이고, Task 1~20처럼 "이미 계획이 있는 작업 이어하기"와는 시작점이
다르다는 걸 구분해두면 됨.

### 그 외 사용한 스킬

- **claude-api**: OpenAI → Claude API로 LLM 프로바이더를 바꿔볼 때
  로드함. 최신 모델 ID(`claude-opus-4-8` 등), Anthropic SDK 사용법
  (`client.messages.create` — OpenAI의 `chat.completions.create`와
  달리 system 프롬프트가 별도 파라미터로 빠짐), 마이그레이션 체크리스트를
  참고해서 `services/chat_service.py` 등을 고쳤다. (이후 크레딧 문제로
  다시 OpenAI로 되돌림 — 위 "LLM 프로바이더는 OpenAI" 항목 참고.)
- **artifact-design**: 마이크로 음성을 녹음해서 다운로드하는 테스트
  페이지를 Claude Artifact로 처음 만들 때 로드함. 다만 Artifact가
  샌드박스 iframe이라 마이크 권한이 막혀서, 실제로는 로컬 `python -m
  http.server`로 띄우는 `scripts/manual_test.html` 쪽으로 옮겨감 —
  Artifact 버전은 디자인 참고용으로만 남음.

### 왜 이렇게 기록해두나

Claude한테 다시 이 프로젝트를 맡기거나 팀원이 비슷한 방식으로 다른
기능을 추가하고 싶을 때, "설계 문서 먼저 → 태스크 쪼개기 → 태스크당
TDD로 커밋" 이 순서를 그대로 재사용할 수 있게 하려고 남겨둠. 실제
설계 스펙/계획 문서가 `docs/superpowers/` 밑에 그대로 있으니 필요하면
열어보면 됨.

---

## 알려진 제한사항

- **TTS 목소리**: CosyVoice2 zero-shot용 레퍼런스 음성이 아직
  placeholder(`CosyVoice/asset/zero_shot_prompt.wav`, 중국어 화자)라
  한국어 발음이 외국인 억양처럼 들림. `services/tts_service.py`의
  `PLACEHOLDER_PROMPT_WAV`/`PLACEHOLDER_PROMPT_TEXT`를 한국어 레퍼런스
  음성+정확한 스크립트로 교체하면 해결됨.
- **STT 정확도**: 짧은 발화에서 SenseVoice가 가끔 다르게 알아듣는
  경우가 있음 — 모델 자체 한계.
- **세션 휘발성**: 서버 재시작하면 진행 중이던 세션(대화 기록)은 전부
  날아감. 데모 환경 전제라 의도된 동작.
