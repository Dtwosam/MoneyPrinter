# Printer V1 V2-9.7E.40 Full-Pilot Admission and Candidate-Supply Micro-Design

## Status

Frozen micro-design for the same-session repair of BL-39-01 and BL-39-03. It
does not adopt a provider, add a source contract, change schema, or unlock any
locked capability. It reuses only owners already committed and READY at commit
`6d8472b`.

## Problem

`run(mode=FULL_PILOT)` → `run_operational` composed bounded newest-create Pump
origin activation directly into the 15m/1h/4h lifecycle. It applied neither the
frozen 900-second categorical maturity boundary nor a fail-closed
two-mature-candidate gate (BL-39-01), and its candidate universe was solely the
newest Pump create transactions (BL-39-03). The maturity boundary and its honest
`BLOCKED_INSUFFICIENT_MATURE_POOL` outcome existed only in
`run_snapshot_readiness`.

## Frozen full-pilot admission sequence

```text
combined governed acquisition (existing LivePumpOriginAdapter)
-> durable prospective-origin staging + due reload (existing registry owner)
-> categorical 900s maturity admission (existing evaluate_snapshot_maturity)
-> fail-closed: fewer than two DUE candidates -> stop before holder/lifecycle
-> holder evidence funnel on DUE candidates only (existing owner)
-> exact two-token atomic activation (existing combined executor + driver)
-> new main WINDOW_15M collected forward (existing lifecycle)
```

### Distinctions the design preserves

- **Historical admission evidence** (finalized Pump create `block_time`, ≥ 900s)
  decides only whether tracking may begin. It is never a memory outcome.
- The **new main `WINDOW_15M`** is collected *after* activation, going forward.
  The full pilot does **not** require a completed *historical* 15m candle before
  activation — that `SNAPSHOT_READINESS` dry-run gate would conflict with the
  lifecycle's own forward 15-minute window, so it is intentionally not copied.
- **Support-only 5m** and **selective 1h / conditional 4h** continuation remain
  exactly as the existing lifecycle owner decides them. Discovery never triggers
  them.

## BL-39-01 — admission integration

`run_operational` now, before any holder or lifecycle work:

1. builds the candidate universe (below);
2. classifies each candidate with `evaluate_snapshot_maturity`
   (`block_time + 900s`, timezone-aware UTC clock);
3. keeps only `DUE` candidates as the active selection pool;
4. if fewer than two `DUE` candidates exist, persists the operation ledger and
   returns a clean `OriginLifecycleResult` terminal with
   `run_status = NOT_STARTED`, `stop_reason = BLOCKED_INSUFFICIENT_MATURE_POOL`,
   `lifecycle_started = False`, and zero forbidden deltas — before any holder,
   snapshot, lifecycle or memory work;
5. otherwise runs the existing holder funnel on the `DUE` candidates only and
   proceeds into the unchanged activation + lifecycle driver.

The terminal maps through `finalize_execution_from_report` to
`TERMINAL_GOVERNED_SAFE_STOP`, so the live pilot runner attaches the run,
finalizes, and replays cleanly.

## BL-39-03 — candidate supply (smallest categorical policy)

The full-pilot candidate universe is no longer solely the newest creates:

- Every confirmed origin in the cycle is staged into the existing durable
  prospective-origin registry (`record_confirmed_origin`, idempotent). Immature
  creates are retained for a later independent cycle, not selected now.
- Previously staged confirmed origins that are **now categorically due** are
  reloaded with zero source calls (`load_due_staged_origins`) and unioned into
  the universe, excluding the current cycle's mints.
- Maturity then decides the active pool. The **newest, too-young creates are
  categorically excluded** from selection; only `DUE` candidates (older members
  of the bounded window, or previously staged origins now due) may be selected.

Properties preserved: no new provider, no paid dependency, no invented source
contract, no provider rank/order/score/weight/popularity, deterministic uniform
selection after fixed gates (unchanged combined executor), pair age never
represented as token creation age (admission uses finalized create age only;
pair age is reported as an explicit unknown), and bounded ceilings.

### Honest structural limit

On a **fresh isolated DB** (required per pilot attempt) the prior registry is
empty, so the universe is the current bounded creates only. Under normal Pump
throughput those are seconds-to-minutes old, so a cold-start attempt will
usually have fewer than two `DUE` candidates and close honestly with
`BLOCKED_INSUFFICIENT_MATURE_POOL`. The staging mechanism supplies mature
candidates only across cycles/time on a persistent DB, or when low throughput
makes the bounded window span ≥ 900s. Guaranteeing two mature candidates on a
cold start would require either adopting a currently blocked secondary discovery
provider (with live origin verification) or a persistent cross-run staged pool —
both operator decisions, out of scope for this repair.

## Reporting

The returned report carries `full_pilot_admission`:

- `threshold_seconds`, `candidate_universe`, `mature_candidate_count`,
  categorical `state_counts`;
- per-candidate `state`, `origin_block_time_epoch`,
  `observed_origin_age_seconds`, UTC origin/due/evaluated timestamps, and an
  explicit `pair_age_context = UNKNOWN_PAIR_AGE_NOT_FETCHED_AT_ADMISSION`;
- `channel_counts` by discovery channel (`LATEST_PUMPFUN`,
  `STAGED_DUE_REGISTRY`, and secondary enrichment channels) and
  `staged_this_cycle`.

## Owners changed

- `src/printer_v1/sources/pumpfun_origin.py`: add `load_due_staged_origins`
  (zero-RPC due-staged reload from the existing registry).
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`:
  `run_operational` gains the staging + maturity + fail-closed admission gate and
  `_full_pilot_admission_diagnostics`.

No migration, provider adapter, Source Governor, Central Scheduler, holder owner,
snapshot owner, lifecycle owner, memory owner, retrieval owner, decision owner,
or financial owner changed.

## Offline proof

- `tests/test_v2_9_7e_40_full_pilot_admission.py`: two immature candidates fail
  closed before lifecycle with zero holder/lifecycle/memory/financial rows and
  two staged registry rows; one mature + one immature is still insufficient
  (partition proven); staged-registry reload returns only due origins and is
  deterministic and zero-source.
- Directly affected regressions pass unchanged: E.11 operational (mature
  fixtures traverse the gate and the full lifecycle), E.8 integration, E.36-38
  maturity, E.33 readiness, E.14 pilot runner, E.5/E.6/E.4g origin/registry.

## What remains locked

Everything under the V2-9.7E permanent locks. A cold-start full-pilot PASS,
adopting blocked secondary discovery providers, and a persistent cross-run
staged pool remain out of scope and, where relevant, operator decisions.
