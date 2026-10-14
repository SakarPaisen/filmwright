"""Quiet background beds: a slow chord progression on detuned sine pads with a soft bass and an occasional bell,
low-passed and given a little echo. Meant to sit about 20 dB under narration and be noticed only if it stops.
It has no beat and no sections; use composer.score() when the music should follow scene changes.

Beds: calm (A minor), bright (C major), focus (D minor), sad (A minor, darker), tense (C minor).
Any score mood name also works and maps to the nearest bed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from .composer import write_stereo
from .synth import RATE

NOTE = {"C": 0, "D": 2, "Eb": 3, "E": 4, "F": 5, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
CHORDS = {"Am": ("A", "C", "E"), "F": ("F", "A", "C"), "C": ("C", "E", "G"), "G": ("G", "B", "D"),
          "Dm": ("D", "F", "A"), "Bb": ("Bb", "D", "F"), "Em": ("E", "G", "B"), "Cm": ("C", "Eb", "G"),
          "Ab": ("Ab", "C", "Eb"), "Fm": ("F", "Ab", "C")}
AMBIENT_MOODS = {"calm": (["Am", "F", "C", "G"], 9.0), "bright": (["C", "G", "Am", "F"], 8.0),
                 "focus": (["Dm", "Bb", "F", "C"], 10.0), "sad": (["Am", "Dm", "F", "Em"], 10.0),
                 "tense": (["Cm", "Ab", "Fm", "G"], 9.0)}
MOOD_TO_AMBIENT = {"upbeat": "bright", "playful": "bright", "inspiring": "bright", "corporate": "focus",
                   "calm": "calm", "sad": "sad", "epic": "focus", "suspense": "tense"}


def hz(name: str, octave: int) -> float:
    return 440.0 * 2 ** ((NOTE[name] - 9) / 12 + (octave - 4))


def voicing(chord: str) -> list[float]:
    """Close voicing around middle C, with the root an octave lower for warmth."""
    root, third, fifth = CHORDS[chord]
    out, last = [hz(root, 3)], hz(root, 3)
    for n in (third, fifth, root):
        f = hz(n, 3)
        while f <= last:
            f *= 2
        out.append(f)
        last = f
    return out


def ambient(out_wav: Path, seconds: float, mood: str = "calm", seed: int = 7) -> Path:
    """Write a quiet 48 kHz stereo bed of `seconds`. `mood` is a bed name or a score mood name."""
    bed = mood if mood in AMBIENT_MOODS else MOOD_TO_AMBIENT.get(mood, "calm")
    progression, chord_len = AMBIENT_MOODS[bed]
    rng = np.random.default_rng(seed)
    n = int((seconds + 2) * RATE)
    t = np.arange(n) / RATE
    left, right = np.zeros(n), np.zeros(n)
    fade = 3.0                                    # chords cross-fade over three seconds
    n_chords = int(np.ceil((seconds + 2) / chord_len)) + 1
    for i in range(n_chords):
        start = i * chord_len - fade / 2
        env = np.clip((t - start) / fade, 0, 1) - np.clip((t - start - chord_len) / fade, 0, 1)
        env = 0.5 - 0.5 * np.cos(np.pi * env)      # raised cosine: no clicks between chords
        chord = progression[i % len(progression)]
        for j, f in enumerate(voicing(chord)):
            amp = 0.16 if j else 0.12
            for detune, pan in ((1.0, 0.5), (1.0035, 0.15), (0.9965, 0.85)):
                phase = rng.uniform(0, 2 * np.pi)
                tone = np.sin(2 * np.pi * f * detune * t + phase) + 0.18 * np.sin(4 * np.pi * f * detune * t + phase)
                left += amp / 3 * env * tone * (1 - pan)
                right += amp / 3 * env * tone * pan
        bass = 0.10 * env * np.sin(2 * np.pi * hz(CHORDS[chord][0], 2) * t)
        left += bass
        right += bass
    tt = rng.uniform(2.0, 4.0)                    # an occasional soft bell on a chord tone
    while tt < seconds:
        chord = progression[int(tt // chord_len) % len(progression)]
        f = hz(CHORDS[chord][rng.integers(0, 3)], 5)
        i0 = int(tt * RATE)
        k = np.arange(min(int(3.5 * RATE), n - i0)) / RATE
        bell = 0.05 * np.exp(-k / 1.2) * (np.sin(2 * np.pi * f * k) + 0.3 * np.sin(2 * np.pi * f * 2.76 * k))
        pan = rng.uniform(0.3, 0.7)
        left[i0:i0 + len(k)] += bell * (1 - pan)
        right[i0:i0 + len(k)] += bell * pan
        tt += rng.uniform(2.5, 5.0)
    swell = 1 + 0.08 * np.sin(2 * np.pi * 0.05 * t)   # a slow breath, so it never feels static
    stereo = np.stack([left * swell, right * swell], axis=1)
    stereo /= max(1e-9, np.abs(stereo).max()) / 0.7
    out_wav = Path(out_wav)
    raw = out_wav.with_suffix(".raw.wav")
    write_stereo(raw, stereo)
    p = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(raw), "-af",
                        "lowpass=f=3200,aecho=0.8:0.55:190|310:0.28|0.18,"
                        f"afade=t=in:d=2,afade=t=out:st={max(0.0, seconds - 3):.2f}:d=3,atrim=0:{seconds:.2f}",
                        "-ar", str(RATE), "-fflags", "+bitexact", "-flags:a", "+bitexact", str(out_wav)],
                       capture_output=True, text=True)
    raw.unlink(missing_ok=True)
    if p.returncode:
        raise RuntimeError(f"ambient render failed: {p.stderr[-400:]}")
    return out_wav


make_ambient = ambient
