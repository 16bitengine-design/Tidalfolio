#!/usr/bin/env python3
"""Write new puppet stories with an AI model (checked against the channel rules) and queue them.

  python puppet_story.py --ensure 3            # make sure at least 3 unrendered stories are queued
  python puppet_story.py --count 1 --idea "a rabbit who won't share a carrot"
  python puppet_story.py --storyboard my.json  # no AI: check, compile and queue a storyboard you wrote
Needs OPENAI_API_KEY (text only, a few cents per story). See puppet/README.md.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ensure", type=int, help="write stories until this many unrendered ones are queued")
    ap.add_argument("--count", type=int, default=0, help="write this many new stories")
    ap.add_argument("--idea")
    ap.add_argument("--series", choices=["Bird Banter", "Funny Animals"])
    ap.add_argument("--storyboard", help="skip the AI: validate this storyboard JSON file and queue it")
    a = ap.parse_args()
    from puppet import storywriter as W

    if a.storyboard:
        import generate_script as G
        sb = json.loads(Path(a.storyboard).read_text())
        n = G.next_number()
        bad, script = W.problems(sb, n)
        if bad:
            sys.exit("Storyboard rejected:\n- " + "\n- ".join(bad))
        script["title"] = f"{a.series or 'Bird Banter'} #{n}: {sb['title'].strip()}"
        path = W.SCRIPTS / f"{script['slug']}.json"
        path.write_text(json.dumps(script, indent=1))
        with open(W.QUEUE, "a") as f:
            f.write(path.name + "\n")
        print(f"Wrote and queued {path.name}")
        return
    count = a.count
    if a.ensure is not None:
        count = a.ensure - len(W.unrendered())
        if count <= 0:
            print(f"Queue already has {len(W.unrendered())} unrendered story(ies): nothing to write.")
            return
    for _ in range(max(1, count)):
        W.write_story(a.idea, a.series)


if __name__ == "__main__":
    main()
