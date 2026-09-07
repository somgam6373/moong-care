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
    # 2026-08-29 색상 개편: 3D 프린트 디퓨저가 채도를 한 번 더 깎아서, 기존 저채도
    # 팔레트(S 0.17~0.38)는 확산 후 서로 구분이 안 됐음. PAD quadrant는 유지하고
    # 채도만 올림 (docs 상 color-palette-revision.md 참고).
    "calm": CareColor(hex="#88D1A6", brightness=0.42, transition_ms=1600),
    "joy": CareColor(hex="#F2C66D", brightness=0.50, transition_ms=1200),
    "excitement": CareColor(hex="#85B8F2", brightness=0.44, transition_ms=1800),
    "relief": CareColor(hex="#82D98E", brightness=0.42, transition_ms=1800),
    "sadness": CareColor(hex="#CC8F7A", brightness=0.38, transition_ms=2200),
    "loneliness": CareColor(hex="#B877B8", brightness=0.35, transition_ms=2400),
    "anxiety": CareColor(hex="#6369A6", brightness=0.36, transition_ms=2000),
    "tension": CareColor(hex="#77C7AC", brightness=0.38, transition_ms=1800),
    "anger": CareColor(hex="#68ACB2", brightness=0.32, transition_ms=2500),
    "stress": CareColor(hex="#6C8CAD", brightness=0.34, transition_ms=2200),
    "fatigue": CareColor(hex="#B29E62", brightness=0.30, transition_ms=2800),
    "helplessness": CareColor(hex="#AD8F71", brightness=0.32, transition_ms=2800),
    "confusion": CareColor(hex="#876CAD", brightness=0.34, transition_ms=2200),
    "shame_guilt": CareColor(hex="#BF7C82", brightness=0.32, transition_ms=2600),
}

SLEEP_COLORS: dict[str, CareColor] = {
    # 버킷(고각성/저에너지/관계·수치심/기본값) 구분이 명도·채도 순서로 드러나도록
    # 재배치. hue는 멜라토닌 안전범위(350°~40°) 안에서만 벌림.
    "warm_dim": CareColor(hex="#B86E49", brightness=0.16, transition_ms=6000),
    "deep_amber": CareColor(hex="#993F31", brightness=0.12, transition_ms=8000),
    "soft_peach": CareColor(hex="#D1A96D", brightness=0.14, transition_ms=7000),
    "low_rose": CareColor(hex="#B2626D", brightness=0.13, transition_ms=7000),
}


def get_care_emotion_label(care_emotion: str) -> str:
    return CARE_EMOTION_LABELS.get(care_emotion, CARE_EMOTION_LABELS[FALLBACK_CARE_EMOTION])


def get_realtime_color(care_emotion: str) -> CareColor:
    return REALTIME_COLORS.get(care_emotion, REALTIME_COLORS[FALLBACK_CARE_EMOTION])


def get_sleep_color(sleep_profile: str) -> CareColor:
    return SLEEP_COLORS.get(sleep_profile, SLEEP_COLORS["warm_dim"])
