"""Make the sample recording the hybrid example uses: recordings/inbox.mp4, an 8-second animation of a small
fictional task app (mock-app.html). In your own films, use real recordings instead, for example the
videos/<scenario>.mp4 files that `filmwright` demo runs produce.

    python examples/both/make_sample_clip.py
"""
from pathlib import Path

from filmwright.explainer import render as R

HERE = Path(__file__).resolve().parent

if __name__ == "__main__":
    out = HERE / "recordings" / "inbox.mp4"
    R.render_frames(HERE / "mock-app.html", {}, 8.0, out, size=(1920, 1080), fps=30, workers=1, dpr=1)
    print(out)
