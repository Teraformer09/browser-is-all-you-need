#!/usr/bin/env bash
# Same logged installation recipe for the diagnostic Prime VM and OCI image.
set -euo pipefail
SOURCE=/opt/democart/source
export DEBIAN_FRONTEND=noninteractive ANDROID_SDK_ROOT=/opt/android-sdk
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export ANDROID_USER_HOME=/data/Tirtha/democart-runtime/android-user
export TMPDIR=/data/Tirtha/democart-runtime/tmp
export PYTHONDONTWRITEBYTECODE=1
export PATH="/opt/venv/bin:$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$JAVA_HOME/bin:$PATH"
stage() { printf 'DEMOCART_BUILD_STAGE %s\n' "$1"; }
test -f "$SOURCE/pyproject.toml"
mkdir -p "$TMPDIR" "$ANDROID_USER_HOME" "$ANDROID_SDK_ROOT/cmdline-tools"
stage os_dependencies
apt-get update
apt-get install -y --no-install-recommends python3 python3-venv openjdk-21-jdk-headless \
    ca-certificates curl unzip zip ffmpeg libasound2t64 libnss3 libx11-6 libxcomposite1 \
    libxcursor1 libxi6 libxtst6 libxrandr2 libxrender1 libglu1-mesa libpulse0 libdbus-1-3 libxkbcommon0 libxkbfile1
stage sdk_download_and_checksum
curl --connect-timeout 20 --max-time 180 -fSL \
    https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip \
    -o /opt/democart/commandline.zip
printf '%s  %s\n' 4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583 /opt/democart/commandline.zip | sha256sum -c -
unzip -q /opt/democart/commandline.zip -d "$ANDROID_SDK_ROOT/cmdline-tools"
mv "$ANDROID_SDK_ROOT/cmdline-tools/cmdline-tools" "$ANDROID_SDK_ROOT/cmdline-tools/latest"
stage sdk_licenses
# yes exits with SIGPIPE after sdkmanager exits. Only sdkmanager determines success.
(set +o pipefail; yes | sdkmanager --licenses)
stage android_packages
# The offline app needs API 33, not Google background services. Keep the
# original KVM Dockerfile unchanged; this separate software recipe uses AOSP.
sdkmanager 'platform-tools' 'emulator' 'platforms;android-34' 'build-tools;34.0.0' 'system-images;android-33;default;x86_64'
stage emulator_executable_preflight
# Fail here with the actual linker error, before declaring runtime installation ready.
"$ANDROID_SDK_ROOT/emulator/emulator" -version > /opt/democart/emulator-version.txt
stage python_dependencies
python3 -m venv /opt/venv
pip install --no-cache-dir "$SOURCE"
stage apk_build
bash "$SOURCE/app/amazon_android_ui/build_apk.sh"
cp "$SOURCE/app/amazon_android_ui/build/out/democart-ui.apk" /opt/democart/app.apk
sha256sum /opt/democart/app.apk > /opt/democart/apk.sha256
sdkmanager --list_installed > /opt/democart/android-packages.txt
stage complete
