"""WS2812 24구 링 상태 표시 — 눕혀놓고 위에 확산 커버를 씌운 상태 기준.

커버를 씌우면 개별 픽셀이 뭉개져 하나의 빛 덩어리로 보이고, 위아래 방향성도
사라집니다. 그래서 커버 밑에서도 확실히 살아남는 세 가지 — 전체 밝기, 색,
굵은 덩어리의 회전 — 만으로 설계했습니다. (자세한 근거는 pi/led-preview.html 참고.
이 파일의 render 함수들은 그 미리보기와 동일한 계산식입니다.)

구분 규칙
    회전 있음 + 채도 최대       =  기계의 상태
    회전 없음 + 파스텔 단색 호흡 =  사람의 감정 (표의 14색, 서버가 알려줌)

상태 정의
    boot        부팅 확인용 1회 무지개 스윕
    ready       질문해도 된다  : 무지개 전체가 8초에 한 바퀴, 아주 느리게
    recording   녹음 중        : 전체 밝기가 목소리 크기를 그대로 따라감 (앰버~주황빨강)
    processing  계산 중        : 무지개 전체가 0.55초에 한 바퀴, 밝기 파동과 함께 빠르게
    speaking    답변 중        : care_color 로 회전 없이 제자리 호흡 (표의 14색 중 하나)
    error       오류           : 빨강 ↔ 흰색 교차 깜빡임
"""

from __future__ import annotations

import colorsys
import math
import os
import stat
import subprocess
import threading
import time

import config

# ---------------------------------------------------------------------------
# 드라이버
#
# 파이 5는 rpi_ws281x 파이썬 패키지의 PWM/DMA 직접 접근 방식을 RP1 칩이
# 지원하지 않는다 (ws2811_init 이 런타임에 HW_NOT_SUPPORTED 로 실패).
# 그래서 파이썬 바인딩은 아예 쓰지 않고, 이미 검증된 C 라이브러리(libws2811.a,
# rpi_ws281x 의 pi5 브랜치)를 링크해서 만든 상주 프로세스(led_bridge)에
# 매 프레임 24픽셀 RGB 값을 stdin으로 흘려보내는 방식을 쓴다.
#
#   led_bridge 바이너리가 있으면        -> C 브릿지 사용 (실제 하드웨어)
#   없으면 (PC 개발 중 / 아직 빌드 전)  -> 콘솔 목업
#
# 둘 다 아래 3개 메서드(begin/numPixels/setPixelColor/show)만 구현하면 되므로
# 애니메이션 로직(STYLE, _ready/_recording/... 등)은 어느 쪽을 쓰든 그대로다.
# ---------------------------------------------------------------------------


def Color(r, g, b):
    return (int(r) << 16) | (int(g) << 8) | int(b)


def _is_executable(path: str) -> bool:
    try:
        st = os.stat(path)
    except OSError:
        return False
    return bool(st.st_mode & stat.S_IXUSR)


