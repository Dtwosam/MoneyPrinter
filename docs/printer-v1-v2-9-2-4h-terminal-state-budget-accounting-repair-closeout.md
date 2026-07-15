# Printer V1 V2-9.2 4h Terminal-State and Budget Accounting Repair Closeout

## Verdict

`V2_9_2_TERMINAL_BUDGET_REPAIR_PASS`

V2-9.2 repaired and deterministically verified the bounded 4h terminal-state
and budget-accounting defects exposed by the failed V2-9 proof. This lane used
fixtures and temporary databases only. It did not run a source adapter,
scheduler runtime, or another 4h proof.

## Scope and source governance

The audit used the active Printer source stack, the V2-8 readiness closeout,
V2-8.1 runtime implementation closeout, V2-9.1 schema-readiness closeout, the
V2-9 failed-proof closeout, and the applicable Solana Builder README and Source
Governor evidence rules.

No source-governance rule was loosened. Source Governor and Central Scheduler
remain mandatory, automatic retries and endpoint rotation remain zero, and the
holder fallback maximum remains one.

## Audit findings

Four defects combined in V2-9:

1. The final report derived `COMPLETED` only from the scheduler loop's generic
   `STOP_COMPLETED` reason. It did not independently require exact 4h evidence,
   a successful forced close, a WINDOW_4H successor, or completed audit gates.
2. A governed source failure correctly failed the affected step and cancelled
   that token's remaining jobs, but the token-local failure did not replace the
   generic loop stop reason. The final run therefore reported `COMPLETED` after
   a terminal DexScreener transport failure.
3. The report reused the earlier 5m/15m/1h lifecycle limits as if they were the
   complete 4h lifecycle limits, while also labeling the approved 4h limits as
   full-run limits. Phase-local and cumulative usage were conflated.
4. The 4h pre-step guard checked phase requests only and returned before a
   cumulative check. Scheduler planning also lacked a projected cumulative
   pre-enqueue check, and legacy scheduler counting did not include V2-8.1 job
   names.

The V2-9 proof's 24/31 snapshots, failed source step, cancelled forced close,
and absent WINDOW_4H were therefore incompatible with `COMPLETED`. Under the
V2-9.2 clarified accounting, its recorded phase usage remained inside the
approved NORMAL phase limits and its lifecycle totals remained inside the
newly explicit policy-derived lifecycle ceilings. The proof still fails on
terminal evidence and status honesty; it is not reclassified as a budget
overrun.

## Repair

### Terminal semantics

The final report now performs an independent 4h terminal validation. A 4h run
can report `COMPLETED` only when all of the following are true:

- the policy-exact snapshot count is present in current-run long-step evidence;
- exactly one forced close exists and succeeded;
- that close is attached to a WINDOW_4H successor;
- the close result contains the E2Q/window-audit, Lane Q, and Lane K/E2Z report
  path;
- phase and cumulative budgets are within their applicable ceilings;
- no long step failed;
- no step remains pending/running and no scheduler job remains running.

Incomplete collection, a missing/failed forced close, no successor, missing
audit path, a budget breach, or incomplete cleanup can no longer report
`COMPLETED`.

A terminal transport failure remains token-local: the existing runner fails
the affected step, records its exact error, calls the scheduler failure path
with `max_retries=0`, cancels only that token's remaining pending jobs, and the
final cleanup leaves zero running jobs. Terminal validation then reports
`FAILED / SAFE_STOP_SOURCE_FAILURE`; it cannot inherit a stale generic
`COMPLETED` result.

### Budget accounting

The approved 4h phase ceilings are unchanged:

| Lane | 4h requests | 4h scheduler rows |
| --- | ---: | ---: |
| TRACK_FAST | 69 | 64 |
| TRACK_NORMAL | 39 | 34 |

Reports and enforcement now expose separate `four_hour_phase_usage` and
`cumulative_lifecycle_usage` sections. Cumulative ceilings are computed from
the canonical cadence policies and approved context/discovery allowances:

| Lane | Request derivation | Request ceiling | Scheduler derivation | Scheduler ceiling |
| --- | --- | ---: | --- | ---: |
| TRACK_FAST | 2 discovery + 16 15m + 5 context + 24 1h + 69 4h | 116 | 1 handoff + 16 15m + 24 1h + 64 4h | 105 |
| TRACK_NORMAL | 2 discovery + 9 15m + 5 context + 13 1h + 39 4h | 68 | 1 handoff + 9 15m + 13 1h + 34 4h | 57 |

