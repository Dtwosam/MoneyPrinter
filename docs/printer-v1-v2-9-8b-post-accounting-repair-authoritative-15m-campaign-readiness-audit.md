# Printer V1 V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit

Date: 2026-07-31

Lane:
`V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Readiness Audit`

Branch:
`codex/v2-9-8b-post-repair-15m-readiness-audit`

Inspected baseline HEAD:
`35258c4a3f4a4b8d3099d06345ce1afd1bf436c2`

Verdict:
`V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_15M_CAMPAIGN_READINESS_AUDIT_PASS`

## 1. Boundary

This was an audit/readiness lane only.

Allowed work performed:

- static source and documentation inspection of the ordinary repaired
  `WINDOW_15M` route;
- read-only SQLite open of `data/printer_v1.sqlite3` via `mode=ro`;
- SHA-256 before/after equality;
- read-only inspection of the permanent external no-rerun marker and July 31
  terminal-summary artifact;
- readiness documentation.

Not performed:

- operational command execution (`preflight-only`, `run`, `report-only`, or any
  other mode);
- providers, RPC, WebSockets, or source fetching;
- authoritative DB mutation or copy-back;
- recovery, N2, N7, cursor reset, campaign, tracking, lifecycle, snapshot,
  window, or memory generation;
- July 31 report repair or reclassification;
- tests or broad regression suites;
- runtime, test, migration, build-order anchor, or policy changes;
- 1h/4h/12h/24h, V2-10, retrieval, paper decisions, BUY/SELL/HOLD, positions,
  trades, audits, or PnL unlock.

## 2. Baseline and Inspected Commit

| Item | Value |
| --- | --- |
| Branch | `codex/v2-9-8b-post-repair-15m-readiness-audit` |
| Inspected HEAD | `35258c4a3f4a4b8d3099d06345ce1afd1bf436c2` |
| HEAD subject | `Correct historical operational campaign status` |
| Repair closeout | `docs/printer-v1-v2-9-8b-accounting-exact-identity-report-only-repair-closeout.md` |
| Repair implementation commits | `b168c57`, `fd35b41`, `0118a37` |
| Design baseline | `e71e543d197154eba427b41e2e01574a59f527f5` |
| Worktree at audit start | clean (no runtime/doc edits before this audit file) |

## 3. Ordinary Public Route Trace (Static)

Ordinary public entry:

```text
pyproject entry: printer-run-v2-9-8-memory-factory
  -> printer_v1.operator_cli.operational_memory_factory_command:main
```

Mode dispatch (`main`):

| Mode | Owner | Ordinary authority |
| --- | --- | --- |
| `preflight-only` | `build_activation_preflight` | readiness only |
| `run` | `run_operational_campaign` | ordinary two-token `WINDOW_15M` |
| `report-only` | `report_only` | exact-identity zero-source replay |
| `status` / `cooperative-stop` / `recover-orphan` | restricted helpers | not ordinary campaign start |
| `discovery-only` | qualification only | not campaign authority |
| `selective-1h-*` | separate proof policy | locked for ordinary run |
| candidate-acquisition / cursor-recovery | deferred helpers | not ordinary prerequisite |

Ordinary `run` path (static):

```text
main(run --operator-approved)
-> run_operational_campaign / _run_operational_campaign
-> build_activation_preflight + verified backup / restore rehearsal
-> CampaignSixUnitOwner created before first accounted stage
-> independent action_local_transport_identities observer installed
-> acquire_campaign_supervision + heartbeat
-> AuthoritativeLiveOperationalCampaignOwner.run_operational(
     fifteen_minute_only=True,
     accounting_stage_evidence_sink=owner.ingest only,
     transport_identity_observer=pre-seal measurement observer
   )
-> graduated/eligible supply:
     optional locator
     direct migration discovery
     multi-round exact-liquidity front door
     selection / tracking handoff when capacity ready
-> Source Governor + Central Scheduler for lifecycle (if started)
-> cleanup_campaign_supervision
-> reconcile_campaign_terminal
-> assemble_campaign_terminal_reporting
-> _finalize_operational_six_unit_accounting
     + reconcile_owner_to_action_local (pre-lifecycle exact identity gate)
-> build/write terminal report only when accounting complete
-> report-only exact campaign/run replay
-> safe stop (automatic_retries=0; restart/successor false)
```

Policy constants on the ordinary path:

