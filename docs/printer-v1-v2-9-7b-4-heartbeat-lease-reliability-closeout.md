# Printer V1 V2-9.7B.4 Heartbeat / Lease Reliability Closeout

## Verdict

`V2_9_7B_4_HEARTBEAT_LEASE_RELIABILITY_PASS`

V2-9.7B.4 passes. The proof lease now retries only confirmed transient Windows
atomic-replacement failures within a fixed three-attempt ceiling, rejects
missing, malformed, expired, wrong-scope, and foreign locks, and advances both
heartbeat and expiry monotonically. If renewal remains unconfirmed after the
bounded retry, the launcher records the immutable supervision cause, stops
renewing, begins cooperative shutdown, and retains the existing expiry-based
forced-stop and cleanup path. No successor or automatic restart exists.

The launcher output boundary now captures the native command exit code before
rendering or normal logging. An unreadable output object or primary-log failure
therefore cannot erase a confirmed heartbeat. The exact first launcher fault is
persisted through the existing independent fallback path, and later heartbeats
continue when renewal was confirmed.

This repair does not create the future operational supervisor or authorize any
runtime, source, memory-growth, retrieval, decision, position, trade, audit, or
PnL behavior.

## Todo / Checklist

- [x] Revalidate exact commit, tracked cleanliness, inactive proof lock/runtime,
  and persistent DB hash.
- [x] Inspect Attempt 6 and Attempt 7 launcher, heartbeat, fault, and cleanup
  evidence against the active source stack.
- [x] Implement bounded atomic-replacement retry and fail-closed lease checks.
- [x] Separate confirmed renewal from output rendering and normal logging.
- [x] Prove first-fault persistence, safe stop, cleanup, no restart, and lock
  preservation with focused and nearest regression tests.
- [x] Recheck persistent DB isolation, accidental unlocks, scope, compilation,
  PowerShell parsing, and diff integrity.

## Preflight and Scope

- Starting HEAD: exact `2d1c10c2ee635df985a35705a7c663cbf27e16c2`.
- Tracked tree: clean before lane edits.
- One-proof lock / PID files: absent at preflight.
- Runtime: no Python proof child was present. Windows denied command-line CIM
  inspection of unrelated standing PowerShell processes; absent lock/PID state
  plus absent Python child was used as the fail-closed proof-runtime signal.
- Persistent DB: `data/printer_v1.sqlite3`, SHA-256
  `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`,
  length 13,017,088 bytes.
- Unrelated untracked artifacts were not edited, staged, or removed.
- No real proof, source request, runtime, or persistent DB command was started.

## Repair

### Bounded atomic lease replacement

`proof_supervision._write_lock_payload_atomic()` still writes a unique temporary
file in the lock's directory and uses `os.replace()` for atomic publication.
It now:

- permits at most three replacement attempts;
- sleeps 50 ms only between retryable attempts;
- retries only Windows replacement errors 5, 32, and 33;
- re-reads the authoritative lock before every attempt;
- aborts if the lock vanished or changed execution ownership;
- removes the temporary file after success or failure;
- reports replacement attempts and retries on successful heartbeats;
- converts permanent replacement failure into an explicit fail-closed
  supervision error.

`heartbeat_active_lease()` now requires exact V2-9 proof scope, parseable
heartbeat/expiry timestamps, an unexpired lease, exact execution ownership, and
strictly advancing heartbeat and expiry values. Historical rows and schemas are
unchanged.

### Launcher-fault observability

`Invoke-SupervisionCommand()` now exposes `CommandCompleted` and
`CommandSucceeded` from the native exit code captured before output processing.
Output rendering is guarded independently. A render/capture/logging fault is
registered once through `Register-LauncherLogFault()` and mirrored to the
fallback log without changing a successful command result.

The launcher now treats one failed heartbeat command as terminal because the
Python primitive has already exhausted its bounded transient retry. It records
`SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED`, requests cooperative stop, stops
future renewal attempts for that child, and retains the existing forced stop
after the last confirmed lease plus grace. The first cause remains immutable.
There is still exactly one `Start-Process`, no successor, and
`automatic_retries=0` for the proof runtime.

## Verification Results

Focused V2-9.7B.4 tests:

- 7 passed, including 5 subtests.
- Repeated renewals preserved valid JSON, exact scope/ownership, monotonic
  timestamps, and zero temporary-file residue.
- Injected WinError 5 contention retried exactly to the fixed ceiling and
  reported attempts/retries before succeeding.
- Permanent and non-transient replacement failures produced no false renewal
  and left the original lock unchanged.
- Missing, foreign, expired, malformed timestamp, and malformed JSON locks all
  failed closed.
- Real PowerShell harness: a confirmed heartbeat followed by injected
  `Stream was not readable.` output rendering failure persisted the exact first
  fault in the independent fallback log, then a later heartbeat renewed the
  same lease successfully.

Nearest supervision and cleanup regressions:

- 30 passed, including 4 subtests, covering heartbeat close boundaries,
  launcher bootstrap, launcher/fallback logging, natural terminalization,
  lock release, immutable first cause, abandoned-run cleanup, zero-source
  recovery, and no successor/restart behavior.
- 11 adjacent V2-9.7B.1/B.2/B.3 tests passed, including 3 subtests. Promotion
  reporting, timeframe-aware safety reporting, and tracking/lifecycle behavior
  remain unchanged.
