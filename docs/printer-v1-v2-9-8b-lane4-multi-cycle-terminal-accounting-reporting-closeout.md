# V2-9.8B Lane 4 — Multi-Cycle Terminal Accounting / Reporting Closeout

**Document status:** `CLOSEOUT`

**Date:** 2026-08-23

**Starting bounded-proof HEAD reviewed:**
`35ff7ba8db6c45ddb63a9496394e7013a88f0089`

**Verdict:**
`V2_9_8B_LANE4_MULTI_CYCLE_TERMINAL_ACCOUNTING_REPORTING_CLOSEOUT_PASS`

## Scope

This closeout covers only the current authorized Cycle-1 plus Cycle-2 terminal
accounting and reporting path. It performs no campaign, provider call,
authoritative operational-database mutation, report regeneration, later
implementation, or Cycle-3 activation.

No new terminal ledger or migration exists. Existing persisted campaign, cycle,
slot, window, Scheduler-work, progression, report, and supervision rows remain
the production truth.

## Accepted commits

| Commit | Accepted role |
| --- | --- |
| `4c0fe31f773c14f59e2008ed3f17f8f03580bb98` | Lane-4 readiness audit |
| `2c98a0f82faf787e0f2a209b74bd2d422549c8f8` | Lane-4 design |
| `2bfb19ee31d7add4c7185f119154741613e56804` | Narrow implementation |
| `2b507ceed5966e2d5ddf08b4070e1c0615b8ff0c` | Peer-stop active-target repair |
| `35ff7ba8db6c45ddb63a9496394e7013a88f0089` | Bounded production-path proof |

Independent source inspection of the implementation, peer-stop repair, and
bounded proof is accepted. This closeout does not reopen those lanes.

## Final production path

The accepted reachable path is:

```text
exact admitted Cycle 1 production truth
+ exact admitted Cycle 2 production truth
-> derive_cycle_terminal_accounting_result() independently per cycle
-> derive_two_cycle_campaign_terminal_accounting()
-> exact per-cycle terminal reconciliation
-> canonical full-run accounting
-> canonical immutable two-cycle terminal report
-> subordinate immutable terminal summary
-> read-only exact report replay
```

Canonical per-cycle accounting remains in
`campaign_full_run_accounting.derive_cycle_terminal_accounting_result`.
The exact two-cycle aggregate remains
`derive_two_cycle_campaign_terminal_accounting`. Callers supply identity only.
Finished execution, quality, peer-stop, first-cause, and report results are not
accepted as inputs.

## Exact cycle isolation

Each admitted cycle resolves through its own campaign, campaign-run,
configuration, factory-run, cycle id, ordinal, slots, mint/pair, tracking
queue/lane, windows, factory steps, Scheduler jobs, campaign-work mirrors, and
Lane-3 progression truth. Cycle-1 owned steps cannot satisfy a Cycle-2
requirement. Factory Phase A no longer applies one shared status/cause to every
admitted cycle.

## Two-cycle campaign success

Campaign success requires truthful completion of exact authorized ordinals
`(1, 2)`. One missing, active, failed, cancelled, or ambiguous required cycle
cannot be masked by the other. Ordinal 3 and more than two admitted cycles fail
closed. Cycle 3 remains locked.

## Fault-scope result

Token-local failure remains token-local and does not automatically fail the
peer token or cycle. Cycle-local failure remains cycle-local. Campaign-shared
supervision/run faults retain `origin_scope=CAMPAIGN` and
`effect_scope=CAMPAIGN`. One cycle's local cause is never copied as the peer
cycle's local cause.

## Peer-stop repair

`CAMPAIGN_STOPPED_AFTER_PEER_CYCLE_TERMINAL` is lawful only when canonical
accounting independently derives:

- origin `execution_outcome == CYCLE_FAILED` with an exact primary fault; and
- target `execution_outcome == ACTIVE_INCOMPLETE`.

Factory selection and `derive_peer_cycle_stop_effect()` both use that allowlist.
`INTERRUPTED_AMBIGUOUS` is not peer-stopped and is not rewritten. A nonfailed
origin cannot peer-stop another cycle.

## Execution versus quality

Honest `DIRTY`, `NON_CLEAN`, `NO_PROMOTION`, and other authorized non-CLEAN
evidence remains quality truth. Execution can stay `TERMINAL_SUCCESS`. Quality
and execution remain separate axes on the cycle and campaign aggregates and in
the canonical report.

## Lane-3 consumption

Lane 4 consumes Lane-3 canonical progression through
`derive_standard_4h_progression_status`. Missing required Standard-4H
progression is incomplete/ambiguous, never disabled or successful. Lane-3
attempt/token ownership, 0/1/2 handoff, immutable 1h predecessor, first-primary
preservation, and interrupted/ambiguous semantics are unchanged.

## First-cause preservation

Lower-level and campaign/run first causes remain immutable. Later cycle,
accounting, report, summary, or cleanup faults remain secondary.
`SAFE_STOP_PREFLIGHT_FAILED` does not replace a known earlier exact cause.

