# Printer V1 V2-9.8B — Post-DTW86 Bounded Activation-Route Proof Blocked Closeout

## Verdict

`V2_9_8B_POST_DTW86_BOUNDED_DETERMINISTIC_ACTIVATION_ROUTE_PROOF_BLOCKED_IMMUTABLE_READINESS_SCHEMA_ROUTE_CONSTRAINT`

## Baseline

- DTW-86 implementation closeout: `f47490441506a30f52adb84f7a0c74e540284f9a`
- Proof branch: `agent/v2-9-8b-post-dtw86-activation-route-bounded-proof`
- Bounded proof test commit: `3fecea57c6dd1b22f68e49a66f96e684d0829fcd`
- Disposable PR: #70, closed unmerged

## Bounded proof

Workflow run `31272170064`, job `93139871087` executed only:

1. the DTW-87 offline activation-authority composition proof; and
2. the existing focused DTW-86 readiness regression if the bounded proof passed.

The proof used an isolated temporary SQLite database and no live sources or Printer operational runtime.

Two DTW-87 proof cases passed before the blocker:

- canonical `AdmissionAuthority` role semantics and exact operational projection;
- fail-closed FUTURE_ACTION / contradictory MARKET_PRESENT_POOL route behavior.

The mixed-authority positive MEMORY_OBSERVATION case passed `evaluate_readiness_gates(...) == PILOT_INPUT_READY`, then failed when the immutable readiness bundle was persisted.

Exact failure:

`sqlite3.IntegrityError: CHECK constraint failed: latest_activation_route IN ('GRADUATION_NATIVE', 'PUMP_CREATE')`

The existing bundle writer persists `latest.activation_route` and `persisted.activation_route` directly into the legacy immutable route columns. Therefore a truthful `MARKET_PRESENT_POOL` candidate accepted by the repaired purpose-scoped gate cannot currently be written to `printer_pilot_input_readiness_bundle`.

## Root-cause classification

This is a real post-DTW86 contract mismatch, not a proof-fixture defect:

- the canonical activation owner supports source-specific `AdmissionAuthority.MARKET_PRESENT_POOL`;
- DTW-86 correctly projects that authority and validates the truthful `MARKET_PRESENT_POOL` route for MEMORY_OBSERVATION;
- the immutable readiness persistence schema still constrains the legacy route columns to `GRADUATION_NATIVE` / `PUMP_CREATE`;
- the writer uses the truthful route directly, so SQLite fails closed before a readiness bundle can be committed.

No attempt was made to bypass the CHECK constraint, falsify the route, map MARKET_PRESENT_POOL to a Pump route, or weaken FUTURE_ACTION semantics.

## Money-usefulness contribution

The bounded proof prevented a false readiness PASS. Without this proof, lawful market-present Solana memecoin candidates could pass the repaired in-memory gate yet fail at durable readiness persistence, blocking later clean WINDOW_15M memory collection unexpectedly.

## What this lane improves

- proves the DTW-86 in-memory authority/gate behavior reaches the persistence boundary;
- identifies the exact next contract blocker before any real operational authorization;
- preserves truthful source-specific route identity instead of manufacturing Pump lineage.

## What this lane still does not unlock

Nothing operational is unlocked. In particular:

- no real `WINDOW_15M` authorization or run;
- no WINDOW_1H/4h/12h/24h;
- no memory generation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions, trades, audits or PnL;
- no live wallet, keys, funds or execution.

## Required next step

Do not implement a schema change directly from this blocker.

Next is a separate read-only audit of the immutable readiness persistence contract to identify:

- the exact migration/table owner of the legacy activation-route CHECK constraint;
- all readers/writers/tests depending on those legacy columns;
- whether the safest repair is a new forward migration, a compatibility persistence representation, or another design that preserves immutable historical rows and truthful ordered candidate surfaces;
- rollback/upgrade implications for authoritative DB migration-ledger exactness.

Only after that audit should a separate design lane specify the repair. Any implementation then requires its own focused proof before authoritative DB/operational rereadiness.

## Functionality Risks / Setbacks / Efficiency Blockers

- DTW-86 is not operationally complete for MARKET_PRESENT_POOL persistence despite its focused unit-level PASS.
- Existing authoritative databases remain on the current canonical migration ledger; no migration was added or applied here.
- A careless fix that rewrites MARKET_PRESENT_POOL into a legacy Pump route would destroy truthful admission provenance and is forbidden.
- A careless schema edit could break immutable historical readiness bundles or migration-ledger exactness; audit/design must precede implementation.

## Lane boundary confirmation

No production code was changed. No live source fetching, authoritative DB mutation, Printer runtime, authorization creation/consumption, real WINDOW_15M execution, memory generation, retrieval, decision, position, trade, audit or PnL occurred. The disposable proof runner was removed after use and PR #70 was closed unmerged.
