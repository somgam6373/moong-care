from pydantic import BaseModel


class VoiceAnalyzeResponse(BaseModel):
    transcript: str
    emotions: dict[str, float]
