# Feature montage

Many features of one product in about a minute: an intro (a busy team, then the headline and logo), one scene per
feature (an animated world on the left, the title and three points on the right), and a close where every feature
flies into the logo, followed by the lockup and a call to action. It is laid out natively for 16:9, 9:16 and 1:1:
the vertical and square films are re-rendered with their own layouts, not cropped, and share the 16:9 soundtrack,
so the timing is identical.

```bash
python -m filmwright.explainer.montage my-montage init     # montage.json (fictional example)
python -m filmwright.explainer.montage my-montage tts
python -m filmwright.explainer.montage my-montage stills                 # one still per scene
python -m filmwright.explainer.montage my-montage stills --aspect 9x16   # check the vertical layout too
FPS=60 WORKERS=6 python -m filmwright.explainer.montage my-montage render
python -m filmwright.explainer.montage my-montage verify
```

Outputs: `<prefix>-4k.mp4`, `-hd.mp4`, `-vertical.mp4` (1080x1920), `-square.mp4` (1080x1080) as listed in
`outputs`, plus `<prefix>.srt`.

## montage.json

| field | meaning |
|---|---|
| `product`, `wordmark`, `tagline`, `url`, `file_prefix`, `brand` | as in [story-config.md](story-config.md) |
| `headline` | the intro's on-screen headline |
| `intro`, `close` | narration for the first and last scenes |
| `features` | a list (4 to 8 works best) of `{key, label, title, art, points, line}` |
| `cta` | the call-to-action pill on the close (optional) |
| `footnote` | small print shown during the feature scenes, e.g. "Illustrative example with fictional data" |
| `voice`, `music`, `talking_head`, `captions`, `outputs`, `checks`, `tempo` | see [explainer.md](explainer.md#options) |

A feature: `label` is the small header ("Scheduling"), `title` the big line, `points` up to three short lines that
fly in on the beat, `line` its narration (one sentence), and `art` the animated world:

| art | what moves |
|---|---|
| `calendar` | a week fills with shift blocks; a highlight sweeps across the days |
| `chat` | a phone conversation: bubbles pop in turn, typing dots |
| `chart` | metric tiles count up, bars grow, a trend line draws |
| `checklist` | five items tick off in rhythm |
| `bell` | a ringing bell; notification cards slide in |
| `people` | five team members pop in and get connected |
| `flow` | a small workflow: nodes appear, links draw, items travel along them |
| `lock` | a shield appears, the padlock snaps shut, a ring of dots pulses |

Without `art`, features cycle through the list in order. Feature colours cycle through the brand accent, alt and
warm colours and a few neutrals; set `color` on a feature to choose.
