from services.sleep_color_service import choose_sleep_profile, sleep_profile_for_emotion


def test_sleep_profile_for_emotion_high_arousal():
    assert sleep_profile_for_emotion("anxiety") == "deep_amber"


def test_sleep_profile_for_emotion_low_energy():
    assert sleep_profile_for_emotion("fatigue") == "soft_peach"


def test_sleep_profile_for_emotion_relationship():
    assert sleep_profile_for_emotion("shame_guilt") == "low_rose"


def test_sleep_profile_for_emotion_defaults_to_warm_dim():
    assert sleep_profile_for_emotion("joy") == "warm_dim"


def test_choose_sleep_profile_defaults_to_warm_dim_for_empty_timeline():
    assert choose_sleep_profile([]) == "warm_dim"


def test_choose_sleep_profile_uses_high_arousal_group():
    timeline = [{"care_emotion": "anxiety"}, {"care_emotion": "stress"}, {"care_emotion": "joy"}]

    assert choose_sleep_profile(timeline) == "deep_amber"


def test_choose_sleep_profile_uses_low_energy_group():
    timeline = [{"care_emotion": "sadness"}, {"care_emotion": "fatigue"}, {"care_emotion": "calm"}]

    assert choose_sleep_profile(timeline) == "soft_peach"


def test_choose_sleep_profile_uses_relationship_group():
    timeline = [{"care_emotion": "shame_guilt"}, {"care_emotion": "calm"}]

    assert choose_sleep_profile(timeline) == "low_rose"
