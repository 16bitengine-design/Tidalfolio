# tidalfolio signature theme

The current theme is original: composed and synthesized by `tools/make_theme.py` (no samples, no third-party audio),
so there is no license to track. Re-render with `python tools/make_theme.py` (`--seed N` for another take). Replace the
three files with a Suno-made version later if you like; the pipeline just uses whatever is in `theme/`.

Every video uses the SAME theme: the "Tidal Fable" theme. No other music, no sound effects.

Put three files in `assets/music/theme/` (mp3, wav, m4a or ogg):

| file       | length        | what it is                                                        |
|------------|---------------|-------------------------------------------------------------------|
| `intro.*`  | 4-6 s         | the piano motif with a pad swell, plays once at the start         |
| `loop.*`   | 90 s or more  | seamless loop that runs under the whole video                     |
| `outro.*`  | 4-6 s         | the motif resolving on a warm major chord, ends with the video    |

Only `loop` is required. With no theme folder, the pipeline falls back to any single track in this
folder, then to a quiet synthesized pad.

## Music volume (never constant)

The music level changes through each video in two ways:

1. **Emotion.** Each scene's `delivery` words set a level (see `EMOTION_LEVELS` in `pipeline.py`):
   - swells (0.75-0.90): sincere, tender, earnest, triumphant, intense
   - mid (0.45): hushed, ominous, conspiratorial
   - dips (0.28): dry, deadpan, blunt, calm, so a joke can land
   - the story's `emotional_beat_scene` is lifted to at least 0.85, and the last scene to at least 0.7
   - levels glide from scene to scene over 0.7 s
2. **Narration.** Whenever the narrator speaks, the music is ducked further, then rises again in the pauses.

Override any scene in its script entry:

```json
"music": {"emotion": "tender"}      // or {"level": 0.8}
```

## Generation prompt for the theme

> Instrumental ethereal Celtic ambient theme, about 70 BPM, minor key resolving to major. A simple memorable
> four-note piano motif that repeats, soft wordless choir pads, gentle harp arpeggios like rolling tides, a low
> warm string drone. No drums, no vocals with words, no sound effects. Emotional, timeless, fable-like, slightly
> bittersweet, slow build, seamless loop.

Use a generator whose terms allow commercial use on a monetized channel, keep a copy of those terms next to the
files, and test-upload privately once to confirm no Content ID claim.

## Two theme options

- `theme/` : "Tidal Fable", piano motif in A minor (default).
- `theme_pentatonic/` : same calm mood, but the motif is pentatonic (D E F# A B) on a guzheng-like string.

Switch without moving files by setting the environment variable `MUSIC_THEME=theme_pentatonic` (in the GitHub
workflow, under `env:`). Regenerate either with `python tools/make_theme.py --style ethereal|pentatonic`.

- `theme_fusion/` : the ethereal chords, choir pad and harp arpeggios of the first theme, with the pentatonic
  motif of the second played by a guzheng-style string doubled by soft piano (A minor pentatonic: A C D E G).
  `MUSIC_THEME=theme_fusion` to use it; `python tools/make_theme.py --style fusion` to regenerate.
