# V2-9.8B Graduated Discovery, Early Liquidity and Memory-Eligibility Design

Date: 2026-08-04

Lane: `V2-9.8B — Graduated Discovery, Early Liquidity and Memory-Eligibility Design`

Status: `V2_9_8B_GRADUATED_DISCOVERY_LIQUIDITY_MEMORY_ELIGIBILITY_DESIGN_APPROVED`

Depends on:

- `docs/printer-v1-v2-9-8b-graduated-discovery-liquidity-memory-eligibility-audit.md`
- `docs/printer-v1-v2-9-8b-permanent-discovery-conversion-repair-closeout.md`
- `docs/printer-v1-v2-9-8b-governed-pumpswap-account-batch-confirmation-closeout.md`
- `docs/printer-v1-v2-9-8b-multi-round-market-batch-six-unit-sequencing-repair-closeout.md`
- `docs/printer-v1-v2-9-8b-post-sequencing-repair-window-15m-reproof-closeout.md`

This is design only. It authorizes no implementation, provider call, authorization, runtime, lifecycle, memory, retrieval, paper decision, position, trade, audit, or PnL activity.

## 1. Objective

Tailor Printer to consistently build a bounded surplus of memory-observation candidates from the live Solana Pump/PumpSwap market by:

1. using Pump migration/registry, DexScreener, GeckoTerminal, and persisted rotation as complementary discovery sources;
2. preserving exact-pool liquidity at discovery time;
3. applying the `$3,000` floor before expensive on-chain confirmation whenever current source evidence already exists;
4. confirming exact PumpSwap pool owner and mint binding only for above-floor nominations;
5. promoting confirmed candidates without an unnecessary second market lookup while evidence remains fresh;
6. treating holder concentration and manipulation as memory context, not automatic memory exclusion;
7. freezing two selected tokens and two alternates from a larger neutral observation reserve;
8. sealing complete campaign accounting so honest terminals always produce durable reports.

## 2. Money-usefulness contribution

The design improves Printer’s ability to learn from the market a human operator actually sees:

- newly graduated tokens;
- active PumpSwap pools;
- revivals;
- concentrated-holder tokens;
- manipulation contexts;
- winners, losers, traps, and failed continuations.

It does not promise profit in every condition. It increases the probability that Printer observes enough lawful market situations to build useful clean memories and later distinguish tradeable opportunity from traps, while future action eligibility remains separately locked.

## 3. Non-goals and hard locks

Do not:

- lower the `$3,000` floor;
- increase the flat operation ceiling above `30` in this lane;
- change reservations `3/2/6/7/8/4` before proof shows they remain binding after reordering;
- remove exact pool owner or base-mint confirmation;
- silently substitute another pool;
- activate Meteora or another unsupported venue;
- require a separate Pump migration transaction/registry proof for every DexScreener or GeckoTerminal candidate;
- claim DexScreener/GeckoTerminal provenance is authoritative migration proof;
- add scoring, ranking, confidence, weights, prediction, or best-token logic;
- add retries, reruns, resumes, successors, or paid APIs;
- bypass Source Governor or Central Scheduler;
- unlock retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.

## 4. Source roles

### 4.1 Pump migration intake and graduated registry

Role:

- authoritative direct migration evidence when observed;
- durable persisted supply of previously confirmed graduated mints and canonical pools;
- due, below-floor, incomplete, and revival rotation.

A valid registry row is not re-proven on every campaign.

Current liquidity is not assumed from registry membership. Registry candidates enter the current market-prefilter queue.

### 4.2 DexScreener

Role:

- fresh profile/token discovery;
- current exact-pool liquidity and activity evidence;
- batched market lookup for direct-registry and persisted candidates;
- active/revival rediscovery.

DexScreener candidates do not require separate Pump migration proof before market evaluation or memory observation.

### 4.3 GeckoTerminal

Role:

- fresh/new-pool discovery;
- current exact-pool market evidence;
- one bounded backup lookup when DexScreener has no exact pool, missing liquidity, or conflicting visibility;
- active/revival rediscovery.

GeckoTerminal candidates do not require separate Pump migration proof before market evaluation or memory observation.

### 4.4 Solana RPC / PumpSwap account confirmation

Role:

- exact account existence;
- exact PumpSwap program owner;
- exact expected mint at `base_mint@43`;
- candidate-local null, owner mismatch, malformed data, or mint mismatch.

