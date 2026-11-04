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
    ap.add_argument("--parts", type=int, choices=[2, 3, 4], help="how many parts (default: random 2 to 4)")
    ap.add_argument("--series", choices=["Bird Banter", "Funny Animals"])
    ap.add_argument("--storyboard", help="skip the AI: validate this storyboard JSON file and queue it")
    a = ap.parse_args()
    from puppet import storywriter as W

    if a.storyboard:
        import generate_script as G
        sb = json.loads(Path(a.storyboard).read_text())
        n = G.next_number()
        bad, scripts = W.problems(sb, n)
        if bad:
            sys.exit("Storyboard rejected:\n- " + "\n- ".join(bad))
        names = []
        for sc in scripts:
            path = W.SCRIPTS / f"{sc['slug']}.json"
            path.write_text(json.dumps(sc, indent=1))
            names.append(path.name)
        with open(W.QUEUE, "a") as f:
            f.write("\n".join(names) + "\n")
        print("Wrote and queued: " + ", ".join(names))
        return
    count = a.count
    if a.ensure is not None:
        count = 1 if len(W.unrendered()) < a.ensure else 0     # one story = 2 to 4 queued videos
        if count <= 0:
            print(f"Queue already has {len(W.unrendered())} unrendered story(ies): nothing to write.")
            return
    for _ in range(max(1, count)):
        idea = a.idea or W.take_idea()          # a human idea from ideas.txt always beats the model's own
        try:
            W.write_story(idea, a.series, a.parts)
        except BaseException:
            if idea and not a.idea:
                W.give_back_idea(idea)
            raise


if __name__ == "__main__":
    main()
