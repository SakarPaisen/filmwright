"""Open a visible browser so a PERSON can sign in, then save the session.

    python -m filmwright.demo.login --base-url https://<env> --run-dir runs/<slug> \
        [--ready-js "!!localStorage.getItem('auth_token')"] [--timeout 600]

The script never touches credentials. It polls `--ready-js` (a JS expression evaluated in the page) until
it is truthy, then writes <run-dir>/auth.json (Playwright storage state: cookies + localStorage). That
file holds a live session token — it stays in the run directory (chmod 600) and must never be committed
or printed. Re-run this when the session expires.

If sign-in lands in a browser window Playwright doesn't control, use --import-local-storage (see
import_local_storage below). A Workspace Google account can cause this by making Chrome switch to a
separate work profile.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from filmwright.demo.guard import check_url  # noqa: E402
from filmwright.demo.recorder import launch_kwargs  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--ready-js", default="document.cookie.length > 0 || localStorage.length > 0",
                    help="JS expression that is truthy once signed in")
    ap.add_argument("--start-path", default="/", help="page to open first")
    ap.add_argument("--timeout", type=int, default=600, help="seconds to wait for the sign-in")
    ap.add_argument("--allow-host", action="append", default=[],
                    help="extra hostname to allow (default: localhost, *.localhost, *.test, playground/dev hosts)")
    ap.add_argument("--import-local-storage", action="store_true",
                    help="read the signed-in tab's localStorage as JSON from stdin instead of opening a browser")
    args = ap.parse_args()

    check_url(args.base_url, args.allow_host)
    run_dir = Path(os.path.expanduser(args.run_dir))
    run_dir.mkdir(parents=True, exist_ok=True)
    out = run_dir / "auth.json"

    if args.import_local_storage:
        return import_local_storage(args.base_url, out)

    # A persistent profile, not launch() + new_context(): tabs and windows the person opens themselves
    # (Cmd+T, Cmd+N, an SSO popup) then belong to the context we watch, instead of a hidden default one.
    # The profile holds whatever the person signed in to (Google cookies included), so it is deleted on
    # every exit: normal, timeout, Ctrl-C or SIGTERM.
    profile = Path(tempfile.mkdtemp(prefix="filmwright-login-"))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    before = out.stat().st_mtime if out.exists() else 0.0
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(profile), **launch_kwargs(headless=False, viewport={"width": 1440, "height": 900},
                                              service_workers="block"))
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(args.base_url.rstrip("/") + args.start_path)
            print(f"A browser window is open at {args.base_url}. Please sign in there; "
                  f"waiting up to {args.timeout // 60} min…", flush=True)
            deadline, last_note = time.time() + args.timeout, time.time()
            base = args.base_url.rstrip("/")
            while time.time() < deadline:
                # Every tab, not just the first: SSO can finish in a new tab or popup.
                signed_in = False
                for pg in list(context.pages):
                    try:
                        if pg.url.startswith(base) and pg.evaluate(f"() => Boolean({args.ready_js})"):
                            signed_in = True
                            break
                    except Exception:
                        pass  # mid-navigation (SSO redirects); try again
                if signed_in:
                    break
                if out.exists() and out.stat().st_mtime > before:
                    # Saved by --import-local-storage from a tab this window can't see: nothing left to do.
                    print(f"Session imported into {out}; closing the sign-in window.")
                    context.close()
                    return 0
                if time.time() - last_note > 60:
                    where = ", ".join(sorted({urlparse(pg.url).netloc or pg.url for pg in context.pages})) or "no tabs"
                    print(f"  still waiting — this window's tabs are on: {where}", flush=True)
                    last_note = time.time()
                time.sleep(1.5)
            else:
                print("Timed out waiting for sign-in; nothing saved.", file=sys.stderr)
                context.close()
                return 1
            time.sleep(1.5)  # let the app finish writing its session
            context.storage_state(path=str(out))
            os.chmod(out, 0o600)
            context.close()
    finally:
        shutil.rmtree(profile, ignore_errors=True)
    print(f"Signed in. Session saved to {out} (do not commit or share it).")
    return 0


def import_local_storage(base_url: str, out: Path) -> int:
    """Fallback when SSO moves the sign-in out of the automated browser.

    For example, a Google Workspace account can make Chrome open a separate work profile, and
    Playwright can't see that profile. In the signed-in tab's DevTools console, run
    `copy(JSON.stringify(localStorage))`, then
    `pbpaste | python -m filmwright.demo.login --import-local-storage --base-url … --run-dir …`.
    Values are written to auth.json only; nothing is printed.
    """
    try:
        data = json.loads(sys.stdin.read())
    except ValueError:
        print("stdin isn't JSON. In the signed-in tab's console run: copy(JSON.stringify(localStorage))",
              file=sys.stderr)
        return 1
    if not isinstance(data, dict) or not data:
        print("that JSON has no localStorage keys; copy it from a tab where you're signed in", file=sys.stderr)
        return 1
    p = urlparse(base_url)
    origin = f"{p.scheme}://{p.netloc}"
    state = {"cookies": [], "origins": [{"origin": origin, "localStorage": [
        {"name": str(k), "value": v if isinstance(v, str) else json.dumps(v)} for k, v in data.items()]}]}
    out.write_text(json.dumps(state))
    os.chmod(out, 0o600)
    print(f"Imported {len(data)} localStorage keys for {origin} into {out} (do not commit or share it).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
