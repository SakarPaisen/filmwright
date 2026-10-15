"""The 2D animated presenter: a rigged cartoon narrator whose mouth follows the narration and whose
gestures aim at what the camera is about to show.

For each film section, the demo builder calls `render_presenter()` with the section's narration WAV and
text; `overlay_on_video()` puts the host over any finished film (explainers, hybrid films). This module:
1. gets mouth cues from Rhubarb Lip Sync (MIT; installed by `filmwright setup`), or, where Rhubarb isn't
   available, from the narration's loudness;
2. builds a timeline: blinks (some double), syllable beats for micro-nods, a wave on the first section,
   a thumbs-up on the last, an open-palm "present" when a section opens on a new screen, and a point at
   every zoom target, with the target mapped from film pixels into the character's own coordinates so the
   finger, eyes and lean really aim at it;
3. fades the presenter out while the camera is zoomed in, so it never covers the target;
4. renders transparent PNG frames of assets/presenter/presenter.html in open-source Chromium
   (deterministically, 30 fps) and encodes them to a QuickTime RLE movie with alpha.

Sections are rendered in parallel. Stand-alone preview, over a real UI frame with crosshairs at the
aimed targets:

    python -m filmwright.presenter preview --bg frame.png --text "Hello." [--style ana] [--out preview.mp4]
    python -m filmwright.presenter overlay film.mp4 --wav narration.wav --out film-host.mp4 [--style maya]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np

from filmwright.demo.recorder import launch_kwargs
from filmwright.paths import ASSETS, cache_dir

# FILMWRIGHT_PRESENTER_HTML: try another character file
HTML = Path(os.environ.get("FILMWRIGHT_PRESENTER_HTML") or (ASSETS / "presenter" / "presenter.html"))
FPS = 30
VIEW = (560, 420)            # CSS px of the character's canvas (80 px of padding each side, so hands never clip)
VIEW_OFFSET = 80             # the SVG viewBox starts at x = -80: canvas px → character coordinates
STYLES = ("leo", "leo-light", "leo-stubble", "sam", "ana", "lee", "maya", "raj", "kit", "jo")
DEFAULT_PLACEMENT = {"position": "bottom-right", "height": 0.21, "margin": 0.015}


def rhubarb_path() -> str | None:
    if os.environ.get("FILMWRIGHT_RHUBARB"):
        return os.environ["FILMWRIGHT_RHUBARB"]
    cache = cache_dir()
    for c in sorted((cache / "rhubarb").glob("*/rhubarb")) + sorted((cache / "rhubarb").glob("*/rhubarb.exe")):
        if os.access(c, os.X_OK):
            return str(c)
    return shutil.which("rhubarb")


def mouth_cues(wav: Path, text: str, work: Path) -> tuple[list[dict[str, Any]], str]:
    """(cues, source). Rhubarb reads 16-bit mono WAV; the dialog text makes its recogniser more accurate."""
    mono = work / (wav.stem + ".16k.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-ar", "16000", "-ac", "1",
                    "-sample_fmt", "s16", str(mono)], check=True)
    exe = rhubarb_path()
    if exe:
        out = work / (wav.stem + ".rhubarb.json")
        cmd = [exe, "-f", "json", "-o", str(out)]
        if text.strip():
            dialog = work / (wav.stem + ".txt")
            dialog.write_text(text)
            cmd += ["--dialogFile", str(dialog)]
        p = subprocess.run(cmd + [str(mono)], capture_output=True, text=True)
        if p.returncode == 0 and out.exists():
            cues = json.loads(out.read_text())["mouthCues"]
            return [{"start": float(c["start"]), "end": float(c["end"]), "value": c["value"]} for c in cues], "rhubarb"
    # Fallback: loudness → open/closed shapes. Not lip-sync, but the mouth moves with the voice.
    with wave.open(str(mono)) as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768
    step = 16000 // 25
    cues, t = [], 0.0
    peak = max(1e-6, float(np.percentile(np.abs(pcm), 99)))
    for i in range(0, len(pcm), step):
        rms = float(np.sqrt(np.mean(pcm[i:i + step] ** 2))) / peak
        shape = "X" if rms < 0.06 else "B" if rms < 0.18 else "C" if rms < 0.4 else "D"
        if cues and cues[-1]["value"] == shape:
            cues[-1]["end"] = t + step / 16000
        else:
            cues.append({"start": t, "end": t + step / 16000, "value": shape})
        t += step / 16000
    return cues, "loudness"


def mapping(frame: tuple[int, int], placement: dict[str, Any]) -> tuple[float, float, float]:
    """(ox, oy, scale): where the character canvas sits in the film frame, so targets can be mapped."""
    fw, fh = frame
    ph = fh * float(placement.get("height", 0.21))
    cw = VIEW[0] * ph / VIEW[1]
    margin = fw * float(placement.get("margin", 0.015))
    ox = margin if str(placement.get("position", "bottom-right")) == "bottom-left" else fw - margin - cw
    return ox, fh - ph, ph / VIEW[1]


def to_canvas(xy: tuple[float, float], m: tuple[float, float, float]) -> list[float]:
    """Film px → character coordinates (the SVG's user space)."""
    ox, oy, s = m
    return [round((xy[0] - ox) / s - VIEW_OFFSET, 1), round((xy[1] - oy) / s, 1)]


def beats_from_cues(cues: list[dict[str, Any]], lead: float) -> list[float]:
    """Syllable onsets: a closed→open transition, or a jump to a big shape. At most one per 0.28 s."""
    big = {"C", "D", "H"}
    out: list[float] = []
    prev = "X"
    for c in cues:
        v = c["value"]
        onset = (prev == "X" and v != "X") or (v in big and prev not in big and prev != "X")
        if onset and (not out or c["start"] + lead - out[-1] >= 0.28):
            out.append(round(c["start"] + lead, 3))
        prev = v
    return out


def body_rect(frame: tuple[int, int], placement: dict[str, Any]) -> tuple[float, float, float, float]:
    """Where the character's body (not the padded canvas) sits in the film frame: x0, y0, x1, y1."""
    ox, oy, s = mapping(frame, placement)
    return (ox + 100 * s, oy + 50 * s, ox + (VIEW[0] - 100) * s, oy + VIEW[1] * s)


def build_timeline(cues: list[dict[str, Any]], seconds: float, lead: float, voice_seconds: float,
                   camera: list[tuple[float, float, float, float]], frame: tuple[int, int],
                   placement: dict[str, Any], first: bool, last: bool, kind: str = "clip",
                   seed: int = 7, demo_idle: bool = False, hide: list[tuple[float, float]] | None = None,
                   points: list[tuple[float, float, float]] | None = None,
                   words: list[dict[str, Any]] | None = None, energy: dict[str, Any] | None = None) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    m = mapping(frame, placement)
    mouth = [{"start": c["start"] + lead, "end": c["end"] + lead, "value": c["value"]} for c in cues]
    blinks, t = [], float(rng.uniform(0.8, 2.0))
    while t < seconds - 0.3:
        blinks.append(round(t, 3))
        if rng.random() < 0.2:
            blinks.append(round(t + 0.26, 3))      # an occasional double blink reads as alive
        t += float(rng.uniform(2.2, 4.8))
    gestures: list[dict[str, Any]] = []
    zoom_ins = [(t0, cx, cy) for (t0, z0, _, _), (t1, z1, cx, cy) in zip(camera, camera[1:]) if z0 == 1.0 and z1 > 1.0]
    if first:
        gestures.append({"type": "wave", "start": 0.7, "end": 2.5})
    elif kind == "clip" and (not zoom_ins or zoom_ins[0][0] > 5.0):
        # a new screen: an open hand toward it, then back
        gestures.append({"type": "present", "start": 1.1, "end": 3.4, "target": to_canvas((frame[0] * 0.42, frame[1] * 0.45), m)})
    elif kind == "card" and not last:
        gestures.append({"type": "present", "start": 1.0, "end": 3.2, "target": to_canvas((frame[0] * 0.3, frame[1] * 0.4), m)})
    for t0, cx, cy in zoom_ins:
        gestures.append({"type": "point", "start": max(0.0, t0 - 1.0), "end": t0 + 0.25, "target": to_canvas((cx, cy), m)})
    for t0, cx, cy in (points or []):             # callouts and spotlights: point at them as they appear
        if not any(abs(t0 - z[0]) < 1.5 for z in zoom_ins):
            gestures.append({"type": "point", "start": max(0.0, t0 - 0.8), "end": t0 + 1.4, "target": to_canvas((cx, cy), m)})
    if last:
        gestures.append({"type": "thumbs", "start": max(0.6, seconds - 4.2), "end": seconds - 1.4})
        gestures.append({"type": "nod", "start": max(0.5, seconds - 4.0), "end": seconds - 1.6})
    # gestures and moods that follow the words: beats on stressed words, counting, a shrug, calm hands
    mood: list[dict[str, Any]] = []
    if words:
        from filmwright.demo import cues as speech_cues  # (`cues` here is the lip-sync list)
        busy_spans = [(a_, b_) for a_, b_ in (hide or [])] + [(g["start"], g["end"]) for g in gestures]
        busy_spans += [(max(0.0, t0 - 1.0), t0 + 0.25) for t0, _, _ in zoom_ins]
        if last:
            busy_spans.append((max(0.6, seconds - 4.2), seconds - 1.4))
        extra = speech_cues.speech_gestures(words, lead, seconds, busy_spans)
        gestures += extra["gestures"]
        mood = extra["mood"]
    # blink when the gaze shifts, as people do
    for g in gestures:
        if g["type"] in ("point", "present", "wave") and not any(abs(b - g["start"]) < 0.4 for b in blinks):
            blinks.append(round(g["start"] + 0.06, 3))
    # glances at the camera: as the section opens, and when the narration ends
    glances = [{"start": 0.55, "end": 1.9}]
    if voice_seconds and lead + voice_seconds + 1.8 < seconds - 0.8:
        glances.append({"start": lead + voice_seconds + 0.3, "end": lead + voice_seconds + 1.7})
    for gl in glances:
        if not any(abs(b - gl["start"]) < 0.4 for b in blinks):
            blinks.append(round(gl["start"] + 0.05, 3))
    blinks.sort()
    # idle poses: drift between a few relaxed poses during long sections, never mid-gesture
    idle = [{"start": 0.0, "pose": "rest"}]
    busy = [(g["start"] - 1.6, g["end"] + 0.9) for g in gestures]
    choices = ["clasp", "chin", "hip", "rest"] if kind == "clip" else ["clasp", "rest"]
    if demo_idle:
        idle += [{"start": 2.6 * (k + 1), "pose": choices[k % len(choices)]} for k in range(int(seconds / 2.6))]
    elif seconds > 9:
        t = float(rng.uniform(6.5, 10.0))
        while t < seconds - 4.0:
            if not any(a < t < b for a, b in busy):
                options = [c for c in choices if c != idle[-1]["pose"]]
                idle.append({"start": round(t, 2), "pose": options[int(rng.integers(0, len(options)))]})
                t += float(rng.uniform(7.0, 12.0))
            else:
                t += 0.5
    zoomed = [(a[0], b[0]) for a, b in zip(camera, camera[1:]) if a[1] > 1.0 or b[1] > 1.0]
    zoomed = sorted(zoomed + [(max(0.0, a), min(seconds, b)) for a, b in (hide or []) if b > a])   # + steps that happen under the presenter
    opacity: list[dict[str, Any]] = []
    if zoomed:
        wins = [list(zoomed[0])]
        for a, b in zoomed[1:]:
            if a <= wins[-1][1] + 0.05:
                wins[-1][1] = max(wins[-1][1], b)
            else:
                wins.append([a, b])
        opacity = [{"start": a, "end": b, "value": 0.0} for a, b in wins]
    return {"mouth": mouth, "blinks": blinks, "beats": beats_from_cues(cues, lead), "gestures": gestures,
            "idle": idle, "glances": glances, "opacity": opacity, "talking": [{"start": lead, "end": lead + voice_seconds}] if voice_seconds else [],
            "fadeIn": 0.5, "fadeOut": 0.5, "duration": seconds,
            "mood": mood, "energy": energy, "entrance": {"slide": 0.6}, "exitSlide": True}


def render_frames(timeline: dict[str, Any], seconds: float, out_mov: Path, style: str | dict[str, Any],
                  scale: int = 2) -> Path:
    from playwright.sync_api import sync_playwright
    name, overrides = (style, {}) if isinstance(style, str) else (str(style.get("preset", "sam")), style)
    frames_dir = Path(tempfile.mkdtemp(prefix="filmwright-presenter-"))
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs(args=[f"--force-device-scale-factor={scale}"]))
            ctx = browser.new_context(viewport={"width": VIEW[0], "height": VIEW[1]})
            page = ctx.new_page()
            page.goto(HTML.as_uri())
            page.evaluate("([n, o]) => window.setStyle(n, o)", [name, {k: v for k, v in overrides.items() if k != "preset"}])
            page.evaluate("tl => { window.TIMELINE = tl }", timeline)
            cdp = ctx.new_cdp_session(page)
            cdp.send("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
            n = max(1, int(round(seconds * FPS)))
            for i in range(n):
                page.evaluate(f"window.render({i / FPS:.5f})")
                shot = cdp.send("Page.captureScreenshot", {
                    "format": "png", "captureBeyondViewport": False,
                    "clip": {"x": 0, "y": 0, "width": VIEW[0], "height": VIEW[1], "scale": 1}})
                (frames_dir / f"f{i:05d}.png").write_bytes(base64.b64decode(shot["data"]))
            ctx.close()
            browser.close()
        p = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames_dir / "f%05d.png"),
                            "-c:v", "qtrle", "-pix_fmt", "argb", str(out_mov)], capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError(f"presenter encode failed: {p.stderr[-400:]}")
        return out_mov
    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)


