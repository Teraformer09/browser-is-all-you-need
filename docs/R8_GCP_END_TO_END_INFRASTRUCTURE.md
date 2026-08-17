# R8 GCP end-to-end infrastructure and file map

## Purpose and claim boundary

This document explains the complete repository-controlled path used to launch,
run, persist, and evaluate the R8 GLM-4.7-Flash GRPO experiment on one GCP
`a3-highgpu-8g` VM. It maps each infrastructure stage to the files that own it,
the data entering and leaving that stage, and the conditions that stop it.

The documented successful training execution is managed Job 22, durable attempt
`unadmitted-r8-r87-run21-20260814T030808Z-attempt-20260814T031719Z-d951d40e`.
It completed six optimizer updates and checkpoints `iter_0000000` through
`iter_0000005`. Managed Job 30 evaluated the final checkpoint with the raw
fixed-26 prompts.

Execution success is not CHARM admission. The R8 profile is
`UNADMITTED_EXPERIMENT_ONLY`, its checkpoints are `QUARANTINE_ONLY`, and it is
not eligible for retroactive promotion. The fixed-26 suite is evaluation-only
and is never part of training data, reward computation, or task selection.

## What “end to end” means here

The repository controls:

1. immutable profile and source validation;
2. source transport construction;
3. SkyPilot VM request and teardown policy;
4. model, adapter, runtime, and result mounts;
5. host GPU and Docker validation;
6. immutable training and verifier image selection;
7. HF-to-Megatron reference-checkpoint conversion;
8. runtime schedule projection and reward preflight;
9. Miles/SGLang GRPO execution and GLM compatibility patches;
10. isolated C++ reward verification and pre-optimizer signal validation;
11. LoRA updates and checkpoint creation;
12. periodic artifacts, marker-last checkpoints, and terminal receipts in GCS;
13. final-checkpoint fixed-26 evaluation on a separate SkyPilot VM; and
14. regression tests for the static contracts above.

The repository does **not** create the GCP project, service accounts, IAM
bindings, quota, buckets, or Artifact Registry repositories. It also does not
contain credentials, model weights, private task trees, verifier controls,
checkpoint binaries, or W&B runtime state. Those are external prerequisites
bound by paths and digests.

## End-to-end flow

```text
operator
  |
  | cost authorization + RUN_ID
  v
R8 submitter
  |-- validates profile and frozen assets
  |-- builds a source-bound /tmp transport
  v
SkyPilot managed job
  |-- provisions 8xH100 Spot VM
  |-- copies model + SFT adapter + private runtime from GCS
  |-- mounts durable result bucket
  v
host setup
  |-- validates H100 inventory, driver, Docker, NVIDIA runtime, storage
  |-- pulls immutable training and verifier images
  v
attempt runner
  |-- inspect -> render -> host-check -> prepare -> train
  |-- writes stage records and failure evidence
  v
prepare stage
  |-- validates assets and image/Miles contracts
  |-- runs reward/no-update preflights
  |-- converts HF model to TP4/PP1/EP8 torch-dist reference checkpoint
  v
training stage
  |-- projects 40 tasks into 3 epochs / 120 rows
  |-- starts Miles trainer + colocated SGLang
  |-- generates 20 groups x 8 samples per update
  |-- verifies samples in network-isolated C++ containers
  |-- validates batch signal, computes GRPO, updates LoRA
  |-- evaluates development rows and writes one checkpoint per update
  v
durable publisher
  |-- syncs receipts and completed rollouts every 60 seconds
  |-- publishes only stable, complete 8-shard checkpoints
  |-- uploads COMPLETE.json last
  |-- requires final sync + two consecutive successful receipts
  v
Job 22 terminal execution receipt: PASS
  |
  | final adapter iter_0000005
  v
Job 30 fixed-26 SkyPilot evaluator
  |-- starts two SGLang shards
  |-- runs two attempts on 26 evaluation-only tasks
  |-- validates and syncs the evaluation receipt
  v
pass@1 0/26, pass@2 4/26, well formed 26/26
```

