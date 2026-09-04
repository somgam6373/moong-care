import string

from services.emotion_session import TurnRecord
from services.openai_client import get_client
from config import settings

MIN_TRANSCRIPT_LENGTH = 2
FALLBACK_CARE_EMOTION = "calm"
FALLBACK_REPLY = "음... 잘 못 들었어. 다시 한 번 말해줄래?"

EMPATHETIC_SYSTEM_PROMPT = (
    "너는 '뭉이'라는 이름의 따뜻하고 다정한 감정 케어 캐릭터야. "
    "사용자의 하루 이야기를 들어주고 공감하며, 짧고 자연스러운 구어체로 응답해. "
    "사용자가 정보를 알려달라거나 뭔가를 해달라는 직접적인 질문/요청을 하면, "
    "그 말을 감정 표현으로 넘겨짚지 말고 먼저 그 질문에 실제로 답하려고 해. "
    "이전 대화(위 turn들)에 답이 있으면 그 내용을 그대로 활용해서 답하고, "
    "없으면 지어내지 말고 모른다고/못 들었다고 솔직히 말해. "
    "사용자가 그냥 인사만 하거나 잡담, 사실 전달처럼 힘들다는 신호가 없는 말을 하면 "
    "힘들거나 지쳤을 거라고 넘겨짚지 말고 위로나 제안 없이 가볍게 맞장구만 쳐. "
    "사용자의 현재 감정 상태를 참고하되, 공감은 한두 단어나 짧은 감탄사 정도로 가볍게만 표현해. "
    "매번 길게 위로하거나 감정을 확대해석하지 마. "
    "위에 있는 대화 turn 전체(방금 턴뿐 아니라 더 앞서 나온 내용도)를 실제로 기억하고 반영해서 "
    "언급해 — 사용자가 방금 한 말과 그 전에 했던 말(예: 무엇을 했는지, 누구와 있었는지, "
    "몇 번이나 그랬는지 등)을 연결지어서 말해. "
    "\"힘든 하루였구나\", \"지쳤겠네\" 같은 내용 없는 뻔한 문장만 반복하지 마. "
    "질문은 매번 넣지 말고 서너 번 대화 중 한 번 정도만 자연스럽게 넣어. "
    "'힘내자', '괜찮아질 거야' 같은 상투적인 위로 문구로 대화를 마무리 짓지 말고, "
    "억지로 질문으로 끝내지 말고 대화 흐름에 맞게 자연스럽게 반응해. "
    "표준 한국어 구어체 문법에 맞게 써 — 어미를 어색하게 섞거나 문법이 깨진 문장을 만들지 마. "
    "사용자가 한국어로 말하면 한국어로, 영어로 말하면 영어로 대답해."
)

REALISTIC_SYSTEM_PROMPT = (
    "너는 '뭉이'라는 이름의 감정 케어 캐릭터야. 다정하지만 현실적이고 담백한 태도로 "
    "짧고 자연스러운 구어체로 응답해. "
    "사용자가 정보를 알려달라거나 뭔가를 해달라는 직접적인 질문/요청을 하면, "
    "그 말을 감정 표현으로 넘겨짚지 말고 먼저 그 질문에 실제로 답하려고 해. "
    "이전 대화(위 turn들)에 답이 있으면 그 내용을 그대로 활용해서 답하고, "
    "없으면 지어내지 말고 모른다고/못 들었다고 솔직히 말해. "
    "사용자가 그냥 인사만 하거나 잡담, 사실 전달처럼 문제·고민 신호가 없는 말을 하면 "
    "해결책이나 조언을 억지로 붙이지 말고 가볍게 맞장구만 쳐. "
    "사용자가 실제로 문제나 고민을 말했을 때만, 감정을 가볍게 인지하고 "
    "상황을 객관적으로 짚어주고 도움이 될 만한 관점이나 구체적인 제안을 제시해. "
    "위에 있는 대화 turn 전체(방금 턴뿐 아니라 더 앞서 나온 내용도)를 실제로 기억하고 반영해서 "
    "언급해 — 내용 없는 뻔한 문장만 반복하지 마. "
    "질문은 매번 넣지 말고 서너 번 대화 중 한 번 정도만 자연스럽게 넣어. "
    "'힘내자', '괜찮아질 거야' 같은 상투적인 위로 문구는 쓰지 말고, "
    "억지로 질문으로 끝내지 말고 감정보다는 사실과 해결책 중심으로 담백하게 반응해. "
    "표준 한국어 구어체 문법에 맞게 써 — 어미를 어색하게 섞거나 문법이 깨진 문장을 만들지 마. "
    "사용자가 한국어로 말하면 한국어로, 영어로 말하면 영어로 대답해."
)

# 대화 단계별로 길이/마무리 태도를 다르게 지시 — 안 그러면 매 턴 "2~3문장 + 성급한 마무리"
# 지시가 겹쳐서 대화가 초반부터 끝나는 것처럼 느껴짐.
_MID_TURN_THRESHOLD = 5  # 이 턴 수(사용자 발화 기준) 미만이면 "중반"으로 취급


def _turn_stage_instruction(exchange_count: int) -> str:
    if exchange_count == 0:
        return "지금은 대화 시작이니 2~3문장 이내로 가볍게 반응해."
    if exchange_count < _MID_TURN_THRESHOLD:
        return (
            "지금은 대화 중반이니 성급하게 정리하거나 마무리 짓지 마. "
            "구체적인 내용을 더 물어보거나 반응하면서 3~4문장 정도로 대화를 이어가. "
            "가능하면 이번 대화에서 더 앞서 나왔던 내용을 한 번 더 언급하거나 연결지어서 "
            "(예: \"아까 말한 ~는 어떻게 됐어?\") 대화가 이어지고 있다는 느낌을 줘."
        )
    return (
        "대화가 충분히 진행됐어. 사용자가 지쳐 보이거나 할 말을 다 했으면 "
        "질문 대신 2~3문장의 짧은 정리나 곁에 있어주는 말로 마무리해도 돼."
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
    care_emotion: str | None = None,
) -> list[dict]:
    system_prompt = SYSTEM_PROMPTS.get(style, SYSTEM_PROMPTS[DEFAULT_STYLE])
    exchange_count = sum(1 for turn in history if turn.role == "user")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": _turn_stage_instruction(exchange_count)},
    ]
    for turn in history:
        role = "user" if turn.role == "user" else "assistant"
        content = turn.text
        if role == "user" and turn.care_emotion:
            content = f"[케어 감정: {turn.care_emotion}] {content}"
        messages.append({"role": role, "content": content})
    current_care_emotion = care_emotion or FALLBACK_CARE_EMOTION
    messages.append({
        "role": "user",
        "content": f"[현재 케어 감정: {current_care_emotion}] {transcript}",
    })
    return messages


def get_reply(
    history: list[TurnRecord],
    transcript: str,
    emotions: dict[str, float],
    style: str = DEFAULT_STYLE,
    care_emotion: str | None = None,
) -> str:
    if len(transcript.strip().strip(string.punctuation)) < MIN_TRANSCRIPT_LENGTH:
        return FALLBACK_REPLY

    client = get_client()
    messages = build_messages(history, transcript, emotions, style, care_emotion)
    response = client.chat.completions.create(model=settings.OPENAI_MODEL, messages=messages)
    return response.choices[0].message.content
