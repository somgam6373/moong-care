import os
import subprocess
import wave

import pytest
import soundfile as sf

from utils.audio_converter import ensure_ffmpeg_available, ensure_wav_16k_mono, webm_to_wav


@pytest.fixture(scope="module")
def sample_webm(tmp_path_factory):
    out = tmp_path_factory.mktemp("audio") / "sample.webm"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
         "-t", "1", "-c:a", "libopus", str(out)],
        check=True, capture_output=True,
    )
    return str(out)


def _make_wav(path: str, framerate: int, channels: int, duration_s: float = 0.2) -> None:
    n_frames = int(framerate * duration_s)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * n_frames * channels)


def test_ensure_ffmpeg_available_does_not_raise():
    ensure_ffmpeg_available()


def test_webm_to_wav_converts_to_16k_mono(sample_webm, tmp_path):
    out_path = str(tmp_path / "sample.wav")
    webm_to_wav(sample_webm, out_path)

    assert os.path.exists(out_path)
    info = sf.info(out_path)
    assert info.samplerate == 16000
    assert info.channels == 1


def test_ensure_wav_16k_mono_skips_conversion_when_already_correct(tmp_path):
    src = str(tmp_path / "already.wav")
    dst = str(tmp_path / "converted.wav")
    _make_wav(src, framerate=16000, channels=1)

    result = ensure_wav_16k_mono(src, dst)

    assert result == src
    assert not os.path.exists(dst)  # 변환이 아예 일어나지 않았어야 함


def test_ensure_wav_16k_mono_converts_when_wrong_rate(tmp_path):
    src = str(tmp_path / "wrong_rate.wav")
    dst = str(tmp_path / "converted.wav")
    _make_wav(src, framerate=44100, channels=2)

    result = ensure_wav_16k_mono(src, dst)

    assert result == dst
    assert os.path.exists(dst)
    info = sf.info(dst)
    assert info.samplerate == 16000
    assert info.channels == 1


def test_ensure_wav_16k_mono_converts_non_wav_input(sample_webm, tmp_path):
    dst = str(tmp_path / "converted.wav")

    result = ensure_wav_16k_mono(sample_webm, dst)

    assert result == dst
    info = sf.info(dst)
    assert info.samplerate == 16000
    assert info.channels == 1
