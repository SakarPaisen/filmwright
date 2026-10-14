# Installing

filmwright runs on macOS (Apple Silicon or Intel) and Linux (x86_64 and ARM; WSL works). The neural voices
need an Apple Silicon Mac; everywhere else, narration uses the system voice (espeak-ng).

## 1. The package

```bash
python3 -m venv .venv && source .venv/bin/activate      # Python 3.11 or newer
pip install filmwright                                     # or, from a clone: pip install -e '.[dev]'
```

## 2. System dependencies

```bash
filmwright setup --check      # what's there, what's missing; changes nothing
filmwright setup              # installs what doesn't need an admin password
```

(`filmwright setup` runs `src/filmwright/tools/setup.sh` with your current Python. You can also run the script
directly: `PYTHON=$(which python) bash src/filmwright/tools/setup.sh --check`.)

It installs, without asking for a password:

| dependency | used for | where |
|---|---|---|
| ffmpeg | recording, mixing, encoding | Homebrew / apt |
| espeak-ng | the system voice | Homebrew / apt |
| Python packages (Playwright, Pillow, PyYAML, NumPy) | everything | your current Python environment |
| Chromium (the open-source project build) | recording demos, rendering animation | `~/.cache/filmwright/chromium` |
| Rhubarb Lip Sync | the talking head's mouth shapes | `~/.cache/filmwright/rhubarb` |

Things that need your password or an interactive installer (Xcode Command Line Tools, Homebrew itself,
`sudo apt-get`) are printed as commands for you to run; the script never runs them itself, because an unattended
prompt just hangs. Inside a container running as root, apt installs run directly.

Exit codes: `0` all good, `2` you need to run the printed commands, `1` an install failed.

### Chromium

Playwright's own browser download is Google's "Chrome for Testing" build. filmwright installs the Chromium
project's open-source snapshot instead (or Debian's `chromium` package on Linux ARM). Where neither exists, it
falls back to Chrome for Testing and reports `FALLBACK`. Use `FILMWRIGHT_CHROMIUM=/path/to/chromium` to point at
a browser you already have, or `FILMWRIGHT_CHROMIUM_REVISION=latest` for the newest snapshot.

## 3. Optional: neural voices (Apple Silicon)

```bash
filmwright setup --voice preset       # built-in speakers: 4.2 GB model + 1.6 GB read-back model
filmwright setup --voice described    # voices described in words: 8.4 GB + 1.6 GB
filmwright setup --voice clone        # consented voice clones: 4.2 GB + 1.6 GB
filmwright setup --voice all
filmwright setup --check --voice all  # what's already downloaded
```

This installs `mlx-audio` into your current Python environment (the same as `pip install 'filmwright[voice-mlx]'`)
and downloads the models into the Hugging Face cache (`~/.cache/huggingface`), once.

## Where things live

| what | default | override |
|---|---|---|
| Chromium, Rhubarb, designed voices | `~/.cache/filmwright` | `FILMWRIGHT_CACHE` (or `XDG_CACHE_HOME`) |
| voice models | `~/.cache/huggingface` | `HF_HOME` |
| a cloned-voice sample and its consent record | `./voice/` in your project | `FILMWRIGHT_VOICE_DIR` |
| generated narration | `<project>/.tts-cache/` | |

Nothing filmwright installs is uploaded anywhere, and nothing it runs sends your text, recordings or films off
your machine.
