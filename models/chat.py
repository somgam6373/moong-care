from typing import Literal

from pydantic import BaseModel


class ChatReplyRequest(BaseModel):
    session_id: str
    transcript: str
    emotions: dict[str, float]
    style: Literal["empathetic", "realistic"] = "empathetic"


class ChatReplyResponse(BaseModel):
    reply_text: str
