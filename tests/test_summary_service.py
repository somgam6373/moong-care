from types import SimpleNamespace

from services import summary_service


class _FakeMessages:
    def __init__(self, reply_text):
        self.reply_text = reply_text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply_text)])


class _FakeClient:
    def __init__(self, reply_text):
        self.messages = _FakeMessages(reply_text)


def test_summarize_diary_returns_one_line(monkeypatch):
    fake_client = _FakeClient("발표를 성공적으로 마쳐서 뿌듯한 하루였다.")
    monkeypatch.setattr(summary_service, "get_client", lambda: fake_client)

    summary = summary_service.summarize_diary("오늘은 발표를 해서 뿌듯했다. 친구들도 칭찬해줬다.")

    assert summary == "발표를 성공적으로 마쳐서 뿌듯한 하루였다."
    assert fake_client.messages.last_kwargs["messages"][-1]["content"] == "오늘은 발표를 해서 뿌듯했다. 친구들도 칭찬해줬다."
