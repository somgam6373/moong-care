# 감정 케어 무드등 개발 계획

날짜: 2026-08-13

## 개요

MoongCare의 핵심 경험을 "감정 분석 대화 서버"에서 **감정 케어 무드등**으로 확장한다.
사용자의 음성을 매 턴 분석하고, 그 순간의 감정을 완화하는 색상을 실시간으로 라즈베리 파이에
HTTP push한다. 대화가 종료되면 전체 대화 흐름을 종합해 수면에 도움이 되는 최종 무드등 색상을
반환하고, `diary/generate`는 기존 일기 대신 뭉이가 써주는 편지 형태의 리포트를 생성한다.

이 문서는 구현 전에 고정해야 할 설계 방향, 프롬프트 엔지니어링 전략, API 변경안, 태스크 순서를
정리한다. 기존 개발 방식은 `docs/설계 방법론.md`의 "설계 문서 먼저, 테스트 먼저 구현" 흐름을 따른다.

---

## 1. 배경과 문제 정의

현재 서버는 emotion2vec의 9개 감정 점수 중 가장 높은 값을 `dominant_emotion`으로 채택한다.
이 방식은 구현이 단순하지만 다음 문제가 있다.

1. **top-1 편향**
   - `happy=0.31`, `sad=0.29`, `neutral=0.28`처럼 감정이 섞인 턴도 `happy` 하나로 확정된다.
   - 미세한 점수 차이가 극단적인 최종 결과로 바뀐다.

2. **케어 목적과 모델 라벨의 불일치**
   - emotion2vec 라벨은 `angry`, `disgusted`, `fearful`, `happy`, `neutral`, `other`, `sad`,
     `surprised`, `unknown`이다.
   - 무드등은 감정을 그대로 표현하는 것이 아니라 **감정을 완화하고 안정시키는 색상**을 제공해야 한다.
   - 따라서 모델 라벨을 서비스 고유의 감정 케어 분류로 재해석해야 한다.

3. **텍스트 의미 손실**
   - 음성 신호만 보면 사용자가 실제로 어떤 상황을 말했는지 알 수 없다.
   - 예를 들어 같은 `fearful` 점수라도 발표 전 긴장, 안전 문제, 관계 불안은 케어 방향이 다를 수 있다.

해결 방향은 emotion2vec의 top-1 결과를 최종 감정으로 쓰지 않고, **9개 점수 전체 + transcript +
pitch 지표 + 최근 대화 맥락**을 LLM이 읽어 MoongCare 전용 감정 분류로 판단하게 만드는 것이다.

---

## 2. 확정된 요구사항

### 2.1 실시간 감정 케어 색상

- 매 음성 턴마다 감정 케어 색상을 도출한다.
- 색상은 "현재 감정을 표현하는 색"이 아니라 **현재 감정을 완화하는 색**이다.
- 서버는 도출된 색상을 라즈베리 파이에 HTTP push한다.
- API 응답에도 같은 색상 정보를 포함한다.

색상 payload는 다음 필드를 갖는다.

```json
{
  "mode": "realtime",
  "emotion": "anxiety",
  "hex": "#8DB7D9",
  "brightness": 0.36,
  "transition_ms": 2000
}
```

### 2.2 수면등 색상

- 대화 종료 시 `session/end`에서 전체 대화 흐름을 고려해 수면에 도움이 될 최종 색상을 반환한다.
- 이 색상은 마지막 턴 하나의 감정이 아니라 세션 전체 감정 흐름을 안정화하는 색상이다.
- 서버는 최종 수면등 색상도 라즈베리 파이에 HTTP push한다.

```json
{
  "mode": "sleep",
  "emotion": "settled",
  "hex": "#C9785A",
  "brightness": 0.16,
  "transition_ms": 6000
}
```

### 2.3 라즈베리 파이 연동