## Stage 0 — external cloud prerequisites

These requirements must exist before repository code can launch a VM:

| Requirement | Expected value or capability | Repository behavior |
| --- | --- | --- |
| GCP project | `lifeandhalf-24122025` | Read from the frozen profile; not created here. |
| Compute quota | One `a3-highgpu-8g` / eight H100 GPUs in `us-central1` | SkyPilot requests capacity; lack of quota or capacity blocks provisioning. |
| Service account | Compute, GCS read/write, Artifact Registry pull | VM uses its metadata identity; no key is stored in the repository. |
| Asset bucket | `gs://lifeandhalf-24122025-w8-biayn` | Supplies model, adapter, private runtime, checkpoints, and durable results. |
| Artifact Registry | Immutable training and verifier image digests | The driver rejects mutable or mismatched image references. |
| Local control plane | `sky`, `gcloud`, Git, Python dependencies | The submitter fails before requesting GPUs when preflight is incomplete. |

There is no Terraform, Deployment Manager, or equivalent project/IAM bootstrap
in this branch. Reviewers evaluating portability must treat that as an explicit
gap rather than assuming a fresh GCP project can launch the pipeline directly.

## Stage 1 — immutable configuration and asset publication

### Files

| File | Responsibility | Inputs | Outputs / failure boundary |
| --- | --- | --- | --- |
| `configs/full_v5_charm_grpo/gcp-r8-unadmitted-hybrid45-exact40-r87-skypilot.json` | Machine-readable source of truth for GCP shape, immutable assets, TP/PP/EP topology, GRPO hyperparameters, reward policy, result destination, and quarantine semantics. | Frozen digests, GCS paths, schedule counts, policy identities. | Loaded by every local and VM-stage command. Schema or identity drift fails before training. |
| `configs/full_v5_charm_grpo/r8-effective-source-manifest.json` | Binds the exact implementation files transported into the job. | Repository files selected by the effective-source collector. | Per-file SHA-256, manifest SHA-256, and source-set SHA-256. Missing, extra, backup, or changed files invalidate the profile. |
| `src/glm47_posttraining/aider_polyglot/effective_source.py` | Collects and validates the R8 effective source set. | Repository root and manifest policy. | Deterministic inventory; excludes `.orig`, `.rej`, caches, and unrelated runtime material. |
| `scripts/gcp_full_v5_charm_r8_publish_assets.py` | Administrative publication gate for the private runtime and immutable images. It is not executed for every training run. | Explicit publication authorization, local image, private runtime, expected digests. | Verifies remote bytes, writes publication receipts, and narrowly updates profile asset status. It does not launch compute. |
| `docker/full-v5-charm-grpo-gcp/Dockerfile` | Builds the training image on the pinned Miles base and installs the aligned FlashInfer/SGLang/TMS/libclang runtime. | Repository integrations, runners, dataset configuration, pinned build arguments and Miles source hashes. | Immutable training image. Build fails if package or Miles contract checks drift. |
| `docker/full-v5-charm-grpo-gcp/Verifier.Dockerfile` | Builds the network-isolated C++ verifier image with GCC 13 and Clang 18. | Pinned compiler base images. | Verifier image used by reward workers; no model or private task data is embedded. |
| `scripts/gcp_full_v5_runtime_build_stage.sh` | Older source-first helper for building and staging an independently produced Full-V5 runtime. | An owner-controlled producer checkout and verified source trees. | Verified runtime bundle and GCS round-trip evidence. It is not the Job 22 launch entry point and does not provision GPUs. |

### Effective Job 22 hyperparameters

| Setting | Value |
| --- | ---: |
| Hardware | 8 x H100 80 GB |
| Trainer topology | TP4 / PP1 / CP1 / EP8 / ETP1 |
| SGLang data parallelism | 8 |
| LoRA rank / alpha | 16 / 32 |
| Updates / epochs | 6 / 3 |
| Training targets | 40 |
| Prompts per update | 20 |
| Samples per prompt | 8 |
| Global batch | 160 |
| Learning rate | `5e-7` |
| KL coefficient | `0.02` with reference model enabled |
| Temperature | `0.7` |
| Prompt / response limits | 2,048 / 16,384 tokens |
| Packed sequence length | 34,816 tokens |
| Maximum tokens per GPU | 18,432 |
| Development targets / interval | 11 / update 6 |
| Checkpoint interval | Every update |

