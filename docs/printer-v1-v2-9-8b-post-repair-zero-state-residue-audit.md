# Printer V1 V2-9.8B Post-Repair Zero-State Residue Audit

Date: 2026-08-14

## Verdict

`V2_9_8B_POST_REPAIR_ZERO_STATE_RESIDUE_AUDIT_PASS_RESIDUE_CONFIRMED_CANONICAL_CLEANUP_PATH_INSUFFICIENT`

The five orphaned rows are confirmed to still exist, all belong to consumed
execution `20260814T172224Z-490856f405bf`, and no live ownership remains. The
already-completed slot-order/rollback repair is present and is **not** re-opened
by this audit. However, no existing canonical operator-reachable path can close
this residue without production-code changes, and one residual gap in the
four-token shared-terminal owner is identified for a later lane.

## Boundary

Read-only audit only. No DB mutation, no reconciliation, no cleanup, no
authorization, no Printer/proof/runtime execution, no discovery or source fetch,
no memory generation, no Scheduler work creation, no six-token widening, no
retrieval, no BUY/SELL/HOLD, no positions, trades, audits, or PnL.

The consumed authorization
`V2_9_8B_FOUR_TOKEN_PROOF_AUTH_20260814T171249Z_0022b4dc` remains permanently
consumed.

## Repository state

- Starting HEAD: `c7279622247a7e18ff2b29c6ebc63597d4774b92`
  (`Review four-token slot-order rollback post-repair rereadiness`)
- Final code HEAD: `c7279622247a7e18ff2b29c6ebc63597d4774b92` — unchanged. Every
  check in this audit was performed at that exact commit, and this lane adds one
  documentation-only commit carrying this file. No production source, test,
  migration, database, runtime, Source Governor, Central Scheduler, memory,
  retrieval, or trading state was changed.
- Final branch HEAD: the single audit commit on this branch, whose hash is
  reported in the lane report (a commit cannot embed its own hash).
- Branch: `agent/v2-9-8b-post-repair-zero-state-residue-audit`, created from
  exactly `c7279622247a7e18ff2b29c6ebc63597d4774b92` after `git fetch --all`
- Prior local commit `8adad8bfb010eef3ed9c9d40e01078ef7b287d01` is **not** an
  ancestor of this branch and was not carried forward (verified with
  `git merge-base --is-ancestor`)

### Correction to the prior lane

The previous audit ran on stale lineage at HEAD
`aa5ab488c74b90ba57b1ca8e390bb50507609537` and reported that
`c7279622247a7e18ff2b29c6ebc63597d4774b92` did not exist. That commit was simply
un-fetched at the time; it exists on `origin` and is now local. Its lineage
(`0881482` repair → `35d7db2` closeout → `c727962` rereadiness review) already
contains the slot-order/rollback production repair. That defect is **not**
re-audited or re-repaired here.

## Authoritative database identity and integrity

Read with a sidecar-safe immutable read-only handle
(`inspect_authoritative_database`):

- path: `/Users/Dtwo1/Developer/MoneyPrinter/data/printer_v1.sqlite3`
- sha256: `5e830af41d58325d3f9e521f1b95f697b8151113cb783cf05a2a776e204639bc`
- size: `94961664`
- inode: `1230526`
- mtime_ns: `1786728163188205876`
- migration count: `55`
- migration head: `055_pre_admission_discovery_attempt_ownership.sql`
- ledger digest: `6aab51d80f9899d338c4991ba793dfbe073b5777ac30c954979f4d327acf47f8`
- integrity: `ok`
- foreign-key violations: `0`
- SQLite sidecars: none
- opened mode: `read_only_immutable`

The sha256 is byte-identical to the value observed by the previous lane, which
independently confirms no mutation has occurred in the interim and that this
audit did not disturb the database.

## Question 1 — do the five rows still exist?

Yes. `project_four_token_proof_zero_state()` at this exact codebase reports:

| domain | count |
| --- | --- |
| `active_campaigns` | **1** |
| `active_campaign_runs` | **1** |
| `active_campaign_cycles` | **1** |
| `active_campaign_scheduler_work` | 0 |
| `campaign_supervision` | **1** |
| `proof_supervision` | 0 |
| `active_discovery_work` | 0 |
| `active_factory_runs` | **1** |
| `active_factory_steps` | 0 |
| `pre_admission_discovery_attempts` | 0 |
| `active_scheduler_jobs` | 0 |

Five non-zero domains, identical to the prior report. The prior interpretation is
re-established from this codebase rather than inherited.

## Question 2 — exact ownership and state

All five rows are owned by consumed execution `20260814T172224Z-490856f405bf`.
No row belongs to any other execution.

| # | table | identity | state | linkage |
| --- | --- | --- | --- | --- |
| 1 | `printer_memory_factory_campaigns` | `20260814T172224Z-490856f405bf-campaign` | `RUNNING` | `first_terminal_cause` null, `terminal_at` null |
| 2 | `printer_memory_factory_campaign_runs` | `20260814T172224Z-490856f405bf-campaign-run` | `RUNNING` | `campaign_id` → row 1; `authoritative_run_id` → row 5 |
| 3 | `printer_memory_factory_campaign_cycles` | `20260814T172224Z-490856f405bf-cycle` | `PLANNED` (ordinal 1) | `campaign_id` → row 1, `run_id` → row 2 |
| 4 | `printer_memory_factory_campaign_supervision` | `20260814T172224Z-490856f405bf-supervision` | `ACTIVE` | `campaign_id` → row 1, `run_id` → row 2 |
| 5 | `printer_memory_factory_runs` | `ed0fa279-38e6-401b-8b34-0a9531a9c720` | `RUNNING` | `config_json` carries campaign/run/cycle ids of rows 1–3 |

Supporting facts:

- campaign `policy_version` = `V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1`
- campaign `db_target_identity` = `sha256:a9c82e97…` (the pre-write identity the
  consumed authorization bound); this column is written at campaign creation and
  is read only for reporting — no reconciliation owner re-validates it, so it is
  not itself a blocker
- factory run `config_json.git_provenance.git_head` =
  `aa5ab488c74b90ba57b1ca8e390bb50507609537`, i.e. the residue was produced by
  the pre-repair lineage
- factory run `selected_token_count` = 0, `finished_at` null, `stop_reason` null

Cycle-scoped children (all already terminal, none counted as residue):

- `printer_memory_factory_campaign_token_slots`: exactly **2** rows,
  `slot_ordinal` 1 and 2, both `token_state = SELECTED` (non-terminal but not a
  zero-state domain). Slot 1 = `yUmeQo96g6MurikjHiMg7u23X5yQXJ9SQpoJPcbpump`,
  slot 2 = `CAGtwKrcnwgLABdg5o16oMczxUV6i1pj973K9XWQpump` — the exact slot order
  named in the blocker audit, preserved as forensic evidence.
- `printer_memory_factory_campaign_scheduler_work`: 10 rows, all terminal
  (8 `SUCCEEDED`, 2 `CANCELLED`), all `ownership_contract_version =
  V2_STAGE_SCOPED`, all `work_scope` ∈ `WORK_SCOPES`, all with a non-null
  `scheduler_job_id`.
- `printer_scheduler_jobs` 2011–2020: all terminal (`SUCCEEDED`/`CANCELLED`),
  every `locked_at` and `lock_owner` null — no orphan lock.
- `printer_memory_factory_campaign_windows` for the cycle: 0 rows.
- `printer_memory_factory_run_steps` for factory run `ed0fa279…`: 0 rows.
- `printer_pre_admission_discovery_attempts` for the campaign: **0 rows**.

## Question 3 — does any live ownership remain?

No.

- `active_printer_runtime_processes()` returns `()` — no live Printer runtime.
- Host scan for `operational_memory_factory_command`: 0 processes.
- Consumed child PID `59354` is not alive.
- `proof_supervision` (`STARTING`/`RUNNING`): 0.
- `active_scheduler_jobs` (`PENDING`/`RUNNING`/`COOLDOWN`): 0; no job holds
  `locked_at` or `lock_owner`.
