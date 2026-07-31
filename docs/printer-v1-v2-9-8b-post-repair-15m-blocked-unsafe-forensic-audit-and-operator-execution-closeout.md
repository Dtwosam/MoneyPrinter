# Printer V1 V2-9.8B Post-Repair WINDOW_15M BLOCKED_UNSAFE Forensic Audit and Operator Execution Closeout

Date: 2026-07-31

Lane:
`V2-9.8B Post-Repair WINDOW_15M BLOCKED_UNSAFE Forensic Audit and Operator Execution Closeout`

Branch:
`codex/v2-9-8b-post-repair-15m-forensic-closeout`

Type: read-only forensic audit plus documentation closeout only. This lane ran
**no** operational command, campaign, preflight, report, status, recovery, stop,
discovery, N2/N7, cursor, source/provider/RPC/WebSocket call, repair, test, or
rerun. It made no database mutation. Its only mutation anywhere is this closeout
document and its commit.

Verdict:

`V2_9_8B_POST_REPAIR_15M_BLOCKED_UNSAFE_FORENSIC_AUDIT_CONFIRMED`

A confirmed audit does **not** mean the campaign passed. It confirms that the
`20260731T145230Z-2f345456ea78` attempt is `BLOCKED_UNSAFE`: two real
`WINDOW_15M` lifecycles occurred, but the campaign's terminal accounting and
reporting omit the full-run per-token/window terminal evidence and rest on a
vacuous owner/action-local reconciliation, so the `COMPLETED` / `reconciled` /
`clean_terminal` terminal cannot be trusted as a Campaign PASS.

---

## 0. Baseline and Exact Identities

| Item | Value |
| --- | --- |
| Start point | clean `master` |
| Exact launch/audit-base commit | `444ed0191db2d9c50ad097e3f78607f423ef3e68` |
| Launch commit subject | `Repair post-repair 15m campaign design boundaries` |
| Audit branch | `codex/v2-9-8b-post-repair-15m-forensic-closeout` |
| Final-authorization branch (unmerged) | `codex/v2-9-8b-post-repair-15m-final-authorization` |
| Final-authorization commit (unmerged) | `6ca642ca84c238a4d90892cd8f4b44f9f96abf35` |
| HEAD at audit start | `444ed0191db2d9c50ad097e3f78607f423ef3e68` (clean) |

### 0.1 Exact execution identities (as authorized)

| Identity | Value |
| --- | --- |
| execution | `20260731T145230Z-2f345456ea78` |
| campaign | `20260731T145230Z-2f345456ea78-campaign` |
| campaign run | `20260731T145230Z-2f345456ea78-campaign-run` |
| cycle | `20260731T145230Z-2f345456ea78-cycle` |
| configuration | `20260731T145230Z-2f345456ea78-configuration` |
| supervision | `20260731T145230Z-2f345456ea78-supervision` |
| owner | `20260731T145230Z-2f345456ea78-owner` |
| report | `20260731T145230Z-2f345456ea78-report` |
| factory run | `206d2ae9-3de5-4241-89d7-08dd6ef87a43` |
| artifact root | `$HOME/PrinterOperations/v2-9-8/20260731T145230Z-2f345456ea78` |

All persisted rows carry exactly these identities; no second execution, campaign,
run, cycle, supervision, report, or factory run exists for this attempt.

---

## 1. One-Invocation / No-Rerun Evidence

- Exactly one campaign row (`printer_memory_factory_campaigns.id=19`), one run,
  one cycle, one supervision row (`id=19`), one report row, and one factory run
  row (`printer_memory_factory_runs.id=7`, `run_id=206d2ae9-…`) exist for this
  execution identity.
- The factory run is `run_status=COMPLETED`, single `started_at`
  `2026-07-31T14:52:48.376170+00:00`, single `finished_at`
  `2026-07-31T15:07:59.918987+00:00`.
- Campaign supervision is `supervision_state=TERMINAL`,
  `terminal_status=COMPLETED`, `lease_released_at` set, single owner.
- The post-repair authorization marker records `rerun_authorized=false`,
  `attempt_number=1`; the first-authoritative marker records
  `rerun_authorized=false`, `attempt_number=1`.
- No restart, successor, or resume row exists (`restart_created=false`,
  `successor_created=false` in report and terminal summary).

This lane performed no invocation of any operational mode. Its read-only proof is
Section 3.1 (DB SHA-256 before == after).

---

## 2. Artifact Inventory and Hashes

Artifact root: `$HOME/PrinterOperations/v2-9-8/20260731T145230Z-2f345456ea78`.
Every file under the root was hashed:

| File | Size (bytes) | SHA-256 |
| --- | --- | --- |
| `reports/20260731T145230Z-2f345456ea78-report.campaign-report.json` | 31961 | `592da4d41dbfea1aa5557af75b031812899e97522fbec224155352958a42a116` |
| `terminal-summary.json` | 2084 | `2e1ccc4eed45d5594fe1f04f529f5480762cfe7ec241071164796137ed061dd0` |
| `printer_v1.pre-campaign.backup.sqlite3` | 64901120 | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` |
| `printer_v1.restore-rehearsal.sqlite3` | 64901120 | `f36f3b3fd7c389018323c219b3ce9421e2006769de3db860593ce4b31415a511` |

- Canonical report SHA-256 equals the expected value
  `592da4d4…a42a116` **and** equals the persisted `report_hash` in
  `printer_memory_factory_campaign_reports` (report_id `…-report`). Match.
- The pre-campaign backup and the restore-rehearsal DB copies both hash to
  `f36f3b3f…415a511`, exactly the pre-launch authorized DB hash. This proves the
  internal backup/restore gate captured, and rehearsed a restore of, the exact
  pre-launch authoritative state before any campaign/source work.

### 2.1 Marker verification (both unchanged)

| Marker | Path | Expected SHA-256 | Observed | Result |
| --- | --- | --- | --- | --- |
| July 31 first-authoritative | `…/first-authoritative-window-15m-attempt.json` | `dd079f82a361aa2364b4142384a0b472698759a861a507539939aab839011564` | identical | unchanged |
| Post-repair authorization | `…/post-accounting-repair-authoritative-window-15m-attempt.json` | `6bb58474511527a7e2076a9e7b8096208b7018f4e4eb66dd219a26ba5cd2677b` | identical | unchanged |

Neither marker was edited, moved, recreated, or reused by this audit.

---

## 3. Exact DB Evidence and SQL

Authoritative DB: `data/printer_v1.sqlite3`. All queries used the read-only URI
`file:…/data/printer_v1.sqlite3?mode=ro` with `PRAGMA query_only=ON`.

### 3.1 Read-only proof (DB SHA-256 before / after this audit)

```text
DB SHA-256 before audit: e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2
DB SHA-256 after  audit: e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2
equality: true  (audit is read-only)
```

As designed, the post-run DB hash `e13c4089…` differs from the pre-launch
authorized hash `f36f3b3f…` — the campaign legitimately mutated the authoritative
DB. The audit proves *itself* read-only by before==after equality, not by
matching the pre-launch hash.

### 3.2 Integrity, migration, FK, sidecar state

```sql
PRAGMA integrity_check;      -- ok
PRAGMA foreign_key_check;    -- (no rows)
SELECT COUNT(*) FROM printer_schema_migrations;                 -- 49
SELECT version FROM printer_schema_migrations ORDER BY 1 DESC LIMIT 1;
                             -- 049_candidate_acquisition_integration.sql
```

- integrity_check: `ok`
- foreign_key_check: zero violations
- migration count/head: 49 / `049_candidate_acquisition_integration.sql`
- sidecars: no `-wal`, `-shm`, or `-journal` under `data/` before or after audit.

### 3.3 Campaign / run / cycle / supervision / report / configuration

```sql
SELECT campaign_state, first_terminal_cause, db_target_identity, policy_version
FROM printer_memory_factory_campaigns
WHERE campaign_id='20260731T145230Z-2f345456ea78-campaign';
```

| Record | Key facts |
| --- | --- |
| campaign (id 19) | `TERMINAL_COMPLETED`; cause `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`; `db_target_identity=sha256:f36f3b3f…415a511`; policy `V2-9.8-15M-OPERATIONAL-V1` |
| run | `TERMINAL_COMPLETED` |
| cycle | `TERMINAL_COMPLETED` |
| supervision (id 19) | `TERMINAL` / `COMPLETED`; lease released `2026-07-31T15:07:59.921888+00:00`; no cancellation |
| report | `report_kind=TERMINAL`; `report_hash=592da4d4…a42a116` (matches artifact) |
| configuration | `…-configuration`, bound to campaign |

### 3.4 Factory run row and steps

```sql
SELECT run_status, stop_reason, window_kind, db_mode, selection_batch_id,
       eligible_pool_size, selected_token_count, started_at, finished_at