- 라즈베리 파이 연동 방식은 HTTP push로 한다.
- endpoint는 기존 서버 API 스타일을 맞춰 `/api/v1/mood-light/color` 형태를 기본안으로 한다.
- endpoint가 비어 있으면 서버는 push를 건너뛰고 API 응답은 정상 반환한다.
- endpoint 연결 실패나 timeout은 warning log만 남기고 API 응답은 실패시키지 않는다.

환경변수:

```env
MOOD_LIGHT_ENDPOINT=http://<raspberry-pi-ip>:8000/api/v1/mood-light/color
MOOD_LIGHT_TIMEOUT_SECONDS=2
```

### 2.4 편지형 리포트

- `diary/generate`는 기존 "일기" 중심 응답에서 **뭉이가 사용자에게 써주는 편지** 형태로 확장한다.
- 기존 `diary_text`는 유지한다.
- 편지는 `diaries` 테이블 컬럼으로 섞지 않고 `letters` 전용 테이블에 저장한다.
- API 응답에는 `diary_id`, `letter_id`, `diary_text`, `letter_text`를 함께 반환한다.

---

## 3. 확정된 설계 결정

이번 회의에서 다음 네 항목을 구현 기준으로 확정한다.

1. **최종 감정 분류**
   - emotion2vec의 9개 라벨보다 세분화한 MoongCare 전용 감정 분류 `14개`를 사용한다.
   - LLM은 반드시 이 허용 목록 중 하나를 선택한다.

2. **감정별 색상 매핑**
   - LLM이 매번 색상을 자유 생성하지 않는다.
   - LLM은 감정 분류만 수행하고, 색상은 서버의 고정 테이블에서 `hex/brightness/transition_ms`로 결정한다.

3. **라즈베리 파이 endpoint**
   - 기본 endpoint 형식은 `http://<raspberry-pi-ip>:8000/api/v1/mood-light/color`로 한다.
   - 실제 IP와 port는 `.env`의 `MOOD_LIGHT_ENDPOINT`로 주입한다.

4. **라즈베리 파이 실패 정책**
   - endpoint 미설정, 연결 실패, timeout은 대화 API를 실패시키지 않는다.
   - warning log만 남기고 API 응답에는 서버가 의도한 색상값을 그대로 반환한다.
   - 초기 버전에는 재시도/큐잉을 넣지 않는다.

---

## 4. 감정 분류 확정안

최종 감정 분류는 `14개`로 한다. 9개보다 충분히 세분화하면서도 LLM이 안정적으로 구분 가능한 범위를
넘지 않는 수준이다.

| 코드 | 한국어 라벨 | 의미 | 케어 방향 |
|---|---|---|---|
| `calm` | 평온 | 안정적이고 특별한 동요가 낮음 | 유지, 부드럽게 안정 |
| `joy` | 기쁨/만족 | 만족감, 즐거움, 뿌듯함 | 과각성 없이 따뜻하게 유지 |
| `excitement` | 설렘/들뜸 | 긍정적이지만 각성이 높음 | 들뜸을 부드럽게 낮춤 |
| `relief` | 안도 | 긴장/걱정 이후 풀림 | 안정된 회복감 유지 |
| `sadness` | 슬픔 | 속상함, 상실감, 울적함 | 따뜻하게 위로 |
| `loneliness` | 외로움 | 고립감, 소속감 부족 | 포근함과 연결감 제공 |
| `anxiety` | 불안 | 걱정, 예측 불가, 초조 | 안정감과 호흡 유도 |
| `tension` | 긴장 | 발표/시험/대면 전 압박 | 차분하게 이완 |
| `anger` | 분노/짜증 | 억울함, 화, 날카로운 반응 | 진정, 탈각성 |
| `stress` | 스트레스/과부하 | 할 일 과다, 압박 누적 | 과부하 완화 |
| `fatigue` | 피로 | 지침, 에너지 저하 | 회복감, 부담 완화 |
| `helplessness` | 무기력 | 의욕 저하, 막막함 | 낮은 자극으로 안정 |
| `confusion` | 혼란/당황 | 정리되지 않음, 놀람, 어수선함 | 질서감과 안정 |
| `shame_guilt` | 자책/민망함 | 후회, 부끄러움, 자기비난 | 부드러운 수용감 제공 |

