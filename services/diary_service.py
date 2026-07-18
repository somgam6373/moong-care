from services.emotion_session import TurnRecord
from services.anthropic_client import get_client
from config import settings

DIARY_SYSTEM_PROMPT = (
    "너는 사용자 본인이 되어 오늘 하루를 되돌아보는 1인칭 일기를 쓰는 작가야. "
    "아래 대화 내용과 감정 데이터를 참고해서, 사용자가 직접 쓴 것처럼 자연스러운 "
    "1인칭 일기를 3~5문장으로 작성해."
)


def _format_conversation(history: list[TurnRecord]) -> str:
    lines = []
    for turn in history:
        speaker = "나" if turn.role == "user" else "뭉이"
        lines.append(f"{speaker}: {turn.text}")
    return "\n".join(lines)


def generate_diary(history: list[TurnRecord], average_emotions: dict[str, float]) -> str:
    client = get_client()
    conversation = _format_conversation(history)
    dominant = max(average_emotions, key=average_emotions.get) if average_emotions else "neutral"
    user_prompt = (
        f"오늘의 대화:\n{conversation}\n\n"
        f"오늘의 대표 감정: {dominant}\n"
        f"감정 평균 점수: {average_emotions}"
    )
    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=1024,
        system=DIARY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return next(block.text for block in response.content if block.type == "text")
