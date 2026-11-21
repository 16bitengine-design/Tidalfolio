"""The director's rule: everything the narrator names that has a physical form is on screen, and nothing goes off script.
Run:  python tests/test_director.py     (or pytest tests)"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from puppet import audit, builtin_props as BP, design as DZ, storyboard as SB   # noqa: E402


def scene(narr, stage="street", world="day", props=None, carry=None):
    return {"narration": narr, "stage": stage, "world": world, "props": props or [], "actors": [{"who": "a", "carry": carry}] if carry else [{"who": "a"}]}


def problems(sc):
    SB._PROP_NAMES = set()
    SB._ALL_PROPS = set(DZ.with_builtins(None))
    return SB._unseen(sc, "scene 1")


def test_named_but_undrawn_objects_are_caught():
    p = problems(scene("The boy blew the whistle and waved a flag at the train."))
    named = " ".join(p)
    for word in ("whistle", "flag", "train"):
        assert f"'{word}'" in named, word


def test_built_in_props_satisfy_their_words():
    sc = scene("The boy blew the whistle and waved a flag at the train.", props=[{"item": "train"}], carry="flag")
    assert problems(sc) == []                       # a train carries its steam whistle


def test_a_map_may_be_a_notebook_page():
    assert problems(scene("It was a map.", carry="notebook_page")) == []
    assert problems(scene("It was a map.")) != []


def test_darkness_needs_a_night_scene():
    assert any("dark" in x for x in problems(scene("By dark he was lost again.", world="dusk")))
    assert problems(scene("By dark he was lost again.", world="night")) == []


def test_setting_already_paints_its_own_things():
    assert problems(scene("The clock struck nine.", stage="classroom")) == []
    assert problems(scene("The clock struck nine.", stage="street")) != []


def test_timed_scene_props_compile_to_show_windows():
    cast = {"a": {"species": "human", "role": "baker", "gender": "male", "age": "adult", "skin": "tan", "hair": "brown"}}
    SB._PROP_NAMES, SB._ALL_PROPS = set(), set(DZ.with_builtins(None))
    sc = {"narration": "The doors were closing. The boy jammed them open.", "world": "dusk", "stage": "street",
          "actors": [{"who": "a", "at": "ground_left"}],
          "props": [{"item": "train_doors_closing", "at": "ground_right", "to": "jammed"}, {"item": "train_doors_jammed", "at": "ground_right", "from": "jammed"}]}
    out = SB._compile_scenes([sc], cast)[0]["things"]
    shows = {t["item"]: t["show"] for t in out if t["type"] == "prop"}
    assert shows["train_doors_closing"] == [-0.1, "@jammed"]
    assert shows["train_doors_jammed"] == ["@jammed"]


def test_every_built_in_recipe_draws_within_limits():
    props = DZ.with_builtins(None)
    assert set(props) == set(BP.NAMES)
    for name, shapes in props.items():
        assert 1 <= len(shapes) <= DZ.MAX_SHAPES, name


def test_story_011_is_on_script():
    for n in (1, 2, 3):
        script = json.loads((ROOT / "scripts" / f"011-the-tour-guide-part-{n}.json").read_text())
        assert audit.audit_script(script) == [], n


if __name__ == "__main__":
    fns = [f for k, f in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print("ok  ", f.__name__)
    print(f"\n{len(fns)} passed")
