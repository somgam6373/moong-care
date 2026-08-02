# FER (표정 감정 인식) 도입 검토

> 상태: **검증 완료, 통합 대기**
> 담당 스크립트: `scripts/fer_check.py`
> 의존성: `requirements-fer.txt`

현재 MoongCare는 **음성만으로** 감정을 판단한다 (emotion2vec). 여기에
**사용자의 표정**을 추가로 읽어 감정 판정의 정확도를 올리는 것이 이 문서의 목표다.

---

## 1. 왜 EmotiEffLib인가

음성 쪽 emotion2vec에 대응하는 "얼굴 쪽 표준"을 찾은 결과다.

| | 채택 이유 | 비고 |
|---|---|---|
| **EmotiEffLib** (ex-HSEmotion) | pip 한 줄, 모델 16~30MB, ONNX 지원, Apache-2.0 | **채택** |
| ModelScope FER | 이미 쓰는 modelscope 생태계 | VGG19라 무겁고 정확도 낮음 |
| POSTER++ / DDAMFN | 논문 SOTA | pip 패키지 없음, 체크포인트 수동 로딩 |
| OpenAI vision | GPU 부담 0 | 턴마다 API 호출, 확률 벡터 아님 |

**EmotiEffLib 요약**

- 저장소: https://github.com/sb-ai-lab/EmotiEffLib
- 라이선스: **Apache-2.0** (상업적 사용 제한 없음)
- 검증: ABAW(CVPR/ECCV 워크샵 감정인식 대회) 3~10회차 연속 입상
- 논문: ICML 2023 Oral, IEEE Trans. Affective Computing 2022

### 1.1 누가 만들었나

**Andrey V. Savchenko** — 사실상 단독 저자다.

| | |
|---|---|
| 소속 | HSE University(러시아 고등경제대학, Nizhny Novgorod 캠퍼스) 정교수 |
| | Sber AI Lab 과학 디렉터 (Sber = 러시아 최대 은행 Sberbank) |
| 전공 | 컴퓨터 비전, 패턴 인식, 머신러닝, 음성 처리 |
| 이메일 | andrey.v.savchenko@gmail.com (PyPI 등록 저자) |

구 이름 `HSEmotion`은 **HSE + Emotion**으로, 소속 대학 이름을 그대로 붙인 것이다.
지금도 ABAW 대회 참가 팀명이 "HSEmotion"이다.

**조직 — sb-ai-lab**

Sber AI Lab의 GitHub 조직이다 (구 계정 `sberbank-ai-lab`). 다른 대표 프로젝트:

- **LightAutoML (LAMA)** — AutoML 프레임워크, 조직 대표작
- **RePlay** — 추천 시스템
- **Eco2AI** — 학습 시 전력/탄소 추적

즉 EmotiEffLib은 개인 연구(HSEmotion)가 Sber AI Lab 조직 저장소로
이관·리브랜딩된 형태다.

### 1.2 언제 만들어졌나

| 시기 | 내용 |
|---|---|
| **2021** | HSEmotion 원 저장소 공개 (`av-savchenko/face-emotion-recognition`). EfficientNet-B0/B2 기반 모델 가중치 — **현재 쓰는 모델의 실체가 이때 것** |
| 2022.03 | CVPR 2022 ABAW 워크샵 논문 (arXiv:2203.13436) |
| 2022.07 | IEEE Trans. Affective Computing 논문 |
| 2022.10 | *HSEmotion: High-speed emotion recognition library* (Software Impacts) |
| 2023.07 | **ICML 2023 Oral** (Adaptive Frame Rate) |
| 2023 / 2024 | CVPR Workshops — EmotiEffNets, TCN 확장 |
| **2025.02.24** | **EmotiEffLib 1.0** — sb-ai-lab로 이관, 리브랜딩, PyPI 정식 배포 |
| 2025.09.10 | **1.1.1** — 현재 프로젝트가 쓰는 버전 |
| 2026 | ABAW-10 입상 (Violence Detection 1위, Expression Recognition 2위) |

정리하면 **모델 가중치는 2021~2023년, 라이브러리 패키징은 2025년**이다.
Python/C++ 통합, ONNX 백엔드, 문서화가 2025년에 정리됐다.

