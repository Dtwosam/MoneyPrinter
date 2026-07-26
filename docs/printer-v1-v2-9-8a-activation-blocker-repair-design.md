# Printer V1 V2-9.8A.7 — Activation Blocker Repair Design

## Verdict

`V2_9_8A_7_REPAIR_DESIGN_PASS`

This design is implementation-authorizing only for V2-9.8A.8. It does not run
sources, mutate the authoritative corpus, publish the production command, start
a campaign, or start V2-9.8B.

## Mandatory Source-Grounded Work Gate

| Item | Record |
|---|---|
| Baseline | `master`; HEAD and `origin/master` at `93a3ca214277c5840fc35d88f44ca15c1ec10863`; tracked tree and index clean |
| Authoritative corpus | `data/printer_v1.sqlite3`; SHA-256 `985e44b136bf599b6a864874cdb2c0f10b61dbcd476271c2ba2d39680ce6b9f3`; migrations 001–042; integrity `ok`; zero foreign-key violations |
| Active lane | V2-9.8A.7, inside the active V2 memory-growth source stack |
| Allowed | Design the exact historical Scheduler reconciliation and the committed V2-9.8 public command |
| Forbidden | Source calls, authoritative mutation, campaign execution, V2-9.8B, longer windows, retrieval, decisions, financial capabilities, restart/successor |
| Canonical owners affected | Central Scheduler; Source Governor; operational backup/restore preflight; campaign persistence/supervision; authoritative live campaign owner; 15m Memory Factory; terminal reporting/replay |
| Proven blockers | Fifteen unlocked/unlinked historical `PENDING` Scheduler rows; no registered public V2-9.8 command |
| Classification | Both are `MISSING_INTEGRATION`. Neither is provider availability, market insufficiency, rate limiting, or a reason to weaken evidence policy |
| Expected files | One narrow Scheduler reconciliation module and tests; one public operational command module and tests; one PowerShell Core wrapper; minimal owner-mode wiring; `pyproject.toml`; lane docs |
| Database boundary | Disposable copies in proof; authoritative mutation only after A.9 disposable PASS and a verified backup |
| Minimum tests | Exact-ID/field reconciliation, path/SHA/ownership/window/lock gates, zero-source auxiliary modes, wrapper preflight-only, directly affected operational regressions |
| Stop condition | First relevant failed design, implementation, proof, repair, or repeat-preflight gate |
| Locks after PASS | Every V1 restriction; only bounded persistent 15m memory growth becomes eligible for the separately run V2-9.8B lane |

The requested source name
`operator_cli/operational_backup_preflight.py` does not exist at the baseline.
The committed canonical owner is
`operator_cli/operational_backup_restore_preflight.py`; this design reuses it
and does not create a duplicate backup owner.

## Repair 1 — Exact Historical Scheduler Reconciliation

### Scope

The immutable approved job-ID set is:

```text
8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 738, 980, 981, 982
```

All fifteen were independently classified
`UNLINKED_HISTORICAL_ACTIVE_STATUS`. Each is `PENDING`, unlocked, has a valid
tracking-queue target, and has zero links from:

- `printer_discovery_work`;
- `printer_memory_factory_campaign_scheduler_work`;
- `printer_memory_factory_run_steps`.

### Existing truthful terminal transition

`printer_v1.scheduler.scheduler.cancel_job` is the existing Central
Scheduler-owned transition. `CANCELLED` truthfully represents abandoned
historical work that must never execute. It deletes no row and changes only:

- `status`: `PENDING` -> `CANCELLED`;
- `finished_at`: `NULL` -> the single reconciliation timestamp;
- `updated_at`: prior timestamp -> the same reconciliation timestamp.

`locked_at` and `lock_owner` are assigned `NULL` by the existing transition but
must already be `NULL`; therefore their values do not change. Identity, name,
kind, target, priority, `scheduled_for`, `started_at`, retry count,
`last_error`, and `created_at` remain byte-for-byte equal.

### Command contract

The one-time repair requires:

- explicit `--operator-approved`;
- the exact authoritative path;
- expected pre-repair SHA-256
  `985e44b136bf599b6a864874cdb2c0f10b61dbcd476271c2ba2d39680ce6b9f3`;
- the exact fifteen IDs, with no omission, addition, or reordering ambiguity;
- a fresh read classification proving every row remains `PENDING`, unlocked,
  unlinked, and target-valid;
- zero active campaign, supervision, discovery, or factory-run ownership;
- no SQLite sidecar or foreign process/lease;
- a verified backup and disposable restore rehearsal through the committed
  operational backup owner before mutation;
- one short `BEGIN IMMEDIATE` transaction;
- post-commit allowed-field-only, integrity, foreign-key, row-count, and
  unrelated-table reconciliation.

The repair invokes `cancel_job` with a borrowed Scheduler connection for each
approved ID. Any classification drift rolls back the whole set. A second
invocation may return an idempotent `ALREADY_RECONCILED` result only when all
fifteen are `CANCELLED`, unlocked/unlinked, and their other protected fields
remain the expected values. A partial mix fails closed.

No source call, campaign row, discovery row, run-step row, deletion, retry,
restart, or successor is permitted.

## Repair 2 — Public V2-9.8 Operational Command

### Ownership and entry points

Add one registered command:

```text
printer-run-v2-9-8-memory-factory
```

Add one PowerShell Core wrapper:

```text
scripts/Start-PrinterV1-MemoryFactory.ps1
```