def _ensure_kernel_driver() -> None:
    """led_bridge를 띄우기 전에 RP1 PWM 커널 모듈/dtoverlay/pinctl 을 준비한다.
    이미 되어 있으면 led_setup.sh 안에서 바로 건너뛴다."""
    if not os.path.exists(config.LED_SETUP_SCRIPT):
        return
    result = subprocess.run(
        ["bash", config.LED_SETUP_SCRIPT],
        capture_output=True, text=True,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0:
        raise RuntimeError(
            f"led_setup.sh 실패 (커널 모듈/dtoverlay 준비 안 됨): {result.stderr.strip()}"
        )


HAS_HARDWARE = _is_executable(config.LED_BRIDGE_BIN)

if HAS_HARDWARE:

    class PixelStrip:
        """led_bridge(C, 상주 프로세스)로 프레임을 흘려보내는 어댑터.

        rpi_ws281x.PixelStrip 과 같은 모양(begin/numPixels/setPixelColor/show)을
        흉내내서, 이 파일의 나머지 애니메이션 로직은 전혀 안 바뀌어도 되게 한다.
        """

        def __init__(self, count, pin, freq_hz, dma, invert, brightness, channel):
            self._n = count
            self._px = [(0, 0, 0)] * count
            self._proc: subprocess.Popen | None = None

        def begin(self):
            _ensure_kernel_driver()
            self._proc = subprocess.Popen(
                [config.LED_BRIDGE_BIN],
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,  # 줄 단위로 즉시 flush
            )
            print(f"[led] C 브릿지 시작: {config.LED_BRIDGE_BIN}")

        def numPixels(self):
            return self._n

        def setPixelColor(self, i, color):
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            self._px[i] = (r, g, b)

        def show(self):
            if self._proc is None or self._proc.stdin is None or self._proc.poll() is not None:
                return
            line = ",".join(f"{r},{g},{b}" for r, g, b in self._px)
            try:
                self._proc.stdin.write(line + "\n")
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                print(f"[led] 브릿지와 연결이 끊김: {e}")
                self._proc = None

        def close(self):
            if self._proc is None:
                return
            try:
                if self._proc.stdin:
                    self._proc.stdin.close()  # EOF -> led_bridge가 알아서 블랙아웃 후 종료
                self._proc.wait(timeout=2.0)
            except Exception:  # noqa: BLE001
                self._proc.terminate()
            self._proc = None

else:

    class PixelStrip:  # pragma: no cover - PC 개발용 콘솔 목업
        def __init__(self, count, *a, **kw):
            self._n = count
            self._px = [0] * count

        def begin(self):
            print(f"[led] mock driver (led_bridge 없음: {config.LED_BRIDGE_BIN})")

        def numPixels(self):
            return self._n

        def setPixelColor(self, i, c):
            self._px[i] = c

        def show(self):
            pass


def hsv(h: float, s: float, v: float) -> tuple[float, float, float]:
    """h,s,v 0~1 -> r,g,b 0~255"""
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return r * 255.0, g * 255.0, b * 255.0


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# 상태별 파라미터 — pi/led-preview.html 의 슬라이더로 먼저 확인하고 여기 반영
# ---------------------------------------------------------------------------
STYLE = {
    "ready": {
        "brightness": 0.28,
        "rev_s": 8.0,          # 한 바퀴 도는 데 걸리는 초
        "breath_s": 4.0,       # 밝기 호흡 주기
    },
    "recording": {
        "brightness_lo": 0.10,
        "brightness_hi": 0.72,
        "hue_quiet": 0.105,    # 조용할 때: 앰버
        "hue_loud": 0.030,     # 크게 말할 때: 주황빨강
        "wave_rev_s": 2.86,    # 조용할 때도 도는 굵은 파동 (1/0.35Hz)
    },
    "processing": {
        "brightness": 0.55,
        "rev_s": 0.55,         # 색 회전: 0.55초에 한 바퀴
        "wave_count": 3,       # 밝기 파동 개수 (링을 따라)
        "wave_hz": 1.8,        # 밝기 파동이 시간에 따라 도는 속도
        "floor": 0.30,
    },
    "error": {
        "brightness": 0.70,
        "blink_hz": 4.0,
        "on_s": 2.0,
        "cycle_s": 3.4,
    },
    "boot": {
        "brightness": 0.35,
        "sweep_s": 1.2,
    },
}


class LedController:
    def __init__(self) -> None:
        self._strip = PixelStrip(
            config.LED_COUNT,
            config.LED_PIN,
            config.LED_FREQ_HZ,
            config.LED_DMA,
            config.LED_INVERT,
            config.LED_MAX_BRIGHTNESS,
            config.LED_CHANNEL,
        )
        self._strip.begin()

        self._n = config.LED_COUNT
        self._lock = threading.Lock()
        self._state = "ready"
        self._params: dict = {}
        self._level = 0.0             # 0~1 마이크 입력 크기
        self._state_started = time.monotonic()
        self._stop = threading.Event()

        self._current = [(0.0, 0.0, 0.0)] * self._n
        self._fade_ms = 300.0

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------ API
    def set_state(self, state: str, **params) -> None:
        with self._lock:
            if state != self._state or params != self._params:
                self._state = state
                self._params = params
                self._state_started = time.monotonic()
                # 상태 전환은 빠르게, 감정색 전환만 표의 transition_ms 사용
                self._fade_ms = float(params.get("transition_ms", 300))

    def set_level(self, level: float) -> None:
        """녹음 중 마이크 입력 크기(0~1)."""
        with self._lock:
            lv = max(0.0, min(1.0, level))
            self._level = self._level * 0.55 + lv * 0.45

    def set_care_color(self, care_color: dict) -> None:
        """서버 응답의 care_color 그대로 넘기면 감정색으로 전환합니다.
        care_color = {"hex": "#F2B6A0", "brightness": 0.38, "transition_ms": 2200}
        """
        self.set_state(
            "speaking",
            hex=care_color["hex"],
            brightness=float(care_color.get("brightness", 0.4)),
            transition_ms=int(care_color.get("transition_ms", 1600)),
        )

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        self._blackout()
        # 콘솔 목업엔 close()가 없으므로 있을 때만 호출 (C 브릿지 프로세스 정리용)
        closer = getattr(self._strip, "close", None)
        if closer is not None:
            closer()

    # -------------------------------------------------------------- 렌더링
    def _run(self) -> None:
        frame_s = 1.0 / config.LED_FPS
        while not self._stop.is_set():
            with self._lock:
                state = self._state
                params = dict(self._params)
                level = self._level
                elapsed = time.monotonic() - self._state_started
                fade_ms = self._fade_ms

            target = self._compose(state, params, level, elapsed)
            self._blend_and_show(target, frame_s, fade_ms)
            time.sleep(frame_s)

    def _compose(self, state, params, level, t):
        if state == "boot":
            return self._boot(t)
        if state == "recording":
            return self._recording(level, t)
        if state == "processing":
            return self._processing(t)
        if state == "speaking":
            return self._speaking(params, t)
        if state == "error":
            return self._error(t)
        if state == "off":
            return [(0.0, 0.0, 0.0)] * self._n
        return self._ready(t)

    # --- 상태별 그림 (led-preview.html 과 동일한 식) ------------------------
    def _ready(self, t):
        """무지개 전체가 아주 느리게 회전. '언제든 말 걸어도 돼'."""
        s = STYLE["ready"]
        spin = t / s["rev_s"]
        breath = 0.80 + 0.20 * (0.5 + 0.5 * math.sin(2 * math.pi * t / s["breath_s"]))
        v = s["brightness"] * breath
        return [hsv(i / self._n + spin, 1.0, v) for i in range(self._n)]

    def _recording(self, level, t):
        """방향 없이 전체 밝기가 음량을 그대로 따라감. 조용할 때도 굵은 파동 2개가 돎."""
        s = STYLE["recording"]
        brightness = s["brightness_lo"] + (s["brightness_hi"] - s["brightness_lo"]) * level
        hue = s["hue_quiet"] + (s["hue_loud"] - s["hue_quiet"]) * level
        out = []
        for i in range(self._n):
            wave = 0.5 + 0.5 * math.cos(2 * math.pi * (i / self._n * 2 - t / s["wave_rev_s"]))
            v = brightness * (0.72 + 0.28 * wave)
            out.append(hsv(hue, 0.95, v))
        return out

    def _processing(self, t):
        """무지개 전체가 빠르게 회전 + 밝기 파동. 서버 응답을 기다리는 4~8초 동안 표시."""
        s = STYLE["processing"]
        spin = t / s["rev_s"]
        out = []
        for i in range(self._n):
            wave = 0.5 + 0.5 * math.cos(2 * math.pi * (i / self._n * s["wave_count"] - t * s["wave_hz"]))
            v = s["brightness"] * (s["floor"] + (1.0 - s["floor"]) * wave ** 1.6)
            out.append(hsv(i / self._n + spin, 1.0, v))
        return out

    def _speaking(self, params, t):
        """감정색: 회전 없이 링 전체가 같은 단색으로 제자리 호흡."""
        r, g, b = hex_to_rgb(params.get("hex", "#A7CDBD"))
        peak = float(params.get("brightness", 0.42))
        period = max(0.4, float(params.get("transition_ms", 1600)) * 2 / 1000.0)
        k = 0.60 + 0.40 * (0.5 + 0.5 * math.sin(2 * math.pi * t / period))
        v = peak * k
        return [(r * v, g * v, b * v)] * self._n

    def _error(self, t):
        """빨강 ↔ 흰색 교차 깜빡임. 어떤 감정색과도 안 닮음."""
        s = STYLE["error"]
        cyc = t % s["cycle_s"]
        if cyc > s["on_s"]:
            return [(0.0, 0.0, 0.0)] * self._n
        step = int(cyc * s["blink_hz"] * 2)
        if step % 2 == 1:
            return [(0.0, 0.0, 0.0)] * self._n
        white = (step // 2) % 2 == 1
        v = s["brightness"] * 255.0
        return [(v, v, v) if white else (v, 0.0, 0.0)] * self._n

    def _boot(self, t):
        """무지개가 한 바퀴 그려지며 채워진다."""
        s = STYLE["boot"]
        head = (t / s["sweep_s"]) * self._n
        return [
            hsv(i / self._n, 1.0, s["brightness"]) if i <= head else (0.0, 0.0, 0.0)
            for i in range(self._n)
        ]

    # --- 출력 --------------------------------------------------------------
    def _blend_and_show(self, target, frame_s, fade_ms):
        alpha = 1.0 if fade_ms <= 0 else min(1.0, frame_s / (fade_ms / 1000.0) * 3.0)
        for i in range(self._n):
            cr, cg, cb = self._current[i]
            tr, tg, tb = target[i]
            nr = cr + (tr - cr) * alpha
            ng = cg + (tg - cg) * alpha
            nb = cb + (tb - cb) * alpha
            self._current[i] = (nr, ng, nb)
            self._strip.setPixelColor(i, Color(int(nr), int(ng), int(nb)))
        self._strip.show()

    def _blackout(self):
        for i in range(self._n):
            self._strip.setPixelColor(i, Color(0, 0, 0))
        self._strip.show()


if __name__ == "__main__":
    # 눈으로 확인:  sudo -E python3 led_controller.py
    led = LedController()
    try:
        print("boot — 무지개 스윕");         led.set_state("boot");       time.sleep(2)
        print("ready — 무지개 느린 회전");    led.set_state("ready");      time.sleep(9)
        print("recording — 음량 연동");       led.set_state("recording")
        for i in range(150):
            led.set_level(max(0.0, math.sin(i / 9) * 0.9))
            time.sleep(0.05)
        print("processing — 무지개 빠른 회전"); led.set_state("processing"); time.sleep(6)
        print("error — 빨강/흰색");           led.set_state("error");      time.sleep(4)
        print("speaking — 감정색 예시 3개 (표는 서버가 줌, 여기선 데모용 하드코딩)")
        demo_colors = {
            "sadness": {"hex": "#F2B6A0", "brightness": 0.38, "transition_ms": 2200},
            "joy": {"hex": "#F6C66D", "brightness": 0.50, "transition_ms": 1200},
            "fatigue": {"hex": "#F0B06A", "brightness": 0.30, "transition_ms": 2800},
        }
        for name, c in demo_colors.items():
            print(f"  {name}")
            led.set_care_color(c); time.sleep(5)
    finally:
        led.close()
