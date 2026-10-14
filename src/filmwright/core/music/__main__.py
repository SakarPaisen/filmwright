"""Render music from the command line.

    python -m filmwright.core.music list
    python -m filmwright.core.music render --mood sad --seconds 30 --cuts 0,8,16 out.wav
    python -m filmwright.core.music render --mood upbeat --seconds 40 --cuts 6.2,13.9 --snap out.wav
    python -m filmwright.core.music render --ambient --mood calm --seconds 120 bed.wav
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import AMBIENT_MOODS, MOODS, ambient, plan, score


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m filmwright.core.music", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list the moods")
    r = sub.add_parser("render", help="render a score (or an ambient bed) to a WAV")
    r.add_argument("out", type=Path)
    r.add_argument("--mood", default="upbeat")
    r.add_argument("--seconds", type=float, required=True)
    r.add_argument("--cuts", default="", help="comma-separated scene-change times in seconds")
    r.add_argument("--bpm", type=float)
    r.add_argument("--seed", type=int, default=23)
    r.add_argument("--snap", action="store_true", help="snap the cuts to the beat grid")
    r.add_argument("--ambient", action="store_true", help="a quiet bed with no beat (ignores --cuts)")
    a = ap.parse_args(argv)

    if a.cmd == "list":
        for m in MOODS.values():
            print(f"{m.name:10s} {m.bpm:5.0f} bpm  {m.key} {m.scale:5s}  {m.description}")
        print(f"\nambient beds: {', '.join(AMBIENT_MOODS)} (score mood names also work)")
        return 0

    if a.ambient:
        print(ambient(a.out, a.seconds, a.mood))
        return 0
    cuts = [float(c) for c in a.cuts.split(",") if c.strip()]
    out = score(a.out, a.seconds, cuts, a.mood, a.bpm, a.seed, a.snap)
    secs = plan(a.seconds, cuts, a.mood, a.bpm, a.snap)
    print(out)
    print("sections: " + ", ".join(f"{s['kind']}@{s['start']:.2f}" for s in secs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
