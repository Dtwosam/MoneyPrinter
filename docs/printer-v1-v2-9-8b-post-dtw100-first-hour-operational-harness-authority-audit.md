# Printer V1 V2-9.8B Post-DTW100 First-Hour Operational Harness / Authority Integration Current-State Audit

## Verdict

```text
V2_9_8B_POST_DTW100_FIRST_HOUR_OPERATIONAL_HARNESS_AUTHORITY_AUDIT_BLOCKED_FIXTURE_AND_REPORTING_ALIGNMENT_DESIGN_REQUIRED
```

The current first-hour continuation policy itself is not disproven by the historical comprehensive suite failures. Most failures are caused by stale proof fixtures that predate the current canonical clean-object contract. One current production reporting defect is also confirmed: hard first-hour continuation blocks can be summarized as `ZERO_ELIGIBLE_CONTINUATIONS`, which is no longer truthful after the standard-first-hour policy amendment.

This is an audit-only closeout. It does not authorize implementation, runtime, source fetching, Scheduler work, authoritative DB mutation, memory generation, authorization creation, wrapper execution, `WINDOW_15M`, `WINDOW_1H`, or longer-window operation.

## 1. Baseline and lane boundary

- Exact audit baseline: `cf8876faccdc85abdab8b388dcec029421cbf4b4`
- Baseline branch: `agent/v2-9-8b-post-dtw100-first-hour-lifecycle-policy-implementation`
- Audit branch: `agent/v2-9-8b-post-dtw100-first-hour-operational-authority-audit`
- Immediate predecessor verdict: `V2_9_8B_POST_DTW100_STANDARD_FIRST_HOUR_LIFECYCLE_POLICY_IMPLEMENTATION_FOCUSED_PROOF_PASS`
- Required current behavior: every otherwise-valid activated token continues from `WINDOW_15M` through `WINDOW_1H`; 15m outcome/learning-need labels have no authority to stop the first-hour observation.
- `WINDOW_1H -> WINDOW_4H` remains selective until its later explicit policy lane.

Allowed here: static inspection, Git/history comparison, prior CI/log review, retained artifact/document review, and this audit document.

Not allowed here: production code/test/schema changes, migrations, source/provider calls, Scheduler runtime, authoritative DB writes, memory generation, authorization/wrapper work, or live/bounded lifecycle execution.

## 2. Why the audit was required

During the preceding first-hour policy implementation proof, the historical comprehensive suite

`tests/test_v2_9_8b_operational_selective_1h.py`

ran 32 tests and produced 10 failures plus 1 error on an untouched pre-policy baseline. The same file had previously been part of the July 28 selective-1h comprehensive repair proof, where a 12-module focused package passed 170 tests plus 28 subtests.

Therefore the current red state is post-proof contract drift and must be classified instead of being attributed blindly to the new standard-first-hour policy.

## 3. Historical proof versus current contracts

### 3.1 Historical comprehensive harness is unchanged

The historical operational test file has the same blob SHA at the July 28 repair commit and at the current baseline:

```text
fe7e1a95fc327ac3e1b22992f541affa398d1cc9
```

So the suite itself was not maintained as later clean-memory contracts evolved.

### 3.2 B.1/B.2 adapter file is also unchanged

`src/printer_v1/operator_cli/campaign_authority_adapters.py` has the same blob SHA at the historical repair commit and current baseline:

```text
e09cf97d2ddd361dbb7a44f3adadd1513ccd486f
```

Its exact campaign/run/cycle/token-slot/window identity checks, exact close-step requirement, and B.2 safety validation have not drifted.

### 3.3 The authoritative clean-promotion contract did evolve

`src/printer_v1/operator_cli/one_command_15m_factory.py` changed after the historical proof.

Historical `_authoritative_promotions_for_run()` accepted an eligible clean `printer_episodes` row joined to a run step.

Current `_authoritative_promotions_for_run()` requires the clean episode to be joined to exactly the canonical clean fingerprint contract:

- `fingerprint_kind='STATIC_CONDITION_SUMMARY'`
- `memory_status='CLEAN_MEMORY'`
- `data_quality_label='CLEAN_DATA'`
- `do_not_train=0`

This is consistent with the current product lifecycle, which builds episodes and memory fingerprints, and with DTW100, which produced clean window IDs 163/164, episode IDs 60/61, and fingerprint IDs 24/25.

## 4. Primary root cause: stale episode-only fixture

