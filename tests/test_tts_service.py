import torch

from services.tts_service import synthesize, register_moong_speaker


class _FakeTTSModel:
    sample_rate = 16000

    def inference_zero_shot(self, text, prompt_text, prompt_wav, zero_shot_spk_id):
        yield {"tts_speech": torch.zeros(1, 1600)}

    def add_zero_shot_spk(self, prompt_text, prompt_wav, spk_id):
        self.registered_spk_id = spk_id
        return True

    def save_spkinfo(self):
        self.saved = True


def test_synthesize_returns_wav_bytes():
    audio_bytes = synthesize(_FakeTTSModel(), "안녕하세요")
    assert isinstance(audio_bytes, bytes)
    assert audio_bytes[:4] == b"RIFF"


def test_register_moong_speaker_calls_add_and_save():
    model = _FakeTTSModel()
    register_moong_speaker(model)
    assert model.registered_spk_id == "moong"
    assert model.saved is True
