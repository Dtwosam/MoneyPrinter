# Printer V1 V2-9.8B Post-DTW100 Standard First-Hour Harness / Reporting Alignment Design

## Verdict

```text
V2_9_8B_POST_DTW100_FIRST_HOUR_HARNESS_REPORTING_ALIGNMENT_DESIGN_READY
```

Design-only lane. No runtime, source fetching, Scheduler work, authoritative DB mutation, authorization creation, wrapper invocation, or lifecycle execution is authorized here.

## 1. Baseline

- Audit baseline: `dee67b4def9a413d315f40e8ae825a6e0293bca3`
- Prior audit verdict: `V2_9_8B_POST_DTW100_FIRST_HOUR_OPERATIONAL_HARNESS_AUTHORITY_AUDIT_BLOCKED_FIXTURE_AND_REPORTING_ALIGNMENT_DESIGN_REQUIRED`
- Current product rule: every otherwise-valid activated token continues from `WINDOW_15M` through the `WINDOW_1H` observation horizon. Outcome and learning-need labels do not qualify that transition.
- `WINDOW_1H -> WINDOW_4H` remains selective until its later explicit lane.

## 2. Confirmed audit findings

1. The historical operational selective-1h harness is stale against the current canonical clean-object contract.
2. Current B.1 requires a clean episode plus canonical `STATIC_CONDITION_SUMMARY` fingerprint; the old fixture manufactures only an episode.
3. Current E2Z atomically creates/verifies the clean episode and fingerprint and rejects unknown-outcome promotion; the old 1h promotion fixture omits a genuine outcome.
4. B.2 safety authority is not defective and must not be weakened.
5. Current first-hour reporting can classify a fully evaluated all-BLOCK result as `ZERO_ELIGIBLE_CONTINUATIONS`; that wording is no longer truthful under standard-first-hour policy.

## 3. Design decisions

### 3.1 Canonical fixture construction

Focused operational tests must stop manually manufacturing episode-only clean memory.

For any predecessor intended to be authoritative `CLEAN_MEMORY`, the fixture must create the same canonical clean-object shape required by production:

- exact closed main memory window;
- known truthful `outcome_label`;
- E2Q-audited supporting context and required snapshot linkage;
- current clean-object promotion owner invoked to create/verify:
  - one clean episode;
  - one `STATIC_CONDITION_SUMMARY` clean fingerprint;
- exact close-step result linked to that promotion.

Do not weaken `_authoritative_promotions_for_run()` to accept episode-only rows.

### 3.2 Standard-first-hour expectations

For valid canonical predecessors:

- `CONSOLIDATION` continues to 1h;
- `NO_PUMP` continues to 1h;
- pump/dump/slow-bleed/dead/moderate continuation continue to 1h;
- no ranking, scoring, confidence, weighted logic, or profitability criterion is introduced.

Hard gates remain authoritative. Dirty/invalid/mismatched/stale/unsafe/budget-exhausted inputs may still `BLOCK_CONTINUATION`.

### 3.3 Reporting semantics

Reporting must distinguish successful standard continuation from blocked continuation. A fully evaluated all-BLOCK result must not be reported as `ZERO_ELIGIBLE_CONTINUATIONS`.

Adopt the following current first-hour outcome semantics:

- `TWO_CONTINUATIONS`: 2 CONTINUE, 0 BLOCK.
- `ONE_CONTINUATION_ONE_BLOCK`: 1 CONTINUE, 1 BLOCK.
- `FIRST_HOUR_CONTINUATION_BLOCKED`: 0 CONTINUE, 1-2 BLOCK with a complete two-slot decision set.
- `EVALUATION_BLOCKED_SYSTEM_DEFECT`: decision/persistence set inconsistent or incomplete after evaluation should have been possible.
- `EVALUATION_NOT_REACHED`: evaluation did not occur.

Legacy normal STOP semantics are not an expected standard-first-hour success outcome. Preserve parsing compatibility where necessary, but do not let STOP masquerade as a normal new-policy terminal result.

`ZERO_ELIGIBLE_CONTINUATIONS` may remain as a historical compatibility constant, but current standard-first-hour reporting must not emit it for a complete two-slot evaluation.

