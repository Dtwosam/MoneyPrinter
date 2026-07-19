# V2-9.7D.7B.1 Multi-Source Discovery and Selection Readiness Audit

## Status

PASS for the audit only. A bounded multi-source campaign is not ready to run.
No operational campaign or command surface should start.

## Todo / Checklist

- [x] Confirm the exact baseline and inspect the active source stack.
- [x] Inspect discovery, selection, cooldown, persistence, and 7A ownership.
- [x] Review current official provider documentation where contracts may drift.
- [x] Inspect the persistent target read-only without migration or mutation.
- [x] Classify every requested source and identify exact blockers.
- [x] Define the minimum design, implementation, and live-proof sequence.
- [x] Run source-bypass scans and static diff verification.

## Scope and Method

This was a static, read-only audit from commit
`a424ea51fa5422bee1e8d4e7e6905ab37561fd94`. It reviewed the active Printer V1
source stack, V2-9.7C operational design, 7A abstract command surface, current
source rules, adopted provider contracts, discovery/selection/cooldown code,
campaign persistence, final reporting, and directly relevant tests.

Current official documentation was used only to assess contract drift,
authentication, free limits, and provider authority. No source endpoint was
called. `data/printer_v1.sqlite3` was opened with SQLite URI `mode=ro` and
`PRAGMA query_only=ON`; no migration or write was performed.

## Executive Decision

The recommended final architecture is direct Pump.fun on-chain creation
discovery as the primary creation authority, with independently governed
third-party feeds as secondary candidate discovery or corroboration. That
architecture is not implemented today.

DexScreener fresh profiles are the only requested third-party discovery lane
whose committed contract is ready to participate in a future combined run.
PumpSwap is ready only as migration/pool confirmation. GeckoTerminal,
PumpPortal, direct Pump.fun decoding, and Solana Tracker each have blocking
contract or implementation gaps. Pumpdev must remain fallback-only research
and outside automatic campaign execution.

The legacy discovery command can govern and combine request kinds within one
selected provider. It cannot plan or merge multiple providers in one campaign.
The 7A command accepts injected Source Governor and Central Scheduler owners,
but delegates the campaign body through `execute_campaign`; it does not bind
discovery to selection, tracking, or provider-contribution reporting.

## Source Readiness Matrix

| Source | Classification | Final role | Discovery authority | Automatic Source Governor use now |
|---|---|---|---|---|
| Direct Pump.fun on-chain creation events | `PARTIAL_WITH_BLOCKER` | Primary creation authority after a pinned decoder and continuity proof | Authoritative for successful Pump Program creation transactions | No request contract, decoder, cursor, reconnect, or backfill owner exists |
| PumpPortal launch/migration events | `PARTIAL_WITH_BLOCKER` | Secondary low-latency corroboration only | Provider observation, not canonical on-chain authority | Registered transport is based on a stale authentication contract and lacks continuity |
| Solana Tracker free trending/top channels | `NOT_READY` | Optional secondary REST candidate feed after adoption | Provider candidate observation only | No registry entry, adapter, normalizer, secret contract, or focused proof |
| DexScreener fresh profiles | `READY_FOR_COMBINED_RUN` | Secondary fresh-profile candidate feed | Profile/listing observation only | Yes through the committed legacy governed path; not yet bound by 7A |
| GeckoTerminal new/trending pools | `PARTIAL_WITH_BLOCKER` | Secondary pool candidate feed after contract proof | Provider pool observation only | Registered, but adopted rules keep current requests fixture-only |
| PumpSwap confirmation | `CONFIRMATION_ONLY` | Confirm migrated venue and exact pool | Authoritative only for the confirmed PumpSwap program/pool relationship | Governed confirmation primitives exist; it must never originate a token candidate |
| Pumpdev | `FALLBACK_ONLY` | Manual/offline contract research if primary documentation is insufficient | None | No; exclude it from automatic planning and selection |

No requested source is permitted to provide a ranking, risk score, confidence
score, or direct selection decision.

## Source Findings

### Direct Pump.fun On-Chain Creation

