.PHONY: test unit integration android-world prime docker-build docker-test docker-run docker-real-adb-smoke build-apk install-apk adb-run androidworld-openai prime-eval prime-eval-form prime-eval-ride run clean benchmark-proof benchmark-quick benchmark-release

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

build-apk:
	bash ./scripts/build_dummy_apk.sh

install-apk:
	bash ./scripts/install_dummy_apk.sh

adb-run:
	python3 -B -m android_adk_rl_env.runner --task dummy_apk --policy adb-scripted --install-apk --compact

androidworld-openai:
	./scripts/run_android_world_openai.sh

prime-eval:
	./scripts/run_prime_eval_android_adk.sh

prime-eval-form:
	./scripts/run_prime_eval_android_adk.sh

prime-eval-ride:
	PRIME_ANDROID_TASKSET=ride ./scripts/run_prime_eval_android_adk.sh

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
	  --output "artifacts/benchmarks/proof"

benchmark-quick:
	./scripts/run_proof_benchmark.sh \
	  --backend "$${ROLLOUT_BACKEND:-adb}" \
	  --policy scripted \
	  --attempts-per-instance "$${BENCHMARK_ATTEMPTS_QUICK:-4}" \
	  --pass-k 1 2 3 \
	  --max-steps "$${BENCHMARK_MAX_STEPS:-12}" \
	  --bootstrap-samples "$${BENCHMARK_BOOTSTRAP_SAMPLES:-0}" \
	  --output "artifacts/benchmarks/proof-quick"

benchmark-release:
	./scripts/run_proof_benchmark.sh \
	  --backend "$${ROLLOUT_BACKEND:-adb}" \
	  --policy scripted \
	  --attempts-per-instance "$${BENCHMARK_ATTEMPTS_RELEASE:-20}" \
	  --pass-k 1 2 5 10 \
	  --max-steps "$${BENCHMARK_MAX_STEPS:-12}" \
	  --bootstrap-samples "$${BENCHMARK_BOOTSTRAP_SAMPLES:-0}" \
	  --output "artifacts/benchmarks/release"

docker-build:
	docker compose -f docker-compose.yml build

docker-test:
	docker compose -f docker-compose.yml run --rm mobile-rl-runner make test

docker-run:
	docker compose -f docker-compose.yml run --rm mobile-rl-runner make run

docker-real-adb-smoke:
	bash ./scripts/docker_real_adb_openai_rollout.sh

clean:
	rm -rf artifacts/runs/*
