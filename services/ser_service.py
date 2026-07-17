def parse_emotion2vec_output(raw_result: list[dict]) -> dict[str, float]:
    labels = raw_result[0]["labels"]
    scores = raw_result[0]["scores"]
    emotions: dict[str, float] = {}
    for label, score in zip(labels, scores):
        key = label.split("/")[-1] if "/" in label else "unknown"
        emotions[key] = float(score)
    return emotions


def analyze_emotion(model, wav_path: str) -> dict[str, float]:
    raw_result = model.generate(wav_path, granularity="utterance", extract_embedding=False)
    return parse_emotion2vec_output(raw_result)
