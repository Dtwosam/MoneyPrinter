# Printer V1 Post-DTW100 First-Hour Lifecycle Policy Implementation Plan

**Goal:** Remove the 15m outcome/learning-need qualification gate so every otherwise-valid bounded main-lifecycle token continues from `WINDOW_15M` to `WINDOW_1H`, while preserving all existing hard evidence/safety/identity/continuity/budget gates and preserving selective `WINDOW_1H -> WINDOW_4H` behavior.

**Architecture:** Keep the existing campaign/factory and `operational_selective_1h` compatibility surface. Change only the shared pure continuation policy at the transition-specific decision point. For 15m->1h, once all existing hard fail-closed requirements and token budget pass, continue regardless of `learning_need`; for 1h->4h, retain the current learning-need gate unchanged.

**Tech stack:** Python, `unittest`, existing Printer V1 continuation contracts. No migration, live source call, Scheduler runtime, or authoritative DB mutation.

## Global constraints

- Solana-only, memecoin-only, paper-only.
- No wallet/private keys/real funds/live execution/paid APIs.
- No scoring/ranking/confidence/weighted logic/embeddings/vectors.
- No Source Governor or Central Scheduler bypass.
- `WINDOW_5M_MICRO_EVENT` remains support-only/non-authoritative.
- No retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.
- No authorization creation or operational 15m/1h run.
- Preserve risk-based verification: focused affected tests only in this lane.

## Task 1 — RED: first-hour policy tests

**Files:**
- Modify: `tests/test_v2_9_7d_4a_token_local_selective_continuation.py`

Required failing assertions before production change:

- 15m->1h with `learning_need=None` continues for both otherwise-valid tokens.
- 1h->4h with `learning_need=None` still stops at 1h.
- Existing hard blocker tests remain unchanged.

Run focused test file and confirm the first-hour assertions fail for the expected old `STOP_AFTER_WINDOW_15M` behavior.

## Task 2 — GREEN: minimal transition-specific implementation

**Files:**
- Modify: `src/printer_v1/scheduler/token_local_continuation.py`

After existing shared/token hard gates pass:

1. check token budget;
2. if transition is exactly `WINDOW_15M -> WINDOW_1H`, return `CONTINUE_TO_WINDOW_1H` with a categorical first-hour-lifecycle reason without consulting `learning_need`;
3. otherwise preserve the existing 1h->4h learning-need logic exactly.

Do not remove or weaken identity, closed-window, clean-memory, clean-data, do-not-train, evidence eligibility/completeness/freshness/provenance, safety, continuity, token/campaign state, DB/lease/integrity, or bounded-resource gates in this implementation.

## Task 3 — Direct operational regression alignment

**Files:**
- Modify only old assertions that encode `NO_PUMP`/`CONSOLIDATION` as normal 15m stops in `tests/test_v2_9_8b_operational_selective_1h.py`.

Required new expectation: otherwise-valid clean `NO_PUMP`/`CONSOLIDATION` predecessors both create first-hour continuations. Dirty/ineligible predecessor and all hard blocker tests remain blocked.

## Task 4 — Focused proof and closeout

Run only:

- `tests/test_v2_9_7d_4a_token_local_selective_continuation.py`
- directly affected first-hour cases in `tests/test_v2_9_8b_operational_selective_1h.py`
- syntax/compile check for changed Python files
- diff/lock scan proving 5m, 4h+, retrieval, paper/financial locks unchanged

Close only after RED was observed, GREEN passes, and no hard gate was weakened. Stop before authorization or runtime.
