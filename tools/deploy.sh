#!/usr/bin/env bash
#     ,_,
#    (O,O)
#    (   )   Mïmïr
#  ---"-"---
set -euo pipefail
cd "$(dirname "$0")/.."
export BASE="${BASE:-/dao-arts/}" NOINDEX="${NOINDEX:-1}"
tools/build.sh
REMOTE="$(git remote get-url origin)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone --depth 1 --branch gh-pages "$REMOTE" "$TMP/pages" 2>/dev/null || { git init -q "$TMP/pages"; git -C "$TMP/pages" checkout -q -b gh-pages; git -C "$TMP/pages" remote add origin "$REMOTE"; }
find "$TMP/pages" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -a dist/. "$TMP/pages/"
cd "$TMP/pages"
git add -A
git diff --cached --quiet && { echo "Nessuna modifica da pubblicare"; exit 0; }
git -c user.name="$(git -C "$OLDPWD" config user.name)" -c user.email="$(git -C "$OLDPWD" config user.email)" commit -qm "Pubblicazione $(date '+%Y-%m-%d %H:%M')"
git push -q origin gh-pages
echo "Pubblicato su gh-pages"
