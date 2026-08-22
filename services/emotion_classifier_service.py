import json
import string
from dataclasses import dataclass

from config import settings
from services import chat_service
from services.color_care_service import (
    ALLOWED_CARE_EMOTIONS,
    FALLBACK_CARE_EMOTION,
    get_care_emotion_label,
)
from services.emotion_session import TurnRecord
from services.openai_client import get_client

MIN_REAL_TRANSCRIPT_LENGTH = 2

CLASSIFIER_SYSTEM_PROMPT = (
    "너는 MoongCare의 실시간 감정 케어 분류기다. "
    "사용자의 발화 텍스트, emotion2vec 전체 점수, pitch 지표, 최근 대화 맥락을 함께 보고 "
    "허용된 care_emotion 중 하나만 고른다. "
    "emotion2vec의 최고 점수를 그대로 복사하지 말고, 발화 의미와 목소리 상태를 함께 해석해. "
    "예를 들어 '발표 끝났어', '일이 끝났어'처럼 부담이 끝난 문맥에서 낮은 톤이나 한숨 때문에 sad 점수가 높게 나오면 "
    "명시적인 슬픔 표현이 없는 한 sadness보다 fatigue 또는 relief를 우선 고려해. "
    "confidence는 emotion2vec 원점수를 그대로 쓰지 말고, 종합 판단의 확신도로 정해. "
    "색상은 만들지 않는다. 반드시 JSON만 반환한다."
)

COMPLETION_KEYWORDS = ("끝났", "끝냈", "끝나", "마쳤", "마무리", "해냈")
SIGH_OR_TIRED_MARKERS = ("하 ", "하,", "하.", "후 ", "휴 ", "아 ", "피곤", "지쳤", "힘들")
SADNESS_KEYWORDS = ("슬프", "속상", "울적", "눈물", "상처", "서운", "가라앉", "상실", "그리워")


@dataclass
class CareEmotionResult:
    care_emotion: str
    care_emotion_label: str
    confidence: float
    reason: str
    fallback: bool = False
    reply_text: str = ""


def _fallback(reason: str, reply_text: str = "") -> CareEmotionResult:
    return CareEmotionResult(
        care_emotion=FALLBACK_CARE_EMOTION,
        care_emotion_label=get_care_emotion_label(FALLBACK_CARE_EMOTION),
        confidence=0.0,
        reason=reason,
        fallback=True,
        reply_text=reply_text,
    )


def _has_real_transcript(transcript: str) -> bool:
    return len(transcript.strip().strip(string.punctuation)) >= MIN_REAL_TRANSCRIPT_LENGTH


