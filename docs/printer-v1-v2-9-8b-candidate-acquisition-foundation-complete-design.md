# Printer V1 V2-9.8B Candidate-Acquisition Foundation Complete Design

Date: 2026-07-29
Depends on: `printer-v1-v2-9-8b-candidate-acquisition-foundation-combined-audit.md`
Gate: 2 of 4 — complete capacity-neutral design
Verdict: `V2_9_8B_CANDIDATE_ACQUISITION_FOUNDATION_GATE_2_PASS`

## 1. Scope and invariants

This design implements a durable, generic-N candidate-acquisition foundation
without changing the existing active Memory Factory runtime.

| Capacity | Definition | Allowed bound in this lane |
| --- | --- | --- |
| `candidate_acquisition_capacity` | maximum unique normalized candidates evaluated in one frozen execution | explicit `M = 2N`, supports N 1 through 16 |
| `candidate_reserve_capacity` | resilience target for admitted unexpired reserve facts | `R = N + ceil(N/2)`, never activation |
| `selection_capacity` | exact count required in a successful immutable manifest | explicit N, 1 through 16 |
| `approved_active_memory_capacity` | count the existing runtime may activate | exactly 2, immutable lock |

Success means exactly N distinct mint/pool item rows. A partial manifest is not
success. A manifest above two is durable but runtime-neutral. The foundation
does not create runtime work.

The implementation remains Solana-only, memecoin-only, paper-only, free-source
only, non-scoring, non-ranking, non-weighted, non-vector, Scheduler-led and
Source-Governed. It does not activate retrieval, decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL, wallets, signing, transaction submission, or
live execution.

## 2. Canonical flow and ownership

```text
Central Scheduler DISCOVERY_REFRESH plan identity
-> CandidateAcquisitionOwner (one finite execution owner)
   -> Source Governor validation for every declared request kind
   -> bounded source-specific observation rounds
   -> source-specific normalization
   -> exact mint/pair/pool identity merge
   -> deterministic deduplication and conflict capture
   -> categorical low-cost gates
   -> market/freshness/age evidence
   -> holder and safety evidence
   -> liquidity/tradeability evidence
   -> immutable candidate certificate per identity
   -> durable capacity-neutral reserve
   -> deterministic exact-N all-or-none selection
   -> immutable runtime-neutral manifest
   -> immutable canonical report
-> explicit LegacyTwoTokenManifestAdapter
   -> validates exactly two only
   -> produces a read-only projection
   -> does not enqueue or activate anything
```

`CandidateAcquisitionOwner` is the only new composition owner. It consumes
already frozen normalized observations in this lane; it has no network client,
loop, retry, reconnect, sleep, or endpoint rotation. Existing DexScreener,
GeckoTerminal, Pump creation, Pump migration, PumpSwap, holder and safety owners
remain authoritative for their source-specific parsing and future governed
transport. The new owner composes their evidence; it does not duplicate their
live transports.

## 3. Frozen execution plan

Each execution has an immutable plan:

```text
execution_id
policy_id / policy_hash / schema_version / git_provenance
network = solana-mainnet
requested_selection_capacity N
candidate_acquisition_capacity M = 2N
candidate_reserve_target R = N + ceil(N/2)
approved_active_memory_capacity = 2
frozen window start/end/cutoff time and finalized cutoff slot
persisted selection seed and seed domain
allowed source set and deterministic source order
per-source request/operation/byte ceilings
round ceiling and total duration ceiling
no_retry = true / no_reconnect = true
Scheduler owner/kind and Source Governor policy identity
forbidden-delta table/capability set
```

N must be 1 through 16. M and R are derived, never caller-overridden. A plan is
rejected before persistence when any owner, capacity, time boundary, source,
budget, or lock field is missing or inconsistent.

## 4. Observation contract

### 4.1 Rounds

One execution contains a finite ordered sequence of rounds. Each round records:

- round ordinal and mode (`FROZEN_OFFLINE`, future `LIVE_TAIL`, or future
  `BACKFILL`);
