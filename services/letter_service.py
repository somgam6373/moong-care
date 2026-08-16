import json

from config import settings
from services.emotion_session import TurnRecord
from services.openai_client import get_client

LETTER_SYSTEM_PROMPT = (
    "너는 '뭉이'라는 이름의 다정한 감정 케어 캐릭터야. "
    "사용자에게 오늘 대화를 바탕으로 짧은 편지를 써. "
    "감정을 진단하거나 치료한다고 말하지 말고, 대화에서 관찰된 감정 흐름을 부드럽게 표현해. "
    "사용자가 말한 구체적 사건을 반영하고, 마지막에는 수면 전 무드등 색상을 자연스럽게 언급해. "
    "5~8문장으로 작성해."
)


def _format_conversation(history: list[TurnRecord]) -> str:
    lines = []
    for turn in history:
        speaker = "사용자" if turn.role == "user" else "뭉이"
        lines.append(f"{speaker}: {turn.text}")
    return "\n".join(lines)


def generate_letter(
    history: list[TurnRecord],
    average_emotions: dict[str, float],
    dominant_care_emotion: str,
    care_timeline: list[dict],
    sleep_color: dict | None,
) -> str:
    client = get_client()
    payload = {
        "conversation": _format_conversation(history),
        "average_voice_emotions": average_emotions,
        "dominant_care_emotion": dominant_care_emotion,
        "care_timeline": care_timeline,
        "sleep_color": sleep_color,
    }
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": LETTER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    return response.choices[0].message.content
