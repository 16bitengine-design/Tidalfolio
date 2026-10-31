# tidalfolio auto-video pipeline

Turns a script file into a finished video: hand-painted storybook illustrations with pop-ups (speech bubbles, labels and painted props that bounce in), a deep older-woman narrator, several camera moves and cuts per scene, a music bed (music only, no sound effects), highlighted-word captions, a thumbnail and upload details. It makes a 16:9 version for YouTube and a 9:16 version for TikTok and Shorts. It runs free on GitHub Actions.

## One-time setup (about 10 minutes)

1. Create a free GitHub account and a **new private repository** (for example `tidalfolio-auto`).
2. Upload everything in this folder. **GitHub's web uploader often skips the hidden `.github` folder and sometimes the `scripts` folder.** After uploading, check the repository's front page for: `pipeline.py`, `generate_script.py`, `upload_youtube.py`, `queue.txt`, `done.txt`, `requirements.txt`, `README.md` and the folders `scripts` and `.github`. If a folder is missing, click **Add file > Create new file**, type its path as the name (for example `.github/workflows/make-video.yml` or `scripts/001-bird-banter-kingfishers.json`; the slashes create the folders), paste the file's contents, and click **Commit changes**.
3. Get an API key from **fal.ai** (add a few dollars of credit) and copy it.
4. In the repo: **Settings > Secrets and variables > Actions > New repository secret**. Name: `FAL_KEY`. Value: your key.
5. Open the **Actions** tab and enable workflows if GitHub asks.
6. **Settings > Actions > General > Workflow permissions**: choose **Read and write permissions** and save (the workflow saves the queue back to the repo).

### Optional: let ChatGPT (OpenAI) write the scripts and narrate

Add a repository secret named `OPENAI_API_KEY`. Then:
- **Scripts write themselves.** Before each render, if no unrendered script is left in `queue.txt`, `generate_script.py` writes the next episode, rotating through your five series (the least-used one goes next) and avoiding earlier titles. It continues from the previous episode's open thread, so episodes feel like a series. New scripts are saved back to the repo, so you can read or edit them.
- **Story rules.** Every script must teach one human lesson (courage, generosity, pride, patience, honesty and so on), shown through what the animals do and what it costs them, never preached. Scripts that say "the moral is" are rejected, and a lesson already used on the channel is not reused. The lesson is saved in the script's `story.lesson`, hinted at in the YouTube description, and turned into a pinned-comment question. Every script also has a **mirror act**: about two thirds in, it cuts for 3 to 5 scenes to a plain stick-figure human living the same lesson in an ordinary place (office, shop, kitchen), in a flat illustration style set by `style_mirror`, with a soft white dissolve in and out, then returns to the animals for the ending twist. Every script must also have: a stakes-first first line, one named protagonist who wants something and can lose it, three escalating reversals, one sincere emotional beat with no joke, a haunting last line, and an open thread that needs a Part 2. It also needs a shareable moment, a silent "witness" creature in the background of 6+ scenes, and a planted detail that returns in the last three scenes as an unexplained twist. Scripts that break a rule are rejected and rewritten (up to four attempts).
- **Punch-up pass.** After the first draft a second pass has ChatGPT act as an editor and strengthen the story and jokes. If that pass breaks a rule, the first draft is kept. Set the repository variable `PUNCH_UP` to `0` to skip it.
- **The narrator is a deep-voiced woman in her sixties.** With the key present, narration uses OpenAI's text-to-speech (`gpt-4o-mini-tts`, voice `sage`) with instructions to sound like a grandmother telling a story she finds funny: low, slightly raspy, warm, dry and unhurried. The pitch is then lowered 6% without changing the speed (`voice.deepen` in the script, 0.90 to 1.0; lower is deeper). Each scene carries a `delivery` note ("dry, deadpan", "hushed, conspiratorial", "quietly sincere") that is passed to the voice as acting direction. If OpenAI's voice fails, a free British woman's voice (`en-GB-SoniaNeural`) is used instead. To pick the best voice, render a short test with `voice.openai_voice` set to `sage`, `coral`, `fable` and `shimmer`, and keep the one that sounds oldest and deepest.
- Optional repository variables: `OPENAI_TEXT_MODEL` (default `gpt-4o-mini`; choose a stronger model if the stories feel weak) and `OPENAI_TTS_MODEL`.
- Write scripts on demand: `python generate_script.py --count 5`, or `--series "Underwater Laughs" --idea "a crab who claims every shell"`. Without the key, add scripts by hand as described below.

### Optional: automatic YouTube upload

Without this, finished videos are only in the downloadable artifact. To have each video uploaded for you:

1. Go to console.cloud.google.com, create a project, and enable **YouTube Data API v3**.
2. **APIs & Services > OAuth consent screen**: choose External, add yourself as a test user, then **Publish app** (set to *In production*). If you leave it in *Testing*, the refresh token expires after 7 days and uploads will start failing.
3. **Credentials > Create credentials > OAuth client ID** (type: Web application). Add `https://developers.google.com/oauthplayground` as an authorized redirect URI. Copy the client ID and client secret.
4. Open developers.google.com/oauthplayground. Click the gear icon, tick *Use your own OAuth credentials*, and paste your client ID and secret. In Step 1 enter the scope `https://www.googleapis.com/auth/youtube.upload`, authorize with the Google account that owns the tidalfolio channel, then in Step 2 click *Exchange authorization code for tokens* and copy the **refresh token**.
5. Add three repository secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
6. Videos upload as **private** by default so you can check them first. To publish automatically, add a repository *variable* (Settings > Secrets and variables > Actions > Variables) named `UPLOAD_PRIVACY` with the value `public` (or `unlisted`).

Notes: YouTube's thumbnail upload needs a verified channel. The upload sets "not made for kids" (the channel targets all ages); change `made_for_kids` in the script's `youtube` block if that is wrong for a video. A failed YouTube upload does not lose the video: it is still saved in the downloadable artifact. Check YouTube's current rules on disclosing AI-generated content.

## Making videos

- **Automatic:** the workflow runs Mon/Wed/Fri at 05:00 UTC (08:00 Uganda). Each run renders the next script listed in `queue.txt` that is not yet in `done.txt`. Change the `cron` line in `.github/workflows/make-video.yml` to change the rhythm.
- **On demand:** Actions tab > *Make tidalfolio video* > **Run workflow**. Type a script file name (for example `001-bird-banter-kingfishers.json`) or leave it blank for the next one in the queue.
- **Download:** open the finished run and download the `tidalfolio-videos` artifact (kept 30 days). Each video comes in two formats: `youtube/video.mp4` (16:9) and `vertical/video.mp4` (9:16 for TikTok and Shorts), each with `thumbnail.png` and `captions.srt`. `metadata.md` has the YouTube title, description, tags, pinned comment, TikTok caption and hashtags.
- **Run time:** roughly 15 to 30 minutes per video on GitHub's free runners (image generation plus rendering both formats). The workflow stops after 60 minutes.

## Adding videos by hand

1. Copy `scripts/001-bird-banter-kingfishers.json`, change the story, and save it as `scripts/002-....json`.
2. Add the file name on a new line in `queue.txt`.

Script fields:
- `style`: look added to every image prompt. Use `{frame}` where the frame shape goes.
- `characters`: locked descriptions. List a scene's characters in `"characters": [...]` and their description is added to that prompt. Keep descriptions identical to help the animals look the same in every scene. `seed` is shared by every scene for the same reason.
- Per scene:
  - `narration`: the spoken line. Short lines (6 to 14 words) are punchier.
  - `delivery`: acting direction for the narrator voice.
  - `image_prompt`: say exactly what each character is doing, beat by beat.
  - `image_prompt_b` (optional, `characters_b` if the cast differs): the same moment half a second later. The video cuts between the two images so the scene moves. Use it on action scenes.
  - `focus`: `left`, `center` or `right`, where the camera should aim.
  - `motion`: `zoom_in`, `zoom_out`, `pan_left`, `pan_right`.
  - `look`: set to `mirror` on mirror-act scenes so they use `style_mirror` instead of `style`.
  - `transition`: set to `dissolve` on the first scene of an act change for a soft white dissolve.
  - `camera`: `impact` (a silent hard camera slam with shake and a white flash) or `whoosh` (the camera whips across for an entrance). Old scripts' `sfx` tags are still read as camera hints; **no sound effect is ever played.**
  - `popups`: a list of things that bounce in over the picture on the beat of the joke (details below).
- `music_prompt` (optional): one sentence describing the music bed if it is generated.
- `aspects`: `["16:9", "9:16"]` renders both formats (images are generated again for each, so image cost doubles). Use `["16:9"]` to render YouTube only.
- `story` (including `lesson`), `shareable_scene`: notes used by the script writer; they do not change the video.
- **Length: every video runs between 60 and 90 seconds** (aim for about 75 to 85). That is roughly 18 scenes with 6 to 12 words of narration each. The pipeline measures the real narration before paying for images: if a video is a little under 60 seconds it stretches the pauses, if it is far too short it stops, and if it runs over 90 seconds it prints a warning. The script writer checks the same window and writes 16 to 20 scenes, with the human mirror act cut down to 3 scenes.

## Pop-ups

Each scene can carry up to three pop-ups. They pop in with a bounce, breathe while they are on screen, and shrink away. Three kinds:

```
{"kind": "bubble",  "text": "MINE.", "at": 1.5, "x": 0.3, "y": 0.28, "size": 0.2, "tail": "left"}
{"kind": "label",   "text": "Six hours later", "at": 1.0, "x": 0.5, "y": 0.16, "size": 0.34}
{"kind": "sticker", "prompt": "a small hourglass", "at": 3.0, "x": 0.5, "y": 0.35, "size": 0.18}
```

`at` is seconds after the scene starts. `x` and `y` are the centre as fractions of the frame (keep `y` between 0.15 and 0.6 so captions stay clear). `size` is the width as a fraction of the frame. Optional `hold` is seconds on screen. A bubble is a speech bubble with a tail, a label is a plain card (time jumps, titles), and a sticker is a small painted prop generated by fal.ai on a white background, then cut out. Stickers cost one extra image each, so a script uses at most 8. New scripts get their pop-ups from the script writer; hand-written scripts can add them to any scene.

## What makes the videos move

Stills cannot truly animate, so each scene is cut into shots about every 2.5 seconds: a wide opening move, a punch-in, a drift, and (on action scenes) a cut to the second frame. Impacts slam in with a silent camera shake and a white flash, entrances whip across the frame, and pop-ups bounce in on the jokes. The narrator is compressed and normalized to broadcast loudness, and the music bed ducks under every spoken line. There are no sound effects.

## Settings you can change

- **Narrator voice:** `voice` block in the script (`openai_voice`, plus `voice`, `rate`, `pitch` for the free fallback voice). The free voice uses the unofficial `edge-tts` package, so if it ever breaks, swap `make_narration()` in `pipeline.py` for another TTS service.
- **Look:** the `style` field of each script sets the illustration style for every image (new scripts get a hand-painted storybook watercolor-and-ink look; the mirror act keeps its flat stick-figure style). The same style is added to every prompt, which keeps scenes looking alike.
- **Image model:** the default is `fal-ai/flux/schnell` (cheapest, fast). For better quality add a repository variable named `FAL_IMAGE_MODEL` set to `fal-ai/flux/dev`. Check fal.ai for current prices.
- **Music (the only sound besides her voice):** the pipeline uses, in order, (1) a track from `assets/music/` (mp3, wav, m4a or ogg; with several tracks one is picked per video, and short tracks are looped with a crossfade), (2) a track generated once per video with fal.ai (`fal-ai/stable-audio`, needs `FAL_KEY`; set the repository variable `MUSIC_GENERATE` to `0` to turn this off), (3) a very quiet placeholder pad, so a video still renders. **For good music, add licensed or royalty-free tracks to `assets/music/`.** Only use audio you have the licence for, and check the licence terms of any generated music before monetizing. Gentle, dry, acoustic tracks suit the grandmother's voice best.
- **Captions:** big highlighted-word captions are burned in (`"burn_captions": false` turns them off). `captions.srt` is always written, for YouTube's own caption track.

## Cost

Images are the biggest cost: about 18 scenes plus up to 8 second frames, in two formats, is roughly 50 images per video, plus up to 8 pop-up stickers (generated once per video and shared by both formats). Check fal.ai's current per-image price for the model you pick (`flux/schnell` is cheapest). To halve the image cost, set `"aspects": ["16:9"]`. OpenAI usage (script writing and narration) is typically a few cents per video, but check OpenAI's current pricing.

## Test without spending anything

```
pip install -r requirements.txt
python pipeline.py scripts/001-bird-banter-kingfishers.json --dry-run
```
Dry run uses placeholder images and tone "narration" to check timing and assembly. Needs ffmpeg and the DejaVu Sans font.

## Honest limits

- AI images can vary between scenes. Locked character descriptions and a fixed seed help but do not guarantee identical animals. Skim each video before posting.
- Stills with camera moves and pop-ups are not real animation. The animals inside each painting stay still; the movement comes from the camera, the cuts between two frames, and the pop-ups.
- The older-woman voice depends on OpenAI's voices and the acting instructions. It will sound like a warm, low-voiced woman, but it may not sound exactly sixty. Compare voices and the `deepen` setting on a short test.
- The story quality depends on the text model. The default is the cheapest; set `OPENAI_TEXT_MODEL` to a stronger one if episodes feel flat.
- **TikTok is not automated.** TikTok's official posting API limits content from unaudited apps to private viewing, and public posting needs an app audit. Until you get that, upload `vertical/video.mp4` from your phone using the caption and hashtags in `metadata.md` (about a minute per video), or use a scheduling tool that already has TikTok access.
- The YouTube upload code was written against Google's documented upload flow but could not be tested against a real account here. Run the first video as `private` and check it.
