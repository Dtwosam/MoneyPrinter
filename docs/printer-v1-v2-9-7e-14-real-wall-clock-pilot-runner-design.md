# V2-9.7E.14 Real-Wall-Clock Pilot Runner — Design

**Status:** FROZEN AFTER INTERNAL REVIEW

**Baseline:** `8de1ff4501ad68f2284996b59aa3a0671e4aa535`

## Todo / Checklist

- [x] Phase 1 — runner-gap audit against `run_operational`.
- [x] Phase 2 — freeze the internal runner contract (this document).
- [ ] Phase 3 — implement the frozen contract.
- [ ] Phase 4 — focused offline proof (no live provider).

## Scope

The E.11 operational owner and lifecycle policy are complete and are NOT
redesigned. The missing capability is exactly one committed, internal,
pilot-only real-wall-clock runner that can drive
`AuthoritativeLiveOperationalCampaignOwner.run_operational` (the two-token
finalized-origin operational owner) against live adapters and real timing, wired
to the existing supervision, backup, report and replay owners.

## Phase 1 — Runner-gap audit

`run_operational` is invoked today only by the E.11 test suite, always with
**fixture** snapshot/context adapters and a **compressed deterministic clock**.
The committed live harness (`scripts/v2_9_7e_11_readiness_cycle.py`) is
readiness-only. Tracing what a real invocation needs, against what already
exists:

| Requirement | Existing owner (reused) | Gap filled by the runner |
|---|---|---|
| approved target creation + identity | `campaign_persistence.create_campaign`, `campaign_ownership.create_campaign_run` | thin composition + explicit path contract |
| migration + integrity/FK validation | `proof_db_schema_readiness.prepare_proof_db` / `validate_runtime_schema` (`PRAGMA integrity_check`, `PRAGMA foreign_key_check`) | invoked by `prepare_pilot_target` |
| pre-run backup + restore rehearsal | `prepare_proof_db` builds a byte-identical backup | **restore rehearsal on a disposable copy** (new step) |
| source configuration | `OneShotUrllibPumpTransport`, `OneShotUrllibSecondaryTransport` | injected as defaults; test-overridable |
| Git provenance | `git_provenance.validate_launch_provenance` (dirty → error) | validated before mutation |
| campaign ownership | `create_campaign` + campaign/run/cycle graph | built by `build_pilot_command` |
| lease acquisition + heartbeat | `proof_supervision.create_execution`, `heartbeat_active_lease` | orchestrated + a durable heartbeat worker |
| process observability | `proof_supervision.inspect_execution` (`source_calls: 0`) | `pilot_status` wrapper |
| cooperative operator stop | `proof_supervision.request_cooperative_stop` / `cooperative_stop_reason` | `cancellation_probe` wired into the run + `request_pilot_stop` |
| final report | `run_one_command_15m_factory` persists `final_report_json` | consumed as the terminal report |
| report-only status + replay | `one_command_15m_factory.load_report_only` (`new_source_calls: 0`) | `pilot_report_only_replay` wrapper |
| cleanup | `proof_supervision.finalize_execution_from_report` / `stop_execution` / `recover_abandoned_execution` | orchestrated + terminal-relaunch refusal |
| terminal no-restart enforcement | `proof_supervision` immutable terminal cause | runner never re-invokes a terminal execution |

**Conclusion:** the entire supervision/backup/report/replay surface already
exists and is tested. The only genuinely missing artifact is one composition
module that binds them to the E.11 two-token `run_operational` under real
canonical timing, plus a disposable restore rehearsal and a terminal-relaunch
refusal. No second campaign or lifecycle owner is implemented.

## Phase 2 — Frozen runner contract

### Artifacts

- `src/printer_v1/operator_cli/two_token_operational_pilot_runner.py` — the
  composition module (importable, testable).
- `scripts/v2_9_7e_14_two_token_operational_pilot.py` — an **unregistered**
  pilot-only script (operator-run; not the future V2-9.8 PowerShell command; not
  added to `pyproject.toml`).
- `tests/test_v2_9_7e_14_two_token_operational_pilot_runner.py` — focused offline
  proof.

### Composition (no new campaign/lifecycle owner)

```text
prepare_pilot_target(paths)                 # migrate, integrity/FK, byte-identical
  -> backup, restore rehearsal, no-lease     #   backup, disposable restore rehearsal
validate_launch_provenance(provenance)       # dirty tracked tree blocks
create_execution(...)                        # single active proof, lock, backup==target
build_pilot_command(...)                     # campaign/config/run/cycle graph
HeartbeatWorker.start()                      # durable periodic heartbeat
owner.run_operational(..., lifecycle_kwargs) # exactly one campaign, real timing
HeartbeatWorker.stop()
attach_run(...) + finalize_execution_from_report(report)   # terminal, lock released
load_report_only(target, run_id)             # zero-source deterministic replay
```

