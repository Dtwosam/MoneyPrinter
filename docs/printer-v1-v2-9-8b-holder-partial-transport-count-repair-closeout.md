# V2-9.8B Holder Partial Transport Count Repair Closeout

Date: 2026-08-04

Lane: `V2-9.8B — Holder Partial Transport Count Repair`

Baseline branch: `grok/v2-9-8b-holder-partial-accounting-repair`
Baseline HEAD: `bb9277b65c53c1db7d3af1053fa50a1c15d9400b`
Lane branch: `grok/v2-9-8b-holder-partial-transport-count-repair`

## Verdict

`V2_9_8B_HOLDER_PARTIAL_TRANSPORT_COUNT_REPAIR_PASS`

Offline fixture-only. No providers, discovery runtime, Scheduler runtime, authorization, `WINDOW_15M`, memory generation, retrieval, decisions, positions, trades, audits, or PnL were run.

## The exact undercount defect

`persist_bundle_attempts()` captured a durable request identity before any operation that can raise, so a governed `printer_source_requests` row could not disappear. But when a later execution's holder-evidence persistence raised, the typed partial it built erased every transport count that real executions had already proven:

```python
for item in coverage:
    blocked = dict(item)
    blocked["terminal_status"] = "BLOCKED"
    blocked["transport_identity_count"] = 0     # proven work erased
    blocked["normalized_member_count"] = 0
    blocked_coverage.append(blocked)
...
measured_transport_count=0,                     # proven total erased
```

Two consequences on a real partial attempt:

* every preserved coverage entry reported `transport_identity_count=0`, including executions whose authoritative measured metadata had already proven a non-zero count, and including executions that had already been persisted successfully in the same pass;
* `HolderBundlePersistResult.measured_transport_count` was hard-coded to `0`, so `_evaluate_holder_eligibility()` charged **zero** transports to the campaign ledger for work that really consumed transport operations.

The failing execution itself was also never measured before the raising evidence-table operation, so even its own proven count was unavailable to the partial.

The result was a systematic transport undercount exactly on the fail-closed path — the campaign ledger under-consumed its operation ceiling, and the holder reservation looked cheaper than the work that had actually been performed. The request-identity half of the earlier repair was correct; the transport-count half was not.

## Production owner changed

| File | Change |
|---|---|
| `src/printer_v1/operator_cli/holder_reliability_budget_control.py` | `persist_bundle_attempts()` measures each execution with `_measure_holder_transport_count()` **before** any evidence-table operation that can raise, and preserves that proven count into the typed partial; `_blocked_coverage_entry()` gains `transport_identity_count`; the partial's `measured_transport_count` is now the exact sum of the preserved coverage counts instead of `0` |

Exactly one production module changed. No other production owner needed a change: `_evaluate_holder_eligibility()` in `authoritative_live_operational_campaign.py` already charged `partial_result.governed_request_count` and `partial_result.measured_transport_count` to the campaign ledger — it was being handed a zero.

No migration. No provider, fallback, Source Governor, or Central Scheduler policy changed.

## Before / after partial accounting behaviour

Scenario: two genuine governed executions, measured `1` and `2`; the first persists; holder evidence persistence raises on the second.

| Surface | Before | After |
|---|---|---|
| `partial.source_request_ids` | both preserved | both preserved (unchanged) |
| coverage `terminal_status` | both `BLOCKED` | both `BLOCKED` (unchanged) |
| coverage `transport_identity_count` | `0`, `0` | `1`, `2` |
| coverage `normalized_member_count` | `0`, `0` | `0`, `0` (unchanged) |
| `partial.governed_request_count` | `2` | `2` (unchanged) |
| `partial.measured_transport_count` | `0` | `3` |
| `partial.accounting_blocker` | `True` | `True` (unchanged) |
| stage / ledger transports charged | `0` | `3` |

A persistence failure may change an execution's coverage terminal to `BLOCKED`; it no longer erases transport counts already proven by authoritative measured metadata.

Required invariant, now enforced by construction:

```text
partial measured transport total
=
sum of all transport counts proven from the preserved real executions
```

Zero is used only for an execution whose measurement is itself absent, invalid, negative, or contradictory — the same `_measure_holder_transport_count()` rules as the complete path (`HOLDER_TRANSPORT_IDENTITY_ABSENT`, `HOLDER_TRANSPORT_COUNT_INVALID`, `HOLDER_TRANSPORT_COUNT_NEGATIVE`, `HOLDER_TRANSPORT_IDENTITY_COUNT_MISMATCH`, `HOLDER_TRANSPORT_IDENTITIES_MISSING`). Nothing is inferred from source names, response presence, RPC method names, or provider type. Alias keys pointing at the same execution object stay de-duplicated, so a preserved count is never counted twice.

