# Animated explainers

Fully animated films: no screen recording and no slides. Everything on screen is drawn and animated in code:
illustrated characters, hand-drawn whiteboard sketches, flat 2D scenes and motion graphics. Every frame is
rendered on its narration cue by seeking the animation, so the timing is exact and a re-render is identical.

Two formats:

| format | what it is | length | config |
|---|---|---|---|
| `story` | one short character-led film per use case, in one of three story shapes | about 30 to 40 s each | `project.json` + `stories.json` ([story-config.md](story-config.md)) |
| `montage` | many features of one product in a minute, natively laid out for 16:9, 9:16 and 1:1 | about a minute | `montage.json` ([montage.md](montage.md)) |

For animated scenes mixed with real recordings of your product, see [hybrid.md](hybrid.md).

## Quick start

```bash
filmwright new            # pick "explainer" and "story" (or "montage")
filmwright build          # narration, frames, score, mix, captions, 4K + HD
```

Or drive the pipeline directly, step by step:

```bash
python -m filmwright.explainer.story my-films init        # writes project.json + stories.json (fictional example)
python -m filmwright.explainer.story my-films tts all     # narration per story, cached per sentence
python -m filmwright.explainer.story my-films sheet all   # contact-sheet.png: one row per story, a still per beat
python -m filmwright.explainer.story my-films stills 2 4.5,12.0,30.2   # full-size stills to check details
FPS=60 WORKERS=6 python -m filmwright.explainer.story my-films render all
python -m filmwright.explainer.story my-films verify all
```

Each story is written to `NN-<slug>/<prefix>-<slug>-4k.mp4`, `-hd.mp4` and `.srt`. Rendering a 40-second film takes
about two minutes of wall time on a recent laptop with six workers; `FPS=30` halves it for drafts.

`filmwright build` passes the `voice`, `music`, `talking_head`, `captions`, `outputs` and `brand` blocks of
`reel.yaml` to the pipeline with `--settings`, so the same project folder works for both.

## The workflow that gives good films

1. **Understand the product and the audience.** For each film: a person, their job, what they need done, why it
   is slow or risky today, and what the product does about it. Check every claim against the product: never put a
   feature, integration or number in a film unless it is true.
2. **Write the stories** in `stories.json` ([story-config.md](story-config.md)). Rotate the three shapes so a
   batch never feels samey.
3. **Narrate** (`tts`). Each sentence is generated separately and cached. With the neural voices, each sentence is
   read back and regenerated if it comes out garbled; a `WEAK` line names a sentence to listen to.
4. **Review before rendering.** `sheet` writes one row per story with a still per beat. Then check the risky
   details at full size with `stills`: the longest request text, the result lines, the setup chips, the whiteboard
   labels, and the neck across a breath (the head must never separate from the body).
5. **Render**, then **verify**: lengths, resolutions, loudness (-16 LUFS), no encoder tags in the files, and the
   optional film-text check.
6. **Watch** at least one film of each shape end to end with sound.

Caption changes don't need a full re-render: `recaption` re-encodes from the kept frames and mix.

## Options

| setting (project.json or reel.yaml) | effect |
|---|---|
| `voice` | narration voice ([voice.md](voice.md)): preset, described, cloned (with consent) or system |
| `music.mood` | the score ([music.md](music.md)); every scene start is a cut, so sections change with the picture |
| `talking_head.enabled` | draws the lip-synced host over the finished film ([presenter.md](presenter.md)) |
| `captions.burn_in` | small captions burned in at the bottom; the `.srt` is always written |
| `outputs` | `4k`, `hd` for stories; the montage also renders `vertical` and `square` natively |
| `checks.tool_names` | `off`, `warn` or `block` for the film-text check |

## How it is built

- Templates: `src/filmwright/templates/story/story.html`, `templates/montage/montage.html`. They are plain SVG pages.
- Animation: `assets/motion.js`, an MIT-licensed, deterministic, seek-only timeline engine with a familiar
  `gsap`-style API (`timeline().to/from/fromTo/set`, eases, repeat/yoyo, stagger, keyframes, `svgOrigin`). It
  replaced a third-party library whose licence does not allow redistribution; frame-by-frame comparisons
  against the original renders differ in under 0.25% of pixels (anti-aliasing), with one intended exception: a
  single-number `strokeDasharray` replaces the whole dash array instead of keeping extra values from an existing
  attribute.
- Sketches: rough.js (MIT), vendored in `assets/vendor/`. Fonts: IBM Plex Sans, Space Grotesk and Caveat (SIL OFL),
  bundled, so renders never load anything from the network.
- Rendering: `filmwright.explainer.render` opens the page in headless Chromium, seeks each frame and pipes the
  screenshots to ffmpeg in parallel chunks; the same module mixes narration, score and effects and burns captions.

The quality rules (pivots, breathing, timing, captions, variety) are in [style-guide.md](style-guide.md).