- source name, request kind, Scheduler owner/kind, Source Governor decision;
- start/end/cutoff boundaries;
- request, transport-operation, row, byte, and duration use/ceilings;
- response category and stale/failure reason;
- cursor/range identity where applicable; and
- canonical raw-payload hash or fixture hash, never secrets.

Default deterministic source order is direct Pump chain evidence, DexScreener,
GeckoTerminal, optional Birdeye, Solana account evidence, then optional
holder/safety providers. The order governs bounded work and accounting only; it
cannot affect selection because normalized identities are canonicalized before
selection.

### 4.2 Source request kinds

The Source Governor registry gains exact kinds:

| Source | Kinds |
| --- | --- |
| `solana_rpc` | `candidate_mint_account_batch`, `pumpfun_migration_signature_page`, `pumpfun_migration_transaction`, `pumpswap_pool_account_batch` |
| `dexscreener` | `candidate_nomination`, `candidate_market_batch` |
| `geckoterminal` | `candidate_nomination`, `candidate_market_batch` |
| `birdeye` | `birdeye_new_listing_nomination` only |

Historical source kinds remain for reproducibility. PumpPortal and DEXTools get
no new foundation kind. Every new kind has zero automatic retries.

### 4.3 Live tail and backfill modes

Future source execution may use two bounded modes of the same owner:

- `LIVE_TAIL`: fixed finalized slot/time bounds; a WebSocket, if ever adopted,
  is a lossy locator only; finalized HTTP proof remains required.
- `BACKFILL`: fixed oldest/newest range with explicit `before`/`until`, page,
  decode, account, byte, row and duration ceilings.

No separate adapter loop exists. A range is one of `CONTIGUOUS`, `GAPPED`,
`UNKNOWN`, or `BLOCKED_CONTRACT`. Cursor namespace includes network, indexed
address, contract pin, decoder version and direction. Cursor advancement and
accepted/rejected evidence commit atomically. Only a contiguous resolved range
can advance. A blocked/unknown/gapped range is persisted but leaves the prior
cursor unchanged.

## 5. Source normalization

Every provider normalizes to an immutable observation fact:

```text
observation_id and content hash
source / request kind / round / observed_at / expires_at
mint
pair_or_pool
pool_program_id when independently established
base and quote mint
provider venue label
market facts supported by that provider
pair creation time (T4 only)
source status / data quality / stale category
lineage claim, authority scope, and proof identity
```

Unsupported numeric or promotional fields are discarded. A source observation
cannot set an admission result. It supplies facts to categorical gates.

Birdeye normalization accepts only a successful Solana new-listing payload with
an exact address. Name, symbol, liquidity and listing time are nomination facts;
they do not establish exact pair/pool, token origin, Pump lineage, safety or
tradeability.

## 6. Identity merge and lineage

Primary candidate identity is exact Solana mint. Market identity is exact
`network:pool_program:pool`. A candidate cannot carry two current selected pools
or two base mints. All observations remain linked after deduplication.

Identity outcomes:

- `IDENTITY_MERGED`: one mint and one exact current pair/pool;
- `IDENTITY_INCOMPLETE`: required identity absent;
- `IDENTITY_CONFLICT`: same source fact maps mint/pool incompatibly;
- `DUPLICATE_OBSERVATION`: same semantic fact/hash, diagnostic only.

Lineage states:

- `PUMP_ORIGIN_CONFIRMED`;
- `PUMP_GRADUATION_CONFIRMED` (includes exact Pump origin, migrate and canonical
  PumpSwap pool);
- `NON_PUMP_POOL_CONFIRMED` (a pinned supported pool relationship without a
  Pump claim);
- `UNKNOWN_ORIGIN` (present supported pool is exact; launch origin is unknown);
- `CONFLICTING_LINEAGE`;
- `UNSUPPORTED_LINEAGE`.

