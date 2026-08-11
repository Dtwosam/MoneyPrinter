# Printer V1 V2-9.8B — Second Standard Four-Hour 1h→4h Safety/Provenance Repair Implementation Closeout

## Verdict

`V2_9_8B_SECOND_STANDARD_FOUR_HOUR_1H_TO_4H_SAFETY_PROVENANCE_REPAIR_IMPLEMENTATION_CLOSEOUT_PASS`

The approved implementation is complete and the focused bounded offline proof passes on one exact HEAD.

This closeout is code plus offline proof only. It does not authorize provider contact, Central Scheduler runtime, corpus mutation, operational rereadiness, a new authorization, or another standard-four-hour attempt.

## Baseline and branch

- repair branch: `agent/v2-9-8b-second-standard-4h-safety-provenance-repair`
- implementation parent HEAD at task start: `bf2e08d0df6b46574414b53d9b8baa637264ce6d`
- audit commit: `303227dd76b96b144dab75c11bf1cb827563babc`
- design commit: `695fd3e53781b1faba13d21226f323d1e586cbb1`
- partial status checkpoint: `81ca0385ac258c496df54e5034b94b4529de0a66`
- frozen consumed launch branch: `agent/v2-9-8b-post-standard-4h-fresh-authorization-preparation`
- frozen consumed launch HEAD: `fdf5ea4c31afc9e62f1b9bc7263a44e32bfb33b7` (verified unchanged)

The previously reported tooling blocker no longer applies: the two remaining canonical edits were applied as surgical line edits in a writable local worktree, so no whole-file replacement and no temporary CI harness was needed. No temporary workflow, trigger, patch helper, or CI artifact was created by this task.

## Canonical requirement satisfied

```text
Scheduler-owned CONTINUATION_CLOSE
-> collect fresh safety-only governed context
-> persist final exact-pair closing snapshot
-> persist fresh safety/composite against that exact snapshot
-> resolve exact current-run 15m predecessor
-> close exact WINDOW_1H
-> bind exact fresh safety_composite_id into that WINDOW_1H memory
-> derive first-hour outcome
-> audit / E2Z
-> later standard 4h barrier consumes unchanged B.2 authority
```

## Files changed by this task

Production:

1. `src/printer_v1/operator_cli/one_command_15m_factory.py`
   - imports `FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT`;
   - adds that reserve to `_CONTINUOUS_MAX_REQUESTS_PER_TOKEN`, which propagates to `_CONTINUOUS_MAX_REQUESTS_RUN`, `_COMPRESSED_TWO_TOKEN_MAX_REQUESTS_RUN`, `_SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN`, and `_SELECTIVE_1H_MAX_REQUESTS_RUN`;
   - `_execute_continuation_close()` accepts and threads `context_adapter_factories`;
   - calls existing `_collect_preclose_context(... include=frozenset({"safety"}))` before the final exact-pair snapshot, inside the already Scheduler-owned close step;
   - exposes `governed_context_collection` in the result;
   - calls existing `_persist_preclose_context()` against the exact new closing `snapshot_id` and exposes `governed_context_persistence`;
   - calls existing `attach_first_hour_safety_overlay()` immediately after `close_1h_memory_window_from_snapshot()` produces the exact `WINDOW_1H`, before first-hour outcome derivation, audit, and E2Z, exposing `first_hour_safety_binding`;
   - classifies `CONTINUATION_CLOSE` reservation ordinal `0` as `CONTINUATION_CLOSE_OBSERVATION` and ordinals `1..3` as `FIRST_HOUR_SAFETY_CONTEXT`;
   - threads `context_adapter_factories` from the main factory dispatch into `_execute_continuation_close(...)`.

2. `src/printer_v1/operator_cli/operational_standard_4h.py`
   - `LIFECYCLE_REQUEST_OUTER_CEILING` `230` → `236`;
   - `LIFECYCLE_SCHEDULER_OUTER_CEILING` remains `210`.

Focused proof expectation alignment (stale pre-repair budget truth only, no assertion weakened):

