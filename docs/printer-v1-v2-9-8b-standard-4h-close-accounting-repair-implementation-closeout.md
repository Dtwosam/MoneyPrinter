# Printer V1 V2-9.8B Standard-4h Close/Accounting Repair — Implementation Closeout

## Scope and baseline

- Branch: `agent/v2-9-8b-standard-4h-close-accounting-repair`.
- Starting implementation HEAD: `a33fb6b9de1ceba6ab44f199cc5a2886ef5622d8`.
- Root-cause classification: `COMMITTED_CODE_DEFECT`.
- Approved design: `docs/printer-v1-v2-9-8b-standard-4h-close-authority-terminal-accounting-repair-design.md`.
- Fifth standard-4h authorization remains permanently consumed.
- No sixth authorization was created or prepared.

This lane used only local source edits, static inspection, compilation, and disposable/in-memory tests. It did not contact a provider, fetch a source, run a campaign, execute the Memory Factory, or mutate the authoritative database.

## Verdict

`V2_9_8B_STANDARD_4H_CLOSE_ACCOUNTING_REPAIR_IMPLEMENTATION_PASS`

Both committed defects are repaired on the exact branch, and the focused proof plus the nearest directly affected regressions pass.

## Test-first RED evidence

Command:

```text
.venv/bin/python -m pytest tests/test_v2_9_8b_standard_4h_close_accounting_repair.py -q
```

Expected RED result before production edits:

```text
ImportError: cannot import name '_load_terminal_scheduler_correspondence' from
'printer_v1.operator_cli.campaign_full_run_accounting'
1 error in 0.10s
```

Pytest exited 2 during collection. This was the committed missing-repair surface, not a provider/runtime failure.

## Defect A result — explicit final-close authority

PASS.

- `close_current_run_4h()` now accepts and validates the existing `FourHourExecutionAuthority` contract.
- Missing, disabled, or invalid authority fails before predecessor resolution.
- The standard factory caller carries `STANDARD_CAMPAIGN`; the proof caller carries `PROOF`; ordinary/non-authorized execution carries `DISABLED`.
- Only a valid scoped 4h authority enables the already-existing `WINDOW_4H` predecessor resolution at final close.
- The global `allow_enabled_successor_planning=False` default is unchanged.
- The close owner remains fixed to `WINDOW_4H`; this repair grants no `WINDOW_12H` or `WINDOW_24H` authority.

## Defect B result — terminal Scheduler correspondence

PASS.

- Existing `SNAPSHOT`/`WINDOW_CLOSE` source accounting, four mandatory sealed stages, six-unit evidence, cadence proof, and 15m memory accounting remain unchanged.
- Ordinary campaigns still construct the correspondence family from only `WINDOW_15M` lifecycle steps and retain the historical eighteen-job family acceptance contract.
- Standard campaigns dynamically add persisted `WINDOW_1H` and eligible `WINDOW_4H` lifecycle steps only when their exact factory run, campaign, campaign run, cycle, Scheduler job, token, pair, slot, window kind, stage, target category, and target identity reconcile.
- Duplicate, missing, mismatched, non-succeeded, or unexplained owned Scheduler work remains fail-closed.
- Standard Scheduler-family attribution uses the exact observed authorized lifecycle count rather than hard-coded `18`.
- Scheduler retry bookkeeping remains visible as `scheduler_retry_count`, but is no longer represented as a campaign-level automatic retry. Automatic retry, restart, resume, successor, bound-run, terminal-state, ownership, and active-work checks remain independent.
- Runtime terminal completion remains an independent acceptance predicate; command/process exit 0 cannot manufacture campaign PASS or proof success.

## GREEN verification

Focused repair:

```text
.venv/bin/python -m pytest tests/test_v2_9_8b_standard_4h_close_accounting_repair.py -q
8 passed in 0.07s
```

Direct accounting, wiring, and exact 4h-close owner regressions:

```text
.venv/bin/python -m pytest tests/test_v2_9_8b_standard_4h_close_accounting_repair.py tests/test_v2_9_8b_full_run_accounting_semantics_correction.py tests/test_v2_9_8b_full_run_wiring_integration.py tests/test_v2_8_1_one_token_4h_runtime.py::OneToken4hRuntimeTests::test_clean_close_runs_e2q_lane_q_lane_k_and_is_idempotent tests/test_v2_8_1_one_token_4h_runtime.py::OneToken4hRuntimeTests::test_historical_snapshot_between_ids_is_not_cadence_evidence -q
40 passed, 6 subtests passed in 12.56s
```

Nearest standard-4h planning, collection-state, close-memory, and terminal reconciliation regressions:

```text
.venv/bin/python -m pytest tests/test_v2_9_8b_post_dtw100_standard_four_hour_close_memory_terminal_reconciliation.py tests/test_v2_9_8b_post_dtw100_standard_four_hour_collection_state_accounting.py tests/test_v2_9_8b_post_dtw100_standard_four_hour_campaign_planning.py -q
37 passed in 10.35s
```

Changed production modules also passed `py_compile`; the repository diff passed `git diff --check`.

## Unrelated pre-existing verification result

The first whole-file run of `tests/test_v2_8_1_one_token_4h_runtime.py` reported `6 passed, 2 subfailures`. Both subfailures are the existing `test_budget_and_plans_are_exact_and_real_collection_is_explicit` assertions that expect real 4h collection to be disabled for `TRACK_FAST` and `TRACK_NORMAL`, while the already-committed cadence policy reports it enabled. This repair does not modify `runtime_budget` or cadence policy. The two directly affected close tests from that file pass and the unrelated assertion was not weakened or brought into scope.

## Money-usefulness contribution

The repair prevents a valid standard four-hour lifecycle from collecting useful governed evidence and then failing solely because approved close authority was dropped or legitimate owned 1h/4h Scheduler work was misclassified as extra ownership. It does not increase collection scope or authorize a run.

## Preserved locks / not touched

- No source fetching, provider calls, runtime campaign, Memory Factory run, or authoritative DB mutation.
- No authorization creation, replacement, retry, or sixth authorization.
- No Source Governor or Central Scheduler bypass or ownership weakening.
- No source-budget, cadence, ceiling, provider-policy, or collection-capacity change.
- No `WINDOW_12H`/`WINDOW_24H` activation.
- No retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL.
- No wallet, private key, real-fund, live-execution, paid-API, scoring, ranking, confidence, weighting, vector, or embedding capability.

## Functionality Risks / Setbacks / Efficiency Blockers

- The new standard correspondence deliberately depends on the persisted run configuration and exact ownership/window rows; malformed or incomplete lineage blocks rather than falling back to permissive classification.
- Scheduler retry count is now observability rather than campaign-retry truth. Failed, unresolved, retry-wait, active, mismatched, or nonterminal work must continue to be caught by their independent terminal gates.
- The unrelated cadence-policy expectation in the older whole-file test remains a separate baseline maintenance issue and does not affect this repair proof.
- A broad suite was not run because the production changes are confined to the approved owners and the risk policy requires minimum sufficient verification.

## Stop condition

Implementation and focused proof are closed PASS. Proceed only to the separate read-only post-repair rereadiness review. Do not create or prepare an authorization and do not run a standard-4h campaign.
