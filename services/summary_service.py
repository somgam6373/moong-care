from services.anthropic_client import get_client
from config import settings

SUMMARY_SYSTEM_PROMPT = "아래 일기를 한 문장으로 요약해. 반드시 한 줄로만 답해."


def summarize_diary(diary_text: str) -> str:
    client = get_client()
    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=256,
        system=SUMMARY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": diary_text}],
    )
    return next(block.text for block in response.content if block.type == "text")
