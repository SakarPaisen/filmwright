import json
from pathlib import Path

import pytest

from filmwright.explainer.montage import ARTS, EXAMPLE, TEMPLATE, Montage

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def montage(tmp_path):
    (tmp_path / "montage.json").write_text(EXAMPLE.read_text())
    return Montage(tmp_path)


def test_bundled_example_matches_the_repo_example():
    assert EXAMPLE.read_text() == (REPO / "examples" / "montage" / "montage.json").read_text()


def test_narration_order_is_intro_features_close(montage):
    keys = [k for k, _ in montage.lines()]
    assert keys[0] == "intro" and keys[-1] == "close"
    assert keys[1:-1] == [f["key"] for f in montage.features()]


def test_features_get_keys_and_art(tmp_path):
    cfg = json.loads(EXAMPLE.read_text())
    cfg["features"] = [{"title": "One", "line": "One."}, {"title": "Two", "line": "Two.", "art": "lock"}]
    (tmp_path / "montage.json").write_text(json.dumps(cfg))
    fs = Montage(tmp_path).features()
    assert [f["key"] for f in fs] == ["f1", "f2"]
    assert fs[0]["art"] in ARTS and fs[1]["art"] == "lock"


def test_every_art_kind_exists_in_the_template():
    html = TEMPLATE.read_text()
    for art in ARTS:
        assert f"  {art}(st, f, t0, t1)" in html


def test_page_config_carries_brand_and_aspect(montage, tmp_path):
    (tmp_path / "beats.json").write_text(json.dumps([{"key": k, "text": t, "dur": 2.0} for k, t in montage.lines()]))
    page = montage.page("9x16")
    assert page["ASPECT"] == "9x16" and page["MC"]["brand"]["wordmark"] == "ACME TASKS"
    assert len(page["BEATS"]) == len(montage.features()) + 2