| Constant | Value |
| --- | --- |
| `TOKEN_CAPACITY` | `2` |
| `MAIN_WINDOW` | `WINDOW_15M` |
| `TOTAL_DURATION_SECONDS` | `1200` |
| `AUTOMATIC_RETRIES` | `0` |
| `LOCKED_WINDOWS` | `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, `WINDOW_24H` |
| `AUTHORITATIVE_DB` | `data/printer_v1.sqlite3` (via `CANONICAL_PERSISTENT_DB`) |
| ordinary `fifteen_minute_only` | hard-coded `True` |
| ordinary selective-1h continuation | `False` |
| candidate acquisition | `DEFERRED_EXPERIMENTAL_NOT_OPERATIONAL_AUTHORITY` |

## 4. Evidence Table

| Claim | Evidence |
| --- | --- |
| Public command entry is non-placeholder | `pyproject.toml` console script `printer-run-v2-9-8-memory-factory`; module `operational_memory_factory_command.main` |
| Authoritative DB target | `AUTHORITATIVE_DB = Path(CANONICAL_PERSISTENT_DB).resolve()`; `CANONICAL_PERSISTENT_DB = .../data/printer_v1.sqlite3` |
| Required env names | `PRINTER_SOLANA_RPC_URL`, optional `PRINTER_HELIUS_API_KEY` in `operational_source_contracts.py` / readiness preflight |
| Two-token / 15m-only ordinary policy | `TOKEN_CAPACITY = 2`, `MAIN_WINDOW = "WINDOW_15M"`, `fifteen_minute_only=True`, `LOCKED_WINDOWS` |
| No proof-launcher ordinary dependency | Ordinary `run` uses `_NORMAL_CAMPAIGN_POLICY` and operational owner; no proof DB launcher |
| No N2/N7/cursor operational dependency | Deferred modes listed; ordinary run does not require them; `CANDIDATE_ACQUISITION_STATE` deferred |
| Pre-seal observer installed by coordinator | `_observe_transport_identity` + `transport_identity_observer=` in `_run_operational_campaign` |
| Owner sink is seal-ingest only | `_campaign_stage_evidence_sink` only calls `campaign_units.ingest_stage_evidence` |
| Observer reaches locator | `run_fresh_profile_locator` sets `MeasuredTransportLedger(on_transport_recorded=transport_identity_observer)` |
| Observer reaches direct migration | `direct_migration_discovery` assigns `measured_ledger.on_transport_recorded = transport_identity_observer` |
| Observer reaches each exact-liquidity round | `eligible_token_supply` passes observer into `run_graduated_liquidity_front_door`; front door ledger uses `on_transport_recorded` |
| Exception-safe sealing active | locator, direct-migration, and exact-liquidity stages seal/ingest in `finally` before unexpected exceptions escape |
| Exact identity reconciliation active | `reconcile_owner_to_action_local` requires both-direction identity-set equality; count-only -> `ACTION_LOCAL_TRANSPORT_IDENTITY_DESIGN_BLOCKED` |
| Exact report-only selection active | `_resolve_report_only_identity` + report query by exact campaign/configuration; no global newest-report fallback |
| Missing report/summary fail-closed | `EXACT_TERMINAL_REPORT_MISSING` vs `EXACT_TERMINAL_SUMMARY_MISSING_OR_MISMATCHED` |
| Migration head | 49 migrations; latest `049_candidate_acquisition_integration.sql` |
| Integrity | `PRAGMA integrity_check = ok`; foreign-key check rows `0` |
| DB SHA-256 before | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` |
| DB SHA-256 after | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` (equal) |
| No WAL/SHM/journal sidecars | only `data/printer_v1.sqlite3` present under `data/` |
| Active campaigns/runs/supervision | all campaign/run rows terminal (`TERMINAL_COMPLETED` or `TERMINAL_FAILED`); all supervision `TERMINAL` |
| Active Scheduler jobs/locks | status only `SUCCEEDED`/`FAILED`/`CANCELLED`; zero locked/runnable jobs |
| Discovery work / factory steps | only terminal `SUCCEEDED`/`FAILED`/`CANCELLED` |
| Candidate-acquisition leases active | zero active/stopping held leases; 19 terminal leases historical |
| July 31 campaign residual | campaign/run/cycle terminal with `SOURCE_VISIBILITY_SHORTAGE`; supervision terminal COMPLETED; lease released; cleanup completed |
| July 31 report row | `0` rows for that campaign |
| July 31 exhaustion certificate | present; classification `SOURCE_VISIBILITY_SHORTAGE`; 30 source ops used |
| July 31 terminal summary | present externally; `report_written=false`; `SIX_UNIT_ACCOUNTING_BLOCKED` / `SIX_UNIT_EVIDENCE_MISSING`; `restart_created=false`; `successor_created=false` |
| Permanent no-rerun marker | `$HOME/PrinterOperations/v2-9-8/first-authoritative-window-15m-attempt.json`; `attempt_number=1`; `rerun_authorized=false`; pins launch commit `b5761b65...` |
| Retrieval / financial baselines | retrieval matches `0`; retrieval queries `10`; paper decisions `2`; paper audit reports `1`; positions/trade events/trade audits `0` |

## 5. Independent Pre-Seal Observer Coverage

The public coordinator creates one action-local list and one observer. That
observer is passed through:

1. `AuthoritativeLiveOperationalCampaignOwner.run_operational`
2. `build_graduated_supply` / `run_persistent_eligible_token_supply`
3. optional locator stage
4. direct migration discovery stage
5. each exact-liquidity front-door round

At measurement time, `MeasuredTransportLedger.record_transport` invokes
`on_transport_recorded` **before** stage sealing. The campaign sink remains a
separate owner-ingest path and does not copy sealed transports into
action-local. This preserves independent verification rather than sealed-stage
self-comparison.

Pre-lifecycle completion requires exact owner/action-local identity equality.
Holder/lifecycle stages after lifecycle start are intentionally not forced into
that pre-lifecycle gate (documented residual risk from the repair closeout; not
a readiness blocker for ordinary pre-lifecycle accounting).

## 6. Exact Report-Only and Historical July 31 Behavior

Repaired `report-only`:

- requires both `--campaign-id` and `--run-id`, or neither;
- with neither, resolves newest **supervision** first, then that exact
  campaign/run/configuration;
- never selects the globally newest report first;
- returns deterministic `REPLAY_BLOCKED` when the exact report is missing.

Historical July 31 facts remain:

- campaign verdict `V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_BLOCKED_UNSAFE`;
- no terminal report row;
- terminal summary exists but lacks top-level `run_id` and `configuration_id`;
- under the repaired summary loader, incomplete summary identity fails closed
  rather than replaying the unrelated July 28 report;
- permanent marker forbids rerun of execution `20260731T002406Z-7612696c7295`.

This audit does not repair or reclassify that attempt.

## 7. Authoritative Residual State Summary

```text
DB: data/printer_v1.sqlite3
SHA-256: f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
integrity: ok
foreign_key_violations: 0
migration_rows: 49
migration_head: 049_candidate_acquisition_integration.sql
sidecars: none
```

Operational residual:

| Surface | Residual |
| --- | --- |
| Campaigns | 18 terminal historical rows (11 completed / 7 failed) |
| Runs | 18 terminal historical rows |
| Supervision | 18 terminal rows; zero non-terminal |
| Scheduler jobs | only SUCCEEDED/FAILED/CANCELLED; zero active/locked |
| Discovery work | only SUCCEEDED/FAILED |
| Factory steps | only SUCCEEDED/CANCELLED |
| Proof supervision | 0 rows |
| Active CA leases | 0 |
| July 31 lifecycle windows/slots/factory runs/discovery work/jobs | 0 |
| July 31 reports | 0 |
| Restart/successor/resume for July 31 | false / not present |

Residual history is present and expected after prior operator campaigns. No
active campaign, supervision, Scheduler lock, discovery work, factory step, or
proof supervision remains runnable.

## 8. Exact Command and Environment Contract

Readiness command shape (not executed by this audit):

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  preflight-only
```