This is pool-identity confirmation, not repeated graduation proof.

## 5. Canonical nomination object

All discovery routes normalize into one immutable candidate object before filtering:

```text
DiscoveryNomination
  nomination_id
  campaign_id / run_id / cycle_id
  source_name
  source_request_id
  source_response_id
  mint
  pool
  base_mint
  quote_mint
  provider_venue
  observed_at
  liquidity_usd
  liquidity_observed_at
  liquidity_evidence_expires_at
  market_evidence_contract_version
  migration_registry_identity (optional)
  exact_pool_confirmation_status
```

Required truth rules:

- `mint` and `pool` are exact identities.
- Liquidity belongs only to the exact nominated pool.
- No highest-liquidity or token-wide borrowing.
- Dex/Gecko provenance is labelled as market-source provenance, not migration proof.
- Direct-registry provenance retains immutable migration evidence.

Use existing exact-market and reserve tables where they can represent these fields. Add a migration only if static implementation inspection proves that current JSON/provenance/evidence columns cannot preserve the required immutable data.

## 6. New funnel order

```text
SOURCE INTAKE
→ EXACT-POOL MARKET PREFILTER
→ ABOVE-FLOOR NOMINATION QUEUE
→ PUMPSWAP ACCOUNT CONFIRMATION
→ MEMORY-OBSERVATION ELIGIBILITY
→ HOLDER / MANIPULATION CONTEXT
→ OBSERVATION RESERVE
→ NEUTRAL FREEZE
→ 2 SELECTED + 2 ALTERNATES
```

The controlling change is that current exact-pool liquidity is evaluated before protocol confirmation when already available.

## 7. Stage A — Source intake

Process the existing categories through deterministic round-robin traversal:

1. `DIRECT_MIGRATION`
2. `DEXSCREENER_FRESH`
3. `GECKOTERMINAL_FRESH`
4. `DUE_PERSISTED`
5. `REVIVAL_OR_DISTINCT_EVIDENCE`
6. `LIQUIDITY_UNKNOWN_RECHECK`
7. `BELOW_FLOOR_RECHECK`

Ordering within a category:

- oldest lawful due time;
- mint;
- pool;
- source identity.

No source may starve another. No category is a score or rank.

Deduplicate by exact `(mint, pool)`. Merge source provenance without merging conflicting pool identities.

## 8. Stage B — Early exact-pool liquidity prefilter

### 8.1 Source response already has liquidity

For fresh DexScreener and GeckoTerminal pool rows, persist:

- `liquidity_usd`;
- exact observation time;
- source request/response IDs;
- evidence expiry;
- exact mint/pool/quote/venue.

Do not reduce these rows to generic `CONTRACT_BLOCKED` before using their market evidence.

### 8.2 Source response lacks current liquidity

For direct-registry and persisted candidates:

- batch up to 30 mints through DexScreener;
- match only the exact nominated pool;
- use one bounded GeckoTerminal fallback only for exact-pool missing or liquidity unknown;
- no retry.

### 8.3 Categorical outcomes

| Condition | State / queue action |
|---|---|
| Exact pool, fresh liquidity `>= 3000` | `ABOVE_FLOOR_NOMINATION`; enqueue protocol confirmation |
| Exact pool, fresh liquidity `< 3000` | `BELOW_LIQUIDITY_FLOOR`; future cooldown/recheck |
| Exact pool, liquidity missing | `LIQUIDITY_UNKNOWN`; one backup lookup then defer |
| Exact pool not returned | `EXACT_POOL_NO_MATCH`; cooldown/reconciliation |
| Pool/mint/orientation conflict | `IDENTITY_CONFLICT`; fail closed |
| Unsupported venue label | keep candidate-local unsupported state; no protocol call |
| Shared source failure | source-health classification; other healthy channels continue |

Below-floor, no-match, unknown, unsupported, and conflict candidates must not consume PumpSwap account-confirmation capacity in that campaign.

## 9. Stage C — PumpSwap account confirmation

Process only `ABOVE_FLOOR_NOMINATION` rows whose market evidence is still fresh.

Use the existing governed `getMultipleAccounts` owner:

- up to 100 unique pool addresses;
- deterministic exact address order;
- one request/transport per batch;
- no retry;
- independent member results;
- exact PumpSwap owner;
- exact expected `base_mint@43`.

