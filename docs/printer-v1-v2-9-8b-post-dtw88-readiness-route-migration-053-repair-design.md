# Printer V1 V2-9.8B — Post-DTW88 Readiness Route Migration 053 Repair Design

## Verdict

`V2_9_8B_POST_DTW88_READINESS_ROUTE_MIGRATION_053_REPAIR_DESIGN_PASS`

## Baseline

- DTW-88 audit closeout: `ec6aa689543a4631b819752d10cfe880debedba8`
- Design branch: `agent/v2-9-8b-post-dtw88-readiness-route-migration-053-design`
- Exact historical owner: `migrations/041_pilot_input_readiness_bundle.sql`
- Current canonical migration head: `052_memory_observation_eligibility_layers.sql`

## Design decision

Implement one forward migration only:

`migrations/053_pilot_input_readiness_route_domain.sql`

Do not edit migration 041.

Migration 053 rebuilds `printer_pilot_input_readiness_bundle` with the exact same column names, column order, non-route constraints, index and immutable triggers. The only semantic schema change is that both activation-route CHECK constraints become:

`IN ('GRADUATION_NATIVE', 'PUMP_CREATE', 'MARKET_PRESENT_POOL')`

This makes the durable schema a representational superset while leaving purpose-specific eligibility under the existing Python readiness gate.

## Exact SQL sequence

Migration 053 must follow the repository's established migration-052 table-rebuild pattern:

1. `CREATE TABLE printer_pilot_input_readiness_bundle_053 (...)`
   - copy every migration-041 column and constraint exactly;
   - widen only `latest_activation_route` CHECK;
   - widen only `persisted_activation_route` CHECK.
2. `INSERT INTO printer_pilot_input_readiness_bundle_053 (...) SELECT ... FROM printer_pilot_input_readiness_bundle;`
   - enumerate every column explicitly;
   - no transformed values;
   - no recomputed hash;
   - no synthetic route/authority values.
3. `DROP TABLE printer_pilot_input_readiness_bundle;`
4. `ALTER TABLE printer_pilot_input_readiness_bundle_053 RENAME TO printer_pilot_input_readiness_bundle;`
5. recreate `printer_pilot_input_readiness_created` exactly;
6. recreate `printer_pilot_input_readiness_immutable_update` exactly;
7. recreate `printer_pilot_input_readiness_immutable_delete` exactly.

Do not remove the CHECK. Do not add wildcard/UNKNOWN route values.

## Python surface

No Python behavior change is required for the repair.

`pilot_input_readiness.py` already:

- accepts MARKET_PRESENT_POOL only under MEMORY_OBSERVATION when authority/route are truthful;
- keeps FUTURE_ACTION on the legacy route law;
- writes the truthful candidate route directly;
- stores the ordered candidate surface including `admission_authority` in durable JSON.

One comment-only clarification is allowed in `pilot_input_readiness.py`: replace the stale wording that says the context is preserved "without migration 053" with wording that makes clear migration 053 only expands durable route representability while authority/context remain in JSON.

No change is allowed to:

- `LAWFUL_ROUTES`;
- `evaluate_readiness_gates` behavior;
- `ReadinessCandidate` fields;
- operational projection logic;
- Source Governor;
- Central Scheduler;
- discovery/selection;
- holder budgets;
- liquidity floor;
- registry/migration discovery logic.

## Why no new admission-authority columns

The canonical ordered readiness candidate JSON already persists `admission_authority` and truthful `activation_route`. Adding DB authority columns would require historical backfill semantics and broaden the migration unnecessarily.

The blocker is only that the legacy route columns cannot represent a currently lawful MEMORY_OBSERVATION route.

## Historical immutability / hash preservation

All pre-053 rows necessarily contain only `GRADUATION_NATIVE` or `PUMP_CREATE`, so every existing row is valid under the widened superset CHECK.

Migration 053 must copy every column byte-for-byte / value-for-value. In particular:

- `readiness_id` unchanged;
- route values unchanged;
- JSON blobs unchanged;
- `bundle_hash` unchanged;
- `created_at` unchanged;
- no row added, deleted or rewritten semantically.

The migration changes schema representability, not historical readiness content.

## FUTURE_ACTION safety proof

Allowing MARKET_PRESENT_POOL at the SQLite representation layer does not make it lawful for FUTURE_ACTION.

The existing FUTURE_ACTION gate must still return `PILOT_INPUT_BLOCKED_ACTIVATION` for MARKET_PRESENT_POOL before the writer executes.

No global route-set widening is permitted.

## Implementation file surface

Required:

- `migrations/053_pilot_input_readiness_route_domain.sql`
- one new focused migration/proof test file, recommended:
  `tests/test_dtw90_pilot_input_readiness_route_migration.py`

Allowed comment-only:

- `src/printer_v1/operator_cli/pilot_input_readiness.py`

No other production file should change unless implementation discovers a directly blocking, documented dependency; if so, stop rather than widen scope silently.

## TDD / minimum sufficient verification

### Test A — migration 041-shape preservation

Construct an isolated pre-053 table using the exact migration-041 readiness schema, insert at least one valid legacy immutable row, then execute migration 053.

Assert:

- one row before / one row after;
- every column value identical;
- `bundle_hash` identical;
- original route unchanged;
- UPDATE still aborts;
- DELETE still aborts;
- created-at index exists;
- route CHECK now accepts MARKET_PRESENT_POOL.

### Test B — fresh canonical migration ledger

Run canonical `apply_migrations()` on an isolated DB.

Assert:

- canonical/applied migration count = 53;
- latest canonical/applied migration is `053_pilot_input_readiness_route_domain.sql`;
- `validate_migration_ledger(...).matches` is true;
- FK/integrity remains clean for the isolated fixture.

### Test C — mixed-authority MEMORY_OBSERVATION persistence

Use the DTW-87 mixed pair:

- MARKET_PRESENT_POOL authority + route;
- DIRECT_PUMP_PUMPSWAP authority + genuine legacy carried route;
- holder false/context-only.

Assert:

- MEMORY_OBSERVATION gate is ready;
- immutable bundle INSERT succeeds;
- ordered candidate JSON preserves exact authorities/routes;
- identical rewrite remains idempotent;
- no source rows are created by the readiness writer;
- no memory/decision/position/trade/audit rows are created.

### Test D — FUTURE_ACTION regression

With holder pass supplied only to reach route evaluation, assert MARKET_PRESENT_POOL still returns `PILOT_INPUT_BLOCKED_ACTIVATION` and no bundle is inserted.

### Test E — focused existing regression

Run:

- `tests/test_v2_9_7e_45_pilot_input_readiness.py`
- exact DTW-87 bounded proof `tests/test_dtw87_activation_route_bounded_proof.py`

Do not run the broader stale `test_v2_9_8b_remaining_runtime_blocker_repair.py` as a completion gate; its unrelated 7 failures were baseline-reproduced in DTW-86. Do not repair it in this lane.

## Expected implementation verdict

`V2_9_8B_POST_DTW89_READINESS_ROUTE_MIGRATION_053_IMPLEMENTATION_PASS`

Implementation PASS is not sufficient for operational authorization. It only permits the separate bounded proof/closeout lane.

## Bounded proof after implementation

The proof lane must rerun the exact DTW-87 positive composition against the migrated schema and prove:

- truthful mixed authority reaches durable PILOT_INPUT_READY;
- immutable/readback surfaces preserve exact route and authority;
- FUTURE_ACTION remains blocked;
- no downstream unlock rows;
- no source/runtime activity.

Only after proof PASS may authoritative DB/operational rereadiness begin.

## Authoritative DB / rollout implication

Migration 053 changes the canonical migration ledger from 52 to 53. The existing authoritative Mac DB must not be silently mutated during implementation/proof.

After proof PASS, a separate rereadiness lane must:

1. align Git lineage;
2. take/verify the required DB backup/identity evidence under existing DB safety rules;
3. apply/verify the canonical 053 migration through the approved migration path;
4. prove exact migration-ledger match, integrity/FK cleanliness, operational terminal state, source configuration and zero-I/O composition;
5. stop before any new authorization unless rereadiness passes.

## Rollback / failure posture

- no downgrade migration is designed;
- implementation must prove migration correctness on disposable DBs before any authoritative application;
- if 053 fails on a disposable upgrade fixture, implementation is BLOCKED and must not proceed to authoritative DB work;
- if a later authoritative migration attempt fails, follow existing backup/restore and DB-reconciliation rules rather than manually editing `printer_schema_migrations` or schema objects.

The existing migration runner uses the canonical ordered catalogue and `executescript`; this design does not widen scope into migration-runner refactoring.

## Money-usefulness contribution

Migration 053 allows valid market-present Solana memecoin candidates to retain truthful route identity in durable readiness instead of being lost at the final persistence boundary, improving lawful WINDOW_15M memory candidate throughput without weakening action safety.

## What this design improves

- exact durable representability of source-specific MEMORY_OBSERVATION routes;
- historical row/hash preservation;
- loader compatibility;
- unchanged FUTURE_ACTION safety;
- narrow, testable migration surface.

## What this design still does not unlock

- no migration implementation yet;
- no authoritative DB migration;
- no real WINDOW_15M authorization/run;
- no WINDOW_1H/4h/12h/24h;
- no memory generation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions, trades, audits or PnL;
- no live wallet, keys, funds or execution.

## Proof/test needed before repair completion

Migration-preservation, fresh canonical ledger, mixed-authority persistence, FUTURE_ACTION regression, focused readiness tests and DTW-87 bounded proof must all pass. Then authoritative DB/operational rereadiness is still mandatory.

## Functionality Risks / Setbacks / Efficiency Blockers

- table recreation must preserve immutable triggers/index exactly;
- migration-ledger head changes to 053 and therefore invalidates current 52-migration authoritative readiness until separately reconciled;
- any route transformation would corrupt provenance and is prohibited;
- adding authority columns would unnecessarily broaden compatibility/backfill work;
- the migration runner's existing execution/ledger mechanics are intentionally not redesigned here; authoritative rollout must retain current backup/reconciliation discipline.

## Lane boundary confirmation

Design only. No migration or production code was changed, no authoritative DB was mutated, and no source fetching, Printer runtime, authorization, real WINDOW_15M, memory generation, retrieval, decision, position, trade, audit or PnL activity occurred.
