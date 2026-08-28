# Printer V1 V2-9.8B — Post-Consumption Interrupted Four-Token Residual Reconciliation / Lease-Failure Cleanup Design

Date: 2026-08-28

Lane: **DESIGN / SPECIFICATION ONLY**

Verdict:

```text
V2_9_8B_POST_CONSUMPTION_INTERRUPTED_FOUR_TOKEN_RESIDUAL_RECONCILIATION_LEASE_FAILURE_CLEANUP_DESIGN_AMENDMENT_PASS
IMPLEMENTATION APPROVAL REQUIRED
```

Operator-review amendment (same day): closes three withheld-approval
ambiguities without changing Architecture B, interruption semantics, Scheduler
ownership direction, exact-residue binding, migration stance, or permanent
locks. Amended sections: **§4** (hard renewal deadline + exact DB/file order),
**§5.3–§5.5** (atomic/replay interrupt cleanup + single call site), plus
dependent updates in **§4.6 / §7 / §9 / §10 / §11 / §13 / §15 / §18**.

This design does **not** authorize implementation, residue mutation, lease
release, Scheduler cancellation, Printer execution, provider/RPC/WebSocket
contact, Central Scheduler runtime, authorization preparation/application,
campaign resume/retry/restart, or remote-host work.

---

## 1. Authority / baseline

Active source stack (in order):

1. `AGENTS.md`
2. `docs/printer-v1-clean-master-spec.md`
3. `docs/printer-v1-post-rc-build-order.md`
4. `docs/printer-v1-memory-factory-guide.md`
5. `docs/printer-v1-current-state-memory-growth-audit.md`
6. `docs/printer-v1-memory-growth-build-order-v2.md`
7. `CURRENT_HANDOFF.md` (assistance only; currently stale — see §17)

Accepted forensic input (do not re-run):

- In-repo forensic report:
  `operator-runs/v2-9-8b-consumed-one-shot-forensic-audit/forensic-audit.md`
- Application package:
  `/Users/Dtwo1/PrinterOperations/v2-9-8/four-token-standard-four-hour-one-shot-applications/V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5/`
- Execution directory:
  `/Users/Dtwo1/PrinterOperations/v2-9-8/20260828T220832Z-704f53472011/`

Re-verified at design time (read-only; no mutation):

| Item | Value |
|---|---|
| Repo HEAD | `1d75715ca38c14294f58303b3a5cdb785ed4ad4c` |
| Authoritative DB | `data/printer_v1.sqlite3` |
| Authoritative DB SHA-256 | `c90376b9e26d0f2953a8d9b2fd5fee01d80ac4984510113e595fd1ccc3d9033d` |
| Integrity / FK | `ok` / 0 |
| Journal mode | `delete` |
| Consumed auth | `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5` (non-reusable) |
| Execution | `20260828T220832Z-704f53472011` |
| Lease file | still present under execution directory |

---

## 2. Forensic facts accepted as input

Primary classification: `EXPECTED_RECOVERABLE_INTERRUPTED_STATE`  
Secondary product gap: `CLEANUP_OR_RESIDUE_RECONCILIATION_DEFECT`

Accepted durable chain:

1. Cycle 1 admitted 2 tokens; `WINDOW_15M` lifecycle started; 19 snapshot works succeeded.
2. Legitimate concurrent SQLite/source-response writing occurred.
3. Lease renewal failed with durable `LEASE_RENEWAL_SQLITE_LOCKED` /
   `SQLITE_LOCK_CONTENTION`.
4. Cycle 1 safely terminalized/blocked with that cause.
5. Cycle-2 cooperative acquisition attempt remained `RUNNING`.
6. Scheduler job `2808` (`PRE_ADMISSION_DISCOVERY_SELECTION`) remained
   `PENDING`, never claimed/executed; linked only through
   `printer_pre_admission_discovery_attempts.scheduler_job_id`, **not** through
   `printer_memory_factory_campaign_scheduler_work`.
7. Exact terminal no-admission evidence did **not** exist.
8. `finalize_four_token_shared_terminal` correctly refused to fabricate that
   evidence (`ONE_CYCLE_HONEST_NO_ADMISSION` predicates fail on `RUNNING`).
9. Shared terminalizer therefore never ran → cleanup/lease release incomplete.
10. Current residue: supervision `ACTIVE`, lease present, campaign/run/factory
    `RUNNING`, attempt `RUNNING`, job `2808` `PENDING`.
11. No Printer/Governor/Scheduler process is running. DB integrity healthy.
12. Historical recovery owners are hard-bound to other executions and must not
    be stretched onto this residue.

Do **not** redesign the fail-closed refusal to invent a no-admission certificate.

---

## 3. Problem decomposition

Two distinct product gaps:

| Gap | Class | Owner surface |
|---|---|---|
| G1 | Short legitimate SQLite writer collision can still end lease renewal immediately after existing busy budget | `renew_campaign_lease` / `_begin_immediate` in `campaign_supervision.py` |
| G2 | After lease-failure Cycle-1 terminalization, four-token Phase B has no sanctioned interruption path for a still-open Cycle-2 attempt; shared cleanup never runs; attempt-linked Scheduler jobs are invisible to `cleanup_campaign_supervision` | `four_token_factory_adapter.py`, factory finally path, `cleanup_campaign_supervision`, `reconcile_campaign_terminal` |

Chicken-and-egg in current production order:

```text
RUNNING Cycle-2 attempt
  -> finalize requires zero active_pre_admission_attempts + sanctioned shape
  -> raises before shared_terminalizer
  -> reconcile_campaign_terminal (which already knows how to CANCEL open attempts
     and cancel their jobs via campaign_scoped_job_ids) never runs
  -> cleanup_campaign_supervision never runs / would not see job 2808 anyway
```

