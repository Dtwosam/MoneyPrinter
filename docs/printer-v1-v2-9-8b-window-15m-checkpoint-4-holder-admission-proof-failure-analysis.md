# Printer V1 V2-9.8B WINDOW_15M Checkpoint 4 — Focused Proof Failure Analysis

## Status

`V2_9_8B_WINDOW_15M_CHECKPOINT_4_FOCUSED_PROOF_BLOCKED_BY_SUPERSEDED_TEST_FIXTURES`

This is not a production repair verdict and does not close Checkpoint 4.

- Baseline: `af4503b8f175b556129516a7770fb1c3f9df6906`
- Audit commit tested: `3979a447418509cb6bbf1a032cd939a5eedf34dc`
- Branch: `agent/v2-9-8b-window-15m-checkpoint-4-holder-budget-evidence-two-token-admission`
- Linear: `DTW-30`
- Provider contact: none
- Printer/runtime: none
- Authorization: none
- Authoritative database: not accessed or mutated
- Checkpoint 5: not started

## Observed result

The first detached-worktree proof reached the exact audit commit and passed syntax/import checks.

Pytest result:

- `117 passed`
- `17 failed`
- elapsed: `23.91s`

The wrapper cleanup ran after pytest returned non-zero.

## Root-cause classification

No failing stack trace demonstrates a current production holder/admission defect.

The failures split into two superseded fixture contracts.

### A. Pre-exact-manifest coverage fixtures

Several historical tests construct request-manifest or stage-coverage entries with:

- `transport_identity_count > 0`; and
- no `transport_identity_keys`.

The later exact pre-holder transport-identity repair intentionally rejects that shape. Current production requires exact canonical identity keys, count/key parity, unique ownership, and exact `M = C = A` set equality.

The historical tests therefore receive the newer truthful aggregate classification such as:

- `MULTIPLE_PRE_HOLDER_TRANSPORT_IDENTITY_DEFECTS`; or
- `MULTIPLE_SOURCE_REQUEST_RECONCILIATION_DEFECTS`.

Changing production to restore the older count-only behavior would weaken an adopted safety repair and is forbidden.

Affected historical fixture surfaces include:

- `_manifest()` in `tests/test_v2_9_8b_window_15m_freeze_holder_budget_decoupling_repair.py`;
- `_coverage()` in `tests/test_v2_9_8b_holder_partial_accounting_repair.py`;
- `_coverage()` and the missing-row coverage fixture in `tests/test_v2_9_8b_holder_manifest_composition_repair.py`.

### B. Pre-temporal-authority candidate fixtures

Several historical holder tests call `_evaluate_holder_eligibility()` with:

```python
SimpleNamespace(mint=..., bonding_curve=..., block_time=0)
```

The later source-specific temporal-contract repair intentionally permits only:

- `SourceSpecificCandidateAdmission` carrying validated retained market or direct-graduation temporal context; or
- legacy `FixtureOriginProof` carrying an exact positive block time.

Unsupported duck-typed carriers and zero timestamps now fail closed before maturation or holder transport with:

`UNSUPPORTED_CANDIDATE_TEMPORAL_AUTHORITY`

That failure is the correct current behavior. Restoring duck-typed or zero-time fallback would weaken the adopted temporal-safety contract and is forbidden.

Affected historical helper surfaces include:

- `_evaluate_permanent_holder_context()` in the freeze/holder-budget suite;
- the holder-stage fan-out fixture in the safe-stop holder-accounting suite;
- `_evaluate()` in the partial-accounting suite;
- the direct holder-result fixture in the holder-manifest suite.

## Cascading assertion failures

The campaign-level empty holder diagnostics in the failed historical tests are downstream effects of the same stale fixture contracts:

- count-only pre-holder coverage blocks before holder evaluation; or
- unsupported temporal carriers block before maturation and holder execution.

They do not independently prove that current holder IDs, coverage, accounting blockers, or memory-observation context fail on lawful current inputs.

## Production decision

`NO_PRODUCTION_CHANGE_APPROVED`

The current fail-closed contracts are preserved:

- exact manifest identity keys and `M = C = A`;
- typed source-honest temporal authority;
- no holder transport after either pre-holder defect;
- no fabricated timestamp, identity, request, response, or holder pass.

## Corrected proof method

The next proof must use only current-contract evidence:

1. run the current exact pre-holder identity suite;
2. run the current source-specific temporal-contract suite;
3. run current budget, pacing, maturation, failure-precedence, and memory-admission tests;
4. perform a disposable direct holder-funnel probe with lawful positive-time `FixtureOriginProof` candidates;
5. perform a disposable exact holder-stage fan-out/sealing probe with the real measured GoPlus fixture transport and no network;
6. retain syntax/import, `git diff --check`, and clean detached-worktree checks.

The 17 historical failures remain explicit test-maintenance debt. They are not counted as a current-contract PASS and are not silently hidden or relabelled.

## Money-usefulness contribution

This classification prevents the test suite from pressuring production back toward count-only accounting or invented candidate time. Exact source-cost identity and source-honest time are necessary for trustworthy holder context and clean memory.

## What remains locked

No authorization, provider execution, authoritative database access, Scheduler/lifecycle runtime, memory generation, longer windows, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets, keys, signing, funds, paid APIs, scores, ranks, confidence, weighting, embeddings, or vectors are unlocked.

## Functionality Risks / Setbacks / Efficiency Blockers

- Four historical holder-related test modules still contain superseded fixtures and should be updated in a separately bounded test-maintenance change if desired.
- Passing the corrected current-contract proof will establish checkpoint readiness, not live provider availability or candidate sufficiency.
- No claim of Checkpoint 4 PASS is allowed until the corrected proof completes cleanly.
