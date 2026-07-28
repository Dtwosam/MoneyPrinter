# Printer V1 V2-9.8B — First Successful Bounded Memory-Growth Campaign Closeout

## Final verdict

```text
V2_9_8B_FIRST_SUCCESSFUL_BOUNDED_MEMORY_GROWTH_PASS
```

This closeout documents the first successful operator-authorized V2-9.8B bounded
two-token operational memory-growth campaign on the authoritative persistent
corpus.

It is documentation only. It does not authorize another campaign, selective
`WINDOW_1H` / `WINDOW_4H` collection, retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL, live execution, wallets, private keys, paid
APIs, scoring, ranking, confidence percentages, weighted logic, embeddings, or
vectors.

V2-9.8B remains the active memory-growth operations lane. V2-10 does not begin.
`WINDOW_12H` and `WINDOW_24H` remain locked.

---

## 1. Baseline and campaign identities

| Item | Value |
|---|---|
| Repository | `/Users/Dtwo1/Developer/MoneyPrinter` |
| Branch | `master` |
| Required starting commit / observed HEAD | `0ad6efa38f10700d894b30efa2f6408fb9bfe0e9` |
| HEAD subject | `Close V2-9.8B discovery-only command surface` |
| Tracked worktree / index at closeout start | clean |
| Authoritative database | `data/printer_v1.sqlite3` |
| Authoritative DB SHA-256 (read-only inspection) | `1a8190ef0fa4b9226cf3fe25f4403998fadedc6a88ffad0f3faf0e1e410e9166` |
| Integrity / foreign keys | `ok` / 0 violations |
| Applied migrations observed | 46 |
| Public command surface | `printer-run-v2-9-8-memory-factory` → `operational_memory_factory_command` |
| PowerShell wrapper | `scripts/Start-PrinterV1-MemoryFactory.ps1` |

### Campaign identities

| Identity | Value |
|---|---|
| Execution | `20260727T235023Z-390455e31060` |
| Campaign | `20260727T235023Z-390455e31060-campaign` |
| Configuration | `20260727T235023Z-390455e31060-configuration` |
| Campaign run | `20260727T235023Z-390455e31060-campaign-run` |
| Cycle | `20260727T235023Z-390455e31060-cycle` |
| Factory run | `cf4ab538-f4a2-4c2f-bd5a-b10e3f7c8d74` |
| Report | `20260727T235023Z-390455e31060-report` |
| Report kind | `PILOT_CAMPAIGN_TERMINAL` / `TERMINAL` |
| Policy version (report) | `V2_9_7E_47_UNIFIED_TERMINAL_CLOSURE` |
| Campaign policy version (DB) | `V2-9.8-15M-OPERATIONAL-V1` |
| DB mode | `OPERATIONAL_PERSISTENT` |

### Retained artifacts