`reconcile_campaign_terminal` already contains the attempt/job cancellation
logic for `PLANNED`/`RUNNING` (and exact `PAIR_READY` parent revoke). The defect
is that Phase B never reaches it for this residue shape, and supervision cleanup
ownership does not independently discover attempt-linked jobs.

---

## 4. Lease-contention design (Question 1)

### 4.1 Exact current failure mechanism

`renew_campaign_lease` today:

1. Loads ACTIVE supervision from the DB ledger.
2. Advances the on-disk lease file **first**.
3. Opens a writer connection with `timeout=2.0s` and
   `PRAGMA busy_timeout=2000`.
4. Calls `_begin_immediate` — up to `SQLITE_BUSY_MAX_ATTEMPTS=5` with
   `SQLITE_BUSY_RETRY_SECONDS=0.05` between attempts (~10.2s theoretical inner
   busy budget that is **not** capped by any renewal-level deadline).
5. Compare-and-swaps supervision heartbeat/expiry in SQLite.
6. On SQLite lock/busy → sanitized
   `LEASE_RENEWAL_SQLITE_LOCKED` / `SQLITE_LOCK_CONTENTION`, durable heartbeat
   failure row, **no** renewal-thread cleanup.
7. If step 2 succeeded and step 5 failed, the lease file can already be ahead of
   the DB ledger (partial renewal skew).

This incident is **not** the historical V2-9.8B.20 long-I/O-held-transaction
class (already repaired by releasing writes before source I/O). It is a short
legitimate concurrent Printer write (source-response/snapshot path) colliding
with renewal. Inner busy handling still left a residual campaign-ending failure.

### 4.2 Selected repair — hard monotonic renewal deadline

**Bounded same-renewal SQLite-contention treatment** inside
`renew_campaign_lease` only, under one fixed renewal-level deadline.

#### Constants (single unambiguous maximum set)

| Constant | Value | Role |
|---|---:|---|
| `LEASE_CONTENTION_WALL_CLOCK_SECONDS` | `15.0` | Hard maximum elapsed time for one `renew_campaign_lease` call |
| `LEASE_CONTENTION_REMAINING_SAFETY_SECONDS` | `15.0` | Minimum remaining lease lifetime required before starting any further blocking attempt |
| `LEASE_CONTENTION_OUTER_MAX_ATTEMPTS` | `3` | Includes the first try; hard cap on outer loops |
| `LEASE_CONTENTION_OUTER_SLEEP_SECONDS` | `0.25` | Sleep between outer attempts only when the full sleep fits before the deadline |
| `SQLITE_BUSY_TIMEOUT_SECONDS` | `2.0` (existing) | **Ceiling** per inner `BEGIN IMMEDIATE` wait, never an addition beyond the renewal deadline |
| `SQLITE_BUSY_MAX_ATTEMPTS` | `5` (existing) | Inner attempt cap; each attempt still deadline-clamped |
| `SQLITE_BUSY_RETRY_SECONDS` | `0.05` (existing) | Inner sleep only when the full sleep fits before the deadline |
| `LEASE_CONTENTION_MIN_BLOCK_SECONDS` | `0.001` | If remaining deadline is below this, do not begin another blocking wait |

#### Monotonic-deadline contract

At the start of one `renew_campaign_lease` call:

```text
t0 = time.monotonic()
renewal_deadline = t0 + LEASE_CONTENTION_WALL_CLOCK_SECONDS   # exactly one fixed deadline
```

Wall-clock / ISO `attempted_at` remains evidence only. **All deadline math uses
`time.monotonic()` against `renewal_deadline`.**

Before **every** blocking action (outer loop entry, inner `_begin_immediate`
attempt, outer sleep, inner sleep):

1. `remaining_deadline = renewal_deadline - time.monotonic()`
2. If `remaining_deadline < LEASE_CONTENTION_MIN_BLOCK_SECONDS` → fail closed
   immediately with `LEASE_RENEWAL_SQLITE_LOCKED` / `SQLITE_LOCK_CONTENTION`
   **without** beginning another blocking SQLite wait or sleep.
3. Re-read ACTIVE ownership + `lease_expires_at` from the DB ledger.
4. If lease already expired → `LEASE_RENEWAL_LEASE_EXPIRED` (no contention retry).
5. `remaining_lease = lease_expires_at - now_utc`
6. If `remaining_lease <= LEASE_CONTENTION_REMAINING_SAFETY_SECONDS` → fail
   closed with `LEASE_RENEWAL_SQLITE_LOCKED` **without** beginning another
   blocking attempt (insufficient safe lease lifetime for further contention
   waiting).
7. Let `planned_block = min(SQLITE_BUSY_TIMEOUT_SECONDS, remaining_deadline)`.
8. If `remaining_lease - planned_block <= LEASE_CONTENTION_REMAINING_SAFETY_SECONDS`
   → fail closed without beginning that blocking attempt (safety margin
   rechecked against the time needed for this further attempt).
9. Configure this connection/attempt so its SQLite busy wait cannot exceed
   `planned_block` (set connection `timeout` / `PRAGMA busy_timeout` to
   `floor(planned_block * 1000)` ms for this attempt only).
10. Outer attempt count must remain `< LEASE_CONTENTION_OUTER_MAX_ATTEMPTS`
    before starting another outer try after a lock failure.
11. Outer/inner sleeps execute only when
    `sleep_duration <= remaining_deadline`; otherwise fail closed without
    sleeping.

