#!/usr/bin/env sh
# Builds the macOS app on a Mac: one KairaVPN Проверка.app for Apple silicon
# and Intel together, and KairaVPN-Check.dmg holding it, into dist/.
#
#   VERSION=1.2.0 SITE=https://example.com packaging/macos.sh
#
# The window is the system's WebKit through cgo, which is why this needs a
# Mac and build.sh does not build it. Not signed with a Developer ID: the
# first start asks once (System Settings → Privacy & Security → Open Anyway).
set -eu
cd "$(dirname "$0")/.."

VERSION="${VERSION:-$(git describe --tags --always --dirty 2>/dev/null || echo dev)}"
SITE="${SITE:-}"
DOMAINS="${DOMAINS:-sub.kairavpn.pro}"
# What Finder and the About box show: the numbers only.
NUMBER="$(printf '%s' "$VERSION" | sed -n 's/^v\{0,1\}\([0-9][0-9]*\(\.[0-9][0-9]*\)\{0,2\}\).*/\1/p')"
NUMBER="${NUMBER:-0.0.0}"

APP="dist/KairaVPN Проверка.app"
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
mkdir -p dist
rm -rf "$APP" dist/KairaVPN-Check.dmg

export CGO_ENABLED=1 GOOS=darwin MACOSX_DEPLOYMENT_TARGET=12.0
export CGO_CFLAGS="-mmacosx-version-min=12.0" CGO_LDFLAGS="-mmacosx-version-min=12.0"
for arch in arm64 amd64; do
    echo "building the app for $arch"
    GOARCH="$arch" go build -trimpath -tags desktop,production \
        -ldflags "-s -w -X main.version=$VERSION -X main.domains=$DOMAINS -X main.site=$SITE" \
        -o "$BUILD/KairaVPN-Check-$arch" ./cmd/vpncheck-app
done

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
lipo -create -output "$APP/Contents/MacOS/KairaVPN-Check" "$BUILD/KairaVPN-Check-arm64" "$BUILD/KairaVPN-Check-amd64"
cp packaging/AppIcon.icns "$APP/Contents/Resources/AppIcon.icns"
sed "s/@VERSION@/$NUMBER/g" packaging/Info.plist > "$APP/Contents/Info.plist"
printf 'APPL????' > "$APP/Contents/PkgInfo"
# Ad hoc: no identity, but Apple silicon runs nothing unsigned, and the
# bundle's seal covers the icon and Info.plist with the binary.
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

# The usual disk image: the app and a link to Applications to drag it onto.
mkdir "$BUILD/dmg"
cp -R "$APP" "$BUILD/dmg/"
ln -s /Applications "$BUILD/dmg/Applications"
hdiutil create -quiet -volname "KairaVPN Проверка" -srcfolder "$BUILD/dmg" -fs HFS+ -format UDZO -ov dist/KairaVPN-Check.dmg
echo "done: dist/KairaVPN-Check.dmg ($(du -h dist/KairaVPN-Check.dmg | cut -f1))"
