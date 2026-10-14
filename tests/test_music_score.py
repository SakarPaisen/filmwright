import shutil
import wave

import numpy as np
import pytest

from filmwright.core.music import MOODS, ambient, plan, score, snap_cuts


def _read(path):
    with wave.open(str(path)) as w:
        assert w.getnchannels() == 2 and w.getframerate() == 48000
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).astype(float) / 32767


def test_sections_start_exactly_on_cuts():
    cuts = [3.17, 7.5, 12.04]
    secs = plan(20.0, cuts, "upbeat")
    assert [s["start"] for s in secs] == [0.0] + cuts
    assert [s["kind"] for s in secs] == ["intro", "main", "main", "close"]
    assert all(a["end"] == b["start"] for a, b in zip(secs, secs[1:]))


def test_snapping_puts_cuts_on_the_beat_grid():
    beat = 60 / 120
    secs = plan(20.0, [3.17, 7.6, 12.04], "upbeat", snap=True)
    for s in secs[1:]:
        assert abs(s["start"] / beat - round(s["start"] / beat)) < 1e-6
    assert snap_cuts([1.1, 1.2], 120) == [1.0]


def test_cuts_outside_the_film_are_ignored():
    secs = plan(10.0, [0, -1, 4.0, 9.9, 50], "calm")
    assert [s["start"] for s in secs] == [0.0, 4.0]


@pytest.mark.parametrize("mood", sorted(MOODS))
def test_score_renders_every_mood(tmp_path, mood):
    out = score(tmp_path / f"{mood}.wav", 6.0, [2.0, 4.0], mood)
    x = _read(out)
    assert len(x) == 6 * 48000
    peak = np.abs(x).max()
    assert 0.2 < peak < 0.95                     # audible, never clipped
    assert np.sqrt((x ** 2).mean()) > 0.01       # not silent


def test_score_is_deterministic(tmp_path):
    a = _read(score(tmp_path / "a.wav", 5.0, [2.5], "playful", seed=5))
    b = _read(score(tmp_path / "b.wav", 5.0, [2.5], "playful", seed=5))
    assert np.array_equal(a, b)


def test_upbeat_lands_on_the_cut(tmp_path):
    x = _read(score(tmp_path / "u.wav", 12.0, [6.0], "upbeat")).mean(1)
    i, w = 6 * 48000, int(0.12 * 48000)
    after = np.sqrt((x[i:i + w] ** 2).mean())
    before = np.sqrt((x[i - w:i] ** 2).mean())
    assert after > 2 * before                    # impact on the cut, kick dropped just before it


def test_none_mood_is_not_a_score(tmp_path):
    with pytest.raises(ValueError):
        score(tmp_path / "n.wav", 5.0, [], "none")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_ambient_bed(tmp_path):
    x = _read(ambient(tmp_path / "bed.wav", 8.0, "sad"))
    assert abs(len(x) / 48000 - 8.0) < 0.05 and np.abs(x).max() > 0.05