**Hard guarantee:** no inner SQLite wait/retry may extend past
`renewal_deadline`. A retry that would begin before second 15 but whose inner
busy budget would overrun second 15 is **not** started; the call fails closed
instead. Elapsed monotonic time for one renewal call must be
`<= 15.0s + negligible scheduling overhead` (test tolerance ≤ 250ms on CI).

This is **not** “increase SQLite timeout” and **not** unbounded retry. The
existing 2.0s busy value is only a per-attempt ceiling inside the remaining
deadline.

On success: return `renewal_confirmed=True` with
`contention_outer_attempts` / `contention_wait_ms` observability fields.

### 4.3 Exact DB / lease-file renewal ordering (authoritative choice)

#### Authority

| Artifact | Authority |
|---|---|
| `printer_memory_factory_campaign_supervision.heartbeat_at` / `lease_expires_at` | **Authoritative lease ledger** (monotonic CAS source of truth) |
| On-disk lease lock file | **Exclusive ownership mirror** (identity fields must match supervision; heartbeat/expiry must not claim a renewal the ledger has not committed) |

`renewal_confirmed=True` is returned only when **both** the DB ledger and the
lease file carry the same new `heartbeat_at` / `lease_expires_at` under exact
ownership identity.

#### Selected mutation order (mandatory)

```text
1. Read-only load + ownership/expiry/monotonicity prechecks (unchanged intent)
2. BEGIN IMMEDIATE under the deadline-clamped busy contract
3. DB compare-and-swap UPDATE of heartbeat_at / lease_expires_at / updated_at
   WHERE supervision ACTIVE and prior heartbeat/expiry match expected priors
4. COMMIT DB
5. Advance lease file via existing _replace_lock to the exact committed
   heartbeat/expiry (identity fields unchanged)
6. Read-back: DB row and lease file must agree on heartbeat/expiry + identity
7. Only then return renewal_confirmed=True
```

**Rejected:** current file-first-then-DB order for renewal; “either order” /
implementation-detail wording; leaving partial-file-ahead-of-DB as acceptable
confirmed renewal.

Acquire may keep its existing file-then-DB create pattern with file unlink on
DB failure. This amendment changes **renewal** only.

#### Partial-failure matrix

| Step outcome | Required behavior |
|---|---|
| DB CAS fails (lock/busy) inside deadline | Rollback; no file mutation; outer contention treatment may continue only under §4.2 predicates |
| DB CAS fails (ownership/rowcount≠1/expired/non-ACTIVE) | Rollback; no file mutation; fail closed with the matching existing cause; **no** contention retry |
| DB CAS commits; file replace succeeds; read-back agrees | `renewal_confirmed=True` |
| DB CAS commits; file replace fails transiently | Retry file replace only within existing `LEASE_REPLACE_MAX_ATTEMPTS` **and** only while `remaining_deadline` still permits; do not open new SQLite waits for this sync |
| DB CAS commits; file still disagrees after replace bound | **Do not** roll back the committed DB ledger (SQLite commit is durable). Return `renewal_confirmed=False` with `LEASE_RENEWAL_UNCONFIRMED`, durable heartbeat-failure evidence, and explicit partial flags `db_ledger_advanced=true`, `lease_file_synced=false`. Heartbeat thread performs **no** cleanup. |
| Process crash after DB commit before file sync | Later renew/inspect treats DB ledger as authoritative priors; file must be reconciled forward to DB heartbeat/expiry only when exact ownership identities still match and supervision is still ACTIVE. Until file matches DB, observers must treat renewal as **unconfirmed/partial**, never as a confirmed renewal. |

#### How later observers distinguish confirmed vs partial renewal

Confirmed renewal requires **all** of:

- supervision row ACTIVE (or later terminalized by the main coordinator);
- lease file identity fields exact-match supervision;
- `file.heartbeat_at == db.heartbeat_at` and
  `file.lease_expires_at == db.lease_expires_at`;
- the renew call returned `renewal_confirmed=True` (when that return is
  available).

Partial renewal is any state where the DB ledger advanced but the file does not
yet match, or a failure return carried `db_ledger_advanced=true` and
`lease_file_synced=false`. Partial must never be reported as
`renewal_confirmed=True`.

Durable terminal cause when agreement cannot be established after DB advance:
existing `LEASE_RENEWAL_UNCONFIRMED` (not a new migration subtype). When no DB
advance occurred and contention bound exhausted:
`LEASE_RENEWAL_SQLITE_LOCKED`.

### 4.4 Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Generic “retry SQLite until it works” | Unbounded; hides genuine lock storms; violates fail-closed |
| Busy-timeout increase alone | Explicitly rejected by V2-9.8B.20 closeout as sole fix; does not define renewal-level deadline |
| Soft 15s check only before starting another full ~10.2s inner budget | Allows overrun past the intended hard maximum — forbidden by this amendment |
| Lengthen lease / slow heartbeat | Masks contention; weakens expiry safety |
| Suppress / reclassify `LEASE_RENEWAL_SQLITE_LOCKED` | Hides real renewal failure |
| Background renewer loop / second authority | Concurrent-authority weakening; Scheduler/Governor bypass risk |
| Campaign retry/resume on lock | Forbidden; authorization one-shot |
| Re-open long write transactions across I/O | Regresses V2-9.8B.20 |
| File-first renewal with optional restore as coder choice | Leaves safety contract undecided; creates file-ahead-of-ledger skew |
| Returning `renewal_confirmed=True` after DB-only advance | Lies about file/ledger agreement |

### 4.5 Genuine renewal failure after contention treatment

Fail closed with existing sanitized causes when any of:

- hard monotonic deadline insufficient for another safe blocking attempt;
- outer attempt cap exhausted;
- lease safety margin insufficient for the planned block;
- lease expired;
- ownership mismatch / non-ACTIVE;
- DB advanced but lease-file agreement cannot be established →
  `LEASE_RENEWAL_UNCONFIRMED`.

No duplicate campaign work. No cleanup from the heartbeat thread.

### 4.6 Observability / evidence

- Success: `contention_outer_attempts`, `contention_wait_ms`, matched
  heartbeat/expiry.
- Failure: existing immutable first heartbeat-failure row; return dict may carry
  `contention_outer_attempts`, `db_ledger_advanced`, `lease_file_synced`.
  Extra fields must not require a migration if the failure table schema is
  closed; keep them in the return dict / lease-file failure mirror.

### 4.7 Focused lease tests (temp DB)

1. Brief legitimate writer holds SQLite → renewal waits only within the hard
   deadline → succeeds when lock clears; `renewal_confirmed=True` only with
   DB/file agreement.
2. Prolonged contention → `LEASE_RENEWAL_SQLITE_LOCKED`; measured monotonic
   elapsed `<= 15.0 + 0.250s`.
3. Remaining deadline `<` next planned busy clamp → fail closed **without**
   starting that blocking attempt (prove no overrun path).
4. Remaining lease lifetime at/under safety margin, or safety margin minus
   planned block insufficient → fail closed without further blocking wait.
5. Expired lease → `LEASE_RENEWAL_LEASE_EXPIRED`; no contention retry.
6. Ownership mismatch → immediate fail-closed (no contention retry).
7. DB commit succeeds, forced file-replace failure →
   `renewal_confirmed=False`, `LEASE_RENEWAL_UNCONFIRMED`,
   `db_ledger_advanced=true`, `lease_file_synced=false`; DB and file disagree
   until a later exact ownership file sync.
8. DB CAS failure before commit → lease file unchanged from pre-call content.
9. No duplicate campaign/scheduler work from renewal retries.
10. Regression: genuine non-contention lease failure semantics unchanged.

---

## 5. Interrupted Cycle-2 cleanup design (Question 2)

### 5.1 Interruption semantics (no fabricated no-admission)

Do **not** convert the open attempt into fake `NO_PAIR`, successful
no-admission, completed acquisition certificate, provider failure, or market
scarcity.

Reuse existing legal attempt state `CANCELLED` with an explicit interruption
cause prefix:

```text
PARENT_CAMPAIGN_INTERRUPTED:<parent_first_terminal_cause>
```

For this incident class:

```text
PARENT_CAMPAIGN_INTERRUPTED:LEASE_RENEWAL_SQLITE_LOCKED
```

Meaning:

- parent campaign/Cycle-1 already owns a durable terminal cause;
- later-cycle cooperative acquisition was still nonterminal;
- acquisition is revoked because the parent campaign terminally stopped;
- attempt evidence rows remain exactly as written (migration-062 append-only);
- this is **cancellation due to parent interruption**, not honest no-pair.

### 5.2 New Phase-B admitted shape

Add one sanctioned one-cycle shape beside the existing two:

| Shape | Meaning |
|---|---|
| `ONE_CYCLE_HONEST_NO_ADMISSION` | Unchanged acquisition-terminal truth (`NO_PAIR`/`BLOCKED`/`FAILED`, or non-interruption `CANCELLED` if already used historically) |
| `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT` | Unchanged |
| **`ONE_CYCLE_CAMPAIGN_INTERRUPTED_OPEN_ATTEMPT`** | Exactly one admitted Cycle-1 terminal row; exactly one proposed-Cycle-2 attempt now `CANCELLED` with cause `PARENT_CAMPAIGN_INTERRUPTED:<C1_cause>`; `consumed_cycle_id IS NULL`; parent C1 cause non-empty and equals the suffix; zero active attempt/job residue after preflight reconciliation |

Narrow `ONE_CYCLE_HONEST_NO_ADMISSION` so causes matching
`PARENT_CAMPAIGN_INTERRUPTED:` **cannot** be classified as honest no-admission.

Preserve the existing raise:

```text
one-cycle shared terminal requires exact terminal no-admission evidence
```

for the case where an attempt is still nonterminal / lacks interruption
preflight. Do not weaken that guard into silent fabrication.

### 5.3 Ordered ownership transition (production path)

New narrow owner:

`reconcile_parent_interrupted_open_pre_admission_attempts(...)`

#### Single authoritative production call site (mandatory)

**Only** inside `finalize_four_token_shared_terminal`, immediately before
Phase-B admitted-shape and active-work predicates.

Forbidden:

- a second factory “Phase A2” caller beside finalize;
- silent coder choice between finalize-internal vs
  `one_command_15m_factory` finally-path;
- relying on `reconcile_campaign_terminal` alone to discover this residue
  shape (it remains defense-in-depth only after Phase B invokes the shared
  terminalizer).

Exact recovery (§8) must call this **same** owner (or finalize’s public
preflight helper), not a forked transition sequence.

#### Happy-path ordered steps

For `Cycle-1 terminal interrupted` + open later-cycle attempt:

| Step | Target | Action |
|---:|---|---|
| 1–2 | Open attempt + its Scheduler job | **One SQLite transaction** on one connection: `BEGIN IMMEDIATE` → `terminalize_pre_admission_attempt(..., CANCELLED, PARENT_CAMPAIGN_INTERRUPTED:<C1_cause>)` → `cancel_job(connection, job_id=attempt.scheduler_job_id)` → `COMMIT` (see §5.5). Never `claim_due_job`. Never execute the job. |
| 3 | Attempt evidence / checkpoints | Leave append-only rows unchanged; no new provider/opportunity rows; no certificate fabrication |
| 4 | Campaign Scheduler / discovery ownership | Existing `reconcile_campaign_terminal` + extended `cleanup_campaign_supervision` (see §6) |
| 5 | Factory run | Existing shared terminalizer → `SAFE_STOPPED` / preserve `stop_reason=LEASE_RENEWAL_SQLITE_LOCKED` |
| 6 | Campaign / run / cycles | Existing shared terminal / cleanup; Cycle-1 cause preserved; no new Cycle-2 admission |
| 7 | Supervision | `cleanup_campaign_supervision` → `TERMINAL` |
| 8 | Lease | Exact lease release through existing cleanup |
| 9 | Terminal report/evidence | Record admitted_shape=`ONE_CYCLE_CAMPAIGN_INTERRUPTED_OPEN_ATTEMPT`; distinguish from `NO_PAIR` / duration exhaustion |

Hard constraints for this path:

- zero provider calls;
- zero new acquisition work;
- no Scheduler claim/execution;
- no lifecycle restart;
- no token/memory creation;
- no fabricated no-admission certificate;
- preserve Cycle-1 evidence exactly;
- preserve original `LEASE_RENEWAL_SQLITE_LOCKED` as campaign/Cycle-1 first cause;
- never overwrite a conflicting terminal attempt cause;
- never cancel unrelated campaigns’ jobs;
- fail closed on unexpected attempt state (`PAIR_READY` uses existing exact
  parent-revoke owner only; `CONSUMED`/unknown → raise).

### 5.4 Shared-terminalizer ordering companion

Current `_four_token_shared_terminalizer` runs
`cleanup_campaign_supervision` **before** `reconcile_campaign_terminal`.
Because finalize currently demands zero active attempts before invoke, the
reconcile attempt-cancel path is unreachable for this residue.

With §5.3’s finalize-internal preflight selected, production repair requires:

1. parent-interrupt reconciliation inside finalize **before** active checks
   (authoritative), **and**
2. extend cleanup ownership (§6), **and**
3. reorder shared terminalizer to
   `reconcile_campaign_terminal` → `cleanup_campaign_supervision` so any
   residual attempt/job graph known to reconcile is cleared before supervision
   cleanup asserts zero owned work.

Item 3 is a required companion once item 1 lands; it is not an alternate
interrupt call site.

### 5.5 Partial interrupt-cleanup replay / idempotency

Existing owners already permit one-connection composition:

- `terminalize_pre_admission_attempt(connection, ...)` mutates the attempt row;
- `cancel_job(connection, ...)` updates the job without committing when given an
  open connection.

Therefore the **primary** production transition for state A is atomic
(attempt + job in one transaction). Replay must still be safe if a prior crash,
failed companion path, or defense-in-depth caller left a partial state.

Let `EXPECTED_CAUSE = PARENT_CAMPAIGN_INTERRUPTED:<C1_first_terminal_cause>`
where `<C1_first_terminal_cause>` is the exact non-empty Cycle-1 durable cause.

| State | Attempt | Job | Required owner action | Result |
|---|---|---|---|---|
| **A** | `RUNNING` or `PLANNED` | `PENDING` / `RUNNING` / `COOLDOWN` / locked | Single transaction: terminalize → `CANCELLED` + `EXPECTED_CAUSE`; `cancel_job` on `attempt.scheduler_job_id`; commit | Both terminal; continue Phase B |
| **B** | `CANCELLED` with **exact** `EXPECTED_CAUSE` | `PENDING` / `RUNNING` / `COOLDOWN` / locked | Do **not** rewrite attempt cause/state. Cancel only the owned job (same connection transaction OK). | Job terminal; attempt unchanged; continue |
| **C** | `RUNNING` or `PLANNED` | already `CANCELLED` (and unlocked) | Terminalize attempt only to `CANCELLED` + `EXPECTED_CAUSE`. Job cancel is idempotent no-op if invoked. | Attempt terminal; job remains cancelled; continue |
| **D** | `CANCELLED` with **exact** `EXPECTED_CAUSE` | already `CANCELLED` (and unlocked) | Pure no-op success (`idempotent_replay=true`) | Continue Phase B |

Fail closed (no mutation of the conflicting fact) when:

- attempt is `CANCELLED` (or other terminal) with a **different** non-empty
  cause than `EXPECTED_CAUSE`;
- attempt is `CONSUMED`, `PAIR_READY` (unless routed through the existing exact
  PAIR_READY parent-revoke owner for that distinct shape), `NO_PAIR`,
  `BLOCKED`, or `FAILED` under this interrupt owner;
- `scheduler_job_id` missing / ownership mismatch / job belongs to another
  campaign;
- job is active but not the attempt’s linked id.

Never on any of A–D:

- claim or execute the job;
- fabricate no-admission / `NO_PAIR` evidence;
- overwrite a conflicting terminal attempt cause;
- cancel unrelated Scheduler work;
- contact providers;
- resume/retry/restart the campaign.

---

## 6. Scheduler ownership solution

### Future production (no hard-coded job `2808`)

Extend `cleanup_campaign_supervision` job discovery/cancellation and
post-cleanup active-work checks to include jobs linked by:

```text
printer_pre_admission_discovery_attempts
  WHERE campaign_id=? AND campaign_run_id=?
    AND scheduler_job_id IS NOT NULL
```

for attempts in active or just-cancelled cleanup scope, mirroring
`campaign_active_work.campaign_scoped_job_ids["pre_admission_attempt_jobs"]`.

Prefer provenance/ownership repair over special-case job-ID cancellation.

