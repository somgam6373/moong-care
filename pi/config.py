"""라즈베리파이 클라이언트 설정.

값은 환경변수로 덮어쓸 수 있습니다. (예: MOONG_SERVER=http://192.168.0.10:8000)
"""

import os
import socket
from pathlib import Path


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


_PI_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- 서버
SERVER_BASE = _env("MOONG_SERVER", "http://192.168.0.10:8000").rstrip("/")
SESSION_ID = _env("MOONG_SESSION_ID", f"pi-{socket.gethostname()}")
CHAT_STYLE = _env("MOONG_STYLE", "empathetic")   # empathetic | realistic
TTS_VOICE = _env("MOONG_VOICE", "nova")

# /api/v1/care/turn 하나가 STT+감정분류+GPT답변+TTS 를 전부 처리하므로 넉넉히 잡는다.
# (연결, 응답) 초 단위
TIMEOUT_TURN = (5, 120)

# ---------------------------------------------------------------- GPIO
BUTTON_PIN = int(_env("MOONG_BUTTON_PIN", "17"))   # 물리 11번 핀 = BCM 17, 반대쪽은 GND
BUTTON_BOUNCE_S = 0.08                            # 채터링 제거

# ---------------------------------------------------------------- LED
LED_COUNT = 24
LED_PIN = 12             # 물리 32번 핀 = BCM 12 = PWM0 (channel 0)
LED_FREQ_HZ = 800_000
LED_DMA = 10
LED_INVERT = False
LED_CHANNEL = 0
LED_MAX_BRIGHTNESS = 255   # 전역 상한. 눈부시면 128 정도로 낮추세요
LED_FPS = 60

# 파이 5는 rpi_ws281x 파이썬 패키지가 RP1 칩을 지원하지 않아 런타임에
# HW_NOT_SUPPORTED 로 실패한다. 그래서 상주 C 프로세스(led_bridge)에 매 프레임
# 색상을 흘려보내는 방식을 쓴다. 이 바이너리가 있으면 무조건 이걸 쓰고,
# 없으면(PC 개발 중이거나 아직 빌드 전) 콘솔 목업으로 대체된다.
WS281X_DIR = _env("MOONG_WS281X_DIR", str(Path.home() / "rpi_ws281x"))
LED_BRIDGE_BIN = _env("MOONG_LED_BRIDGE", os.path.join(_PI_DIR, "led_bridge", "led_bridge"))
LED_SETUP_SCRIPT = os.path.join(_PI_DIR, "led_setup.sh")

# ---------------------------------------------------------------- 오디오
SAMPLE_RATE = 48_000
CHANNELS = 1
_input_device_raw = os.environ.get("MOONG_INPUT_DEVICE")
INPUT_DEVICE = int(_input_device_raw) if _input_device_raw is not None and _input_device_raw.isdigit() else _input_device_raw
OUTPUT_DEVICE = os.environ.get("MOONG_OUTPUT_DEVICE")  # aplay -D 에 들어갈 이름

MIN_RECORD_S = 0.6      # 이보다 짧으면 오녹음으로 보고 버림
MAX_RECORD_S = 30.0     # 버튼을 안 눌러도 이 시간이 지나면 자동 종료

RECORD_PATH = "/tmp/moong_input.wav"
REPLY_PATH = "/tmp/moong_reply.wav"

# ---------------------------------------------------------------- 자장가 / 취침
# 이 이상 누르고 있으면(짧은 tap이 아니라 꾹 누르기) 대화를 끝내고 자장가 모드로 들어간다.
LONG_PRESS_S = float(_env("MOONG_LONG_PRESS_S", "1.2"))

# /api/v1/session/end 호출 타임아웃. (연결, 응답) 초 단위
TIMEOUT_SESSION_END = (5, 15)

# 자장가 파일. mp3 등 다른 포맷이면 aplay가 못 읽으므로 wav로 미리 변환해서 넣어야 한다.
#   ffmpeg -i lullaby.mp3 -ar 44100 -ac 2 pi/media/lullaby.wav
LULLABY_PATH = _env("MOONG_LULLABY", os.path.join(_PI_DIR, "media", "lullaby.wav"))

# 자장가 모드 진입 시 /session/end 호출이 실패하면 이 색으로 대체한다 (warm_dim과 동일).
DEFAULT_SLEEP_COLOR = {"hex": "#C9785A", "brightness": 0.16, "transition_ms": 6000}