설계 원칙:

- 모델 라벨을 그대로 UI 감정으로 쓰지 않는다.
- 최종 분류는 `emotion2vec` 점수만이 아니라 발화 의미와 피치까지 함께 본다.
- 감정을 치료하거나 의학적으로 진단한다고 표현하지 않는다.
- 색상은 감정을 표현하는 색이 아니라 완화 방향의 색이다.

---

## 5. 색상 매핑 확정안

### 5.1 근거와 원칙

실시간 색상은 "감정 표현색"이 아니라 "감정 완화색"이다. 따라서 분노에 빨강, 불안에 고채도 파랑처럼
감정 자체를 증폭할 수 있는 색을 직접 쓰지 않는다.

근거:

- Valdez & Mehrabian(1994): 색의 밝기와 채도는 PAD(Pleasure-Arousal-Dominance) 감정 차원에
  강하게 작용한다. 케어 목적에서는 과채도와 과밝기를 피한다.
- Plitnick et al.(2010): 야간 red/blue light 모두 alertness와 positive affect를 올릴 수 있다.
  실시간 케어에서는 고채도 red/blue를 피한다.
- Brainard et al.(2001), Cajochen 계열 연구: 짧은 파장과 높은 melanopic irradiance는 멜라토닌과
  수면 흐름에 영향을 줄 수 있다. 수면등에서는 고밝기 blue/cool white를 피한다.
- CDC/NIOSH: 밤에는 dim red, very dim yellow/orange 계열이 circadian clock 부담이 적은 방향이다.

### 5.2 실시간 감정 케어 색상

| care_emotion | hex | brightness | transition_ms |
|---|---:|---:|---:|
| `calm` | `#A7CDBD` | `0.42` | `1600` |
| `joy` | `#F6C66D` | `0.50` | `1200` |
| `excitement` | `#BFD8FF` | `0.44` | `1800` |
| `relief` | `#B8E0C8` | `0.42` | `1800` |
| `sadness` | `#F2B6A0` | `0.38` | `2200` |
| `loneliness` | `#E8B7D4` | `0.35` | `2400` |
| `anxiety` | `#8DB7D9` | `0.36` | `2000` |
| `tension` | `#7DCAC3` | `0.38` | `1800` |
| `anger` | `#86BFA6` | `0.32` | `2500` |
| `stress` | `#91B7A8` | `0.34` | `2200` |
| `fatigue` | `#F0B06A` | `0.30` | `2800` |
| `helplessness` | `#D9B8A6` | `0.32` | `2800` |
| `confusion` | `#B6B4D8` | `0.34` | `2200` |
| `shame_guilt` | `#D8A6A1` | `0.32` | `2600` |

### 5.3 수면등 색상

`session/end`에서는 감정 하나에 직접 색을 매핑하지 않고, 세션 전체 흐름을 `sleep_profile`로 요약한 뒤
색상을 결정한다.

| sleep_profile | 적용 조건 | hex | brightness | transition_ms |
|---|---|---:|---:|---:|
| `warm_dim` | 기본 수면 안정 | `#C9785A` | `0.16` | `6000` |
| `deep_amber` | 불안/긴장/스트레스/분노가 높음 | `#B85A3D` | `0.12` | `8000` |
| `soft_peach` | 슬픔/외로움/무기력/피로가 높음 | `#D18461` | `0.14` | `7000` |
| `low_rose` | 자책/민망함/관계 감정이 높음 | `#B96F6B` | `0.13` | `7000` |

### 5.4 참고 자료

- Valdez, P., & Mehrabian, A. (1994). *Effects of color on emotions.*
  https://pubmed.ncbi.nlm.nih.gov/7996122/
- Plitnick, B., Figueiro, M. G., Wood, B., & Rea, M. S. (2010). *The effects of red and blue light on alertness and mood at night.*
  https://journals.sagepub.com/doi/10.1177/1477153509360887
- Brainard, G. C., et al. (2001). *Action Spectrum for Melatonin Regulation in Humans.*
  https://www.jneurosci.org/content/21/16/6405
