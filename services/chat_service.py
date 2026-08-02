import string

from services.emotion_session import TurnRecord
from services.openai_client import get_client
from config import settings

MIN_TRANSCRIPT_LENGTH = 2
FALLBACK_REPLY = "음... 잘 못 들었어. 다시 한 번 말해줄래?"

EMPATHETIC_SYSTEM_PROMPT = (
    "너는 '뭉이'라는 이름의 따뜻하고 다정한 감정 케어 캐릭터야. "
    "사용자의 하루 이야기를 들어주고 공감하며, 짧고 자연스러운 구어체로 응답해. "
    "사용자의 현재 감정 상태를 참고해서 그 감정에 맞는 공감 반응을 먼저 보여줘. "
    "그 다음, 사용자가 방금 말한 구체적인 내용(예: 무엇을 했는지, 누구와 있었는지, "
    "몇 번이나 그랬는지 등)을 언급하면서 사용자가 더 이야기를 이어갈 수 있도록 "
    "짧은 후속 질문을 반드시 하나 덧붙여. "
    "'힘내자', '괜찮아질 거야' 같은 상투적인 위로 문구로 대화를 마무리 짓지 말고, "
    "대화가 계속 이어지도록 자연스럽게 반응해. "
    "한 번에 2~3문장 이내로 짧게 대답해."
)

REALISTIC_SYSTEM_PROMPT = (
    "너는 '뭉이'라는 이름의 감정 케어 캐릭터야. 다정하지만 현실적이고 담백한 태도로 "
    "짧고 자연스러운 구어체로 응답해. "
    "사용자의 현재 감정 상태를 가볍게 인지하되, 감정을 과하게 위로하거나 다독이기보다는 "
    "상황을 객관적으로 짚어주고 도움이 될 만한 관점이나 구체적인 제안을 제시해. "
    "사용자가 방금 말한 구체적인 내용을 언급하면서, 문제를 정리하거나 다음에 어떻게 "
    "해볼 수 있을지에 대한 짧은 후속 질문이나 제안을 반드시 하나 덧붙여. "
    "'힘내자', '괜찮아질 거야' 같은 상투적인 위로 문구는 쓰지 말고, "
    "감정보다는 사실과 해결책 중심으로 담백하게 반응해. "
    "한 번에 2~3문장 이내로 짧게 대답해."
)

SYSTEM_PROMPTS = {
    "empathetic": EMPATHETIC_SYSTEM_PROMPT,
    "realistic": REALISTIC_SYSTEM_PROMPT,
}
DEFAULT_STYLE = "empathetic"


def build_messages(
    history: list[TurnRecord],
    transcript: str,
    emotions: dict[str, float],
    style: str = DEFAULT_STYLE,
) -> list[dict]:
    system_prompt = SYSTEM_PROMPTS.get(style, SYSTEM_PROMPTS[DEFAULT_STYLE])
    messages = [{"role": "system", "content": system_prompt}]
    for turn in history:
        role = "user" if turn.role == "user" else "assistant"
        content = turn.text
        if role == "user" and turn.emotions:
            past_dominant = max(turn.emotions, key=turn.emotions.get)
            content = f"[감정: {past_dominant}] {content}"
        messages.append({"role": role, "content": content})
    dominant = max(emotions, key=emotions.get) if emotions else "neutral"
    messages.append({
        "role": "user",
        "content": f"[현재 감정: {dominant}] {transcript}",
    })
    return messages


def get_reply(
    history: list[TurnRecord],
    transcript: str,
    emotions: dict[str, float],
    style: str = DEFAULT_STYLE,
) -> str:
    if len(transcript.strip().strip(string.punctuation)) < MIN_TRANSCRIPT_LENGTH:
        return FALLBACK_REPLY

    client = get_client()
    messages = build_messages(history, transcript, emotions, style)
    response = client.chat.completions.create(model=settings.OPENAI_MODEL, messages=messages)
    return response.choices[0].message.content
