from fastapi import APIRouter, HTTPException

from models.emotion import SessionEndRequest, SessionEndResponse
from services import emotion_session

router = APIRouter(prefix="/api/v1/session", tags=["session"])


@router.post("/end", response_model=SessionEndResponse)
async def end(payload: SessionEndRequest):
    try:
        dominant, average = emotion_session.compute_average(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")
    return SessionEndResponse(dominant_emotion=dominant, average_emotions=average)
