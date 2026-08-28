from fastapi import APIRouter, BackgroundTasks, HTTPException

from models.emotion import (
    SessionEndRequest,
    SessionEndResponse,
    SessionLiveResponse,
    SessionStartResponse,
)
from services import color_care_service, emotion_session, mood_light_client, session_state, sleep_color_service

router = APIRouter(prefix="/api/v1/session", tags=["session"])


@router.post("/start", response_model=SessionStartResponse)
async def start():
    session_id = session_state.start_session()
    return SessionStartResponse(session_id=session_id)


@router.get("/live", response_model=SessionLiveResponse)
async def live():
    session_id = session_state.get_current()
    if session_id is None:
        return SessionLiveResponse(session_id=None, has_session=False, ended=False)

    _, sleep_color = emotion_session.get_sleep_result(session_id)
    ended = sleep_color is not None
    snapshot = emotion_session.get_latest_snapshot(session_id) or {}
    return SessionLiveResponse(
        session_id=session_id,
        has_session=True,
        ended=ended,
        turn_count=snapshot.get("turn_count", 0),
        transcript=snapshot.get("transcript"),
        care_emotion=snapshot.get("care_emotion"),
        care_confidence=snapshot.get("care_confidence"),
        care_color=snapshot.get("care_color"),
        reply_text=snapshot.get("reply_text"),
    )


@router.post("/end", response_model=SessionEndResponse)
async def end(payload: SessionEndRequest, background_tasks: BackgroundTasks):
    try:
        _, average = emotion_session.compute_average(payload.session_id)
        dominant = emotion_session.compute_dominant_care_emotion(payload.session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")

    sleep_profile = sleep_color_service.sleep_profile_for_emotion(dominant)
    sleep_color = color_care_service.get_sleep_color(sleep_profile)
    sleep_color_dict = sleep_color.model_dump()
    emotion_session.set_sleep_result(payload.session_id, sleep_profile, sleep_color_dict)

    background_tasks.add_task(
        mood_light_client.push_color,
        {
            "mode": "sleep",
            "emotion": "settled",
            **sleep_color_dict,
        },
    )

    session_state.clear()

    return SessionEndResponse(
        dominant_emotion=dominant,
        average_emotions=average,
        sleep_color=sleep_color,
    )
