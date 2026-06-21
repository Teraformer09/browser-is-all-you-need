.PHONY: test unit integration android-world prime docker-build docker-test docker-run docker-real-adb-smoke build-apk install-apk adb-run androidworld-openai prime-eval prime-eval-form prime-eval-ride run clean benchmark-proof benchmark-quick benchmark-release \
	mobile-help mobile-preflight mobile-health mobile-benchmark-proof mobile-benchmark-quick mobile-benchmark-release mobile-rollout mobile-prime-eval mobile-android-world mobile-pipeline

# Standard project checks

test:
	python3 -m unittest discover -s tests/unit

unit:
	python3 -m unittest discover -s tests/unit

integration:
	python3 -m unittest discover -s tests/integration

android-world:
	python3 -m unittest discover -s tests/android_world

prime:
	python3 -m unittest discover -s tests/prime

# Build / install
build-apk:
	bash ./scripts/build_dummy_apk.sh

install-apk:
	bash ./scripts/install_dummy_apk.sh

# Scripted / rollout / benchmark paths
adb-run:
	python3 -B -m android_adk_rl_env.runner --task dummy_apk --policy adb-scripted --install-apk --compact

run:
	bash ./scripts/run_rollout.sh

benchmark-proof:
	./scripts/run_proof_benchmark.sh \
	  --backend "$${ROLLOUT_BACKEND:-adb}" \
	  --policy scripted \
	  --attempts-per-instance "$${BENCHMARK_ATTEMPTS:-20}" \
	  --pass-k 1 2 5 10 \
	  --max-steps "$${BENCHMARK_MAX_STEPS:-12}" \
	  --bootstrap-samples "$${BENCHMARK_BOOTSTRAP_SAMPLES:-0}" \
	  --output "$${MOBILE_BENCHMARK_OUTPUT_PREFIX:-artifacts/benchmarks}/proof"

benchmark-quick:
	./scripts/run_proof_benchmark.sh \
	  --backend "$${ROLLOUT_BACKEND:-adb}" \
	  --policy scripted \
	  --attempts-per-instance "$${BENCHMARK_ATTEMPTS_QUICK:-4}" \
	  --pass-k 1 2 3 \
	  --max-steps "$${BENCHMARK_MAX_STEPS:-12}" \
	  --bootstrap-samples "$${BENCHMARK_BOOTSTRAP_SAMPLES:-0}" \
	  --output "$${MOBILE_BENCHMARK_OUTPUT_PREFIX:-artifacts/benchmarks}/proof-quick"

benchmark-release:
	./scripts/run_proof_benchmark.sh \
	  --backend "$${ROLLOUT_BACKEND:-adb}" \
	  --policy scripted \
	  --attempts-per-instance "$${BENCHMARK_ATTEMPTS_RELEASE:-20}" \
	  --pass-k 1 2 5 10 \
	  --max-steps "$${BENCHMARK_MAX_STEPS:-12}" \
	  --bootstrap-samples "$${BENCHMARK_BOOTSTRAP_SAMPLES:-0}" \
	  --output "$${MOBILE_BENCHMARK_OUTPUT_PREFIX:-artifacts/benchmarks}/release"

# Prime / AndroidWorld runners
androidworld-openai:
	./scripts/run_android_world_openai.sh

prime-eval:
	./scripts/run_prime_eval_android_adk.sh

prime-eval-form:
	./scripts/run_prime_eval_android_adk.sh

prime-eval-ride:
	PRIME_ANDROID_TASKSET=ride ./scripts/run_prime_eval_android_adk.sh

# Docker tasks
docker-build:
	docker compose -f docker-compose.yml build

docker-test:
	docker compose -f docker-compose.yml run --rm mobile-rl-runner make test

docker-run:
	docker compose -f docker-compose.yml run --rm mobile-rl-runner make run

docker-real-adb-smoke:
	bash ./scripts/docker_real_adb_openai_rollout.sh

# Standardized mobile orchestrator interface (recommended)
mobile-help:
	@echo "Standard mobile commands:"
	@echo "  make mobile-preflight"
	@echo "  make mobile-health"
	@echo "  make mobile-benchmark-proof"
	@echo "  make mobile-benchmark-quick"
	@echo "  make mobile-benchmark-release"
	@echo "  make mobile-rollout"
	@echo "  make mobile-prime-eval"
	@echo "  make mobile-android-world"
	@echo "  make mobile-pipeline"

mobile-preflight:
	POOL_SIZE="$${POOL_SIZE:-1}" ./scripts/mobile_rl.sh preflight

mobile-health:
	./scripts/mobile_rl.sh health

mobile-benchmark-proof:
	POOL_SIZE="$${POOL_SIZE:-1}" ./scripts/mobile_rl.sh benchmark proof --collect-screenshot --pool-size "$${POOL_SIZE:-1}"

mobile-benchmark-quick:
	POOL_SIZE="$${POOL_SIZE:-1}" ./scripts/mobile_rl.sh benchmark quick --pool-size "$${POOL_SIZE:-1}"

mobile-benchmark-release:
	POOL_SIZE="$${POOL_SIZE:-1}" ./scripts/mobile_rl.sh benchmark release --pool-size "$${POOL_SIZE:-1}"

mobile-rollout:
	POOL_SIZE="$${POOL_SIZE:-1}" ./scripts/mobile_rl.sh rollout --pool-size "$${POOL_SIZE:-1}"

mobile-prime-eval:
	./scripts/mobile_rl.sh prime-eval

mobile-android-world:
	./scripts/mobile_rl.sh android-world

# Optional end-to-end proof flow (default: preflight + proof benchmark + rollout)
mobile-pipeline:
	./scripts/mobile_rl.sh pipeline ${MOBILE_PIPELINE_ARGS}

clean:
	rm -rf artifacts/runs/*
