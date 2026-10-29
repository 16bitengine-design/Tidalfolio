#!/usr/bin/env python3
"""Upload the last rendered video (output/<slug>/youtube/video.mp4) to YouTube.

Needs three secrets (see README): YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN.
Privacy comes from the UPLOAD_PRIVACY env var: private (default), unlisted or public.
"""
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent


def access_token():
    r = requests.post("https://oauth2.googleapis.com/token", timeout=60, data={
        "client_id": os.environ["YT_CLIENT_ID"],
        "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    })
    if not r.ok:
        sys.exit(f"Could not refresh the YouTube token ({r.status_code}): {r.text[:300]}\n"
                 "If your OAuth app is still in 'Testing', refresh tokens expire after 7 days. See README.")
    return r.json()["access_token"]


def main():
    if not all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        print("YouTube secrets not set: skipping upload (video is still in the downloadable artifact).")
        return
    marker = ROOT / "output" / "LAST_SLUG"
    if not marker.exists():
        print("Nothing was rendered this run: skipping upload.")
        return
    slug = marker.read_text().strip()
    base = ROOT / "output" / slug
    video, thumb = base / "youtube" / "video.mp4", base / "youtube" / "thumbnail.png"
    meta = json.loads((base / "metadata.json").read_text())
    yt = meta.get("youtube", {})
    privacy = os.environ.get("UPLOAD_PRIVACY", "private").strip() or "private"
    if privacy not in ("private", "unlisted", "public"):
        sys.exit("UPLOAD_PRIVACY must be private, unlisted or public")

    body = {
        "snippet": {
            "title": yt.get("title", meta["title"])[:100],
            "description": yt.get("description", ""),
            "tags": yt.get("tags", []),
            "categoryId": str(yt.get("category_id", "23")),   # 23 = Comedy
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": bool(yt.get("made_for_kids", False)),
        },
    }
    token = access_token()
    auth = {"Authorization": f"Bearer {token}"}
    size = video.stat().st_size

    # 1) start a resumable upload
    r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={**auth, "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(size)},
        json=body, timeout=60)
    if not r.ok:
        sys.exit(f"YouTube refused the upload request ({r.status_code}): {r.text[:500]}")
    upload_url = r.headers["Location"]

    # 2) send the file
    with open(video, "rb") as f:
        r = requests.put(upload_url, data=f, timeout=1800,
                         headers={"Content-Type": "video/mp4", "Content-Length": str(size)})
    if not r.ok:
        sys.exit(f"YouTube upload failed ({r.status_code}): {r.text[:500]}")
    video_id = r.json()["id"]
    print(f"Uploaded: https://youtu.be/{video_id} (privacy: {privacy})")

    # 3) thumbnail (needs a verified channel; failure here is not fatal)
    if thumb.exists():
        t = requests.post(
            f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}&uploadType=media",
            headers={**auth, "Content-Type": "image/png"}, data=thumb.read_bytes(), timeout=120)
        print("Thumbnail set." if t.ok else f"Thumbnail not set ({t.status_code}): {t.text[:200]}")

    (base / "youtube_url.txt").write_text(f"https://youtu.be/{video_id}\n")


if __name__ == "__main__":
    main()
