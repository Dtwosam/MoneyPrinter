# Printer V1 V2-9.7E.40 Persistent Candidate Pool Micro-Design

## Status

Frozen micro-design for the operator-approved (Option 1) persistent
candidate-supply repair of BL-39-03, inside the same continuous E.40 session. It
adopts no provider, adds no source contract, adds no schema table, adds no paid
dependency, and increases no source budget. It reuses the existing durable
`printer_pumpfun_finalized_origin_registry` (the adopted prospective-origin
persistence owner) and the frozen 900-second maturity policy.

## Problem restated

Attempt 2 (live, clean) proved the E.40 admission gate works: real Pump creates
are ~2 minutes old, so on a fresh isolated DB with an empty staged pool the full
pilot honestly closes `BLOCKED_INSUFFICIENT_MATURE_POOL`. A cold-start attempt
cannot reach two categorically mature candidates.

## Approved architecture

```text
bounded governed Pump acquisition cycles
-> durable confirmed-origin pool (one DB, existing registry table)
-> Scheduler-owned categorical 900s maturity (evaluate_snapshot_maturity)
-> mixed-age available pool
-> bounded immutable DUE candidate export
-> copy only DUE candidate facts into a fresh isolated FULL_PILOT attempt DB
-> deterministic uniform selection from DUE candidates (existing combined owner)
```

Maturity waiting happens through real wall clock and Scheduler-owned categorical
states OUTSIDE `FULL_PILOT`. `run(mode=FULL_PILOT)` never waits.

## Pool isolation contract (discovery/source state only)

The persistent pool holds only confirmed Pump origin identity, origin time and
provenance. It never holds, and the pool owner never reads or writes:

- pilot authorizations;
- campaign / run / cycle identities;
- active Scheduler jobs;
- lifecycle state;
- memory rows;
- retrieval or decision state;
- terminal causes;
- report results.

Every `FULL_PILOT` attempt still uses a fresh isolated pilot DB, identity and
authorization. The persistent pool DB is **never** cloned into the pilot as
operational state. Instead a bounded immutable DUE candidate export (exact
identity, origin evidence, timestamps, provenance) is copied verbatim into the
fresh attempt's discovery registry. The existing E.40 `run_operational` then
reloads those rows as DUE (`load_due_staged_origins`) and unions them with the
attempt's own fresh (immature) creates; maturity keeps only the DUE pool, and
the existing combined executor performs deterministic, seeded, uniform selection
of two.

## Owners

- `src/printer_v1/sources/pumpfun_origin.py`:
  `export_due_confirmed_origins` (bounded immutable DUE export) and
  `import_confirmed_origin_row` (verbatim, idempotent, fail-closed import).
- `src/printer_v1/operator_cli/persistent_candidate_pool.py` (new, discovery
  only): `record_acquisition_into_pool`, `pool_maturity_state`,
  `seed_attempt_from_pool`.

No new table, migration, provider, Source Governor, Central Scheduler, holder,
snapshot, lifecycle, memory, retrieval, decision or financial owner changed.

## Candidate-supply properties satisfied

- fresh Pump launches continue to be captured (`record_acquisition_into_pool`);
- confirmed origins are retained across bounded discovery cycles (durable
  registry);
- candidates under 900s remain staged and make zero holder, readiness, lifecycle
  or memory calls (they are never exported or selected while immature);
- candidates become `DUE` categorically at `block_time + 900s`;
- the available pool mixes fresh staged candidates with previously observed
  mature candidates when both exist; the two active candidates are the DUE
  members (previously observed), never exclusively the newest acquisition cycle;
- duplicates across cycles or channels do not increase selection probability
  (registry is keyed by mint identity; import is idempotent; selection is
  identity-deduplicated and uniform);
- selection among qualified candidates remains deterministic, seeded and uniform
  (unchanged combined executor);
- no score, rank, confidence, weighting, provider-order dependence or popularity
  preference;
- pair age is never substituted for authoritative Pump origin time;
- no new provider, paid API, source-budget increase, hidden retry or source
  substitution.

## Explicit remaining limitation (discovery-channel diversity)

This repair supplies **mixed-age Pump-origin** candidates from organically
captured direct launches. It does **not** by itself prove trending / top /
active secondary-channel coverage: those providers remain blocked for candidate
selection, so the pool's channel diversity is limited to the direct
`LATEST_PUMPFUN` origin channel. Secondary-channel candidate discovery remains a
separate future operator decision.

## Offline proof

- `tests/test_v2_9_7e_40b_persistent_candidate_pool.py`: staging, categorical
  maturity before/after the boundary, DUE export, verbatim seed into a fresh
  attempt, idempotent re-seed (no duplicate boost), exclusion, and that an
  immature pool seeds nothing and touches no campaign/lifecycle/memory table.
- Directly affected regressions: E.5/E.6 origin/registry, E.40 admission.

## Operator-run flow (not committed product)

1. Populate the discovery-only pool via bounded governed acquisition cycles.
2. Wait through real wall clock / Scheduler-owned maturity states (not inside
   `FULL_PILOT`) until `pool_maturity_state(...).due >= 2`.
3. Prepare a fresh isolated attempt DB, seed only the DUE export into it, then
   run `run(mode=FULL_PILOT)` for Attempt 3.
