ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE}
ARG ANDROID_CMDLINE_TOOLS_VERSION=11076708
ENV DEBIAN_FRONTEND=noninteractive ANDROID_SDK_ROOT=/opt/android-sdk ANDROID_HOME=/opt/android-sdk ANDROID_BUILD_TOOLS=/opt/android-sdk/build-tools/35.0.0
ENV PATH=/opt/uber031-venv/bin:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:/opt/android-sdk/emulator:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl unzip zip python3 python3-pip python3-venv openjdk-21-jdk qemu-kvm tesseract-ocr libxkbfile1 libgl1 libnss3 libpulse0 libx11-6 libxcb1 libxcomposite1 libxcursor1 libxi6 libxrandr2 libxtst6 libasound2t64 libxdamage1 libxfixes3 libxkbcommon0 libdrm2 libgbm1 && rm -rf /var/lib/apt/lists/*
RUN if [ ! -x "$ANDROID_SDK_ROOT/emulator/emulator" ]; then \
      mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools" && \
      curl -fsSL "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_CMDLINE_TOOLS_VERSION}_latest.zip" -o /tmp/uber031-tools.zip && \
      unzip -q /tmp/uber031-tools.zip -d /tmp/uber031-tools && \
      mv /tmp/uber031-tools/cmdline-tools "$ANDROID_SDK_ROOT/cmdline-tools/latest" && \
      (yes | sdkmanager --licenses >/dev/null || true) && \
      sdkmanager "platform-tools" "emulator" "build-tools;35.0.0" "platforms;android-34" "system-images;android-33;google_apis;x86_64"; \
    fi
WORKDIR /workspace
COPY . /workspace
RUN python3 -m venv /opt/uber031-venv && /opt/uber031-venv/bin/pip install --no-cache-dir .
RUN bash scripts/build_apk.sh
# Even when reusing an Android base image, never inherit an emulator-starting entrypoint.
ENTRYPOINT []
CMD ["python", "-m", "uber_clone_031.harness.readiness"]