The historical `Selective1hFixture.prepare_eligible()` manually constructs predecessor authority by:

1. inserting safety;
2. inserting a `WINDOW_15M` row;
3. manually inserting a `CLEAN_MEMORY` episode;
4. writing a synthetic close-step E2Z result;
5. persisting the campaign window.

Its `insert_episode()` creates no canonical `printer_memory_fingerprints` row.

Under the current B.1 contract, that episode-only object is intentionally not an authoritative clean promotion. Consequently:

- `_authoritative_promotions_for_run()` returns no clean promotion for the fixture window;
- B.1 reports no authoritative episode;
- `build_4a_authority_facts()` makes the predecessor evidence ineligible / `DO_NOT_TRAIN`;
- the continuation policy correctly returns `BLOCK_CONTINUATION` before any market-outcome continuation semantics matter;
- no `WINDOW_1H` campaign window is persisted.

This stale fixture explains the main failure cascade, including the historical continuation, idempotency, reporting, barrier, and 1h-binding assertions.

Classification:

```text
STALE_FIXTURE_DRIFT — NOT A CONFIRMED B.1/B.2 PRODUCTION DEFECT
```

The repair must use the current canonical clean-object owner rather than restoring episode-only authority.

## 5. E2Z 1h fixture drift

The historical `test_e2z_promotes_clean_1h_once` also predates the current atomic clean-object promotion contract.

Current `create_clean_memory_from_window()` delegates to `memory.clean_object_promotion.promote_clean_object()`, which atomically creates or verifies:

- one exact clean episode; and
- one exact canonical fingerprint.

It also requires a known, non-empty, non-`OUTCOME_UNKNOWN` outcome and verifies exact window/token/pair/window-kind and fingerprint identity/outcome consistency.

The old test constructs a `WINDOW_1H` candidate without an `outcome_label` and expects old episode-only promotion. Current E2Z correctly blocks that incomplete candidate.

Classification:

```text
STALE_E2Z_FIXTURE_DRIFT — NO CURRENT E2Z CORE DEFECT ESTABLISHED
```

The repair proof must construct a genuine current 1h candidate with a truthful known outcome and exercise the canonical episode+fingerprint owner. It must not weaken E2Z to make the old fixture pass.

## 6. B.2 safety status

The early safety-focused tests in the historical comprehensive module continue to exercise the current adapter successfully before the continuation cascade:

- exact producer null-lineage safety is accepted;
- wrong composite, target identity, pair, closing snapshot, memory-window linkage, stale evidence, conflicted evidence, blocked evidence, and missing source trace fail closed.

No current B.2 production repair is justified by this audit.

Classification:

```text
B.2 CURRENT CONTRACT — NO REPAIR EVIDENCE
```

## 7. Standard-first-hour policy makes old behavioral expectations stale

The current policy at the exact baseline explicitly makes `WINDOW_15M -> WINDOW_1H` the standard first-hour lifecycle after hard gates pass. `learning_need` is not consulted for that transition.

Therefore these old comprehensive assertions are no longer valid once their fixtures become truly authoritative:

- `CONSOLIDATION + NO_PUMP -> 0 continuation / 2 STOP`;
- `SHORT_TERM_PUMP + CONSOLIDATION -> exactly one continuation`.

Under current policy, both otherwise-valid tokens continue in both cases.

This is intentional product-policy supersession, not a regression.

Classification:

```text
STALE_SELECTIVE_EXPECTATION — MUST ALIGN TO STANDARD_FIRST_HOUR_POLICY
```

The historical `learning_need` derivation may remain useful as informational memory context, but it must not regain authority over 15m->1h continuation.

## 8. Confirmed current production reporting defect

A separate real defect exists in `src/printer_v1/operator_cli/operational_selective_1h.py`.

Current reporting computes a complete two-token decision set, checks persisted 1h count against `continue_count`, then maps:

- `continue_count == 0` -> `ZERO_ELIGIBLE_CONTINUATIONS`
- `continue_count == 1` -> `ONE_CONTINUATION`
- otherwise -> `TWO_CONTINUATIONS`

It does not distinguish `STOP` from `BLOCK` before assigning the zero-continuation label.

That was already ambiguous under the old selective model. It is now factually wrong under the standard-first-hour model: after hard gates pass there is no normal behavior-driven 15m stop. If an evaluated activated token cannot continue through the first hour, that is an operational/evidence/safety/resource block, not an absence of learning need.

