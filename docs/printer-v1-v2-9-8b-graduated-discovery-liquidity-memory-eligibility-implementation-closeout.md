# V2-9.8B Graduated Discovery, Early Liquidity and Memory-Eligibility Implementation Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Graduated Discovery, Early Liquidity and Memory-Eligibility Implementation`

Verdict: `V2_9_8B_GRADUATED_DISCOVERY_LIQUIDITY_MEMORY_ELIGIBILITY_IMPLEMENTATION_PASS`

## Baseline

| Item | Value |
|---|---|
| Repository | `MoneyPrinter` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Baseline HEAD | `c7dd3a7a90118f5369bcb33784789ca3d7550143` |
| Subject (baseline) | Design graduated discovery and memory eligibility |
| Mode | Implementation + focused offline proof only |
| Not run | Providers, discovery runtime, Scheduler, authorization, `WINDOW_15M`, memory generation, retrieval, decisions, positions, trades, audits, PnL |

Untracked operator evidence and authorization packages under `operator-runs/` were preserved. `/private/tmp/mp-preclaim` was not touched.

## Exact files changed

### Production

- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`

### Schema

- `migrations/052_memory_observation_eligibility_layers.sql`

### Tests

- `tests/test_v2_9_8b_graduated_discovery_liquidity_memory_eligibility.py` (new)
- `tests/test_v2_9_8b_governed_pumpswap_account_batch_confirmation.py` (seed liquidity / unsupported venue expectations)
- `tests/test_v2_9_8b_permanent_discovery_conversion_repair.py` (protocol-due liquidity seeds)
- `tests/test_v2_9_8b_permanent_discovery_availability.py` (migration head + Gecko nomination shape)

### Documentation

- `docs/printer-v1-v2-9-8b-graduated-discovery-liquidity-memory-eligibility-implementation-closeout.md` (this file)

## Failing tests observed before implementation

Strict red-green-refactor was applied. Before production behavior existed, the new focused suite failed on:

1. Fresh nomination discarding `liquidity_usd` / provenance / evidence expiry.
2. All fresh nominations entering protocol without floor prefilter.
3. Below-floor rows still protocol-eligible.
4. Confirmed rows requiring a second market-batch operation to become market-ready.
5. Freeze input gated on `fully_eligible` / holder pass rather than observation eligibility.
6. Protocol queue accepting `stage_evidence_sink` but never sealing campaign stage evidence.
7. Reserve layer CHECK rejecting `MEMORY_OBSERVATION_ELIGIBLE` / `ABOVE_FLOOR_NOMINATED`.

Existing protocol-queue tests then failed after prefilter landed until seeds included above-floor exact-pool liquidity (expected).

## Implemented source and stage flow

```text
Pump migration/registry
+ DexScreener fresh (liquidity preserved)
+ GeckoTerminal fresh (liquidity preserved)
+ persisted due/revival candidates
→ exact-pool market prefilter ($3,000)
→ ABOVE_FLOOR_NOMINATION → protocol confirmation due
→ BELOW_LIQUIDITY_FLOOR / LIQUIDITY_UNKNOWN / UNSUPPORTED_VENUE → no protocol
→ PumpSwap account confirmation (above-floor only)
→ join retained unexpired exact-pool liquidity
→ MEMORY_OBSERVATION_ELIGIBLE (direct promotion)
→ holder/manipulation context enrichment (non-blocking for memory)
→ bounded observation reserve
→ deterministic neutral freeze → 2 selected + 2 alternates
```

Early protocol confirmation now runs after fresh intake and before market batches consume residual promotion capacity. Residual protocol work remains available after the market walk for any later above-floor due rows.

## Liquidity preservation and floor behavior

- DexScreener `pool_observations` now carry exact-pool `liquidity_usd`.
- GeckoTerminal new-pool nomination retains `reserve_in_usd` / liquidity into the nomination object.
- `record_fresh_pool_nominations` persists mint, pool, base/quote, venue, liquidity, observation time, evidence expiry, request/response IDs, and provider contract version in exact-market provenance and reserve evidence JSON.
- Floor remains `$3,000` (`SELECTION_FLOOR_USD`).
- Outcomes:
  - `>= 3000` → `ABOVE_FLOOR_NOMINATION` + `ABOVE_FLOOR_NOMINATED` layer → protocol due
  - `< 3000` → `BELOW_LIQUIDITY_FLOOR` → zero protocol transport
  - missing → `LIQUIDITY_UNKNOWN` → not protocol-due (bounded market backup remains the registry/persisted path)
  - unsupported venue → candidate-local `UNSUPPORTED_VENUE` at nomination
  - incomplete mint/pool/orientation → exclusion / identity fail-closed

Never borrows token-wide liquidity, never substitutes another pool, never lowers the floor.

## Removal of unnecessary graduation re-proof

DexScreener and GeckoTerminal candidates do not require a separate Pump migration transaction or graduated-registry membership before market evaluation, protocol confirmation, or memory observation. Provenance is labelled `MARKET_SOURCE_OBSERVATION`, not migration proof.

## Exact pool protection retained

Protocol confirmation still requires:

- account existence;
- owner equals supported PumpSwap program;
- exact expected mint at `base_mint@43`;
- candidate-local mismatch outcomes;
- no unsupported venue activation.

## Memory / action eligibility separation

New reserve layer: `MEMORY_OBSERVATION_ELIGIBLE`.

Qualifies on identity, exact pool protocol confirmation, fresh exact-pool liquidity ≥ $3,000, no unresolved conflict, lawful tracking state, and complete governed provenance/expiry.

Does **not** require:

- `HOLDER_CONCENTRATION_HEALTHY`;
- holder evidence complete;
- future action eligibility.

Explicit context fields travel with candidates:

```text
memory_observation_eligible = true
holder_condition = HOLDER_CONCENTRATION_EXTREME | ...
holder_evidence_status = COMPLETE | SOURCE_UNAVAILABLE_OR_INCOMPLETE
future_action_eligibility = BLOCKED_OR_UNKNOWN
```

`FULLY_ELIGIBLE` is retained only for future action-specific policy and no longer controls memory freeze input.

## Reserve and freeze behavior

- `MINIMUM_FREEZE_DEPTH = 4`
- `OBSERVATION_SURPLUS_TARGET = 8`
- Depth status helper reports freeze met / surplus not met / honest coverage blocker.
- Freeze from observation-eligible rows only: deterministic neutral order → 2 selected + 2 alternates.
- Distinct mints and pools; evidence freshness required.
- No score, rank, confidence, weight, popularity, liquidity preference, or provider preference.
- Flat 30-operation ceiling and stage reservations `3/2/6/7/8/4` unchanged.

## Protocol stage-accounting repair

`process_protocol_confirmation_queue` now:

- measures one stage ledger spanning its account batches;
- records each transport identity exactly once;
- records one named local-validation identity per processed member;
- seals `PROTOCOL_CONFIRMATION` with immutable stage id / sequence / terminal status / first cause;
- attaches source request/response/failure IDs, outcome counts, and member counts;
- emits through `stage_evidence_sink` exactly once per logical protocol stage when campaign/run/cycle identities are present.

Action-local evidence is not copied into the campaign owner; both surfaces observe independently.

## Source-request reconciliation repair

Protocol report now includes `source_request_coverage` entries:

```text
source_request_id
source_name
request_kind
logical_stage_id
transport_identity_count
normalized_member_count
terminal_status
```

Helper `build_source_request_coverage_manifest` deduplicates by durable request ID. Request count and transport count remain separate surfaces. Supply diagnostics expose protocol coverage under `protocol_confirmation`.

## Focused test results

| Suite | Result |
|---|---|
| `tests/test_v2_9_8b_graduated_discovery_liquidity_memory_eligibility.py` | **21 passed** |
| `tests/test_v2_9_8b_governed_pumpswap_account_batch_confirmation.py` | passed (with liquidity seed updates) |
| `tests/test_v2_9_8b_permanent_discovery_conversion_repair.py` | passed |
| `tests/test_v2_9_8b_permanent_discovery_availability.py` | passed |
| `tests/test_v2_9_8b_multi_round_market_batch_six_unit_sequencing.py` | passed |
| Combined affected discovery/protocol/sequencing | **86 passed** |
| `python -m compileall` on changed modules | OK |
| `git diff --check` | OK |

### Behaviors proven (minimum required set)

1. DexScreener fresh nomination preserves exact-pool liquidity and provenance  
2. GeckoTerminal fresh nomination preserves exact-pool liquidity and provenance  
3. Below-floor candidates consume zero protocol confirmations  
4. Liquidity-unknown candidates do not enter the protocol queue  
5. Above-floor candidates enter protocol confirmation  
6. Confirmed candidates promote using retained unexpired liquidity without a second market request  
7. Expired evidence requires revalidation rather than silent promotion  
8. Owner mismatch and base-mint mismatch remain candidate-local blockers  
9. Dex/Gecko candidates require no separate graduation proof  
10. `HOLDER_CONCENTRATION_EXTREME` remains memory context and does not remove observation eligibility  
11. Future action eligibility remains blocked or unknown  
12. Freeze chooses two selected and two alternates deterministically from four+ observation-eligible rows  
13. Selection ignores liquidity magnitude, source order, holder condition, and provider popularity  
14. Protocol confirmation emits one sealed stage with transport and local-validation identities  
15. Durable source requests reconcile to a logical stage via coverage manifest  
16. Request counts and transport counts remain separately correct  
17. Honest insufficient coverage produces durable depth status / terminal-ready report surface  
18. Stage ceilings and flat 30 ceiling unchanged  
19. Market-batch stage sequencing helpers remain monotonic  
20. No Source Governor bypass (protocol uses governed requests)

## Schema / migration result

Migration **052** added:

- `ABOVE_FLOOR_NOMINATED`
- `MEMORY_OBSERVATION_ELIGIBLE`

to `printer_discovery_reserve_layers` via table recreation with row copy (CHECK expansion). Proven:

- fresh database application;
- upgrade from prior head (050 → full apply reaches 052);
- foreign keys and integrity checks;
- affected row persistence for new layers;
- no authoritative DB mutation beyond structural migration.

Exact-market state enum was **not** expanded; prefilter outcomes use existing states plus reason codes (`ABOVE_FLOOR_NOMINATION_REQUIRES_PROTOCOL_CONFIRMATION`, `LIQUIDITY_UNKNOWN`, `BELOW_3000_FLOOR`).

## Money-usefulness contribution

Printer can now:

- keep the market liquidity it already paid to observe;
- avoid wasting protocol capacity on below-floor pools;
- promote confirmed graduated/fresh PumpSwap pools without a dead-end second market-batch dependency;
- admit concentrated-holder and manipulation-context tokens into memory observation while keeping future paper action locked;
- freeze a neutral two-plus-two set from a bounded observation reserve with honest coverage accounting.

This increases the chance of building useful clean memories from real Solana Pump/PumpSwap conditions without unlocking trading.

## What remains locked

- live funds, wallets, private keys;
- paid APIs;
- Source Governor / Central Scheduler bypass;
- scoring / ranking / confidence systems;
- retrieval, paper decisions, BUY/SELL/HOLD;
- positions, trades, trade audits, PnL;
- lowering the $3,000 floor;
- raising the flat 30-operation ceiling in this lane;
- unsupported venues (e.g. Meteora).

## Proof still required

Per design §21, after this offline PASS:

1. fixture-driven integrated campaign proving ≥8 observation-eligible candidates;
2. exact operation/stage accounting and durable blocked-report emission under insufficient coverage;
3. HEAD review;
4. separate one-use authorization;
5. exactly one canonical real `WINDOW_15M` attempt;
6. PASS only for authoritative lifecycle completion and clean memory.

This closeout does **not** authorize a live campaign.

## Functionality Risks / Setbacks / Efficiency Blockers

- Dex/Gecko liquidity may be missing or stale; unknown liquidity still needs the bounded market-backup path for registry/persisted rows.
- Provider-visible pools may still fail owner/mint confirmation; protocol remains mandatory for above-floor nominations.
- Observation-eligible concentrated tokens are useful for learning but remain action-ineligible.
- Eight-candidate surplus may not be reached within a short campaign; minimum four remains the lifecycle gate.
- Source rate limits may still reduce fallback coverage; candidate-local handling continues.
- Protocol stage sealing requires campaign/run/cycle identities; callers without those still get outcomes but no sealed stage block.
- Residual vs early protocol stage sequences (1 then 2) must remain monotonic in live composition proof.
- Pre-existing untracked live-run artifacts remain necessary for any later per-identity forensic audit of the 25→1 event; they were not required for this offline implementation.

## Verdict

`V2_9_8B_GRADUATED_DISCOVERY_LIQUIDITY_MEMORY_ELIGIBILITY_IMPLEMENTATION_PASS`
