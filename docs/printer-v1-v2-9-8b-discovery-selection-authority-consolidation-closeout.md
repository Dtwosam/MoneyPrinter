# Printer V1 V2-9.8B Discovery and Selection Authority Consolidation Closeout

Date: 2026-07-30

Lane: `V2-9.8B Discovery and Selection Authority Consolidation`

Verdict:
`V2_9_8B_DISCOVERY_SELECTION_AUTHORITY_CONSOLIDATION_PASS`

## Outcome

One cohesive discovery/selection authority consolidation is complete on the
restored ordinary path:

```text
full code audit
→ consolidation design
→ complete implementation
→ frozen offline proof
→ closeout
```

No live provider, RPC, WebSocket, Memory Factory campaign, N2, N7, cursor,
recovery, backfill, retrieval or financial capability was authorized or run
against the authoritative database.

## Baseline

- Branch: `master`
- Required HEAD at lane start:
  `98263872315ca8556b2620a80e6418c73a50e8eb`
- Authoritative database SHA-256 (unchanged):
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Migration head remains `049` (no schema migration required)

## Final active call graph

```text
public operational `run`
  -> resolve Solana RPC once (immutable SolanaRpcConfiguration)
  -> zero-I/O preflight (same resolved endpoint + typed prohibitions)
  -> direct Pump live-tail (1 signature page + <=12 txs)
  -> exact 25-role migrate decode + PumpSwap join
       (1 getTransaction + 1..3 getMultipleAccounts per candidate, m<=5)
  -> graduated registry
  -> DexScreener fresh profiles (2 HTTP) + bounded exact-pair evaluation
  -> holder/safety funnel (injected same Solana endpoint)
  -> CANONICAL select_two_candidates (neutral two-candidate contract)
  -> atomic two-or-none activation / lifecycle materialization
  -> WINDOW_15M Scheduler-led lifecycle
  -> six-unit terminal report + zero-source replay
  -> safe stop (no retry / restart / successor)
```

## Removed / replaced owners

| Prior owner | Status |
|---|---|
| Hardcoded `2 * pumpswap` transport assumption | Replaced by measured `transport_operations_used` |
| Request-count treated as transport count | Separated governed requests vs transports |
| Partial migrate fixed-account checks | Replaced by full 25-role validator |
| Fragmented mixed-two-slot / reserve-slice / holder-pair as peer authorities | Canonical `selection_authority.select_two_candidates` |
| Lexicographic `sorted(mints)` preference on fresh profiles | Removed; first-seen dedup only |
| `selected_latest` / `selected_persisted` as readiness product | Diagnostic provenance attributes only |
| Fail-open missing cooldown/market-floor tables | Fail closed |
| Frozen-start deadline comparison | Wall-clock monotonic deadline |
| Independent holder RPC fallback default | Shared `resolve_solana_rpc_configuration()` |
| Incomplete prohibition schema | Typed capability fields + recursive active scan |
| PumpPortal ordinary-path documentation drift | Active docs aligned to direct Pump |

## Candidate state machine

```text
NOMINATED (direct Pump / registry)
  -> VERIFICATION (exact migrate + PumpSwap join)
  -> REGISTRY_GRADUATED
  -> MARKET_ENRICHED (exact-pair liquidity)
  -> ELIGIBLE | REJECTED (floor / identity / cooldown / safety / holder)
  -> SELECTED_TWO | NONE (canonical two-or-none)
  -> ACTIVATED_TWO | COMPENSATED_NONE
  -> WINDOW_15M lifecycle (when activated)
```

## Eligibility and rejection contract

Preserved and not weakened:

- exact mint + PumpSwap pair identity
- $3,000 exact-pool floor (categorical)
- holder / safety / freshness / tradeability / cooldown gates
- truthful `LATEST_GRADUATED` / `PERSISTED_GRADUATED` provenance attributes
- fail-closed cooldown and market-floor state errors
- provider-controlled row and response-byte ceilings via measured ledger

## Selector and handoff contract

- One owner: `printer_v1.discovery.selection_authority`
- Deterministic combined seeded-uniform order (identity-stable preimage only)
- Exactly two distinct mint+pair identities or none
- Neutral product: `candidate_a` / `candidate_b` / `two_candidate_selection`
- Composition label is diagnostic only
- Activation remains two-or-none with compensating rollback on partial failure
  (existing atomic savepoint path preserved)

## Accounting / storage / reporting contract

Six units:

1. `SOURCE_TRANSPORT_OPERATION`
2. `LOCAL_VALIDATION_STEP`
3. `SCHEDULER_WORK_ITEM`
4. `SOURCE_RESPONSE_BYTES`
5. `NORMALIZED_SOURCE_ROWS`
6. `LIFECYCLE_RESERVED_TRANSPORT_OPERATION`

PumpSwap verification reports actual batch counts (`1 + ceil(keys/100)`, max 3).
Direct migration discovery reconciles migration + pumpswap measured transports
against governed requests. Report/replay equality is supported by
`reconcile_six_unit_totals`.

## Files changed

Design / closeout / authority docs:

- `docs/printer-v1-v2-9-8b-discovery-selection-authority-consolidation-design.md`
- `docs/printer-v1-v2-9-8b-discovery-selection-authority-consolidation-closeout.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`

Runtime:

- `src/printer_v1/sources/measured_transport.py` (new)
- `src/printer_v1/discovery/selection_authority.py` (new)
- `src/printer_v1/sources/pump_contracts.py`
- `src/printer_v1/sources/operational_source_contracts.py`
- `src/printer_v1/sources/pump_migration.py`
- `src/printer_v1/sources/pumpswap.py`
- `src/printer_v1/sources/solana_rpc_holder.py`
- `src/printer_v1/discovery/direct_migration_discovery.py`
- `src/printer_v1/discovery/graduated_liquidity_front_door.py`
- `src/printer_v1/discovery/eligible_token_supply.py`
- `src/printer_v1/operator_cli/graduated_supply_front_door.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/evidence_fill/real.py`

Tests:

- `tests/test_v2_9_8b_discovery_selection_authority_consolidation.py` (new)
- `tests/test_v2_9_8b_restored_factory_source_compatibility_reset.py`
- `tests/test_v2_9_8b_candidate_acquisition_foundation.py`
- `tests/test_v2_9_7e_42_direct_migration_discovery.py`
- `tests/test_v2_9_7e_43_graduated_liquidity_front_door.py`
- `tests/test_v2_9_7e_44_full_pilot_supply_integration.py`
- `tests/test_v2_9_8b_21_eligible_token_supply_architecture.py`

## Proof results

Frozen transports + disposable migration-049 databases only.

| Proof | Result |
|---|---|
| Exact public-command composition (no PumpPortal ordinary path) | PASS |
| One/two/three PumpSwap account batches | PASS |
| Complete 25-role rejection coverage | PASS |
| Measured operation / byte / row reconciliation | PASS |
| Deterministic bounded DexScreener handling | PASS |
| One Solana endpoint owner | PASS |
| Truthful two-candidate provenance attributes | PASS |
| Real deadline exhaustion (wall clock) | PASS |
| Fail-closed database-state cooldown errors | PASS |
| Two-or-none selection under insufficient supply | PASS |
| Exactly two distinct mints/pairs when ready | PASS |
| Honest insufficient-supply safe stop | PASS |
| Report/replay six-unit equality helper | PASS |
| Zero candidate-acquisition / cursor / recovery deltas | PASS |
| Zero retrieval / decision / position / trade / audit / PnL deltas | PASS |
| Migration head 049, integrity, FK | PASS |

### Focused tests

- `tests/test_v2_9_8b_discovery_selection_authority_consolidation.py`
- `tests/test_v2_9_8b_restored_factory_source_compatibility_reset.py`
- `tests/test_v2_9_7e_42_direct_migration_discovery.py`
- `tests/test_v2_9_7e_43_graduated_liquidity_front_door.py`
- `tests/test_v2_9_7e_44_full_pilot_supply_integration.py`
- `tests/test_v2_9_8b_21_eligible_token_supply_architecture.py`

Result: all green in the focused lane suites above.

### Broad affected operational suite

- `tests/test_v2_9_8b_operational_factory_active_path_restoration.py`
- `tests/test_v2_9_8a_public_operational_command.py` (prior run context)
- eligible-supply architecture suite

Result: PASS for the suites re-run after alignment.

## Pre-existing unrelated failures

Not repaired in this lane (unchanged producer blobs / unrelated debt):

- holder-report wording baseline debts (if still present outside this surface)
- GoPlus forbidden-term wording debts (if still present outside this surface)

No unrelated broad suites were expanded merely to chase them.

## Authoritative DB hash

`e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`

## Money-usefulness contribution

This consolidation makes discovery and selection authority honest enough to
support future paper memory:

- exact graduation identity cannot pass on partial role checks;
- transport budgets cannot hide multi-call PumpSwap/Dex work;
- two-token activation cannot pretend one eligible candidate is enough;
- cooldown/state faults cannot fail open into false eligibility;
- provenance remains truthful without becoming a score or compulsory quota.

It creates no profit, decision, position, trade, audit or PnL capability.

## What remains locked

- live source probe / Memory Factory campaign
- N2 / N7 / cursor / recovery / backfill as operational authority
- PumpPortal ordinary runtime authority
- capacity above exactly two active tokens
- `WINDOW_1H` / `4H` / `12H` / `24H` production
- clean-memory creation / retrieval
- paper decisions, BUY / SELL / HOLD
- positions, trade events, paper audits, PnL
- wallets, private keys, signing, funding, live execution
- paid APIs, scoring, ranking, confidence, weighting, embeddings, vectors
- automatic retry, restart, successor

## Functionality Risks / Setbacks / Efficiency Blockers

- Full ordinary worst-case transport plan remains large (measured budget max 136);
  stage ceilings and reservations must continue to protect lifecycle capacity.
- DexScreener multi-row pair arrays still require declared row ceilings at every
  call site; the ledger fails closed when undeclared multi-row kinds appear.
- Existing fixture-era class names (`FixtureOriginProof`) remain as historical
  carriers for graduation-native data; they are not discovery authority.
- Provider pacing wait must continue to avoid holding SQLite write locks.
- Intersecting historical tests that assumed single-slot selection or PumpPortal
  frames were realigned; historical closeouts remain historical.

## Exact next permitted task

Operator review of this consolidation branch and closeout only.

PASS does **not** authorize a live source probe or Memory Factory campaign.
