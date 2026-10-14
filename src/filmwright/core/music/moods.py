"""The moods a score can take. Each mood is a preset of tempo, key, scale, chord progressions, arrangement and
mix. Add a mood by adding an entry to MOODS; the composer needs nothing else.

Chords are Roman numerals relative to the key: upper case is major, lower case minor, a trailing "o" diminished,
a leading "b" or "#" shifts the root by a semitone (so in a minor key "bVI" is the major chord on the flat sixth).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .synth import NOTE

DEGREE = {"I": 0, "II": 2, "III": 4, "IV": 5, "V": 7, "VI": 9, "VII": 11}


@dataclass(frozen=True)
class Mood:
    name: str
    description: str
    bpm: float
    key: str                                   # tonic, e.g. "C", "Eb", "F#"
    scale: str                                 # major | minor (sets the tonic chord of the ending)
    progressions: tuple[tuple[str, ...], ...]  # four chords per bar group; sections rotate through these
    drums: str                                 # none | light | four | bounce | halftime | tick
    bass: str                                  # none | sustain | pulse | pump | bounce | ostinato
    lead: str                                  # none | pluck | piano | bell | marimba | ping
    lead_rate: int                             # lead notes per beat (1, 2 or 4)
    pad: float                                 # pad level, 0 = none
    pad_timbre: str = "sine"                   # sine | strings | drone
    stabs: str = "none"                        # none | offbeat | brass
    brightness: float = 9000.0                 # low-pass cutoff of the mix, Hz
    reverb: float = 0.15                       # 0..1
    risers: str = "riser"                      # none | riser | swell: what builds into each cut
    impacts: float = 0.0                       # impact level on each cut, 0 = none
    swing: float = 0.0                         # 0..0.3: delays every second lead/hat subdivision
    lead_octave: int = 5
    lead_level: float = 0.07


MOODS: dict[str, Mood] = {m.name: m for m in (
    Mood("upbeat", "bright four-on-the-floor groove with plucks, stabs, risers and impacts",
         bpm=120, key="C", scale="major",
         progressions=(("I", "V", "vi", "IV"), ("vi", "IV", "I", "V"), ("IV", "V", "iii", "vi"),
                       ("I", "vi", "IV", "V"), ("ii", "V", "I", "vi"), ("IV", "I", "V", "vi")),
         drums="four", bass="pump", lead="pluck", lead_rate=4, pad=0.0, stabs="offbeat",
         brightness=11000, reverb=0.12, risers="riser", impacts=0.8),
    Mood("calm", "slow, soft pads and bells, no drums", bpm=76, key="A", scale="minor",
         progressions=(("i", "bVI", "bIII", "bVII"), ("bVI", "bIII", "bVII", "i")),
         drums="none", bass="sustain", lead="bell", lead_rate=1, pad=0.022, pad_timbre="sine",
         brightness=3600, reverb=0.4, risers="none", impacts=0.0, lead_octave=5, lead_level=0.05),
    Mood("corporate", "clean, steady and optimistic: light drums, piano eighths", bpm=110, key="D", scale="major",
         progressions=(("I", "vi", "IV", "V"), ("I", "V", "vi", "IV"), ("IV", "I", "V", "V")),
         drums="light", bass="pulse", lead="piano", lead_rate=2, pad=0.012, pad_timbre="sine",
         brightness=7500, reverb=0.2, risers="swell", impacts=0.0, lead_level=0.08),
    Mood("inspiring", "warm build: piano, strings, gentle drums, soft impacts", bpm=96, key="G", scale="major",
         progressions=(("IV", "I", "V", "vi"), ("I", "V", "vi", "IV"), ("vi", "IV", "I", "V")),
         drums="light", bass="sustain", lead="piano", lead_rate=2, pad=0.006, pad_timbre="strings",
         brightness=8500, reverb=0.3, risers="swell", impacts=0.45, lead_level=0.085),
    Mood("playful", "bouncy, light and swung: marimba, shaker, staccato bass", bpm=126, key="F", scale="major",
         progressions=(("I", "vi", "ii", "V"), ("I", "IV", "I", "V"), ("IV", "V", "iii", "vi")),
         drums="bounce", bass="bounce", lead="marimba", lead_rate=4, pad=0.0,
         brightness=11000, reverb=0.12, risers="none", impacts=0.0, swing=0.14, lead_octave=5, lead_level=0.11),
    Mood("epic", "big half-time drums, low strings, brass stabs, risers and heavy impacts", bpm=84, key="D", scale="minor",
         progressions=(("i", "bVI", "bIII", "bVII"), ("i", "bVII", "bVI", "bVII"), ("bVI", "bVII", "i", "i")),
         drums="halftime", bass="sustain", lead="none", lead_rate=1, pad=0.007, pad_timbre="strings", stabs="brass",
         brightness=7000, reverb=0.35, risers="riser", impacts=1.0),
    Mood("sad", "slow minor piano over soft strings, no drums", bpm=66, key="A", scale="minor",
         progressions=(("i", "bVI", "iv", "v"), ("i", "iv", "bVII", "bIII"), ("bVI", "iv", "i", "v")),
         drums="none", bass="sustain", lead="piano", lead_rate=2, pad=0.005, pad_timbre="strings",
         brightness=3000, reverb=0.45, risers="none", impacts=0.0, lead_octave=4, lead_level=0.1),
    Mood("suspense", "dark pulse, ticking hats, drone and glassy pings; tension into every cut", bpm=92, key="C", scale="minor",
         progressions=(("i", "i", "bVI", "V"), ("i", "iv", "bVI", "V")),
         drums="tick", bass="ostinato", lead="ping", lead_rate=1, pad=0.02, pad_timbre="drone",
         brightness=4200, reverb=0.4, risers="riser", impacts=0.7, lead_octave=6, lead_level=0.035),
)}


def get_mood(name: str) -> Mood:
    try:
        return MOODS[name.lower()]
    except KeyError:
        raise ValueError(f"unknown mood {name!r}; choose one of {', '.join(MOODS)}") from None


def parse_chord(numeral: str, key: str) -> tuple[int, tuple[int, ...]]:
    """(root pitch class, intervals) of a Roman-numeral chord in `key`."""
    m = re.fullmatch(r"(b|#)?([ivIV]+)(o|\+)?(7)?", numeral)
    if not m or m.group(2).upper() not in DEGREE:
        raise ValueError(f"can't read chord {numeral!r}")
    acc, roman, quality, seventh = m.groups()
    root = (NOTE[key] + DEGREE[roman.upper()] + (-1 if acc == "b" else 1 if acc == "#" else 0)) % 12
    if quality == "o":
        iv: tuple[int, ...] = (0, 3, 6)
    elif quality == "+":
        iv = (0, 4, 8)
    elif roman.isupper():
        iv = (0, 4, 7)
    else:
        iv = (0, 3, 7)
    if seventh:
        iv = iv + (10,)
    return root, iv