### 3.4 E2Z 1h proof fixture

The focused 1h promotion proof must use a genuine `WINDOW_1H` candidate with:

- exact 1h identity and anchors;
- closed window;
- clean data/partial-memory candidate state;
- E2Q-audited supporting context;
- known non-`OUTCOME_UNKNOWN` outcome;
- current clean-object promotion path;
- assertions for one episode + one canonical fingerprint;
- idempotent second promotion;
- dirty 1h remains unpromoted;
- 5m remains support-only and cannot satisfy 1h/E2Z.

### 3.5 B.1/B.2 preservation

Do not change campaign ownership identity checks, exact close-step requirements, fingerprint requirement, safety target checks, freshness checks, provenance checks, or fail-close behavior.

## 4. Minimal implementation scope

Allowed implementation files:

- `src/printer_v1/operator_cli/operational_selective_1h.py` — reporting classification only.
- `tests/test_v2_9_8b_operational_selective_1h.py` — align stale fixture/expectations if feasible without broad rewrite.
- one new focused test module may be preferred over broad editing of the historical suite where it gives cleaner risk-based proof.

Do not change:

- `src/printer_v1/scheduler/token_local_continuation.py` standard-first-hour policy already proven;
- B.1/B.2 authority adapters;
- clean-object promotion owner;
- migrations/schema;
- Source Governor or Scheduler runtime;
- authorization/wrapper code;
- 4h+ policy.

## 5. TDD / focused proof

RED must prove at least:

1. current reporting maps 0 CONTINUE + 2 BLOCK to the obsolete zero-eligible result;
2. old episode-only fixture cannot satisfy current B.1;
3. old outcome-less 1h fixture cannot satisfy current E2Z.

GREEN must prove at least:

1. canonical predecessor + `CONSOLIDATION` -> 1h continuation;
2. canonical predecessor + `NO_PUMP` -> 1h continuation;
3. canonical predecessor adverse outcome -> 1h continuation;
4. hard safety/integrity/budget failure still blocks;
5. 2 CONTINUE -> `TWO_CONTINUATIONS`;
6. 1 CONTINUE + 1 BLOCK -> `ONE_CONTINUATION_ONE_BLOCK`;
7. 0 CONTINUE + BLOCK(s) -> `FIRST_HOUR_CONTINUATION_BLOCKED`;
8. inconsistent persistence/decision state -> `EVALUATION_BLOCKED_SYSTEM_DEFECT`;
9. genuine clean 1h E2Z creates episode + fingerprint and is idempotent;
10. dirty 1h and 5m remain unpromoted/locked;
11. retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL remain zero/locked.

Use temporary SQLite and mocks only. No provider/network/runtime access.

## 6. Money-usefulness contribution

This alignment makes the first-hour corpus less biased while preserving trustworthy clean-memory identity. It prevents valid quiet or adverse tokens from being dropped at 15m and prevents operational blocks from being misreported as benign lack of eligibility.

## 7. What this does not unlock

- no live or bounded `WINDOW_1H` execution;
- no authorization or one-shot wrapper;
- no automatic `WINDOW_1H -> WINDOW_4H` continuation;
- no 4h/12h/24h activation;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions/trades/audits/PnL;
- no wallet, signing, private keys, real funds, live execution, or paid APIs.

## 8. Proof required before completion

Focused offline RED/GREEN proof on the exact implementation head, followed by exact-head verification and closeout. Broad regression is not required unless the change expands beyond the scoped reporting/harness owners.

## 9. Functionality Risks / Setbacks / Efficiency Blockers

- Updating the historical comprehensive fixture can become a broad rewrite; prefer a focused canonical composition harness if that better isolates the current contract.
- Historical constants/strings may be consumed by retained reports; preserve read compatibility even if new runs stop emitting obsolete semantics.
- A reporting fix must not convert hard BLOCK into benign STOP.
- The separate first-hour one-use authorization/wrapper integration blocker remains unresolved after this lane.
- Standard 4h policy remains a later audit/design problem.

## 10. Stop condition

After implementation, focused proof, exact-head verification, and closeout, stop. Do not create authorization or run any lifecycle window in this lane.
