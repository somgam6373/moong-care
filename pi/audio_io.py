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


def list_devices() -> str:
    return str(sd.query_devices())


if __name__ == "__main__":
    print(list_devices())
