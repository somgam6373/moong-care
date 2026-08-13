from models.care import CareColor

CARE_EMOTION_LABELS: dict[str, str] = {
    "calm": "평온",
    "joy": "기쁨/만족",
    "excitement": "설렘/들뜸",
    "relief": "안도",
    "sadness": "슬픔",
    "loneliness": "외로움",
    "anxiety": "불안",
    "tension": "긴장",
    "anger": "분노/짜증",
    "stress": "스트레스/과부하",
    "fatigue": "피로",
    "helplessness": "무기력",
    "confusion": "혼란/당황",
    "shame_guilt": "자책/민망함",
}

ALLOWED_CARE_EMOTIONS = set(CARE_EMOTION_LABELS)
FALLBACK_CARE_EMOTION = "calm"

REALTIME_COLORS: dict[str, CareColor] = {
    "calm": CareColor(hex="#A7CDBD", brightness=0.42, transition_ms=1600),
    "joy": CareColor(hex="#F6C66D", brightness=0.50, transition_ms=1200),
    "excitement": CareColor(hex="#BFD8FF", brightness=0.44, transition_ms=1800),
    "relief": CareColor(hex="#B8E0C8", brightness=0.42, transition_ms=1800),
    "sadness": CareColor(hex="#F2B6A0", brightness=0.38, transition_ms=2200),
    "loneliness": CareColor(hex="#E8B7D4", brightness=0.35, transition_ms=2400),
    "anxiety": CareColor(hex="#8DB7D9", brightness=0.36, transition_ms=2000),
    "tension": CareColor(hex="#7DCAC3", brightness=0.38, transition_ms=1800),
    "anger": CareColor(hex="#86BFA6", brightness=0.32, transition_ms=2500),
    "stress": CareColor(hex="#91B7A8", brightness=0.34, transition_ms=2200),
    "fatigue": CareColor(hex="#F0B06A", brightness=0.30, transition_ms=2800),
    "helplessness": CareColor(hex="#D9B8A6", brightness=0.32, transition_ms=2800),
    "confusion": CareColor(hex="#B6B4D8", brightness=0.34, transition_ms=2200),
    "shame_guilt": CareColor(hex="#D8A6A1", brightness=0.32, transition_ms=2600),
}

SLEEP_COLORS: dict[str, CareColor] = {
    "warm_dim": CareColor(hex="#C9785A", brightness=0.16, transition_ms=6000),
    "deep_amber": CareColor(hex="#B85A3D", brightness=0.12, transition_ms=8000),
    "soft_peach": CareColor(hex="#D18461", brightness=0.14, transition_ms=7000),
    "low_rose": CareColor(hex="#B96F6B", brightness=0.13, transition_ms=7000),
}


def get_care_emotion_label(care_emotion: str) -> str:
    return CARE_EMOTION_LABELS.get(care_emotion, CARE_EMOTION_LABELS[FALLBACK_CARE_EMOTION])


def get_realtime_color(care_emotion: str) -> CareColor:
    return REALTIME_COLORS.get(care_emotion, REALTIME_COLORS[FALLBACK_CARE_EMOTION])


def get_sleep_color(sleep_profile: str) -> CareColor:
    return SLEEP_COLORS.get(sleep_profile, SLEEP_COLORS["warm_dim"])