The profile label contains `dp8` because the rollout serving topology is DP8;
the trainer parallelism must be read from the explicit `parallelism` object,
not inferred from that label.

## Stage 2 — local submission and frozen transport

### `scripts/gcp_full_v5_charm_r8_unadmitted_skypilot_submit.sh`

This is the operator entry point. It:

1. validates the run-ID prefix and optional one-update mode;
2. requires the exact explicit 8xH100 cost authorization;
3. runs driver `inspect` and `render` locally;
4. verifies that training image, verifier image, and private runtime are marked
   available and bound to immutable digests;
5. checks that the private runtime manifest exists in GCS;
6. creates a fresh transport root under `/tmp` so SkyPilot does not traverse
   parent worktree metadata;
7. invokes `scripts/build_r8_skypilot_workdir.py`; and
8. launches a managed job with `sky jobs launch`.

No GPU is requested if authorization, profile, source, or asset validation
fails.

### `scripts/build_r8_skypilot_workdir.py`

The builder turns the effective-source manifest into a deterministic frozen
workdir archive and a rewritten transport task. It records the archive digest,
source identity, boot image, host Python dependencies, and task bytes in
`r8-skypilot-transport-receipt.json`. The generated task unpacks the frozen
archive on the worker rather than depending on a Git checkout.

This prevents an edited local file from being silently omitted from the paid
run and prevents repair code from existing locally but not inside the remote
job.

### `.skyignore`

Excludes local results, caches, checkpoints, credentials, private runtime
trees, and other non-source material from SkyPilot workdir scanning.

## Stage 3 — VM provisioning and mounts

### `grpo_h100_full_v5_charm_r8_unadmitted.yaml`

The generated transport retains the resource and mount contract from this
task:

- cloud and region: GCP, `us-central1`;
- machine: `a3-highgpu-8g`, eight H100 GPUs;
- storage: 500 GB high-tier boot disk;
- lifecycle: Spot, `FAILOVER`, zero application-error restarts, autostop and
  cluster teardown after ten idle minutes;
- model mount: pinned GLM-4.7-Flash GCS tree;
- warm-start mount: SynthMem v1 epoch-50 LoRA adapter;
- runtime mount: private, receipt-bound R8 task/reward runtime;
- result mount: durable GCS bucket; and
- run command: the attempt-isolated R8 SkyPilot runner.

SkyPilot `FAILOVER` can provision another VM after infrastructure loss, but the
application has no mid-run checkpoint-resume entry point. A replacement
attempt starts from the original SFT adapter, receives a new attempt ID, and
must not be described as resuming the previous optimizer state.

### `scripts/gcp_h100_host_setup.sh`

This idempotent setup script validates or installs the NVIDIA container
runtime, verifies the Docker daemon, confirms the requested GPU count/model and
minimum memory, and leaves the worker ready for GPU containers. The task then
uses the VM service-account token for immediate immutable registry pulls; the
short-lived token is not written into repository files.

## Stage 4 — attempt isolation and stage control

### `scripts/gcp_full_v5_charm_r8_unadmitted_skypilot.sh`

The VM runner creates a unique attempt ID beneath the operator-supplied base
run ID. It never reuses a result root. It executes five visible stages:

| Stage | Driver command | Primary evidence |
| --- | --- | --- |
| `inspect` | `gcp_full_v5_charm_grpo.py inspect` | Resolved profile, paths, metadata, GPU inventory, gates. |
| `render` | `... render --phase experimental` | Exact container command and environment without launching training. |
| `host-check` | `... host-check` | H100, Docker, disk, and provisioning validation. |
| `prepare` | `... prepare --prebuilt-images` | Image, reward, Miles, adapter, and converted-checkpoint receipt. |
| `train` | `... train --phase experimental` | Launch contract, checkpoints, sync receipts, and execution receipt. |

