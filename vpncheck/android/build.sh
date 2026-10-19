#!/usr/bin/env sh
# Builds the Android app into ../dist/KairaVPN-Check.apk: vpncheck-app for
# each ABI into jniLibs/<abi>/libvpncheck.so, then the APK around it with
# Gradle. Needs Go, a JDK 17 or newer, Gradle, the Android SDK and its NDK
# (ANDROID_HOME, ANDROID_NDK_HOME); GitHub Actions runners have them all.
#
#   ./build.sh                          phones: 64- and 32-bit ARM
#   ABIS=x86_64 ./build.sh debug        an emulator, debuggable
#
# VERSION, SITE and DOMAINS are as for ../build.sh; SITE= and DOMAINS= set
# to nothing build an app that checks any link and asks no site.
set -eu
cd "$(dirname "$0")"

TYPE="${1:-release}"
ABIS="${ABIS:-arm64-v8a,armeabi-v7a}"
VERSION="${VERSION:-$(git describe --tags --always --dirty 2>/dev/null || echo dev)}"
SITE="${SITE-}"
DOMAINS="${DOMAINS-sub.kairavpn.pro}"
NDK="${ANDROID_NDK_HOME:-${ANDROID_NDK_LATEST_HOME:-}}"
[ -n "$NDK" ] || { echo "ANDROID_NDK_HOME is not set" >&2; exit 1; }
CLANG="$(ls -d "$NDK"/toolchains/llvm/prebuilt/*/bin | head -n 1)"

# Through the NDK's clang, as Android's own programs are: Go links android
# executables only that way, but for arm64. 16 KB pages: Android 15 phones
# may use them, and a program laid out for 4 KB ones does not start there.
# -checklinkname=0: Xray's wlynxg/anet reaches into the net package.
rm -rf jniLibs
for abi in $(printf '%s' "$ABIS" | tr ',' ' '); do
    case "$abi" in
        arm64-v8a) goarch=arm64 cc=aarch64-linux-android26-clang ;;
        armeabi-v7a) goarch=arm cc=armv7a-linux-androideabi26-clang ;;
        x86_64) goarch=amd64 cc=x86_64-linux-android26-clang ;;
        *) echo "unknown ABI: $abi" >&2; exit 1 ;;
    esac
    echo "building $abi"
    mkdir -p "jniLibs/$abi"
    (cd .. && CGO_ENABLED=1 CC="$CLANG/$cc" GOOS=android GOARCH="$goarch" GOARM=7 go build -trimpath -tags timetzdata \
        -ldflags "-s -w -checklinkname=0 -extldflags=-Wl,-z,max-page-size=16384 -X main.version=$VERSION -X main.domains=$DOMAINS -X main.site=$SITE" \
        -o "android/jniLibs/$abi/libvpncheck.so" ./cmd/vpncheck-app)
done

# Each release a higher number, or the phone will not update the app:
# v1.2.3-beta.4 is 1020304, v1.2.3 itself 1020399. Anything that is not a
# release is 1.
CODE=1
parts="$(printf '%s' "$VERSION" | sed -n 's/^v\([0-9]\{1,3\}\)\.\([0-9]\{1,2\}\)\.\([0-9]\{1,2\}\)\(-[a-z]*\.\([0-9]\{1,2\}\)\)\{0,1\}$/\1 \2 \3 \5/p')"
if [ -n "$parts" ]; then
    # shellcheck disable=SC2086
    set -- $parts
    CODE=$(( (($1 * 100 + $2) * 100 + $3) * 100 + ${4:-99} ))
fi

task="assembleRelease"
[ "$TYPE" = debug ] && task="assembleDebug"
${GRADLE:-gradle} --no-daemon -q "$task" -PversionName="$VERSION" -PversionCode="$CODE" -Pabis="$ABIS"
mkdir -p ../dist
apk="$(find "build/outputs/apk/$TYPE" -name '*.apk' | head -n 1)"
cp "$apk" ../dist/KairaVPN-Check.apk
echo "done: dist/KairaVPN-Check.apk ($VERSION, code $CODE, $ABIS)"
