"""Titles, descriptions, tags and #hashtags for every platform, built automatically for every video.

The story writer supplies a teaser, a few tags and a TikTok hook. This module adds everything that should never be forgotten and
never be typed by hand: the part line ("Part 3 is next"), who is in the story, the channel's standing tags, hashtags worked out from
the cast and the story's own tags, and a version for each platform with the right length and the right number of hashtags
(YouTube shows the first three above the title; TikTok likes few; Instagram likes more).
No AI call is needed, so it costs nothing and always runs.
"""
import re

CHANNEL = "tidalfolio"
BRAND_TAGS = ["tidalfolio", "storytime", "animatedstory", "funnystories"]
EVERGREEN = ["funny stories", "animated story", "storytime", "short story", "comedy", "cartoon", "tidalfolio"]
GENERIC = {"funny stories", "short story", "animated story", "storytime", "comedy", "everyday life", "heartwarming", "story", "stories", "funny"}
TONE_HOOK = {"tense": "WAIT FOR IT", "playful": "SO FUNNY", "tender": "AWWW", "sad": "OH NO", "joyful": "LOVE THIS", "eerie": "WHAT WAS THAT?", "calm": "STORYTIME"}
FOOTER = "New funny little stories about everyday people. Subscribe to tidalfolio so you never miss the next part."


def _tag(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _hash(s):
    t = _tag(s)
    return ("#" + t) if 2 <= len(t) <= 30 else None


def _uniq(seq):
    seen, out = set(), []
    for x in seq:
        k = x.lower()
        if x and k not in seen:
            seen.add(k)
            out.append(x)
    return out


def hook_for(script):
    """a 1 to 3 word tease for the thumbnail. The story's own hook if it has one, else one that fits the key scene's tone."""
    h = (script.get("thumbnail_hook") or "").strip()
    if h:
        return h.upper()[:22]
    try:
        sc = script["scenes"][int(script.get("thumbnail_scene", 1)) - 1]
        return TONE_HOOK.get(sc.get("tone", "calm"), "STORYTIME")
    except (KeyError, IndexError, ValueError):
        return "STORYTIME"


def _roles(script):
    out = []
    for r in script.get("cast_roles") or []:
        r = str(r).strip().lower()
        if r and r not in out:
            out.append(r)
    return out


def _story_tags(script, yt):
    """tags that are about THIS story: the cast, then the writer's own specific tags (generic ones are added separately)"""
    roles = _roles(script)
    own = [t.strip().lower() for t in yt.get("tags", []) if t.strip() and t.strip().lower() not in GENERIC]
    return _uniq(roles + own)


def build(script, total=None):
    yt, tt = dict(script.get("youtube") or {}), dict(script.get("tiktok") or {})
    sp = script.get("series_part")
    short = str(script.get("short_title") or script.get("title", "")).split(" (Part")[0].strip()
    roles = _roles(script)
    story_tags = _story_tags(script, yt)
    teaser = re.sub(r"\n\nPart \d+ of \d+.*$", "", (yt.get("description") or "").strip(), flags=re.S).strip()

    # ---- hashtags: story-specific first, then the channel's
    niche = [h for h in (_hash(t) for t in story_tags) if h][:6]
    brand = ["#" + t for t in BRAND_TAGS]
    all_tags = _uniq(niche + brand)

    # ---- YouTube
    title = (yt.get("title") or script.get("title") or short).strip()
    part_line = ""
    if sp and sp.get("of", 1) > 1:
        part_line = f"Part {sp['part']} of {sp['of']} of \"{sp['story']}\". " + (f"Part {sp['part'] + 1} is next, subscribe so you don't miss it." if sp["part"] < sp["of"] else "The end. Watch the story from Part 1 in the playlist.")
    cast_line = ("In this story: " + ", ".join(roles) + ".") if roles else ""
    yt_tags_hash = _uniq(["#Shorts"] + niche[:2] + ["#tidalfolio", "#storytime", "#animatedstory"])[:8]
    desc = "\n\n".join(x for x in (teaser, part_line, cast_line, FOOTER, " ".join(yt_tags_hash)) if x)
    tags, total_len = [], 0
    for t in _uniq(story_tags + EVERGREEN + ["shorts"]):
        if total_len + len(t) + 1 > 450 or len(tags) >= 15:
            break
        tags.append(t)
        total_len += len(t) + 1
    youtube = dict(yt)
    youtube.update(title=title[:100], description=desc[:4900], tags=tags, hashtags=yt_tags_hash)

    # ---- TikTok: a short hook and five hashtags
    cap = (tt.get("caption") or teaser[:130]).strip()
    tt_tags = _uniq([h for h in tt.get("hashtags", []) if h.startswith("#")] + niche[:2] + ["#tidalfolio", "#storytime", "#funnystories"])[:5]
    tiktok = dict(tt)
    tiktok.update(caption=cap[:150], hashtags=tt_tags)

    # ---- Instagram Reels / Facebook Reels
    nxt = f" Follow @{CHANNEL} for Part {sp['part'] + 1}." if sp and sp["part"] < sp["of"] else f" Follow @{CHANNEL} for more stories."
    ig_tags = _uniq(niche[:5] + ["#reels", "#storytime", "#animatedstory", "#funnystories", "#cartoon", "#tidalfolio"])[:10]
    instagram = {"caption": (cap + "\n\n" + teaser[:260] + "\n" + nxt.strip() + "\n\n" + " ".join(ig_tags))[:2200], "hashtags": ig_tags}
    facebook = {"caption": (cap + "\n\n" + teaser[:260] + "\n" + nxt.strip() + "\n\n" + " ".join(ig_tags[:3] + ["#tidalfolio"]))[:2200]}
    return {"youtube": youtube, "tiktok": tiktok, "instagram": instagram, "facebook": facebook, "thumbnail_hook": hook_for(script)}


def with_hashtags(desc, tags=("#Shorts", "#storytime", "#tidalfolio")):
    """safety net for posting scripts: make sure a description carries hashtags"""
    return desc if "#" in desc else (desc.rstrip() + "\n\n" + " ".join(tags)).strip()
