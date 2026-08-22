# Policy 4: Free-operator contract

Three failed trials implemented free operators by reading private or stale member names. This policy compiles and runs the externally visible equality, stream, and scalar-operator surface so valid implementations must use a legal access path.

| Kernel | Binary pass condition | Evidence |
|---|---|---|
| 4A | Equality and stream insertion compile, link, and expose the expected component values. | Probe compile/run logs and hashes |
| 4B | Addition and subtraction work with the scalar on either side. | Probe compile/run logs and hashes |
| 4C | Multiplication and division work with the scalar on either side. | Probe compile/run logs and hashes |

No private field name or friendship layout is required. A candidate may use public observers, friends, or another valid design, but every declared free operator must compile and behave correctly.

Each group returns `+1/-1`; evaluator failures remain `INVALID`.

## Run

    python3 verifiers/verifier_04_free_operator_contract.py --exercise-dir TASK --output-dir NEW_EMPTY_DIR
