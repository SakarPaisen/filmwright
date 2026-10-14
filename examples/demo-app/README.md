# Example: a demo walkthrough of a sample app

"Acme Tasks" is a tiny fictional to-do app in `app/` (plain HTML, CSS and JavaScript; data stays in the browser tab).
It gives demo mode something real to record without touching anyone's product.

```bash
cd examples/demo-app
python -m http.server 8765 --directory app &     # serve the sample app on localhost
filmwright build                                 # or step by step:
python -m filmwright.demo.run_scenarios scenarios.yaml   # record S01-S03 headless -> videos/, results.md
python -m filmwright.demo.build_video video.yaml         # narrate and assemble -> out/acme-tasks-tour.mp4
```

- `scenarios.yaml`: three scenarios (see docs/scenario-dsl.md), each recorded as its own clip with an event log.
- `video.yaml`: the film: title card, one narrated section per clip, closing card, music, presenter (docs/film.md).
- `reel.yaml`: the project file `filmwright build` reads; it picks the voice, host, music mood and outputs.

On a machine without the neural voice models, set `voice: {type: system}` for a quick, fully offline run.
