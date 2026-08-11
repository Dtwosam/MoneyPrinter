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
- first-hour lifecycle policy design commit begins at `04668c7204e0d56f1df7b56dfcd1eaa8d50be921` on branch `agent/v2-9-8b-post-dtw100-first-hour-lifecycle-policy-design`;
- first-hour Checkpoint 1-6 offline-composition chain closes at `7c793dca805bccf79a8bbadaed2fb57e426c6b93`;
- standard-four-hour current-state audit commit: `74bd2b48f4a1a0cd8d87e3696773d038ce59e2ca`;
- post-DTW100 standard-four-hour operational rereadiness closeout: `3b558d2af77ac469dd0d6c2f04e3993515988b2e`;
- consumed standard-four-hour preflight runtime closeout: `b3a4e16f6791c007399f0079dd2d2ad8d710ef59`;
- standard-four-hour preflight composition repair-scope audit: `30bbeca17f723e5c7cfe6da25f7ef73cc6191256`;
- standard-four-hour preflight composition repair design: `f83d46d02e25a53e4ab8dd60ba8cec8414f1a741`;
- standard-four-hour preflight composition repair implementation: `ca312c737e10b38cbb34e920eb419822913b7baf`;
- standard-four-hour preflight composition repair closeout: `6e7fb3b6d8e9e332ef66f09051e8cdfe424f2b53`.

DTW97 is permanently consumed and must not be rerun. DTW100 is already closed. No historical authorization may be reused.

### Latest standard-four-hour operational incident

The first separately operator-started standard 15m→1h→4h attempt used authorization `V2_9_8B_STANDARD_4H_AUTH_20260810T220717Z`. That authorization passed independent review, was consumed exactly once, and is permanently non-reusable.

Attempt identity:

- launch branch: `agent/v2-9-8b-post-dtw100-standard-four-hour-rereadiness-after-staging-repair`;
- launch HEAD: `3b558d2af77ac469dd0d6c2f04e3993515988b2e`;
- execution: `20260810T221625Z-20e56a0c7f56`;
- campaign: `20260810T221625Z-20e56a0c7f56-campaign`;
- run: `20260810T221625Z-20e56a0c7f56-campaign-run`;
- first terminal cause: `SAFE_STOP_PREFLIGHT_FAILED`;
- retry / rerun / resume / restart / successor: none.

Independent runtime forensics classified the blocker as `COMMITTED_CODE_DEFECT`.

The repair-scope audit established two adjacent composition defects. The approved repair is now implemented and closed:

1. standard-four-hour no longer inherits historical `operational_natural_disposition=True` from the live owner;
2. factory `continuous_first_hour` preflight explicitly recognizes standard-four-hour before historical compressed/natural/one-token proof shapes;
3. ordinary operational-natural behavior remains mode-scoped and preserved;
4. historical one-token proof semantics were not widened;
5. focused offline proof reaches a real factory run and both opening `WINDOW_15M` stage plans under the exact persistent two-token standard configuration;
6. no authorization, provider runtime, authoritative DB mutation, operational memory, or downstream financial capability was created by the repair proof.

`HOLDER_CONTEXT_BUDGET_EXHAUSTED` observed in the consumed attempt remains bounded holder-context truth and was not the root blocker. Holder budgets and memory-observation holder-decoupling law were not changed.

The consumed attempt must never be rerun or resumed.

## Active first-four-hour policy amendments

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

This policy supersedes older active-stack wording that made 15m→1h continuation depend on a 15m outcome/learning-need gate. Historical selective-1h documents remain preserved as historical evidence.

Observation continuation remains fail-closed on operational validity: exact token/mint/pair/lifecycle identity, closed predecessor boundary, tracking continuity, campaign state, cancellation/terminal state, Source Governor ownership, Central Scheduler ownership, DB/lease/integrity health, bounded campaign/token resources, and one-shot execution authority.

