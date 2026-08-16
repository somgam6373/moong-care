from models.voice import VoiceAnalyzeResponse
from models.chat import ChatReplyRequest, ChatReplyResponse
from models.tts import TTSRequest
from models.emotion import SessionEndRequest, SessionEndResponse
from datetime import datetime

from models.care import CareColor, MoodLightPayload
from models.diary import DiaryDetail, DiaryGenerateRequest, DiaryGenerateResponse, DiaryListItem
from models.letter import LetterDetail, LetterListItem as LetterListItemModel


def test_voice_analyze_response_roundtrip():
    care_color = CareColor(hex="#7DCAC3", brightness=0.38, transition_ms=1800)
    resp = VoiceAnalyzeResponse(
        transcript="안녕",
        emotions={"happy": 0.5, "neutral": 0.5},
        pitch_mean=187.3,
        pitch_std=24.1,
        care_emotion="tension",
        care_emotion_label="긴장",
        care_confidence=0.74,
        care_color=care_color,
    )
    assert resp.model_dump() == {
        "transcript": "안녕",
        "emotions": {"happy": 0.5, "neutral": 0.5},
        "pitch_mean": 187.3,
        "pitch_std": 24.1,
        "care_emotion": "tension",
        "care_emotion_label": "긴장",
        "care_confidence": 0.74,
        "care_color": {"hex": "#7DCAC3", "brightness": 0.38, "transition_ms": 1800},
    }


def test_chat_reply_models():
    req = ChatReplyRequest(session_id="s1", transcript="안녕", emotions={"happy": 1.0}, care_emotion="joy")
    assert req.session_id == "s1"
    assert req.care_emotion == "joy"
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
    resp = SessionEndResponse(
        dominant_emotion="joy",
        average_emotions={"happy": 0.9},
        sleep_color=CareColor(hex="#C9785A", brightness=0.16, transition_ms=6000),
    )
    assert req.session_id == "s1"
    assert resp.dominant_emotion == "joy"
    assert resp.sleep_color.hex == "#C9785A"


def test_diary_models():
    req = DiaryGenerateRequest(session_id="s1")
    resp = DiaryGenerateResponse(
        diary_id=1,
        letter_id=2,
        diary_text="오늘은...",
        letter_text="오늘 네 이야기를 들으며...",
        summary="좋은 하루",
        dominant_emotion="happy",
    )
    assert req.session_id == "s1"
    assert resp.diary_id == 1
    assert resp.letter_id == 2


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


def test_care_models():
    color = CareColor(hex="#A7CDBD", brightness=0.42, transition_ms=1600)
    payload = MoodLightPayload(mode="realtime", emotion="calm", **color.model_dump())

    assert payload.model_dump() == {
        "mode": "realtime",
        "emotion": "calm",
        "hex": "#A7CDBD",
        "brightness": 0.42,
        "transition_ms": 1600,
    }


def test_letter_models():
    created_at = datetime(2026, 8, 13, 12, 0, 0)
    item = LetterListItemModel(
        id=1,
        session_id="s1",
        diary_id=2,
        summary="좋은 하루",
        dominant_emotion="happy",
        created_at=created_at,
    )
    detail = LetterDetail(
        id=1,
        session_id="s1",
        diary_id=2,
        letter_text="오늘 네 이야기를 들으며...",
        summary="좋은 하루",
        dominant_emotion="happy",
        sleep_color=CareColor(hex="#C9785A", brightness=0.16, transition_ms=6000),
        created_at=created_at,
    )

    assert item.diary_id == 2
    assert detail.sleep_color.hex == "#C9785A"
