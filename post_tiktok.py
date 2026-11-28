#!/usr/bin/env python3
"""Post the last rendered vertical video to TikTok through Buffer.

Buffer cannot take file uploads, only a public https URL, so the video is first hosted as a GitHub release asset of this
public repo (any length; Cloudinary refuses videos over 60 s) and that URL is handed to Buffer's createPost.

Needs only BUFFER_API_KEY (GITHUB_TOKEN and GITHUB_REPOSITORY come with every Actions run). To use Cloudinary instead, set
VIDEO_HOST=cloudinary plus CLOUDINARY_CLOUD_NAME and either CLOUDINARY_UPLOAD_PRESET or CLOUDINARY_API_KEY/CLOUDINARY_API_SECRET.
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


def find_channel(key, service, forced=""):
    """Return the id of the first Buffer channel whose service matches (e.g. "tiktok", "youtube")."""
    if forced:
        return forced
    orgs = gql(key, "query { account { organizations { id name } } }")["account"]["organizations"]
    seen = []
    for o in orgs:
        chans = gql(key, 'query { channels(input: {organizationId: %s}) { id name service } }'
                    % json.dumps(o["id"]))["channels"]
        for c in chans:
            seen.append(f"{c.get('service')}:{c.get('name')}")
            if service in str(c.get("service", "")).lower():
                print(f"Using Buffer channel {c['name']} ({c['id']})")
                return c["id"]
    sys.exit(f"No {service} channel found in your Buffer account. Connect it in Buffer first. "
             f"Channels seen: {', '.join(seen) or 'none'}")


def find_tiktok_channel(key):
    return find_channel(key, "tiktok", os.environ.get("BUFFER_CHANNEL_ID", "").strip())


def host_video_github(path, slug):
    """Host the video as a GitHub release asset of this (public) repo and return its public https URL.
    Needs no extra account: the workflow's own GITHUB_TOKEN (contents: write) and GITHUB_REPOSITORY are enough.
    One release per video (tag video-<slug>); re-running replaces the asset. Works for any length and any size up to 2 GB."""
    token = os.environ.get("GITHUB_TOKEN", "").strip() or os.environ.get("GH_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or not repo:
        sys.exit("GitHub hosting needs GITHUB_TOKEN and GITHUB_REPOSITORY (both exist inside a GitHub Actions run).")
    api = "https://api.github.com"
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    tag = f"video-{slug}"
    r = requests.get(f"{api}/repos/{repo}/releases/tags/{tag}", headers=h, timeout=60)
    if r.status_code == 404:
        r = requests.post(f"{api}/repos/{repo}/releases", headers=h, timeout=60,
                          json={"tag_name": tag, "name": slug, "body": "Rendered video (hosted here so Buffer can fetch it).",
                                "draft": False, "prerelease": False, "make_latest": "false"})
    if not r.ok:
        sys.exit(f"GitHub release failed ({r.status_code}): {r.text[:400]}")
    rel = r.json()
    name = "video.mp4"
    for asset in rel.get("assets", []):
        if asset["name"] == name:
            requests.delete(f"{api}/repos/{repo}/releases/assets/{asset['id']}", headers=h, timeout=60)
    up = rel["upload_url"].split("{")[0]
    with open(path, "rb") as f:
        r = requests.post(up, params={"name": name}, timeout=1800, data=f,
                          headers={**h, "Content-Type": "video/mp4"})
    if not r.ok:
        sys.exit(f"GitHub upload failed ({r.status_code}): {r.text[:400]}")
    return r.json()["browser_download_url"]


def host_video(path, public_id):
    """Host the video and return a public https URL. GitHub release by default (Cloudinary refuses videos over 60 s);
    set VIDEO_HOST=cloudinary to use Cloudinary instead."""
    if os.environ.get("VIDEO_HOST", "github").strip().lower() != "cloudinary":
        return host_video_github(path, public_id.split("/")[-1])
    return _host_video_cloudinary(path, public_id)


def _host_video_cloudinary(path, public_id):
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
    (base / "hosted_url.txt").write_text(url + "\n")   # reused by post_youtube_buffer.py so the video is uploaded once
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
