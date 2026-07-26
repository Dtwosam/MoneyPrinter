# Printer V1 V2-9.8B.1 — First Operation Blocker Repair Closeout

## Verdict

`V2_9_8B_1_FIRST_OPERATION_BLOCKER_REPAIR_PASS`

V2-9.8B.1 is closed PASS. This does not mark V2-9.8B complete and does not
authorize a production campaign, restart, successor, retry, tag, or push. The
next permitted action is a separately operator-authorized retry of the first
bounded operation.

## Scope and identities

- Audited repository HEAD:
  `6945d5d14627248fe964aba9916505cf55df038b`
- Audited `origin/master`:
  `93a3ca214277c5840fc35d88f44ca15c1ec10863`
- Repair checkpoint:
  `963627ab47f3431f9d3eda2a5265e8ea5396f6ff`
- Execution:
  `20260726T114155Z-95d9979a9302`
- Campaign:
  `20260726T114155Z-95d9979a9302-campaign`
- Configuration:
  `20260726T114155Z-95d9979a9302-configuration`
- Run:
  `20260726T114155Z-95d9979a9302-campaign-run`
- Cycle:
  `20260726T114155Z-95d9979a9302-cycle`
- Supervision:
  `20260726T114155Z-95d9979a9302-supervision`
- Owner:
  `20260726T114155Z-95d9979a9302-owner`
- Report:
  `20260726T114155Z-95d9979a9302-report`

## Exact root cause

The first operation did not call a source or run Scheduler work. It failed
between campaign initialization and lifecycle execution.

1. Git provenance treated every unignored untracked path as arbitrary. SQLite
   was in DELETE journal mode, so authoritative runtime activity could expose
   `data/printer_v1.sqlite3-journal`. The later Git provenance check raised
   `GitProvenanceError` even though the tracked and staged trees were clean.
2. The public campaign exception boundary did not safely own every operation
   after campaign graph creation. Its failure path reconciled campaign/run/cycle
   before supervision cleanup. Reconciliation made those rows terminal;
   cleanup then rejected the already-terminal ownership graph and prevented the
   canonical report path. A closure exception could also replace the original
   failure.
3. Cooperative stop was correctly request-only. It set
   `STOP_REQUESTED`/`STOPPING` and recorded
   `OPERATOR_REQUESTED_COOPERATIVE_STOP`; it could not prove process death,
   reconcile terminal state, release ownership, or write a terminal report
   after the original process no longer existed.

Mandatory blocker classification:

- `COMMITTED_CODE_DEFECT` — exact SQLite runtime companion was not recognized.
- `COMMITTED_CODE_DEFECT` — post-initialization failure closure and ordering
  were incomplete.
- `MISSING_APPROVED_IMPLEMENTATION_BOUNDARY` — no exact orphan recovery owner
  existed.

The repair design is preserved in
`docs/printer-v1-v2-9-8b-first-operation-blocker-repair-design.md`.

## Read-only audit and exact pre-recovery delta

The revised current SHA was verified before implementation:

```text
2db1a11456771a0c5d48e8cee801d29860f21e11de0c70d86db1dd66068ed39a
```

