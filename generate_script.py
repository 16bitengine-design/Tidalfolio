#!/usr/bin/env python3
"""Write new tidalfolio scripts with the OpenAI API and add them to queue.txt.

  python generate_script.py --ensure 1          # make sure at least 1 unrendered script is queued
  python generate_script.py --count 3           # write 3 new scripts now
  python generate_script.py --series "Funny Animals" --idea "a goat who refuses to leave a car roof"
  python generate_script.py --parts 3 --idea "..."   # one story told as Part 1, Part 2, Part 3 (each 60-90 s)

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

STYLE = ("Hand-painted storybook illustration, rich watercolor and ink on textured paper, warm cinematic light, "
         "expressive animals with very human emotions, dry wit, sophisticated and a little melancholic rather than "
         "childish, the main subjects kept in the middle of the frame with room above them, {frame}, "
         "no text, no letters, no watermark.")

MOTIONS = {"zoom_in", "zoom_out", "pan_left", "pan_right"}
CAMERA = {"impact", "whoosh"}      # silent camera moves only: no sound effects exist on this channel
POP_KINDS = {"bubble", "label", "sticker"}
MAX_STICKERS = 8
FOCUS = {"left", "center", "right"}
WORDS_PER_SEC = 2.4          # conservative narration speed
LEAD, TAIL, MIN_SCENE = 0.30, 0.55, 3.0
MIN_RUNTIME = 72.0           # channel rule: every video runs 60 to 90 seconds. The estimate runs ~5s high, so 72-90 lands at roughly 67-85s real
MAX_RUNTIME = 90.0


def system_prompt():
    return f"""You write scripts for "tidalfolio", a YouTube/TikTok comedy channel about animals, plants, insects, birds, fish and reptiles.
Videos are illustrated storybook scenes with pop-ups, told by one narrator: a middle-aged man in his forties with a warm baritone, a gifted storyteller telling a tale he knows by heart to friends, who still finds it funny and never shows it. The only people allowed are the plain stick-figure everyman characters of the MIRROR act (rule 9).

