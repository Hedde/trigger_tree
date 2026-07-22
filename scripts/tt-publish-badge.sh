#!/usr/bin/env bash
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
REMOTE=$(git -C "$ROOT" remote get-url origin)
BADGE_DIR=$(mktemp -d)
trap 'rm -rf "$BADGE_DIR"' EXIT

python3 "$ROOT/scripts/tt-stats.py" --badge >/dev/null

if ! git clone --quiet --single-branch --branch badges "$REMOTE" "$BADGE_DIR"; then
  echo "badge-publish: create and push a badges branch first" >&2
  exit 1
fi

cp "$ROOT/.trigger-tree/badge.json" "$BADGE_DIR/docs-health.json"
if [[ -z $(git -C "$BADGE_DIR" status --porcelain -- docs-health.json) ]]; then
  echo "docs-health badge is already current"
  exit 0
fi

git -C "$BADGE_DIR" add docs-health.json
git -C "$BADGE_DIR" -c user.name="trigger-tree" -c user.email="trigger-tree@users.noreply.github.com" \
  commit -m "chore: publish local docs health"
git -C "$BADGE_DIR" push origin badges
echo "published locally measured docs health to the badges branch"
