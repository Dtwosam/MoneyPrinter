# Printer V1 V2-9.8B.1 — First Operation Blocker Repair Design

## Verdict

`V2_9_8B_1_REPAIR_DESIGN_PASS`

This design authorizes only the minimum repair and bounded recovery requested by
the operator. It does not rerun production, create a successor, activate a new
campaign, unlock longer windows, or unlock retrieval or financial capability.

## Mandatory Source-Grounded Blocker Investigation

```text
BLOCKER CLASSIFICATION:
- COMMITTED_CODE_DEFECT — Git provenance treats the authoritative SQLite
  rollback journal as arbitrary untracked content during runtime.
- COMMITTED_CODE_DEFECT — the public command's terminal exception boundary
  starts after campaign graph and supervision initialization and its cleanup
  chain can replace the original exception or stop before report persistence.
- MISSING_APPROVED_IMPLEMENTATION_BOUNDARY — cooperative stop can request
  cancellation but no exact operator-approved owner can terminalize an expired,
  process-orphaned operational campaign.

EVIDENCE:
- HEAD 6945d5d14627248fe964aba9916505cf55df038b; origin/master
  93a3ca214277c5840fc35d88f44ca15c1ec10863; tracked tree clean.
- Current authoritative SHA-256:
  2db1a11456771a0c5d48e8cee801d29860f21e11de0c70d86db1dd66068ed39a.
- Pre-campaign backup SHA-256:
  e0f506d480b448c65c5f4573df5dea09adabd21bd017cd4664602b920edcae7f.
- No SQLite sidecar and no live Printer process at audit time.
- Current campaign/run are STOP_REQUESTED; supervision is STOPPING with
  OPERATOR_REQUESTED_COOPERATIVE_STOP; terminal, cleanup, and release fields
  remain NULL; both database and lock-file leases are expired.
- Zero active/locked Scheduler jobs; integrity ok; zero foreign-key violations.
- Immutable `.dump` comparison found exactly five added rows and no changed or
  deleted pre-campaign rows.

OFFICIAL-SOURCE COMPARISON:
- SQLite rollback-journal files are expected transaction companions in DELETE
  journal mode. They are not arbitrary project source.
- Python cleanup must use a guaranteed finally/context boundary; exception
  chaining or re-raise must preserve the original exception.

PRINTER-CONTRACT COMPARISON:
- Exact Git provenance is mandatory, but expected runtime SQLite companions may
  not make an otherwise clean committed launch fail.
- First terminal cause is immutable.
- Every terminal route must reconcile owned work, clean supervision, release
  leases, persist a report, and create no restart or successor.
- Recovery must use canonical Scheduler, campaign ownership, supervision, and
  unified terminal owners rather than ad hoc row patches.

ROOT CAUSE:
1. `capture_git_provenance()` treats every non-ignored `git ls-files --others`
   path as equivalent. The repository ignores `*.sqlite3` but not
   `data/printer_v1.sqlite3-journal`, `-wal`, or `-shm`. A DELETE-mode write
   creates the journal, and a later runtime provenance capture rejects it.
2. Campaign graph creation and supervision acquisition occur before the
   protected execution boundary. The exception handler also nests
   reconciliation and cleanup such that a closure error can prevent the
   terminal report and replace the original exception. Focused disposable
   verification exposed the exact incompatibility: unified reconciliation
   terminalizes campaign/run/cycle first, after which supervision cleanup
   rejects those already-terminal ownership rows as inconsistent.
3. `cooperative_stop()` calls only `request_campaign_cancellation()`. That owner
   truthfully sets STOPPING/STOP_REQUESTED and records cancellation; it does not
   claim process death, reconcile terminal ownership, release the lease, or
   write a terminal report. Once the process is gone, no existing public owner
   completes those steps.

CODE CHANGE JUSTIFIED: YES

MINIMUM SAFE RESPONSE:
- Add an explicit exact relative-path untracked allowlist to Git capture and use
  it only for the three authoritative SQLite runtime sidecars.
- Put every operation after campaign graph initialization under one failure
  terminalization coordinator that independently attempts canonical
  reconciliation, supervision cleanup, and report persistence, then re-raises
  the original exception.
- Add one exact, operator-approved orphan recovery owner for this execution.

FOCUSED PROOF:
- Exact sidecars allowed; arbitrary untracked, tracked, and staged changes
  blocked.
- Post-initialization faults at each boundary terminalize and retain the
  original exception.
- Recovery rejects wrong SHA/IDs/delta, live process/lease, and active Scheduler
  work; preserves locked tables; succeeds once and is idempotent.
- Complete disposable failure-and-recovery proof before authoritative recovery.

UNTOUCHED SCOPE:
- Sources, provider contracts, Scheduler execution policy, memory gates,
  migrations, retrieval, paper decisions, positions, trades, audits, PnL,
  longer windows, wallets, private keys, paid APIs, scoring, and ranking.

AUTHORIZATION STATUS:
- Disposable implementation/proof and one exact authoritative recovery are
  operator approved.
- Production rerun, successor, restart, tag, and push are forbidden.

NEXT ROADMAP-COMPLIANT STEP:
- Implement this design, prove it disposably, checkpoint clean Git, then recover
  the exact orphan through canonical owners.
```

