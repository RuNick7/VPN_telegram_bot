#!/usr/bin/env sh
# Opens the app on a running emulator and drives its page's API the way the
# page does, to see that the check works on Android, not only that it
# starts: a check of a link with no subscription behind it still has to
# resolve the name through the phone's DNS, fetch it over TLS against the
# phone's certificates, and write a report naming the phone's network.
#
#   ABIS=x86_64 SITE= DOMAINS= android/build.sh debug
#   android/smoke.sh shot.png
set -eu
cd "$(dirname "$0")/.."
shot="${1:-android.png}"
app=pro.kairavpn.check

adb install -r dist/KairaVPN-Check.apk
adb logcat -c
adb shell am start -W -n "$app/.MainActivity"
trap 'adb exec-out screencap -p > "$shot" || true; adb logcat -d -s vpncheck:* | tail -n 60' EXIT

# The page's address, key included, from a debug build's log.
url=""
for _ in $(seq 60); do
    url="$(adb logcat -d -s vpncheck:I | sed -n 's/.*URL \(http:[^ ]*\).*/\1/p' | tail -n 1)"
    [ -n "$url" ] && break
    sleep 1
done
[ -n "$url" ] || { echo "the check did not start" >&2; exit 1; }
port="$(printf '%s' "$url" | sed 's|^http://127.0.0.1:\([0-9]*\)/.*|\1|')"
key="${url##*#k=}"
adb forward tcp:18080 "tcp:$port"

for _ in $(seq 30); do
    adb logcat -d -s vpncheck:I | grep -q "page loaded" && break
    sleep 1
done
adb logcat -d -s vpncheck:I | grep -q "page loaded" || { echo "the page did not load" >&2; exit 1; }
if adb logcat -d -s vpncheck:E | grep -q "page:"; then
    echo "the page logged errors" >&2
    exit 1
fi

api() {
    path="$1"
    shift
    curl -fsS --max-time 30 -H "Authorization: Bearer $key" -H "Content-Type: application/json" "$@" "http://127.0.0.1:18080$path"
}
api /api/state | jq -c .
api /api/check -d '{"link":"https://www.google.com/vpncheck-smoke-test"}' > /dev/null
state=""
for _ in $(seq 120); do
    state="$(api /api/state)"
    case "$(printf '%s' "$state" | jq -r .phase)" in
        fetching | network | tunnels) sleep 1 ;;
        *) break ;;
    esac
done
printf '%s\n' "$state" | jq -c '{phase, problem}'
title="$(printf '%s' "$state" | jq -r '.problem.title // ""')"
case "$title" in
    "Нет интернета" | "Подписка не скачалась" | "")
        echo "the phone's connection did not work for the check: «$title»" >&2
        exit 1
        ;;
esac

# The report the page would share, as the app's own folder holds it.
name="$(api /api/report -d '{}' | jq -r .name)"
dir="${name#vpncheck-}"
dir="${dir%.zip}"
report="$(adb shell run-as "$app" cat "cache/vpncheck/reports/$dir/report.txt")"
printf '%s\n' "$report" | head -n 30
for want in "Android" "Сеть"; do
    printf '%s' "$report" | grep -q "$want" || { echo "the report does not say «$want»" >&2; exit 1; }
done
echo "smoke test passed"