- Campaign supervision lease: `lease_expires_at =
  2026-08-14T17:23:54.788541+00:00` — expired hours before this audit.
  `cleanup_completed_at` null, `lease_released_at` null,
  `cancellation_requested_at` null.
- Lease lock file
  `/Users/Dtwo1/PrinterOperations/v2-9-8/20260814T172224Z-490856f405bf/campaign.lease.lock`
  still exists on disk, held by no live process.

The residue is **abandoned durable ownership**, not live work.

## Question 4 — can the canonical path close this residue without production changes?

**No.** Three independent reasons, in order of severity.

### 4a. There is no operator-reachable entrypoint

`reconcile_four_token_cycle_terminal()` (Phase A) and
`finalize_four_token_shared_terminal()` (Phase B) are called only from inside
`one_command_15m_factory`'s terminal `finally:` block during a live factory run
(`src/printer_v1/operator_cli/one_command_15m_factory.py:7951` and `:8032`).
Neither is exposed as a standalone operator action.

The operator CLI modes are `preflight-only`, `run`, `selective-1h-preflight`,
`selective-1h-proof`, `standard-four-hour-preflight`, `standard-four-hour-run`,
`four-token-bounded-capacity-proof-run`, `status`, `cooperative-stop`,
`recover-orphan`, `report-only`, `discovery-only`. None invokes four-token
terminal reconciliation against an already-dead execution. Reaching Phase A/B
would require launching a proof run, which is exactly what must not happen.

### 4b. `recover-orphan` is pinned to a different execution

`recover_exact_orphan()` defaults to `OrphanRecoveryContract`, whose
`EXECUTION_ID` is the hardcoded historical value
`20260726T114155Z-95d9979a9302`, with a hardcoded `EXPECTED_CURRENT_SHA256` and
`ORIGINAL_TERMINAL_CAUSE = OPERATIONAL_CAMPAIGN_FAILED:GitProvenanceError`.
Against the current database it fails closed at
`current authoritative DB SHA mismatch`. It cannot address
`20260814T172224Z-490856f405bf` without a production-code change.

### 4c. `cooperative-stop` cannot terminalize an abandoned campaign

`cooperative_stop()` calls `request_campaign_cancellation()`, which records
`cancellation_requested_at`/reason and depends on a live cooperating campaign
process to observe the request and terminalize. With no live owner it would
mutate the database while leaving all five rows non-terminal — strictly worse
than the current state.

### Phase A preconditions, if it were reachable

For completeness, Phase A's guards would be satisfiable by this residue:
`connection.in_transaction` false on a fresh connection; `_require_exact_shared_run`
passes (run `RUNNING`, `authoritative_run_id` = `ed0fa279…`); cycle ordinal 1 is
valid and non-terminal; `slot_count == 2`; all scheduler work is canonical with
non-null job ids; no job is missing. Phase A alone would terminalize the cycle,
the two slots, and cycle-scoped work — but it does **not** touch the campaign,
run, supervision, or factory run, so four of the five residue rows would remain.

## Question 5 — would reconciliation preserve the failed proof history?

Yes, by design — and this is worth stating precisely.

- Reconciliation terminalizes via `transition_state()`, which writes a terminal
  state plus `first_terminal_cause` and `terminal_at`. It issues no `DELETE`.
- Token slots move `SELECTED → MANUAL_REVIEW`, not to deletion, so the recorded
  slot-order evidence (slot 1 `yUme…`, slot 2 `CAGt…`) survives intact.
- The zero-state contract counts only non-terminal states and documents that
  "historical terminal evidence is immutable and must never need deletion to
  authorize a new bounded proof."
- The primary forensic record lives outside the database and is untouched by any
  reconciliation: `application-marker.json`, `git-provenance-manifest.json`,
  `wrapper-terminal.json`, `child-terminal.json`, `child-stderr.txt` under the
  consumed application root, plus `terminal-summary.json` and the pre-campaign
  backup under the run directory.

