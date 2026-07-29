# Printer V1 V2-9.8B Candidate-Acquisition Foundation Combined Audit

Date: 2026-07-29
Lane: V2-9.8B Factory-Wide Candidate-Acquisition Foundation
Gate: 1 of 4 — combined audit and source-scope reconciliation
Verdict: `V2_9_8B_CANDIDATE_ACQUISITION_FOUNDATION_GATE_1_PASS`

## 1. Baseline and authorization

| Check | Result |
| --- | --- |
| Required HEAD | `219ad8125a75f52686bfbf5953be0fa4cdca4712` — exact match |
| Branch | `master` |
| Tracked worktree and index | clean before this lane |
| Untracked inventory | none reported by `git status --short --untracked-files=all` |
| Authoritative DB | `data/printer_v1.sqlite3` |
| Authoritative DB SHA-256 before work | `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872` |
| Live/source authorization | none; zero Printer/provider/RPC/WebSocket calls permitted |
| Mutation authorization | repository files and disposable databases only |

The operator explicitly authorized the combined audit, design, implementation,
disposable migration proof, and frozen offline proof as one gated task. That
authorization supersedes the prior roadmap's read-only-next-step stop point for
this task only. It does not authorize live acquisition or an operational
campaign.

## 2. Python Builder Guide classification

```text
BLOCKER CLASSIFICATION:
  CONTRACT_DRIFT plus MISSING_APPROVED_IMPLEMENTATION_BOUNDARY
EVIDENCE:
  current Pump/PumpSwap artifacts, provider documents, repository owner map,
  migration 046 CHECK mismatch, and capacity feasibility audit
OFFICIAL-SOURCE COMPARISON:
  Pump/PumpSwap layouts are now pinned; broad provider dispositions are resolved
PRINTER-CONTRACT COMPARISON:
  capacity-neutral acquisition is permitted; runtime remains exactly two
ROOT CAUSE:
  the repository has a two-token operational supply path but no generic-N,
  immutable certificate/reserve/manifest foundation and one stale schema CHECK
CODE CHANGE JUSTIFIED: YES
MINIMUM SAFE RESPONSE:
  one normalized offline-capable foundation, one forward migration, exact
  contract repairs, focused tests, and no runtime activation
FOCUSED PROOF:
  disposable migration plus frozen N=2,3,4,5,6,7,10,16 matrix
UNTOUCHED SCOPE:
  authoritative DB, live providers, runtime capacity, memory/retrieval/financial
AUTHORIZATION STATUS:
  this combined lane only
NEXT ROADMAP-COMPLIANT STEP:
  Gate 2 complete capacity-neutral design
```

## 3. Superseding source-authority clarification

The earlier candidate-acquisition roadmap adoption is refined, not discarded.
The following model supersedes only its exclusive-Pump candidate-universe
language:

1. Candidate discovery is multi-source.
2. Pump.fun/PumpSwap is a required first-class discovery lane, but is not the
   exclusive candidate universe.
3. DexScreener and GeckoTerminal may nominate candidates directly.
4. Birdeye may nominate through its adopted free Standard-plan route when an
   operator supplies an account API-key secret reference; it is optional.
5. DEXTools remains unimplemented because the current official public material
   does not expose a sufficiently exact free API endpoint/limit/plan contract.
6. PumpPortal remains an optional but unavailable locator because its API-key
   acquisition and wallet product are not compatible enough with V1 to adopt.
7. Aggregators can establish nomination and their supported market facts. They
   cannot establish unsupported launch origin, protocol lineage, migration, or
   canonical-pool identity.
8. Pump-specific origin and graduation claims require exact Pump and joined
   Pump-migration/PumpSwap proof.
9. A non-Pump or unknown-origin candidate is not required to have Pump lineage.
   It can be eligible when exact Solana mint/token-program/current-pool identity,
   a pinned supported pool program relationship, quote mint, market, age where
   required, safety, holder, liquidity, tradeability, and freshness facts pass.
10. Unknown origin remains `UNKNOWN_ORIGIN`; it is neither rewritten as Pump nor
    rejected merely because origin is unknown.
