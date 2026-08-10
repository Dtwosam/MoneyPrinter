# Printer V1 Assistant Active Build Order Anchor

## Purpose and authority

This document aligns ChatGPT, Codex, Claude, and future assistants before Printer V1 memory-growth work.

It does not replace:

- `AGENTS.md`;
- `docs/printer-v1-clean-master-spec.md`;
- `docs/printer-v1-post-rc-build-order.md`;
- `docs/printer-v1-memory-factory-guide.md`;
- `docs/printer-v1-current-state-memory-growth-audit.md`; or
- `docs/printer-v1-memory-growth-build-order-v2.md`.

Inside that stack, `docs/printer-v1-memory-growth-build-order-v2.md` is the active memory-growth build order, not the sole source of truth. Later committed audits, designs, implementations, proofs, closeouts, and reconciliations control current lane position.

## Current durable state

V2-9.8B has progressed beyond the older Post-C8 authorization-preparation state formerly recorded here.

Durable current anchors include:

- DTW100 `WINDOW_15M` campaign closeout: `059f4fad26d508b09cc361bc267049adc3cdb9ce`;
- post-DTW100 E2Q audit closeout: `b07a946d56886d923129b3eacade775f19f58d71`;
- post-DTW100 selective-1h operational rereadiness audit: `13aa70b3bc91def711a64d8f46ed6fa0b98dc488`;
- post-DTW100 15m trajectory-classification audit: `b976538d3e7a9c7c2173b8751e19eef3295c0d04`;
- first-hour lifecycle policy design commit begins at `04668c7204e0d56f1df7b56dfcd1eaa8d50be921` on branch `agent/v2-9-8b-post-dtw100-first-hour-lifecycle-policy-design`.

DTW97 is permanently consumed and must not be rerun. DTW100 is already closed. No historical authorization may be reused.

## Active first-hour policy amendment

For future bounded main-lifecycle operations, `WINDOW_15M -> WINDOW_1H` is no longer a behavior/outcome-qualified selective transition.

Every token validly activated into the bounded main tracking lifecycle is committed to first-hour observation:

```text
activation
-> same exact token/pair tracked from t=0
-> WINDOW_15M closes as the first main-memory checkpoint
-> observation continues through the remaining first hour
-> WINDOW_1H closes at the full first-hour horizon
```

The 15m checkpoint does not decide whether the token deserves the remaining first-hour observation. `NO_PUMP`, `CONSOLIDATION`, pump/dump/dead/revival labels, final 15m direction, profitability, scoring, ranking, confidence, weighting, and `WINDOW_5M_MICRO_EVENT` have no authority to stop or authorize that first-hour observation.

This policy supersedes older active-stack wording that made 15m->1h continuation depend on a 15m outcome/learning-need gate. Historical selective-1h documents remain preserved as historical evidence.

Observation continuation remains fail-closed on operational validity: exact token/mint/pair/lifecycle identity, closed 15m boundary, tracking continuity, campaign state, cancellation/terminal state, Source Governor ownership, Central Scheduler ownership, DB/lease/integrity health, bounded campaign/token resources, and one-shot execution authority.

Memory quality remains separate. Continuing observation must never relabel dirty/blocked 15m evidence as clean. `WINDOW_1H` is independently audited from its exact first-hour evidence. Dirty memory remains barred from retrieval and decisions.

The bounded observation lifecycle now extends through the 4h checkpoint. After a genuine eligible first-hour close, every otherwise-valid activated token continues to `WINDOW_4H`; 1h outcome, direction, profitability, trajectory class, manipulation label, and learning-need presence/absence have no authority to qualify that observation. Hard identity, evidence quality, freshness, provenance, safety, continuity, campaign health, cancellation, Source Governor, Central Scheduler, and bounded-resource gates remain fail-closed.

Automatic continuation stops at `WINDOW_4H`. `WINDOW_12H` and `WINDOW_24H` remain selective and locked. `WINDOW_4H` real collection also remains disabled until the separately approved campaign-integration implementation, offline proof, closeout, and later operational rereadiness/activation gate pass.

Controlling designs:

- `docs/printer-v1-v2-9-8b-post-dtw100-first-hour-lifecycle-policy-design.md`
- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-lifecycle-policy-campaign-integration-design.md`

## Current lane sequence

The approved sequence is:

1. first-hour lifecycle policy design/source-stack amendment;
2. minimal implementation;
3. focused offline proof and closeout;
4. return to the separate post-DTW100 one-use first-hour authorization/wrapper integration design;
5. authorization implementation/proof and fresh rereadiness;
6. fresh exact-HEAD one-use authorization preparation and independent review;
7. exactly one separately operator-started first-hour operational proof;
8. independent runtime closeout.

The current policy-design/implementation/proof work does not authorize step 4 or later automatically.

## Permanent restrictions

Printer V1 remains:

- Solana-only;
- Solana memecoin-only;
- paper-trading only;
- no live wallet, private keys, signing, real funds, or live execution;
- no paid API dependency;
- no scoring, ranking, confidence, or weighted decision logic;
- no embeddings or vectors unless explicitly approved later;
- no Source Governor bypass;
- no Central Scheduler bypass;
- no dirty memory used for retrieval or decisions;
- no retrieval before its explicit approved lane;
- no paper decisions before their explicit approved lane;
- no BUY/SELL/HOLD before its explicit approved lane;
- no paper positions, trade events, paper-trade audits, or PnL before their explicit approved lanes;
- no 4h/12h/24h activation before explicit approved lanes.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently create a main outcome, start/stop the first-hour lifecycle, unlock retrieval, authorize decisions, or create positions/trades/PnL.

## Assistant execution rule

Preserve the V2 sequence: audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout.

Use minimum sufficient risk-based verification. Broad/full suites belong at major closeout, pre-live-proof, releases/checkpoints, or broad architectural changes, not every step.

Do not create or consume a fresh authorization, invoke a live wrapper, contact providers, mutate the authoritative DB, generate operational memory, or unlock downstream financial capabilities during this policy implementation/proof lane.
