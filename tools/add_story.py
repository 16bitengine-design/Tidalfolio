#!/usr/bin/env python3
"""Add a hand-written story (no AI model needed) to the puppet queue.

  python tools/add_story.py stories/the-third-chair.json --check   # run every check, change nothing
  python tools/add_story.py stories/the-third-chair.json           # check, compile into scripts/ and queue in queue-puppet.txt

The story file is the same plan + parts the AI writer produces (see puppet/storywriter.py: BIBLE_STEP and the stage rules).
It goes through the very same checks (cast, scene format, drawing smoke test, length, director's rule, film team, stock phrases),
so a story that passes here renders like any other.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("story", help="path to the story JSON")
    ap.add_argument("--check", action="store_true", help="only check, do not write or queue anything")
    a = ap.parse_args()

    import generate_script as G
    from puppet import storywriter as W

    sb = W.normalize(json.loads(Path(a.story).read_text()))
    parts = sb.get("parts") or []
    n = len(parts)
    bad = []
    if not 2 <= n <= 4:
        bad.append(f"a story is told in 2 to 4 parts (this one has {n}).")
    else:
        bad += W._bible_problems(sb, n, G.used_words())
        word = str(sb["uncommon_word"]["word"]).strip()
        uw_part = next((k for k, p in enumerate(parts, 1) if re.search(rf"\b{re.escape(word)}\b", " ".join(str(s.get("narration", "")) for s in p.get("scenes", [])), re.I)), 1)
        for k, p in enumerate(parts, 1):
            bad += W._part_problems(p, sb["cast"], k, word, uw_part, n)
    if not bad:
        number = G.next_number()
        problems, scripts = W.problems({k: v for k, v in sb.items() if k != "outline"}, number)
        bad += problems
    if bad:
        print("NOT READY:")
        for b in bad:
            print(" -", b)
        return 1
    if a.check:
        print(f"OK: {n} parts pass every check (nothing written).")
        return 0
    names = W._save_story({k: v for k, v in sb.items() if k != "outline"}, scripts, "Funny People", number, n)
    print("Queued in order: " + ", ".join(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
