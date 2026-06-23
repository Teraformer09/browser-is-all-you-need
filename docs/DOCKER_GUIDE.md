# Docker Guide

Last updated: 2026-06-23

This repository has two Docker execution modes:

```text
1. Host-ADB runner
2. Self-contained Android emulator / AndroidWorld image
```

They are both real containerized workflows, but they solve different problems.

## 1. Host-ADB Runner

File:

```text
docker-compose.yml
```

Use this when:

```text
ADB and the emulator already run on the host
You want the Python code, tests, and rollout logic isolated in Docker
You want the container to talk to the host ADB server
```

The runner container:

```text
installs Python dependencies
installs Android SDK client tools
uses host.docker.internal to reach the host ADB server
mounts artifact directories back to the host
```

Relevant files:

```text
Dockerfile.runner
docker-compose.yml
scripts/docker_real_adb_openai_rollout.sh
```

Example commands:

```bash
docker compose -f docker-compose.yml build
docker compose -f docker-compose.yml run --rm mobile-rl-runner make test
docker compose -f docker-compose.yml run --rm mobile-rl-runner make run
```

This path is the lightest Docker option. It is not self-contained, because the emulator/device lives outside the container.

## 2. Self-Contained Emulator Image

Files:

```text
Dockerfile
compose.yaml
docker/
```

Use this when:

```text
You want the Android emulator created inside Docker
You want AndroidWorld available in the same image
You want Prime / verifiers support from the same container image
You want one container to own the Android runtime stack
```

The image:

```text
installs the Android SDK and emulator
installs AndroidWorld from the vendored `third_party/android_world` copy
installs Prime
builds the dummy APK
copies the repository into /workspace
provides a shell entrypoint with task-oriented subcommands
```

Relevant files:

```text
Dockerfile
compose.yaml
docker/entrypoint.sh
docker/entrypoint.real-adb-runner.sh
docker/prime_start.sh
scripts/docker_run.sh
```

Example commands:

```bash
docker compose -f compose.yaml build
docker compose -f compose.yaml run --rm android-adk help
docker compose -f compose.yaml run --rm android-adk tests
docker compose -f compose.yaml run --rm android-adk build-apk
docker compose -f compose.yaml run --rm android-adk adb-scripted
docker compose -f compose.yaml run --rm --service-ports android-adk android-world-openai
docker compose -f compose.yaml run --rm android-adk prime-eval
```

The helper script defaults to `compose.yaml` and can be overridden with `COMPOSE_FILE=...`.

The vendored `third_party/android_world` tree in this repo is the source of truth.

```bash
./scripts/docker_run.sh build
./scripts/docker_run.sh tests
./scripts/docker_run.sh shell
./scripts/docker_run.sh build-apk
./scripts/docker_run.sh rollout
./scripts/docker_run.sh benchmark proof --json
./scripts/docker_run.sh health
./scripts/docker_run.sh preflight
./scripts/docker_run.sh android-world-openai
./scripts/docker_run.sh prime-eval
```

Make targets mirror these workflows:

```bash
make docker-build
make docker-test
make docker-run
make docker-full-build
make docker-full-tests
make docker-full-shell
make docker-full-build-apk
make docker-full-rollout
make docker-full-android-world
make docker-full-prime-eval
make docker-full-health
make docker-full-preflight
make docker-full-benchmark
```

## 3. What Is And Is Not Fully Dockerized

What is in Docker:

```text
Python package and tests
Android SDK client tools
AndroidWorld dependencies from the vendored repo copy
Prime / verifiers integration
Emulator launch orchestration
Rollout and benchmark commands
```

What still depends on host or external runtime conditions:

```text
Hardware acceleration through /dev/kvm for local emulator performance
An actual reachable ADB server or emulator when using host-ADB mode
OpenAI/Prime API keys when those policies are enabled
Network access for first-time image builds and package downloads
```

So the practical answer is:

```text
The software stack is dockerized.
The Android runtime is containerized in one mode and host-bridged in the other.
```

## 4. Recommended Paths

If you want simple local development:

```bash
docker compose -f docker-compose.yml run --rm mobile-rl-runner make test
```

If you want the full emulator path:

```bash
docker compose -f compose.yaml run --rm android-adk adb-scripted
```

If you want the full orchestrated pipeline:

```bash
./scripts/mobile_rl.sh pipeline --preset proof
```

## 5. Common Pitfalls

If Docker says it cannot reach ADB:

```text
confirm the host ADB server is running
confirm host.docker.internal resolves correctly
confirm ADB_SERVER_SOCKET or ADB_SERIAL is set appropriately
```

If the emulator is slow or fails to boot:

```text
confirm /dev/kvm is available
confirm the container is privileged where required
confirm shm_size is large enough
```

If AndroidWorld fails to import:

```text
the container image may not have been built yet
the AndroidWorld package install may have failed
the emulator launch ports may not match the expected gRPC port
```

If you use the wrong compose file name:

```text
use docker-compose.yml for the host-ADB runner
use compose.yaml for the self-contained emulator image
```