Caveat: the mutable `campaign_state` / `run_state` / `cycle_state` /
`token_state` / `supervision_state` columns are overwritten in place, so the
literal strings `RUNNING`/`PLANNED`/`SELECTED`/`ACTIVE` observed today are not
themselves preserved. This audit document and the immutable artifacts above are
the durable record of the pre-reconciliation shape.

## Question 6 — exact bounded mutation a later cleanup lane would require

Scoped strictly to execution `20260814T172224Z-490856f405bf`:

1. `printer_memory_factory_campaign_cycles` — `…-cycle`: `PLANNED` → terminal,
   with `first_terminal_cause` and `terminal_at`.
2. `printer_memory_factory_campaign_token_slots` — `slot-…-cycle-1` and
   `slot-…-cycle-2`: `SELECTED` → `MANUAL_REVIEW`.
3. `printer_memory_factory_campaign_runs` — `…-campaign-run`: `RUNNING` →
   terminal.
4. `printer_memory_factory_campaigns` — `…-campaign`: `RUNNING` → terminal.
5. `printer_memory_factory_campaign_supervision` — `…-supervision`: `ACTIVE` →
   terminal, setting `terminal_status`, `first_terminal_cause`,
   `cleanup_completed_at`, `lease_released_at`.
6. `printer_memory_factory_runs` — `ed0fa279-38e6-401b-8b34-0a9531a9c720`:
   `RUNNING` → `SAFE_STOPPED` with `stop_reason` and `finished_at`.
7. Filesystem: release
   `/Users/Dtwo1/PrinterOperations/v2-9-8/20260814T172224Z-490856f405bf/campaign.lease.lock`.

Explicitly **not** required: no change to `printer_scheduler_jobs` (all terminal,
no locks), no change to `printer_memory_factory_campaign_scheduler_work` (all
terminal), no row deletion anywhere, no migration, no schema change, no new
Scheduler work, no Source Governor interaction, no backup restore.

The terminal cause should carry the true first cause,
`FourTokenFactoryAdapterError: cycle terminal reconciliation requires a fresh
transaction`, rather than a synthesized cleanup reason.

## Question 7 — does a new software defect remain after the slot-order/rollback repair?

The two repaired defects are confirmed present and closed in this lineage: the
Cycle-1 authoritative-slot reload before `_plan_opening_jobs()`, and the
`conn.rollback()` on the outer factory exception boundary
(`one_command_15m_factory.py:7900`). Neither is re-opened here.

**One residual gap is identified, distinct from both.**

`finalize_four_token_shared_terminal()` accepts exactly two admitted shapes:

- `TWO_CYCLE_COMPLETION` — cycle ordinals `[1, 2]`, both terminal;
- `ONE_CYCLE_HONEST_NO_ADMISSION` — cycle ordinal `[1]` **plus** exactly one
  `printer_pre_admission_discovery_attempts` row with
  `proposed_cycle_ordinal = 2` in a terminal no-admission state
  (`NO_PAIR`/`BLOCKED`/`FAILED`/`CANCELLED`), non-empty `first_terminal_cause`,
  and null `consumed_cycle_id`.

Any other shape raises
`shared terminal requires exact admitted-cycle ownership` or
`one-cycle shared terminal requires exact terminal no-admission evidence`.

This residue is a third shape: **one admitted cycle and zero pre-admission
attempt rows**, because the run died in `CAMPAIGN_PRE_LIFECYCLE` before cycle-2
pre-admission was ever attempted. Phase B would therefore raise, leaving the
campaign, run, supervision, and factory run non-terminal — which is precisely the
residue shape observed.

Because the trigger is *any* early Cycle-1 failure and not specifically the
repaired slot-order fault, a future separately authorized proof that fails early
for an unrelated reason (for example source unavailability) would reproduce the
same unreconciled residue.

Test coverage confirms the gap is untested rather than deliberately excluded:
`ONE_CYCLE_HONEST_NO_ADMISSION` appears in exactly one test
(`tests/test_v2_9_8b_four_token_factory_terminal_integration.py:285`), and that
case constructs a `NO_PAIR` attempt row. No test exercises the zero-attempt-row
shape.

