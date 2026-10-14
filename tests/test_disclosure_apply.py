import json
import shutil
import subprocess

import pytest

from filmwright.core.disclosure import apply, disclosure_text

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def _film(path):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x180:r=30:d=1",
                    "-f", "lavfi", "-i", "sine=f=440:d=1:sample_rate=48000", "-ac", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
                    "-bsf:v", "filter_units=remove_types=6", "-metadata:s:v:0", "encoder=", "-metadata:s:a:0", "encoder=", str(path)],
                   check=True)
    return path


def _probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_text_depends_on_voice():
    assert "synthetic" in disclosure_text("preset")
    assert "consent" in disclosure_text("clone")


def test_none_is_a_no_op(tmp_path):
    f = _film(tmp_path / "f.mp4")
    before = f.read_bytes()
    apply(f, "none", "preset")
    assert f.read_bytes() == before


def test_metadata(tmp_path):
    f = _film(tmp_path / "f.mp4")
    dur = float(_probe(f)["format"]["duration"])
    apply(f, "metadata", "clone")
    info = _probe(f)
    tags = {k.lower(): v for k, v in info["format"].get("tags", {}).items()}
    assert "cloned voice" in tags.get("comment", "")
    assert abs(float(info["format"]["duration"]) - dur) < 0.05
    stream_tags = [s.get("tags", {}).get("encoder", "") for s in info["streams"]]
    assert not any(stream_tags) and "encoder" not in tags


def test_end_card(tmp_path):
    f = _film(tmp_path / "f.mp4")
    out = apply(f, "end-card", "preset", out=tmp_path / "g.mp4")
    info = _probe(out)
    assert abs(float(info["format"]["duration"]) - 3.0) < 0.15
    assert "synthetic" in {k.lower(): v for k, v in info["format"]["tags"].items()}["comment"]
    assert f.exists()                      # the original is untouched when out= is given


def test_bad_mode(tmp_path):
    with pytest.raises(ValueError):
        apply(_film(tmp_path / "f.mp4"), "watermark", "preset")
