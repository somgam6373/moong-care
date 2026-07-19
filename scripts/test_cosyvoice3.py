"""CosyVoice3 self-host feasibility check. Downloads the model on first run.

Run from repo root: python scripts/test_cosyvoice3.py
Output: scripts/cosyvoice3_test_output.wav
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, "CosyVoice"))
sys.path.append(os.path.join(BASE_DIR, "CosyVoice", "third_party", "Matcha-TTS"))

import torchaudio

from cosyvoice.cli.cosyvoice import AutoModel  # noqa: E402

MODEL_DIR = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
TEST_TEXT = "안녕하세요, 오늘 기분이 어때요?"
# CosyVoice3 requires a system-instruction prefix ending in <|endofprompt|>
# before the actual prompt text (see CosyVoice/example.py:76).
PROMPT_TEXT = "You are a helpful assistant.<|endofprompt|>希望你以后能够做的比我还好呦。"
PROMPT_WAV = os.path.join(BASE_DIR, "CosyVoice", "asset", "zero_shot_prompt.wav")
OUTPUT_PATH = os.path.join(BASE_DIR, "scripts", "cosyvoice3_test_output.wav")


def main() -> None:
    model = AutoModel(model_dir=MODEL_DIR)
    print(f"loaded: {type(model).__name__}")

    for i, result in enumerate(model.inference_zero_shot(TEST_TEXT, PROMPT_TEXT, PROMPT_WAV, stream=False)):
        torchaudio.save(OUTPUT_PATH, result["tts_speech"], model.sample_rate)
        print(f"saved: {OUTPUT_PATH}")
        break


if __name__ == "__main__":
    main()
