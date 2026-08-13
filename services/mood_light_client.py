import json
import logging
import urllib.error
import urllib.request

from config import settings

logger = logging.getLogger(__name__)


def push_color(payload: dict) -> bool:
    endpoint = settings.MOOD_LIGHT_ENDPOINT.strip()
    if not endpoint:
        return False

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.MOOD_LIGHT_TIMEOUT_SECONDS):
            return True
    except (OSError, urllib.error.URLError, urllib.error.HTTPError) as exc:
        logger.warning("mood light push failed: %s", exc)
        return False
