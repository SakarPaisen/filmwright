"""Word timings from the narration, and the gestures, moods and anchors that follow from the words.

The narration is synthesised sentence by sentence, so the audio has a short pause between sentences. We use
those pauses to place each sentence exactly, then spread the words of a sentence by their length. That puts a
word within about 0.2 s of where it is spoken, which is enough to land a gesture or a callout on it.

    words = word_times(text, sentences, wav)            # [{word, raw, start, end, si}] seconds from the narration start
    part  = anchor_words(part, words, lead)             # callouts / spotlights / focus / phrases may say `word: "export"`
    extra = speech_gestures(words, lead, seconds, busy) # beats, counting, a shrug, calm hands, moods
    env   = energy_track(wav, lead)                     # loudness envelope the host's movement follows

Everything here is deterministic.
"""
from __future__ import annotations

import copy
import re
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

SR = 16000
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
COUNT_NOUNS = {"steps", "sources", "groups", "things", "signals", "filters", "views", "ways", "kinds", "numbers", "charts",
               "panels", "tabs", "teams", "types", "parts", "areas", "lists", "features", "options", "files", "tasks"}
EMPHASIS = {"rare", "only", "every", "each", "all", "biggest", "largest", "single", "never", "instead", "stands", "everything",
            "whole", "together", "same", "first", "newest", "plain", "free", "straight", "key", "thousands", "hundreds",
            "billions", "millions", "closer", "full", "fully", "easy", "easier", "quickly", "quick"}
SMILE = {"easy", "simple", "free", "quick", "quickly", "helps", "glance", "clear", "plain", "straight", "together", "place",
         "everything", "easier", "catch", "fast"}
SHRUG_AFTER = ("not a guarantee", "no magic", "not a promise", "it depends", "not a judgement", "not a judgment")


