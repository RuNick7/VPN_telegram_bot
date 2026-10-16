#!/usr/bin/env sh
# Builds vpncheck for every platform it is handed out for, into dist/.
#
#   ./build.sh                                   version from git, site from ../.env
#   VERSION=1.2.0 SITE=https://example.com ./build.sh
#
# No Go installed? The same build in Docker:
#   docker run --rm -v "$PWD/..:/src" -w /src/vpncheck golang:1.26 ./build.sh
#
# Each binary is self-contained: Xray is compiled in, nothing to install.
set -eu
cd "$(dirname "$0")"

VERSION="${VERSION:-$(git describe --tags --always --dirty 2>/dev/null || echo dev)}"
# Where a report sent with a support code goes: the website, which owns the
# tickets. Taken from WEB_BASE_URL in the repo's .env unless given.
if [ -z "${SITE:-}" ] && [ -f ../.env ]; then
    SITE="$(sed -n 's/^WEB_BASE_URL=//p' ../.env | tail -n 1 | tr -d '"'"'"'\r')"
fi
SITE="${SITE:-}"

rm -rf dist
mkdir -p dist
for target in linux/amd64 linux/arm64 darwin/amd64 darwin/arm64 windows/amd64 windows/arm64; do
    os="${target%/*}"
    arch="${target#*/}"
    name="vpncheck-${os}-${arch}"
    [ "$os" = windows ] && name="$name.exe"
    [ "$os" = darwin ] && name="vpncheck-macos-${arch}"
    echo "building $name"
    CGO_ENABLED=0 GOOS="$os" GOARCH="$arch" go build -trimpath \
        -ldflags "-s -w -X main.version=$VERSION -X main.defaultSite=$SITE" \
        -o "dist/$name" .
done
# The node agent: Linux only, where the nodes are, and no Xray inside.
for arch in amd64 arm64; do
    name="vpncheck-agent-linux-${arch}"
    echo "building $name"
    CGO_ENABLED=0 GOOS=linux GOARCH="$arch" go build -trimpath \
        -ldflags "-s -w -X main.version=$VERSION" \
        -o "dist/$name" ./cmd/vpncheck-agent
done
(cd dist && sha256sum * > SHA256SUMS 2>/dev/null || shasum -a 256 * > SHA256SUMS)
echo "done: $(ls dist | tr '\n' ' ')"
[ -n "$SITE" ] || echo "note: no site compiled in; sending by code will need -site" >&2
