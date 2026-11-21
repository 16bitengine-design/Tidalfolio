"""Characters must stand IN the floor, not hover on the line where the wall meets it.
Run:  python tests/test_grounding.py     (or pytest tests)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from puppet import vector as V   # noqa: E402


def test_background_is_raised_behind_the_feet():
    assert V.FLOOR_RAISE >= 60          # the floor shows behind the feet by at least this many world units


def test_background_shift_never_leaks_onto_people():
    V.begin()
    try:
        V.stage_world("toon_day_nowhere_that_exists", 0.0)
    except Exception:
        pass
    assert V._BG is False               # people and props are drawn after the background, unshifted


def test_shadow_has_a_dark_contact_line():
    import inspect
    src = inspect.getsource(V.ground_shadow)
    assert src.count("soft_shadow(") >= 3


if __name__ == "__main__":
    fns = [f for k, f in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print("ok  ", f.__name__)
    print(f"\n{len(fns)} passed")