A Pump-origin candidate that is presented as graduated must have the complete
Pump branch. It cannot fall back to unknown origin after a failed Pump proof.
A candidate with no Pump claim may remain `UNKNOWN_ORIGIN` and can pass the
present-pool branch. Source majority never resolves lineage.

## 7. Direct Pump/PumpSwap contract implementation

The existing create/create_v2 decoder remains pinned to Pump commit
`9c82f61cb711b044a17f770ab8ce9f9bdf78f333` and Pump IDL hash
`b90bc471327f671449271d5d1d42354d1fae6f5a06502f5834459a3108138e49`.

Pump migration proof is repaired to require:

- successful finalized legacy/version-0 transaction;
- exactly one compiled Pump `migrate` instruction with discriminator
  `9beae792ec9ea21e`;
- exactly 25 resolved instruction accounts;
- exact fixed programs/accounts at positions 6, 7, 8, 14, 19, 20, 23 and 24;
- expected mint at position 2 and exact candidate pool at position 9;
- no ambiguous second migrate instruction; and
- joined PumpSwap account proof.

PumpSwap Pool proof requires:

- owner `pAMMb...XEA`;
- discriminator `f19a6d0411b16dbc`;
- complete adopted prefix through `virtual_quote_reserves`;
- canonical migration index zero for the Pump branch;
- exact base mint and wrapped-SOL quote for the adopted migration layout;
- PDA from `pool`, u16-le index, creator, base mint, quote mint;
- exact vault/mint relationships exposed by the prefix; and
- no unknown shorter layout. Longer accounts are permitted only after the
  adopted prefix decodes exactly.

For the present-pool non-Pump/unknown branch, a PumpSwap pool may use a
noncanonical index; it proves a supported present pool but not Pump migration.

## 8. Categorical funnel

The owner evaluates stages in this fixed order:

1. `CHAIN_MINT_VALID` — Solana address, mint account exists, supported owner.
2. `TOKEN_PROGRAM_VALID` — legacy SPL or adopted Token-2022 extension set.
3. `IDENTITY_AVAILABLE` — deterministic merge, not active, not in unexpired
   cooldown, no mint/pool conflict.
4. `POOL_QUOTE_VALID` — exact current pair/pool, supported owner/program, base
   mint and adopted quote mint.
5. `MARKET_FRESH` — current source evidence, fixed market/activity/liquidity
   facts; no magnitude-based preference.
6. `AGE_VALID` — exact token age when policy requires it; T4 pair age stays
   pair-only and unknown origin remains honest.
7. `HOLDER_ACCEPTABLE` — adopted categorical holder evidence and limitations.
8. `SAFETY_ACCEPTABLE` — adopted categorical safety evidence.
9. `LIQUIDITY_TRADEABILITY_VALID` — fixed liquidity floor and route/exit
   category where policy requires it.
10. `LINEAGE_VALID` — Pump branch complete when claimed; otherwise exact
    non-Pump/unknown present-pool branch.
11. `ADMITTED` or one exact first-failure reason.

Expensive holder/safety/route work is never treated as performed when a cheaper
prior gate failed. Every candidate receives one terminal admission outcome.

## 9. Immutable candidate certificate

Each normalized candidate receives a versioned canonical JSON certificate and
SHA-256. It contains:

- certificate/version/schema/policy/configuration/Git identities;
- execution/window/cutoff identity;
- exact mint, selected pair/pool, pool program, token program and quote mint;
- ordered source observation IDs, fact hashes and provenance;
- lineage state and exact Pump origin/migration/Pool proof identities where
  applicable;
- market, freshness, token-age and pair-age facts with evidence tiers;
- holder/safety/liquidity/tradeability categorical facts;
- tracking/cooldown read-only disposition;
- every stage outcome, admission outcome and first failure reason;
- evidence issue/expiry and invalidation categories; and
- certificate hash.

It contains no action, financial, score, rank, confidence, weight, expected
return, BUY/SELL/HOLD, position, trade, audit or PnL field. SQL triggers reject
certificate update/delete.