def _build_user_payload(
    transcript: str,
    voice_emotion_scores: dict[str, float],
    pitch_mean: float,
    pitch_std: float,
    recent_context: list[dict],
) -> str:
    payload = {
        "transcript": transcript,
        "voice_emotion_scores": voice_emotion_scores,
        "pitch": {"mean": pitch_mean, "std": pitch_std},
        "recent_context": recent_context,
        "allowed_emotions": sorted(ALLOWED_CARE_EMOTIONS),
        "output_schema": {
            "care_emotion": "one of allowed_emotions",
            "confidence": "number between 0 and 1",
            "reason": "short Korean explanation for internal debugging",
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def _looks_like_completed_burden(transcript: str) -> bool:
    return any(keyword in transcript for keyword in COMPLETION_KEYWORDS)


def _has_explicit_sadness(transcript: str) -> bool:
    return any(keyword in transcript for keyword in SADNESS_KEYWORDS)


def _looks_tired(transcript: str, pitch_mean: float) -> bool:
    stripped = transcript.strip()
    return pitch_mean > 0 and pitch_mean < 120 or any(marker in stripped for marker in SIGH_OR_TIRED_MARKERS)


def _adjust_result(
    result: CareEmotionResult,
    transcript: str,
    voice_emotion_scores: dict[str, float],
    pitch_mean: float,
) -> CareEmotionResult:
    if result.fallback:
        return result

    if not _looks_like_completed_burden(transcript) or _has_explicit_sadness(transcript):
        return result

    happy_score = voice_emotion_scores.get("happy", 0.0)
    if happy_score >= 0.8 and result.care_emotion in {"relief", "calm", "sadness", "fatigue"}:
        return CareEmotionResult(
            care_emotion="joy",
            care_emotion_label=get_care_emotion_label("joy"),
            confidence=max(result.confidence, min(happy_score, 0.95)),
            reason=(
                "completed burden context with very high happy raw score; "
                "adjusted to joy for positive completion"
            ),
            fallback=False,
            reply_text=result.reply_text,
        )

    if result.care_emotion != "sadness":
        return result

    sad_score = voice_emotion_scores.get("sad", 0.0)
    if sad_score < 0.8:
        return result

    adjusted_emotion = "fatigue" if _looks_tired(transcript, pitch_mean) else "relief"
    return CareEmotionResult(
        care_emotion=adjusted_emotion,
        care_emotion_label=get_care_emotion_label(adjusted_emotion),
        confidence=min(result.confidence, 0.78) if result.confidence else 0.72,
        reason=(
            "sad raw score was high, but transcript indicates a completed burden without explicit sadness; "
            f"adjusted to {adjusted_emotion}"
        ),
        fallback=False,
        reply_text=result.reply_text,
    )


def _parse_response(content: str, include_reply: bool = False) -> CareEmotionResult:
    fallback_reply = chat_service.FALLBACK_REPLY if include_reply else ""

    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        return _fallback("classifier returned invalid json", reply_text=fallback_reply)

    care_emotion = data.get("care_emotion")
    if care_emotion not in ALLOWED_CARE_EMOTIONS:
        return _fallback("classifier returned unsupported care_emotion", reply_text=fallback_reply)

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        return _fallback("classifier returned invalid confidence", reply_text=fallback_reply)

    confidence = max(0.0, min(1.0, confidence))
    reason = str(data.get("reason", ""))
    reply_text = str(data.get("reply_text") or fallback_reply) if include_reply else ""
    return CareEmotionResult(
        care_emotion=care_emotion,
        care_emotion_label=get_care_emotion_label(care_emotion),
        confidence=confidence,
        reason=reason,
        fallback=False,
        reply_text=reply_text,
    )


def classify_realtime_emotion(
    transcript: str,
    voice_emotion_scores: dict[str, float],
    pitch_mean: float,
    pitch_std: float,
    recent_context: list[dict],
) -> CareEmotionResult:
    if not _has_real_transcript(transcript):
        return _fallback("transcript is too short")

    messages = [
        {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _build_user_payload(
                transcript,
                voice_emotion_scores,
                pitch_mean,
                pitch_std,
                recent_context,
            ),
        },
    ]

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
    except Exception:
        return _fallback("classifier call failed")

    result = _parse_response(response.choices[0].message.content)
    return _adjust_result(result, transcript, voice_emotion_scores, pitch_mean)


COMBINED_OUTPUT_SCHEMA = {
    "care_emotion": "one of allowed_emotions",
    "confidence": "number between 0 and 1",
    "reason": "short Korean explanation for internal debugging",
    "reply_text": "2~3 short Korean sentences replying to the user, following the persona/tone instructions above",
}


def _combined_system_prompt(style: str) -> str:
    persona_prompt = chat_service.SYSTEM_PROMPTS.get(style, chat_service.SYSTEM_PROMPTS[chat_service.DEFAULT_STYLE])
    return (
        f"{persona_prompt}\n\n{CLASSIFIER_SYSTEM_PROMPT}\n\n"
        "위 두 역할(공감 캐릭터로서 답변 생성 + 감정 케어 분류)을 동시에 수행해. "
        "반드시 JSON 하나만 반환하고, care_emotion/confidence/reason/reply_text 네 필드를 모두 포함해."
    )


def _build_combined_messages(
    history: list[TurnRecord],
    transcript: str,
    voice_emotion_scores: dict[str, float],
    pitch_mean: float,
    pitch_std: float,
    style: str,
) -> list[dict]:
    messages = [{"role": "system", "content": _combined_system_prompt(style)}]
    for turn in history:
        role = "user" if turn.role == "user" else "assistant"
        content = turn.text
        if role == "user" and turn.care_emotion:
            content = f"[케어 감정: {turn.care_emotion}] {content}"
        messages.append({"role": role, "content": content})

    payload = {
        "transcript": transcript,
        "voice_emotion_scores": voice_emotion_scores,
        "pitch": {"mean": pitch_mean, "std": pitch_std},
        "allowed_emotions": sorted(ALLOWED_CARE_EMOTIONS),
        "output_schema": COMBINED_OUTPUT_SCHEMA,
    }
    messages.append({"role": "user", "content": json.dumps(payload, ensure_ascii=False)})
    return messages


def classify_and_reply(
    transcript: str,
    voice_emotion_scores: dict[str, float],
    pitch_mean: float,
    pitch_std: float,
    history: list[TurnRecord],
    style: str = chat_service.DEFAULT_STYLE,
) -> CareEmotionResult:
    if not _has_real_transcript(transcript):
        return _fallback("transcript is too short", reply_text=chat_service.FALLBACK_REPLY)

    messages = _build_combined_messages(history, transcript, voice_emotion_scores, pitch_mean, pitch_std, style)

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
        )
    except Exception:
        return _fallback("classifier+reply call failed", reply_text=chat_service.FALLBACK_REPLY)

    result = _parse_response(response.choices[0].message.content, include_reply=True)
    return _adjust_result(result, transcript, voice_emotion_scores, pitch_mean)
