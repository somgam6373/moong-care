import numpy as np
import pyworld as pw
import soundfile as sf


def analyze_pitch(wav_path: str) -> tuple[float, float]:
    audio, sr = sf.read(wav_path)
    audio = audio.astype(np.float64)

    f0, t = pw.dio(audio, sr)
    f0 = pw.stonemask(audio, f0, t, sr)

    voiced = f0[f0 > 0]
    if len(voiced) == 0:
        return 0.0, 0.0
    return float(voiced.mean()), float(voiced.std())
