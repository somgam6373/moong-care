import io
import os

import torchaudio

SPK_ID = "moong"
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACEHOLDER_PROMPT_WAV = os.path.join(_BASE_DIR, "CosyVoice", "asset", "zero_shot_prompt.wav")
PLACEHOLDER_PROMPT_TEXT = "希望你以后能够做的比我还好呦。"


def register_moong_speaker(tts_model) -> None:
    tts_model.add_zero_shot_spk(PLACEHOLDER_PROMPT_TEXT, PLACEHOLDER_PROMPT_WAV, SPK_ID)
    tts_model.save_spkinfo()


def synthesize(tts_model, text: str) -> bytes:
    for result in tts_model.inference_zero_shot(text, "", "", zero_shot_spk_id=SPK_ID):
        buffer = io.BytesIO()
        torchaudio.save(buffer, result["tts_speech"], tts_model.sample_rate, format="wav")
        return buffer.getvalue()
    raise RuntimeError("TTS produced no audio output")
