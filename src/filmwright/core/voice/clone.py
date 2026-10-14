"""Make a consented voice sample for `voice.type: clone`.

    python -m filmwright.core.voice.clone passage [--terms "Acme, Quick Add, Smart Lists"]  text to read aloud
    python -m filmwright.core.voice.clone devices                                          list microphones
    python -m filmwright.core.voice.clone record --speaker "Full Name"                     record the speaker reading it
    python -m filmwright.core.voice.clone prepare --input memo.m4a --speaker "Full Name"   use an existing recording
    python -m filmwright.core.voice.clone consent --speaker "Full Name"                    (re)record consent for a sample
    python -m filmwright.core.voice.clone check                                            length, level, transcript, consent
    python -m filmwright.core.voice.clone preview --play                                   hear the cloned voice
    python -m filmwright.core.voice.clone forget                                           delete the sample and its records

Only clone a voice with the speaker's explicit permission. Every path that creates a sample also creates a
consent record (sample.consent.json) after the speaker confirms the statement, and clone mode refuses to run
without a record whose hash matches the sample. See docs/voice.md.

Everything lives in the voice directory (default ./voice, or --voice-dir, or $FILMWRIGHT_VOICE_DIR):
- sample.wav: 24 kHz mono, silence trimmed, loudness-normalised.
- sample.txt: the words actually spoken, transcribed by Whisper rather than copied from the passage, because
  people rarely read a script word for word and a mismatched transcript degrades the clone.
- sample.consent.json: who agreed, to what, when, and the sample's SHA-256.

`record` needs the microphone, so the speaker runs it themselves. On macOS the first run asks for microphone
permission for the terminal app; if that permission is off the recording comes back silent, and this script
refuses it and says how to fix it.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .consent import STATEMENT, ConsentError, record_path, verify_consent, write_consent
from .qwen import Transcriber, VoiceUnavailable, match_score, require_mlx, wav_seconds

MIN_SECONDS, MAX_SECONDS = 6.0, 30.0
QUIET_DB = -30.0      # a sample whose loudest moment is below this is treated as "no microphone input"
CLEAN = ("highpass=f=70,"
         "silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.15,areverse,"
         "silenceremove=start_periods=1:start_threshold=-42dB:start_silence=0.25,areverse,"
         "loudnorm=I=-20:TP=-2:LRA=11")
VIRTUAL = re.compile(r"blackhole|zoom|teams|virtual|loopback|soundflower|aggregate|multi-output", re.I)


def default_voice_dir() -> Path:
    return Path(os.environ.get("FILMWRIGHT_VOICE_DIR") or "voice").expanduser()


def joined(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def make_passage(terms: list[str]) -> str:
    """About 20-25 seconds of natural narration-style speech.

    It includes the product's own names (so the clone hears how they're said), a question for rising intonation
    and a number. It's in the register of a walkthrough, because the clone copies reading style as well as timbre.
    """
    names = (f"Today we'll look at {joined(terms)}, and what changed in each one."
             if terms else "Today we'll look at what changed, and why it matters to you.")
    return " ".join([
        "Hi, I'm recording a short sample so this voice can narrate our product videos.",
        names,
        "Each video starts with a quick overview, then shows every change on screen, one step at a time.",
        "Does that sound simple? It is, and the whole thing usually takes about four minutes.",
    ])


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def need_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. Install it with: filmwright setup")


def levels(wav: Path) -> tuple[float, float]:
    """(mean, max) volume in dBFS via ffmpeg's volumedetect."""
    err = run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", "volumedetect", "-f", "null", "-"]).stderr

    def db(key: str) -> float:
        m = re.search(rf"{key}:\s*(-?[\d.]+|-inf) dB", err)
        return -120.0 if not m or m.group(1) == "-inf" else float(m.group(1))
    return db("mean_volume"), db("max_volume")


