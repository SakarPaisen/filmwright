import json
import wave

import pytest

from filmwright.core.voice import ConsentError, make_voice, verify_consent, write_consent
from filmwright.core.voice.consent import record_path
from filmwright.core.voice.qwen import QwenVoice


def _wav(path, seconds=0.5, value=1000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(int(value).to_bytes(2, "little", signed=True) * int(24000 * seconds))
    return path


def test_consent_round_trip(tmp_path):
    sample = _wav(tmp_path / "sample.wav")
    rec = write_consent(sample, "Jordan Example", "recorded by the speaker")
    assert rec == record_path(sample) and rec.name == "sample.consent.json"
    data = verify_consent(sample)
    assert data["speaker"] == "Jordan Example"
    assert "Jordan Example" in data["statement"]
    assert len(data["sample_sha256"]) == 64


def test_missing_record_is_refused(tmp_path):
    sample = _wav(tmp_path / "sample.wav")
    with pytest.raises(ConsentError, match="no consent record"):
        verify_consent(sample)


def test_changed_sample_is_refused(tmp_path):
    sample = _wav(tmp_path / "sample.wav")
    write_consent(sample, "Jordan Example", "test")
    _wav(sample, value=2000)                       # a different recording under the same name
    with pytest.raises(ConsentError, match="changed after consent"):
        verify_consent(sample)


def test_incomplete_record_is_refused(tmp_path):
    sample = _wav(tmp_path / "sample.wav")
    rec = write_consent(sample, "Jordan Example", "test")
    data = json.loads(rec.read_text())
    data["speaker"] = ""
    rec.write_text(json.dumps(data))
    with pytest.raises(ConsentError, match="missing speaker"):
        verify_consent(sample)


def test_consent_needs_a_name(tmp_path):
    sample = _wav(tmp_path / "sample.wav")
    with pytest.raises(ConsentError):
        write_consent(sample, "  ", "test")


def test_clone_voice_refuses_without_consent(tmp_path):
    sample = _wav(tmp_path / "sample.wav")
    (tmp_path / "sample.txt").write_text("hello")
    with pytest.raises(ConsentError):
        make_voice({"type": "clone", "sample": "sample.wav"}, root=tmp_path)
    with pytest.raises(ConsentError):                          # no bypass by constructing the engine directly
        QwenVoice("clone", ref_audio=sample, ref_text="hello")


def test_clone_config_has_no_consent_override(tmp_path):
    sample = _wav(tmp_path / "sample.wav")
    for key in ("consent", "skip_consent", "i_have_consent", "force"):
        with pytest.raises(ConsentError):
            make_voice({"type": "clone", "sample": str(sample), key: True}, root=tmp_path)
