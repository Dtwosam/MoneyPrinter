# Printer V1 V2-9.8B Post-DTW100 First-Hour Lifecycle Policy Implementation + Focused Proof Closeout

## Verdict

```text
V2_9_8B_POST_DTW100_STANDARD_FIRST_HOUR_LIFECYCLE_POLICY_IMPLEMENTATION_FOCUSED_PROOF_PASS
```

This PASS is scoped to the approved first-hour policy change: an otherwise-valid activated token no longer needs a 15m outcome/learning-need qualification to continue from `WINDOW_15M` through the `WINDOW_1H` observation horizon.

It is **not** an operational WINDOW_1H readiness verdict and does not authorize a live/bounded first-hour run. A separate pre-existing operational selective-1h harness/authority-readiness issue was exposed during verification and must be audited before the one-use authorization/wrapper lane proceeds.

## 1. Baseline and branch

- Design/source-stack closeout baseline: `2966cd23712462f79fbca0f7ed9a847e496470ae`
- Implementation branch: `agent/v2-9-8b-post-dtw100-first-hour-lifecycle-policy-implementation`
- Pre-closeout implementation/proof head: `f09340b6eb8119dd1c1188917b2e6a102f5d47c0`
- No production migration was added.
- No authoritative database was opened or mutated.
- No provider/source/RPC call, Scheduler runtime, memory generation, authorization creation, wrapper invocation, or operational 15m/1h run occurred.

## 2. Implemented behavior

Primary owner changed:

- `src/printer_v1/scheduler/token_local_continuation.py`

For exact `WINDOW_15M -> WINDOW_1H`, after the existing hard validity gates pass:

1. token budget must still be available;
2. the verdict is `CONTINUE_TO_WINDOW_1H`;
3. the reason is `standard_first_hour_lifecycle`;
4. `learning_need` is not consulted.

The following existing hard gates remain before that decision:

- exact campaign/configuration/slot/token/mint/pair/lifecycle/predecessor identity;
- supported window transition;
- token not cancelled or terminal;
- eligible token state;
- predecessor window closed;
- predecessor memory/evidence/data quality gates;
- `do_not_train` protection;
- evidence completeness/freshness/provenance;
- mandatory safety context;
- exact continuity;
- shared campaign/DB/lease/integrity health;
- campaign and token budget.

A market outcome is not an operational failure. `NO_PUMP`, `CONSOLIDATION`, pump/dump/dead/revival direction, profitability, scoring, ranking, confidence, weighting, and 5m support do not decide first-hour continuation.

For exact `WINDOW_1H -> WINDOW_4H`, the previous selective logic and ordering remain unchanged: no learning need produces `STOP_AFTER_WINDOW_1H`; an applicable learning need is required before token budget can authorize later continuation.

## 3. Test-first RED evidence

The first policy-test commit was:

- `673e857057c71c112ccc36862d6dcb4466890a4b`

Disposable draft PR #76 ran the focused zero-runtime workflow against that exact pre-implementation head and was closed unmerged.

RED workflow:

- run: `31339091360`
- job: `93309780101`
- compile: PASS
- pure policy tests: 13 run, exactly 2 failures
- both failures were the new first-hour assertions:
  - expected `CONTINUE_TO_WINDOW_1H`
  - observed old `STOP_AFTER_WINDOW_15M`
- operational step skipped after the intended RED failure.

This proves the new tests actually detected the retired qualification behavior before production code changed.

## 4. Implementation correction during review

The first implementation temporarily moved token-budget evaluation ahead of the transition-specific branch. Diff review caught that this would alter the established `WINDOW_1H -> WINDOW_4H` ordering when there is no learning need.

That out-of-scope change was corrected before final proof. Current behavior preserves the old later-window order exactly while applying the token-budget check before unconditional first-hour continuation only for `WINDOW_15M -> WINDOW_1H`.

## 5. Focused GREEN proof

The final scoped proof head was:

- `f09340b6eb8119dd1c1188917b2e6a102f5d47c0`

Disposable draft PR #79 used a zero-runtime workflow from a separate runner-only branch and was closed unmerged.

GREEN workflow:

- run: `31339447474`
- job: `93310697988`
- checkout verified exact head `f09340b6eb8119dd1c1188917b2e6a102f5d47c0`
- Python compile of changed policy + focused tests: PASS
- `tests/test_v2_9_7d_4a_token_local_selective_continuation.py`: 13/13 PASS
- `tests/test_post_dtw100_first_hour_lifecycle_policy.py`: 4/4 PASS

The 4-test composition proof uses the real operational `_learning_need_from_window` helper together with the real token-local policy and proves:

- `NO_PUMP` and `CONSOLIDATION` still derive `learning_need=None`, yet both valid tokens continue to `WINDOW_1H`;
- transition outcomes such as `SHORT_TERM_PUMP` and `DUMP` continue under the same standard first-hour reason rather than gaining special authority;
- token-budget and identity failures still fail closed;
- support-only `WINDOW_5M_MICRO_EVENT` cannot authorize a 1h transition;
- `WINDOW_1H -> WINDOW_4H` with no learning need still stops at 1h.

Total scoped GREEN assertions: 17 tests, 0 failures, 0 errors.

## 6. Pre-existing comprehensive operational harness failure

An initial attempt to use the historical comprehensive `tests/test_v2_9_8b_operational_selective_1h.py` as the GREEN gate failed broadly. Systematic debugging did not assume the new policy caused it.

