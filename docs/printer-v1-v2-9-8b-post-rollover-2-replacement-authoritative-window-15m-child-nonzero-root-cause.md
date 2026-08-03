# Printer V1 V2-9.8B Post-Rollover-2 Replacement Authoritative WINDOW_15M Child Nonzero Root-Cause Capture

Date: 2026-08-03

Lane:

`V2-9.8B Post-Rollover-2 Replacement Authoritative WINDOW_15M Child Nonzero Root-Cause Capture`

This lane is read-only inspection and documentation only. No repair, source edit,
test, provider call, Scheduler runtime, campaign command, DB mutation,
authorization creation, cleanup, reset, or rerun was performed.

## Verdict

`V2_9_8B_POST_ROLLOVER_2_REPLACEMENT_AUTHORITATIVE_WINDOW_15M_CHILD_NONZERO_ROOT_CAUSE_CAPTURED`

## Authorization state

Authorization ID:

`V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z`

Recorded state:

```text
CONSUMED
PERMANENTLY_NON_REUSABLE
```

Consumption evidence:

| Evidence | Value |
| --- | --- |
| Canonical application marker | present, immutable (`-r--r--r--`) |
| `authorization_consumed_at` | `2026-08-03T21:28:01.121959+00:00` |
| Wrapper start | `2026-08-03T21:28:01.121992+00:00` |
| Child launch | `child_start_attempted=true`, `child_pid=8302` |
| Wrapper terminal result | `CHILD_EXITED_NONZERO`, `child_exit_code=1` |

This authorization may never be reused for another attempt, retry, resume,
restart, or successor.

## Baseline preservation (unmodified)

### Git / workspace

| Field | Value |
| --- | --- |
| Current HEAD | `6bb73ca165469fd60171098ff700241ec5667b34` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Ahead of origin | 18 commits |
| Tracked / staged dirty | none |
| Tracked worktree | clean |

Visible untracked inventories (complete at capture):

```text
operator-runs/v2-9-8b-authoritative-mig050/
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/
```

Visible untracked files under those packages (authorization package restored and
left in place; Migration-050 package left in place):

```text
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_started.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stderr.txt
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stdout.txt
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/backup_restore_preflight.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/closeout_inputs.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/final_authorization.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/post_migration_proof.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preauthorization_evidence.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preflight.json
operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/rollback_rehearsal.json
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/authorization_report.md
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/binding_inventory.json
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/consumed_on_start_rule.md
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/exact_manual_command.md
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/final_authorization.json
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/final_authorization.sha256
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/readiness_reference.md
operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/stop_conditions.md
```

Ignored-untracked inventory summary (top path groups; complete listing was
enumerated via `git ls-files --others --ignored --exclude-standard` and is
dominated by local environment noise):

| Group | Approx. file count |
| --- | ---: |
| `.venv/lib` | 1989 |
| `tests/__pycache__` | 573 |
| `src/printer_v1/**/__pycache__` and package tree | 281 |
| `.venv/bin` | 73 |
| `src/printer_v1.egg-info` | 6 |
| `operator-runs/v2-9-8b-authoritative-mig050` ignored sidecars | 2 |
| `.pytest_cache` | 4 |
| `data/printer_v1.sqlite3` | 1 |
| `.claude/settings.local.json` | 1 |
| `.DS_Store` | 1 |

No reset to the authorization-evidence commit was performed. The restored
authorization package was not removed.

### Process and `/private/tmp/mp-preclaim`

| Check | Result |
| --- | --- |
| Child PID 8302 | not running |
| Relevant Printer processes | none observed |
| `/private/tmp/mp-preclaim` | present; points at worktree `gitdir: /Users/Dtwo1/Developer/MoneyPrinter/.git/worktrees/mp-preclaim` |
| Preclaim content | historical lane-x outputs, docs, migrations through 050, scripts, src, tests (unchanged; not modified) |

### Application package

Directory:

`/Users/Dtwo1/PrinterOperations/v2-9-8/window-15m-one-shot-applications/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z`

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `application-marker.json` | 905 | `49d91b61bcc1a6310b18fe266a8f5dcdf725048031d19640b61d7dd9096f7c00` |
| `git-provenance-manifest.json` | 6958 | `c6331641ea1fe1789312a42a64f2f1a02a44f6c71b4de0442e0112f846036da6` |
| `wrapper-terminal.json` | 1750 | `5e04cf20543384a520890db583fe19343f30362112b19aa6a0087284ca9e7297` |
| `child-stderr.txt` | 383 | `4828f080e4d1142b8d467adc4e0d1e79d30ca1b3d6dcd3fd27ea7f1349ffe821` |
| `child-stdout.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

All five artifacts are immutable (`-r--r--r--`).

## Invocation and package bindings

### Application marker

Schema: `PRINTER_V1_APPLICATION_MARKER_V1`

| Field | Value |
| --- | --- |
| `authorization_id` | `V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z` |
| `authorization_sha256` | `5524ada42b3da1a56516ccbb5cfe821b3414ee0653d516453fd4212cb3439c03` |
| `manifest_sha256` | `c6331641ea1fe1789312a42a64f2f1a02a44f6c71b4de0442e0112f846036da6` |
| `authorization_consumed_at` | `2026-08-03T21:28:01.121959+00:00` |
| `repository_head` | `6bb73ca165469fd60171098ff700241ec5667b34` |
| `repository_branch` | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| `allowed_invocation_count` | 1 |
| retry/rerun/resume/restart/successor | all `false` |
| command | `mode=run`, `operator_approved=true` |

### Git provenance manifest

Schema: `PRINTER_V1_GIT_PROVENANCE_MANIFEST_V1`

| Field | Value |
| --- | --- |
| Created at | `2026-08-03T21:28:01.011080+00:00` |
| Authorization file | `operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z/final_authorization.json` |
| Authorization file SHA-256 | `5524ada42b3da1a56516ccbb5cfe821b3414ee0653d516453fd4212cb3439c03` |
| Repository HEAD | `6bb73ca165469fd60171098ff700241ec5667b34` |
| Migration execution ID | `V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f` |
| File set | 12 Migration-050 evidence paths + 8 WINDOW_15M authorization evidence paths |

Marker `manifest_sha256` equals the on-disk hash of
`git-provenance-manifest.json`.

### Complete wrapper result

Schema: `PRINTER_V1_WINDOW_15M_ONE_SHOT_WRAPPER_V1`

```text
terminal_classification = CHILD_EXITED_NONZERO
child_exit_code = 1
child_start_attempted = true
child_pid = 8302
automatic_retries = 0
manual_reruns = 0
restarts = 0
resumes = 0
successors = 0
process_start_error = null
parent_environment_mutated = false
started_at = 2026-08-03T21:28:01.121992+00:00
ended_at   = 2026-08-03T21:28:30.355131+00:00
repository_head = 6bb73ca165469fd60171098ff700241ec5667b34
wrapper_execution_id = V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z
```

Child command:

```text
/Users/Dtwo1/Developer/MoneyPrinter/.venv/bin/python
-m
printer_v1.operator_cli.operational_memory_factory_command
run
--operator-approved
```

Child log bindings recorded by the wrapper:

| Stream | Exists | Size | SHA-256 |
| --- | --- | ---: | --- |
| stdout | true | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| stderr | true | 383 | `4828f080e4d1142b8d467adc4e0d1e79d30ca1b3d6dcd3fd27ea7f1349ffe821` |

No automatic retry, manual rerun, restart, resume, or successor was created.

## Exact child stderr (complete 383 bytes)

No secrets were present. Exact content:

```json
{"action_run_id": "20260803T212801Z-4f7377e702c7-campaign-run", "campaign_source_calls": 30, "database_writes": 0, "error_message": "initialized factory-run identity changed", "error_type": "OperationalMemoryFactoryError", "mode": "run", "restart_created": false, "scheduler_runtime_calls": 0, "source_calls": 30, "status": "OPERATIONAL_COMMAND_BLOCKED", "successor_created": false}
```

Child stdout is empty (0 bytes).

### Stderr field interpretation

| Field | Value | Notes |
| --- | --- | --- |
| `status` | `OPERATIONAL_COMMAND_BLOCKED` | Public CLI exception envelope |
| `error_type` | `OperationalMemoryFactoryError` | Exception class |
| `error_message` | `initialized factory-run identity changed` | Immutable first operational cause for nonzero exit |
| `action_run_id` | `20260803T212801Z-4f7377e702c7-campaign-run` | Campaign-run identity, not factory-run UUID |
| `campaign_source_calls` / `source_calls` | 30 | Governed source activity occurred |
| `scheduler_runtime_calls` | 0 | No Scheduler runtime observer records |
| `database_writes` | 0 | **Hardcoded zero on the exception envelope** — not a true write counter (see DB delta below) |
| restart / successor | false | No follow-on work |

## Immutable first operational cause

### Exception and ownership

| Item | Value |
| --- | --- |
| Exception type | `OperationalMemoryFactoryError` |
| Message | `initialized factory-run identity changed` |
| Traceback owner | `printer_v1.operator_cli.operational_memory_factory_command` |
| Exact site | `retain_factory_run_id()` at `src/printer_v1/operator_cli/operational_memory_factory_command.py:2158-2168` |
| Raise line | `2166-2168` |
| Call site that fed the wrong identity | `operational_memory_factory_command.py:2236-2239` after `active_owner.run_operational(...)` returned |

### What the guard does

At campaign start the coordinator pre-generates:

```text
initialized_factory_run_id = str(uuid.uuid4())
```

(`operational_memory_factory_command.py:1968`)

`retain_factory_run_id(candidate)` does **not** adopt a new identity. It only
asserts equality:

```text
if initialized_factory_run_id != candidate:
    raise OperationalMemoryFactoryError("initialized factory-run identity changed")