참고로 음성 쪽 emotion2vec은 논문이 2023년 12월, `emotion2vec+` 가중치가 2024년이므로
**얼굴 쪽이 2~3년 더 오래된 기술**이다. 다만 아래 설명대로 이 격차가 성능 차이로
이어지지는 않는다.

### 1.3 신뢰할 만한가

이 분야에선 확실한 트랙 레코드다.

- **ABAW** — CVPR/ECCV 워크샵으로 열리는 감정인식 최대 규모 대회.
  HSEmotion 팀이 3회차부터 10회차까지 거의 매년 입상
- ICML 2023 Oral, CVPR Workshops 다수
- Apache-2.0 — 상업적 사용 제한 없음 (emotion2vec과 유사한 라이선스 성격)

**감안할 점** — 유지보수가 소수 인원에 의존하는 학술 라이브러리라, 대기업 프로덕션
SDK 수준의 안정성·지원을 기대하긴 어렵다. 다만 모델 가중치가 저장소에 직접 들어있고
추론 코드가 단순해서, 라이브러리 유지보수가 멈춰도 ONNX 파일만 들고 직접 돌릴 수 있다.

---

**한 가지 감안할 점** — 모델 가중치 자체는 2021~2023년 것이다. 다만 FER 분야는
AffectNet 정확도가 몇 년째 60%대 초반에서 정체되어 있어(사람이 라벨링해도 일치율이
60~70%대라 데이터셋 천장이 낮다), 2025년 SOTA와의 격차가 1%p 미만이다.
"오래됐다"기보다 "이 분야가 그 사이 별로 안 움직였다"고 보는 게 맞다.

### 모델 선택

| 모델 | AffectNet-8 | 크기 | ONNX 제공 |
|---|---|---|---|
| `enet_b0_8_best_afew` | 60.95 | 16MB | O |
| `enet_b0_8_best_vgaf` | 61.32 | 16MB | O ← **현재 사용** |
| `enet_b0_8_va_mtl` | 61.93 | 16MB | O |
| `enet_b2_8_best` | **63.13** | 30MB | **X (.pt만)** |

`enet_b2_8_best`가 가장 정확하지만 저장소에 ONNX 파일이 없어 404가 난다.
`fer_check.py`는 실패 시 자동으로 `enet_b0_8_best_vgaf`로 폴백한다.
정확도 차이 1.8%p는 실사용에서 무시할 수준이다.

---

## 2. 파이프라인

emotion2vec은 wav 파일 하나를 넣으면 끝이지만, FER은 **영상을 이미지로 쪼개는
전처리**가 필요하다.

```
영상 (mp4/mov, 20초)
   │
   ├─ [1] 프레임 추출          cv2.VideoCapture
   │      30fps 원본 → 3fps 샘플링 → 60장
   │
   ├─ [2] 얼굴 검출 + crop     MediaPipe FaceDetection
   │      1080x1920 원본에서 얼굴 위치를 찾아 잘라냄
   │      (FER 모델은 얼굴만 꽉 찬 이미지를 입력으로 받는다)
   │
   ├─ [3] 감정 추론            EmotiEffLib (프레임마다 독립 실행)
   │      → 8개 감정의 확률 벡터 × 60장
   │
   └─ [4] 집계                 60장의 스코어를 하나로 합침
          → 턴 하나의 감정 벡터
```

### 왜 얼굴 검출이 따로 필요한가

FER 모델의 입력은 **얼굴만 꽉 찬 정사각 이미지**다. 폰으로 찍은 1080x1920 원본에는
배경·상체·벽지가 다 들어있어서 그대로 넣으면 결과가 의미 없다.
음성 파이프라인에서 `webm → wav` 변환이 필요한 것과 같은 위치의 필수 전처리다.

MediaPipe를 쓰는 이유는 CPU에서 프레임당 5~10ms로 빠르고 **GPU 메모리를 안 먹기**
때문이다. 8GB GPU에 SenseVoice + emotion2vec이 이미 올라가 있는 상황에 적합하다.

### 집계 방식 3가지

`fer_check.py`는 세 방식을 모두 계산해 비교할 수 있게 한다.

| 방식 | 계산 | 의미 |
|---|---|---|
| **전체 평균** | 60장 전부 평균 | "평균적으로 얼마나" |
| **상위 30% 평균** | 감정별로 점수 상위 18장만 평균 후 정규화 | "가장 강했을 때 얼마나" |
| **neutral 제외** | neutral을 0으로 두고 재정규화 | "무표정 빼고 감정끼리만 비교하면" |

