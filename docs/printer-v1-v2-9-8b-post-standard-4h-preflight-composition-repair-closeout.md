# Printer V1 — Post-Standard-4H Preflight Composition Repair Closeout

## Verdict

`V2_9_8B_POST_STANDARD_4H_PREFLIGHT_COMPOSITION_REPAIR_CLOSEOUT_PASS`

The narrow two-boundary preflight-composition repair is closed PASS.

This closeout authorizes only the next roadmap lane: a fresh standard-four-hour operational rereadiness review. It does not create or authorize a live run, a fresh one-use authorization, provider/source execution, authoritative DB mutation, memory generation, retrieval, decisions, paper positions, BUY/SELL/HOLD, trades, audits, PnL, or `WINDOW_12H` / `WINDOW_24H` activation.

## Durable chain

- repair-scope audit: `30bbeca17f723e5c7cfe6da25f7ef73cc6191256`
- design: `f83d46d02e25a53e4ab8dd60ba8cec8414f1a741`
- implementation: `ca312c737e10b38cbb34e920eb419822913b7baf`
- implementation commit message: `Repair standard four-hour preflight composition`
- implementation branch: `agent/v2-9-8b-post-standard-4h-preflight-composition-repair-implementation`
- closeout branch: `agent/v2-9-8b-post-standard-4h-preflight-composition-repair-closeout`

The implementation branch is exactly one commit ahead of the design baseline and zero commits behind.

## Exact production repair

Only two production files changed.

### 1. Live owner authority separation

File:

`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`

The historical natural-disposition injection is now mode-scoped:

```python
if not standard_four_hour_campaign:
    lk["operational_natural_disposition"] = True
```

Result:

- ordinary operational-natural mode retains its existing authority;
- standard-four-hour no longer inherits historical natural-disposition authority;
- caller-supplied historical proof/disposition keys remain rejected.

### 2. Factory preflight mode partition

File:

`src/printer_v1/operator_cli/one_command_15m_factory.py`

Inside `continuous_first_hour`, standard-four-hour is recognized before historical compressed/natural/one-token proof shapes. The dedicated standard-four-hour preflight remains the authority for its exact persistent two-token shape.

The historical one-token rule was not widened, compressed proof semantics were not changed, and V2-5 incompatibility remains fail-closed.

## Focused proof evidence

New proof file:

`tests/test_v2_9_8b_post_standard_4h_preflight_composition_repair.py`

Repair-specific result:

- `3 passed`

The production-shaped offline standard path proves all of the following before intentionally stopping at the opening-plan boundary:

- factory run exists;
- factory run status is `RUNNING`;
- DB mode is `OPERATIONAL_PERSISTENT`;
- `standard_four_hour_campaign=True`;
- `continuous_first_hour=True`;
- `continuous_four_hour=True`;
- `selective_1h_continuation=True`;
- `four_hour_proof_mode=False`;
- `operational_natural_disposition=False`;
- exactly two opening `SNAPSHOT` lifecycle steps exist;
- the opening steps cover two distinct token IDs and two distinct pair IDs;
- exactly two Scheduler rows back those opening steps;
- zero memory windows exist at the intentional proof stop.

The proof uses disposable migrated SQLite and fixture source adapters. It does not contact live providers or mutate the authoritative production DB.

## Focused regression evidence

Risk-based verification was used rather than a broad repository suite.

Observed passing evidence:

- repair-specific tests: `3 passed`;
- remaining `test_v2_4_one_command_15m_factory.py`: `15 passed, 1 deselected`;
- remaining authoritative-live-owner E.11 suite: `36 passed, 5 deselected`;
- standard-four-hour final-public-wiring: `10 passed`;
- standard-four-hour factory-barrier: `16 passed`;
- standard-four-hour operational-activation: `10 passed`;
- standard-four-hour campaign-planning: `9 passed`.