A disposable untouched-baseline comparison was therefore run on design baseline code plus a trigger-only documentation commit:

- baseline comparison PR #78, closed unmerged;
- baseline run `31339220095`;
- job `93310120329`;
- compile: PASS;
- pure historical policy tests: 13/13 PASS;
- comprehensive operational suite: 32 tests, 10 failures + 1 error.

Failures on the untouched baseline included historical cases that should already have continued under the old policy, such as DUMP/SLOW_BLEED, plus B.1/authority-linked continuation, campaign-window creation/reporting, and a standalone E2Z 1h promotion fixture.

Therefore those failures pre-date this policy change. They are not repaired or hidden in this lane. A temporary 23-line expectation edit to that old test file was removed from the implementation branch; the final implementation diff does not modify that comprehensive file.

Classification for next work:

```text
PRE_EXISTING_OPERATIONAL_SELECTIVE_1H_HARNESS_OR_AUTHORITY_INTEGRATION_DRIFT_REQUIRES_READ_ONLY_AUDIT
```

This classification does not yet decide whether the root cause is stale fixtures/tests, current B.1/B.2 authority-contract drift, E2Z fixture drift, or a current production integration defect. That determination belongs to the next audit/readiness lane.

## 7. Final implementation diff scope

Relative to design/source-stack closeout `2966cd23712462f79fbca0f7ed9a847e496470ae`, the pre-closeout implementation/proof head changed exactly four files:

- added `docs/printer-v1-v2-9-8b-post-dtw100-first-hour-lifecycle-policy-implementation-plan.md`;
- modified `src/printer_v1/scheduler/token_local_continuation.py`;
- modified `tests/test_v2_9_7d_4a_token_local_selective_continuation.py`;
- added `tests/test_post-dtw100-first-hour-lifecycle-policy.py` equivalent repository path `tests/test_post_dtw100_first_hour_lifecycle_policy.py`.

No disposable workflow or baseline-trigger file is present on the implementation branch.

## 8. Source-stack amendment status

The controlling design and design/source-stack closeout explicitly supersede the older active-stack clause that made `WINDOW_15M -> WINDOW_1H` depend on a behavior/learning-need qualification. The repository assistant alignment anchor was also updated in the design lane.

Older selective-1h documents remain preserved as historical evidence. They must not be read as current authority for the 15m->1h outcome gate after this amendment.

Core source documents were not wholesale replaced through the GitHub contents API because the repository versions are newer than the uploaded copies and replacing large current files from stale copies would risk destructive source-stack regression. The later committed amendment is deliberately narrow: only the 15m->1h behavior qualification is superseded; later-window selectivity and all V1 locks remain.

## 9. Money-usefulness contribution

Printer can now retain a standard first-hour learning horizon for every otherwise-valid activated token rather than filtering the corpus at minute 15 based on a coarse early outcome label. This improves future learning about delayed pumps/dumps, consolidation breaks, collapse/recovery, revival, and genuinely quiet full-hour behavior without unlocking any paper action.

## 10. What this improves

- removes the 15m outcome/learning-need qualification gate;
- preserves hard operational/evidence/safety/resource gates;
- preserves 1h->4h selectivity;
- preserves 5m non-authority;
- provides actual RED/GREEN proof for the changed policy and its immediate operational outcome adapter seam.

## 11. What this still does not unlock

- operational first-hour readiness;
- fresh one-use first-hour authorization;
- one-shot first-hour wrapper execution;
- source fetching or Scheduler runtime;
- authoritative DB mutation or operational memory generation;
- 4h/12h/24h activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper audits, or PnL;
- live wallet, keys, real funds, execution, paid APIs;
- scoring/ranking/confidence/weighted logic, embeddings, or vectors.

The earlier post-DTW100 one-use first-hour authorization/wrapper integration blocker remains unresolved.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Current control | Next proof needed |
|---|---|---|
| First-hour spend now reaches the bounded two-token worst case by policy | Existing token/campaign budget gates preserved | re-derive exact current Source Governor/Scheduler ceilings before authorization |
| Pre-existing operational selective-1h comprehensive harness is red | excluded from this scoped policy gate only after untouched-baseline comparison | read-only audit of current B.1/B.2/E2Z/fixture contract drift |
| Old selective terminology may imply an outcome gate | later design/source-stack amendment supersedes that clause | future docs/authorization must use standard-first-hour semantics |
| Dirty evidence could be confused with observation eligibility | existing evidence-quality gates were not weakened in this implementation | later operational audit must keep quality and observation semantics explicit |
| 5m could accidentally gain authority | unsupported 5m->1h transition proof passes | retain exclusion in later operational tests |
| Later windows could become automatic by drift | 1h->4h no-learning-need STOP proof passes | keep 4h+ locked/selective until explicit lanes |

## 13. Correct next lane

Do **not** proceed directly to authorization preparation.

The newly exposed pre-existing failures change rereadiness evidence. The next roadmap-correct lane is:

```text
V2-9.8B Post-DTW100 First-Hour Operational Harness / Authority Integration Current-State Audit
```

Type: read-only / offline audit.

It should determine, without production runtime or authoritative DB mutation, why the untouched current comprehensive selective-1h suite blocks cases that historical closeouts expected to continue, and classify each failure as stale fixture/test drift versus current code/integration defect.

Only after that audit and any required design/repair/proof closeout should Printer return to the separate one-use first-hour authorization/wrapper integration design. No authorization may be created before then.
