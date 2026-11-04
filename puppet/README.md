# Puppet engine: code-drawn storybook videos (free)

A second way to make a tidalfolio video. Instead of generating images, everything is **drawn by code**: inked eagles,
squirrels, fish and rabbits with feathers and blinking eyes, painted parallax hills and cliffs, paper grain, parchment
pop-ups, word-by-word captions, a synthesized music bed, and a **free offline storyteller voice** (Kokoro).
Cost per video: **nothing**. No fal.ai, no OpenAI.

It lives next to the image pipeline and does not touch it. The image pipeline (`pipeline.py`) is unchanged.

## Make a video

- **On GitHub:** Actions tab > *Make puppet video (code-drawn, free)* > **Run workflow**. Type a script file name from
  `scripts/` (for example `005-the-eagle-who-waited-ink-part-1.json`) or leave it blank to render the next one in
  `queue-puppet.txt`. Tick *upload* to send it to YouTube (same `YT_*` secrets and `UPLOAD_PRIVACY` as the main workflow).
  Download the `tidalfolio-puppet-videos` artifact. About 5 to 10 minutes per video; the first run also downloads the voice model (cached afterwards).
- **On a computer:** `pip install -r puppet/requirements.txt`, install ffmpeg, then
  `python puppet_render.py scripts/005-the-eagle-who-waited-ink-part-1.json`. Add `--dry-run` for a quick silent check of the scenes.

Output matches the image pipeline, so `upload_youtube.py` and `post_tiktok.py` work unchanged:
`output/<slug>/vertical/video.mp4` (9:16, also copied to `youtube/video.mp4`, which YouTube treats as a Short), `thumbnail.png`,
`captions.srt`, `metadata.md`. Every video must run **50 to 90 seconds** or nothing is rendered. Every story is told in **2 to 4 parts**; each part ends with a closing card ("Continue to Part N" except on the last part, then "The end") and the line **Follow · Like · Subscribe · Share**.

## Script format

A puppet script is JSON with `"engine": "puppet"`, plus the usual `slug`, `title`, `youtube`, `tiktok`, `series_part`,
`thumbnail_scene`, and `voice` (`{"kokoro": "bm_george"}`; try `bm_fable`, `bm_daniel`, `am_michael`). Each scene:

```
{ "narration": "Full sentences. Short ones are spoken slowly and dramatically.",
  "world": "dawn",                       dawn | day | dusk | storm | night | sunset  (or your own under "worlds")
  "camera": {"x": 470, "y": 1010, "z": {"kf": [[0, 1.0], [7, 1.1]]}},
  "things": [ ...drawn in order... ],
  "popups": [ {"text": "Z", "at": 0.6, "x": 470, "y": 700, "dur": 2.0, "size": 58} ],
  "music":  {"pad": 0.5, "pluck": {"step": 1.6, "notes": [0,3,2,4], "vol": 0.5}, "silence_before": "No mother"},
  "freeze": "@No mother-0.5",             optional: everything stops here (the camera keeps moving)
  "end_card": true }                     last scene of the video: the tidalfolio title card
```

**Things:** `eagle` (`who`: orrin, dad, mom), `squirrel` (`item`: popcorn, `hat`: bowler), `fish`, `rabbit`, `nest`, `tree`, `pole`, `net`,
`sign`, `poly`, `line`. Eagles take `x`, `y`, `scale`, `face` (1 right, -1 left), `eye` (open, half, closed, wide), `beak`, `brow`,
`look`, `flap` (`{"rate", "amp", "rest"}`), `legs`, `tear`, `head_dx`/`head_dy`, `tailsway`, `droop`. A thing can `"show": [from, to]`,
and can follow another with `"attach": {"to": "<id>", "dx": -112, "dy": -70}`. World coordinates: the cliff top is at y = 1240.

**Anything that changes over time** is a channel: a plain number, `{"kf": [[t, v], ...]}` (smooth), `{"lin": ...}` (straight),
`{"step": [[t, v], ...]}` (jumps, for eyes and poses), and `{"base": b, "sin": {"amp", "rate", "from", "to"}}` (wobble).

**Times follow the narrator.** Any time can be seconds into the scene, or `"@some words"` = the moment the voice says those words
(`"@He flew+1.5"`, `"@Mom, Dad-0.3"`, `"@end"`). So a net can snap shut exactly on "caught her", and nothing drifts when the voice speed changes.

Look at `scripts/005-the-eagle-who-waited-ink-part-1.json` and `-part-2.json` for a worked example (the style can also be asked of Claude:
*"write the next story as a puppet script"*).

## Files

- `puppet_render.py`: command line. `puppet/render.py`: narration, timing, frames, mixing. `puppet/dsl.py`: reads scenes.
- `puppet/engine.py`: the drawing (characters, painted worlds, paper grain, pop-ups, captions). `puppet/worlds.py`: world presets.
- `puppet/tts.py`: the voice. `puppet/music.py`: the music synth (copyright-safe, made from scratch each run).
- `puppet/fonts/Lora-Variable.ttf`: Lora, SIL Open Font License.

## Limits

- Motion is storybook "puppet" animation (bobbing, wing flaps, camera moves, pop-ups), not fluid cartoon animation.
- Stories are limited to what the engine can draw: eagles, squirrels and a rabbit on a clifftop/tree stage (see `puppet/storyboard.py`). `generate_script.py` still writes scripts for the image pipeline only.
- The voice is clear and warm but not a paid voice. Change `voice.kokoro` to compare. Kokoro is Apache-2.0; check its current licence before relying on it commercially.
- Only the fusion-style music theme exists here so far (no nursery theme).
- Linux or macOS with ffmpeg (the frame workers use `fork`).

## Looks
Set `"look": "toon"` in a script for the bold comic-cartoon style (thick outlines, saturated colours, big eyes, castle/sun-ray/moon-crater worlds `toon_day|dawn|dusk|storm|night|sunset`, outlined dust puffs `puff`, `sparkle`, `speed` things, popup `shape`: `bubble|burst|card`). Default is `"ink"` (storybook). Quick preview without rendering video: `python puppet_render.py <script> --stills /tmp/preview`.

## Automatic stories
`python puppet_story.py --ensure 1` (add `--parts 3` to choose) asks an AI model (OpenAI, `OPENAI_API_KEY`; text only, a few cents a story; set the repository
variable `OPENAI_TEXT_MODEL` to a stronger model for better stories) for a *storyboard*: narration plus who stands where, their mood, what they do and
when (tied to words in the narration). `puppet/storyboard.py` checks it against the channel rules (narrator never says "I", exactly one uncommon word,
valid cast and cues, popups of 4 words or fewer), compiles it to a script, draws a test frame of every scene and measures the narration with the real voice
(50 to 90 s for every part). Any problem goes back to the model (up to 4 tries). A story is 2 to 4 parts (the writer picks); all parts are saved to `scripts/` and queued in order, so Part 2 follows Part 1 on the next daily run. Every part but the last ends on a cliffhanger.
The daily workflow runs this step when the queue is empty (one story = 2 to 4 days of videos), so no one has to write anything. `python puppet_story.py --storyboard file.json` checks and queues a storyboard you wrote yourself (no AI, no key).
