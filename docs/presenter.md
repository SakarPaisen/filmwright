# The talking-head presenter

An animated 2D host who stands in a bottom corner of the film, lip-synced to the narration. It is drawn in code
(`src/filmwright/assets/presenter/presenter.html`), so there is no artwork licence to track, and every frame is
rendered deterministically at 30 fps.

Lip-sync comes from [Rhubarb Lip Sync](https://github.com/DanielSWolf/rhubarb-lip-sync) (MIT), which `filmwright setup`
installs. Without it, the mouth follows the narration's loudness instead: not true lip-sync, but it moves with the voice.

## Turning it on

In reel.yaml:

```yaml
talking_head:
  enabled: true
  character: maya          # see the table below
  corner: bottom-right     # or bottom-left
```

In a demo film's video.yaml (docs/film.md has every option):

```yaml
presenter: {style: leo, height: 0.25}
presenter: {style: {preset: leo, shirt: "#7c5cff", shirt2: "#5b3fd9"}, position: bottom-left}
```

## Characters

| Character | Look | Temperament |
|---|---|---|
| `leo` (default) | short dark hair with a side part, blue tee | friendly, steady |
| `leo-light` | `leo` with lighter skin | friendly, steady |
| `leo-stubble` | `leo` with stubble | friendly, steady |
| `sam` | brown hair, green tee, headphones | friendly, steady |
| `ana` | long dark hair, blue tee, earrings | warm, calm |
| `lee` | side part, glasses, purple tee, headphones | thoughtful, precise |
| `maya` | curly hair, coral tee, earrings | upbeat, expressive |
| `raj` | side part, short beard, teal tee | confident, composed |
| `kit` | ginger bun, freckles, mustard tee, headphones | playful, quick |
| `jo` | grey hair, glasses, navy tee | calm mentor |

Any field can be overridden on a character: `skin`, `hair`, `shirt`, `shirt2`, `hairStyle` (short, long, curly, bun,
part, men), `glasses`, `beard`, `freckles`, `earrings`, `headphones`, `energy` (how much it moves), and `badge` (an
image URL or data URI drawn as a small round badge on the chest, for your own logo).

## What it does

- Waves on the first section and gives a thumbs-up on the last.
- In demo films, **aims at the real target**: each zoom's coordinates are mapped into the character's space, so the
  finger, eyes, head turn and lean face the thing the camera is about to show; then it steps aside while the camera
  is zoomed in.
- Presents each new screen with an open palm, beats on stressed words, counts 1 to 5 on its fingers ("three steps"),
  shrugs on a hedge ("not a guarantee"), and rests with hands together during long pauses.
- Picks the bottom corner with less going on, and steps aside for any step whose target sits under it.
- Breathes, blinks (some double), shifts its weight and nods on syllable beats.

## Over any finished film

Explainers and hybrid films don't have recorded clicks to point at, so the host is added over the finished film:

```python
from filmwright.presenter import overlay_on_video
overlay_on_video("film.mp4", "narration.wav", "film-host.mp4", character="kit", corner="bottom-left")
```

```bash
python -m filmwright.presenter overlay film.mp4 --wav narration.wav --text "the narration" --style kit --out film-host.mp4
```

`narration.wav` is the narration on its own, starting at the film's first frame. The film's own audio is kept.
Passing the narration text (`--text`) makes the lip-sync more accurate.

## Previewing a character

```bash
python -m filmwright.presenter preview --style maya --bg frame.png --out preview.mp4      # points at two crosshairs
python -m filmwright.presenter preview --style jo --idle-demo --out idle.mp4               # cycles the idle poses
```
