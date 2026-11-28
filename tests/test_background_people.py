from puppet import storyboard as SB


def test_background_people_rules():
    a = [{"who": "x", "at": "ground_mid"}]
    day = SB._background_people({"world": "day", "narration": "A boy ran."}, 0, "street", a, {})
    assert 1 <= len(day) <= 3 and all(t["scale"] < 0.7 for t in day)
    assert SB._background_people({"world": "night", "narration": "A boy ran."}, 0, "street", a, {}) == []
    assert SB._background_people({"world": "day", "narration": "The street was empty."}, 0, "street", a, {}) == []
    assert SB._background_people({"world": "day", "narration": "Hi.", "extras": False}, 0, "street", a, {}) == []
    assert SB._background_people({"world": "day", "narration": "Hi."}, 0, "home", a, {}) == []
