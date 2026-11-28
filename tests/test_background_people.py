from puppet import storyboard as SB


def test_background_people_rules():
    a = [{"who": "x", "at": "ground_mid"}]
    day = SB._background_people({"world": "day", "narration": "A boy ran."}, 0, "street", a, {})
    assert 1 <= len(day) <= 3 and all(t["scale"] < 0.7 for t in day)
    assert SB._background_people({"world": "night", "narration": "A boy ran."}, 0, "street", a, {}) == []
    assert SB._background_people({"world": "day", "narration": "The street was empty."}, 0, "street", a, {}) == []
    assert SB._background_people({"world": "day", "narration": "Hi.", "extras": False}, 0, "street", a, {}) == []
    assert SB._background_people({"world": "day", "narration": "Hi."}, 0, "home", a, {}) == []


def test_background_creatures():
    seen = set()
    for si in range(12):
        t = SB._background_creature({}, si, "street")
        if t:
            seen.add(t["item"])
            assert t["item"].startswith("bg_") and t["x"]["kf"]
    assert any("car" in i or "bus" in i for i in seen) and any("bird" in i for i in seen)
    assert SB._background_creature({}, 0, "office") is None
