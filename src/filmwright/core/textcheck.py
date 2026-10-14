"""An optional lint for the text a viewer sees or hears: narration, cards, labels, captions, post copy.

It flags two things:
- **tool-name**: wording that names how the film was produced (tool, engine or model names, "narrated by ...",
  "recorded automatically"). Some people prefer films that are about the product, not the tooling. This is a
  style choice, never a requirement: the check is off unless the project turns it on, and it doesn't touch
  the disclosure feature (see disclosure.py), whose text is added after this check runs.
- **placeholder**: leftovers such as TODO, TBD, lorem ipsum, {{name}} or [insert ...].

Finished media files (.mp4, .m4a, .mov) given explicitly are checked for encoder tags.

    python -m filmwright.core.textcheck --mode warn video.yaml captions.srt
    python -m filmwright.core.textcheck --mode block film.mp4

reel.yaml: `checks: {tool_names: off | warn | block}`. Placeholders are always reported when the check runs.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

MODES = ("off", "warn", "block")

TOOL_WORDING = re.compile(
    r"(cloned?\s+voice|voice\s+clon\w*|synthes[iz]\w*\s+(voice|narrat|speech)|text[- ]to[- ]speech|\btts\b|\bqwen\w*"
    r"|playwright|ffmpeg|chromium|\bwhisper\b|rhubarb|espeak|filmwright|narrated\s+(by|in|using|with)|voiced\s+(by|using|with)"
    r"|(recorded|filmed|produced|created|made|built|edited)\s+(automatically|with|using|by)\s+(an?\s+)?(ai|bot|script|tool|software|automation|model)"
    r"|(made|created|generated|produced)\s+with\s+(an?\s+)?(ai\b|model|language\s+model)"
    r"|ai[- ]generated|ai[- ](voice|narrat\w*|presenter|host)|generated\s+(by|with|using)\s+(an?\s+)?(ai\b|model|language\s+model)"
    r"|virtual\s+(narrator|presenter|host)|automated\s+(recording|walkthrough|test\s+run)|screen[- ]?record\w*\s+(tool|bot))",
    re.I,
)
PLACEHOLDER = re.compile(r"(\bTODO\b|\bTBD\b|\bFIXME\b|\bXXX\b|lorem\s+ipsum|\{\{[^}]*\}\}|\[\s*insert[^\]]*\]|<\s*placeholder\s*>|\bPLACEHOLDER\b)",
                         re.I)
# Keys that configure the pipeline rather than appear in the film.
INTERNAL_KEYS = {"tts", "voice", "checks", "disclosure", "music", "outputs", "talking_head", "presenter",
                 "recording", "brand", "auth", "site"}
MEDIA = {".mp4", ".m4a", ".mov", ".m4v"}
ENCODER_BYTES = re.compile(rb"(x264 - core|Lavf\d|Lavc\d|libx264)", re.I)


@dataclass
class Finding:
    file: str
    where: str
    match: str
    kind: str          # tool-name | placeholder | media-tag | missing

    def __str__(self) -> str:
        return f"{self.file}:{self.where}: {self.kind}: '{self.match}'"


class TextCheckError(RuntimeError):
    def __init__(self, findings: list[Finding]):
        self.findings = findings
        super().__init__("film text check failed:\n" + "\n".join(f"  - {f}" for f in findings))


def _strings(node: Any, path: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if isinstance(node, str):
        out.append((path, node))
    elif isinstance(node, dict):
        for k, v in node.items():
            if str(k) in INTERNAL_KEYS:
                continue
            out += _strings(v, f"{path}.{k}" if path else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += _strings(v, f"{path}[{i}]")
    return out


def scan_text(text: str, file: str = "<text>", where: str = "", tool_names: bool = True) -> list[Finding]:
    found = []
    if tool_names:
        found += [Finding(file, where, m.group(0), "tool-name") for m in TOOL_WORDING.finditer(text)]
    found += [Finding(file, where, m.group(0), "placeholder") for m in PLACEHOLDER.finditer(text)]
    return found


def scan_media(path: Path) -> list[Finding]:
    found = []
    raw = path.read_bytes()
    edge = 256 * 1024                       # container metadata sits at the head and tail of the file
    hit = ENCODER_BYTES.search(raw[:edge] + b"\0" + raw[-edge:])
    if hit:
        found.append(Finding(path.name, "file", hit.group(0).decode(errors="ignore"), "media-tag"))
    tags = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags:stream_tags", "-of", "default=nw=1", str(path)],
                          capture_output=True, text=True).stdout
    for line in tags.splitlines():
        if line.lower().startswith("tag:encoder=") and line.split("=", 1)[1].strip():
            found.append(Finding(path.name, "tags", line.strip(), "media-tag"))
    return found


def scan_file(path: Path, tool_names: bool = True) -> list[Finding]:
    path = Path(path).expanduser()
    if not path.exists():
        return [Finding(str(path), "", "file not found", "missing")]
    if path.suffix.lower() in MEDIA:
        return scan_media(path) if tool_names else []
    if path.suffix.lower() in (".yaml", ".yml", ".json"):
        data = yaml.safe_load(path.read_text()) if path.suffix != ".json" else __import__("json").loads(path.read_text())
        items = _strings(data)
        for _, v in list(items):                       # scenes referenced by file are on screen too
            if isinstance(v, str) and v.endswith(".html") and (path.parent / v).is_file():
                items.append((v, (path.parent / v).read_text()))
    else:
        items = [("", path.read_text(errors="ignore"))]
    out: list[Finding] = []
    for where, s in items:
        out += scan_text(s, path.name, where, tool_names)
    return out


def check(paths: list[Path | str], mode: str = "warn", log: Any = print) -> list[Finding]:
    """Scan `paths`. off: does nothing. warn: prints findings. block: raises TextCheckError if anything is found.
    Placeholders are reported in warn and block modes; tool-name wording is the part `mode` controls."""
    if mode not in MODES:
        raise ValueError(f"checks mode must be one of {', '.join(MODES)} (got {mode!r})")
    if mode == "off":
        return []
    findings: list[Finding] = []
    for p in paths:
        findings += scan_file(Path(p))
    if findings:
        if mode == "block":
            raise TextCheckError(findings)
        log("film text check (warn):")
        for f in findings:
            log(f"  - {f}")
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m filmwright.core.textcheck", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=MODES, default="warn")
    ap.add_argument("paths", nargs="+", type=Path)
    a = ap.parse_args(argv)
    try:
        found = check(a.paths, a.mode)
    except TextCheckError as e:
        print(e)
        return 1
    if not found and a.mode != "off":
        print("OK: nothing flagged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
