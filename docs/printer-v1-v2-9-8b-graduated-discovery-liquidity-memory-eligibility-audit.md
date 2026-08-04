# V2-9.8B Graduated Discovery, Early Liquidity, Memory-Eligibility and Accounting Audit

Date: 2026-08-04

Lane: `V2-9.8B — Graduated Discovery, Early Liquidity and Memory-Eligibility Audit`

Mode: static/read-only repository audit plus committed live-closeout review. No provider call, runtime, database mutation, authorization, memory generation, retrieval, decision, position, trade, audit, or PnL activity occurred.

## Verdict

`V2_9_8B_GRADUATED_DISCOVERY_LIQUIDITY_MEMORY_ELIGIBILITY_AUDIT_PASS_CODE_ROOT_CAUSES_PROVEN_WITH_RUN_ARTIFACT_LIMIT`

The production code proves the main discovery-yield, memory-admission, and accounting defects. The committed live closeout proves their operational impact. The raw SQLite database and operator-run payloads remain intentionally untracked and were not available through GitHub, so this audit does not claim a raw-row reconstruction for every one of the 25 protocol-confirmed identities. That limitation does not block the design because the controlling code paths and aggregate live outcomes are sufficient to prove the root causes.

## Verified baseline

| Item | Value |
|---|---|
| Repository | `Dtwosam/MoneyPrinter` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| HEAD | `74bc5bf4bb3cb6925ed5c89e5e0d082cbb5eacfb` |
| Subject | `Close post-sequencing-repair 15m re-proof` |
| Live execution reviewed | `20260804T164755Z-b723daf73da2` |
| Live first terminal | `PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT` |
| Secondary finalization fault | `CAMPAIGN_STAGE_OPERATION_RECONCILIATION_MISMATCH` |

## Active boundaries preserved

