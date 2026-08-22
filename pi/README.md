# moong-care · Raspberry Pi 클라이언트

택트 스위치 1개 → 녹음 → 서버 1회 호출(`/api/v1/care/turn`) → 답변 재생.
24구 WS2812 링(눕혀놓고 확산 커버 씌움)이 각 단계를 색으로 알려줍니다.

색과 애니메이션을 실제로 보려면 `pi/led-preview.html` 을 브라우저로 여세요.
설계 배경과 전체 파이프라인은 `pi/PLAN.md` 참고.

## 흐름

```
READY ──짧게──▶ RECORDING ──짧게(or 30초)──▶ PROCESSING ──▶ SPEAKING ──재생끝──▶ READY
무지개 회전       음량 연동 밝기               무지개 빠른 회전    care_color 호흡
(8초/바퀴)                                  (0.55초/바퀴)      (표의 14색)

READY(또는 대화 중 아무 때나) ──꾹 누름(1.2초+)──▶ SLEEPING ──아무 버튼──▶ READY(새 세션)
                                    수면색 호흡 + 자장가 반복 재생
```

버튼 하나로 "짧게"와 "꾹"을 구분합니다. 뗄 때(release) 눌려있던 시간을 재서
`MOONG_LONG_PRESS_S`(기본 1.2초) 이상이면 취침, 아니면 평소 대화 버튼입니다.
자장가 재생 중에는 짧게든 꾹이든 아무 버튼이나 누르면 바로 깨어나 **새 session_id**로
대화를 다시 시작합니다 (지난 대화 맥락과 섞이지 않도록).

## 서버 API — 두 개

```
POST /api/v1/care/turn
```

| 필드 | 필수 | 설명 |
|---|---|---|
| `audio` | O | 16kHz mono wav. 파이가 항상 이 형식으로 녹음하므로 서버에서 변환이 생략됨 |
| `session_id` | O | 부팅 시 만든 값을 계속 재사용 (대화 맥락 유지) |
| `style` | X | `empathetic`(기본) / `realistic` |
| `voice` | X | 기본 `nova` |

**응답**: 본문 = 답변 wav 바이너리. 헤더에 감정/색/전사/답변텍스트/타이밍이 실려 옴
(`X-Care-Emotion`, `X-Care-Hex`, `X-Care-Brightness`, `X-Care-Transition-Ms`,
`X-Transcript`, `X-Reply-Text`, `X-Timing` 등. 한글은 percent-encoding 되어 있어
`server_client.py` 가 자동으로 풀어줍니다).

서버가 STT → 9→14 감정분류(GPT) → 답변생성 → TTS 를 전부 처리하고 한 번에 돌려줍니다.
**폴링은 필요 없습니다.** `requests.post()` 가 서버 처리가 끝날 때까지 기다렸다가
결과를 리턴값으로 주기 때문입니다. 파이에 서버를 띄울 필요도 없습니다.

```
POST /api/v1/session/end
```

버튼을 꾹 눌러 대화를 끝낼 때 1번 호출합니다. `{"session_id": "..."}` 를 보내면
그 세션 동안 나온 케어 감정 중 **confidence로 가중 합산해서 가장 점수가 높았던 감정
하나**에 대응하는 수면색(`sleep_color`)을 돌려줍니다 (`services/sleep_color_service.py`
의 `warm_dim` / `deep_amber` / `soft_peach` / `low_rose` 4색 중 하나, 실시간 14색보다
훨씬 어둡고 전환이 느림). 이 색을 자장가 재생 중 LED에 씁니다.

## care_emotion 매핑

**파이는 이 로직을 갖고 있지 않습니다.** 9개 → 14개 변환은 서버의
`services/emotion_classifier_service.py`(GPT 기반) + `services/color_care_service.py`(색상표)
가 전담합니다. 파이는 응답 헤더로 받은 색을 그대로 LED에 씌우기만 합니다.
표가 바뀌면 서버만 고치면 됩니다.

## 파일 구성

```
pi/
├── main.py             상태머신. 버튼 → 녹음 → /care/turn → 재생 루프
├── led_controller.py   WS2812 렌더러. 별도 스레드 60fps, 눕힘+커버 기준 설계
├── led_bridge/
│   ├── led_bridge.c    상주 C 프로세스. libws2811.a(pi5 브랜치)를 직접 링크
│   └── build.sh        빌드 스크립트 (인자나 WS281X_DIR 로 클론 경로 지정)
├── led_setup.sh        RP1 PWM 커널모듈+dtoverlay+pinctl (led_controller.py가 자동 호출)
├── server_client.py    /care/turn, /session/end 호출 + 헤더 파싱/한글 디코딩
├── audio_io.py         sounddevice 녹음(+음량) / aplay 재생 / 자장가 반복 재생(LullabyPlayer)
├── media/lullaby.wav   자장가 음원 (직접 넣어야 함, 아래 "자장가" 섹션 참고)
├── config.py            서버주소 · 핀번호 · 타임아웃 · led_bridge 경로 · 자장가 경로
├── led-preview.html    LED 색·애니메이션 브라우저 미리보기 (실제 계산식과 동일)
├── PLAN.md              전체 설계 문서 (파이프라인 · API · LED 근거)
└── requirements.txt
```

