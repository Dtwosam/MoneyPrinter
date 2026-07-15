# Printer V1 V2-9.3 Early-Failure Propagation and Unreached-Phase Accounting Repair Closeout

## Verdict

`V2_9_3_EARLY_FAILURE_ACCOUNTING_REPAIR_PASS`

V2-9.3 repaired early 15m/1h failure propagation and unreached 4h accounting
using deterministic fixtures and temporary databases only. No source adapter,
scheduler runtime, bounded proof, persistent-data write, or later lane ran.

## Scope and baseline

- Required baseline: `d62987d Close V2-9 failed 4h proof attempt 2`.
- Starting HEAD: `d62987df7ce8bea47b2a090eeb2e89d9bde84a5b`.
- Starting tracked worktree: clean.
- Applicable governance was read from the active Printer stack and the two
  approved Solana Builder evidence-governance files.
- V2-9, V2-10, WINDOW_12H, and WINDOW_24H runtime remained disabled.

## Audit result and root cause

The failed attempt correctly stopped token-local work after the early
DexScreener failure, but final reporting had no authoritative first-cause
contract. Three later calculations could therefore replace the real cause:

1. the run loop retained a generic completion reason after token-local failure;
2. the budget report encoded an unreached 4h phase as unavailable and
   `within_ceiling=false`;
3. terminal validation interpreted that false value as a 4h budget breach, and
   post-report cleanup/integrity calculations could overwrite the result again.

The incorrect budget reason was therefore a reporting-precedence defect, not a
real phase or cumulative ceiling breach. The 4h phase had never started.

## Repair

### Authoritative terminal cause

The current-run ledger now resolves the first genuine failed runtime step in
scheduled ledger order. A source failure becomes the primary terminal cause and
retains its exact canonical failure type, message, source, request kind, step,
and timestamp. It also records whether the failure occurred in `PRE_4H_15M`,
`PRE_4H_1H`, or `FOUR_HOUR`.

The existing status and stop-reason vocabulary is reused:

- source failure: `FAILED` / `STOP_SOURCE_FAILURE`;
- projected or actual budget breach: `SAFE_STOPPED` / `STOP_BUDGET`;
- other existing run stops retain their existing reason.

Terminal validation consumes that primary cause. Later phase, cumulative,
cleanup, and forbidden-delta calculations are secondary details and cannot
replace it. Cleanup or integrity failure still prevents an otherwise successful
run from returning `COMPLETED`.

### Unreached 4h phase

When no current-run `LONG_CONTINUATION_*` ledger step exists, the report now
represents the 4h phase explicitly as:

- `state=NOT_STARTED`;
- `source_requests=0`;
- `scheduler_rows=0`;
- `budget_verdict=null`;
- `within_ceiling=null`.

The lane may still be identified from an earlier current-run step so cumulative
lifecycle usage can be reported against the policy-derived lane ceiling.
`NOT_STARTED` never means exceeded and cannot produce a 4h budget stop.

### Phase and cumulative budget separation

The approved ceilings were not changed. Projected 4h checks now attach the
authoritative scope `FOUR_HOUR_PHASE`; projected whole-run checks attach
`CUMULATIVE_LIFECYCLE`. Actual terminal validation reports those scopes
separately and emits a budget reason only when the relevant phase has started
and the explicit verdict is `EXCEEDED`, or when the distinct cumulative verdict
is explicitly `EXCEEDED`.

4h holder fallback accounting is phase-local. Cumulative holder usage remains
available separately. Zero automatic retries and no endpoint rotation remain
unchanged.

## Deterministic V2-9.3 proof

Six new tests use fully migrated temporary SQLite databases:

1. A 15m DexScreener TLS/transport failure preserves
   `dexscreener_transport_failure` and its exact TLS message, returns
   `FAILED` / `STOP_SOURCE_FAILURE`, marks `PRE_4H_15M`, cancels pending
   token-local work, leaves zero running jobs, and reports 4h `NOT_STARTED`.
