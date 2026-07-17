from models.voice import VoiceAnalyzeResponse
from models.chat import ChatReplyRequest, ChatReplyResponse
from models.tts import TTSRequest
from models.emotion import SessionEndRequest, SessionEndResponse
from models.diary import DiaryGenerateRequest, DiaryGenerateResponse


def test_voice_analyze_response_roundtrip():
    resp = VoiceAnalyzeResponse(transcript="안녕", emotions={"happy": 0.5, "neutral": 0.5})
    assert resp.model_dump() == {"transcript": "안녕", "emotions": {"happy": 0.5, "neutral": 0.5}}


def test_chat_reply_models():
    req = ChatReplyRequest(session_id="s1", transcript="안녕", emotions={"happy": 1.0})
    assert req.session_id == "s1"
    resp = ChatReplyResponse(reply_text="반가워")
    assert resp.reply_text == "반가워"


def test_tts_request():
    assert TTSRequest(text="hello").text == "hello"


def test_session_end_models():
    req = SessionEndRequest(session_id="s1")
    resp = SessionEndResponse(dominant_emotion="happy", average_emotions={"happy": 0.9})
    assert req.session_id == "s1"
    assert resp.dominant_emotion == "happy"


def test_diary_models():
    req = DiaryGenerateRequest(session_id="s1")
    resp = DiaryGenerateResponse(diary_id=1, diary_text="오늘은...", summary="좋은 하루", dominant_emotion="happy")
    assert req.session_id == "s1"
    assert resp.diary_id == 1