Projected pre-call checks now enforce both the 4h phase ceiling and the
policy-derived cumulative ceiling. Projected pre-enqueue checks enforce both
scheduler ceilings before any 4h job or run-step row is created. Exact-ceiling
usage passes; one above either applicable ceiling fails closed before creation.

## Deterministic verification

The lane-specific suite proved:

- 24/31 snapshots with no successful forced close or successor cannot return
  `COMPLETED`;
- a terminal DexScreener transport failure preserves the exact reason, reports
  `FAILED / SAFE_STOP_SOURCE_FAILURE`, and requires complete cleanup;
- final-report integration overrides a stale generic `STOP_COMPLETED` reason;
- valid completion requires exact collection, WINDOW_4H, E2Q, Lane Q, and Lane
  K/E2Z report evidence;
- exact request and scheduler ceilings pass, while one above stops before a
  request, job, or run-step row is created;
- phase-local usage is reported separately from cumulative lifecycle usage;
- cumulative ceilings equal the sum of canonical policy components;
- no successor is accepted from incomplete evidence.

Focused regression results, all green:

- V2-9.2 terminal/budget suite: `10 passed`;
- V2-8.1 4h runtime: `6 passed`;
- V2-4 one-command runtime: `16 passed`;
- V2-6.3 continuous runtime: `8 passed`;
- V2-7.1 cadence and V2-7.2 continuity: `12 + 8 passed`;
- shared-context gate: `8 passed`;
- E2Q, Lane Q, Lane K/E2Z, E2Z, and clean-context blocker groups:
  `97 + 88 + 127 + 66 + 7 passed`;
- scheduler/resource, single-tick, and bounded-cycle groups:
  `25 + 8 + 74 passed`;
- V2-9.1 migration/preflight/isolation: `10 passed`;
- financial-action locks: `85 passed`.

The E2Q group was also rerun independently and passed a second time. The V2-4
report-only replay test confirmed zero new source calls and zero new evidence
rows. The V2-9.1 suite reconfirmed migration idempotence, proof/persistent
isolation, backup equality, and fail-closed incomplete migration behavior.

## Persistent DB and locks

The canonical persistent DB was opened read-only. Its SHA-256 remained:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

Critical counts remained identical to the V2-9 and V2-9.1 baselines:

- source requests / responses / failures: `1118 / 1071 / 47`;
- scheduler jobs: `989`;
- token snapshots: `1012`;
- memory windows / fingerprints: `156 / 23`;
- retrieval queries / matches: `10 / 0`;
- paper decisions: `2`;
- positions / trade events / trade audits: `0 / 0 / 0`;
- run-ledger tables remain absent from the older persistent schema, as expected;
  V2-9.1 applies their canonical migrations only to isolated proof copies.

All V2-9.2 fixture deltas were temporary. Retrieval, paper decisions,
positions, trade events, trade audits, PnL, BUY/SELL/HOLD, wallet/key/signing,
live execution, paid sources, scoring/ranking/confidence, weighted logic,
embeddings, and vectors remained locked. No memory was created in the
persistent DB.

## Files changed

- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/one_token_4h_runtime.py`
- `tests/test_v2_9_2_terminal_budget_repair.py`
- `docs/printer-v1-v2-9-2-4h-terminal-state-budget-accounting-repair-closeout.md`

## Functionality risks / setbacks / efficiency blockers

1. This lane is deterministic repair evidence, not a real 4h proof. The next
   proof still requires separate operator approval.
2. Cumulative ceilings intentionally reserve approved maxima, including two
   discovery requests and the full 4h phase allowance. This is conservative
   and may safe-stop before all theoretical capacity is consumed; it cannot
   silently loosen a phase ceiling.
3. The persistent DB remains on its older schema by design. The canonical
   V2-9.1 preparation command must continue migrating isolated proof copies
   before any future proof preflight.
4. Pre-existing untracked repository artifacts were not modified or included
   in this lane.

## Boundary

V2-9 was not rerun. V2-10, 12h, 24h, retrieval activation, paper decisions,
BUY/SELL/HOLD, positions, trades, audits, and PnL were not started. A new
bounded V2-9 proof attempt requires separate operator approval.
