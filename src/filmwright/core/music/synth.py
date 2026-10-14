"""Instruments for the score, all synthesised with numpy: no samples, no models, nothing to license.

Every instrument returns a mono float array at RATE. Noise-based instruments draw from the Synth's own seeded
generator, so a score renders identically every time.
"""

from __future__ import annotations

import numpy as np

RATE = 48000
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7,
        "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def hz(pc: int, octave: int) -> float:
    """Frequency of pitch class `pc` (0 = C) in `octave` (4 = the octave of middle C)."""
    return 440.0 * 2 ** ((pc + 12 * (octave + 1) - 69) / 12)


def _t(n: int) -> np.ndarray:
    return np.arange(n) / RATE


def env(n: int, attack: float, tau: float) -> np.ndarray:
    t = _t(n)
    return np.minimum(1.0, t / max(attack, 1e-4)) * np.exp(-t / tau)


def fade_tail(x: np.ndarray, seconds: float = 0.01) -> np.ndarray:
    m = min(len(x), max(2, int(seconds * RATE)))
    x[-m:] *= 0.5 * (1 + np.cos(np.pi * np.arange(m) / (m - 1)))
    return x


class Synth:
    def __init__(self, seed: int = 23):
        self.rng = np.random.default_rng(seed)

    def noise(self, n: int) -> np.ndarray:
        return self.rng.standard_normal(n)

    # --- drums --------------------------------------------------------------------------

    def kick(self, punch: float = 1.0) -> np.ndarray:
        n = int(0.42 * RATE)
        t = _t(n)
        f = 46 + 110 * punch * np.exp(-t * 30)
        x = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t * 8.5)
        k = int(0.004 * RATE)
        x[:k] += np.linspace(0.6, 0, k) * punch
        return np.tanh(1.8 * x) * 0.9

    def clap(self) -> np.ndarray:
        n = int(0.3 * RATE)
        x = np.zeros(n)
        for d in (0, 0.011, 0.022):
            s = int(d * RATE)
            m = n - s
            x[s:] += self.noise(m) * np.exp(-np.arange(m) / RATE * (60 if d < 0.02 else 16))
        return np.diff(x, prepend=0) * 0.22

    def snare(self) -> np.ndarray:
        n = int(0.35 * RATE)
        t = _t(n)
        body = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 22) * 0.5
        rattle = np.diff(self.noise(n), prepend=0) * np.exp(-t * 13) * 0.35
        return (body + rattle) * 0.5

    def hat(self, open_: bool = False, amp: float = 1.0) -> np.ndarray:
        n = int((0.22 if open_ else 0.05) * RATE)
        x = np.diff(self.noise(n), prepend=0)
        return x * np.exp(-_t(n) * (14 if open_ else 70)) * (0.08 if open_ else 0.06) * amp

    def shaker(self, amp: float = 1.0) -> np.ndarray:
        n = int(0.07 * RATE)
        t = _t(n)
        x = np.diff(np.diff(self.noise(n), prepend=0), prepend=0)
        shape = np.minimum(1, t / 0.012) * np.exp(-t * 45)
        return x * shape * 0.025 * amp

    def tom(self, f0: float = 90.0, amp: float = 1.0) -> np.ndarray:
        """A low, booming drum (taiko-like when f0 is low)."""
        n = int(0.7 * RATE)
        t = _t(n)
        f = f0 * (1 + 0.6 * np.exp(-t * 25))
        body = np.sin(2 * np.pi * np.cumsum(f) / RATE) * np.exp(-t * 5.5)
        slap = np.diff(self.noise(n), prepend=0) * np.exp(-t * 60) * 0.25
        return np.tanh(1.5 * (body + slap)) * 0.75 * amp

    # --- bass ---------------------------------------------------------------------------

    def bass(self, f: float, dur: float, style: str = "pump") -> np.ndarray:
        n = max(1, int(dur * RATE))
        t = _t(n)
        if style == "pump":
            x = np.tanh(2.2 * np.sin(2 * np.pi * f * t)) + 0.3 * np.sin(4 * np.pi * f * t)
            return fade_tail(x * env(n, 0.005, 0.16) * 0.26)
        if style in ("pulse", "bounce", "ostinato"):
            x = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) + 0.12 * np.sin(6 * np.pi * f * t)
            tau = {"pulse": 0.12, "bounce": 0.08, "ostinato": 0.1}[style]
            return fade_tail(x * env(n, 0.004, tau) * 0.24)
        # sustain: a round held note that swells in and releases
        x = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
        shape = np.minimum(1, t / 0.08) * np.clip((dur - t) / 0.25, 0, 1)
        return x * shape * 0.2

    # --- melodic ------------------------------------------------------------------------

    def pluck(self, f: float, dur: float, amp: float) -> np.ndarray:
        n = int(dur * RATE)
        t = _t(n)
        x = sum(np.sin(2 * np.pi * f * k * t) / k * np.exp(-t * (6 + 9 * k)) for k in range(1, 6))
        return fade_tail(x * env(n, 0.003, 0.3) * amp)

    def piano(self, f: float, dur: float, amp: float) -> np.ndarray:
        n = int(dur * RATE)
        t = _t(n)
        x = np.zeros(n)
        for k in range(1, 8):
            fk = f * k * np.sqrt(1 + 0.0004 * k * k)      # slight stiff-string stretch
            x += np.sin(2 * np.pi * fk * t) / (k ** 1.3) * np.exp(-t * (1.6 + 1.4 * k))
        hammer = np.diff(self.noise(n), prepend=0) * np.exp(-t * 300) * 0.05
        return fade_tail((x + hammer) * np.minimum(1, t / 0.002) * amp)

    def bell(self, f: float, dur: float, amp: float) -> np.ndarray:
        n = int(dur * RATE)
        t = _t(n)
        x = (np.sin(2 * np.pi * f * t) * np.exp(-t / 1.1) + 0.35 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t / 0.5)
             + 0.15 * np.sin(2 * np.pi * 5.4 * f * t) * np.exp(-t / 0.25))
        return fade_tail(x * np.minimum(1, t / 0.004) * amp)

    def marimba(self, f: float, dur: float, amp: float) -> np.ndarray:
        n = int(dur * RATE)
        t = _t(n)
        x = np.sin(2 * np.pi * f * t) * np.exp(-t * 9) + 0.3 * np.sin(2 * np.pi * 3.93 * f * t) * np.exp(-t * 30)
        return fade_tail(x * np.minimum(1, t / 0.002) * amp)

    def ping(self, f: float, dur: float, amp: float) -> np.ndarray:
        """A thin, glassy high tone with a slow beat: unsettled rather than pretty."""
        n = int(dur * RATE)
        t = _t(n)
        x = np.sin(2 * np.pi * f * t) + 0.6 * np.sin(2 * np.pi * f * 1.006 * t)
        return fade_tail(x * env(n, 0.01, 0.9) * amp)

    def stab(self, notes: list[float], dur: float, amp: float, brass: bool = False) -> np.ndarray:
        n = int(dur * RATE)
        t = _t(n)
        if brass:                                            # band-limited saw with a filter-like swell
            x = sum(np.sin(2 * np.pi * f * k * t) / k * np.exp(-t * (1 + 0.8 * k)) for f in notes for k in range(1, 9))
            return fade_tail(x * np.minimum(1, t / 0.03) * np.exp(-t * 2.2) * amp)
        x = sum(np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.003 * t) for f in notes)
        return fade_tail(x * env(n, 0.01, 0.12) * amp)

    def pad(self, notes: list[float], dur: float, amp: float, timbre: str = "sine") -> np.ndarray:
        n = int(dur * RATE)
        t = _t(n)
        if timbre == "strings":
            x = sum(np.sin(2 * np.pi * f * d * k * t) / k for f in notes for d in (0.996, 1.0, 1.005) for k in range(1, 6))
            x = x * (1 + 0.05 * np.sin(2 * np.pi * 5.2 * t))          # a little vibrato-like movement
            attack, release = 0.6, 0.5
        elif timbre == "drone":
            x = sum(np.sin(2 * np.pi * f * d * t) + 0.3 * np.sin(2 * np.pi * 2 * f * d * t)
                    for f in notes[:2] for d in (0.998, 1.0, 1.003))
            x = x * (0.75 + 0.25 * np.sin(2 * np.pi * 0.18 * t))
            attack, release = 0.8, 0.6
        else:
            x = sum(np.sin(2 * np.pi * f * d * t) for f in notes for d in (0.997, 1.0, 1.004))
            attack, release = 0.35, 0.4
        e = np.minimum(1, t / attack) * np.clip((dur - t) / release, 0, 1)
        return x * e * amp

    # --- transitions --------------------------------------------------------------------

    def riser(self, dur: float) -> np.ndarray:
        n = int(dur * RATE)
        t = _t(n)
        noise = np.diff(self.noise(n), prepend=0)
        sweep = np.sin(2 * np.pi * np.cumsum(300 + 1700 * (t / dur) ** 2) / RATE)
        return (noise * 0.35 + sweep * 0.12) * (t / dur) ** 2.2 * 0.5

    def swell(self, dur: float) -> np.ndarray:
        """A soft reversed-cymbal swell: a gentler riser with no pitch sweep."""
        n = int(dur * RATE)
        t = _t(n)
        x = np.diff(self.noise(n), prepend=0)
        return x * (t / dur) ** 3 * 0.14

    def impact(self) -> tuple[np.ndarray, np.ndarray]:
        n = int(1.6 * RATE)
        t = _t(n)
        boom = np.sin(2 * np.pi * np.cumsum(38 + 50 * np.exp(-t * 12)) / RATE) * np.exp(-t * 4) * 0.7
        crash = np.diff(self.noise(n), prepend=0) * np.exp(-t * 2.6) * 0.16
        return boom + crash, crash
