FROM ubuntu:24.04

ARG ANDROID_CMDLINE_TOOLS_VERSION=11076708

ENV DEBIAN_FRONTEND=noninteractive
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
ENV ANDROID_SDK_ROOT=/opt/android-sdk
ENV ANDROID_HOME=/opt/android-sdk
ENV ANDROID_BUILD_TOOLS=/opt/android-sdk/build-tools/34.0.0
ENV ANDROID_WORLD_VENV=/opt/android-adk-venv
ENV ANDROID_WORLD_SRC=/workspace/third_party/android_world
ENV ANDROID_AVD_HOME=/workspace/.deps/android_avd
ENV ANDROID_WORLD_AVD_NAME=AndroidWorld_API_33
ENV ANDROID_WORLD_SYSTEM_IMAGE=system-images;android-33;google_apis;x86_64
ENV ADB_PATH=/opt/android-sdk/platform-tools/adb
ENV EMULATOR_BIN=/opt/android-sdk/emulator/emulator
ENV PATH=/opt/android-adk-venv/bin:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/emulator:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      unzip \
      zip \
      openssh-server \
      procps \
      netcat-openbsd \
      build-essential \
      python3 \
      python3-dev \
      python3-pip \
      python3-venv \
      openjdk-21-jdk \
      qemu-kvm \
      libgl1 \
      libnss3 \
      libpulse0 \
      libx11-6 \
      libxcb1 \
      libxcomposite1 \
      libxcursor1 \
      libxi6 \
      libxrandr2 \
      libxtst6 \
      libasound2t64 \
      libxdamage1 \
      libxfixes3 \
      libxkbcommon0 \
      libdrm2 \
      libgbm1 \
      libqhull-dev && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools" /var/run/sshd /root/.ssh && \
    curl -fsSL "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_CMDLINE_TOOLS_VERSION}_latest.zip" -o /tmp/android-cmdline-tools.zip && \
    unzip -q /tmp/android-cmdline-tools.zip -d /tmp/android-cmdline-tools && \
    mv /tmp/android-cmdline-tools/cmdline-tools "$ANDROID_SDK_ROOT/cmdline-tools/latest" && \
    rm -rf /tmp/android-cmdline-tools /tmp/android-cmdline-tools.zip && \
    ssh-keygen -A && \
    chmod 700 /root/.ssh

RUN yes | sdkmanager --sdk_root="$ANDROID_SDK_ROOT" --licenses >/dev/null || true && \
    sdkmanager --sdk_root="$ANDROID_SDK_ROOT" \
      "cmdline-tools;latest" \
      "platform-tools" \
      "emulator" \
      "build-tools;34.0.0" \
      "platforms;android-33" \
      "platforms;android-34" \
      "$ANDROID_WORLD_SYSTEM_IMAGE"

RUN python3 -m venv "$ANDROID_WORLD_VENV" && \
    python -m pip install --upgrade pip wheel "setuptools<81" && \
    python -m pip install prime

WORKDIR /workspace
COPY . /workspace

RUN python -m pip install -r "$ANDROID_WORLD_SRC/requirements.txt" && \
    python -m pip install --no-build-isolation -e "$ANDROID_WORLD_SRC" && \
    python -m pip install -e /workspace && \
    /workspace/scripts/build_dummy_apk.sh

COPY docker/entrypoint.sh /usr/local/bin/android-adk-docker
COPY docker/prime_start.sh /usr/local/bin/prime-start.sh
RUN chmod +x /usr/local/bin/android-adk-docker /usr/local/bin/prime-start.sh

EXPOSE 22 5554 5555 5556 5557 8554

ENTRYPOINT ["android-adk-docker"]
CMD ["help"]
