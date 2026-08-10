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
- standard-four-hour preflight composition repair-scope audit: `30bbeca17f723e5c7cfe6da25f7ef73cc6191256`.

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

The repair-scope audit established the complete two-boundary defect:

1. the live operational owner marks the standard-four-hour campaign correctly but also unconditionally injects the legacy `operational_natural_disposition=True` lifecycle option;
2. the origin→lifecycle driver truthfully forwards that option into `run_one_command_15m_factory`;
3. the factory's standard-four-hour preflight explicitly rejects historical operational-natural disposition semantics and requires `four_hour_proof_mode=False`;
4. the inherited legacy operational-natural branch simultaneously requires terminal 4h proof mode;
5. even if the legacy natural flag is merely removed, the generic `continuous_first_hour` preflight falls through to the historical one-autonomous-token rule, while standard-four-hour requires exactly two token slots;
6. therefore both live-owner option ownership and factory preflight mode classification require one narrow coordinated repair design.

`HOLDER_CONTEXT_BUDGET_EXHAUSTED` was observed during the bounded holder stage but is not the root blocker. Holder budget exhaustion remains bounded completion/context truth under the adopted memory-observation holder-decoupling law and must not be repaired by increasing budgets or re-gating memory admission on holder pass.

Terminal cleanup completed, the lease was released, active work returned to zero, and no current-run memory window/episode/fingerprint or downstream retrieval/paper-financial capability was created.

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

This policy supersedes older active-stack wording that made 15m->1h continuation depend on a 15m outcome/learning-need gate. Historical selective-1h documents remain preserved as historical evidence.

Observation continuation remains fail-closed on operational validity: exact token/mint/pair/lifecycle identity, closed predecessor boundary, tracking continuity, campaign state, cancellation/terminal state, Source Governor ownership, Central Scheduler ownership, DB/lease/integrity health, bounded campaign/token resources, and one-shot execution authority.

Memory quality remains separate. Continuing observation must never relabel dirty/blocked predecessor evidence as clean. `WINDOW_1H` and `WINDOW_4H` remain independently audited from their exact evidence. Dirty memory remains barred from retrieval and decisions.

The bounded observation lifecycle extends through the 4h checkpoint. After a genuine eligible first-hour close, every otherwise-valid activated token continues to `WINDOW_4H`; 1h outcome, direction, profitability, trajectory class, manipulation label, and learning-need presence/absence have no authority to qualify that observation. Hard identity, evidence quality, freshness, provenance, safety, continuity, campaign health, cancellation, Source Governor, Central Scheduler, and bounded-resource gates remain fail-closed.

Automatic continuation stops at `WINDOW_4H`. `WINDOW_12H` and `WINDOW_24H` remain selective and locked.

Controlling designs:

- `docs/printer-v1-v2-9-8b-post-dtw100-first-hour-lifecycle-policy-design.md`
- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-lifecycle-policy-campaign-integration-design.md`

## Current lane sequence

The first standard-four-hour one-shot was consumed and safely closed blocked. The following read-only repair-scope audit is now closed PASS at `30bbeca17f723e5c7cfe6da25f7ef73cc6191256` with verdict:

`V2_9_8B_POST_STANDARD_4H_PREFLIGHT_COMPOSITION_REPAIR_SCOPE_AUDIT_PASS_TWO_BOUNDARY_DEFECTS_DESIGN_REQUIRED`

The current roadmap-compliant sequence is now:

1. read-only repair-scope audit — **COMPLETE PASS**;
2. **design/specify the minimum two-boundary mode-scoped correction**;
3. implement only the approved correction;
4. run focused offline production-shaped proof showing the standard-four-hour path reaches factory-run creation and both first-15m lifecycle stages, while ordinary operational-natural behavior remains unchanged and invalid mixed configurations still fail closed;
5. close the repair/proof with exact safety and capability-delta evidence;
6. perform a fresh standard-four-hour operational rereadiness review;
7. only after rereadiness PASS, prepare a completely fresh exact-HEAD one-use authorization and independently review it;
8. only after that review PASS, consider at most one new separately operator-started bounded standard-four-hour operational proof;
9. perform independent runtime closeout before any further capability lane.

No step authorizes the next automatically. Do not reuse the consumed standard-four-hour authorization, DTW97, DTW100, or any historical authorization.

### Current lane boundary

The immediate next lane is **design/specification only**:

`V2-9.8B Post-Standard-4H Preflight Composition Repair Design`

Allowed now:

- static inspection and existing artifact review needed to specify the repair;
- design documentation;
- exact caller/configuration matrix;
- RED/GREEN test-plan specification;
- risk, rollback, proof, and closeout criteria.

Not allowed now:

- production code changes;
- test execution that invokes runtime/source/Scheduler behavior;
- source fetching or provider calls;
- Scheduler/runtime execution;
- authoritative DB mutation;
- memory generation;
- new authorization preparation/application;
- rerun/resume/restart/successor of the consumed attempt;
- retrieval activation;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper-trade audits, or PnL;
- `WINDOW_12H` or `WINDOW_24H` activation.

The audit currently justifies only two production repair surfaces for later implementation consideration:

- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`;
- `src/printer_v1/operator_cli/one_command_15m_factory.py`.

Do not broaden implementation unless the design or focused proof establishes a separate defect.

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
- no BUY/SELL/HOLD before their explicit approved lane;
- no paper positions, trade events, paper-trade audits, or PnL before their explicit approved lanes.

`WINDOW_5M_MICRO_EVENT` remains support-only and cannot independently create a main outcome, start/stop the first-four-hour lifecycle, unlock retrieval, authorize decisions, or create positions/trades/PnL.

## Assistant execution rule

Preserve the V2 sequence: audit/readiness -> design/specification -> implementation if approved -> bounded proof/test -> closeout.

Use minimum sufficient risk-based verification. Broad/full suites belong at major closeout, pre-live-proof, releases/checkpoints, or broad architectural changes, not every step.

During the current repair-design lane, do not modify production code, create or consume an authorization, invoke a live wrapper, contact providers, mutate the authoritative DB, generate operational memory, or unlock downstream financial capabilities.