- Schöllhorn, I., Stefani, O., Spitschan, M., Cajochen, C., et al. (2023).
  *Melanopic irradiance defines the impact of evening display light on sleep latency, melatonin and alertness.*
  https://www.nature.com/articles/s42003-023-04598-4
- CDC/NIOSH. *The Color of the Light Affects the Circadian Rhythms.*
  https://archive.cdc.gov/www_cdc_gov/niosh/emres/longhourstraining/color.html

---

## 6. 프롬프트 엔지니어링 계획

### 6.1 실시간 감정 분류 프롬프트 입력

LLM에는 다음 정보를 전달한다.

```json
{
  "transcript": "오늘 발표 때문에 너무 긴장돼",
  "voice_emotion_scores": {
    "angry": 0.02,
    "disgusted": 0.01,
    "fearful": 0.42,
    "happy": 0.05,
    "neutral": 0.30,
    "other": 0.03,
    "sad": 0.11,
    "surprised": 0.04,
    "unknown": 0.02
  },
  "pitch": {
    "mean": 211.4,
    "std": 38.2
  },
  "recent_context": [
    {
      "role": "user",
      "text": "내일 발표가 있어",
      "care_emotion": "tension"
    }
  ],
  "allowed_emotions": [
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
    "shame_guilt"
  ]
}
```

### 6.2 실시간 감정 분류 프롬프트 출력

모델 출력은 JSON으로 제한한다.

```json
{
  "care_emotion": "tension",
  "confidence": 0.74,
  "reason": "발화 내용은 발표 전 압박을 말하고 있고, fearful 점수와 pitch_std가 높아 긴장으로 판단했다."
}
```

출력 규칙:

- `care_emotion`은 허용 목록 중 하나여야 한다.
- `confidence`는 0~1 숫자다.
- `reason`은 디버깅용이며 사용자에게 그대로 노출하지 않는다.
- 색상은 이 프롬프트에서 만들지 않는다. 색상은 서버의 매핑 테이블에서 결정한다.

### 6.3 수면등 색상 판단 프롬프트

`session/end`에서는 전체 세션의 감정 타임라인을 입력한다.

```json
{
  "turns": [
    {
      "transcript": "오늘 발표 때문에 너무 긴장됐어",
      "care_emotion": "tension",
      "confidence": 0.74
    },
    {
      "transcript": "그래도 끝나고 나니까 좀 후련했어",
      "care_emotion": "relief",
      "confidence": 0.66
    }
  ],
  "average_voice_emotion_scores": {
    "fearful": 0.31,
    "neutral": 0.29,
    "happy": 0.18
  }
}
```

출력은 서버가 사용할 수면 안정화 목적의 판단으로 제한한다.

```json
{
  "sleep_care_state": "settled_recovery",
  "recommended_profile": "warm_dim",
  "reason": "세션 전반에 긴장과 부담이 많았지만 후반에는 완화 흐름이 있어 낮은 밝기의 따뜻한 색이 적합하다."
}
```

최종 `hex`, `brightness`, `transition_ms`는 `recommended_profile`을 서버 색상 테이블에 매핑해 결정한다.

---

## 7. API 변경안

### 7.0 기존 엔드포인트 설계 기준

현재 서버의 엔드포인트는 다음 패턴을 쓴다.

| endpoint | method | request 형식 | response 형식 | 비고 |
|---|---|---|---|---|
| `/health` | GET | 없음 | JSON | 서버 상태 확인 |
| `/api/v1/voice/analyze` | POST | multipart form (`session_id`, `audio`) | JSON | 오디오 업로드 때문에 form 사용 |
| `/api/v1/chat/reply` | POST | JSON body | JSON | `session_id`, `transcript`, `emotions`, `style` |
| `/api/v1/tts` | POST | JSON body | `audio/wav` bytes | TTS 바이너리 응답 |
| `/api/v1/session/end` | POST | JSON body | JSON | 세션 종료/요약성 응답 |
| `/api/v1/diary/generate` | POST | JSON body | JSON | 생성 액션 |
| `/api/v1/diary` | GET | query string | JSON list | 목록 조회 |
| `/api/v1/diary/{diary_id}` | GET | path param | JSON | 상세 조회 |