## Preserved coverage transport counts

On the proven two-execution partial:

```text
request A  terminal_status=BLOCKED  transport_identity_count=1  normalized_member_count=0
request B  terminal_status=BLOCKED  transport_identity_count=2  normalized_member_count=0
partial.governed_request_count   = 2
partial.measured_transport_count = 3
```

On a mixed measured/unmeasured partial:

```text
request A  transport_identity_count=1   (measured)
request B  transport_identity_count=0   (measurement absent)
partial.measured_transport_count = 1
partial.accounting_blocker       = True
```

## Exact ledger proof

`_evaluate_holder_eligibility()` is driven directly with two candidates whose GoPlus fixtures carry measured counts `1` and `2`, with failure injected only in holder evidence persistence for the second candidate. The stage starts from a zero-operation ledger (`build_ledger(pump_operations=0, ...)`), so the returned ledger delta is the charge:

```text
result.ledger.underlying_transport_operations == 3     # not 0
result.ledger.governed_requests              == 2
result.measured_transport_count              == 3
result.governed_request_count                == 2      # not double-charged
sorted(coverage transport_identity_count)    == [1, 2]
```

Every reported ID is verified to be a genuine durable `printer_source_requests` row. The partial is charged exactly once — the recovery path in `_evaluate_holder_eligibility()` consumes the typed partial rather than re-persisting an already-persisted result.

## Tests and counts

New focused proof: `tests/test_v2_9_8b_holder_partial_transport_count_repair.py` — **14 passed**.

TDD order: all 14 were written before the production change; 8 failed against `bb9277b` on exactly the undercount assertions (`transport_identity_count`, `measured_transport_count`, ledger delta, and the campaign/readiness surfaces), 6 passed as unchanged-behaviour guards. All 14 pass after the repair.

| # | Proof | Result |
|---|---|---|
| 1 | second execution's persistence raises a typed `HOLDER_BUNDLE_PERSIST_INCOMPLETE`; both durable rows really exist | pass |
| 2 | both durable request IDs preserved | pass |
| 3 | both coverage entries `BLOCKED` with `normalized_member_count=0` | pass |
| 4 | preserved transport counts remain `1` and `2` | pass |
| 5 | partial `measured_transport_count == 3`, equal to the sum of preserved counts | pass |
| 6 | partial `governed_request_count == 2` | pass |
| 7 | `_evaluate_holder_eligibility()` adds exactly `3` transports (and `2` requests) to its returned ledger | pass |
| 8 | holder context / diagnostics expose measured transport count `3`, coverage counts `[1, 2]`, all IDs durable | pass |
| 9 | `PILOT_INPUT_READINESS` reconciliation still `BLOCKED` on the partial attempt, with the preserved count reaching the campaign surfaces | pass |
| 10 | `SNAPSHOT_READINESS` still attempts zero readiness bundles (`assert_not_called`, zero `printer_token_snapshots`), status `BLOCKED_HOLDER_ACCOUNTING`, preserved count exposed | pass |
| 11 | a genuinely unmeasured execution stays transport count `0` and sets the accounting blocker | pass |
| 12 | a measured source failure with complete accounting preserves its count (`accounting_blocker=False`, `BLOCKED` coverage keeps its count) | pass |
| 13 | alias executions remain de-duplicated (one ID, one coverage entry, count `2` once) | pass |
| 14 | no lifecycle, memory, retrieval, decisions, positions, trades, audits, or PnL occur | pass |

Tests 1–6, 11, 13 use two genuine governed executions with real `printer_source_requests` rows created through `execute_source_request_with_governor`, injecting failure only inside holder evidence persistence (`record_attempt`). Tests 7, 8, 14 drive the real `_evaluate_holder_eligibility()` collection path; tests 9, 10 drive the real `PILOT_INPUT_READINESS` and `SNAPSHOT_READINESS` owners. No proof is satisfied with a prebuilt `HolderBundlePersistResult` or `HolderContextResult`.

Directly affected holder ledger, reconciliation, campaign, and snapshot-readiness suites (20 files including the new one): **251 passed, 27 subtests passed, 16 pre-existing failures**.

Pre-existing failures confirmed unchanged against the baseline `bb9277b` (identical set, identical count, verified by re-running the same five files with the production change stashed):

