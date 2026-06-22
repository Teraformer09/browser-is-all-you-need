.PHONY: test unit integration android-world prime docker-build docker-test docker-run docker-real-adb-smoke build-apk install-apk adb-run androidworld-openai androidworld-scripted prime-eval prime-eval-form prime-eval-ride run clean benchmark-proof benchmark-quick benchmark-release throughput-benchmark \
	mobile-help mobile-preflight mobile-health mobile-benchmark-proof mobile-benchmark-quick mobile-benchmark-release mobile-throughput mobile-rollout mobile-prime-eval mobile-android-world mobile-android-world-scripted mobile-pipeline

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
	python3 -B -m android_adk_rl_env.cli eval --task tasks/form_default.yaml --policy scripted --compact

run:
	bash ./scripts/run_rollout.sh

benchmark-proof:
	python3 -B -m android_adk_rl_env.cli benchmark \
	  --policy scripted \
	  --samples-per-task "$${BENCHMARK_SAMPLES_PER_TASK:-10}" \
	  --pass-k 1 2 3 5 10 \
	  --max-steps "$${BENCHMARK_MAX_STEPS:-12}" \
	  --bootstrap-samples "$${BENCHMARK_BOOTSTRAP_SAMPLES:-0}" \
	  --tasks-dir tasks \
	  --pool-size "$${POOL_SIZE:-1}" \
	  --output "$${MOBILE_BENCHMARK_OUTPUT_PREFIX:-artifacts/benchmarks}/proof"

benchmark-quick:
	python3 -B -m android_adk_rl_env.cli benchmark \
	  --policy scripted \
	  --samples-per-task "$${BENCHMARK_ATTEMPTS_QUICK:-4}" \
	  --pass-k 1 2 3 \
	  --max-steps "$${BENCHMARK_MAX_STEPS:-12}" \
	  --bootstrap-samples "$${BENCHMARK_BOOTSTRAP_SAMPLES:-0}" \
	  --tasks-dir tasks \
	  --pool-size "$${POOL_SIZE:-1}" \
	  --output "$${MOBILE_BENCHMARK_OUTPUT_PREFIX:-artifacts/benchmarks}/proof-quick"

benchmark-release:
	python3 -B -m android_adk_rl_env.cli benchmark \
	  --policy scripted \
	  --samples-per-task "$${BENCHMARK_ATTEMPTS_RELEASE:-10}" \
	  --pass-k 1 2 3 5 10 \
	  --max-steps "$${BENCHMARK_MAX_STEPS:-12}" \
	  --bootstrap-samples "$${BENCHMARK_BOOTSTRAP_SAMPLES:-0}" \
	  --enable-calibration \
	  --tasks-dir tasks \
	  --pool-size "$${POOL_SIZE:-1}" \
	  --output "$${MOBILE_BENCHMARK_OUTPUT_PREFIX:-artifacts/benchmarks}/release"

throughput-benchmark:
	python3 -B -m android_adk_rl_env.benchmarking.throughput \
	  --pool-sizes $${THROUGHPUT_POOL_SIZES:-1 2 4 8} \
	  --attempts-per-instance "$${BENCHMARK_SAMPLES_PER_TASK:-10}" \
	  --pass-k 1 2 3 5 10 \
	  --tasks-dir tasks \
	  --output "$${MOBILE_THROUGHPUT_OUTPUT_PREFIX:-artifacts/throughput}"

# Prime / AndroidWorld runners
androidworld-openai:
	./scripts/run_android_world_openai.sh

androidworld-scripted:
	POLICY=scripted ./scripts/run_android_world_openai.sh

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
	@echo "  make mobile-throughput"
	@echo "  make mobile-rollout"
	@echo "  make mobile-prime-eval"
	@echo "  make mobile-android-world"
	@echo "  make mobile-pipeline"

mobile-preflight:
	POOL_SIZE="$${POOL_SIZE:-1}" ./scripts/mobile_rl.sh preflight

mobile-health:
	python3 -B -m android_adk_rl_env.cli health

mobile-benchmark-proof:
	python3 -B -m android_adk_rl_env.cli benchmark --policy scripted --samples-per-task "$${BENCHMARK_SAMPLES_PER_TASK:-10}" --pass-k 1 2 3 5 10 --max-steps "$${BENCHMARK_MAX_STEPS:-12}" --bootstrap-samples "$${BENCHMARK_BOOTSTRAP_SAMPLES:-0}" --tasks-dir tasks --pool-size "$${POOL_SIZE:-1}" --output "$${MOBILE_BENCHMARK_OUTPUT_PREFIX:-artifacts/benchmarks}/proof"

mobile-benchmark-quick:
	python3 -B -m android_adk_rl_env.cli benchmark --policy scripted --samples-per-task "$${BENCHMARK_ATTEMPTS_QUICK:-4}" --pass-k 1 2 3 --max-steps "$${BENCHMARK_MAX_STEPS:-12}" --bootstrap-samples "$${BENCHMARK_BOOTSTRAP_SAMPLES:-0}" --tasks-dir tasks --pool-size "$${POOL_SIZE:-1}" --output "$${MOBILE_BENCHMARK_OUTPUT_PREFIX:-artifacts/benchmarks}/proof-quick"

mobile-benchmark-release:
	python3 -B -m android_adk_rl_env.cli benchmark --policy scripted --samples-per-task "$${BENCHMARK_ATTEMPTS_RELEASE:-10}" --pass-k 1 2 3 5 10 --max-steps "$${BENCHMARK_MAX_STEPS:-12}" --bootstrap-samples "$${BENCHMARK_BOOTSTRAP_SAMPLES:-0}" --enable-calibration --tasks-dir tasks --pool-size "$${POOL_SIZE:-1}" --output "$${MOBILE_BENCHMARK_OUTPUT_PREFIX:-artifacts/benchmarks}/release"

mobile-throughput:
	python3 -B -m android_adk_rl_env.benchmarking.throughput --pool-sizes $${THROUGHPUT_POOL_SIZES:-1 2 4 8} --attempts-per-instance "$${BENCHMARK_SAMPLES_PER_TASK:-10}" --pass-k 1 2 3 5 10 --tasks-dir tasks --output "$${MOBILE_THROUGHPUT_OUTPUT_PREFIX:-artifacts/throughput}"

mobile-rollout:
	POOL_SIZE="$${POOL_SIZE:-1}" ./scripts/mobile_rl.sh rollout --pool-size "$${POOL_SIZE:-1}"

mobile-prime-eval:
	./scripts/mobile_rl.sh prime-eval

mobile-android-world:
	./scripts/mobile_rl.sh android-world

mobile-android-world-scripted:
	./scripts/mobile_rl.sh android-world --policy scripted

# Optional end-to-end proof flow (default: preflight + proof benchmark + rollout)
mobile-pipeline:
	./scripts/mobile_rl.sh pipeline ${MOBILE_PIPELINE_ARGS}

clean:
	rm -rf artifacts/runs/*
