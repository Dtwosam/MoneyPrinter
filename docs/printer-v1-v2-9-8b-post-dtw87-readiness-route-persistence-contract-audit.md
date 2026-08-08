# Printer V1 V2-9.8B — Post-DTW87 Readiness Route Persistence Contract Audit

## Verdict

`V2_9_8B_POST_DTW87_READINESS_ROUTE_PERSISTENCE_AUDIT_PASS_FORWARD_MIGRATION_REQUIRED`

## Baseline

- DTW-87 blocked closeout: `181878b8c9e04587e79a976490d09d575e61b313`
- Audit branch: `agent/v2-9-8b-post-dtw87-readiness-route-persistence-audit`
- Audit is static/read-only except this documentation commit.

## Exact blocker owner

The immutable readiness table is introduced by:

- `migrations/041_pilot_input_readiness_bundle.sql`
- original owner commit `cf65b4a7437c2bc7889ee48fb3f9d827456966cb` (`Add immutable PILOT_INPUT_READY boundary`)

Migration 041 constrains both:

- `latest_activation_route`
- `persisted_activation_route`

to exactly:

- `GRADUATION_NATIVE`
- `PUMP_CREATE`

The table also owns immutable UPDATE/DELETE triggers and the readiness-created index.

## Current writer / reader dependency map

### Writer and gate owner

`src/printer_v1/operator_cli/pilot_input_readiness.py`

- `evaluate_readiness_gates(...)` now correctly uses purpose-scoped authority-aware validation for MEMORY_OBSERVATION.
- `build_pilot_input_ready_bundle(...)` writes `latest.activation_route` and `persisted.activation_route` directly into the legacy route columns.
- the same writer already stores the richer ordered candidate surface, including `admission_authority`, in durable JSON (`source_ledger_json`) and in the canonical bundle payload.
- therefore the writer is truthful; the schema is stale.

### Loader

`load_pilot_input_ready_bundle(...)` uses `SELECT *` and derives column names via `pragma_table_info(...)`. A same-column table rebuild does not require a loader API change.

### Operational producer

