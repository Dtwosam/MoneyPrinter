# Printer V1 V2-9.8B Candidate-Acquisition Foundation Implementation Closeout

Date: 2026-07-29
Lane: V2-9.8B Factory-Wide Candidate-Acquisition Foundation
Scope: combined audit, design, implementation, disposable migration proof, and frozen offline proof

## Final verdict

`V2_9_8B_CANDIDATE_ACQUISITION_FOUNDATION_IMPLEMENTATION_PASS`

This PASS closes the four internal gates for the transport-free,
capacity-neutral candidate-acquisition foundation. It does not authorize a live
source, Solana RPC, WebSocket, historical backfill, operational campaign,
selective-1h proof, or active Memory Factory capacity above two.

## Phase-gate results

| Gate | Result | Evidence |
| --- | --- | --- |
| Gate 1 — combined audit and source-scope reconciliation | PASS | `printer-v1-v2-9-8b-candidate-acquisition-foundation-combined-audit.md`; exact official pins, provider dispositions, repository owner/defect map |
| Gate 2 — complete capacity-neutral design | PASS | `printer-v1-v2-9-8b-candidate-acquisition-foundation-complete-design.md`; complete owner, schema, budget, failure, certificate, reserve, manifest, replay and verification contracts |
| Gate 3 — implementation and disposable migration proof | PASS | migration 048 on fresh DB and authoritative DB copy; focused and broad relevant suites |
| Gate 4 — frozen offline capacity proof | PASS | committed mechanics fixture; exact-N and N-1 matrix for N=2,3,4,5,6,7,10,16; deterministic replay and capability-lock proof |

## Exact authority model

1. Candidate discovery is multi-source.
2. Direct Pump/PumpSwap is a required first-class lane, but not the exclusive
   candidate universe.
3. DexScreener and GeckoTerminal may nominate directly.
4. Optional Birdeye Standard ($0) new-listing observations may nominate when an
   operator supplies an account API-key secret reference. There is no paid
   fallback.
5. Aggregators establish only their supported nomination and present-market
   facts. They cannot independently prove unsupported launch origin, protocol
   lineage, migration, or canonical PumpSwap pool identity.
6. Exact Pump origin and exact joined Pump-migration/PumpSwap evidence are
   mandatory when a candidate carries those Pump-specific claims.
7. Non-Pump and `UNKNOWN_ORIGIN` candidates are not forced into Pump lineage.
   Their exact present mint/token-program/pool/owner/quote, market, age, holder,
   safety, liquidity, tradeability, and freshness facts must pass.
8. Unknown origin remains honest and categorical.
9. No source quota, percentage, preference, score, rank, confidence, or
   weighting exists. Source contribution is diagnostic only.

## Source contracts adopted, deferred, and prohibited

| Source | Disposition | Implemented surface | Unsupported claims / failure semantics |
| --- | --- | --- | --- |
| Direct Pump + PumpSwap through approved Solana RPC | adopted first-class exact-proof contract | transport-free create/create_v2 discriminator decoder; exact finalized migrate instruction/account decoder; strict Pool discriminator/layout/PDA/index/LP/vault verifier | unknown discriminator/layout/version/account order/PDA/quote fails `UNSUPPORTED_CONTRACT` or categorical proof failure; no live transport in this lane |
| DexScreener | adopted | governed nomination and market-batch request kinds; existing adapter retained | no origin, lineage, migration, safety, or canonical-pool claim |
| GeckoTerminal | adopted | governed nomination and market-batch request kinds; existing adapter retained | no origin or Pump lineage claim; stale/failure remains categorical |
| Birdeye | optional adopted free route | fixture-only `/defi/v2/tokens/new_listing` normalizer; Standard-plan constants; no network transport | absent key/account is source unavailable; paid fallback prohibited; nomination facts only |
| DEXTools | deferred | none | current exact free programmatic endpoint/limit/plan contract was not sufficiently established |
| PumpPortal | prohibited for this foundation under current contract | none added | current API-key acquisition is coupled to its wallet product; metered/funded surfaces incompatible; not a shortage if absent |
| GoPlus | retained conditional | existing safety source contract | availability/failure is categorical; never lineage proof |
| Jupiter quote | retained paper-only | no change | paper realism only; never discovery lineage or execution |

