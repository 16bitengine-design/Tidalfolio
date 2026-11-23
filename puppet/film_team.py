"""The film team: the craft brief every tidalfolio story is written, directed and scored under.

Eight specialists share one table. Each has a short list of non-negotiables that is added to the story writer's instructions
(`BRIEF`) and the editor's score sheet (`EDITOR_QUESTIONS`). The same rules are turned into cheap code checks (`direction_problems`)
so a flat, unmotivated or badly directed part is sent back before anything is rendered.

Nothing here changes the channel rules (no names, no moral, no first person, 45 to 60 s a part): it adds emotion and direction on top.
"""
import re

BRIEF = """THE FILM TEAM (eight specialists read every story before it is allowed to exist; all of this is mandatory and sits on top of every rule above)

1. THE STORY WRITER (heart). The story is about ONE WOUND: what the protagonist is afraid of, ashamed of or cannot say. Everything funny sits on top of it. Make us LOVE them in the first two scenes with one small, specific act of decency or one endearing flaw (the baker saves the burnt roll for the cleaner), THEN put them in trouble. Pain lands only on people we like. The emotional beat is built from an OBJECT and a GESTURE, never from a named feeling.
2. THE SCREENWRITER (structure). Each part is a tiny three-act film: SETUP (scene 1 to 2: who, want, wound), CONFRONTATION (middle: the want collides with the wound; each scene makes it worse), TURN (last two scenes: a reveal that changes what we thought). Every scene has ONE job and ONE change of power: somebody gains or loses the upper hand. If a scene could be deleted and nothing changes, replace it. Each line of dialogue carries a want and hides another (subtext): people ask for the salt when they mean "stay".
3. THE DIRECTOR (staging). Decide, for every scene, where the viewer's eye goes FIRST and what it is meant to feel. Use the stage like a camera: push_in on a decision or a lie, pull_back on loss and loneliness, hold on a stare, pan on a pursuit. Block people so their positions tell the power: the one who is winning stands closer to the middle; the one losing drifts to the edge; two people who are about to break apart stand a full spot away. Use SILENCE and STILLNESS as tools: the biggest line of the part is preceded by a beat of nothing ("silence_before") and said by someone who has stopped moving. No scene may be pure talking: each has one thing a person DOES (a hand, an object, a step) that shows what they feel.
4. THE CINEMATOGRAPHER (shot rhythm). Vary the shot size by changing the camera and the number of people: a crowded scene (three people, wide), a two-shot (confrontation), a single (confession). Never three scenes in a row with the same number of people and the same camera. Open the part wide, close in as the emotion rises, and finish on the image that will stay in the viewer's head.
5. THE CASTING DIRECTOR (faces and bodies). Cast against type for surprise: the gruff mechanic is the gentlest person in the story, the cheerful tourist is the one who is lying. Every main character is instantly readable by SILHOUETTE (build, height, hat, colour) and has ONE physical habit (touches a collar, counts coins, never sits). Reactions are casting too: the listener's face must change on the exact word that hurts (use "beats").
6. THE ANIMATION DIRECTOR (performance). Think like a Studio Ghibli animator: the small, true movement beats the big one. Anticipation before a big action (a breath in before the shout, a step back before the lunge), follow-through after (the hand stays out after the throw), and the HOLD: after the emotional line nobody moves for a beat. Use "wipe", "hugself", "clasp", "cower", "hold" and "place" for the quiet moments; use "hop", "flap" and "cheer" only for the true peaks, so they land. Never the same gesture in two scenes in a row.
7. THE SOUND DIRECTOR (voice and silence). The narrator is the only voice and the room's tone: he LEANS IN and slows for the heart (short lines, long pauses), lifts for a win, flattens for a lie. Put a short sentence of at most five words directly AFTER the longest one. Use "silence_before" on the biggest reveal (at most two per part). No sound effects exist, so the silence itself is the sound design: after a shock, leave the line alone and let the picture breathe.
8. THE MUSIC DIRECTOR (the lullaby). The channel theme is the nursery lullaby "Tidal Hush": a music box over a soft rocking 6/8. It must never fight the story. It SWELLS on tender and sad moments and when someone does something kind, it THINS to almost nothing under tension and dread, and it drops OUT completely just before the part's biggest line, then returns warmer. Write each scene's tone so the music can follow: the tone is the score.

THE TABLE READ (before you answer, run it silently; if any answer is no, rewrite that scene first)
- Can I say in one sentence what the protagonist is afraid of? Is it never said aloud?
- By the end of scene 2 would a stranger care what happens to them?
- Does every scene change who has the power?
- Is there one moment, in the second half, where nobody moves and nothing is said, and it is the loudest moment of the part?
- Is there one object that carries the emotion, planted early and returning late?
- Does the part's last image make the viewer want the next part (or, in the last part, sit quietly for a second)?
"""