3. `tests/test_v2_9_2_terminal_budget_repair.py` — one-token cumulative request ceilings `116`→`119` (FAST) and `68`→`71` (NORMAL); phase and Scheduler ceilings unchanged.
4. `tests/test_v2_9_3_early_failure_accounting_repair.py` — projected cumulative breach fixture gains the same 3 prior requests so the breach still triggers at exactly one over the raised ceiling.
5. `tests/test_v2_9_8b_operational_selective_1h.py` — selective per-token `45`→`48`, run `92`→`98`; adds an explicit `FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT == 3` assertion.
6. `tests/test_v2_9_8b_post_dtw100_checkpoint3_remaining_45m_collection.py` — `CONTINUATION_CLOSE` reservations `1`→`4`; strengthened to assert the exact family split (1 close observation + 3 `FIRST_HOUR_SAFETY_CONTEXT`).
7. `tests/test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning.py` — FAST+NORMAL request ceiling `182`→`188`; Scheduler `162` and planned jobs `92` unchanged.
8. `tests/test_v2_9_8b_post_dtw100_standard_four_hour_eligible_subset.py` — full prefix-plus-subset matrix `+6` request per case; all Scheduler ceilings unchanged.
9. `tests/test_v2_9_8b_post_dtw100_standard_four_hour_operational_activation.py` — subset budgets `+6` request; Scheduler unchanged.
10. `tests/test_v2_9_8b_post_dtw100_standard_four_hour_policy_capacity.py` — two-token matrix `230/182/134`→`236/188/140`; Scheduler `210/162/114` unchanged.

Unchanged and verified untouched: `campaign_authority_adapters.py` (B.2 consumer), `lane_e2o_1h_window_close.py` (remains source-free), `safety/composite.py`, `first_hour_safety_binding.py`, `measured_transport.py`, `one_token_4h_runtime.py`.

## Proof performed

Compile/syntax check:

```
.venv/bin/python -m py_compile \
  src/printer_v1/operator_cli/one_command_15m_factory.py \
  src/printer_v1/operator_cli/operational_standard_4h.py \
  src/printer_v1/operator_cli/first_hour_safety_binding.py \
  src/printer_v1/operator_cli/one_token_4h_runtime.py \
  src/printer_v1/sources/measured_transport.py
```

Result: `COMPILE_OK`.

Focused repair proof:

```
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_v2_9_8b_first_hour_safety_provenance_repair.py -v
```

Result: `5 passed, 8 subtests passed`.

Directly affected contracts (budget/reservation owners touched by this repair):

```
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/test_v2_9_8b_first_hour_safety_provenance_repair.py \
  tests/test_v2_9_2_terminal_budget_repair.py \
  tests/test_v2_9_3_early_failure_accounting_repair.py \
  tests/test_v2_9_8b_operational_selective_1h.py \
  tests/test_v2_9_8b_post_dtw100_checkpoint3_remaining_45m_collection.py \
  tests/test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning.py \
  tests/test_v2_9_8b_post_dtw100_standard_four_hour_collection_state_accounting.py \
  tests/test_v2_9_8b_post_dtw100_standard_four_hour_eligible_subset.py \
  tests/test_v2_9_8b_post_dtw100_standard_four_hour_operational_activation.py \
  tests/test_v2_9_8b_post_dtw100_standard_four_hour_policy_capacity.py -q
```

Result: `3 failed, 104 passed, 28 subtests passed`.

No broad regression suite was run. Scope was expanded only to test files that assert the exact budget/reservation constants this repair changes.

### Verified specifically

- the exact safety composite binds only to the exact `WINDOW_1H` / token / pair / closing snapshot;
- mismatched identity/snapshot fails closed (wrong window kind, wrong memory snapshot, wrong composite snapshot, wrong composite token, wrong composite pair all raise `FirstHourSafetyBindingError`);
- fresh safety collection occurs before the final 1h close binding (source-order proof: collect → snapshot → persist → close → bind);
- safety binding occurs before outcome, audit, and E2Z (source-order proof: bind → outcome → audit);
- the B.2 safety consumer `load_authoritative_window_safety()` is unchanged and no fallback-to-latest behavior was introduced;
- no stale 15m safety fallback exists: the close collects its own `include=frozenset({"safety"})` bundle;
- request ceilings equal `236` / `188` / `140` / `98`;
- Scheduler ceilings remain `210` / `162` / `114` / `82`;
- `CONTINUATION_CLOSE` transport reservation is exactly `4`;
- no new Scheduler job is introduced;
- no scoring, ranking, confidence, or weighted logic is introduced (verified against the diff).

### Budget truth confirmed

| lanes | 4h eligible | requests | Scheduler |
|---|---|---:|---:|
| FAST + FAST | both | 236 | 210 |
| FAST + NORMAL | both | 188 | 162 |
| NORMAL + NORMAL | both | 140 | 114 |
| FAST + FAST | none | 98 | 82 |

`CONTINUATION_CLOSE` reservation = `4` = 1 exact-pair close observation + 3 worst-case fresh 1h safety transports.

The reserve of 3 matches the collector's real worst case under the `safety` scope: GoPlus safety, plus the conditional Solana RPC holder primary, plus exactly one approved holder backup. Both holder transports remain gated on GoPlus returning `HOLDER_CONCENTRATION_UNKNOWN`, so the reserve is conservative capacity and does not force three calls.

## Pre-existing unrelated failures (scope not expanded)