Future ordinary campaign command shape (not authorized by this audit):

```bash
PYTHONPATH=src .venv/bin/python -m \
  printer_v1.operator_cli.operational_memory_factory_command \
  run --operator-approved
```

Equivalent entrypoint name:

```text
printer-run-v2-9-8-memory-factory
```

Environment-variable names (values not inspected/printed here):

- required: `PRINTER_SOLANA_RPC_URL`
- optional free holder backup: `PRINTER_HELIUS_API_KEY`

DB target:

```text
data/printer_v1.sqlite3
```

## 9. Readiness Blockers

None found that require mutation, execution, source access, or repair.

Non-blocking residual awareness items:

1. Historical July 31 attempt remains `BLOCKED_UNSAFE` with incomplete canonical
   report and incomplete top-level terminal-summary identity fields. The repaired
   report-only path fail-closes rather than replaying a stale report.
2. Permanent first-authoritative no-rerun marker remains in place and correctly
   blocks any rerun of execution `20260731T002406Z-7612696c7295`. A later
   post-repair campaign, if ever authorized, must use a new execution identity
   and its own design/authorization sequence.
3. Post-lifecycle holder/scheduler stages are still outside the pre-lifecycle
   action-local identity gate (repair residual risk).
4. This audit did not re-run zero-source preflight or local tests; runtime proof
   of the repair remains grounded in the prior implementation closeout and the
   static/DB evidence above.

