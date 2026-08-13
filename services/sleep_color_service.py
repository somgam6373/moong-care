SLEEP_PROFILE_DEFAULT = "warm_dim"

HIGH_AROUSAL_EMOTIONS = {"anxiety", "tension", "anger", "stress", "confusion"}
LOW_ENERGY_EMOTIONS = {"sadness", "loneliness", "fatigue", "helplessness"}
RELATIONSHIP_EMOTIONS = {"shame_guilt"}


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