Optional defense-in-depth: when creating
`create_scheduled_pre_admission_attempt`, also insert a
`printer_memory_factory_campaign_scheduler_work` row bound to the same
`scheduler_job_id` **only if** an existing campaign-work contract can represent
pre-admission work without lying about cycle FK (proposed cycle may not exist
yet). If cycle FK makes that unsafe, **do not** force a fake work row; the
attempt table remains the canonical ownership link and cleanup must read it.
Design default: **attempt-table ownership is sufficient**; do not add a
migration solely to duplicate linkage.

### Exact consumed recovery

May bind exact job `2808` as a predicate, not as the cancellation mechanism:
verify `attempt.scheduler_job_id == 2808` then cancel through the same
attempt-ownership cancel path used in production.

---

## 7. Existing vs new owner responsibilities

| Owner | Responsibility |
|---|---|
| `renew_campaign_lease` / deadline-clamped `_begin_immediate` | G1 hard monotonic contention deadline; **DB-then-file** renewal order; confirmed only on DB/file agreement |
| `terminalize_pre_admission_attempt` | Existing state transition to `CANCELLED` |
| `cancel_job` | Existing Scheduler cancel API (same-connection, non-committing) |
| **new** `reconcile_parent_interrupted_open_pre_admission_attempts` | Sole parent-interrupt preflight; atomic A transition + B/C/D replay table |
| `finalize_four_token_shared_terminal` | **Only** production caller of the interrupt preflight; new admitted shape; honest-shape narrowing |
| `reconcile_campaign_terminal` | Existing broader terminal graph; defense-in-depth only after Phase B |
| `cleanup_campaign_supervision` | Extend job ownership discovery to attempt-linked jobs; lease release |
| `_four_token_shared_terminalizer` | Compose reconcile **then** cleanup once |
| **new** exact recovery module | Bound to this consumed execution only; reuses the same interrupt owner |

Do **not** broaden:

- `operational_campaign_recovery.py`
- `scheduler_residue_reconciliation.py`
- `heartbeat_terminalization_recovery.py`

Those remain immutable historical/exact owners for other executions.

---

## 8. Current exact-residue recovery design

### Architecture decision: **B (two bounded components)**

**A** (one production path only) is insufficient for the live residue because:

- the authorization is permanently consumed;
- resume/retry/restart are forbidden;
- no Printer process may be relaunched under that auth;
- historical recovery owners are not bound to this execution.

Therefore:

1. **Production-path repair** for future campaigns (G1 + G2 + Scheduler
   ownership).
2. **Exact-execution reconciliation owner** for
   `20260828T220832Z-704f53472011` after implementation proof.

### Exact recovery binding predicates (fail closed if any mismatch)

| Predicate | Expected |
|---|---|
| Authorization | `V2_9_8B_FOUR_TOKEN_STD4H_AUTH_20260828T211924Z_5fcb1bf5` consumed/non-reusable |
| Execution / campaign / run / supervision / owner | `...704f53472011...` exact IDs |
| Factory run | `42ef6217-3932-4846-948d-e2103fd34309` |
| Attempt | `pre-admission:...704f53472011...:c0002` state `RUNNING` |
| Scheduler job | `2808` `PENDING` `PRE_ADMISSION_DISCOVERY_SELECTION` |
| Cycle 1 | `TERMINAL_BLOCKED` / cause `LEASE_RENEWAL_SQLITE_LOCKED` |
| Campaign/run/factory/supervision | `RUNNING` / `RUNNING` / `RUNNING`+stop_reason lease-locked / `ACTIVE` |
| DB SHA at recovery start | must equal operator-approved expected SHA (re-hash immediately before apply; design-time SHA `c90376b9…d9033d`) |
| Processes | no Printer/Governor/Scheduler |
| Sidecars | no `-wal/-shm/-journal` |
| Integrity/FK | `ok` / 0 |
| Lease path | exact execution lease file present |

Recovery procedure (future only; **not executed in this lane**):

1. Design PASS (this document).
2. Explicit implementation approval.
3. Implement production owners + exact recovery module.
4. Focused temp-DB / disposable-copy proof.
5. Independent implementation closeout.
6. Explicit operator approval for authoritative reconciliation.
7. Fresh verified backup + disposable restore rehearsal.
8. Run exact recovery owner once against authoritative DB.
9. Prove: attempt `CANCELLED` with interruption cause; job `2808` `CANCELLED`;
   campaign/run/factory/supervision terminal; lease released; zero active work;
   Cycle-1 evidence unchanged; integrity/FK clean; no provider/Scheduler
   runtime; auth still non-reusable.

No ad-hoc SQL. No manual lease deletion outside the recovery owner.

---

## 9. State-transition table

| From | Event | To | Cause / notes |
|---|---|---|---|
| Lease renew + short SQLite busy | Hard deadline contention treatment; lock clears; DB then file agree | Renewed ACTIVE | `renewal_confirmed=True` |
| Lease renew + deadline/safety/attempt bound exhausted | Fail closed without further blocking wait | Heartbeat failure recorded | `LEASE_RENEWAL_SQLITE_LOCKED` |
| Lease renew + DB committed, file sync impossible | Fail closed | Partial ledger advance | `LEASE_RENEWAL_UNCONFIRMED` |
| Interrupt state A | Atomic attempt+job txn | Both `CANCELLED` | `PARENT_CAMPAIGN_INTERRUPTED:<C1_cause>` |
| Interrupt state B/C/D | Monotonic replay (§5.5) | Both terminal / no-op | Never overwrite conflicting cause |
| One-cycle + interrupted cancelled attempt | Phase B inside finalize | Shape `ONE_CYCLE_CAMPAIGN_INTERRUPTED_OPEN_ATTEMPT` | Then shared terminalizer |
| Supervision `ACTIVE` + cleanup | Existing cleanup | `TERMINAL` + lease released | First campaign cause preserved |
| Unexpected attempt state / SHA drift / process live | Any recovery/cleanup | Fail closed | No partial authority |

