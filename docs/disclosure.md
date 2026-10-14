# Disclosure

filmwright narrates films with synthetic voices, and can clone a real person's voice with their consent. Viewers
should be able to find that out. `reel.yaml` decides how:

```yaml
disclosure: metadata    # none | metadata | end-card
```

| mode | what it does |
|---|---|
| `metadata` (default) | writes one plain sentence into the file's `comment` and `description` tags. Picture and sound are untouched (the streams are copied, not re-encoded). |
| `end-card` | appends a 2-second card with the same sentence to the end of the film, and writes the tags too. |
| `none` | adds nothing. |

The sentence depends on the voice:

- preset, described or system voice: "Narration uses a synthetic voice."
- cloned voice: "Narration uses a cloned voice, used with the speaker's consent."

Choose what fits where the film will be shown. Rules about synthetic and altered media are spreading: for example,
the EU AI Act has transparency obligations for synthetic audio and video, and several video platforms ask
uploaders to label realistic synthetic content. filmwright doesn't give legal advice; check what applies to you.
Whatever you choose, cloning a voice always needs that person's consent (see [voice.md](voice.md)).

From Python or the command line:

```python
from filmwright.core.disclosure import apply
apply("film.mp4", mode="metadata", voice_type="preset")
```

```bash
python -m filmwright.core.disclosure film.mp4 --mode end-card --voice clone
```

## The film text check

Separately, `checks.tool_names` can flag film text (narration, cards, captions, post copy) that names production
tools ("narrated by ...", engine or model names). Some people prefer films that talk about the product rather than
the tooling. It's a style lint, off by default in the library and `warn` in new projects; it never blocks the
disclosure above, which is added after the check runs.

```yaml
checks:
  tool_names: warn      # off | warn | block
```

The same check always reports leftover placeholders (TODO, TBD, lorem ipsum, `{{name}}`, `[insert ...]`).