This audit is interpreted inside the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`

The active memory-growth build order is not treated as the sole source of truth.

The following remain locked: live funds, wallets, private keys, paid APIs, source/scheduler bypass, scoring/ranking/confidence systems, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, trade audits, and PnL.

## Executive findings

The latest live funnel was:

```text
21 DexScreener fresh pairs
+ 20 GeckoTerminal new-pool pairs
+ persisted/direct-migration inventory
→ 106 pool accounts protocol-checked
→ 25 exact PumpSwap owner+base-mint confirmations
→ 1 market-ready candidate
→ 1 holder attempt
→ 0 holder passes
→ 0 fully eligible candidates
```

The market did not receive a fair chance to produce a memory reserve because the current flow performs the work in the wrong order:

1. Fresh DexScreener and GeckoTerminal nominations are persisted without their available liquidity.
2. The two reserved market-batch operations are spent only on the canonical graduated registry inventory.
3. Fresh nominations are protocol-confirmed afterward.
4. Confirmed fresh pools may return to market validation only if market-batch capacity remains.
5. In the live attempt, the market capacity was already consumed, so 25 protocol-confirmed pools could not become market-ready through the same campaign.
6. The one market-ready survivor was then removed from memory selection because holder concentration was used as an admission gate rather than memory context.

The accounting finalizer also used incomplete ownership surfaces: the protocol queue did not seal campaign stage evidence, and pre-lifecycle reporting derived `campaign_source_calls` from the holder-operation ledger rather than the complete permanent-discovery source lineage.

## A. Current discovery-source ownership

### A1. Direct Pump migration and persisted registry

`run_persistent_eligible_token_supply` calls direct migration discovery and then exports `printer_pumpswap_graduated_candidate_registry` through `export_graduated_candidates`.

The graduated registry is a valid authoritative source for rows already recorded with immutable migration evidence. Repeated market campaigns do not need to re-prove the migration transaction for those rows.

The registry currently provides the canonical inventory traversed by `order_canonical_inventory_fairly` across:

- `FRESH_NOMINATION`
- `DIRECT_MIGRATION`
- `DUE_PERSISTED`
- `POOL_RECONCILIATION`
- `REVIVAL_OR_DISTINCT_EVIDENCE`

However, a DexScreener mint receives `FRESH_NOMINATION` placement in this traversal only when it is already present in the graduated registry. A fresh market nomination outside that registry does not enter the initial market-batch inventory.

### A2. DexScreener

DexScreener is used in two distinct ways:

1. fresh-profile discovery followed by token-batch enrichment;
2. batched market resolution for up to 30 due mints.

The normalized pair data can carry `liquidity.usd`. The market resolver correctly preserves exact pool identities, never chooses by provider order or liquidity magnitude, and requires the exact historical/nominated pool.

### A3. GeckoTerminal

GeckoTerminal contributes:

1. one fresh new-pool nomination request;
2. up to six one-mint reconciliation requests per market round when DexScreener does not expose the exact expected pool.

GeckoTerminal rate limits remain candidate-local in the repaired flow. They reduce coverage but do not create a shared source-death terminal.

### A4. Fresh Dex/Gecko nominations do not currently receive a separate migration proof

The fresh nomination path writes DexScreener/GeckoTerminal pool observations directly into exact-market state and the broad reserve as `FRESH_AGGREGATOR_NOMINATION_REQUIRES_EXACT_PROTOCOL_PROOF`.

No separate Pump migration transaction or registry-membership proof is required before protocol confirmation. This part already aligns with the operator decision.

The required safety boundary is the exact pool check, not repeated graduation proof:

- exact pool address;
- PumpSwap program owner;
- exact `base_mint@43` binding;
- no silent pool substitution.

## B. Proven 25-to-1 attrition root cause

### B1. Fresh source liquidity is discarded

`record_fresh_pool_nominations` accepts only:

- mint;
- pool;
- base mint;
- quote mint;
- venue;
- request provenance.

It does not retain `liquidity_usd`, source observation time, or a fresh market-evidence expiry even when the source response already contains those values.

`run_geckoterminal_fresh_nomination` similarly rebuilds observations without liquidity before calling `record_fresh_pool_nominations`.

Therefore a fresh pool that already has `$3,000+` liquidity is reduced to a generic protocol-due row. Printer loses the opportunity to apply the floor before on-chain confirmation.

Classification: `PROVEN_CODE_DEFECT`.

### B2. Initial market batches exclude fresh nominations outside the graduated registry

The permanent loop builds `permanent_rows` from `inventory_rows`, and `inventory_rows` is produced by `export_graduated_candidates`.

Fresh DexScreener and GeckoTerminal broad nominations are stored in exact-market tables and reserve layers, but are not merged into `permanent_rows` for the initial market batches unless the mint already exists in the graduated registry.

Classification: `PROVEN_DISCOVERY_COMPOSITION_DEFECT`.

### B3. Market capacity is consumed before protocol confirmation

The permanent loop can consume the two reserved `market_batching` operations before calling `process_protocol_confirmation_queue`.

The protocol queue is processed only after the main market loop ends. Confirmed identities re-enter market validation only when:

```text
confirmed_for_market
and stage_budget.available("market_batching") >= 1
and dexscreener_batch_transport_factory is not None
```

In the live attempt, both market rounds had already run. The 25 successful protocol confirmations therefore did not have a remaining market-batch operation to attach fresh liquidity and become market-ready.

This is the controlling explanation for the aggregate `25 confirmed → 1 market-ready` result. The one market-ready candidate came from the earlier canonical inventory path, not from successful post-market protocol confirmation.

Classification: `PROVEN_STAGE_ORDERING_AND_CAPACITY_COMPOSITION_DEFECT`.

### B4. Exact pool confirmation remains necessary

The live protocol batches returned:

- 25 `CURRENT_POOL_CONFIRMED`;
- 77 `POOL_OWNER_MISMATCH`;
- 4 `BASE_MINT_MISMATCH`.

This proves that provider-visible pool rows cannot be accepted as exact PumpSwap identity merely because they were returned by DexScreener or GeckoTerminal.

Removing a separate Pump.fun graduation lookup is safe for the approved memory-discovery direction. Removing exact pool owner/mint validation is not.

Classification: `EXPECTED_SAFETY_BEHAVIOR`.

## C. Earliest safe `$3,000` liquidity filter

The earliest safe filter is the first source response that contains current liquidity for the exact nominated `(mint, pool)` identity.

### C1. DexScreener fresh/token-batch rows

DexScreener pair rows already expose liquidity. Printer should preserve that value when recording fresh nominations.

### C2. GeckoTerminal new-pool rows

GeckoTerminal normalized pool rows can carry current market liquidity. Printer should preserve it at fresh nomination rather than discarding it.

### C3. Persisted/direct-migration registry rows

Registry rows do not necessarily carry current liquidity. They require one current DexScreener mint-batch lookup, with one bounded GeckoTerminal fallback when the exact pool is missing or liquidity is unknown.

### C4. Required categorical outcomes

```text
exact pool + liquidity >= 3000
→ ABOVE_FLOOR_NOMINATION
→ protocol confirmation due

exact pool + liquidity < 3000
→ BELOW_LIQUIDITY_FLOOR
→ cooldown / future reconsideration

exact pool + liquidity missing
→ LIQUIDITY_UNKNOWN
→ one bounded backup lookup

