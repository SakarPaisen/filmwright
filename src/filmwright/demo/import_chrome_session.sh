#!/bin/bash
# Copy the signed-in session of a site from the person's real Chrome into <run-dir>/auth.json, without printing
# or storing the token anywhere else. Needs: macOS, Chrome open with a tab on the site, and
# Chrome > View > Developer > Allow JavaScript from Apple Events turned on. Works across Chrome profiles.
#
#   import_chrome_session.sh <host-substring> <base-url> <run-dir> [token-key]
#   token-key: the localStorage key that holds the app's session token (default auth_token). It is read only to check
#              the token's expiry when it is a JWT; the value is never printed.
#   MIN_MINUTES=8 (default): if the token has less than this left, the Chrome tab is reloaded once so the site
#   issues a fresh token, then it is read again.
#   FILMWRIGHT_STRIP_KEYS='a,b:*'  comma-separated localStorage keys (globs ok) to REMOVE from the saved session (emails, UI state).
#   ALLOW_HOST=<host>              pass the host to the environment guard when it isn't a recognised test host (ask first).
#   PY=<python>                    the interpreter filmwright is installed in (default: python3).
# Exit codes: 0 ok · 2 no tab / Apple Events off · 3 not signed in (no token) · 4 token expired or too short
set -u
[ $# -ge 3 ] || { sed -n '2,16p' "$0"; exit 1; }
HOST="$1"; BASE="$2"; RUN="$3"; MIN="${MIN_MINUTES:-8}"
export FILMWRIGHT_TOKEN_KEY="${4:-${FILMWRIGHT_TOKEN_KEY:-auth_token}}"
PY="${PY:-python3}"
TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT; chmod 600 "$TMP"

read_ls() {
  osascript -e "tell application \"Google Chrome\"
    repeat with w in windows
      repeat with t in tabs of w
        if URL of t contains \"$HOST\" then return execute t javascript \"JSON.stringify(localStorage)\"
      end repeat
    end repeat
    return \"\"
  end tell" 2>/dev/null > "$TMP"
}
reload_tab() {
  osascript -e "tell application \"Google Chrome\"
    repeat with w in windows
      repeat with t in tabs of w
        if URL of t contains \"$HOST\" then
          reload t
          return \"ok\"
        end if
      end repeat
    end repeat
  end tell" >/dev/null 2>&1
}
minutes_left() {   # prints minutes left (negative if expired); exit 3 when not signed in
  python3 - "$TMP" <<'PYEOF'
import sys, json, base64, time
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(2)
import os
t = d.get(os.environ.get("FILMWRIGHT_TOKEN_KEY", "auth_token")) or ""
if not t: sys.exit(3)
try:
    exp = json.loads(base64.urlsafe_b64decode(t.split(".")[1] + "=="))["exp"]
    print(int((exp - time.time()) // 60))
except Exception:
    print(999)       # not a JWT we can read: assume fine
PYEOF
}

read_ls
[ "$(wc -c < "$TMP")" -gt 5 ] || { echo "no $HOST tab found in Chrome, or Apple Events JavaScript is off" >&2; exit 2; }
LEFT="$(minutes_left)"; rc=$?
[ $rc -eq 3 ] && { echo "the Chrome tab is not signed in" >&2; exit 3; }
if [ $rc -ne 0 ] || [ "${LEFT:-0}" -lt "$MIN" ]; then
  echo "token has ${LEFT:-?} min left (< $MIN): reloading the tab for a fresh one" >&2
  reload_tab; sleep 9; read_ls
  LEFT="$(minutes_left)"; rc=$?
  [ $rc -eq 3 ] && { echo "the Chrome tab is not signed in" >&2; exit 3; }
  [ "${LEFT:-0}" -ge 3 ] || { echo "token still short (${LEFT:-?} min): sign in again in Chrome" >&2; exit 4; }
fi
echo "session found; token valid for ${LEFT} more minutes" >&2
python3 - "$TMP" <<'PYEOF'
import sys, json, os, fnmatch
d = json.load(open(sys.argv[1]))
pats = [p for p in os.environ.get("FILMWRIGHT_STRIP_KEYS", "").split(",") if p]
d = {k: v for k, v in d.items() if not any(fnmatch.fnmatch(k, p) for p in pats)}
json.dump(d, open(sys.argv[1], "w"))
PYEOF
EXTRA=(); [ -n "${ALLOW_HOST:-}" ] && EXTRA=(--allow-host "$ALLOW_HOST")
"$PY" -m filmwright.demo.login --import-local-storage --base-url "$BASE" --run-dir "$RUN" ${EXTRA[@]+"${EXTRA[@]}"} < "$TMP"
