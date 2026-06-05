from app.wedge import decide_wedge


def test_smart_wedge_skips_known_free():
    decision = decide_wedge({"is_freeleech": True}, mode="smart", unknown_fallback=True)
    assert decision.use_wedge is False
    assert decision.reason == "already_free"


def test_smart_wedge_uses_normal_non_free():
    decision = decide_wedge({"is_freeleech": False}, mode="smart", unknown_fallback=True)
    assert decision.use_wedge is True
    assert decision.reason == "normal_non_free"


def test_smart_wedge_unknown_uses_fallback_preference():
    assert decide_wedge({}, mode="smart", unknown_fallback=True).use_wedge is True
    assert decide_wedge({}, mode="smart", unknown_fallback=False).use_wedge is False


def test_override_records_force_behavior():
    assert decide_wedge({"is_freeleech": True}, mode="smart", override=True).use_wedge is True
    assert decide_wedge({"is_freeleech": False}, mode="smart", override=False).use_wedge is False
