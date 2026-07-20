from pydantic import BaseModel


class TTSRequest(BaseModel):
    text: str
    session_id: str | None = None
    voice: str | None = None