## 10. Money-Usefulness Contribution

This readiness gate confirms that the accounting/exact-identity repair is
present on the ordinary route and that the authoritative corpus is quiet enough
to consider a later design/authorization packet. That reduces the chance a next
bounded 15m learning attempt starts with:

- incomplete stage accounting;
- sealed-stage self-comparison disguised as independent verification;
- stale report-only fallback;
- active Scheduler/supervision residue;
- accidental July 31 rerun; or
- retrieval/financial unlock drift.

Honest shortage and fail-closed accounting remain valid terminal outcomes.

## 11. What This Audit Improves

- re-validates the repaired ordinary public route after the accounting repair;
- confirms independent pre-seal observation and exact owner reconciliation;
- confirms exact-identity report-only fail-closed behavior;
- records current authoritative residual state without mutating it;
- preserves the permanent July 31 no-rerun boundary;
- establishes the evidence needed for a post-repair campaign design/runbook.

## 12. What This Audit Still Does Not Unlock

It does not unlock:

- campaign execution;
- providers/RPC/WebSockets/source fetching;
- July 31 repair, backfill, or reclassification;
- recovery, N2, N7, cursor reset, or candidate-acquisition authority;
- memory generation or clean-memory promotion;
- `WINDOW_1H` / `WINDOW_4H` / `WINDOW_12H` / `WINDOW_24H`;
- V2-10;
- retrieval;
- paper decisions, BUY/SELL/HOLD, positions, trades, audits, or PnL;
- wallets, private keys, signing, real funds, paid APIs, scoring, ranking,
  confidence, weighting, embeddings, or vectors.

A readiness PASS may authorize only the next approved design/specification or
final-authorization step. It does not authorize campaign execution.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

- Provider availability and two-token eligible supply remain unproved until an
  authorized live attempt; readiness cannot guarantee market visibility.
- Environment values can drift between this audit and any future authorization;
  a fresh zero-source preflight must be part of any later design/authorization
  packet.
- Historical terminal corpus rows remain in the authoritative DB; future
  readiness/preflight must continue to distinguish terminal history from active
  residue.
- The first-authoritative permanent marker must not be deleted or reused as a
  shortcut for a second attempt.
- Focused repair suites previously passed, but this audit intentionally did not
  re-run tests; any later implementation lane must not weaken those proofs.
- Post-lifecycle identity equality remains a residual design surface if full-run
  transport equality is required beyond pre-lifecycle shortage terminals.

## 14. Acceptance Gate

PASS because all of the following hold:

- repaired ordinary route statically includes independent pre-seal observation,
  exception-safe sealing, exact owner/action-local reconciliation, and exact-
  identity report-only fail-closed behavior;
- authoritative residual state is terminal-only with zero active/runnable work;
- exact non-placeholder command, DB target, env names, two-token/`WINDOW_15M`
  policy, and deferred N2/N7/cursor status are consistent;
- July 31 remains permanently no-rerun and `BLOCKED_UNSAFE` without
  retry/restart/resume/successor/recovery/reclassification;
- retrieval/financial baselines remain locked;
- authoritative DB SHA-256 is unchanged by this audit.

## 15. Exact Next Permitted Lane

```text
V2-9.8B Post-Accounting-Repair Authoritative WINDOW_15M Campaign Design and Operator Runbook
```

Type: design/specification only.

That lane must define the exact post-repair launch command packet, one-campaign
boundary, fresh preflight requirements, operator checkpoints, terminal evidence
bundle, stop conditions, interaction with the existing first-authoritative
no-rerun marker, and closeout requirements for a new execution identity.

It must not execute a campaign, contact providers/RPC, mutate the authoritative
database, repair the July 31 attempt, or unlock retrieval/financial capabilities.

## Appendix A. Read-Only Evidence Transcript

Date of transcript re-inspection: 2026-07-31