---

## 10. Fail-closed predicates

1. Never invent `NO_PAIR` / admission certificate / opportunity completion.
2. Never claim or execute pending Scheduler work during interrupt cleanup.
3. Never contact providers during interrupt cleanup or exact recovery.
4. Never resume/retry/restart the consumed authorization/campaign.
5. Never classify `PARENT_CAMPAIGN_INTERRUPTED:*` as
   `ONE_CYCLE_HONEST_NO_ADMISSION`.
6. Never cancel unrelated campaigns’ Scheduler jobs.
7. Exact recovery refuses any DB SHA / ID / state predicate mismatch.
8. Lease renewal never retries non-lock failures or expired leases, and never
   starts a blocking wait that would exceed the hard monotonic deadline or the
   lease safety margin minus planned block time.
9. `renewal_confirmed=True` requires DB/file agreement; DB-only advance is
   partial/`LEASE_RENEWAL_UNCONFIRMED`.
10. Interrupt cleanup never overwrites a conflicting terminal attempt cause.
11. Heartbeat thread still must not perform terminal cleanup.
12. Permanent V1 locks unchanged (§14).

---

## 11. Implementation file scope (proposed)

Production (call-site choice resolved — **no** factory Phase A2 fork):

- `src/printer_v1/operator_cli/campaign_supervision.py` — hard monotonic
  contention deadline; DB-then-file renewal; cleanup attempt-job ownership
- `src/printer_v1/operator_cli/four_token_factory_adapter.py` —
  `reconcile_parent_interrupted_open_pre_admission_attempts` invoked only from
  `finalize_four_token_shared_terminal`; new admitted shape; honest-shape
  narrowing; A–D replay
- `src/printer_v1/operator_cli/pre_admission_discovery_attempt.py` — optional
  cause-prefix constant / thin helper only; no second call site
- `src/printer_v1/operator_cli/operational_memory_factory_command.py` —
  required shared-terminalizer reorder (reconcile then cleanup)
- `src/printer_v1/operator_cli/one_command_15m_factory.py` — **out of interrupt
  call-site scope**; unchanged for parent-interrupt preflight

Exact recovery (new; hard-bound):

- `src/printer_v1/operator_cli/interrupted_four_token_704f53472011_residue_reconciliation.py`
  (name may follow existing recovery naming; must encode exact execution binding
  and reuse the same interrupt owner)

Tests (new/focused):

- `tests/test_v2_9_8b_lease_renewal_sqlite_contention_bound.py` — includes hard
  deadline non-overrun + DB/file partial-failure boundaries
- `tests/test_v2_9_8b_interrupted_cycle2_parent_interrupt_cleanup.py` — includes
  atomic A and replay B/C/D
- `tests/test_v2_9_8b_interrupted_cycle2_cleanup_regressions.py`
- disposable proof for exact recovery owner against a copy of the residue shape

Docs:

- this design;
- later implementation/closeout docs only after approval.

---

## 12. DB / schema impact

**No migration required** for the truthful state:

- attempt state `CANCELLED` already exists;
- cause text can carry `PARENT_CAMPAIGN_INTERRUPTED:...`;
- Scheduler `CANCELLED` already exists;
- supervision/campaign/run terminalization already exists.

Add schema/vocabulary only if implementation proves cause-length or check
constraints reject the prefix form — not expected. Avoid migrations unless
unavoidable.

---

## 13. Bounded test / proof matrix

### Lease contention

| # | Condition | Required result |
|---:|---|---|
| L1 | Brief legitimate Printer write owns SQLite | Waits only under deadline-clamped busy; succeeds with DB/file agreement |
| L2 | Contention clears inside hard deadline | `renewal_confirmed=True` |
| L3 | Prolonged contention | `LEASE_RENEWAL_SQLITE_LOCKED`; elapsed `<= 15.0 + 0.250s` |
| L4 | Next busy clamp would overrun deadline or safety−block | Fail closed **without** starting that blocking wait |
| L5 | Lease expires | `LEASE_RENEWAL_LEASE_EXPIRED`; no contention retry |
| L6 | Ownership mismatch | Fail closed; no contention retry |
| L7 | DB commits; file replace forced to fail | `LEASE_RENEWAL_UNCONFIRMED`; partial flags; not confirmed |
| L8 | DB CAS fails before commit | Lease file unchanged |
| L9 | Retries create no duplicate campaign/scheduler work | Pass |

### Interrupted Cycle-2 cleanup

Fixture: one admitted Cycle-1; lifecycle started; durable
`LEASE_RENEWAL_SQLITE_LOCKED`; Cycle-2 attempt `RUNNING`; pending cooperative
acquisition Scheduler job linked only via attempt; no terminal no-admission
certificate.

| # | Required result |
|---:|---|
| C1 | Does not fabricate `NO_PAIR` / admission certificate |
| C2 | Zero provider calls |
| C3 | Does not claim/execute pending Scheduler work |
| C4 | State A atomic → attempt `CANCELLED` + exact interruption cause and job `CANCELLED` |
| C5 | States B/C/D replay per §5.5; conflicting cause fail-closed |
| C6 | Job cancelled through attempt ownership (not hard-coded ID in production) |
| C7 | Cycle-1 evidence preserved exactly |
| C8 | Campaign/factory/supervision terminal; lease released |
| C9 | Zero active work for the campaign |
| C10 | Idempotent replay safe |
| C11 | Integrity/FK clean |
| C12 | Only finalize invokes the interrupt owner (no factory duplicate path) |

