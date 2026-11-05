#!/usr/bin/env python3
"""Queue the last rendered vertical video to YouTube (as a Short) through Buffer.

Why: Buffer holds the YouTube sign-in, so this repo needs no YT_* secrets and no Google OAuth refresh token
(which expires every 7 days while a Google Cloud OAuth app is in Testing mode).

Secrets/variables: BUFFER_API_KEY and the same CLOUDINARY_* values as post_tiktok.py (the video is hosted on Cloudinary,
or the URL saved by post_tiktok.py is reused). Optional: BUFFER_YOUTUBE_CHANNEL_ID, UPLOAD_PRIVACY (private, unlisted or
public; default private so you can review first), YT_AI_DISCLOSURE (1 to tick Buffer's "AI-generated" box).

  python post_youtube_buffer.py            # queue the video named in output/LAST_SLUG
  python post_youtube_buffer.py --dry-run  # show what would be sent, change nothing
"""
import argparse
import json
import os
import sys

import post_tiktok as pt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not key and not a.dry_run:
        print("BUFFER_API_KEY is not set: skipping the YouTube post.")
        return
    marker = pt.ROOT / "output" / "LAST_SLUG"
    if not marker.exists():
        print("Nothing was rendered this run: skipping the YouTube post.")
        return
    slug = marker.read_text().strip()
    base = pt.ROOT / "output" / slug
    video = base / "vertical" / "video.mp4"
    if not video.exists():
        sys.exit(f"No vertical video at {video}. Make sure the script's aspects include \"9:16\".")
    meta = json.loads((base / "metadata.json").read_text())
    yt = meta.get("youtube", {})
    title = (yt.get("title") or meta.get("title") or slug)[:100]
    text = (yt.get("description", "").strip() + "\n\n#shorts").strip()[:5000]
    privacy = os.environ.get("UPLOAD_PRIVACY", "private").strip() or "private"
    if privacy not in ("private", "unlisted", "public"):
        sys.exit("UPLOAD_PRIVACY must be private, unlisted or public")
    ai = os.environ.get("YT_AI_DISCLOSURE", "").strip() == "1"
    kids = bool(yt.get("made_for_kids", False))
    category = str(yt.get("category_id", "23"))   # 23 = Comedy

    if a.dry_run:
        print(f"DRY RUN: would queue {video} on YouTube via Buffer.\nTitle: {title}\nPrivacy: {privacy}\n"
              f"Made for kids: {kids}  AI-generated: {ai}  Category: {category}\n{text}")
        return

    channel = pt.find_channel(key, "youtube", os.environ.get("BUFFER_YOUTUBE_CHANNEL_ID", "").strip())
    saved = base / "hosted_url.txt"
    url = saved.read_text().strip() if saved.exists() else pt.host_video(video, f"tidalfolio/{slug}")
    print(f"Video URL: {url}")
    meta_in = ('{ youtube: { title: %s, categoryId: %s, privacy: %s, madeForKids: %s, isAiGenerated: %s } }'
               % (json.dumps(title), json.dumps(category), privacy, str(kids).lower(), str(ai).lower()))
    q = ('mutation { createPost(input: { text: %s, channelId: %s, schedulingType: automatic, mode: addToQueue, '
         'metadata: %s, assets: [{ video: { url: %s } }] }) { ... on PostActionSuccess { post { id } } '
         '... on MutationError { message } } }') % (json.dumps(text), json.dumps(channel), meta_in, json.dumps(url))
    res = pt.gql(key, q)["createPost"]
    if res.get("message"):
        sys.exit(f"Buffer refused the post: {res['message']}")
    print(f"Queued on YouTube in Buffer: post {res['post']['id']}")
    (base / "youtube_buffer_post.txt").write_text(res["post"]["id"] + "\n")


if __name__ == "__main__":
    main()
