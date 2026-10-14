"""Where filmwright keeps its bundled files and its per-user cache.

Bundled (read-only, shipped in the wheel):
    PKG / "assets"     fonts, presenter characters, motion engine
    PKG / "templates"  scene, story, montage and example templates
    PKG / "brands"     the example brand

Per user (writable): ``$FILMWRIGHT_CACHE`` or ``$XDG_CACHE_HOME/filmwright`` (default ``~/.cache/filmwright``)
    holds Chromium, Rhubarb Lip Sync and downloaded fonts. Voice models stay in the Hugging Face cache.
"""
from __future__ import annotations

import os
from pathlib import Path

PKG = Path(__file__).resolve().parent
ASSETS = PKG / "assets"
FONTS = ASSETS / "fonts"
TEMPLATES = PKG / "templates"
BRANDS = PKG / "brands"
TOOLS = PKG / "tools"

FONT_REGULAR = FONTS / "IBMPlexSans-Regular.ttf"
FONT_SEMIBOLD = FONTS / "IBMPlexSans-SemiBold.ttf"
FONT_BOLD = FONTS / "IBMPlexSans-Bold.ttf"


def cache_dir() -> Path:
    base = os.environ.get("FILMWRIGHT_CACHE") or Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "filmwright"
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p


def brand_dir(name_or_path: str | os.PathLike) -> Path:
    """A brand is either a folder path holding brand.yaml, or the name of a bundled brand."""
    p = Path(name_or_path).expanduser()
    if (p / "brand.yaml").is_file():
        return p.resolve()
    bundled = BRANDS / str(name_or_path)
    if (bundled / "brand.yaml").is_file():
        return bundled
    raise FileNotFoundError(f"no brand.yaml in {p} and no bundled brand named {name_or_path!r}")