Thus a two-token result with two `BLOCK_CONTINUATION` verdicts and zero 1h windows can currently be reported as:

```text
ZERO_ELIGIBLE_CONTINUATIONS
```

when the truthful meaning is that first-hour continuation was blocked.

Classification:

```text
CONFIRMED_CURRENT_REPORTING_SEMANTICS_DEFECT
```

This must be designed before implementation. The design should distinguish at minimum:

- standard first-hour continuation completed/planned for both valid tokens;
- mixed continuation plus hard block;
- fully blocked first-hour continuation;
- evaluation not reached;
- system/integrity defect.

A normal behavior-driven zero-continuation result must not remain an accepted standard-first-hour outcome.

## 9. Legacy naming and compatibility drift

The current owner and public proof mode still use historical names such as:

- `operational_selective_1h.py`
- `SELECTIVE_1H_POLICY_VERSION`
- `selective-1h-proof`
- `selective_1h_outcome`

These names predate the standard-first-hour amendment.

This audit does not require an unsafe rename. The later design must determine whether to preserve command/module names as compatibility surfaces while introducing truthful standard-first-hour semantics, or to add explicit aliases/migrations without breaking the proven 15m path or future one-use authorization binding.

Classification:

```text
COMPATIBILITY/NAMING_DRIFT — DESIGN DECISION REQUIRED, NOT BLIND RENAME
```

## 10. `STOP_AFTER_WINDOW_15M` current status

The enum/reference still exists for compatibility and older documents/tests. Current exact 15m->1h policy does not return a normal `STOP_AFTER_WINDOW_15M` after all hard gates pass.

A fallback occurrence in `one_command_15m_factory.py` is legacy scheduling/report plumbing for an absent plan; it is not authority to reintroduce behavioral qualification for a valid standard-first-hour token.

The repair design must preserve this distinction and must not allow compatibility code to silently restore the retired outcome gate.

## 11. Failure classification matrix

| Historical current-baseline failure | Primary classification | Required disposition |
|---|---|---|
| `test_authoritative_episode_not_raw_partial_label` | stale episode-only clean fixture | use current canonical episode+fingerprint promotion |
| `test_two_eligible_tokens_fair_bounded_continuation` | stale clean fixture | repair fixture, then assert standard first-hour continuation |
| `test_duplicate_continuation_idempotent` | cascade from stale B.1 fixture | repair fixture and retain idempotency proof |
| `test_conflicting_recomputation_fails_closed_without_replacement` | initial evaluation blocked by stale fixture | repair fixture; preserve immutable-object conflict proof |
| `test_post_success_campaign_barrier_is_close_order_independent` (both orders) | stale B.1 fixture | repair fixture; preserve close-order barrier proof |
| `test_reporting_contains_linkage_and_windows` | stale B.1 fixture plus legacy reporting vocabulary | repair fixture and reporting expectations |
| `test_one_eligible_token_exactly_one_continuation` | stale fixture + superseded selective expectation | both valid tokens should continue under current policy |
| `test_zero_eligible_tokens_zero_continuation` | superseded selective expectation; current fixture also blocked | replace with truthful standard-first-hour cases |
| `test_bind_1h_memory_and_terminalize` | cascade: no 1h campaign window created because predecessor blocked | repair authoritative fixture, then reprove binding |
| `test_e2z_promotes_clean_1h_once` | stale pre-atomic E2Z fixture | construct genuine outcome-bearing 1h candidate and prove episode+fingerprint |

The prior baseline run also exposed reporting behavior that can pass old zero-continuation assertions for the wrong reason. Passing legacy assertions must therefore not be treated as evidence of current correctness.

## 12. Exact repair scope justified by this audit

A later design may cover only the following proven needs:

1. Align the comprehensive first-hour proof fixture with the canonical clean episode+fingerprint contract.
2. Align 15m->1h expectations to the adopted standard-first-hour policy.
3. Repair first-hour reporting so BLOCK cannot masquerade as `ZERO_ELIGIBLE_CONTINUATIONS`.
4. Reprove current E2Z 1h promotion with a genuine outcome-bearing window and canonical fingerprint.
5. Preserve B.1/B.2 exact identity, quality, safety, provenance, continuity, and fail-close requirements.
6. Preserve immutable continuation objects, close-order barrier, idempotency, 1h campaign-window binding, reporting/replay, zero forbidden deltas, and no retry/restart/successor.
7. Decide compatibility-safe naming without requiring a broad module/CLI rename.

