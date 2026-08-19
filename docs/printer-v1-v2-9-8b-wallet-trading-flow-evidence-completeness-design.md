# Printer V1 V2-9.8B Wallet / Trading-Flow Evidence Completeness Design

Status: DESIGN_APPROVED_FOR_IMPLEMENTATION_BY_OPERATOR, SOURCE-BOUNDED

Baseline: `cf329a03801ca8af7e9fb5dbe65455f96cb9a2c6`

## Product requirement

Wallet participation and trading-flow detail remain optional for E2Q/E2Z clean-object eligibility, but collection is no longer optional behavior.

For every selected-token observation window, Printer should make the strongest lawful free-source collection attempt that fits the approved Source Governor / Scheduler budget. `UNKNOWN` / `PARTIAL` is an honest terminal fallback only when permitted evidence paths cannot resolve the field.

Target semantic:

`MAXIMIZE_WALLET_AND_FLOW_EVIDENCE_COMPLETENESS_WITH_HONEST_UNKNOWN_FALLBACK`

## Current gap

DexScreener-normalized pair snapshots provide transaction counts and total volume but do not provide the fields currently needed for descriptive `TRADING_FLOW_CONTEXT_CLEAN`:
- unique wallet participation;
- split buy-volume amount;
- split sell-volume amount.

These gaps do not currently block E2Z clean promotion and must not be made mandatory merely to increase a label count.

## C1 — mandatory enrichment-attempt contract

Add an explicit, durable/local enrichment decision surface with outcomes such as:
- `NOT_NEEDED_ALREADY_RESOLVED`
- `ATTEMPTED_RESOLVED`
- `ATTEMPTED_PARTIAL`
- `ATTEMPTED_SOURCE_UNAVAILABLE`
- `ATTEMPTED_BUDGET_EXHAUSTED`
- `NOT_SUPPORTED_BY_APPROVED_FREE_SOURCE`

This is categorical accounting, not scoring/confidence/ranking.

The attempt must:
- be Source-Governed when external evidence is required;
- be Scheduler-owned when scheduled runtime work is created;
- preserve stronger existing evidence;
- never infer unique wallets or split volume from aggregate values that cannot support those facts;
- never introduce a paid dependency.

## C2 — free on-chain enrichment readiness boundary

A Solana RPC path may be implemented only where current repository transaction evidence can deterministically bind:
- the exact mint/pool/program;
- successful transactions inside the relevant bounded interval;
- participant wallet identity from transaction account keys/signers; and
- token/SOL balance deltas sufficient to classify buy vs sell amount without heuristic scoring.

If current repository parsing does not support deterministic PumpSwap/pump.fun flow attribution, implementation must stop at the mandatory-attempt/accounting layer and preserve `UNKNOWN` rather than add an unsafe heuristic parser.

## C3 — refresh behavior

- Attempt enrichment at the smallest useful cadence that does not materially threaten core 15m/1h/4h lifecycle deadlines or source ceilings.
- Reuse resolved evidence until its explicit freshness boundary; do not repeat identical calls merely because a later window exists.
- 1h/4h may refresh or aggregate only from exact predecessor-bound evidence.
- Lifecycle observation always has priority over optional context enrichment.

## Required proof

1. already-resolved wallet/flow fields trigger no unnecessary external request;
2. unresolved optional fields create the bounded enrichment-attempt decision instead of silently being ignored;
3. unsupported/unavailable evidence remains honestly unknown and still may support clean memory under V2-9.4.7;
4. stronger resolved evidence is never overwritten by weaker missing/unresolved evidence;
5. no paid provider, retry loop, endpoint rotation, scoring, ranking, or confidence field is introduced;
6. any on-chain derived wallet/flow value has deterministic fixture proof for exact identity/direction/amount attribution.

If deterministic on-chain derivation cannot be proven from current repository evidence, do not implement that derivation in this package. Implement only the attempt/accounting seam and close with the remaining source capability explicitly blocked.