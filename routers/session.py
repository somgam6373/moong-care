from fastapi import APIRouter, BackgroundTasks, HTTPException

from models.emotion import SessionEndRequest, SessionEndResponse
from services import color_care_service, emotion_session, mood_light_client, sleep_color_service

router = APIRouter(prefix="/api/v1/session", tags=["session"])


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

    return SessionEndResponse(
        dominant_emotion=dominant,
        average_emotions=average,
        sleep_color=sleep_color,
    )