exact pool absent
→ EXACT_POOL_NO_MATCH
→ cooldown / future reconciliation
```

Only `ABOVE_FLOOR_NOMINATION` should consume PumpSwap account-confirmation capacity.

The exact number of the 106 protocol members that would have been avoided cannot be calculated from GitHub because the raw source payloads and SQLite rows are untracked. The live result proves the upper bound: at least 81 members failed exact protocol identity and all 106 were confirmed before a productive early-liquidity funnel was established.

## D. Holder concentration is wrongly coupled to memory admission

The production campaign currently performs the following:

1. market-ready candidates enter holder evaluation;
2. only holder facts with `eligible == true` become `fully_eligible_rows`;
3. only those rows receive the `FULLY_ELIGIBLE` reserve layer;
4. `freeze_eligible_reserve` ignores any row without `fully_eligible`;
5. final selection again chooses only candidates whose holder fact is eligible.

Therefore:

```text
MARKET_READY
+ HOLDER_CONCENTRATION_EXTREME
→ no FULLY_ELIGIBLE layer
→ no memory selection
```

The latest live attempt proves this path operationally: one market-ready candidate received one holder request, failed `HOLDER_CONCENTRATION_EXTREME`, and memory-selection depth became zero.

This conflicts with the adopted manipulation-aware architecture. Holder concentration is a market-integrity and future action-risk signal. It is valuable memory context and must not automatically erase the observation subject.

Classification: `PROVEN_POLICY_CONFLATION_AND_CODE_DEFECT`.

The correct separation is:

```text
MEMORY_OBSERVATION_ELIGIBLE
  exact identity
  exact supported pool
  fresh exact-pool liquidity >= 3000
  complete governed market evidence

MEMORY_CONTEXT
  holder concentration
  manipulation condition
  holder evidence completeness

FUTURE_ACTION_ELIGIBILITY
  separately locked
  may remain BLOCKED or UNKNOWN
