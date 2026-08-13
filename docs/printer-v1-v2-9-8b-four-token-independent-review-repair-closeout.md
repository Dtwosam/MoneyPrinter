# Printer V1 V2-9.8B Four-Token Independent-Review Repair Closeout

Date: 2026-08-13

## Verdict

`V2_9_8B_FOUR_TOKEN_INDEPENDENT_REVIEW_REPAIR_PASS_READY_FOR_REREVIEW`

## Scope and starting state

- Repository: `Dtwosam/MoneyPrinter`
- Branch: `agent/v2-9-8b-four-token-bounded-capacity-proof-integration-implementation`
- Starting HEAD: `55bf7d87a4a5277ba28be063359151ee6af4744d`
- The untracked operator authorization artifact under
  `operator-runs/v2-9-8b-standard-four-hour-final-authorization/` was preserved
  untouched.

This repair addressed only the three blockers recorded by the independent
review. Accepted Gates A-G and all capability locks remain in force.

## RED and GREEN commits

### Factory wake ordering

- RED: `1752ed9bbb9d11d7e2f9b591fd398a5aaf959cdd`
- Exact RED: the actual `run_one_command_15m_factory(...)` loop asked its sleep
  boundary for `300.0` seconds while two owned lifecycle jobs were durably due
  in `100` seconds: `assert [300.0] == [100]` failed.
- GREEN: `4f8ea0eccdae03a1c87dfd92332d3616443165d1`

The deferred disposition now passes future lifecycle, lawful admission/rearm,
and proof-deadline boundaries through `next_four_token_factory_wake(...)`.
Future lifecycle work always participates when present, independent of
`recheck_on_lifecycle_change`; lifecycle keeps equal-time priority. No polling
or retry boundary was added.

### Production cycle accounting adapter

- RED: `e2a7484a94847e2c4a84388345fc805cd0758e78`
- Exact RED: focused collection failed because
  `build_four_token_cycle_accounting_package` did not exist and Gate H could
  not import the production adapter.
- GREEN: `7959c7ae52f4f45e951e5c76171d0c56445a5239`

The adapter is read-only and produces one existing aggregate-compatible
two-token package per cycle. Its authority is:

- exact two-slot campaign ownership from durable campaign token slots;
- factory steps exclusively from `cycle_scoped_factory_step_ids(...)`;
- exact Scheduler job/work attribution from `V2_STAGE_SCOPED` lifecycle work;
- source attribution through the existing full-run law
  `factory_run_id:step_key%`, factored into the owner-local
  `load_attributable_lifecycle_source_attempts(...)` helper;
- memory-quality evidence from the exact cycle-owned 15m windows, with
  `NO_PROMOTION` when no owned promoted window exists;
- `expected_token_capacity=2` unchanged.

Missing, extra, cross-owned, or ambiguous step, Scheduler, request, slot, or
window ownership fails closed. Gate H now obtains both cycle packages from this
adapter; it no longer hand-authors accounting counts.

### Operational SQLite owner

- RED: `0b1aa61b1056885f69a5abc0a0be9923262380a6`
- Exact RED: focused collection failed because the later-cycle module had no
  `connect_operational` owner to patch.
- GREEN: `b4049533b5bf2adfb7a7ebeb11df477170e3ebc0`

The later-cycle identity path now uses `connect_operational(...)` and
`short_write_transaction(...)`. Permanent-supply construction, holder evidence
evaluation, evidence canonicalization, hashing, timestamp parsing, and
provenance validation happen before the transaction. The transaction contains
only the two neutral token/pair identity writes. Source lineage is read after
the transaction is released. The focused test observes transaction states
`[True, True]` for identity ownership and `[False]` for lineage reading.

Neutral `token_status=NULL` remains unchanged. The adapter creates no tracking
row, Scheduler job, campaign cycle/window, memory window, or lifecycle
activation.

## Files changed

- `src/printer_v1/operator_cli/campaign_full_run_accounting.py`
- `src/printer_v1/operator_cli/four_token_factory_adapter.py`
- `src/printer_v1/operator_cli/four_token_proof_integration.py`
- `src/printer_v1/operator_cli/later_cycle_graduated_supply.py`
- `tests/test_v2_9_8b_four_token_cycle_accounting_adapter.py`
- `tests/test_v2_9_8b_four_token_factory_wake_ordering.py`
- `tests/test_v2_9_8b_four_token_gate_a_supply_identity.py`
- `tests/test_v2_9_8b_four_token_gate_h_integrated_disposable.py`
- this closeout

## Verification

Focused repair and directly affected four-token, factory, full-run accounting,
and standard-four-hour tests:

```text
157 passed, 31 subtests passed in 23.09s
```

This set included all `tests/test_v2_9_8b_four_token_*.py`, the directly
affected full-run accounting tests, and focused standard-four-hour planning,
capacity, collection-state, factory-barrier, and close-accounting regressions.

Additional owner-specific checks passed during GREEN:

```text
Factory wake/readiness/disposition: 12 passed, 4 subtests passed
Accounting adapter/Gate H/full-run: 43 passed, 6 subtests passed
SQLite owner/callback contracts: 9 passed
```

All touched production modules pass `py_compile`. `git diff --check` passes.

The known unrelated compressed-time baseline failure reproduces unchanged:

```text
tests/test_v2_4_one_command_15m_factory.py::
OneCommand15mFactoryTests::
test_continuous_first_hour_path_terminally_safe_blocks_compressed_time

continuation_1h.step_status: actual FAILED, expected SUCCEEDED
```

Seven additional pre-existing assertions in
`test_v2_9_8b_campaign_accounting_terminal_enforcement.py` still require the
migration head to start with `050`; the committed canonical disposable schema
now ends at migration `055`. Those stale test assertions are unrelated to the
three reviewed blockers and were not weakened or changed.

## Locks and operational activity

- No migration was added.
- Migration 055 was not applied to the authoritative operational database.
- No operational database was opened or mutated by this task.
- No live source request was made.
- No real Scheduler runtime was executed or enqueued.
- No four-token runtime or proof was started.
- No authorization was created, consumed, or modified.
- No 12h/24h, retrieval, decision, position, trade, audit, or PnL capability
  was touched.
- `TOKEN_CAPACITY` and expected per-cycle capacity remain exactly 2.
- Provider ceilings remain unchanged.

## Functionality Risks / Setbacks / Efficiency Blockers

- The new accounting adapter deliberately fails closed on any factory-scoped
  request-key lineage that cannot be attributed to exactly one durable factory
  step. A future lawful source operation with a new request-key ownership shape
  will require an explicit owner update before it can pass accounting.
- The actual-loop wake test uses a disposable database and intercepts the first
  bounded sleep call; it proves canonical event-loop ordering without executing
  live lifecycle collection.
- The unrelated compressed-time baseline failure and stale migration-050 test
  assertions remain visible and documented; neither masks a failure in this
  repair set.

No migration readiness, authorization, or runtime work is authorized by this
closeout. The only next step is independent rereview of this repair.
