
from filmwright.paths import TEMPLATES
from filmwright.series import brandkit

SCENES = TEMPLATES / "brand-scenes"


def test_example_brand_is_native_and_untouched():
    b = brandkit.load_brand("example")
    assert b["native"] is True
    text = (SCENES / "intro.html").read_text()
    assert brandkit.recolor(text, b) == text


def test_native_palette_matches_example_brand():
    b = brandkit.load_brand("example")
    for role, hexv in brandkit.NATIVE.items():
        assert b["colors"][role].lower() == hexv.lower()


def test_recolor_maps_roles_and_families():
    brand = {"colors": {"bg": "#101a14", "bg2": "#14241b", "card": "#1d3326", "line": "#2b4a37", "ink": "#f2f7f3",
                        "muted": "#a3b8aa", "accent": "#14b8a6", "on_accent": "#04201c"}, "themes": {"main": "#14b8a6"}}
    rc = brandkit.Recolor(brand)
    assert rc.hex(brandkit.NATIVE["accent"]) == "#14b8a6"
    assert rc.hex(brandkit.NATIVE["bg"]) == "#101a14"
    assert rc.hex("#22c55e") == "#22c55e"                     # semantic green is left alone
    out = brandkit.recolor((SCENES / "scenes" / "funnel.html").read_text(), brand)
    assert brandkit.NATIVE["accent"] not in out.lower()
