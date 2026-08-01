# Printer V1 V2-9.8B C1-C15 Independent Read-Only Conformance Review

Date: 2026-08-01

Lane:
`V2-9.8B Post-Repair WINDOW_15M Full-Run Accounting and Terminal-Evidence Independent Read-Only Conformance Review`

Reviewed implementation branch:
`agent/v2-9-8b-c1-c15-full-run-implementation`

Reviewed implementation commit:
`02f872899b1b848d58718e5ee6bc866fb7958607`

Implementation baseline:
`6aab4aa22f81b6e52b7376ad767a47fed121de6f`

Review type: static/read-only review of the implementation diff, implementation report, and focused test sources. No code was changed, no test or runtime command was executed, no provider/source/RPC/WebSocket path was contacted, and no database was opened or mutated.

## Verdict

`CONFORMANCE_REVIEW_BLOCKED`

Block classification:
`BLOCKED_C13_AUTHORIZATION_AND_LEASE_EVIDENCE_FALSE_PASS_PATH`

The implementation makes substantial, credible progress across C1-C15, but the completion law is not satisfied because Campaign PASS remains reachable without actual lease-release evidence, and the claimed invocation-marker hash is not an invocation-marker hash.

A bounded proof is not authorized.

## Review method

The review checked the implementation against:

- the active Printer V1 source stack;
- the approved full-run accounting and terminal-evidence design;
- the final C1-C15 conformance map;
- the accepted Scheduler-ownership schema amendment and migration closeout;
- commit `02f872899b1b848d58718e5ee6bc866fb7958607` and its one-commit diff;
- the changed focused tests and the implementation report's claimed outputs.

Each C item was evaluated using the required chain:

```text
design requirement
-> real execution boundary
-> single-owner evidence
-> independent action-local evidence
-> canonical report field
-> acceptance-gate check
-> negative fail-closed test
```

## Blocking finding F1: lease truth can default to PASS

File:
`src/printer_v1/operator_cli/operational_memory_factory_command.py`

Function:
`_apply_full_run_campaign_acceptance()`

The helper still declares:

```python
lease_released: bool = True
```

This is an acceptance-boundary default, not merely a display default. The helper passes that value into `finalize_full_run_ownership_and_report()`, which records it as terminal safety truth, and the acceptance gate checks only the resulting boolean.

The positive integration test:

`tests/test_v2_9_8b_full_run_wiring_integration.py::test_coordinator_helper_consumes_primitives_and_gates_pass`

calls `_apply_full_run_campaign_acceptance()` without supplying `lease_released`. The test expects and receives `CAMPAIGN_PASS` through the default `True` value.

Therefore the positive proof does not prove actual lease release. It proves that omitted lease evidence is interpreted as released.

This violates:

- C12: no omitted/default-true terminal-safety inputs;
- C13: PASS requires real lease-release truth from the authoritative cleanup owner;
- the completion law's negative-proof column, because missing lease evidence is not independently proven to block.

Required repair:

- remove the default;
- require explicit lease truth from unified cleanup;
- reject `None`, omission, missing cleanup evidence, and non-boolean values;
- add a negative test proving omission cannot reach PASS;
- keep the ordinary coordinator call explicitly wired to the real cleanup result.

## Blocking finding F2: invocation-marker hash is the factory config hash

File:
`src/printer_v1/operator_cli/campaign_full_run_accounting.py`

The report hash is assigned as:

```python
"invocation_marker_sha256": str(
    report["identity"].get("factory_config_hash") or ""
)
```

The gate then checks only that this value has 64 characters.

A factory configuration hash is not an invocation authorization marker, no-rerun marker, or successor-prevention marker. The implementation does not identify the marker owner, marker identity, marker path/row, marker payload, or independently recomputed marker digest at this boundary.

Consequently:

- a 64-character config hash satisfies the gate even when invocation-marker evidence is absent;
- report-only replay can reproduce the same substituted value without proving an invocation marker;
- the report field name materially overstates what the value proves.

This violates:

- C12: canonical report fields must carry the claimed evidence family;
- C13: exact authorization/invocation and marker/hash truth;
- C14: replay must reconstruct the actual marker evidence, not reproduce a semantically substituted hash.

Required repair:

- obtain the actual invocation/no-rerun marker identity from its canonical owner;
- carry marker identity plus canonical payload digest into the final report;
- independently recompute and compare the digest during report-only replay;
- keep `factory_config_hash` as a separate field;
- block on missing marker, wrong marker identity, malformed digest, hash mismatch, duplicate marker, or a config-hash-only substitute.

## Blocking finding F3: invocation count is inferred from binding, not authorization evidence

`_apply_full_run_campaign_acceptance()` derives `authorized_invocation_count` by counting campaign-run rows with a non-null `authoritative_run_id` when no explicit count is supplied.

A campaign-run-to-factory-run bind proves identity linkage. It does not by itself prove that exactly one authorized invocation marker existed, that no retry/restart/resume/successor marker was created, or that the invocation was the one authorized by the operator.

The finalizer separately inspects bound-run count and cleanup booleans, but it still lacks the actual authorization/marker evidence required by C13.

Required repair:

- derive authorization count from the canonical authorization/invocation owner;
- cross-check it against the campaign/factory bind rather than replacing it with the bind count;
- require exactly one matching authorization identity;
- add 0, 2, wrong-identity, and successor-marker negative tests.

## C1-C15 review status

| ID | Review status | Review result |
| --- | --- | --- |
| C1 | SUPPORTED | One coordinator-created owner and ledger are preserved into finalization; continuity absence blocks. |
| C2 | SUPPORTED | Factory identity is preallocated and immutable context is constructed before lifecycle work. |
| C3 | SUPPORTED | Governed attempt observer includes success/failure attempts and source context. |
| C4 | SUPPORTED | Transport metadata carries measured bytes/rows; prior `LENGTH(...)` reconstruction was removed. |
| C5 | SUPPORTED | Shared reservation policy and execution-boundary reservation evidence are present. |
| C6 | SUPPORTED | Named validation identities are emitted and required by the gate. |
| C7 | SUPPORTED | Stage-scoped Scheduler ownership and transition observation cover the required job families. |
| C8 | SUPPORTED | Full-manifest reconciliation is unscoped and non-vacuous. |
| C9 | SUPPORTED | Window ownership precedes terminalization and missing queue truth no longer defaults to `COOLDOWN`. |
| C10 | SUPPORTED | Exact cadence, snapshot IDs, coverage, and close counts are reported and gated. |
| C11 | SUPPORTED | Clean-episode creation has a pre-insert quality gate and negative test coverage. |
| C12 | BLOCKED | Canonical report still labels a config hash as an invocation-marker hash and permits default lease truth. |
| C13 | BLOCKED | Actual authorization marker and lease-release evidence are not mandatory at every PASS entry point. |
| C14 | BLOCKED | Replay reproduces the substituted marker value rather than proving the actual invocation marker. |
| C15 | SUPPORTED | Stage terminal status and first-cause handling are represented and fail closed. |

`SUPPORTED` means the reviewed diff and focused test sources provide evidence for the requirement. It is not a lane PASS while any required C item is blocked.

## Test-evidence review

The implementation report records:

- compilation exit 0;
- 47 focused C1-C15/integration tests plus 6 subtests;
- 51 migration/projection tests with one intentional skip;
- 130 nearest affected tests;
- 10 source-accounting tests;
- final public replay/wiring tests;
- clean `git diff --check`.

This independent review did not rerun those commands. Static inspection found that the positive coordinator-helper test omits `lease_released`, so its PASS result is evidence of the F1 false-PASS path rather than proof of actual lease release.

No broad suite is required for the narrow repair.

## Money-usefulness contribution

The review prevents a false terminal-safety PASS from being accepted into operational history. Actual lease release and actual invocation authorization are necessary before later memory evidence can be trusted for any future paper-only decision lane.

This review unlocks no trading or retrieval capability and makes no profit claim.

## What this review improves

- distinguishes factory configuration identity from invocation authorization evidence;
- prevents omitted lease evidence from being treated as safe terminal closure;
- preserves the accepted C1-C15 architecture while narrowing the repair to the failed completion-law rows;
- avoids an unsafe jump into bounded proof.

## What remains locked

- migration 050 application to `data/printer_v1.sqlite3`;
- bounded or live campaign proof;
- provider/source/RPC/WebSocket execution;
- authoritative memory generation or promotion;
- WINDOW_1H/4H/12H/24H;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL;
- wallets, keys, signing, real funds, or live execution;
- paid APIs;
- scoring, ranking, confidence, weighting, embeddings, or vectors.

## Minimum repair and proof

The next implementation must be limited to:

1. mandatory explicit lease-release evidence at the acceptance boundary;
2. actual invocation/authorization marker identity and hash;
3. authorization-count derivation from the marker owner, cross-checked with the factory bind;
4. strict report and replay validation for those facts;
5. focused negative tests for omission, substitution, mismatch, duplication, and count drift;
6. update of the C1-C15 implementation report.

Minimum tests:

- missing `lease_released` blocks;
- `lease_released=None` blocks;
- `lease_released=False` blocks;
- actual cleanup `True` passes;
- missing invocation marker blocks;
- config hash used as marker blocks;
- marker digest mismatch blocks;
- wrong authorization identity blocks;
- authorization counts 0 and 2 block;
- exact marker replay passes read-only with zero side effects.

Do not run a broad repository suite unless focused failures demonstrate a shared regression.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Effect | Required control |
| --- | --- | --- |
| Acceptance helper defaults safety truth | Missing evidence may become PASS | Require explicit cleanup evidence and fail on omission |
| Config hash masquerades as marker hash | Report/replay overstate authorization proof | Separate config and invocation-marker identities/hashes |
| Bound-run count used as authorization count | Identity binding may be mistaken for operator authorization | Derive from canonical authorization owner and cross-check binding |
| Repair expands into unrelated accounting work | Increases regression and review scope | Limit change to C12/C13/C14 surfaces and focused tests |

## Exact next permitted task

`V2-9.8B C12-C14 Authorization Marker and Lease-Evidence Conformance Repair`

After that focused implementation passes, repeat the independent read-only conformance review. The bounded-proof lane remains prohibited until the review returns `CONFORMANCE_REVIEW_PASS`.
