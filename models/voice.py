from pydantic import BaseModel


class VoiceAnalyzeResponse(BaseModel):
    transcript: str
    emotions: dict[str, float]
    pitch_mean: float
    pitch_std: float
