#!/usr/bin/env python3
"""Write new tidalfolio scripts with the OpenAI API and add them to queue.txt.

  python generate_script.py --ensure 1          # make sure at least 1 unrendered script is queued
  python generate_script.py --count 3           # write 3 new scripts now
  python generate_script.py --series "Funny Animals" --idea "a goat who refuses to leave a car roof"

Needs OPENAI_API_KEY. Model: OPENAI_TEXT_MODEL (default gpt-4o-mini; set a stronger model for better stories).
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
SFX = {"hit", "whoosh", "splash", "boom", "sting", "tick", "riser"}
FOCUS = {"left", "center", "right"}
WORDS_PER_SEC = 2.4          # conservative narration speed
LEAD, TAIL, MIN_SCENE = 0.30, 0.55, 3.0
MIN_RUNTIME = 110.0          # channel rule: at least 90s, almost 120s. The estimate runs ~7s high, so 110-124 lands at roughly 103-117s real
MAX_RUNTIME = 124.0


def system_prompt():
    return f"""You write scripts for "tidalfolio", a YouTube/TikTok comedy channel about animals, plants, insects, birds, fish and reptiles.
Videos are image sequences with a dramatic narrator. The only people allowed are the plain stick-figure everyman characters of the MIRROR act (rule 9).

