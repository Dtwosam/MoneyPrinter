# Printer V1 V2-9.4.3 Launcher Supervision and Log-Writer Reliability Closeout

## Verdict

`V2_9_4_3_LAUNCHER_LOG_RELIABILITY_PASS`

Lane: `V2-9.4.3 - Launcher supervision and log-writer reliability repair`

The launcher fault proven by the Attempt 6 forensic audit is repaired at its
exact boundary. Launcher-event logging and native supervision output capture are
now separated from the authoritative supervision result, logging can no longer
throw, a logging fault can no longer discard a successful heartbeat, kill a
healthy child, masquerade as `OPERATOR_CANCELLED`, or replace the original fault
cause, and a durable fallback diagnostic path records the exact first cause
without depending on the failing logger. No proof runtime, source, budget,
cadence, context resolution, DB schema, retry, or safety-lock behavior changed.
No migration was needed.

## Preflight gates

| Gate | Result |
| --- | --- |
| Attempt 6 forensic audit committed | Yes — `6e95249` |
| Tracked working tree clean | Yes — 0 modified tracked files |
| Proof runtime active | No — zero `python.exe` processes |
| One-proof lock present | No — `operator-runs/v2-9-one-proof.lock.json` absent |

All gates passed; the lane proceeded.

## Root cause repaired (from the Attempt 6 audit)

At `14:16:58.863479Z` the filesystem-only `heartbeat` command **succeeded** and
atomically renewed the lease to `14:18:28.863479Z`. The failure was entirely in
the PowerShell native-output capture/logging boundary *after* that renewal:

1. `Write-LauncherEvent` wrote through a **pipeline**
   (`$record | ConvertTo-Json | Add-Content`). A fault in that pipeline throws,
   and a broken pipeline can surface as `PipelineStoppedException` — the exact
   exception type the launcher used to identify a genuine operator Ctrl+C.
2. `Invoke-Supervision` logged **inside** its output loop, so a logging throw
   aborted the function *after* the native command had already succeeded,
   discarding the real exit code and the proven lease renewal.
3. The generic `catch` then logged `LAUNCHER_FAULT` through the **same broken
   logger**, so the fault could not record itself; `Request-CooperativeStop` and
   the `finally` path had the same dependency.

Net effect: no `LAUNCHER_FAULT`, no `LAUNCHER_FINISH`, launcher supervision
silently stopped, the lease expired ~4 hours before the healthy child completed
naturally, and the lowest-level cause left no durable stack.

## Implementation — smallest repair

New `scripts/V2-9-LauncherLogging.ps1` (dot-sourced by the launcher) owns the
reliability boundary and contains no proof-runtime, schema, or evidence logic:

- **`Write-LauncherEvent`** — never throws. Builds the record, serialises with
  `ConvertTo-Json -InputObject` (**no pipeline**, so it can no longer emit
  `PipelineStoppedException`), and appends **one complete line** via
  `[System.IO.File]::AppendAllText` with UTF-8 (no BOM). Either the whole JSONL
  record lands or none of it does — no partial JSON records. Returns
  `$true`/`$false`; on failure it registers the fault and returns.
- **`Invoke-SupervisionCommand`** — captures the native command and reads
  `$global:LASTEXITCODE` **before any logging happens**, so the authoritative
  supervision result can never be discarded by a logging or capture fault. The
  capture itself is wrapped in try/catch (this also absorbs PS 5.1's
  `NativeCommandError`, which `$ErrorActionPreference='Stop'` raises for any
  `2>&1` stderr line from a native command). Returns `ExitCode`, `Output`, and
  `CaptureFault`.
- **`Register-LauncherLogFault`** — records the **exact first** cause once and
  never replaces it: boundary label, exception type, message, category,
  `FullyQualifiedErrorId`, `ScriptStackTrace`, `InvocationInfo.PositionMessage`,
  command, and the launcher log path. Always mirrored to the fallback.
- **`Write-LauncherFallback`** — durable diagnostic path using direct .NET file
  IO with no pipeline and no dependency on the primary logger, so it stays
  usable exactly when the primary logger is what failed. Never throws; last
  resort is `[Console]::Error`.
- **`Test-LauncherLogHealthy` / `Get-LauncherLogFirstFault`** — expose log
  health and the preserved first cause.

`scripts/Start-V2-9-Proof.ps1` changes:

- dot-sources and initialises the boundary; adds
  `$launcherFallbackLog` (`<prefix>-launcher-fallback.log`);
- `Invoke-Supervision` is now a thin wrapper over `Invoke-SupervisionCommand`;
- every `Write-LauncherEvent` call site is `| Out-Null` guarded so the new
  boolean return can never corrupt the launcher's JSON stdout;
- both `catch` blocks resolve the reason from `Get-LauncherLogFirstFault` when
  present, so **the original cause is preserved** rather than relabelled by a
  later symptom, and both write a durable fallback record;
- the `PipelineStoppedException` catch is **guarded**: if a logging/capture
  fault was already recorded, the pipeline stop is that fault cascading and is
  classified as a launcher fault; `$operatorCancelled = $true` is reached only
  on the `else` branch (still exactly one assignment in the file), so genuine
  Ctrl+C is preserved;
- the terminal path mirrors `LAUNCHER_FINISH` to the fallback when the primary
  log is unhealthy, and the final JSON now reports `launcher_log_healthy`,
  `launcher_log_fault`, and `launcher_fallback_log`.