Expired, stale, malformed, conflicting or unsupported evidence cannot produce
an admitted certificate. Requalification creates a new immutable certificate;
it never edits the prior certificate.

## 10. Durable reserve

Reserve membership is mutable operational state linked to immutable
certificates. Identity is exact mint plus pool. A row contains current
certificate hash, reserve version, `ELIGIBLE_FRESH`/`ELIGIBLE_EXPIRED`/
`EXCLUDED`/`CLAIMED_NEUTRAL` status, issue/expiry, last requalified time and
optional manifest claim.

Rules:

- only admitted, unexpired certificates enter `ELIGIBLE_FRESH`;
- a new certificate increments the reserve version;
- expiry is deterministic at the frozen cutoff;
- an expired row cannot be selected until a new certificate requalifies it;
- a failed exact-N transaction claims nothing;
- a neutral claim creates no runtime side effect;
- reserve target R is reporting, not a quota or source preference.

## 11. Deterministic exact-N selection

Selection reads all fresh admitted reserve rows for the same execution/policy
cutoff, then:

1. canonicalizes by `(mint, pool, certificate_hash)`;
2. rejects duplicate mint or pool identities;
3. computes a seeded permutation key
   `SHA256(seed_domain || persisted_seed || mint || pool || certificate_hash)`;
4. sorts by the permutation key and exact identity tie-breakers;
5. selects the first exactly N only when at least N rows remain;
6. persists N ordered manifest items and one manifest hash atomically.

The permutation is uniform mechanics, not a candidate rank. No provider,
lineage category, liquidity, recency, holder or safety magnitude is used to
prefer an item. Reordered source input yields the same identities, hashes and
manifest.

Readiness:

- Q < N: no manifest; structured failure;
- N <= Q < R: `READY_EXACT_NO_SPARE`;
- Q >= R: `READY_WITH_RESERVE`;
- both ready states select exactly N.

## 12. Runtime-neutral manifest and legacy adapter

Manifest header contains N, item count, ordered item hashes, certificate set,
policy/window/seed/provenance, `runtime_neutral = 1`,
`approved_active_memory_capacity = 2`, manifest hash and creation time. Header
and items are immutable via SQL triggers.

`LegacyTwoTokenManifestAdapter`:

- recomputes and verifies the manifest hash;
- requires exactly two distinct item rows and N=2;
- requires runtime-neutral and active-capacity lock fields;
- rejects N=1 and every N>2 for operational projection;
- returns an immutable two-item projection only;
- creates no campaign, slot, queue, Scheduler or runtime row.

Existing runtime owners must separately validate and consume that projection in
a future explicitly authorized operational-adoption lane. This lane does not
wire the projection into runtime.

## 13. Structured failure taxonomy

Execution failure has exactly one primary family and may include stage detail:

| Family | Examples |
| --- | --- |
| `COVERAGE_FAILURE` | round/page ceiling, incomplete cursor range, unexplored work |
| `SOURCE_PROVIDER_FAILURE` | transport/5xx/unavailable optional or required source |
| `BUDGET_EXHAUSTION` | request, operation, byte, row or duration ceiling |
| `STALE_OR_INCOMPLETE_EVIDENCE` | stale, expired, missing required field |
| `UNSUPPORTED_CONTRACT` | unknown instruction/account/program/version/extension |
| `IDENTITY_MERGE_FAILURE` | conflicting mint/pool/base/quote relationships |
| `ADMISSION_FAILURE` | candidates observed but categorical gates rejected them |
| `INSUFFICIENT_ELIGIBLE_POOL` | all declared coverage complete, providers healthy, budgets not the cause, and fewer than N truly qualify |

Precedence is unsupported contract, provider failure, budget, coverage,
stale/incomplete, identity, admission, then actual insufficient pool. A source
outage can never silently become market shortage.

Migration 048 also adds `TRACKING_STATE_CAPACITY_BLOCKED` to the legacy
exhaustion CHECK, preserving its exact existing code meaning.

