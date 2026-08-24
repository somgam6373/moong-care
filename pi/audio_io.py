"""마이크 녹음 / 스피커 재생.

녹음은 sounddevice 콜백으로 받으면서 동시에 RMS(입력 크기)를 계산해
LED 링이 목소리 크기만큼 차오르도록 넘겨줍니다.
재생은 aplay(alsa-utils) 를 씁니다. USB 스피커에서 가장 말썽이 적습니다.
"""

from __future__ import annotations

import subprocess
import threading
import wave

import numpy as np
import sounddevice as sd

import config


class Recorder:
    """버튼 토글 방식 녹음기."""

    def __init__(self, on_level=None) -> None:
        self._on_level = on_level
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    def start(self) -> None:
        with self._lock:
            self._frames = []

        def callback(indata, frames, time_info, status):  # noqa: ARG001
            if status:
                print(f"[audio] {status}")
            chunk = indata.copy()
            with self._lock:
                self._frames.append(chunk)
            if self._on_level is not None:
                rms = float(np.sqrt(np.mean(np.square(chunk, dtype=np.float64))))
                # 16bit 기준 대략 0.02(조용) ~ 0.35(큰 목소리) → 0~1 로 정규화
                self._on_level(min(1.0, max(0.0, (rms - 0.01) / 0.22)))

        self._stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype="float32",
            device=config.INPUT_DEVICE,
            blocksize=int(config.SAMPLE_RATE * 0.05),
            callback=callback,
        )
        self._stream.start()

    def stop(self, path: str = config.RECORD_PATH) -> tuple[str, float]:
        """녹음을 끝내고 16kHz mono wav 로 저장. (경로, 길이초) 반환."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        with self._lock:
            frames = self._frames
            self._frames = []

        if not frames:
            return path, 0.0

        audio = np.concatenate(frames, axis=0).flatten()
        duration = len(audio) / config.SAMPLE_RATE
        pcm = np.clip(audio, -1.0, 1.0)
        pcm = (pcm * 32767).astype(np.int16)

        with wave.open(path, "wb") as wf:
            wf.setnchannels(config.CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(config.SAMPLE_RATE)
            wf.writeframes(pcm.tobytes())

        return path, duration

    def abort(self) -> None:
        if self._stream is not None:
            self._stream.abort()
            self._stream.close()
            self._stream = None
        with self._lock:
            self._frames = []


# ----------------------------------------------------------------------
def play_wav(path: str) -> None:
    """블로킹 재생. 재생이 끝나야 리턴합니다."""
    cmd = ["aplay", "-q"]
    if config.OUTPUT_DEVICE:
        cmd += ["-D", config.OUTPUT_DEVICE]
    cmd.append(path)
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"aplay 실패: {result.stderr.decode(errors='ignore')}")


class LullabyPlayer:
    """자장가를 버튼이 눌릴 때까지 반복 재생.

    aplay는 한 곡이 끝나면 그냥 종료되므로, 별도 스레드에서 stop() 이 불릴 때까지
    같은 파일을 계속 다시 튼다. main.py 의 버튼 대기 루프는 이 스레드와 무관하게
    계속 돌기 때문에 재생 중에도 버튼 입력을 즉시 감지할 수 있다.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._stop = threading.Event()
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        cmd = ["aplay", "-q"]
        if config.OUTPUT_DEVICE:
            cmd += ["-D", config.OUTPUT_DEVICE]
        cmd.append(self._path)
        while not self._stop.is_set():
            try:
                self._proc = subprocess.Popen(cmd)
            except FileNotFoundError:
                print(f"[audio] 자장가 파일을 못 찾음: {self._path}")
                return
            self._proc.wait()
            self._proc = None
            # 곡이 끝까지 자연 재생되면 stop() 이 불릴 때까지 처음부터 반복한다.

    def stop(self) -> None:
        """즉시 중단. 재생 중인 aplay 프로세스를 죽이고 스레드가 끝나길 기다린다."""
        self._stop.set()
        if self._proc is not None:
            self._proc.terminate()
        if self._thread is not None:
            self._thread.join(timeout=2.0)


def list_devices() -> str:
    return str(sd.query_devices())


if __name__ == "__main__":
    print(list_devices())
