from services import color_care_service


def test_all_care_emotions_have_realtime_color():
    for emotion in color_care_service.ALLOWED_CARE_EMOTIONS:
        color = color_care_service.get_realtime_color(emotion)
        assert color.hex.startswith("#")
        assert 0 <= color.brightness <= 1
        assert color.transition_ms > 0


def test_unknown_care_emotion_falls_back_to_calm_color():
    color = color_care_service.get_realtime_color("unknown-emotion")

    assert color == color_care_service.REALTIME_COLORS["calm"]


def test_sleep_profiles_have_colors():
    for profile in color_care_service.SLEEP_COLORS:
        color = color_care_service.get_sleep_color(profile)
        assert color.hex.startswith("#")
        assert 0 <= color.brightness <= 1
        assert color.transition_ms > 0


def test_unknown_sleep_profile_falls_back_to_warm_dim():
    color = color_care_service.get_sleep_color("unknown-profile")

    assert color == color_care_service.SLEEP_COLORS["warm_dim"]


def test_get_care_emotion_label_falls_back_to_calm():
    assert color_care_service.get_care_emotion_label("tension") == "긴장"
    assert color_care_service.get_care_emotion_label("nope") == "평온"
