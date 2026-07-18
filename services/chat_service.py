import string

from services.emotion_session import TurnRecord
from services.openai_client import get_client
from config import settings

MIN_TRANSCRIPT_LENGTH = 2
FALLBACK_REPLY = "음... 잘 못 들었어. 다시 한 번 말해줄래?"

MOONG_SYSTEM_PROMPT = (
    "너는 '뭉이'라는 이름의 따뜻하고 다정한 감정 케어 캐릭터야. "
    "사용자의 하루 이야기를 들어주고 공감하며, 짧고 자연스러운 구어체로 응답해. "
    "사용자의 현재 감정 상태를 참고해서 그 감정에 맞는 위로나 반응을 보여줘. "
    "한 번에 2~3문장 이내로 짧게 대답해."
)


def build_messages(
    history: list[TurnRecord], transcript: str, emotions: dict[str, float]
) -> list[dict]:
    messages = [{"role": "system", "content": MOONG_SYSTEM_PROMPT}]
    for turn in history:
        role = "user" if turn.role == "user" else "assistant"
        messages.append({"role": role, "content": turn.text})
    dominant = max(emotions, key=emotions.get) if emotions else "neutral"
    messages.append({
        "role": "user",
        "content": f"[현재 감정: {dominant}] {transcript}",
    })
    return messages


def get_reply(history: list[TurnRecord], transcript: str, emotions: dict[str, float]) -> str:
    if len(transcript.strip().strip(string.punctuation)) < MIN_TRANSCRIPT_LENGTH:
        return FALLBACK_REPLY

    client = get_client()
    messages = build_messages(history, transcript, emotions)
    response = client.chat.completions.create(model=settings.OPENAI_MODEL, messages=messages)
    return response.choices[0].message.content