## Exact Pre-Campaign Database Delta

All 83 user tables and the schema were compared through immutable read-only
SQLite dumps. No pre-existing row changed or disappeared. Exactly these rows
were added:

### `printer_memory_factory_campaigns`

- `id=1`
- `campaign_id=20260726T114155Z-95d9979a9302-campaign`
- `campaign_state=STOP_REQUESTED`
- `db_mode=OPERATIONAL_PERSISTENT`
- `db_target_identity=sha256:e0f506d480b448c65c5f4573df5dea09adabd21bd017cd4664602b920edcae7f`
- `proof_source_db_identity=NULL`
- `policy_version=V2-9.8-15M-OPERATIONAL-V1`
- `first_terminal_cause=NULL`
- `terminal_at=NULL`
- `created_at=2026-07-26T11:41:56.024271+00:00`
- `updated_at=2026-07-26T11:54:51.686863+00:00`

### `printer_memory_factory_campaign_configurations`

- `id=1`
- `configuration_id=20260726T114155Z-95d9979a9302-configuration`
- exact campaign ID above
- `configuration_hash=834a0e94864c875380ba9c43680c9382c76dcbac702740d27b4134556e6da384`
- immutable configuration fixes two slots, `WINDOW_15M`, 900 seconds, no
  continuation, no retries, and the committed bounded ceilings
- launch provenance records clean HEAD
  `6945d5d14627248fe964aba9916505cf55df038b`
- `created_at=2026-07-26T11:41:56.024271+00:00`

### `printer_memory_factory_campaign_runs`

- `run_id=20260726T114155Z-95d9979a9302-campaign-run`
- exact campaign ID above
- `run_ordinal=1`
- `run_state=STOP_REQUESTED`
- `authoritative_run_id=NULL`
- `proof_supervision_id=NULL`
- `first_terminal_cause=NULL`
- `terminal_at=NULL`
- `created_at=2026-07-26T11:41:56.024139+00:00`
- `updated_at=2026-07-26T11:54:51.686863+00:00`

### `printer_memory_factory_campaign_cycles`

- `cycle_id=20260726T114155Z-95d9979a9302-cycle`
- exact campaign and run IDs above
- `cycle_ordinal=1`
- `cycle_state=PLANNED`
- terminal cause/time fields `NULL`
- created/updated `2026-07-26T11:41:56.024139+00:00`

### `printer_memory_factory_campaign_supervision`

