# CURRENT HANDOFF

Date: 2026-08-18

## Current lane

`V2-9.8B Post-Repair Standard 15m-to-1h-to-4h Bounded Campaign Design`

Status: `CLOSED_PASS`

Verdict: `V2_9_8B_POST_REPAIR_STANDARD_15M_TO_1H_TO_4H_BOUNDED_CAMPAIGN_DESIGN_PASS`

Implementation disposition: `IMPLEMENTATION_NOT_REQUIRED`

## Current code baseline

Repaired operational product-code baseline:

`df1aced491d01d1a6d25ae38ca2da4eab72665c6`

Design documentation branch:

`agent/v2-9-8b-post-repair-standard-campaign-design`

Design closeout commit before this handoff update:

`6632ac72f170e2db21feb23681a474e632710163`

The design adds no product source or migration. Master remains untouched by this lane.

## Latest completed work

The post-repair bounded standard campaign design is closed PASS. It binds the existing repaired runtime to one fresh, operator-approved, exactly-two-slot standard observation campaign using the canonical `standard-four-hour-run` path.

The designed observation law is `WINDOW_15M -> WINDOW_1H -> eligible WINDOW_4H`, with `WINDOW_5M_MICRO_EVENT` support-only and `WINDOW_12H` / `WINDOW_24H` locked.

The design preserves:

- source-specific candidate authority, including direct Pump migration + exact PumpSwap and repaired `MARKET_PRESENT_POOL` admission;
- exact mint+pair/current-pool identity;
- the exact `$3,000` liquidity floor with no score/rank/weight;
- Source Governor and Central Scheduler ownership;
- repaired later-cycle fresh acquisition if a later cycle is lawfully reached inside the same invocation;
- exact H predecessor cutoff and fresh first-hour safety authority;
- selected-slot holder ownership, holder concentration as descriptive rather than an automatic veto, and honest UNKNOWN for unsupported optional evidence;
- promotion/safety reporting separation;
- evidence-derived accounting, unified terminal closure and zero-work read-only replay;
- no retry/rerun/resume/restart/successor;
- migration head 058 and no migration 059; and
- all retrieval/financial/live/12h/24h capability locks.

No new implementation is required because these behaviors are already present at `df1aced...` and were covered by the immediately preceding integrated proof and independent closeout.

## Blockers

No proven product-code blocker for the next authorization-preparation/readiness step.

The actual host authoritative DB identity is not proven by GitHub and must be read-only bound during authorization preparation. A DB identity/ledger/integrity problem is therefore a preparation/readiness blocker unless evidence proves a code defect.

Future provider/source scarcity, insufficient eligible supply, exact-pair failure, liquidity below `$3,000` or unproven liquidity, honest UNKNOWN evidence, continuity/freshness/provenance failure, authorization mismatch, or bounded budget/duration/cancellation stop must be classified truthfully before reopening code.

## Exact next permitted action

`V2-9.8B Post-Repair Fresh Standard-4H One-Use Authorization Preparation`

Preparation/readiness only.

Allowed:

- host-local read-only preflight;
- bind exact repository/launch identity;
- bind exact authoritative DB filesystem/hash identity;
- verify migration head 058 and DB integrity/ledger readiness;
- derive the current standard capacity from committed code;
- construct one fresh temporally bounded standard-4h authorization package;
- record historical authorization non-reuse evidence; and
- stop for independent review.

Not allowed:

- consume the authorization;
- start providers/RPC/WebSockets for campaign execution;
- mutate the authoritative DB as campaign work;
- run a Memory Factory campaign;
- reuse any historical authorization;
- change product source or migrations;
- create migration 059;
- activate 12h/24h, retrieval, decisions, positions, trades, audits or PnL; or
- unlock wallets/private keys/signing/real funds, paid APIs, scoring/ranking/confidence/weighted logic, embeddings or vectors.

After preparation, the next required gate is:

`V2-9.8B Post-Repair Fresh Standard-4H One-Use Authorization Independent Review`

Only an independent review PASS may authorize at most one bounded campaign invocation while the fresh authorization remains temporally valid.

The active authority stack wins any conflict with this handoff.