## LED — 파이 5는 rpi_ws281x 파이썬 패키지가 안 됩니다

**원인**: 파이 5는 GPIO 칩이 RP1으로 바뀌어서, PWM/DMA 레지스터를 직접 건드리는
`rpi_ws281x` 방식이 런타임에 `ws2811_init failed (code -3, HW_NOT_SUPPORTED)` 로 실패합니다.
`pip install` 자체는 성공하지만(그래서 import 성공 여부로는 구분이 안 됨) 실제
초기화 시점에 죽습니다.

**해결**: `jgarff/rpi_ws281x` 저장소의 `pi5` 브랜치가 RP1용 커널 모듈
(`rp1_ws281x_pwm.ko`)을 제공합니다. 이 프로젝트는 그 브랜치를 클론+빌드해서 나온
`libws2811.a` 를 **파이썬 바인딩 없이 C 레벨에서 직접** 씁니다.

```
led_controller.py (애니메이션 계산, 60fps 스레드)
        │  매 프레임 "r,g,b,r,g,b,..." 한 줄을 stdin으로 전송
        ▼
led_bridge  (C, 상주 프로세스, libws2811.a 직접 링크)
        │  ws2811_render()
        ▼
       LED
```

`led_bridge` 바이너리가 있으면 무조건 그걸 쓰고, 없으면(PC 개발 중) 콘솔 목업으로
자동 전환됩니다 — `led_controller.py` 의 애니메이션 로직은 어느 쪽이든 그대로입니다.

### led_bridge 빌드

