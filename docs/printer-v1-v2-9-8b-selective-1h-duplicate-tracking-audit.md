# Printer V1 V2-9.8B Selective-1h Duplicate Tracking Audit

## Scope and authority

This is the read-only audit for the discovery-to-tracking failure in blocked
execution `20260728T174735Z-5c86dd14b245`. It is limited to the V2-9.8B
selective-1h activation boundary. It does not authorize another operational
proof.

Baseline verification before investigation:

- branch: `master`
- exact HEAD: `65bb0ad75b1555d95c7748d38c3fd8322959cfb2`
- tracked, staged, and untracked worktree state: clean
- authoritative DB pre-repair SHA-256: `dd5ecc835bf21e91a01470000d2d1738a271acbe20a8c1d9539594f30aa28aea`
- all authoritative DB inspection used SQLite read-only/query-only mode

The active source stack, Python Builder Guide blocker procedure, selective-1h
audit/design/implementation/proof-command/operator-readiness closeouts, first
successful bounded-growth closeout, V2-2 persistence/revival/cooldown sources,
combined executor, queue owner, and atomic handoff tests were reviewed.

## Blocked execution evidence

Retained artifacts:

- `/Users/Dtwo1/PrinterOperations/v2-9-8/20260728T174735Z-5c86dd14b245/terminal-summary.json`
- `/Users/Dtwo1/PrinterOperations/v2-9-8/20260728T174735Z-5c86dd14b245/reports/20260728T174735Z-5c86dd14b245-report.campaign-report.json`

The retained and database evidence agree:

| Fact | Evidence |
|---|---|
| Campaign | `20260728T174735Z-5c86dd14b245-campaign` |
| Discovery batch | `TERMINAL_FAILED` |
| First terminal cause | `DUPLICATE_ACTIVE_TRACKING` |
| Lifecycle | not started; `factory_run_id=null` |
| Governed source calls | 21 |
| Campaign scheduler calls | 0 |
| Terminal reconciliation | clean |
| Restart / successor | false / false |
| Downstream unlocks | all false |

The discovery batch retained two merged graduated candidates. The first
conflicting exact identity was:

| Field | Exact value |
|---|---|
| Mint | `12u9FULaUfHD8uHHe98Fz5gdhg8qeX6DyV93B3Dtpump` |
| Pair | `ECobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwgc` |
| Queue row | `26` |
| Tracking lane | `TRACK_NORMAL` |
| Tracking action | `ENTER_COOLDOWN` |
| Queue status | `COOLDOWN` |
| Priority reason | `factory_terminal:COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED:CLEAN` |
| Created | `2026-07-27 23:56:51` |
| Updated | `2026-07-28T00:12:09.302655+00:00` |

The queue-status corpus counts at audit time were `COOLDOWN=2`, `QUEUED=17`,
`SKIPPED=8`, and literal `ACTIVE=0`. Therefore this exact failure was not an
`ACTIVE` row collision.

## Required blocker-investigation output

```text
BLOCKER CLASSIFICATION: COMMITTED_CODE_DEFECT
EVIDENCE: selection admitted the exact mint/pair while queue row 26 was COOLDOWN; enqueue returned created=False; the executor translated every false result to DUPLICATE_ACTIVE_TRACKING.
OFFICIAL-SOURCE COMPARISON: no Python, SQLite, or pytest runtime discrepancy was involved; SQLite returned the committed predicate result. This is an application-state contract defect.
PRINTER-CONTRACT COMPARISON: V2-2 requires explicit cooldown revival/reopen evidence; the combined selector did not apply the queue-state contract and the queue duplicate predicate grouped COOLDOWN with live ownership.
ROOT CAUSE: selection and handoff used different categorical contracts, and handoff discarded the conflicting row's actual status.
CODE CHANGE JUSTIFIED: YES
MINIMUM SAFE RESPONSE: central exact-state assessment in the queue owner; pre-holder and pre-selection exclusion; final enqueue guard; no new reopen path.
FOCUSED PROOF: temporary DBs and mocks covering every queue category, reserve continuation, exact identity, holder-budget avoidance, atomic rollback, Scheduler ownership, and locked capabilities.
UNTOUCHED SCOPE: live sources/runtime, authoritative DB writes, migrations, proof ceilings, 4h+, retrieval, paper/financial capabilities, retry/restart/successor policy.
AUTHORIZATION STATUS: offline audit/design/repair/proof only; no operational proof authorized.
NEXT ROADMAP-COMPLIANT STEP: repeat the selective-1h operator-readiness review only after repair PASS.
```

## Root cause and call path

`AuthoritativeLiveOperationalCampaignOwner` assembled a bounded graduated
reserve and evaluated holder evidence. `CombinedPumpfunCampaignExecutor` then
applied discovery gates that did not inspect `printer_tracking_queue`. Its
handoff called `enqueue_tracking_item()`, whose active-status tuple included
`COOLDOWN`. The returned `(False, None)` carried no category, and the executor
unconditionally raised `DUPLICATE_ACTIVE_TRACKING`.

This caused three defects at one boundary:

1. a known non-activatable candidate could consume holder evaluation before
   the queue conflict was considered;
2. an eligible reserve candidate was not substituted before selection;
3. a cooldown-policy refusal was reported as active duplication.

Atomic rollback and terminal reconciliation behaved correctly. They are not
the defect.

## Functionality Risks / Setbacks / Efficiency Blockers

- Queue history is append-preserving, so the contract must use the latest exact
  token/pair/lane row rather than any historical row.
- The committed revival owner reopens into `WATCH_ONLY`; discovery must not
  imitate it or silently promote that reopened token to `TRACK_NORMAL`.
- An unknown queue status must fail closed rather than be treated as fresh.
- A reserve may still be genuinely insufficient after categorical exclusions;
  that is an honest terminal outcome, not a retry signal.
- The blocked run spent 21 governed source calls before the defect surfaced.
  This repair can avoid holder/handoff work for already-known conflicts, but it
  cannot retroactively recover discovery source budget.

## Audit verdict

`COMMITTED_CODE_DEFECT`

Implementation is justified only inside the existing queue, holder funnel,
selection, and handoff owners.