The verified pre-campaign backup was:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8/20260726T114155Z-95d9979a9302/printer_v1.pre-campaign.backup.sqlite3
SHA-256: e0f506d480b448c65c5f4573df5dea09adabd21bd017cd4664602b920edcae7f
```

All 83 user tables and the schema were compared read-only. No baseline row was
changed or deleted. Exactly five rows were added:

### `printer_memory_factory_campaigns`

```json
{
  "id": 1,
  "campaign_id": "20260726T114155Z-95d9979a9302-campaign",
  "campaign_state": "STOP_REQUESTED",
  "db_mode": "OPERATIONAL_PERSISTENT",
  "db_target_identity": "sha256:e0f506d480b448c65c5f4573df5dea09adabd21bd017cd4664602b920edcae7f",
  "proof_source_db_identity": null,
  "policy_version": "V2-9.8-15M-OPERATIONAL-V1",
  "first_terminal_cause": null,
  "terminal_at": null,
  "created_at": "2026-07-26T11:41:56.024271+00:00",
  "updated_at": "2026-07-26T11:54:51.686863+00:00"
}
```

### `printer_memory_factory_campaign_configurations`

```json
{
  "id": 1,
  "configuration_id": "20260726T114155Z-95d9979a9302-configuration",
  "campaign_id": "20260726T114155Z-95d9979a9302-campaign",
  "configuration_hash": "834a0e94864c875380ba9c43680c9382c76dcbac702740d27b4134556e6da384",
  "configuration_json": {
    "automatic_retries": 0,
    "backup_preflight_references": {
      "backup_sha256": "e0f506d480b448c65c5f4573df5dea09adabd21bd017cd4664602b920edcae7f",
      "latest_migration": "042_held_to_15m_moderate_continuation.sql",
      "preflight_status": "READY",
      "required_migration": "032_campaign_ownership_schema.sql",
      "source_identity": "sha256:e0f506d480b448c65c5f4573df5dea09adabd21bd017cd4664602b920edcae7f"
    },
    "ceilings": {
      "campaign_count": 1,
      "cycle_count": 1,
      "duration_seconds": 1200,
      "failures": 20,
      "scheduler_work": 51,
      "source_calls": 45,
      "storage_bytes": 67108864
    },
    "continuous_first_hour": false,
    "continuous_four_hour": false,
    "inner_15m_ceilings": {
      "discovery_requests": 2,
      "governed_requests": 65,
      "governed_requests_per_token": 21,
      "scheduler_rows": 51
    },
    "main_window": "WINDOW_15M",
    "main_window_seconds": 900,
    "report_directory_identity": "path-sha256:778bad7c57f7b50b12738d4a5dd42a1df80d7e413426627fd57439fdbe3926ef",
    "support_5m_only": true,
    "token_capacity": 2
  },
  "launch_provenance_json": {
    "git_head": "6945d5d14627248fe964aba9916505cf55df038b",
    "git_provenance_captured_at": "2026-07-26T11:41:55.863878+00:00",
    "git_staged_changes_present": false,
    "git_tracked_tree_clean": true,
    "git_unstaged_changes_present": false,
    "git_untracked_present": false
  },
  "created_at": "2026-07-26T11:41:56.024271+00:00"
}
```

`configuration_json` and `launch_provenance_json` are stored as canonical JSON
text; they are expanded above without changing their content.

### `printer_memory_factory_campaign_runs`

```json
{
  "run_id": "20260726T114155Z-95d9979a9302-campaign-run",
  "campaign_id": "20260726T114155Z-95d9979a9302-campaign",
  "run_ordinal": 1,
  "run_state": "STOP_REQUESTED",
  "authoritative_run_id": null,
  "proof_supervision_id": null,
  "first_terminal_cause": null,
  "terminal_at": null,
  "created_at": "2026-07-26T11:41:56.024139+00:00",
  "updated_at": "2026-07-26T11:54:51.686863+00:00"
}
```

### `printer_memory_factory_campaign_cycles`

```json
{
  "cycle_id": "20260726T114155Z-95d9979a9302-cycle",
  "campaign_id": "20260726T114155Z-95d9979a9302-campaign",
  "run_id": "20260726T114155Z-95d9979a9302-campaign-run",
  "cycle_ordinal": 1,
  "cycle_state": "PLANNED",
  "first_terminal_cause": null,
  "terminal_at": null,
  "created_at": "2026-07-26T11:41:56.024139+00:00",
  "updated_at": "2026-07-26T11:41:56.024139+00:00"
}
```

### `printer_memory_factory_campaign_supervision`

```json
{
  "id": 1,
  "supervision_id": "20260726T114155Z-95d9979a9302-supervision",
  "campaign_id": "20260726T114155Z-95d9979a9302-campaign",
  "configuration_id": "20260726T114155Z-95d9979a9302-configuration",
  "run_id": "20260726T114155Z-95d9979a9302-campaign-run",
  "owner_id": "20260726T114155Z-95d9979a9302-owner",
  "supervision_state": "STOPPING",
  "terminal_status": null,
  "first_terminal_cause": null,
  "heartbeat_at": "2026-07-26T11:41:56.028089+00:00",
  "lease_expires_at": "2026-07-26T11:43:26.028089+00:00",
  "lease_lock_path": "/Users/Dtwo1/PrinterOperations/v2-9-8/20260726T114155Z-95d9979a9302/campaign.lease.lock",
  "cancellation_requested_at": "2026-07-26T11:54:51.686863+00:00",
  "cancellation_reason": "OPERATOR_REQUESTED_COOPERATIVE_STOP",
  "cleanup_completed_at": null,
  "lease_released_at": null,
  "created_at": "2026-07-26T11:41:56.028089+00:00",
  "updated_at": "2026-07-26T11:54:51.686863+00:00"
}
```

Retrieval, financial, source, and Scheduler rows had zero unexpected delta.
The locked historical counts were:

| Table | Rows |
|---|---:|
| `printer_memory_retrieval_queries` | 10 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_paper_decisions` | 2 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |
| `printer_paper_audit_reports` | 1 |
| `printer_paper_quote_evidence` | 20 |
| `printer_source_requests` | 1118 |
| `printer_source_responses` | 1071 |
| `printer_source_failures` | 47 |
| `printer_scheduler_jobs` | 989 |