CHANNEL RULES (all mandatory):
- Audience is all ages INCLUDING adults. Humour must be witty and dry, never childish, never cartoonish or babyish. No baby talk, no puns on every line.
- Narrator voice: a middle-aged male storyteller. Warm, grounded and bone-dry, treating tiny animal conflicts with total seriousness, never winking. He may open with a short aside ("Now, listen.") and may use a small "mm." or a sigh, but never baby talk, never a trailer voice, never shouting. Write sentences he could say aloud with a pause before the punchline.
- THE NARRATOR IS A STORYTELLER OUTSIDE THE STORY: he tells the tale to an audience that sits listening (think of a grandfather retelling Tom and Jerry to his grandson, or a gifted teacher telling a war to a class) and he must never let them get bored. He is NEVER part of the story and never mentions himself: no "I", "me", "my", "we", no "I saw", "I was there", no memories of his own, no opinions about himself. He tells it in the third person and mostly in the past tense, in vivid, specific, dramatic detail. He knows his audience is there, so he may use light storyteller's signposts that do not mention himself ("Now, here is where it goes wrong.", "And then, nothing.", "Hold that thought.", "Watch the crow."), at most one in every three scenes. He NEVER tells the listener what to do or think in life: no "you should", no advice, no moral, no lesson, no "remember that", no commands beyond those tiny signposts. HOLD THE AUDIENCE: withhold before a reveal, promise what is coming without spoiling it, slow right down at the frightening or tender part, speed up when things tumble, and drop in a dry joke when the audience needs to breathe. Open scenes like speech, not like a book: contractions, short punchy sentences, never "once upon a time", never encyclopedia or caption prose.
- STORYTELLING ETIQUETTE (the voice must never run at one speed or one tone): vary the PACE across the story: slower for suspense, secrets and the emotional beat, brisker for action and escalation, a clipped rush for the chase. Vary sentence length: a long rolling sentence of build-up, then a short one that lands. Put the key word LAST in a sentence so it can be stressed. Use silence as a tool: a long pause before a twist or punchline, a held beat after a shocking line. Let the voice drop to a hush before a reveal and open up at the triumph. Use the rule of three, and let the third item break the pattern. Use at most one rhetorical question in the whole story and let it hang. Never explain a joke. The story stays brisk and action-oriented overall.
- There is NO sound design: no sound effects exist. The only audio is his voice and a music bed. Never write sound effects, onomatopoeia or "*crash*" in the narration.
- Total runtime must be between {MIN_RUNTIME:.0f} and {MAX_RUNTIME:.0f} seconds. Each scene lasts about 0.85 seconds plus its narration at {WORDS_PER_SEC} words per second, so write 16 to 20 scenes with 6 to 12 words of narration each (roughly 140 to 175 words in total). Aim for a finished video of about 75 to 85 seconds: never under 60, never over 90.
- STORY ENGINE (the most important rule; a funny video with no story gets watched once and forgotten):
  1. STAKES FIRST. Scene 1 narration (max 14 words) states a high-stakes premise a stranger understands instantly, e.g. "A kingfisher had three days to repay a debt to a crow." Never open with scenery, a greeting or the channel name.
  2. ONE PROTAGONIST who WANTS something badly, faces an obstacle, and has something to lose if they fail. Name them. The viewer must be able to say "I hope Marco..." about them.
  3. THREE ESCALATING REVERSALS. Each one changes the situation and makes it worse or stranger; each must flip what the viewer hopes for. No scene may merely repeat the previous one.
  4. ONE REAL EMOTIONAL BEAT in the middle third (loyalty, shame, fear, tenderness, a sacrifice) played straight with no joke for that scene, so the later jokes land harder.
  5. A HAUNTING LAST LINE: calm, short, quietly impossible or unresolved. The comedy stays dry; the feeling is dread or wonder.
  6. AN OPEN THREAD: end with one unresolved consequence or question that makes a Part 2 necessary. The final scene narration is the haunting line; the sign-off "This is tidalfolio." may follow only in the same final scene.
  7. THE SHAREABLE MOMENT: one line or image so absurd or striking that a viewer would show a friend. Mark it with "shareable_scene" (1-based).
  8. A LESSON FOR HUMANS. Every episode teaches one real human lesson (courage, generosity, pride, patience, honesty, jealousy, loyalty, fear, greed, forgiveness, humility, curiosity...) through what the animals do and what it costs them. The lesson is the reason the protagonist's choice at the emotional beat matters, so story and lesson are one thing. SHOW it through consequence; never lecture. Forbidden: "the moral is", "remember kids", "lesson learned", any sermon. At most one understated line (a character's remark or the narrator's dry observation) may point at it, and the last haunting line must stay unresolved, not preachy. Write the lesson as ONE plain sentence in story.lesson (max 25 words), something an adult would nod at and a child could repeat. Never reuse a lesson already used on the channel. THE WHY BEHIND THE CHOICE: people rarely go wrong because they are fools. Pick ONE cause for the protagonist's key choice and write it in story.cause: "forgot" (they knew the value and lost it under pressure), "believed" (they sincerely thought it was the right thing and were wrong or only half right) or "no_options" (every path cost something and they took the least bad one). Show that cause through the protagonist's own reasoning and circumstances so a viewer understands the choice from the inside and never just judges it; for "believed" let their logic make real sense, for "no_options" make the alternatives visibly worse. Vary the cause from story to story, and make the human mirror scenes carry the SAME cause. Never state the cause aloud.
  9. THE MIRROR (the lesson reaches humans). About two thirds in, right after the animal story has shown its lesson in action (after the emotional beat and the choice), cut away for 3 to 5 consecutive scenes to a short HUMAN vignette: a plain stick-figure everyman (white round head, simple grey clothes, thin dark outline) in an ordinary modern place (office, shop, kitchen, school, bus stop) facing the SAME lesson in a small everyday situation, with the same shape of choice and the same kind of consequence. It must be a complete miniature (want, choice, consequence), never a recap. The first mirror narration is a short dry bridge like "Humans live by this river too." (adapt the animal's world). Then cut back to the animal story for the ending twist. The mirror scenes are not the first scene, not among the last three, and never explain the lesson. Give each mirror scene "look": "mirror"; put "transition": "dissolve" on the first mirror scene and on the first animal scene after it. Define the mirror art style in top-level "style_mirror" (flat, clean 2D editorial illustration, expressive round-headed stick figures, warm light, {{frame}}, no text, no watermark) and add the human characters (e.g. "human", "colleague") to "characters".
- Each image_prompt describes ONE frozen moment and states each visible character's exact action and expression beat by beat (what the body, wings, beak, legs, eyes are doing). No broad summaries. Under 600 characters each. Prefer dramatic or slow-motion moments (frozen splashes, mid-air collisions, extreme close-ups).
- Characters: 2 to 4 recurring characters (plus the witness), each with a locked visual description (species, colours, size, distinctive feature, build). The "characters" list in a scene uses the keys from the characters object. Use the same key whenever that character appears.
- Animals are never harmed: slapstick mishaps only. No real people, brands, logos or text in images.
- Each scene picks a motion from: zoom_in, zoom_out, pan_left, pan_right. Optional "camera": "impact" (a hard silent camera slam with shake and a white flash on a collision or shock) or "whoosh" (the camera whips across for an entrance). Use impact in at most 5 scenes and whoosh in at most 3.
- Each scene has a "delivery": a 3 to 8 word acting note for the narrator (e.g. "dry, deadpan", "hushed, conspiratorial", "slow, amused", "quietly sincere, softer", "low, haunted whisper"). Vary it. The emotional beat uses sincere delivery.
- Each scene also has a "pace": one of "slow", "measured", "steady", "brisk", "rushed". Never give more than three scenes in a row the same pace; use "slow" for the emotional beat and the final line, "brisk" or "rushed" for chases and escalation.
- TIMING TOOLS (use sparingly, they are what make the story dramatic): "pause_before" (seconds of silence before the line, 0.1 to 2.5; use 0.9 to 1.6 right before a twist or punchline) and "pause_after" (seconds of silence after the line, 0.2 to 2.5; use 1.0 to 1.8 after the shocking line and after the last line). Use each in at most 5 scenes and keep total runtime inside the window. Optionally "music": {{"silence_before": 1.0}} on at most 2 scenes: the music cuts out just before that line and returns after it. Optionally "freeze": true on at most 2 scenes: the picture stops dead on the reveal.
- POP-UPS bring each illustration to life: small things that bounce in over the picture on the beat of the joke. Aim to give 8 or more scenes a "popups" list (1 to 3 each). Kinds: "bubble" (a speech bubble with a short spoken line or reaction, max 4 words, e.g. "MINE.", "That was SPRING."; "tail" is "left" or "right"), "label" (a plain card for a time jump or a title, max 5 words, e.g. "Six hours later"), "sticker" (a small painted prop that pops in, with a "prompt" of max 12 words naming ONE object, e.g. "a single empty fishbone"). Use at most 8 stickers in the whole script and at least 5 bubbles in total. Each pop-up has "at" (seconds after the scene starts, between 0.8 and the scene's narration length), "x" and "y" (centre as fractions of the frame; y between 0.15 and 0.6 so it never covers the captions), "size" (width as a fraction of the frame, 0.16 to 0.3) and optional "hold" (seconds shown, 1.2 to 2.5). Pop-ups are the joke's punctuation: a bubble the witness never says, a label that undercuts the narrator. Never put text inside an image_prompt.
- Each scene may have "focus": left, center or right: where the camera should aim in the image.
- Make the images feel like ACTION: in at least 6 scenes also give "image_prompt_b" (and "characters_b" if the cast differs): the SAME moment a half second later (the next frame of the action, e.g. wings now fully open, splash now at its peak). The video cuts between the two images so the scene moves. Same location and characters, only the action advances.

HUMOUR CRAFT (a viewer should smile or laugh several times):
- Deadpan gravity vs trivial stakes: the narrator treats a squabble over a branch like the fall of an empire, and never winks at the audience.
- Specifics beat generalities: "seventeen minnows", "three thousand dives", "once out-stared a heron". Invent precise, absurd numbers, histories and rules.
- Rule of three where the third item breaks the pattern. Understatement after a big action ("Physics took notes.").
- Every image_prompt contains at least one small visual gag a viewer can spot (a bystander reacting, an object out of place, a wildly overserious expression). Keep gags visual and silent, never text.
- SILENT WITNESS running gag: one extra creature (use the character key "witness", e.g. a small frog, a snail, a crow) watches the action from the background with zero expression in at least 5 scenes, spread across the video. Its reactions are never explained.
- Callbacks: one odd object or fact planted early must return later in a way that raises a question.
- Jokes are original and observational. No memes, no catchphrases, no baby talk, no sarcasm aimed at the viewer.

THE ENDING (mandatory): the video must leave the viewer pondering what exactly they just watched. In the last three scenes, introduce one unexplained, quietly impossible detail that recontextualises the story without explaining it (for example: the object from the callback turns up somewhere it should not be, or the witness is suddenly looking straight into the camera as if it knew all along). The narrator stays completely sincere and moves on as if nothing odd happened, and the final line is calm, short and leaves a question hanging (e.g. "Nobody asked how."). Never explain the mystery. The story itself must still make sense and the ending must feel deliberate, not random.

Reply with ONE JSON object only, in exactly this shape:
{{
  "title": "Series Name #N: Episode Title",
  "characters": {{"key": "Name: locked visual description"}},
  "story": {{"protagonist": "key", "want": "...", "risk": "what they lose", "lesson": "one plain sentence, the human lesson the story shows", "cause": "forgot | believed | no_options", "reversals": ["...", "...", "..."], "emotional_beat_scene": 1-based, "open_thread": "the unresolved question for Part 2"}},
  "style_mirror": "art style for the mirror act scenes",
  "music_prompt": "one sentence describing a wry, warm instrumental music bed that suits this story (no vocals, no drums)",
  "thumbnail_scene": 1-based number of the funniest, most striking frame (it is the thumbnail),
  "shareable_scene": 1-based,
  "scenes": [{{"narration": "...", "delivery": "hushed, ominous", "pace": "slow", "pause_before": 1.2, "pause_after": 0.8, "characters": ["key"], "image_prompt": "...", "image_prompt_b": "optional next frame", "focus": "center", "motion": "zoom_in", "camera": "impact", "popups": [{{"kind": "bubble", "text": "MINE.", "at": 1.5, "x": 0.3, "y": 0.28, "size": 0.2, "tail": "left", "hold": 1.6}}, {{"kind": "sticker", "prompt": "a small hourglass", "at": 3.0, "x": 0.5, "y": 0.35, "size": 0.18}}]}}],
  "youtube": {{"title": "<=90 chars, curiosity-driven", "description": "2-4 sentences: the story teaser, then one sentence that hints at the lesson without spelling it out, then a subscribe line", "tags": ["8-12 tags"], "pinned_comment": "a question that makes viewers apply the lesson to their own life (e.g. 'Would you have given it away? Be honest.')"}},
  "tiktok": {{"caption": "<=140 chars hook", "hashtags": ["5-6 hashtags starting with #"]}}
}}

MIRROR SCENES carry two extra fields, written exactly like this (the literal word, nothing added): "look": "mirror". The first mirror scene and the first animal scene after the mirror act also get "transition": "dissolve". No other scene has "look" or "transition".

FINAL CHECKLIST (count before you answer):
- "witness" is listed in the "characters" array of at least 5 scenes.
- At least 6 scenes have "image_prompt_b"; about 8 scenes have "popups" (at least 5 bubbles, at most 8 stickers). The story, the lesson and the runtime matter more than pop-ups.
- Every key in a scene's "characters" array exists in the top-level "characters" object. Define "human" (and any colleague/boss) there if the mirror act uses them.
- "motion" is only zoom_in, zoom_out, pan_left or pan_right. "camera" is only impact or whoosh. No sound effects anywhere.
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


PART_SUFFIX = re.compile(r"\s*\(Part \d+/\d+\)\s*$")


def existing():
    """Titles used so far and the number of distinct stories per series (all parts of one story count once)."""
    titles, seen = [], {s: set() for s in SERIES}
    for f in sorted(SCRIPTS.glob("*.json")):
        try:
            t = json.loads(f.read_text()).get("title", "")
        except Exception:
            continue
        base = PART_SUFFIX.sub("", t)
        if base not in titles:
            titles.append(base)
        for s in SERIES:
            if t.startswith(s):
                seen[s].add(base)
    return titles, {s: len(v) for s, v in seen.items()}


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


DEFAULT_STYLE_MIRROR = ("Flat clean 2D editorial illustration, expressive plain white round-headed stick figures with thin "
                        "dark outlines, warm dusk light and soft shadows, simple detailed modern interiors, {frame}, "
                        "no text, no watermark.")


def clean_popups(raw):
    """Keep well-formed pop-ups only, with numbers clamped, so one sloppy field never sinks a script."""
    out = []
    for p in raw if isinstance(raw, list) else []:
        if not isinstance(p, dict) or p.get("kind") not in POP_KINDS:
            continue
        try:
            q = {"kind": p["kind"], "at": round(min(max(float(p.get("at", 1.5)), 0.8), 9.0), 2),
                 "x": round(min(max(float(p.get("x", 0.5)), 0.12), 0.88), 2),
                 "y": round(min(max(float(p.get("y", 0.3)), 0.15), 0.6), 2),
                 "size": round(min(max(float(p.get("size", 0.22)), 0.14), 0.34), 2)}
            if p.get("hold") is not None:
                q["hold"] = round(min(max(float(p["hold"]), 1.0), 3.0), 2)
        except (TypeError, ValueError):
            continue
        if p["kind"] == "sticker":
            q["prompt"] = str(p.get("prompt", "")).strip()[:120]
            if not q["prompt"]:
                continue
        else:
            q["text"] = str(p.get("text", "")).strip()[:40]
            if not q["text"]:
                continue
            if p["kind"] == "bubble":
                q["tail"] = "right" if p.get("tail") == "right" else "left"
        out.append(q)
    return out[:3]


def repair(d):
    """Fix the mechanical mistakes a model keeps making, so retries are spent only on real story problems."""
    scenes, chars = d.get("scenes"), d.get("characters")
    if not isinstance(scenes, list) or not isinstance(chars, dict):
        return
    cycle = ["zoom_in", "pan_right", "zoom_out", "pan_left"]
    for i, s in enumerate(scenes):
        if not isinstance(s, dict):
            continue
        for want, alts in (("image_prompt", ("imagePrompt", "image", "prompt", "image_description", "visual", "visuals", "image_prompt_a")),
                           ("image_prompt_b", ("imagePromptB", "image_prompt_2", "next_frame", "image_prompt_next", "second_frame", "image_b"))):
            if not (isinstance(s.get(want), str) and s[want].strip()):
                for a in alts:
                    if isinstance(s.get(a), str) and s[a].strip():
                        s[want] = s[a]
                        break
        if not (isinstance(s.get("image_prompt"), str) and s["image_prompt"].strip()) \
                and isinstance(s.get("narration"), str) and s["narration"].strip():
            # still missing: build a plain frame from the narration so one forgotten field does not sink the script
            s["image_prompt"] = ("A single dramatic frozen moment that shows this story beat, characters mid-action with "
                                 "clear expressions: " + s["narration"].strip())
        m = str(s.get("motion", "")).strip().lower().replace(" ", "_").replace("-", "_")
        s["motion"] = m if m in MOTIONS else cycle[i % 4]
        if isinstance(s.get("narration"), str):            # no sound effects or *stage directions* in his lines
            s["narration"] = re.sub(r"\s*\*[^*]{1,40}\*\s*", " ", s["narration"]).strip()
        legacy = s.pop("sfx", None)                       # sound effects are gone: an old tag only becomes a camera hint
        cam = s.get("camera") or legacy
        if isinstance(cam, list):
            cam = next((x for x in cam if isinstance(x, str)), None)
        cam = cam.strip().lower() if isinstance(cam, str) else None
        cam = {"hit": "impact", "boom": "impact", "splash": "impact"}.get(cam, cam)
        if cam in CAMERA:
            s["camera"] = cam
        else:
            s.pop("camera", None)
        s["popups"] = clean_popups(s.get("popups"))
        if not s["popups"]:
            s.pop("popups")
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
    if not isinstance(d.get("style_mirror"), str) or len(d["style_mirror"].split()) < 8:
        d["style_mirror"] = DEFAULT_STYLE_MIRROR
    scenes = [s for s in scenes if isinstance(s, dict)]

    # the model often forgets the "look" flag even when it wrote the human vignette: detect the stick-figure
    # scenes from their characters, and mark them
    def is_human(k):
        return k in HUMAN_DEFAULTS or "stick figure" in str(chars.get(k, "")).lower()
    mir = [i for i, s in enumerate(scenes) if s.get("look") == "mirror"]
    if not (3 <= len(mir) <= 5 and mir == list(range(mir[0], mir[0] + len(mir)))):
        for s in scenes:
            s.pop("look", None)
        run, best = [], []
        for i, s in enumerate(scenes + [{}]):
            cs = s.get("characters") or []
            if cs and all(is_human(c) for c in cs):
                run.append(i)
            else:
                if len(run) > len(best):
                    best = run
                run = []
        if len(best) >= 3:
            for i in best[:5]:
                scenes[i]["look"] = "mirror"
        mir = [i for i, s in enumerate(scenes) if s.get("look") == "mirror"]
    if 3 <= len(mir) <= 5 and mir == list(range(mir[0], mir[0] + len(mir))):
        scenes[mir[0]]["transition"] = "dissolve"
        if mir[-1] + 1 < len(scenes):
            scenes[mir[-1] + 1]["transition"] = "dissolve"

    # the silent witness: find it under another key, then credit scenes whose image prompt already shows it,
    # then add it to the background of extra animal scenes if it is still short of 6
    if "witness" not in chars:
        alt = next((k for k, v in chars.items() if "witness" in str(v).lower() or "witness" in k.lower()), None)
        if alt:
            chars["witness"] = chars.pop(alt)
            for s in scenes:
                s["characters"] = ["witness" if c == alt else c for c in s.get("characters", [])]
    if "witness" in chars:
        for s in scenes:
            if "witness" not in s["characters"] and "witness" in str(s.get("image_prompt", "")).lower():
                s["characters"].append("witness")
        have = sum("witness" in s["characters"] for s in scenes)
        if have < 5:
            gag = " In the background the Witness watches, blank and unmoved."
            cand = [i for i, s in enumerate(scenes)
                    if s.get("look") != "mirror" and "witness" not in s["characters"]
                    and len(str(s.get("image_prompt", ""))) + len(gag) <= 690]
            need = min(5 - have, len(cand))
            for j in range(need):
                s = scenes[cand[int((j + 0.5) * len(cand) / need)]]
                s["characters"].append("witness")
                s["image_prompt"] = str(s["image_prompt"]).rstrip() + gag


def validate(d, mirror=True):
    repair(d)
    errs = []
    chars, scenes = d.get("characters"), d.get("scenes")
    if not isinstance(chars, dict) or not 2 <= len(chars) <= 9:
        errs.append("characters must be an object with 2 to 9 entries (animals, witness and the mirror-act humans)")
        chars = chars if isinstance(chars, dict) else {}
    if not isinstance(scenes, list) or not 14 <= len(scenes) <= 24 or not all(isinstance(s, dict) for s in scenes):
        n = len(scenes) if isinstance(scenes, list) else 0
        return errs + [f"your reply has {n} scenes in a top-level \"scenes\" array; it must have 14 to 24 (write exactly 18)"]
    if mirror and (not isinstance(d.get("style_mirror"), str) or len(d["style_mirror"].split()) < 8):
        errs.append("style_mirror (the mirror act's art style) is required")
    mir = [i for i, s in enumerate(scenes) if s.get("look") == "mirror"]
    if not mirror:
        if mir:
            errs.append('this part must NOT contain the mirror act: remove "look": "mirror" from every scene')
    elif not 3 <= len(mir) <= 5 or mir != list(range(mir[0], mir[0] + len(mir))):
        errs.append('the mirror act needs 3 to 5 consecutive scenes with "look": "mirror"')
    else:
        if mir[0] < len(scenes) * 0.4 or mir[-1] > len(scenes) - 4:
            errs.append("the mirror act must sit in the middle-to-late story, with at least 3 animal scenes after it")
        elif scenes[mir[0]].get("transition") != "dissolve" or scenes[mir[-1] + 1].get("transition") != "dissolve":
            errs.append('put "transition": "dissolve" on the first mirror scene and on the first scene after it')
    if "witness" not in chars:
        errs.append('characters must include a "witness" (a silent deadpan bystander creature)')
    elif sum("witness" in s.get("characters", []) for s in scenes) < 5:
        errs.append('the "witness" must appear in at least 5 scenes (list it in the scene "characters")')
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
    # pop-ups are never a reason to reject a story: ensure_popups() adds or trims them afterwards
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
Rewrite it to be better while keeping the exact same JSON structure, character keys, and every rule from the original brief (length window of 60 to 90 seconds, 6-12 words of narration per scene, beat-by-beat image prompts, silent witness in 5+ scenes, ending that leaves the viewer pondering).
Checklist:
1. Cut every joke that is merely cute; replace it with something specific, absurd and deadpan.
2. Sharpen the narrator: more gravity, more precise numbers, understatement after big moments.
3. Add or improve one small silent visual gag in each image_prompt.
4. Make sure a planted detail pays off in the final three scenes with an unexplained, quietly impossible twist, and the last line is short, calm and leaves a question hanging. Do not explain it.
5. Keep it all-ages and not childish. No animal is harmed.
6. Protect the story engine: stakes in the first line, a protagonist who wants something, three escalating reversals, one sincere emotional beat with no joke, a haunting last line and an open thread. If any is weak, fix it first; story beats jokes.
7. Protect the lesson (story.lesson): it must be shown through the protagonist's choice and its cost, never preached. If it is vague or preachy, make it concrete and quiet.
8. Keep the MIRROR act (the human stick-figure vignette, scenes with look "mirror", style_mirror, dissolve transitions) intact and make sure it is a real miniature of the same lesson, not a recap.
8. Keep delivery, focus, camera, popups, music_prompt, image_prompt_b and the story/shareable_scene fields. The narrator is a dry, warm middle-aged male storyteller who tells the story from outside it (third person, never mentioning himself, never telling the listener what to do or think): sharpen his lines, vary sentence length, never turn him into a trailer voice, and write no sound effects. Keep pace, pause_before, pause_after, music and freeze fields, and vary pace across the story.
Return ONLY the full improved JSON."""


def punch_up(data, mirror=True, extra=""):
    if os.environ.get("PUNCH_UP", "1") == "0":
        return data
    raw = call_openai([{"role": "system", "content": system_prompt()},
                       {"role": "user", "content": PUNCH_UP_PROMPT + ("\n\n" + extra if extra else "") + "\n\n" + json.dumps(data, ensure_ascii=False)}])
    try:
        better = json.loads(raw)
        errs = validate(better, mirror)
    except json.JSONDecodeError:
        errs = ["not valid JSON"]
    if errs:
        print("  punch-up pass rejected (" + "; ".join(errs[:2]) + "): keeping the first draft")
        return data
    print("  punch-up pass applied")
    return better


def ensure_next_frames(data, target=6):
    """The model rarely gives enough 'next frame' images. Ask for just those, in one small focused call;
    if that fails, derive a plain 'half a second later' frame so the scene still moves."""
    scenes = data["scenes"]
    have = sum(bool(s.get("image_prompt_b")) for s in scenes)
    if have >= target:
        return
    cand = [i for i, s in enumerate(scenes) if not s.get("image_prompt_b")]
    cand.sort(key=lambda i: (scenes[i].get("look") == "mirror", scenes[i].get("camera") not in CAMERA, i))
    pick = sorted(cand[:target - have])
    frames = {}
    try:
        listing = "\n".join(f"{i + 1}: {scenes[i]['image_prompt']}" for i in pick)
        raw = call_openai([
            {"role": "system", "content": "You write next-frame image prompts for an animated comedy. Reply with ONE JSON object only."},
            {"role": "user", "content": "For each numbered image prompt below, write the SAME moment half a second later: same location, same "
             "characters, same framing, only the action advances (wings now open, splash at its peak, expression changed). "
             "State each visible character's exact action. Under 450 characters each, no text in the image.\n"
             'Reply as {"frames": {"<number>": "<next frame prompt>"}}.\n\n' + listing}], 0.7)
        frames = (json.loads(raw).get("frames") or {})
    except (json.JSONDecodeError, AttributeError, SystemExit):
        frames = {}
    for i in pick:
        f = frames.get(str(i + 1))
        if not (isinstance(f, str) and f.strip()):
            f = "The same moment half a second later, the action has advanced one beat: " + scenes[i]["image_prompt"]
        scenes[i]["image_prompt_b"] = f.strip()


def ensure_popups(data, target=8, min_bubbles=5):
    """The model often skips or under-fills pop-ups. Add them with one small focused call; if that fails,
    keep the script as it is (a video without pop-ups still renders)."""
    scenes = data["scenes"]
    have = [i for i, s in enumerate(scenes) if s.get("popups")]
    bubbles = sum(p["kind"] == "bubble" for s in scenes for p in s.get("popups", []))
    stickers = sum(p["kind"] == "sticker" for s in scenes for p in s.get("popups", []))
    if len(have) >= target and bubbles >= min_bubbles and stickers <= MAX_STICKERS:
        return
    need = max(target - len(have), 3)
    free = [i for i, s in enumerate(scenes) if not s.get("popups") and 0 < i < len(scenes) - 1]
    pick = sorted(free[int((j + 0.5) * len(free) / need)] for j in range(min(need, len(free))))
    try:
        listing = "\n".join(
            f"{i + 1} (narration lasts about {len(scenes[i]['narration'].split()) / WORDS_PER_SEC:.1f}s): "
            f"{scenes[i]['narration']} | picture: {scenes[i]['image_prompt'][:160]}" for i in pick)
        raw = call_openai([
            {"role": "system", "content": "You add pop-ups to the scenes of an illustrated animal comedy narrated by a dry, warm male storyteller. Reply with ONE JSON object only."},
            {"role": "user", "content": (
                "For each numbered scene below write 1 or 2 pop-ups that land the joke or the feeling. Kinds: "
                '"bubble" (a short spoken reaction, max 4 words, e.g. "MINE." or "That was SPRING.", with "tail": "left" or "right"), '
                '"label" (a plain card, max 5 words, e.g. "Six hours later"), "sticker" (a small painted prop, "prompt" = ONE object in max 12 words). '
                "Use mostly bubbles (at least 5 bubbles in all), at most 3 stickers in all. Each has: kind, at (seconds after the scene starts, between 0.8 and "
                "the narration length), x and y (centre as fractions of the frame; y between 0.15 and 0.6), size (0.16 to 0.3), text or prompt. "
                'Reply as {"popups": {"<scene number>": [ {...}, {...} ]}}.\n\n' + listing)}], 0.8)
        added = (json.loads(raw).get("popups") or {})
    except (json.JSONDecodeError, AttributeError, SystemExit):
        print("  could not add pop-ups: continuing without them")
        return
    for i in pick:
        items = clean_popups(added.get(str(i + 1)))
        if items:
            scenes[i]["popups"] = items
    left = MAX_STICKERS                                  # never more than MAX_STICKERS in the whole script
    for s in scenes:
        keep = []
        for p in s.get("popups", []):
            if p["kind"] == "sticker":
                if left <= 0:
                    continue
                left -= 1
            keep.append(p)
        if keep:
            s["popups"] = keep
        else:
            s.pop("popups", None)
    n = sum(bool(s.get("popups")) for s in scenes)
    print(f"  pop-ups on {n} scenes")


def plan_story(series, idea, n):
    """One planning call for a multi-part story: title, lesson, locked cast, and what each part does."""
    titles, _ = existing()
    user = (f'Plan ONE story for the series "{series}" (theme: {SERIES[series]}) that will be told across exactly {n} separate videos '
            f'("parts"), each 60 to 90 seconds (about 16 to 18 scenes). Reply with ONE JSON object: '
            '{"title": "the story title, no part number", "lesson": "one plain sentence, the human lesson (5 to 25 words)", '
            '"characters": {"key": "Name: locked visual description (species, colours, size, distinctive feature)"}, '
            '"parts": [{"summary": "2 to 3 sentences: what happens in this part and what changes", '
            '"ending": "how this part ends: a cliffhanger reversal for every part except the last; for the last part, the quiet impossible final image"}]}. '
            f'Rules: exactly {n} parts; 2 to 4 animal characters plus a silent deadpan "witness" creature, and no humans (the human '
            "mirror vignette is written in the final part); one protagonist who wants something badly; three escalating reversals spread "
            "across the parts; the emotional beat sits in the middle of the story; the final part pays off the lesson through consequence, "
            "never preached; every part must be worth watching on its own.\n"
            + (f"Story idea to develop: {idea}\n" if idea else "Invent a fresh, specific premise.\n")
            + ("Lessons already used on the channel (teach a different one):\n- " + "\n- ".join(used_lessons()) + "\n" if used_lessons() else "")
            + ("Do NOT reuse these existing stories:\n- " + "\n- ".join(titles) if titles else ""))
    for attempt in range(3):
        raw = call_openai([{"role": "system", "content": "You plan multi-part animal-comedy stories for the deadpan channel tidalfolio. Reply with JSON only."},
                           {"role": "user", "content": user}], 0.9 if attempt == 0 else 0.5)
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError:
            continue
        ok = (isinstance(plan.get("title"), str) and isinstance(plan.get("characters"), dict) and "witness" in plan["characters"]
              and 3 <= len(plan["characters"]) <= 6 and isinstance(plan.get("parts"), list) and len(plan["parts"]) == n
              and all(isinstance(x, dict) and x.get("summary") and x.get("ending") for x in plan["parts"])
              and 5 <= len(str(plan.get("lesson", "")).split()) <= 25)
        if ok:
            return plan
        print("  story plan rejected: needs title, lesson, a cast with a witness, and exactly %d parts" % n)
    sys.exit("Could not get a valid story plan after 3 attempts.")


def part_brief(part, plan):
    k, n = part
    lines = [f'THIS EPISODE IS PART {k} OF {n} OF ONE STORY, "{plan["title"]}". The whole story is told across {n} separate videos, each '
             "60 to 90 seconds. Every part must be a complete, satisfying watch on its own while moving the story forward.",
             "Story plan for all parts:"]
    for i, pt in enumerate(plan["parts"], 1):
        lines.append(f"  Part {i}: {pt['summary']} (ends on: {pt['ending']})")
    lines.append(f"Write ONLY part {k}. Use exactly these characters (same keys, same descriptions; you may add one-off extras): "
                 + json.dumps(plan["characters"], ensure_ascii=False) + f'. story.lesson is the whole story\'s lesson: "{plan["lesson"]}".')
    if k > 1:
        lines.append("Scene 1 narration is a dry recap-plus-stakes line of at most 14 words that tells a new viewer what is at stake, then the story continues.")
    if k == n:
        lines.append("This is the FINAL part: pay off the whole story and land the lesson through consequence. Include the mirror act and the "
                     "quietly impossible ending exactly as the standard rules say.")
    else:
        lines.append("This is NOT the final part. Rule 9 (the human mirror act) does NOT apply here: write no mirror scenes, give no scene "
                     '"look" or "transition", and set style_mirror to the single sentence "not used in this part". Do not resolve the story. '
                     "THE ENDING rule is replaced: end on a cliffhanger (a reversal that makes the viewer need the next part) with a short, calm last line.")
    return "\n".join(lines)


def part_extra(part):
    k, n = part
    if k == n:
        return f"This is the final part ({k} of {n}) of a multi-part story: keep its recap line, its payoff and the mirror act."
    return (f"This is part {k} of {n} of a multi-part story and NOT the final part: keep it WITHOUT any mirror act and WITHOUT "
            "an explained ending. Its last scene must stay a cliffhanger (ignore items 4 and 8 of the checklist). Keep every character key.")


def performance_notes():
    """What the channel's own viewers did with earlier videos (insights.md, written by tools/make_insights.py).
    Empty until there is enough data, so early runs are unaffected."""
    f = ROOT / "insights.md"
    if not f.exists():
        return ""
    txt = f.read_text()
    if "<!-- ready -->" not in txt:
        return ""
    body = txt.split("<!-- ready -->", 1)[1].strip()[:1800]
    return ("\nREAL RESULTS FROM THIS CHANNEL'S EARLIER VIDEOS (small sample: use as a steer, never copy a plot, title or joke). "
            "Do more of what holds viewers, less of what loses them. Make the first line a stronger hook than the average one below:\n" + body + "\n")


def write_one(series=None, idea=None, part=None, plan=None, ep=None, prior_end=""):
    titles, counts = existing()
    if not series:
        series = min(SERIES, key=lambda s: (counts[s], list(SERIES).index(s)))
    ep = ep or counts[series] + 1
    final = part is None or part[0] == part[1]
    if part and not final:
        structure = ("REQUIRED STRUCTURE: write exactly 17 scenes, ALL of them animal scenes (no human mirror vignette in this part). "
                     "The emotional beat, if this part has one, is around scene 9. ")
    else:
        structure = ("REQUIRED STRUCTURE: write exactly 18 scenes. Scenes 1-11 are the animal story (the emotional beat is around "
                     "scene 8). Scenes 12, 13 and 14 are the human MIRROR vignette: only plain stick-figure humans "
                     "(keys like \"human\", \"colleague\", \"boss\", defined in \"characters\"), no animals, each with \"look\": \"mirror\"; "
                     "scene 12 and scene 15 also carry \"transition\": \"dissolve\". Scenes 15-18 return to the animals for the twist. ")
    user = (f"Write the next episode of the series \"{series}\" (episode #{ep}). "
            f"Series theme: {SERIES[series]}.\n" + structure +
            "Keep the narration brisk: the whole video must run 60 to 90 seconds. "
            "The \"witness\" key must be listed in the \"characters\" array of at least 5 animal scenes.\n"
            + (part_brief(part, plan) + "\n" if part else "")
            + (f"Part {part[0] - 1} ended with: \"{prior_end}\". Continue directly from there.\n" if part and prior_end else "")
            + ("" if part else (f"Episode idea to develop: {idea}\n" if idea else "Invent a fresh, specific premise.\n"))
            + ("" if part else previous_thread(series) + "\n")
            + ("" if part else ("Lessons already used on the channel (teach a different one):\n- " + "\n- ".join(used_lessons()) + "\n" if used_lessons() else ""))
            + ("" if part else ("Do NOT reuse these existing episodes or their premises:\n- " + "\n- ".join(titles) if titles else "")) + performance_notes())
    messages = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": user}]
    data, errs = None, []
    for attempt in range(4):
        raw = call_openai(messages, 1.0 if attempt == 0 else 0.5)   # calmer on retries: fix, don't reinvent
        try:
            data = json.loads(raw)
            errs = validate(data, final)
        except json.JSONDecodeError as e:
            data, errs = None, [f"reply was not valid JSON ({e})"]
        if not errs:
            break
        print(f"  attempt {attempt + 1} rejected: {'; '.join(errs)}")
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "Fix ONLY these problems and return the full JSON with everything else unchanged "
                      "(keep every character key defined in the top-level \"characters\" object):\n- " + "\n- ".join(errs)}]
    else:
        # a story that is only a little off the length window is still a good story: the video renderer stretches
        # the pauses to reach 60 seconds, and a few seconds over the estimate still lands under 90 real seconds
        runtime_only = bool(data) and all("runtime" in e for e in errs)
        est = estimate_runtime(data["scenes"]) if runtime_only else 0
        if runtime_only and MIN_RUNTIME - 6 <= est <= MAX_RUNTIME + 3:
            print(f"  accepting a script that is slightly off the window (~{est:.0f}s estimated, target {MIN_RUNTIME:.0f}-{MAX_RUNTIME:.0f}s)")
        else:
            sys.exit("Could not get a valid script after 4 attempts. Last problems: " + "; ".join(errs))

    data = punch_up(data, final, part_extra(part) if part else "")
    ensure_next_frames(data)
    ensure_popups(data)
    n = next_number()
    if part:
        k, total = part
        title = f"{series} #{ep}: {plan['title']} (Part {k}/{total})"
    else:
        title = data.get("title") or f"{series} #{ep}"
        if not title.startswith(series):
            title = f"{series} #{ep}: {title}"
    slug = f"{n:03}-" + re.sub(r"[^a-z0-9]+", "-", PART_SUFFIX.sub("", title).rsplit(":", 1)[-1].lower()).strip("-")[:40] \
        + (f"-part-{part[0]}" if part else "")
    script = {
        "slug": slug, "title": title, "aspects": ["16:9", "9:16"],
        "seed": random.randint(1, 999999) if not part else int(plan.setdefault("seed", random.randint(1, 999999))),
        "thumbnail_scene": int(data["thumbnail_scene"]),
        "story": data.get("story"), "shareable_scene": int(data.get("shareable_scene", 1)),
        "burn_captions": True,
        "voice": {"openai_voice": "ballad", "voice": "en-GB-RyanNeural", "rate": "-4%", "pitch": "-4Hz"},
        "music_prompt": str(data.get("music_prompt") or "").strip() or None,
        "style": STYLE, "style_mirror": data.get("style_mirror") if final else None,
        "characters": data["characters"], "scenes": data["scenes"],
        "youtube": data["youtube"], "tiktok": data["tiktok"],
    }
    if part:
        script["series_part"] = {"story": plan["title"], "part": part[0], "of": part[1]}
        label_parts(script)
    path = SCRIPTS / f"{slug}.json"
    path.write_text(json.dumps(script, indent=2, ensure_ascii=False))
    with open(ROOT / "queue.txt", "a") as f:
        f.write(path.name + "\n")
    print(f"Wrote {path.name} (~{estimate_runtime(script['scenes']):.0f}s) and queued it.")
    return path.name


def label_parts(script):
    """Mark a part in its titles and text, and on screen: 'Part k' card at the start, 'To be continued' at the end."""
    sp = script["series_part"]
    k, n = sp["part"], sp["of"]
    suffix = f" (Part {k}/{n})"
    yt, tt = script.setdefault("youtube", {}), script.setdefault("tiktok", {})
    base = PART_SUFFIX.sub("", str(yt.get("title", script.get("title", ""))))
    yt["title"] = base[: 90 - len(suffix)].rstrip() + suffix
    extra = []
    if k > 1:
        extra.append(f"This is part {k} of {n}: watch the earlier parts first.")
    if k < n:
        extra.append(f"Part {k + 1} is next.")
    desc = str(yt.get("description", "")).strip()
    if extra and extra[0] not in desc:
        yt["description"] = (desc + " " + " ".join(extra)).strip()
    cap = str(tt.get("caption", "")).strip()
    if not cap.startswith(f"Part {k}/{n}"):
        tt["caption"] = f"Part {k}/{n}: " + cap
    scenes = script["scenes"]
    scenes[0].setdefault("popups", []).insert(0, {"kind": "label", "text": f"Part {k}", "at": 0.8, "x": 0.5, "y": 0.16, "size": 0.26, "hold": 1.6})
    if k < n:
        scenes[-1].setdefault("popups", []).append({"kind": "label", "text": "To be continued", "at": 1.0, "x": 0.5, "y": 0.16, "size": 0.34, "hold": 2.2})


def write_story(series, idea, n):
    """Write a story as n consecutive parts (each 60 to 90 s) and queue them in order."""
    _, counts = existing()
    if not series:
        series = min(SERIES, key=lambda s: (counts[s], list(SERIES).index(s)))
    plan = plan_story(series, idea, n)
    print(f'Story "{plan["title"]}" in {n} parts, series {series}.')
    ep, prior_end, names = counts[series] + 1, "", []
    for k in range(1, n + 1):
        print(f"--- part {k} of {n} ---")
        name = write_one(series, idea, (k, n), plan, ep, prior_end)
        names.append(name)
        prior_end = json.loads((SCRIPTS / name).read_text())["scenes"][-1]["narration"]
    print("Queued in order: " + ", ".join(names))


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
    ap.add_argument("--parts", type=int, choices=range(2, 7), metavar="N",
                    help="tell ONE story across N videos (Part 1, Part 2, ...), each 60 to 90 seconds, queued in order")
    a = ap.parse_args()
    SCRIPTS.mkdir(exist_ok=True)
    if a.parts:
        write_story(a.series, a.idea, a.parts)
        return
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
