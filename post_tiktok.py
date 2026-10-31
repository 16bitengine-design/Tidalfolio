#!/usr/bin/env python3
"""Post the last rendered vertical video to TikTok through Buffer.

Buffer cannot take file uploads, only a public https URL, so the video is first uploaded to Cloudinary
(free tier) and that URL is handed to Buffer's createPost.

Secrets needed: BUFFER_API_KEY, CLOUDINARY_CLOUD_NAME, plus EITHER the variable CLOUDINARY_UPLOAD_PRESET (unsigned preset)
OR the secrets CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET.
Optional: BUFFER_CHANNEL_ID (otherwise the first TikTok channel in your Buffer account is used).

  python post_tiktok.py            # post the video named in output/LAST_SLUG
  python post_tiktok.py --dry-run  # show what would be sent, change nothing
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
BUFFER = "https://api.buffer.com"


def gql(key, query):
    r = requests.post(BUFFER, json={"query": query}, timeout=60,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    if not r.ok:
        sys.exit(f"Buffer request failed ({r.status_code}): {r.text[:500]}")
    j = r.json()
    if j.get("errors"):
        sys.exit(f"Buffer returned errors: {json.dumps(j['errors'])[:600]}")
    return j["data"]


def find_tiktok_channel(key):
    forced = os.environ.get("BUFFER_CHANNEL_ID", "").strip()
    if forced:
        return forced
    orgs = gql(key, "query { account { organizations { id name } } }")["account"]["organizations"]
    seen = []
    for o in orgs:
        chans = gql(key, 'query { channels(input: {organizationId: %s}) { id name service } }'
                    % json.dumps(o["id"]))["channels"]
        for c in chans:
            seen.append(f"{c.get('service')}:{c.get('name')}")
            if "tiktok" in str(c.get("service", "")).lower():
                print(f"Using Buffer channel {c['name']} ({c['id']})")
                return c["id"]
    sys.exit("No TikTok channel found in your Buffer account. Connect TikTok in Buffer first. "
             f"Channels seen: {', '.join(seen) or 'none'}")


def host_video(path, public_id):
    """Upload to Cloudinary. Preferred: an UNSIGNED upload preset (CLOUDINARY_UPLOAD_PRESET), which needs no API
    key. Otherwise a signed upload with CLOUDINARY_API_KEY / CLOUDINARY_API_SECRET (the key must be allowed to upload)."""
    cloud = os.environ.get("CLOUDINARY_CLOUD_NAME", "").strip()
    preset = os.environ.get("CLOUDINARY_UPLOAD_PRESET", "").strip()
    k = os.environ.get("CLOUDINARY_API_KEY", "").strip()
    secret = os.environ.get("CLOUDINARY_API_SECRET", "").strip()
    if not cloud:
        sys.exit("CLOUDINARY_CLOUD_NAME is missing.")
    if preset:
        data = {"upload_preset": preset, "public_id": public_id}
    elif k and secret:
        ts = str(int(time.time()))
        sig = hashlib.sha1(f"public_id={public_id}&timestamp={ts}{secret}".encode()).hexdigest()
        data = {"api_key": k, "timestamp": ts, "public_id": public_id, "signature": sig}
    else:
        sys.exit("Cloudinary is not configured: set CLOUDINARY_UPLOAD_PRESET (an unsigned preset), "
                 "or CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET.")
    with open(path, "rb") as f:
        r = requests.post(f"https://api.cloudinary.com/v1_1/{cloud}/video/upload", timeout=1800,
                          data=data, files={"file": f})
    if not r.ok:
        hint = ""
        if r.status_code in (401, 403):
            hint = ("\nThe Cloudinary key is not allowed to upload (or the secret/cloud name is wrong). Fix: in Cloudinary, "
                    "Settings > Upload > Upload presets, add an UNSIGNED preset, then add the repo variable "
                    "CLOUDINARY_UPLOAD_PRESET with its name; or create an API key with full permissions.")
        elif r.status_code in (400, 413):
            hint = "\nIf this is a size error, lower MAX_VIDEO_MB or use only the 9:16 aspect."
        sys.exit(f"Cloudinary upload failed ({r.status_code}): {r.text[:500]}{hint}")
    return r.json()["secure_url"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not key and not a.dry_run:
        print("BUFFER_API_KEY is not set: skipping TikTok post (the video is still in the downloadable artifact).")
        return
    marker = ROOT / "output" / "LAST_SLUG"
    if not marker.exists():
        print("Nothing was rendered this run: skipping TikTok post.")
        return
    slug = marker.read_text().strip()
    base = ROOT / "output" / slug
    video = base / "vertical" / "video.mp4"
    if not video.exists():
        sys.exit(f"No vertical video at {video}. Make sure the script's aspects include \"9:16\".")
    tt = json.loads((base / "metadata.json").read_text()).get("tiktok", {})
    text = tt.get("caption", "").strip()
    tags = [h for h in tt.get("hashtags", []) if h.lower() not in text.lower()]
    text = (text + "\n" + " ".join(tags)).strip()[:2000]

    if a.dry_run:
        print(f"DRY RUN: would upload {video} ({video.stat().st_size / 1e6:.1f} MB) and post to TikTok via Buffer with text:\n{text}")
        return

    channel = find_tiktok_channel(key)
    url = host_video(video, f"tidalfolio/{slug}")
    print(f"Hosted at {url}")
    q = ('mutation { createPost(input: { text: %s, channelId: %s, schedulingType: automatic, mode: addToQueue, '
         'assets: [{ video: { url: %s } }] }) { ... on PostActionSuccess { post { id } } '
         '... on MutationError { message } } }') % (json.dumps(text), json.dumps(channel), json.dumps(url))
    res = gql(key, q)["createPost"]
    if res.get("message"):
        sys.exit(f"Buffer refused the post: {res['message']}")
    print(f"Queued in Buffer: post {res['post']['id']}")
    (base / "tiktok_post.txt").write_text(res["post"]["id"] + "\n")


if __name__ == "__main__":
    main()