## 14. Schema and migration 048

Migration `048_candidate_acquisition_foundation.sql` is append-only and owns:

1. rebuild `printer_discovery_exhaustion_certificates` with the missing
   `TRACKING_STATE_CAPACITY_BLOCKED` CHECK value; copy all existing rows exactly;
2. `printer_candidate_acquisition_policies` — immutable policy/config capacity,
   source, budget and lock identity;
3. `printer_candidate_acquisition_executions` — immutable execution/window,
   input, verdict and failure identity;
4. `printer_candidate_source_rounds` — bounded source round/accounting;
5. `printer_candidate_source_observations` — source-specific normalized facts;
6. `printer_candidate_identities` — exact merged identity and lineage;
7. `printer_candidate_observation_links` — contribution/overlap join;
8. `printer_candidate_cursor_ranges` — cursor namespace, boundaries and
   continuity;
9. `printer_candidate_evidence` — stage/category/fact hash rows;
10. `printer_candidate_certificates` — immutable canonical candidate JSON/hash;
11. `printer_candidate_reserve` — capacity-neutral current membership/version;
12. `printer_candidate_manifests` — immutable exact-N runtime-neutral headers;
13. `printer_candidate_manifest_items` — immutable ordinals/certificate links;
14. `printer_candidate_acquisition_failures` — structured reason/family;
15. `printer_candidate_acquisition_reports` — immutable canonical report and
    replay hash.

Unique constraints prevent duplicate semantic observation, mint/pool identity,
certificate hash, manifest hash and manifest ordinal. CHECKs enforce N 1..16,
M=2N, R formula supplied by code and validated by table values, active capacity
2, runtime-neutral true, valid categorical states and nonempty hashes.

No foreign key points from runtime tables into this foundation. Manifest items
point to certificates; reserve points to current certificate and optional
neutral manifest. Immutable tables have update/delete-abort triggers.

### 14.1 Forward migration proof

On disposable copies only:

1. copy the authoritative DB bytes to a temporary directory;
2. record pre-migration legacy exhaustion row count and canonical JSON/hash
   values;
3. apply migrations through 048;
4. validate migration ledger, `integrity_check`, `foreign_key_check`, new tables,
   indexes and triggers;
5. compare every legacy exhaustion row field;
6. insert the previously failing tracking-capacity classification;
7. run old read/report paths against the upgraded copy.

Fresh empty disposable DB migration is also required.

### 14.2 Rollback/restore

Applied migrations are never edited or reversed in place. The rollback plan is
restore of the byte-for-byte pre-migration backup after verifying its hash. If
048 fails, discard the disposable DB. Any later operational adoption must take
an operator-approved backup before applying 048 to an authoritative DB.

## 15. Report and zero-source replay

The canonical report contains:

- observations and governed operations per source/request kind;
- unique contribution and cross-source overlap counts;
- funnel input/pass/exclusion counts by stage and reason;
- provider/contract/coverage/budget/stale failures;
- cursor continuity;
- certificates issued/admitted/rejected;
- reserve count and readiness category;
- requested N, exact-N result, manifest/item/hash identity;
- inability reason/family when no manifest;
- runtime handoff projection count (always 0 unless explicit adapter validation
  is invoked; still no runtime write);
- active capacity lock 2;
- forbidden table before/after counts and zero deltas;
- reliability claim status.

The owner stores one idempotent immutable canonical report keyed by execution
and report hash. `replay_candidate_acquisition_report` opens the DB read-only,
loads and hashes that report, verifies execution/policy/input/replay identity,
and returns the canonical payload. It performs zero source, Scheduler and DB
writes. Repeated replay is byte-identical.

## 16. Frozen fixtures

Committed fixtures contain no secrets and no live captures created by this
lane. They include synthetic mechanics cases for:

- at least 32 qualifying identities across DexScreener, GeckoTerminal and
  optional Birdeye overlap;