### Target and backup contract

`prepare_pilot_target(paths, *, allow_authoritative_target=False)`:

1. Every path (persistent source, target, backup, restore-rehearsal, report dir,
   lock, logs) must be present, non-empty and mutually distinct; a missing or
   ambiguous path blocks before any mutation.
2. The target and backup may not be the canonical authoritative corpus unless
   `allow_authoritative_target` is explicitly set (never set by the pilot).
3. `prepare_proof_db` copies the persistent source to the target, migrates
   through the canonical repository head, runs integrity and foreign-key checks,
   confirms the persistent source is byte-unchanged, and writes a byte-identical
   fresh backup.
4. **Restore rehearsal:** the backup is restored onto a disposable copy, its
   runtime schema is validated, its hash is confirmed equal to the backup, and
   the disposable copy is removed. A failed rehearsal blocks.
5. No active or foreign lease may exist in the target
   (`printer_proof_run_supervision` STARTING/RUNNING or
   `printer_memory_factory_campaign_supervision` ACTIVE/STOPPING).
6. Exact target, backup, schema and provenance identities are returned; the
   runner never guesses a path.

### Real-time contract

Production timing uses the canonical real lifecycle durations already built into
`run_one_command_15m_factory` **by omission**: the production lifecycle kwargs
set only `supervision_execution_id`, `cancellation_probe`, `launch_provenance`
and `total_duration_seconds` (the 4.25h envelope). They deliberately set none of
`_window_seconds`, `_continuation_seconds`, `_sleep`, `_monotonic`,
`snapshot_adapter_factory` or `context_adapter_factories`, so the factory
defaults apply: real 900 s / real 2700 s / `time.sleep` / `time.monotonic` /
live DexScreener + GeckoTerminal adapters. There is **no production parameter**
to compress 15m, 1h, 4h, support-only 5m, lease or heartbeat timing.

Tests inject a **fake owner** at the runner→owner seam (not a clock into the
production configuration). The fake records the lifecycle kwargs it receives;
the offline proof asserts they contain no timing-override or fixture-adapter key
and that `total_duration_seconds` equals the canonical envelope. A test clock
therefore cannot leak into a live run: the only injection point is replacing the
owner itself, which in production is the real owner.

### Supervision contract

Reuses `proof_supervision` end to end:

- single-process ownership + one active proof (`create_execution`);
- bounded lease acquisition and a durable periodic heartbeat
  (`HeartbeatWorker` → `heartbeat_active_lease`, monotonic advance);
- immutable first terminal cause (`finalize_execution_from_report`,
  `_terminalize_execution`);
- cooperative stop request (`request_cooperative_stop`) surfaced to the run as a
  `cancellation_probe`;
- safe handling of host disappearance (`recover_abandoned_execution`, requires
  expired lease + absent process);
- local read-only status (`inspect_execution`, `source_calls: 0`);
- terminal report exactly once; zero-source replay (`load_report_only`);
- no automatic restart or successor: a relaunch that inspects a terminal
  execution refuses to rerun.

Status and stop operations make zero provider and zero Scheduler calls.

## Internal design review

- **Single authority.** The runner composes existing owners only; it adds no
  discovery, disposition, barrier, continuation, support-5m, promotion,
  activation, Governor or Scheduler logic, and no second campaign/lifecycle
  owner. The E.11 owner remains the sole operational authority.
- **Real timing is structural.** Real durations are the factory defaults; the
  runner cannot express a compressed production run, and tests cannot leak a
  clock through the production path.
- **Fail-closed target handling.** Ambiguous/missing paths, dirty provenance,
  migration/integrity/FK failure, non-byte-identical backup, failed restore
  rehearsal, or an active/foreign lease all block before any campaign mutation.
- **Terminal safety.** One immutable terminal cause; no restart or successor;
  relaunch against a terminal execution refuses; cleanup leaves zero
  pending/running work and no active lease; retrieval/financial tables stay
  outside the mutation surface.
- **No live use in E.14.** The runner is exercised only with a dependency-
  injected fake owner and deterministic clocks; no provider is contacted and the
  E.13 pilot authorization stays unconsumed.

**Review verdict:** approved for implementation.

## Locks

All Printer V1 Solana-only, paper-only, free/public-source, governance,
two-or-none, clean-memory, support-only-5m, and financial/retrieval locks remain
unchanged. This lane registers no CLI entry point, publishes no operator
command, runs no live pilot, and unlocks no retrieval or financial capability.