```

### How the wrong candidate was supplied

Pre-lifecycle shortage / supply-block returns from the live operational owner set:

```text
lifecycle["run_id"] = command.run_id   # campaign-run identity
lifecycle_started = False
```

Observed owner site pattern:

`src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
around the graduated-supply shortage / pre-lifecycle return
(`"run_id": command.run_id`, `lifecycle_started=False`).

After `run_operational` returns, the coordinator **always** does:

```text
lifecycle = dict(result.lifecycle)
returned_factory_run_id = str(lifecycle.get("run_id") or "").strip() or None
if returned_factory_run_id is not None:
    retain_factory_run_id(returned_factory_run_id)
```

This runs **before** the pre-lifecycle branch that would honor
`result.lifecycle_started is False`.

Therefore a truthful pre-lifecycle return that carries campaign-run identity in
`lifecycle["run_id"]` is misread as a factory-run identity, compared to the
pre-generated UUID, and hard-fails.

### Failure phase

| Phase | Occurred? |
| --- | --- |
| Before campaign creation | no — campaign rows exist |
| Wrapper / child launch | succeeded |
| Operational preflight | passed far enough to create campaign supervision and discovery supply work |
| Discovery / graduated supply | yes — 30 governed source calls; exhaustion certificate written |
| Activation / token-slot handoff | no durable token slots |
| Lifecycle factory entry | no durable `printer_memory_factory_runs` row for the report-carried factory UUID |
| Cleanup | yes — completed and lease released |
| Wrapper classification | later envelope only; does not replace the child cause |

Immutable first cause for the nonzero child exit:

```text
OperationalMemoryFactoryError: initialized factory-run identity changed
```

at post-`run_operational` identity retain, while processing a pre-lifecycle
return that already carried campaign-run identity and zero eligible supply.

This is **not** replaced by later cleanup status, wrapper classification, or the
hardcoded `database_writes: 0` envelope field.

### Concurrent pre-lifecycle market/supply fact (not the exit exception)

Discovery exhaustion certificate for this campaign:

| Field | Value |
| --- | --- |
| Certificate ID | `exh-20260803T212801Z-4f7377e702c7` |
| `shortage_classification` | `SOURCE_VISIBILITY_SHORTAGE` |
| `eligible_count` / `eligible_reserve_count` | 0 / 0 |
| `required_eligible_capacity` | 2 |
| `unique_tokens_observed` | 34 |
| `rejected_count` | 34 |
| `source_operations_used` | 30 |
| `last_reason_discovery_could_not_continue` | `DISCOVERY_OPERATION_BUDGET_EXHAUSTED` |
| Top rejection reasons | `LIQUIDITY_SOURCE_dexscreener_malformed_fixture` (16), `LIQUIDITY_BELOW_SELECTION_FLOOR` (11), `TERMINAL_TRACKING_STATE` (5), `DUPLICATE_ACTIVE_TRACKING` (2) |

Seventeen `printer_source_failures` rows were written during the run window,
including one exact Pump migration transaction rejection and sixteen DexScreener
pair-market snapshot failures labeled `dexscreener_malformed_fixture` /
`DexScreener fixture missing pairs` (label language is historical; these rows
timestamp with the live run and pair-market request kinds).

That supply shortage is real concurrent operational evidence. It is **not** the
exception that produced child exit code 1. The committed identity-retain defect
masked what should have been a clean pre-lifecycle shortage terminal.

## Child-launch and campaign execution identities

| Identity | Value |
| --- | --- |
| Authorization | `V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z` |
| Execution HEAD | `6bb73ca165469fd60171098ff700241ec5667b34` |
| Wrapper execution ID | `V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z` |
| Child PID | 8302 (exited; not running at capture) |
| Execution / artifact root | `20260803T212801Z-4f7377e702c7` |
| Campaign ID | `20260803T212801Z-4f7377e702c7-campaign` |
| Campaign run ID | `20260803T212801Z-4f7377e702c7-campaign-run` |
| Cycle ID | `20260803T212801Z-4f7377e702c7-cycle` |
| Configuration ID | `20260803T212801Z-4f7377e702c7-configuration` |
| Supervision ID | `20260803T212801Z-4f7377e702c7-supervision` |
| Owner ID | `20260803T212801Z-4f7377e702c7-owner` |
| Report ID | `20260803T212801Z-4f7377e702c7-report` |
| Report-carried factory_run_id | `7b21755c-65a5-4ff4-b96e-8d010add5a89` |
| Durable factory run row for that UUID | **not found** |

Campaign artifact directory:

`/Users/Dtwo1/PrinterOperations/v2-9-8/20260803T212801Z-4f7377e702c7`

| Artifact | SHA-256 / note |
| --- | --- |
| `printer_v1.pre-campaign.backup.sqlite3` | `d85442e630c2eac3b71021e2e3a33ecbd3a729517caf90aa9dbf936f08925cbe` (matches authorization-time DB hash) |
| `printer_v1.restore-rehearsal.sqlite3` | same hash as pre-campaign backup |
| `terminal-summary.json` | `f0c89ba4f2d50ac70a7c53119e96b8844567bfee07ce5ec724bcf3c87dfba3f5` |
| `reports/...campaign-report.json` | `6dbb45123a01d276745f3b01a1e1aa8650e5289781e42d9eea74789b44d3d68b` |
| `campaign.lease.lock` | absent after cleanup (`lease_released=true`) |

Terminal summary highlights:

```text
status = OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE
first_terminal_cause = OPERATIONAL_CAMPAIGN_FAILED:OperationalMemoryFactoryError
original_exception_type = OperationalMemoryFactoryError
cleanup_completed = true
lease_released = true
active_owned_work_after = 0
cancelled_scheduler_jobs = 0
restart/resume/successor/automatic_retries = 0
factory_run = not_found
records.campaign/run/cycle = TERMINAL_FAILED
```

Note: reconciliation reports `lifecycle_started=true` because terminalization was
fed the pre-generated factory UUID even though no durable factory-run row exists.
That reporting flag must not be read as proof that lifecycle collection started.

