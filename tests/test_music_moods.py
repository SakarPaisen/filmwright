import pytest

from filmwright.core.music import MOOD_NAMES, MOODS, get_mood
from filmwright.core.music.moods import parse_chord

REQUIRED = {"upbeat", "calm", "corporate", "inspiring", "playful", "epic", "sad", "suspense"}


def test_required_moods_exist():
    assert REQUIRED <= set(MOOD_NAMES)


@pytest.mark.parametrize("name", sorted(MOODS))
def test_every_chord_parses(name):
    m = MOODS[name]
    assert 40 <= m.bpm <= 180
    assert m.scale in ("major", "minor")
    for prog in m.progressions:
        assert len(prog) == 4
        for c in prog:
            root, iv = parse_chord(c, m.key)
            assert 0 <= root < 12 and iv[0] == 0


def test_moods_are_distinct():
    sigs = {(m.bpm, m.key, m.scale, m.drums, m.lead) for m in MOODS.values()}
    assert len(sigs) == len(MOODS)


def test_parse_chord():
    assert parse_chord("I", "C") == (0, (0, 4, 7))
    assert parse_chord("vi", "C") == (9, (0, 3, 7))
    assert parse_chord("bVI", "A") == (5, (0, 4, 7))      # F major in A minor
    assert parse_chord("V7", "G") == (2, (0, 4, 7, 10))
    with pytest.raises(ValueError):
        parse_chord("H", "C")


def test_unknown_mood():
    with pytest.raises(ValueError, match="unknown mood"):
        get_mood("jazzy")