11. No source quota, Pump percentage, preference, score, rank, confidence,
    weighting, or source-order selection advantage is allowed.
12. Source contribution and overlap are diagnostic counts only.

## 4. Exact Pump and PumpSwap pins

Official repository: `https://github.com/pump-fun/pump-public-docs`
Pinned commit: `9c82f61cb711b044a17f770ab8ce9f9bdf78f333`
Commit timestamp: `2026-07-16T02:22:27+08:00`
Commit subject: `chore: README virtual quotes reserves`

Raw artifacts were retrieved read-only from that exact commit into a disposable
directory. These hashes are the implementation authority:

| Artifact | Raw SHA-256 |
| --- | --- |
| `idl/pump.json` | `b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49` |
| `idl/pump_amm.json` | `6b5c7ec4e5ef9742fa99dc57b0d75b1031b379bba02a7e1b3c5a4cad68d77e56` |
| `docs/PUMP_PROGRAM_README.md` | `3532f985fcab38480392759a6c2f01015b7178b9f2c7dc0db8c9f85ce9f72571` |
| `docs/PUMP_SWAP_README.md` | `3ac4a835604d7fd3855d66531d109c0547e006bd314b5e5d6cb27b1e20d27abc` |
| `docs/instructions/COIN_CREATION.md` | `310f4560d0c95d8a196a4d3193399de87407de7f90218949290d4b03ec874536` |
| repository `README.md` | `7609341176750cd2c78a74e8b3eab052053d71cecabd0252ef9c4d8e356e8cca` |

### 4.1 Pump program

Program ID: `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`.

Supported creation layouts:

| Layout | Discriminator | Exact account count/order summary | Token program |
| --- | --- | --- | --- |
| `create` | `181ec828051c0777` | 14 accounts; mint at 0, mint authority 1, bonding curve 2, ATA 3, global 4, metadata program 5, metadata 6, user 7, system 8, token 9, ATA program 10, rent 11, event authority 12, Pump 13 | SPL Token |
| `create_v2` | `d6904cec5f8b31b4` | 16 IDL accounts; mint 0, mint authority 1, bonding curve 2, ATA 3, global 4, user 5, system 6, Token-2022 7, ATA program 8, mayhem accounts 9-13, event authority 14, Pump 15; non-native quote support has exactly three documented remaining accounts | Token-2022 |

Both variants touch the exact Pump mint-authority PDA
`TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM`, so the existing finalized
create-exclusive index remains an exact bounded indexing surface. Unknown
creation discriminators or wrong account order are `BLOCKED_CONTRACT`.

`BondingCurve` account discriminator is `17b7f83760d8ac60`. Its pinned prefix is:
virtual token reserves, virtual quote reserves, real token reserves, real quote
reserves, token supply, complete, creator, mayhem flag, cashback flag, quote mint.
Pump documents `extend_account`; shorter accounts fail malformed, and longer
accounts may be accepted only when the complete pinned prefix decodes exactly.

Relevant events:

| Event | Discriminator | Role |
| --- | --- | --- |
| `CreateEvent` | `1b72a94ddeeb6376` | exact create consistency evidence |
| `CompleteEvent` | `5f72619cd42e9808` | bonding-curve completion context |
| `CompletePumpAmmMigrationEvent` | `bde95db95c94ea94` | user, mint, amounts, fee, curve, timestamp, pool, quote-mint migration evidence |

### 4.2 Pump migration

`migrate` discriminator: `9beae792ec9ea21e`.

The exact 25-account order is:

```text
global, withdraw_authority, mint, bonding_curve, associated_bonding_curve,
user, system_program, token_program, pump_amm, pool, pool_authority,
pool_authority_mint_account, pool_authority_wsol_account, amm_global_config,
wsol_mint, lp_mint, user_pool_token_account, pool_base_token_account,
pool_quote_token_account, token_2022_program, associated_token_program,
pump_amm_event_authority, event_authority, program, rent
```