`rpi_ws281x` 의 `pi5` 브랜치를 이미 클론·빌드해서 `libws2811.a` 를 갖고 계셔야 합니다
(안 하셨으면 [pi5 브랜치 위키](https://github.com/jgarff/rpi_ws281x/wiki/Raspberry-Pi-5-Support) 참고).

```bash
cd ~/moong-care-pi/led_bridge
chmod +x build.sh
./build.sh                    # 기본값: ~/rpi_ws281x 에서 libws2811.a 찾음
# 다른 경로면: ./build.sh /그경로
```

`led_bridge` 실행파일이 생기면 끝입니다. `led_controller.py` 가 자동으로 찾아 씁니다.

### 커널 모듈은 재부팅마다 다시 로드해야 함

`led_setup.sh` 가 이 작업(`insmod` + `dtoverlay` + `pinctl`)을 자동으로 해줍니다.
`led_controller.py` 가 브릿지를 띄우기 직전에 알아서 호출하므로 평소엔 신경 안 써도
되지만, LED만 따로 테스트하고 싶을 땐 직접 돌려도 됩니다.

```bash
sudo bash led_setup.sh
```

경로가 `~/rpi_ws281x` 가 아니면 `MOONG_WS281X_DIR` 환경변수로 알려주세요.

## 배선

| | |
|---|---|
| WS2812 링 | 눕혀서 고정, 위에 확산 커버 |
| WS2812 DIN | **물리 32번 핀 (GPIO12)** |
| WS2812 5V / GND | **별도 5V 어댑터**, GND는 파이와 공통 연결 |
| 택트 스위치 | **물리 11번 핀 (BCM 17)** ↔ GND |
| 마이크 / 스피커 | USB |

24구 최대밝기는 약 1.4A입니다. 파이 5V 핀에서 끌어오면 전압강하로 재부팅됩니다.

## 설치 · 실행

```bash
sudo apt install -y alsa-utils python3-dev \
     portaudio19-dev libopenblas-dev

pip install -r requirements.txt   # rpi_ws281x 는 이제 안 씀 — led_bridge 로 대체

# led_bridge 빌드 (위 "LED" 섹션 참고, 최초 1회)
cd led_bridge && chmod +x build.sh && ./build.sh ~/rpi_ws281x && cd ..

# 서버 주소 확인 (PC에서 ipconfig)
export MOONG_SERVER=http://192.168.0.10:8000

python3 audio_io.py                  # 오디오 장치 목록 확인
sudo -E python3 led_controller.py    # 상태 5가지 + 감정색 3개 데모, 눈으로 확인
sudo -E python3 main.py              # 실행
```

C 브릿지가 하드웨어 레지스터를 직접 씁니다. `sudo -E` 를 빼면 `MOONG_SERVER` 같은
환경변수가 사라져 기본값(192.168.0.10)으로 붙습니다.

## LED 색 조정하는 법

1. `pi/led-preview.html` 을 컴퓨터에서 브라우저로 열고, 확산 강도 슬라이더를
   실제 커버에 맞게 움직여 보면서 값을 정한다
2. 정해진 숫자를 `led_controller.py` 맨 위 `STYLE` 딕셔너리에 반영한다
3. `sudo -E python3 led_controller.py` 로 실제 LED에서 확인한다

감정 14색(파스텔, 답변할 때 씀)은 파이에 없습니다 — 서버 `color_care_service.py`
에서 고치세요.

## 자장가

버튼을 1.2초 이상 꾹 누르면 대화가 끝나고 자장가 모드로 들어갑니다. 파일은
직접 구해서 `pi/media/lullaby.wav` 에 넣어야 합니다 (저작권 없는 음원 또는
직접 준비한 음원 — 클래식처럼 잔잔한 곡 추천). `aplay`는 wav만 재생하므로
mp3 등 다른 포맷이면 미리 변환하세요.

```bash
ffmpeg -i lullaby.mp3 -ar 44100 -ac 2 pi/media/lullaby.wav
```

- 곡이 끝까지 재생되면 버튼을 누를 때까지 처음부터 반복됩니다.
- 짧게든 꾹이든 아무 버튼이나 누르면 즉시 멈추고, **새 session_id**로 대화가 다시
  시작됩니다 (자기 전 대화 맥락이 다음 대화에 섞이지 않도록).
- LED는 `/session/end` 가 준 수면색으로 아주 느리게(6~8초 주기) 호흡합니다.
- 파일 경로나 길게 누르는 기준 시간은 환경변수로 바꿀 수 있습니다.

## 환경변수

| 변수 | 기본값 |
|---|---|
| `MOONG_SERVER` | `http://192.168.0.10:8000` |
| `MOONG_SESSION_ID` | `pi-<hostname>` |
| `MOONG_STYLE` | `empathetic` (또는 `realistic`) |
| `MOONG_VOICE` | `nova` |
| `MOONG_BUTTON_PIN` | `17` |
| `MOONG_LULLABY` | `pi/media/lullaby.wav` |
| `MOONG_LONG_PRESS_S` | `1.2` (이 이상 누르고 있어야 취침으로 인식) |
| `MOONG_INPUT_DEVICE` / `MOONG_OUTPUT_DEVICE` | 시스템 기본 |

## 자동 시작 (선택)

```ini
# /etc/systemd/system/moongcare.service
[Unit]
Description=moong-care pi client
After=network-online.target sound.target

[Service]
WorkingDirectory=/home/pi/moong-care/pi
Environment=MOONG_SERVER=http://192.168.0.10:8000
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now moongcare
journalctl -u moongcare -f
```

## 자주 겪는 것

| 증상 | 원인 |
|---|---|
| `ws2811_init failed (code -3)` | 파이 5에서 `rpi_ws281x` 파이썬 패키지를 직접 씀 → 이 프로젝트는 `led_bridge` C 브릿지로 우회함, 위 "LED" 섹션 참고 |
| `[led] mock driver (led_bridge 없음)` 이 뜸 | `led_bridge` 를 아직 빌드 안 함 → `cd led_bridge && make` |
| `led_setup.sh 실패` | 커널 모듈(`rp1_ws281x_pwm.ko`)을 못 찾음 → `MOONG_WS281X_DIR` 로 클론 경로 지정 |
| LED가 안 켜짐 | `sudo` 없이 실행 / 아날로그 오디오가 PWM을 점유 → `dtparam=audio=off` |
| 재부팅이 걸림 | LED를 파이 5V에서 끌어옴 → 별도 어댑터 |
| `/care/turn` 이 500 | 서버 PC에 ffmpeg 없음, 또는 GPT 호출 실패 (`.env`의 `OPENAI_API_KEY` 확인) |
| 연결 안 됨 | PC 방화벽에서 8000 인바운드 허용 필요 |
| 전사가 빈 문자열 | 마이크 게인 부족 → `alsamixer`에서 Capture 올리기 |
| 자장가가 안 나옴 / `[audio] 자장가 파일을 못 찾음` | `pi/media/lullaby.wav` 가 없음 → 파일을 넣거나 `MOONG_LULLABY` 로 경로 지정 |
| 꾹 눌렀는데 대화(RECORDING)로 들어감 | `MOONG_LONG_PRESS_S`(기본 1.2초)보다 짧게 눌렀다 뗌 → 더 오래 누르기 |
| 응답이 너무 느림 | 서버 로그의 `X-Timing` 헤더로 어느 단계가 오래 걸리는지 확인 |
