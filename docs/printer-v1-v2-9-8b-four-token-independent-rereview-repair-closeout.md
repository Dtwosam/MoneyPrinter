# Printer V1 V2-9.8B Four-Token Independent Rereview Repair Closeout

Date: 2026-08-13

## Verdict

`V2_9_8B_FOUR_TOKEN_INDEPENDENT_REREVIEW_REPAIR_PASS_READY_FOR_REREVIEW`

This closes only the two blockers in
`printer-v1-v2-9-8b-four-token-independent-rereview.md`: through-4h cycle
accounting completeness and canonical two-phase terminal integration. It does
not authorize migration readiness, migration 055 application, an operational
proof, authorization, runtime, or any financial capability.

## Identity and resumed state

- Repository: `Dtwosam/MoneyPrinter`
- Branch:
  `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`
- Rereview baseline: `c0280996d932aaae46695ec3dc5a59098313345a`
- Resumed working-tree HEAD: `8236a0f` (accounting RED/GREEN and terminal RED
  already committed; terminal GREEN in progress)
- The untracked operator artifact at
  `operator-runs/v2-9-8b-standard-four-hour-final-authorization/` remained
  untouched and untracked.

## RED and GREEN commits

### Through-4h cycle accounting completeness

- RED: `11b886a2c53726ea57a9f38ab3643d7c508e931c`
- Exact failure: the opening-only cycle expected
  `FourTokenFactoryAdapterError("canonical lifecycle accounting is incomplete")`,
  but pytest reported `DID NOT RAISE`.
- GREEN: `b00afcd` — `fix: require complete four-token cycle accounting`

The production adapter now calls the owner-local, read-only
`project_cycle_lifecycle_accounting_completeness(...)` projection. That
projection reuses the existing full-run stage owner, canonical standard-4h
eligibility manifest validator, exact cycle-scoped Scheduler ownership,
durable 15m/1h/4h campaign-window and physical-window correspondence, cadence
policy, quality consistency, and slot disposition. It does not copy a required
stage set or invent a second accounting policy. Per-cycle capacity remains 2.

The positive fixture builds a real disposable 15m -> 1h -> 4h graph using the
canonical opening, anchored, first-hour, and standard-four-hour planners. Gate
H calls `build_four_token_cycle_accounting_package(...)` twice over two
independently built durable complete graphs. Its second disposable graph is
re-keyed before projection so the durable cycle, targets, and factory-step
identities are distinct; neither returned package is edited or synthesized.

### Canonical two-phase factory terminal integration

- RED: `8236a0f` — `test: expose missing four-token factory terminal integration`
- Exact failure, both terminal shapes:
  `TypeError: run_one_command_15m_factory() got an unexpected keyword argument
  'four_token_shared_terminalizer'`.
- GREEN: `4da964887f6a1c223e78aa736b6c7eda33f48ffa` —
  `fix: integrate four-token terminal ownership`

The actual canonical factory `finally` path now performs:

1. Phase A `reconcile_four_token_cycle_terminal(...)` once for every admitted
   cycle, without terminalizing shared run/campaign/lease state.
2. Phase B `finalize_four_token_shared_terminal(...)` once, through the
   operational composition's existing supervision cleanup and unified campaign
   terminal owners, only after every admitted cycle is terminal and all owned
   work is inactive.

Two exact terminal shapes are accepted:

- exact cycle ordinals 1 and 2, both terminal;
- exact cycle ordinal 1 plus one durable proposed-cycle-2 attempt terminalized
  as `NO_PAIR`, `BLOCKED`, `FAILED`, or `CANCELLED`, with a non-empty first
  cause and no consumed cycle.

The one-cycle `NO_PAIR` path preserves its exact cause only after existing
cycle-1 lifecycle work drains. It ends `TERMINAL_BLOCKED` / `SAFE_STOPPED`,
creates no cycle 2, and cannot retry, restart, or create a successor. The exact
two-cycle completion ends both cycles and the shared campaign run
`TERMINAL_COMPLETED`, with the factory row `COMPLETED`.

The public/two-token controller-absent path retains its legacy terminal flow.

## Files changed from the rereview baseline

- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
- `src/printer_v1/operator_cli/four_token_factory_adapter.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/operational_memory_factory_command.py`
- `src/printer_v1/operator_cli/unified_terminal_closure.py`
- `tests/test_v2_9_8b_four_token_cycle_accounting_adapter.py`
- `tests/test_v2_9_8b_four_token_factory_terminal_integration.py`
- `tests/test_v2_9_8b_four_token_factory_wake_ordering.py`
- `tests/test_v2_9_8b_four_token_gate_h_integrated_disposable.py`
- this closeout

## Focused verification

Fresh final integrated prerequisite set:

```text
183 passed, 31 subtests passed in 33.04s
```

This included all `tests/test_v2_9_8b_four_token_*.py`, directly affected
full-run accounting tests, and focused standard-four-hour handoff, planning,
collection-state accounting, policy-capacity, factory-barrier, and close
accounting tests.

Additional focused evidence during GREEN:

```text
Terminal integration: 2 passed
Accounting adapter + Gate H: 9 passed
Complete four-token set: 76 passed, 22 subtests passed
Direct terminal-owner callers: 17 passed, 8 subtests passed
```

All touched production modules pass `py_compile`. `git diff --check` passes.

The known unrelated compressed-time baseline failure reproduces unchanged:

```text
tests/test_v2_4_one_command_15m_factory.py::
OneCommand15mFactoryTests::
test_continuous_first_hour_path_terminally_safe_blocks_compressed_time

continuation_1h.step_status: actual FAILED, expected SUCCEEDED
```

One wider diagnostic run produced `101 passed, 30 subtests passed, 16 failed`.
Those failures are pre-existing fixture/assertion drift outside this repair:

- six migration-ledger assertions remain hard-coded to 49 while the canonical
  disposable ledger contains 55 migrations;
- legacy natural-campaign and pre-lifecycle coordinator heartbeat fixtures do
  not expose the already-required `failure_event` interface;
- two legacy blocked-action envelope fixtures no longer reach their asserted
  action-local counters because of current preflight/fixture drift.

No such test was weakened or changed.

## Locks and operational activity

- No migration was added or applied.
- Migration 055 was not applied to the authoritative operational database.
- The authoritative operational database was not opened or mutated.
- No live source request or real Scheduler runtime operation occurred.
- No operational four-token proof, runtime, or authorization was started.
- No 12h/24h, retrieval, decision, BUY/SELL/HOLD, position, trade, audit, or
  PnL capability was touched.
- `TOKEN_CAPACITY` and `expected_token_capacity` remain exactly 2.
- Provider ceilings remain unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- The accounting adapter intentionally fails closed if durable stage,
  manifest, Scheduler, source, quality, physical-window, or slot-disposition
  evidence is missing, extra, or ambiguous. A future lawful ownership shape
  requires an explicit canonical-owner update.
- Gate H uses two separate disposable databases to prove independently
  complete per-cycle packages. The aggregate contract intentionally shares the
  durable factory identity string while requiring distinct targets and
  factory-step identities across those projected packages.
- Existing stale migration, heartbeat-fixture, action-envelope, and
  compressed-time baselines remain visible. They do not mask a failure in the
  focused repair set, but they reduce the usefulness of a broad suite until
  repaired in their own authorized lanes.

## Stop boundary

Stop for independent rereview. Do not begin migration readiness,
authorization, operational proof, factory runtime, or any later capability.
