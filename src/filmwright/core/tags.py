"""Remove encoder tags from a finished file.

`-fflags +bitexact` and an empty `encoder=` keep most ffmpeg builds from tagging a file, but ffmpeg 6.x still writes a
per-stream "Lavc libx264" tag when it encodes. A stream-copy remux without that tag is cheap and works on every
version, so every delivered file goes through it. Titles, chapters, subtitle languages and the disclosure note are kept.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def strip_encoder_tags(path: Path | str) -> Path:
    p = Path(path)
    if p.suffix.lower() not in (".mp4", ".m4a", ".mov"):
        return p
    tmp = p.with_name(p.stem + ".untagged" + p.suffix)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(p), "-map", "0", "-c", "copy",
                    "-map_metadata", "0", "-map_chapters", "0", "-metadata:s", "encoder=", "-fflags", "+bitexact",
                    "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(p)
    return p
