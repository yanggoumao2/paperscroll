#!/usr/bin/env bash
# Build the PaperScroll Android APK (Linux / macOS).
#   ./build-apk.sh http://100.x.y.z:8766
# Needs Node.js 20+, JDK 21 (JAVA_HOME) and the Android SDK with platform 35 (ANDROID_HOME).
set -euo pipefail
SERVER="${1:-${PAPERSCROLL_SERVER:-}}"
[ -n "$SERVER" ] || { echo "usage: $0 http://<server-address>:8766" >&2; exit 1; }
SERVER="${SERVER%/}"
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
: "${JAVA_HOME:?set JAVA_HOME to a JDK 21}"; : "${ANDROID_HOME:?set ANDROID_HOME to your Android SDK}"
cd "$HERE"
[ -d node_modules ] || npm ci
rm -rf www && cp -r "$ROOT/web" www && rm -rf www/download
echo "sdk.dir=$ANDROID_HOME" > android/local.properties
npx cap sync android
node scripts/set-server.mjs "$SERVER"
(cd android && ./gradlew assembleDebug --no-daemon --console=plain)
mkdir -p "$ROOT/dist" "$ROOT/web/download"
cp android/app/build/outputs/apk/debug/app-debug.apk "$ROOT/dist/PaperScroll.apk"
cp "$ROOT/dist/PaperScroll.apk" "$ROOT/web/download/PaperScroll.apk"
echo "BUILD_OK  ($ROOT/dist/PaperScroll.apk, server: $SERVER)"
