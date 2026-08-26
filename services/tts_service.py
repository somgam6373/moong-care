from collections.abc import Iterator

from services.emotion_session import get_last_user_emotion
from services.openai_client import get_client

TTS_MODEL = "gpt-4o-mini-tts"

EMOTION_INSTRUCTIONS: dict[str, str] = {
    "angry": "Speak in a calm, soothing, de-escalating tone.",
    "disgusted": "Speak in a calm, neutral, non-judgmental tone.",
    "fearful": "Speak in a reassuring, steady, gentle tone.",
    "happy": "Speak in a bright, cheerful, warm tone.",
    "neutral": "Speak in a natural, warm, conversational tone.",
    "other": "Speak in a natural, warm, conversational tone.",
    "sad": "Speak in a warm, gentle, comforting tone, as if empathizing with someone who's feeling sad.",
    "surprised": "Speak in an animated, curious, engaged tone.",
    "unknown": "Speak in a natural, warm, conversational tone.",
}


def resolve_instructions(session_id: str | None) -> str:
    emotions = get_last_user_emotion(session_id) if session_id else None
    if not emotions:
        return EMOTION_INSTRUCTIONS["neutral"]
    dominant = max(emotions, key=emotions.get)
    return EMOTION_INSTRUCTIONS.get(dominant, EMOTION_INSTRUCTIONS["neutral"])


def synthesize_stream(text: str, voice: str, instructions: str) -> Iterator[bytes]:
    client = get_client()
    with client.audio.speech.with_streaming_response.create(
        model=TTS_MODEL,
        voice=voice,
        input=text,
        instructions=instructions,
        response_format="wav",
    ) as response:
        yield from response.iter_bytes()