For every stage the runner writes started/passed/failed records, streams the
logs, copies control artifacts into durable storage, and preserves the last
stage and exit code on termination. This is why a generic SkyPilot return code
can still be traced to a precise application boundary.

## Stage 5 — central orchestration and preparation

### `scripts/gcp_full_v5_charm_grpo.py`

This is the infrastructure control plane inside the worker.

#### Configuration and host validation

- `load_config()` resolves the base/overlay profile and enforces profile
  invariants.
- `require_h100()` reads `nvidia-smi` and rejects the wrong count, model, or
  memory.
- `require_provisioning_policy()` compares expected provisioning with instance
  metadata when the profile requires it.
- `exclusive_gpu_job()` prevents two GPU-heavy preparation or training jobs
  from sharing the host.
- `verify_assets()` verifies model, adapter, runtime, manifests, and the
  converted reference checkpoint.

#### Preparation

`prepare()` either builds images or, in the R8 SkyPilot path, pulls the exact
immutable registry references and verifies their observed digests. It then:

1. runs the pinned Miles GRPO advantage contract with zero optimizer updates;
2. runs reward/runtime preflight in the training image;
3. runs the Hybrid45 no-update canary and validates its receipt;
4. converts the HF model into the TP4/PP1/EP8 torch-distributed reference
   checkpoint if its marker is absent; and
5. writes `preparation-receipt.json` binding source, config, assets, GPUs,
   images, reward receipt, and trainer-contract receipt.

### Checkpoint conversion files

| File | Role |
| --- | --- |
| `scripts/convert_checkpoint.sh` | Container entry point for distributed HF-to-Megatron conversion. |
| `src/glm47_posttraining/integrations/miles_convert_with_glm47_bridge.py` | Registers GLM mappings and safely handles the pinned Miles PP1 converter behavior before executing it. |
| `configs/miles/glm4.7-flash.sh` | Compatibility adapter for Miles model arguments after Miles moved the model definition from shell to Python. |

## Stage 6 — schedule, environment, and container launch

Inside `train()`, the driver:

1. rechecks authorization and quarantine semantics;
2. validates H100s, assets, disk policy, and unique result root;
3. projects the private runtime into the exact 40-task, 3-epoch, 120-row
   schedule with 11 disjoint development targets;
4. builds the complete environment from the frozen profile;
5. writes `launch-contract.json` before starting the container;
6. starts periodic GCS synchronization; and
7. runs the immutable training image with model, adapter, results, Docker
   socket, and Miles model-argument compatibility mounts.

### Runtime entry files

| File | Responsibility |
| --- | --- |
| `examples/grpo.sh` | Converts environment values into Miles topology, batching, SGLang, LoRA, reward, W&B, and checkpoint arguments. Prepares the hybrid adapter and calls the generic trainer wrapper. |
| `scripts/check_runtime.py` | Verifies the live CUDA-aligned FlashInfer, SGLang kernel, and TMS package family before training. |
| `scripts/prepare_grpo_adapter.py` | Strips MTP tensors from the serving view, validates the source adapter, and preserves the complete EP-aware native training state. |
| `scripts/train_grpo.sh` | Builds the final Miles command line, starts Ray/Miles, and records runtime/checkpoint evidence. |
| `src/glm47_posttraining/integrations/miles_train_with_glm47_bridge.py` | Installs compatibility hooks and then executes the pinned `/root/miles/train.py`. |
| `src/glm47_posttraining/integrations/miles_glm47_bridge.py` | Owns GLM model registration, conversion mappings, EP-aware LoRA state, optimizer warm start, TMS sleep/wake, DP reward alignment, router fixes, and SGLang LoRA synchronization. |

The bridge contains the compatibility repairs proven across Jobs 7–22. It is
part of the immutable training image, not a host-side monkey patch.

## Stage 7 — reward verification and optimizer gate

### Data and reward files