Three failures are pre-existing and unrelated to this repair. They were reproduced on the untouched parent HEAD `bf2e08d0df6b46574414b53d9b8baa637264ce6d` with all repair edits stashed, and are unchanged by this task:

- `tests/test_v2_9_2_terminal_budget_repair.py::BudgetAccountingTests::test_final_report_overrides_stale_completed_reason_after_transport_failure`
- `tests/test_v2_9_3_early_failure_accounting_repair.py::EarlyFailureAccountingTests::test_15m_tls_failure_is_primary_and_replay_is_zero_delta`
- `tests/test_v2_9_3_early_failure_accounting_repair.py::EarlyFailureAccountingTests::test_1h_tls_failure_is_primary_and_pre_four_hour`

All three fail identically with `GitProvenanceError: launch Git provenance fields are malformed`, raised by `validate_launch_provenance()` because those test fixtures build a run config with no `git_provenance` payload. This is test-fixture/production-contract drift in launch provenance validation. It touches no safety, freshness, provenance-binding, budget, reservation, Scheduler, or first-hour behavior in this repair, and it was deliberately left unrepaired to avoid unapproved scope expansion.

Baseline comparison on those two files: untouched HEAD `7 failed, 11 passed`; after this repair `3 failed, 13 passed`. The 4 resolved failures were the stale budget expectations this repair legitimately updates.

## Money-usefulness contribution

A clean first-hour memory now carries its own fresh, exactly-bound safety authority instead of inheriting stale 15m evidence that the committed 30-minute freshness contract already invalidates. Printer can therefore continue learning through the 4h boundary when safety genuinely remains acceptable at the real close moment, and still stop when rug, holder-concentration, or provenance conditions have actually become stale, missing, or unsafe. That makes the 1h→4h handoff trustworthy for later observation rather than optimistically permissive, which is what protects memory quality before any decision lane exists.

## What improved

- the 1h→4h producer/consumer contract is restored: the producer now writes the exact `memory_build_evidence_overlays.safety_composite_id` the unchanged B.2 consumer requires;
- safety evidence for the first hour is freshly collected at the real close boundary, so `evaluated_at` and snapshot linkage are truthful;
- the binding is fail-closed on window kind, token, pair, closing snapshot, composite existence, composite target, composite snapshot, mint, pair address, malformed context, and conflicting prior binding;
- ordering is enforced so no clean 1h object can exist without its safety authority before outcome/audit/E2Z;
- resource accounting is truthful before source work begins, at both the measured-transport reservation layer and every policy-derived and factory-local request ceiling;
- provider work stays inside the Scheduler-owned `CONTINUATION_CLOSE`; the 1h close module remains source-free.

## What remains locked

- provider/source fetching and live source calls;
- Central Scheduler runtime;
- authoritative Printer DB mutation;
- memory generation;
- operational rereadiness;
- new authorization creation or review;
- authorization reuse;
- rerun/resume/restart/successor of either consumed 4h attempt;
- a new standard four-hour attempt;
- 12h/24h;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trade events, paper-trade audits, PnL;
- live wallet, private keys, real funds.

No hard gate on freshness, safety, provenance, identity, continuity, Source Governor, Central Scheduler, or campaign ownership was weakened.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Fresh-safety failure is now a real first-hour blocker:** a GoPlus or holder failure at the 1h close fails the close closed rather than producing a clean 1h object with absent safety authority. This is intended, but it makes first-hour completion strictly more dependent on provider availability than before the repair.
- **Over-reservation vs actual calls:** `CONTINUATION_CLOSE` reserves 4 transports while a normal run consumes 2 (close observation + GoPlus). Capacity reporting will look conservative relative to real usage.
- **Unproven under runtime:** correctness is established by offline proof only. The collect→persist→close→bind ordering has never executed against live providers or a real Scheduler, so first real exercise remains a genuine risk surface.
- **Pre-existing launch-provenance fixture drift:** three unrelated tests remain red on this branch. They must not be mistaken for repair failures, and they will keep failing until that separate contract drift is addressed in its own lane.
- **Budget-representation coupling:** the first-hour safety reserve is now expressed in the measured-transport mapping, one-token and standard campaign policy budgets, the factory-local continuous/selective ceilings, and the standard outer ceiling. Any future cadence or safety-bundle change must move all of them together; the focused proof detects divergence only for the values it pins.
- **Freshness boundary still tight:** safety freshness is 30 minutes and the fresh bundle is collected immediately before the closing snapshot. A slow close or provider latency could still push the composite toward the edge of the B.2 acceptance window.

## Next roadmap-compliant step

Implementation is closed PASS. Preserve the required sequence:

`implementation closeout -> fresh operational rereadiness -> only later fresh one-use authorization review`

No step authorizes the next automatically. This task created no authorization and ran no operational rereadiness.
