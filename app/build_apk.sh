#!/usr/bin/env bash
set -euo pipefail
APP="$(cd "$(dirname "$0")" && pwd)"
BUILD="$APP/build"
export TMPDIR="$BUILD/tmp" TMP="$BUILD/tmp" TEMP="$BUILD/tmp"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk-amd64}"
export PATH="$JAVA_HOME/bin:$PATH"
export JAVA_TOOL_OPTIONS="-Djava.io.tmpdir=$BUILD/tmp -Duser.home=$BUILD/java-home"
SDK="${ANDROID_SDK_ROOT:-/data/Balram/android-sdk}"
BT="$SDK/build-tools/34.0.0"
JAR="$SDK/platforms/android-34/android.jar"
mkdir -p "$BUILD"/{tmp,java-home,out}
WORK="$(mktemp -d "$BUILD/compile.XXXXXX")"
cleanup() { case "$WORK" in "$BUILD"/compile.*) rm -rf -- "$WORK";; esac; }
trap cleanup EXIT
mkdir -p "$WORK"/{generated,classes,dex}
"$BT/aapt" package -f -m -J "$WORK/generated" -M "$APP/AndroidManifest.xml" -S "$APP/res" -I "$JAR"
find "$APP/src" "$WORK/generated" -name '*.java' | sort > "$WORK/sources.txt"
# javac 21 emits unnamed synthetic parameters which D8 8.2.2 cannot read.
# Emit real parameter names; record the compiler actually resolved from PATH.
javac -version > "$BUILD/compiler-version.txt" 2>&1
javac --release 8 -parameters -classpath "$JAR" -d "$WORK/classes" @"$WORK/sources.txt"
jar cf "$BUILD/main-classes.jar" -C "$WORK/classes" .
mapfile -t classes < <(find "$WORK/classes" -name '*.class' | sort)
"$BT/d8" --min-api 23 --lib "$JAR" --output "$WORK/dex" "${classes[@]}"
"$BT/aapt" package -f -M "$APP/AndroidManifest.xml" -S "$APP/res" -I "$JAR" -F "$WORK/unsigned.apk"
(cd "$WORK/dex" && zip -q "$WORK/unsigned.apk" classes.dex)
"$BT/zipalign" -f 4 "$WORK/unsigned.apk" "$WORK/aligned.apk"
if [[ ! -f "$BUILD/debug.keystore" ]]; then
    keytool -genkeypair -keystore "$BUILD/debug.keystore" -storepass android -keypass android \
        -alias demo -keyalg RSA -validity 10000 -dname "CN=Offline Demo"
fi
"$BT/apksigner" sign --ks "$BUILD/debug.keystore" --ks-pass pass:android --key-pass pass:android \
    --v4-signing-enabled false --out "$WORK/democart-ui.apk" "$WORK/aligned.apk"
"$BT/apksigner" verify "$WORK/democart-ui.apk"
cp "$WORK/democart-ui.apk" "$BUILD/out/democart-ui.apk"
sha256sum "$BUILD/out/democart-ui.apk"
