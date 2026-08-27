# Global Verifiers Set 2 — Validation Report

Date: 2026-08-27

## Scope and hard boundary

The package contains exactly ten task-independent Python modules. No Python
module contains `portable-adder`, Bank Account, Crypto Square, or another task's
API or semantic behavior. All example-specific facts live under
`task_bundle_example/` as authenticated data assets.

## Validation cycles

| Cycle | Result | Finding | Repair |
|---:|---:|---|---|
| 1 | 2 passed, 6 failed | Placeholder protected-asset digests failed closed at manifest loading | Replaced placeholders with SHA-256 ledger |
| 2 | 3 passed, 5 failed | G01 detected fixture bytes changed after initial ledger generation | Recomputed and pinned the observed immutable bytes |
| 3 | 2 passed, 6 failed | Strengthened manifest loader required `api.contract`; example manifest omitted the pointer | Added `api.contract: public_api.json` after the final allowed run |

The third result is intentionally preserved. Per the run instruction, no fourth
validation execution was performed. The final manifest repair is therefore
code-reviewed but not rerun, and this package must not be described as having a
passing canary until a later validation run confirms it.

## Implemented controls

- Baseline-aware Aider reconstruction with returned/inherited file receipts.
- G01 protected-asset and path-boundary authentication.
- Dependency preflight with evaluator failures classified `INVALID`.
- G02 translation-unit compilation with compile/warning reason codes.
- G03 Clang-AST declaration matching and separate trusted-caller linking.
- G04 authenticated functional execution with test fraction receipts.
- Optional G05 ASan/UBSan diagnostic.
- Optional G07 GCC/Clang portability diagnostic.
- Strict G01 → G02 → G03 → G04 prerequisites and `NOT_RUN` downstream states.
- Hash-bound final receipts and Docker/host execution adapters.

## Promotion status

Implementation: complete. Validation: **not passing as last executed**. Do not
use this report as evidence of production readiness; rerun the focused suite and
task-by-task shadow parity before connecting Set 2 to paid GRPO rewards.
