import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from filmwright.core.mix import mix

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
SR = 48000


def tone(path: Path, freq: float, seconds: float, amp: float, gaps: bool = False) -> Path:
    t = np.arange(int(SR * seconds)) / SR
    x = amp * np.sin(2 * np.pi * freq * t)
    if gaps:                                    # speech-like: on for half a second, off for half a second
        x *= (np.floor(t * 2) % 2 == 0)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    return path


def samples(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, "<f4").reshape(-1, 2)


def test_stems_add_up_to_the_mix(tmp_path):
    vo = tone(tmp_path / "vo.wav", 220, 4.0, 0.3, gaps=True)
    music = tone(tmp_path / "music.wav", 440, 4.0, 0.2)
    sfx = tone(tmp_path / "sfx.wav", 880, 1.0, 0.1)
    out = mix(vo, tmp_path / "mix.wav", music, sfx, music_db_under=-12, seconds=4.0, stems_dir=tmp_path / "stems")
    stems = {n: samples(tmp_path / "stems" / f"{n}.wav") for n in ("narration", "music", "sfx")}
    assert not list((tmp_path / "stems").glob("*.raw.wav"))
    whole = samples(out)
    for name, x in stems.items():
        assert len(x) == len(whole), name                 # every stem runs the mix's full length
    total = sum(stems.values())
    err = np.sqrt(np.mean((total - whole) ** 2)) / np.sqrt(np.mean(whole ** 2))
    assert err < 0.02, err                              # summed stems match the mix to within 2% RMS
    assert np.abs(stems["sfx"][SR * 2:]).max() < 1e-4  # the one-second effect stays where it was