The IDL fixes the base token program to legacy SPL Token, `pump_amm` to the
PumpSwap program, `wsol_mint` to wrapped SOL, account 23 to Pump, and the LP
program account to Token-2022. Therefore this pin supports the exact legacy
SPL/WSOL migration layout only. It does not authorize guessing a Token-2022 base
mint migration layout. `create_v2` origin can be recorded, but Pump graduation
cannot be claimed unless a later pinned migration contract supports it.

Direct migration indexing is feasible without a guessed address:

1. bounded finalized `getSignaturesForAddress` pages on the exact Pump program
   address, using `before`/`until` boundaries;
2. finalized `getTransaction` with `maxSupportedTransactionVersion = 0`;
3. require successful transaction and exact `migrate` compiled instruction;
4. resolve the exact 25 instruction accounts, with mint at 2 and pool at 9;
5. require the joined PumpSwap account proof below.

The strategy is program-wide and potentially expensive, but finite page/decode
budgets and a restart-safe cursor make it implementable. It is not evidence of
absence when history is pruned or a budget ends.

### 4.3 PumpSwap

Program ID: `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`.

`Pool` account discriminator: `f19a6d0411b16dbc`. The exact pinned prefix is:

```text
pool_bump u8, index u16, creator pubkey, base_mint pubkey,
quote_mint pubkey, lp_mint pubkey, pool_base_token_account pubkey,
pool_quote_token_account pubkey, lp_supply u64, coin_creator pubkey,
is_mayhem_mode bool, is_cashback_coin bool, virtual_quote_reserves i128
```

Pool PDA seeds are `pool`, little-endian `u16 index`, creator, base mint, quote
mint. Pump migrations require canonical index `0`. Pool ownership, account
discriminator, exact prefix, PDA, base mint, wrapped-SOL quote mint, and vault
relationships are mandatory for the adopted migration layout. The appended
`virtual_quote_reserves` field proves the program's append-only extension
practice, but future unknown extensions are ignored only after the full adopted
prefix is present and valid.

`CreatePoolEvent` discriminator is `b1310cd2a076a774`; it carries timestamp,
index, creator, base/quote mint, pool and vault identities, amounts, bump, LP
mint, coin creator, and mayhem flag. It is corroborating evidence; exact account
state remains authoritative.

### 4.4 Finality, transaction version, and continuity

- Accepted chain facts require successful finalized transactions.
- Supported transaction versions are legacy and version 0 only.
- `getTransaction` must request `commitment=finalized` and
  `maxSupportedTransactionVersion=0`.
- Version, missing transaction, pruning, malformed loaded addresses, unknown
  discriminator, or instruction ambiguity fail closed.
- Range states are exactly `CONTIGUOUS`, `GAPPED`, `UNKNOWN`, and
  `BLOCKED_CONTRACT`.
- A cursor contains network, indexed address, contract pin, decoder version,
  direction, slot, signature, and same-slot ordering identity.
- Accepted facts, rejected facts, range status, and advancement must commit
  atomically. Cursor advancement cannot cross unresolved evidence.

## 5. Broad discovery provider reconciliation

Research date for all moving provider contracts: 2026-07-29.

