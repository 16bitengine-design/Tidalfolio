#!/usr/bin/env python3
"""Write new tidalfolio scripts with the OpenAI API and add them to queue.txt.

  python generate_script.py --ensure 1          # make sure at least 1 unrendered script is queued
  python generate_script.py --count 3           # write 3 new scripts now
  python generate_script.py --series "Funny Animals" --idea "a goat who refuses to leave a car roof"

Needs OPENAI_API_KEY. Model: OPENAI_TEXT_MODEL (default gpt-4o-mini; set a stronger model for funnier scripts).
Every script is checked against the channel rules before it is saved; failures are retried with feedback.
"""
import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"

SERIES = {
    "Bird Banter": "birds of any kind: rivalries, heists, bad landings, territorial drama",
    "Funny Animals": "mammals: farm, wild or domestic, in absurd high-stakes situations",
    "Tiny Troublemakers": "insects, spiders and other tiny creatures causing outsized chaos",
    "Underwater Laughs": "fish, octopuses, crabs and other aquatic life in dramatic underwater comedy",
    "Wild Moments": "reptiles, amphibians and the odd plant, treated like epic nature-documentary thrillers",
}

STYLE = ("Cinematic stylized animated-film look, richly detailed 3D render, dramatic rim lighting, "
         "shallow depth of field, expressive but realistic animal faces, {frame}, no text, no watermark.")

MOTIONS = {"zoom_in", "zoom_out", "pan_left", "pan_right"}
SFX = {"hit", "whoosh", "splash"}
WORDS_PER_SEC = 2.4          # conservative narration speed
LEAD, TAIL, MIN_SCENE = 0.30, 0.55, 3.0
MIN_RUNTIME = 98.0           # channel rule: 1.5 to 2 minutes; keep a margin on both sides
MAX_RUNTIME = 114.0


def system_prompt():
    return f"""You write scripts for "tidalfolio", a YouTube/TikTok comedy channel about animals, plants, insects, birds, fish and reptiles.
Videos are image sequences with a dramatic narrator, no on-screen people.

CHANNEL RULES (all mandatory):
- Audience is all ages INCLUDING adults. Humour must be witty and dry, never childish, never cartoonish or babyish. No baby talk, no puns on every line.
- Narrator voice is dramatic and intense: movie-trailer gravity applied to tiny animal conflicts. Fast-paced, action-oriented.
- Total runtime must be between {MIN_RUNTIME:.0f} and {MAX_RUNTIME:.0f} seconds. Each scene lasts about 0.85 seconds plus its narration at {WORDS_PER_SEC} words per second, so write 21 to 26 scenes with 6 to 14 words of narration each (roughly 210 to 250 words in total). A new image every 4 to 6 seconds keeps the pace fast.
- One clear story: a hook in the first 5 seconds, three escalating attempts or complications, a reversal, then a punchline ending. Last line lands the joke; it may include the sign-off "This is tidalfolio." only in the final scene.
- Each image_prompt describes ONE frozen moment and states each visible character's exact action and expression beat by beat (what the body, wings, beak, legs, eyes are doing). No broad summaries. Under 600 characters each. Prefer dramatic or slow-motion moments (frozen splashes, mid-air collisions, extreme close-ups).
- Characters: 2 to 4 recurring characters, each with a locked visual description (species, colours, size, distinctive feature, build). The "characters" list in a scene uses the keys from the characters object. Use the same key whenever that character appears.
- Animals are never harmed: slapstick mishaps only. No real people, brands, logos or text in images.
- Each scene picks a motion from: zoom_in, zoom_out, pan_left, pan_right. Optional sfx from: hit, whoosh, splash (use at impacts, entrances, water).

HUMOUR CRAFT (this is what makes the video work; a viewer should smile or laugh several times):
- Deadpan gravity vs trivial stakes: the narrator treats a squabble over a branch like the fall of an empire, and never winks at the audience.
- Specifics beat generalities: "seventeen minnows", "three thousand dives", "once out-stared a heron". Invent precise, absurd numbers, histories and rules.
- Rule of three where the third item breaks the pattern. Understatement after a big action ("Physics took notes.").
- Every image_prompt contains at least one small visual gag a viewer can spot (a bystander reacting, an object out of place, a wildly overserious expression). Keep gags visual and silent, never text.
- SILENT WITNESS running gag: one extra creature (use the character key "witness", e.g. a small frog, a snail, a crow) watches the action from the background with zero expression in at least 6 scenes, spread across the video. Its reactions are never explained.
- Callbacks: one odd object or fact planted early must return later in a way that raises a question.
- Jokes are original and observational. No memes, no catchphrases, no baby talk, no sarcasm aimed at the viewer.

THE ENDING (mandatory): the video must leave the viewer pondering what exactly they just watched. In the last three scenes, introduce one unexplained, quietly impossible detail that recontextualises the story without explaining it (for example: the object from the callback turns up somewhere it should not be, or the witness is suddenly looking straight into the camera as if it knew all along). The narrator stays completely sincere and moves on as if nothing odd happened, and the final line is calm, short and leaves a question hanging (e.g. "Nobody asked how."). Never explain the mystery. The story itself must still make sense and the ending must feel deliberate, not random.

Reply with ONE JSON object only, in exactly this shape:
{{
  "title": "Series Name #N: Episode Title",
  "characters": {{"key": "Name: locked visual description"}},
  "thumbnail_scene": 1-based number of the funniest, most absurd frame (it is the thumbnail),
  "scenes": [{{"narration": "...", "characters": ["key"], "image_prompt": "...", "motion": "zoom_in", "sfx": "hit"}}],
  "youtube": {{"title": "<=90 chars, curiosity-driven", "description": "2-4 sentences + subscribe line", "tags": ["8-12 tags"], "pinned_comment": "a question that invites comments"}},
  "tiktok": {{"caption": "<=140 chars hook", "hashtags": ["5-6 hashtags starting with #"]}}
}}"""


