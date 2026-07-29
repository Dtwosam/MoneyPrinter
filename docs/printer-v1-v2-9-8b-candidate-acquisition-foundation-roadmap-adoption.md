# Printer V1 V2-9.8B Candidate-Acquisition Foundation Roadmap Adoption

> **Superseding clarification — 2026-07-29:** Candidate discovery is
> multi-source. Pump/PumpSwap remains a required, first-class lane and the only
> authority for Pump-specific origin/migration/canonical-pool claims, but it is
> not the exclusive candidate universe. DexScreener and GeckoTerminal may
> directly nominate candidates and contribute their supported market facts.
> Birdeye may be used only through an adopted no-cost programmatic contract.
> Non-Pump and honest unknown-origin candidates are not forced to possess Pump
> lineage when exact Solana mint/token-program/current-pool, supported pool
> owner/program, quote, market, age where required, safety, holder, liquidity,
> tradeability, and freshness gates pass. No source quota, preference, score,
> rank, confidence or weighting is introduced. This clarification is normative
> for later work; the historical facts and verdict below remain preserved.

Date: 2026-07-28

Starting HEAD: `7416bc762744a56907d59f30d842d5fced0c9260`

Mode: documentation-only roadmap adoption and official primary-source research

## Verdict

`V2_9_8B_CANDIDATE_ACQUISITION_FOUNDATION_ROADMAP_ADOPTION_PASS`

Pump.fun and PumpSwap are adopted as first-class required components of
Printer's factory-wide candidate-acquisition foundation. Direct Pump activity
is the authority for exact launch origin. Direct Pump migration plus exact
PumpSwap state is the authority for graduation and canonical pool identity.
DexScreener and GeckoTerminal remain market-visibility and enrichment sources;
they cannot establish or replace either on-chain fact.

This PASS changes roadmap and design authority only. It does not authorize
implementation, schema migration, source execution, live observation,
historical backfill, discovery, Scheduler or campaign runtime, memory runtime,
capacity above two, another selective-1h proof, wallets, paid APIs, or any
retrieval or financial capability.

## 1. Authority and adoption basis

This adoption implements the exact next permitted lane from
`docs/printer-v1-v2-9-8b-candidate-acquisition-capacity-feasibility-audit.md`.
That audit remains the capacity/economics/design evidence. This document makes
the operator's Pump/PumpSwap authority decision active in the roadmap.

Official primary authority refreshed on 2026-07-28:

- [Pump public documentation repository](https://github.com/pump-fun/pump-public-docs)
  `main` resolved to commit
  `9c82f61cb711b044a17f770ab8ce9f9bdf78f333` at inspection time.
- [Pump program documentation](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_PROGRAM_README.md)
  identifies program `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`,
  creation on its bonding curve, and permissionless, idempotent `migrate` for a
  completed curve.
- [Official Pump IDL](https://github.com/pump-fun/pump-public-docs/blob/main/idl/pump.json)
  is the instruction/account/event-layout authority that must be pinned before
  implementation.
- [PumpSwap documentation](https://github.com/pump-fun/pump-public-docs/blob/main/docs/PUMP_SWAP_README.md)
  identifies program `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`, the
  `Pool` PDA seeds, canonical migration pool index zero, and appended Pool
  fields.
- [Official PumpSwap IDL](https://github.com/pump-fun/pump-public-docs/blob/main/idl/pump_amm.json)
  is the PumpSwap instruction/account/event-layout authority that must be
  pinned before implementation.

The refresh confirms the program identities and the protocol-level authority
hierarchy. It is not the required implementation pin. The next contract lane
must independently download exact raw bytes, record the repository commit and
SHA-256 for both IDLs and every adopted documentation artifact, and produce
fixture-proven supported layouts. A moving `main` URL is never an implementation
contract.

## 2. Adopted source-authority hierarchy

The candidate foundation must apply this order without inversion:

1. **Direct Pump on-chain activity** establishes exact launch origin.
2. **Direct Pump migration and PumpSwap evidence** jointly establish exact
   graduation and canonical pool identity.
3. **DexScreener and GeckoTerminal** provide current visibility, liquidity,
   activity, age, and cross-source coverage enrichment only.
4. **Approved Solana RPC providers** transport and verify exact finalized
   on-chain evidence under Source Governor and Central Scheduler ownership.
5. **PumpPortal** may become an optional governed locator only after its current
   authentication, wallet, free-versus-metered, and cost contract is resolved.

Consequences:

- Aggregator pair age is not Pump launch time.
- An aggregator venue or graduation label is not Pump migration evidence.
- An aggregator pool address is not canonical PumpSwap identity until the exact
  on-chain contract proves it.
- PumpPortal cannot be the primary or sole creation/migration authority.
- RPC providers are transports, not competing semantic authorities.
- Cross-source agreement may enrich a certificate but cannot cure a missing
  direct origin or direct graduation fact.

## 3. Factory-wide ownership map

```text
Central Scheduler candidate-observation work
  -> Source Governor request admission and durable accounting
     -> one direct Pump/PumpSwap observation owner
        -> bounded finalized live tail
        -> bounded cursor-based historical backfill
        -> exact supported transaction/instruction decode
        -> exact program-owned account verification
        -> durable origin / graduation / canonical-pool facts
     -> DexScreener + GeckoTerminal enrichment owner
     -> approved Solana RPC verification transports
     -> optional PumpPortal locator (contract unresolved; currently unavailable)
  -> categorical evidence funnel
  -> immutable candidate certificate
  -> capacity-neutral reserve and deterministic N-manifest boundary
  -> explicit legacy two-slot runtime adapter
  -> existing two-token Memory Factory runtime
```

There must be one observation owner, not a WebSocket engine plus an independent
backfill engine. Live tail and historical backfill are two bounded modes of the
same Source-Governed, Scheduler-led owner and use the same decoder, evidence
contract, cursor rules, budgets, deduplication identity, and failure taxonomy.

## 4. Required direct Pump launch-origin contract

A launch-origin fact may exist only when Printer verifies all adopted fields
from one supported successful finalized Pump creation transaction:

- exact Pump program identity;
- supported creation instruction discriminator and exact account/argument
  layout from the pinned Pump IDL;
- exact mint and bonding-curve relationship;
- transaction signature, slot, finality, and success;
- exact event/instruction consistency where the pinned contract requires it;
- durable contract version and evidence provenance; and
- continuity status for the observed range.

The current repository has a finalized, cursor-based creation path and a
historical `create` pin. That is reusable evidence, not blanket authorization.
Current official surfaces include newer creation variants and quote-mint
evolution. Every adopted creation variant must be named and fixture-proven;
unadopted variants are `UNSUPPORTED_PUMP_LAYOUT` and do not establish origin.

## 5. Required direct Pump migration and PumpSwap contract

Graduation must require a joined exact fact, not merely program presence:

- one supported successful finalized Pump `migrate` instruction for the exact
  mint;
- exact adopted migration discriminator and account ordering;
- exact migration signature, slot, finality, and success;
- the exact PumpSwap Pool account created or referenced by that migration;
- PumpSwap program ownership and the pinned Anchor account discriminator;
- supported Pool layout and length/version rule;
- exact base mint, approved quote mint, creator, and PDA derivation;
- canonical Pump migration pool index `0`;
- exact token vault / mint relationships required by the pinned contract; and
- one unambiguous canonical pool identity.

Current production discovery begins migration acquisition with PumpPortal's
`subscribeMigration` locator and then performs on-chain verification. That is
not sufficient under this adoption. The repository has no equivalent
authoritative, restart-safe direct-migration observation cursor whose exact
instruction/account contract is pinned. This is a confirmed design gap and
blocks migration-observer implementation until resolved.

PumpSwap account presence by itself does not prove that a Pump migration made
the pool. Conversely, a Pump migration decode without exact canonical PumpSwap
state does not complete graduation evidence. Both sides are required.

## 6. Bounded live observation

The future design must define a finite `LIVE_TAIL` observation window:

- immutable start/end time and start/end finalized slot boundaries;
- explicit program/index address and pinned contract version;
- fixed page, signature, transaction-decode, account-read, byte, duration, and
  governed-request ceilings;
- finalized HTTP transaction/account verification for every accepted fact;
- deterministic signature/slot ordering and duplicate identity;
- no wallet, signing, transaction submission, trade subscription, or paid API;
- no independent adapter loop, unbounded reconnect, automatic retry storm, or
  endpoint rotation; and
- explicit gap recording when the window cannot be proven contiguous.

A WebSocket may later be designed as a lossy locator inside the bounded owner,
but it cannot establish finality and cannot be required for correctness. Its
events must be reverified through approved finalized RPC methods. Disconnect,
lag, truncation, unsupported message, or budget exhaustion creates a visible
gap; it never creates evidence of absence.

## 7. Restart-safe cursor-based historical backfill

The same owner must define a finite `BACKFILL` mode for missed Pump creation and
migration activity:

- cursor namespace includes network, program, observation channel/index,
  contract pin, and decoder version;
- durable high-water and low-water boundaries contain at least finalized slot
  and signature, with deterministic same-slot ordering;
- RPC pagination uses explicit `before` / `until` boundaries or an equally
  exact pinned provider-independent contract;
- every invocation has frozen oldest/newest boundaries and fixed request,
  decode, byte, row, page, and duration ceilings;
- restart resumes from the last atomically committed contiguous boundary;
- accepted facts, rejected/unsupported observations, range status, and cursor
  advancement commit atomically;
- a cursor never jumps past an unavailable, malformed, conflicting,
  unsupported, or unverified transaction;
- live-tail gaps become durable backfill work; backfill closes only the exact
  proven range; and
- pruning or unavailable history is `GAPPED` or `UNKNOWN`, never "no events."

Required range states are categorical: `CONTIGUOUS`, `GAPPED`, `UNKNOWN`, and
`BLOCKED_CONTRACT`. A later design may add more fail-closed categories but may
not collapse them into a score, rank, confidence percentage, or weighted value.

Creation backfill may reuse the already adopted create-exclusive index only
after the dual-contract refresh revalidates it. Migration backfill needs an
officially supported, exact address/instruction/account indexing strategy. No
program-wide heuristic or guessed account offset may fill that gap.

## 8. Fail-closed layout policy

Unknown or unsupported Pump/PumpSwap instructions, events, accounts, versions,
quote mints, extensions, ownership, or PDA relationships must fail closed.

| Observation | Required outcome |
| --- | --- |
| Unknown instruction discriminator | `BLOCKED_CONTRACT`; no fact; cursor does not cross it |
| Known name but different account order/layout | `BLOCKED_CONTRACT`; no heuristic recovery |
| Unknown Anchor account discriminator | reject account and candidate fact |
| Account shorter than pinned layout | reject as malformed |
| Account longer than pinned layout | reject unless the pin explicitly adopts append-only compatibility and exact prefix semantics |
| Unsupported quote mint | no canonical graduation fact |
| Pool owner, PDA, mint, index, or vault mismatch | no canonical graduation fact |
| Multiple plausible pools or migrations | ambiguous; no certificate |
| Failed, non-finalized, null, pruned, or unsupported transaction version | no fact; preserve gap reason |
| Aggregator-only origin/graduation | enrichment only; admission fails |

Byte offsets may be implementation details derived from a pinned IDL fixture;
they are not authority by themselves. The current Pool base-mint offset check
must not be generalized into support for future layouts without exact account
discriminator, prefix, length/extension, canonical-index, and quote-mint checks.

## 9. Candidate certificate and reserve effects

The capacity-neutral candidate certificate adopted by the feasibility audit is
extended with mandatory Pump authority fields:

- exact Pump origin evidence identity and pinned contract version;
- exact Pump migration evidence identity and pinned contract version;
- exact canonical PumpSwap pool evidence and pinned contract version;
- live/backfill observation window and continuity state;
- source trace for every direct RPC operation and optional locator;
- categorical aggregator enrichment with observed-at/freshness;
- categorical admission/rejection facts and reason codes; and
- immutable certificate hash and provenance.

No certificate can be `ADMISSIBLE` without exact Pump origin and exact joined
Pump-migration/PumpSwap graduation evidence. Aggregator coverage is useful but
not substitutable. PumpPortal contribution, if later adopted, is recorded as
`LOCATOR_ONLY` and cannot satisfy a mandatory fact.

The capacity-neutral reserve and deterministic `N`-manifest remain separated
from the current runtime. Active Memory Factory handoff stays capped at two.
The legacy runtime adapter may consume exactly two certified items only after a
future implementation/proof lane; this adoption does not change it.

## 10. Source budgets and priority

Direct Pump/PumpSwap observation is candidate-acquisition work below active
token snapshots and memory-window close work in the existing resource priority
order. It must yield when higher-priority Scheduler work requires budget.

The future design must budget separately for:

- live-tail signature/log observation;
- backfill signature pagination;
- transaction decoding;
- Pump/PumpSwap account verification;
- DexScreener enrichment;
- GeckoTerminal enrichment;
- admission/safety work; and
- durable storage/bytes.

Each source must expose governed-request count, underlying RPC operation count,
duration, bytes, accepted facts, rejected facts, duplicates, gaps, and marginal
unique-candidate yield. No hidden retry, fallback, or multi-operation request is
free in accounting.

## 11. PumpPortal disposition

PumpPortal is not a required component of the adopted foundation. It is
currently unavailable to the authority path because its present authentication,
API-key, wallet linkage, funding, free-versus-metered, and cost terms are not
sufficiently resolved for Printer's locked rules.

A later official contract lane may permit free `subscribeNewToken` and
`subscribeMigration` messages as bounded locators if and only if it proves:

- no wallet connection or funded wallet is required;
- no paid or metered API dependency is created;
- one governed connection and exact ceilings are defined;
- no trade/account stream is used;
- every observation is independently verified on-chain; and
- absence or failure never weakens the direct Pump/PumpSwap requirements.

Until then, the existing PumpPortal-led migration acquisition path may remain
historical/current code, but it cannot be the foundation's authoritative design.

## 12. Roadmap adoption and dependency order

This adoption inserts the following candidate-acquisition sequence inside
V2-9.8B without activating the operational campaign:

1. **Candidate-Acquisition Foundation Roadmap Adoption** — this PASS.
2. **Direct Pump/PumpSwap Contract Refresh and Pin Readiness Audit** — exact
   current official commit/file hashes, instruction/event/account contracts,
   canonical-pool rules, supported variants, indexing strategy, and fixture
   requirements; read-only.
3. **Source-Contract Reconciliation Audit** — DexScreener, GeckoTerminal,
   approved RPC providers, GoPlus, and optional PumpPortal; read-only.
4. **Capacity-Neutral Foundation Design** — live/backfill owner, cursor and gap
   contract, evidence funnel, certificate, reserve, budgets, schemas, reports,
   and legacy two-slot adapter; documentation-only.
5. **Schema/Migration Design** — forward/rollback plan only; no migration.
6. **Implementation Readiness Review** — prove prerequisites and lock scope.
7. Later implementation, offline fixtures, bounded isolated proof, and closeout
   only after separate explicit authorizations.
8. Another selective-1h proof only after the entire adopted foundation path is
   implemented, bounded-proof PASS, operationally adopted, and separately
   authorized.

The exact next permitted lane is **V2-9.8B Direct Pump/PumpSwap Contract Refresh
and Pin Readiness Audit**, read-only. It must not fetch through Printer, invoke
live Solana RPC, mutate any DB, or implement a decoder. Official documentation
and raw official repository artifacts are permitted research inputs.

## 13. Money-usefulness contribution

This adoption improves future memory usefulness by preventing two common forms
of false history: treating aggregator first-seen age as launch origin and
treating a visible pool as proved Pump graduation. Exact origin, migration, and
canonical pool lineage make age, liquidity evolution, continuation, traps,
graduation outcomes, and exit-realism memories more defensible. Cursor backfill
also makes restarts less likely to bias the corpus toward only events observed
while Printer happened to be online.

This is evidence quality, not alpha. It does not predict winners, score or rank
candidates, create confidence, authorize a paper decision, or imply profit.

## 14. What remains locked

- Production source adapters, decoders, transports, subscriptions, and cursors.
- Any Printer source fetch, live observation, or historical backfill.
- Source Governor, Scheduler, campaign, lifecycle, or memory runtime changes.
- Schemas, migrations, authoritative DB writes, proofs, retries, and restarts.
- Runtime capacity above two and generic `N` runtime activation.
- Another selective-1h proof and all 4h+/12h/24h production work.
- Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL.
- Wallets, private keys, signing, real funds, execution, and paid APIs.
- Scoring, ranking, confidence percentages, weighted logic, embeddings, and
  vectors.

## 15. Functionality Risks / Setbacks / Efficiency Blockers

| Classification | Risk / setback / blocker | Required treatment |
| --- | --- | --- |
| current confirmed blocker | Migration acquisition is PumpPortal-led and lacks an authoritative direct on-chain migration cursor. | Contract audit must establish exact migration indexing and cursor feasibility before design or implementation. |
| source-contract gap | Pump and PumpSwap layouts evolve; current Pump pin and Pool offset alone are insufficient foundation authority. | Pin both official IDLs, docs, program IDs, discriminators, accounts, events, PDA rules, hashes, and fixtures. |
| expected fail-closed policy | Unsupported creation/migration variants can reduce yield. | Preserve gaps and categorical rejection; never guess or fall back to an aggregator. |
| efficiency blocker | Direct program histories can be high-volume and RPC history can be pruned. | Use exact index addresses where officially supported, finite pages/decode ceilings, cursor ranges, and honest gaps. |
| external source risk | Public/free RPC retention, limits, latency, and availability are not guaranteed. | Keep provider-independent cursor semantics, governed budgets, no claimed absence from unavailable history, and no paid dependency. |
| scalability blocker | Backfill demand can compete with active snapshot and closeout work. | Scheduler priority, explicit per-mode budget, resumable slices, and mandatory yield to higher-priority work. |
| source-contract gap | PumpPortal's free/auth/wallet/cost boundary remains ambiguous. | Keep it unavailable and optional until a separate official contract adoption passes. |
| future runtime-capacity concern | A generic certificate/reserve could be mistaken for permission to activate `N > 2`. | Preserve a separate two-item legacy adapter and explicit operational cap of two. |
| safe generic foundation | One direct observation owner with live/backfill modes can provide restart-safe exact facts without a wallet or engine bypass. | Keep all access Source-Governed, Scheduler-led, bounded, and immutable. |
| inconclusive | The exact best direct migration indexing address/strategy has not yet been adopted. | Resolve only from pinned official contracts and fixture analysis in the next read-only lane. |

## 16. Adoption checks

Closeout checks for this documentation lane:

- active-roadmap authority hierarchy and next-lane consistency: PASS;
- historical audit/design/closeout documents unchanged: PASS;
- code, test, fixture, migration, schema, and DB scope: zero changes;
- Printer source and runtime invocation count: zero;
- accidental-unlock scan: PASS; all matches are explicit prohibitions;
- stale PumpPortal-primary / V2-9.7A active-pointer scan: PASS;
- `git diff --check` and changed-document trailing-whitespace scan: PASS; and
- authoritative DB SHA-256 before and after:
  `4aecba119fb9b02436999a9813bc14364c0fa188b6c2957768e146346a32f872`
  / identical: PASS.

## 17. Files and change boundary

Files changed:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`
- `docs/printer-v1-v2-9-8b-candidate-acquisition-foundation-roadmap-adoption.md`

What was built: documentation-only adoption of direct Pump/PumpSwap authority,
bounded live plus cursor-backfill design requirements, fail-closed contract
policy, and the dependency-ordered next lane.

What was not touched: production code, tests, fixtures, schemas, migrations,
databases, source adapters, Source Governor, Central Scheduler, campaigns,
runtime, memory, retrieval, paper/financial surfaces, wallets, and paid APIs.