CHANNEL RULES (all mandatory):
- Audience is all ages INCLUDING adults. Humour must be witty and dry, never childish, never cartoonish or babyish. No baby talk, no puns on every line.
- Narrator voice is dramatic and intense: movie-trailer gravity applied to tiny animal conflicts. Fast-paced, action-oriented.
- Total runtime must be between {MIN_RUNTIME:.0f} and {MAX_RUNTIME:.0f} seconds. Each scene lasts about 0.85 seconds plus its narration at {WORDS_PER_SEC} words per second, so write 24 to 28 scenes with 6 to 14 words of narration each (roughly 245 to 275 words in total). Aim for a finished video of about 110 to 118 seconds: never under 90, never over 120.
- STORY ENGINE (the most important rule; a funny video with no story gets watched once and forgotten):
  1. STAKES FIRST. Scene 1 narration (max 14 words) states a high-stakes premise a stranger understands instantly, e.g. "A kingfisher had three days to repay a debt to a crow." Never open with scenery, a greeting or the channel name.
  2. ONE PROTAGONIST who WANTS something badly, faces an obstacle, and has something to lose if they fail. Name them. The viewer must be able to say "I hope Marco..." about them.
  3. THREE ESCALATING REVERSALS. Each one changes the situation and makes it worse or stranger; each must flip what the viewer hopes for. No scene may merely repeat the previous one.
  4. ONE REAL EMOTIONAL BEAT in the middle third (loyalty, shame, fear, tenderness, a sacrifice) played straight with no joke for that scene, so the later jokes land harder.
  5. A HAUNTING LAST LINE: calm, short, quietly impossible or unresolved. The comedy stays dry; the feeling is dread or wonder.
  6. AN OPEN THREAD: end with one unresolved consequence or question that makes a Part 2 necessary. The final scene narration is the haunting line; the sign-off "This is tidalfolio." may follow only in the same final scene.
  7. THE SHAREABLE MOMENT: one line or image so absurd or striking that a viewer would show a friend. Mark it with "shareable_scene" (1-based).
  8. A LESSON FOR HUMANS. Every episode teaches one real human lesson (courage, generosity, pride, patience, honesty, jealousy, loyalty, fear, greed, forgiveness, humility, curiosity...) through what the animals do and what it costs them. The lesson is the reason the protagonist's choice at the emotional beat matters, so story and lesson are one thing. SHOW it through consequence; never lecture. Forbidden: "the moral is", "remember kids", "lesson learned", any sermon. At most one understated line (a character's remark or the narrator's dry observation) may point at it, and the last haunting line must stay unresolved, not preachy. Write the lesson as ONE plain sentence in story.lesson (max 25 words), something an adult would nod at and a child could repeat. Never reuse a lesson already used on the channel.
  9. THE MIRROR (the lesson reaches humans). About two thirds in, right after the animal story has shown its lesson in action (after the emotional beat and the choice), cut away for 3 to 5 consecutive scenes to a short HUMAN vignette: a plain stick-figure everyman (white round head, simple grey clothes, thin dark outline) in an ordinary modern place (office, shop, kitchen, school, bus stop) facing the SAME lesson in a small everyday situation, with the same shape of choice and the same kind of consequence. It must be a complete miniature (want, choice, consequence), never a recap. The first mirror narration is a short dry bridge like "Humans live by this river too." (adapt the animal's world). Then cut back to the animal story for the ending twist. The mirror scenes are not the first scene, not among the last three, and never explain the lesson. Give each mirror scene "look": "mirror"; put "transition": "dissolve" on the first mirror scene and on the first animal scene after it. Define the mirror art style in top-level "style_mirror" (flat, clean 2D editorial illustration, expressive round-headed stick figures, warm light, {{frame}}, no text, no watermark) and add the human characters (e.g. "human", "colleague") to "characters".
- Each image_prompt describes ONE frozen moment and states each visible character's exact action and expression beat by beat (what the body, wings, beak, legs, eyes are doing). No broad summaries. Under 600 characters each. Prefer dramatic or slow-motion moments (frozen splashes, mid-air collisions, extreme close-ups).
- Characters: 2 to 4 recurring characters (plus the witness), each with a locked visual description (species, colours, size, distinctive feature, build). The "characters" list in a scene uses the keys from the characters object. Use the same key whenever that character appears.
- Animals are never harmed: slapstick mishaps only. No real people, brands, logos or text in images.
- Each scene picks a motion from: zoom_in, zoom_out, pan_left, pan_right. Optional sfx from: hit, whoosh, splash, boom, sting, tick, riser (hit/splash/boom at impacts; sting at a shock or reveal; tick for suspense; riser before a big reveal; use at least 6 scenes).
- Each scene has a "delivery": a 3 to 8 word acting note for the narrator (e.g. "hushed, ominous", "fast and furious", "deadpan, flat", "breaking slightly, sincere", "slow, haunted whisper"). Vary it. The emotional beat uses sincere delivery.
- Each scene may have "focus": left, center or right: where the camera should aim in the image.
- Make the images feel like ACTION: in at least 8 scenes also give "image_prompt_b" (and "characters_b" if the cast differs): the SAME moment a half second later (the next frame of the action, e.g. wings now fully open, splash now at its peak). The video cuts between the two images so the scene moves. Same location and characters, only the action advances.

HUMOUR CRAFT (a viewer should smile or laugh several times):
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
  "story": {{"protagonist": "key", "want": "...", "risk": "what they lose", "lesson": "one plain sentence, the human lesson the story shows", "reversals": ["...", "...", "..."], "emotional_beat_scene": 1-based, "open_thread": "the unresolved question for Part 2"}},
  "style_mirror": "art style for the mirror act scenes",
  "thumbnail_scene": 1-based number of the funniest, most striking frame (it is the thumbnail),
  "shareable_scene": 1-based,
  "scenes": [{{"narration": "...", "delivery": "hushed, ominous", "characters": ["key"], "image_prompt": "...", "image_prompt_b": "optional next frame", "focus": "center", "motion": "zoom_in", "sfx": "hit"}}],
  "youtube": {{"title": "<=90 chars, curiosity-driven", "description": "2-4 sentences: the story teaser, then one sentence that hints at the lesson without spelling it out, then a subscribe line", "tags": ["8-12 tags"], "pinned_comment": "a question that makes viewers apply the lesson to their own life (e.g. 'Would you have given it away? Be honest.')"}},
  "tiktok": {{"caption": "<=140 chars hook", "hashtags": ["5-6 hashtags starting with #"]}}
}}

MIRROR SCENES carry two extra fields, written exactly like this (the literal word, nothing added): "look": "mirror". The first mirror scene and the first animal scene after the mirror act also get "transition": "dissolve". No other scene has "look" or "transition".