| Provider | Official route and capability | Auth / free boundary | Limits, pagination, freshness, fields | Foundation role and disposition |
| --- | --- | --- | --- | --- |
| DexScreener | `GET /token-profiles/latest/v1`; `GET /tokens/v1/solana/{addresses}`; exact pair route | keyless; free public API | profiles 60/min; pair/search/token 300/min; token batch up to 30; fields include chain/dex/pair, base/quote, price, txns, volume, price change, liquidity, FDV, market cap, pair creation | direct nomination plus current supported market facts; **approved and implemented**; no origin/migration/canonical claim |
| GeckoTerminal | `/api/v2/networks/solana/new_pools`, `/trending_pools`, exact/multi pool routes | keyless public beta | current public limit 30/min; finite `page`; pool fields include exact address, base/quote relationship, reserve USD, creation time, price, transactions and volume; 20 rows/page is treated as a bounded adapter ceiling | direct nomination plus current market/pair-age facts; **approved and implemented**; no token-origin claim |
| Birdeye | `GET https://public-api.birdeye.so/defi/v2/tokens/new_listing`, `meme_platform_enabled` optional | Standard plan costs $0; account and `X-API-KEY` required; no wallet | Standard 1 request/second and 30,000 monthly CU; new-listing max 20; `time_to`; Solana `x-chain`; address/name/symbol/liquidity/listing time; 400/401/403/429/500 explicit | optional direct nomination; **approved for fixture/parser implementation only**; absent key is source unavailable, not shortage; no paid plan and no origin/pool proof |
| DEXTools | API V2 portal exists and official articles say free and paid plans | exact current machine-readable free endpoint, auth, quota and Solana batch contract are not publicly resolved without the JS plan portal | insufficient exact current contract for bounded Source Governor adoption | **deferred/prohibited from implementation**; UI availability is not an API contract |
| PumpPortal | one WebSocket `wss://pumpportal.fun/api/data?api-key=...`; `subscribeNewToken` and `subscribeMigration` labeled free | API key required by current URL; official API-key creation is tied to a generated Lightning wallet/private key; funded wallet required for metered trade streams | one connection; processed-level locator only; no historical data; trade streams cost 0.01 SOL/10,000 and require wallet funding | **optional but unavailable/prohibited from new implementation**; no wallet/key creation; no trade streams; never authoritative |

Official provider sources:

- DexScreener: `https://docs.dexscreener.com/api/reference`
- GeckoTerminal: `https://apiguide.geckoterminal.com/faq` and `/changelogs`
- Birdeye: `https://docs.birdeye.so/docs/pricing`,
  `/docs/authentication-api-keys`, and
  `/reference/get-defi-v2-tokens-new_listing`
- DEXTools: `https://developer.dextools.io/` and official API V2 announcements
- PumpPortal: `https://pumpportal.fun/data-api/real-time/`, `/fees/`, and `/FAQ/`

### 5.1 Failure and stale semantics

All providers use one governed attempt per frozen operation. No hidden retry,
endpoint rotation, or fallback can be omitted from accounting.

| Condition | Required category |
| --- | --- |
| provider unavailable / 5xx / transport | `SOURCE_PROVIDER_FAILURE` |
| 401/403 or required key absent | `SOURCE_AUTH_UNAVAILABLE` |
| 429 | `SOURCE_BUDGET_OR_RATE_LIMIT` |
| malformed body or missing identity | `SOURCE_MALFORMED` |
| observation after its frozen freshness cutoff | `STALE_OR_EXPIRED_EVIDENCE` |
| pagination/round ceiling with unobserved work | `COVERAGE_INCOMPLETE` or `BUDGET_EXHAUSTION` |
| contract/layout not pinned | `UNSUPPORTED_CONTRACT` / range `BLOCKED_CONTRACT` |

None of these may become `INSUFFICIENT_ELIGIBLE_POOL`.

## 6. Supporting evidence providers

- Solana core RPC is read-only transport. Required methods are
  `getSignaturesForAddress`, `getTransaction`, `getMultipleAccounts`,
  `getAccountInfo`, `getTokenLargestAccounts`, and `getTokenSupply`. Public RPC
  has no production SLA, so unavailability is source failure.
- SPL Token program is
  `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA`; Token-2022 is
  `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb`. Exact mint ownership and
  supported extensions are categorical gates.
- GoPlus Solana Token Security remains optional/beta and authenticated. Missing
  GoPlus does not become safe evidence; adopted on-chain safety evidence may
  satisfy the policy independently.
- Jupiter remains paper quote realism only. It contributes no nomination,
  admission, lineage, selection, or manifest fact in this foundation.
- Pair age from aggregators is `T4_PAIR_ONLY`; it never becomes token creation
  age. Exact token-age tiers remain governed by the token-age registry.

## 7. Minimum compliant source set

The minimum implementable foundation is:

1. DexScreener and/or GeckoTerminal for direct candidate nomination and current
   market facts;
2. approved Solana RPC for mint/token-program and exact pool-owner/account
   verification;
3. direct Pump create and migration indexing when a Pump claim is made;
4. exact PumpSwap state for Pump graduation and for any PumpSwap current-pool
   relationship;
5. adopted holder and safety evidence through Solana RPC and optional free
   providers; and
