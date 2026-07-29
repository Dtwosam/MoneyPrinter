# Printer V1 V2-9.8B Candidate-Acquisition Capacity Feasibility Audit

Date: 2026-07-28

Required baseline: `7c38f13816169c69697ed19893b7e12802d9b1b7`

Mode: read-only source inspection, existing-test inspection,
official-primary-documentation research, and SQLite `mode=ro` /
`query_only=ON` only

Operational memory capacity: locked at `2`

## Verdict

`V2_9_8B_CANDIDATE_ACQUISITION_CAPACITY_FEASIBILITY_PASS`

It is feasible to design a factory-wide, capacity-neutral acquisition foundation
that observes, admits, reserves, deterministically selects, and certifies exact
bounded capacity `N`, including `2` through `7`, `10`, and `16`, while the active
memory operation remains capped at two tokens. The safe boundary is an immutable
candidate certificate plus an atomic, runtime-neutral reserve manifest. It is not
the current campaign slot handoff.

This PASS authorizes only a separate roadmap-adoption/design lane. It does not
authorize implementation, migrations, source execution, discovery, Scheduler or
campaign runtime, memory runtime, capacity above two, another selective-1h proof,
or any financial capability.

## 1. Scope, authority, and method

The audit used the required authority stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-python-builder-guide.md`
- `docs/printer-v1-v2-9-8b-selective-1h-comprehensive-blocker-audit.md`
- `docs/printer-v1-v2-9-8b-selective-1h-comprehensive-repair-design.md`
- `docs/printer-v1-v2-9-8b-selective-1h-comprehensive-repair-closeout.md`

The inspection then covered the discovery, eligible-supply, persistent reserve,
tracking, selection, atomic handoff, Source Governor, Central Scheduler, campaign,
reporting, provider adapter, source-contract, schema, migration, and corresponding
test surfaces. The semantic test sweep included all 263 test/fixture files whose
names or contents reference discovery, eligible supply, reserves, tracking,
selection, handoff, sources, Scheduler, campaigns, or reports. The current V2-9.8B
and nearest V2-9.7D/E contract tests were inspected in detail. Historical Lane X4
and X5 runners were inspected as evidence of isolated three- and five-token work,
not as a generic current architecture.

No Printer adapter, provider transport, discovery command, campaign command,
Scheduler executor, lifecycle owner, memory factory, proof command, retry,
restart, or successor was invoked. The Python Builder Guide classification for
this study is primarily `DESIGN_GAP`: capacity-neutral acquisition has no adopted
implementation boundary. The observed provider mismatches are `CONTRACT_DRIFT`
or `UNKNOWN_REQUIRES_RESEARCH`; current fail-closed market/tracking outcomes are
not evidence that an unapproved code repair or larger runtime is justified.

## 2. Authoritative repository and database state

| Check | Result |
| --- | --- |
| `HEAD` | `7c38f13816169c69697ed19893b7e12802d9b1b7` |
| Initial worktree | clean |
| SQLite open mode | `mode=ro`; `PRAGMA query_only=ON` |
| `PRAGMA query_only` | `1` |
| `PRAGMA integrity_check` | `ok` |
| Authoritative DB before SHA-256 | `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872` |

Read-only current-state facts:

- `printer_eligible_token_reserve`: three `ELIGIBLE_FRESH`, five `REMOVED`;
  all eight carry `LIQUIDITY_PROVEN`.
- `printer_tracking_queue`: six `TRACK_FAST/QUEUED`; four
  `TRACK_NORMAL/COOLDOWN`; ten `TRACK_NORMAL/QUEUED`; eight
  `TRACK_NORMAL/SKIPPED`; one `WATCH_ONLY/QUEUED`.
- The three current fresh reserve mints have exact PumpSwap pools and liquidity
  of `$9,867.12`, `$3,260.44`, and `$16,020.66`. The first two are attached to
  `TRACK_NORMAL/COOLDOWN` rows whose retained timing caused the last pre-lifecycle
  stop; the third has no existing queue row.
- The latest retained campaign run is terminal with
  `COOLDOWN_REOPEN_REQUIRED`. The earlier retained runs include one completed
  two-token 15m campaign and one source-outage shortfall.
- The only persisted exhaustion certificate requires capacity two and records
  `BUDGET_EXHAUSTION` with zero eligible reserve rows for its intake window.

These facts explain why “tokens exist in the market” and “two candidates are
simultaneously claimable” are not interchangeable.

## 3. Current end-to-end call and ownership map

```text
operator command
  operational_memory_factory_command.py  [TOKEN_CAPACITY = 2]
          |
          v
single operational campaign owner
  authoritative_live_operational_campaign.py
          |
          +--> Source Governor admission + durable request/response/failure rows
          |      sources/governor.py, governed_execution.py, recording.py
          |
          +--> candidate observation
          |      Pump create index / PumpPortal migration
          |      GeckoTerminal / DexScreener / Solana Tracker observations
          |
          +--> exact origin and graduation
          |      pumpfun_origin.py -> finalized create proof
          |      direct_migration_discovery.py -> pumpswap.py
          |      getTransaction + getMultipleAccounts, exact mint/pool ownership
          |
          +--> persistent eligible-supply owner
          |      eligible_token_supply.py
          |      durable reserve -> mandatory stale/fresh revalidation
          |      deterministic batches of six until capacity/budget/duration stop
          |
          +--> exact-pool market front door
          |      graduated_liquidity_front_door.py
          |      current $3,000 categorical floor; no score/rank
          |
          +--> pre-source tracking assessment
          |      lifecycle/tracking_queue.py
          |      active/cooldown/terminal/expired-cooldown categories
          |
          +--> holder/safety admission
          |      GoPlus + Solana RPC; Helius free backup where configured
          |      holder_reliability_budget_control.py [45-operation ledger]
          |
          +--> deterministic two-candidate choice
          |      combined seeded-uniform reserve order; stop at two eligible
          |
          +--> pilot input pair bundle
          |      pilot_input_readiness.py [latest + persisted fields]
          |
          +--> atomic two-slot handoff
          |      combined_executor.py / campaign_ownership.py
          |      tracking rows + slot 1/2 + 15m windows + Scheduler work
          |
          v
two-token Scheduler and lifecycle
  scheduler/two_token_fairness.py
  scheduler/token_local_continuation.py
          |
          v
15m / selective-1h runtime and terminal report
  operational_selective_1h.py
  final_campaign_report.py
  unified_terminal_closure.py