def mac_audio_devices() -> list[tuple[int, str]]:
    err = run(["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""]).stderr
    out, in_audio = [], False
    for line in err.splitlines():
        if "audio devices" in line:
            in_audio = True
        elif "video devices" in line:
            in_audio = False
        elif in_audio and (m := re.search(r"\[(\d+)\] (.+)$", line)):
            out.append((int(m.group(1)), m.group(2).strip()))
    return out


def pick_mac_device(devices: list[tuple[int, str]]) -> tuple[int, str]:
    real = [d for d in devices if not VIRTUAL.search(d[1])]
    for d in real:
        if "microphone" in d[1].lower():
            return d
    return (real or devices)[0]


def input_args(device: str | None) -> list[str]:
    if platform.system() == "Darwin":
        devs = mac_audio_devices()
        if not devs:
            sys.exit("ffmpeg found no microphones. Check System Settings > Sound > Input.")
        if device is None:
            idx, name = pick_mac_device(devs)
        else:
            match = [d for d in devs if str(d[0]) == device or device.lower() in d[1].lower()]
            if not match:
                sys.exit(f"no microphone matches {device!r}. List them with: python -m filmwright.core.voice.clone devices")
            idx, name = match[0]
        print(f"Microphone: [{idx}] {name}   (change with --device)")
        return ["-f", "avfoundation", "-i", f":{idx}"]
    if shutil.which("pactl"):
        return ["-f", "pulse", "-i", device or "default"]
    return ["-f", "alsa", "-i", device or "default"]


def clean_into(src: Path, dst: Path) -> float:
    """Trim silence, normalise, 24 kHz mono; returns the result's length in seconds."""
    tmp = dst.with_name(dst.stem + ".tmp.wav")
    p = run(["ffmpeg", "-y", "-hide_banner", "-i", str(src), "-af", CLEAN, "-ar", "24000", "-ac", "1",
             "-t", str(MAX_SECONDS), str(tmp)])
    if p.returncode:
        sys.exit(f"ffmpeg couldn't read {src.name}:\n{p.stderr[-800:]}")
    tmp.replace(dst)
    return wav_seconds(dst)


def refuse_if_silent(wav: Path) -> None:
    mean, peak = levels(wav)
    if peak < QUIET_DB:
        hint = ("macOS: System Settings > Privacy & Security > Microphone > turn on your terminal app, then run this again."
                if platform.system() == "Darwin" else "Check the input device (devices) and that it isn't muted.")
        sys.exit(f"The recording is silent (loudest moment {peak:.0f} dB), so the microphone isn't reaching it.\n{hint}")
    if mean < -45:
        print(f"note: the sample is quiet (average {mean:.0f} dB). Sit closer to the mic if the clone sounds thin.")


def confirm_consent(speaker: str, flag: bool) -> None:
    """The speaker (or the person running this with the speaker's permission) must agree to the statement."""
    statement = STATEMENT.format(speaker=speaker)
    print(f"\nConsent statement:\n  {statement}\n")
    if flag:
        print("Confirmed with --i-have-consent.")
        return
    if not sys.stdin.isatty():
        sys.exit("Consent is required. Re-run with --i-have-consent after the speaker has agreed to the statement above.")
    answer = input('Type "I agree" if the speaker agrees: ').strip().lower()
    if answer != "i agree":
        sys.exit("No consent, so no sample was kept.")


def finish(voice_dir: Path, sample: Path, speaker: str, source: str, transcript: str | None,
           expected: str | None) -> None:
    secs = wav_seconds(sample)
    if secs < MIN_SECONDS:
        sample.unlink(missing_ok=True)
        sys.exit(f"Only {secs:.1f}s of speech after trimming silence; the clone needs at least {MIN_SECONDS:.0f}s.")
    if secs >= MAX_SECONDS - 0.05:
        print(f"note: cut to the first {MAX_SECONDS:.0f}s. The transcript below matches the cut clip.")
        transcript = None
    if not transcript:
        print("Transcribing with Whisper (the first run downloads about 1.6 GB) ...")
        transcript = Transcriber("en")(sample)
    sample.with_suffix(".txt").write_text(transcript + "\n")
    rec = write_consent(sample, speaker, source)
    print(f"\nSaved {sample} ({secs:.1f}s), {sample.with_suffix('.txt').name} and {rec.name}:\n  \"{transcript}\"")
    if expected:
        score = match_score(expected, transcript)
        if score < 0.6:
            print(f"note: that differs a lot from the passage (match {score:.0%}). That's fine if it was said "
                  "differently; if Whisper misheard, fix sample.txt by hand. It has to match what was said.")
    print("\nNext: hear the clone with  python -m filmwright.core.voice.clone preview --play")


def backup(sample: Path) -> None:
    for p in (sample, sample.with_suffix(".txt"), record_path(sample)):
        if p.exists():
            p.replace(p.with_name(p.name.replace("sample", "sample.prev", 1)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m filmwright.core.voice.clone", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voice-dir", type=Path, default=None, help="default: ./voice or $FILMWRIGHT_VOICE_DIR")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("passage", help="write and show the text to read aloud")
    ps.add_argument("--terms", default="", help="comma-separated product or feature names to include")
    sub.add_parser("devices", help="list microphones")
    rc = sub.add_parser("record", help="record the speaker reading the passage")
    rc.add_argument("--speaker", required=True, help="the full name of the person whose voice this is")
    rc.add_argument("--device", help="index or part of the name (see: devices)")
    rc.add_argument("--seconds", type=float, help="default: long enough for the passage")
    rc.add_argument("--i-have-consent", action="store_true", help="the speaker agreed to the consent statement")
    pr = sub.add_parser("prepare", help="use an existing recording (any audio or video file)")
    pr.add_argument("--input", type=Path, required=True)
    pr.add_argument("--speaker", required=True, help="the full name of the person whose voice this is")
    pr.add_argument("--text", help="exact words spoken; default: Whisper transcribes it")
    pr.add_argument("--i-have-consent", action="store_true", help="the speaker agreed to the consent statement")
    co = sub.add_parser("consent", help="record consent for the current sample")
    co.add_argument("--speaker", required=True)
    co.add_argument("--sample", type=Path, help="default: <voice-dir>/sample.wav")
    co.add_argument("--source", default="provided by the speaker")
    co.add_argument("--i-have-consent", action="store_true")
    sub.add_parser("check", help="length, level, transcript and consent of the current sample")
    pv = sub.add_parser("preview", help="hear the cloned voice")
    pv.add_argument("--text", default="Here's a quick preview of the narration voice. If it sounds right, "
                                      "we'll use it for the whole film.")
    pv.add_argument("--play", action="store_true")
    sub.add_parser("forget", help="delete the sample, its transcript and consent record, and previews")
    args = ap.parse_args(argv)
    voice_dir = (args.voice_dir or default_voice_dir()).expanduser()
    sample, passage_file = voice_dir / "sample.wav", voice_dir / "passage.txt"

    if args.cmd == "passage":
        voice_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        terms = [t.strip() for t in args.terms.split(",") if t.strip()]
        text = make_passage(terms)
        passage_file.write_text(text + "\n")
        print(f"{text}\n\n({len(text.split())} words, about {len(text.split()) / 2.6:.0f}s to read) -> {passage_file}")
        return 0

    if args.cmd == "forget":
        if voice_dir.exists():
            for p in voice_dir.iterdir():
                if p.name.startswith(("sample", "preview", "passage")) and p.suffix in (".wav", ".txt", ".json"):
                    p.unlink()
        print(f"Deleted the voice sample, transcript and consent record in {voice_dir}. "
              "Cached narration lives in each project's .tts-cache folder; delete it too to remove every trace.")
        return 0

    if args.cmd == "consent":
        target = (args.sample or sample).expanduser()
        if not target.is_file():
            sys.exit(f"no sample at {target}")
        confirm_consent(args.speaker, args.i_have_consent)
        print(f"Wrote {write_consent(target, args.speaker, args.source)}")
        return 0

    need_ffmpeg()
    if args.cmd == "devices":
        if platform.system() == "Darwin":
            devs = mac_audio_devices()
            default = pick_mac_device(devs) if devs else None
            for i, name in devs:
                print(f"[{i}] {name}{'   <- default' if default and default[0] == i else ''}")
        else:
            print(run(["pactl", "list", "short", "sources"]).stdout if shutil.which("pactl") else "ALSA: default")
        return 0

    if args.cmd == "check":
        if not sample.exists():
            sys.exit(f"no sample yet at {sample}")
        mean, peak = levels(sample)
        txt = sample.with_suffix(".txt")
        print(f"{sample}: {wav_seconds(sample):.1f}s, average {mean:.0f} dB, peak {peak:.0f} dB")
        print(f"transcript: {txt.read_text().strip() if txt.exists() else 'MISSING (run prepare)'}")
        try:
            rec = verify_consent(sample)
            print(f"consent: {rec['speaker']}, {rec['created']} ({rec['source']})")
        except ConsentError as e:
            print(f"consent: NOT VALID. {e}")
            return 1
        return 0

    if args.cmd == "preview":
        from . import make_voice
        from .__main__ import play
        try:
            voice = make_voice({"type": "clone", "sample": str(sample)}, root=Path.cwd(), cache=None)
        except (ConsentError, VoiceUnavailable, ValueError) as e:
            sys.exit(str(e))
        out = voice_dir / "preview-clone.wav"
        secs = voice.say(args.text, out)
        voice.close()
        print(f"{out} ({secs:.1f}s)")
        if args.play:
            play(out)
        return 0

    try:
        require_mlx()          # the sample is only useful to the neural clone, and Whisper transcribes it
    except VoiceUnavailable as e:
        sys.exit(str(e))
    voice_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    if args.cmd == "prepare":
        src = args.input.expanduser()
        if not src.exists():
            sys.exit(f"{src} not found")
        confirm_consent(args.speaker, args.i_have_consent)
        refuse_if_silent(src)        # before normalising, which would lift a noise floor
        backup(sample)
        clean_into(src, sample)
        finish(voice_dir, sample, args.speaker, f"prepared from {src.name}", args.text, None)
        return 0

    # record
    confirm_consent(args.speaker, args.i_have_consent)
    passage = passage_file.read_text().strip() if passage_file.exists() else make_passage([])
    seconds = args.seconds or round(len(passage.split()) / 2.3 + 5)
    src_args = input_args(args.device)
    print("\nRead this aloud at your normal narration pace, in a quiet room:\n")
    print("  " + "\n  ".join(re.findall(r".{1,78}(?:\s|$)", passage)))
    print(f"\nRecording for {seconds:.0f}s. Small slips are fine; Ctrl-C stops early.")
    for n in (3, 2, 1):
        print(f"  starting in {n}...", flush=True)
        time.sleep(1)
    print("* Recording: read now", flush=True)
    raw = voice_dir / "raw.tmp.wav"
    proc = subprocess.Popen(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *src_args, "-t", f"{seconds}",
                             "-ac", "1", "-ar", "48000", str(raw)], stdin=subprocess.DEVNULL)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.wait()
    print("Stopped")
    if not raw.exists() or raw.stat().st_size < 1000:
        sys.exit("Nothing was recorded. On macOS, allow microphone access for your terminal app "
                 "(System Settings > Privacy & Security > Microphone), then run this again.")
    try:
        refuse_if_silent(raw)
        backup(sample)
        clean_into(raw, sample)
    finally:
        raw.unlink(missing_ok=True)
    finish(voice_dir, sample, args.speaker, "recorded on this machine's microphone by the speaker", None, passage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
