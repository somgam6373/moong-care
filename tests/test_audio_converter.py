import os
import subprocess

import pytest
import soundfile as sf

from utils.audio_converter import ensure_ffmpeg_available, webm_to_wav


@pytest.fixture(scope="module")
def sample_webm(tmp_path_factory):
    out = tmp_path_factory.mktemp("audio") / "sample.webm"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
         "-t", "1", "-c:a", "libopus", str(out)],
        check=True, capture_output=True,
    )
    return str(out)


def test_ensure_ffmpeg_available_does_not_raise():
    ensure_ffmpeg_available()


def test_webm_to_wav_converts_to_16k_mono(sample_webm, tmp_path):
    out_path = str(tmp_path / "sample.wav")
    webm_to_wav(sample_webm, out_path)

    assert os.path.exists(out_path)
    info = sf.info(out_path)
    assert info.samplerate == 16000
    assert info.channels == 1
