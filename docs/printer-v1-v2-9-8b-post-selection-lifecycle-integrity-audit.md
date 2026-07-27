# Printer V1 V2-9.8B.10A — Post-Selection Lifecycle Integrity Audit

## Verdict

```text
V2_9_8B_10A_POST_SELECTION_INTEGRITY_AUDIT_PASS
```

This audit is read-only. It does not rewrite execution
`20260727T001520Z-d513e21260b5`, does not run production, and does not unlock
any financial capability.

## Baseline

| Item | Value |
|---|---|
| Local HEAD | `f607e8946a78f78866076bc11efc4b69b43dd2a7` |
| Audited execution | `20260727T001520Z-d513e21260b5` |
| Artifact root | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260727T001520Z-d513e21260b5/` |
| First durable cause | `OPERATIONAL_CAMPAIGN_FAILED:IntegrityError` |

## Proven sequence

```text
PILOT_INPUT_READY bundle written
→ two SELECTED token slots (mint UUdf…, 7tKKxa…)
→ discovery work SUCCEEDED through TRACKING_HANDOFF_SLOT_1/2
→ origin-activated selection batch materialised
→ OriginLifecycleDriver invokes run_one_command_15m_factory(
     operational_persistent_mode=True)
→ INSERT printer_memory_factory_runs(... db_mode='OPERATIONAL_PERSISTENT' ...)
→ sqlite3.IntegrityError: CHECK constraint failed: db_mode = 'PROOF_ONLY'
→ zero factory-run rows, zero WINDOW_15M campaign windows
→ exception terminalization contends with open factory connection / heartbeat
→ cleanup/report initially fail with database is locked
```

## Exact failed statement and constraint

| Field | Value |
|---|---|
| Persistence function | `run_one_command_15m_factory` in `one_command_15m_factory.py` |
| SQL | `INSERT INTO printer_memory_factory_runs (run_id, run_status, window_kind, db_mode, config_hash, config_json, started_at, created_at, updated_at) VALUES (?, 'RUNNING', ?, ?, ?, ?, ?, ?, ?)` |
| Conflicting value | `db_mode = 'OPERATIONAL_PERSISTENT'` |
| Table | `printer_memory_factory_runs` |
| Constraint | `CHECK (db_mode = 'PROOF_ONLY')` from migration `028_memory_factory_run_ledger.sql` |
| Proven message | `CHECK constraint failed: db_mode = 'PROOF_ONLY'` |

Reproduction (disposable schema clone of production table):

* `PROOF_ONLY` insert → success  
* `OPERATIONAL_PERSISTENT` insert → IntegrityError (same message)

Caller wiring:

* Public operational command sets `fifteen_minute_only=True`
* `AuthoritativeLiveOperationalCampaignOwner.run_operational` passes
  `operational_persistent_mode=fifteen_minute_only`
* Factory config maps that flag to `db_mode='OPERATIONAL_PERSISTENT'`

Campaign table `printer_memory_factory_campaigns.db_mode` already allows
`OPERATIONAL_PERSISTENT` (migration 031). The factory-run ledger was never
widened when operational persistence was introduced.

## Classification

| Question | Answer |
|---|---|
| Deterministic? | **Yes** — every operational-persistent lifecycle entry hits the CHECK |
| Defect class | Schema / policy drift: invalid mode value for existing CHECK |
| Duplicate creation? | No |
| Invalid ownership transition? | No (failure is before window/run graph creation) |
| Missing predecessor? | No |
| Stale identity? | No |
| Transaction ordering? | Secondary: unclosed factory connection after insert failure worsens lock contention |

## Why zero `WINDOW_15M` rows

Lifecycle entry aborts on the first factory-run INSERT. No
`printer_memory_factory_runs` row is committed, so planning of opening jobs and
campaign window materialisation never runs. Observed:

* `printer_memory_factory_runs` count for this attempt: 0  
* `printer_memory_factory_campaign_windows` for campaign: 0  
* Token slots remain `SELECTED` (pre-lifecycle)

Cancelled `TRACK_NORMAL_FIRST_15M` scheduler jobs (998/999) are disposable
discovery handoff artefacts, not campaign lifecycle windows.

## Both `LATEST_GRADUATED` selections

**Incidental.** Readiness bundle successfully stored both tokens as
`LATEST_GRADUATED`. The IntegrityError is mode-CHECK based and would occur for
any two-token readiness that reaches operational lifecycle entry.

## Partial lifecycle / Scheduler state

| Surface | Partial write? |
|---|---|
| Factory run / steps | No |
| Campaign windows / campaign scheduler work | No |
| Token slots / tracking queue / selection batches | Yes (pre-lifecycle selection residue; intentional durable discovery result) |
| Discovery work / scheduler discovery jobs | Yes, already SUCCEEDED |
| Restart / successor | No |

## Heartbeat / `database is locked`

Contributing factors:

1. Factory opens a write connection, fails INSERT, and **does not close** the
   connection (INSERT sits outside the function’s `try/finally` that calls
   `conn.close()`).
2. Heartbeat renewer may hold short write locks on supervision rows.
3. Automatic `_terminalize_initialized_failure` then competes for `BEGIN IMMEDIATE`
   and report write; retained `terminal-summary.json` records:
   * `cleanup:OperationalError:database is locked`
   * `report:TerminalClosureError:... database is locked`

First cause remains IntegrityError (correct). Lock contention is a secondary
terminalization defect.

## Why public surface reported `source_calls: 0`

`operational_memory_factory_command.main` exception handler hard-codes:

```text
source_calls: 0
```

It does not read the durable holder ledger (`governed_requests=18` for this
run). Action-local zero is wrong for a post-initialization campaign fault once
a ledger exists.

## Owners inspected

* `src/printer_v1/operator_cli/one_command_15m_factory.py` — factory-run INSERT  
* `src/printer_v1/operator_cli/origin_lifecycle_campaign.py` — activation→lifecycle  
* `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py` — operational mode flag  
* `src/printer_v1/operator_cli/operational_memory_factory_command.py` — heartbeat, terminalize, public exception surface  
* `src/printer_v1/operator_cli/campaign_supervision.py` — lease renew / cleanup  
* `src/printer_v1/operator_cli/pilot_input_readiness.py` — readiness bundle (not the failure)  
* migrations `028`, `031`

## Money-usefulness note

Discovery productivity already proved two eligible tokens can be selected under
ceiling 45. This integrity defect is the gate that blocks those selections from
becoming `WINDOW_15M` memory collection.

## Stop condition

Exact defect is proven. Proceed to design.
