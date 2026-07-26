# Printer V1 V2-9.8A — Operator Activation Gate Closeout

## Verdict

`V2_9_8A_OPERATOR_ACTIVATION_GATE_PASS`

V2-9.8A is complete. This closeout publishes the committed, bounded production
command but does not run it. No campaign was started and V2-9.8B was not
started.

## Gate Results

| Gate | Verdict |
|---|---|
| V2-9.8A.7 repair design | `V2_9_8A_7_REPAIR_DESIGN_PASS` |
| V2-9.8A.8 implementation | `V2_9_8A_8_IMPLEMENTATION_PASS` |
| V2-9.8A.9 bounded repair and command proof | `V2_9_8A_9_BOUNDED_REPAIR_AND_COMMAND_PROOF_PASS` |
| V2-9.8A.10 activation preflight | `V2_9_8A_10_ACTIVATION_PREFLIGHT_PASS` |
| V2-9.8A.11 closeout | `V2_9_8A_OPERATOR_ACTIVATION_GATE_PASS` |

## Git and Database Provenance

| Item | Value |
|---|---|
| Starting HEAD / `origin/master` | `93a3ca214277c5840fc35d88f44ca15c1ec10863` |
| Implementation checkpoint | `db6c2a11ff1b6429c4948cfd269084ce1c655e50` |
| Starting corpus SHA-256 | `985e44b136bf599b6a864874cdb2c0f10b61dbcd476271c2ba2d39680ce6b9f3` |
| Ending corpus SHA-256 | `e0f506d480b448c65c5f4573df5dea09adabd21bd017cd4664602b920edcae7f` |
| Migrations | 42; latest `042_held_to_15m_moderate_continuation.sql` |
| Integrity / foreign keys | `ok` / 0 violations |

The local implementation checkpoint intentionally precedes `origin/master`;
push was not authorized. Clean launch provenance records the exact local HEAD
and does not require a remote-equality bypass.

## Verified Backup

```text
/Users/Dtwo1/PrinterRecovery/v2-9-8a-9/20260726T111601Z-db6c2a1/printer_v1.pre-reconciliation.backup.sqlite3
```

The backup is byte-identical to the starting corpus:

```text
985e44b136bf599b6a864874cdb2c0f10b61dbcd476271c2ba2d39680ce6b9f3
```

The committed operational backup owner held the writer boundary, verified the
copy, ran a disposable restore rehearsal through migration 042, and confirmed
integrity, foreign keys, and critical row counts before authoritative mutation.

## Scheduler Reconciliation

The Central Scheduler's existing truthful `cancel_job` transition reconciled
exactly:

```text
8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 738, 980, 981, 982
```

All fifteen were freshly re-proven `PENDING`, unlocked, target-valid, and
unlinked from campaign Scheduler work, discovery work, and Memory Factory run
steps. They are now `CANCELLED`.

Only these fields changed:

```text
status
finished_at
updated_at
```

No row was deleted. Identity, job name/kind, target, priority, schedule,
`started_at`, locks, retry count, error, and creation timestamp were preserved.
Every unrelated Scheduler row and every unrelated table remained logically
identical to the verified backup.

The historical `printer_paper_audit_reports` row was preserved byte-for-byte.
It remains historical paper-only audit evidence with no position link and is
not capability activation.

## Public Command Architecture

Owner and registered entry point:

```text
printer-run-v2-9-8-memory-factory
-> printer_v1.operator_cli.operational_memory_factory_command:main
```

PowerShell Core wrapper:

```text
scripts/Start-PrinterV1-MemoryFactory.ps1
```

The public path does not import, rename, or run the V2-9 proof launcher or
`scripts/v2_9_7e_14_two_token_operational_pilot.py`.

The command fixes its database target to:

```text
/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3
```

It accepts no DB path. Execution, report, backup, restore-rehearsal, lease,
stdout, stderr, and terminal-summary paths are generated internally beneath:

```text
~/PrinterOperations/v2-9-8/<generated execution identity>/
```

Public modes are:

- `preflight-only`;
- `run` with explicit operator approval;
- `status`;
- `cooperative-stop` with explicit operator approval;
- `report-only`.

Preflight, status, and report-only are zero-source. Status and report-only are
read-only. Cooperative stop creates no source or Scheduler runtime call.

## Finite Ceilings and Window Policy

| Boundary | Value |
|---|---:|
| Campaigns | 1 |
| Cycles | 1 |
| Active token slots | 2 |
| Main window | `WINDOW_15M` |
| Main-window duration | 900 seconds |
| Command duration | 1,200 seconds |
| Discovery requests | 2 |
| Governed 15m requests | 65 |
| Governed requests per token | 21 |
| Scheduler rows | 51 |
| Admission operations | 45 |
| Storage growth | 67,108,864 bytes |
| Failures | 20 |
| Automatic retries | 0 |

`WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, and `WINDOW_24H` are structurally
disabled. `WINDOW_5M_MICRO_EVENT` remains support-only and cannot replace 15m,
trigger continuation, count toward main clean thresholds, or unlock any
retrieval or financial capability.

## Source Governor and Central Scheduler Ownership

The public command binds the existing `SOURCE_GOVERNOR` and
`CENTRAL_SCHEDULER` ports. Missing or incorrect owners fail closed. Discovery,
selection, graduated-token admission, governed collection, exact two-slot
activation, 15m Memory Factory work, terminal cleanup, and reporting reuse the
committed owners.

No direct provider loop, independent schedule, retry loop, source rotation,
successor, or automatic restart was added.

## Safe Stop, Reporting, and Replay

The command reuses operational campaign supervision with a renewable lease,
cooperative cancellation, immutable first terminal cause, campaign-scoped
Scheduler cleanup, unified terminal reconciliation, terminal report
persistence, and deterministic report-only replay.

Every terminal result reports:

```text
restart_created = false
successor_created = false
```

Relaunch is not automatic and a new campaign requires new explicit operator
approval.

## Tests and Proofs

- Focused A.8/A.9 tests: 10 passed.
- Disposable reconciliation proof:
  - wrong SHA, changed IDs, missing approval, locked row, linked row fail closed;
  - exact 15 rows only;
  - allowed fields only;
  - unrelated rows/tables preserved;
  - paper-audit row preserved;
  - integrity `ok`;
  - zero foreign-key violations;
  - idempotent terminal classification.
- Direct operational regression slice: 127 passed with 47 subtests; two
  unchanged legacy pilot lease tests failed only when combined into a
  six-minute aggregate and passed individually (2 passed in 60.95 seconds).
- An older abstract-command test fixture has five baseline failures because it
  records stale pre-042 migration metadata. Neither the abstract command module
  nor that test changed in this lane; the current operational backup and
  migration-042 checks pass.
- PowerShell Core 7.6.4 wrapper:
  - before reconciliation: cleanly blocked on exactly 15 active, zero locked
    Scheduler rows;
  - after reconciliation: `V2_9_8_OPERATIONAL_PREFLIGHT_READY`.
- Post-repair PowerShell preflight SHA before/after:
  `e0f506d480b448c65c5f4573df5dea09adabd21bd017cd4664602b920edcae7f`.
- Post-repair preflight reported zero source calls, zero Scheduler runtime
  calls, and zero database writes.

## Money-Usefulness Contribution

This gate makes the first real persistent campaign operationally auditable
without pretending to guarantee profit. It protects future money-useful memory
by removing stale historical work that could run unexpectedly, fixing the
corpus identity, requiring a recoverable backup, enforcing exact two-token 15m
collection, preserving negative/dirty outcomes, and keeping reports and
terminal state inspectable.

## What Improved

- Historical Scheduler residue is truthfully terminal.
- The authoritative corpus has a verified recovery point.
- A public, placeholder-free operational command now exists.
- The production target cannot be replaced by a proof DB.
- The first campaign is structurally two-token and 15m-only.
- Safe stop, reporting, replay, and no-restart behavior are explicit.
- Clean Git provenance is enforced at operation time.

## What Remains Locked

- V2-9.8B has not run.
- V2-10 and V2-11.
- 1h, 4h, 12h, and 24h production windows.
- Retrieval activation.
- Paper decisions and BUY/SELL/HOLD.
- Positions, trade events, paper audits, and PnL.
- Live execution, wallets, private keys, signing, and real funds.
- Paid APIs.
- Scoring, ranking, confidence percentages, weighted logic.
- Embeddings and vectors.
- Automatic restart, successor creation, and unbounded runtime.

Historical retrieval-query, paper-decision, and paper-audit rows remain
preserved context; the activation baseline requires zero delta from those exact
rows and zero position/trade/PnL rows.

## First V2-9.8B Operation Proof Required

The first separately operator-run V2-9.8B campaign must prove:

- exact final clean Git provenance;
- exact authoritative DB target and pre-campaign backup;
- exactly two active slots;
- `WINDOW_15M` only;
- Source Governor and Central Scheduler traces;
- conditional support-only 5m semantics;
- bounded source/Scheduler/storage/failure ceilings;
- honest clean/dirty/blocked outcomes;
- campaign-scoped zero active work at terminal;
- terminal report and deterministic zero-source replay;
- zero retrieval and financial deltas;
- no restart or successor.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Effect | Required response |
|---|---|---|
| Free-source outage or rate limit | Campaign may block or yield incomplete evidence | Preserve governed failure; do not raise budgets or weaken evidence |
| Small two-token sample | Limited corpus diversity | Review quality and rotation over bounded campaigns, never raw row targets |
| 15m cadence gaps | Dirty/blocked memory | Keep gaps visible and deny clean promotion |
| Historical locked-row baseline misunderstood | False activation or destructive cleanup | Compare exact deltas; preserve historical rows |
| Lease renewal uncertainty | Ambiguous active work | Safe stop with immutable first cause; no restart |
| Public command run from dirty Git | Reproducibility loss | Fail closed |
| Longer-window pressure | Source waste and roadmap bypass | Keep 1h/4h/12h/24h disabled until explicit later lanes |
| Provider data lacks wallet authenticity | Overclaimed flow lessons | Preserve partial/unknown labels |

## Exact Production PowerShell Command

This command is published for the next separately authorized V2-9.8B
operation. It was not run in V2-9.8A.

```powershell
pwsh -NoProfile -File /Users/Dtwo1/Developer/MoneyPrinter/scripts/Start-PrinterV1-MemoryFactory.ps1 -Mode run -OperatorApproved
```

No production campaign ran during V2-9.8A.
