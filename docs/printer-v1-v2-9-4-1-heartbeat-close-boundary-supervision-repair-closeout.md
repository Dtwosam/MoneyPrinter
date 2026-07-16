# Printer V1 V2-9.4.1 Heartbeat and Close-Boundary Supervision Repair Closeout

## Verdict

`V2_9_4_1_HEARTBEAT_CLOSE_REPAIR_PASS`

V2-9.4.1 is complete as an implementation-and-fixture repair lane. No live source
was called, no V2-9 Attempt 6 was launched or authorized, no persistent database
was opened or mutated, and no V2-10 or operational-memory campaign work began.

Starting gate:

- required clean starting commit: `ddbfdc7`
- observed starting HEAD: `ddbfdc7`
- observed tracked working tree: clean

## Scope and authority

The repair used the active Printer source stack, the V2-8.1 and V2-9 through
V2-9.4 closeouts, and only the applicable Solana Builder source-governance
README and evidence rules. Source Governor and Central Scheduler ownership is
unchanged. Solana-only, paper-only, no-retry, retrieval, financial, 12h, and 24h
locks remain in force.

## Attempt 5 causal sequence

Inspected identity:

- execution: `af5dcb91-41ab-4b74-a1be-bf87e7b367fc`
- run: `36b500cd-dba7-4bdd-bc8b-ab534e8f7cb0`

Observed boundary:

1. The last successful supervision heartbeat was persisted at
   `2026-07-16T11:34:23.140621Z`.
2. The 15m close began at `2026-07-16T11:34:52.040228Z`.
3. The launcher's next 30-second heartbeat became due while close work held the
   proof DB write boundary.
4. The old heartbeat implementation attempted to update the supervision row in
   that same proof DB. SQLite contention rejected that write, so the launcher
   emitted `Proof heartbeat failed`.
5. The generic launcher catch set `operatorCancelled = true`, even though no
   operator pressed Ctrl+C.
6. The old `finally` block force-killed the child and immediately invoked the
   operator-cancellation cleanup path.
7. Terminal recovery was recorded at
   `2026-07-16T11:34:59.014135Z`, only about 36 seconds after the last
   successful heartbeat and therefore before the 90-second lease expired.

Consequences and answers:

- The heartbeat failure was proof-DB lock contention, not proof-process
  disappearance and not operator cancellation.
- `heartbeat_expired=false` was correct for the time of cleanup: the
  cancellation cleanup path did not require lease expiry, and the recorded
  90-second lease was still valid.
- `OPERATOR_CANCELLED` was false attribution caused by the generic catch
  sharing the Ctrl+C flag and cleanup path.
- The launcher did kill a still-lease-valid child while it was performing the
  15m close.
- Stdout remained empty because the child was launched without unbuffered mode
  and was force-killed before buffered output flushed. Stderr remained empty
  because the launcher-side failure did not originate as an uncaught child
  exception.
- The child was killed before its normal final-report persistence path could
  complete. The old recovery report then persisted recovery-local zero deltas
  as the available final evidence, obscuring the real lifecycle totals.
- Attempt 5 retained the Attempt 4 artifact name because the launcher hardcoded
  `v2-9-attempt4` into every proof, backup, preparation, stdout, and stderr
  path.

## Repair implemented

### Independent active lease

The one-proof lock is now the authoritative active heartbeat and lease record.
Heartbeat renewal atomically replaces that small lock-file payload and does not
open or write the proof DB. The proof DB remains the durable execution/run
ledger and terminal-report store.

The lock records execution identity, proof identity, PID, heartbeat timestamp,
lease expiry, creation/update timestamps, and cooperative stop metadata.
Read-only supervision inspection overlays the active lock lease onto the
durable ledger while the execution is active.

A focused contention fixture holds `BEGIN IMMEDIATE` on the proof DB and proves
that the independent heartbeat still renews on schedule.

### Stop-cause and launcher semantics

Only the dedicated
`System.Management.Automation.PipelineStoppedException` branch can represent
genuine Ctrl+C/operator cancellation.

A heartbeat persistence fault uses the exact reason
`SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED`. Other launcher failures use an
explicit `SUPERVISION_LAUNCHER_FAULT:<message>` reason. Neither is converted
to `OPERATOR_CANCELLED`.

One failed heartbeat is logged and the process continues under its valid lease.
A sustained failure requests cooperative stop. The launcher does not force
termination until the last valid lease plus the configured cooperative grace
has elapsed. If lock-file persistence itself prevents the cooperative request,
the same explicit supervision fault remains primary and forced cleanup is still
deferred until the lease and grace boundary.

