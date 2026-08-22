"""SER 9클래스 -> care_emotion 14클래스 + LED 색상 매핑.

서버(/api/v1/voice/analyze)는 emotion2vec 기준 9개 클래스만 돌려줍니다.
    angry, disgusted, fearful, happy, neutral, other, sad, surprised, unknown

기획서의 care_emotion 은 14개라서 1:1 대응이 안 됩니다.
그래서 여기서 세 가지 신호를 합쳐 14개 중 하나로 좁힙니다.

    1) SER 확률분포 (가장 큰 가중치)
    2) 전사 텍스트 키워드 (외로움 / 피로 / 자책 처럼 음성만으로는 구분 불가한 것)
    3) 피치 통계 (pitch_std 가 크면 각성도 높음 -> joy 대신 excitement 등)

이 파일만 고치면 매핑 규칙 전체를 튜닝할 수 있습니다.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 기획서 표 그대로
# ---------------------------------------------------------------------------
CARE_COLORS: dict[str, dict] = {
    "calm":         {"label": "평온",       "hex": "#A7CDBD", "brightness": 0.42, "transition_ms": 1600},
    "joy":          {"label": "기쁨/만족",  "hex": "#F6C66D", "brightness": 0.50, "transition_ms": 1200},
    "excitement":   {"label": "설렘/들뜸",  "hex": "#BFD8FF", "brightness": 0.44, "transition_ms": 1800},
    "relief":       {"label": "안도",       "hex": "#B8E0C8", "brightness": 0.42, "transition_ms": 1800},
    "sadness":      {"label": "슬픔",       "hex": "#F2B6A0", "brightness": 0.38, "transition_ms": 2200},
    "loneliness":   {"label": "외로움",     "hex": "#E8B7D4", "brightness": 0.35, "transition_ms": 2400},
    "anxiety":      {"label": "불안",       "hex": "#8DB7D9", "brightness": 0.36, "transition_ms": 2000},
    "tension":      {"label": "긴장",       "hex": "#7DCAC3", "brightness": 0.38, "transition_ms": 1800},
    "anger":        {"label": "분노/짜증",  "hex": "#86BFA6", "brightness": 0.32, "transition_ms": 2500},
    "stress":       {"label": "스트레스/과부하", "hex": "#91B7A8", "brightness": 0.34, "transition_ms": 2200},
    "fatigue":      {"label": "피로",       "hex": "#F0B06A", "brightness": 0.30, "transition_ms": 2800},
    "helplessness": {"label": "무기력",     "hex": "#D9B8A6", "brightness": 0.32, "transition_ms": 2800},
    "confusion":    {"label": "혼란/당황",  "hex": "#B6B4D8", "brightness": 0.34, "transition_ms": 2200},
    "shame_guilt":  {"label": "자책/민망함", "hex": "#D8A6A1", "brightness": 0.32, "transition_ms": 2600},
}

# ---------------------------------------------------------------------------
# 1) SER 클래스 -> care_emotion 가중치
# ---------------------------------------------------------------------------
SER_TO_CARE: dict[str, dict[str, float]] = {
    "happy":     {"joy": 1.00, "excitement": 0.55, "relief": 0.30, "calm": 0.20},
    "sad":       {"sadness": 1.00, "loneliness": 0.55, "helplessness": 0.45, "fatigue": 0.30},
    "angry":     {"anger": 1.00, "stress": 0.65, "tension": 0.35},
    "disgusted": {"anger": 0.80, "stress": 0.55, "shame_guilt": 0.30},
    "fearful":   {"anxiety": 1.00, "tension": 0.70, "confusion": 0.35},
    "surprised": {"excitement": 0.80, "confusion": 0.70, "tension": 0.35},
    "neutral":   {"calm": 1.00, "fatigue": 0.35, "relief": 0.30},
    "other":     {"calm": 0.50, "confusion": 0.35},
    "unknown":   {"calm": 0.50},
}

# ---------------------------------------------------------------------------
# 2) 전사 키워드 -> care_emotion 보너스
#    음성 톤만으로는 "슬픔"과 "외로움"이 구분되지 않으므로 말의 내용으로 좁힙니다.
# ---------------------------------------------------------------------------
KEYWORD_BONUS: list[tuple[tuple[str, ...], str, float]] = [
    (("외로", "혼자", "쓸쓸", "아무도", "보고 싶", "그리워"),           "loneliness",   0.85),
    (("피곤", "졸리", "지쳐", "지쳤", "잠 못", "못 잤", "하품", "힘 빠"), "fatigue",      0.85),
    (("무기력", "의욕", "하기 싫", "아무것도", "귀찮", "손에 안 잡"),     "helplessness", 0.85),
    (("미안", "죄송", "내 탓", "잘못", "창피", "부끄", "민망", "후회"),   "shame_guilt",  0.85),
    (("모르겠", "헷갈", "어떡", "당황", "정신 없", "복잡"),              "confusion",    0.75),
    (("다행", "괜찮아졌", "끝났", "해결", "덜었", "후련"),               "relief",       0.80),
    (("바쁘", "일이 많", "부담", "마감", "쫓기", "밀렸", "벅차"),        "stress",       0.80),
    (("긴장", "떨려", "떨린", "발표", "면접", "시험"),                   "tension",      0.80),
    (("불안", "걱정", "무서", "두려"),                                   "anxiety",      0.80),
    (("설레", "기대", "신나", "두근"),                                   "excitement",   0.80),
    (("짜증", "화가", "빡", "열받", "억울"),                             "anger",        0.80),
    (("슬퍼", "슬프", "울었", "눈물", "속상"),                           "sadness",      0.80),
    (("행복", "즐거", "좋았", "만족", "뿌듯"),                           "joy",          0.80),
    (("편안", "평온", "차분", "여유"),                                   "calm",         0.70),
]

# 각성도(arousal)가 낮게 나온 감정 / 높게 나온 감정
HIGH_AROUSAL = {"excitement", "anger", "tension", "anxiety", "joy"}
LOW_AROUSAL = {"fatigue", "helplessness", "calm", "sadness", "loneliness"}

DEFAULT_CARE = "calm"

# 키워드가 SER 톤 판정을 뒤집을 수 있는 정도. 낮추면 목소리 톤 위주가 됩니다.
KEYWORD_WEIGHT = 1.0


def _keyword_scores(transcript: str) -> dict[str, float]:
    text = (transcript or "").replace(" ", "")
    scores: dict[str, float] = {}
    for words, care, weight in KEYWORD_BONUS:
        for w in words:
            if w.replace(" ", "") in text:
                scores[care] = max(scores.get(care, 0.0), weight)
                break
    return scores


def _arousal_factor(pitch_mean: float, pitch_std: float) -> float:
    """-1.0(축 처짐) ~ +1.0(들뜸). 값이 0이면 판단 불가."""
    if not pitch_mean or pitch_mean <= 0:
        return 0.0
    # 한국어 평균 발화 피치 대략 100(남)~220(여). 표준편차 25 근처가 보통.
    std_part = (pitch_std - 25.0) / 25.0
    return max(-1.0, min(1.0, std_part))


def map_care_emotion(
    emotions: dict[str, float],
    transcript: str = "",
    pitch_mean: float = 0.0,
    pitch_std: float = 0.0,
) -> tuple[str, float, dict[str, float]]:
    """(care_emotion, confidence, 전체 점수표) 반환."""
    scores: dict[str, float] = {k: 0.0 for k in CARE_COLORS}

    # 1) SER 분포 반영
    for ser_cls, prob in (emotions or {}).items():
        for care, w in SER_TO_CARE.get(ser_cls, {}).items():
            scores[care] += prob * w

    # 2) 키워드 반영.
    #    "슬픔 vs 외로움 vs 자책"처럼 톤만으로는 못 가르는 것을 말의 내용이
    #    뒤집을 수 있어야 하므로 SER 최대값(1.0)과 맞먹는 스케일을 줍니다.
    for care, bonus in _keyword_scores(transcript).items():
        scores[care] += bonus * KEYWORD_WEIGHT

    # 3) 각성도 보정
    arousal = _arousal_factor(pitch_mean, pitch_std)
    if arousal:
        for care in scores:
            if care in HIGH_AROUSAL:
                scores[care] += arousal * 0.15
            elif care in LOW_AROUSAL:
                scores[care] -= arousal * 0.15

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if ranked[0][1] <= 0:
        return DEFAULT_CARE, 0.0, scores

    care, top = ranked[0]
    second = max(0.0, ranked[1][1]) if len(ranked) > 1 else 0.0
    # 1위가 2위를 얼마나 앞서는가 = 0.5(박빙) ~ 1.0(압도적)
    confidence = round(top / (top + second), 2) if (top + second) > 0 else 1.0
    return care, confidence, scores


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def care_payload(
    emotions: dict[str, float],
    transcript: str = "",
    pitch_mean: float = 0.0,
    pitch_std: float = 0.0,
) -> dict:
    """기획서 JSON 형태 그대로 만들어 줍니다."""
    care, conf, _ = map_care_emotion(emotions, transcript, pitch_mean, pitch_std)
    spec = CARE_COLORS[care]
    return {
        "transcript": transcript,
        "emotions": emotions,
        "pitch_mean": pitch_mean,
        "pitch_std": pitch_std,
        "care_emotion": care,
        "care_emotion_label": spec["label"],
        "care_confidence": conf,
        "care_color": {
            "hex": spec["hex"],
            "brightness": spec["brightness"],
            "transition_ms": spec["transition_ms"],
        },
    }
