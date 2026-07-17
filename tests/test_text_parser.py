from utils.text_parser import strip_sensevoice_tags


def test_strip_sensevoice_tags_removes_all_tags():
    raw = "<|ko|><|NEUTRAL|><|Speech|><|woitn|>오늘 발표가 잘 됐어요"
    assert strip_sensevoice_tags(raw) == "오늘 발표가 잘 됐어요"


def test_strip_sensevoice_tags_handles_no_tags():
    assert strip_sensevoice_tags("안녕하세요") == "안녕하세요"


def test_strip_sensevoice_tags_handles_empty_string():
    assert strip_sensevoice_tags("") == ""