def render_presenter(wav: Path | None, text: str, seconds: float, lead: float, voice_seconds: float,
                     camera: list[tuple[float, float, float, float]], frame: tuple[int, int],
                     out_mov: Path, style: str | dict[str, Any], first: bool = False, last: bool = False,
                     kind: str = "clip", placement: dict[str, Any] | None = None,
                     hide: list[tuple[float, float]] | None = None, work: Path | None = None,
                     points: list[tuple[float, float, float]] | None = None,
                     words: list[dict[str, Any]] | None = None) -> tuple[Path, str]:
    """One section's presenter movie (with alpha) and the lip-sync source used."""
    work = work or out_mov.parent
    cues, source = mouth_cues(wav, text, work) if wav and text else ([], "silent")
    energy = None
    if wav:
        from filmwright.demo import cues as speech_cues
        energy = speech_cues.energy_track(wav, lead)
    tl = build_timeline(cues, seconds, lead, voice_seconds, camera, frame, placement or DEFAULT_PLACEMENT,
                        first, last, kind, hide=hide, points=points, words=words, energy=energy)
    render_frames(tl, seconds, out_mov, style)
    return out_mov, source


def _probe(path: Path, entries: str, stream: str | None = None) -> list[str]:
    cmd = ["ffprobe", "-v", "error"] + (["-select_streams", stream] if stream else []) + \
          ["-show_entries", entries, "-of", "csv=p=0", str(path)]
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip().split(",")