라즈베리 파이 endpoint는 이 패턴에 맞춰 `POST /api/v1/mood-light/color`를 기본안으로 한다.
서버가 라즈베리 파이에 HTTP push할 때는 JSON body를 보낸다.

### 7.1 `POST /api/v1/voice/analyze`

기존 필드는 유지한다.

추가 응답:

```json
{
  "transcript": "오늘 발표 때문에 너무 긴장돼",
  "emotions": {
    "fearful": 0.42,
    "neutral": 0.30
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

서버 내부 side effect:

```json
{
  "mode": "realtime",
  "emotion": "tension",
  "hex": "#7DCAC3",
  "brightness": 0.38,
  "transition_ms": 1800
}
```

### 7.2 `POST /api/v1/session/end`

기존 필드는 유지한다.

추가 응답:

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

서버 내부 side effect:

```json
{
  "mode": "sleep",
  "emotion": "settled",
  "hex": "#C9785A",
  "brightness": 0.16,
  "transition_ms": 6000
}
```

### 7.3 `POST /api/v1/diary/generate`

추가 응답:

```json
{
  "diary_id": 1,
  "letter_id": 1,
  "diary_text": "기존 호환용 텍스트",
  "letter_text": "오늘 네 이야기를 들으면서...",
  "summary": "발표 전 긴장과 끝난 뒤의 안도감",
  "dominant_emotion": "tension"
}
```

DB 변경:

- 기존 `diaries` 테이블은 유지한다.
- 새 `letters` 전용 테이블을 만든다.
- 두 테이블은 장기적으로 함께 유지한다.

`letters` 테이블 초안:

| column | type | nullable | 설명 |
|---|---|---:|---|
| `id` | Integer PK | N | letter id |
| `session_id` | String(64) | N | 원본 세션 id |
| `diary_id` | Integer | Y | 같은 세션에서 생성된 diary id. 생성 실패/분리 저장을 고려해 nullable |
| `letter_text` | Text | N | 뭉이가 작성한 편지 전문 |
| `summary` | String(255) | N | 편지 한 줄 요약 |
| `dominant_emotion` | String(32) | N | 세션 대표 감정 또는 대표 care emotion |
| `sleep_color` | Text | Y | `hex/brightness/transition_ms` JSON 문자열 |
| `created_at` | DateTime | N | 생성 시각 |

---

## 8. 신규 모듈 계획

### 8.1 `services/emotion_classifier_service.py`

역할:

- transcript, emotion2vec 전체 점수, pitch 지표, 최근 세션 맥락을 받아 LLM 감정 분류를 수행한다.
- 출력은 구조화된 `care_emotion`, `confidence`, `reason`으로 제한한다.
- LLM 출력이 깨지거나 허용 목록 밖이면 fallback 정책을 적용한다.

확정 fallback:

- transcript가 거의 비어 있거나, LLM 호출 실패/JSON 파싱 실패/허용 목록 밖 감정 반환이 발생하면 `calm`으로 처리한다.
- fallback이 발생해도 API 응답은 정상 반환하고, 실시간 무드등에는 `calm`의 케어 색상을 보낸다.

### 8.2 `services/color_care_service.py`

역할:

- `care_emotion`을 케어 색상 프로필로 변환한다.
- 확정된 실시간/수면 색상 매핑표가 들어갈 위치다.
- 실시간 프로필과 수면 프로필을 분리한다.

예상 인터페이스:

```python
def get_realtime_color(care_emotion: str) -> CareColor:
    ...

def get_sleep_color(profile: str) -> CareColor:
    ...