`granularity="utterance"`를 준 emotion2vec이 내부적으로 프레임 임베딩을 평균내는
것과 같은 개념이다. FER은 이 단계를 라이브러리가 대신 해주지 않을 뿐이다.

**전체 평균의 함정** — 대화 중엔 대부분의 순간이 무표정이라, 잠깐 스친 표정이
나머지 프레임에 희석된다. 예를 들어 60장 중 3장에서만 sad가 0.6대로 튀어도
전체 평균은 0.2 아래로 내려간다. 그래서 상위 30% 평균을 같이 본다.

---

## 3. 환경 세팅

### 딸깍 설치 (권장)

```powershell
cd C:\moong-care
.venv\Scripts\activate
.\scripts\install_fer.bat
```

> PowerShell에서는 앞에 `.\`를 반드시 붙여야 한다. 없으면
> `'install_fer.bat' 용어가 cmdlet, 함수, 스크립트 파일 또는 실행할 수 있는
> 프로그램 이름으로 인식되지 않습니다` 오류가 난다.
> 파일이 `scripts\` 안에 있으므로 경로도 같이 적어야 한다.

가상환경 확인 → 설치 → 버전 검증까지 한 번에 한다.
numpy나 OpenCV 버전이 잘못되면 그 자리에서 잡아준다.

`.bat`은 얇은 래퍼일 뿐이고 실제 로직은 `scripts/install_fer.py`에 있다.
(cmd.exe가 배치 파일을 시스템 코드페이지로 파싱해서, `.bat` 안에 UTF-8 한글이
있으면 명령어 파싱 자체가 깨진다. 그래서 `.bat`은 ASCII만 유지한다.)

파이썬으로 직접 실행해도 동일하다.

```powershell
python scripts/install_fer.py
```

### 수동 설치

```powershell
pip install -r requirements-fer.txt
```

### 설치 후 확인

```powershell
python -c "import numpy, cv2, onnxruntime, mediapipe; print(numpy.__version__, cv2.__version__)"
```

`1.26.4 4.11.0` 처럼 **numpy는 1.x, opencv는 4.x**가 나와야 한다.

### 검증된 조합

| 패키지 | 버전 |
|---|---|
| Python | 3.10 |
| emotiefflib | 1.1.1 |
| mediapipe | 0.10.14 |
| opencv-python | 4.11.0.86 |
| opencv-contrib-python | 4.11.0.86 |
| onnxruntime | 1.18.0 |
| numpy | 1.26.4 |

---

## 4. 트러블슈팅

도입 과정에서 실제로 겪은 문제들이다. `requirements-fer.txt`의 버전 상한은
전부 이 사고들을 막기 위한 것이므로 임의로 풀지 말 것.

### `'install_fer.bat' 용어가 ... 인식되지 않습니다`

PowerShell은 보안상 현재 디렉터리의 실행 파일을 자동으로 찾지 않는다.
`.\`를 붙이고, `scripts\` 경로도 같이 적는다.

```powershell
.\scripts\install_fer.bat
```

### `AttributeError: _ARRAY_API not found` / `numpy 1.x cannot be run in NumPy 2.x`

FER 패키지를 설치하면서 pip이 **numpy를 2.x로 올려버린** 경우.
`torch 2.3.1`과 `onnxruntime 1.18.0`이 numpy 1.x로 컴파일돼 있어서 깨진다.
**FER뿐 아니라 STT/SER까지 전부 죽는다.**

```powershell
pip install "numpy<2"
```

### `opencv-python 5.x requires numpy>=2`

OpenCV 5.x가 numpy 2를 요구해서 위 제약과 충돌한다. 4.x로 내린다.

```powershell
pip install "opencv-python<5" "opencv-contrib-python<5" "numpy<2"
```

`opencv-contrib-python`도 같이 내려야 한다. mediapipe가 끌어오기 때문이다.

### `module 'mediapipe' has no attribute 'solutions'`

mediapipe 0.11 이후 `mp.solutions` 레거시 API가 제거됐다.

```powershell
pip install "mediapipe==0.10.14"
```

### `HTTP Error 404` (모델 다운로드 실패)

`enet_b2_8_best`의 ONNX 파일이 저장소에 없어서 발생한다.
스크립트가 자동으로 `enet_b0_8_best_vgaf`로 폴백하므로 무시해도 된다.
404 로그조차 보기 싫으면 모델을 명시한다.

```powershell
python scripts/fer_check.py temp/test1.mp4 --model enet_b0_8_best_vgaf
```

사용 가능한 모델 목록은:

```powershell
python scripts/fer_check.py --list-models x
```

### `Looks like torch module is not installed`

`--engine torch`를 쓸 때 나온다. 실제로는 torch가 아니라 **torchvision**이 없어서다
(`requirements.txt`에 torch, torchaudio만 있다).
기본값인 ONNX 엔진을 쓰면 torchvision이 필요 없으므로 신경 쓸 것 없다.

---

## 5. 테스트 방법

영상에서는 **얼굴만 사용한다** (음성은 안 본다). 그래도 자연스러운 표정이 나오도록
실제로 말을 하면서 찍는 것이 좋다.

### 촬영

- 각 **10~15초**, 폰을 **눈높이**에 세우고 정면
- 얼굴이 화면의 **1/3 이상**
- 밝은 곳, 역광 피하기
- 안경 김서림 / 마스크 / 앞머리로 눈 가리기 주의

| 파일 | 내용 | 목적 |
|---|---|---|
| `temp/normal.mp4` | 무표정하게 오늘 한 일 말하기 | 기준선 |
| `temp/happy.mp4` | 실제로 좋았던 일 떠올리며 | 긍정 감정 |
| `temp/sad.mp4` | 속상했던 일 | 부정 감정 |
| `temp/exaggerated.mp4` | 웃음 → 찡그림 → 놀람 크게 | 모델 정상 동작 확인 |

### 실행

```powershell
python scripts/fer_check.py temp/normal.mp4 --fps 5
```

주요 옵션:

| 옵션 | 기본값 | 설명 |
|---|---|---|
| `--fps` | 3 | 초당 추출 프레임 수. 20초 영상 × 3 = 60장 |
| `--model` | `enet_b2_8_best` | 실패 시 자동 폴백 |
| `--engine` | `onnx` | `torch`도 가능 (torchvision 필요) |
| `--rotate` | 0 | 폰 세로 영상이 눕혀 나올 때 90/180/270 |
| `--max-frames` | 200 | 상한 |
| `--json` | - | 프레임별 원시 스코어 저장 |

**세로로 찍었는데 얼굴 검출이 줄줄이 실패하면** `--rotate 90`을 의심할 것.
폰 영상은 회전 메타데이터가 있는데 OpenCV가 이를 무시하는 경우가 흔하다.

### 판정 기준

`exaggerated.mp4`가 가장 중요하다.

- 과장했는데도 neutral만 나온다 → 모델/설정 문제
- 과장은 잡히는데 나머지가 전부 neutral → 모델은 정상, 실제 대화 표정이 너무 미묘한 것

---

## 6. 실제 테스트 결과 (2026-08)

**촬영 내용**: 무표정 → 행복 → 찡그림 → 무표정 (8초, 25프레임)
**모델**: `enet_b0_8_best_vgaf` (onnx)

### 프레임별 타임라인

```
t= 0.00s  Sadness   0.563   Neutral  0.276     ┐ 무표정
t= 0.34s  Sadness   0.505   Neutral  0.320     ┘
t= 0.67s  Happiness 0.792   Disgust  0.076     ┐
t= 1.01s  Happiness 0.779   Fear     0.091     │
t= 1.34s  Happiness 0.953   Disgust  0.027     │
t= 1.68s  Happiness 0.994   Surprise 0.003     │ 행복
t= 2.01s  Happiness 0.974   Surprise 0.007     │
t= 2.35s  Happiness 0.961   Surprise 0.020     │
t= 2.68s  Happiness 0.989   Surprise 0.006     │
t= 3.02s  Happiness 0.987   Surprise 0.007     │
t= 3.35s  Happiness 0.988   Surprise 0.006     ┘
t= 3.69s  Sadness   0.843   Neutral  0.081     ┐
t= 4.02s  Neutral   0.471   Sadness  0.280     │
t= 4.36s  Neutral   0.412   Sadness  0.403     │ 전환
t= 4.69s  Neutral   0.520   Sadness  0.291     │
t= 5.03s  Neutral   0.480   Sadness  0.308     │
t= 5.36s  Sadness   0.524   Neutral  0.328     ┘
t= 5.70s  Fear      0.531   Disgust  0.254     ┐
t= 6.03s  Fear      0.602   Disgust  0.132     │
t= 6.37s  Fear      0.680   Anger    0.146     │ 찡그림
t= 6.70s  Fear      0.703   Anger    0.137     │
t= 7.04s  Fear      0.666   Anger    0.162     │
t= 7.37s  Fear      0.656   Anger    0.137     ┘
t= 7.71s  Sadness   0.693   Neutral  0.219     ┐ 무표정
t= 8.04s  Sadness   0.491   Neutral  0.364     ┘
```

### 집계 결과

| 감정 | 전체 평균 | 상위 30% | neutral 제외 |
|---|---|---|---|
| Happiness | 0.339 | 0.341 | 0.394 |
| Sadness | 0.205 | 0.200 | 0.238 |
| Fear | 0.172 | 0.195 | 0.200 |
| Neutral | 0.140 | 0.144 | 0.000 |
| Anger | 0.060 | 0.050 | 0.070 |
| Surprise | 0.043 | 0.028 | 0.050 |
| Disgust | 0.039 | 0.040 | 0.045 |
| Contempt | 0.003 | 0.002 | 0.003 |

### 진단

```
1) 얼굴 검출 성공 25/25  (실패율 0%)      [양호]
2) neutral 평균 0.140                     [양호] 감정이 분산되어 잡힘
3) 프레임 간 최상위 감정 변동률 25%       [양호] 예측이 일관적
4) 최종 판정: Happiness 0.339
```

### 해석

**잘 된 점**

- 촬영 순서(무표정→행복→찡그림→무표정)와 타임라인이 정확히 일치한다
- 행복 구간에서 0.99까지 올라간다. 확신이 매우 강하다는 뜻
- 찡그림이 Fear(2위 Anger)로 나온 것은 타당하다. AffectNet에서 찡그림은
  anger/disgust/fear 경계에 걸쳐 있다
- 얼굴 검출 실패 0건. 전처리가 안정적이다

**우려했던 문제는 발생하지 않음**

도입 전 가장 걱정했던 것은 "실제 대화에선 대부분 무표정이라 neutral로 쏠려
신호가 안 잡힐 것"이었다. 실측 neutral 평균은 0.140으로 오히려 낮았다.

**대신 반대 문제가 발견됨** → [7. 알려진 한계](#7-알려진-한계)

---

## 7. 알려진 한계

### 무표정이 Sadness로 읽힌다 ⚠️

가장 중요한 이슈다. 위 테스트에서 **무표정 구간(0.0~0.3s, 7.7~8.0s)이
Neutral이 아니라 Sadness 0.5로 판정**됐다.

실서비스에서는 대화 시간의 대부분이 무표정이다. 이게 계속 sad로 새면
일기가 "오늘 슬펐다"로 왜곡된다.

**원인 추정** — AffectNet의 서구권 얼굴 편향, 그리고 연출된 표정 위주로 수집된
데이터셋 특성. 동아시아권의 평상시 표정이 상대적으로 낮은 각성도로 해석되는
경향이 보고된 바 있다.

**대응 방안 (통합 시 적용)**

1. Sadness에 임계값을 걸어 0.6 미만이면 Neutral로 보정
2. 사용자별 기준선 캘리브레이션 — 첫 세션에서 무표정 영상을 받아 편향을 측정하고 차감
3. 음성 감정에 더 큰 가중치를 주고, 얼굴은 보조 신호로만 사용

### 그 외

- **AffectNet 자체의 천장** — 8-class 정확도가 60%대 초반이다. 사람이 라벨링해도
  일치율이 60~70%대라 절대적 신뢰는 어렵다
- **얼굴 미검출 구간** — 이번 테스트에선 0%였지만, 실사용에서는 화면 밖·어두움·
  각도 문제로 실패가 발생한다. 그 턴은 음성만 사용하는 fallback이 필요하다
- **Contempt 라벨 대응 없음** — emotion2vec에는 contempt가 없어 `other`로 매핑한다.
  다행히 실측값이 0.003으로 무시할 수준이다

---

## 8. emotion2vec과의 호환성

FER 라벨(8종)과 emotion2vec 라벨(9종)이 거의 1:1로 대응한다.
**융합 시 라벨 재설계가 거의 필요 없다는 뜻**이다.

| EmotiEffLib | → | `EMOTION_CLASSES` | 비고 |
|---|---|---|---|
| Anger | → | `angry` | |
| Disgust | → | `disgusted` | |
| Fear | → | `fearful` | |
| Happiness | → | `happy` | |
| Neutral | → | `neutral` | |
| Sadness | → | `sad` | |
| Surprise | → | `surprised` | |
| Contempt | → | `other` | emotion2vec에 대응 라벨 없음 |
| (없음) | | `unknown` | 얼굴 미검출 시 사용 |

구조도 맞는다. 양쪽 다 **감정별 확률 벡터**를 내므로
`services/emotion_session.py`의 `emotion_sums` 누적 로직을 그대로 쓸 수 있다.

| | emotion2vec (음성) | EmotiEffLib (표정) |
|---|---|---|
| 입력 | wav 파일 | 얼굴 crop 이미지 |
| 출력 | `dict[str, float]` | `dict[str, float]` |
| 클래스 수 | 9 | 8 |
| 단위 | 발화 하나 | 프레임 하나 → 집계 필요 |

---

## 9. 다음 단계 (통합 계획)

아직 서버에 붙이지 않았다. 붙일 때의 계획은 다음과 같다.

### 9.1 `services/fer_service.py` 신설

`ser_service.py`와 **같은 시그니처**로 맞춘다.

```python
def analyze_face_emotion(model, video_path: str) -> dict[str, float]:
    ...