Audit integrity was `ok`, foreign-key violations were zero, active/locked
Scheduler jobs were zero, both lease representations were expired, no
authoritative SQLite sidecar existed, and no Printer process was live.

## Provenance repair

Runtime Git provenance continues to reject:

- any staged tracked change;
- any unstaged tracked change;
- any arbitrary untracked path.

Only these exact repository-relative untracked paths may be excluded from the
runtime untracked result:

```text
data/printer_v1.sqlite3-journal
data/printer_v1.sqlite3-wal
data/printer_v1.sqlite3-shm
```

The allowlist rejects absolute paths, traversal, directories, and glob syntax.
No suffix-wide allowance and no broad `.gitignore` weakening were added.

## Failure terminalization repair

The failure boundary now begins immediately after campaign graph creation. Any
later exception stops heartbeat coordination and attempts canonical supervision
cleanup, campaign-owned work reconciliation, lease release, and terminal report
persistence. Cleanup occurs before graph reconciliation because that is the
accepted canonical ownership order.

The first stored terminal cause is preserved. Closure diagnostics are attached
to, but never replace, the original exception; the original is re-raised.
Terminal reports and return payloads keep:

```text
restart_created=false
successor_created=false
```

## Exact recovery boundary

The new recovery command is deliberately fixed to this execution. It required:

- explicit operator approval;
- the revised expected current SHA;
- the exact pre-campaign backup SHA;
- exact identities and exact hashes for all five added graph rows;
- no other table delta;
- the exact STOP_REQUESTED/STOPPING cooperative-stop state;
- expired database and filesystem leases;
- exact lock-file ownership;
- no live Printer owner;
- zero global active/locked Scheduler work;
- zero campaign-owned active work;
- unchanged retrieval and financial row-content hashes.

It created and restore-verified this fresh backup outside Git:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8-recovery/20260726T140335Z-841c68da1cf8/printer_v1.pre-recovery.backup.sqlite3
SHA-256: 2db1a11456771a0c5d48e8cee801d29860f21e11de0c70d86db1dd66068ed39a
```

Restore rehearsal:

```text
/Users/Dtwo1/PrinterOperations/v2-9-8-recovery/20260726T140335Z-841c68da1cf8/printer_v1.recovery-restore-rehearsal.sqlite3
integrity: ok
foreign-key violations: 0
migrations: 42/42
```

Recovery used `cleanup_campaign_supervision()`,
`reconcile_campaign_terminal()`, and `write_campaign_terminal_report()`. It did
not manually patch rows or delete history.

## Recovered authoritative state

Final authoritative SHA:

```text
6bc642018aec12c1a9cc09b950de390f4927d75e53a7bc4965c0c509fe4909f1
```

Recovered state:

```text
campaign_state: TERMINAL_FAILED
run_state: TERMINAL_FAILED
cycle_state: TERMINAL_FAILED
supervision_state: TERMINAL
terminal_status: FAILED
first_terminal_cause: OPERATIONAL_CAMPAIGN_FAILED:GitProvenanceError
cleanup_completed_at: 2026-07-26T14:03:35.964509+00:00
lease_released_at: 2026-07-26T14:03:35.964509+00:00
cancellation_reason: OPERATOR_REQUESTED_COOPERATIVE_STOP
```

- The terminal cause is identical on campaign, run, cycle, supervision, and
  report.
- The stale lease file is absent.
- Campaign-owned active work is zero.
- Active/locked Scheduler jobs are zero.
- Integrity is `ok`; foreign-key violations are zero.
- Full-row `EXCEPT` comparisons against the pre-campaign backup show zero
  retrieval, financial, and source delta.
- Source calls, Scheduler runtime calls, restarts, and successors are zero.
- Report hash:
  `917c754c7317ada04049cd4b829e09bf4454598564de94390af01c1be20a3f22`.

## Tests and disposable proof

Focused command:

```text
.venv/bin/python -m pytest -q \
  tests/test_v2_9_7b_5_embedded_git_provenance.py \
  tests/test_v2_9_8a_public_operational_command.py \
  tests/test_v2_9_8b_1_first_operation_blocker_repair.py