FROM printer_memory_factory_runs WHERE run_id='206d2ae9-3de5-4241-89d7-08dd6ef87a43';
SELECT step_kind, step_status, COUNT(*) FROM printer_memory_factory_run_steps
WHERE run_id='206d2ae9-…' GROUP BY step_kind, step_status;
```

- factory run: `COMPLETED`, `stop_reason=COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`,
  `window_kind=WINDOW_15M`, `db_mode=OPERATIONAL_PERSISTENT`,
  `selection_batch_id=origin-activated:20260731T145230Z-2f345456ea78-cycle`,
  `eligible_pool_size=2`, `selected_token_count=2`.
- steps: **18 SUCCEEDED** — `SNAPSHOT` × 16 and `WINDOW_CLOSE` × 2. No PENDING /
  RUNNING / FAILED / CANCELLED steps.
- of the 18 steps: `scheduler_job_id` set on **18**, `snapshot_id` set on **18**,
  `memory_window_id` set on **2** (the two WINDOW_CLOSE steps → windows 161, 162).
- distinct step tokens: `2C3CURT…pump` (token_id 28, pair_id 32) and
  `Av2cD8GQ…dt2` (token_id 27, pair_id 31).

### 3.5 The two `printer_memory_windows` attributable to the factory run

```sql
SELECT id, token_id, pair_id, window_kind, opened_at, closed_at,
       expected_snapshot_count, actual_snapshot_count, missing_snapshot_count,
       coverage_state, memory_status, data_quality_label, do_not_train,
       window_status, outcome_label, memory_quality_label, created_by_phase
FROM printer_memory_windows WHERE id IN (161,162);
```

| window | token/pair | opened → closed | snapshots (exp/act/miss) | coverage | memory_status | data_quality | do_not_train | window_status | outcome |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 161 | 28 / 32 (`2C3CURT…pump`) | 14:52:49 → 15:07:55 | 9 / 9 / 0 | `COVERAGE_PASS` | `PARTIAL_MEMORY` | `CLEAN_DATA` | 0 | `WINDOW_CLOSED` | `CONSOLIDATION` |
| 162 | 27 / 31 (`Av2cD8GQ…dt2`) | 14:52:49 → 15:07:59 | 9 / 9 / 0 | `COVERAGE_PASS` | `PARTIAL_MEMORY` | `CLEAN_DATA` | 0 | `WINDOW_CLOSED` | `CONSOLIDATION` |

Both windows were created by phase `lane_e2o`. Both carry an **empty `cycle_id`** —
they are not linked to the campaign cycle identity (root evidence for the
ownership disconnect in Section 8).

### 3.6 Snapshots, episodes, fingerprints, audits, micro-events

```sql
SELECT token_id, COUNT(*) FROM printer_token_snapshots
WHERE token_id IN (27,28) AND created_at>='2026-07-31T14:52' GROUP BY token_id;   -- 27→9, 28→9
SELECT id, memory_window_id, token_id, episode_kind, memory_status, do_not_train
FROM printer_episodes WHERE memory_window_id IN (161,162);
SELECT COUNT(*) FROM printer_episode_outcomes WHERE episode_id IN (58,59);        -- 0
SELECT COUNT(*) FROM printer_memory_fingerprints WHERE episode_id IN (58,59);     -- 0
SELECT COUNT(*) FROM printer_memory_audit_reports
WHERE memory_window_id IN (161,162) OR episode_id IN (58,59);                     -- 0
SELECT COUNT(*) FROM printer_micro_events
WHERE token_id IN (27,28) AND created_at>='2026-07-31T14:52';                     -- 0
```

- token_snapshots: 9 per token (18 total), matching each window's
  `expected==actual==9`, `missing=0`.
- episodes: two — id 58 (window 161, token 28) and id 59 (window 162, token 27),
  `episode_kind=WINDOW_15M_CLEAN_MEMORY`, `do_not_train=0`.
- episode_outcomes: **0**; memory_fingerprints: **0**; memory_audit_reports:
  **0**; micro_events (5m support): **0**.
- Note an internal quality inconsistency: the two windows are `PARTIAL_MEMORY`
  while their episodes are `episode_kind=WINDOW_15M_CLEAN_MEMORY` /
  `memory_status=CLEAN_MEMORY`. Neither produced a fingerprint or audit report,
  so nothing promoted to clean-memory retrieval.

### 3.7 Token slots, tracking queues, lifecycle events

```sql
SELECT token_slot_id, slot_ordinal, token_row_id, tracking_queue_id, token_state,
       first_terminal_cause FROM printer_memory_factory_campaign_token_slots
WHERE cycle_id='20260731T145230Z-2f345456ea78-cycle';
SELECT id, token_id, queue_status, tracking_action, priority_reason,
       data_quality_label, next_check_at FROM printer_tracking_queue WHERE id IN (30,31);
