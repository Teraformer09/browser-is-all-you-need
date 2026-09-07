#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/app/shopping_android_app"
: "${ANDROID_SDK_ROOT:?Set ANDROID_SDK_ROOT to an SDK containing platforms;android-34}"
export ANDROID_HOME="$ANDROID_SDK_ROOT"
# Keep build caches and temporary files inside this task by default.
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$ROOT/artifacts/tool-cache/gradle}"
export TMPDIR="${TMPDIR:-$ROOT/artifacts/tool-cache/tmp}"
mkdir -p "$GRADLE_USER_HOME" "$TMPDIR"
export GRADLE_OPTS="${GRADLE_OPTS:-} -Djava.io.tmpdir=$TMPDIR"
: "${JAVA_HOME:?Set JAVA_HOME to a JDK 17 or newer installation}"
JAVA_MAJOR="$("$JAVA_HOME/bin/java" -XshowSettings:properties -version 2>&1 | awk '$1 == "java.specification.version" {print $3}')"
[[ "$JAVA_MAJOR" =~ ^[0-9]+$ && "$JAVA_MAJOR" -ge 17 ]] || {
    echo "Android Gradle Plugin 8.7.3 requires JDK 17 or newer" >&2
    exit 2
}
if [[ -n "${GRADLE_BIN:-}" ]]; then
    GRADLE=("$GRADLE_BIN")
elif [[ -f "$APP/gradlew" ]]; then
    GRADLE=(bash "$APP/gradlew")
else
    echo "Generate the pinned Gradle 8.9 wrapper, or set GRADLE_BIN to Gradle 8.9." >&2
    exit 2
fi
GRADLE_VERSION="$("${GRADLE[@]}" --version | awk '$1 == "Gradle" {print $2}')"
[[ "$GRADLE_VERSION" == "8.9" ]] || { echo "Use pinned Gradle 8.9" >&2; exit 2; }
"${GRADLE[@]}" --no-daemon -p "$APP" :app:testDebugUnitTest :app:assembleDebug
APK="$APP/app/build/outputs/apk/debug/app-debug.apk"
[[ -s "$APK" ]] || { echo "APK was not produced" >&2; exit 1; }
sha256sum "$APK"
printf 'APK=%s\n' "$APK"
