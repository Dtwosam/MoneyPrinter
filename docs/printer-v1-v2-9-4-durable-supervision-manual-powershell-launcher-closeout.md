# Printer V1 V2-9.4 Durable Supervision and Manual PowerShell Proof Launcher Closeout

## Verdict

`V2_9_4_DURABLE_SUPERVISION_PASS`

Lane: `V2-9.4 - Durable Supervision and Manual PowerShell Proof Launcher`

V2-9.4 repairs the gap V2-9 Attempt 3 exposed: a bounded V2-9 proof's host
process can be terminated by the execution environment mid-run with zero
internal failure, leaving a `RUNNING` factory row and abandoned `PENDING`
run steps/scheduler jobs that need manual DB forensics to interpret. This
lane adds a durable, DB-backed supervision ledger, a lease/heartbeat
mechanism, zero-source recovery for an abandoned execution, and an explicit
manual PowerShell launcher that owns exactly one proof process. No live V2-9
proof ran under this lane, no source was fetched, and no persistent DB was
touched. This closeout does not reopen V2-9 as passed, does not begin V2-10,
and does not authorize Attempt 4 — a future Attempt 4 may only be considered
after this PASS and a separate operator approval.

## Scope and baseline

- Required baseline named by the operator: commit `f7234a3` (since reverted
  as out-of-scope roadmap drift; see below).
- The V2-9.4 implementation itself was already present, uncommitted, in the
  working tree when this closeout began; it was not written as part of this
  closeout task, only verified, repaired where a stale dependency blocked
  it, and committed.
- V2-9, V2-10, and any live source/scheduler runtime remained out of scope.
  No `data/printer_v1.sqlite3` (persistent) mutation occurred at any point.

## Gate 1 - roadmap drift correction