def existing():
    titles, counts = [], {s: 0 for s in SERIES}
    for f in sorted(SCRIPTS.glob("*.json")):
        try:
            t = json.loads(f.read_text()).get("title", "")
        except Exception:
            continue
        titles.append(t)
        for s in SERIES:
            if t.startswith(s):
                counts[s] += 1
    return titles, counts


def next_number():
    nums = [int(m.group(1)) for f in SCRIPTS.glob("*.json") if (m := re.match(r"(\d+)-", f.name))]
    return (max(nums) + 1) if nums else 1


def estimate_runtime(scenes):
    return sum(max(MIN_SCENE, LEAD + len(s["narration"].split()) / WORDS_PER_SEC + TAIL) for s in scenes)


def validate(d):
    errs = []
    chars, scenes = d.get("characters"), d.get("scenes")
    if not isinstance(chars, dict) or not 2 <= len(chars) <= 5:
        errs.append("characters must be an object with 2 to 4 entries")
        chars = chars if isinstance(chars, dict) else {}
    if not isinstance(scenes, list) or not 18 <= len(scenes) <= 32:
        return errs + ["scenes must be a list of 18 to 32 scenes (aim for 21 to 26)"]
    if "witness" not in chars:
        errs.append('characters must include a "witness" (a silent deadpan bystander creature)')
    elif sum("witness" in s.get("characters", []) for s in scenes) < 5:
        errs.append('the "witness" must appear in at least 6 scenes (list it in the scene "characters")')
    for i, s in enumerate(scenes, 1):
        for k in ("narration", "image_prompt", "motion"):
            if not isinstance(s.get(k), str) or not s[k].strip():
                errs.append(f"scene {i} missing {k}")
        if s.get("motion") not in MOTIONS:
            errs.append(f"scene {i} motion must be one of {sorted(MOTIONS)}")
        if s.get("sfx") not in (None, "") and s.get("sfx") not in SFX:
            errs.append(f"scene {i} sfx must be one of {sorted(SFX)}")
        for c in s.get("characters", []):
            if c not in chars:
                errs.append(f"scene {i} uses unknown character key '{c}'")
        if len(s.get("image_prompt", "")) > 700:
            errs.append(f"scene {i} image_prompt is too long (max 700 chars)")
        if len(s.get("narration", "").split()) > 20:
            errs.append(f"scene {i} narration is too long (max 18 words; split it into two scenes)")
    if not errs:
        rt = estimate_runtime(scenes)
        if rt < MIN_RUNTIME:
            errs.append(f"estimated runtime {rt:.0f}s is under {MIN_RUNTIME:.0f}s: add scenes or lengthen narration")
        if rt > MAX_RUNTIME:
            errs.append(f"estimated runtime {rt:.0f}s is over {MAX_RUNTIME:.0f}s: cut scenes or shorten narration")
        if not 1 <= int(d.get("thumbnail_scene", 0) or 0) <= len(scenes):
            errs.append("thumbnail_scene must be a valid scene number")
    for k in ("youtube", "tiktok"):
        if not isinstance(d.get(k), dict):
            errs.append(f"missing {k} block")
    if isinstance(d.get("youtube"), dict) and not d["youtube"].get("title"):
        errs.append("youtube.title missing")
    return errs


def call_openai(messages):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY is not set. Add it as a GitHub secret (see README).")
    model = os.environ.get("OPENAI_TEXT_MODEL") or "gpt-4o-mini"
    last = None
    for attempt in range(4):
        r = requests.post("https://api.openai.com/v1/chat/completions", timeout=180,
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": model, "messages": messages, "temperature": 1.0,
                                "response_format": {"type": "json_object"}})
        if r.ok:
            return r.json()["choices"][0]["message"]["content"]
        last = f"{r.status_code} {r.text[:300]}"
        if r.status_code in (400, 401, 403, 404):   # won't fix itself by retrying
            break
        time.sleep(5 * (attempt + 1))
    sys.exit(f"OpenAI request failed: {last}")


