# Style guide for animated films

The look is flat and friendly, with one bold idea per scene. A story mixes four styles, each used for what it
does best.

| style | use it for | in the story template |
|---|---|---|
| Character animation | the person, their day, their relief | the office scene, the happy avatar with confetti |
| Whiteboard | the pain, rules of thumb, "the old way" | marker sketches drawn stroke by stroke, handwriting revealed left to right |
| Flat 2D | the product's world: inputs, sorted items | the setup scene |
| Motion graphics | the result, numbers, the product window | the app scene, links, the logo lockup |

## Palette and type

- The product's world uses the brand background with a radial glow in the accent colour; the person's world uses
  light pastel walls (one tint per story or group of stories); the whiteboard is off-white with a grid.
- From the brand: `accent` (highlights, the logo tile), `alt` (done, correct, positive), `warm` (secondary
  highlight), `ink` (text on dark). Red is reserved for "wrong" and "overdue".
- Space Grotesk for display and wordmarks, IBM Plex Sans for UI text, Caveat for handwriting. All bundled.

## Motion

- Ease out on entrances (`power3.out`, `back.out(2-3)` for pops), ease in on exits. Nothing linear except
  continuous motion (particles, orbits, conveyor-like movement).
- Hold every important frame for at least 0.8 seconds. Let the narration finish before a scene leaves.
- One flourish per moment: drifting particles, a glint along a link, a shimmer across the result, a light sweep
  over the wordmark, confetti on the payoff, a slow camera push on the whiteboard.

## Characters

The story template's office scene rigs a seated person: body, neck, head, hair, face, arms, desk props.

- **Pivots in screen coordinates.** Use `svgOrigin: "x y"`. `transformOrigin: "Npx Npx"` is measured from the
  element's bounding box, so a head tilted with it swings around a point far away and leaves the neck.
- **Breathing:** the torso group scales `scaleY: 1.012` from the seat (`svgOrigin: "960 800"`). The head moves
  `y: -2.35`, exactly as far as the top of the neck moves ((800 - 604) × 1.2%), with the same duration and ease.
- **Arms belong to the torso group**, so shoulders never separate from the body.
- **Head tilts** pivot on the neck (`svgOrigin: "960 604"`) and stay small (about 3°). A weary lean rotates the
  whole person about 1° from the seat.
- **Blinks** every 2.5 to 3 seconds, 70 ms each way. Expression changes swap mouth paths and rotate the brows from
  their own centres.
- **Variety:** hair style, skin and hair colours, glasses, shirt colours. Characters are always invented; never
  draw a real person.

## Whiteboard

- Sketches use rough.js with a fixed seed per shape, so re-renders are identical.
- A pen follows the drawing tip; handwriting is revealed by a growing clip.
- Labels fit their space with `fitHand()` (Caveat is about 0.42 em per character).

## Captions

Burned in, small and low: about 1.6% of the frame height, near-white with a soft outline, on a dark strip, centred,
1.75% above the bottom edge, wrapped only beyond 70% of the frame width. Never ship a default-on subtitle track,
which most players draw large. The `.srt` is written next to every film for platforms that accept caption files.

## Music and sound

- The score ([music.md](music.md)) starts a new section on every scene start, which the pipelines snap to the
  120 BPM beat; pops and reveals inside a scene use the eighth-note grid.
- Mix: the score sits under the narration (`music.level`, dB) and ducks while the voice speaks; effects are quiet;
  the whole mix is normalised to -16 LUFS with a -1.5 dB true peak.

## Pitfalls

- **`renderAt` must return nothing.** Write `window.renderAt = t => { tl.seek(t); }` with braces; a returned object
  is serialised by the browser driver and the call hangs.
- **A group that animates its own transform can't also carry a layout transform.** Wrap it in an outer group (the
  montage's `.layout`, `.stagewrap`, `.colwrap`).
- **Text measurement needs fonts loaded.** Build scenes only after `document.fonts.load(...)` for every face.
- **Encoder tags:** the encoders strip container metadata and encoder strings. A raw `strings | grep` hit inside
  compressed video is not proof of a tag; check the container metadata.
- **Headless browsers left behind** by a killed render hold memory; stop them before a re-run.

## Review checklist

1. Contact sheet: every beat reads at a glance; no two neighbouring films look alike.
2. Full-size stills: the longest texts, both result lines, the setup chips, whiteboard labels.
3. The neck across a breath cycle and a head tilt.
4. One film per story shape watched end to end with sound.
5. `verify`: lengths, resolutions, loudness, no tags.