- exact Pump origin/migration/canonical PumpSwap proof-shaped facts;
- exact present-pool unknown-origin and non-Pump cases;
- malformed, conflicting, stale, expired, unsupported and provider-outage
  observations;
- exact N success and N-1 failure;
- source input reordering;
- duplicate mint/pool observations; and
- cursor continuity categories.

Fixture metadata states `SYNTHETIC_MECHANICS_ONLY`. It cannot be used as an
independently frozen real-observation qualifying window.

## 17. Verification design

Focused tests must prove:

1. registry/request-kind and no-paid/no-wallet contracts;
2. Birdeye fixture normalization and no-network default;
3. exact Pump migrate discriminator/account/finality/version proof;
4. PumpSwap discriminator/prefix/index/base/quote/PDA verification;
5. Scheduler owner is `DISCOVERY_REFRESH` and every declared source request is
   Governor-allowed;
6. deterministic multi-source merge, overlap and conflicts;
7. Pump, non-Pump and unknown-origin lineage behavior;
8. all categorical stages and failure precedence;
9. certificate canonicalization, expiry, immutability and requalification;
10. durable reserve and exact-N all-or-none atomicity;
11. deterministic seeded ordering independent of input/source order;
12. runtime-neutral N>2 manifests and strict two-token adapter;
13. zero-source deterministic/idempotent replay;
14. disposable forward migration, row preservation, CHECK repair, FK/integrity;
15. zero runtime/memory/retrieval/financial deltas; and
16. N matrix `2,3,4,5,6,7,10,16`, success and N-1 honest failure.

Nearest source, Source Governor, Scheduler, migration, eligible-supply,
report/replay and capability-lock regressions run after focused tests. The broad
relevant suite runs once at final closeout.

No reliability PASS is permitted without 459 independently frozen qualifying
windows per N and the predeclared acceptance rule. The committed synthetic
matrix proves mechanics only; reliability remains `UNPROVEN_NO_INDEPENDENT_SAMPLE`.

## 18. Implementation file boundary

Expected production scope:

- `migrations/048_candidate_acquisition_foundation.sql`;
- `src/printer_v1/discovery/candidate_acquisition.py`;
- `src/printer_v1/sources/birdeye.py`;
- exact registry and Pump migration/Pool contract repairs;
- package exports only where needed;
- frozen fixture and focused tests;
- active source-stack clarification and closeout documents.

Existing operational campaign, combined executor, tracking queue, Scheduler
execution, memory, retrieval, paper and financial owners are not generalized.

## 19. Functionality Risks / Setbacks / Efficiency Blockers

| Type | Risk / blocker | Design response |
| --- | --- | --- |
| migration risk | SQLite CHECK repair requires table rebuild | disposable copy proof and exact row comparison; restore backup on failure |
| contract risk | future Pump variants/extensions | immutable pins and categorical `UNSUPPORTED_CONTRACT` |
| capacity risk | M=2N may not find N in real markets | honest coverage/admission/shortage outcome; no reliability claim |
| source risk | optional Birdeye requires account key | unavailable source category; no secret in durable data; no paid fallback |
| efficiency blocker | holder/safety work scales per candidate | cheap gates first; exact M ceiling; source-specific accounting |
| identity risk | multiple pools per mint | exact selected current pool required; conflict otherwise |
| runtime risk | N>2 manifest mistaken as permission | runtime-neutral CHECK plus strict two-item adapter and no runtime FK |
| replay risk | report drift | canonical JSON/hash and read-only replay verification |
| evidence limitation | synthetic proof is not live reliability | explicit mechanics-only marker and unproven status |

## 20. Gate 2 pass basis

Gate 2 passes because the owner, capacities, source kinds, observation/cursor
semantics, lineage, staged gates, certificate, reserve, exact-N selection,
manifest, legacy adapter, schema, migration, report, replay, fixtures, failure
precedence and verification are fully specified without inventing an unresolved
provider or protocol contract.

Next permitted step inside this combined task: Gate 3 implementation and
disposable-DB migration proof.
