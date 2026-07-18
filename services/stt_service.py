from utils.text_parser import strip_sensevoice_tags


def transcribe(model, wav_path: str) -> str:
    raw_result = model.generate(input=wav_path, cache={}, language="auto", use_itn=True)
    raw_text = raw_result[0]["text"]
    return strip_sensevoice_tags(raw_text)