6. no PumpPortal, DEXTools, paid Birdeye, or paid RPC dependency.

Birdeye can add optional nomination coverage. Its absence does not block the
foundation. Pump candidates must satisfy the Pump-specific branch. Unknown or
non-Pump candidates follow the present-pool branch and retain honest lineage.

## 8. Repository owner map

| Concern | Current canonical owner | Finding / foundation treatment |
| --- | --- | --- |
| source registry/request kinds | `sources/registry.py`, `sources/governor.py` | add exact foundation kinds and Birdeye-free disposition; no private source calls |
| Dex/Gecko parsing | `sources/dexscreener.py`, `sources/geckoterminal.py`, `sources/secondary_discovery.py` | reusable normalization; preserve provider provenance |
| Pump creation | `sources/pumpfun_origin.py`, `sources/pumpfun_direct.py` | current pin and create/create_v2 decoder reusable |
| Pump migration | `sources/pump_migration.py`, `discovery/direct_migration_discovery.py` | current proof uses program presence and says discriminator unknown; must be repaired to exact migrate decode |
| PumpSwap pool | `sources/pumpswap.py`, `sources/pumpswap_graduated_registry.py` | current owner/base-mint check is incomplete; foundation needs discriminator/index/quote/PDA/prefix proof |
| discovery orchestration | `discovery/combined_executor.py` | operational two-slot owner remains unchanged; new capacity-neutral owner stops before runtime |
| eligible supply | `discovery/eligible_token_supply.py` | multi-round reserve is useful but Pump-only/pair-shaped and not an immutable generic certificate |
| selection | `discovery/selection_batch.py` | existing deterministic seeded primitive is reusable only without source/value preference |
| holder/safety | operational holder funnel, `sources/solana_rpc_holder.py`, `sources/helius_holder.py`, `sources/goplus.py`, `safety/*` | expensive evidence remains after cheap identity/market gates |
| tracking/cooldown | `lifecycle/tracking_queue.py`, selection cooldown owners | read-only precheck and atomic recheck; no queue write from neutral foundation |
| Scheduler | `scheduler/contracts.py`, `scheduler/scheduler.py`, resource governor | `DISCOVERY_REFRESH` remains the lower-priority Scheduler work class; no new loop |
| Source Governor | `sources/governor.py`, governed execution and recording | every future transport request must use it; offline proof validates request kinds only |
| runtime handoff | `discovery/combined_executor.py`, campaign ownership and readiness owners | explicit adapter accepts at most two; N>2 remains runtime-neutral |
| report/replay | operational report owners and zero-source replay | add a foundation report/replay owner; no source or Scheduler execution |
| schema/migrations | `migrations/*.sql`, `db/migrate.py` | new append-only 048 migration; never edit applied migrations |

## 9. Two-token assumptions and generic-N impact

The feasibility audit's inventory is confirmed:

- operational selection, holder funnel, combined executor, campaign ownership,
  runtime slots, trigger, readiness pair, Scheduler fairness, snapshot budgets,
  continuation and reports are exactly two;
- `printer_memory_factory_campaign_token_slots.slot_ordinal`, cycle triggers and
  pair-shaped readiness schema prohibit slot 3+;
- candidate acquisition, reserve, certificate and manifest can be row-oriented
  and generic through at least 16 without changing runtime;
- the neutral owner must not insert tracking queue, campaign, Scheduler,
  lifecycle, snapshot, window, memory, retrieval or financial rows;
- the legacy adapter is a validation/projection boundary only and rejects any
  manifest whose item count is above two.

## 10. Funnel and cost-order audit

Current code sometimes performs exact-pair liquidity and holder work before all
identity/tracking exclusions are settled. The safe order is:

```text
chain/mint validity
-> token-program validity
-> identity/dedup/active tracking/cooldown
-> usable exact pool and quote mint
-> batched market/liquidity/activity/freshness
-> token/pair-age evidence where required
-> holder and safety evidence
-> route/tradeability evidence where required
```

Every transition is categorical. Numeric facts can be compared to fixed policy
thresholds, but cannot be combined into a score, rank or weight.

