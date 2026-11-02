#!/usr/bin/env python3
"""Resolve a git rebase conflict in metrics/videos.json by keeping the rows from BOTH sides.

metrics/videos.json is an append-only log with one row per upload (keyed by video_id). When two runs both add rows, git
sees an add/add or modify/modify conflict that retrying can never fix. Inside a conflicted rebase:
  stage 2 (:2:) = the version already on origin/main
  stage 3 (:3:) = the version from the commit being replayed (this run)

Usage: python tools/merge_metrics.py metrics/videos.json
Writes the merged JSON to that path. Exits 1 if either side is not valid JSON (then nothing is overwritten).
"""
import json
import subprocess
import sys
from pathlib import Path


def stage(n, path):
    out = subprocess.run(["git", "show", f":{n}:{path}"], capture_output=True, text=True)
    if out.returncode != 0:
        return []                                  # that side does not have the file
    rows = json.loads(out.stdout or "[]")
    if not isinstance(rows, list):
        raise ValueError(f"stage {n} of {path} is not a JSON list")
    return rows


def key(row, i):
    return row.get("video_id") or row.get("slug") or f"row-{i}"


def newer_stats(a, b):
    """Pick the stats block with the later as_of date (either may be missing)."""
    sa, sb = a.get("stats"), b.get("stats")
    if not sa:
        return sb
    if not sb:
        return sa
    return sb if sb.get("as_of", "") >= sa.get("as_of", "") else sa


def merge(upstream, mine):
    merged, order = {}, []
    for i, row in enumerate(upstream):
        k = key(row, i)
        merged[k] = row
        order.append(k)
    for i, row in enumerate(mine):
        k = key(row, i)
        if k in merged:
            combined = {**merged[k], **row}
            stats = newer_stats(merged[k], row)
            if stats:
                combined["stats"] = stats
            merged[k] = combined
        else:
            merged[k] = row
            order.append(k)
    return [merged[k] for k in order]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    try:
        rows = merge(stage(2, path), stage(3, path))
    except (ValueError, json.JSONDecodeError) as e:
        sys.exit(f"Cannot merge {path}: {e}")
    Path(path).write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    print(f"Merged {path}: {len(rows)} rows")


if __name__ == "__main__":
    main()