Purpose: exact reproducible read-only evidence for every authoritative residual-state
claim in this audit. No writable connection, no provider/RPC/source contact, no
preflight, no campaign/report-only command, no tests, no DB mutation/copy, and no
runtime/policy change.

Transcript result: every residual-state claim above was reproduced. No contradiction
was found; the readiness verdict remains
`V2_9_8B_POST_ACCOUNTING_REPAIR_AUTHORITATIVE_15M_CAMPAIGN_READINESS_AUDIT_PASS`.

### A.1 SQLite read-only connection setup

```text
authoritative relative path: data/printer_v1.sqlite3
authoritative resolved path: <repo>/data/printer_v1.sqlite3
URI: file:<repo>/data/printer_v1.sqlite3?mode=ro
open: sqlite3.connect(uri, uri=True)
PRAGMA query_only=ON
PRAGMA query_only readback: 1
writable connection: false
```

`<repo>` is the MoneyPrinter worktree root. No non-`mode=ro` connection was opened.

### A.2 Sidecar inspection

```text
listing under data/:
  printer_v1.sqlite3  size=64901120

WAL/SHM/journal present: none
```

### A.3 Authoritative DB SHA-256 before / after

```text
DB SHA-256 before: f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
DB SHA-256 after:  f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511
equality: true
```

### A.4 Migration count and latest migration

```sql
SELECT COUNT(*) AS migration_count,
       MAX(version) AS latest_migration
FROM printer_schema_migrations;
```

```text
(49, '049_candidate_acquisition_integration.sql')
```

```sql
SELECT version, applied_at
FROM printer_schema_migrations
ORDER BY version DESC
LIMIT 3;
```

```text
('049_candidate_acquisition_integration.sql', '2026-07-29 11:23:54')
('048_candidate_acquisition_foundation.sql', '2026-07-29 11:23:54')
('047_campaign_oneshot_linkage_binds.sql', '2026-07-28 17:34:10')
```

### A.5 Integrity and foreign-key checks

```sql
PRAGMA integrity_check;
```

```text
('ok',)
```

```sql
PRAGMA foreign_key_check;
```

```text
[]
ROW_COUNT: 0
```

### A.6 Campaigns and runs by state

```sql
SELECT campaign_state, COUNT(*) AS n
FROM printer_memory_factory_campaigns
GROUP BY campaign_state
ORDER BY campaign_state;
```

```text
('TERMINAL_COMPLETED', 11)
('TERMINAL_FAILED', 7)
```

```sql
SELECT COUNT(*) AS n FROM printer_memory_factory_campaigns;
```

```text
(18,)
```

```sql
SELECT run_state, COUNT(*) AS n
FROM printer_memory_factory_campaign_runs
GROUP BY run_state
ORDER BY run_state;
```

```text
('TERMINAL_COMPLETED', 11)
('TERMINAL_FAILED', 7)
```

```sql
SELECT COUNT(*) AS n FROM printer_memory_factory_campaign_runs;
```

```text
(18,)
```

### A.7 Supervision by state

```sql
SELECT supervision_state, terminal_status, COUNT(*) AS n
FROM printer_memory_factory_campaign_supervision
GROUP BY supervision_state, terminal_status
ORDER BY supervision_state, terminal_status;
```

```text
('TERMINAL', 'COMPLETED', 11)
('TERMINAL', 'FAILED', 7)
```

```sql
SELECT COUNT(*) AS n
FROM printer_memory_factory_campaign_supervision
WHERE supervision_state IS NULL OR supervision_state != 'TERMINAL';
```

```text
(0,)
```

### A.8 Scheduler job states and lock counts

```sql
SELECT status, COUNT(*) AS n
FROM printer_scheduler_jobs
GROUP BY status
ORDER BY status;
```

```text
('CANCELLED', 41)
('FAILED', 14)
('SUCCEEDED', 1282)
```

```sql
SELECT COUNT(*) AS n
FROM printer_scheduler_jobs
WHERE status NOT IN ('SUCCEEDED','FAILED','CANCELLED');
```

```text
(0,)
```

```sql
SELECT
  COUNT(*) AS total_jobs,
  SUM(CASE WHEN locked_at IS NOT NULL THEN 1 ELSE 0 END) AS locked_at_nonnull,
  SUM(CASE WHEN lock_owner IS NOT NULL AND lock_owner != '' THEN 1 ELSE 0 END)
    AS lock_owner_nonempty
FROM printer_scheduler_jobs;
```