The wrapper is a thin launcher for the registered Python owner. It does not
copy, rename, import, or execute
`scripts/v2_9_7e_14_two_token_operational_pilot.py`.

### Fixed target and internally generated paths

The command resolves the repository from its installed module and accepts only:

```text
<repository>/data/printer_v1.sqlite3
```

No database path flag exists on the public run surface. Proof, alternate, and
copied databases are structurally unrepresentable.

For an approved run the owner creates a fresh execution identity and generates
all artifacts beneath:

```text
~/PrinterOperations/v2-9-8/<UTC execution identity>/
```

This root contains the verified backup, disposable restore rehearsal, reports,
lease lock, stdout log, stderr log, and terminal execution summary. Artifact
paths never resolve inside the database target.

### Modes

The single command exposes:

- `preflight-only`: read-only, zero-source, zero-DB-write validation;
- `run`: requires `--operator-approved`; performs backup before campaign state;
- `status`: read-only status of the newest/specified committed operational
  execution, with zero source/Scheduler runtime calls;
- `cooperative-stop`: requires `--operator-approved`; requests stop only for an
  existing active execution and creates no successor;
- `report-only`: deterministic read-only replay of the newest/specified
  terminal report with zero source calls and zero evidence writes.

Only `run` may create campaign state, and V2-9.8A never invokes it.

### Preflight order

Before campaign mutation:

1. exact authoritative path and current SHA;
2. canonical migrations 001–042, integrity, foreign keys, and quiescent
   sidecars;
3. clean launch Git provenance;
4. required free-source environment shape without recording values;
5. source-contract and runtime-dependency `READY`;
6. zero active/locked global Scheduler jobs;
7. zero active campaign, cycle, run, discovery, run-step, proof-supervision, or
   campaign-supervision work;
8. no active/foreign filesystem lease;
9. locked-capability baseline capture;
10. internally generated writable report/artifact paths;
11. verified backup and disposable restore rehearsal;
12. immutable campaign/configuration/run/cycle graph;
13. Source Governor and Central Scheduler owner binding;
14. campaign execution.

### Runtime boundary

The public owner reuses:

- the graduated discovery/selection and exact two-slot activation path;
- `SOURCE_GOVERNOR` and `CENTRAL_SCHEDULER` owner ports;
- the canonical `WINDOW_15M` Memory Factory runner;
- existing campaign persistence and supervision;
- cooperative cancellation and unified terminal reconciliation;
- terminal report persistence and deterministic zero-source replay.

The operational mode added to the existing owner differs from `FULL_PILOT` in
one deliberate way: it passes `continuous_first_hour=False`,
`continuous_four_hour=False`, and `four_hour_proof_mode=False`. It retains
exactly two selected tokens and real 900-second 15m timing. The public command
rejects 1h, 4h, 12h, and 24h configuration. Conditional 5m remains explanatory
support only and cannot trigger continuation.

### Finite committed ceilings

The command preserves existing committed hard ceilings rather than accepting
operator overrides:

| Boundary | Ceiling |
|---|---:|
| Campaigns | 1 |
| Cycles | 1 |
| Active token slots | 2 |
| Main window | `WINDOW_15M` |
| Main-window seconds | 900 |
| 15m command duration | 1,200 seconds |
| Discovery requests | 2 |
| Governed 15m requests | 65 |
| Governed requests per token | 21 |
| 15m Scheduler rows | 51 |
| Automatic retries | 0 |
| Admission operation ceiling | 45 |
| Campaign storage growth | 64 MiB |
| Campaign failures | 20 |

The outer campaign configuration records the committed admission and lifecycle
ceilings separately; it does not sum them into an invented score or hidden
budget.

### Terminal law

Every terminal route:

- preserves the first terminal cause;
- reconciles all attributable Scheduler and ownership work;
- releases supervision and lock state;
- writes a terminal report;
- permits deterministic report-only replay;
- reports locked-capability deltas;
- records `restart_created=false` and `successor_created=false`.

Relaunch against an existing execution identity fails closed. No terminal
outcome creates another campaign.

## Proof Gates

A.8 may implement only this design. A.9 must prove the implementation on
disposable databases before the authoritative reconciliation. A.10 must repeat
the complete zero-write preflight against the repaired corpus and committed
command. A.11 may publish the command only after all earlier verdicts pass.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Consequence | Mitigation / stop |
|---|---|---|
| Scheduler row drift before repair | Wrong operational work could be cancelled | Reclassify all fifteen inside the write transaction; rollback on any mismatch |
| Backup owner invoked on non-quiescent SQLite state | Incomplete recovery artifact | Reject sidecars/writers; verified restore rehearsal before mutation |
| Operational flag accidentally relaxes proof-only guards broadly | Proof/production identity confusion | Exact authoritative-path mode only; proof mode remains unchanged and tested |
| Longer-window parameter leaks into public command | Unauthorized source use and lifecycle expansion | No public window flags; structural assertions for 15m-only |
| Historical paper-audit row mistaken for activation | Destructive or dishonest cleanup | Preserve row and compare its content before/after |
| Report/status mode performs work | Hidden source calls or DB writes | Read-only URI, query-only checks, source-call counters fixed at zero |
| Terminal failure relaunches | Duplicate corpus mutation | Immutable execution identity, no loop, no successor, no restart |
| Public RPC/Helius availability | Campaign may honestly block | Preserve governed failure; never weaken eligibility or raise ceilings |