```

Holder evidence collection itself is not a defect. The defect is using its action-risk result as the memory-admission authority.

## E. Reserve and selection findings

### E1. Current selection authority is neutral but uses the wrong input layer

`freeze_eligible_reserve` uses deterministic neutral selection and preserves freshness, distinct mints, and distinct pools. Those properties should remain.

The wrong input is `FULLY_ELIGIBLE`, which currently means identity + market + holder/safety pass.

For memory growth, the input should be `MEMORY_OBSERVATION_ELIGIBLE`.

### E2. A bounded surplus is feasible without raising the 30-operation ceiling first

Current provider batching is already efficient:

- DexScreener: up to 30 mints per batch;
- PumpSwap confirmation: up to 100 unique pools per batch.

When liquidity is preserved from fresh-source responses and the `$3,000` floor is applied before protocol confirmation, the existing ceiling can evaluate a materially larger useful universe than the current flow.

A budget increase is not justified before implementing and proving the reordered funnel.

### E3. Proposed reserve target

The design lane may safely use:

- minimum freeze depth: `4`;
- bounded surplus target: `8` observation-eligible identities;
- frozen campaign set: `2 selected + 2 alternates`;
- remaining observation-eligible identities: retained as bounded standby/due inventory.

This is a capacity target, not a score, rank, confidence value, or prediction system.

## F. Campaign accounting mismatch

### F1. Protocol confirmation does not seal stage evidence

`process_protocol_confirmation_queue` accepts:

- `stage_evidence_sink`;
- `transport_identity_observer`.

It reports source request IDs, transport operations, and local validation counts. It calls the independent transport observer, but it never seals and emits a `PROTOCOL_CONFIRMATION` campaign stage-evidence block through `stage_evidence_sink`.

The live run performed:

- two protocol source requests;
- two transports;
- 106 local validations.

Those operations were visible to the action-local surface but lacked their matching sealed owner stage.

Classification: `PROVEN_SIX_UNIT_STAGE_EVIDENCE_DEFECT`.

### F2. Pre-lifecycle source reporting uses the holder-operation ledger

`authoritative_live_operational_campaign.py` writes:

```text
campaign_source_calls = int(ledger.governed_requests)
```

where `ledger` is the holder/readiness operation ledger. It is not the complete permanent-discovery Source Governor request lineage.

The live run had 20 durable source requests but reported 13 campaign source calls.

Classification: `PROVEN_REPORTING_OWNERSHIP_DEFECT`.

### F3. Request counts and transport counts must remain separate

A Source Governor request and a measured transport operation are not always one-to-one. For example, the DexScreener fresh-profile flow may use multiple transports inside one governed profile flow.

The design must provide two separate reconciliations:

1. exact durable source-request coverage by request ID;
2. six-unit transport/local-validation/scheduler/reservation accounting by immutable identity.

The finalizer must never equate request count with transport count.

### F4. Exact 20-to-13 row mapping remains artifact-limited

The raw database and operator-run package are not in GitHub. Therefore this audit does not assign each of the seven-count difference to a particular request row.

The code nevertheless proves two independent causes sufficient to require repair:

- missing protocol stage evidence;
- wrong source-call reporting owner.

An honest blocked campaign must persist a durable report containing the first terminal plus a secondary accounting blocker. Accounting failure must not erase the report itself.

## G. Root-cause hierarchy

1. **Fresh liquidity loss:** source liquidity is discarded at fresh nomination.
2. **Inventory split:** initial market batches traverse registry inventory, while fresh market nominations wait outside that path.
3. **Wrong stage order:** market capacity is spent before fresh protocol confirmations can return to market validation.
4. **Memory/action conflation:** holder concentration removes otherwise observable candidates from memory selection.
5. **Protocol evidence omission:** protocol confirmation has no sealed campaign stage evidence.
6. **Reporting ownership defect:** pre-lifecycle source calls are reported from the holder ledger rather than complete source lineage.
7. **Secondary operational friction:** GeckoTerminal rate limits reduce fallback completeness but were not the first terminal.

## H. Exact defects

| ID | Defect |
|---|---|
| D1 | Fresh Dex/Gecko nomination persistence drops exact-pool liquidity and freshness. |
| D2 | Initial market batching excludes fresh nominations outside the graduated registry. |
| D3 | Protocol confirmation runs after market capacity is consumed; confirmed rows cannot be promoted. |
| D4 | Holder/safety pass is required for memory selection. |
| D5 | Protocol confirmation does not seal campaign stage evidence. |
| D6 | Pre-lifecycle campaign source-call reporting uses an incomplete holder ledger. |
| D7 | Honest accounting-blocked terminals can fail to emit a durable report. |

## I. Exact non-defects

- `$3,000` exact-pool floor.
- Exact PumpSwap program-owner validation.
- Exact `base_mint@43` validation.
- No silent pool substitution.
- Candidate-local owner/base-mint mismatch.
- Neutral deterministic selection.
- Holder evidence collection as context.
- No separate Pump migration re-proof for fresh DexScreener/GeckoTerminal candidates.
- Existing no-paid-source, no-ranking, no-retry, Source Governor, and Scheduler locks.

## J. Narrowest design/implementation boundary

The next design must specify only:

1. three-source discovery composition: Pump migration/registry, DexScreener, GeckoTerminal, plus persisted due/revival rows;
2. liquidity-preserving fresh nominations;
3. early exact-pool `$3,000` categorical prefilter;
4. protocol confirmation only for above-floor nominations;
5. immediate promotion after protocol confirmation using retained unexpired market evidence;
6. memory-observation eligibility separated from holder/action risk;
7. bounded surplus observation reserve and neutral freeze;
8. complete protocol stage evidence and request-coverage reconciliation;
9. durable honest terminal reports even when accounting is blocked.

Do not raise the operation ceiling, reduce the floor, weaken exact pool proof, activate unsupported venues, add scores/ranking/confidence, or unlock future action capabilities.

## Money-usefulness contribution

The audit identifies why Printer failed to find the market supply visible to a human operator. The current flow spends expensive protocol work before retaining and using the most useful market fact—exact-pool liquidity—and then excludes the only observed candidate because of a manipulation-risk signal that should be learned from.

The repair increases money usefulness by making Printer observe a broader, more realistic market diet while preserving exact identity and future action safety.

## What this lane still does not unlock

- provider execution;
- another `WINDOW_15M` attempt;
- clean memory proof;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL;
- any live wallet or real-fund capability.

## Proof required after implementation

A bounded offline proof must show:

- fresh source liquidity is retained;
- below-floor pools never consume protocol confirmation;
- above-floor fresh pools can be promoted after exact confirmation without a second market request;
- direct registry rows receive batched market evidence;
- Dex/Gecko candidates require no migration re-proof;
- exact pool owner/mint checks remain mandatory;
- concentrated-holder tokens remain memory-observation eligible with context attached;
- action eligibility remains locked;
- at least eight fixture observation-eligible identities can be accumulated within the unchanged ceiling;
- four are frozen neutrally as two selected and two alternates;
- every source request and every six-unit identity reconciles;
- honest blocked reports persist.

## Functionality Risks / Setbacks / Efficiency Blockers

- Source-provided liquidity may be absent or stale; exact freshness and one-backup rules are required.
- Provider venue labels cannot replace on-chain pool identity.
- Removing holder concentration as a memory blocker must not silently unlock action eligibility.
- An eight-candidate surplus target must remain bounded and non-ranked.
- Protocol stage evidence must avoid duplicate transport/local-validation identities.
- Request-count and transport-count reconciliation must stay separate.
- Raw identity-level run forensics remain unavailable through GitHub until operator artifacts are intentionally supplied; no claim should exceed the committed evidence boundary.