Not justified by this audit:

- weakening canonical fingerprint requirements;
- weakening E2Z outcome/integrity checks;
- changing B.2 safety acceptance;
- restoring market-outcome qualification for first-hour continuation;
- adding source calls or retries;
- activating 4h;
- creating authorization or wrapper execution.

## 13. Minimum sufficient future proof

After design and implementation, use a focused offline proof rather than a broad repository suite.

Minimum required checks:

- canonical clean 15m predecessor produces episode + fingerprint and is accepted by B.1;
- two otherwise-valid tokens continue to 1h regardless of `NO_PUMP`, `CONSOLIDATION`, pump, dump, or other market outcome;
- dirty/incomplete/mismatched/unsafe/stale/budget-exhausted predecessors still BLOCK;
- BLOCK is reported as block, not zero learning need;
- two standard continuations create two distinct 1h campaign windows with no ranking/scoring;
- repeated evaluation is idempotent;
- conflicting immutable recomputation fails closed;
- close-order barrier remains order-independent;
- genuine current 1h E2Z candidate creates/recognizes exactly one episode+fingerprint clean object;
- 5m remains support-only;
- 4h+ remain locked during this repair;
- retrieval/paper/financial tables remain unchanged.

Broader regression is not required unless the repair expands beyond these owners.

## 14. Money-usefulness contribution

This audit prevents Printer from mistaking stale test construction for a production learning defect and prevents hard evidence/safety failures from being reported as ordinary lack of learning value. Truthful first-hour authority and reporting are necessary before collecting a less-biased corpus and before extending standard observation toward 4h.

## 15. What this audit improves

- identifies the exact stale clean-object fixture contract;
- separates fixture drift from B.1/B.2 production behavior;
- identifies the stale E2Z 1h fixture contract;
- confirms the new first-hour behavioral expectations that must replace old selective assertions;
- identifies a real reporting-semantics defect;
- narrows the next implementation scope.

## 16. What this audit still does not unlock

- production/test implementation changes;
- operational `WINDOW_1H` readiness;
- selective/standard first-hour one-use authorization;
- wrapper execution;
- source fetching or Scheduler runtime;
- authoritative DB mutation or operational memory generation;
- automatic `WINDOW_1H -> WINDOW_4H`;
- 4h/12h/24h activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, PnL;
- wallets, keys, real funds, live execution, paid APIs;
- scoring/ranking/confidence/weighted logic, embeddings, or vectors.

## 17. Functionality Risks / Setbacks / Efficiency Blockers

| Risk / blocker | Why it matters | Required control / next proof |
|---|---|---|
| Old fixtures manufacture episode-only clean memory | can falsely accuse current B.1 of blocking valid memory | use canonical clean-object promotion in proof fixtures |
| Old 1h E2Z fixture omits truthful outcome | could pressure implementation to weaken clean-memory integrity | preserve current E2Z and build a genuine candidate fixture |
| Legacy zero-continuation reporting conflates STOP/BLOCK | hides safety/evidence/resource failures as normal behavior | design explicit standard-first-hour outcome/report semantics |
| Legacy selective names remain in APIs/artifacts | can confuse future authorization and reporting | compatibility-safe design; no blind rename |
| Standard first-hour uses worst-case two-token continuation budget | future authorization must freeze exact current ceilings | rederive Source Governor/Scheduler totals later, after repair closeout |
| One-use selective/standard first-hour wrapper still absent | direct `--operator-approved` remains insufficient | return to wrapper/authorization design only after operational repair/rereadiness |
| Proposed automatic 1h->4h is not yet operationally proven | changing it now would stack a new capability on an unresolved 1h interface | defer to dedicated standard-four-hour audit after first-hour repair closes |

## 18. Correct next lane

Do not proceed to authorization and do not implement automatic 4h yet.

The next roadmap-correct lane is:

```text
V2-9.8B Post-DTW100 Standard First-Hour Operational Harness / Reporting Alignment Design
```

Type: design/specification only.

It should specify the smallest compatibility-safe fixture and reporting repair described in section 12, preserve current canonical clean-object and safety contracts, define focused RED/GREEN proof requirements, and stop before implementation.

After design -> implementation -> focused proof -> closeout -> fresh first-hour rereadiness, Printer may return to the one-use first-hour authorization/wrapper integration lane. Only after the first-hour operational foundation is clean should the dedicated standard-four-hour current-state audit begin.