def overlay_on_video(in_mp4: Path | str, narration_wav: Path | str | None, out_mp4: Path | str,
                     character: str | dict[str, Any] = "leo", corner: str = "bottom-right",
                     height: float = 0.25, text: str = "", lead: float = 0.0) -> Path:
    """Draw the lip-synced host over a finished film and keep the film's own audio.

    `narration_wav` is the narration on its own, starting at the film's t=0 (or at `lead` seconds); the host's
    mouth follows it. Without it the host still breathes, blinks, waves at the start and gives a thumbs-up at
    the end. `character` is a preset name (see STYLES) or {"preset": name, "shirt": "#hex", ...}. `corner` is
    bottom-right or bottom-left; `height` is the host's height as a share of the frame height."""
    in_mp4, out_mp4 = Path(in_mp4), Path(out_mp4)
    if corner not in ("bottom-right", "bottom-left"):
        raise ValueError("corner must be bottom-right or bottom-left")
    name = character if isinstance(character, str) else str(character.get("preset", "leo"))
    if name not in STYLES:
        raise ValueError(f"unknown presenter character {name!r}; choose one of {', '.join(STYLES)}")
    w, h = (int(v) for v in _probe(in_mp4, "stream=width,height", "v:0")[:2])
    seconds = float(_probe(in_mp4, "format=duration")[0])
    has_audio = bool(_probe(in_mp4, "stream=index", "a")[0])
    work = Path(tempfile.mkdtemp(prefix="filmwright-host-"))
    try:
        wav = Path(narration_wav) if narration_wav else None
        voice_seconds = float(_probe(wav, "format=duration")[0]) if wav else 0.0
        placement = {"position": corner, "height": height, "margin": 0.015}
        cues, source = mouth_cues(wav, text, work) if wav else ([], "silent")
        energy = None
        if wav:
            from filmwright.demo import cues as speech_cues
            energy = speech_cues.energy_track(wav, lead)
        tl = build_timeline(cues, seconds, lead, voice_seconds, [], (w, h), placement, True, True, "clip", energy=energy)
        mov = render_frames(tl, seconds, work / "host.mov", character)
        ph = int(h * height) // 2 * 2
        margin = int(w * 0.015)
        x = f"{margin}" if corner == "bottom-left" else f"W-w-{margin}"
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(in_mp4), "-i", str(mov), "-filter_complex",
               f"[1:v]format=rgba,scale=-1:{ph}:flags=lanczos[p];[0:v][p]overlay={x}:H-h:eof_action=pass,format=yuv420p[v]",
               "-map", "[v]"] + (["-map", "0:a", "-c:a", "copy"] if has_audio else []) + \
              ["-c:v", "libx264", "-preset", "medium", "-crf", "17", "-fflags", "+bitexact", "-flags:v", "+bitexact",
               "-metadata:s:v:0", "encoder=", "-movflags", "+faststart", str(out_mp4)]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError(f"presenter overlay failed: {p.stderr[-600:]}")
        from filmwright.core.tags import strip_encoder_tags
        strip_encoder_tags(out_mp4)
        print(f"presenter: {name}, {corner}, lip-sync from {source}")
        return out_mp4
    finally:
        shutil.rmtree(work, ignore_errors=True)


