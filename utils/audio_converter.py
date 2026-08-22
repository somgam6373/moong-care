import shutil
import subprocess
import wave


def ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpeg not found on PATH. Install ffmpeg and add it to PATH before starting the server."
        )


def webm_to_wav(input_path: str, output_path: str) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", input_path, "-ar", "16000", "-ac", "1", output_path],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr.decode(errors='ignore')}")


TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1


def _is_16k_mono_wav(path: str) -> bool:
    """path 가 이미 16kHz mono wav 인지 확인한다. wav가 아니거나 손상됐으면 False."""
    try:
        with wave.open(path, "rb") as wf:
            return wf.getframerate() == TARGET_SAMPLE_RATE and wf.getnchannels() == TARGET_CHANNELS
    except (wave.Error, EOFError, OSError):
        return False


def ensure_wav_16k_mono(input_path: str, output_path: str) -> str:
    """이미 16kHz mono wav 면 변환을 건너뛰고 input_path 를 그대로 반환한다.

    라즈베리파이는 처음부터 16kHz mono wav 로 녹음하므로, 이 경로에서는
    ffmpeg 프로세스 실행(약 100~300ms)이 통째로 생략된다.
    그 외 포맷(webm 등)이면 기존 webm_to_wav 로 변환하고 output_path 를 반환한다.
    """
    if _is_16k_mono_wav(input_path):
        return input_path
    webm_to_wav(input_path, output_path)
    return output_path
