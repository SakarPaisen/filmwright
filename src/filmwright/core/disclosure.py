"""Tell viewers that the narration voice is synthetic.

reel.yaml `disclosure:`
    none      nothing is added.
    metadata  (default) a plain sentence is written into the file's comment and description tags. Players and
              platforms that read metadata show it; the picture and sound are untouched (stream copy).
    end-card  the same sentence on a 2-second card appended to the film, plus the metadata tags.

The sentence depends on the voice: a cloned voice says it was used with the speaker's consent. Many places
require or expect this kind of disclosure for synthetic or cloned voices (for example the EU AI Act's
transparency rules, and several platforms' policies on altered or synthetic media); check what applies to you.

    python -m filmwright.core.disclosure film.mp4 --mode metadata --voice preset
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from filmwright.paths import FONT_REGULAR

MODES = ("none", "metadata", "end-card")
CARD_SECONDS = 2.0
CLEAN_FLAGS = ["-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact",
               "-metadata:s:v:0", "encoder=", "-metadata:s:a:0", "encoder="]


def disclosure_text(voice_type: str) -> str:
    if voice_type == "clone":
        return "Narration uses a cloned voice, used with the speaker's consent."
    if voice_type == "none":
        return ""
    return "Narration uses a synthetic voice."


def _probe(mp4: Path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(mp4)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"ffmpeg failed: {p.stderr[-600:]}")


def _card_png(path: Path, text: str, w: int, h: int) -> Path:
    img = Image.new("RGB", (w, h), (12, 14, 20))
    d = ImageDraw.Draw(img)
    size = max(14, int(h * 0.035))
    font = ImageFont.truetype(str(FONT_REGULAR), size)
    words, lines, cur = text.split(), [], ""
    for word in words:                                  # wrap to 80% of the width
        trial = f"{cur} {word}".strip()
        if d.textlength(trial, font=font) > w * 0.8 and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    lh = int(size * 1.4)
    y = (h - lh * len(lines)) // 2
    for line in lines:
        d.text(((w - d.textlength(line, font=font)) / 2, y), line, font=font, fill=(226, 230, 238))
        y += lh
    img.save(path)
    return path


def _with_metadata(src: Path, dst: Path, text: str) -> None:
    _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-map", "0", "-map_metadata", "0",
          "-c", "copy", "-metadata", f"comment={text}", "-metadata", f"description={text}", *CLEAN_FLAGS,
          "-movflags", "+faststart", str(dst)])


def _with_end_card(src: Path, dst: Path, text: str) -> None:
    info = _probe(src)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    w, h = int(v["width"]), int(v["height"])
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 30.0
    with tempfile.TemporaryDirectory(prefix="filmwright-disclosure-") as tmp:
        card = _card_png(Path(tmp) / "card.png", text, w, h)
        inputs = ["-i", str(src), "-loop", "1", "-framerate", f"{fps:.3f}", "-t", f"{CARD_SECONDS}", "-i", str(card)]
        if a:
            sr = int(a.get("sample_rate", 48000))
            layout = "stereo" if int(a.get("channels", 2)) >= 2 else "mono"
            inputs += ["-f", "lavfi", "-t", f"{CARD_SECONDS}", "-i", f"anullsrc=r={sr}:cl={layout}"]
            graph = (f"[0:v]setsar=1,format=yuv420p[v0];[1:v]scale={w}:{h},setsar=1,fps={fps:.3f},format=yuv420p[v1];"
                     "[v0][0:a][v1][2:a]concat=n=2:v=1:a=1[v][a]")
            maps = ["-map", "[v]", "-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
        else:
            graph = (f"[0:v]setsar=1,format=yuv420p[v0];[1:v]scale={w}:{h},setsar=1,fps={fps:.3f},format=yuv420p[v1];"
                     "[v0][v1]concat=n=2:v=1:a=0[v]")
            maps = ["-map", "[v]"]
        _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", graph, *maps,
              "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
              "-bsf:v", "filter_units=remove_types=6", "-map_metadata", "0",
              "-metadata", f"comment={text}", "-metadata", f"description={text}", *CLEAN_FLAGS,
              "-movflags", "+faststart", str(dst)])


def apply(mp4: Path | str, mode: str = "metadata", voice_type: str = "preset", out: Path | str | None = None) -> Path:
    """Apply the disclosure to `mp4` (in place unless `out` is given) and return the resulting path."""
    mode = mode.replace("_", "-")
    if mode not in MODES:
        raise ValueError(f"disclosure must be one of {', '.join(MODES)} (got {mode!r})")
    src = Path(mp4)
    dst = Path(out) if out else src
    text = disclosure_text(voice_type)
    if mode == "none" or not text:
        if dst != src:
            shutil.copyfile(src, dst)
        return dst
    tmp = dst.with_name(dst.stem + ".disclosure.tmp" + dst.suffix)
    try:
        if mode == "metadata" or src.suffix.lower() == ".m4a":
            _with_metadata(src, tmp, text)
        else:
            _with_end_card(src, tmp, text)
        tmp.replace(dst)
    finally:
        tmp.unlink(missing_ok=True)
    return dst


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m filmwright.core.disclosure", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", type=Path)
    ap.add_argument("--mode", choices=MODES, default="metadata")
    ap.add_argument("--voice", default="preset", help="preset | described | clone | system")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    print(apply(a.file, a.mode, a.voice, a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
