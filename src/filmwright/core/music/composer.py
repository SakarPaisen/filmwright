"""An original score for a film, composed for a mood and locked to its scene changes.

Every cut (a scene change, in seconds) starts a new section on its own downbeat. Unless the caller asks for
snapping, sections start exactly at the cut times and each keeps its own beat grid, so the music follows the
picture rather than the other way round. Before each cut, moods that build get a riser or a swell and the kick
drops out for the last half beat; moods with impacts land one on the cut. The first section is a lighter intro,
the last one is the fullest, and the film ends on a ringing tonic chord.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Any

import numpy as np

from .moods import Mood, get_mood, parse_chord
from .synth import NOTE, RATE, Synth, hz

TARGET_RMS = 10 ** (-19.0 / 20)      # about -17 LUFS for typical material
ARP = ((0, 1, 2, 1), (0, 2, 1, 2), (0, 1, 2, 3), (2, 1, 0, 1))


def snap_cuts(cuts: list[float], bpm: float, first: float = 0.0) -> list[float]:
    """Move each cut to the nearest beat of a grid that starts at `first` (and drop duplicates)."""
    beat = 60.0 / bpm
    out: list[float] = []
    for c in sorted(cuts):
        s = round(first + round((c - first) / beat) * beat, 4)
        if not out or s > out[-1] + 1e-6:
            out.append(s)
    return out


def plan(seconds: float, cuts: list[float], mood: Mood | str, bpm: float | None = None,
         snap: bool = False) -> list[dict[str, Any]]:
    """The sections of the score: [{start, end, kind, prog}], kind in intro | main | close | solo."""
    mood = get_mood(mood) if isinstance(mood, str) else mood
    bpm = float(bpm or mood.bpm)
    tail = 2.0 if seconds >= 8 else max(0.5, seconds * 0.2)
    end_music = max(0.5, seconds - tail)
    cs = sorted({round(float(c), 4) for c in cuts if 0.0 < float(c) < end_music - 0.25})
    if snap:
        cs = [c for c in snap_cuts(cs, bpm) if 0.0 < c < end_music - 0.25]
    starts = [0.0] + cs
    ends = cs + [end_music]
    out = []
    for i, (s, e) in enumerate(zip(starts, ends)):
        if len(starts) == 1:
            kind = "solo"
        elif i == 0:
            kind = "intro"
        elif i == len(starts) - 1:
            kind = "close"
        else:
            kind = "main"
        prog = 0 if kind in ("intro", "solo") else (i - 1) % len(mood.progressions)
        out.append({"start": s, "end": e, "kind": kind, "prog": prog})
    return out


class _Track:
    def __init__(self, seconds: float):
        self.n = int(RATE * (seconds + 2.0))
        self.L = np.zeros(self.n)
        self.R = np.zeros(self.n)

    def put(self, x: np.ndarray, t: float, pan: float = 0.5, gain: float = 1.0) -> None:
        s = int(round(t * RATE))
        if s >= self.n or s < 0 or len(x) == 0:
            return
        e = min(self.n, s + len(x))
        y = x[: e - s] * gain
        self.L[s:e] += y * (1 - pan) * 2 ** 0.5 * 0.71
        self.R[s:e] += y * pan * 2 ** 0.5 * 0.71


def _lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    """Second-order Butterworth magnitude response, applied in the frequency domain (zero phase)."""
    spec = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(x.shape[0], 1 / RATE)
    spec *= (1 / np.sqrt(1 + (f / cutoff) ** 4))[:, None]
    return np.fft.irfft(spec, n=x.shape[0], axis=0)


def _reverb(x: np.ndarray, amount: float, rng: np.random.Generator) -> np.ndarray:
    if amount <= 0:
        return x
    decay = 0.35 + 1.6 * amount
    n_ir = int(RATE * min(3.0, decay * 2.2))
    t = np.arange(n_ir) / RATE
    out = np.empty_like(x)
    size = 1 << int(np.ceil(np.log2(x.shape[0] + n_ir)))
    for ch in range(x.shape[1]):
        ir = rng.standard_normal(n_ir) * np.exp(-t * 6.9 / decay)
        ir[: int(0.012 * RATE)] = 0.0                       # pre-delay
        ir /= np.sqrt(np.sum(ir ** 2))
        wet = np.fft.irfft(np.fft.rfft(x[:, ch], size) * np.fft.rfft(ir, size), size)[: x.shape[0]]
        out[:, ch] = x[:, ch] + amount * 0.6 * wet
    return out


def _voicing(root: int, iv: tuple[int, ...], octave: int) -> list[float]:
    base = 12 * (octave + 1) + root
    return [440.0 * 2 ** ((base + i - 69) / 12) for i in iv]


def compose(seconds: float, cuts: list[float], mood: Mood | str, bpm: float | None = None, seed: int = 23,
            snap: bool = False) -> np.ndarray:
    """Return the score as a (frames, 2) float array in -1..1."""
    mood = get_mood(mood) if isinstance(mood, str) else mood
    bpm = float(bpm or mood.bpm)
    beat = 60.0 / bpm
    syn = Synth(seed)
    tr = _Track(seconds)
    put = tr.put
    sections = plan(seconds, cuts, mood, bpm, snap)
    end_music = sections[-1]["end"]

    for i, sec in enumerate(sections):
        t0, t1, kind = sec["start"], sec["end"], sec["kind"]
        prog = mood.progressions[sec["prog"]]
        light = kind == "intro"
        has_next = i + 1 < len(sections)
        arp = ARP[(sec["prog"] + (1 if mood.lead == "piano" else 0)) % len(ARP)]
        k = 0
        while t0 + k * beat < t1 - 1e-6:
            t = t0 + k * beat
            bar, pos = divmod(k, 4)
            root, iv = parse_chord(prog[bar % len(prog)], mood.key)
            chord_tones = iv[:3] if len(iv) >= 3 else iv
            last_half = has_next and t >= t1 - beat * 0.5 - 1e-6
            sw = mood.swing * beat / 2

            # --- a soft chord accent on the downbeat of each new section, for moods with no drums to mark it
            if k == 0 and i > 0 and mood.drums == "none":
                acc_fn = {"piano": syn.piano, "bell": syn.bell, "marimba": syn.marimba}.get(mood.lead, syn.pluck)
                for x, off in zip(chord_tones, (0.0, 0.012, 0.024)):
                    put(acc_fn(hz((root + x) % 12, max(3, mood.lead_octave - 1)), 2.5, mood.lead_level * 1.4),
                        t + off, 0.35 + 0.15 * chord_tones.index(x))
                put(syn.bass(hz(root, 2), min(2.0, t1 - t), "sustain"), t, 0.5, 0.9)

            # --- drums
            d = mood.drums
            if d == "four":
                if not light and not last_half:
                    put(syn.kick(), t, 0.5)
                elif light and pos in (0, 2) and t > 2.5 and not last_half:
                    put(syn.kick(), t, 0.5, 0.55)
                if not light and pos in (1, 3):
                    put(syn.clap(), t, 0.45)
                put(syn.hat(), t + beat / 2, 0.62)
                if not light:
                    put(syn.hat(), t, 0.38, 0.7)
                    if pos == 3:
                        put(syn.hat(True), t + beat / 2, 0.6)
            elif d == "light":
                if pos in (0, 2) and not last_half and (not light or t > 2.0):
                    put(syn.kick(0.8), t, 0.5, 0.7 if not light else 0.45)
                if not light and pos in (1, 3):
                    put(syn.clap(), t, 0.47, 0.55)
                put(syn.hat(amp=0.8), t + beat / 2, 0.62)
            elif d == "bounce":
                if not last_half and (pos in (0, 2) or (pos == 1 and not light)):
                    put(syn.kick(0.7), t + (beat / 2 if pos == 1 else 0), 0.5, 0.6)
                if not light and pos in (1, 3):
                    put(syn.clap(), t, 0.5, 0.75)
                for h in range(4):
                    put(syn.shaker(1.0 if h % 2 else 0.6), t + h * beat / 4 + (sw / 2 if h % 2 else 0), 0.65)
            elif d == "halftime":
                if pos == 0 and not last_half:
                    put(syn.kick(1.2), t, 0.5, 1.0)
                    put(syn.tom(55, 0.9 if not light else 0.5), t, 0.5)
                if not light:
                    if pos == 2:
                        put(syn.snare(), t, 0.5, 1.1)
                    if not last_half:
                        for h, (f0, g) in enumerate(((95, 0.35), (80, 0.3))):
                            put(syn.tom(f0, g), t + beat / 2 + h * 0.001, 0.3 + 0.4 * h)
            elif d == "tick":
                for h in range(4):
                    put(syn.hat(amp=0.55 if h % 2 else 0.35), t + h * beat / 4, 0.6)
                if pos == 0 and not last_half and not light:
                    put(syn.kick(0.6), t, 0.5, 0.55)

            # --- bass
            fb = hz(root, 2)
            if mood.bass == "pump" and not light:
                for h in (0, 0.5):
                    put(syn.bass(fb, beat * 0.48, "pump"), t + h * beat, 0.5)
            elif mood.bass == "pulse" and not light:
                for h in (0, 0.5):
                    put(syn.bass(fb, beat * 0.4, "pulse"), t + h * beat, 0.5, 0.85)
            elif mood.bass == "bounce" and not light:
                for h, octv in ((0, 2), (0.5, 3)):
                    put(syn.bass(hz(root, octv), beat * 0.3, "bounce"), t + h * beat + (sw if h else 0), 0.5)
            elif mood.bass == "ostinato":
                for h in (0, 0.5):
                    put(syn.bass(hz(root, 2), beat * 0.42, "ostinato"), t + h * beat, 0.5, 0.6 if light else 0.9)
            elif mood.bass == "sustain" and pos == 0:
                dur = min(4 * beat, t1 - t + 0.2)
                put(syn.bass(hz(root, 2 if mood.drums != "halftime" else 1), dur, "sustain"), t, 0.5, 0.8 if light else 1.0)

            # --- lead
            if mood.lead != "none":
                rate = max(1, mood.lead_rate // (2 if light and mood.lead_rate > 1 else 1))
                for j in range(rate):
                    tj = t + j * beat / rate + (sw if j % 2 else 0)
                    if tj >= t1 - 1e-6:
                        continue
                    idx = arp[(k * rate + j) % len(arp)] % len(chord_tones)
                    octv = mood.lead_octave + (1 if (mood.lead == "pluck" and j == 3) else 0)
                    f = hz((root + chord_tones[idx]) % 12, octv)
                    amp = mood.lead_level * (0.85 if light else 1.0)
                    pan = 0.3 + 0.4 * (j % 2)
                    if mood.lead == "pluck":
                        put(syn.pluck(f, 0.5, amp), tj, pan)
                    elif mood.lead == "piano":
                        put(syn.piano(f, min(2.5, beat * 4), amp), tj, pan)
                    elif mood.lead == "marimba":
                        put(syn.marimba(f, 0.35, amp), tj, pan)
                    elif mood.lead == "bell" and (pos in (0, 2) or kind == "close"):
                        put(syn.bell(f, 3.0, amp), tj, float(syn.rng.uniform(0.3, 0.7)))
                    elif mood.lead == "ping" and pos in (0, 3):
                        g = hz((root + (chord_tones[idx] if pos == 0 else 1)) % 12, octv)   # a semitone rub on beat 4
                        put(syn.ping(g, 2.0, amp), tj, float(syn.rng.uniform(0.2, 0.8)))

            # --- stabs
            if mood.stabs == "offbeat" and not light and pos in (1, 3):
                put(syn.stab([hz((root + x) % 12, 4) for x in chord_tones], 0.3, 0.035), t + beat / 2, 0.5)
            elif mood.stabs == "brass" and not light and pos == 0:
                put(syn.stab(_voicing(root, chord_tones, 3), beat * 1.6, 0.03, brass=True), t, 0.5)

            # --- pads
            if pos == 0:
                level = mood.pad * (0.6 if light else 1.0)
                if kind == "close":
                    level = max(level * 1.3, 0.02 if mood.pad == 0 else level * 1.3)
                if level > 0:
                    dur = min(4 * beat + 0.3, t1 - t + 0.4)
                    notes = _voicing(root, chord_tones, 3) + [hz(root, 4)]
                    put(syn.pad(notes, dur, level, mood.pad_timbre), t, 0.5)
            k += 1

        # --- transition into the next section
        if has_next:
            if mood.risers == "riser":
                put(syn.riser(beat * 1.5), t1 - beat * 1.5, 0.5)
            elif mood.risers == "swell":
                put(syn.swell(beat * 2), t1 - beat * 2, 0.5)
            if mood.impacts > 0:
                boom, crash = syn.impact()
                put(boom, t1, 0.5, 0.8 * mood.impacts)
                put(crash, t1 + 0.002, 0.2, 0.5 * mood.impacts)
                put(crash, t1, 0.8, 0.5 * mood.impacts)

    # --- the ending: a ringing tonic chord
    tonic = (0, 4, 7) if mood.scale == "major" else (0, 3, 7)
    kp = NOTE[mood.key]
    ring = min(2.6, seconds - end_music + 0.6)
    put(syn.pad(_voicing(kp, tonic, 3) + [hz(kp, 4), hz((kp + 7) % 12, 4)], ring, 0.04, "sine"), end_music, 0.5)
    lead_fn = {"piano": syn.piano, "bell": syn.bell, "marimba": syn.marimba}.get(mood.lead, syn.pluck)
    put(lead_fn(hz(kp, 5), 2.0, 0.12), end_music, 0.5)
    put(lead_fn(hz((kp + 7) % 12, 5), 2.0, 0.09), end_music + 0.02, 0.6)
    if mood.impacts > 0:
        boom, crash = syn.impact()
        put(boom, end_music, 0.5, 0.6 * mood.impacts)
        put(crash, end_music, 0.5, 0.5 * mood.impacts)

    st = np.stack([tr.L, tr.R], axis=1)
    st = _lowpass(st, mood.brightness)
    st = _reverb(st, mood.reverb, syn.rng)
    st = st[: int(round(RATE * seconds))]
    fade = min(len(st), int(RATE * 0.6))
    if fade:
        st[-fade:] *= np.linspace(1, 0, fade)[:, None]
    head = min(len(st), int(RATE * 0.01))
    if head:
        st[:head] *= np.linspace(0, 1, head)[:, None]
    peak = float(np.abs(st).max()) if len(st) else 0.0
    rms = float(np.sqrt(np.mean(st ** 2))) if len(st) else 0.0
    if peak > 0 and rms > 0:
        st *= min(TARGET_RMS / rms, 0.89 / peak)      # an even loudness across moods, never above -1 dBFS peak
    return st


def write_stereo(path: Path, st: np.ndarray) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype("<i2").tobytes())
    return path


def score(out_wav: Path, seconds: float, cuts: list[float], mood: str = "upbeat", bpm: float | None = None,
          seed: int = 23, snap: bool = False) -> Path:
    """Compose and write a 48 kHz stereo WAV of `seconds` with a section downbeat on every cut."""
    if mood == "none":
        raise ValueError("mood 'none' means no music; don't call score()")
    return write_stereo(Path(out_wav), compose(seconds, cuts, mood, bpm, seed, snap))
