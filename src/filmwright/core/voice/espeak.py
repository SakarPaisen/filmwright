"""The `system` voice: espeak-ng. Robotic, but open source and available on every platform, so a film can
always be built. It is also the automatic fallback when the neural voices can't run on this machine."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from .qwen import sentences


class EspeakVoice:
    kind = "system"

    def __init__(self, voice: str = "en-us", rate: int = 165, pitch: int | None = None, log=print):
        if not shutil.which("espeak-ng"):
            raise RuntimeError("espeak-ng not found. Install it with: filmwright setup  (or brew/apt install espeak-ng)")
        self.voice, self.rate, self.pitch, self.log = voice, int(rate), pitch, log
        self.report: list[tuple[str, float]] = []

    @property
    def name(self) -> str:
        return f"system voice ({self.voice})"

    def say(self, text: str, out_wav: Path) -> float:
        """Speak `text` into a 24 kHz mono WAV; returns its length in seconds."""
        out_wav = Path(out_wav)
        spoken = " ".join(sentences(text)) or text
        with tempfile.TemporaryDirectory(prefix="filmwright-espeak-") as tmp:
            raw = Path(tmp) / "raw.wav"
            cmd = ["espeak-ng", "-v", self.voice, "-s", str(self.rate), "-w", str(raw)]
            if self.pitch is not None:
                cmd += ["-p", str(self.pitch)]
            subprocess.run(cmd + [spoken], check=True, capture_output=True)
            if shutil.which("ffmpeg"):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-ar", "24000", "-ac", "1",
                                str(out_wav)], check=True)
            else:
                shutil.copyfile(raw, out_wav)
        with wave.open(str(out_wav)) as w:
            return w.getnframes() / w.getframerate()

    synth = say

    def close(self) -> None:
        pass
