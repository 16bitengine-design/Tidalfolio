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
        "client_id": os.environ["YT_CLIENT_ID"].strip(),
        "client_secret": os.environ["YT_CLIENT_SECRET"].strip(),
        "refresh_token": os.environ["YT_REFRESH_TOKEN"].strip(),
        "grant_type": "refresh_token",
    })
    if not r.ok:
        sys.exit(f"Could not refresh the YouTube token ({r.status_code}): {r.text[:300]}\n"
                 "invalid_client = the client ID/secret do not match an existing OAuth client (re-copy both from Google Cloud > Credentials).\n"
                 "invalid_grant = the refresh token is expired or was made with a different client (Testing apps expire after 7 days). See README.")
    return r.json()["access_token"]


def with_hashtags(desc):
    """YouTube shows the first three #hashtags above the title and uses them for discovery."""
    if "#" in desc:
        return desc
    return (desc.rstrip() + "\n\n#Shorts #storytime #tidalfolio").strip()


def story_name(meta):
    sp = (meta.get("info") or {}).get("part")
    if not sp:
        return None
    return sp["story"].split(": ", 1)[-1]


def extras(auth, video_id, meta, base, privacy):
    """Optional polish, never fatal: caption track from our SRT and one playlist per story (so Part 2 follows Part 1).
    These need a token with the broader scope https://www.googleapis.com/auth/youtube.force-ssl (see README);
    with an upload-only token they are skipped with a message."""
    api = "https://www.googleapis.com/youtube/v3"
    srt = base / "youtube" / "captions.srt"
    try:
        if srt.exists():
            boundary = "tidalfolio-captions"
            head = json.dumps({"snippet": {"videoId": video_id, "language": "en", "name": "English", "isDraft": False}})
            body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{head}\r\n"
                    f"--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + srt.read_bytes() + f"\r\n--{boundary}--".encode()
            c = requests.post("https://www.googleapis.com/upload/youtube/v3/captions?uploadType=multipart&part=snippet",
                              headers={**auth, "Content-Type": f"multipart/related; boundary={boundary}"}, data=body, timeout=120)
            print("Captions added." if c.ok else f"Captions not added ({c.status_code}): {c.text[:160]}")
    except Exception as e:
        print(f"Captions skipped: {e}")
    name = story_name(meta)
    if not name:
        return
    try:
        lst = requests.get(f"{api}/playlists", params={"part": "snippet", "mine": "true", "maxResults": 50}, headers=auth, timeout=60)
        if not lst.ok:
            print(f"Playlist skipped ({lst.status_code}): needs the broader token scope, see README.")
            return
        pid = next((i["id"] for i in lst.json().get("items", []) if i["snippet"]["title"] == name), None)
        if not pid:
            mk = requests.post(f"{api}/playlists?part=snippet,status", headers={**auth, "Content-Type": "application/json"}, timeout=60,
                               json={"snippet": {"title": name, "description": f"{name}, told in parts. Watch in order."}, "status": {"privacyStatus": "public"}})
            if not mk.ok:
                print(f"Playlist not created ({mk.status_code}): {mk.text[:160]}")
                return
            pid = mk.json()["id"]
        part = (meta.get("info") or {})["part"]["part"]
        add = requests.post(f"{api}/playlistItems?part=snippet", headers={**auth, "Content-Type": "application/json"}, timeout=60,
                            json={"snippet": {"playlistId": pid, "position": part - 1, "resourceId": {"kind": "youtube#video", "videoId": video_id}}})
        print(f"Added to playlist '{name}'." if add.ok else f"Not added to playlist ({add.status_code}): {add.text[:160]}")
    except Exception as e:
        print(f"Playlist skipped: {e}")


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
            "description": with_hashtags(yt.get("description", "")),
            "tags": (yt.get("tags", []) + [t for t in ("shorts", "storytime") if t not in yt.get("tags", [])])[:15],
            "categoryId": str(yt.get("category_id", "23")),   # 23 = Comedy
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
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

    extras(auth, video_id, meta, base, privacy)

    (base / "youtube_url.txt").write_text(f"https://youtu.be/{video_id}\n")

    # remember this upload so later runs can look up how it performed (tools/collect_metrics.py)
    try:
        from datetime import datetime, timezone
        log = ROOT / "metrics" / "videos.json"
        log.parent.mkdir(exist_ok=True)
        rows = json.loads(log.read_text()) if log.exists() else []
        rows.append({**meta.get("info", {}), "title": meta.get("title", ""), "video_id": video_id, "privacy": privacy,
                     "uploaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%d")})
        log.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Could not record the upload for the results tracker: {e}")


if __name__ == "__main__":
    main()
