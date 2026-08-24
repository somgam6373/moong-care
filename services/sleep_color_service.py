SLEEP_PROFILE_DEFAULT = "warm_dim"

HIGH_AROUSAL_EMOTIONS = {"anxiety", "tension", "anger", "stress", "confusion"}
LOW_ENERGY_EMOTIONS = {"sadness", "loneliness", "fatigue", "helplessness"}
RELATIONSHIP_EMOTIONS = {"shame_guilt"}


def sleep_profile_for_emotion(care_emotion: str) -> str:
    """세션 대표 케어 감정(confidence 가중 1위) 하나로 수면색 프로파일을 정한다.

    choose_sleep_profile()과 달리 대화 전체를 훑어 다수결로 정하지 않고,
    가장 점수가 높았던 감정 하나에 대응되는 색을 그대로 쓴다.
    """
    if care_emotion in RELATIONSHIP_EMOTIONS:
        return "low_rose"
    if care_emotion in HIGH_AROUSAL_EMOTIONS:
        return "deep_amber"
    if care_emotion in LOW_ENERGY_EMOTIONS:
        return "soft_peach"
    return SLEEP_PROFILE_DEFAULT


def choose_sleep_profile(care_timeline: list[dict]) -> str:
    if not care_timeline:
        return SLEEP_PROFILE_DEFAULT

    counts = {
        "deep_amber": 0,
        "soft_peach": 0,
        "low_rose": 0,
    }
    for item in care_timeline:
        emotion = item.get("care_emotion")
        if emotion in RELATIONSHIP_EMOTIONS:
            counts["low_rose"] += 1
        elif emotion in HIGH_AROUSAL_EMOTIONS:
            counts["deep_amber"] += 1
        elif emotion in LOW_ENERGY_EMOTIONS:
            counts["soft_peach"] += 1

    profile, count = max(counts.items(), key=lambda kv: kv[1])
    if count == 0:
        return SLEEP_PROFILE_DEFAULT
    return profile