## Six-unit result

`CampaignSixUnitProjection` remains subordinate reconstruction/evidence. It is
not terminal authority. Registered cycle owners must equal the exact admitted
cycle set. Each cycle reconciles only its own action-local evidence. Cycle-1
sealed evidence cannot satisfy a Cycle-2 owner.

## Canonical report result

One Lane-4 report version carries campaign_id, configuration_id,
campaign_run_id, factory_run_id, execution_id, report_id, required ordinals
`[1, 2]`, ordered per-cycle composites, campaign execution and quality
outcomes, accounting completeness, first cause, and secondary faults. No
top-level Cycle-1 `cycle_id` is used as campaign identity. Exact replay is
idempotent. A divergent payload for the same identity is rejected. Report
persistence creates no Scheduler, provider, or lifecycle work.

## Terminal-summary result

`unified_terminal_closure.write_campaign_terminal_summary()` is the single
canonical summary writer. The summary is a projection of already-derived
accounting plus the report-write result. It includes configuration_id, ordered
Cycle-1/Cycle-2 summaries, report identity/hash/path,
`restart_created=false`, and `successor_created=false`. Identical replay is
idempotent. Differing existing content fails closed and does not override
runtime or report truth.

Discovery-only artifacts may still write their own discovery report file; the
terminal-summary file for that branch still goes through the same canonical
summary writer.

## Report-only result

`report_only()` opens SQLite with `mode=ro`. It prefers the exact persisted
canonical report, returns that aggregate without recomputing lifecycle truth,
and performs no provider, Scheduler, DB-write, or regeneration work. A valid
summary without a report returns `REPLAY_BLOCKED` /
`EXACT_TERMINAL_REPORT_MISSING`. Identity, hash, or aggregate mismatch fails
closed.

## Crash / partial-state result

Durable cycle truth is reconstructable read-only without creating work.
Campaign terminal rows with no report do not fabricate a report. A durable
report remains authoritative when the summary is absent or failed. Ambiguous
or partial cycle state cannot become campaign PASS. No automatic retry,
resume, restart, recovery, or successor exists.

## No-migration result

Lane 4 added no migration, no accounting ledger, no alternate fault ledger, no
new report table, and no summary database authority. Existing persisted owners
are sufficient.

## Bounded proof

Disposable production-path proof at `35ff7ba8db6c45ddb63a9496394e7013a88f0089`
induced underlying ownership rows and let canonical owners derive the matrix
results. Closeout reuse of that proof plus nearest locks:

- Lane-4 bounded-proof module, existing Lane-4 accounting/peer-stop/report/
  summary/report-only tests, and six-unit cycle-owner tests;
- directly affected Lane-3 progression/fault locks;
- directly affected Lane-2 category/deadline/fairness/provenance locks;
- compilation of Lane-4-touched production Python;
- static single-summary-writer and Cycle-3/`REQUIRED_MULTI_CYCLE_ORDINALS=(1,2)`
  scans;
- `git diff --check` and tracked-tree/index review.

Focused closeout command: **63 passed**. No campaign, provider, or
authoritative operational-database mutation was performed.

## Non-blocking baseline debt

Previously identified stale synthetic/test-only multi-cycle fixture
expectations remain baseline debt. They were not repaired. The older Lane-4
builder tests that pass already-derived maps into report/summary helpers remain
schema/writer contract tests; they are not a substitute for the production-path
bounded proof.

Untracked historical `operator-runs/` artifacts and unrelated patch files were
not used as execution or closeout authority. The consumed campaign was not
rerun.

## Locks preserved

Lane-2 Central Scheduler authority, category/deadline/fairness, Source
Governor, cadence, source-unit yielding, and evidence timing are unchanged.
Lane-3 Migration 061, progression attempt/token ownership, 0/1/2 handoff,
immutable 1h predecessor, first-primary preservation, and
interrupted/ambiguous semantics are unchanged.

Printer V1 remains Solana-only, Solana memecoin-only, and paper-trading only.
No wallet, private key, signing, live funds, or live execution. No paid APIs.
No scoring, ranking, confidence, or weighted logic. No embeddings/vectors. No
Source Governor or Central Scheduler bypass. No dirty-memory retrieval or
decisions. Retrieval, BUY/SELL/HOLD, positions, trade events, paper audits, and
PnL remain locked until later explicit approved lanes. `WINDOW_5M_MICRO_EVENT`
remains support-only. Cycle 3 and WINDOW_12H/WINDOW_24H remain locked.

## Final verdict and next permitted action

Lane 4 is **CLOSED PASS** with no remaining proven Lane-4 blocker.

The forensic four-lane repair sequence is complete through closeout. Cycle 3
is not authorized by this closeout or by the active source stack. The next
permitted action is only:

```text
POST-LANE-4:
Fresh authoritative readiness audit only.
Cycle 3 remains locked.
No campaign.
No reuse of consumed authorization.
```

This closeout does not begin that audit, issue authorization, or activate
Cycle 3.
