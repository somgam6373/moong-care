import io
from types import SimpleNamespace

from services import mood_light_client


def test_push_color_noops_when_endpoint_missing(monkeypatch):
    monkeypatch.setattr(mood_light_client.settings, "MOOD_LIGHT_ENDPOINT", "")

    assert mood_light_client.push_color({"mode": "realtime"}) is False


def test_push_color_posts_json(monkeypatch):
    captured = {}

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["data"] = request.data
        captured["content_type"] = request.headers["Content-type"]
        captured["timeout"] = timeout
        return _FakeResponse()

    monkeypatch.setattr(mood_light_client.settings, "MOOD_LIGHT_ENDPOINT", "http://pi/api/v1/mood-light/color")
    monkeypatch.setattr(mood_light_client.settings, "MOOD_LIGHT_TIMEOUT_SECONDS", 1.5)
    monkeypatch.setattr(mood_light_client.urllib.request, "urlopen", fake_urlopen)

    result = mood_light_client.push_color({"mode": "realtime", "emotion": "calm"})

    assert result is True
    assert captured["url"] == "http://pi/api/v1/mood-light/color"
    assert captured["data"] == b'{"mode": "realtime", "emotion": "calm"}'
    assert captured["content_type"] == "application/json"
    assert captured["timeout"] == 1.5


def test_push_color_swallows_http_errors(monkeypatch):
    def fake_urlopen(request, timeout):
        raise OSError("network down")

    monkeypatch.setattr(mood_light_client.settings, "MOOD_LIGHT_ENDPOINT", "http://pi/api/v1/mood-light/color")
    monkeypatch.setattr(mood_light_client.urllib.request, "urlopen", fake_urlopen)

    assert mood_light_client.push_color({"mode": "realtime"}) is False
