# tidalfolio signature theme: "Tidal Fable" (fusion)

Every video uses this same theme. No other music, no sound effects. It is original: composed and synthesized by
`tools/make_theme.py` (no samples, no third-party audio), so there is no license to track.

- Ethereal chords (Am F C G), wordless choir pad, harp arpeggios and a low drone, 70 BPM, no drums.
- Signature tune: A minor pentatonic (A C D E G) on a guzheng-style string doubled by soft piano, with an answering phrase.
- Outro resolves to A major (bittersweet to hopeful).

Files in `assets/music/theme/`: `intro.mp3` (about 7 s, plays once at the start), `loop.mp3` (about 110 s, runs under the
whole video; a shorter track is looped with a crossfade), `outro.mp3` (about 10 s, ends with the video). Only `loop` is required.

## Music volume (never constant)

1. **Emotion.** Each scene's `delivery` words set a level (see `EMOTION_LEVELS` in `pipeline.py`):
   - swells (0.75-0.90): sincere, tender, earnest, triumphant, intense
   - mid (0.45): hushed, ominous, conspiratorial
   - dips (0.28): dry, deadpan, blunt, calm, so a joke can land
   - the story's `emotional_beat_scene` is lifted to at least 0.85, and the last scene to at least 0.7
   - levels glide from scene to scene over 0.7 s
2. **Narration.** Whenever the narrator speaks, the music is ducked further, then rises again in the pauses.

Override any scene in its script entry: `"music": {"emotion": "tender"}` or `{"level": 0.8}`.

## Changing the theme

- Regenerate: `python tools/make_theme.py` (`--seed N` for another take, `--loop-bars N` for a different length).
- Earlier alternatives can be rendered on demand: `--style ethereal` (piano, A minor) or `--style pentatonic`
  (guzheng, D pentatonic). They are written to `assets/music/theme_ethereal/` and `theme_pentatonic/`; set
  `MUSIC_THEME=<folder name>` to use one without moving files.
- To use a Suno-made or library track instead, replace the files in `theme/`. Only use tracks you have commercial
  rights to, keep a copy of the license, and test-upload privately once to check for Content ID claims.