FINAL CHECKLIST (count before you answer):
- "witness" is listed in the "characters" array of at least 6 scenes.
- At least 8 scenes have "image_prompt_b"; at least 6 scenes have "sfx".
- Every key in a scene's "characters" array exists in the top-level "characters" object. Define "human" (and any colleague/boss) there if the mirror act uses them.
- "motion" is only zoom_in, zoom_out, pan_left or pan_right. "sfx" is only hit, whoosh, splash, boom, sting, tick or riser.
- 3 to 5 consecutive mirror scenes, in the second half, with at least 3 animal scenes after them."""


def previous_thread(series):
    """Open thread and last line of the latest episode of this series, for Part 2 continuity."""
    last = None
    for f in sorted(SCRIPTS.glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:
            continue
        if d.get("title", "").startswith(series):
            last = d
    if not last:
        return ""
    thread = (last.get("story") or {}).get("open_thread", "")
    end = last["scenes"][-1]["narration"] if last.get("scenes") else ""
    wit = (last.get("characters") or {}).get("witness", "")
    return (f"\nPrevious episode of this series ended with: \"{end}\" Open thread: {thread or 'none recorded'}. "
            f"You may pay it off or deepen it, but this episode must still stand alone. "
            + (f"Reuse the witness: {wit}" if wit else ""))


def used_lessons():
    out = []
    for f in sorted(SCRIPTS.glob("*.json")):
        try:
            out.append(((json.loads(f.read_text()).get("story") or {}).get("lesson") or "").strip())
        except Exception:
            continue
    return [x for x in out if x]


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


HUMAN_DEFAULTS = {
    "human": "Sam: a plain white round-headed stick figure in a grey hoodie and black trousers, thin dark outline, big worried eyes.",
    "colleague": "Jo: a plain white round-headed stick figure in a navy sweater with a lanyard, thin dark outline, tired eyes.",
    "boss": "The boss: a tall friendly stick figure with brown hair in a blue shirt, thin dark outline, warm smile.",
    "customer": "The customer: a plain white round-headed stick figure in a green coat, thin dark outline, patient eyes.",
    "shopkeeper": "The shopkeeper: a plain white round-headed stick figure in a brown apron, thin dark outline, tired smile.",
    "stranger": "The stranger: a plain white round-headed stick figure in a grey scarf and coat, thin dark outline, calm eyes.",
}


def repair(d):
    """Fix the mechanical mistakes a model keeps making, so retries are spent only on real story problems."""
    scenes, chars = d.get("scenes"), d.get("characters")
    if not isinstance(scenes, list) or not isinstance(chars, dict):
        return
    cycle = ["zoom_in", "pan_right", "zoom_out", "pan_left"]
    for i, s in enumerate(scenes):
        if not isinstance(s, dict):
            continue
        m = str(s.get("motion", "")).strip().lower().replace(" ", "_").replace("-", "_")
        s["motion"] = m if m in MOTIONS else cycle[i % 4]
        sfx = s.get("sfx")
        if isinstance(sfx, list):
            sfx = next((x for x in sfx if isinstance(x, str) and x.strip().lower() in SFX), None)
        sfx = sfx.strip().lower() if isinstance(sfx, str) else None
        if sfx in SFX:
            s["sfx"] = sfx
        else:
            s.pop("sfx", None)
        if s.get("focus") not in FOCUS:
            s.pop("focus", None)
        look = str(s.get("look", "")).strip().lower()
        if look.startswith("mirror"):
            s["look"] = "mirror"
        else:
            s.pop("look", None)
        if str(s.get("transition", "")).strip().lower().startswith("dissolve"):
            s["transition"] = "dissolve"
        else:
            s.pop("transition", None)
        if not isinstance(s.get("characters"), list):
            s["characters"] = []
        for c in s["characters"]:
            if isinstance(c, str) and c not in chars and c in HUMAN_DEFAULTS:
                chars[c] = HUMAN_DEFAULTS[c]       # the model used a human key without defining it
    mir = [i for i, s in enumerate(scenes) if isinstance(s, dict) and s.get("look") == "mirror"]
    if 3 <= len(mir) <= 5 and mir == list(range(mir[0], mir[0] + len(mir))):
        scenes[mir[0]]["transition"] = "dissolve"
        if mir[-1] + 1 < len(scenes):
            scenes[mir[-1] + 1]["transition"] = "dissolve"


def validate(d):
    repair(d)
    errs = []
    chars, scenes = d.get("characters"), d.get("scenes")
    if not isinstance(chars, dict) or not 2 <= len(chars) <= 9:
        errs.append("characters must be an object with 2 to 9 entries (animals, witness and the mirror-act humans)")
        chars = chars if isinstance(chars, dict) else {}
    if not isinstance(scenes, list) or not 18 <= len(scenes) <= 32 or not all(isinstance(s, dict) for s in scenes):
        return errs + ["scenes must be a list of 18 to 32 scenes (aim for 24 to 28)"]
    if not isinstance(d.get("style_mirror"), str) or len(d["style_mirror"].split()) < 8:
        errs.append("style_mirror (the mirror act's art style) is required")
    mir = [i for i, s in enumerate(scenes) if s.get("look") == "mirror"]
    if not 3 <= len(mir) <= 5 or mir != list(range(mir[0], mir[0] + len(mir))):
        errs.append('the mirror act needs 3 to 5 consecutive scenes with "look": "mirror"')
    else:
        if mir[0] < len(scenes) * 0.4 or mir[-1] > len(scenes) - 4:
            errs.append("the mirror act must sit in the middle-to-late story, with at least 3 animal scenes after it")
        elif scenes[mir[0]].get("transition") != "dissolve" or scenes[mir[-1] + 1].get("transition") != "dissolve":
            errs.append('put "transition": "dissolve" on the first mirror scene and on the first scene after it')
    if "witness" not in chars:
        errs.append('characters must include a "witness" (a silent deadpan bystander creature)')
    elif sum("witness" in s.get("characters", []) for s in scenes) < 6:
        errs.append('the "witness" must appear in at least 6 scenes (list it in the scene "characters")')
    for i, s in enumerate(scenes, 1):
        for k in ("narration", "image_prompt", "motion"):
            if not isinstance(s.get(k), str) or not s[k].strip():
                errs.append(f"scene {i} missing {k}")
        if s.get("motion") not in MOTIONS:
            errs.append(f"scene {i} motion must be one of {sorted(MOTIONS)}")
        if s.get("focus") not in (None, "") and s.get("focus") not in FOCUS:
            errs.append(f"scene {i} focus must be one of {sorted(FOCUS)}")
        if s.get("image_prompt_b") is not None and not str(s["image_prompt_b"]).strip():
            s.pop("image_prompt_b")
        if s.get("sfx") not in (None, "") and s.get("sfx") not in SFX:
            errs.append(f"scene {i} sfx must be one of {sorted(SFX)}")
        for c in s.get("characters", []):
            if c not in chars:
                errs.append(f"scene {i} uses unknown character key '{c}'")
        if len(s.get("image_prompt", "")) > 700:
            errs.append(f"scene {i} image_prompt is too long (max 700 chars)")
        if len(s.get("narration", "").split()) > 20:
            errs.append(f"scene {i} narration is too long (max 18 words; split it into two scenes)")
    st = d.get("story")
    if not isinstance(st, dict) or not all(st.get(k) for k in ("protagonist", "want", "risk", "open_thread")) \
            or not isinstance(st.get("reversals"), list) or len(st["reversals"]) < 3:
        errs.append("story block needs protagonist, want, risk, 3 reversals and open_thread")
    elif st["protagonist"] not in chars:
        errs.append("story.protagonist must be a key in characters")
    if isinstance(st, dict):
        lesson = str(st.get("lesson", "")).strip()
        if not lesson or len(lesson.split()) > 25 or len(lesson.split()) < 5:
            errs.append("story.lesson must be one plain sentence of 5 to 25 words: the human lesson the story teaches")
        elif re.search(r"\bthe moral\b|\blesson learned\b|\bremember,? kids\b", json.dumps(scenes).lower()):
            errs.append("the narration must not preach: remove phrases like 'the moral is' or 'lesson learned'; show the lesson through consequence")
    if len(scenes[0].get("narration", "").split()) > 14:
        errs.append("scene 1 narration must be a stakes-first hook of at most 14 words")
    if sum(bool(s.get("image_prompt_b")) for s in scenes) < 6:
        errs.append("give image_prompt_b (the next-frame image) in at least 6 scenes so the video has action")
    if sum(bool(s.get("sfx")) for s in scenes) < 6:
        errs.append("use sfx in at least 6 scenes")
    if sum(bool(s.get("delivery")) for s in scenes) < len(scenes) - 1:
        errs.append("every scene needs a delivery note")
    if not errs:
        rt = estimate_runtime(scenes)
        if rt < MIN_RUNTIME:
            errs.append(f"estimated runtime {rt:.0f}s is under {MIN_RUNTIME:.0f}s: add scenes or lengthen narration")
        if rt > MAX_RUNTIME:
            errs.append(f"estimated runtime {rt:.0f}s is over {MAX_RUNTIME:.0f}s: cut scenes or shorten narration")
        if not 1 <= int(d.get("shareable_scene", 0) or 0) <= len(scenes):
            errs.append("shareable_scene must be a valid scene number")
        if not 1 <= int(d.get("thumbnail_scene", 0) or 0) <= len(scenes):
            errs.append("thumbnail_scene must be a valid scene number")
    for k in ("youtube", "tiktok"):
        if not isinstance(d.get(k), dict):
            errs.append(f"missing {k} block")
    if isinstance(d.get("youtube"), dict) and not d["youtube"].get("title"):
        errs.append("youtube.title missing")
    return errs


def call_openai(messages, temperature=1.0):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        sys.exit("OPENAI_API_KEY is not set. Add it as a GitHub secret (see README).")
    model = os.environ.get("OPENAI_TEXT_MODEL") or "gpt-4o-mini"
    last = None
    for attempt in range(4):
        r = requests.post("https://api.openai.com/v1/chat/completions", timeout=180,
                          headers={"Authorization": f"Bearer {key}"},
                          json={"model": model, "messages": messages, "temperature": temperature,
                                "response_format": {"type": "json_object"}})
        if r.ok:
            return r.json()["choices"][0]["message"]["content"]
        last = f"{r.status_code} {r.text[:300]}"
        if r.status_code in (400, 401, 403, 404):   # won't fix itself by retrying
            break
        time.sleep(5 * (attempt + 1))
    sys.exit(f"OpenAI request failed: {last}")


PUNCH_UP_PROMPT = """You are a ruthless script editor for a deadpan animal-comedy channel. Below is a valid draft script (JSON).
Rewrite it to be better while keeping the exact same JSON structure, character keys, and every rule from the original brief (length window, 6-14 words of narration per scene, beat-by-beat image prompts, silent witness in 6+ scenes, ending that leaves the viewer pondering).
Checklist:
1. Cut every joke that is merely cute; replace it with something specific, absurd and deadpan.
2. Sharpen the narrator: more gravity, more precise numbers, understatement after big moments.
3. Add or improve one small silent visual gag in each image_prompt.
4. Make sure a planted detail pays off in the final three scenes with an unexplained, quietly impossible twist, and the last line is short, calm and leaves a question hanging. Do not explain it.
5. Keep it all-ages and not childish. No animal is harmed.
6. Protect the story engine: stakes in the first line, a protagonist who wants something, three escalating reversals, one sincere emotional beat with no joke, a haunting last line and an open thread. If any is weak, fix it first; story beats jokes.
7. Protect the lesson (story.lesson): it must be shown through the protagonist's choice and its cost, never preached. If it is vague or preachy, make it concrete and quiet.
8. Keep the MIRROR act (the human stick-figure vignette, scenes with look "mirror", style_mirror, dissolve transitions) intact and make sure it is a real miniature of the same lesson, not a recap.
8. Keep delivery, focus, sfx, image_prompt_b and the story/shareable_scene fields.
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
            + previous_thread(series) + "\n"
            + ("Lessons already used on the channel (teach a different one):\n- " + "\n- ".join(used_lessons()) + "\n" if used_lessons() else "")
            + ("Do NOT reuse these existing episodes or their premises:\n- " + "\n- ".join(titles) if titles else ""))
    messages = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": user}]
    data, errs = None, []
    for attempt in range(4):
        raw = call_openai(messages, 1.0 if attempt == 0 else 0.5)   # calmer on retries: fix, don't reinvent
        try:
            data = json.loads(raw)
            errs = validate(data)
        except json.JSONDecodeError as e:
            data, errs = None, [f"reply was not valid JSON ({e})"]
        if not errs:
            break
        print(f"  attempt {attempt + 1} rejected: {'; '.join(errs)}")
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "Fix ONLY these problems and return the full JSON with everything else unchanged "
                      "(keep every character key defined in the top-level \"characters\" object):\n- " + "\n- ".join(errs)}]
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
        "story": data.get("story"), "shareable_scene": int(data.get("shareable_scene", 1)),
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
    return [q for q in lines(ROOT / "queue.txt") if q not in done and (SCRIPTS / q).exists()]


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
