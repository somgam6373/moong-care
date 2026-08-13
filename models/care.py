from typing import Literal

from pydantic import BaseModel


class CareColor(BaseModel):
    hex: str
    brightness: float
    transition_ms: int


class MoodLightPayload(BaseModel):
    mode: Literal["realtime", "sleep"]
    emotion: str
    hex: str
    brightness: float
    transition_ms: int