The compliant minimum implemented source set is DexScreener plus GeckoTerminal
for nomination/current market coverage and approved Solana RPC contracts for
exact mint/program/pool and Pump/PumpSwap proof when applicable. Birdeye is
optional and cannot be required for foundation success.

## Official pins and hashes

Official Pump repository: `https://github.com/pump-fun/pump-public-docs`
Commit: `9c82f61cb711b044a17f770ab8ce9f9bdf78f333`

| Artifact | SHA-256 |
| --- | --- |
| `idl/pump.json` | `b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49` |
| `idl/pump_amm.json` | `6b5c7ec4e5ef9742fa99dc57b0d75b1031b379bba02a7e1b3c5a4cad68d77e56` |
| `docs/PUMP_PROGRAM_README.md` | `3532f985fcab38480392759a6c2f01015b7178b9f2c7dc0db8c9f85ce9f72571` |
| `docs/PUMP_SWAP_README.md` | `3ac4a835604d7fd3855d66531d109c0547e006bd314b5e5d6cb27b1e20d27abc` |
| `docs/instructions/COIN_CREATION.md` | `310f4560d0c95d8a196a4d3193399de87407de7f90218949290d4b03ec874536` |
| repository `README.md` | `7609341176750cd2c78a74e8b3eab052053d71cecabd0252ef9c4d8e356e8cca` |

Pinned programs and layouts:

- Pump program: `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`;
- PumpSwap: `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`;
- create: `181ec828051c0777`; create_v2: `d6904cec5f8b31b4`;
- migrate: `9beae792ec9ea21e`, exactly 25 accounts;
- BondingCurve: `17b7f83760d8ac60`;
- PumpSwap Pool: `f19a6d0411b16dbc`;
- canonical Pump migration pool index: zero; base uses legacy SPL Token and
  quote is wrapped SOL under this pin;
- transaction versions: legacy/version 0, successful and finalized only.

## Architecture and canonical owners

```text
Central Scheduler DISCOVERY_REFRESH ownership
-> Source Governor request-kind and frozen budget validation
-> finite source observation rounds and cursor continuity
-> source-specific normalized immutable observations
-> exact mint/current-pool identity merge and deterministic dedup
-> categorical cheap-to-expensive admission stages
-> immutable versioned candidate certificate + SHA-256
-> durable capacity-neutral reserve/requalification version
-> deterministic seeded exact-N all-or-none manifest
-> runtime-neutral persistence
-> explicit read-only legacy projection requiring exactly two items
```

The acquisition owner has no transport. Live-tail and backfill are schema/plan
modes only; neither was executed or connected. A backfill/live-tail observation
requires a cursor range. Continuity is exactly `CONTIGUOUS`, `GAPPED`,
`UNKNOWN`, or `BLOCKED_CONTRACT`; advancement past a non-contiguous range is
rejected before persistence.

Capacities are separate:

- `candidate_acquisition_capacity M = 2N`;
- `candidate_reserve_target R = N + ceil(N/2)`;
- `selection_capacity N`, bounded 1 through 16;
- `approved_active_memory_capacity = 2`, immutable.

## Schema and migration

Migration: `048_candidate_acquisition_foundation.sql`.

It repairs the confirmed migration-046 code/schema mismatch by rebuilding
`printer_discovery_exhaustion_certificates` with
`TRACKING_STATE_CAPACITY_BLOCKED` in its CHECK while preserving all existing
columns and rows. It then adds normalized tables for:

- acquisition policies and executions;
- source rounds and immutable normalized observations;
- exact candidate identities and observation overlap links;
- cursor ranges and continuity;
- staged categorical evidence;
- immutable certificates;
- durable reserve membership/version;
- exact-N runtime-neutral manifests/items;
- structured failure/exhaustion records; and
- immutable canonical reports/replay identity.

Certificate, manifest, manifest-item, and report UPDATE/DELETE operations are
blocked by triggers. Constraints preserve M=2N, R=N+ceil(N/2), active capacity
two, runtime neutrality, exact manifest count, identity uniqueness, and
canonical failure families.

Disposable proof results:

| Migration proof | Result |
| --- | --- |
| fresh empty temporary DB, migrations 001–048 | PASS; integrity `ok`; zero FK violations |
| disposable byte copy of authoritative DB, forward migration 048 | PASS; integrity `ok`; zero FK violations; latest 048 |
| existing-row preservation / CHECK repair | PASS; prior rows copy through rebuild; new blocked classification inserts successfully |
| rollback/restore approach | restore the pre-migration byte-identical backup; no reverse/destructive migration is used |

The authoritative database was never opened for migration or foundation
persistence.

## Frozen offline capacity matrix

Fixture: `tests/fixtures/candidate_acquisition_capacity_v1.json`.
Evidence status: `SYNTHETIC_MECHANICS_ONLY`.

| N | M=2N qualifying inputs | exact-N success | N-1 qualifying inputs | all-or-none failure | N>2 runtime neutral / legacy adapter |
| ---: | ---: | --- | ---: | --- | --- |
| 2 | 4 | PASS, 2 selected | 1 | PASS, 0 selected/no manifest | two-item read-only projection accepted |
| 3 | 6 | PASS, 3 selected | 2 | PASS, 0 selected/no manifest | neutral; adapter rejected |
| 4 | 8 | PASS, 4 selected | 3 | PASS, 0 selected/no manifest | neutral; adapter rejected |
| 5 | 10 | PASS, 5 selected | 4 | PASS, 0 selected/no manifest | neutral; adapter rejected |
| 6 | 12 | PASS, 6 selected | 5 | PASS, 0 selected/no manifest | neutral; adapter rejected |
| 7 | 14 | PASS, 7 selected | 6 | PASS, 0 selected/no manifest | neutral; adapter rejected |
| 10 | 20 | PASS, 10 selected | 9 | PASS, 0 selected/no manifest | neutral; adapter rejected |
| 16 | 32 | PASS, 16 selected | 15 | PASS, 0 selected/no manifest | neutral; adapter rejected |

Additional Gate 4 proofs passed:

- reversed input order produces the same manifest and ordered item hashes;
- cross-source overlap preserves provenance but creates one candidate identity;
- cross-mint pool conflicts become structured identity failures;
- a source outage reports `SOURCE_PROVIDER_FAILURE`, not market shortage;
- budget exhaustion reports `BUDGET_EXHAUSTION`;
- stale, unsupported, malformed, conflicting and incomplete Pump evidence cannot
  be admitted;
- exact Pump, non-Pump and unknown-origin branches coexist without forced
  lineage;
- cursor advancement across a gap is rejected;
- same-execution rerun and read-only zero-source replay are deterministic,
  idempotent, and byte-non-mutating;
- certificate immutability and fresh requalification/reserve-version increments
  are enforced;
- forbidden memory/retrieval/decision/position/trade/audit/PnL and Scheduler/
  tracking tables have zero deltas.

## Verification and totals

Focused final foundation suite:

```text
25 passed
```

Affected contract/regression slices:

- Source Registry / Source Governor: 15 passed;
- production-readiness canonical migration ledger: 16 passed;
- post-selection lifecycle plus production-readiness rerun: 27 passed;
- disposable fresh/copy migration integrity checks: PASS/PASS;
- static AST and `git diff --check`: PASS.

Broad relevant suite final target covers candidate foundation, Source Governor,
Scheduler priority, DexScreener, GeckoTerminal, PumpPortal compatibility,
PumpSwap confirmation/resolution, direct migration compatibility, discovery
productivity, lifecycle integrity, migration/readiness, eligible-supply
architecture, and durable supervision. Final recorded result after the closeout
rerun: **333 passed, 4 subtests passed**.

One baseline failure remains explicitly outside this lane:
`tests/test_phase1_database_schema.py::test_migration_runner_is_idempotent`
hard-codes migrations only through 034 even though required starting HEAD
already contained migrations through 047. It was confirmed against the required
baseline and was not weakened or broadened into this lane.

## Authoritative DB hashes

| Point | SHA-256 |
| --- | --- |
| before Gate 1 | `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872` |
| after Gate 3 disposable migrations | `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872` |
| after Gate 4 frozen proof | `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872` |

Result: byte-identical.

## Files changed

