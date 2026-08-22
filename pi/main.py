"""moong-care 라즈베리파이 클라이언트 — 상태머신.

    [READY]  --짧게 누름--> [RECORDING] --짧게 누름(or 30초)--> [PROCESSING]
       ^                                                            |
       |                                                POST /api/v1/care/turn (wav 1개)
       |                                                서버가 STT+감정분류+답변+TTS 처리
       |                                                            v
       |                                                       [SPEAKING] --재생끝--> [READY]
       |
       +--꾹 누름(1.2초+)--> [SLEEPING] --아무 버튼--+
                POST /api/v1/session/end                (새 세션으로 복귀)
                오늘 대표 케어감정 -> 수면색, 자장가 반복 재생

버튼 하나로 두 가지를 구분합니다: 짧게 눌렀다 떼면 대화, 꾹 눌렀다 떼면 취침.
그래서 눌림/뗌 이벤트에서 유지 시간을 재고, "짧음/길음"을 뗄 때 큐에 넣습니다.

실행:  sudo -E python3 main.py        (rpi_ws281x 가 root 권한을 요구합니다)
"""

from __future__ import annotations

import queue
import signal
import sys
import time
import uuid

from gpiozero import Button

import config
import server_client as api
from audio_io import LullabyPlayer, Recorder, play_wav
from led_controller import LedController


class MoongCare:
    def __init__(self) -> None:
        self.led = LedController()
        self.rec = Recorder(on_level=self.led.set_level)
        self.button = Button(
            config.BUTTON_PIN,
            pull_up=True,
            bounce_time=config.BUTTON_BOUNCE_S,
        )
        # 큐에는 "short"(짧게 눌렀다 뗌) / "long"(꾹 눌렀다 뗌) 문자열이 들어온다.
        # 판정은 뗄 때(when_released) 눌려있던 시간으로 한다.
        self.presses: queue.Queue[str] = queue.Queue()
        self._press_started: float | None = None
        self.button.when_pressed = self._on_press
        self.button.when_released = self._on_release

        self.state = "ready"
        self.session_id = config.SESSION_ID
        self._running = True

    # --------------------------------------------------------------- 버튼
    def _on_press(self) -> None:
        self._press_started = time.monotonic()

    def _on_release(self) -> None:
        if self._press_started is None:
            return
        held = time.monotonic() - self._press_started
        self._press_started = None
        self.presses.put("long" if held >= config.LONG_PRESS_S else "short")

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.led.set_state("boot")
        time.sleep(1.2)

        if not api.health():
            print(f"[warn] 서버에 닿지 않음: {config.SERVER_BASE}")
            self.led.set_state("error")
            time.sleep(2)

        self._to_ready()
        print("준비 완료. 버튼을 눌러 말하세요.")

        while self._running:
            try:
                press = self._wait_press()  # READY 에서 버튼 대기
                if not self._running or press is None:
                    break
                if press == "long":
                    self._sleep_cycle()     # SLEEPING (자장가) -> 새 세션으로 복귀
                    continue
                wav, duration = self._record()   # RECORDING
                if duration < config.MIN_RECORD_S:
                    print(f"[skip] 너무 짧음 ({duration:.1f}s)")
                    self._to_ready()
                    continue
                self._process_and_speak(wav)     # PROCESSING -> SPEAKING
            except KeyboardInterrupt:
                break
            except api.ServerError as e:
                print(f"[server error] {e}")
                self.led.set_state("error")
                time.sleep(2)
            except Exception as e:                # noqa: BLE001
                print(f"[error] {e}")
                self.led.set_state("error")
                time.sleep(2)
            finally:
                if self._running:
                    self._to_ready()

    # ------------------------------------------------------------- 단계별
    def _to_ready(self) -> None:
        self.state = "ready"
        self.led.set_state("ready")
        self._drain_presses()

    def _drain_presses(self) -> None:
        while not self.presses.empty():
            self.presses.get_nowait()

    def _wait_press(self) -> str | None:
        """READY 에서 버튼 대기. "short"/"long" 을 돌려주거나, 종료 중이면 None."""
        while self._running:
            try:
                return self.presses.get(timeout=0.2)
            except queue.Empty:
                continue
        return None

    def _record(self) -> tuple[str, float]:
        self.state = "recording"
        self.led.set_state("recording")
        print("● 녹음 시작")
        self.rec.start()

        started = time.monotonic()
        while self._running:
            elapsed = time.monotonic() - started
            if elapsed >= config.MAX_RECORD_S:
                print("● 최대 길이 도달, 자동 종료")
                break
            try:
                self.presses.get(timeout=0.1)
                break
            except queue.Empty:
                continue

        wav, duration = self.rec.stop()
        self.led.set_level(0.0)
        print(f"■ 녹음 종료 ({duration:.1f}s)")
        return wav, duration

    def _process_and_speak(self, wav: str) -> None:
        self.state = "processing"
        self.led.set_state("processing")

        # 서버가 STT + 9->14 감정분류(GPT) + 답변생성 + TTS 를 전부 처리하고
        # 한 번의 응답으로 돌려준다. 폴링 없음 — 이 호출이 끝날 때까지 기다리면 끝.
        result = api.care_turn(wav, config.REPLY_PATH, session_id=self.session_id)

        print(f'  전사: "{result.transcript}"')
        print(
            f"  감정: {result.care_emotion} ({result.care_emotion_label}) "
            f"conf={result.care_confidence} color={result.care_color['hex']}"
            + (" [fallback]" if result.care_fallback else "")
        )
        print(f'  답변: "{result.reply_text}"')
        if result.timing:
            print(f"  시간: {result.timing}")

        self.state = "speaking"
        self.led.set_care_color(result.care_color)
        play_wav(result.audio_path)

    def _sleep_cycle(self) -> None:
        """꾹 눌러서 대화 종료 -> 자장가. 아무 버튼이나 누르면 새 세션으로 깨어난다."""
        self.state = "sleeping"
        print("● 대화 종료, 자장가 모드")

        try:
            sleep_color = api.end_session(self.session_id)
            print(f"  오늘의 색: {sleep_color['hex']}")
        except api.ServerError as e:
            print(f"[server error] session/end 실패, 기본색 사용: {e}")
            sleep_color = config.DEFAULT_SLEEP_COLOR

        self.led.set_sleep_color(sleep_color)
        self._drain_presses()

        player = LullabyPlayer(config.LULLABY_PATH)
        player.start()
        try:
            while self._running:
                try:
                    self.presses.get(timeout=0.2)
                    break  # short든 long이든 상관없이 아무 버튼이나 누르면 깨어남
                except queue.Empty:
                    continue
        finally:
            player.stop()

        if self._running:
            self.session_id = self._new_session_id()
            print(f"● 기상. 새 대화 시작 (session_id={self.session_id})")

    def _new_session_id(self) -> str:
        return f"{config.SESSION_ID}-{uuid.uuid4().hex[:6]}"

    # ------------------------------------------------------------------
    def shutdown(self, *_args) -> None:
        self._running = False
        try:
            self.rec.abort()
        except Exception:  # noqa: BLE001
            pass
        self.led.set_state("off")
        time.sleep(0.3)
        self.led.close()


def main() -> int:
    app = MoongCare()
    signal.signal(signal.SIGTERM, app.shutdown)
    try:
        app.run()
    finally:
        app.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
