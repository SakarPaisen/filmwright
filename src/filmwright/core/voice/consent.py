"""Consent records for cloned voices.

A cloned voice may only be used when the person whose voice it is agreed to it. filmwright enforces that in
code, not in configuration: clone mode reads `<sample>.consent.json` next to the sample and refuses to run when
the record is missing, incomplete, or was made for a different recording (the SHA-256 of the sample must match).
There is deliberately no setting that skips this check.

The record holds who the speaker is, the statement they agreed to, when, who created the record on this machine,
where the sample came from, and the sample's hash. It is a local accountability record, not a legal document.
"""

from __future__ import annotations

import getpass
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RECORD_VERSION = 1
STATEMENT = ("I am {speaker}, or I have {speaker}'s explicit permission. I agree that this recording may be used "
             "to generate narration in this voice for the films made in this project, and I can withdraw that "
             "permission at any time by deleting the sample and this record.")
REQUIRED = ("speaker", "statement", "created", "sample_sha256", "created_by", "source", "version")


class ConsentError(PermissionError):
    """Clone mode was asked to use a sample without a valid consent record."""


def record_path(sample: Path) -> Path:
    sample = Path(sample)
    return sample.with_name(sample.stem + ".consent.json")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_consent(sample: Path, speaker: str, source: str) -> Path:
    """Write the consent record for `sample`. Call it only after the speaker agreed to STATEMENT."""
    sample = Path(sample).expanduser()
    speaker = (speaker or "").strip()
    if not speaker:
        raise ConsentError("a consent record needs the speaker's name")
    if not sample.is_file():
        raise ConsentError(f"no sample at {sample}")
    record = {
        "version": RECORD_VERSION,
        "speaker": speaker,
        "statement": STATEMENT.format(speaker=speaker),
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "created_by": getpass.getuser(),
        "source": source,
        "sample": sample.name,
        "sample_sha256": file_sha256(sample),
    }
    out = record_path(sample)
    out.write_text(json.dumps(record, indent=2) + "\n")
    try:
        out.chmod(0o600)
    except OSError:
        pass
    return out


def verify_consent(sample: Path) -> dict[str, Any]:
    """Return the consent record for `sample`, or raise ConsentError explaining what is wrong."""
    sample = Path(sample).expanduser()
    rec_file = record_path(sample)
    how = ("Record consent with: python -m filmwright.core.voice.clone consent "
           f"--sample {sample} --speaker \"<full name>\"")
    if not sample.is_file():
        raise ConsentError(f"no voice sample at {sample}")
    if not rec_file.is_file():
        raise ConsentError(f"no consent record for {sample.name} (expected {rec_file.name}). "
                           f"A cloned voice needs the speaker's consent. {how}")
    try:
        record = json.loads(rec_file.read_text())
    except (OSError, ValueError) as e:
        raise ConsentError(f"{rec_file.name} is unreadable ({e}). {how}") from e
    missing = [k for k in REQUIRED if not record.get(k)]
    if missing:
        raise ConsentError(f"{rec_file.name} is missing {', '.join(missing)}. {how}")
    if record["sample_sha256"] != file_sha256(sample):
        raise ConsentError(f"{sample.name} changed after consent was recorded (its hash no longer matches "
                           f"{rec_file.name}). Record consent again for the new sample. {how}")
    return record
