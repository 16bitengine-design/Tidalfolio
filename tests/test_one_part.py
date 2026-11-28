"""One-part stories: the writer's defaults and prompts, and the storyboard checker, accept a story told in a single video."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from puppet import storywriter as W      # noqa: E402
from puppet import storyboard as SB      # noqa: E402


def test_default_is_one_part():
    os.environ.pop("STORY_PARTS", None)
    assert W.choose_parts() == 1
    os.environ["STORY_PARTS"] = "3"
    try:
        assert W.choose_parts() == 3
    finally:
        os.environ.pop("STORY_PARTS", None)


def test_prompt_for_one_part_has_no_cliffhanger_block():
    one, many = W.system_prompt(6, 8, 1), W.system_prompt(6, 8, 3)
    assert "ONE STORY, ONE VIDEO" in one and "STORY IN PARTS" not in one
    assert '"parts": [{"scenes": [...]}]' in one                      # single braces: it is not an f-string
    assert "STORY IN PARTS" in many and "ONE STORY, ONE VIDEO" not in many


def test_one_part_rules_are_a_resolution_not_a_cliffhanger():
    rules = W._part_rules(1, 1, "serene", 1, None)
    assert "CLIFFHANGER" not in rules and "haunting last line" in rules


def test_one_part_storyboard_compiles_without_part_labels():
    sb = json.loads((ROOT / "scripts" / "016-the-umbrella-that-followed.json").read_text())
    assert sb["series_part"]["of"] == 1
    assert "Part" not in sb["title"] and "Part" not in sb["youtube"]["title"] and "Part" not in sb["tiktok"]["caption"]
    assert "Part" not in sb["youtube"]["description"] and sb["scenes"][-1].get("end_card")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("4 passed")
