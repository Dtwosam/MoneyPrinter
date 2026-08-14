# Printer V1 V2-9.8B Four-Token Authorization Wrapper Independent Review Repair Closeout

Date: 2026-08-14

## Verdict

`V2_9_8B_FOUR_TOKEN_AUTHORIZATION_WRAPPER_INDEPENDENT_REVIEW_REPAIR_PASS_READY_FOR_REREVIEW`

This repair lane created no authorization, started no Printer runtime, performed
no source or RPC call, mutated no authoritative database, applied no migration,
and did not run the four-token proof.

## Baseline

- Reviewed implementation HEAD: `5defeb035e6693384c2fede5c128030668376c77`
- Independent review: `66c9c559992dac689a71dce11ea9951bd9c1f055`
- Local branch synchronized to `66c9c55` by fast-forward only. No reset, clean,
  stash, or removal of untracked operator artifacts; both protected
  `operator-runs/` directories remain untracked and untouched.

Scope was limited to the two independent-review blockers. No accepted seam was
reopened, and the two previously documented baseline-identical failing test files
were not touched.

## Blocker 1 — supervision zero-state semantics

### Defect

The gate counted every supervision row:

```sql
SELECT COUNT(*) FROM printer_memory_factory_campaign_supervision
SELECT COUNT(*) FROM printer_proof_run_supervision
```

Migration 033 keeps campaign supervision rows in `TERMINAL` and defines active
ownership as `ACTIVE`/`STOPPING`. Migration 030 keeps proof supervision rows in
`TERMINAL` and defines active proof ownership as `STARTING`/`RUNNING`. A healthy
quiescent authoritative database is therefore expected to carry historical
terminal supervision, so the gate would have blocked a healthy database and
implied destructive cleanup.

### Local design clarification

"Zero campaign/proof supervision" in the wrapper design means **zero active,
non-terminal supervision ownership**. It never means destruction of historical
terminal evidence. This clarification is recorded in the gate source next to the
queries it governs.

### RED (`1c47315`)

A disposable post-055 database carrying only historical `TERMINAL` campaign and
proof supervision was wrongly blocked:

```
FourTokenProofZeroStateError: four-token proof zero-state gate blocked before
consumption: campaign_supervision: observed 1; proof_supervision: observed 1
```

The companion cases confirmed `ACTIVE`/`STOPPING` and `STARTING`/`RUNNING` were
already blocking correctly, so the RED isolates exactly the reported defect.

```
1 failed, 2 passed, 4 subtests passed
```

### GREEN (`21c69cb`)

Campaign supervision counts only `supervision_state IN ('ACTIVE','STOPPING')`;
proof supervision counts only `execution_status IN ('STARTING','RUNNING')`.

Proven by focused tests: historical terminal supervision passes with both domain
counts at zero and both rows still present afterwards with an unchanged file
mtime; `ACTIVE` and `STOPPING` campaign supervision still block; `STARTING` and
`RUNNING` proof supervision still block. The gate remains read-only and deletes
or rewrites nothing.

```
11 passed, 6 subtests passed
```

## Blocker 2 — real production Printer-process probe

### Defect

`_default_zero_state_gate(...)` passed a hard-coded probe returning `()`, so the
production wrapper path could never observe an already-running Printer runtime
and always reported `printer_processes=0`.

### Repair

`active_printer_runtime_processes(db_path, *, liveness_probe, self_pids)` was
added to the zero-state gate as the smallest dedicated helper, reusing the
existing `proof_supervision.process_is_alive` owner rather than adding a second
liveness authority:

- candidate PIDs come only from `printer_proof_run_supervision` rows still
  claiming active ownership (`STARTING`/`RUNNING`) with a non-null `process_id`;
  terminal history is not a runtime;
- the authoritative database is opened through the existing sidecar-safe
  immutable inspector and the read-only connection, so the probe cannot write or
  create a sidecar;
- one bounded pass, no polling loop, no retry;
- no process is signalled, killed, or mutated;
- the wrapper's own process tree (`os.getpid()`, `os.getppid()`) is excluded, so
  the harmless wrapper process is never classified as an active Printer run;
- fail closed: an unreadable database, an unreadable ledger, or any exception
  from the liveness inspection raises `FourTokenProofZeroStateError`.

`_default_zero_state_gate` now builds that probe. `apply_authorization_once`
gained `authoritative_db_path` and `printer_runtime_liveness_probe` seams so the
production default path can be exercised against a disposable database without
starting a Printer runtime; both default to production behavior.

### RED (`7877282`)

The RED exercises the real default gate — it does **not** substitute a fake
`zero_state_gate`:

```
TypeError: apply_authorization_once() got an unexpected keyword argument
'authoritative_db_path'
AttributeError: module 'four_token_proof_zero_state_gate' has no attribute
'active_printer_runtime_processes'
```

```
8 failed
```

### GREEN (`0668401`)

```
8 passed
```

Proven: an existing Printer runtime blocks before consumption with
`printer_process_present`, no canonical application directory or marker is
created, and no child starts; clean process state proceeds through the remaining
free gates and launches exactly one child with
`zero_state_ready=True, printer_processes=0`; the probe reads durable state
without changing file mtime or size; terminal supervision, a dead recorded
process, and the wrapper's own PID are all correctly not active runtimes;
unreadable process state fails closed; the probe performs exactly one liveness
call per candidate.

## Files changed

| File | Change |
|---|---|
| `src/printer_v1/operator_cli/four_token_proof_zero_state_gate.py` | active-only supervision queries; new `active_printer_runtime_processes` probe |
| `src/printer_v1/operator_cli/four_token_proof_one_shot_wrapper.py` | real probe wired into `_default_zero_state_gate`; db/liveness seams on `apply_authorization_once` |
| `tests/test_v2_9_8b_four_token_proof_zero_state_gate.py` | supervision fixtures and semantics tests |
| `tests/test_v2_9_8b_four_token_proof_production_process_probe.py` | new focused production-probe contract |
| `tests/test_v2_9_8b_four_token_proof_migration_055_evidence.py` | fixture accepts an exact database binding |

## Verification

Four-token lane (8 files):

```
56 passed, 8 subtests passed
```

Directly affected provenance/wrapper regression locks (standard-four-hour
activation authorization, WINDOW_15M one-shot wrapper, four-token canonical
factory wiring), run together with the lane:

```
62 passed, 8 subtests passed
```

`py_compile` passed for both touched production modules. `git diff --check` is
clean. The tracked worktree is clean; only the two protected operator-runs
artifact directories remain untracked.

The two previously documented baseline-identical failing test files were
deliberately not run or modified: neither blocker intersects them.

## Preserved seams

Untouched and still locked by their existing tests: the dedicated proof
authorization profile/schema, exact 4/2/2 policy, separate 900 / 18,000 clocks,
migration-055 evidence binding, one-marker/one-child law, proof-only CLI
composition, canonical factory integration, and the existing WINDOW_15M and
standard-four-hour wrappers.

## What remains locked

Real four-token authorization creation, four-token runtime, live source/RPC
execution, 12h/24h, retrieval, paper decisions and BUY/SELL/HOLD, positions,
trades, audits, PnL, live wallet/private keys/real funds, and paid APIs.
Retry, rerun, resume, restart, and successor remain false.

## Next permitted lane

Focused independent rereview of these two repairs. No authorization package may
be prepared or created until that rereview passes.