| Artifact | Path |
|---|---|
| Terminal campaign report | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260727T235023Z-390455e31060/reports/20260727T235023Z-390455e31060-report.campaign-report.json` |
| Terminal summary | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260727T235023Z-390455e31060/terminal-summary.json` |
| Pre-campaign backup | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260727T235023Z-390455e31060/printer_v1.pre-campaign.backup.sqlite3` |
| Restore rehearsal | `/Users/Dtwo1/PrinterOperations/v2-9-8/20260727T235023Z-390455e31060/printer_v1.restore-rehearsal.sqlite3` |
| Report SHA-256 | `46766d20b368df4c3ffd4fe10840aef8a835d0423711b69c57a463db7872fdad` |

Report hash match: retained file SHA-256 == terminal-summary `report_hash` ==
database `printer_memory_factory_campaign_reports.report_hash`. One terminal
report row. `artifact_count = 1`, `report_rows = 1`.

---

## 2. Scope and boundaries

### In scope

- Documentation-only closeout of one already-executed successful campaign.
- Static source/test inspection of clean-memory promotion semantics.
- Read-only review of retained artifacts.
- Read-only SQLite inspection (`mode=ro`, `PRAGMA query_only = ON`).
- Minimum sufficient safety and diff checks.
- One documentation-only commit of this closeout.

### Explicitly out of scope / not performed

- Source fetching, discovery, Scheduler runtime, campaign execution.
- Memory generation or database mutation.
- Code, migration, or test-fixture changes.
- Another 15m campaign.
- Any `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` collection or proof.
- Retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, paper-trade
  audits, PnL, live execution, wallet/private-key logic, paid APIs, scoring,
  ranking, confidence or weighted logic, embeddings or vectors.
- Selective 1h/4h readiness audit (next permitted separate lane; not started).

---

## 3. Preflight evidence

Launch Git provenance recorded in the retained terminal report:

| Field | Value |
|---|---|
| `git_head` | `0ad6efa38f10700d894b30efa2f6408fb9bfe0e9` |
| `git_tracked_tree_clean` | `true` |
| `git_staged_changes_present` | `false` |
| `git_unstaged_changes_present` | `false` |
| `git_untracked_present` | `false` |
| `git_provenance_captured_at` | `2026-07-27T23:50:22.984063+00:00` |

This matches the required closeout baseline. The campaign was one separately
authorized operational run after V2-9.8A operator activation and the V2-9.8B
repair/readiness sequence. No automatic retry, restart, or successor was created
by this campaign.

Pre-campaign backup and restore-rehearsal artifacts were retained under the
execution root. This closeout did not re-run preflight, backup, or restore.

---

## 4. Campaign execution evidence

| Field | Observed value |
|---|---|
| Campaign state | `TERMINAL_COMPLETED` |
| Run state | `TERMINAL_COMPLETED` |
| Cycle state | `TERMINAL_COMPLETED` |
| Factory run status | `COMPLETED` |
| Terminal status | `COMPLETED` |
| First / terminal cause | `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED` |
| Lifecycle started | `true` |
| Main window policy | `WINDOW_15M` only |
| Token capacity | exact 2 |
| Campaign source calls | **15** |
| Campaign Scheduler runtime calls | **0** |
| Restart created | `false` |
| Successor created | `false` |
| Factory started_at | `2026-07-27T23:56:51.321581+00:00` |
| Factory finished_at | `2026-07-28T00:12:09.305106+00:00` |
| Campaign terminal_at | `2026-07-28T00:12:09.306449+00:00` |

### Safe-terminal reconciliation

From retained report `reconciliation` and read-only DB checks:

| Check | Result |
|---|---|
| `clean_terminal` | `true` |
| Active jobs | 0 |
| Active work rows | 0 |
| Locked job IDs | `[]` |
| Pending/running run steps | 0 |
| Jobs by status in scope | `SUCCEEDED: 26` (8 discovery + 18 factory steps) |
| Cancelled jobs at terminal | 0 |
| Global PENDING/RUNNING/COOLDOWN scheduler jobs | 0 |
| Locked scheduler jobs (`locked_at` / `lock_owner`) | 0 |
| Heartbeat failure rows for this campaign | 0 |

Post-lifecycle dispositions:

| Token slot | Queue disposition | Slot disposition | Tracking queue |
|---|---|---|---|
| `slot-...-cycle-1` | `COOLDOWN` | `MANUAL_REVIEW` | 26 |
| `slot-...-cycle-2` | `COOLDOWN` | `MANUAL_REVIEW` | 27 |

Slot DB states are both `MANUAL_REVIEW` with terminal cause
`COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`.

### No-unlock deltas

Retained report forbidden deltas for this campaign:

| Table / capability | Delta |
|---|---:|
| `printer_memory_retrieval_queries` | 0 |
| `printer_memory_retrieval_matches` | 0 |
| `printer_paper_decisions` | 0 |
| `printer_paper_positions` | 0 |
| `printer_paper_trade_events` | 0 |
| `printer_paper_trade_audits` | 0 |
| `printer_paper_audit_reports` | 0 |

Downstream unlock flags all `false`: retrieval, paper decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL.

Historical corpus rows may already exist from earlier phases; campaign-scoped
deltas remained zero.

---

## 5. Exact token / pair / window / episode traceability

### Tokens and pairs

| Slot | Token ID | Mint | Pair ID | Pair address | PumpSwap registry | Discovery confirmation |
|---:|---:|---|---:|---|---|---|
| 1 | 22 | `12u9FULaUfHD8uHHe98Fz5gdhg8qeX6DyV93B3Dtpump` | 26 | `ECobcS1MSzzAnnzz89xjwRSEYsHAChB7DMbd3G25gwgc` | `PUMPSWAP_GRADUATED_CONFIRMED` | `CONFIRMED` / `ADMITTED` |
| 2 | 24 | `3zh9CTwPf8vvPrM5xBWmdkzpWRbmRJyvYo46fZBVpump` | 28 | `BNiVaqvJg5WXBUdZdqrcHAttGtii5fDvBTR5UaERRsbj` | `PUMPSWAP_GRADUATED_CONFIRMED` | `CONFIRMED` / `ADMITTED` |

Both tokens are Solana-only (`printer_tokens.chain = solana`). Both have exact
PumpSwap-graduated identities in
`printer_pumpswap_graduated_candidate_registry` with pools matching the
selected pair addresses and program id
`pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA`. Campaign-scoped discovery
confirmations for batch
`discovery-batch:20260727T235023Z-390455e31060-campaign:...` are `CONFIRMED` /
`ADMITTED`.

### Memory windows

| Window ID | Token | Pair | Kind | Status | `memory_status` | `memory_quality_label` | `data_quality_label` | `do_not_train` | Opened | Closed |
|---:|---:|---:|---|---|---|---|---|---:|---|---|
| 157 | 22 | 26 | `WINDOW_15M` | `WINDOW_CLOSED` | **`PARTIAL_MEMORY`** | **`PARTIAL_MEMORY`** | `CLEAN_DATA` | 0 | `2026-07-27T23:56:51.899348+00:00` | `2026-07-28T00:12:04.462330+00:00` |
| 158 | 24 | 28 | `WINDOW_15M` | `WINDOW_CLOSED` | **`PARTIAL_MEMORY`** | **`PARTIAL_MEMORY`** | `CLEAN_DATA` | 0 | `2026-07-27T23:56:52.386832+00:00` | `2026-07-28T00:12:09.203783+00:00` |

Both windows are E2Q-audited (`e2q_audited=true`, `e2q_audited_by=lane_e2q`)
with snapshot links and full 9-snapshot ID sets in supporting context.

### Clean episodes (authoritative promoted memory)

| Episode ID | Window | Token | Pair | `episode_kind` | `episode_status` | `memory_status` | `memory_quality_label` | `data_quality_label` | `do_not_train` | Created by |
|---:|---:|---:|---:|---|---|---|---|---|---:|---|
| 54 | 157 | 22 | 26 | `WINDOW_15M_CLEAN_MEMORY` | `COMPLETE` | **`CLEAN_MEMORY`** | **`CLEAN_MEMORY`** | `CLEAN_DATA` | 0 | `lane_e2z` |
| 55 | 158 | 24 | 28 | `WINDOW_15M_CLEAN_MEMORY` | `COMPLETE` | **`CLEAN_MEMORY`** | **`CLEAN_MEMORY`** | `CLEAN_DATA` | 0 | `lane_e2z` |

Episode supporting context records:

- `source_window_id` 157 / 158
- close `snapshot_id` 1035 / 1036
- `e2q_audit_status` = `PARTIAL_MEMORY` (source-window candidate status at audit)
- `created_by` = `lane_e2z`

### Snapshot and factory-step proof

Factory run `cf4ab538-f4a2-4c2f-bd5a-b10e3f7c8d74`:

| Metric | Value |
|---:|---:|
| Total steps | 18 |
| Succeeded steps | 18 |
| Failed / cancelled / pending / running | 0 |
| Token 22 SNAPSHOT steps | 8 |
| Token 22 WINDOW_CLOSE steps | 1 (`SUCCEEDED`, window 157, snapshot 1035) |
| Token 24 SNAPSHOT steps | 8 |
| Token 24 WINDOW_CLOSE steps | 1 (`SUCCEEDED`, window 158, snapshot 1036) |
| Distinct snapshots per token | **9 of 9** |

Token 22 snapshot IDs: 1019, 1021, 1023, 1025, 1027, 1029, 1031, 1033, 1035  
Token 24 snapshot IDs: 1020, 1022, 1024, 1026, 1028, 1030, 1032, 1034, 1036  

Only `WINDOW_15M` main windows were created by this campaign. No 1h/4h/12h/24h
memory windows were opened.

---

## 6. Clean-memory semantic verification

### Question under review

Why do the source memory-window rows remain:

```text
printer_memory_windows.memory_status = PARTIAL_MEMORY
printer_memory_windows.memory_quality_label = PARTIAL_MEMORY
```

while the matching promoted episodes are:

```text
printer_episodes.episode_kind = WINDOW_15M_CLEAN_MEMORY
printer_episodes.episode_status = COMPLETE
printer_episodes.memory_status = CLEAN_MEMORY
printer_episodes.memory_quality_label = CLEAN_MEMORY
printer_episodes.data_quality_label = CLEAN_DATA
```

### Implementation trace (authoritative promotion path)

1. **Source-window candidate state**  
   Closed 15m windows are stored as audit-eligible candidates. E2Z eligibility
   deliberately requires the window itself to remain pre-promotion partial:

   - module: `src/printer_v1/operator_cli/e2z_clean_memory_creation.py`
   - gate constants: `_REQUIRED_MEMORY_STATUS = "PARTIAL_MEMORY"`,
     `_REQUIRED_MEMORY_QUALITY = "PARTIAL_MEMORY"`
   - docstring contract: eligibility is
     `WINDOW_15M + WINDOW_CLOSED + CLEAN_DATA + PARTIAL_MEMORY + e2q_audited +
     snapshot link + do_not_train=0 + no legacy CLEAN_MEMORY label on the window`

2. **Promotion write boundary**  
   `create_clean_memory_from_window(...)` is the only Lane E write path into
   `printer_episodes`. On success it inserts:

   - `episode_kind = f"{window_kind}_CLEAN_MEMORY"` → `WINDOW_15M_CLEAN_MEMORY`
   - `episode_status = COMPLETE`
   - `memory_status = CLEAN_MEMORY`
   - `memory_quality_label = CLEAN_MEMORY`
   - `data_quality_label = CLEAN_DATA`
   - `do_not_train = 0`
   - `created_by = lane_e2z` in supporting context

   It does **not** rewrite the source window row to `CLEAN_MEMORY`. The window
   remains the pre-promotion candidate record.

3. **Authoritative yield / reporting contract**  
   Committed V2-9.7B.1 repair and factory reporting treat eligible episodes as
   authoritative clean yield, not the window label:

   - `_authoritative_promotions_for_run()` in
     `src/printer_v1/operator_cli/one_command_15m_factory.py` selects
     `printer_episodes` with
     `episode_status='COMPLETE'`, `memory_status='CLEAN_MEMORY'`,
     `data_quality_label='CLEAN_DATA'`, `do_not_train=0`,
     `memory_quality_label='CLEAN_MEMORY'`, joined to the run's steps.
   - `_per_token_outcomes()` still surfaces
     `source_memory_window_status` / window `memory_quality_label` as candidate
     evidence, while `promotion_status` / `authoritative_episode_id` come from
     the episode.
   - Closeout
     `docs/printer-v1-v2-9-7b-1-authoritative-promotion-reporting-closeout.md`
     states explicitly that a successfully promoted episode is reported clean
     while its source candidate may remain `PARTIAL_MEMORY`.

4. **Focused tests that lock this contract**

   - `tests/test_v2_9_7b_1_authoritative_promotion_reporting.py`
     — clean promoted episodes counted once; pre-promotion `PARTIAL_MEMORY`
     remains visible and does not suppress clean yield.
   - `tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py`
     — clean/dirty evidence gates and lifecycle reporting.
   - Lane K / E2Z pipeline tests — promote eligible `PARTIAL_MEMORY` windows
     into `CLEAN_MEMORY` episodes without treating the window label as the
     final yield.

### Answers required by this closeout

| # | Question | Finding |
|---:|---|---|
| 1 | Why do representations differ? | By design: window = pre-promotion candidate evidence; episode = promoted clean-memory yield created by E2Z. |
| 2 | Expected by committed design? | **Yes.** E2Z gate requires window `PARTIAL_MEMORY`; promotion creates episode `CLEAN_MEMORY` and does not mutate the window into clean. V2-9.7B.1 reporting documents this dual representation. |
| 3 | Which row is authoritative for persistent clean-memory yield? | **`printer_episodes`** rows matching the E2Z / B.1 eligibility contract (`COMPLETE` + `CLEAN_MEMORY` + `CLEAN_DATA` + `do_not_train=0` + `WINDOW_15M_CLEAN_MEMORY`). |
| 4 | Does continuation currently consume the correct representation? | **Intended path yes; raw window label no.** `campaign_authority_adapters.build_4a_authority_facts()` maps B.1 promotion success to `predecessor_memory_quality = CLEAN_MEMORY`. `token_local_continuation` then requires predecessor clean quality. Reading only `printer_memory_windows.memory_status` would wrongly treat promoted windows as non-clean. |
| 5 | Does this mismatch block later selective 1h continuation? | **The PARTIAL-vs-CLEAN dual representation itself is not a blocker.** It is the expected candidate/promoted split. Separate readiness concerns for a future 1h audit are: this campaign has **zero** rows in `printer_memory_factory_campaign_windows`, and the campaign run's `authoritative_run_id` is **null**. Those graph-link fields are required by the campaign-authority / final-report adapters, so a later selective-1h readiness review must verify how operational 15m success is re-bound for continuation. That is out of scope for this closeout and does **not** invalidate the 15m clean episodes. |

### Semantic verdict for this campaign

Episodes 54 and 55 are trustworthy completed clean-memory evidence for windows
157 and 158. Clean memory means trustworthy completed evidence, **not** a
favourable setup, tradeable opportunity, or BUY readiness.

Observed context labels include adverse/neutral learning content (for example
choppy/sideways structure, flow caution, dead/low activity labels). Clean does
not mean profitable.

---

## 7. Terminal-report under-count: `reconciliation.windows = {}`

### Observed fact

Retained terminal report:

```text
reconciliation.windows = {}
```

Read-only DB:

```text
COUNT(*) FROM printer_memory_factory_campaign_windows
WHERE campaign_id = '20260727T235023Z-390455e31060-campaign'
= 0
```

### Implementation explanation

`reconcile_campaign_terminal()` in
`src/printer_v1/operator_cli/unified_terminal_closure.py` initializes
`windows: {}` and only fills it from
`printer_memory_factory_campaign_windows` rows for the campaign/run. With zero
campaign-window graph rows, the report field remains empty even though:

- `printer_memory_windows` 157 and 158 exist and closed;
- factory steps succeeded;
- E2Z clean episodes 54 and 55 exist.

### Classification

| Classification | Result |
|---|---|
| Blocker for this closeout PASS? | **No** |
| Accepted reporting limitation / carry-forward? | **Yes** |
| Documented family | Related to residual report honesty / graph completeness awareness from the V2-9 / V2-9.7 program; not repaired here |

This is an accepted terminal-report graph under-count. Operators must not infer
“no windows / no clean memory” from `reconciliation.windows = {}` alone. Exact
yield must be read from factory steps, `printer_memory_windows`, and
authoritative `printer_episodes`.

No repair was performed in this task.

---

## 8. Report-only replay proof

Established campaign evidence (not re-executed by this closeout):

| Check | Result |
|---|---|
| Report-only source calls | 0 |
| Report-only Scheduler runtime calls | 0 |
| Report-only database writes | 0 |
| Duplicate reports created | 0 (DB still has exactly one terminal report row for this campaign) |
| Retained artifact matched | Yes — file/DB/summary hash `46766d20b368df4c3ffd4fe10840aef8a835d0423711b69c57a463db7872fdad` |

Public `report-only` ownership remains
`operational_memory_factory_command.report_only()`, which is a read-only path
over stored terminal reports and does not start discovery, collection, or
Scheduler runtime.

This closeout did not re-run `report-only`.

---

## 9. Source and Scheduler accounting

| Counter | Campaign value |
|---|---:|
| Campaign source calls | 15 |
| Campaign Scheduler runtime calls | 0 |
| Restart | false |
| Successor | false |
| Automatic retry | none observed |

Fifteen governed source calls completed the bounded two-token 15m campaign
within the operational ceiling model. No Scheduler runtime expansion occurred
for this campaign report accounting surface.

---

## 10. Host-sleep failure history and `caffeinate`

### Prior operational failure (not this campaign)

Immediately before the successful campaign, execution
`20260727T232042Z-11c5edd2d9da` failed with durable first cause:

```text
LEASE_RENEWAL_LEASE_EXPIRED
```

Heartbeat failure ledger evidence:

| Field | Value |
|---|---|
| Supervision | `20260727T232042Z-11c5edd2d9da-supervision` |
| Safe category | `LEASE_EXPIRED` |
| Safe message | lease had expired before renewal could be confirmed |
| Prior heartbeat | `2026-07-27T23:28:38.238638+00:00` |
| Prior lease expiry | `2026-07-27T23:30:08.238638+00:00` |
| Attempted renewal | `2026-07-27T23:31:38.492516+00:00` |
| `sqlite_locked` | 0 |
| Lifecycle started | true |
| Clean terminal / no restart / no successor | true / false / false |
| Campaign source calls before fail | 14 |

The renewal attempt landed after the lease expiry window. That pattern is
consistent with host suspension (macOS sleep / process freeze) interrupting the
operational heartbeat thread, not with a newly discovered Printer promotion
defect.

Earlier the same day also recorded `LEASE_RENEWAL_SQLITE_LOCKED` failures on
other executions; those are separate SQLite contention cases already addressed
by V2-9.8B heartbeat/concurrency repairs. The immediate predecessor of the
successful campaign is the lease-expired case above.

### Operational correction, not code repair

Keeping the host awake with macOS `caffeinate` (or equivalent sleep prevention)
is an **operator environment correction**. It does not change Printer code,
widen leases as a substitute for honesty, unlock capabilities, or repair dirty
memory logic.

The successful campaign `20260727T235023Z-390455e31060` completed with:

- no heartbeat failure row for this campaign;
- factory run `COMPLETED`;
- terminal cause `COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED`.

---

## 11. Money-usefulness contribution

This campaign contributes the first operationally produced pair of trustworthy
two-token 15m clean memories on the persistent corpus under the public V2-9.8
command surface.

Money-usefulness here means:

- governed discovery → selection → tracking → 15m collection → close → audit →
  E2Z promotion → report → safe stop worked end-to-end;
- both positive-process and adverse-outcome evidence can become clean when
  evidence is complete;
- operators can trust episode-level clean yield without inventing profit,
  ranking, or BUY readiness.

It does **not** mean the tokens were good trades. Clean memory is completed
evidence quality, not alpha.

---

## 12. What this campaign improved

- Proved V2-9.8B can complete a bounded two-token operational 15m campaign on
  the authoritative DB.
- Produced exact token/pair/window/episode lineage for two PumpSwap-graduated
  Solana memecoins.
- Completed 18/18 factory steps and 9/9 snapshots per token.
- Promoted two authoritative `WINDOW_15M_CLEAN_MEMORY` episodes.
- Preserved zero campaign-scoped retrieval/financial deltas.
- Stopped cleanly with no restart/successor and no residual active work.
- Confirmed retained report hash identity across file, summary, and DB.

---

## 13. What it still does not unlock

Still locked after this PASS:

- V2-10 / V2-11
- Operational selective `WINDOW_1H` (requires separate readiness audit first)
- Conditional `WINDOW_4H`
- `WINDOW_12H` / `WINDOW_24H`
- Retrieval activation / similarity use for decisions
- Paper decisions
- BUY / SELL / HOLD
- Paper positions, trade events, paper-trade audits, PnL
- Live execution, wallets, private keys, signing, real funds
- Paid APIs
- Scoring, ranking, confidence percentages, weighted decision logic
- Embeddings / vectors
- Automatic campaign retry/restart/successor
- Scaling beyond the current bounded two-token operational posture without a
  later authorized lane
- Any claim of profit, favourable setup, or tradeability merely from clean
  episodes

V2-9.8B remains active as the bounded memory-growth operations lane. This
closeout does **not** authorize another campaign by itself.

---

## 14. Functionality Risks / Setbacks / Efficiency Blockers

| ID | Item | Severity for this closeout | Notes |
|---|---|---|---|
| R1 | Terminal `reconciliation.windows = {}` under-count | Carry-forward / non-blocking | Campaign-window graph table empty; yield must be read from windows/episodes/steps |
| R2 | Campaign run `authoritative_run_id` is null | Carry-forward for later 1h audit | Does not erase 15m clean episodes; may affect campaign-authority adapters |
| R3 | Zero `printer_memory_factory_campaign_windows` rows | Carry-forward for later 1h audit | Same family as R1/R2; selective continuation wiring must be re-checked before 1h |
| R4 | Host-sleep / lease-expiry operational risk | Residual operational risk | Mitigated by host awake policy (`caffeinate`); not a Printer code defect for this PASS |
| R5 | Partial wallet-level flow authenticity remains limited | Residual awareness | Existing V2-9 residual; did not prevent clean 15m promotion under current gates |
| R6 | Some context engines still partial/unknown at payload edges | Residual awareness | Clean promotion still required complete mandatory evidence path; do not over-read labels as trade signals |
| R7 | Misreading window `PARTIAL_MEMORY` as “not clean” | Operator/process risk | Authoritative yield is episode-based; documentation must stay explicit |
| R8 | Temptation to treat clean episodes as BUY readiness | Hard lock risk | Forbidden; clean ≠ favourable ≠ tradeable |

No item above blocks the first-successful-campaign PASS when interpreted under
the committed promotion contract and remaining locks.

---

## 15. Final verdict and next permitted lane

### Verdict

```text
V2_9_8B_FIRST_SUCCESSFUL_BOUNDED_MEMORY_GROWTH_PASS
```

### Preserved after PASS

- V2-9.8B remains active.
- V2-10 does not begin.
- 12h/24h remain locked.
- Retrieval and all paper/financial capabilities remain locked.
- No further campaign is authorized by this closeout.
- Selective 1h/4h are **not** labeled ready.

### Exact next permitted lane

```text
Separate audit/readiness review for operational selective WINDOW_1H
(followed later, only if that audit passes, by conditional WINDOW_4H readiness)
```

Do not start the selective 1h/4h readiness audit inside this closeout. Do not
implement or activate any continuation window until that separate lane is
explicitly opened and completed.

---

## 16. Closeout method and verification

### Performed

- Confirmed HEAD `0ad6efa38f10700d894b30efa2f6408fb9bfe0e9` and clean tracked tree.
- Read active source stack and just-in-time promotion/reporting sources.
- Read retained campaign report and terminal summary.
- Read-only SQLite inspection with URI `mode=ro` and `PRAGMA query_only = ON`.
- Verified integrity `ok` and foreign-key violations empty.
- Verified report SHA-256 match across retained file, terminal summary, and DB.
- Statically traced E2Z / B.1 / continuation-adapter semantics and focused tests.
- Created this documentation file only.

### Not performed

- No source call.
- No discovery.
- No Scheduler runtime.
- No campaign execution.
- No memory generation.
- No database mutation.
- No code/test/migration change.
- No 1h/4h run.
- No retrieval or financial unlock.
- No broad regression suite.

### Database hash after inspection

```text
1a8190ef0fa4b9226cf3fe25f4403998fadedc6a88ffad0f3faf0e1e410e9166
```

Unchanged from the start of this documentation inspection.

---

## 17. Required response anchors

- **Files changed:** this document only
  (`docs/printer-v1-v2-9-8b-first-successful-bounded-memory-growth-closeout.md`)
- **What was built:** documentation-only closeout of the first successful
  V2-9.8B bounded two-token operational memory-growth campaign
- **What was not touched:** code, migrations, tests, database, operations
  artifacts, build order files
- **Tests/checks run:** static source/test inspection; read-only SQLite
  integrity/FK; report hash match; documentation safety language review
- **Pass/fail status:** `V2_9_8B_FIRST_SUCCESSFUL_BOUNDED_MEMORY_GROWTH_PASS`
- **Risks or concerns:** empty terminal `windows` map; null
  `authoritative_run_id`; host-sleep operational residual; do not misread clean
  as tradeable
- **Next recommended phase:** separate audit/readiness review for operational
  selective `WINDOW_1H` (not started here)
