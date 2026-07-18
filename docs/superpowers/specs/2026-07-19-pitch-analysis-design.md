# 음성 피치(pitch) 분석 추가 설계

날짜: 2026-07-19

## 개요

`voice/analyze` 응답에 피치(음높이) 평균/표준편차를 추가한다. emotion2vec
감정 점수를 대체하거나 감정 판단 로직에 관여하지 않는, 순수 부가 정보
(감정 신뢰도를 사람이 참고할 수 있는 보조 지표)다.

## 범위

- **포함**: `voice/analyze` 응답에 `pitch_mean`, `pitch_std` 필드 추가.
- **제외**: jitter/shimmer 등 정식 음성 떨림(voice tremor) 지표는 다루지
  않는다 — `pitch_std`(피치 표준편차)를 떨림의 근사치로만 사용한다.
  세션 누적 평균(`emotion_session.py`), `chat/reply` 프롬프트,
  `diary/generate`는 이 값을 참고하지 않는다 (서버 판단 로직에
  영향 없음, 순수 노출용 수치).

## 지표 정의

- **pitch_mean**: 발화 구간(유성음 프레임만) F0(기본주파수)의 평균, 단위 Hz.
- **pitch_std**: 같은 구간 F0의 표준편차, 단위 Hz. 값이 클수록 발화 중
  억양 기복이 컸다는 뜻 — "떨림" 근사 지표로 사용.
- 무성음/무음 프레임(F0=0)은 통계 계산에서 제외한다.
- 유성음 프레임이 하나도 없으면(완전 무음) `pitch_mean=0.0`,
  `pitch_std=0.0`을 반환한다.

## 구현 방식

- 라이브러리: `pyworld` (이미 `requirements.txt`에 있음, CosyVoice가
  내부적으로 씀 — 새 의존성 없음), 오디오 로딩은 `soundfile`(이미 설치돼
  있음, 별도 requirements 명시는 불필요 — 다른 패키지의 전이 의존성으로
  이미 들어와 있음).
- `pyworld.dio()`로 프레임별 F0 1차 추정 → `pyworld.stonemask()`로
  정제 → F0 배열에서 0보다 큰 값만 골라 평균/표준편차 계산.

## 파일 구조

- 신규: `services/pitch_service.py`
  - `analyze_pitch(wav_path: str) -> tuple[float, float]`
  - 기존 `stt_service.py`/`ser_service.py`와 동일한 패턴(모델 객체 없이
    순수 함수, GPU 안 씀 → `asyncio.Lock` 불필요).
- 수정: `services/voice_service.py`
  - `analyze_voice()`가 STT/SER와 함께 pitch 분석도 `asyncio.gather`로
    병렬 실행.
  - 반환 타입: `(transcript, emotions)` → `(transcript, emotions, pitch_mean, pitch_std)`
- 수정: `models/voice.py`
  - `VoiceAnalyzeResponse`에 `pitch_mean: float`, `pitch_std: float` 필드 추가.
- 수정: `routers/voice.py`
  - `analyze_voice()`의 4개 반환값을 받아 응답 모델에 채워 넣음.

## API 응답 예시

```json
{
  "transcript": "오늘 발표가 잘 됐어요",
  "emotions": {"happy": 0.65, "sad": 0.10, "neutral": 0.20, "angry": 0.05},
  "pitch_mean": 187.3,
  "pitch_std": 24.1
}
```

## 에러 처리

- 완전 무음/무성음만 있는 오디오: 예외를 던지지 않고 `(0.0, 0.0)` 반환
  (STT의 "I.", "." 같은 hallucination 케이스와 동일하게 정상 200 응답
  경로 유지).
- `pyworld` 처리 중 예외 발생 시: 기존 STT/SER과 동일하게 500 + 로그로
  처리 (별도 예외 처리 로직 추가하지 않음 — 기존 라우터 에러 처리 원칙
  따름).

## 테스트 계획

- `tests/test_pitch_service.py`
  - 유성음이 섞인 짧은 sine wave 합성 오디오로 `pitch_mean`이 대략
    입력 주파수 근처로 나오는지 확인.
  - 무음 오디오(`anullsrc` 등) 입력 시 `(0.0, 0.0)` 반환 확인.
- `tests/test_voice_service.py`
  - `analyze_voice`가 STT/SER/pitch 세 개를 병렬로 호출하고 4-tuple을
    반환하는지 확인 (fake로 세 서비스 모두 monkeypatch).
- `tests/test_voice_router.py`
  - 라우터 응답 JSON에 `pitch_mean`/`pitch_std` 필드가 포함되는지 확인.
- `tests/test_models.py`
  - `VoiceAnalyzeResponse`에 새 필드 round-trip 확인.