```text
(1337, 0, 0)
```

```sql
SELECT id, job_name, status, locked_at, lock_owner
FROM printer_scheduler_jobs
WHERE locked_at IS NOT NULL
   OR (lock_owner IS NOT NULL AND lock_owner != '')
LIMIT 20;
```

```text
(empty) ROW_COUNT=0
```

### A.9 Discovery work states

```sql
SELECT work_state, COUNT(*) AS n
FROM printer_discovery_work
GROUP BY work_state
ORDER BY work_state;
```

```text
('FAILED', 2)
('SUCCEEDED', 62)
```

```sql
SELECT COUNT(*) AS n
FROM printer_discovery_work
WHERE work_state NOT IN ('SUCCEEDED','FAILED','CANCELLED');
```

```text
(0,)
```

### A.10 Factory-step states

```sql
SELECT step_status, COUNT(*) AS n
FROM printer_memory_factory_run_steps
GROUP BY step_status
ORDER BY step_status;
```

```text
('CANCELLED', 12)
('SUCCEEDED', 42)
```

```sql
SELECT COUNT(*) AS n
FROM printer_memory_factory_run_steps
WHERE step_status NOT IN ('SUCCEEDED','FAILED','CANCELLED');
```

```text
(0,)
```

### A.11 Proof-supervision rows

```sql
SELECT COUNT(*) AS n FROM printer_proof_run_supervision;
```

```text
(0,)
```

### A.12 Active candidate-acquisition lease count

```sql
SELECT lease_state, COUNT(*) AS n
FROM printer_candidate_acquisition_leases
GROUP BY lease_state
ORDER BY lease_state;
```

```text
('TERMINAL', 19)
```

```sql
SELECT COUNT(*) AS active_held
FROM printer_candidate_acquisition_leases
WHERE lease_state IN ('ACTIVE','STOPPING','HELD','RUNNING','ACQUIRED')
   OR (
        released_at IS NULL
        AND lease_state NOT LIKE 'TERMINAL%'
        AND lease_state NOT IN (
          'RELEASED','EXPIRED','FAILED','COMPLETED','CANCELLED','TERMINAL'
        )
      );
```

```text
(0,)
```

```sql
SELECT COUNT(*) AS n FROM printer_candidate_acquisition_leases;
```

```text
(19,)
```

### A.13 Exact July 31 campaign / run / cycle / supervision state

Identity under inspection:

```text
campaign_id:    20260731T002406Z-7612696c7295-campaign
run_id:         20260731T002406Z-7612696c7295-campaign-run
cycle_id:       20260731T002406Z-7612696c7295-cycle
supervision_id: 20260731T002406Z-7612696c7295-supervision
execution_id:   20260731T002406Z-7612696c7295
```

```sql
SELECT campaign_id, campaign_state, first_terminal_cause, terminal_at
FROM printer_memory_factory_campaigns
WHERE campaign_id = '20260731T002406Z-7612696c7295-campaign';
```

```text
('20260731T002406Z-7612696c7295-campaign',
 'TERMINAL_COMPLETED',
 'SOURCE_VISIBILITY_SHORTAGE',
 '2026-07-31T00:24:29.612374+00:00')
```

```sql
SELECT run_id, campaign_id, run_state, first_terminal_cause, terminal_at
FROM printer_memory_factory_campaign_runs
WHERE campaign_id = '20260731T002406Z-7612696c7295-campaign';
```

```text
('20260731T002406Z-7612696c7295-campaign-run',
 '20260731T002406Z-7612696c7295-campaign',
 'TERMINAL_COMPLETED',
 'SOURCE_VISIBILITY_SHORTAGE',
 '2026-07-31T00:24:29.612374+00:00')
```

```sql
SELECT cycle_id, campaign_id, run_id, cycle_state, first_terminal_cause, terminal_at
FROM printer_memory_factory_campaign_cycles
WHERE campaign_id = '20260731T002406Z-7612696c7295-campaign';
```

```text
('20260731T002406Z-7612696c7295-cycle',
 '20260731T002406Z-7612696c7295-campaign',
 '20260731T002406Z-7612696c7295-campaign-run',
 'TERMINAL_COMPLETED',
 'SOURCE_VISIBILITY_SHORTAGE',
 '2026-07-31T00:24:29.612374+00:00')
```