The official Pump public repository now publishes Pump and PumpSwap IDLs and
documents the Pump Program ID
`6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`. Its Pump Program documentation
defines the `create` instruction and permissionless, idempotent `migrate`
instruction. This supersedes the local contract's earlier uncertainty about an
official IDL, but it has not been adopted or pinned in Printer.

Required implementation before this can be primary:

- Pin an exact official repository commit, program ID, IDL hash, instruction
  discriminator, account order, and emitted event layout.
- Accept only successful, finalized Pump Program transactions on Solana
  mainnet and exact-link signature, slot, block time, mint, bonding-curve
  account, creator as an observed address, and instruction/event provenance.
- Keep creator address distinct from unsupported wallet control, insider,
  coordination, authenticity, intent, or participant-identity claims.
- Add a Source Governor request/operation family and Central Scheduler work
  type; no decoder may poll RPC or subscribe independently.
- Own a durable high-water mark and reconnect cursor. On reconnect, backfill
  missed signatures/slots with bounded `getSignaturesForAddress` and
  `getTransaction` work before accepting new live observations.
- Define finalized-slot lag, duplicate-signature handling, failed transaction
  rejection, fork/reorg treatment, RPC truncation, unavailable history, and a
  maximum backfill horizon. A continuity gap must remain explicit and block
  unsupported launch authority.
- Bound public-RPC consumption. Program-wide polling can be high volume and
  must not compete with token snapshots or exceed adopted source/scheduler
  ceilings.

WebSocket `logsSubscribe` may be the efficient live input, but Printer has no
adopted subscription contract for it. A polling-only fallback still requires
the same cursor, missed-slot, and historical-gap proof.

Official references:

- [Pump public documentation](https://github.com/pump-fun/pump-public-docs)
- [Pump Program instructions](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_PROGRAM_README.md)
- [Official IDLs](https://github.com/pump-fun/pump-public-docs/tree/main/idl)
- [Solana logsSubscribe](https://solana.com/docs/rpc/websocket/logssubscribe)

### PumpPortal

The committed contract is stale. Current PumpPortal documentation uses
`wss://pumpportal.fun/api/data?api-key=...`, while Printer's transport uses the
older anonymous `wss://pumpportal.fun/api/data`. Launch and migration events
are described as free, but current access documentation says the API key is
associated with a linked wallet funded with at least `0.02 SOL`.

That prerequisite conflicts with Printer V1's no-wallet, no-private-key, and
no-real-funds locks. It cannot be treated as an available free/public automatic
source merely because launch events have no per-event fee. No workaround,
funded account, signing path, or wallet placeholder may be added in this lane.

The current adapter is also a short bounded sample transport, not a continuity
owner. PumpPortal recommends one WebSocket connection and reconnect handling,
emits at `processed` commitment, and does not provide historical token data.
Printer therefore needs a single governed socket owner, heartbeat/reconnect
policy, event deduplication, explicit processed-to-finalized on-chain
confirmation, and an independent missed-slot/backfill source. PumpPortal can
never be the sole authority after a disconnect.

Official references:

- [PumpPortal real-time data API](https://pumpportal.fun/data-api/real-time/)
- [PumpPortal fees](https://pumpportal.fun/fees/)
- [PumpPortal FAQ](https://pumpportal.fun/faq/)

### Solana Tracker

Solana Tracker requires an `x-api-key`. Its free REST plan is potentially
usable as a secondary source, but published free quotas have changed and must
be captured from the exact activation-time terms. Its paid WebSocket/Data
Stream is not allowed. Printer has no Solana Tracker source registry entry,
request-kind allowlist, authentication-secret owner, response schema,
normalizer, provenance contract, fixtures, or tests.

Trending/top endpoints are provider-ranked views, not Pump.fun creation
authority. Token responses expose pool, market, launchpad/market, risk, score,
and ranking fields, but the provider's filtering vocabulary is not yet pinned
consistently enough to prove that every result is a Pump.fun token. A future
adapter must:

- use only the free REST tier;
- require exact Solana/mainnet and Pump.fun launchpad provenance rather than
  inferring origin from token popularity or pool venue;
- exact-link mint and every returned pool independently;
- discard provider score, risk score, rank, order, and promoted status before
  Printer gates or uniform selection;
- preserve the raw provider fields as non-authoritative provenance only;
- block records whose Pump.fun origin cannot be proven.

Official references:

- [Solana Tracker API quickstart](https://docs.solanatracker.io/quickstart)
- [Solana Tracker Data API plans](https://www.solanatracker.io/data-api)
- [Solana Tracker trending tokens](https://docs.solanatracker.io/data-api/tokens/trending)

### DexScreener

DexScreener is keyless and free for the adopted endpoints. The current
contract supports fresh token profiles, exact Solana filtering, and a bounded
profile-to-token batch enrichment path. Official limits are 60 requests per
minute for token profiles and 300 requests per minute for token/pair
enrichment, subject to the exact endpoint.

Fresh profiles are a provider-listed subset. They do not prove creation time,
Pump.fun origin, migration, authenticity, or complete launch coverage.
DexScreener should contribute candidates and market/pair observations only.
Its profile order, boosts, labels, and visibility must not become a ranking or
selection advantage. Its existing Source Governor path is reusable, but the
multi-provider campaign planner and 7A binding are missing.

Official reference:

- [DexScreener API reference](https://docs.dexscreener.com/api/reference)

### GeckoTerminal

GeckoTerminal offers keyless public API access with new-pool and trending-pool
endpoints, but its v2 API is beta, responses are cached, and public rate
capacity is low and variable. Current documentation describes approximately
10 calls per minute for the free public API. Higher stable capacity is a paid
CoinGecko product and cannot become a Printer dependency.

Printer's adopted evidence rules keep GeckoTerminal requests fixture-only
until schema, completeness, identity, and provider-specific proof is complete.
That policy is authoritative over the legacy command catalog that labels the
request kinds `READY`.

Trending order is produced from provider engagement, market activity, and
security/credibility inputs. All such order and score-like fields must be
discarded before canonical gates and uniform selection. New/trending pools may
contribute a mint/pool candidate only after exact network, token side, pair,
pool address, observed time, response provenance, and age semantics are
validated.

Official references:

- [GeckoTerminal API documentation](https://api.geckoterminal.com/docs/index.html)
- [CoinGecko keyless public API guidance](https://docs.coingecko.com/docs/keyless-public-api)
- [GeckoTerminal trending-pool methodology](https://www.geckoterminal.com/learn/trending-pools)

### PumpSwap Confirmation

The committed PumpSwap contract correctly treats PumpSwap as confirmation
only. It verifies the PumpSwap program
`pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`, resolves a pool from an exact
migration signature, and fails closed unless owner and base-mint evidence
identify one unique pool.

PumpSwap may confirm that a Pump.fun mint migrated and identify its new
PumpSwap pool. It may not discover a token independently, establish token age,
choose a candidate, or promote 5m/support evidence into authority.

Official reference:

- [PumpSwap Program documentation](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMPSWAP_PROGRAM_README.md)

### Pumpdev

Pumpdev currently advertises a no-key WebSocket for launch and migration
events. It is not adopted, registered, or proven in Printer, and its broader
product surface is execution/trading oriented. It has no authority over
on-chain facts, no committed continuity contract, and no place in automatic
campaign planning.

Pumpdev may be consulted manually as fallback-only research when official
documentation is incomplete. Any useful contract fact must then be verified
against official Solana/Pump transactions and adopted in a later lane. Its
transaction, signing, trading, and execution paths remain prohibited.

Reference:

- [Pumpdev data API](https://pumpdev.io/data-api/)

## Recommended Source Architecture

The future bounded campaign should use this authority order:

1. Direct finalized Pump Program creation transactions provide primary launch
   identity and creation authority.
2. DexScreener fresh profiles provide a secondary candidate channel.
3. GeckoTerminal new/trending pools and Solana Tracker free REST may become
   secondary candidate channels only after their blocking contract lanes pass.
4. PumpPortal may provide low-latency launch/migration corroboration only if
   its authentication can comply with all V1 locks and continuity is proven.
5. PumpSwap confirms an exact migrated pool; it never originates candidates.
6. Pumpdev remains outside the automatic run.

Each provider must be an independent Source Governor request family and
Central Scheduler work item with its own ceiling, timeout, response/failure
record, provenance, and cancellation. A provider may not own a background
loop, call a second provider, or bypass either central owner.

## Identity, Merge, and Deduplication

The combined planner must first normalize provider observations without
discarding their original payload/provenance:

- Chain identity is exactly Solana mainnet plus canonical base58 mint.
- A market identity is mint plus exact pair/pool address, venue/program, base
  and quote orientation, and lifecycle phase.
- The Pump bonding-curve account and a post-migration PumpSwap pool are
  different market identities even when the mint is the same.
- Exact duplicate provider observations may merge by canonical identity and
  immutable observation key, while retaining every provider request, response,
  observed time, and contribution.
- Same mint/new pair does not silently merge. It is accepted only as an exact
  migration or separately governed revival/distinct-market classification.
  Unsupported pair drift remains a visible gap and fails closed.
- A migration must exact-link the source creation identity, migration
  signature/transaction, old market identity, new PumpSwap pool, and lifecycle
  transition. Provider text labels alone are insufficient.
- Conflicting mint, pair, token side, network, creation time, or migration
  evidence must remain conflicting; no majority vote or useful-but-dirty
  overwrite is allowed.

The current deduplication code handles exact pair duplicates and limited
same-token/new-pair migration classification. Its own comments defer
cross-response revival/distinct evidence. That deferred ownership must be
resolved before a combined run.

## Candidate Gates and Uniform Selection

Provider ranking, trend position, risk score, popularity, boosts, and response
order must be removed before selection. They may be retained only as raw,
non-authoritative provenance.

A candidate must pass fixed, non-scoring gates:

- canonical Solana mainnet mint and exact pair/pool orientation;
- approved provider request kind and complete request/response provenance;
- source-specific mandatory identity and freshness evidence;
- active market and adopted categorical liquidity/activity minimums;
- supported token age or explicit unknown/gap treatment;
- no infrastructure token or invalid token/pair identity;
- exact duplicate and same-token/new-pair rules;
- persisted token and pair cooldown;
- lifecycle reconciliation and vacancy eligibility;
- PumpSwap confirmation where a migration is claimed.

After gates, candidates must be canonical-sorted and sampled uniformly without
replacement for the exact number of vacant slots. The random seed must be an
immutable campaign/configuration fact. The current selector generates a seed
when one is absent; operational binding must reject an absent seed instead so
replay and repeated evaluation remain deterministic. Provider quotas may be
reported diagnostically but must not reserve slots or influence selection.

Exactly two active token slots remain the campaign capacity. Replacement is
allowed only after B.3 reconciliation, zero active associated work, and
pair-specific cooldown. Same-pair recycling remains blocked.

## Source Failure Isolation

A provider timeout, malformed response, quota exhaustion, or disconnect must:

- create its own governed failure/provenance record;
- stop only that provider's owned work;
- leave observations from healthy providers immutable;
- never manufacture missing authority or silently convert a partial candidate
  into a valid one;
- appear in provider-contribution and final campaign reporting.

A healthy secondary feed may continue after another secondary feed fails.
However, a candidate that lacks its required primary creation identity,
migration confirmation, or mandatory source-specific evidence remains
ineligible. Shared database integrity, Source Governor, Central Scheduler,
lease, configuration, identity, or ceiling failure remains a campaign-level
first fault and invokes the committed safe-stop path.

## Provenance and Provider Contribution Reporting

Current final-report usage records source request/response/failure identities
and aggregate budgets, but it does not explain each provider's contribution to
discovery and selection. A later schema/representation review must prove the
smallest immutable report link for each provider:

- planned, attempted, completed, failed, timed-out, and cancelled operations;
- candidate observations received and rejected during normalization;
- exact duplicates and same-mint/new-pair classifications;
- candidates passing fixed gates;
- selected token-slot assignments;
- confirmation-only observations and the facts they confirmed;
- authoritative fields contributed by direct on-chain evidence;
- exact request, response, failure, scheduler-work, cutoff, and observed-time
  identities.

These are factual counts and links, not scores or provider performance ranks.
An unavailable provider must remain visible rather than disappearing from the
report.

## Current Wiring and Persistent Readiness

### 7A Binding

7A validates immutable configuration, explicit database/report identities,
two-slot capacity, finite ceilings, backup evidence, provenance, leases, and
locked capabilities. It requires injected Source Governor and Central
Scheduler owner ports and checks returned ownership evidence.

It does not define a discovery plan, multi-provider fan-out, canonical
observation merge, selection batch, tracking handoff, or provider contribution
object. Its `execute_campaign` callback is intentionally abstract. Therefore
7A does not currently bind:

`discovery -> normalization -> merge -> fixed gates -> uniform selection -> tracking`

Adding provider calls directly inside 7A would duplicate ownership and is not
an acceptable repair. A committed campaign execution owner must be inserted
behind the abstract handler in a later implementation lane.

### Read-Only Persistent-Target Inspection

The persistent target's latest migration ledger entry is
`024_discovery_source_channel.sql`. It contains discovery rows from
DexScreener and GeckoTerminal and governed source-request rows, but it has no
`selection_batches` or `campaigns` table. The current campaign ownership graph
and migrations 025 and 031-033 have not been applied to that target.

This is a hard operational blocker. The inspection does not authorize or
perform migration. Existing backup/restore preflight and a later explicit
persistent-migration gate remain prerequisites.

## Exact Blockers

1. No committed multi-provider campaign planner or 7A execution owner binds
   governed discovery to merge, selection, tracking, and terminal reporting.
2. Direct Pump.fun creation has no pinned official IDL, decoder, governed
   operation family, finality rule, cursor, reconnect, or missed-slot backfill.
3. PumpPortal's committed anonymous WebSocket contract is stale; current access
   introduces an API-key/funded-wallet prerequisite incompatible with V1 locks.
4. PumpPortal has no continuity owner or historical backfill and emits
   lower-commitment events that require independent finalized confirmation.
5. Solana Tracker is absent from the source registry and has no free-tier,
   authentication, schema, Pump.fun-origin, normalization, or score-discard
   contract.
6. GeckoTerminal's legacy `READY` catalog conflicts with the adopted
   fixture-only evidence contract and current beta/rate-limit constraints.
7. Cross-provider same-mint/new-pair merge ownership is incomplete beyond
   exact duplicate and limited migration handling.
8. The selector does not operationally require a persisted immutable seed.
9. Final campaign reporting lacks provider-contribution and merge/gate lineage.
10. The persistent target is at migration 024 and lacks selection and campaign
    ownership schemas required by the committed abstract command.
11. No bounded combined fixture or live proof establishes provider failure
    isolation, reconnect/backfill continuity, exact two-slot fairness, and
    source/scheduler ceilings together.

## Minimum Follow-On Sequence

The minimum safe sequence is:

1. **7B.2 combined discovery design:** freeze authority order, provider
   operation types, canonical identities, event-time/finality rules, merge and
   conflict semantics, fixed gates, immutable seed, contribution reporting,
   ceilings, and stop conditions. Pin official contracts and versions.
2. **Provider contract adoption:** separately adopt direct Pump Program
   decoding/continuity; resolve or reject PumpPortal authentication; adopt
   Solana Tracker free REST if still compliant; repair GeckoTerminal's
   fixture-only blocker. Keep PumpSwap confirmation-only and Pumpdev excluded.
3. **Narrow implementation lanes:** implement the direct on-chain adapter and
   continuity owner; implement only approved secondary adapters; then add one
   combined planner/normalizer/merge owner behind 7A. Do not put source logic
   in the command handler.
4. **Persistence/report reconciliation:** add only proven missing immutable
   discovery-batch, selection, provider-contribution, and campaign links while
   preserving Source Governor, Central Scheduler, B.1-B.5, and campaign-root
   ownership.
5. **Disposable fixture proof:** prove multi-provider normalization, exact
   migration linkage, duplicate/conflict handling, uniform two-slot selection,
   cooldown/rotation, provider failure isolation, safe stop, deterministic
   report, zero-source replay, and zero locked-capability deltas.
6. **Persistent migration readiness:** run the already committed
   backup/restore preflight and an explicit later migration gate. Do not
   migrate during design or fixture proof.
7. **Bounded live source proof:** only after operator approval, use governed
   low ceilings and separate provider slices to prove authentication,
   rate-limit behavior, reconnect/backfill, finality, real response schemas,
   and contribution reporting. Stop on the first material contract failure.
8. **Pilot review:** assess the evidence before publishing an operational
   command or starting a two-token campaign. A successful audit or fixture is
   not pilot authorization.

## Focused Proof Needed by Follow-On Lane

- Direct Pump decoder fixtures for valid create, failed transaction, wrong
  program, malformed accounts, duplicate signature, fork/finality, reconnect,
  missed-slot backfill, truncated history, and deterministic replay.
- PumpPortal contract tests for current authentication, one-socket ownership,
  processed-to-finalized confirmation, reconnect, duplicate events, and
  irrecoverable gaps. If wallet funding remains required, the provider stays
  blocked without implementation.
- Solana Tracker tests for API-key isolation, free REST ceilings, Pump.fun
  origin proof, pagination/cache, schema drift, score/rank stripping, and
  fail-closed pool identity.
- GeckoTerminal tests for current headers/schema, cache/freshness, token side,
  exact pool identity, trending-order stripping, and partial/malformed pages.
- Combined planner tests for canonical merge, all same-mint/new-pair cases,
  migration, provider conflicts, independent failures, fixed gates, immutable
  seed, uniform selection, two-slot capacity, cooldown, and tracking handoff.
- Report/replay tests for exact provider contribution, unchanged unknowns and
  gaps, deterministic canonical bytes, and zero source/scheduler/database work
  during replay.
- Source-bypass tests proving every network operation is Source-Governed and
  Scheduler-led and that no adapter creates an independent loop.

## Money-Usefulness Contribution

This audit defines how Printer can broaden candidate coverage without
confusing provider visibility with authoritative creation evidence or turning
provider rankings into trade signals. Direct on-chain identity, explicit
provider gaps, deterministic uniform selection, exact migration handling, and
failure isolation would reduce missed eligible launches and contaminated
memory while preserving realistic source budgets and auditable provenance.

It does not claim that broader discovery improves profit. Its contribution is
cleaner, more representative campaign intake for later memory evaluation.

## What Remains Locked

Operational source fetching, source subscriptions, campaign execution,
persistent-target migration, memory generation, retrieval, paper decisions,
BUY/SELL/HOLD, WAIT/AVOID/NO_ACTION activation, positions, trades, audits, PnL,
wallets, private keys, signing, real funds, paid APIs, scoring, ranking,
confidence, weighted logic, live execution, the exact PowerShell command, and
the two-token pilot remain locked.

No provider may bypass Source Governor or Central Scheduler. The 5m window
remains support-only. This audit does not authorize V2-9.7D closeout.

## Functionality Risks / Setbacks / Efficiency Blockers

- Provider authentication, free quotas, schemas, and access terms can change.
  Exact activation-time contracts must be pinned and rechecked.
- Public RPC program-wide discovery may consume substantial request and
  scheduler capacity; continuity proof must include realistic bounded load.
- WebSocket delivery without historical backfill creates invisible launch
  gaps. PumpPortal cannot close those gaps by itself.
- Provider "new" and "trending" feeds are curated/cached subsets and can bias
  the candidate population even after numerical ranks are discarded.
- Cross-provider timestamps describe different events: creation, profile
  publication, pool creation, provider observation, and migration must not be
  collapsed into one token-age value.
- Same-mint/new-pair behavior can represent migration, legitimate distinct
  markets, revival, drift, or malicious duplication. Unsupported
  classification must remain blocked.
- The persistent target's schema lag prevents safe operational binding even if
  source contracts are repaired.
- Free-tier capacity may be too small for a reliable combined run. Printer must
  reduce cadence or omit a provider rather than add a paid dependency.

## Stop Boundary

V2-9.7D.7B.1 ends with this audit. No design, implementation, live source call,
V2-9.7D closeout, pilot, operational command, or persistent migration begins.
