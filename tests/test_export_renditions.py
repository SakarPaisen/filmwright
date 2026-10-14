import shutil
import subprocess

import pytest

from filmwright.core.export import OUTPUTS, render_outputs
from filmwright.core.export.renditions import probe
from filmwright.core.export.social import parse_srt
from filmwright.core.export.web import vtt

SRT = "1\n00:00:00,200 --> 00:00:01,400\nHello there.\n\n2\n00:00:01,500 --> 00:00:02,800\nSecond line\nwraps here.\n"


def test_parse_srt_and_vtt():
    cues = parse_srt(SRT)
    assert cues == [(0.2, 1.4, "Hello there."), (1.5, 2.8, "Second line wraps here.")]
    assert vtt(SRT).startswith("WEBVTT\n\n00:00:00.200 --> 00:00:01.400\nHello there.")


def test_unknown_output_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        render_outputs(tmp_path / "x.mp4", None, ["8k"], tmp_path, "x")
    assert set(OUTPUTS) == {"4k", "hd", "vertical", "square", "web", "gif"}


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg")
def test_renditions_from_a_small_master(tmp_path):
    master = tmp_path / "m.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1280x720:d=3:r=30", "-f", "lavfi",
                    "-i", "sine=f=440:d=3", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(master)], check=True)
    srt = tmp_path / "m.srt"
    srt.write_text(SRT)
    files = render_outputs(master, srt, ["4k", "hd", "square", "vertical", "gif"], tmp_path / "out", "film", burn_captions=True)
    names = {f.name for f in files}
    assert names == {"film-hd.mp4", "film-square.mp4", "film-vertical.mp4", "film-teaser.gif"}     # never upscaled to 4k
    assert probe(tmp_path / "out" / "film-vertical.mp4")[:2] == (1080, 1920)
    assert probe(tmp_path / "out" / "film-square.mp4")[:2] == (1080, 1080)
    tags = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream_tags=encoder", "-of", "csv=p=0",
                           str(tmp_path / "out" / "film-hd.mp4")], capture_output=True, text=True).stdout
    assert "Lavc" not in tags and "x264" not in tags
    assert (tmp_path / "out" / "film.srt").exists()