| File | Responsibility |
| --- | --- |
| `src/glm47_posttraining/aider_polyglot/full_v5_charm.py` | Projects the private runtime into the exact train/development schedule and verifies counts and identities. |
| `src/glm47_posttraining/integrations/miles_aider_polyglot.py` | Miles-facing dataset builder, parallel reward entry point, response-contract preflight, and pre-optimizer batch validator. |
| `src/glm47_posttraining/aider_polyglot/hybrid45.py` | Hybrid bipolar reward policy and receipt validation. |
| `src/glm47_posttraining/aider_polyglot/policy45.py` | Shared 45-check policy primitives and versioned scoring contract. |
| `src/glm47_posttraining/aider_polyglot/ast_evaluator.py` | Clang-backed public-API and AST evidence. |
| `src/glm47_posttraining/aider_polyglot/public_api_manifest.py` | Exact case-sensitive public-API contract representation. |
| `src/glm47_posttraining/aider_polyglot/prompt_preflight.py` | Prompt-length, response-contract, and tokenizer-bound checks. |
| `src/glm47_posttraining/aider_polyglot/rollout_receipts.py` | Per-sample context-isolation and verifier-workspace receipts. |
| `src/glm47_posttraining/aider_polyglot/grpo_advantage_contract.py` | Proves the pinned Miles group-local GRPO advantage behavior before training. |

Each candidate is evaluated in an isolated verifier workspace using the
network-disabled verifier image. Compile, tests, sanitizers, API checks, and
receipt integrity produce the reward evidence. An ordinary bad model response
receives its policy score; an infrastructure failure raises and aborts rather
than being misreported as a model reward.

Before optimization, `validate_aider_rollout_batch()` verifies:

- exactly 20 unique logical groups and eight samples per group;
- context-isolated workspace and response receipts;
- finite and policy-consistent rewards;
- at least one positive group;
- at least two semantic-, reward-, and kernel-variance groups;
- exact-format rate at least 0.50; and
- compile rate at least 0.20.

Job 22 passed this gate for every update. These thresholds are training signal
requirements, not fixed-26 evaluation thresholds.

## Stage 8 — optimizer update, LoRA refresh, and checkpoint

Miles owns forward/backward, KL loss, gradient reduction, and optimizer
execution. The repository bridge owns the GLM-specific boundaries around it:

1. warm-start LoRA and optimizer master parameters are restored from all
   expected EP-native shards;
2. the trainer produces an updated rank-16 adapter;
3. MTP-only tensors are excluded from the serving payload;
4. process groups and TMS state are transitioned in the correct order;
5. updated LoRA weights are pushed into colocated SGLang; and
6. one complete adapter/training-state checkpoint is written per update.

Job 19 proved the first optimizer and checkpoint boundary but failed during a
later SGLang memory-resume transition. Job 22 used the resident-trainer path
and completed all six cycles.

## Stage 9 — durable result and checkpoint publication

The durable-sync implementation lives in
`scripts/gcp_full_v5_charm_grpo.py`:

- `_sync_result_tree()` publishes nonvolatile logs, receipts, rollout dumps,
  and metrics while excluding runtime temp state, W&B state, and incomplete
  checkpoints;
- `_checkpoint_file_stats()` requires nonempty PEFT files, the exact eight
  EP-native adapter shards, the exact eight training-state shards, no symlinks,
  no temporary files, and no empty files;
- `_publish_complete_checkpoints()` observes a stable checkpoint twice,
  computes a content manifest, syncs the tree, rechecks that it did not mutate,
  and uploads `COMPLETE.json` last;
- `periodic_result_sync()` performs initial, 60-second periodic, and final
  cycles, recording every success and periodic failure; and
- `train()` requires the Miles success marker, final sync PASS, at least two
  consecutive successful sync receipts, and exactly six published checkpoints
  before writing a terminal execution PASS.

On failure, the driver writes `execution-receipt.json`, attempts a final
artifact sync, and re-raises the original error. A successful GCS sync does not
turn a failed trainer into a successful execution.

## Stage 10 — fixed-26 evaluation of Job 22

### `aider_fixed26_r8_checkpoint_eval.yaml`