`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

- projects the frozen activation candidate's canonical `admission_authority` into `ReadinessCandidate`;
- calls `build_pilot_input_ready_bundle(..., readiness_purpose=MEMORY_OBSERVATION)`;
- does not need a schema-specific alternate route representation.

### Focused tests

- `tests/test_v2_9_7e_45_pilot_input_readiness.py` covers readiness gate, immutable bundle behavior, source-specific authority, legacy compatibility, FUTURE_ACTION regression and projection.
- `tests/test_dtw87_activation_route_bounded_proof.py` exposed the persistence mismatch at the exact positive mixed-authority boundary.

## Why representation-only repair is rejected

Do not map `MARKET_PRESENT_POOL` into `GRADUATION_NATIVE` or `PUMP_CREATE` merely to satisfy migration 041. That would store false Pump lineage in durable route columns while the JSON surface carries a different truthful authority/route.

Do not globally add `MARKET_PRESENT_POOL` to `LAWFUL_ROUTES`; FUTURE_ACTION must remain legacy-route-only and holder-gated.

Do not remove the route CHECK entirely; that weakens fail-closed persistence.

Do not edit migration 041 in place; it is historical canonical migration material and already exists in authoritative ledgers.

## Recommended design boundary

A new forward migration is required. Current canonical head is migration 052, so the next lawful ordinal is 053.

The smallest safe migration design is:

1. create a replacement `printer_pilot_input_readiness_bundle_053` table with the same columns, constraints and column order as migration 041;
2. change only both activation-route CHECK sets to:
   - `GRADUATION_NATIVE`
   - `PUMP_CREATE`
   - `MARKET_PRESENT_POOL`
3. copy all historical readiness rows column-for-column with no value transformation;
4. drop the old table;
5. rename the replacement table to `printer_pilot_input_readiness_bundle`;
6. recreate the existing created-at index;
7. recreate the immutable UPDATE/DELETE triggers exactly.

Migration 052 already establishes the repository's accepted forward table-rebuild pattern for CHECK expansion, including copy/drop/rename/index/trigger recreation.

No new admission-authority DB column is required: the canonical authority already persists in the ordered JSON candidate surface. The stale constraint is specifically the route-column domain.

## Historical compatibility / hash preservation

Existing readiness rows contain only the original lawful route values, so they remain valid under the widened superset CHECK.

The migration must copy every stored column exactly. No readiness payload or `bundle_hash` is recomputed. Therefore historical immutable bundle content and hashes remain unchanged.

The same-column design keeps the current loader compatible and minimizes migration risk.

## FUTURE_ACTION safety

Widening the DB CHECK does not itself authorize MARKET_PRESENT_POOL for FUTURE_ACTION. The application gate remains authoritative and must continue to reject MARKET_PRESENT_POOL under FUTURE_ACTION before persistence.

This separation is required:

- schema: durable representability of truthful MEMORY_OBSERVATION routes;
- gate: purpose-specific action eligibility.

## Migration-ledger implications

`src/printer_v1/db/migrate.py` discovers canonical migrations from the ordered `migrations/*.sql` catalogue and enforces a gap-free ordinal sequence rather than a hard-coded count.

Adding 053 therefore changes the canonical migration ledger from 52 to 53. Any authoritative DB must be separately aligned and rereadiness-audited after implementation/proof and before any future real WINDOW_15M authorization.

No authoritative DB migration is allowed in this audit or design lane.

## Minimum later implementation verification

Risk-based checks only:

1. **052 → 053 preservation fixture**
   - build a DB at pre-053 state with at least one legacy immutable readiness row;
   - apply 053;
   - prove all row values and `bundle_hash` unchanged;
   - prove UPDATE and DELETE remain blocked;
   - prove index/triggers exist.

2. **Fresh 053 mixed-authority write**
   - MEMORY_OBSERVATION with truthful `MARKET_PRESENT_POOL` + direct candidate persists successfully;
   - ordered JSON preserves exact authority and route;
   - idempotent identical rewrite remains valid.

3. **FUTURE_ACTION regression**
   - MARKET_PRESENT_POOL remains `PILOT_INPUT_BLOCKED_ACTIVATION` before insert.

4. **Focused existing readiness tests**
   - rerun the existing DTW-86 focused readiness suite.

5. **DTW-87 bounded proof**
   - rerun the exact bounded positive composition after migration implementation.

No broad suite is required for implementation unless a wider architectural change is introduced.

## Money-usefulness contribution

This repair path allows lawful market-present Solana memecoin candidates to retain truthful source identity all the way into durable readiness, preventing avoidable candidate loss before clean WINDOW_15M memory collection while preserving future-action safety.

## What the audit improves

- identifies the exact historical schema owner;
- separates correct gate behavior from stale persistence representation;
- rejects unsafe route falsification and global route widening;
- establishes the minimal forward-migration boundary;
- preserves existing hashes, rows, loader API and immutable semantics.

## What this audit still does not unlock

- no migration 053 implementation;
- no authoritative DB migration/alignment;
- no real WINDOW_15M authorization or run;
- no WINDOW_1H/4h/12h/24h;
- no memory generation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions, trades, audits or PnL;
- no live wallet, keys, funds or execution.

## Proof/test required before completion of the repair section

After a separate approved design and implementation, the 052→053 preservation test, fresh mixed-authority persistence proof, focused readiness regression and DTW-87 bounded proof must pass. Then a separate authoritative DB/operational rereadiness lane is required before any real authorization can be considered.

## Functionality Risks / Setbacks / Efficiency Blockers

- SQLite CHECK constraints require table recreation rather than an in-place ALTER of the constraint.
- migration 041's immutable triggers/index must be recreated exactly after the table rebuild.
- authoritative DB migration-ledger exactness will change from 52 to 53 and must be reconciled separately.
- any attempt to encode MARKET_PRESENT_POOL as a legacy Pump route would corrupt provenance and is forbidden.
- adding new DB authority columns would create unnecessary historical backfill/compatibility scope; current JSON authority persistence already exists.

## Lane boundary confirmation

No production code or migration was changed. No authoritative DB mutation, source fetching, Printer runtime, authorization, real WINDOW_15M, memory generation, retrieval, decision, position, trade, audit or PnL activity occurred.