### Regressions (focused only)

| # | Preserve |
|---:|---|
| R1 | Honest `NO_PAIR` one-cycle shared terminal |
| R2 | Duration exhaustion semantics |
| R3 | Successful two-cycle completion path |
| R4 | Genuine lease failure after contention bound still fail-closed |
| R5 | Existing `ONE_CYCLE_PRE_LIFECYCLE_ZERO_ATTEMPT` |
| R6 | Existing PAIR_READY parent-terminal revoke path |

No giant unrelated suite.

---

## 14. Permanent-lock verification

This repair must not unlock: live trading; wallets/keys/signing/real funds;
paid APIs; scoring/ranking/confidence/weighted logic; embeddings/vectors;
Source Governor bypass; Central Scheduler bypass; dirty-memory
retrieval/decisions; retrieval/financial capability; BUY/SELL/HOLD;
positions/trades/PnL; 12h/24h; 5m as main outcome. Candidate-acquisition
N2/N7/cursor/recovery remain deferred.

---

## 15. Rejected alternatives

| Alternative | Why |
|---|---|
| Treat interruption as `ONE_CYCLE_HONEST_NO_ADMISSION` via bare `CANCELLED` | Semantic lie; conflates cancellation with no-admission success |
| Fabricate no-admission certificate so current Phase B passes | Explicitly forbidden; audit proved evidence does not exist |
| Stretch historical recovery owners onto this execution | Wrong binding; unsafe |
| Ad-hoc SQL / manual lease delete | No owner, no predicates, no idempotent proof |
| Production-only repair without exact recovery | Leaves live residue uncleared under consumed auth |
| Exact-recovery-only without production repair | Future recurrence remains |
| Add migration solely for a new attempt state | Unnecessary; `CANCELLED` + cause prefix is truthful |
| Duplicate hard-coded job-2808 cancellation in production | Ownership gap remains for future IDs |
| Campaign resume under same authorization | Permanent one-shot non-reuse |
| Soft 15s outer check that still allows a full ~10.2s inner overrun | Violates hard renewal deadline |
| File-first renewal / “order is an implementation detail” | Leaves partial-renewal safety undecided |
| Competing factory Phase A2 + finalize interrupt call sites | Split authority; replay/proof ambiguity |

---

## 16. Implementation stop conditions

Stop and return to design/operator review if:

1. implementing the cause prefix requires a schema migration not justified here;
2. `PAIR_READY` open attempt appears in this residue class (different owner);
3. cleanup reorder breaks an existing terminal accounting invariant and cannot
   be proven on temp DB;
4. exact recovery predicates no longer match live residue;
5. any path would contact providers, claim Scheduler work, or reuse the auth;
6. tests can pass only by injecting terminal classifications instead of
   underlying conditions;
7. deadline clamping cannot be proven to prevent inner busy overrun of the
   15.0s hard maximum;
8. DB-then-file renewal cannot establish a confirmed-vs-partial observer rule
   without weakening existing lease ownership law.

---

## 17. Implementation lane split

Ordered sub-lanes after explicit approvals:

1. **Production implementation lane** — G1 hard-deadline lease contention +
   DB-then-file renewal + G2 finalize-only interrupt cleanup/shape + A–D replay
   + cleanup Scheduler ownership + required shared-terminalizer reorder +
   focused temp-DB proofs + closeout.
2. **Exact-residue reconciliation lane** — implement hard-bound recovery owner;
   disposable-copy proof; independent closeout; **separate** operator approval
   before authoritative apply.
3. **Governance synchronization** — update `CURRENT_HANDOFF.md` / AGENTS current
   pointer after closeouts; `CURRENT_HANDOFF.md` is currently stale (still
   describes pre-consumption auth-prep / DB SHA `dececa7c…`) and must not
   authorize execution.

Recommended: do **not** merge sub-lanes 1 and 2 into one approval that also
mutates the authoritative DB. Production code may land first; authoritative
residue apply remains a distinct gated step.

---

## 18. Design verdict

```text
V2_9_8B_POST_CONSUMPTION_INTERRUPTED_FOUR_TOKEN_RESIDUAL_RECONCILIATION_LEASE_FAILURE_CLEANUP_DESIGN_AMENDMENT_PASS
IMPLEMENTATION APPROVAL REQUIRED
```

An implementer can proceed without inventing:

- interruption semantics (`CANCELLED` + `PARENT_CAMPAIGN_INTERRUPTED:<cause>` +
  new admitted shape);
- hard renewal deadline (one monotonic `renewal_deadline = t0+15s`; every inner
  busy/sleep clamped to remaining deadline; safety margin rechecked against
  planned block; no blocking start when unsafe);
- DB/file renewal order (DB CAS commit, then file advance; confirmed only on
  agreement; partial → `LEASE_RENEWAL_UNCONFIRMED`);
- interrupt replay (atomic state A; monotonic B/C/D; conflicting cause
  fail-closed);
- single production call site (`finalize_four_token_shared_terminal` only);
- Scheduler cancellation ownership (attempt-linked discovery in cleanup +
  existing `cancel_job` / reconcile paths);
- terminal-state meaning (interruption ≠ honest no-admission);
- current-residue recovery behavior (exact-ID-bound owner; production owners
  reused; no ad-hoc SQL).

### Exact next permitted action

```text
EXPLICIT IMPLEMENTATION APPROVAL
FOR THE PRODUCTION REPAIR SUB-LANE ONLY
```

Still forbidden until separately approved: authoritative residue apply; lease
release; cancelling job `2808`; mutating the attempt; running Printer;
preparing/applying authorization; providers; Scheduler runtime; remote/VPS work.
