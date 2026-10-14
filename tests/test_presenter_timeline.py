import pytest

from filmwright.paths import ASSETS
from filmwright.presenter import STYLES, overlay_on_video
from filmwright.presenter.presenter import DEFAULT_PLACEMENT, beats_from_cues, body_rect, build_timeline, mapping


def test_characters():
    assert STYLES[0] == "leo"
    assert {"leo", "sam", "ana", "lee", "maya", "raj", "kit", "jo"} <= set(STYLES)
    html = (ASSETS / "presenter" / "presenter.html").read_text()
    for s in STYLES:
        key = f'"{s}"' if "-" in s else f"{s}:"
        assert key in html, s
    assert "base64" not in html                               # no embedded third-party artwork


def test_placement_math():
    ox, oy, s = mapping((1920, 1080), DEFAULT_PLACEMENT)
    x0, y0, x1, y1 = body_rect((1920, 1080), DEFAULT_PLACEMENT)
    assert 0 < ox < x0 < x1 <= 1920 and oy < y0 < y1 <= 1080 + 1
    left = mapping((1920, 1080), {**DEFAULT_PLACEMENT, "position": "bottom-left"})
    assert left[0] < ox


def test_timeline_from_mouth_cues():
    cues = [{"start": 0.0, "end": 0.2, "value": "X"}, {"start": 0.2, "end": 0.5, "value": "C"},
            {"start": 0.5, "end": 0.6, "value": "X"}, {"start": 0.6, "end": 0.9, "value": "D"}]
    assert beats_from_cues(cues, 0.6) == [0.8, 1.2]
    tl = build_timeline(cues, 6.0, 0.6, 1.0, [], (1920, 1080), DEFAULT_PLACEMENT, True, True)
    assert tl["duration"] == 6.0 and tl["talking"] == [{"start": 0.6, "end": 1.6}]
    assert {g["type"] for g in tl["gestures"]} & {"wave", "thumbs"}


def test_overlay_rejects_unknown_character(tmp_path):
    with pytest.raises(ValueError):
        overlay_on_video(tmp_path / "in.mp4", None, tmp_path / "out.mp4", character="nobody")
    with pytest.raises(ValueError):
        overlay_on_video(tmp_path / "in.mp4", None, tmp_path / "out.mp4", corner="top-left")
