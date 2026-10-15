"""Every delivery format of one finished film, from its master.

    render_outputs(master_mp4, srt, outputs, out_dir, stem) -> list[Path]

Outputs (any combination, in any order):
    4k        <stem>-4k.mp4        3840 wide (2160 wide for a vertical master); only when the master is at least that big
    hd        <stem>-hd.mp4        1920x1080 (1080x1920 for a vertical master)
    vertical  <stem>-vertical.mp4  1080x1920 for Reels, Shorts and TikTok
    square    <stem>-square.mp4    1080x1080 for feeds
    web       web/<stem>-720p.mp4, -480p.mp4, -poster.jpg, .en.vtt
    gif       <stem>-teaser.gif    a 10-second, 640-wide loop

A vertical or square cut of a landscape film puts the whole picture in the middle of the frame over a blurred,
darkened copy of itself, with the captions below it. With `burn_captions` the captions are drawn into the 4K, HD,
vertical and square files (small, at the bottom); the .srt is always kept beside them, and the web files always
carry captions as a switchable WebVTT track. Every file is written without encoder or tool tags.

    python -m filmwright.core.export film.mp4 --srt film.srt --outputs hd,vertical,square,gif --out-dir out/
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from filmwright.core.export.social import parse_srt, render

OUTPUTS = ("4k", "hd", "vertical", "square", "web", "gif")
CLEAN = ["-fflags", "+bitexact", "-flags:v", "+bitexact", "-flags:a", "+bitexact", "-bsf:v", "filter_units=remove_types=6",
         "-metadata:s:v:0", "encoder=", "-metadata:s:a:0", "encoder=", "-movflags", "+faststart"]


def _run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f"ffmpeg failed: {p.stderr[-800:]}")


def probe(path: Path) -> tuple[int, int, float, bool]:
    """(width, height, seconds, has_audio)."""
    def q(*args: str) -> str:
        return subprocess.run(["ffprobe", "-v", "error", *args, str(path)], capture_output=True, text=True).stdout.strip()
    w, h = (int(v) for v in q("-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0").split(",")[:2])
    secs = float(q("-show_entries", "format=duration", "-of", "csv=p=0") or 0)
    return w, h, secs, bool(q("-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0"))


def _caption_inputs(srt: Path | None, w: int, h: int, tmp: Path, vertical: bool, base: str, start_idx: int,
                    box: tuple[int, int, int, int] | None = None) -> tuple[list[str], list[str], str]:
    """Caption PNG inputs and the overlay chain on top of stream label `base`. `box` limits the captions to a region
    (x, y, w, h) of the frame, used to put them under the picture in a vertical or square cut."""
    inputs: list[str] = []
    chain: list[str] = []
    last = base
    if not srt or not srt.exists():
        return inputs, chain, last
    bw, bh = (box[2], box[3]) if box else (w, h)
    for i, (t0, t1, text) in enumerate(parse_srt(srt.read_text())):
        png = tmp / f"cap{i:03d}.png"
        render(text, bw, bh, png, vertical=vertical, discreet=not vertical)
        inputs += ["-i", str(png)]
        x, y = (box[0], box[1]) if box else (0, 0)
        chain.append(f"[{last}][{start_idx + i}:v]overlay={x}:{y}:enable='between(t,{t0:.3f},{t1 + 0.15:.3f})'[cap{i}]")
        last = f"cap{i}"
    return inputs, chain, last


def scaled(master: Path, srt: Path | None, out: Path, width: int, height: int, burn: bool) -> Path:
    """The film at another size with the same framing (4K, HD)."""
    _, _, _, audio = probe(master)
    tmp = Path(tempfile.mkdtemp(prefix="filmwright-export-"))
    try:
        cap_in, cap_chain, last = _caption_inputs(srt if burn else None, width, height, tmp, height > width, "s", 1)
        chain = [f"[0:v]scale={width}:{height}:flags=lanczos,setsar=1[s]", *cap_chain, f"[{last}]format=yuv420p[v]"]
        _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(master), *cap_in, "-filter_complex", ";".join(chain),
              "-map", "[v]", *(["-map", "0:a:0", "-c:a", "aac", "-b:a", "192k"] if audio else []), "-sn", "-map_chapters", "-1",
              "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", *CLEAN, str(out)])
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def reframed(master: Path, srt: Path | None, out: Path, width: int, height: int, burn: bool) -> Path:
    """A taller frame (9:16 or 1:1) around a landscape film: blurred fill, the film in the middle, captions under it."""
    mw, mh, _, audio = probe(master)
    if mh >= mw * height / width:                       # the master already has this shape (or taller): just scale it
        return scaled(master, srt, out, width, height, burn)
    fg_h = round(width * mh / mw) // 2 * 2
    fg_y = (height - fg_h) // 2 - (round(height * 0.04) if height > width else 0)
    tmp = Path(tempfile.mkdtemp(prefix="filmwright-export-"))
    try:
        cap_box = (0, fg_y + fg_h, width, height - fg_y - fg_h) if height > width else None
        cap_in, cap_chain, last = _caption_inputs(srt if burn else None, width, height, tmp, height > width, "c", 1, cap_box)
        chain = ["[0:v]split=2[a][b]",
                 f"[a]scale={width}:{height}:force_original_aspect_ratio=increase:flags=bilinear,crop={width}:{height},"
                 f"boxblur=24:2,eq=brightness=-0.18:saturation=0.8[bg]",
                 f"[b]scale={width}:{fg_h}:flags=lanczos,setsar=1[fg]",
                 f"[bg][fg]overlay=0:{fg_y}[c]", *cap_chain, f"[{last}]format=yuv420p[v]"]
        _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(master), *cap_in, "-filter_complex", ";".join(chain),
              "-map", "[v]", *(["-map", "0:a:0", "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-16:TP=-1.5:LRA=11"] if audio else []),
              "-sn", "-map_chapters", "-1", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", *CLEAN, str(out)])
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def teaser_gif(master: Path, out: Path, start: float = 3.0, seconds: float = 10.0, width: int = 640) -> Path:
    _, _, total, _ = probe(master)
    start = max(0.0, min(start, total - seconds)) if total > seconds else 0.0
    _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.2f}", "-t", f"{seconds:.1f}", "-i", str(master), "-vf",
          f"fps=12,scale={width}:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=5",
          "-loop", "0", str(out)])
    return out


def render_outputs(master_mp4: Path | str, srt: Path | str | None, outputs: list[str] | tuple[str, ...], out_dir: Path | str,
                   stem: str, burn_captions: bool = False) -> list[Path]:
    """Write the requested outputs of one film into `out_dir` and return their paths (see the module docstring)."""
    master, out_dir = Path(master_mp4), Path(out_dir)
    srt_p = Path(srt) if srt else None
    unknown = [o for o in outputs if o not in OUTPUTS]
    if unknown:
        raise ValueError(f"unknown output(s) {unknown}; choose from {', '.join(OUTPUTS)}")
    out_dir.mkdir(parents=True, exist_ok=True)
    mw, mh, _, _ = probe(master)
    portrait = mh > mw
    made: list[Path] = []
    for o in dict.fromkeys(outputs):                    # keep order, drop repeats
        if o == "4k":
            size = (2160, 3840) if portrait else (3840, 2160)
            if max(mw, mh) < 3840:
                print(f"4k skipped: the master is {mw}x{mh}, and filmwright never upscales")
                continue
            made.append(scaled(master, srt_p, out_dir / f"{stem}-4k.mp4", *size, burn_captions))
        elif o == "hd":
            made.append(scaled(master, srt_p, out_dir / f"{stem}-hd.mp4", *((1080, 1920) if portrait else (1920, 1080)), burn_captions))
        elif o == "vertical":
            made.append(reframed(master, srt_p, out_dir / f"{stem}-vertical.mp4", 1080, 1920, burn_captions))
        elif o == "square":
            made.append(reframed(master, srt_p, out_dir / f"{stem}-square.mp4", 1080, 1080, burn_captions))
        elif o == "web":
            from filmwright.core.export.web import web_renditions
            files = web_renditions(master, srt_p, out_dir / "web", stem)
            made += [out_dir / "web" / f for f in files.values()]
        elif o == "gif":
            made.append(teaser_gif(master, out_dir / f"{stem}-teaser.gif"))
    if srt_p and srt_p.exists() and srt_p.parent.resolve() != out_dir.resolve():
        shutil.copy(srt_p, out_dir / f"{stem}.srt")
    from filmwright.core.tags import strip_encoder_tags
    for f in made:
        strip_encoder_tags(f)
    return made


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("master", type=Path)
    ap.add_argument("--srt", type=Path)
    ap.add_argument("--outputs", default="hd", help=f"comma-separated: {', '.join(OUTPUTS)}")
    ap.add_argument("--out-dir", type=Path, default=Path("."))
    ap.add_argument("--stem", help="output file name stem (default: the master's)")
    ap.add_argument("--burn-captions", action="store_true", help="draw the captions into the picture")
    a = ap.parse_args()
    files = render_outputs(a.master, a.srt, [x.strip() for x in a.outputs.split(",") if x.strip()], a.out_dir,
                           a.stem or a.master.stem, a.burn_captions)
    print("\n".join(str(f) for f in files))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