EDITOR_QUESTIONS = """q17 EMOTIONAL ARC: do we care about the protagonist by scene 2, and does a quiet moment (a gesture or an object, no joke) make a viewer feel something in the chest? Score 1 or 2 if the feeling is announced or absent.
q18 DIRECTION: does every scene have one job, one change of power and one visible action (not people just talking)? Do shot sizes, positions and camera change so the staging tells the story? Score 1 or 2 if scenes are talk, then talk, then talk.
q19 PERFORMANCE AND SILENCE: do the characters react on the exact words, with a held beat after the biggest line, and is the biggest reveal preceded by silence? Score 1 or 2 if everybody simply keeps talking or moves through the story."""

QUIET = ("hold", "clasp", "wipe", "hugself", "cower", "place", "think", "wrap", "offer", "reach")


def direction_problems(part, k):
    """Cheap, deterministic craft checks on one part (a dict with 'scenes'). Returns plain-language problems for the writer."""
    bad = []
    scenes = part.get("scenes") if isinstance(part, dict) else None
    if not isinstance(scenes, list) or len(scenes) < 4 or not all(isinstance(s, dict) for s in scenes):
        return bad
    acts = [[a for a in (s.get("actors") or []) if isinstance(a, dict)] for s in scenes]
    # 1. the shot rhythm: the number of people and the camera must not repeat three scenes running
    sig = [(len(a), s.get("camera", "hold")) for a, s in zip(acts, scenes)]
    for i in range(2, len(sig)):
        if sig[i] == sig[i - 1] == sig[i - 2]:
            bad.append(f"part {k}, scenes {i - 1} to {i + 1}: the same shot ({sig[i][0]} people, camera {sig[i][1]}) three scenes in a row. The cinematographer needs variety: change the camera, or the number of people on screen (one for a confession, two for a confrontation, three for a crowd).")
            break
    # 2. the held beat: somewhere in the second half a quiet action carries the emotion
    half = len(scenes) // 2
    quiet = any(a.get("action") in QUIET for ac in acts[half:] for a in ac)
    if not quiet:
        bad.append(f"part {k}: no quiet moment in the second half. The animation director needs one scene where a person does a small true thing (clasp, wipe, hold, place, hugself, wrap, offer) instead of talking or jumping.")
    # 3. the big gestures must be earned: peak actions only on peak tones
    for i, (s, ac) in enumerate(zip(scenes, acts), 1):
        tone = s.get("tone")
        if tone in ("sad", "tender") and any(a.get("action") in ("hop", "flap", "cheer", "laugh") for a in ac):
            bad.append(f"part {k}, scene {i}: a {tone} scene with a big comic gesture ({', '.join(sorted({a.get('action') for a in ac if a.get('action') in ('hop', 'flap', 'cheer', 'laugh')}))}). Play the heart straight and still: use a small gesture so the feeling lands.")
            break
    # 4. the sound director: a short line after a long one, once per part
    lens = [len(re.findall(r"[A-Za-z0-9']+", str(s.get("narration", "")))) for s in scenes]
    if lens and min(lens) > 8:
        bad.append(f"part {k}: no short line. The sound director needs at least one scene of 8 words or fewer, placed right after a long one, so the storyteller can slow down and let it land.")
    return bad
