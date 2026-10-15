#!/usr/bin/env bash
# Create or update the repository's labels from .github/labels.yml (needs the GitHub CLI, logged in).
# Old labels that were renamed are migrated so existing issues keep them; anything else not in the file is left alone.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO="${REPO:-dassjaylabs/filmwright}"
EXISTING="$(gh label list -R "$REPO" --limit 200 --json name -q '.[].name')"
migrate() {   # old name -> new name, only if the old one still exists and the new one doesn't yet
  if grep -qx "$1" <<<"$EXISTING" && ! grep -qx "$2" <<<"$EXISTING"; then
    gh label edit "$1" -R "$REPO" --name "$2" >/dev/null && echo "renamed: $1 -> $2"
  fi
}
migrate "bug" "type: bug"
migrate "enhancement" "type: feature"
migrate "documentation" "type: docs"
migrate "question" "type: question"
python3 - <<'PY' | while IFS=$'\t' read -r name color desc; do
import yaml
for l in yaml.safe_load(open(".github/labels.yml")):
    print(f"{l['name']}\t{l['color']}\t{l['description']}")
PY
  gh label create "$name" -R "$REPO" --color "$color" --description "$desc" --force >/dev/null && echo "ok: $name"
done
