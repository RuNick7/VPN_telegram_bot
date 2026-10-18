#!/usr/bin/env sh
# Builds vpncheck for every platform it is handed out for, into dist/: the
# command line, the customers' app and the node agent. The macOS app needs a
# Mac (packaging/macos.sh, run from here when this is one).
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
# The website: where a report sent to support goes, and what the app asks
# for a subscription's status. Taken from WEB_BASE_URL in the repo's .env
# unless given; empty builds leave both out.
if [ -z "${SITE:-}" ] && [ -f ../.env ]; then
    SITE="$(sed -n 's/^WEB_BASE_URL=//p' ../.env | tail -n 1 | tr -d '"'"'"'\r')"
fi
SITE="${SITE:-}"
# The hosts subscription links are on: the app turns any other link away
# with an explanation instead of checking someone else's servers.
DOMAINS="${DOMAINS:-sub.kairavpn.pro}"

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
# The customers' app. Windows: a window of its own (WebView2), with the icon
# and version in the file. Linux: the same page in the browser.
NUMBER="$(printf '%s' "$VERSION" | sed -n 's/^v\{0,1\}\([0-9][0-9]*\(\.[0-9][0-9]*\)\{0,2\}\).*/\1/p')"
WINVER="$(printf '%s.0.0.0' "${NUMBER:-0}" | cut -d. -f1-4)"
go run github.com/tc-hib/go-winres@v0.3.3 make --in packaging/winres.json --arch amd64,arm64 \
    --out cmd/vpncheck-app/rsrc --product-version "$WINVER" --file-version "$WINVER"
trap 'rm -f cmd/vpncheck-app/rsrc_windows_*.syso' EXIT
# Named in full: the service's download page links these names, and its
# tests look for them here.
for target in amd64:KairaVPN-Check-x64.exe arm64:KairaVPN-Check-arm64.exe; do
    arch="${target%%:*}" name="${target#*:}"
    echo "building $name"
    CGO_ENABLED=0 GOOS=windows GOARCH="$arch" go build -trimpath -tags desktop,production \
        -ldflags "-s -w -H windowsgui -X main.version=$VERSION -X main.domains=$DOMAINS -X main.site=$SITE" \
        -o "dist/$name" ./cmd/vpncheck-app
done
for target in amd64:KairaVPN-Check-linux-x64 arm64:KairaVPN-Check-linux-arm64; do
    arch="${target%%:*}" name="${target#*:}"
    echo "building $name"
    CGO_ENABLED=0 GOOS=linux GOARCH="$arch" go build -trimpath \
        -ldflags "-s -w -X main.version=$VERSION -X main.domains=$DOMAINS -X main.site=$SITE" \
        -o "dist/$name" ./cmd/vpncheck-app
done
# macOS: the window is WebKit through cgo, so the app is built on a Mac.
if [ "$(uname -s)" = Darwin ]; then
    VERSION="$VERSION" SITE="$SITE" DOMAINS="$DOMAINS" packaging/macos.sh
    rm -rf "dist/KairaVPN Проверка.app"
else
    echo "note: the macOS app (KairaVPN-Check.dmg) is built on a Mac: packaging/macos.sh" >&2
fi
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
[ -n "$SITE" ] || echo "note: no site compiled in: the app will not show payment status or send reports, and vpncheck -send needs -site" >&2
