# tidalfolio auto-video pipeline

Turns a script file into a finished video: AI images, dramatic narration, Ken Burns motion, sound design, burned-in captions, thumbnail and upload details. Runs free on GitHub Actions.

## One-time setup (about 10 minutes)

1. Create a free GitHub account and a **new private repository** (for example `tidalfolio-auto`).
2. Upload everything in this folder to the repository, keeping the folder structure (including the hidden `.github` folder).
3. Get an API key from **fal.ai** (add a few dollars of credit) and copy it.
4. In the repo: **Settings > Secrets and variables > Actions > New repository secret**. Name: `FAL_KEY`. Value: your key.
5. Open the **Actions** tab and enable workflows if GitHub asks.

### Optional: let ChatGPT (OpenAI) write the scripts and narrate

Add a repository secret named `OPENAI_API_KEY`. Then:
- **Scripts write themselves.** Before each render, if no unrendered script is left in `queue.txt`, `generate_script.py` writes the next episode, rotating through your five series (the least-used one goes next) and avoiding earlier titles. Each script is checked against your rules (1.5 to 2 minute runtime, beat-by-beat image prompts, locked characters, dramatic non-childish tone) and rewritten if it fails. New scripts are saved back to the repo, so you can read or edit them.
- **Better narrator.** With the key present, narration uses OpenAI's text-to-speech (`gpt-4o-mini-tts`, deep "onyx" voice, directed to sound dramatic) and falls back to the free voice if that fails.
- Optional repository variables: `OPENAI_TEXT_MODEL` (default `gpt-4o-mini`; choose a stronger model if the humour is flat) and `OPENAI_TTS_MODEL`.
- **Humour and ending.** Every auto-written script follows comedy rules: deadpan narrator, absurdly specific numbers, a visual gag in every image, a silent "witness" creature in the background of 6+ scenes, and a planted odd detail that comes back in the last three scenes as an unexplained twist. The final line is short, calm and leaves a question hanging (in Bird Banter #1: "Nobody asked how."). After the first draft, a second "punch-up" pass has ChatGPT act as a comedy editor and rewrite the jokes. If that pass fails the checks, the first draft is kept. Set the repository variable `PUNCH_UP` to `0` to skip it. Humour is subjective, so read the first few scripts in `scripts/` and tell me what lands.
- Write scripts on demand: `python generate_script.py --count 5`, or `--series "Underwater Laughs" --idea "a crab who claims every shell"`. Without the key, add scripts by hand as described below.

Cost: a script is a few thousand tokens, and narration is billed per character by OpenAI. For a 1.5 to 2 minute video that is typically a few cents, but check OpenAI's current pricing.

Images are the bigger cost: about 24 scenes in each of two formats is roughly 50 images per video. Check fal.ai's current per-image price for the model you pick (`flux/schnell` is the cheapest). To halve the image cost, set `"aspects": ["16:9"]` in a script (or `STYLE`/`aspects` in `generate_script.py` for auto-written ones) and post the 16:9 video to YouTube only.

### Optional: automatic YouTube upload

Without this, finished videos are only in the downloadable artifact. To have each video uploaded for you:

1. Go to console.cloud.google.com, create a project, and enable **YouTube Data API v3**.
2. **APIs & Services > OAuth consent screen**: choose External, add yourself as a test user, then **Publish app** (set to *In production*). If you leave it in *Testing*, the refresh token expires after 7 days and uploads will start failing.
3. **Credentials > Create credentials > OAuth client ID** (type: Web application). Add `https://developers.google.com/oauthplayground` as an authorized redirect URI. Copy the client ID and client secret.
4. Open developers.google.com/oauthplayground. Click the gear icon, tick *Use your own OAuth credentials*, and paste your client ID and secret. In Step 1 enter the scope `https://www.googleapis.com/auth/youtube.upload`, authorize with the Google account that owns the tidalfolio channel, then in Step 2 click *Exchange authorization code for tokens* and copy the **refresh token**.
5. Add three repository secrets: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
6. Videos upload as **private** by default so you can check them first. To publish automatically, add a repository *variable* (Settings > Secrets and variables > Actions > Variables) named `UPLOAD_PRIVACY` with the value `public` (or `unlisted`).

Notes: YouTube's thumbnail upload needs a verified channel. The upload sets "not made for kids" (the channel targets all ages); change `made_for_kids` in the script's `youtube` block if that is wrong for a video. Check YouTube's current rules on disclosing AI-generated content for your videos.

## Making videos

- **Automatic:** the workflow runs Mon/Wed/Fri at 05:00 UTC (08:00 Uganda). Each run renders the next script listed in `queue.txt` that is not yet in `done.txt`. Change the `cron` line in `.github/workflows/make-video.yml` to change the rhythm.
- **On demand:** Actions tab > *Make tidalfolio video* > **Run workflow**. Type a script file name (for example `001-bird-banter-kingfishers.json`) or leave it blank for the next one in the queue.
- **Download:** open the finished run and download the `tidalfolio-videos` artifact (kept 30 days). Each video comes in two formats: `youtube/video.mp4` (16:9) and `vertical/video.mp4` (9:16 for TikTok and Shorts), each with `thumbnail.png` and `captions.srt`. `metadata.md` has the YouTube title, description, tags, pinned comment, TikTok caption and hashtags.

## Adding new videos

1. Copy `scripts/001-bird-banter-kingfishers.json`, change the story, and save it as `scripts/002-....json`.
2. Add the file name on a new line in `queue.txt`.

Script fields:
- `style`: look added to every image prompt.
- `characters`: locked descriptions. List a scene's characters in `"characters": [...]` and their description is added to that prompt. Keep descriptions identical to help the birds look the same in every scene.
- `seed`: same seed for every scene, which improves consistency.
- Per scene: `narration`, `image_prompt` (say exactly what each character is doing), `motion` (`zoom_in`, `zoom_out`, `pan_left`, `pan_right`), `sfx` (`hit`, `whoosh`, `splash`).
- `aspects`: `["16:9", "9:16"]` renders both formats (images are generated again for each, so image cost doubles). Use `{frame}` in `style` where the frame shape goes.
- Target length is 1.5 to 2 minutes (about 21 to 26 scenes, 6 to 14 words each). The pipeline measures the real narration before paying for images: if a video is a little short it stretches the pauses, if it is more than ~25% short it stops, and if it runs over 2 minutes it warns you.

## Settings you can change

- **Narrator voice:** `voice` block in the script (`voice`, `rate`, `pitch`). Narration uses the free `edge-tts` package (Microsoft voices). It is unofficial, so if it ever breaks, swap `make_narration()` in `pipeline.py` for another TTS service.
- **Image model:** the default is `fal-ai/flux/schnell` (cheapest, fast). For better quality add a repository variable named `FAL_IMAGE_MODEL` (same place as the secrets) set to `fal-ai/flux/dev`. Check fal.ai for current prices.
- **Music and sound effects:** the pipeline synthesizes a low drone and basic effects so it works out of the box. For better sound, add a royalty-free track to `assets/music/` and/or your own `hit.wav`, `whoosh.wav`, `splash.wav` to `assets/sfx/`. Only use audio you have the licence for.

## Test without spending anything

```
pip install -r requirements.txt
python pipeline.py scripts/001-bird-banter-kingfishers.json --dry-run
```
Dry run uses placeholder images and tone "narration" to check timing and assembly.

## Honest limits

- AI images can vary between scenes. Locked character descriptions and a fixed seed help but do not guarantee identical birds. Skim each video before posting, and regenerate a scene by deleting its image from the work folder if you run locally.
- **TikTok is not automated.** TikTok's official posting API limits content from unaudited apps to private viewing, and public posting needs an app audit. Until you get that, upload `vertical/video.mp4` from your phone using the caption and hashtags in `metadata.md` (about a minute per video), or use a scheduling tool that already has TikTok access.
- The YouTube upload code was written against Google's documented upload flow but could not be tested against a real account here. Run the first video as `private` and check it.
