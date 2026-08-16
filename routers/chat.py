from fastapi import APIRouter, HTTPException

from models.chat import ChatReplyRequest, ChatReplyResponse
from services import chat_service, emotion_session

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/reply", response_model=ChatReplyResponse)
async def reply(payload: ChatReplyRequest):
    session = emotion_session.get_session(payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    care_emotion = payload.care_emotion or emotion_session.get_last_user_care_emotion(payload.session_id)
    reply_text = chat_service.get_reply(
        session.turns,
        payload.transcript,
        payload.emotions,
        payload.style,
        care_emotion,
    )
    emotion_session.add_assistant_turn(payload.session_id, reply_text)
    return ChatReplyResponse(reply_text=reply_text)
