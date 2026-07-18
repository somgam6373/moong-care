from types import SimpleNamespace

from services import summary_service


class _FakeCompletions:
    def __init__(self, reply_text):
        self.reply_text = reply_text
        self.last_messages = None

    def create(self, model, messages):
        self.last_messages = messages
        message = SimpleNamespace(content=self.reply_text)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


class _FakeClient:
    def __init__(self, reply_text):
        self.chat = SimpleNamespace(completions=_FakeCompletions(reply_text))


def test_summarize_diary_returns_one_line(monkeypatch):
    fake_client = _FakeClient("발표를 성공적으로 마쳐서 뿌듯한 하루였다.")
    monkeypatch.setattr(summary_service, "get_client", lambda: fake_client)

    summary = summary_service.summarize_diary("오늘은 발표를 해서 뿌듯했다. 친구들도 칭찬해줬다.")

    assert summary == "발표를 성공적으로 마쳐서 뿌듯한 하루였다."
    assert fake_client.chat.completions.last_messages[-1]["content"] == "오늘은 발표를 해서 뿌듯했다. 친구들도 칭찬해줬다."