```

| slot | token_row | tracking_queue_id | token_state |
| --- | --- | --- | --- |
| slot-…-cycle-1 | 27 (`Av2cD8GQ…`) | 30 | `MANUAL_REVIEW` |
| slot-…-cycle-2 | 28 (`2C3CURT…`) | 31 | `MANUAL_REVIEW` |

| tracking queue | token | queue_status | tracking_action | priority_reason | data_quality |
| --- | --- | --- | --- | --- | --- |
| 30 | 27 | `COOLDOWN` | `ENTER_COOLDOWN` | `factory_terminal:COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED:CLEAN` | `CLEAN_DATA` |
| 31 | 28 | `COOLDOWN` | `ENTER_COOLDOWN` | `factory_terminal:COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED:CLEAN` | `CLEAN_DATA` |

- `printer_token_lifecycle_events`: exactly one `ENTER_COOLDOWN` event for token
  27 and one for token 28 on 2026-07-31.
- Both queues have `next_check_at` 30 minutes after their `last_checked_at`
  (`15:07 → 15:37`), the standard `TRACKING_COOLDOWN_SECONDS` re-track delay.

### 3.8 Scheduler jobs and campaign-scoped work

```sql
SELECT status, COUNT(*) FROM printer_scheduler_jobs
WHERE id IN (SELECT scheduler_job_id FROM printer_memory_factory_run_steps
             WHERE run_id='206d2ae9-…') GROUP BY status;                          -- SUCCEEDED 18
SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
WHERE campaign_id='20260731T145230Z-2f345456ea78-campaign';                      -- 0
SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
WHERE campaign_id='…-campaign' AND run_id='…-campaign-run';                       -- 0
SELECT COUNT(*) FROM printer_external_source_operations
WHERE run_id IN ('206d2ae9-…','…-campaign-run');                                 -- 0
```

- The 18 factory-step scheduler jobs are all `SUCCEEDED`.
- Reconciliation attributed job counts: `discovery_jobs=8`,
  `factory_run_step_jobs=18`, `campaign_scheduler_work_jobs=0`; `jobs_by_status:
  {SUCCEEDED: 26}`.
- **`printer_memory_factory_campaign_scheduler_work` = 0 rows.**
- **`printer_memory_factory_campaign_windows` = 0 rows** (the campaign-window
  ownership map is empty).
- **`printer_external_source_operations` = 0 rows** for both run identities;
  durable source rows for the attempt live in `printer_source_requests`
  (ids 1706–1718 present) and `printer_source_responses` (ids 1574–1579 present),
  referenced directly by the report's admission candidates.

### 3.9 Selection batch and selected items

```sql
SELECT batch_status, window_kind, candidate_pool_total, selected_count, rejected_count
FROM printer_selection_batches WHERE batch_id='origin-activated:…-cycle';
SELECT COUNT(*) FROM printer_selection_batch_items WHERE batch_id='origin-activated:…-cycle';
```

- selection batch: `ASSEMBLED`, `WINDOW_15M`, pool total 2, selected 2, rejected 0.
- selection_batch_items: 2.
- one discovery batch was created in the campaign window.

### 3.10 Locked-capability / forbidden-delta counts (current)

```sql
SELECT COUNT(*) FROM printer_memory_retrieval_matches;   -- 0
SELECT COUNT(*) FROM printer_memory_retrieval_queries;   -- 10
SELECT COUNT(*) FROM printer_paper_decisions;            -- 2
SELECT COUNT(*) FROM printer_paper_positions;            -- 0
SELECT COUNT(*) FROM printer_paper_trade_events;         -- 0
SELECT COUNT(*) FROM printer_paper_trade_audits;         -- 0
SELECT COUNT(*) FROM printer_paper_audit_reports;        -- 1
```

Every count equals the pre-launch authorized baseline recorded in the final
authorization (matches 0, queries 10, decisions 2, positions 0, trade_events 0,
trade_audits 0, audit reports 1). The report's `forbidden_deltas` are all 0 and
`downstream_unlocks` are all `false`. No retrieval or financial capability was
created or incremented.

---

## 4. Two-Token Transition Timeline

| Time (UTC) | Event |
| --- | --- |
| 14:52:29.965 | launch git provenance captured; HEAD `444ed01…`, clean tree |
| 14:52:30.412 | campaign / cycle / supervision created; six-unit owner start |
| 14:52:48.376 | factory run `206d2ae9-…` started; tracking queues 30, 31 created |
| 14:52:49.188 | window 161 opened (token 28 / pair 32) |
| 14:52:49.813 | window 162 opened (token 27 / pair 31) |
| 14:52:49 → 15:07 | 9 governed snapshots per token; 16 SNAPSHOT steps SUCCEEDED |
| 15:07:55.167 | window 161 closed — `COVERAGE_PASS`, 9/9, `PARTIAL_MEMORY`/`CLEAN_DATA` |
| 15:07:59.789 | window 162 closed — `COVERAGE_PASS`, 9/9, `PARTIAL_MEMORY`/`CLEAN_DATA` |
| 15:07:59.916 | tracking queues 30, 31 → `ENTER_COOLDOWN` / `COOLDOWN` (clean) |
| 15:07:59.921 | campaign / run / cycle / supervision terminalized; lease released |
| 15:07:59.927 | token slots → `MANUAL_REVIEW` |
| 15:07:59.932 | six-unit evidence sealed (`ended_at`); elapsed 929.519 s |

---

## 5. Exact Lifecycle / Window Outcomes

- **Two real terminal `WINDOW_15M` lifecycles occurred** (windows 161 and 162),
  each `WINDOW_CLOSED` with `COVERAGE_PASS`, `expected==actual==9`,
  `missing_snapshot_count=0`, `do_not_train=0`, outcome `CONSOLIDATION`.
- Window/token/pair/quality identities:

  | window | token_id | mint | pair_id | pool | memory_status | data_quality | episode |
  | --- | --- | --- | --- | --- | --- | --- | --- |
  | 161 | 28 | `2C3CURT1uZUdqxoxFcMGwbVevom1ETu6FNDcaaByDR7A` | 32 | `AR4eDzUGi3wfPJGwXSJMAXLN3Y49oBAD2srexBCorV59` | `PARTIAL_MEMORY` | `CLEAN_DATA` | 58 |
  | 162 | 27 | `Av2cD8GQT5dnCiC2cav2X37hs9z2mbBSxAMGkRbwkdt2` | 31 | `REUdyzJNhNYJbgxAWfjiicvcTsfSJhyd61oN1JhhJXo` | `PARTIAL_MEMORY` | `CLEAN_DATA` | 59 |

- The 18 SUCCEEDED factory steps (16 SNAPSHOT + 2 WINDOW_CLOSE) are the complete
  two-token main-window cadence: 9 persisted snapshots per token and one clean
  window close per token, full coverage, no gaps.
- Neither window produced a fingerprint, episode outcome, or audit report; neither
  promoted to clean-memory retrieval. Both remain `PARTIAL_MEMORY` and are not
  retrieval-eligible.

---

## 6. Six-Unit Accounting Coverage Matrix

Report `six_unit_totals` (top level, equal to the sealed evidence reconstruction):

| Unit | Reported | Source of the count | Full-run truth in DB |
| --- | --- | --- | --- |
| `SOURCE_TRANSPORT_OPERATION` | 10 | 10 sealed discovery/nomination/liquidity transports | discovery/selection only |
| `SOURCE_RESPONSE_BYTES` | 70375 | sum of the 10 transports | discovery/selection only |
| `NORMALIZED_SOURCE_ROWS` | 47 | sum of the 10 transports | discovery/selection only |
| `LOCAL_VALIDATION_STEP` | 0 | owner counter (never fed) | window-close validations occurred |
| `SCHEDULER_WORK_ITEM` | 0 | owner counter (never fed) | **18 factory scheduler jobs SUCCEEDED** |
| `LIFECYCLE_RESERVED_TRANSPORT_OPERATION` | 0 | owner counter (never fed) | 2 lifecycles / 18 snapshot ops ran |

The five sealed stages ingested by `CampaignSixUnitOwner` are:
`LOCATOR|1`, `DIRECT_MIGRATION|1`, `EXACT_LIQUIDITY|1`, `EXACT_LIQUIDITY|2`,
`EXACT_LIQUIDITY|3` — all **pre-lifecycle** discovery / nomination / liquidity
stages. No `SNAPSHOT`, `WINDOW_CLOSE`, holder, or Scheduler stage from the factory
run was ingested. `six_unit_evidence.scheduler_work_items`,
`lifecycle_reservations`, and `local_validations` are literal `0` because the
owner was only ever handed the pre-lifecycle discovery/selection evidence.

**Coverage gap (Q7, Q8):** the operations absent from six-unit evidence are exactly
the factory run's lifecycle operations — the 18 governed snapshot/window-close
Scheduler jobs, the per-window lifecycle reservations, and the window-close local
validations. They are zero in the six-unit block not because they did not happen
(they did — Sections 3.4–3.8) but because the campaign six-unit accounting scope
ends at pre-lifecycle selection and never seals full-run lifecycle stages.

---

## 7. Owner / Action-Local Reconciliation Findings

- `reconcile_owner_to_action_local` (in
  `src/printer_v1/sources/campaign_six_unit_accounting.py`) proves owner-vs-
  action-local *transport identity* equality **only** when action-local evidence
  is supplied. When both `action_local_source_operations` and
  `action_local_transport_identities` are `None`, no branch fires and the function
  returns `equal=True` with `mismatch_reason=None` — a **vacuous pass** (Q10).
- For this attempt the campaign built the owner from the five pre-lifecycle stages
  but supplied **no action-local lifecycle evidence** for the lifecycle-started
  run. There is therefore **no independent proof** that the factory run's
  operations equal any owner ledger (Q9): the "equality" that underwrites the
  clean terminal is either the vacuous default above or the self-consistent
  discovery-stage comparison in `compare_report_totals_to_evidence` (which rebuilds
  totals *from the same evidence* and compares them to themselves).
- Consequently `six_unit_evidence_match=true` in the report attests only that the
  10 discovery transports are internally consistent. It does **not** attest that
  the two `WINDOW_15M` lifecycles, their 18 Scheduler jobs, or their window closes
  were measured, reconciled, or accounted.

---

## 8. Reporting Omissions and the `windows={}` Question

- `reconciliation.windows={}` is built (in
  `src/printer_v1/operator_cli/unified_terminal_closure.py`, step 3) by selecting
  from `printer_memory_factory_campaign_windows` — the **campaign-window ownership
  map**, which has **0 rows** for this campaign/run. It is therefore an empty
  ownership result, **not** a statement that no `printer_memory_windows` exist.
  The real `printer_memory_windows` 161 and 162 do exist and closed cleanly (Q6).
- The same closure path emits `pre_lifecycle_dispositions` (step 4a) for the token
  slots. Its own comment states it handles "a terminal reached **before any
  main-window lifecycle step**." Because the campaign-window ownership map is empty
  and the slots were still `SELECTED`, the closure routes both slots to
  `MANUAL_REVIEW` as a *pre-lifecycle* disposition (Q5) — even though two full
  main-window lifecycles actually completed. The paired `COOLDOWN` queue
  disposition it reports is the pre-existing clean-terminal cooldown set earlier by
  `tracking_lifecycle_reconciliation` (the slot-close `UPDATE … WHERE
  queue_status='QUEUED'` did not match a `COOLDOWN` row, so it reported the current
  `COOLDOWN` status).
- **Net reporting omission (Q11):** the canonical report omits the factory
  per-token/window terminal evidence required for Campaign PASS — no campaign-owned
  window rows, no full-run six-unit stages, no owner/action-local reconciliation of
  the lifecycle. What it *does* surface (`windows={}`, slot `MANUAL_REVIEW`,
  `scheduler_work_items=0`) actively misrepresents a completed two-lifecycle run as
  a pre-lifecycle-style terminal.

### 8.1 COOLDOWN and MANUAL_REVIEW semantics (confirmed, not assumed)

- **COOLDOWN is not a failure (Q4).** The post-cycle reconciler
  (`tracking_lifecycle_reconciliation.reconcile`) sets `ENTER_COOLDOWN` /
  `queue_status=COOLDOWN` on the `main_terminal` branch — i.e. when a token reached
  a real terminal main window. The persisted per-token outcome confirms this:
  `tracking_action=ENTER_COOLDOWN`, `data_quality_label=CLEAN_DATA`,
  `priority_reason=factory_terminal:COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED:CLEAN`,
  and a 30-minute re-track delay. Both tokens ended COOLDOWN because both 15m
  lifecycles closed clean.
- **MANUAL_REVIEW (Q5)** is the campaign-slot disposition applied by
  `terminally_reconcile_campaign` to `SELECTED` slots at closure. It is a
  pre-lifecycle-ownership closure path, which fired here only because the factory
  windows were never registered as campaign windows.

---

## 9. Confirmed Root Cause

**Smallest root-cause set (Q12):** a single ownership/accounting disconnect between
the factory run and the campaign layer.

1. The factory run's `WINDOW_15M` lifecycle produced real evidence
   (`printer_memory_windows` 161/162, 18 `printer_memory_factory_run_steps`, 18
   `printer_scheduler_jobs`, 2 episodes, 18 snapshots) but **never registered any
   `printer_memory_factory_campaign_windows` rows** and left the windows'
   `cycle_id` empty. The campaign-window ownership graph is empty.
2. The campaign six-unit accounting scope **ends at pre-lifecycle selection**: only
   discovery/nomination/liquidity stages are sealed into `CampaignSixUnitOwner`;
   the full-run lifecycle stages (Scheduler jobs, lifecycle reservations,
   window-close validations) are never sealed, so their unit counts are `0`.
3. No action-local lifecycle evidence is fed to
   `reconcile_owner_to_action_local`, so the owner/action-local equality that
   underwrites the clean terminal is **vacuous** and `six_unit_evidence_match=true`
   is a discovery-only self-comparison.

Because of (1)–(3), the campaign terminalized as `COMPLETED` /
`reconciled=true` / `clean_terminal=true` / `lifecycle_started=true` while its
terminal accounting and canonical report **omit the full-run per-token/window
terminal evidence and rest on unproven reconciliation**. Per the design runbook
§9.3, an attempt whose terminal accounting/reporting is incomplete or cannot be
trusted is **`BLOCKED_UNSAFE`** — never a Campaign PASS (§9.1 requires "complete
six-unit accounting with exact owner/action-local reconciliation"). The design
runbook itself anticipated exactly this as the "Post-lifecycle identity gate
residual… holder/scheduler stages after lifecycle start are outside the
pre-lifecycle action-local identity gate" (Section 14 of that runbook).

**`BLOCKED_UNSAFE` is confirmed.**

### 9.1 Answers to the twelve questions

1. **Two real terminal `WINDOW_15M` lifecycles?** Yes — windows 161 and 162, both
   `WINDOW_CLOSED`, `COVERAGE_PASS`, 9/9, `do_not_train=0`.
2. **Exact identities?** See Section 5 table (tokens 28/`2C3CURT…`, 27/`Av2cD8GQ…`;
   pairs 32/`AR4eD…`, 31/`REUdy…`; windows 161/162; episodes 58/59; both
   `PARTIAL_MEMORY` / `CLEAN_DATA`).
3. **Do the 18 succeeded steps represent the complete two-token cadence?** Yes —
   16 SNAPSHOT + 2 WINDOW_CLOSE = 9 snapshots and one clean close per token,
   full coverage, zero gaps.
4. **Why both tracking queues COOLDOWN?** Clean `main_terminal` → `ENTER_COOLDOWN`;
   persisted reason `factory_terminal:…:CLEAN`, `CLEAN_DATA`, 30-min re-track. Not
   a failure.
5. **Why campaign slots later MANUAL_REVIEW?** `terminally_reconcile_campaign`
   routes `SELECTED` slots to `MANUAL_REVIEW` on the pre-lifecycle-ownership
   closure path, which fired because campaign-window ownership was empty.
6. **Does `windows={}` mean campaign-window ownership, not real windows?** Yes — it
   is the empty `printer_memory_factory_campaign_windows` result; real windows 161,
   162 exist.
7. **Which lifecycle/Scheduler ops are absent from six-unit evidence?** The factory
   run's 18 governed snapshot/window-close Scheduler jobs, per-window lifecycle
   reservations, and window-close local validations.
8. **Why are Scheduler work items / lifecycle reservations / local validations all
   zero?** The six-unit owner is only fed pre-lifecycle discovery/selection stages;
   the full-run lifecycle stages are never sealed, so the counters stay `0`.
9. **Was owner/action-local equality independently proven for the lifecycle-started
   run?** No — no action-local lifecycle evidence was supplied.
10. **Does missing action-local evidence incorrectly return reconciliation
    equality?** Yes — `reconcile_owner_to_action_local` returns `equal=True`
    vacuously when no action-local surface is provided.
11. **Does the canonical report omit factory per-token/window evidence required for
    Campaign PASS?** Yes — no campaign-owned windows, no full-run six-unit stages,
    no lifecycle owner/action-local reconciliation.
12. **Is `BLOCKED_UNSAFE` confirmed, and the smallest root-cause set?** Confirmed;
    the single factory↔campaign ownership/accounting disconnect described above.

---

## 10. Safety and Residual-State Findings

- **Read-only proof:** DB SHA-256 before == after (`e13c4089…`); no sidecars
  created; integrity `ok`; FK clean; migrations 49/`049`.
- **No unauthorized mutation:** no DB row was created, repaired, backfilled, or
  reclassified by this audit; no marker was edited; no synthetic evidence created.
- **Residual state is clean for this campaign:** 0 locked Scheduler jobs
  (`locked_at`/`lock_owner` null across the table); 0 active Scheduler jobs
  (`PENDING`/`RUNNING`/`COOLDOWN` status is empty); supervision `TERMINAL` with
  lease released; factory run `COMPLETED`. The campaign's tokens 30/31 sit in
  tracking `COOLDOWN`, a valid post-clean-terminal 30-minute re-track state, not
  active owned residue.
- **No risky unlock:** `forbidden_deltas` all 0; `downstream_unlocks` all false;
  retrieval and all financial table counts equal the pre-launch baseline.

---

## 11. Money-Usefulness Contribution

This audit is defensive money-usefulness. It prevents a false Campaign PASS from
being accepted: the attempt *looks* successful (COMPLETED, two closed windows,
clean data) but its accounting cannot substantiate that the two lifecycles were
measured and reconciled. Accepting it would let Printer grow "memory" and a
"passing" operational record on unverifiable terminal evidence — the July 31
failure mode in a subtler form. By confirming `BLOCKED_UNSAFE` read-only, the audit
keeps the authoritative corpus honest, keeps the two `PARTIAL_MEMORY` windows out
of any promoted/retrieval path, and routes the program to a design lane that will
make full-run terminal evidence provable before any future attempt is trusted. It
makes no profit claim and creates no financial capability.

---

## 12. What This Audit Improves

- Establishes, with exact SQL and hashes, that the `20260731T145230Z-2f345456ea78`
  attempt is `BLOCKED_UNSAFE`, distinguishing it from both PASS and
  `HONEST_BLOCKED`.
- Pins the precise defect to code: the campaign six-unit owner is fed only
  pre-lifecycle stages, and `reconcile_owner_to_action_local` passes vacuously
  without an action-local lifecycle surface.
- Separates real lifecycle truth (windows 161/162, 18 steps) from campaign-ownership
  artifacts (`windows={}`, slot `MANUAL_REVIEW`) so the next lane repairs the right
  layer.
- Confirms COOLDOWN and MANUAL_REVIEW semantics from the reconciler and persisted
  outcomes, removing the temptation to read either as a failure or a rerun trigger.

---

## 13. What Remains Locked

Unchanged and locked: clean-memory promotion/retrieval activation, retrieval
matches, paper decisions, BUY/SELL/HOLD, paper positions, trade events, paper
trade audits, PnL, live execution, wallet/private-key/signing, paid APIs,
scoring/ranking/confidence/weighted logic, embeddings/vectors, source fetching
outside governed commands, and Scheduler runtime expansion. The two `PARTIAL_MEMORY`
windows are not retrieval-eligible and were not promoted. No rerun of this
execution identity is authorized; the final-authorization branch/commit
(`6ca642c…`) remains unmerged.

---

## 14. Proof Needed Before Any Future Live Attempt

1. Full-run six-unit accounting: the factory lifecycle stages (per-token snapshot
   Scheduler work, lifecycle reservations, window-close local validations) must be
   sealed as campaign stage evidence with exact identities.
2. Campaign-window ownership: every real `printer_memory_windows` row from the run
   must be registered under `printer_memory_factory_campaign_windows` (or the
   equivalent), with `cycle_id` populated, so `reconciliation.windows` reflects the
   real lifecycle.
3. Non-vacuous owner/action-local reconciliation: an independently observed
   action-local transport surface for the lifecycle-started run must be supplied,
   so equality is *proven*, not defaulted.
4. Report gate: Campaign PASS must fail closed unless two real lifecycles are
   present *and* full-run accounting + owner/action-local equality are complete.
5. All existing safety invariants preserved (read-only preflight, backup/restore
   gate, zero forbidden deltas, DB before/after hashes, both markers unchanged,
   `AUTOMATIC_RETRIES=0`, one-attempt boundary).

---

## Functionality Risks / Setbacks / Efficiency Blockers

- **Functionality risk — false-clean terminal.** The current closure path can mark
  a two-lifecycle run `COMPLETED`/`reconciled` while omitting full-run evidence.
  Until repaired, no campaign terminal on this path can be trusted as PASS.
- **Functionality risk — vacuous reconciliation default.** `reconcile_owner_to_
  action_local` returns `equal=True` when handed no action-local surface; any
  caller that forgets to supply it gets a silent pass. The next design lane should
  make the lifecycle path require a non-empty action-local surface (fail closed).
- **Setback — one authorized attempt consumed.** The single-attempt boundary was
  spent producing an untrustworthy terminal; a fresh readiness → design →
  authorization cycle is required. Governed source budget (18 source calls, 10
  transports) and two real 15m lifecycles were spent for no trusted PASS.
- **Setback — orphaned real memory.** Windows 161/162 and episodes 58/59 exist in
  the authoritative DB but are unlinked to the campaign cycle and unpromoted;
  preflight must keep classing them as terminal history, not active residue.
- **Efficiency blocker — accounting scope.** Sealing full-run lifecycle stages and
  wiring an action-local observer for the lifecycle path is a non-trivial,
  design-first change; it must precede any further live attempt, adding a lane
  before the machine can attempt WINDOW_15M growth again.
- **Efficiency blocker — quality-label inconsistency.** Windows are
  `PARTIAL_MEMORY` while their episodes are `WINDOW_15M_CLEAN_MEMORY`; the design
  lane should reconcile these so promotion decisions are unambiguous.

---

## 15. Exact Next Permitted Lane

```text
V2-9.8B Post-Repair Authoritative WINDOW_15M Full-Run Accounting and Terminal-Evidence Design
```

Type: **design-only.** The root cause is isolated to a single factory↔campaign
ownership/accounting disconnect (Section 9), so the program may proceed to design
the full-run accounting and terminal-evidence model. That lane must not implement
runtime changes, run any campaign/preflight/report/recovery/N2/N7/cursor/source
operation, mutate the authoritative DB, repair or reclassify the July 31 or this
attempt's rows, merge `6ca642c…`, authorize another attempt, or unlock any
retrieval/financial capability. Implementation, bounded proof, and a fresh
authorization cycle remain separate later lanes.

---

## 16. Verdict

`V2_9_8B_POST_REPAIR_15M_BLOCKED_UNSAFE_FORENSIC_AUDIT_CONFIRMED`

A confirmed audit does not mean the campaign passed. Two real `WINDOW_15M`
lifecycles occurred, but the attempt is `BLOCKED_UNSAFE`: its terminal accounting
and canonical report omit the full-run per-token/window terminal evidence and rest
on a vacuous owner/action-local reconciliation, so its `COMPLETED` terminal cannot
be trusted as a Campaign PASS. No operational command, repair, test, or rerun
occurred; the authoritative DB was read only (before == after SHA-256).