* `test_v2_9_8b_campaign_accounting_terminal_enforcement.py` — 7 (6 parametrised post-handoff fault compensation + `test_normal_success_two_slots_two_window_15m_jobs`);
* `test_v2_9_8b_19_production_readiness_consolidation.py` — 6 (canonical migration ledger, action-local blocked counters, preflight zero surface, backup/restore corpus shape);
* `test_v2_9_7e_28_readiness_contract_preflight.py::test_geckoterminal_contract_is_conditional_exact_and_zero_retry`;
* `test_v2_9_7e_33_canonical_readiness_boundary.py::CanonicalModeSurfaceTests::test_activation_only_dispatch_starts_no_lifecycle`;
* `test_v2_9_6_safety_context_source_redundancy.py::SafetyContextSourceRedundancyTests::test_goplus_holder_disagreement_is_blocking`.

Scope was not expanded to chase them, per the risk-based verification policy.

Other checks:

| Check | Result |
|---|---|
| `compileall` (1 changed production module + 1 new test module) | OK |
| `git diff --check` | OK |

No live sources and no unrelated full suite were run.

## Schema result

No migration. No new table, column, or index. Existing `printer_source_requests`, `printer_holder_evidence_attempts`, and `printer_holder_campaign_operation_ledgers` only. `HolderBundlePersistResult`, `HolderContextResult`, and all report/diagnostics JSON surfaces keep their existing shape — only the values inside `transport_identity_count` and `measured_transport_count` are now honest on a partial attempt. `_blocked_coverage_entry()` gains one keyword-only parameter with a `0` default, so its existing call shape is unchanged.

## Money-usefulness contribution

The campaign operation ledger is the machine's spend accounting. A holder stage that really performed transport work but reported zero made the ceiling, the holder reservation, and the remaining budget look larger than they were. Every downstream decision that reads the ledger — candidate cap, reservation checks, deadline pacing, permanent-availability exhaustion — was being made against an understated bill, and precisely on the failure path, where an operator most needs the truth. The repair makes a partial holder attempt cost exactly what it really cost: the operator sees the same durable IDs and `BLOCKED` terminals as before, plus the real transport total behind them, so budget exhaustion arrives honestly instead of late. It creates no new evidence and softens no gate — an unmeasured execution still contributes zero and still blocks.

## What remains locked

Freeze depth `4`, surplus target `8`, liquidity floor `$3,000`, ceiling `30`, reservations `3/2/6/7/8/4`, holder evidence as `MEMORY_OBSERVATION` context, the `FUTURE_ACTION` holder gate, provider and fallback selection, Source Governor and Central Scheduler ownership, retrieval and trading locks, clean-memory creation, paper decisions, BUY/SELL/HOLD, positions, trade events, paper audits, PnL, live execution, wallets, private keys, paid APIs, scoring/ranking/confidence/weighted logic, embeddings/vectors, authorization, and `WINDOW_15M`.

## Remaining risks

* Charging the real transport total on a partial attempt consumes the operation ceiling and the holder safety reservation faster than the previous undercount did. A repeatedly-failing holder source will now reach `PERMANENT_DISCOVERY_HOLDER_SAFETY_RESERVATION_EXCEEDED` sooner. That is the intended fail-closed correction, not a regression, but any budget expectation calibrated against the undercounted behaviour will shift.
* The measurement now runs twice per execution on the success path (once before persistence, once inside `_persist_one_holder_attempt()`). Both calls use the same pure helper over the same normalized payload, so they cannot disagree, but a future change to `_measure_holder_transport_count()` must stay pure or the two call sites must be collapsed.
* If the execution record itself is unreadable, the pre-measurement falls back to `0` and the attempt still blocks. Evidence is degraded but never invented.
* Fixture adapters that bypass a source normalizer must still attach measured transport metadata when they participate in the holder path; otherwise the stage correctly fails closed with a zero count. This lane adds no new tolerance for that.
* The 16 pre-existing failures listed above remain open and outside this lane.

## Next offline integrated fixture-transport proof

The narrowest useful next lane is unchanged in shape and now provable end-to-end for counts as well as identities:

```text
locator → direct pump → gecko → backup → market → protocol → holder
→ durable/stage/coverage ID equality including a partial holder attempt
→ transport-count equality: ledger total == sum of all stage coverage counts
→ accounting-complete source failure vs incomplete measurement vs partial attempt
→ MEMORY_OBSERVATION readiness or durable mismatch / accounting terminal
→ stop before lifecycle
```

## Commit subject

`Preserve partial holder transport counts`

Do not push. Do not authorize or run a live campaign.