Outcomes remain candidate-local except a malformed/shared RPC envelope.

### 9.1 Promotion without second market request

When a candidate returns `CURRENT_POOL_CONFIRMED`:

- join it to the retained exact-pool liquidity evidence by exact `(mint, pool)`;
- require the market evidence to remain unexpired;
- promote directly to `MEMORY_OBSERVATION_ELIGIBLE`;
- do not consume another DexScreener market-batch operation.

A second market request is required only when:

- liquidity evidence expired during confirmation;
- pool identity changed;
- source evidence was incomplete or conflicted.

This removes the current `protocol confirmed but no market capacity remains` dead end.

## 10. Stage D — Memory-observation eligibility

Create a new reserve layer:

`MEMORY_OBSERVATION_ELIGIBLE`

A candidate qualifies when all are true:

1. Solana memecoin candidate and non-infrastructure mint;
2. exact mint and pool identities complete;
3. exact pool confirmed as supported PumpSwap owner and expected base mint;
4. fresh exact-pool liquidity evidence `>= $3,000`;
5. no unresolved identity conflict;
6. current tracking/cooldown rules permit a new observation;
7. complete governed provenance and freshness boundary.

These do not block memory observation by themselves:

- `HOLDER_CONCENTRATION_EXTREME`;
- concentrated top holders;
- manipulation context;
- unusual activity;
- holder evidence unavailable;
- future action eligibility blocked or unknown.

The memory candidate must carry the exact context label rather than losing admission.

## 11. Stage E — Holder and manipulation context

Holder/safety requests remain bounded by the existing holder reservation.

They are context enrichment, not memory-admission authority.

Allowed candidate context examples:

```text
holder_condition = HOLDER_CONCENTRATION_EXTREME
holder_evidence_status = COMPLETE
market_integrity_context = MANIPULATION_CONTEXT_PRESENT
future_action_eligibility = BLOCKED_OR_UNKNOWN
memory_observation_eligible = true
```

When holder evidence is unavailable:

```text
holder_condition = UNKNOWN
holder_evidence_status = SOURCE_UNAVAILABLE_OR_INCOMPLETE
future_action_eligibility = UNKNOWN
memory_observation_eligible = true
```

provided the identity and market-evidence requirements remain clean.

This lane does not define or unlock future paper-action policy.

## 12. Stage F — Bounded surplus reserve

Use two thresholds:

- `MINIMUM_FREEZE_DEPTH = 4`
- `OBSERVATION_SURPLUS_TARGET = 8`

Meaning:

- fewer than 4: honest pre-lifecycle coverage blocker;
- 4–7: sufficient for one freeze, but report `SURPLUS_TARGET_NOT_MET` and retain due work according to campaign bounds;
- 8: preferred bounded reserve target; stop expanding unless another already-started batch must close truthfully.

The target of eight is not a prediction, score, confidence, or rank. It is a bounded capacity goal equal to twice the required freeze depth.

The unchanged flat ceiling of 30 remains controlling. The target must not cause a budget increase or retry.

## 13. Stage G — Neutral freeze and selection

Replace `FULLY_ELIGIBLE` as the input to memory selection with `MEMORY_OBSERVATION_ELIGIBLE`.

Preserve:

- exact freshness;
- distinct mints;
- distinct pools;
- deterministic uniform authority;
- no provider/recency/liquidity/holder weighting.

Freeze exactly four:

```text
4 observation-eligible
→ deterministic neutral order
→ 2 selected
→ 2 alternates
```

Rows five through eight remain bounded standby/due inventory and are not silently activated in the same campaign.

Holder facts, manipulation context, and future-action status travel with each selected/alternate record.

## 14. State model

Recommended state/reason additions or semantic refinements:

### Market state/reason

- `ABOVE_FLOOR_NOMINATION`
- `LIQUIDITY_UNKNOWN`
- existing `BELOW_LIQUIDITY_FLOOR`
- existing `EXACT_POOL_NO_MATCH`
- existing `IDENTITY_CONFLICT`
- existing `CURRENT_POOL_CONFIRMED`

If adding enum/state values requires schema migration, prefer reason-code refinement under existing safe states unless the current schema cannot represent the distinction without ambiguity.

### Reserve layers