Preserved unchanged: cooperative cancellation, lease-expiry recovery,
`SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED`, the two-consecutive-failure rule
("one failed renewal never kills"), `FORCED_TERMINATION_AFTER_EXPIRED_LEASE`,
bootstrap/`-ProjectRoot` handling, explicit `-AttemptNumber` naming, `-u`
unbuffered child, `--lock-path` heartbeats, and `automatic_retries = 0`.

No schema change was required, so no migration was added.

## Minimum sufficient verification

| Check | Result |
| --- | --- |
| Windows PowerShell 5.1 parse (both files) | `PARSE_OK`, PSVersion 5.1.26100.8737 |
| Real `powershell.exe -File` with repeated native supervision output | Pass — 3 rounds × 12 output lines |
| Injected primary log-write failure right after a successful command | Pass — writes return `$false`, never throw |
| Lease/loop continues, healthy child not killed | Pass — all 3 rounds ran with a permanently dead logger; exit code `0` preserved every round |
| Injected capture failure with durable exact-cause fallback | Pass — `Invoke-Supervision:capture:inspect-lock` boundary recorded with message/stack |
| Terminal cleanup when primary logger unavailable | Pass — `LAUNCHER_FINISH` mirrored to fallback |
| Fallback also unavailable | Pass — still never throws (last-resort console path) |
| Exact first cause preserved, never replaced | Pass — exactly one fallback record after repeated faults |
| JSONL structurally valid, no partial records | Pass — every line parses; healthy run wrote 5/5 complete records |
| Genuine Ctrl+C remains `OPERATOR_CANCELLED` | Pass — guard ordering asserted; single assignment on the `else` branch; supervision-side fault still yields `GOVERNED_SAFE_STOP`, not `OPERATOR_CANCELLED` |
| Expired-host recovery unchanged | Pass — V2-9.4.1 recovery fixtures green |
| Bootstrap + AttemptNumber naming fixtures | Pass |
| Temporary isolated DBs only | Pass — `tempfile` dirs; every fixture re-asserts the persistent hash |
| Persistent DB hash unchanged | `97DB9A15CC464D86137CBBB0DD0A4EF1880E9F4E231FB41E8B22CA09FB177FBB` |
| Python compilation | New test file compiles; no Python source changed |
| `git diff --check` | Clean (exit 0) |

Suites run (directly affected only, per the risk-based verification policy — the
full repository suite was **not** run):

- `test_v2_9_4_3_launcher_log_reliability.py` — 10 passed (new);
- `test_v2_9_4_2_launcher_bootstrap.py`, `test_v2_9_4_1_heartbeat_close_boundary.py`,
  `test_v2_9_4_durable_supervision.py` — 20 passed, 4 subtests;
- combined: **30 passed, 4 subtests, 0 failed**.

No lock file, Attempt 7 artifact, or stray fallback log leaked into
`operator-runs/`.

## Money-usefulness contribution and what this improves

No clean corpus row is added. The contribution is operational trustworthiness of
the one mechanism that supervises a multi-hour bounded proof. Attempt 6's
completed child was luck, not safety: the launcher had already gone blind and
could not have force-stopped a hung child or recorded why. After this repair a
launcher-log fault degrades to a recorded diagnostic instead of silently ending
supervision, and the exact first cause survives even when the primary logger is
the casualty — which is what makes the next attempt's supervision claim
verifiable rather than assumed.

## What remains locked / not touched

Proof runtime, sources, budgets, cadence, context resolution, DB schema,
retries, and safety locks are unchanged. The 4h shared-context boundary defect
(audit repair item 2) is explicitly **not** repaired in this lane. `WINDOW_12H`,
`WINDOW_24H`, retrieval, paper decisions, BUY/SELL/HOLD, positions, trades,
audits, PnL, live execution, wallets, keys, and paid APIs remain locked. No live
source was called, no Attempt 7 was launched, no V2-10 or active memory growth
began, and the persistent DB was never written.

## Functionality Risks / Setbacks / Efficiency Blockers

1. The lowest-level Attempt 6 cause (`Stream was not readable`, the exact .NET
   stream instance) remains `UNKNOWN_REQUIRES_RESEARCH`. This lane makes that
   class of fault survivable and self-recording rather than diagnosing the
   original object; the next occurrence will now carry a durable stack.
2. Log-fault survivability is proven by injected faults under real
   `powershell.exe`, not by a multi-hour live run. Continuous launcher
   supervision over a full 4h proof is still unproven until an operator-approved
   attempt runs.
3. The `PipelineStoppedException` guard distinguishes a cascading log fault from
   a genuine Ctrl+C by whether a logging/capture fault was already recorded.
   A genuine Ctrl+C arriving *after* an unrelated log fault would be recorded as
   a launcher fault rather than `OPERATOR_CANCELLED`. This is the conservative
   direction (it preserves the true first cause and still cooperatively stops),
   but it is a deliberate trade-off.
4. The 4h shared-context boundary defect remains open and still blocks a
   closing V2-9 proof conclusion on its own terms.

## Files changed

- `scripts/V2-9-LauncherLogging.ps1` (new)
- `scripts/Start-V2-9-Proof.ps1`
- `tests/test_v2_9_4_3_launcher_log_reliability.py` (new)
- `docs/printer-v1-v2-9-4-3-launcher-supervision-log-reliability-closeout.md` (this file)

## Next recommended phase

Hold. The next item in the audit's ordered repair sequence is item 2 — the 4h
shared-context close-boundary repair (consume the exact current-run ledger IDs
and separate the immutable logical deadline from the approved closing-evidence
cutoff). It is **not** started here. No Attempt 7, V2-10, active memory growth,
retrieval, or financial capability is authorized by this closeout; each requires
a new explicit operator-approved lane.