- `id=1`
- `supervision_id=20260726T114155Z-95d9979a9302-supervision`
- exact campaign/configuration/run IDs above
- `owner_id=20260726T114155Z-95d9979a9302-owner`
- `supervision_state=STOPPING`
- `terminal_status=NULL`
- `first_terminal_cause=NULL`
- `heartbeat_at=2026-07-26T11:41:56.028089+00:00`
- `lease_expires_at=2026-07-26T11:43:26.028089+00:00`
- exact external lease path
- cancellation requested at `2026-07-26T11:54:51.686863+00:00`
- `cancellation_reason=OPERATOR_REQUESTED_COOPERATIVE_STOP`
- `cleanup_completed_at=NULL`
- `lease_released_at=NULL`
- created at `2026-07-26T11:41:56.028089+00:00`
- updated at `2026-07-26T11:54:51.686863+00:00`

Retrieval, paper/financial, source request/response/failure, and Scheduler tables
have zero delta. Historical locked counts remain 10 retrieval queries, 2 paper
decisions, 1 paper audit report, 20 quote-evidence rows, and zero retrieval
matches, positions, trade events, decision audits, trade audits, and PnL rows.

## Repair Design

### Exact Git sidecar allowance

`capture_git_provenance()` receives an optional exact repository-relative
allowlist. It parses NUL-delimited Git output and rejects every untracked path
except:

```text
data/printer_v1.sqlite3-journal
data/printer_v1.sqlite3-wal
data/printer_v1.sqlite3-shm
```

No glob, directory, suffix-wide, or arbitrary SQLite allowance is permitted.
Tracked and staged checks are unchanged. No `.gitignore` change is needed.

### Post-initialization terminalization

After campaign graph creation, a single coordinator owns the failure boundary.
On any `BaseException` it:

1. stops heartbeat/child coordination;
2. records the first truthful cause from the original exception;
3. invokes `cleanup_campaign_supervision()` while ownership rows are still in
   their accepted active/stop-requested states;
4. invokes `reconcile_campaign_terminal()` after cleanup to canonically prove
   the whole graph and active-work result;
5. builds and writes the canonical terminal report;
6. records `restart_created=false` and `successor_created=false`;
7. attaches closure faults without replacing the original;
8. re-raises the original exception.

Normal terminal behavior uses the same coordinator inputs and canonical owners.

### Exact orphan recovery

The recovery owner is fixed to this execution and requires:

- explicit operator approval;
- current SHA
  `2db1a11456771a0c5d48e8cee801d29860f21e11de0c70d86db1dd66068ed39a`;
- the exact five-row delta above and no other delta against the exact verified
  pre-campaign backup;
- exact campaign/configuration/run/cycle/supervision/owner/report identities;
- STOP_REQUESTED/STOPPING with the exact cooperative cancellation;
- expired database and filesystem leases;
- no live Printer process;
- zero active/locked global or campaign-owned Scheduler work;
- unchanged locked capability rows;
- a fresh verified recovery backup and restore rehearsal outside Git.

It then invokes canonical unified reconciliation with the truthful original
cause `OPERATIONAL_CAMPAIGN_FAILED:GitProvenanceError`, canonical supervision
cleanup, and canonical terminal report persistence. It creates no source call,
restart, successor, or history deletion. A repeat after successful exact
recovery returns an idempotent already-recovered result without new writes.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Consequence | Required mitigation |
|---|---|---|
| Sidecar allowance broadens accidentally | Arbitrary dirty launch could pass | Exact three-path equality tests |
| Cleanup owner faults | Original error or terminal report could be lost | Independent attempts; retain and re-raise original |
| Recovery runs against drifted corpus | Wrong history could be terminalized | Exact SHA plus full table delta contract |
| Original process still alive | Two owners could mutate one campaign | Lease and process gates both required |
| Recovery backup is incomplete | No safe rollback point | Canonical online backup and restore rehearsal |
| Cooperative cancellation overwrites failure truth | False terminal cause | Fixed original Git failure cause; first cause immutable |
| Report/replay mutates evidence | Hidden new work | Canonical report owner; zero-source/read-only replay checks |
| Pressure to rerun immediately | Repeats production risk | Retry remains a separately authorized action |
