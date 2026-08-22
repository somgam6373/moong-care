"""moong-care FastAPI 서버 호출.

파이가 거는 POST 는 두 개입니다.

- /api/v1/care/turn   매 턴마다: STT, 9->14 감정 분류(GPT), 답변 생성, TTS 를
  서버가 한 번에 처리하고 결과를 그 응답으로 바로 돌려줍니다. 폴링이 필요 없습니다.
- /api/v1/session/end 버튼을 꾹 눌러 대화를 끝낼 때 1번: 오늘 대화의 대표 케어
  감정에 대응하는 수면색을 받아 자장가 재생 중 LED에 씁니다.

응답은 답변 wav(본문) + 감정/색/전사(헤더) 로 옵니다. 헤더는 HTTP 규격상
latin-1만 허용되므로, 한글이 들어가는 값(라벨/전사/답변텍스트)은 서버가
percent-encoding 해서 보냅니다. 여기서 urllib.parse.unquote 로 복원합니다.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass

import requests

import config


class ServerError(RuntimeError):
    pass


@dataclass
class CareTurnResult:
    audio_path: str
    care_emotion: str
    care_emotion_label: str
    care_confidence: float
    care_fallback: bool
    care_color: dict            # {"hex":..., "brightness":..., "transition_ms":...}
    transcript: str
    reply_text: str
    timing: dict[str, float]


def _unquote(headers, key: str, default: str = "") -> str:
    value = headers.get(key)
    return urllib.parse.unquote(value) if value is not None else default


def _parse_timing(raw: str) -> dict[str, float]:
    timing: dict[str, float] = {}
    for part in raw.split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        try:
            timing[k] = float(v)
        except ValueError:
            pass
    return timing


def care_turn(
    wav_path: str,
    out_path: str,
    session_id: str = config.SESSION_ID,
    style: str = config.CHAT_STYLE,
    voice: str = config.TTS_VOICE,
) -> CareTurnResult:
    """POST /api/v1/care/turn 하나로 STT~TTS 전부 처리하고 결과를 받는다."""
    url = f"{config.SERVER_BASE}/api/v1/care/turn"
    with open(wav_path, "rb") as f:
        files = {"audio": ("input.wav", f, "audio/wav")}
        data = {"session_id": session_id, "style": style, "voice": voice}
        r = requests.post(url, files=files, data=data, timeout=config.TIMEOUT_TURN)

    if r.status_code != 200:
        raise ServerError(f"care/turn {r.status_code}: {r.text[:300]}")

    with open(out_path, "wb") as f:
        f.write(r.content)

    h = r.headers
    return CareTurnResult(
        audio_path=out_path,
        care_emotion=h.get("x-care-emotion", "calm"),
        care_emotion_label=_unquote(h, "x-care-label", "평온"),
        care_confidence=float(h.get("x-care-confidence", "0")),
        care_fallback=h.get("x-care-fallback", "0") == "1",
        care_color={
            "hex": h.get("x-care-hex", "#A7CDBD"),
            "brightness": float(h.get("x-care-brightness", "0.4")),
            "transition_ms": int(float(h.get("x-care-transition-ms", "1600"))),
        },
        transcript=_unquote(h, "x-transcript"),
        reply_text=_unquote(h, "x-reply-text"),
        timing=_parse_timing(h.get("x-timing", "")),
    )


def end_session(session_id: str) -> dict:
    """POST /api/v1/session/end. 오늘 대화의 대표 케어 감정에 대응하는 수면색을 받는다.

    반환값은 care_turn()의 care_color와 같은 모양: {"hex":..., "brightness":..., "transition_ms":...}
    """
    url = f"{config.SERVER_BASE}/api/v1/session/end"
    r = requests.post(url, json={"session_id": session_id}, timeout=config.TIMEOUT_SESSION_END)
    if r.status_code != 200:
        raise ServerError(f"session/end {r.status_code}: {r.text[:300]}")
    return r.json()["sleep_color"]


def health() -> bool:
    try:
        r = requests.get(f"{config.SERVER_BASE}/health", timeout=3)
        return r.status_code == 200
    except requests.RequestException:
        return False
