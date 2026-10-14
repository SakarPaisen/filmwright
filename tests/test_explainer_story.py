import json
import shutil
from pathlib import Path

import pytest

from filmwright import paths
from filmwright.explainer import render as R
from filmwright.explainer.story import EXAMPLE, SHAPES, TEMPLATE, Project, init_project

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path):
    init_project(tmp_path)
    return Project(tmp_path)


def test_bundled_example_matches_the_repo_example():
    for name in ("project.json", "stories.json"):
        assert (EXAMPLE / name).read_text() == (REPO / "examples" / "explainer" / name).read_text()


def test_template_uses_only_bundled_assets():
    html = TEMPLATE.read_text()
    assert "fonts.googleapis" not in html and "gsap" not in html.lower().replace("gsap-compatible", "")
    for rel in ("../../assets/motion.js", "../../assets/vendor/rough.js", "../../assets/fonts/SpaceGrotesk-Variable.ttf",
                "../../assets/fonts/Caveat-Variable.ttf", "../../assets/fonts/IBMPlexSans-Bold.ttf"):
        assert rel in html
        assert (TEMPLATE.parent / rel).resolve().is_file()


@pytest.mark.parametrize("shape", ["A", "B", "C"])
def test_every_shape_has_narration_for_each_beat(project, shape):
    c = dict(project.stories[1], arch=shape, need="the plan")
    lines = project.lines(c)
    assert list(lines) == SHAPES[shape]
    assert all(t.strip() and t.strip()[-1] in ".!?" for t in lines.values())
    assert project.cfg["product"] in " ".join(lines.values()) or shape == "A"


def test_lines_can_be_overridden(project):
    c = dict(project.stories[1], lines={"meet": "Say hello to Priya."})
    assert project.lines(c)["meet"] == "Say hello to Priya."


def test_shapes_rotate_and_palettes_vary(project):
    assert [project.arch(project.stories[n]) for n in (1, 2, 3)] == ["A", "B", "C"]
    walls = {tuple(project.page_config(project.stories[n])["wall"]) for n in (1, 2, 3)}
    assert len(walls) == 3


def test_brand_defaults_and_overrides(project, tmp_path):
    b = project.brand
    assert b["wordmark"] == "ACME TASKS" and b["tagline"] == "Plan less. Do more." and b["colors"]["accent"] == "#7c5cff"
    logo = tmp_path / "logo.png"
    from PIL import Image
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(logo)
    b2 = R.load_brand({"logo": "logo.png", "colors": {"accent": "#123456"}}, tmp_path)
    assert b2["logo"].startswith("data:image/png;base64,") and b2["colors"]["bg"] == "#0f1222"


def test_beats_snap_to_the_music_and_hold_long_enough():
    raw = [{"key": "meet", "text": "a", "dur": 1.0}, {"key": "setup", "text": "b", "dur": 1.0}, {"key": "result", "text": "c", "dur": 2.0}]
    bs = R.snap_beats(raw, 1.0, .6, .28, None, {"setup": 5.6})
    for b in bs:
        assert (b["start"] / R.BEAT) == pytest.approx(round(b["start"] / R.BEAT))
    assert bs[2]["start"] - bs[1]["start"] >= 5.6
    assert bs[1]["dur"] == 1.0            # the spoken length stays the caption length


def test_captions_are_small_and_low(tmp_path):
    beats = [{"key": "a", "text": "A short line of narration.", "start": 1.0, "dur": 2.0}, {"key": "b", "text": "", "start": 3, "dur": 1}]
    caps = R.caption_images(beats, 1920, 1080, tmp_path)
    assert len(caps) == 1
    png, x, y, t0, t1 = caps[0]
    from PIL import Image
    w, h = Image.open(png).size
    assert h < 1080 * .05 and y + h <= 1080 - 1080 * .0175 + 1 and (t0, t1) == (1.0, 3.0)


def test_srt_times(tmp_path):
    out = R.write_srt([{"text": "Hi.", "start": 61.5, "dur": 1.25}], tmp_path / "a.srt")
    assert "00:01:01,500 --> 00:01:02,750" in out.read_text()


def test_stories_need_narration_first(project):
    with pytest.raises(SystemExit):
        project.beats(project.stories[1])


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg is not installed")
def test_stills_render_without_errors(project):
    pytest.importorskip("playwright")
    from playwright.sync_api import Error
    c = project.stories[1]
    d = project.outdir(c)
    d.mkdir(parents=True, exist_ok=True)
    (d / "beats.json").write_text(json.dumps([{"key": k, "text": "x.", "dur": 3.0} for k in SHAPES["A"]]))
    try:
        files = project.stills(1, [1.0, 20.0, 34.0])
    except Error as e:
        pytest.skip(f"headless Chromium unavailable: {e}")
    assert len(files) == 3 and all(f.stat().st_size > 10_000 for f in files)
    assert paths.TEMPLATES.is_dir()