- 101 E2V 5m support-only tests passed with a clean command exit.
- The E2W command printed `116 passed` with no assertion failure, then its
  sandbox temporary-directory wrapper exceeded the shell ceiling during
  teardown and returned timeout status after the green pytest summary. No E2W
  product file was changed by this lane.

Static checks:

- Python compilation: passed for changed Python source and tests.
- Windows PowerShell 5.1 parse check: passed for both launcher scripts.
- Persistent DB hash after verification: unchanged at
  `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB`.
- Code-diff accidental-unlock scan: no retrieval, paper-decision, financial,
  source, memory, safety, lifecycle, or 5m behavior was added or loosened.
- `git diff --check`: passed.

All focused fixtures use temporary lock files or isolated temporary databases.
The persistent DB created no source, memory, retrieval, decision, position,
trade, audit, or PnL rows and remained byte-identical by SHA-256.

## Money-Usefulness Contribution

Reliable lease continuity protects long evidence campaigns from becoming
ambiguous halfway through a valuable trajectory. Bounded recovery from ordinary
Windows sharing contention reduces avoidable loss of clean collection time,
while fail-closed permanent failure prevents an unsupervised child from
silently contaminating later corpus interpretation. Durable first-cause evidence
also makes wasted source budget and interrupted learning time diagnosable.

## What This Lane Improves

- Handles the exact Attempt 7 WinError 5 replacement fault within a small,
  observable retry ceiling.
- Prevents expired, malformed, missing, wrong-scope, or foreign locks from being
  renewed.
- Preserves exact ownership and monotonic lease state.
- Prevents normal logging or output rendering from discarding a confirmed
  heartbeat.
- Makes Attempt 6-style unreadable output durably observable.
- Stops renewal after an unconfirmed heartbeat and preserves safe cleanup.
- Preserves the first terminal cause and no-restart contract.

## What Remains Locked

- The future operational supervisor, campaign lease, resume logic, backup and
  restore, and embedded Git provenance.
- V2-9.7C, V2-9.7D, V2-9.7E, V2-9.8, and V2-10.
- Operational memory growth and persistent corpus campaigns.
- Source fetching or runtime expansion.
- Retrieval and dirty-memory use.
- Paper decisions, BUY, SELL, HOLD, positions, trades, audits, and PnL.
- Live execution, wallets, private keys, signing, real funds, and paid APIs.
- Scoring, ranking, confidence percentages, weighted logic, embeddings, and
  vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The retry set intentionally covers only confirmed Windows replacement errors
   5, 32, and 33. Any other filesystem error fails immediately; this is safer
   than guessing that an unknown error is transient.
2. The proof launcher remains proof-specific and must not be reused as the
   future operational campaign supervisor.
3. Once a bounded renewal fails, the launcher terminalizes even if a later
   replacement might have succeeded. This deliberately preserves first-cause
   and fail-closed semantics at the cost of ending that proof.
4. Windows sandbox ACL behavior prevented ordinary Python-created temporary
   directories from being writable in this session. Verification used a
   PowerShell-created temporary-directory shim; the actual test assertions and
   product paths were unchanged.
5. Eleven inaccessible `tmp*` directories created by the failed initial sandbox
   test attempt could not be removed by the current token. They are untracked,
   contain no committed lane output, and are excluded from the commit.
6. The E2W suite reached a green 116-test summary but its wrapper teardown did
   not return before the shell ceiling. This is an environment efficiency issue,
   not an observed assertion failure.

## Files Changed

- `src/printer_v1/operator_cli/proof_supervision.py`
- `scripts/Start-V2-9-Proof.ps1`
- `scripts/V2-9-LauncherLogging.ps1`
- `tests/test_v2_9_4_1_heartbeat_close_boundary.py`
- `tests/test_v2_9_4_3_launcher_log_reliability.py`
- `tests/test_v2_9_7b_4_heartbeat_lease_reliability.py`
- `docs/printer-v1-v2-9-7b-4-heartbeat-lease-reliability-closeout.md`

## What Was Built

A minimal proof-supervision reliability repair: bounded Windows atomic-replace
retry, stricter lease validation, independent output-fault capture, durable
first-fault evidence, and fail-closed launcher shutdown after an unconfirmed
renewal.

## What Was Not Touched

No migration, schema, database, source adapter, source request, runtime proof,
memory pipeline, promotion/reporting policy, safety acceptance, tracking or
lifecycle behavior, 5m behavior, continuation behavior, operational supervisor,
Git provenance, retrieval, or financial function was changed.

## Tests / Checks Run

Focused heartbeat/lease tests, real PowerShell launcher/logging harness,
launcher bootstrap and logging regressions, durable supervision and cleanup
regressions, adjacent V2-9.7B reporting/safety/lifecycle tests, E2V/E2W 5m
support-only regressions, Python compilation, PowerShell parse checks,
persistent DB hash comparison, accidental-unlock scan, scope inspection, and
`git diff --check`.

## Pass / Fail Status

PASS: `V2_9_7B_4_HEARTBEAT_LEASE_RELIABILITY_PASS`.

## Risks or Concerns

The retry remains deliberately tiny and Windows-specific. Unknown or persistent
filesystem faults end safely instead of being retried indefinitely. The
unremovable sandbox-generated temporary directories and E2W wrapper timeout are
recorded above and are not included in the lane commit.

## Next Recommended Phase

Stop after this commit. Do not begin V2-9.7C/D/E or operational memory growth.
A later operator-approved lane may continue the remaining V2-9.7B repair
sequence without reusing this proof launcher as an operational supervisor.