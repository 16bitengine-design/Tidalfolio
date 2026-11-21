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


def off_script(path):
    """the director's gate: plain-language problems if the narration names a physical thing (or the dark) that the picture does not show"""
    import json
    from puppet.audit import audit_script
    return audit_script(json.loads(Path(path).read_text()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="?", help="path to a puppet script, or just its file name inside scripts/")
    ap.add_argument("--next", action="store_true", help="render the next unfinished script from queue-puppet.txt")
    ap.add_argument("--dry-run", action="store_true", help="placeholder (silent) narration, nothing downloaded")
    ap.add_argument("--workers", type=int, default=None, help="parallel frame workers (default: all CPUs)")
    ap.add_argument("--stills", metavar="DIR", help="only write preview PNGs (3 per scene) into DIR")
    ap.add_argument("--allow-off-script", action="store_true", help="render even if the narration names things the picture does not show (the director's audit is skipped)")
    a = ap.parse_args()
    from puppet.render import render_script, render_stills

    if a.stills and a.script:
        p = Path(a.script)
        render_stills(p if p.exists() else ROOT / "scripts" / a.script, [1.5, 3.5, 5.5], a.stills)
        return

    if a.next:
        blocked = {l.split("#")[0].strip() for l in read_lines(ROOT / "blocked-puppet.txt")}
        todo = [q for q in read_lines(ROOT / "queue-puppet.txt") if q not in set(read_lines(ROOT / "done-puppet.txt")) and q not in blocked]
        name = None
        for q in todo:                                           # nothing goes out off script: a story that fails the audit is set aside and the next one is rendered
            problems = [] if a.allow_off_script else off_script(ROOT / "scripts" / q)
            if not problems:
                name = q
                break
            print(f"BLOCKED {q}: the narration names things the picture does not show:\n  - " + "\n  - ".join(x.split(". ")[0] for x in problems))
            with open(ROOT / "blocked-puppet.txt", "a") as f:
                f.write(f"{q}  # off script: {len(problems)} scene problem(s), run: python -m puppet.audit scripts/{q}\n")
        if not name:
            print("queue-puppet.txt has nothing left to render.")
            return
        render_script(ROOT / "scripts" / name, a.dry_run, a.workers)
        if not a.dry_run:
            with open(ROOT / "done-puppet.txt", "a") as f:
                f.write(name + "\n")
    elif a.script:
        p = Path(a.script)
        p = p if p.exists() else ROOT / "scripts" / a.script
        problems = [] if a.allow_off_script else off_script(p)
        if problems:
            print(f"OFF SCRIPT {p.name}: the narration names things the picture does not show:\n  - " + "\n  - ".join(problems) +
                  "\nFix the script (python -m puppet.audit shows each scene) or pass --allow-off-script.")
            return 3
        render_script(p, a.dry_run, a.workers)
    else:
        ap.error("give a script or --next")


if __name__ == "__main__":
    sys.exit(main())