This separate SkyPilot task provisions another 8xH100 VM, mounts the base model
and Job 22 `iter_0000005` adapter, installs the pinned Aider benchmark
dependencies, checks out exact Aider and Polyglot revisions, pulls the exact
training image used by Job 22, runs the evaluator, and synchronizes its receipt
and benchmark outputs to GCS on both success and failure.

Important reproducibility boundary: `~/fixed26-eval-code` is currently copied
from the frozen GCS transport
`gs://lifeandhalf-24122025-w8-biayn/transports/aider-fixed26-r19-iter0-20260814`.
The evaluator implementation is also tracked at
`examples/lium/aider_fixed26_eval.py`, but the YAML does not currently build a
new source-bound evaluation transport from the checked-out PR branch. A
reviewer can audit and rerun the historical Job 30 configuration in the
authorized project, but a branch-local evaluation-transport builder is still
needed before claiming that a fresh PR revision is evaluated end to end.

### `examples/lium/aider_fixed26_eval.py`

The evaluator:

1. validates model, adapter, data-manifest, and benchmark revisions;
2. creates a serving adapter with 207 MTP tensors removed;
3. splits the 26 tasks into two shards;
4. starts two SGLang servers on ports 18000 and 18001;
5. loads the final LoRA adapter into each server;
6. runs the pinned whole-edit benchmark with two attempts per task;
7. validates task coverage and result structure; and
8. writes a digest-bound `run_receipt.json`.

Job 30 completed with pass@1 `0/26`, pass@2 `4/26`, and `26/26` well-formed
outputs. Attempt-two passes were `allergies`, `complex-numbers`, `knapsack`,
and `space-age`. Because Job 30 used raw prompts while the historical SFT
trials used a prompt overlay, this is execution evidence rather than matched
uplift evidence.

## Separate SFT/base evaluation path

These files are related but are not the Job 22 fixed-26 launcher:

| File | Responsibility |
| --- | --- |
| `eval_h100_v8.yaml` | Provisions an on-demand 8xH100 VM for the SynthMem/SFT evaluation profile. |
| `scripts/gcp_public_pr_eval_host_setup.sh` | Installs and validates the host packages for that evaluation lane. |
| `scripts/gcp_public_pr_eval_run.sh` | Builds or pulls the evaluation image, mounts persistent results, and invokes the evaluator. |
| `scripts/gcp_public_pr_synthmem_50ep_eval.py` | Runs the public-PR evaluation and writes its receipt/diagnostic report. |
| `docker/public-pr-synthmem-v1-ep50-gcp/Dockerfile*` | Builds the verified evaluator and its runtime overlay. |

Keeping this lane separate prevents the Job 22 checkpoint evaluation from
being confused with the historical SFT baseline or its prompt overlay.

## Stage 11 — tests and what they prove

| Test file | Covered infrastructure contract |
| --- | --- |
| `tests/test_effective_source.py` | Source-manifest collection and backup-file exclusion. |
| `tests/test_gcp_charm_r8_unadmitted_skypilot.py` | Quarantine profile, exact schedule, one-update shape, Spot task, attempt isolation, transport, stage failure persistence, and cost authorization. |
| `tests/test_gcp_charm_r8_asset_publication.py` | Non-compute publication behavior, runtime inventory, authorization, atomic profile update, and remote identity verification. |
| `tests/test_gcp_full_v5_charm_grpo.py` | GCP-only profile, admission controls, image contents, asset validation, periodic synchronization, stable checkpoint publication, incomplete checkpoint rejection, and terminal sync receipts. |
| `tests/test_glm47_h100.py` | H100 runners, package alignment, adapter preparation, converter, Miles bridge, SGLang/TMS lifecycle, weight refresh, DP reward alignment, and fixed-26 evaluator pins. |
| `tests/test_public_pr_eval_skypilot.py` | Separate SFT/base evaluation VM topology, container overlay, runtime arguments, and result mounts. |