The runtime polls the cooperative stop contract:

- during scheduler waits in one-second slices;
- before and after governed context requests;
- before and after snapshot boundaries;
- before 15m, 1h, and 4h successor close creation;
- after step execution and before terminal reporting.

The first stop cause is retained through cancellation, cleanup, finalization,
and reporting. Cleanup may prevent completion but cannot rewrite that cause.

### Evidence accounting and final-report persistence

Normal runtime reports now persist:

- `full_run_evidence_deltas`: the complete current-run lifecycle deltas;
- `recovery_evidence_deltas`: zero for the normal terminal path.

Abandoned/forced recovery reports now persist:

- `full_run_evidence_deltas`: proof DB minus the prepared proof backup;
- `recovery_evidence_deltas`: only rows changed by zero-source recovery;
- legacy `evidence_deltas`: retained as the recovery-local alias.

Recovery uses `COALESCE(final_report_json, ...)` for a factory run, so it cannot
replace an already-persisted full runtime report. A fixture proves that a late
recovery leaves a completed report byte-for-byte logically unchanged.

### Diagnostics and artifact identity

The child now launches with Python `-u`. Runtime stdout emits flushed JSON
events for process start, run start, step/close start, terminal cause, and
cleanup completion. The launcher writes its own timestamped JSONL event stream
and preserves all supervision-command output.

Every future operator invocation must supply an explicit `-AttemptNumber`.
Proof, backup, preparation, stdout, stderr, and launcher-log artifacts all use
`v2-9-attempt<AttemptNumber>-<timestamp>`. No token, pair, predecessor, or
window identity is hardcoded.

A fixture interrupts an unbuffered child and proves that both stdout and stderr
retain usable diagnostic markers.

## Schema decision

No migration was added. The existing V2-9.4 supervision schema already owns the
durable execution and terminal ledger. The active lease is transient
lock-file state, and the new report fields are JSON report-contract fields.
Adding columns or parallel tables would have duplicated existing ownership
without improving the safety boundary.

## Verification

All verification used fixtures and temporary databases only.

- PowerShell launcher parse: PASS
- Python compile for runtime and supervision modules: PASS
- `git diff --check`: PASS
- V2-9.4.1 focused heartbeat/close-boundary plus V2-9.4 direct supervision:
  15 passed, 4 subtests passed
- V2-9.3 early-failure accounting, V2-9.2 terminal/budget, V2-9.1 proof-schema,
  and V2-8.1 runtime: 32 passed, 4 subtests passed
- E2Q, Lane Q, Lane K/E2Z, clean-memory gate, replay, isolation, retrieval, and
  financial-lock direct regressions: 378 passed
- Total selected tests: 425 passed, 8 subtests passed

The fixtures prove:

- heartbeat renewal survives proof-DB write contention;
- a single heartbeat miss does not stop or kill a valid process;
- sustained heartbeat persistence failure retains its exact non-operator cause;
- cooperative stop and cleanup leave zero pending/running proof jobs;
- recovery full-run totals and recovery-local deltas remain separate;
- late recovery cannot overwrite a completed full report;
- interrupted child stdout/stderr are usable;
- explicit attempt-number naming has no Attempt 4 hardcode;
- no automatic retry, invalid successor, duplicate evidence, retrieval row, or
  financial row is introduced.

## Files changed

- `scripts/Start-V2-9-Proof.ps1`
- `src/printer_v1/operator_cli/proof_supervision.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `tests/test_v2_9_4_durable_supervision.py`
- `tests/test_v2_9_4_1_heartbeat_close_boundary.py`
- `docs/printer-v1-v2-9-4-1-heartbeat-close-boundary-supervision-repair-closeout.md`

## What was not touched

No live source, V2-9 proof runtime, persistent DB, production proof artifact,
retrieval activation, paper decision, BUY/SELL/HOLD, paper position, trade,
audit, PnL, wallet, key, live execution, paid API, scoring, 12h, 24h, V2-10, or
operational-memory campaign was touched or authorized.

## Risks and concerns

The active heartbeat intentionally depends on the local filesystem that owns the
one-proof lock. A sustained filesystem failure therefore produces a governed
supervision fault and cooperative/lease-bounded stop; it never authorizes an
automatic retry. Force termination remains a last resort after the active lease
and cooperative grace boundary, because a non-responsive host process cannot be
allowed to retain proof jobs indefinitely.

## Next recommended phase

Stop. V2-9 Attempt 6 remains unauthorized. Any later proof or lane requires a
new, explicit operator instruction.
