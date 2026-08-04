# V2-9.8B Permanent Discovery Availability Design

Date: 2026-08-04

Lane: `V2-9.8B — Permanent Discovery Availability Implementation`

Contract authority: operator-approved implementation prompt plus the active Printer V1 source stack

## Verdict and blocker classification

```text
BLOCKER CLASSIFICATION: MISSING_APPROVED_IMPLEMENTATION_BOUNDARY
CODE CHANGE JUSTIFIED: YES
```

The active production path has a canonical persistent eligible-token-supply owner, exact Pump migration verification, a `$3,000` exact-pool market gate, holder/safety admission, neutral selection, and atomic two-slot Scheduler handoff. It does not have the approved permanent exact mint+pool state boundary, batch-first current-market resolution, mint-level reconciliation cascade, protected stage capacity, or four-candidate fully eligible reserve. The repeated exact-pair no-match spend proven by the 2026-08-04 exhaustion audit is a committed behavior defect inside that missing boundary.

Evidence used:

- baseline `68f8770a126f3345b344fa4fc43af60ee10425b4` on the required branch;
- `docs/printer-v1-v2-9-8b-strengthened-discovery-operation-budget-exhaustion-audit.md` proves 22 exact-pair no-matches, 16 repeated within about 55 minutes, and 11 lawful persisted mints left unexplored at the ceiling;
- `run_persistent_eligible_token_supply` is the active canonical reserve/traversal owner;
- `build_graduated_supply` is its production composition boundary;
- `AuthoritativeLiveOperationalCampaignOwner.run_operational` owns holder/safety admission and passes the final two into the existing lifecycle driver;
- `CombinedDiscoveryExecutor._atomic_initial_two_slot_handoff` owns the transactional two-slot Scheduler handoff and rollback.

No provider outage, database-state defect, operator-input defect, or capability unlock can implement the approved missing boundary. Repairing only one stale pair or increasing the budget would leave the structural defect intact.

## Current production ownership map

| Path stage | Production owner | Classification | This lane |
|---|---|---:|---|
| nomination | direct Pump migration + DexScreener fresh-profile locator | `DEFECTIVE` | retain both; make Dex fresh rows canonical nominations and add approved Gecko fresh-pool nominations |
| candidate reserve | `run_persistent_eligible_token_supply` + `printer_eligible_token_reserve` | `DEFECTIVE` | keep this owner; add durable broad, market-ready and fully eligible layers keyed by exact mint+pool |
| market validation | `run_graduated_liquidity_front_door` individual exact-pair calls | `DEFECTIVE` | definitive local checks, then one governed Dex mint batch of up to 30, then targeted calls only for unresolved/conflicted/changed pools |
| migration/re-entry | direct Pump/PumpSwap registry plus exact-pair recheck | `DEFECTIVE` | preserve canonical migration proof, add no-match suppression, same-pool revival and different-pool pending-proof reconciliation |
| holder/safety | authoritative campaign `_evaluate_holder_eligibility` | `ALREADY_CORRECT` for gates; `DEFECTIVE` for depth | call only for market-ready survivors and continue until four fully eligible or honest terminal |
| eligibility | market floor + existing holder/safety/tracking/cooldown/STNP gates | `ALREADY_CORRECT` for thresholds; `DEFECTIVE` for reserve depth | preserve every gate and evidence TTL; freeze four distinct eligible mints |
| selection | `selection_authority.select_two_candidates` | `ALREADY_CORRECT` | reuse unchanged neutral seeded selection over the frozen eligible set; retain the two unselected rows as alternates |
| Scheduler/tracking handoff | existing lifecycle driver and atomic two-slot handoff | `ALREADY_CORRECT` | atomically recheck selected identities; retain rollback and no-partial-activation law |
| terminal reporting | eligible-supply diagnostics + campaign report | `DEFECTIVE` | add exact nominations, mint/pools, batch sizes, transitions, stage calls, reserve counts, alternates, unexplored work and exact terminal reason |

## Contract pins refreshed for changed code

Only official primary sources are adopted:

- DexScreener API Reference, checked 2026-08-04: `/tokens/v1/{chainId}/{tokenAddresses}` accepts at most 30 comma-separated addresses. Pin: `DEXSCREENER_TOKENS_V1_2026_08_04`, cap 30.
- CoinGecko/GeckoTerminal Keyless Public API, checked 2026-08-04: the keyless v2 root is supported and throttling is dynamic/IP-based. Printer keeps the stricter fixed 10 requests/minute, six-second spacing and zero retry. New-pool responses remain capped at 20 per page and describe the preceding 48 hours. Pin: `GECKOTERMINAL_KEYLESS_V2_2026_08_04`.
- Pump official `pump-public-docs` HEAD `9c82f61cb711b044a17f770ab8ce9f9bdf78f333`: current quote-mint-aware Pump/PumpSwap layouts are authoritative. PumpSwap liquidity interpretation must use effective quote reserves (`quote vault amount + virtual_quote_reserves`). Unknown older/newer layout variants or quote mints fail `CONTRACT_BLOCKED`.
- Solana official `getMultipleAccounts`, checked 2026-08-04: at most 100 addresses, results aligned to request order. Printer preserves one per-account outcome and provenance; one null or malformed member does not fabricate facts for its siblings. Pin: `SOLANA_GET_MULTIPLE_ACCOUNTS_2026_08_04`.

These pins do not authorize retries, additional providers, paid access, wallets, transactions, or live execution beyond the separately authorized one-shot attempt.

## Permanent exact-market persistence

Migration 051 adds:

1. `printer_exact_market_states`, one current projection row per exact `(network, mint, pool)`;
2. `printer_exact_market_state_transitions`, append-only history for every categorical transition;
3. `printer_discovery_reserve_layers`, one durable row per `(network, mint, pool, layer)` for `BROAD_NOMINATED`, `MARKET_READY`, and `FULLY_ELIGIBLE`.

Exact-market rows retain network, mint, pool, token program, pool program, base mint, quote mint, venue, categorical state/reason, observation/visibility/no-match times, no-match count/streak, next lawful action, latest source provenance and contract version. The state set is exactly:

`CURRENT_VISIBLE`, `BELOW_LIQUIDITY_FLOOR`, `EXACT_POOL_NO_MATCH`, `POOL_RECONCILIATION_DUE`, `SAME_POOL_REOBSERVED`, `NEW_POOL_PENDING_PROOF`, `CURRENT_POOL_CONFIRMED`, `NO_SUPPORTED_CURRENT_POOL`, `SOURCE_UNAVAILABLE`, `IDENTITY_CONFLICT`, `UNSUPPORTED_VENUE`, `CONTRACT_BLOCKED`.

History rows cannot be updated or deleted. Projection identity fields cannot change. A new pool creates another projection identity; it never replaces or deletes the historical pool. A lawful no-match records `EXACT_POOL_NO_MATCH`, increments no-match history, sets the next lawful reconciliation boundary, then records/queues `POOL_RECONCILIATION_DUE` without another direct exact-pair poll before that boundary.

## Canonical mint-first funnel

The existing eligible-token-supply entry point remains the sole active acquisition/reserve owner. It merges observations by exact mint and exact pool while retaining every source contribution. The deferred candidate-acquisition cursor runtime remains deferred and is not consulted.

The broad reserve admits categorical observations from:

- finalized direct Pump migration;
- fresh DexScreener Solana profiles plus their batch materialization;
- approved GeckoTerminal Solana fresh pools;
- persisted reserve or graduated-registry rows whose `next_lawful_action_at` is due;
- same-pool revival or distinct-evidence resurfacing;
- mint-level reconciliation outcomes.

Infrastructure mints and definitive local identity/tracking/cooldown exclusions are recorded as zero-source exclusions before market work.

## Batch-first current-market resolution

For all due mints, after local checks:

1. deterministic fair traversal yields at most 30 distinct mints;
2. one Source-Governed DexScreener `candidate_market_batch` request resolves all returned Solana pools;
3. provider order and numeric magnitude are discarded as selection inputs;
4. every exact returned pool identity is retained;
5. current-pool confirmation requires exact mint/orientation, supported venue/program, infrastructure exclusion, current market/activity/liquidity and applicable migration/STNP/pair-drift proof;
6. only unresolved, conflicting, migrated or changed-pool identities may receive targeted exact-pair/protocol work.

Solana account confirmation uses governed `getMultipleAccounts` batches when the existing verifier contract supports the requested account kind. Each returned index receives its own source outcome and may independently be `CURRENT_POOL_CONFIRMED`, `IDENTITY_CONFLICT`, `CONTRACT_BLOCKED`, or `SOURCE_UNAVAILABLE`.

## Mint-to-pool reconciliation

