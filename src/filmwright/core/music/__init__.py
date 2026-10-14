"""Original music for films, synthesised on this machine: no samples, no models, nothing to license.

    from filmwright.core.music import score, ambient, MOODS
    score("music.wav", seconds=42.0, cuts=[0, 6.5, 14.0, 23.2, 35.0], mood="upbeat")   # follows the scene changes
    ambient("bed.wav", seconds=180, mood="calm")                                         # a quiet bed, no beat

Moods: upbeat, calm, corporate, inspiring, playful, epic, sad, suspense (see moods.py).
"""

from .ambient import AMBIENT_MOODS, ambient
from .composer import compose, plan, score, snap_cuts
from .moods import MOODS, Mood, get_mood

MOOD_NAMES = tuple(MOODS)

__all__ = ["score", "ambient", "compose", "plan", "snap_cuts", "MOODS", "MOOD_NAMES", "AMBIENT_MOODS", "Mood", "get_mood"]
