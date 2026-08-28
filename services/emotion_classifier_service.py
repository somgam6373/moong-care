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


def _has_hangul(text: str) -> bool:
    return any("가" <= ch <= "힣" for ch in text)

CLASSIFIER_SYSTEM_PROMPT = (
    "너는 MoongCare의 실시간 감정 케어 분류기다. "
    "사용자의 발화 텍스트, emotion2vec 전체 점수, pitch 지표, 최근 대화 맥락을 함께 보고 "
    "허용된 care_emotion 중 하나만 고른다.\n\n"
    "판단은 반드시 아래 순서로 해.\n\n"
    "1단계 — 텍스트-음성 충돌 여부부터 확인해. emotion2vec 점수에서 disgusted, angry, "
    "sad 중 하나가 1순위 또는 2순위이고 그 값이 대략 0.3 이상인가?\n"
    "- 아니오라면: 이 규칙은 적용하지 않는다. 텍스트가 칭찬/감사/인정 같은 긍정적인 "
    "표현이면 무조건 그대로 존중해서 joy/calm/relief/excitement 계열을 우선 고려해. "
    "surprised가 1순위로 아무리 높게 나와도 그 자체는 반어법의 증거가 아니다 — "
    "disgusted/angry/sad가 실제로 이 turn 점수에 없다면 의심할 근거가 없는 것이다. "
    "'예전에 비슷한 문장을 의심했었다'는 기억으로 이번 turn을 의심하지 마라. 근거 없이 "
    "반어법이나 비꼼을 추측해서 reason에 쓰지 마라.\n"
    "- 예라면: 텍스트가 칭찬/감사/인정하는 긍정적인 표현인지 확인해. 그렇다면 텍스트를 "
    "문자 그대로 믿지 마라 — 반어법/비꼼이거나 진심이 아닌 칭찬일 가능성이 높다는 신호다. "
    "이때는 anger, stress, confusion, shame_guilt 중 하나만 골라라. sadness나 "
    "helplessness처럼 순수한 슬픔·무기력 계열로는 절대 가지 마라 — 반어법/비꼼은 슬픔이 "
    "아니라 짜증·불쾌·당혹감에 가깝다. (disgusted/angry 같은 emotion2vec 라벨 이름 "
    "자체를 care_emotion에 그대로 쓰면 안 된다 — 반드시 allowed_emotions 목록의 단어만 써라.)\n\n"
    "2단계 — 1순위만 보지 말고 2순위도 같이 봐. 예를 들어 surprised가 1순위여도 2순위가 "
    "happy면 '기쁜 놀람/설렘'에 가깝고, 2순위가 fearful/sad/disgusted처럼 부정적이면 "
    "놀람 속에 불안이나 불쾌가 섞여 있다고 봐야 해. 단, 2순위 점수가 대략 0.1 미만이면 "
    "사실상 잡음이니 무시해도 된다.\n\n"
    "3단계 — 부담이 끝난 문맥('발표 끝났어', '일이 끝났어' 등)에서 낮은 톤이나 한숨 "
    "때문에 sad 점수가 높게 나오면, 명시적인 슬픔 표현이 없는 한 sadness보다 fatigue "
    "또는 relief를 우선 고려해.\n\n"
    "4단계 — 위 상황들에 해당하지 않으면 텍스트 의미와 목소리 상태를 균형 있게 함께 "
    "해석해.\n\n"
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
        return _fallback(
            f"classifier returned unsupported care_emotion: {care_emotion!r}",
            reply_text=fallback_reply,
        )

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
    "reply_text": "2~3 short sentences replying to the user in the SAME LANGUAGE as the transcript, following the persona/tone instructions above",
}


def _combined_system_prompt(style: str) -> str:
    persona_prompt = chat_service.SYSTEM_PROMPTS.get(style, chat_service.SYSTEM_PROMPTS[chat_service.DEFAULT_STYLE])
    return (
        f"{persona_prompt}\n\n{CLASSIFIER_SYSTEM_PROMPT}\n\n"
        "위 두 역할(공감 캐릭터로서 답변 생성 + 감정 케어 분류)을 동시에 수행해. "
        "reply_text는 반드시 네가 고른 care_emotion과 같은 해석을 따라야 해 — "
        "겉으로는 칭찬처럼 들려도 care_emotion을 부정적으로(anger/stress/confusion/shame_guilt 등) "
        "판단했다면, reply_text도 문자 그대로 감사 인사를 하지 말고 그 판단에 맞게 "
        "조심스럽게 서운함이나 진심을 확인하는 톤으로 반응해. "
        "IMPORTANT: reply_text MUST be written in the same language as the user's transcript below "
        "(e.g. if the transcript is in English, reply_text must be in English, not Korean). "
        "reason은 내부 디버깅용이니 한국어로 써도 되지만, reply_text는 반드시 transcript 언어를 따라라. "
        "payload의 recent_reply_had_question이 true면, 직전에 이미 질문을 했다는 뜻이야 — "
        "이번 reply_text는 절대 질문으로 만들지 말고(물음표로 끝내지 마) 공감/반응/의견만 말해. "
        "'공감 한마디 + 질문'을 매번 반복하는 로봇 같은 패턴은 피해 — "
        "때로는 질문 없이 네 생각이나 의견을 짧게 말하거나, 사용자 말에 자연스럽게 리액션만 하거나, "
        "화제를 이어받아 네 얘기를 살짝 보태는 식으로 사람 친구랑 티키타카하듯 반응 방식을 다양하게 바꿔가며 응답해. "
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

    last_assistant_text = next((t.text for t in reversed(history) if t.role == "assistant"), "")
    recent_reply_had_question = last_assistant_text.rstrip().endswith("?")

    payload = {
        "transcript": transcript,
        "voice_emotion_scores": voice_emotion_scores,
        "pitch": {"mean": pitch_mean, "std": pitch_std},
        "allowed_emotions": sorted(ALLOWED_CARE_EMOTIONS),
        "recent_reply_had_question": recent_reply_had_question,
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
            temperature=0.3,
            response_format={"type": "json_object"},
        )
    except Exception:
        return _fallback("classifier+reply call failed", reply_text=chat_service.FALLBACK_REPLY)

    result = _parse_response(response.choices[0].message.content, include_reply=True)

    # ponytail: heuristic Hangul-presence check, not a real language detector;
    # upgrade to langdetect if transcripts start mixing languages within one sentence.
    if _has_hangul(transcript) != _has_hangul(result.reply_text):
        target_lang = "한국어" if _has_hangul(transcript) else "영어(English)"
        try:
            retry_messages = messages + [
                {"role": "assistant", "content": response.choices[0].message.content},
                {
                    "role": "user",
                    "content": f"reply_text 언어가 틀렸어. transcript는 {target_lang}야. "
                    f"reply_text를 반드시 {target_lang}로만 다시 써서 같은 JSON 형식으로 반환해. "
                    "다른 필드는 그대로 유지해.",
                },
            ]
            retry_response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=retry_messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            retry_result = _parse_response(retry_response.choices[0].message.content, include_reply=True)
            if _has_hangul(transcript) == _has_hangul(retry_result.reply_text):
                result = retry_result
        except Exception:
            pass

    return _adjust_result(result, transcript, voice_emotion_scores, pitch_mean)
