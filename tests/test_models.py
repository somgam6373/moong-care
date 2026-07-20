from models.voice import VoiceAnalyzeResponse
from models.chat import ChatReplyRequest, ChatReplyResponse
from models.tts import TTSRequest
from models.emotion import SessionEndRequest, SessionEndResponse
from datetime import datetime

from models.diary import DiaryDetail, DiaryGenerateRequest, DiaryGenerateResponse, DiaryListItem


def test_voice_analyze_response_roundtrip():
    resp = VoiceAnalyzeResponse(
        transcript="안녕",
        emotions={"happy": 0.5, "neutral": 0.5},
        pitch_mean=187.3,
        pitch_std=24.1,
    )
    assert resp.model_dump() == {
        "transcript": "안녕",
        "emotions": {"happy": 0.5, "neutral": 0.5},
        "pitch_mean": 187.3,
        "pitch_std": 24.1,
    }


def test_chat_reply_models():
    req = ChatReplyRequest(session_id="s1", transcript="안녕", emotions={"happy": 1.0})
    assert req.session_id == "s1"
    resp = ChatReplyResponse(reply_text="반가워")
    assert resp.reply_text == "반가워"


def test_tts_request():
    req = TTSRequest(text="hello")
    assert req.text == "hello"
    assert req.session_id is None
    assert req.voice is None

    req_full = TTSRequest(text="hello", session_id="s1", voice="nova")
    assert req_full.session_id == "s1"
    assert req_full.voice == "nova"


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


def test_diary_list_item_model():
    item = DiaryListItem(
        id=1,
        session_id="s1",
        summary="좋은 하루",
        dominant_emotion="happy",
        created_at=datetime(2026, 7, 20, 12, 0, 0),
    )
    assert item.id == 1
    assert item.session_id == "s1"


def test_diary_detail_model():
    detail = DiaryDetail(
        id=1,
        session_id="s1",
        diary_text="오늘은...",
        summary="좋은 하루",
        dominant_emotion="happy",
        average_emotions={"happy": 0.9, "neutral": 0.1},
        created_at=datetime(2026, 7, 20, 12, 0, 0),
    )
    assert detail.average_emotions == {"happy": 0.9, "neutral": 0.1}
