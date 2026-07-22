# V2-9.7E.14 Real-Wall-Clock Pilot Runner and Supervision — Closeout

**Status:** IMPLEMENTATION AND OFFLINE PROOF COMPLETE

**Verdict:** `V2_9_7E_14_REAL_WALL_CLOCK_PILOT_RUNNER_PASS`

## Exact baseline

- Commit: `8de1ff4501ad68f2284996b59aa3a0671e4aa535`
- Message: `Close final two-token pilot preflight blocker`
- HEAD verified equal to the authorized baseline; clean tracked tree; no stash;
  E.11 implementation, E.12 readiness proof and E.13 preflight closeout present;
  no active campaign, runner, lease or stale pilot process.

No live provider was contacted. The E.13 pilot authorization remains
**unconsumed**.

## Runner-gap findings (Phase 1)

`AuthoritativeLiveOperationalCampaignOwner.run_operational` is invoked today only
by the E.11 test suite, always with fixture adapters and a compressed
deterministic clock; the committed live harness is readiness-only. Tracing a real
invocation showed the entire supervision/backup/report/replay surface already
exists and is tested:

- target/backup/migration/integrity: `proof_db_schema_readiness.prepare_proof_db`
  (`PRAGMA integrity_check`, `PRAGMA foreign_key_check`, byte-identical backup,
  persistent-unchanged);
- ownership graph: `campaign_persistence.create_campaign` +
  `campaign_ownership.create_campaign_run`;
- Git provenance: `git_provenance.validate_launch_provenance` (dirty → error);
- lease/lock/heartbeat/stop/host-recovery/finalize:
  `proof_supervision.{create_execution, attach_run, heartbeat_active_lease,
  request_cooperative_stop, cooperative_stop_reason, inspect_execution,
  recover_abandoned_execution, stop_execution, finalize_execution_from_report}`;
- report + zero-source replay: `one_command_15m_factory.load_report_only`.

The only genuinely missing artifact was **one composition** binding these to the
E.11 two-token `run_operational` under real canonical timing, plus a disposable
restore rehearsal and a terminal-relaunch refusal. No second campaign or
lifecycle owner was created; the E.11 owner remains the sole operational
authority.

## Final ownership and launch architecture

```text
prepare_pilot_target(paths)                  # migrate, integrity/FK, byte-identical
  -> byte-identical backup, restore rehearsal #   backup, disposable restore rehearsal,
  -> no active/foreign lease                  #   fail closed on any gap
validate_launch_provenance(provenance)        # dirty tracked tree blocks
refuse-relaunch-if-execution-present          # never rerun/restart a known execution
create_execution(...)                         # single active proof, lock, target==backup
build_pilot_command(...)                      # campaign/config/run/cycle graph
HeartbeatWorker.start()                       # durable periodic heartbeat (real thread)
owner.run_operational(..., lifecycle_kwargs)  # EXACTLY ONE campaign, real timing
HeartbeatWorker.stop()
attach_run + finalize_execution_from_report   # one immutable terminal cause, lock freed
load_report_only(target, run_id)              # deterministic zero-source replay
```

The E.11 owner is invoked exactly once. Supervision reuses `proof_supervision`
end to end. `create_execution` runs before `build_pilot_command` so its
byte-identical target/backup check sees the freshly prepared target.

## Files changed

- `src/printer_v1/operator_cli/two_token_operational_pilot_runner.py` — the
  pilot-only composition module (importable, testable; no CLI registration).
- `scripts/v2_9_7e_14_two_token_operational_pilot.py` — an **unregistered**
  operator-run pilot script (not in `pyproject.toml`; not the V2-9.8 command).
- `tests/test_v2_9_7e_14_two_token_operational_pilot_runner.py` — the focused
  offline proof.
- `docs/printer-v1-v2-9-7e-14-real-wall-clock-pilot-runner-design.md` — design.
- `docs/printer-v1-v2-9-7e-14-real-wall-clock-pilot-runner-closeout.md` — this.

