# Printer V1 V2-9.8B WINDOW_15M Checkpoint 4 — Current-Contract Proof Follow-up Analysis

## Status

`V2_9_8B_WINDOW_15M_CHECKPOINT_4_CURRENT_CONTRACT_PROOF_PARTIAL_PASS_WITH_STALE_SINGLE_CATEGORY_ASSERTION`

This document records the second focused proof result. It does not approve a production change and does not close Checkpoint 4.

- Baseline: `af4503b8f175b556129516a7770fb1c3f9df6906`
- Proof head: `36c6112ec0c2aed344ba98fecca22bdcd7012c30`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-4-holder-budget-evidence-two-token-admission`
- Linear: `DTW-30`
- Provider contact: none
- Printer/runtime: none
- Authorization: none
- Authoritative database: not accessed or mutated

Checkpoint 5 remains locked.

## Evidence that passed

At the exact proof head:

- syntax/current-contract constants passed;
- the superseding current-contract suite passed: `117 passed in 13.59s`;
- lawful positive-time holder-budget probe passed;
- exact measured holder stage-seal probe passed;
- partial holder persistence probe passed;
- baseline-to-head diff check completed;
- disposable worktree was clean.

## Remaining assertion

The final reconciliation probe created this deliberate state:

- stage-reported request IDs: `{777}`;
- coverage manifest request IDs: `{777}`;
- durable request IDs: `{}`.

The probe expected the single category `STAGE_REPORTED_REQUEST_NOT_DURABLE`.

That expectation is incomplete under the current exact three-set reconciliation contract. The same state violates two independent relations:

1. stage-reported ID `777` is not durable;
2. manifest ID `777` is not durable.

The current classifier therefore correctly reports:

- `STAGE_REQUEST_NOT_DURABLE`;
- `MANIFEST_REQUEST_NOT_DURABLE`;
- aggregate categorical detail `MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS`.

This is not a holder/admission production defect. Changing production to collapse the two relations into one would reduce diagnostic precision and weaken the adopted exact reconciliation contract.

## Shell-marker issue

The proof script did not connect the Python probe block to the next command with `&&`, and did not start the subshell with `set -e`. Therefore the Python `AssertionError` did not stop later diff/status commands or the final printed marker.

`CHECKPOINT4_CORRECTED_CURRENT_CONTRACT_PROOF_PASS` from that execution is invalid and must not be used as completion evidence.

## Correct next proof

Run one minimal strict-shell disposable proof that:

- starts with `set -euo pipefail`;
- checks exact head;
- reproduces the three-set state;
- requires the two exact mismatch categories in deterministic order;
- requires aggregate `MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS`;
- requires no transport-identity blocker;
- performs diff and clean-worktree checks;
- prints the final PASS marker only after every assertion succeeds.

## Decision

No production or test-file modification is approved. The existing production behavior is consistent with the current exact reconciliation contract. Checkpoint 4 remains open only for the strict final proof and closeout.
