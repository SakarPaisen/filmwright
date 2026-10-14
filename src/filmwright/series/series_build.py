#!/usr/bin/env python3
"""Build a whole numbered series, unattended, with a live status file.

    python -m filmwright.series.series_build <series-dir> [--episodes 2-19] [--steps record,build,social] [--no-sleep-guard]

<series-dir> holds series.yaml (see docs/series.md) and the episode specs. Per episode, in order:

  record  refresh the signed-in session (brand.auth.mode: chrome-session), VERIFY it is the right account (auth.account_check), then
          run the episode's scenarios. A failed check STOPS the whole run: it never records a logged-out view.
  build   narrate, assemble and effects (zooms, host, scenes, sounds)  -> <slug>.mp4 + .srt
  social  1080p cut with small burned-in captions + the post caption file

then it writes the posting plan. Progress is appended to <series-dir>/STATUS.txt (one line per step, with times).
Exit code 1 means it stopped early (read the last STATUS line); failed episodes are marked and skipped, not fatal.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

from filmwright.paths import PKG
from filmwright.series import brandkit

PY = sys.executable
CHROME_IMPORT = PKG / "demo" / "import_chrome_session.sh"


def load_series(d: Path) -> dict:
    cfg = yaml.safe_load((d / "series.yaml").read_text())
    cfg["_dir"] = d
    name = cfg.get("brand") or "example"
    local = d / str(name)
    cfg["_brand"] = brandkit.load_brand(local if local.exists() else name)
    return cfg


def parse_range(s: str | None, have: list[int]) -> list[int]:
    if not s:
        return have
    out: set[int] = set()
    for part in s.split(","):
        a, _, b = part.partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return [n for n in have if n in out]


class Status:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.write_text("")

    def say(self, msg: str) -> None:
        with self.path.open("a") as f:
            f.write(f"{time.strftime('%H:%M')}  {msg}\n")
        print(msg, flush=True)


def session_check_yaml(brand: dict, dest: Path) -> Path | None:
    """A one-step scenario that proves the saved session is the expected account (auth.account_check in brand.yaml):
    {path: /api/me, field: plan, equals: pro, page: / (optional), wait_text: "..." (optional)}."""
    pc = (brand.get("auth") or {}).get("account_check")
    if not pc:
        return None
    site = brand["site"]
    steps = [{"goto": pc.get("page", "/")}]
    if pc.get("wait_text"):
        steps.append({"wait_for": {"text": pc["wait_text"]}})
    steps.append({"api": {"path": pc["path"], "expect": [{"path": pc["field"], "equals": pc["equals"]}]}})
    cfg = {"name": "session check", "base_url": site["base_url"], "allow_hosts": site["allow_hosts"],
           "auth": {"storage_state": "auth.json", "token_js": brand["auth"].get("token_js", "")},
           "viewport": {"width": 1440, "height": 810}, "recording": {"resolution": "720p"},
           "scenarios": [{"id": "C01", "title": "session check", "steps": steps}]}
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "check.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return dest / "check.yaml"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("series_dir", type=Path)
    ap.add_argument("--episodes", help="e.g. 2-19 or 3,5,7 (default: all)")
    ap.add_argument("--steps", default="record,build,social")
    a = ap.parse_args()
    d = a.series_dir.expanduser().resolve()
    cfg = load_series(d)
    brand = cfg["_brand"]
    steps = set(a.steps.split(","))
    specs = {int(yaml.safe_load(p.read_text())["episode"]): p for p in sorted((d / cfg.get("specs", "specs")).glob("ep*.yaml"))}
    eps = parse_range(a.episodes, sorted(specs))
    st = Status(d / "STATUS.txt")
    mk = [PY, "-m", "filmwright.series.mkepisode"]
    auth = brand.get("auth") or {}
    master = d / ".session"                       # the one place the live session is kept
    chk_dir = d / ".session-check"
    failures = 0
    for n in eps:
        spec_path = specs[n]
        spec = yaml.safe_load(spec_path.read_text())
        ep_dir = Path(str(spec["dir"])).expanduser()
        tag = f"ep{n:02d}"
        subprocess.run(mk + ["gen", str(spec_path)], capture_output=True)
        if "record" in steps:
            if auth.get("mode") == "chrome-session":
                st.say(f"{tag}  refreshing session")
                master.mkdir(parents=True, exist_ok=True)
                env = {**os.environ, "PY": PY, "FILMWRIGHT_STRIP_KEYS": ",".join(auth.get("strip_keys") or [])}
                r = subprocess.run(["bash", str(CHROME_IMPORT), auth["chrome_host"], brand["site"]["base_url"], str(master),
                                    auth.get("token_key", "auth_token")], capture_output=True, text=True, env=env)
                if r.returncode:
                    st.say(f"STOPPED before {tag}: SESSION PROBLEM: {(r.stderr.strip().splitlines() or ['?'])[-1][:140]}")
                    return 1
                ep_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy(master / "auth.json", ep_dir / "auth.json")
                (ep_dir / "auth.json").chmod(0o600)
                chk = session_check_yaml(brand, chk_dir)
                if chk:
                    shutil.copy(master / "auth.json", chk_dir / "auth.json")
                    (chk_dir / "auth.json").chmod(0o600)
                    if subprocess.run([PY, "-m", "filmwright.demo.run_scenarios", str(chk)], cwd=chk_dir, capture_output=True).returncode:
                        st.say(f"STOPPED before {tag}: the session is not the expected account (check failed). Sign in again.")
                        return 1
            st.say(f"{tag}  recording")
            r = subprocess.run(mk + ["record", str(spec_path)], capture_output=True, text=True)
            if r.returncode or "FAIL" in r.stdout:
                bad = next((ln for ln in r.stdout.splitlines() if "FAIL" in ln), "failed")
                st.say(f"{tag}  RECORD FAILED: {bad[:140]}")
                failures += 1
                continue
        if "build" in steps:
            st.say(f"{tag}  building")
            r = subprocess.run(mk + ["build", str(spec_path)], capture_output=True, text=True)
            zooms = sum(int(m) for m in re.findall(r"camera: (\d+) zoom", r.stdout))
            if "chapters)" not in r.stdout:
                (d / f".build-{tag}.log").write_text(r.stdout + r.stderr)
                st.say(f"{tag}  BUILD FAILED (log: .build-{tag}.log)")
                failures += 1
                continue
        else:
            zooms = 0
        if "social" in steps:
            r = subprocess.run(mk + ["social", str(spec_path)], capture_output=True, text=True)
            if r.returncode:
                st.say(f"{tag}  SOCIAL CUT FAILED")
                failures += 1
                continue
        st.say(f"{tag}  DONE" + (f"  (zooms: {zooms})" if "build" in steps else ""))
    subprocess.run([PY, "-m", "filmwright.series.series_plan", str(d)], capture_output=True)
    st.say("posting plan written")
    st.say(f"ALL FINISHED ({failures} failed)")
    return 0


if __name__ == "__main__":
    caff = shutil.which("caffeinate")
    if caff and "--no-sleep-guard" not in sys.argv and not os.environ.get("FILMWRIGHT_CAFFEINATED"):
        os.environ["FILMWRIGHT_CAFFEINATED"] = "1"
        os.execvp(caff, [caff, "-i", PY, "-m", "filmwright.series.series_build"] + sys.argv[1:])   # keep the Mac awake for the whole run
    sys.argv = [x for x in sys.argv if x != "--no-sleep-guard"]
    raise SystemExit(main())