PUNCH_UP_PROMPT = """You are a ruthless comedy script editor for a deadpan animal-comedy channel. Below is a valid draft script (JSON).
Rewrite it to be funnier while keeping the exact same JSON structure, character keys, and every rule from the original brief (length window, 6-14 words of narration per scene, beat-by-beat image prompts, silent witness in 6+ scenes, ending that leaves the viewer pondering).
Checklist:
1. Cut every joke that is merely cute; replace it with something specific, absurd and deadpan.
2. Sharpen the narrator: more gravity, more precise numbers, understatement after big moments.
3. Add or improve one small silent visual gag in each image_prompt.
4. Make sure a planted detail pays off in the final three scenes with an unexplained, quietly impossible twist, and the last line is short, calm and leaves a question hanging. Do not explain it.
5. Keep it all-ages and not childish. No animal is harmed.
Return ONLY the full improved JSON."""


def punch_up(data):
    if os.environ.get("PUNCH_UP", "1") == "0":
        return data
    raw = call_openai([{"role": "system", "content": system_prompt()},
                       {"role": "user", "content": PUNCH_UP_PROMPT + "\n\n" + json.dumps(data, ensure_ascii=False)}])
    try:
        better = json.loads(raw)
        errs = validate(better)
    except json.JSONDecodeError:
        errs = ["not valid JSON"]
    if errs:
        print("  punch-up pass rejected (" + "; ".join(errs[:2]) + "): keeping the first draft")
        return data
    print("  punch-up pass applied")
    return better


def write_one(series=None, idea=None):
    titles, counts = existing()
    if not series:
        series = min(SERIES, key=lambda s: (counts[s], list(SERIES).index(s)))
    ep = counts[series] + 1
    user = (f"Write the next episode of the series \"{series}\" (episode #{ep}). "
            f"Series theme: {SERIES[series]}.\n"
            + (f"Episode idea to develop: {idea}\n" if idea else "Invent a fresh, specific premise.\n")
            + ("Do NOT reuse these existing episodes or their premises:\n- " + "\n- ".join(titles) if titles else ""))
    messages = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": user}]
    data, errs = None, []
    for attempt in range(4):
        raw = call_openai(messages)
        try:
            data = json.loads(raw)
            errs = validate(data)
        except json.JSONDecodeError as e:
            data, errs = None, [f"reply was not valid JSON ({e})"]
        if not errs:
            break
        print(f"  attempt {attempt + 1} rejected: {'; '.join(errs[:4])}")
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "Fix these problems and return the full corrected JSON:\n- " + "\n- ".join(errs)}]
    else:
        sys.exit("Could not get a valid script after 4 attempts. Last problems: " + "; ".join(errs))

    data = punch_up(data)
    n = next_number()
    title = data.get("title") or f"{series} #{ep}"
    if not title.startswith(series):
        title = f"{series} #{ep}: {title}"
    slug = f"{n:03}-" + re.sub(r"[^a-z0-9]+", "-", title.rsplit(":", 1)[-1].lower()).strip("-")[:40]
    script = {
        "slug": slug, "title": title, "aspects": ["16:9", "9:16"],
        "seed": random.randint(1, 999999), "thumbnail_scene": int(data["thumbnail_scene"]),
        "burn_captions": True,
        "voice": {"voice": "en-GB-RyanNeural", "rate": "-10%", "pitch": "-8Hz"},
        "style": STYLE, "characters": data["characters"], "scenes": data["scenes"],
        "youtube": data["youtube"], "tiktok": data["tiktok"],
    }
    path = SCRIPTS / f"{slug}.json"
    path.write_text(json.dumps(script, indent=2, ensure_ascii=False))
    with open(ROOT / "queue.txt", "a") as f:
        f.write(path.name + "\n")
    print(f"Wrote {path.name} (~{estimate_runtime(script['scenes']):.0f}s) and queued it.")
    return path.name


def unrendered():
    def lines(p):
        return [l.strip() for l in p.read_text().splitlines() if l.strip() and not l.startswith("#")] if p.exists() else []
    done = set(lines(ROOT / "done.txt"))
    return [q for q in lines(ROOT / "queue.txt") if q not in done]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ensure", type=int, help="write scripts until this many unrendered ones are queued")
    ap.add_argument("--count", type=int, default=0, help="write this many new scripts")
    ap.add_argument("--series", choices=list(SERIES))
    ap.add_argument("--idea")
    a = ap.parse_args()
    SCRIPTS.mkdir(exist_ok=True)
    if a.ensure is not None:
        need = a.ensure - len(unrendered())
        if need <= 0:
            print(f"Queue already has {len(unrendered())} script(s): nothing to write.")
            return
        a.count = need
    for _ in range(max(1, a.count)):
        write_one(a.series, a.idea)


if __name__ == "__main__":
    main()