Classification: `SUSPECTED_COMMITTED_CODE_DEFECT`, established by static reading
of the current code and by the observed row shape, **not** by execution. This
audit deliberately ran no tests and wrote no code. A later lane must reproduce it
offline with a focused RED test before any repair is accepted.

## Production repair required?

Yes — but not in this lane, and not to the already-repaired slot-order/rollback
code.

A later lane must decide between two options and prove it offline:

1. extend `finalize_four_token_shared_terminal()` with an explicit third
   admitted shape for a pre-admission-phase failure carrying zero cycle-2
   attempt evidence; or
2. add a bounded, operator-approved, execution-scoped terminal-reconciliation
   entrypoint that composes the existing owners against an abandoned execution
   with no live process and an expired lease.

Option 1 also fixes the recurrence risk for future proofs; option 2 only cleans
up existing residue. They are not mutually exclusive, and option 1 should be
treated as the primary repair.

## Safest next lane

`V2-9.8B Four-Token Shared-Terminal Pre-Admission-Phase Shape Audit & Repair
Design` — a static audit/design lane that:

- confirms the Phase B shape gap with a focused offline RED test;
- decides between the two repair options above;
- leaves the authoritative database untouched.

Database cleanup must follow the repair, not precede it. Fresh authorization
preparation must follow both, because any reconciliation changes the
authoritative DB identity and would invalidate an authorization bound to today's
sha256.

Do not clean the database, create an authorization, or run the proof on the basis
of this audit.

## Money-usefulness contribution

Prevents a second scarce one-shot four-token proof from being consumed on a
residue that the current code cannot close, and identifies a recurrence path that
would otherwise strand every future early-failing proof in the same state.
Establishing that the residue is abandoned rather than live also rules out the
most expensive failure mode — cleaning up underneath a running Printer.

## What this lane improves

- Re-establishes the residue evidence from the correct post-repair lineage
  instead of inheriting a stale-branch interpretation.
- Proves all five rows belong to one consumed execution, with no cross-execution
  contamination.
- Proves no live campaign, cycle, run, Scheduler, lease, or process ownership
  remains.
- Establishes that no existing operator-reachable path can close the residue, and
  says exactly why for each candidate.
- Specifies the exact bounded mutation a cleanup lane would need, table by table.
- Identifies a residual shared-terminal shape gap that survives the completed
  slot-order/rollback repair.

## What remains locked

Four-token proof execution, reuse of any consumed authorization, fresh
authorization creation, database cleanup or reconciliation, six-token proof and
capacity advancement, 12h/24h activation, source fetching and discovery, memory
generation, Scheduler work creation, retrieval, paper decisions, BUY/SELL/HOLD,
positions, trade events, paper audits, PnL, wallets, private keys, signing, live
execution, real funds, paid APIs, scoring/ranking/confidence/weighted logic,
embeddings, and vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- The Phase B shape gap is a static-analysis finding. If a focused offline
  reproduction fails to confirm it, the repair scope must be re-derived rather
  than implemented on this document's authority alone.
- Any cleanup changes the authoritative DB sha256, so authorization creation must
  strictly follow cleanup. Preparing authority first would waste it.
- The expired lease and stale lock file are safe today only because no process is
  alive; a cleanup lane must re-verify liveness immediately before mutating, not
  rely on this audit's snapshot.
- Terminalizing overwrites mutable state columns. The pre-reconciliation shape
  survives only in this document and in the immutable operator-run artifacts, so
  those artifacts must not be deleted.
- `recover-orphan` remains pinned to a single historical execution. Widening it
  generically would be a capability change, not a cleanup, and must not be done
  casually to close this residue.
- The residue was produced by pre-repair lineage `aa5ab488…`. Its existence is
  not evidence about whether the repaired code works; only a future separately
  authorized proof can establish that.
- Rereadiness verdict
  `V2_9_8B_FOUR_TOKEN_SLOT_ORDER_ROLLBACK_POST_REPAIR_REREADINESS_PASS_READY_FOR_FRESH_AUTHORIZATION`
  was a static code review and did not inspect authoritative DB zero state. It
  must not be read as clearing this residue.