The five deselected E.11 nodes were each run separately on both the repaired tree and untouched design HEAD `f83d46d02e25a53e4ab8dd60ba8cec8414f1a741`. Every one failed on both trees with the same legacy `supply is None` / `holder_reserve_candidates` traceback. They are therefore classified `PRE_EXISTING_OR_ENVIRONMENTAL_FAILURE` and were not pulled into this repair lane.

One historical compressed-time factory test was also independently run on both repaired and untouched design trees and failed on both with the same fixed-deadline closeout condition. It is likewise classified `PRE_EXISTING_OR_ENVIRONMENTAL_FAILURE` and remains out of scope.

No unrelated pre-existing failure was repaired, suppressed, or used to expand production scope.

## TDD evidence note

The guarded implementation sequence required the new repair test to fail before applying the production source edits, then reran it GREEN after the two narrow production changes. The standalone RED transcript was not preserved in the later uploaded terminal artifacts; therefore this closeout records the enforced RED gate but does not overstate a separately retained RED log artifact.

## Acceptance-gate review

- standard-four-hour does not inherit `operational_natural_disposition`: PASS
- exact standard persistent two-token shape passes the conflicting preflight seam: PASS
- ordinary natural-mode injection remains present: PASS
- historical one-token continuous-first-hour semantics remain separate: PASS
- invalid standard/historical mixed configurations remain fail-closed: PASS
- production-shaped offline standard path reaches factory-run creation: PASS
- both first `WINDOW_15M` opening stage plans are created: PASS
- no source-budget, holder, Scheduler, DB, memory-quality, authorization, or later-window law was weakened: PASS by exact diff review
- no later capability was unlocked: PASS

## Money-usefulness contribution

This repair removes a deterministic configuration contradiction that previously consumed a valid one-shot standard-four-hour attempt before the first main lifecycle stage could begin. Printer can now reach the already-designed first-four-hour observation machinery in offline production-shaped proof, improving the chance that a later properly authorized bounded run can collect trustworthy 15m/1h/4h learning evidence instead of failing at composition preflight.

It does not prove profitability and does not authorize any paper-financial action.

## What this lane improves

- separates standard-four-hour production authority from historical natural/proof authorities;
- restores exact two-token standard preflight composition;
- preserves ordinary historical mode semantics;
- closes the exact composed-preflight proof gap exposed by the consumed attempt;
- gives the next rereadiness lane a reviewed implementation HEAD.

## What this lane still does not unlock

- no fresh one-use authorization;
- no live standard-four-hour run;
- no retry/resume/restart/successor of the consumed attempt;
- no provider/source fetching;
- no authoritative DB mutation;
- no operational memory generation;
- no `WINDOW_12H` / `WINDOW_24H` activation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no paper positions, trade events, paper-trade audits, or PnL;
- no wallet/private keys/signing/real funds/live execution;
- no paid API dependency;
- no scoring/ranking/confidence/weighted decision system;
- no embeddings/vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Functionality Risks / Setbacks / Efficiency Blockers

- The broader repository still contains pre-existing legacy test failures identified above. They are not caused by this repair and should be handled only by their own roadmap-compliant audit if they become relevant to a future lane.
- This proof stops deliberately after the real opening planner. It proves the repaired preflight seam and opening lifecycle composition, not a real 15m/1h/4h runtime.
- A later live attempt could expose a different downstream defect. If so, stop and classify it rather than widening this repair retrospectively.
- The previous consumed standard-four-hour authorization remains permanently non-reusable.
- Fresh rereadiness must independently recheck exact HEAD, authoritative DB/lease/integrity state, no active work, ownership/budget/capability locks, and one-shot readiness before any new authorization may be prepared.

## Next permitted lane

`V2-9.8B Post-Standard-4H Operational Rereadiness After Preflight Composition Repair`

This next lane is read-only/rereadiness work first.

Only after that rereadiness closes PASS may a completely fresh exact-HEAD one-use standard-four-hour authorization be prepared and independently reviewed. No authorization or runtime is authorized by this closeout.