## Authoritative database identity and delta

### Before / after identity

| State | Path | Size | SHA-256 | Inode |
| --- | --- | ---: | --- | ---: |
| Authorization binding / pre-campaign backup | `data/printer_v1.sqlite3` at auth time; preserved as `.../printer_v1.pre-campaign.backup.sqlite3` | 65806336 | `d85442e630c2eac3b71021e2e3a33ecbd3a729517caf90aa9dbf936f08925cbe` | 1230526 (auth binding) |
| Current authoritative after run | `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3` | 65896448 | `a4a36867f563d3c900c3b5efffe27b0c8eb7191a8a066ab5e944886a50077b7c` | 1230526 (same file) |

Sidecars at capture:

| Sidecar | Present |
| --- | --- |
| `printer_v1.sqlite3-wal` | no |
| `printer_v1.sqlite3-shm` | no |
| journal | no |

Migration head remains:

```text
050_campaign_scheduler_ownership_scope.sql | applied_at 2026-08-01 20:44:32
```

Integrity / FK (read-only):

```text
PRAGMA integrity_check = ok
PRAGMA foreign_key_check = 0 rows
```

**Do not infer “no DB change” from the ~29s runtime or from stderr
`database_writes: 0`.** The authoritative corpus changed.

### Runtime / DB delta matrix (pre-campaign backup vs current)

| Entity | Pre | Auth now | Delta | This-run identity present? |
| --- | ---: | ---: | ---: | --- |
| Campaigns | 20 | 21 | +1 | yes — `TERMINAL_FAILED` |
| Campaign runs | 20 | 21 | +1 | yes — `TERMINAL_FAILED` |
| Campaign cycles | 20 | 21 | +1 | yes — `TERMINAL_FAILED` |
| Campaign supervision | 20 | 21 | +1 | yes — `TERMINAL` / `FAILED`; cleanup completed |
| Campaign configurations | 20 | 21 | +1 | yes |
| Campaign reports | 19 | 20 | +1 | yes — terminal report row |
| Discovery exhaustion certificates | 2 | 3 | +1 | yes — shortage cert |
| Holder campaign operation ledgers | 18 | 19 | +1 | yes — 30 governed requests recorded |
| Graduated market floor state | 46 | 47 | +1 | yes (one row growth) |
| Source requests | 1756 | 1786 | +30 | yes — matches source_calls |
| Source responses | 1617 | 1630 | +13 | yes |
| Source failures | 139 | 156 | +17 | yes — run-window failures |
| Token slots | 18 | 18 | 0 | **none for this campaign** |
| Campaign windows | 2 | 2 | 0 | **none for this campaign** |
| Memory windows | 162 | 162 | 0 | none for this campaign |
| Factory runs | 7 | 7 | 0 | **none for report factory UUID** |
| Factory run steps | 72 | 72 | 0 | none |
| Campaign scheduler work | 10 | 10 | 0 | none for this campaign |
| Discovery work / batches | 80 / 10 | 80 / 10 | 0 | none for this campaign |
| Scheduler jobs | 1375 | 1375 | 0 | no new jobs; no active/locked residue |

Campaign row facts:

```text
campaign_state = TERMINAL_FAILED
first_terminal_cause = OPERATIONAL_CAMPAIGN_FAILED:OperationalMemoryFactoryError
db_mode = OPERATIONAL_PERSISTENT
db_target_identity = sha256:d85442e630c2eac3b71021e2e3a33ecbd3a729517caf90aa9dbf936f08925cbe
created_at = 2026-08-03T21:28:01.778406+00:00
terminal_at = 2026-08-03T21:28:30.324528+00:00
```

Supervision:

```text
supervision_state = TERMINAL
terminal_status = FAILED
cleanup_completed_at = 2026-08-03T21:28:30.324528+00:00
lease_released_at = 2026-08-03T21:28:30.324528+00:00
```

### Scheduler and residue matrix

