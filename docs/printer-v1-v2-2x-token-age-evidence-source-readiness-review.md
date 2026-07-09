# Printer V1 V2-2X Token-Age Evidence Source Readiness Review

Status: AUDIT/READINESS ONLY

Readiness verdict: READINESS_COMPLETE_WITH_BLOCKERS

V2-2X reviewed whether Printer V1 is ready to implement real token-age
evidence after the V2-2 discovery/selection closeout, V2-2O token-age design,
and V2-2P pair-age metadata verification. This review did not implement source
adapters, run live source calls, mutate any database, create memory, activate
retrieval, create paper decisions, or unlock any financial path.

## Source Stack Read

The review used the active source stack together, not as isolated documents:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-v2-2j-discovery-selection-foundation-closeout.md`
- `docs/printer-v1-v2-2o-token-age-evidence-repair-design.md`
- `docs/printer-v1-v2-2p-3-pair-market-age-metadata-verification.md`
- `docs/printer-v1-v2-2k-discovery-selection-practical-coverage-diagnostic-audit.md`

Current anchors reviewed:

- V2-2J closeout: `c6f002a`
- V2-2O token-age design: existing design document
- V2-2P.3 pair-age metadata verification: `be70309`

## Files Inspected

Static inspection covered:

- `src/printer_v1/discovery/parser.py`
- `src/printer_v1/discovery/selection_batch.py`
- `src/printer_v1/sources/registry.py`
- `src/printer_v1/sources/geckoterminal.py`
- `src/printer_v1/sources/dexscreener.py`
- `src/printer_v1/sources/pumpportal.py`
- `src/printer_v1/sources/pumpswap.py`
- `src/printer_v1/sources/solana_rpc_holder.py`
- `src/printer_v1/evidence_fill/real.py`
- `src/printer_v1/operator_cli/commands.py`
- `tests/test_v2_2p_pair_age_context.py`
- `tests/test_v2_2h3_field_normalization_fast_events.py`
- related V2-2H, V2-2P, V2-2V, source, and controlled discovery references found by static search

No read-only database inspection was needed for this readiness review because
the blocker being classified is source/path readiness, not current row state.
The V2-2K and V2-2J docs already contain the relevant live-audit evidence:
`token_created_at` and `token_age_seconds` remained missing for 70/70
normalized candidates.

## Current Parser State

`src/printer_v1/discovery/parser.py` already has normalized fields for:

- `pair_created_at`
- `token_created_at`
- `pair_age_seconds`
- `token_age_seconds`
- `pair_age_context_label`
- `token_age_evidence_tier`

Current extraction behavior:

- `pair_created_at` is read from `pair_created_at`, `pairCreatedAt`,
  `pool_created_at`, or `poolCreatedAt`.
- `token_created_at` is read only from `token_created_at` or
  `tokenCreatedAt`.
- `pair_age_seconds` is derived only from the pair-created timestamp.
- `token_age_seconds` is derived only from the token-created timestamp.
- `token_age_evidence_tier` is always `None` until a real T1/T2/T3
  source path is implemented.
- `pair_age_context_label` is diagnostic context only.

The parser is structurally ready to receive token-age evidence, but no current
READY source supplies `token_created_at` in the live discovery path.

## Current Pair-Age State

V2-2P and V2-2P.3 verified the pair-age boundary:

- Pair age is available for most current GeckoTerminal/DexScreener candidates.
- Pair age is carried as `pair_age_seconds` and `pair_age_context_label`.
- Pair age is persisted in selection-batch metadata.
- Pair age is not copied into `token_age_seconds`.
- Pair age does not drive `derive_age_bucket()`.
- Pair age does not unlock A3.
- Pair age does not unlock recent-active tiers.

This is correct and must remain unchanged. Pair age is T4 evidence only.

## Source Capability Matrix

| Source/path | Current status | Token-age tier potential | Can provide token age now? | Readiness finding |
| --- | --- | --- | --- | --- |
| GeckoTerminal new-pool discovery | READY governed discovery path | T4 pair-age context only | NO | Provides pool/pair age from `pool_created_at`, not token creation age. Not suitable as first token-age source. |
| GeckoTerminal trending-pool reference | READY governed reference path | T4 pair-age context only | NO | Useful for market/pair context, but does not resolve token age. |
| DexScreener token discovery/search | READY governed discovery path | T4 pair-age context only | NO | Provides `pairCreatedAt`, price, liquidity, volume, txns, fdv, and market cap fields, but not token creation age. |
| PumpPortal launch stream | Source registry entry and fixture-style source shell exist; live path remains NOT_READY | T2 source-observed launch timing | NOT YET | Best first source design candidate because launch-event timing can be mapped to token age if governed, bounded, source-traced, and operator-approved. |
| PumpPortal migration stream | Source registry entry and fixture-style source shell exist; live path remains NOT_READY | T2/T4 context depending on event semantics | NOT YET | Useful for migration context, but must not overwrite token launch age unless the event is proven to represent initial token launch. |
| PumpSwap pool confirmation/migration reference | Source registry entry and fixture-style confirmation shell exist; live path remains NOT_READY | T4/migration context | NO | Useful as read-only pool confirmation, not a primary token-age source. |
| Solana public RPC | Registered as a source reference; holder concentration fallback exists | T3 mint-derived enrichment | NOT YET | Current code supports holder concentration, not token mint creation age. A new governed enrichment design is required. |
| Helius free tier | Registered as optional free-tier source | T3 mint-derived enrichment | NOT YET | Possible later fallback, but must remain optional/free and cannot become a paid dependency. |
| Jupiter quote | Registered as paper quote realism only | None | NO | Paper realism only. Not a discovery or token-age source. |

## T1/T2/T3 Feasibility Matrix

| Tier | Meaning | Current readiness | Main blocker | V2-2X finding |
| --- | --- | --- | --- | --- |
| T1 | Confirmed token age from a source response | NOT_READY | No current READY discovery source provides a canonical `token_created_at` field | Feasible only if a future source response carries a trustworthy token creation timestamp. |
| T2 | Source-observed launch timing, such as PumpPortal launch event | DESIGN_READY, IMPLEMENTATION_NOT_READY | PumpPortal is registered but not live-active; event timestamp semantics and bounded collection need design | Best first implementation path after a narrow design update. |
| T3 | Solana RPC / Helius mint-derived age enrichment | DESIGN_NEEDED | Current Solana RPC path is holder/safety reference, not mint creation age enrichment | Feasible as a later enrichment path, but larger and more rate-limit sensitive than T2. |
| T4 | Pair-age-only context | IMPLEMENTED | Must remain diagnostic only | Already implemented by V2-2P. Must not drive age gates. |
| T5 | Unknown | CURRENT DEFAULT | No token-age evidence source active | Correct default until T1/T2/T3 exists. |

## Recommended First Source Path

Recommended first implementation path after design update:

`T2 - governed PumpPortal launch-event token-age evidence`

Reasoning:

- It is aligned with the Solana memecoin launch universe.
- It is already present in the Source Registry as `pumpportal` with
  `pumpfun_launch_stream` and `pumpfun_migration_stream` request kinds.
- It can be kept free/public and operator-approved.
- It can be implemented as bounded source-governed evidence, not an
  unbounded runtime stream.
- It can be proven deterministically with fixture launch events before any
  bounded live public source proof.
- It provides a direct source-observed launch time that can populate
  `token_created_at`, `token_age_seconds`, and `token_age_evidence_tier = T2`
  without abusing pair age.

T3 Solana RPC / Helius mint-derived enrichment should be the secondary path,
not the first path, unless the operator explicitly prefers on-chain enrichment.
It is useful because it can enrich any token, but it requires a new governed
request contract, source-budget controls, rate-limit handling, timestamp
provenance rules, and proof that it does not become a paid dependency.

## Does V2-2O Need a V2-2X.1 Design Update?

Yes.

V2-2O is sufficient as the high-level token-age evidence taxonomy and the
pair-age safety design. It is not specific enough to begin implementation of a
real token-age source path.

A V2-2X.1 design update is required before implementation to define:

- the first source path, recommended as governed PumpPortal launch timing;
- allowed request kind and source registry usage;
- event timestamp semantics;
- whether `captured_at`, event time, block time, or source-provided launch time
  is allowed to become `token_created_at`;
- source trace requirements;
- freshness and stale-event rules;
- how migration events differ from launch events;
- bounded operator approval and Source Governor boundaries;
- Central Scheduler compatibility without starting runtime;
- proof DB and fixture proof requirements;
- no-pair-age-fallback invariants;
- no retrieval, paper decision, BUY, position, trade, audit, or PnL unlocks.

Implementation should not proceed directly from V2-2X.

## Required Proof/Test Plan

Before token-age evidence can be accepted, the next implementation/proof path
must add focused tests proving:

1. A valid T2 PumpPortal launch fixture maps to `token_created_at`,
   `token_age_seconds`, and `token_age_evidence_tier = T2`.
2. A PumpPortal migration fixture does not overwrite token launch age unless
   the design explicitly classifies it as a token launch event.
3. Missing, stale, failed, mismatched, or dirty launch evidence leaves
   `token_age_seconds` unknown.
4. Pair age is never assigned to `token_age_seconds`.
5. Pair age alone never unlocks A3.
6. Pair age alone never unlocks recent-active tiers.
7. `derive_age_bucket()` continues to read only `token_age_seconds`.
8. A3 can fire only when real token-age evidence exists and its other field
   requirements are met.
9. Selection metadata preserves `token_age_evidence_tier` and
   `pair_age_context_label`.
10. Source requests, responses, and failures remain source-governed and
    audit-visible.
11. Bounded proof DB row deltas show no memory windows, retrieval rows, paper
    decisions, positions, trade events, paper audits, or PnL rows.
12. Persistent DB remains unchanged unless a later operator-approved lane
    explicitly permits bounded writes.

## Safety Confirmations

V2-2X confirmed:

- No current code path copies `pair_age_seconds` into `token_age_seconds`.
- `derive_age_bucket()` still reads only `token_age_seconds`.
- A3 still requires real `token_age_seconds`.
- Recent-active tier logic depends on token-age bucket, not pair age.
- Current `token_age_evidence_tier` remains `None` until a real T1/T2/T3 path
  is active.
- GeckoTerminal and DexScreener remain useful for pair and market context but
  cannot honestly fill token age.
- Solana RPC holder fallback remains safety/holder evidence, not token-age
  enrichment.
- Jupiter quote remains paper-realism-only, not discovery or token-age evidence.

## Safety Risks

Primary risks before implementation:

- Treating pair age as token age would create false recent-launch labels.
- Treating PumpPortal migration time as token launch time could misclassify
  old tokens with new pairs.
- Treating `captured_at` as token creation time without event semantics would
  fabricate age.
- Using Solana public RPC for enrichment without budget controls could hit
  rate limits and create stale/failed evidence.
- Enabling PumpPortal as an unbounded stream would violate the bounded proof
  and scheduler/source-governor discipline.
- Any token-age evidence path that lacks source trace, freshness, and target
  matching would weaken the memory-diet selection gates.

## Money-Usefulness Contribution

Real token-age evidence improves money-usefulness without creating trade
signals by enabling:

- honest age buckets;
- recent-active tier evaluation;
- A3 late-buy-trap classification when the other evidence requirements exist;
- better separation of new launches from old-token/new-pair resurfacing;
- better negative-learning samples for traps, failed pumps, and late-buy setups;
- more balanced memory-diet candidate selection.

This is still discovery/selection context only. It is not a trade signal and
does not create clean memory by itself.

## What This Does Not Unlock

V2-2X does not unlock:

- token-age implementation;
- source expansion;
- PumpPortal or PumpSwap runtime;
- Solana RPC or Helius enrichment;
- scheduler runtime;
- memory generation;
- retrieval activation;
- paper decisions;
- BUY, SELL, or HOLD;
- paper positions;
- trade events;
- paper trade audits;
- PnL;
- live execution;
- wallet/private-key/signing logic;
- paid API dependencies;
- scoring, ranking, confidence, or weighted decision logic;
- embeddings or vectors.

## Remaining Blockers

| Blocker | Status | Impact |
| --- | --- | --- |
| No READY source provides `token_created_at` | CONFIRMED | Token age remains T5 unknown in live discovery. |
| PumpPortal launch source not live-active | CONFIRMED | Best T2 path requires design and bounded implementation proof. |
| Solana RPC / Helius token-age enrichment not implemented | CONFIRMED | T3 remains future work. |
| A3 live classification blocked by missing token age | CONFIRMED | A3 cannot fire honestly until T1/T2/T3 exists. |
| Recent-active priority blocked by missing token age | CONFIRMED | Recent-active tiers remain unknown for live candidates. |
| Pair age cannot be used as fallback | INTENTIONAL | Correct safety guard; must remain. |

## Final Verdict

V2-2X Token-Age Evidence Source Readiness Review:

`READINESS_COMPLETE_WITH_BLOCKERS`

The repo is structurally ready to receive token-age evidence because parser
fields, metadata handoff, pair-age labels, and safety tests already exist. It
is not implementation-ready because no first source path has been narrowed into
a source-governed, bounded, timestamp-safe contract.

## Exact Next Recommended Lane

`V2-2X.1 - Token-Age Evidence Source Design Update`

Recommended scope:

- Choose governed PumpPortal launch timing as the first T2 token-age source
  path.
- Define event timestamp semantics and source trace requirements.
- Define stale/failed/missing/migration safeguards.
- Define fixture-first proof and later bounded public proof.
- Preserve the no-pair-age-fallback rule.
- Keep V2-3, V2-4, token-age implementation, runtime/scheduler, memory,
  retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits,
  and PnL paused.