## Target / backup / report contract

`prepare_pilot_target` fails closed unless every one holds: all paths present,
non-empty and mutually distinct; target/backup never the authoritative corpus
(unless a never-set authorization flag); persistent source copied to the target
and migrated through the canonical repository head; integrity and foreign-key
checks pass; the persistent source is byte-unchanged; a fresh byte-identical
backup is written; the backup is **restored onto a disposable copy, validated,
hash-confirmed and removed**; and no active/foreign lease exists in the target
(`printer_proof_run_supervision` STARTING/RUNNING or
`printer_memory_factory_campaign_supervision` ACTIVE/STOPPING). The runner never
guesses a path. The report directory identity is bound into the command.

## Timing and supervision contract

**Real timing is structural.** Production lifecycle kwargs contain only
`total_duration_seconds` (the 4.25 h envelope), `cancellation_probe` and
`launch_provenance`. They set none of `_window_seconds`,
`_continuation_seconds`, `_sleep`, `_monotonic`, `snapshot_adapter_factory`,
`fallback_snapshot_adapter_factory` or `context_adapter_factories`, so the
factory's real 900 s / 2700 s / 4 h / `time.sleep` / live-adapter defaults apply.
A guard rejects any forbidden key, and the runner exposes **no** production
parameter to compress 15m/1h/4h/5m/lease/heartbeat timing. Tests inject a fake
owner at the runner→owner seam, never a clock into the production configuration,
so a test clock cannot leak into a live run.

**Supervision** reuses `proof_supervision`: single-process ownership and one
active proof; bounded lease with a durable periodic `HeartbeatWorker`
(monotonic advance); immutable first terminal cause; cooperative stop surfaced to
the run as a `cancellation_probe`; safe host-disappearance handling (recovery
requires an expired lease and an absent process); read-only local status; a
terminal report exactly once; zero-source replay; and no automatic restart or
successor — a relaunch that finds a known execution refuses to rerun.

## Status, stop and replay behavior

- `pilot_status` → `inspect_execution` (read-only, `source_calls: 0`,
  `scheduler_calls: 0`).
- `request_pilot_stop` → `request_cooperative_stop` (zero source/Scheduler
  calls); the run observes it via the cancellation probe and safe-stops to one
  immutable terminal cause.
- `pilot_report_only_replay` → `load_report_only` (deterministic,
  `new_source_calls: 0`).

## Focused offline proof

`tests/test_v2_9_7e_14_two_token_operational_pilot_runner.py` — **13 passed**,
covering proofs 1–19:

| # | Proof | Test |
|---|---|---|
| 1,2 | mandatory + unambiguous paths block before mutation | `test_missing_or_ambiguous_paths_block_before_mutation` |
| 3 | backup + disposable restore rehearsal pass | `test_backup_and_restore_rehearsal_pass` |
| 4 | migration/integrity/FK failure blocks | `test_migration_or_integrity_failure_blocks` |
| 5 | dirty Git provenance blocks | `test_dirty_git_provenance_blocks` |
| 6 | active/foreign lease blocks | `test_active_or_foreign_lease_blocks` |
| 7,14,16,17,18,19 | one invocation; no restart/successor; report once; deterministic zero-source replay; zero pending/lease; zero retrieval/financial deltas | `test_exactly_one_invocation_report_replay_and_clean_terminal` |
| 8,9 | production receives real canonical timing; no clock leak | `test_production_invocation_receives_real_canonical_timing`, `test_production_lifecycle_kwargs_reject_compression` |
| 10 | heartbeat durable over a long simulated process (240 ticks / 2 h) | `test_heartbeat_advances_monotonically_over_a_long_process` |
| 11 | status read-only, zero source/Scheduler calls | `test_status_is_read_only_with_zero_calls` |
| 12 | cooperative stop → one immutable terminal cause | `test_cooperative_stop_reaches_one_immutable_terminal_cause` |
| 13 | host disappearance fails closed when process alive | `test_host_disappearance_fails_closed_when_process_alive` |
| 15 | relaunch against terminal execution refuses | `test_relaunch_against_terminal_execution_refuses` |

