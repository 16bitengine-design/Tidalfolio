#!/usr/bin/env python3
"""Turn metrics/videos.json into insights.md: what worked and what did not, for the script writer to read.

Only videos that are at least 2 days old and have stats are used. Until 4 such videos exist the file says "not enough
data" and the writer ignores it. Ranking uses average percentage watched (retention) when YouTube provides it,
otherwise views per day.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG, OUT = ROOT / "metrics" / "videos.json", ROOT / "insights.md"
MIN_VIDEOS = 4


def score(v):
    st = v["stats"]
    if st.get("averageViewPercentage"):
        return st["averageViewPercentage"]
    return st.get("views", 0) / max(1, v["_age"])


def avg(xs):
    return sum(xs) / len(xs) if xs else 0.0


def line(v):
    st = v["stats"]
    bits = [f"{st.get('views', 0)} views"]
    if st.get("averageViewPercentage"):
        bits.append(f"{st['averageViewPercentage']:.0f}% watched on average")
    if st.get("subscribersGained"):
        bits.append(f"+{st['subscribersGained']} subs")
    return f'- "{v.get("title", "")}" ({v.get("runtime", "?")}s, {", ".join(bits)}). Opening line: "{v.get("hook", "")}"'


def main():
    rows = json.loads(LOG.read_text()) if LOG.exists() else []
    today = datetime.now(timezone.utc).date()
    use = []
    for v in rows:
        if not v.get("stats") or v.get("privacy") == "private":
            continue
        try:
            v["_age"] = (today - datetime.fromisoformat(v["uploaded_at"]).date()).days
        except Exception:
            continue
        if v["_age"] >= 2:
            use.append(v)
    if len(use) < MIN_VIDEOS:
        OUT.write_text(f"# Channel insights\n\nNot enough data yet ({len(use)} of {MIN_VIDEOS} public videos with results). "
                       "The script writer ignores this file until there are enough.\n")
        print(f"Insights: not enough data yet ({len(use)}/{MIN_VIDEOS}).")
        return
    use.sort(key=score, reverse=True)
    metric = "average % watched" if any(v["stats"].get("averageViewPercentage") for v in use) else "views per day"
    out = [f"# Channel insights\n\nBased on {len(use)} videos, ranked by {metric}. Small sample: treat as a steer.\n",
           "<!-- ready -->\n", "Best performers:"] + [line(v) for v in use[:3]]
    out += ["", "Weakest performers:"] + [line(v) for v in use[-3:][::-1]]

    by_series = {}
    for v in use:
        by_series.setdefault(v.get("series") or "unknown", []).append(score(v))
    ranked = sorted(by_series.items(), key=lambda kv: avg(kv[1]), reverse=True)
    out += ["", "Series, best to weakest (" + metric + "): " + "; ".join(f"{k} {avg(x):.0f}" for k, x in ranked)]

    buckets = {"under 70s": [], "70 to 80s": [], "over 80s": []}
    for v in use:
        r = v.get("runtime") or 0
        buckets["under 70s" if r < 70 else "70 to 80s" if r <= 80 else "over 80s"].append(score(v))
    shown = [f"{k}: {avg(x):.0f} ({len(x)} videos)" for k, x in buckets.items() if x]
    if len(shown) > 1:
        out.append("Length: " + "; ".join(shown))
    out.append(f"Average opening line of the top 3 is {avg([len(v.get('hook', '').split()) for v in use[:3]]):.0f} words; "
               f"of the weakest 3, {avg([len(v.get('hook', '').split()) for v in use[-3:]]):.0f} words.")
    OUT.write_text("\n".join(out) + "\n")
    print(f"Insights written from {len(use)} videos.")


if __name__ == "__main__":
    main()
