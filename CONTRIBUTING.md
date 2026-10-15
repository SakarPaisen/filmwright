# Contributing

Thanks for helping. Bug reports, new scene templates, presenter characters, music moods and docs fixes are
all welcome.

## Set up

```bash
git clone https://github.com/dassjaylabs/filmwright && cd filmwright
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
filmwright setup            # ffmpeg, Chromium, espeak-ng, Rhubarb (prints any admin commands for you to run)
filmwright doctor
```

On Apple Silicon add the neural voices with `pip install -e '.[all]'` and `filmwright setup --voice preset`.

## Before you open a pull request

```bash
ruff check src tests
python -m compileall -q src
pytest
```

- Keep changes focused; one feature or fix per pull request.
- Add or update tests for logic changes (config, music, voice gating, export).
- Templates must stay deterministic: a frame at time *t* is identical on every render.
- Use the fictional example brand (Acme) in examples, docs and screenshots. Don't add real company names,
  logos, people or trademarks.
- Everything bundled must be open source with a license compatible with MIT. Add new components to
  `THIRD_PARTY_LICENSES.md`.
- Never commit sessions (`auth.json`), voice samples, consent records or rendered media.

## Voice cloning

Changes to cloning must keep the consent gate: no option, flag or environment variable may skip it.

## Contributor License Agreement

Code, docs and template contributions need a signed [Contributor License Agreement](CLA.md). When you open your
first pull request, a bot asks you to sign it by posting one comment; it takes a minute and covers all your future
pull requests. The CLA lets the maintainer keep using your contribution as the project evolves, including under
other license terms. You keep the copyright in your work. Bug reports and ideas in issues don't need it.

## License

The project is MIT licensed (see [LICENSE](LICENSE)). The filmwright name and logo are not covered by it; see
[TRADEMARKS.md](TRADEMARKS.md).
