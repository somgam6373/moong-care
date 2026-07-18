import numpy as np
import soundfile as sf

from services.pitch_service import analyze_pitch


def test_analyze_pitch_returns_mean_near_input_frequency(tmp_path):
    sr = 16000
    duration = 1.0
    freq = 220.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    audio = 0.5 * np.sin(2 * np.pi * freq * t)
    wav_path = str(tmp_path / "tone.wav")
    sf.write(wav_path, audio, sr)

    pitch_mean, pitch_std = analyze_pitch(wav_path)

    assert 180.0 < pitch_mean < 260.0
    assert pitch_std < 15.0


def test_analyze_pitch_returns_zero_for_silence(tmp_path):
    sr = 16000
    audio = np.zeros(sr)
    wav_path = str(tmp_path / "silence.wav")
    sf.write(wav_path, audio, sr)

    pitch_mean, pitch_std = analyze_pitch(wav_path)

    assert pitch_mean == 0.0
    assert pitch_std == 0.0