Unresolved mint identities cascade once through already-approved sources:

1. DexScreener mint batch/pool rows;
2. GeckoTerminal token-pools resolution when Dex remains unresolved;
3. direct finalized Pump migration plus exact PumpSwap account proof only for Pump-specific migration claims.

A different pool is `NEW_POOL_PENDING_PROOF` until exact mint/orientation, supported venue/program, infrastructure exclusion, fresh liquidity/activity, migration/revival/STNP/pair-drift rules and required on-chain confirmation all pass. Aggregator data never silently substitutes the historical pool and never proves Pump lineage.

No-match, provider failure, identity conflict and unsupported contract remain separate categorical outcomes.

## Fair traversal and immutable stage reservations

Traversal interleaves these categories in a fixed round-robin cycle:

`FRESH_NOMINATION`, `DIRECT_MIGRATION`, `DUE_PERSISTED`, `POOL_RECONCILIATION`, `REVIVAL_OR_DISTINCT_EVIDENCE`.

Within each category, rows are ordered by oldest due/observed timestamp and stable `(mint, pool, source)` identity. This is scheduling fairness, not ranking.

The existing total discovery ceiling remains 30. One immutable stage budget reserves:

| Stage | Reserved operations |
|---|---:|
| intake | 3 |
| market batching | 2 |
| reconciliation | 6 |
| protocol confirmation | 7 |
| holder/safety | 8 |
| final refresh and handoff | 4 |

Unused capacity may flow only forward. A stage may spend its own reservation plus flowed-forward unused capacity; it may not borrow from a later stage. In particular, stale/exact-pool polling cannot consume holder/safety or handoff reservations. Transport-operation counts remain separate from governed source-request counts.

## Reserve, eligibility, selection and handoff

The canonical owner maintains:

- broad nominated reserve: all lawful exact mint+pool observations;
- market-ready reserve: exact current supported pools passing current market/activity/liquidity and protocol requirements;
- fully eligible reserve: four distinct, evidence-fresh mints that also pass holder, safety, tracking, cooldown, STNP, rotation and deduplication gates.

The `$3,000` exact-liquidity floor is unchanged. Alternates pass the same gates as selected candidates. All evidence carries an expiry. A stale alternate is rejected and must be requalified before activation.

After four (or the lawfully exhausted available set) are frozen, the existing deterministic uniform selection authority selects two distinct mints without source order, liquidity, activity, holder magnitude or any other market magnitude influencing the choice. The two valid unselected rows are alternates. The selected pair receives an atomic final freshness/tracking check and the existing two-slot Scheduler handoff. Any second-slot failure rolls back both slots and leaves no partial tracking, Scheduler, lifecycle, window or memory residue.

## Terminal truth

The final report includes nominations/unique mints by source, exact pools per mint, batch sizes, zero-source exclusions, reconciliation outcomes, state transitions, source requests and transports by stage, market-ready/fully eligible counts, selected/alternate identities, expired alternates, unexplored work and the exact stop reason.

The following terminals are never collapsed: `SOURCE_UNAVAILABLE`, `CONTRACT_BLOCKED`, `IDENTITY_CONFLICT`, `BUDGET_EXHAUSTION`, `DURATION_EXHAUSTION`, and `GOVERNED_UNIVERSE_EXHAUSTED`. Universe exhaustion is legal only when all approved intake, due persisted and reconciliation work is terminal. Any lawful unexplored work forbids a shortage/universe-exhaustion claim.

## Safety and scope locks

This lane adds no score, rank, confidence, weighting, retry, autonomous loop, successor, paid source, unsupported eligible venue, provider bypass, Scheduler bypass, wallet, signing, transaction, retrieval, decision, BUY/SELL/HOLD, position, trade, audit or PnL capability. It does not lower eligibility thresholds or treat dirty/expired/conflicting evidence as eligible.

## Offline proof contract

Focused tests must prove migration/upgrade integrity; 30-mint batching; no repeat direct polling after no-match; mint reconciliation; same/different-pool behavior; canonical migration versus unrelated pools; multi-source merge/disagreement; provider failure versus absence; fair fresh/persisted traversal; stage protection; holder/safety only after market readiness; four fully eligible rows; stale alternate rejection; neutral two-token selection; atomic handoff/rollback; no false shortage with unexplored work; exact source/transport accounting; clean cancellation/zero residue; and zero forbidden financial-capability deltas.