```

### 8.3 `services/mood_light_client.py`

역할:

- 라즈베리 파이에 HTTP POST를 보낸다.
- endpoint 미설정 시 no-op.
- 연결 실패와 timeout은 API 전체를 실패시키지 않고 warning log만 남긴다.
- 초기 버전에는 재시도/큐잉을 넣지 않는다.

예상 인터페이스:

```python
def push_color(payload: MoodLightPayload) -> None:
    ...
```

### 8.4 `services/sleep_color_service.py`

역할:

- 세션 전체 감정 타임라인을 종합해 수면등 프로필을 고른다.
- 초기에는 규칙 기반으로 시작할 수 있고, 필요하면 LLM 판단을 붙인다.
- 단, 최종 색상 자체는 서버 매핑 테이블에서 가져온다.

### 8.5 `services/letter_service.py`

역할:

- 대화 기록, 감정 흐름, 수면 색상 정보를 바탕으로 뭉이의 편지를 생성한다.
- 기존 `diary_service.py`를 확장할지 별도 서비스로 분리할지는 구현 전 결정한다.

권장:

- `diary_service.py`와 `diaries` 테이블은 기존 호환을 위해 유지
- 새 편지 생성은 `letter_service.py`로 분리
- 새 편지 저장은 `database/letter_repository.py`와 `letters` 테이블로 분리
- `routers/diary.py`에서 둘을 조합

---

## 9. 세션 상태 변경안

현재 `TurnRecord`는 다음 구조다.

```python
class TurnRecord:
    role: str
    text: str
    emotions: dict[str, float] | None = None
```

확장안:

```python
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

주의:

- dataclass 필드를 추가하면 기존 테스트가 깨질 수 있으므로 기본값을 둔다.
- 감정 평균 계산은 기존 emotion2vec raw score 기준으로 유지한다.
- 새 감정 케어 타임라인은 별도 helper로 계산한다.

---

## 10. 구현 태스크 계획

### Phase 1. 스키마와 세션 저장 구조

1. `models/voice.py`에 실시간 케어 감정/색상 응답 필드 추가
2. `models/emotion.py`에 `sleep_color` 응답 필드 추가
3. `models/diary.py`에 `letter_id`, `letter_text` 응답 필드 추가
4. `services/emotion_session.py`에 턴별 `pitch`, `care_emotion`, `care_color` 저장 구조 추가
5. 기존 테스트 업데이트 및 회귀 확인

### Phase 2. 감정 분류 프롬프트

1. 확정된 14개 감정 분류를 상수로 추가
2. `services/emotion_classifier_service.py` 신설
3. LLM JSON 출력 파싱 및 허용 목록 검증
4. LLM 실패/무음/짧은 transcript fallback을 `calm`으로 구현
5. 단위 테스트 작성

### Phase 3. 색상 케어 매핑

1. 확정된 `care_emotion -> realtime color` 매핑 구현
2. 확정된 `sleep_profile -> sleep color` 매핑 구현
3. `services/color_care_service.py` 신설
4. 밝기/전환시간 범위 validation 추가
5. 단위 테스트 작성

### Phase 4. 라즈베리 파이 HTTP push

1. `config.py`에 `MOOD_LIGHT_ENDPOINT`, `MOOD_LIGHT_TIMEOUT_SECONDS` 추가
2. `services/mood_light_client.py` 신설
3. endpoint 미설정 no-op 처리
4. push 실패 시 로그만 남기는 정책 구현
5. 라우터 테스트에서 HTTP push mock 검증

### Phase 5. `voice/analyze` 통합

1. `voice_service.analyze_voice()` 결과에 기존 `transcript/emotions/pitch` 유지
2. 라우터에서 LLM 감정 분류 호출
3. 감정별 care color 매핑
4. 세션에 raw emotions + care result 저장
5. 라즈베리 파이 실시간 색상 push
6. API 응답 확장

### Phase 6. `session/end` 수면등 통합

1. 세션 전체 care emotion timeline 조회 helper 추가
2. 수면등 프로필 판단 로직 구현
3. sleep color 매핑
4. 라즈베리 파이 sleep 색상 push
5. API 응답 확장

### Phase 7. 편지형 리포트

