#!/usr/bin/env bash
# Opens the built macOS app the way a customer would and lets it drive its
# own page (cmd/vpncheck-app/smoke.go): passes when the window loaded the
# page and a button's request reached the app. Takes a screenshot meanwhile.
#
#   packaging/smoke-macos.sh shot.png                 the Apple silicon half
#   SMOKE_ARCH=x86_64 packaging/smoke-macos.sh x.png   the Intel half, via Rosetta
set -u
cd "$(dirname "$0")/.."
shot="$1"
binary="dist/KairaVPN Проверка.app/Contents/MacOS/KairaVPN-Check"
marker="$(mktemp -d)/smoke"

run=("$binary")
[ -n "${SMOKE_ARCH:-}" ] && run=(arch "-${SMOKE_ARCH}" "$binary")
VPNCHECK_SMOKE="$marker" VPNCHECK_SMOKE_HOLD=8s "${run[@]}" &
pid=$!
for _ in $(seq 1 120); do
    [ -s "$marker" ] && break
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
done
screencapture -x "$shot" || echo "no screenshot"
code=0
wait "$pid" || code=$?
echo "exit $code, verdict: $(cat "$marker" 2>/dev/null || echo none)"
[ "$code" = 0 ] && [ "$(cat "$marker" 2>/dev/null)" = ok ]