Memory quality remains separate. Continuing observation must never relabel dirty/blocked predecessor evidence as clean. `WINDOW_1H` and `WINDOW_4H` remain independently audited from their exact evidence. Dirty memory remains barred from retrieval and decisions.

The bounded observation lifecycle extends through the 4h checkpoint. After a genuine eligible first-hour close, every otherwise-valid activated token continues to `WINDOW_4H`; 1h outcome, direction, profitability, trajectory class, manipulation label, and learning-need presence/absence have no authority to qualify that observation. Hard identity, evidence quality, freshness, provenance, safety, continuity, campaign health, cancellation, Source Governor, Central Scheduler, and bounded-resource gates remain fail-closed.

Automatic continuation stops at `WINDOW_4H`. `WINDOW_12H` and `WINDOW_24H` remain selective and locked.

Controlling designs:

- `docs/printer-v1-v2-9-8b-post-dtw100-first-hour-lifecycle-policy-design.md`
- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-lifecycle-policy-campaign-integration-design.md`

## Current lane sequence

The consumed standard-four-hour attempt was safely closed blocked. The subsequent composition repair chain is now complete:

1. read-only repair-scope audit — **COMPLETE PASS**;
2. repair design/specification — **COMPLETE PASS** at `f83d46d02e25a53e4ab8dd60ba8cec8414f1a741`;
3. narrow two-boundary implementation — **COMPLETE** at `ca312c737e10b38cbb34e920eb419822913b7baf`;
4. focused offline production-shaped proof — **COMPLETE PASS**;
5. repair/proof closeout — **COMPLETE PASS** at `6e7fb3b6d8e9e332ef66f09051e8cdfe424f2b53`;
6. **fresh standard-four-hour operational rereadiness review**;
7. only after rereadiness PASS, prepare a completely fresh exact-HEAD one-use authorization and independently review it;
8. only after authorization review PASS, consider at most one new separately operator-started bounded standard-four-hour operational proof;
9. perform independent runtime closeout before any further capability lane.

No step authorizes the next automatically. Do not reuse the consumed standard-four-hour authorization, DTW97, DTW100, or any historical authorization.

### Current lane boundary

The immediate next lane is read-only operational rereadiness:

`V2-9.8B Post-Standard-4H Operational Rereadiness After Preflight Composition Repair`

Allowed now:

- static inspection;
- read-only authoritative DB inspection;
- lease/integrity/active-work inspection;
- exact Git/branch/HEAD verification;
- existing artifact and authorization-history review;
- Source Governor / Central Scheduler ownership and configuration review;
- read-only checks of budgets, locked capabilities, one-shot readiness, and wrapper/profile binding;
- rereadiness documentation and closeout.

Not allowed now:

- discovery/source fetching or provider calls;
- Scheduler/runtime execution;
- authoritative DB mutation;
- memory generation;
- fresh authorization preparation/application before rereadiness PASS;
- rerun/resume/restart/successor of the consumed attempt;
- retrieval activation;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper-trade audits, or PnL;
- `WINDOW_12H` or `WINDOW_24H` activation.

The rereadiness lane must independently confirm that the repaired exact HEAD is operationally safe to bind to a future fresh authorization. If any new blocker is found, close rereadiness blocked and classify it rather than bypassing it.

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
- no paper positions, trade events, paper-trade audits, or PnL before their explicit approved lanes.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently create a main outcome, start/stop the first-four-hour lifecycle, unlock retrieval, authorize decisions, or create positions/trades/PnL.

## Assistant execution rule

Preserve the V2 sequence: audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout.

Use minimum sufficient risk-based verification. Broad/full suites belong at major closeout, pre-live-proof, releases/checkpoints, or broad architectural changes, not every step.

During the current rereadiness lane, do not create or consume an authorization, invoke a live wrapper, contact providers, mutate the authoritative DB, generate operational memory, or unlock downstream financial capabilities. Rereadiness must close PASS before any fresh exact-HEAD one-use authorization is prepared.