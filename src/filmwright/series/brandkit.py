"""Brand support: load a brand file and recolour the animated scene templates from it.

The scene templates (templates/brand-scenes/*) are drawn in the example brand's palette: an indigo neutral ramp, a violet
accent, and a few semantic colours (green and red for up and down, blue and teal for categories). `templates/brand-scenes/
palette.json` lists the seven native roles and, for every other tone in the templates, whether it belongs to the accent
family or the neutral ramp. `recolor()` re-expresses the templates in another brand's palette by ROLE, not colour by colour:

  1. the named roles map exactly (bg, bg2, card, line, ink, muted, accent, on_accent);
  2. any other neutral-ramp tone keeps its lightness but takes the brand neutrals' hue and (scaled) saturation;
  3. any other accent tone keeps its relative lightness and takes the brand accent's hue and saturation;
  4. everything else (green, red, white, black, category colours) is left alone, so up/down meanings survive.

The headline font and the wordmark are not text-swapped: the scenes read them from PARAMS.brand (see runtime.js, intro.html, outro.html).

A brand with `native: true` (the bundled example) is returned untouched.
"""
from __future__ import annotations

import colorsys
import json
import re
from pathlib import Path
from typing import Any

import yaml

from filmwright.paths import BRANDS, TEMPLATES

PALETTE = json.loads((TEMPLATES / "brand-scenes" / "palette.json").read_text())
NATIVE: dict[str, str] = {k: v for k, v in PALETTE["native"].items() if k != "on_accent"}   # role -> hex, as drawn
NATIVE_ON_ACCENT = PALETTE["native"]["on_accent"]
FAMILIES: dict[str, str] = PALETTE["families"]                                               # hex -> accent | neutral


def load_brand(name_or_path: str | Path) -> dict[str, Any]:
    p = Path(str(name_or_path)).expanduser()
    if p.suffix in (".yaml", ".yml"):
        f = p
    elif (p / "brand.yaml").is_file():
        f = p / "brand.yaml"
    else:
        f = BRANDS / str(name_or_path) / "brand.yaml"
    if not f.exists():
        raise SystemExit(f"brand not found: {name_or_path} (looked for {f})")
    b = yaml.safe_load(f.read_text())
    b["_dir"] = f.parent
    b.setdefault("native", False)
    b.setdefault("themes", {"main": b["colors"]["accent"]})
    b.setdefault("fonts", {"headline": '"IBM Plex Sans", system-ui, sans-serif'})
    return b


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in (r, g, b))


def _hls(h: str) -> tuple[float, float, float]:
    r, g, b = _hex_to_rgb(h)
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)


def _from_hls(hh: float, ll: float, ss: float) -> str:
    r, g, b = colorsys.hls_to_rgb(hh % 1.0, max(0.0, min(1.0, ll)), max(0.0, min(1.0, ss)))
    return _rgb_to_hex(r * 255, g * 255, b * 255)


class Recolor:
    def __init__(self, brand: dict[str, Any]) -> None:
        c = brand["colors"]
        self.exact = {NATIVE[k].lower(): c[k].lower() for k in NATIVE if k in c}
        if NATIVE_ON_ACCENT.lower() != "#ffffff":         # white is used everywhere; only a tinted on-accent is mapped
            self.exact[NATIVE_ON_ACCENT.lower()] = c.get("on_accent", "#ffffff").lower()
        nh, nl, ns = _hls(NATIVE["bg2"])
        bh, bl, bs = _hls(c["bg2"])
        self.n_hue, self.n_sat_scale = bh, max(0.35, min(1.4, bs / ns if ns else 1.0))
        ah, al, as_ = _hls(c["accent"])
        _, gl, _ = _hls(NATIVE["accent"])
        self.a_h, self.a_s, self.a_lscale = ah, as_, (al / gl if gl else 1.0)
        self.cache: dict[str, str] = {}

    def hex(self, h: str) -> str:
        key = h.lower()
        if len(key) == 4:
            key = "#" + "".join(ch * 2 for ch in key[1:])
        if key in self.cache:
            return self.cache[key]
        fam = FAMILIES.get(key)
        if key in self.exact:
            out = self.exact[key]
        elif fam == "accent":                                                             # accent tones -> brand accent
            hh, ll, ss = _hls(key)
            out = _from_hls(self.a_h, ll * self.a_lscale, self.a_s)
        elif fam == "neutral":                                                            # neutral ramp -> brand neutrals
            hh, ll, ss = _hls(key)
            out = _from_hls(self.n_hue, ll, ss * self.n_sat_scale)
        else:
            out = key
        self.cache[key] = out
        return out

    def text(self, s: str) -> str:
        s = re.sub(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", lambda m: self.hex(m.group(0)), s)

        def rgba(m: re.Match) -> str:
            r, g, b = int(m.group(2)), int(m.group(3)), int(m.group(4))
            nr, ng, nb = _hex_to_rgb(self.hex(_rgb_to_hex(r, g, b)))
            return f"{m.group(1)}({nr},{ng},{nb}"
        return re.sub(r"(rgba?)\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", rgba, s)


def recolor(text: str, brand: dict[str, Any]) -> str:
    """Scene template text re-expressed in the brand's palette (identity for a native brand)."""
    if brand.get("native"):
        return text
    return Recolor(brand).text(text)


def theme_color(brand: dict[str, Any], theme: str | None) -> str:
    return brand["themes"].get(theme or "main") or brand["themes"].get("main") or brand["colors"]["accent"]
