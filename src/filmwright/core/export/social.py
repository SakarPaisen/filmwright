#!/usr/bin/env python3
"""Social cut of a finished film: 1080p H.264, loudness-normalised, with the subtitles burned in.

Most people watch social video with the sound off, and platforms ignore the soft subtitle track the
builder writes, so this draws each cue onto the picture. ffmpeg builds without libass/drawtext can't do
that, so the captions are rendered with Pillow (IBM Plex Sans, bundled) and overlaid as images.

    python -m filmwright.core.export.social --video film.mp4 --srt film.srt --out post.mp4 [--height 1080]

Captions are small (1.7% of the height), sit at the very bottom edge and are centred left of the host, who stands in
the bottom-right corner, so they never cover the host.
Use --vertical for a 9:16 cut made from a vertical build (mkepisode spec with `vertical: true`); for a 9:16 or 1:1
cut of a landscape film use filmwright.core.export.render_outputs (outputs `vertical`, `square`).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from filmwright.paths import FONT_SEMIBOLD as FONT

STRIP = (15, 18, 34)        # caption strip colour (a near-black indigo); alpha is set per style


def parse_srt(text: str) -> list[tuple[float, float, str]]:
    def secs(s: str) -> float:
        h, m, rest = s.split(":")
        return int(h) * 3600 + int(m) * 60 + float(rest.replace(",", "."))
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        for i, ln in enumerate(lines):
            if "-->" in ln:
                a, b = (x.strip() for x in ln.split("-->"))
                cues.append((secs(a), secs(b), " ".join(lines[i + 1:]).strip()))
                break
    return [c for c in cues if c[2]]


def render(text: str, w: int, h: int, out: Path, vertical: bool = False, scale: float = 1.0, discreet: bool = False) -> None:
    if discreet:
        return render_discreet(text, w, h, out, scale)
    size = max(12, int((w * 0.025 if vertical else h * 0.017) * scale))      # half the earlier size; --caption-scale enlarges
    font = ImageFont.truetype(str(FONT), size)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    max_w = int(w * (0.80 if vertical else 0.62))
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if probe.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    lh = int(size * 1.32)
    pad_x, pad_y = int(size * 0.8), int(size * 0.5)
    bw = int(max(probe.textlength(ln, font=font) for ln in lines)) + 2 * pad_x
    bh = lh * len(lines) + 2 * pad_y
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # landscape: sit at the very bottom edge and centre on the area LEFT of the host (the host stands bottom-right);
    # vertical: centred, just above the bottom edge
    cx = w / 2 if vertical else w * 0.38
    x0 = int(cx - bw / 2)
    y0 = int(h * (0.975 if not vertical else 0.965)) - bh
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), radius=int(size * 0.6), fill=STRIP + (205,))
    for i, ln in enumerate(lines):
        tw = probe.textlength(ln, font=font)
        d.text((cx - tw / 2, y0 + pad_y + i * lh), ln, font=font, fill=(238, 242, 247, 255))
    img.save(out)


def render_discreet(text: str, w: int, h: int, out: Path, scale: float) -> None:
    """Very small, centred caption on the bottom edge: light text, thin dark outline, faint strip, at most two lines.
    The lowest text line sits 1.75% of the height above the bottom edge. Size = 1.7% of the height x scale."""
    size = max(10, int(h * 0.017 * scale))
    font = ImageFont.truetype(str(FONT), size)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for frac in (0.62, 0.70, 0.78, 0.86):               # widen only if two lines are not enough
        max_w = int(w * frac)
        lines, cur = [], ""
        for word in text.split():
            trial = (cur + " " + word).strip()
            if probe.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        if len(lines) <= 2:
            break
    lh = int(size * 1.25)
    pad_x, pad_y = int(size * 0.6), int(size * 0.2)
    bw = int(max(probe.textlength(ln, font=font) for ln in lines)) + 2 * pad_x
    text_bottom = int(h * (1 - 0.0175))
    y0 = text_bottom - lh * len(lines) - pad_y
    x0 = int(w / 2 - bw / 2)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x0, y0, x0 + bw, text_bottom + pad_y), radius=int(size * 0.4), fill=STRIP + (80,))
    for i, ln in enumerate(lines):
        tw = probe.textlength(ln, font=font)
        d.text((w / 2 - tw / 2, y0 + pad_y + i * lh), ln, font=font, fill=(244, 247, 250, 255), stroke_width=1, stroke_fill=(5, 10, 18, 235))
    img.save(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, type=Path)
    ap.add_argument("--srt", type=Path, help="subtitle file to burn in (not needed with --no-captions)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--vertical", action="store_true", help="9:16 output (1080x1920) for Reels, TikTok and Shorts")
    ap.add_argument("--caption-scale", type=float, default=1.0, help="caption size multiplier (2.2 suits feeds watched muted, e.g. LinkedIn)")
    ap.add_argument("--no-captions", action="store_true", help="same cut and loudness, but nothing is burned into the picture")
    ap.add_argument("--discreet", action="store_true", help="very small centred caption hugging the bottom edge (1.5-2%% of the height with --caption-scale ~0.9)")
    ap.add_argument("--softsubs", action="store_true", help="also embed --srt as a switchable mov_text track (use with --no-captions for a clean picture)")
    a = ap.parse_args()
    if a.softsubs and not a.srt:
        ap.error("--softsubs needs --srt")
    if not a.no_captions and not a.srt:
        ap.error("--srt is required unless --no-captions is given")
    h = a.height // 2 * 2
    w = (h * 16 // 9) // 2 * 2
    if a.vertical:
        w, h = 1080, 1920
    cues = [] if a.no_captions else parse_srt(a.srt.read_text())
    tmp = Path(tempfile.mkdtemp(prefix="filmwright-social-"))
    inputs, chain, last = ["-i", str(a.video)], [f"[0:v]scale={w}:{h}:flags=lanczos[b0]"], "b0"
    for i, (t0, t1, text) in enumerate(cues, 1):
        png = tmp / f"c{i:03d}.png"
        render(text, w, h, png, a.vertical, a.caption_scale, a.discreet)
        inputs += ["-i", str(png)]
        chain.append(f"[{last}][{i}:v]overlay=0:0:enable='between(t,{t0:.3f},{t1 + 0.15:.3f})'[b{i}]")
        last = f"b{i}"
    chain.append(f"[{last}]format=yuv420p[vout]")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    if a.softsubs:
        inputs += ["-i", str(a.srt)]
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
           "-filter_complex", ";".join(chain), "-map", "[vout]", "-map", "0:a:0", *(["-map", f"{len(cues) + 1}:0"] if a.softsubs else []),
           "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "160k", *(["-c:s", "mov_text", "-metadata:s:s:0", "language=eng"] if a.softsubs else []), "-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
           "-bsf:v", "filter_units=remove_types=6", "-metadata:s:v:0", "encoder=", "-metadata:s:a:0", "encoder=",
           "-movflags", "+faststart", str(a.out)]       # clean file: no encoder/tool tags and no encoder-settings SEI
    p = subprocess.run(cmd, capture_output=True, text=True)
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    if p.returncode:
        print(p.stderr[-800:], file=sys.stderr)
        return p.returncode
    print(f"{a.out} ({len(cues)} captions burned in, {w}x{h})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
