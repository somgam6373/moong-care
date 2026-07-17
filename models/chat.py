from pydantic import BaseModel


class ChatReplyRequest(BaseModel):
    session_id: str
    transcript: str
    emotions: dict[str, float]


class ChatReplyResponse(BaseModel):
    reply_text: str