Active authority and lane documentation:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-memory-growth-build-order-v2.md`;
- `docs/printer-v1-assistant-active-build-order-anchor.md`;
- prior roadmap-adoption clarification;
- combined audit, complete design, and this implementation closeout.

Production foundation:

- migration 048;
- `candidate_acquisition.py`;
- `pump_contracts.py`;
- fixture-only `birdeye.py`;
- source registry and Source Governor request-kind changes.

Verification:

- frozen capacity fixture;
- new focused foundation suite;
- directly affected Source Registry and canonical migration/lifecycle test
  expectations updated from the prior canonical state to migration 048.

No unrelated application owner was refactored.

## Money-usefulness contribution

This foundation improves Printer's ability to find a sufficient eligible pool
without confusing source coverage, provider failure, budget exhaustion, stale
evidence, identity failure, admission failure, and real market shortage. It
retains exact source overlap and categorical evidence, moves expensive checks
behind deterministic cheap gates, and creates replayable reserve/manifest
artifacts. That improves future paper-memory intake realism and auditability.

It creates no profit, trade, decision, position, PnL, or claim that real-market
candidate reliability is already sufficient.

## What improved

- Pump-exclusive candidate-universe drift is corrected.
- Exact current source dispositions are pinned and report-honest.
- The prior presence-only Pump migration proof is not used by the foundation;
  its strict surface checks instruction, account, PDA, Pool, LP, and vault facts.
- Generic bounded N mechanics work through 16 without changing runtime capacity.
- Candidate identity, overlap, categorical admission, certificate, reserve,
  exact-N selection, manifest, failures, report and replay are durable.
- `TRACKING_STATE_CAPACITY_BLOCKED` now persists under migration 048.
- Provider outage, budget exhaustion and identity conflict no longer collapse
  into market shortage or raw SQLite errors.

## What remains locked / not touched

- authoritative DB and operational campaign state;
- all live provider, RPC, WebSocket, discovery and backfill execution;
- existing Scheduler execution and operational Memory Factory runner;
- active capacity above two and every N>2 runtime handoff;
- selective-1h proof and 1h/4h/12h/24h production expansion;
- retrieval activation and dirty-memory retrieval;
- paper decisions, BUY, SELL, HOLD;
- positions, trade events, paper-trade audits, PnL;
- wallets, private keys, signing, real funds, live execution;
- paid dependencies, scoring, ranking, confidence, weighting, embeddings and
  vectors;
- `WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

| Category | Residual item | Required handling |
| --- | --- | --- |
| reliability evidence | fixture matrix is synthetic, not independently frozen qualifying market windows | no 99% or production reliability claim; separately design and collect an authorized sample |
| live integration | owner is intentionally transport-free; no live-tail/backfill integration was authorized | next lane must be read-only readiness first; no source run |
| Pump contract drift | future instruction/account/Pool extensions may invalidate the pin | fail `BLOCKED_CONTRACT`; refresh official commit and hashes before later live adoption |
| RPC history | program-wide migration history may be expensive or pruned | bounded pages, honest `GAPPED`/`UNKNOWN`, no cursor advancement past unresolved facts |
| Birdeye availability | optional free route requires account/API key and monthly CU budget | secret reference only; absence is source unavailable, never paid fallback or shortage |
| DEXTools/PumpPortal | compliant current contracts are not adopted | no adapter; do not guess or silently use them |
| holder/safety cost | expensive evidence still scales with admitted intake | preserve cheap gate order and frozen request-round budgets |
| reserve concurrency | this lane proves one atomic owner offline, not multi-process live contention | review transaction/lease ownership before any live integration |
| baseline test debt | Phase 1 migration test is stale at the required baseline | separate narrow test-maintenance task only if operator schedules it |

## Exact next permitted task

`V2-9.8B Post-Foundation Integration and Activation-Readiness Audit`

That task is read-only. It must reconcile how this runtime-neutral foundation
would integrate with the existing Scheduler/Source Governor/operational command,
confirm lease and source-budget ownership, define a bounded live proof proposal,
and decide whether a later implementation/adoption lane is safe. It must not run
the published operational command, call a live source, mutate the authoritative
DB, raise active capacity above two, or unlock retrieval or financial features.