## 11. Capacity, reserve and selection findings

The audited generic envelope is retained:

- candidate acquisition ceiling `M = 2N`;
- reserve target `R = N + ceil(N/2)`;
- `Q < N`: honest shortfall;
- `N <= Q < R`: `READY_EXACT_NO_SPARE`;
- `Q >= R`: `READY_WITH_RESERVE`;
- success always selects exactly N distinct mint/pool identities;
- no partial manifest is success;
- ordering is canonical hash/identity ordering, or a persisted seeded uniform
  permutation; it never depends on provider order or market magnitude.

## 12. Defect and blocker register

| Finding | Classification | Gate 1 resolution |
| --- | --- | --- |
| migration 046 CHECK omits `TRACKING_STATE_CAPACITY_BLOCKED` while code emits it | `COMMITTED_CODE_DEFECT` | migration 048 must rebuild the table while preserving rows |
| `pump_migration.py` proves only program presence and explicitly says discriminator unknown | `CONTRACT_DRIFT` | exact migrate discriminator/account order now pinned; repair required |
| PumpSwap confirmation checks owner/base offset but not full discriminator/index/quote/PDA/prefix | `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` | exact Pool pin now known; repair or foundation verifier required |
| exclusive-Pump candidate language rejects honest non-Pump/unknown origin | `DESIGN_GAP` | authority clarification above resolves it |
| current supply/exhaustion model conflates several failure families | `COMMITTED_CODE_DEFECT` for CHECK branch; broader missing boundary | structured foundation failure taxonomy required |
| Gecko registry says 10/min while current official limit is 30/min | conservative stale note | keep 10/min or update note; no need to increase budget |
| PumpPortal new URL/API key and wallet linkage | `CONTRACT_DRIFT` | prohibit new implementation; existing historical path is not foundation authority |
| DEXTools exact free API contract unresolved | `UNKNOWN_REQUIRES_RESEARCH` | deferred; does not block minimum set |
| Birdeye free Standard new-listing route | resolved optional contract | fixture/parser implementation allowed; no paid fallback |
| no independent 459-window sample | evidence limitation | mechanics may pass; 99% reliability remains unproven |

## 13. Gate 1 pass basis

Gate 1 passes because:

- the source universe and exact evidence authority are reconciled;
- exact Pump/PumpSwap pins, layouts, discriminators, indexing addresses and
  cursor feasibility are known;
- a compliant minimum provider set exists without paid data or wallets;
- optional/deferred/prohibited providers have explicit dispositions;
- every affected canonical owner and two-token boundary is identified;
- the migration defect and direct migration/pool verification gaps are bounded;
- Gate 2 can define schemas, ownership, budgets and failures without inventing a
  provider or protocol contract.

## 14. Functionality Risks / Setbacks / Efficiency Blockers

| Type | Risk / setback / blocker | Required treatment |
| --- | --- | --- |
| efficiency blocker | Pump program-wide migration history is high-volume | finite pages/decode budget, cursor slices, no evidence-of-absence claim |
| external risk | free/public RPC retention and availability have no SLA | `GAPPED`/`UNKNOWN`, optional predeclared free transport, no hidden retry |
| contract risk | Pump programs can append fields and add variants | immutable pins; exact prefix and supported discriminator allowlist |
| source risk | aggregator pair identity can conflict | exact identity merge; categorical conflict; no provider vote |
| auth risk | Birdeye key can be absent/expired | secret reference only; source-unavailable category; no paid fallback |
| prohibition | PumpPortal API-key acquisition is wallet-linked | no new adapter path; never create/store wallet/private key |
| coverage risk | DEXTools remains unresolved | defer without blocking Dex/Gecko minimum |
| runtime risk | a generic manifest may be mistaken for runtime authority | immutable runtime-neutral flag and hard two-item adapter |
| evidence limitation | synthetic fixtures do not prove live reliability | closeout must state mechanics-only and no 99% claim |

## 15. Gate result and next step

Gate 1: PASS.
Next permitted step inside this combined task: Gate 2 complete
capacity-neutral foundation design. Production code remains untouched until
Gate 2 passes.
