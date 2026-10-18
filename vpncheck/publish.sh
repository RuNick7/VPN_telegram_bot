#!/usr/bin/env sh
# Copies vpncheck/ as committed here into its public repository,
# github.com/RuNick7/vpn-check, where GitHub Actions tests and builds it.
#
#   ./publish.sh            push the current commit's vpncheck/ to main
#   ./publish.sh v1.2.0     the same, then tag it: Actions publish a release
#
# This directory is the source; the public repository is a copy of it. Only
# what is committed goes, so nothing local leaks out with it.
set -eu
cd "$(dirname "$0")"

REPO="${REPO:-https://github.com/RuNick7/vpn-check.git}"
TAG="${1:-}"
source_commit="$(git rev-parse --short HEAD)"
if [ -n "$(git status --porcelain -- .)" ]; then
    echo "vpncheck/ has uncommitted changes: commit them first, only committed files are published" >&2
    exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
git clone --quiet "$REPO" "$work/repo"
# Everything but the history goes, so files deleted here go there too.
find "$work/repo" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
git archive HEAD . | tar -x -C "$work/repo"

cd "$work/repo"
git add -A
if git diff --cached --quiet; then
    echo "nothing changed since the last publish"
else
    git commit --quiet -m "Sync from the service repository at $source_commit"
    git push --quiet origin HEAD:main
    echo "pushed $(git rev-parse --short HEAD) to $REPO"
fi
if [ -n "$TAG" ]; then
    git tag -a "$TAG" -m "KairaVPN Проверка $TAG"
    git push --quiet origin "$TAG"
    echo "tagged $TAG: the release builds in GitHub Actions"
fi