These are deterministic local contract tests. They do not provision a paid VM
and cannot prove GCP capacity, live IAM, registry availability, NCCL health, or
the behavior of a newly changed image. Job 22 and Job 30 are the live evidence
for the exact historical digests documented here.

## Operator commands

### Local contract validation

```bash
python3 -m pytest -q \
  tests/test_effective_source.py \
  tests/test_gcp_charm_r8_unadmitted_skypilot.py \
  tests/test_gcp_charm_r8_asset_publication.py \
  tests/test_gcp_full_v5_charm_grpo.py \
  tests/test_glm47_h100.py \
  tests/test_public_pr_eval_skypilot.py
```

### Launch the six-update unadmitted R8 job

```bash
export GLM47_CHARM_R8_UNADMITTED_FULL_AUTHORIZATION='I_AUTHORIZE_UNADMITTED_R8_HYBRID45_EXACT40_6_UPDATE_EXPERIMENT_AND_GCP_COSTS'
RUN_ID="unadmitted-r8-r87-$(date -u +%Y%m%dT%H%M%SZ)"
bash scripts/gcp_full_v5_charm_r8_unadmitted_skypilot_submit.sh "${RUN_ID}"
```

### Follow managed-job logs

```bash
sky jobs logs -n "${RUN_ID}" --follow --tail 2000
sky jobs logs -n "${RUN_ID}" --controller --no-follow --tail 2000
```

### Launch the Job 22 final-checkpoint evaluator

```bash
EVAL_RUN_ID="job22-iter5-fixed26-$(date -u +%Y%m%dT%H%M%SZ)"
sky jobs launch \
  --name "${EVAL_RUN_ID}" \
  --detach-run \
  --yes \
  --env "EVAL_RUN_ID=${EVAL_RUN_ID}" \
  aider_fixed26_r8_checkpoint_eval.yaml
```

The evaluation command reuses the historical frozen GCS code transport noted
above. Do not present it as validation of new evaluator-code changes until a
branch-local transport is added and bound by digest.

## Result and incident documentation

| File | Meaning |
| --- | --- |
| `docs/r8-grpo-result-2026-08-14.md` | Concise Job 19, Job 22, hyperparameter, checkpoint, and Job 30 result report. |
| `docs/aider-job22-iter5-fixed26-eval-2026-08-14.md` | Detailed Job 30 fixed-26 receipt and SFT comparison boundary. |
| `docs/r8-skypilot-run-issues-2026-08-13.md` | Chronological failure/remediation ledger from the first preflight through Job 30. |
| `docs/GCP_FULL_V5_CHARM_GRPO.md` | Earlier manual-VM production/admission workflow; not the successful unadmitted Job 22 launch path. |
| `docs/GCP_FULL_V5_CHARM_SKYPILOT.md` | Earlier SkyPilot smoke/canary guide; useful background but not a complete Job 22 file map. |
| `docs/GCP_FULL_V5_RUNTIME_BUILD_STAGE.md` | Source-first runtime build/staging guide; it intentionally does not provision a VM. |

## Known infrastructure gaps

1. **No cloud bootstrap IaC.** Project, IAM, quota, buckets, registry, and
   service-account configuration remain external.
2. **No application-level Spot resume.** SkyPilot failover creates a fresh
   attempt from the starting adapter; it does not resume the most recent
   durable optimizer checkpoint.
3. **Fixed-26 code transport is historical.** The Job 30 YAML consumes a
   frozen GCS code bundle rather than rebuilding from the current branch.
4. **W&B is offline and excluded from GCS synchronization.** Durable receipts
   and metric artifacts, not the local W&B directory, are the primary evidence.
5. **External assets are access-controlled.** A public reviewer can audit the
   bindings but cannot rerun the private runtime or checkpoint without GCS and
   Artifact Registry access.
6. **Local tests are not live-cloud tests.** Any changed image, CUDA dependency,
   or VM configuration needs a new receipt-backed paid run before it inherits
   the Job 22/30 evidence.

These gaps do not invalidate the recorded Job 22 and Job 30 executions. They
define what remains before this infrastructure can be called portable,
fresh-project reproducible, or deployment-certified.