- `BROAD_NOMINATED`
- `ABOVE_FLOOR_NOMINATED`
- `MEMORY_OBSERVATION_ELIGIBLE`
- `FULLY_ELIGIBLE` retained only for any future action-specific policy; it must not control memory selection.

## 15. Source and accounting ownership

### 15.1 Mandatory sealed stages

The campaign six-unit owner must ingest stage evidence for every executed operational stage:

1. `FRESH_PROFILE_NOMINATION`
2. `DIRECT_MIGRATION_INTAKE`
3. `GECKOTERMINAL_NEW_POOL_NOMINATION`
4. `MARKET_PREFILTER` / each `MINT_MARKET_BATCH|N`
5. `PROTOCOL_CONFIRMATION|N`
6. `HOLDER_CONTEXT`
7. `SELECTION_HANDOFF`
8. terminal reconciliation as already required.

No stage may accept `stage_evidence_sink` and then omit sealing.

### 15.2 Protocol stage evidence

`process_protocol_confirmation_queue` must:

- create one measured stage ledger spanning its account batches;
- record each transport identity exactly once;
- record one named local-validation identity per member;
- seal a `PROTOCOL_CONFIRMATION` stage with monotonic sequence/immutable stage ID;
- attach source request IDs and member counts as diagnostics;
- emit through `stage_evidence_sink` exactly once.

Do not copy action-local evidence into the owner. Both surfaces observe the same execution independently.

### 15.3 Source-request coverage manifest

Persist a separate request coverage manifest:

```text
source_request_id
source_name
request_kind
logical_stage_id
transport_identity_count
normalized_member_count
terminal status
```

Every durable Source Governor request in campaign scope must appear exactly once.

### 15.4 Keep request and transport accounting separate

- source request count derives from unique durable request IDs;
- transport count derives from immutable measured transport identities;
- local validations derive from immutable validation identities;
- no equality comparison between request count and transport count.

### 15.5 Pre-lifecycle reporting

Remove `campaign_source_calls = holder_ledger.governed_requests` as the complete campaign truth.

Report:

- `campaign_source_request_count` from the request coverage manifest;
- `campaign_transport_operation_count` from the six-unit owner;
- `holder_context_source_request_count` from the holder ledger as a scoped subset only.

### 15.6 Honest report persistence

An accounting mismatch remains fail-closed and blocks lifecycle/memory PASS, but it must not prevent report emission.

The durable report must preserve:

- immutable first terminal cause;
- secondary accounting status/reason;
- all available source/stage evidence;
- cleanup truth;
- `report_acceptance = ACCOUNTING_BLOCKED`.

## 16. Stage-budget use

Keep current reservations for the first implementation/proof:

| Stage | Reservation |
|---|---:|
| intake | 3 |
| market batching / prefilter | 2 |
| reconciliation | 6 |
| protocol confirmation | 7 |
| holder context | 8 |
| final refresh/handoff | 4 |
| total | 30 |

Efficiency changes:

- fresh rows with source liquidity need no additional market-batch operation;
- below-floor rows consume no protocol operation;
- one protocol batch can confirm up to 100 above-floor pools;
- holder context no longer determines observation reserve depth.

Do not redesign the reservations until bounded proof measures the reordered funnel.

## 17. Fairness rules

Printer remains fair and non-ranked:

- deterministic source-category round robin;
- oldest due then stable exact identity;
- one exact candidate identity per mint/pool;
- no provider order authority;
- no liquidity magnitude preference beyond categorical floor pass;
- no holder concentration preference;
- deterministic uniform freeze from the observation reserve;
- complete provenance for every selected and rejected row.

## 18. Terminal truth

### Eligible terminal

Proceed only when at least four fresh `MEMORY_OBSERVATION_ELIGIBLE` identities exist.

### Honest blocker

A coverage blocker is legal only after:

- all started source batches close;
- all above-floor nominations with matching protocol capacity are processed;
- one bounded liquidity backup is used where permitted;
- no executable lawful queue remains with matching capacity;
- exact rejection counts are reported.

Do not classify holder concentration as discovery-selection coverage insufficiency.

Holder concentration may be reported as context but cannot reduce observation depth.

## 19. Production owners to modify

Expected implementation scope:

| Owner | Required change |
|---|---|
| `sources/dexscreener.py` | Preserve exact-pool liquidity/freshness in fresh normalized observations if not already exposed consistently. |
| `sources/geckoterminal.py` | Preserve exact-pool liquidity/freshness in new-pool normalized observations. |
| `discovery/permanent_discovery_availability.py` | Extend nomination object, early prefilter, above-floor queue, protocol stage seal, direct promotion, observation reserve layer. |
| `discovery/eligible_token_supply.py` | Compose all source categories, reorder prefilter before protocol, remove post-protocol market-capacity dependency, build surplus target. |
| `operator_cli/authoritative_live_operational_campaign.py` | Make holder context non-blocking for memory observation; select from observation reserve; correct source reporting ownership. |
| `sources/campaign_six_unit_accounting.py` or finalizer owner | Add request-coverage reconciliation only where needed; preserve transport identity law; persist accounting-blocked report. |
| tests/docs | Focused proof and closeout. |

No broad rewrite or second discovery engine is allowed.

## 20. Minimum implementation proof

Use test-first focused proof.

### Discovery and liquidity

1. Dex fresh nomination retains exact liquidity and expiry.
2. Gecko fresh nomination retains exact liquidity and expiry.
3. `$2,999.99` is below floor; `$3,000.00` passes.
4. Liquidity for another pool cannot be borrowed.
5. Below-floor rows cause zero protocol transport.
6. Unknown liquidity gets at most one backup lookup.
7. Registry candidates receive a batched current market lookup.
8. Dex/Gecko candidates require no migration-registry membership or migration transaction proof.
9. Exact PumpSwap owner/base-mint confirmation remains required.
10. Confirmed above-floor rows promote without a second market request while evidence is fresh.
11. Expired evidence forces fresh market validation.

### Observation eligibility and selection

12. `HOLDER_CONCENTRATION_EXTREME` remains observation eligible.
13. Holder evidence unavailable remains observation eligible with context unknown.
14. Identity conflict and below-floor liquidity still block observation eligibility.
15. Eight fixture candidates accumulate inside the unchanged ceiling.
16. Four are frozen neutrally as two selected and two alternates.
17. No scoring/ranking/confidence/weighting is introduced.
18. Future action eligibility remains locked and distinct.

### Accounting

19. Protocol batches seal one immutable protocol stage evidence block.
20. Protocol local-validation identities equal member count.
21. Every source request ID appears once in the request manifest.
22. Request count and transport count reconcile independently.
23. Honest blocked terminal writes a durable report even with accounting status blocked.
24. No duplicate stage, transport, or validation identity is accepted.

### Safety

25. No retry, successor, provider bypass, Scheduler bypass, retrieval, decision, position, trade, audit, or PnL delta.

Run only changed focused tests and directly affected discovery/source/accounting/campaign tests. Reserve broad suites for lane closeout or pre-live proof according to risk-based verification.

## 21. Bounded proof after implementation

After offline implementation PASS:

1. run a fixture-driven integrated campaign proving at least eight observation-eligible candidates;
2. prove exact operation/stage accounting and durable blocked-report emission;
3. close the implementation lane;
4. review the exact HEAD;
5. issue a separate fresh one-use authorization;
6. run exactly one canonical real `WINDOW_15M` attempt;
7. PASS only for authoritative lifecycle completion and clean memory.

No live attempt is authorized by this design.

## 22. What this design still does not unlock

- guaranteed eligible supply in every market snapshot;
- lower liquidity thresholds;
- unsupported venues;
- action eligibility for concentrated tokens;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, trade audits, or PnL;
- live wallet or real-fund execution;
- longer memory windows.

## 23. Functionality Risks / Setbacks / Efficiency Blockers

- Dex/Gecko liquidity may be missing or stale; freshness must be explicit.
- Exact market sources may return non-PumpSwap or wrong-mint pools; on-chain confirmation remains necessary.
- An observation-eligible concentrated token is useful for learning but may remain action-ineligible later.
- The eight-candidate target may not always be reached within a short campaign; minimum four remains the lifecycle gate.
- Source rate limits may reduce fallback coverage; candidate-local handling must continue.
- Protocol stage evidence must not duplicate action-local identities.
- The untracked latest-run artifacts remain necessary for any later per-identity forensic audit, but they are not required for this implementation boundary.

## 24. Final design classification

`V2_9_8B_GRADUATED_DISCOVERY_LIQUIDITY_MEMORY_ELIGIBILITY_DESIGN_APPROVED`

The narrow next lane is implementation plus focused offline proof. It must not include provider execution or another authorization.