```

Ownership is mostly sound: external observations must enter through Source
Governor, campaign work is Scheduler-owned, and candidate evidence converges on
the shared reserve and campaign pipeline. Capacity neutrality must preserve
those owners. It must not add an adapter loop, a parallel Scheduler, or isolated
memory.

## 4. Why acquisition struggles at capacity two despite market availability

| Finding | Evidence | Classification |
| --- | --- | --- |
| Visible candidates are not admitted candidates. | The retained source-outage attempt observed 24 candidates and spent 30 governed calls, but every exact liquidity transport failed with `No route to host`; zero could become current clean market evidence. | external source risk |
| Reserve eligibility is time- and claim-specific. | Three reserve rows are currently fresh and above the liquidity floor, but two retained exact identities are in cooldown and only one is immediately new/claimable. | expected fail-closed policy |
| Admission is conjunctive. | Exact Pump origin, PumpSwap graduation/pool, exact-pool liquidity, freshness, holder/safety, and tracking claim must all pass for the same mint/pool. Market existence alone satisfies none of the later gates. | expected fail-closed policy |
| The system needs simultaneous capacity. | One lawful candidate is preserved, but the two-slot campaign cannot partially activate. The schema and atomic handoff correctly require two-or-none. | two-token coupling |
| The current funnel stops and budgets for two, not for supply depth. | Discovery defaults are two required, batches of six, 30 discovery operations, and a 45-operation lifecycle ledger. Holder work reserves five transport operations per evaluated candidate and stops after two passes. | scalability blocker |
| Source productivity is asymmetric. | A migration session can return few or duplicate events; each newly observed candidate then consumes exact graduation, market, and holder work. Thin yield magnifies the cost of one rejection. | efficiency blocker |
| Durable evidence saves observation cost but cannot be trusted indefinitely. | Every prior fresh reserve is changed to stale for mandatory market revalidation before it can count in a new campaign. This spends calls but prevents fake availability. | expected fail-closed policy |
| Tracking used to be checked after expensive evidence. | The latest comprehensive repair moved unavoidable tracking exclusions ahead of exact-pool calls, but direct discovery and reserve revalidation can still be necessary to find replacements. | efficiency blocker |
| The most recent comprehensive repair removed known in-repository selective-1h blockers, not provider or supply uncertainty. | Its closeout explicitly leaves free-source availability and genuine two-token qualifying supply operationally unproven. | external source risk |

The root problem is stage yield, not raw market count. For a frozen intake window,
let `O` be unique observations, `G` exact Pump/PumpSwap graduations, `L` current
exact-pool liquidity passes, `H` holder/safety passes, `T` tracking-claimable
identities, and `A` admitted identities. Capacity two succeeds only when
`A >= 2`, where `A <= T <= H <= L <= G <= O`. Current reporting surfaces pieces
of this chain but not one immutable, window-bound funnel certificate.

## 5. Two-token assumption inventory

### 5.1 Code and interface coupling

| Owner / interface | Confirmed assumption | Classification | Generic-foundation disposition |
| --- | --- | --- | --- |
| `discovery/eligible_token_supply.py` | `REQUIRED_TOKEN_CAPACITY = 2`; public defaults require two. The internal loop accepts `required_token_capacity >= 1` and most accumulation logic is already cardinality-generic. | two-token coupling | Retain generic loop idea; replace operational default with an explicit acquisition contract only in a later implementation lane. |
| `discovery/graduated_liquidity_front_door.py` | `_mixed_two_slot`, `_composition_label`, `combined_two_token` domain, `len(selected) == 2`, one latest plus one persisted carrier, `atomic_two_slot_ready`. | two-token coupling | Generalize only the acquisition selector/certificate. Keep current operational front door unchanged until a two-token adapter is designed. |
| `operator_cli/graduated_supply_front_door.py` | Default capacity two, two-slot comments, first-`capacity` slicing, `selected_latest` / `selected_persisted` singleton fields. | two-token coupling | Replace singleton provenance outputs with item rows in the neutral certificate; preserve legacy pair adapter. |
| `discovery/combined_executor.py` | `TRACKING_HANDOFFS = 2`; two handoff work types; fixtures default to `(1, 2)`; preflight requires two selections and slots `[1,2]`; accounting adds two; atomic owner loops over `(1,2)`. | two-token coupling | Do not generalize this runtime owner in the foundation lane. Add a separate neutral manifest boundary. |
| `operator_cli/authoritative_live_operational_campaign.py` | Holder funnel stops at exactly two; choice loop stops at two; readiness is a pair; activation checks two distinct ordinals. | two-token coupling | Keep runtime locked at two. An acquisition service must terminate before this owner. |
| `operator_cli/operational_memory_factory_command.py` | `TOKEN_CAPACITY = 2`; discovery metadata ceiling two; reserve slice `[:TOKEN_CAPACITY]`; “without two selected” failure; two-based close reservations and reports. | two-token coupling | No change until a later runtime-capacity lane; only a capacity-two projection may call it. |
| `operator_cli/pilot_input_readiness.py` | Bundle has `latest_mint/pool/...` and `persisted_mint/pool/...`, with distinct-pair semantics. | two-token coupling | Keep as legacy pair bundle; neutral certificates use item rows. |
| `operator_cli/campaign_ownership.py` and `origin_lifecycle_campaign.py` | Slot set must equal `{1,2}`; non-1/2 ordinals rejected. | two-token coupling | Later runtime-only migration, not acquisition foundation. |
| `scheduler/two_token_fairness.py` | `TWO_TOKEN_ACTIVE_SLOT_COUNT = 2`; other counts fail. | two-token coupling | Remains exactly two. |
| `scheduler/token_local_continuation.py` | Requires and returns exactly two token evaluations. | two-token coupling | Remains exactly two; future multi-token continuation is separate. |
| `operator_cli/final_campaign_report.py` | Every non-insufficient cycle must have two slots; payload key is `two_token_slots`. | two-token coupling | Acquisition report must be separate and cardinality-generic. |
| `operator_cli/unified_terminal_closure.py` | Default required capacity is two, though much blocked-supply reporting accepts an integer. | two-token coupling | Reuse generic fields only; do not route N-slot activation through terminal closure. |
| `operator_cli/two_token_operational_pilot_runner.py` | Command, duration, and lifecycle semantics are explicitly two-token. | two-token coupling | Preserve. |
| Lane X4/X5 runners | Three- and five-token historical runners exist as lane-specific surfaces rather than a shared `N` contract. | scalability blocker | Evidence that copy-per-capacity is unsafe; do not promote them as the foundation. |

### 5.2 Schema coupling

| Schema object | Confirmed assumption | Classification | Impact |
| --- | --- | --- | --- |
| `migrations/032_campaign_ownership_schema.sql` / `printer_memory_factory_campaign_token_slots` | `slot_ordinal CHECK (slot_ordinal IN (1,2))`. | two-token coupling | Current runtime cannot persist slot 3+. |
| `migrations/035_insufficient_pool_cycle_terminal_trigger.sql` | A nonterminal transition from `PLANNED` aborts unless the cycle has exactly two slots. | two-token coupling | Current campaign cannot start with N other than two. |
| `migrations/041_pilot_input_readiness_bundle.sql` | One `latest_*` candidate and one `persisted_*` candidate are columns in a single row. | two-token coupling | Requires item-table replacement for generic N. |
| `migrations/037_holder_reliability_budget_control.sql` | Operation ceiling is exactly 45 and Dex snapshot reservation exactly two. | two-token coupling | Admission economics are operational, not a generic factory budget. |
| `migrations/039_snapshot_readiness_contract_repair.sql` | Snapshot completion reservation is exactly four, i.e. two completion operations per active token. | two-token coupling | Must remain with two-token runtime. |
| `printer_discovery_selected_item_links` | Selected items link directly to campaign token slots. | two-token coupling | A neutral acquisition selection needs an item manifest before runtime slots exist. |
| `printer_selection_batches` / `printer_selection_batch_items` | Counts and item rows are cardinality-generic; no schema check fixes two. | safe generic foundation | Can inform a generic certificate design, subject to source-stack ownership. |
| `printer_eligible_token_reserve` | Identity-keyed rows and status categories contain no two-row constraint. | safe generic foundation | Reusable with certificate lineage and atomic-claim additions. |
| `printer_tracking_queue` | Row-based tracking has no two-row schema cap. | safe generic foundation | Queue cardinality is generic; operational ownership above it is not. |
| `printer_discovery_exhaustion_certificates.required_eligible_capacity` | Accepts any integer `>= 1`. | safe generic foundation | Good cardinality field, but the overall certificate contract is incomplete. |
| `printer_discovery_exhaustion_certificates.shortage_classification` | The CHECK list omits `TRACKING_STATE_CAPACITY_BLOCKED`, although current code can emit and immediately persist it. No later migration or focused test covers that branch. | current confirmed blocker | A tracking-capacity shortfall can fail with SQLite constraint error instead of persisting its truthful certificate. Must be resolved in a separately authorized migration design. |

### 5.3 Budget, report, and test coupling

| Surface | Exact coupling | Classification |
| --- | --- | --- |
| Admission ledger | Fixed charges: nine zero-transport validations, two snapshot reservations, four snapshot-completion reservations; five worst-case transports per candidate; 45 total. | two-token coupling |
| Operational 15m command | 65 governed requests, 21 per token, 51 Scheduler rows, 64 MiB storage, 1,200 seconds. | future runtime-capacity concern |
| Selective-1h command | 92 governed requests, 45 per token, 82 Scheduler rows, 3,900 seconds, 2,700-second continuation. | future runtime-capacity concern |
| Readiness owner | 8 MiB storage, 360 seconds, response ceiling 1.5 MiB, and pair-based activation reports. | two-token coupling |
| Final campaign report | Enforces two-or-none and names its slot collection `two_token_slots`. | two-token coupling |
| Discovery-only report | Capacity field is generic but command always supplies two and selects the first two. | two-token coupling |
| Current focused tests | Assert constant two, slots 1/2, two tracking rows, two windows, two selected links, two activated slots, two continuation objects, and pair bundle fields. | two-token coupling |
| Historical multi-token tests | Assert lane-specific three/five behavior, not a shared N invariant across acquisition, reserve, certificate, and handoff. | scalability blocker |

Not every literal `2` is a capacity assumption. Two RPC methods in the holder
adapter, two seconds of conservative source pacing, two snapshot operations per
token, and test token identifiers are method/cadence facts. They must not be
mechanically parameterized.

## 6. Official source-contract refresh

This section records current official primary documentation as of the audit
date. It does not authorize a request.

| Source | Current official contract | Repository assumption / gap | Classification |
| --- | --- | --- | --- |
| DexScreener | Latest profile/advertising endpoints are 60 requests/minute; pair, search, token-pair, and token endpoints are 300/minute. The tokens endpoint accepts up to 30 comma-separated addresses. [Official API reference](https://docs.dexscreener.com/api/reference) | Registry uses a conservative 60/minute. Current exact-pair work is one request per pair even though a future acquisition observer could batch up to 30 mints and retain only the exact confirmed pool. | safe generic foundation |
| GeckoTerminal | Public API is keyless beta and the current limit is 30 calls/minute. [Official FAQ](https://apiguide.geckoterminal.com/faq) | Registry and notes still say 10/minute. Conservative behavior is safe, but the pinned contract text is stale. | source-contract gap |
| Solana public RPC | Mainnet public endpoints publish 100 requests/10 seconds/IP, 40 requests/10 seconds for one RPC method, 100 MB/30 seconds, and explicitly warn that limits may change and public RPC is not intended for production. [Official cluster limits](https://solana.com/docs/references/clusters) `getMultipleAccounts` accepts up to 100 addresses and returns them in request order. [Official RPC method](https://solana.com/docs/rpc/http/getmultipleaccounts) | Registry uses 30/minute and adapters use read-only finalized calls. The conservative local limit is safe. Public availability has no SLA and must remain an external risk. | external source risk |
| Helius | Free RPC base rate is 10 requests/second; complex `getProgramAccounts` is 5/second; historical `getTransaction` batches may contain up to 100 items. [Official rate limits](https://www.helius.dev/docs/billing/rate-limits) | Optional free-key backup is fixed-host, zero-retry, and conservatively registered at 30/minute. It remains an optional provider, not a required paid dependency. | safe generic foundation |
| Alchemy | Free plan currently publishes 30 million monthly compute units and 500 CU/second. Solana `getMultipleAccounts`, `getTokenLargestAccounts`, and `getTokenSupply` cost 20 CU each; `getSignaturesForAddress` and `getTransaction` cost 40 CU each. [Official plan](https://www.alchemy.com/docs/reference/pricing-plans) [Official CU table](https://www.alchemy.com/docs/reference/compute-unit-costs) | There is no Alchemy registry entry, adapter contract, key policy, or Source Governor request kind. It cannot be silently treated as Helius. | source-contract gap |
| PumpPortal | The current WebSocket URL is documented as `wss://pumpportal.fun/api/data?api-key=...`; `subscribeNewToken` and `subscribeMigration` are marked free; token/account trade streams are metered and require a linked funded wallet. The provider requires one shared WebSocket connection. [Official real-time API](https://pumpportal.fun/data-api/real-time/) | Adapter uses `wss://pumpportal.fun/api/data` without key, says no auth, permits up to five events/120 seconds, and zero reconnects. Whether the free launch/migration methods remain usable without a key/wallet is not stated clearly enough to rely on. Metered trade streams are prohibited regardless. | source-contract gap |
| Pump program | Pump is `6EF8...F6P`; `migrate(user,mint)` is permissionless and idempotent for a completed bonding curve and creates PumpSwap liquidity. [Official Pump program docs](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_PROGRAM_README.md) | Direct origin code pins commit `9c82f61...` and IDL hash `b90bc...`. Current upstream now contains `create_v2`, quote-mint additions, and other layout evolution. Pin refresh is required before any implementation. | source-contract gap |
| PumpSwap | PumpSwap is `pAMM...XEA`; migrated pools use canonical index zero; pool state exposes base/quote mints and now appends `virtual_quote_reserves`. [Official PumpSwap docs](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_SWAP_README.md) | Current owner verifies program ownership and base mint at byte offset 43. That remains plausible for the prefix layout, but the full IDL hash, account length tolerance, quote-mint restriction, and canonical index evidence must be repinned. | source-contract gap |
| GoPlus | Solana Token Security is beta; API is free at 30 calls/minute. The endpoint reference documents an `Authorization: Bearer ...` header. [Official endpoint](https://docs.gopluslabs.io/reference/solanatokensecurityusingget) [Official rate limit](https://docs.gopluslabs.io/reference/support) | Adapter explicitly says no authentication and sends no bearer token. Until an official keyless response contract is adopted, live availability is inconclusive. | source-contract gap |
| Jupiter | New plans use `api.jup.ag`; free is 1 request/second and keyless is 0.5 request/second. The migration guide replaces `lite-api.jup.ag` with `api.jup.ag`. [Official plans](https://developers.jup.ag/docs/portal/plans) [Official migration](https://developers.jup.ag/docs/portal/migration) | Adapter still calls `lite-api.jup.ag/swap/v1/quote`. Jupiter is paper quote realism only and must not become candidate discovery or admission. Host migration is a later paper-realism contract task. | source-contract gap |

## 7. Source coverage and resilience matrix

| Evidence category | Primary observation | Independent supplement | Exact admission rule | Failure behavior |
| --- | --- | --- | --- | --- |
| Newly created Pump mint | Pump create-exclusive on-chain index, finalized signature page + transaction decode | PumpPortal `subscribeNewToken` if its free auth contract is adopted | Exact Pump program, supported create discriminator/layout, exact mint, finalized lineage | Missing/ambiguous origin is excluded. |
| Graduation/migration | Pump `migrate` transaction or PumpPortal `subscribeMigration` | PumpSwap program transaction observation | Exact mint, canonical PumpSwap pool, PumpSwap owner, canonical index zero, allowed quote mint | Aggregator-only migration never qualifies. |
| Pool identity | Decoded Pump/PumpSwap transaction | Batched `getMultipleAccounts` | Exact owner, exact base mint, exact pool identity, supported layout pin | Any mismatch/ambiguous pool fails closed. |
| Market visibility | DexScreener token batch and exact-pool match | GeckoTerminal new/trending observation and exact-pool fallback under an adopted contract | Current exact pool, current timestamp, categorical `$3,000` floor; no best-pool substitution | Stale, missing, malformed, or conflicting evidence does not count. |
| Safety | GoPlus if its auth contract is resolved | Existing Solana safety evidence where available | Existing categorical safety gates only | Unknown safety remains non-admissible under current policy. |
| Holder condition | Solana RPC `getTokenLargestAccounts` + `getTokenSupply` | Helius free fixed-host backup; Alchemy only after a new provider contract | Existing aggregate categorical holder policy; limitations retained | No endpoint rotation or retry; unavailable evidence remains unknown. |
| Tracking claim | Read-only exact mint/pair queue assessment | Final assessment inside atomic claim transaction | New identity or explicitly expired cooldown with wholly fresh requalification evidence | Active, pre-expiry cooldown, terminal, mismatch, or race loses the claim. |
| Paper exit realism | Not part of acquisition | Jupiter quote only in a later paper-realism/runtime boundary | Never a candidate discovery or selection signal | No effect on acquisition capacity. |

Provider disagreement is not settled by majority, voting, weights, or a score.
Identity truth comes from the exact on-chain contract. Aggregators contribute
visibility and current market facts. A conflict becomes a categorical exclusion
or operator-visible source-contract failure.

## 8. Direct Pump.fun / PumpSwap on-chain supplement

Direct observation can safely supplement aggregators without a wallet:

1. The Source Governor admits one bounded read-only observation plan with a
   frozen start, end, finalized cutoff, provider-contract versions, and request
   ceilings.
2. A Central-Scheduler-owned observation work item reads finalized signatures
   from the Pump create-exclusive index and/or Pump migration program address.
3. Bounded `getTransaction` calls decode only the adopted create/migrate
   discriminators and exact account positions.
4. Pool identities extracted from those transactions are deduplicated and
   verified with batched `getMultipleAccounts` calls. Each pool must be owned by
   PumpSwap and decode to the same mint, canonical index, and allowed quote mint.
5. Aggregators can then supply current exact-pool liquidity and market activity;
   they cannot replace the on-chain origin/graduation certificate.
6. Every request has one attempt. There is no retry, reconnect, endpoint
   rotation, transaction construction, signing, subscription per token, or
   independent engine loop.

No wallet is needed for `getSignaturesForAddress`, `getTransaction`, or
`getMultipleAccounts`. The official Pump documentation describes `migrate` as
permissionless, but Printer only observes it; Printer never invokes it. Direct
observation must refresh the Pump and PumpSwap IDL pins before implementation,
because current upstream layout evolution is a confirmed contract risk.

## 9. Proposed capacity-neutral architecture

```text
CapacityRequest(N, frozen_window, categorical_policy, source_budget)
              |
              v
Governed Observation Coordinator
  one Scheduler-owned plan; no per-source loops
  Pump on-chain + PumpPortal (conditional) + Dex + Gecko
              |
              v
Identity Normalizer and Deduplicator
  exact mint/pool/signature; source facts remain separate
              |
              v
Categorical Evidence Funnel
  origin -> graduation -> exact pool -> freshness/liquidity
  -> safety/holder -> tracking claimability
              |
              v
Durable Capacity-Neutral Reserve
  identity rows, evidence expiry, exclusion reasons, no slots
              |
              v
Deterministic Exact-N Selector
  seeded permutation within categorical partitions
  deterministic round-robin across available partitions
  no value comparison, score, rank, confidence, or weight
              |
              v
Immutable Candidate Certificate + N Item Rows
              |
              v
Atomic Runtime-Neutral Reserve Manifest
  expected item count N; all-or-none claims; no Scheduler work
              |
              +--> future explicit adapter for current runtime (must require 2)
              +--> later separate multi-token Scheduler/runtime lane (locked)
```

### 9.1 Capacity invariants

- `N` is an explicit positive integer in the request, certificate, report, and
  manifest. No module infers it from a global constant.
- Candidate evaluation ceiling is explicit and bounded. The reference model in
  this audit uses `M = 2N`; this is an economic envelope, not an eligibility
  relaxation or statistical claim.
- Success requires exactly `N` distinct exact mint/pool item rows and one
  manifest hash over those rows.
- More than `N` admitted candidates remain reserve rows; they are not silently
  activated or discarded.
- Reserve target is `R = N + ceil(N/2)`. `N <= Q < R` is
  `READY_EXACT_NO_SPARE`; `Q >= R` is `READY_WITH_RESERVE`; `Q < N` is a
  truthful shortfall. Both ready states select exactly `N`.
- Every freshness and expiry rule is evaluated at the frozen certificate
  cutoff. A cooldown expiring later cannot change the result.
- Selection order may use the existing audited seeded Fisher-Yates primitive
  inside fixed categorical partitions. It may not use liquidity magnitude,
  recency magnitude, holder percentage, provider order, a score, a rank, a
  confidence value, or a weighted choice.
- The foundation produces no campaign slot, Scheduler job, snapshot, window,
  episode, memory, decision, position, trade, audit, or PnL row.

### 9.2 Categorical evidence funnel

Each item advances through named categories only:

1. `OBSERVED_UNIQUE`
2. `PUMP_ORIGIN_EXACT`
3. `PUMPSWAP_GRADUATION_EXACT`
4. `EXACT_POOL_CURRENT`
5. `LIQUIDITY_FLOOR_PROVEN`
6. `SAFETY_EVIDENCE_ACCEPTABLE`
7. `HOLDER_EVIDENCE_ACCEPTABLE`
8. `TRACKING_CLAIMABLE_AT_CUTOFF`
9. `ADMITTED_TO_RESERVE`
10. `SELECTED_IN_EXACT_N_MANIFEST` or `RESERVE_NOT_SELECTED`

Every loss between stages records a categorical reason. Stage yields are counts
and fractions for factory diagnostics, never candidate scores.

## 10. Stage-yield and request-budget model

### 10.1 Reference envelope and equations

This is a feasibility envelope for a future design lane, not a live budget
change. It assumes one frozen observation window, no retries, no reconnects,
and evaluates at most `M = 2N` unique candidates.

Definitions:

- `M = 2N` — unique candidate evidence ceiling.
- `R = N + ceil(N/2)` — reserve target, never an activation count.
- `P = ceil(M/16)` — bounded on-chain signature pages.
- `A = ceil(M/100)` — batched pool-account verification requests.
- `B = ceil(M/30)` — DexScreener token-batch market requests.
- Fixed observation requests: one PumpPortal session, two GeckoTerminal pool
  observations, one DexScreener profile observation.
- Per candidate governed admission: one GoPlus request, one Solana holder
  request, and one Helius backup request = `3M` governed requests.
- Per candidate worst-case holder/safety transports: GoPlus one + Solana two +
  Helius two = `5M` transports. This deliberately matches the current worst-case
  holder contract; backup evidence is budgeted even when a healthy primary may
  avoid it.
- Total governed request ceiling:
  `G = 4 + P + A + B + 4M`.
- Total underlying network-operation ceiling:
  `U = 4 + P + A + B + 6M`.
- Sequential no-retry duration ceiling:
  `D = 180 + 6M + 2P + 2A` seconds. This includes the 120-second PumpPortal
  window, conservative 30/minute Solana and GoPlus pacing, fixed processing
  headroom, and does not depend on concurrency.
- Proposed normalized durable storage ceiling:
  `S = 128 KiB + (256 KiB * M) + (16 KiB * G)`. Raw responses remain bounded
  source-by-source and are not duplicated into the certificate.
- Current undifferentiated 1.5 MiB response ceiling would permit as much as
  `1.5 MiB * U`; the table shows why source-specific byte ceilings are required.

### 10.2 Exact economics by capacity

| N | M | R | PumpPortal | Gecko | Dex | Solana governed | GoPlus | Helius | G | U | Admission transports `5M` | D seconds | S MiB | Current raw max MiB |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 4 | 3 | 1 | 2 | 2 | 10 | 4 | 4 | 23 | 31 | 20 | 208 | 1.484 | 46.5 |
| 3 | 6 | 5 | 1 | 2 | 2 | 14 | 6 | 6 | 31 | 43 | 30 | 220 | 2.109 | 64.5 |
| 4 | 8 | 6 | 1 | 2 | 2 | 18 | 8 | 8 | 39 | 55 | 40 | 232 | 2.734 | 82.5 |
| 5 | 10 | 8 | 1 | 2 | 2 | 22 | 10 | 10 | 47 | 67 | 50 | 244 | 3.359 | 100.5 |
| 6 | 12 | 9 | 1 | 2 | 2 | 26 | 12 | 12 | 55 | 79 | 60 | 256 | 3.984 | 118.5 |
| 7 | 14 | 11 | 1 | 2 | 2 | 30 | 14 | 14 | 63 | 91 | 70 | 268 | 4.609 | 136.5 |
| 10 | 20 | 15 | 1 | 2 | 2 | 43 | 20 | 20 | 88 | 128 | 100 | 306 | 6.500 | 192.0 |
| 16 | 32 | 24 | 1 | 2 | 3 | 67 | 32 | 32 | 137 | 201 | 160 | 378 | 10.266 | 301.5 |

`Solana governed = P + A + 2M`: one set of transaction decodes plus one holder
request per candidate; the latter contains two underlying RPC methods. Helius is
shown as a fully budgeted backup. If a later adopted contract substitutes Alchemy
for Helius, it is not additive: the backup consumes `M` governed requests and
`40M` Solana CU for the two 20-CU holder methods. That is 160, 240, 320, 400,
480, 560, 800, and 1,280 CU respectively for the capacities above—well below the
published free monthly allowance, but still prohibited until Alchemy has an
approved Source Governor contract.

### 10.3 Current budget incompatibility

The present admission ledger has 45 operations, with fixed charges of:

```text
zero-transport validation                9
reserved Dex snapshots                   2
reserved snapshot completion             4
fixed total                              15
remaining before discovery/holder work  30
worst holder transports per candidate    5
```

If base discovery and market work has already charged `b`, the current candidate
evaluation cap is `floor((30 - b) / 5)`. A four-call base leaves five candidate
attempts, matching the intended two-token funnel with reserve failures. It cannot
fund the reference exact-N evidence envelope for N=4+, and even N=3 would consume
all 30 remaining operations before any base work. Therefore:

- the 45 ceiling must not be raised or repurposed in the foundation lane;
- acquisition observation/admission accounting needs its own explicitly bounded
  ledger and certificate;
- runtime snapshots and close reservations remain exclusively in the two-token
  operational ledger;
- a future two-token adapter may consume an already certified reserve without
  pretending the acquisition calls were runtime snapshot calls.

## 11. Candidate certificate and reserve contract

### 11.1 Certificate header

The immutable header should contain:

- `certificate_id`, version, schema hash, policy hash, and Git provenance;
- requested `N`, candidate ceiling `M`, reserve target `R`, selected count, and
  admitted reserve count;
- frozen intake window id, start, end, finalized cutoff slot/time, and timezone;
- Source Governor policy version, Scheduler plan identity, allowed source set,
  provider-contract commit/hash, request ceilings, duration ceiling, byte
  ceilings, and observed usage by source/request kind;
- no-retry/no-reconnect flags and actual attempt counts;
- stage counts and categorical loss reasons;
- duplicate identity counts, conflicts, stale exclusions, cooldown exclusions,
  and unexplored work at each hard stop;
- exact readiness category and shortage classification;
- selected-manifest hash, item count, and ordered item hashes;
- forbidden-delta attestation for runtime, memory, retrieval, financial, wallet,
  signing, paid-source, scoring, ranking, confidence, weight, embedding, and
  vector tables/capabilities.

The current exhaustion certificate already supplies capacity, reserve count,
channels, observations, duplicates, pools, market checks, rejection reasons,
cooldowns, provider outcomes, operations, duration, unexplored work, stop reason,
and rounds. It lacks a frozen qualifying-window identity/hash, successful exact-N
certificate type, item-level evidence hashes, full source-contract set, atomic
manifest, per-stage counts, provider-specific budgets, byte accounting, and
runtime-lock attestation.

### 11.2 Certificate item

Each selected or reserve item should carry:

- exact mint, Pump origin transaction/signature/slot, supported create layout,
  and source fact hash;
- exact migration transaction/signature/slot and canonical PumpSwap pool;
- PumpSwap program id, pool owner, canonical index, base mint, quote mint,
  decoded layout version, and account-evidence hash;
- exact market identity, liquidity category/value/time/source, freshness cutoff,
  and categorical floor result;
- safety and holder categorical facts, source availability, context slots,
  limitations, and evidence hashes;
- tracking category, queue identity/status, effective cooldown expiry, and
  final claim precondition;
- provenance partition, deterministic permutation domain, selection ordinal,
  and categorical reason; no numeric candidate preference value;
- evidence expiry time and invalidation categories.

### 11.3 Reserve policy

- Reserve rows remain identity-keyed by exact mint and pool.
- `ELIGIBLE_FRESH` can count only for the same certificate cutoff and evidence
  contract; later operations must revalidate stale facts.
- A selected item is not removed from the reserve until the entire manifest is
  atomically claimed.
- A failed all-or-none claim releases every claim marker. No partial handoff is
  left behind.
- Unselected reserve items remain auditable and eligible for later frozen
  windows only after freshness and tracking reassessment.
- Cooldown expiry permits reassessment, never admission by itself.
- Reserve target is resilience reporting only. It is not a quota, score, rank,
  or authorization to track/activate more tokens.

## 12. N-slot handoff feasibility

### 12.1 Safe now: runtime-neutral exact-N manifest

An atomic exact-N reserve manifest is feasible with row-oriented tables and one
SQLite transaction:

1. Read the immutable certificate and require `selected_count == N`.
2. Recompute its ordered item hash and reject duplicates by mint or pool.
3. Recheck every reserve row version, freshness cutoff, and tracking category at
   the fixed claim instant.
4. Insert one manifest header with `expected_item_count = N` and exactly N item
   links.
5. Atomically mark the N reserve versions claimed by that manifest.
6. Commit only if the exact item count, unique constraints, evidence hashes, and
   forbidden-delta checks all pass.

This produces no tracking queue rows, campaign slots, windows, or Scheduler work.
It is a safe generic foundation.

### 12.2 Not safe now: direct N-slot runtime activation

The current atomic handoff cannot safely accept N other than two. Slot CHECKs,
cycle triggers, ownership validators, Scheduler fairness, continuation
cardinality, snapshot and close reservations, pilot bundle columns, final reports,
and focused tests all require two. Generalizing only the insertion loop would
either fail schema constraints or bypass the owners that protect cadence,
fairness, closeout, and memory quality.

A future capacity-two adapter could consume a neutral certificate only when its
own requested runtime capacity equals two and after a separately adopted design.
Certificates for N=3+ must remain acquisition artifacts. No truncation from N to
two, automatic secondary selection, or activation is permitted unless the
adapter contract explicitly issues a new exact-two projection certificate with
complete lineage.

## 13. Offline conditional 99% acquisition-reliability proof

### 13.1 Definition

Reliability is a factory verification statistic, not a candidate confidence
system. For capacity N:

```text
C_N(window) = at least N candidates truly satisfy the frozen categorical
              eligibility contract inside the predeclared intake window

S_N(window) = the offline replay observes, verifies, admits, selects, and
              certifies exactly N within the frozen budgets

target       = P(S_N | C_N) >= 0.99
```

`C_N` must be adjudicated from frozen, independently archived source facts and
exact on-chain evidence after the window is sealed—not from what the acquisition
algorithm happened to find. Provider failures in an otherwise qualifying window
count as acquisition failures. Nonqualifying market windows are not hidden: they
are excluded from the conditional numerator/denominator but reported separately
as the unconditional availability base rate.

No window may be extended, retried, replaced, or relabeled after seeing the
result. Contract hashes, capacity, budgets, source set, seed derivation, window
cutoff, and acceptance rule are frozen first.

### 13.2 Exact statistical acceptance rule

Use 459 independently frozen qualifying windows per N and require zero
acquisition failures. If true success probability were only 0.99, the
probability of 459 consecutive successes is `0.99^459 < 0.01`. Thus zero failures
rejects `p <= 0.99` at a one-sided 1% significance level. This is an offline lane
acceptance statistic only; it is never stored on a candidate or used by a
decision engine.

If any failure occurs, the zero-failure rule does not pass. A later design may
predeclare a larger exact-binomial sample/acceptance plan, but it may not choose
one after seeing outcomes. One frozen window with at least 16 independently
adjudicated qualifying candidates may exercise nested N outcomes, but each N
still needs 459 qualifying observations and its own stage-yield report.

### 13.3 Proof matrix

| Proof family | Frozen cases | Required result |
| --- | --- | --- |
| Capacity | N = 2, 3, 4, 5, 6, 7, 10, 16 | Exact N item rows, exact manifest count/hash, no partial selection. |
| Stage yield | Full `O -> G -> L -> H -> T -> A` funnel | Counts reconcile; every loss has one categorical reason; no score/rank field. |
| Duplicate pressure | Same mint/pool across PumpPortal, Pump chain, Dex, and Gecko | One identity; all source contributions retained; duplicates consume no unique capacity. |
| Source outage | Each optional observer unavailable in turn | Approved independent path can still succeed; exact-chain truth missing must fail closed. |
| Provider conflict | Aggregator pool differs from exact on-chain pool | Candidate excluded or exact-pool fact selected categorically; never provider vote. |
| PumpPortal auth unavailable | PumpPortal omitted before window under its adopted availability rule | On-chain supplement alone can qualify if its frozen budget covers N. |
| RPC provider failure | Public Solana failure with predeclared Helius or adopted Alchemy backup | One attempt per approved path; no retry/rotation; failure counted if truth cannot be established. |
| Thin qualifying supply | Fewer than N true qualifying candidates | Truthful market/supply shortfall; not counted as acquisition algorithm success. |
| Tracking conflict | Candidate becomes active/cooldown between evidence and claim | Atomic manifest fails all-or-none; replacement requires a new frozen certificate, not in-window retry. |
| Freshness boundary | Evidence expires at/before/after cutoff | Deterministic inclusion only when fresh at cutoff; no wall-clock drift on replay. |
| Reserve states | Q below N, N through R-1, and at least R | Shortfall, exact-no-spare, and ready-with-reserve categories; exactly N selected in ready cases. |
| Budget edge | Last allowed request/byte/second and one beyond | Exact boundary succeeds when evidence complete; next operation is not issued and shortfall is truthful. |
| Storage | Maximum accepted payload per source class | Normalized storage stays under S; oversized source response fails before certificate admission. |
| Atomicity | Failure after item 1, item N-1, and manifest insert | Zero durable claims or exactly N; never partial. |
| Determinism | Reordered provider responses and repeated replay | Same canonical facts, selection order, item hashes, and manifest hash. |
| Locks | Table/capability deltas | Zero Scheduler runtime, campaign, lifecycle, memory, retrieval, financial, wallet, signing, paid-source, score/rank/weight, embedding, or vector deltas. |

## 14. Schema and migration impact

### 14.1 Interfaces/tables that are already cardinality-friendly

- `printer_selection_batches` and `printer_selection_batch_items`
- most `printer_discovery_*` observation, contribution, origin, and PumpSwap
  confirmation item tables
- `printer_eligible_token_reserve`
- `printer_tracking_queue`
- row-oriented source request/response/failure tables
- `required_eligible_capacity` in the exhaustion certificate

These still require ownership and contract review before reuse; generic row
shape alone is not authorization.

### 14.2 Foundation migration/design required

A later adopted design should prefer normalized header/item contracts rather
than widening pair-shaped rows:

- a frozen acquisition-window header with requested N, M, R, source contract,
  cutoff, budgets, and forbidden-delta fields;
- per-window provider observations and exact candidate-stage facts, either as
  explicit extensions of the current discovery tables or linked neutral tables;
- a generalized candidate certificate header plus item table;
- an atomic reserve-manifest header plus item links and reserve-version claims;
- certificate/report fields for per-source request, underlying-operation,
  duration, and byte usage;
- an explicit success/readiness category in addition to truthful shortfall
  categories;
- a migration that reconciles the current
  `TRACKING_STATE_CAPACITY_BLOCKED` code/schema mismatch without rewriting
  historical certificate meaning.

Every migration needs a disposable-DB upgrade proof, foreign-key/integrity
checks, historical row preservation, rollback design, and exact read-only
authoritative DB handling. This audit authorizes none of them.

### 14.3 Later runtime-only migration, explicitly separate

The following must not be bundled into the acquisition foundation:

- changing `slot_ordinal IN (1,2)`;
- replacing the exactly-two cycle trigger;
- changing campaign ownership or replacement graphs;
- changing two-token Scheduler fairness;
- changing token-local continuation cardinality;
- scaling snapshot cadence, close reservations, source/Scheduler ceilings,
  supervision, duration, storage, heartbeat, or safe-stop budgets;
- replacing the pilot readiness pair bundle;
- changing final campaign report two-or-none rules;
- enabling N>2 campaign, lifecycle, window, memory, or selective-1h runtime.

Those are future runtime-capacity concerns and require their own audit, design,
implementation, bounded proof, and closeout sequence.

## 15. Finding classification register

| Finding | Classification |
| --- | --- |
| Current exact-two acquisition can be blocked despite visible market candidates because only fully current, exact, holder/safety-admissible, tracking-claimable identities count simultaneously. | current confirmed blocker |
| Code can emit `TRACKING_STATE_CAPACITY_BLOCKED` while the certificate schema rejects it. | current confirmed blocker |
| Runtime slots, cycle trigger, ownership, Scheduler, continuation, reports, budgets, and tests enforce two. | two-token coupling |
| PumpPortal URL/auth, Pump/PumpSwap pins, GoPlus auth, Gecko limit text, Jupiter host, and absent Alchemy provider contract need refresh/adoption. | source-contract gap |
| One-candidate exact-pair calls, stale revalidation, low-yield migration sessions, and per-candidate holder backups magnify request cost. | efficiency blocker |
| Current 45-operation admission and 8/64 MiB runtime envelopes do not scale to the reference N evidence plan. | scalability blocker |
| Active ownership, pre-expiry cooldown, stale/malformed/conflicting evidence, below-floor liquidity, and fewer than N qualifying candidates stop safely. | expected fail-closed policy |
| Free/public providers can fail, throttle, change contracts, or provide no SLA. | external source risk |
| Frozen observation, normalized reserve, deterministic categorical exact-N selection, immutable certificate, and runtime-neutral atomic manifest can be generic. | safe generic foundation |
| N>2 Scheduler fairness, cadence, lifecycle, supervision, closeout, reports, and memory activation are separate. | future runtime-capacity concern |
| PumpPortal free launch/migration access without API key or funded wallet is not sufficiently explicit in current official wording. | inconclusive |

## 16. Recommended dependency-ordered roadmap insertion

Before another selective-1h proof, insert the following sequence inside active
V2-9.8B. Each step stops for its own verdict:

1. **Candidate-Acquisition Foundation Roadmap Adoption** — documentation-only.
   Adopt or reject this architecture boundary, reference envelope, locks, and
   dependency order. This is the exact next permitted lane after this PASS.
2. **Official Source-Contract Reconciliation Audit** — read-only. Resolve
   PumpPortal free auth/wallet wording, repin Pump/PumpSwap IDLs and layouts,
   reconcile GoPlus auth, update Gecko limits, decide whether Alchemy free is an
   approved optional source, and keep Jupiter outside acquisition.
3. **Capacity-Neutral Schema and Certificate Design** — design-only. Specify
   frozen windows, stage facts, certificate/item tables, reserve versions,
   atomic manifest, reports, migrations, and rollback. Include the current
   tracking-shortage CHECK mismatch.
4. **Source-Budget and Storage Contract Design** — design-only. Ratify or revise
   `M`, `R`, `G`, `U`, `D`, source-specific byte ceilings, no-retry rules, and
   provider pacing using official contracts. Do not alter operational ceilings.
5. **Capacity-Neutral Foundation Implementation** — only if steps 1-4 explicitly
   authorize it. No source execution or runtime handoff.
6. **Frozen-Window Offline Proof** — fixtures/retained artifacts only. Prove
   exact N, atomicity, deterministic categorical selection, migrations, reports,
   source outages, storage, and locks for all requested N values.
7. **Conditional Reliability Qualification** — offline archived windows only,
   using the predeclared 459-zero-failure rule per N or another pre-adopted exact
   plan. No candidate confidence field.
8. **Two-Token Projection/Handoff Audit and Design** — prove how a neutral
   certificate can feed the existing exact-two runtime without truncation,
   stale reuse, duplicate tracking, budget concealment, or Scheduler bypass.
9. **Fresh read-only V2-9.8B selective-1h operator-readiness review** — only
   after the foundation work is closed or explicitly deferred. This review may
   recommend a later proof; it cannot execute one.

No later step is authorized by completion of an earlier step unless its own
operator-approved lane says so.

## 17. Money-usefulness contribution

A capacity-neutral acquisition foundation improves the part of Printer that
turns market opportunity into auditable learning supply, without pretending
that observation is profit:

- It measures exactly where potentially useful tokens are lost—visibility,
  origin, graduation, pool identity, liquidity, safety, holders, tracking, or
  capacity—instead of collapsing all shortfalls into “not enough tokens.”
- A deeper certified reserve can reduce wasted campaign starts and protect the
  two active memory slots from being filled with stale, conflicting, or
  unclaimable identities.
- Direct read-only Pump/PumpSwap observation reduces aggregator visibility gaps
  while exact on-chain identity remains authoritative.
- Deterministic categorical selection gives all qualifying identities a fair,
  replayable chance without manufacturing alpha through a score or rank.
- Honest source, request, duration, storage, and stage-yield economics show
  whether more clean memory is operationally affordable before any runtime is
  expanded.
- Frozen-window reliability evidence distinguishes acquisition quality from
  genuine market scarcity, preventing fake productivity and rushed retries.

It does not claim that any candidate will pump, that a paper trade would be
profitable, or that capacity above two is money-useful at runtime. Money
usefulness remains clean, manipulation-aware memory growth and realistic capital
protection—not candidate volume.

## 18. What remains locked

- Any implementation or migration from this study.
- Any Printer source fetching, discovery, campaign, Scheduler, lifecycle,
  memory, proof, retry, restart, resume, or successor execution.
- Operational memory capacity above two.
- Any additional selective-1h proof.
- WINDOW_4H, WINDOW_12H, and WINDOW_24H production work.
- Retrieval activation.
- Paper decisions and `BUY`, `SELL`, or `HOLD`.
- Paper positions, trade events, paper trade audits, and PnL.
- Live execution, wallets, private keys, signing, transactions, or real funds.
- Paid APIs or metered PumpPortal trade streams.
- Scoring, ranking, candidate confidence, weighted logic, embeddings, or vectors.
- Source work outside Source Governor or runtime work outside Central Scheduler.
- Treating market regime, chain heat, Jupiter quotes, or broad context as a
  candidate trade signal.

## 19. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / setback / blocker | Effect | Required mitigation / status |
| --- | --- | --- |
| PumpPortal free auth contract is ambiguous. | Current no-key transport may fail even though launch/migration methods are labeled free. | Resolve in official source-contract lane; never add funded-wallet or metered trade dependency. |
| Pump/PumpSwap upstream evolved after the pinned commit. | Discriminators, account length, quote mint, or pool decoding may drift. | Repin official IDLs and fixture hashes before implementation; fail closed on unknown layouts. |
| GoPlus official endpoint documents bearer auth. | Current no-auth adapter can receive 401/403 and eliminate safety/holder supply. | Adopt a free credential contract or keep it unavailable; no paid fallback. |
| Public RPC has no production SLA. | Direct observation or holder evidence can fail despite qualifying market supply. | Predeclare optional free provider contracts, one attempt each, truthful failure certificate. |
| Alchemy is absent from Source Governor. | Treating it as an existing backup would bypass provider policy/accounting. | Separate adoption required; Helius remains the only current optional free-key backup. |
| `M = 2N` may not be enough in adverse stage-yield windows. | Conditional reliability may fail for higher N. | Offline frozen-window evidence must validate or revise M before implementation; never loosen eligibility gates. |
| Per-candidate holder evidence dominates cost. | N=16 has a 160-transport worst-case admission component. | Preserve staged funnel order, reuse only evidence fresh for the frozen contract, and stop work on categorical failure. |
| Current raw response ceiling scales poorly. | Theoretical raw ceiling reaches 301.5 MiB at N=16. | Adopt source-specific byte limits and normalized certificate storage; never rely on average response size. |
| Reserve evidence expires. | A large durable reserve can look available while no longer current. | Version evidence, freeze cutoff, and revalidate before a later certificate/claim. |
| Atomic claim race | Tracking state may change after certificate creation. | Final transaction recheck; all-or-none failure; no in-window retry. |
| Certificate/schema shortage mismatch | Tracking-capacity failure can abort certificate persistence. | Explicit migration design before implementation. |
| Historical multi-token code may invite reuse. | Lane-specific runners do not prove generic Scheduler/runtime safety. | Keep them historical; build no N>2 runtime in the foundation. |
| Conditional reliability can be gamed by post-hoc window selection. | Reported 99% would be meaningless. | Pre-register windows and conditions; independent adjudication; report unconditional availability and every exclusion. |
| More candidates can consume resources needed for open positions/snapshots. | Factory priorities could invert. | Acquisition foundation remains runtime-neutral; later scheduling must preserve the locked resource-priority order. |
| No live validation was permitted. | Official contract research and static feasibility do not prove provider availability today. | Expected limitation; only later explicitly authorized lanes may test providers. |

## 20. Pass basis and stop point

The feasibility question passes because the observation, evidence, reserve, and
selection domains can be represented as capacity-request and item rows; the
existing eligible-supply loop, row-based reserve, tracking queue, selection
batch schema, Source Governor, and deterministic seeded primitives provide
reusable concepts. Exact N atomicity is straightforward at a neutral manifest
boundary.

The current operational system is not capacity-neutral. Its schema, ownership,
Scheduler, continuation, budgets, reports, and tests are deliberately two-token.
The safe feasibility result therefore depends on keeping the generic foundation
strictly upstream of runtime activation and preserving the operational cap of
two.

The exact next permitted lane is **V2-9.8B Candidate-Acquisition Foundation
Roadmap Adoption**, documentation-only. Stop after that lane's adoption verdict;
do not implement, migrate, execute sources, raise capacity, or run another
selective-1h proof.
