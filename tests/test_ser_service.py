from services.ser_service import parse_emotion2vec_output, analyze_emotion


def test_parse_emotion2vec_output_maps_labels_to_english():
    raw_result = [{
        "key": "sample",
        "labels": ["生气/angry", "开心/happy", "中立/neutral", "<unk>"],
        "scores": [0.05, 0.65, 0.20, 0.10],
    }]
    emotions = parse_emotion2vec_output(raw_result)
    assert emotions == {"angry": 0.05, "happy": 0.65, "neutral": 0.20, "unknown": 0.10}


class _FakeSERModel:
    def generate(self, wav_path, granularity, extract_embedding):
        return [{
            "labels": ["开心/happy", "中立/neutral"],
            "scores": [0.7, 0.3],
        }]


def test_analyze_emotion_calls_model_and_parses_result():
    emotions = analyze_emotion(_FakeSERModel(), "dummy.wav")
    assert emotions == {"happy": 0.7, "neutral": 0.3}