| Check | Result |
| --- | --- |
| Active PENDING/RUNNING/CLAIMED/LOCKED jobs | 0 |
| Jobs with non-empty lock_owner | 0 |
| Campaign-scoped scheduler work rows | 0 for this campaign |
| Discovery work rows | 0 for this campaign |
| Token slots / campaign windows | 0 for this campaign |
| Cleanup completed | true |
| Lease released | true |
| Active owned work after cleanup | 0 |
| Restart / resume / successor / automatic retries | 0 |

Global job status distribution remains terminal-only
(`SUCCEEDED=1316`, `CANCELLED=45`, `FAILED=14`); no active residue introduced by
this run.

### Locked-capability counts

| Capability table / concept | Pre | Auth now | This-run delta |
| --- | ---: | ---: | ---: |
| `printer_memory_retrieval_matches` | 0 | 0 | 0 |
| `printer_paper_decisions` | 2 | 2 | 0 (pre-existing June 2026 rows only) |
| `printer_paper_positions` | 0 | 0 | 0 |
| `printer_paper_trade_events` | 0 | 0 | 0 |
| `printer_paper_trade_audits` | 0 | 0 | 0 |
| `printer_paper_decision_audits` | 0 | 0 | 0 |

Campaign report downstream unlock flags remain false for retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL.

Retrieval, decisions, positions, trades, audits, and PnL remain zero for this
invocation. Historical paper-decision rows (2) are pre-existing and unchanged.

## Root-cause classification

Primary classification (exactly one):

```text
COMMITTED_CODE_DEFECT
```

### Justification

The child exited nonzero because committed coordinator code treated a
pre-lifecycle `lifecycle["run_id"]` value that holds the **campaign-run**
identity as if it were the immutable **factory-run** identity, then fail-closed
in `retain_factory_run_id`.

That defect is:

- reproducible from static code inspection plus this exact artifact set;
- independent of provider flakiness for the *exception type*;
- sufficient to turn an otherwise pre-lifecycle shortage return into
  `OPERATIONAL_COMMAND_BLOCKED` / `CHILD_EXITED_NONZERO`.

### Secondary facts (not the primary classification)

| Fact | Classification if considered alone | Role here |
| --- | --- | --- |
| `SOURCE_VISIBILITY_SHORTAGE`, eligible=0 after 30 source ops | `MARKET_SUPPLY_OR_ELIGIBILITY_BLOCKER` | concurrent honest pre-lifecycle outcome that should have terminalized without identity exception |
| DexScreener pair response failures / Pump migration reject | `LIVE_PROVIDER_OR_SOURCE_FAILURE` (partial) | contributed to eligibility shortage; not the exit exception |
| Authorization / wrapper binding | not defective | marker, manifest, HEAD, and one-shot consumption behaved correctly |
| Cleanup / residue | clean | not the first cause |

### Repair / readiness / re-authorization answers

| Question | Answer |
| --- | --- |
| Is production repair justified? | **Yes** — narrow coordinator/owner identity-contract repair so pre-lifecycle returns do not pass campaign-run IDs through the factory-run retain guard, and so pre-lifecycle shortage terminals are not converted into `OperationalMemoryFactoryError`. |
| Is an operator prerequisite alone sufficient? | **No** — operator cannot fix the identity misbind without a code repair. Market supply may still block a later healthy attempt, but that is a separate expected operational outcome. |
| Is a new readiness lane required before another attempt? | **Yes, after repair** — at minimum a focused offline/bounded proof of the identity-retain / pre-lifecycle path, then a fresh authoritative readiness audit, then a **new** one-use authorization if and only if readiness PASSes. |
| Could another authorization ever be considered after repair/readiness? | **Yes, only after** repair + proof + closeout + fresh readiness PASS + **new** exact-HEAD one-use authorization. The current authorization remains permanently non-reusable. |

Do **not** create a replacement authorization in this lane.

## Exact next permitted lane

```text
V2-9.8B Post-Rollover-2 Pre-Lifecycle Factory-Run Identity Retain Defect Repair Design
```

Design/specification only until separately approved. It may define:

- the exact identity contract for `lifecycle["run_id"]` vs factory-run UUID vs campaign-run ID;
- whether pre-lifecycle returns must omit factory-run fields or use a distinct key;
- ordering so `lifecycle_started=False` is honored before factory-run retain;
- honest terminal cause preservation for `SOURCE_VISIBILITY_SHORTAGE`;
- offline/bounded proof plan;
- non-goals (no campaign rerun, no authorization minting, no retrieval/financial unlock).

It may **not** implement the repair, rerun the wrapper/child, contact providers,
mutate the authoritative DB, or issue authorization.

## Money-usefulness contribution

This capture protects capital and roadmap honesty by:

1. proving the one authorized replacement authoritative 15m attempt was consumed
   and failed closed without leaving active Scheduler residue;
2. separating a committed identity defect (must repair) from market supply
   shortage (may recur even after repair);
3. preventing a false “rerun under the same auth” or “just operator env”
   response;
4. preserving the evidence chain needed for a narrow repair rather than a broad
   rewrite or unauthorized live retry.

It does **not** create clean memory, retrieval value, or paper profit.

## What remains locked

All V1 / V2-9.8B financial and expansion locks remain:

- retrieval activation
- paper decisions / BUY / SELL / HOLD
- paper positions, trade events, paper audits, PnL
- live wallet / private keys / real funds / live execution
- paid APIs
- scoring / ranking / confidence / weighted logic
- embeddings / vectors
- 1h / 4h / 12h / 24h production continuation under this consumed authorization
- automatic retry / resume / restart / successor under this authorization
- any reuse of `V2_9_8B_WINDOW_15M_AUTH_20260803T211336Z`

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Identity key collision risk (active defect):** pre-lifecycle owner returns
   place campaign-run IDs in `lifecycle["run_id"]` while the coordinator treats
   that field as factory-run identity. Any future shortage/block path can
   convert an expected safe stop into a hard command failure.
2. **Cause masking:** the durable terminal cause became
   `OPERATIONAL_CAMPAIGN_FAILED:OperationalMemoryFactoryError` instead of the
   supply shortage classification, reducing operator signal quality.
3. **`lifecycle_started` reporting inflation:** terminalization can report
   lifecycle started because a pre-generated factory UUID exists even when no
   factory-run row, token slots, or factory steps were created.
4. **Stderr write counter is not trustworthy on exception paths:**
   `database_writes` is hardcoded to `0` in the CLI exception envelope despite
   real campaign/source row growth.
5. **Market supply remains thin under current floors:** 34 unique tokens
   observed, 0 eligible, many liquidity malformations / below-floor outcomes.
   After the identity defect is repaired, a later authorized attempt may still
   terminalize on `SOURCE_VISIBILITY_SHORTAGE` without collecting 15m memory.
6. **Efficiency:** ~29 seconds and 30 governed source calls were spent, then
   aborted at identity retain without lifecycle collection. Repairing the retain
   contract recovers honest pre-lifecycle terminal accounting without requiring
   another full supply burn to diagnose this specific defect.
7. **Authorization economics:** one exact-HEAD authorization is permanently
   consumed. Progress now requires repair → proof → readiness → **new**
   authorization; no shortcut reuse is lawful.

## Verification performed (allowed only)

- read-only application package inspection and SHA-256
- Git status / HEAD / branch / untracked inventories
- complete child stderr/stdout byte and hash verification
- read-only SQLite inspection of authoritative DB and pre-campaign backup
- DB size/hash/inode/integrity/FK checks
- process and `/private/tmp/mp-preclaim` observation
- static code inspection of retain/return sites

## Verification not performed (forbidden)

- wrapper or child rerun
- pytest
- provider contact beyond historical rows already written by the failed run
- DB writes
- source/test/package edits (except this documentation deliverable)
- authorization creation
- cleanup or artifact deletion
- reset/checkout/push

## Stop condition

This lane stops after the root-cause report commit. No repair, rerun,
replacement authorization, or 15m/1h/4h command is authorized by this document.
