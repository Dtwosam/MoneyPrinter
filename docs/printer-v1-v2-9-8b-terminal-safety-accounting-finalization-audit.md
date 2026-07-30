# Printer V1 V2-9.8B Terminal Safety and Accounting Finalization Audit

Date: 2026-07-30

Lane: `V2-9.8B Terminal Safety, Accounting, Runner-Proof, and Supply-Truth Finalization`

Status: `AUDIT_COMPLETE`

## Baseline

- Branch: `master`
- Start HEAD: `f77237eea4edfa6d79ca3a463979224fbc63b760`
- Start commit: `Repair post-handoff terminal compensation`
- Local HEAD equals `origin/master`.
- Worktree and index were clean before this audit document was created.
- Authoritative DB SHA-256:
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Applied migration head: `049_candidate_acquisition_integration.sql`

## Mandatory Source-Grounded Blocker Investigation

The active Printer stack, the campaign-accounting / terminal-enforcement
records, the post-handoff terminal-compensation records, the retained
verifiable-real-path records, and the just-in-time Source Governor and
DexScreener contracts were read before implementation.

The committed public path was traced through:

- `operator_cli/origin_lifecycle_campaign.py`
- `operator_cli/unified_terminal_closure.py`
- `operator_cli/one_command_15m_factory.py`
- `sources/campaign_six_unit_accounting.py`
- `operator_cli/operational_memory_factory_command.py`
- `discovery/eligible_token_supply.py`

No provider endpoint, Solana instruction, Pump/PumpSwap semantic, migration, or
external contract change is required. The defects are inside committed Python
ownership, accounting, terminal reporting, proof wiring, and attributable
failure counting.

```text
BLOCKER CLASSIFICATION:

B1 — COMMITTED_CODE_DEFECT
Post-handoff cleanup deletes historical run steps, lifecycle events, and
snapshots by token_id rather than exact current-attempt ownership.

B2 — COMMITTED_CODE_DEFECT
Ordinary compensation globally terminalizes every ACTIVE/STOPPING
candidate-acquisition lease without campaign ownership.

B3 — COMMITTED_CODE_DEFECT
The compensation report omits snapshot tables from residual verification and
silently converts SQLite errors into apparent zero residue.

B4 — COMMITTED_CODE_DEFECT
The coordinator converts absent stage accounting into an empty stage-evidence
sequence, and the aggregator accepts it as a valid zero ledger.

B5 — COMMITTED_CODE_DEFECT
The initialized-failure terminal path can write a lenient canonical report
without mandatory six-unit evidence.

B6 — MISSING_APPROVED_IMPLEMENTATION_BOUNDARY / PROOF_GAP
The final post-handoff faults are simulated at the driver boundary instead of
inside the real run_one_command_15m_factory runner.

B7 — COMMITTED_CODE_DEFECT
The shared eligible-supply owner counts a status-label failure in addition to
distinct governed source failures, over-counting provider failures and
misclassifying true supply shortage as source unavailability.

CODE CHANGE JUSTIFIED: YES
```

## Confirmed Committed Defects

1. `_compensate_post_handoff_teardown` authorizes deletes with
   `WHERE token_id IN (...)`, so older same-token rows are in scope.
2. The same owner selects every `ACTIVE`/`STOPPING` candidate-acquisition lease
   and terminalizes it without campaign-attempt ownership.
3. `sqlite3.OperationalError` is swallowed during snapshot deletion and lease
   mutation; residual verification omits token/episode snapshots and derives a
   clean result from incomplete checks.
4. `_run_operational_campaign` converts missing stage evidence to `[]`;
   `aggregate_campaign_six_unit_owner` accepts an empty sequence.
5. `_terminalize_initialized_failure` calls the canonical report builder/writer
   without mandatory evidence enforcement.
6. `_apply_and_fault_post_runner` fabricates the final proof objects outside
   `run_one_command_15m_factory`.
7. `run_persistent_eligible_token_supply` adds a terminal discovery status
   label to the distinct liquidity failure-ID count.

## Required Repair Boundary

Implement one cohesive repair using the existing canonical owners. Preserve
immutable selected-item links, terminalize pinned slots/tracking through
`reconcile_campaign_terminal`, cancel only exact Scheduler job IDs, make
compensation verification fail closed, require real stage accounting, move the
proof seam inside the real 15m runner, and derive supply failures only from
attributable governed facts.

No schema migration is required. Migration 049 remains the required head.