```

`fer_check.py`의 `extract_frames` / `FaceCropper` / `EmotionScorer`를 옮겨오되,
진단·출력 코드는 제외한다.

### 9.2 모델 싱글톤 로딩

`main.py`의 `lifespan`에서 STT/SER과 함께 한 번만 올린다.

```python
app.state.fer_model = EmotiEffLibRecognizer(engine="onnx", model_name="enet_b0_8_best_vgaf")
app.state.fer_lock = asyncio.Lock()
```

### 9.3 `voice_service` 병렬 실행에 추가

현재 `STT ‖ SER ‖ pitch`를 병렬로 돌리고 있으므로 FER을 네 번째 태스크로 넣는다.
wall-clock은 `max()`이고 SenseVoice가 1~2초 걸리므로 **체감 지연 증가는 거의 없다**.

예상 소요 (5초 영상, 15프레임):

| 단계 | 시간 |
|---|---|
| ffmpeg 프레임 추출 | 0.1~0.3초 |
| 얼굴 검출 15장 | 0.3~0.5초 |
| FER 추론 (배치) | 0.05초 |
| **합계** | **0.5~1초** |

### 9.4 late fusion

```python
fused = w_voice * voice_emotions + w_face * face_emotions
```

`w_voice=0.6, w_face=0.4`에서 시작해 튜닝한다.
음성 감정이 얼굴보다 신뢰도가 높고, 위 [7절]의 Sadness 편향을 감안한 배분이다.

### 9.5 반드시 처리할 것

- 얼굴 미검출 턴 → 음성만으로 fallback
- Sadness 임계값 보정
- 클라이언트에서 영상 해상도를 480p로 낮춰 전송 (업로드 지연이 추론보다 클 수 있음)

---

## 참고 자료

- [EmotiEffLib GitHub](https://github.com/sb-ai-lab/EmotiEffLib)
- [EmotiEffLib 문서](https://sb-ai-lab.github.io/EmotiEffLib/)
- [영상 감정 인식 튜토리얼 (Colab)](https://github.com/sb-ai-lab/EmotiEffLib/blob/main/docs/tutorials/python/Predict%20emotions%20on%20video.ipynb)
- Savchenko, A. — *Facial Expression Recognition with Adaptive Frame Rate based on
  Multiple Testing Correction*, ICML 2023 Oral —
  [PMLR](https://proceedings.mlr.press/v202/savchenko23a.html)
  (프레임 샘플링 주기를 통계적으로 정하는 방법. `--fps` 튜닝 시 참고)
- Savchenko, A.V. et al. — *Classifying emotions and engagement in online learning
  based on a single facial expression recognition neural network*,
  IEEE Trans. Affective Computing 2022 —
  [IEEE](https://ieeexplore.ieee.org/document/9815154)
