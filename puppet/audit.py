"""Director's audit of a FINISHED puppet script (the compiled JSON in scripts/): does the picture show what the narrator says?

It runs the same rule the story writer is held to (storyboard._unseen) over every scene: each physical thing the narration names must be a prop, a
carried item or something the setting already paints, and words that mean darkness need a night scene.
    python -m puppet.audit scripts/011-the-tour-guide-part-3.json      (or several files, or no argument for every script)
Exit status 1 if any scene is off script."""
import glob
import json
import re
import sys
from pathlib import Path

from . import design as DZ
from . import storyboard as SB


def _scene_view(sc):
    """a compiled scene seen the way the writer's storyboard describes it: stage, world, props, carried items"""
    m = re.match(r"toon_(\w+?)_(\w+)$", sc.get("world", ""))
    world, stage = (m.group(1), m.group(2)) if m else (re.sub(r"^toon_", "", sc.get("world", "")), "cliff")
    props, actors = [], []
    for th in sc.get("things", []):
        if th.get("type") == "prop":
            props.append({"item": th.get("item")})
        elif th.get("type") == "human":
            c = th.get("carry")
            if isinstance(c, dict):                                      # carried for a while, then something else: every item that is ever in the hand counts
                for _, v in c.get("step", []):
                    if v and v != "none":
                        actors.append({"carry": v})
            else:
                actors.append({"carry": c})
    return {"narration": sc.get("narration", ""), "world": world, "stage": stage, "props": props, "actors": actors, "sky": bool(sc.get("sky"))}


def audit_script(script):
    SB._PROP_NAMES = set(DZ.sanitize_props(script.get("props")))
    SB._ALL_PROPS = set(DZ.with_builtins(script.get("props")))
    out = []
    for n, sc in enumerate(script.get("scenes", []), 1):
        out += SB._unseen(_scene_view(sc), f"scene {n}")
    return out


def main(argv):
    files = argv or sorted(glob.glob("scripts/*.json"))
    bad_files = 0
    for f in files:
        problems = audit_script(json.loads(Path(f).read_text()))
        print(f"{'OFF SCRIPT' if problems else 'ok        '}  {f}")
        for p in problems:
            print("    -", p.split(". ")[0][:170])
        bad_files += bool(problems)
    print(f"\n{bad_files} of {len(files)} scripts have scenes that name things the picture does not show.")
    return 1 if bad_files else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
