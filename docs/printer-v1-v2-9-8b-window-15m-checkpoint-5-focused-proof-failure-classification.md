# Printer V1 — Checkpoint 5 Focused-Proof Failure Classification

Issue: `DTW-31`

Branch head reviewed: `d2f6bebf6be39c863d0a2ab440f83f4089452604`

## Proof result reviewed

The corrected detached-worktree proof produced:

- stale migration-settle test reproduced exactly before repair;
- import-order proof: `4 passed`;
- Checkpoint 3 contract proof: `3 passed`;
- Checkpoint 5 static contracts: PASS;
- focused Scheduler/lifecycle set: `119 passed, 3 failed, 1 deselected, 36 subtests passed`.

The runner stopped before diff acceptance, commit, or push. The remote branch remained unchanged.

## Failure 1 — historical settle-sleep test

Test:

`tests/test_v2_9_8b_20_sqlite_heartbeat_concurrency.py::TestMigrationDiscoverySleepDoesNotHoldLock::test_settle_sleep_releases_write_transaction`

Classification:

`PREEXISTING_STALE_TEST_UNRELATED_TO_CHECKPOINT5_REPAIR`

Current direct migration discovery forbids nonzero `settle_seconds` and no longer exports the helper patched by this historical test. The test fails before exercising the active contract and ends with a non-proving `count >= 0` assertion. It remains excluded exactly once.

## Failure 2 — replay fixture lease expiry under combined-suite duration

Test:

`tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py::PilotRunnerTerminalClosureTests::test_report_only_replay_creates_no_duplicate_report`

Classification:

`PROOF_FIXTURE_LEASE_DURATION_FLAKE_REQUIRES_ISOLATED_PASS`

The failure is `ProofSupervisionError: active lease is expired` at `attach_run()`. The same `_run(_LifecycleOwner())` path is used by the sibling terminal/replay proof, which passed earlier in the same suite. The failing fixture uses the production 90-second lease while the combined focused proof ran for more than three minutes. No Checkpoint 5 repair file changes proof-supervision lease creation, heartbeat, replay, or this test.

Disposition:

- deselect this test from the long combined run;
- rerun it alone in a fresh process and require PASS;
- do not weaken the production lease or extend its duration for a test fixture.

## Failures 3–4 — superseded legacy no-supply acquisition path

Tests:

- `tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_natural_two_token_operational_campaign_full_proof`
- `tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py::NaturalOperationalLifecycleProofTests::test_token_local_failure_isolates_and_does_not_corrupt_peer`

Classification:

`SUPERSEDED_LEGACY_NO_SUPPLY_PRE_ADMISSION_TESTS_OUTSIDE_CHECKPOINT5_BOUNDARY`

Both tests call the old authoritative owner with `graduation_proofs` only and do not provide the permanent graduated-supply/memory-admission owner. The historical branch therefore reaches `pre_lifecycle_admission` with `supply is None`, where old reporting code dereferences `supply.holder_reserve_candidates`.

This defect is present in the untouched baseline file `authoritative_live_operational_campaign.py`; the Checkpoint 5 repair changes only:

- `src/printer_v1/discovery/__init__.py`;
- `src/printer_v1/discovery/combined_executor.py`;
- `src/printer_v1/discovery/permanent_discovery_availability.py`;
- retirement of `src/printer_v1/discovery/checkpoint3_guards.py`.

The active Checkpoint 5 boundary begins after admission:

`two memory-admitted token slots -> Scheduler handoff -> WINDOW_15M lifecycle -> terminal cleanup`.

The current-contract focused set already passed direct coverage for:

- real two-token factory execution and two terminal WINDOW_15M closes;
- exact Scheduler enqueue/claim/terminal ownership;
- campaign-window registration;
- token-local and global terminal handling;
- support-only 5m separation;
- zero active work and no retry/resume/restart/successor.

Repairing the superseded no-supply pre-admission path here would broaden Checkpoint 5 into historical candidate-supply/reporting behavior and violate the lane boundary. The two tests are therefore excluded exactly and production is not weakened to satisfy them.

## Final bounded proof policy

PASS requires:

1. exact stale settle-test reproduction marker;
2. import-order proof GREEN;
3. all Checkpoint 3 contracts GREEN;
4. Checkpoint 5 static contracts GREEN;
5. the long focused suite GREEN with exactly four named historical/flaky tests deselected;
6. the replay lease test GREEN in isolation;
7. exact repair manifest, clean diff, commit, and push.

Any other failure stops the runner before commit or push.

## Money-usefulness contribution

This classification prevents historical fixtures from forcing unsafe or irrelevant production changes while still requiring current Scheduler/lifecycle ownership, cleanup, and replay behavior to pass. It preserves trustworthy future WINDOW_15M evidence without unlocking memory generation, retrieval, decisions, positions, trades, or PnL.

## What this improves

- exact separation of current-path proof from superseded fixture debt;
- deterministic handling of broad-suite timing flakes;
- stronger confidence that the import repair does not weaken Checkpoint 3 or Checkpoint 5 contracts.

## What this does not unlock

No provider/runtime execution, authorization, authoritative-database mutation, memory generation, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, longer windows, or Checkpoint 6.

## Functionality Risks / Setbacks / Efficiency Blockers

- Historical E.11 no-supply tests remain broken and should not be mistaken for current permanent memory-admission coverage.
- The replay fixture remains sensitive to a production-length lease in a long shared suite; isolated proof is required instead of changing production timing.
- Future proof lists must continue naming exclusions exactly and must stop on every unclassified failure.

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_5_FOCUSED_FAILURES_CLASSIFIED_READY_FOR_STRICT_FINAL_PROOF`