An out-of-scope commit, `f7234a3` ("Add checkpoint/watchdog gap to V2-10
backlog"), had been made against `docs/printer-v1-memory-growth-build-order-v2.md`
while V2-9.4 was the active, uncommitted lane. Inspection confirmed:

- the uncommitted V2-9.4 implementation (migration 030, `proof_supervision.py`,
  `Start-V2-9-Proof.ps1`, `test_v2_9_4_durable_supervision.py`, and in-progress
  edits to `one_command_15m_factory.py`, `proof_db_schema_readiness.py`,
  `pyproject.toml`, and two schema tests) was fully intact and untouched;
- `f7234a3` changed exactly one file
  (`docs/printer-v1-memory-growth-build-order-v2.md`), confirmed by both
  `git show --stat --oneline` and `git show --name-only --format=`;
- no V2-9.4 file was lost, overwritten, or swept into that commit.

`f7234a3` was reverted with a new commit, `8297e4d`
("Revert \"Add checkpoint/watchdog gap to V2-10 backlog\""), restoring
`docs/printer-v1-memory-growth-build-order-v2.md` to byte-identical content
with its pre-`f7234a3` state (`git diff cc2a484 HEAD -- docs/...` is empty).
No history rewrite, stash, clean, or reset was used, and the V2-9.4 working
tree was not touched by the revert.

## Gate 3 - implementation verification

### What V2-9.4 adds

- **Migration `030_v2_9_proof_run_supervision.sql`**: a new
  `printer_proof_run_supervision` table scoping exactly one active V2-9
  execution at a time (`idx_proof_supervision_one_active_scope`, a unique
  partial index on `proof_scope` where `execution_status IN ('STARTING',
  'RUNNING')`), a lease (`heartbeat_at` / `lease_expires_at`), and a closed
  terminal-status vocabulary (`COMPLETED`, `GOVERNED_SAFE_STOP`,
  `OPERATOR_CANCELLED`, `SOURCE_FAILURE`, `BUDGET_STOP`,
  `HOST_PROCESS_DISAPPEARED`) enforced by a `CHECK` that ties
  `execution_status='TERMINAL'` to a non-null `terminal_status`,
  `first_stop_reason`, and `finished_at` together, atomically.
- **`src/printer_v1/operator_cli/proof_supervision.py`**: `create_execution`
  (acquires a one-proof file lock plus the DB row, validates the prepared
  proof/backup pair are schema-valid and byte-identical before allowing a
  new execution), `attach_run`/`heartbeat_execution` (renew the lease),
  `inspect_execution` (read-only, `source_calls=0`), `process_is_alive`
  (Windows `OpenProcess`/`GetExitCodeProcess`, POSIX `os.kill(pid, 0)`
  fallback), `recover_abandoned_execution` and `cancel_execution` (both
  zero-source: they only cancel `PENDING`/`RUNNING` run steps and scheduler
  jobs for the attached run, release scheduler locks, and write a single
  immutable first-cause terminal record - `recover` requires an expired
  lease and a confirmed-dead process; `cancel` does not wait for lease
  expiry), and `finalize_execution_from_report` (maps a governed
  `run_one_command_15m_factory` report onto the closed terminal-status
  vocabulary for the normal-completion path).
- **`run_one_command_15m_factory`** (in `one_command_15m_factory.py`) gained
  an optional `supervision_execution_id` parameter: when supplied, it
  preflight-checks the execution is active and targets the same proof DB,
  attaches the run once the run row exists, and finalizes the execution
  from the final report in every exit path (including the existing
  `finally` block), so a governed stop always closes the supervision row
  the same way a host-level kill's recovery path does.
- **`scripts/Start-V2-9-Proof.ps1`**: requires `-OperatorApproved`; enforces
  a lease more than twice the heartbeat interval; checks the one-proof lock
  before doing anything; runs the sole canonical V2-9.1 preparation path;
  does one GeckoTerminal and one DexScreener preflight request (no retry);
  creates the supervision execution; starts **exactly one** proof process
  via `Start-Process` (no retry loop); holds the system awake
  (`SetThreadExecutionState`) only for the process's lifetime; heartbeats on
  a fixed interval while polling `HasExited`; on any operator interruption
  or launcher exception, force-stops the child and calls `cancel`; and after
  the child exits, either reads the already-terminal execution or waits for
  lease expiry and calls `recover`. It never accepts a manual token, pair, or
  predecessor, and never references `WINDOW_12H`/`WINDOW_24H`.
- **`tests/test_v2_9_4_durable_supervision.py`**: exercises host-disappearance
  recovery during the 15m, 1h-continuation, and 4h-continuation phases and
  during a `RUNNING`-locked forced close; a live-process guard that blocks
  recovery before lease expiry; operator cancellation without waiting for
  expiry; the terminal-status mapping for `COMPLETED`/source-failure/
  budget-stop/other-governed-stop; the one-active-execution-at-a-time lock;
  idempotent re-recovery; and static assertions on the launcher script's
  shape (exactly one `Start-Process`, no manual token/pair/predecessor
  arguments, no 12h/24h references).

### Pre-existing failure found, diagnosed, and repaired (not V2-9.4 scope)

The first full regression pass (18 files, 801 passed / 70 subtests passed,
2 failed) surfaced two failures in `tests/test_v2_6_1h_audit_gate.py`. Before
touching anything, both `git status --short` and `git log` on
`src/printer_v1/operator_cli/e2q_memory_window_audit.py` confirmed:

- neither that source file nor the failing test file appears anywhere in
  the V2-9.4 diff;
- the source file was last changed in commit `3776716` ("Complete V2-8.1
  one-token 4h runtime implementation"), which intentionally added
  `WINDOW_4H` to `E2Q_VALID_MAIN_WINDOW_KINDS` and added a genuine
  4h-continuation structural check, `_validate_genuine_4h_window`, in the
  same way `WINDOW_1H` already had `_validate_genuine_1h_window`;
- the V2-8.1 closeout document explicitly lists "genuine 4h E2Q
  structural/continuity acceptance" as an approved deliverable of that
  lane.

The two failing assertions in `test_v2_6_1h_audit_gate.py` still encoded the
pre-V2-8.1 shape (`WINDOW_4H` excluded from the valid-kinds set; a bare
`WINDOW_4H` fixture blocked with a generic "not enabled" reason). Production
behavior was confirmed correct against the approved V2-8.1 contract; the
test was stale. Per operator direction, only the two stale assertions were
updated (to expect `WINDOW_4H` in `E2Q_VALID_MAIN_WINDOW_KINDS`, and to
expect the specific "missing anchored boundaries or governed snapshot
anchors" block reason a minimal fixture window actually produces), with a
comment naming commit `3776716` as the origin of the intentional change. No
production code changed and the 1h gate (`_validate_genuine_1h_window`,
`E2Q_1H_MIN_ELAPSED_SECONDS`) was not touched. This was committed separately
at `82627ab`, before resuming V2-9.4's own regression requirement.

### Full check results

- `tests/test_v2_9_4_durable_supervision.py`: `9 passed, 4 subtests passed`.
- `tests/test_phase1_database_schema.py` +
  `tests/test_phase18_6_persistent_local_db_bootstrap.py` (migration 030
  validation): `19 passed`.
- PowerShell launcher parsing:
  `[System.Management.Automation.Language.Parser]::ParseFile` on
  `scripts/Start-V2-9-Proof.ps1` returned zero parse errors.
- Cadence, continuity, scheduler, E2Q, Lane Q, Lane K/E2Z, replay,
  isolation, and lock regressions, plus every direct consumer of
  `one_command_15m_factory.py` and the full V2-9.1/9.2/9.3/9.4 suite (23
  files total, including the repaired `test_v2_6_1h_audit_gate.py`):
  `857 passed, 76 subtests passed, 0 failed`.
- Compilation: `python -m py_compile` on every modified/new Python file
  (`one_command_15m_factory.py`, `proof_db_schema_readiness.py`,
  `proof_supervision.py`, `test_v2_9_4_durable_supervision.py`,
  `test_phase18_6_persistent_local_db_bootstrap.py`,
  `test_phase1_database_schema.py`, `test_v2_6_1h_audit_gate.py`):
  `COMPILE_OK`.
- `git diff --check`: exit `0`, no whitespace errors (only benign
  LF-will-become-CRLF advisories from Git's own line-ending normalization).
- New untracked files (`migrations/030_v2_9_proof_run_supervision.sql`,
  `src/printer_v1/operator_cli/proof_supervision.py`,
  `scripts/Start-V2-9-Proof.ps1`, `tests/test_v2_9_4_durable_supervision.py`)
  checked separately for trailing whitespace and conflict markers: none
  found.

## What was not touched

No live V2-9 proof ran, no GeckoTerminal/DexScreener/other source request
was made from this closeout's own actions, no scheduler runtime executed
against the persistent DB, and `data/printer_v1.sqlite3` was never opened
for writing. V2-10, 12h/24h, retrieval, paper decisions, positions, trades,
audits, PnL, and any live wallet/signing path remained untouched and
unreferenced. No Attempt 4 occurred.

## Files changed

Committed as the V2-9.4 lane (this closeout), after the roadmap-drift
revert (`8297e4d`) and the separate stale-test repair (`82627ab`):

- `migrations/030_v2_9_proof_run_supervision.sql` (new)
- `src/printer_v1/operator_cli/proof_supervision.py` (new)
- `scripts/Start-V2-9-Proof.ps1` (new)
- `tests/test_v2_9_4_durable_supervision.py` (new)
- `src/printer_v1/operator_cli/one_command_15m_factory.py` (modified)
- `src/printer_v1/operator_cli/proof_db_schema_readiness.py` (modified)
- `pyproject.toml` (modified - two new console-script entry points)
- `tests/test_phase18_6_persistent_local_db_bootstrap.py` (modified -
  migration count/latest-migration expectations)
- `tests/test_phase1_database_schema.py` (modified - migration 030 added
  to the expected migration list)
- `docs/printer-v1-v2-9-4-durable-supervision-manual-powershell-launcher-closeout.md`
  (this file)

Not part of this lane's commit (already committed separately):

- `docs/printer-v1-memory-growth-build-order-v2.md` (reverted at `8297e4d`)
- `tests/test_v2_6_1h_audit_gate.py` (stale-test repair at `82627ab`)

## Functionality risks / setbacks / efficiency blockers

1. `run_supervised_v2_9_proof` and the `printer-run-v2-9-supervised-proof`
   / launcher `run` action are wired and unit-tested for their supervision
   contract, but no live, supervised, bounded V2-9 proof has actually been
   run end-to-end under this lane. That remains for a future, separately
   approved Attempt 4.
2. `process_is_alive` on Windows only confirms the PID is a *live* process,
   not that it is specifically the supervised Python proof process (PID
   reuse by an unrelated process after a crash is a narrow but real gap).
3. The one-proof file lock and the DB-row lock are two coordination
   mechanisms that must independently agree the execution is inactive
   before a new proof can start; the launcher and `create_execution` check
   both, but a manual DB edit or lock-file edit outside these tools could
   still desynchronize them.

## Next recommended phase

V2-9 remains closed FAIL (Attempt 3, external process termination) and is
not being reopened as PASS by this lane. No Attempt 4 is authorized by this
closeout alone. If a fourth attempt is separately approved by the operator,
it should launch through `scripts/Start-V2-9-Proof.ps1` so the durable
supervision ledger and lease/heartbeat mechanism built here are actually
exercised under a real multi-hour run, closing the gap V2-9 Attempt 3
exposed. Do not begin V2-10.