class PresenterPool:
    """Renders sections concurrently (Rhubarb and Chromium are each single-threaded per section)."""

    def __init__(self, workers: int = 3):
        self.pool = ThreadPoolExecutor(max_workers=workers)
        self.jobs: dict[int, Any] = {}

    def submit(self, key: int, **kw: Any) -> None:
        self.jobs[key] = self.pool.submit(render_presenter, **kw)

    def result(self, key: int) -> tuple[Path, str]:
        return self.jobs[key].result()

    def close(self) -> None:
        self.pool.shutdown(wait=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ov = sub.add_parser("overlay", help="draw the host over a finished film")
    ov.add_argument("video", type=Path)
    ov.add_argument("--wav", type=Path, help="the narration on its own, from the film's start")
    ov.add_argument("--text", default="", help="the narration text (makes lip-sync more accurate)")
    ov.add_argument("--style", default="leo", help=f"one of {', '.join(STYLES)}")
    ov.add_argument("--corner", default="bottom-right", choices=["bottom-right", "bottom-left"])
    ov.add_argument("--height", type=float, default=0.25)
    ov.add_argument("--out", type=Path, required=True)
    pv = sub.add_parser("preview", help="render the presenter over a frame, pointing at two crosshair targets")
    pv.add_argument("--text", default="Hi, I'm the presenter. I'll point at what matters, present a new screen, and step aside when the camera zooms in.")
    pv.add_argument("--style", default="leo", help=f"one of {', '.join(STYLES)}")
    pv.add_argument("--wav", type=Path, help="narration to lip-sync; default: espeak-ng says --text")
    pv.add_argument("--bg", type=Path, help="a frame (png/jpg) to composite over; default: a grey card")
    pv.add_argument("--targets", default="0.22,0.30;0.50,0.62", help="aim points as x,y fractions of the frame")
    pv.add_argument("--idle-demo", action="store_true", help="no zooms; cycle the idle poses every 2.6 s")
    pv.add_argument("--out", type=Path, default=Path("presenter-preview.mp4"))
    a = ap.parse_args()
    if a.cmd == "overlay":
        overlay_on_video(a.video, a.wav, a.out, a.style, a.corner, a.height, a.text)
        print(a.out)
        return 0
    work = Path(tempfile.mkdtemp(prefix="filmwright-pv-"))
    wav = a.wav
    if not wav:
        wav = work / "voice.wav"
        subprocess.run(["espeak-ng", "-v", "en-us", "-s", "165", "-w", str(wav), a.text], check=True)
    secs = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)],
                                capture_output=True, text=True).stdout.strip())
    W, H = 1920, 1080
    total = max(secs + 1.6, 12.0)
    pts = [tuple(float(v) for v in p.split(",")) for p in a.targets.split(";")]
    # camera: point at target 1 around 35% in, zoom briefly; then target 2 at 65%; the presenter steps aside during each zoom
    cam = [(0.0, 1.0, W / 2, H / 2)]
    if a.idle_demo:
        pts = []
    for k, (fx, fy) in enumerate(pts):
        t0 = total * (0.35 + 0.3 * k)
        cam += [(t0, 1.0, W / 2, H / 2), (t0 + 0.7, 1.6, fx * W, fy * H), (t0 + 2.2, 1.6, fx * W, fy * H), (t0 + 2.9, 1.0, W / 2, H / 2)]
    cues, source = mouth_cues(wav, a.text, work)
    tl = build_timeline(cues, total, 0.6, secs, cam, (W, H), DEFAULT_PLACEMENT, first=not a.idle_demo, last=not a.idle_demo,
                        kind="clip", demo_idle=a.idle_demo)
    mov = render_frames(tl, total, work / "p.mov", a.style)
    ox, oy, s = mapping((W, H), DEFAULT_PLACEMENT)
    ph = int(H * DEFAULT_PLACEMENT["height"])
    boxes = "".join(f",drawbox=x={int(fx * W) - 14}:y={int(fy * H) - 14}:w=28:h=28:color=orange@0.9:t=4" for fx, fy in pts)
    bg = ["-loop", "1", "-framerate", "30", "-i", str(a.bg)] if a.bg else ["-f", "lavfi", "-i", f"color=c=0x2b3137:s={W}x{H}:r=30"]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *bg, "-i", str(mov), "-i", str(wav), "-filter_complex",
                    f"[0:v]scale={W}:{H},format=rgba{boxes}[b];[1:v]format=rgba,scale=-1:{ph}[p];"
                    f"[b][p]overlay={int(ox)}:{int(oy)}:shortest=0:eof_action=pass,format=yuv420p[v];[2:a]adelay=600|600,apad[a]",
                    "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264", "-crf", "18", "-c:a", "aac", str(a.out)], check=True)
    shutil.rmtree(work, ignore_errors=True)
    sched = {"wave": "0.7–2.5s", **{f"point {k + 1}": f"{total * (0.35 + 0.3 * k) - 1.0:.1f}s" for k in range(len(pts))}, "thumbs": f"{total - 4.2:.1f}s"}
    print(f"{a.out} ({total:.1f}s, lip-sync: {source}) gestures: {sched}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
