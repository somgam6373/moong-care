import re

_TAG_RE = re.compile(r"<\|.*?\|>")


def strip_sensevoice_tags(raw: str) -> str:
    return _TAG_RE.sub("", raw).strip()
