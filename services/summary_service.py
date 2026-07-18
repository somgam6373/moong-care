from services.openai_client import get_client
from config import settings

SUMMARY_SYSTEM_PROMPT = "아래 일기를 한 문장으로 요약해. 반드시 한 줄로만 답해."


def summarize_diary(diary_text: str) -> str:
    client = get_client()
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": diary_text},
        ],
    )
    return response.choices[0].message.content