def _decode(wav: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype="<f4") if raw else np.zeros(SR // 10, dtype=np.float32)


def _rms(x: np.ndarray, hop: int = SR // 100, win: int = SR // 50) -> np.ndarray:
    n = max(1, (len(x) - win) // hop + 1)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    return np.sqrt((x[np.minimum(idx, len(x) - 1)] ** 2).mean(axis=1))


def speech_segments(wav: Path, min_gap: float = 0.17) -> list[tuple[float, float]]:
    """Voiced stretches (seconds from the start of the file), split wherever there is a pause of `min_gap`."""
    r = _rms(_decode(wav))
    if r.size == 0 or r.max() <= 0:
        return []
    voiced = r > max(r.max() * 0.04, 1e-4)
    segs, start, last = [], None, None
    gap = int(min_gap * 100)
    for i, v in enumerate(voiced):
        if v:
            if start is None:
                start = i
            elif i - last > gap:
                segs.append((start / 100, (last + 1) / 100))
                start = i
            last = i
    if start is not None:
        segs.append((start / 100, (last + 1) / 100))
    return segs


def _fit_segments(segs: list[tuple[float, float]], n: int, lengths: list[int]) -> list[tuple[float, float]]:
    """Make the found segments match the number of sentences: merge across the smallest gaps, or fall back to
    spreading the sentences over the whole voiced stretch by their length."""
    if not segs:
        return []
    segs = list(segs)
    while len(segs) > n:
        gaps = [segs[k + 1][0] - segs[k][1] for k in range(len(segs) - 1)]
        k = int(np.argmin(gaps))
        segs[k:k + 2] = [(segs[k][0], segs[k + 1][1])]
    if len(segs) == n:
        return segs
    lo, hi = segs[0][0], segs[-1][1]
    tot = float(sum(lengths)) or 1.0
    out, cur = [], lo
    for L in lengths:
        d = (hi - lo) * L / tot
        out.append((cur, cur + d))
        cur += d
    return out


def word_times(text: str, sentences: list[str], wav: Path) -> list[dict[str, Any]]:
    sentences = [s for s in sentences if s.strip()] or [text]
    segs = _fit_segments(speech_segments(wav), len(sentences), [len(s) for s in sentences])
    if not segs:
        return []
    words: list[dict[str, Any]] = []
    for si, (sen, (a, b)) in enumerate(zip(sentences, segs)):
        toks = sen.split()
        weights = [len(re.sub(r"\W", "", t)) + 1 + (3 if t.endswith((",", ";", ":")) else 0) for t in toks]
        tot = float(sum(weights)) or 1.0
        cur = a
        for t, wgt in zip(toks, weights):
            d = (b - a) * wgt / tot
            clean = re.sub(r"[^\w$%'-]", "", t).lower()
            if clean:
                words.append({"word": clean, "raw": t, "start": round(cur, 3), "end": round(cur + d, 3), "si": si})
            cur += d
    return words


def anchor_words(part: dict[str, Any], words: list[dict[str, Any]], lead: float) -> dict[str, Any]:
    """Replace `word: "export"` on callouts, spotlights, focus and phrases with the time that word is spoken."""
    out = copy.deepcopy(part)
    for key in ("focus", "callouts", "spotlight", "phrases"):
        for spec in out.get(key) or []:
            if "word" not in spec:
                continue
            needle = str(spec["word"]).lower()
            hits = [w for w in words if w["word"] == needle] or [w for w in words if needle in w["word"]]
            if not hits:
                print(f"  {key} word '{spec['word']}': not found in the narration, using the event time", flush=True)
                continue
            w = hits[min(int(spec.get("word_nth", 0)), len(hits) - 1)]
            spec["at"] = round(max(0.0, lead + w["start"] - float(spec.get("lead_in", 0.3))), 2)
    return out


def energy_track(wav: Path, lead: float, fps: int = 10) -> dict[str, Any]:
    """Loudness per 1/fps second, 0..1, with `lead` seconds of silence in front (the section's quiet start)."""
    r = _rms(_decode(wav), hop=SR // fps, win=SR // fps)
    if r.size:
        p = float(np.percentile(r, 95)) or 1.0
        r = np.clip(r / p, 0.0, 1.0)
        k = np.array([0.25, 0.5, 0.25])
        r = np.convolve(np.pad(r, 1, mode="edge"), k, mode="valid")
    vals = [0.0] * int(round(lead * fps)) + [round(float(v), 3) for v in r]
    return {"fps": fps, "values": vals}


def speech_gestures(words: list[dict[str, Any]], lead: float, seconds: float, busy: list[tuple[float, float]],
                    seed: int = 7) -> dict[str, Any]:
    """Gestures and moods that follow the words. `busy` are (start, end) spans where other gestures or camera moves
    already happen, so these stay out of their way."""
    gestures: list[dict[str, Any]] = []
    moods: list[dict[str, Any]] = []
    if not words:
        return {"gestures": gestures, "mood": moods}
    T = lambda w: lead + w["start"]                              # noqa: E731  section time of a word
    free = lambda t0, t1: not any(a - 0.3 < t1 and t0 < b + 0.5 for a, b in busy + [(g["start"], g["end"]) for g in gestures])  # noqa: E731

    # counting: "three steps", "all three"
    for k, w in enumerate(words):
        n = NUMBER_WORDS.get(w["word"])
        if n and n >= 2:
            nxt = [x["word"] for x in words[k + 1:k + 3]]
            prev = words[k - 1]["word"] if k else ""
            if any(x in COUNT_NOUNS for x in nxt) or prev in ("all", "these", "those", "of"):
                t = T(w)
                if free(t - 0.2, t + 1.8):
                    gestures.append({"type": "count", "start": round(t - 0.2, 2), "end": round(t + 1.7, 2), "n": n, "side": "R"})

    # a gentle shrug on a hedge such as "not a guarantee"
    low = " ".join(w["word"] for w in words)
    for phrase in SHRUG_AFTER:
        pos = low.find(phrase)
        if pos >= 0:
            idx = len(low[:pos].split())
            if idx < len(words):
                t = T(words[idx])
                if free(t - 0.2, t + 1.5):
                    gestures.append({"type": "shrug", "start": round(t - 0.15, 2), "end": round(t + 1.3, 2)})
            break

    # emphasis beats on stressed words, spaced out, alternating arms
    last = -9.0
    side = "L"
    for w in words:
        t = T(w)
        key = w["word"]
        stress = key in EMPHASIS or bool(re.match(r"^\$?\d", key)) or key in NUMBER_WORDS
        if not stress or t < 1.0 or t > seconds - 1.2 or t - last < 1.9 or not free(t - 0.2, t + 0.9):
            continue
        gestures.append({"type": "beat", "start": round(t - 0.1, 2), "end": round(t + 0.7, 2), "strength": 0.75, "side": side})
        side = "R" if side == "L" else "L"
        last = t

    # calm hands together in long gaps between gestures (at most two per section)
    marks = sorted((g["start"], g["end"]) for g in gestures) + sorted(busy)
    marks = sorted(marks)
    cur, made = 1.4, 0
    for a, b in marks + [(seconds - 1.0, seconds)]:
        if a - cur >= 3.4 and made < 2:
            gestures.append({"type": "hands", "start": round(cur + 0.5, 2), "end": round(min(a - 0.6, cur + 4.5), 2)})
            made += 1
        cur = max(cur, b)

    # moods: a smile around benefit words
    for w in words:
        if w["word"] in SMILE:
            t = T(w)
            if not moods or t - moods[-1]["end"] > 0.3:
                moods.append({"start": round(t - 0.5, 2), "end": round(t + 1.6, 2), "smile": 0.7, "brow": 0.3})
    return {"gestures": gestures, "mood": moods}