Proof 20 (E.11 operational invariants remain green) and the required related
surfaces:

- `test_v2_9_7e_11_authoritative_live_operational_campaign.py` — **40 passed**.
- `test_v2_9_1_proof_db_schema_readiness.py`, `test_v2_9_4_durable_supervision.py`,
  `test_v2_9_7d_6b_7_zero_source_read_only_replay.py`,
  `test_v2_9_7b_4_heartbeat_lease_reliability.py` — **32 passed**.
- `test_v2_9_7d_2a_campaign_persistence.py`,
  `test_v2_9_7d_3a_identity_state_validation.py`,
  `test_v2_9_7d_6b_5_operational_lease_safe_stop.py` — **37 passed**.

`git diff --check` clean; module and script compile and import; the runner is
unregistered in `pyproject.toml`.

## Money-usefulness contribution

The lane removes the exact blocker E.13 documented: it delivers a committed,
reviewed, fail-closed way to launch the two-token operational pilot on real
timing with durable supervision, a byte-identical backup and rehearsed restore,
cooperative stop, local observability, and deterministic zero-source replay.
This makes the eventual authorized pilot safe to attempt and safe to interrupt,
protecting both the authoritative corpus and the single pilot authorization while
adding zero financial or retrieval surface.

## What the lane improves

- Closes the E.13 executability gap with a real-wall-clock, uncompressible
  operational entry point that drives the committed E.11 owner exactly once.
- Adds a disposable restore rehearsal and a terminal-relaunch refusal on top of
  the existing, proven supervision machinery.
- Proves the launch/supervision contract offline (19 runner proofs) while the
  E.11 operational invariants stay green (40 proofs).

## What remains locked

All Printer V1 Solana-only, paper-only, free/public-source, governance,
two-or-none, clean-memory, support-only-5m, and financial/retrieval locks remain
unchanged. No CLI entry point was registered, no operator command was published,
no live pilot was run, and no retrieval or financial capability was unlocked.

## Proof still required before V2-9.7F

- One operator-authorized execution of this runner against live free-public
  sources on real wall-clock timing, either proving the two-token operational
  invariants end to end (both 15m closes, barrier, selective natural 1h/4h
  continuation, conditional support-only 5m, exactly one authoritative clean
  promotion, report/replay/cleanup, zero forbidden deltas) or blocking honestly,
  with any natural case the single live campaign does not produce reported
  honestly.
- Ideally a prior readiness cycle in which the bounded secondary-enrichment lanes
  succeed, so governed secondary facts are exercised alongside the finalized
  origin.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Risk:** the real pilot is a single, market-dependent, up-to-~4.25 h run under
  one non-renewable authorization; some natural cases (e.g. an eligible
  support-only 5m capture) may legitimately not occur and must be reported as
  absent, not manufactured.
- **Setback:** the durable heartbeat runs on a background thread inside the
  runner process; a hostile host kill is still covered by the existing
  host-disappearance recovery, but an external sidecar heartbeat (as in the prior
  PowerShell launcher) remains the more robust option for a very long run.
- **Efficiency blocker:** none in the runner; the intrinsic cost is the real
  multi-hour wall-clock lifecycle, which is deliberate (no compression).

## Readiness for one final pilot attempt

**READY to attempt one final authorized two-token operational pilot.** The
committed runner provides a fail-closed, real-wall-clock, single-invocation,
fully-supervised launch path proven offline. The pilot itself is **not run here**
and requires its own separate explicit operator authorization. V2-9.7F, V2-9.8,
the operational memory-growth command, and retrieval/decision/financial
capabilities remain locked and were not started.