```sql
SELECT supervision_id, campaign_id, run_id, supervision_state, terminal_status,
       first_terminal_cause, cleanup_completed_at, lease_released_at
FROM printer_memory_factory_campaign_supervision
WHERE campaign_id = '20260731T002406Z-7612696c7295-campaign';
```

```text
('20260731T002406Z-7612696c7295-supervision',
 '20260731T002406Z-7612696c7295-campaign',
 '20260731T002406Z-7612696c7295-campaign-run',
 'TERMINAL',
 'COMPLETED',
 'SOURCE_VISIBILITY_SHORTAGE',
 '2026-07-31T00:24:29.612374+00:00',
 '2026-07-31T00:24:29.612374+00:00')
```

July 31 residual surface counts:

```sql
SELECT COUNT(*) AS n FROM printer_memory_factory_campaign_windows
WHERE campaign_id = '20260731T002406Z-7612696c7295-campaign';
-- (0,)

SELECT COUNT(*) AS n FROM printer_memory_factory_campaign_token_slots
WHERE campaign_id = '20260731T002406Z-7612696c7295-campaign';
-- (0,)

SELECT COUNT(*) AS n FROM printer_memory_factory_runs
WHERE run_id LIKE '%20260731T002406Z%'
   OR CAST(run_id AS TEXT) LIKE '%7612696c7295%';
-- (0,)

SELECT COUNT(*) AS n FROM printer_discovery_work
WHERE campaign_id = '20260731T002406Z-7612696c7295-campaign';
-- (0,)

SELECT COUNT(*) AS n FROM printer_scheduler_jobs
WHERE target_id LIKE '%20260731T002406Z-7612696c7295%'
   OR CAST(id AS TEXT) LIKE '%7612696c7295%';
-- (0,)
```

### A.14 July 31 report-row count

```sql
SELECT COUNT(*) AS n
FROM printer_memory_factory_campaign_reports
WHERE campaign_id = '20260731T002406Z-7612696c7295-campaign';
```

```text
(0,)
```

### A.15 July 31 exhaustion-certificate facts

```sql
SELECT certificate_id, campaign_id, execution_id, run_id, cycle_id,
       required_eligible_capacity, eligible_reserve_count, shortage_classification,
       certificate_version, created_at
FROM printer_discovery_exhaustion_certificates
WHERE campaign_id = '20260731T002406Z-7612696c7295-campaign';
```

```text
('exh-20260731T002406Z-7612696c7295',
 '20260731T002406Z-7612696c7295-campaign',
 '20260731T002406Z-7612696c7295',
 '20260731T002406Z-7612696c7295-campaign-run',
 '20260731T002406Z-7612696c7295-cycle',
 2,
 1,
 'SOURCE_VISIBILITY_SHORTAGE',
 'V2_9_8B_LIQUIDITY_EVIDENCE_EXHAUSTION_V2',
 '2026-07-31T00:24:06.404380+00:00')
```

Selected scalar fields from `certificate_json` (no secrets):

```text
shortage_classification: SOURCE_VISIBILITY_SHORTAGE
source_operations_used: 30
source_operations_remaining: 0
required_eligible_capacity: 2
eligible_reserve_count: 1
unique_tokens_observed: 30
rejected_count: 29
discovery_rounds: 5
provider_failures: 15
last_reason_discovery_could_not_continue: DISCOVERY_OPERATION_BUDGET_EXHAUSTED
unexplored_work_prevented_by_hard_ceiling: true
```

### A.16 Retrieval and paper / financial baseline counts

```sql
SELECT COUNT(*) AS n FROM printer_memory_retrieval_matches;  -- (0,)
SELECT COUNT(*) AS n FROM printer_memory_retrieval_queries;  -- (10,)
SELECT COUNT(*) AS n FROM printer_paper_decisions;           -- (2,)
SELECT COUNT(*) AS n FROM printer_paper_audit_reports;       -- (1,)
SELECT COUNT(*) AS n FROM printer_paper_positions;           -- (0,)
SELECT COUNT(*) AS n FROM printer_paper_trade_events;        -- (0,)
SELECT COUNT(*) AS n FROM printer_paper_trade_audits;        -- (0,)
```

### A.17 External permanent no-rerun marker

```text
documented path: $HOME/PrinterOperations/v2-9-8/first-authoritative-window-15m-attempt.json
resolved path:   $HOME/PrinterOperations/v2-9-8/first-authoritative-window-15m-attempt.json
exists: true
size: 427
SHA-256: dd079f82a361aa2364b4142384a0b472698759a861a507539939aab839011564
file modified by this audit: false
```

