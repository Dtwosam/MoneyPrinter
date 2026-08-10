# Printer V1 V2-9.8B Post-DTW100 Standard Four-Hour Lifecycle Design and Source-Stack Adoption Closeout

## Verdict

`V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_LIFECYCLE_DESIGN_AND_SOURCE_STACK_ADOPTION_PASS`

The standard-four-hour observation policy and its campaign-integration design are adopted into the active current-policy stack.

For otherwise-valid activated tokens, observation is now standard through the 4h checkpoint after hard gates pass. `WINDOW_15M` and `WINDOW_1H` outcome/behavior/learning-need labels no longer qualify continuation. Automatic continuation stops at 4h; 12h/24h remain selective and locked.

This closeout authorizes implementation only in a separate offline/TDD lane. It does not activate real 4h collection, runtime, source fetching, authorization, authoritative DB mutation, retrieval, decisions, positions, PnL, wallet, signing, or execution.

## Baseline and controlling records

- Audit commit: `74bd2b48f4a1a0cd8d87e3696773d038ce59e2ca`.
- Design commit: `7952ec0d2ec26f4ca93cd8f3f588c5f82c3fc631`.
- Source-stack adoption scope record: `3c8b6947abe152f6b44abb6b9e94211946aa5787`.
- Source-stack amendment commit: `e5fc88c7e874eef71ae02024438b9c78076676f7`.
- Assistant current-lane reconciliation commit: `4efe260abfbd432550986acab06923156f1238de`.

## Files adopted/changed

Current policy/assistant anchors:

- `AGENTS.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-assistant-active-build-order-anchor.md`

New controlling records:

- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-lifecycle-policy-campaign-integration-design.md`
- `docs/printer-v1-v2-9-8b-post-dtw100-standard-four-hour-lifecycle-source-stack-adoption.md`
- this closeout

Historical V2-9.7C/V2-9 designs/proofs/closeouts were not rewritten.

## Exact adopted policy

```text
valid activated token
-> WINDOW_15M checkpoint
-> standard hard-gated continuation
-> WINDOW_1H checkpoint
-> standard hard-gated continuation
-> WINDOW_4H checkpoint
-> stop automatic continuation
```

The following do not authorize or stop 15m->1h or 1h->4h observation by themselves:

- outcome/direction/profitability;
- `NO_PUMP` / `CONSOLIDATION` or transition labels;
- manipulation label;
- learning-need presence/absence;
- 5m support evidence;
- scoring/ranking/confidence/weighting.

Hard identity, evidence quality, freshness, provenance, safety, continuity, campaign health, cancellation, Source Governor, Central Scheduler, and bounded-resource gates remain fail-closed.

## Campaign-integration contract adopted for implementation

The implementation lane must:

- reuse the existing 4h cadence/continuity/physical-close/E2Q/Lane-Q/E2Z machinery;
- atomically create exact campaign `WINDOW_4H` successors from reconciled `WINDOW_1H_CLOSED` predecessors;
- advance exact token slots to `WINDOW_4H_CONTINUING`;
- project every long-window Scheduler job through stage-scoped campaign Scheduler-work ownership;
- support both valid token slots through 4h with categorical fairness;
- derive mixed-lane resource ceilings from policy rather than the old one-continuer proof ceiling;
- reconcile 4h window/token terminal truth using the Checkpoint-6 pattern;
- create no 12h successor;
- preserve zero retries and existing Source Governor/Central Scheduler controls.

Current planning ceilings derived from committed policy are:

- FAST+FAST: 230 requests / 210 Scheduler rows;
- FAST+NORMAL: 182 / 162;
- NORMAL+NORMAL: 134 / 114.

They remain policy-derived implementation targets, not live authorization.

## Real-collection lock

`WINDOW_4H.enabled_for_real_collection` remains false.

The implementation lane must not flip that flag merely to make tests pass. Real collection can be considered only after:

1. TDD implementation;
2. focused offline proof;
3. implementation/proof closeout;
4. separate operational rereadiness;
5. separately approved activation repair/proof;
6. fresh exact-HEAD one-use authorization and independent review.

Historical proof flags are not production authority.

## Static verification

The amendment diff from the controlling audit contains documentation/current-policy changes only. No production code, tests, migrations, DB, workflow, or runtime file exists on the design branch from this adoption.

Static review confirms:

- the Clean Master Spec did not require the superseded selective 1h->4h rule and was left unchanged;
- all four current policy/assistant anchors now agree on standard hard-gated observation through 4h;
- automatic continuation stops at 4h;
- 12h/24h remain selective/locked;
- 5m remains support-only;
- 4h real collection remains separately locked;
- all permanent V1 safety/financial restrictions remain intact;
- historical source documents remain historical rather than silently rewritten.

`git diff --check` passed in the disposable source-stack amendment runner before the amendment commit was pushed.

## Money-usefulness contribution

The policy removes first-hour behavior-conditioned sampling bias while the campaign design prevents that broader observation from becoming unowned or unbounded. Printer can later learn delayed collapse, revival, survival, distribution, round trips, and liquidity deterioration across both active token slots without turning those categories into selection scores.

## What remains locked

- real 4h collection;
- live/bounded operational run;
- fresh authorization/wrapper;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions/trades/audits/PnL;
- live wallet/private keys/signing/real funds/execution;
- paid APIs;
- scoring/ranking/confidence/weighted logic;
- embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- two full 4h continuations have materially higher bounded resource cost than the historical one-continuer proof;
- the one-token proof runtime must be reused/refactored, not duplicated;
- every long Scheduler job needs campaign ownership before real activation;
- close-deadline fairness for two long windows still requires proof;
- report-yield logic must use authoritative clean objects;
- the real-collection cadence lock must remain closed until the later activation lane;
- 4h must not silently unlock 12h.

## Next permitted lane

`V2-9.8B Post-DTW100 Standard Four-Hour Lifecycle Campaign Integration Implementation`

Start with TDD RED. Keep 4h real collection disabled and use only offline/proof-isolated fixtures until implementation/proof closeout passes.
