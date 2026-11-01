#!/usr/bin/env python3
"""Split a script that is too long for one video into Part 1, Part 2, ... (each 60 to 90 seconds).

  python tools/split_script.py scripts/004-some-long-story.json            # write the parts, fix queue.txt
  python tools/split_script.py scripts/004-some-long-story.json --plan     # just show where it would split

Cuts fall only between scenes, never inside the human "mirror" act. Each part gets its own slug, a
"Part k/n" title (YouTube title, TikTok caption, description), a "Part k" card on screen at the start and a
"To be continued" card at the end of every part but the last. In queue.txt the long script is replaced by its
parts, in order. The original file is kept.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WORDS_PER_SEC, LEAD, TAIL, MIN_SCENE = 2.4, 0.30, 0.55, 3.0   # same estimate generate_script.py uses (it runs ~5 s high)
MAX_EST = 88.0                                                # estimated seconds per part: lands at roughly 70-85 s real
PART_SUFFIX = re.compile(r"\s*\(Part \d+/\d+\)\s*$")


def est(scene):
    return max(MIN_SCENE, LEAD + len(scene["narration"].split()) / WORDS_PER_SEC + TAIL)


def split_points(scenes, n, scale=1.0):
    """Indices where parts 2..n begin: closest to an even split, never inside a mirror run."""
    times = [est(s) * scale for s in scenes]
    total = sum(times)
    cum = [sum(times[:i]) for i in range(len(times) + 1)]
    mirror = [s.get("look") == "mirror" for s in scenes]
    cuts = []
    for k in range(1, n):
        want = total * k / n
        best = min(range(1, len(scenes)), key=lambda i: abs(cum[i] - want))
        if mirror[best - 1] and mirror[best]:                     # inside the mirror act: move to its start or end
            lo = best
            while lo > 0 and mirror[lo - 1]:
                lo -= 1
            hi = best
            while hi < len(scenes) and mirror[hi]:
                hi += 1
            best = lo if abs(cum[lo] - want) <= abs(cum[hi] - want) else hi
        cuts.append(best)
    cuts = sorted(set(c for c in cuts if 0 < c < len(scenes)))
    return cuts, times


def remap(value, lo, hi, default=1):
    """1-based scene number in the whole story -> 1-based number inside scenes[lo:hi] (or default)."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return v - lo if lo < v <= hi else default


def split_file(path, real_total=None, plan=False):
    """Split one script into parts and fix queue.txt. real_total = measured runtime in seconds (from the narration
    audio); when given, the estimate is scaled to it so the cuts match what will really be rendered.
    Returns the list of part file names (empty if nothing was split)."""
    path = Path(path)
    script = json.loads(path.read_text())
    scenes = script["scenes"]
    est_total = sum(est(s) for s in scenes)
    scale = real_total / est_total if real_total else 1.0
    total = est_total * scale
    n = max(1, math.ceil(total / MAX_EST))
    if n == 1:
        print(f"{path.name}: about {total:.0f}s, it already fits in one video. Nothing to split.")
        return []
    cuts, times = split_points(scenes, n, scale)
    bounds = [0] + cuts + [len(scenes)]
    n = len(bounds) - 1
    print(f"{path.name}: about {total:.0f}s estimated -> {n} parts")
    for k in range(n):
        lo, hi = bounds[k], bounds[k + 1]
        print(f"  Part {k + 1}: scenes {lo + 1}-{hi} (~{sum(times[lo:hi]):.0f}s)  ends: \"{scenes[hi - 1]['narration'][:60]}\"")
    if plan:
        return []

    from generate_script import label_parts   # shared with the script writer so both label parts the same way
    base_title = PART_SUFFIX.sub("", script.get("title", path.stem))
    base_slug = re.sub(r"-part-\d+$", "", script.get("slug") or path.stem)
    names = []
    for k in range(n):
        lo, hi = bounds[k], bounds[k + 1]
        part = json.loads(json.dumps(script))                     # deep copy
        part["scenes"] = scenes[lo:hi]
        part["slug"] = f"{base_slug}-part-{k + 1}"
        part["title"] = f"{base_title} (Part {k + 1}/{n})"
        part["series_part"] = {"story": base_title, "part": k + 1, "of": n}
        st = part.get("story")
        if isinstance(st, dict):
            beat = st.get("emotional_beat_scene")
            if beat is not None and lo < int(beat) <= hi:
                st["emotional_beat_scene"] = int(beat) - lo
            else:
                st.pop("emotional_beat_scene", None)
        part["thumbnail_scene"] = remap(script.get("thumbnail_scene"), lo, hi, min(2, hi - lo))
        part["shareable_scene"] = remap(script.get("shareable_scene"), lo, hi, 1)
        label_parts(part)
        out = path.parent / f"{part['slug']}.json"
        out.write_text(json.dumps(part, indent=2, ensure_ascii=False))
        names.append(out.name)
        print(f"  wrote {out.name}")

    q = ROOT / "queue.txt"
    lines = q.read_text().splitlines() if q.exists() else []
    done = (ROOT / "done.txt").read_text().split() if (ROOT / "done.txt").exists() else []
    if path.name in lines and path.name not in done:
        i = lines.index(path.name)
        lines[i:i + 1] = names
    else:
        lines += [x for x in names if x not in lines]
    q.write_text("\n".join(lines) + "\n")
    print("queue.txt now lists the parts in order. Check each part's opening and ending before posting.")
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--plan", action="store_true", help="only show the split, write nothing")
    ap.add_argument("--real-total", type=float, help="measured runtime in seconds (the pipeline passes this in)")
    a = ap.parse_args()
    split_file(a.script, a.real_total, a.plan)


if __name__ == "__main__":
    main()