Selected non-secret fields:

```text
attempt_number: 1
attempt_scope: FIRST_AUTHORITATIVE_WINDOW_15M_CAMPAIGN
authorized_git_commit: b5761b6501ad757eecdfc8cfabce6828d5a899bd
authorization_verdict: V2_9_8B_FIRST_AUTHORITATIVE_15M_CAMPAIGN_FINAL_AUTHORIZATION_PASS
authoritative_database_sha256: e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6
created_at_utc: 20260731T002405Z
rerun_authorized: false
```

### A.18 External July 31 terminal-summary artifact

```text
documented path: $HOME/PrinterOperations/v2-9-8/20260731T002406Z-7612696c7295/terminal-summary.json
resolved path:   $HOME/PrinterOperations/v2-9-8/20260731T002406Z-7612696c7295/terminal-summary.json
exists: true
size: 6234
SHA-256: 183d438d5110c448da6fc134079aedb3bf20c7cbb6ce32f1fa0846073162a0ad
file modified by this audit: false
```

Top-level keys present:

```text
accounting_status, campaign_id, campaign_scheduler_calls, campaign_source_calls,
cleanup, closure_errors, execution_id, first_terminal_cause,
original_exception_type, partial_six_unit_evidence, reconciliation,
report_block_reason, report_written, restart_created, status, successor_created
```

Selected non-secret top-level fields used by the verdict:

```text
execution_id: 20260731T002406Z-7612696c7295
campaign_id: 20260731T002406Z-7612696c7295-campaign
report_written: false
report_block_reason: SIX_UNIT_EVIDENCE_MISSING
accounting_status: SIX_UNIT_ACCOUNTING_BLOCKED
first_terminal_cause: SOURCE_VISIBILITY_SHORTAGE
campaign_source_calls: 30
restart_created: false
successor_created: false
status: OPERATIONAL_CAMPAIGN_TERMINAL_FAILURE
top-level run_id present: false
top-level configuration_id present: false
```

Selected nested cleanup fields:

```text
cleanup.cleanup_completed: true
cleanup.lease_released: true
cleanup.automatic_retries: 0
cleanup.restart_created: false
cleanup.resume_created: false
cleanup.successor_created: false
cleanup.terminal_status: COMPLETED
cleanup.active_owned_work_after: 0
```

Selected nested partial six-unit fields:

```text
partial_six_unit_evidence.stage_evidence_count: 1
partial_six_unit_evidence.accounting evidence remains incomplete for report write
```

### A.19 Transcript claim map

| Audit residual claim | Transcript result |
| --- | --- |
| 49 migrations; head `049_candidate_acquisition_integration.sql` | reproduced |
| `integrity_check = ok`; FK violations `0` | reproduced |
| DB SHA-256 unchanged | reproduced equal before/after |
| no WAL/SHM/journal sidecars | reproduced |
| campaigns/runs 18 terminal (11 completed / 7 failed) | reproduced |
| supervision all `TERMINAL`; zero non-terminal | reproduced |
| Scheduler only SUCCEEDED/FAILED/CANCELLED; zero locks | reproduced |
| discovery only SUCCEEDED/FAILED | reproduced |
| factory steps only SUCCEEDED/CANCELLED | reproduced |
| proof supervision `0` | reproduced |
| active CA leases `0`; historical terminal leases `19` | reproduced |
| July 31 campaign/run/cycle terminal `SOURCE_VISIBILITY_SHORTAGE` | reproduced |
| July 31 supervision TERMINAL/COMPLETED; lease released; cleanup done | reproduced |
| July 31 report rows `0` | reproduced |
| July 31 exhaustion `SOURCE_VISIBILITY_SHORTAGE`; 30 source ops | reproduced |
| permanent marker attempt 1 / `rerun_authorized=false` / launch commit pin | reproduced |
| terminal summary `report_written=false` / accounting blocked / no restart/successor | reproduced |
| retrieval/paper/financial baseline counts | reproduced |
| discrepancy requiring verdict change | none |

### A.20 Boundary confirmation for this transcript

Commands/classes of work not run:

- preflight-only;
- tests;
- campaign or report-only command;
- providers, RPC, WebSockets, or sources;
- writable SQLite open;
- authoritative DB mutation or copy;
- July 31 repair/reclassification;
- runtime code, tests, migrations, anchors, policy, verdict, or next-lane wording changes.
