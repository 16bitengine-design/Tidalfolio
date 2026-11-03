#!/usr/bin/env python3
"""Render a code-drawn "puppet" video (storybook ink-and-paper animation, free offline narrator).

  python puppet_render.py scripts/005-the-eagle-who-waited-puppet-part-1.json
  python puppet_render.py --next          # next unfinished script in queue-puppet.txt (marked in done-puppet.txt)
  python puppet_render.py <script> --dry-run   # silent placeholder narration: checks timing and scenes quickly

See puppet/README.md.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_lines(p):
    return [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")] if p.exists() else []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="?", help="path to a puppet script, or just its file name inside scripts/")
    ap.add_argument("--next", action="store_true", help="render the next unfinished script from queue-puppet.txt")
    ap.add_argument("--dry-run", action="store_true", help="placeholder (silent) narration, nothing downloaded")
    ap.add_argument("--workers", type=int, default=None, help="parallel frame workers (default: all CPUs)")
    ap.add_argument("--stills", metavar="DIR", help="only write preview PNGs (3 per scene) into DIR")
    a = ap.parse_args()
    from puppet.render import render_script, render_stills

    if a.stills and a.script:
        p = Path(a.script)
        render_stills(p if p.exists() else ROOT / "scripts" / a.script, [1.5, 3.5, 5.5], a.stills)
        return

    if a.next:
        todo = [q for q in read_lines(ROOT / "queue-puppet.txt") if q not in set(read_lines(ROOT / "done-puppet.txt"))]
        if not todo:
            print("queue-puppet.txt has nothing left to render.")
            return
        name = todo[0]
        render_script(ROOT / "scripts" / name, a.dry_run, a.workers)
        if not a.dry_run:
            with open(ROOT / "done-puppet.txt", "a") as f:
                f.write(name + "\n")
    elif a.script:
        p = Path(a.script)
        render_script(p if p.exists() else ROOT / "scripts" / a.script, a.dry_run, a.workers)
    else:
        ap.error("give a script or --next")


if __name__ == "__main__":
    sys.exit(main())