2. The same failure in the 1h continuation produces the identical contract with
   `PRE_4H_1H`.
3. A projected 4h request above the FAST phase ceiling stops before the call and
   reports `FOUR_HOUR_PHASE`.
4. A projected cumulative request above its policy ceiling remains distinct and
   reports `CUMULATIVE_LIFECYCLE`.
5. Actual phase and cumulative overages remain distinct, while a pre-existing
   source primary cause wins over a later cumulative calculation.
6. Cleanup and integrity problems are preserved as secondary details after a
   failure, but prevent an otherwise completed outcome.

The early-failure fixtures create no successor windows, memories, fingerprints,
retrieval rows, decisions, positions, trade events, trade audits, or PnL. Their
report-only replay is byte-identical and reports zero source calls and zero new
evidence rows.

## Regression evidence

All final focused groups passed:

- V2-9.3 early-failure/accounting repair: `6 passed`;
- V2-9.2 terminal/budget repair: `10 passed`;
- V2-4 one-command runtime and report replay: `16 passed`;
- V2-6.3 continuous runtime: `8 passed`;
- V2-7.1 cadence: `12 passed`;
- V2-7.2 continuity: `8 passed`;
- V2-8.1 4h runtime: `6 passed`;
- V2-9.1 schema readiness/isolation: `10 passed`;
- shared-context gates: `8 passed`;
- E2Q: `97 passed`;
- Lane Q: `88 passed`;
- Lane K/E2Z: `127 passed`;
- downstream financial locks: `85 passed`.

Python compilation and `git diff --check` also passed. No approved cadence,
continuity, schema, E2Q, Lane Q, Lane K/E2Z, shared-context, cleanup, replay, or
lock behavior was loosened.

## Persistent DB and downstream locks

The canonical persistent DB was opened read-only. Its SHA-256 remains:

`97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`

Critical counts remain identical to the V2-9/V2-9.2 baseline:

- source requests / responses / failures: `1118 / 1071 / 47`;
- scheduler jobs: `989`;
- token snapshots: `1012`;
- memory windows / fingerprints / memories: `156 / 23 / 0`;
- retrieval queries / matches: `10 / 0`;
- paper decisions: `2`;
- positions / trade events / trade audits: `0 / 0 / 0`;
- run-ledger runs / steps: `0 / 0` on the older persistent schema baseline.

No sources or scheduler jobs ran. No memory, retrieval, paper decision,
BUY/SELL/HOLD, position, trade, audit, PnL, live execution, wallet/key/signing,
paid-source, scoring/ranking/confidence, weighted-logic, embedding, or vector
capability was created or unlocked.

## Files changed

- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `tests/test_v2_9_3_early_failure_accounting_repair.py`
- `docs/printer-v1-v2-9-3-early-failure-propagation-accounting-repair-closeout.md`

## Functionality risks / setbacks / efficiency blockers

1. This is deterministic repair evidence, not a new bounded 4h proof. Another
   proof requires separate operator approval.
2. Primary-cause resolution depends on canonical failed-step and source-failure
   ledger rows being written before final reporting; missing ledger evidence
   remains fail-closed rather than inferred.
3. `NOT_STARTED` is established by the absence of current-run
   `LONG_CONTINUATION_*` steps. Once such a step exists, normal started-phase
   validation and approved ceilings apply.
4. The scheduler's historical `retry_count` records failed attempts, while the
   governed report's `automatic_retries=0` records that no retry was scheduled.
   This existing representation was not renamed or loosened.
5. Pre-existing untracked repository artifacts were not modified or included.

## Closeout

V2-9.3 passes. Early 15m and 1h failures now retain their exact first runtime
cause, stop and clean up token-local work, and cannot be overwritten by an
unreached 4h phase. Real phase and cumulative budget breaches remain distinct,
fail closed before prohibited work, and preserve every approved ceiling. V2-9
was not rerun, and no later lane began.
