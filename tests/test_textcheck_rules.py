import shutil
import subprocess

import pytest

from filmwright.core.textcheck import TextCheckError, check, scan_text


def test_flags_tool_wording_and_placeholders():
    kinds = {f.kind for f in scan_text("Narrated by a bot. Made with AI. TODO: fix {{name}}")}
    assert kinds == {"tool-name", "placeholder"}


def test_product_ai_features_are_not_flagged():
    assert scan_text("Our assistant drafts replies for you and summarises long threads.") == []


def test_modes(tmp_path):
    f = tmp_path / "narration.txt"
    f.write_text("This film was generated with an AI model.")
    assert check([f], "off") == []
    logged = []
    assert check([f], "warn", log=logged.append) and logged
    with pytest.raises(TextCheckError):
        check([f], "block")
    with pytest.raises(ValueError):
        check([f], "strict")


def test_yaml_skips_settings_and_reads_text(tmp_path):
    y = tmp_path / "video.yaml"
    y.write_text("voice: {type: preset, style: text-to-speech friendly}\n"
                 "sections:\n  - label: Quick add\n    narration: Lorem ipsum dolor.\n")
    found = check([y], "warn", log=lambda *_: None)
    assert [f.kind for f in found] == ["placeholder"]
    assert "sections[0].narration" in found[0].where


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_media_encoder_tags(tmp_path):
    tagged, clean = tmp_path / "tagged.mp4", tmp_path / "clean.mp4"
    base = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=0.5", "-c:v", "libx264"]
    subprocess.run(base + [str(tagged)], check=True)
    subprocess.run(base + ["-bsf:v", "filter_units=remove_types=6", "-fflags", "+bitexact", "-flags:v", "+bitexact",
                           "-metadata:s:v:0", "encoder=", str(clean)], check=True)
    from filmwright.core.tags import strip_encoder_tags
    strip_encoder_tags(clean)                     # ffmpeg 6.x still tags at encode time; the remux removes it
    assert any(f.kind == "media-tag" for f in check([tagged], "warn", log=lambda *_: None))
    assert check([clean], "warn", log=lambda *_: None) == []
