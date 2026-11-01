#!/usr/bin/env python3
"""Fetch YouTube results for every upload listed in metrics/videos.json and store them next to it.

Needs the same secrets as the uploader (YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN), but the refresh token must
also have been authorised for the read scopes (README, "Results tracking"):
  https://www.googleapis.com/auth/youtube.readonly
  https://www.googleapis.com/auth/yt-analytics.readonly
Never fails the run: if anything is missing it says why and exits 0.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "metrics" / "videos.json"
METRICS = "views,averageViewPercentage,averageViewDuration,likes,comments,subscribersGained"
NAMES = METRICS.split(",")


def token():
    r = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={
        "client_id": os.environ["YT_CLIENT_ID"].strip(), "client_secret": os.environ["YT_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["YT_REFRESH_TOKEN"].strip(), "grant_type": "refresh_token"})
    if not r.ok:
        print(f"Results tracking skipped: could not refresh the YouTube token ({r.status_code}).")
        return None
    return r.json()["access_token"]


def analytics(auth, vid, start, end):
    r = requests.get("https://youtubeanalytics.googleapis.com/v2/reports", headers=auth, timeout=60, params={
        "ids": "channel==MINE", "startDate": start, "endDate": end, "metrics": METRICS, "filters": f"video=={vid}"})
    if r.status_code in (401, 403):
        return None, r.status_code
    if not r.ok:
        print(f"  analytics error for {vid} ({r.status_code}): {r.text[:160]}")
        return None, r.status_code
    rows = r.json().get("rows") or []
    if not rows:
        return {n: 0 for n in NAMES}, 200
    return dict(zip(NAMES, rows[0])), 200


def basic(auth, vid):
    r = requests.get("https://www.googleapis.com/youtube/v3/videos", headers=auth, timeout=60,
                     params={"part": "statistics", "id": vid})
    if not r.ok or not r.json().get("items"):
        return None
    st = r.json()["items"][0]["statistics"]
    return {"views": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0)), "comments": int(st.get("commentCount", 0))}


def main():
    if not LOG.exists() or not json.loads(LOG.read_text()):
        print("Results tracking: no uploads recorded yet.")
        return
    if not all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        print("Results tracking skipped: YouTube secrets not set.")
        return
    tok = token()
    if not tok:
        return
    auth = {"Authorization": f"Bearer {tok}"}
    rows = json.loads(LOG.read_text())
    today = datetime.now(timezone.utc).date()
    updated, denied = 0, False
    for row in rows:
        vid = row.get("video_id")
        if not vid:
            continue
        start = row.get("uploaded_at") or (today - timedelta(days=90)).isoformat()
        if (today - datetime.fromisoformat(start).date()).days > 120:
            continue                                         # old videos: keep the numbers we already have
        stats, code = analytics(auth, vid, start, today.isoformat())
        if stats is None and code in (401, 403):
            denied = True
            stats = basic(auth, vid)
        if stats:
            row["stats"] = {**stats, "as_of": today.isoformat()}
            updated += 1
    LOG.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"Results tracking: updated {updated} of {len(rows)} videos.")
    if denied:
        print("NOTE: the YouTube token cannot read analytics (watch-time numbers are missing). Re-authorise the refresh token "
              "with the youtube.readonly and yt-analytics.readonly scopes (README, Results tracking).")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                                   # never break the video run because of tracking
        print(f"Results tracking skipped: {e}")