1. `services/letter_service.py` 신설
2. 뭉이 편지 프롬프트 작성
3. `database/letter_repository.py`와 `letters` 테이블 추가
4. `diary/generate`에서 기존 diary 저장과 letter 저장을 모두 수행
5. `diary/generate` 응답에 `letter_id`, `letter_text` 포함
6. `diaries`와 `letters` 두 테이블을 장기 유지

---

## 11. 테스트 계획

### 단위 테스트

- `emotion_classifier_service`
  - LLM mock 응답이 허용 감정으로 파싱되는지
  - LLM 실패/JSON 파싱 실패/허용 목록 밖 감정이 오면 `calm`으로 fallback되는지
  - transcript, emotion2vec score, pitch, recent_context가 prompt에 들어가는지

- `color_care_service`
  - 감정별 색상 매핑
  - brightness 범위 0~1 검증
  - transition_ms 양수 검증

- `mood_light_client`
  - endpoint 미설정 시 no-op
  - endpoint 설정 시 올바른 JSON POST
  - HTTP 실패 시 예외를 삼키고 로그 처리

- `emotion_session`
  - care emotion timeline 저장
  - 기존 average emotion 계산이 깨지지 않는지

### 라우터 테스트

- `voice/analyze`
  - 기존 응답 필드 유지
  - `care_emotion`, `care_color` 추가
  - mood light push 호출 검증

- `session/end`
  - 기존 평균 감정 응답 유지
  - `sleep_color` 추가
  - sleep mode push 호출 검증

- `diary/generate`
  - `letter_id`, `letter_text` 응답 포함
  - `diaries` 저장 확인
  - `letters` 저장 확인

### 수동 테스트

- 라즈베리 파이 endpoint mock 서버 실행
- 브라우저 또는 기존 manual test 페이지에서 음성 입력
- 매 턴마다 realtime payload 수신 확인
- session/end 호출 시 sleep payload 수신 확인

---

## 12. 구현 시 주의사항

1. **감정 분류와 색상 매핑을 섞지 않는다**
   - LLM은 감정 분류만 한다.
   - 색상은 서버의 고정 매핑에서 결정한다.

2. **emotion2vec raw score를 계속 보존한다**
   - top-1은 최종 판단에 사용하지 않더라도 디버깅과 리포트에 필요하다.

3. **실시간 API는 너무 느려지지 않아야 한다**
   - LLM 감정 분류가 `voice/analyze` 경로에 추가되므로 latency를 반드시 측정한다.
   - 필요하면 `chat/reply`와 통합하거나 비동기 후처리 전략을 검토한다.

4. **라즈베리 파이 실패가 대화를 막으면 안 된다**
   - 무드등 push 실패와 대화 API 실패를 분리한다.

5. **수면등은 고각성 색상을 피한다**
   - 기본 수면등은 낮은 밝기, 느린 전환, warm/dim 계열을 쓴다.
   - 고밝기 blue/cool white는 수면등 매핑에 넣지 않는다.

6. **편지 리포트는 감정 진단처럼 쓰지 않는다**
   - "너는 불안 장애다" 같은 표현 금지.
   - "오늘 이야기에서는 긴장이 많이 느껴졌어"처럼 대화 기반 관찰로 표현한다.

---

## 13. 사용자 확인 대기 항목

다음 항목은 구현 전 반드시 확인한다.

1. 라즈베리 파이 실제 IP/port

---

## 14. 권장 구현 순서

최소 위험 순서는 다음과 같다.

1. 문서와 스키마부터 확정한다.
2. 확정된 색상 매핑과 mood light client를 먼저 단위 테스트로 만든다.
3. LLM 감정 분류 서비스를 mock 기반으로 붙인다.
4. `voice/analyze` 응답 확장과 realtime push를 붙인다.
5. `session/end` sleep color를 붙인다.
6. 마지막으로 `diary/generate`를 편지형 리포트로 확장한다.

이 순서를 따르면 하드웨어 연동, LLM 프롬프트, DB 변경이 한 번에 섞이지 않아 회귀를 좁게 잡을 수 있다.
