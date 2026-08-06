# Printer V1 V2-9.8B WINDOW_15M Checkpoint 4 — Holder Budget, Evidence, and Two-Token Admission Closeout

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_4_HOLDER_BUDGET_EVIDENCE_TWO_TOKEN_ADMISSION_PASS`

Checkpoint 4 is complete on baseline `af4503b8f175b556129516a7770fb1c3f9df6906` and branch `agent/v2-9-8b-window-15m-checkpoint-4-holder-budget-evidence-two-token-admission`.

This checkpoint changed documentation only. No production or test file was modified.

Checkpoint 5 is not started.

## Audit result

The ordinary WINDOW_15M holder/admission path was inspected from exact pre-holder request/transport reconciliation through holder budgeting, pacing, maturation, source execution, measured transport ownership, durable evidence, holder-stage sealing, permanent memory-observation admission, and exact two-token freeze/readiness.

No new reachable deterministic production defect was found.

The current binding contract remains:

- valid market/protocol candidates may remain `MEMORY_OBSERVATION_ELIGIBLE` with holder pass, fail, unavailable, or budget-bound unknown context;
- only a clean actual holder pass may create `FULLY_ELIGIBLE`;
- holder work cannot truncate the otherwise valid memory-observation universe;
- future-action eligibility remains blocked or unknown unless its later explicit lane passes.

## Existing contracts confirmed

- Exact pre-holder `M = C = A` reconciliation requires canonical identity-set equality, not count equality.
- Permanent limits remain `45` total operations, `9` zero-transport validation charge, `2 + 4` snapshot reservations, `5` worst-case per holder attempt, and `8` holder-stage transports.
- Permanent observation admission does not consult the holder-derived candidate cap.
- Sequential pacing remains synchronous and adds no retry, recursion, endpoint rotation, reconnect, or successor.
- Holder transport identities fan out to action-local and campaign ownership and seal one conditional `HOLDER_SAFETY` stage.
- Partial source or persistence failure retains already-created governed request evidence and blocks accounting rather than disappearing.
- Typed source-specific temporal authority fails closed before holder work; no zero or invented candidate time is accepted.
- Holder failures are distinguished from missing or contradictory accounting.
- The four-candidate freeze remains neutral and produces exactly two selected memory candidates plus alternates.

## Proof history and classification

### First focused proof

The first broad historical suite produced `117 passed, 17 failed`.

The failures were classified as superseded fixture contracts, not production defects:

1. older manifest fixtures declared positive transport counts without exact `transport_identity_keys`;
2. older holder fixtures passed untyped `SimpleNamespace(..., block_time=0)` candidates.

Relaxing production to satisfy either fixture would weaken adopted exact-accounting and temporal-authority repairs. No production change was approved.

### Corrected current-contract proof

At commit `36c6112ec0c2aed344ba98fecca22bdcd7012c30`:

- syntax and constants passed;
- `117` current-contract tests passed;
- lawful holder-budget exhaustion probe passed;
- exact holder stage-seal probe passed;
- partial holder persistence probe passed.

A final reconciliation assertion failed because the probe expected one category where two exact set relations were deliberately broken. The shell then printed a false PASS marker because the Python block was not chained with `&&`. That marker was rejected and not used as completion evidence.

### Strict final proof

At commit `7be121b87eed07b2d4eb2584c57aeee3e17b9479`, a strict `set -euo pipefail` disposable proof established:

- exact proof head matched;
- a stage-reported and manifested request absent from durable storage correctly returned `MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS`;
- exact categories were `STAGE_REQUEST_NOT_DURABLE` and `MANIFEST_REQUEST_NOT_DURABLE`;
- exact transport identity validation remained clean;
- `git diff --check` passed;
- the disposable worktree was clean;
- terminal marker: `CHECKPOINT4_STRICT_FINAL_PROOF_PASS`.

## Money-usefulness contribution

Checkpoint 4 protects future paper-only memory quality by preserving exact source-operation ownership, retaining truthful holder uncertainty, and preventing holder availability from deleting otherwise useful clean market observations. It improves evidence reliability without creating a trade signal or financial action.

## What this checkpoint improves

- consolidated confidence in the current holder/admission boundary;
- exact separation of observation eligibility from action eligibility;
- exact holder request, transport, persistence, and campaign-stage evidence;
- truthful budget-bound unknown handling;
- rejection of stale test expectations without weakening production safety.

## What this checkpoint does not unlock

This checkpoint does not unlock or run:

- providers, Printer, or one-command runtime;
- authorization creation or consumption;
- authoritative database mutation;
- Scheduler or lifecycle runtime;
- memory generation or retrieval;
- paper BUY/SELL/HOLD decisions;
- positions, trade events, paper trade audits, or PnL;
- `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H`;
- Checkpoint 5.

All Solana-only, Solana-memecoin-only, paper-only, Source Governor, Central Scheduler, no-paid-API, no-scoring/ranking/confidence/weighting, no-wallet, no-key, and no-real-funds locks remain unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- Live provider availability, candidate sufficiency, and holder-evidence completeness remain runtime conditions, not statically provable guarantees.
- Provider-index maturation remains intentionally `UNPROVEN_DISABLED` rather than guessed.
- Historical tests from earlier repair eras may remain stale relative to exact identity and typed temporal contracts; they must be classified rather than used to weaken current safety.
- Shell proof scripts must use strict failure propagation so a terminal PASS marker cannot print after an assertion failure.
- No broader regression suite was required because production was unchanged and the current-contract holder/admission boundary received focused proof.

## Completion boundary

Checkpoint 4 closes only holder budget, holder evidence/accounting, and two-token memory admission. Any Checkpoint 5 work requires its own audit/readiness review and explicit authorization.