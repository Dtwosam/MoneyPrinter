# Printer V1 Handoff

## Current verified implementation

Branch: `assistant/v2-9-8b-lane8b-paper-decision-lockout-repair`.

Verified code/test HEAD: `8a5940c83b70eac00a28129b099d38f9a57770cd`.

GitHub Actions run `34418256952`, job `102687854610`, is green:

- focused post-holder/reconciliation: **29 passed**;
- clean-memory consumer lockout: **27 passed**;
- legacy Lane 8B / historical decision path group: **100 passed**;
- paper position/monitor/audit/PnL lockout: **46 passed**;
- shared discovery/admission/two-cycle Standard-4H: **399 passed, 2 deselected, 32 subtests passed**;
- affected-module compile and diff whitespace checks passed.

## Current capability

Printer V1 remains Solana-only, memecoin-only, paper-only. Source Governor and Central Scheduler remain the sole owners of governed source requests and scheduling. `WINDOW_5M` is support-only; `WINDOW_12H` and `WINDOW_24H` remain locked.

Current capability locks remain false for retrieval activation, paper decisions, paper positions/monitoring, paper audits, and paper PnL.

The legacy post-RC Lane 8B decision bypass is repaired:

- `build_conservative_paper_decision_payload()` requires the shared paper-decision capability before DB resolution;
- `_lane8b_insert_conservative_decision()` independently requires the same capability before SQL;
- the older `build_create_paper_decision_once_payload()` and `_insert_blocked_paper_decision()` are guarded the same way;
- both CLI surfaces fail with `PAPER_DECISIONS_LOCKED` and create no decision rows while the capability is false;
- historical future-engine tests enable retrieval/decision capability only inside disposable fixtures and restore the locked defaults afterward.

Targeted review found no production consumer treating historical readiness labels such as `READY_REAL_DATA_PAPER_DECISION` as activation authority. They remain descriptive/display outputs; actual mutation is independently capability-gated.

## Latest meaningful result

A direct legacy command path that could write `printer_paper_decisions` outside the shared recorder was closed with five production guard lines. The current repair fails before DB/SQL at both public and private writer boundaries and leaves the previously verified Cycle-1/Cycle-2/4h path unchanged.

## Proven blocker / adjacent defect

No blocker remains in the Lane 8B paper-decision lockout lane.

A separate development-safety defect is now proven in the synthetic validation command path:

- `build_synthetic_validation_payload()` accepts an explicit `--db-path` and passes it to `run_full_synthetic_validation_flow()`;
- that full flow mutates synthetic discovery/context/memory state before reaching the already-locked retrieval/decision stages;
- `run_full_synthetic_validation_flow()` nevertheless reports `temp_db_only: True` unconditionally;
- therefore an explicit non-temporary DB can be mutated by a command represented as temporary synthetic validation.

This violates the development rule that synthetic/testing work use disposable state.

## Exact next permitted action

Repair only the synthetic-validation disposable-state boundary. Make the public synthetic-validation command incapable of running the mutating full synthetic flow against an operator-supplied/persistent DB path. Prefer an internally created temporary DB and fail closed on attempts to target another DB. Add focused tests proving an explicit DB path is not opened or mutated and the temporary validation flow remains testable.

Do not activate retrieval, paper decisions, positions, monitoring, audits, PnL, live execution, providers/RPC/WebSockets, operational Scheduler work, or authoritative database mutation.