```

Result:

```text
21 passed, 4 subtests passed
```

This proves exact sidecars are allowed; arbitrary untracked, tracked, and staged
changes remain blocked; the original post-initialization exception is re-raised
after terminalization; recovery rejects wrong SHA, wrong identities, a live
process, live lease, active Scheduler work, and unexpected row delta; locked
rows are content-preserved; complete disposable recovery succeeds; and repeat
recovery is zero-write idempotent.

Directly affected regression batches also produced 61 passing tests in the
authoritative owners and 49 passing tests plus 41 passing subtests across lease,
abstract-command, cleanup, and lifecycle owners. Six failures were investigated
and reproduced unchanged from an untouched archive of baseline HEAD:

- five `test_v2_9_7d_7a_abstract_command_surface.py` fixtures expect an older
  latest-migration reference;
- one `test_v2_9_7e_1_insufficient_pool_terminal_cleanup.py` fixture expects a
  Scheduler cancellation although its fixture creates no cancellable job.

They do not import or exercise the changed recovery/provenance boundary and were
not loosened or repaired in this lane. Changed Python files and focused tests
also passed `compileall`; `git diff --check` passed.

The disposable proof made zero source calls, created no restart or successor,
preserved locked table content, wrote one canonical terminal report, released
its lease, and returned the same DB SHA on idempotent replay.

## Final public-command preflight

All modes ran through:

```text
scripts/Start-PrinterV1-MemoryFactory.ps1
```

No `-Mode run` command was executed.

### `preflight-only`

```text
status: V2_9_8_OPERATIONAL_PREFLIGHT_READY
git_head: 963627ab47f3431f9d3eda2a5265e8ea5396f6ff
git tracked/staged/unstaged/untracked: clean/false/false/false
source_calls: 0
scheduler_runtime_calls: 0
database_writes: 0
integrity: ok
foreign-key violations: 0
DB SHA before/after: 6bc642018aec12c1a9cc09b950de390f4927d75e53a7bc4965c0c509fe4909f1
```

### `status`

```text
mode: STATUS
supervision_state: TERMINAL
terminal_status: FAILED
first_terminal_cause: OPERATIONAL_CAMPAIGN_FAILED:GitProvenanceError
new_child_work_allowed: false
source_calls: 0
scheduler_runtime_calls: 0
database_writes: 0
DB SHA unchanged: 6bc642018aec12c1a9cc09b950de390f4927d75e53a7bc4965c0c509fe4909f1
```

### `report-only`

```text
mode: REPORT_ONLY
artifact_matches: true
report_rows: 1
duplicate_reports_created: 0
new_source_calls: 0
new_scheduler_work: 0
database_writes: 0
restart_created: false
successor_created: false
all downstream unlocks: false
DB SHA unchanged: 6bc642018aec12c1a9cc09b950de390f4927d75e53a7bc4965c0c509fe4909f1
```

## Money-usefulness contribution

This repair does not claim profit or create paper-trading activity. Its
money-usefulness contribution is operational truth: expected SQLite mechanics
can no longer abort a clean launch, while arbitrary repository dirt still
blocks; every initialized failure is left auditable and terminal; and recovery
cannot silently mutate clean memory, retrieval evidence, or financial history.
That protects future paper-performance evidence from orphan ownership, hidden
work, and false provenance failures.

## What improved

- Exact runtime SQLite companions no longer create false Git dirt.
- Tracked, staged, and arbitrary untracked changes still fail closed.
- Post-initialization exceptions preserve the original fault and finish
  canonical terminal ownership.
- The existing orphan is terminal, reported, lease-released, and replayable.
- Recovery is exact-state, exact-SHA, exact-identity, exact-delta, backed up,
  restore-rehearsed, and idempotent.
- Public status/report paths prove zero-source and zero-write behavior.

## What remains locked

- V2-9.8B is not complete.
- No new campaign, restart, successor, or automatic retry.
- No production rerun.
- No 1h, 4h, 12h, or 24h production expansion.
- No retrieval activation.
- No paper decisions.
- No BUY, SELL, or HOLD.
- No positions, trade events, paper audits, or PnL.
- No live execution, wallet, private key, signing, or real funds.
- No paid source, scoring, ranking, confidence, or weighted logic.
- No embeddings or vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Current disposition |
|---|---|
| Recovery is intentionally one-execution-only | Safe for this incident; a generic recovery surface remains out of scope |
| Original failure occurred before source/Scheduler work | No market-data proof was gained; a new operation requires separate authorization |
| Baseline abstract-command test fixtures reference an old latest migration | Reproduced at untouched HEAD; deferred because unrelated to this repair |
| Baseline insufficient-pool fixture expects a nonexistent cancellation | Reproduced at untouched HEAD; deferred because unrelated to this repair |
| SQLite companions remain transient | Exact path tests protect provenance; continue monitoring journal-mode behavior |
| Process detection is conservative | Recovery also requires exact expired dual leases and exact database delta |
| Report records a failed operation | Truthful and immutable; it is not evidence of money performance |

## Next permitted action

A separately authorized retry of the first bounded V2-9.8B operation may be
considered from a clean worktree. This closeout does not provide that
authorization.
