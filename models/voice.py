from pydantic import BaseModel

from models.care import CareColor


class VoiceAnalyzeResponse(BaseModel):
    transcript: str
    emotions: dict[str, float]
    pitch_mean: float
    pitch_std: float
    care_emotion: str
    care_emotion_label: str
    care_confidence: float
    care_color: CareColor
    reply_text: str
