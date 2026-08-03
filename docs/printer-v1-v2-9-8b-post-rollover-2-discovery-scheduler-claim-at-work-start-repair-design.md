# Printer V1 V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start Repair Design

Date: 2026-08-03

Linear: successor to `DTW-24`

Lane:
`V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start Repair Design`

Lane type: design/specification only.

Starting branch:
`agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit`

Starting HEAD (full SHA):
`869027f2cbb7d42e535fc2dff87da83009c294aa`

Parent audit:
`docs/printer-v1-v2-9-8b-post-rollover-2-discovery-scheduler-claim-coverage-blocker-audit.md`

Parent audit verdict:
`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_COVERAGE_BLOCKER_ROOT_CAUSE_CONFIRMED`

Accepted root-cause classification:
`COMMITTED_CODE_DEFECT`

Accepted production repair HEAD (token-slot projection; separate prior lane):
`089eb38651874d9b3ec4a4ce04600d45ea401b05`

Consumed authorization (permanently non-reusable):
`V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`

This design does not authorize implementation, proof execution, provider contact,
authoritative or disposable DB mutation, wrapper use, operational execution,
memory generation, retrieval, decisions, positions, trades, audits, PnL, longer
windows, or a fresh authorization.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_AT_WORK_START_REPAIR_DESIGN_PASS`

The smallest safe repair is:

**At discovery work creation, after the linked Scheduler job is enqueued (or
exactly rebound on lawful replay) and before discovery work is marked RUNNING or
any governed work proceeds, the Combined Discovery Executor claims that exact
linked job through the committed Central Scheduler owner `claim_due_job`.**

Exact required order:

```text
enqueue (or exact lawful job rebind)
  -> exact claim_due_job(job_id=<linked id>)
  -> discovery work row RUNNING linked to that job
  -> governed / in-process discovery work
  -> parity terminal via complete_job / fail_job / cancel_job
```

No synthetic ledger claim, raw Scheduler SQL, accounting weakening, claim-and-ignore
behavior, next-due selection, or terminal-time-only claim is approved.

## 2. Source-stack and evidence alignment

This design follows the active Printer V1 source stack:

- `AGENTS.md`
- `docs/printer-v1-clean-master-spec.md`
- `docs/printer-v1-post-rc-build-order.md`
- `docs/printer-v1-memory-factory-guide.md`
- `docs/printer-v1-current-state-memory-growth-audit.md`
- `docs/printer-v1-memory-growth-build-order-v2.md`
- `docs/printer-v1-python-builder-guide.md`

Lane evidence (root cause closed; not reopened):

- `docs/printer-v1-v2-9-8b-post-rollover-2-discovery-scheduler-claim-coverage-blocker-audit.md`

Direct owners inspected for this design (static, read-only):

- `src/printer_v1/scheduler/scheduler.py` — `enqueue_job`, `claim_due_job`,
  `complete_job`, `fail_job`, `cancel_job`, observer emission
- `src/printer_v1/scheduler/contracts.py` — `LockResult`
- `src/printer_v1/discovery/combined_executor.py` — `_create_work`,
  `_terminalize_work`, intake work creation
- `src/printer_v1/discovery/scheduler_parity.py` — terminal parity owner
- `src/printer_v1/discovery/persistence.py` — `insert_discovery_work`
- `src/printer_v1/sources/campaign_six_unit_accounting.py` — transition coverage
- `src/printer_v1/operator_cli/campaign_full_run_accounting.py` — acceptance gate
- `src/printer_v1/operator_cli/operational_memory_factory_command.py` — public
  observer wiring
- lifecycle claim reference path in `one_command_15m_factory.py`
- exact public composition and full-run transition tests named by the audit

## 3. Accepted defect (closed)

Discovery `DISCOVERY_REFRESH` jobs are real Central Scheduler rows. The Combined
Discovery Executor:

1. enqueues them;
2. marks linked `printer_discovery_work` as `RUNNING` while the Scheduler job
   remains `PENDING`;
3. executes work synchronously in-process;
4. terminalizes through `terminalize_scheduler_job_for_work` →
   `complete_job` / `fail_job` / `cancel_job`.

Full-run accounting correctly requires for every non-`CANCELLED` observed job:

```text
SCHEDULER_ENQUEUE + SCHEDULER_CLAIM + SCHEDULER_TERMINAL
```

Missing claim is a committed code defect, not an accounting false positive and
not a composition-test artifact.

## 4. Exact design decision

### 4.1 Canonical claim owner

**Canonical owner:** `CombinedDiscoveryExecutor._create_work` in
`src/printer_v1/discovery/combined_executor.py`.

Rationale:

- It is the sole production creator of discovery `DISCOVERY_REFRESH` work rows and
  their linked Scheduler jobs on the operational path.
- It already owns enqueue and discovery-work insertion order.
- It is the earliest point at which the linked `job_id` is known and before
  governed work begins.
- Parity (`scheduler_parity.py`) remains the terminal owner only; it must not
  become a late claim forger.

Optional narrow helper (approved shape only):

- A private helper such as `_claim_linked_discovery_scheduler_job(...)` colocated
  in `combined_executor.py`, or a discovery-local helper that **only** wraps
  equality checks + `claim_due_job` + fail-closed mapping.
- The helper must not invent transitions, rewrite job status via SQL, or select
  jobs by due-order.

### 4.2 Exact ordering

For every discovery work unit that will execute:

```text
1. enqueue_job(...) -> job_id
   or lawful exact rebind of an existing active job_id for the same work name/kind
2. claim_due_job(connection, job_id=job_id, lock_owner=<deterministic>, now=...)
   must return LockResult.ACQUIRED
3. post-claim equality checks (section 6)
4. insert_discovery_work(..., scheduler_job_id=job_id, work_state="RUNNING", ...)
5. return work_id and proceed with governed / in-process work
6. later: _terminalize_work / reconcile_discovery_work_jobs
   -> terminalize_scheduler_job_for_work
   -> complete_job | fail_job | cancel_job
```

Hard rule:

- Discovery work must **not** be inserted or advanced to `RUNNING` until the exact
  claim is acquired.
- Governed source requests and discovery lane logic must **not** run before claim.

### 4.3 Why current `claim_due_job` is sufficient for exact claim

`claim_due_job` is **job-id exact**, not “next due job”:

```text
claim_due_job(db_or_connection, *, job_id: int, lock_owner: str, now=None)
  SELECT * FROM printer_scheduler_jobs WHERE id = ?
  # due/status/lock gates on that row only
  UPDATE ... WHERE id = ?
  _observe("SCHEDULER_CLAIM", scheduler_job_id=job_id, ...)
```

Therefore, when discovery passes the linked `job_id` returned from enqueue (or the
exact rebound id), ordinary due-job ordering **cannot** claim an unrelated pending
job. `list_due_jobs` / `select_next_jobs` are not part of this repair path and
must not be introduced for discovery claim.

Claim success still requires, for that exact row:

- row exists;
- not already `RUNNING` and not already locked;
- status is `PENDING` or `COOLDOWN`;
- `scheduled_for <= now`.

Discovery currently enqueues with `scheduled_for` equal to the discovery
evaluation clock, so a newly enqueued job is due at claim time when the same
clock is passed to `claim_due_job`. Implementation must pass the same authoritative
discovery `now` used for enqueue, not a wall-clock that can race the fixture clock.

### 4.4 Narrow design if claim is unavailable

No claim-and-ignore. No claim-any-due-job fallback. No broad Scheduler rewrite.

If `claim_due_job` does not return `ACQUIRED` for the exact linked job:

1. do not insert discovery work as `RUNNING`;
2. do not start governed work for that unit;
3. fail closed with a typed discovery fault (section 7);
4. ensure any already-enqueued job for this failed unit is terminalized through
   the committed Scheduler owner so residue does not remain active/locked
   (normally `cancel_job` or `fail_job` per section 8 — never raw SQL).

Duplicate-active rebind path (existing `_create_work` behavior that reuses the
latest job with the same `job_name`/`job_kind` when enqueue returns no id):

- Rebind is allowed only when the rebound row is the exact intended discovery job
  for this work name/batch and is still claimable (`PENDING`/`COOLDOWN`, unlocked,
  due).
- After rebind, the same exact `claim_due_job(job_id=rebound_id)` and equality
  checks apply.
- If the rebound job is already locked by another owner, already terminal, not
  due, or not the intended name/kind, fail closed. Do not claim a different job.

## 5. Deterministic `lock_owner` identity

### 5.1 Required identity

`lock_owner` must be deterministic, non-empty, and tied to the discovery
batch/work/job owner — not a random worker string and not a lifecycle factory
owner.

Canonical form (approved):

```text
discovery-work:{discovery_work_id}
```

where current production discovery work ids already are:

```text
work:{work_type}:{discovery_batch_id}
```

Examples:

```text
discovery-work:work:DISCOVERY_IDENTITY_MERGE:discovery-batch:<campaign>:<run>:<cycle>
discovery-work:work:DISCOVERY_UNIFORM_SELECTION:discovery-batch:<campaign>:<run>:<cycle>
```

### 5.2 Identity properties

| Property | Requirement |
| --- | --- |
| Determinism | Same campaign/run/cycle/batch/work_type → same lock_owner |
| Scope | Unique per discovery work unit |
| Owner meaning | Identifies Combined Discovery Executor work unit, not factory step worker |
| Stability | Known before claim; derived from the same `work_id` string that will be inserted |
| Observability | Appears on durable `printer_scheduler_jobs.lock_owner` after claim and on the natural `SCHEDULER_CLAIM` observer event |

Optional diagnostic suffix is **not** approved if it reduces determinism or
equality. Keep the single canonical form above unless a later design amends it.

## 6. Required equality checks after claim

Immediately after `claim_due_job` returns `ACQUIRED`, and before inserting
discovery work as `RUNNING`, re-read the Scheduler row and require all of:

| Check | Exact requirement |
| --- | --- |
| Identity | `job.id == claimed_job_id == intended linked job_id` |
| Kind | `job.job_kind == DISCOVERY_REFRESH` |
| Name | `job.job_name == f"{work_type}:{discovery_batch_id}"` |
| Status | `job.status == RUNNING` |
| Lock owner | `job.lock_owner == discovery-work:{discovery_work_id}` |
| Lock fields | `job.locked_at is not None` and `job.started_at is not None` |
| Link readiness | discovery work insert will store the same `scheduler_job_id` |

After `insert_discovery_work`:

| Check | Exact requirement |
| --- | --- |
| Link | `printer_discovery_work.scheduler_job_id == job.id` |
| Work state | `printer_discovery_work.work_state == RUNNING` |
| Work id | equals the precomputed `discovery_work_id` used in `lock_owner` |
| Batch/campaign/run/cycle | match the command/fixture identities for this unit |

Any mismatch fails closed (section 7). No silent repair, no alternate job
selection, no stripping of lock fields.

## 7. Fail-closed behavior when claim is not acquired

Map Scheduler results and local mismatches to fail-closed discovery faults.
Suggested stable cause tokens (implementation may place them under
`CombinedDiscoveryError` detail strings; names are design-frozen intent):

| Condition | Fail-closed cause intent | Side effects before raise/return |
| --- | --- | --- |
| Enqueue fails and no lawful rebind | `SCHEDULER_JOB_CREATE_FAILED` (existing family) | no work row |
| Exact claim returns `NOT_FOUND` | `DISCOVERY_SCHEDULER_CLAIM_NOT_FOUND` | terminalize enqueued job if still active (`cancel` or `fail`) |
| Exact claim returns `NOT_DUE` | `DISCOVERY_SCHEDULER_CLAIM_NOT_DUE` | same residue rule |
| Exact claim returns `ALREADY_LOCKED` | `DISCOVERY_SCHEDULER_CLAIM_ALREADY_OWNED` | do not steal lock; residue handling only if this unit created an unclaimed PENDING job that is still free — never cancel another owner's RUNNING job |
| Claim returns non-`ACQUIRED` other/unexpected | `DISCOVERY_SCHEDULER_CLAIM_NOT_ACQUIRED` | residue rule |
| Post-claim equality mismatch | `DISCOVERY_SCHEDULER_CLAIM_IDENTITY_MISMATCH` | fail closed; do not proceed; terminalize only if this unit still owns/claim-created the active unclaimed residue path safely |
| Work insert would bind a different job id | `DISCOVERY_SCHEDULER_JOB_LINK_MISMATCH` | fail closed |

Rules:

- Never proceed to governed work without `ACQUIRED` + equality pass.
- Never call `claim_due_job` on a different job after a failed exact claim.
- Never inject a synthetic `SCHEDULER_CLAIM` observation.
- Never update `printer_scheduler_jobs` with raw SQL.

## 8. State handling matrix

| Stage | Durable expectation | On failure / next action |
| --- | --- | --- |
| After enqueue, before claim | Scheduler job `PENDING`, unlocked; no discovery work `RUNNING` yet | Claim exact job. If claim fails: fail closed; terminalize the still-active unit job via Scheduler owner (`cancel_job` preferred for not-started unit) so residue is not left `PENDING` |
| After claim, before discovery work RUNNING | Scheduler job `RUNNING` with exact `lock_owner` / `locked_at` / `started_at`; no work row yet or not RUNNING | Insert work as `RUNNING` linked to same job. If insert/equality fails: terminalize claimed job via `fail_job` or `cancel_job` through parity/owner helpers; do not leave RUNNING+locked residue |
| During governed work | Discovery work `RUNNING`; Scheduler job `RUNNING` claimed by discovery lock_owner | Lane failures call `_terminalize_work` / reconcile with `FAILED`/`CANCELLED` as today; parity drives `fail_job`/`cancel_job` |
| Normal success | `_terminalize_work(..., "SUCCEEDED", ...)` → `complete_job` | Scheduler `SUCCEEDED`; locks cleared; natural `SCHEDULER_TERMINAL` |
| Explicit cancellation of work | work → `CANCELLED` / abandoned cause → parity `cancel_job` | Scheduler `CANCELLED`; claim not required by accounting for that terminal; if the job was claimed earlier, cancel still clears lock through owner |
| Batch failure / reconciliation | `reconcile_discovery_work_jobs` abandons active work and terminalizes linked jobs | Uses existing parity owner only; must not re-claim; already-terminal jobs remain immutable |
| Repeated terminalization / cleanup | parity returns `None` when job already terminal | Idempotent; first terminal cause preserved; unified cleanup `cancel_job` only for still-active/locked residue |

### 8.1 Pure cancel exemption preserved

Accounting continues to exempt `CANCELLED` terminals from requiring
`SCHEDULER_CLAIM`. Implementation must:

- not invent claims solely to decorate cancel residue;
- not weaken the non-cancel claim requirement;
- still claim all discovery work units that actually execute (success or fail).

A unit that fails **before** claim and is cancelled from `PENDING` remains
claim-exempt under accounting. That is lawful only for not-started units; it is
not a substitute for claim on executed work.

## 9. Terminal owners, locks, idempotency, observers

### 9.1 Preserve existing terminal owners

| Terminal path | Owner | Continues to be used |
| --- | --- | --- |
| Success | `complete_job` via `terminalize_scheduler_job_for_work` | Yes |
| Failure | `fail_job(..., max_retries=0)` via parity | Yes |
| Cancel / abandoned / skipped mapping | `cancel_job` via parity / cleanup | Yes |

No new terminal writer. No unowned `UPDATE printer_scheduler_jobs`.

### 9.2 Lock ownership lifecycle

```text
claim_due_job  -> sets lock_owner, locked_at, started_at, status=RUNNING
complete_job   -> clears lock fields, status=SUCCEEDED, emits SCHEDULER_TERMINAL
fail_job       -> clears lock fields on terminal fail path, emits SCHEDULER_TERMINAL
cancel_job     -> clears lock fields, status=CANCELLED, emits SCHEDULER_TERMINAL
```

These natural `_observe(...)` emissions are the only approved claim/terminal
evidence sources for action-local coverage.

### 9.3 Idempotency

- Parity already skips already-terminal jobs.
- Implementation must not claim an already-terminal job to “repair” coverage.
- Implementation must not double-claim; second claim on same job returns
  `ALREADY_LOCKED` and must fail closed if encountered unexpectedly mid-create.
- Cleanup may cancel remaining active/locked residue; cancel of already-terminal
  is a no-op path at higher cleanup layers / parity skip semantics as today.

### 9.4 Observer path unchanged in contract

Public coordinator continues to install
`set_scheduler_operation_observer` around the operational owner. Real
`SCHEDULER_CLAIM` from `claim_due_job` will appear in `scheduler_runtime_records`
and be copied into the action-local ledger for accountable discovery job IDs
exactly as ENQUEUE/TERMINAL already are. No observer patch that invents CLAIM is
approved.

## 10. Explicitly rejected alternatives

| Alternative | Why rejected |
| --- | --- |
| Synthetic action-local `SCHEDULER_CLAIM` without `claim_due_job` | Forges evidence; audit already rejected |
| Raw SQL status/lock updates | Bypasses Central Scheduler owner and natural observer |
| Weakening `scheduler_transition_coverage` to drop claim for discovery successes | Hides real unclaimed execution; accounting law stays intact |
| Terminal-time-only claim immediately before `complete_job` | Work already executed while unclaimed; weaker ownership truth; not the approved work-start boundary |
| Claim via `select_next_jobs` / due-order dequeue | Can touch unrelated pending jobs; forbidden |
| Claim-and-ignore on mismatch | Violates exact link equality |
| Broad Scheduler rewrite or new claim primitive | Out of scope; existing exact-id claim is sufficient |
| Changing lifecycle factory claim behavior | Out of scope; working path must remain unchanged |
| Reusing consumed authorization or issuing a new one in this lane | Forbidden |

## 11. Future implementation boundary

### 11.1 Expected implementation files (later lane only)

Primary:

- `src/printer_v1/discovery/combined_executor.py`
  - reorder `_create_work` to claim before work RUNNING;
  - deterministic lock_owner;
  - equality checks;
  - fail-closed causes;
  - residue terminalization on pre-work claim failure.

Possibly (only if needed for clarity, still narrow):

- a tiny helper in the same discovery package that wraps exact claim + equality;
- focused tests under `tests/`.

### 11.2 Files that must remain untouched by the repair intent

Unless a later explicit design amends them:

- `src/printer_v1/sources/campaign_six_unit_accounting.py` claim coverage law
- `src/printer_v1/operator_cli/campaign_full_run_accounting.py` acceptance checks
  that require coverage completeness
- lifecycle claim loop in `one_command_15m_factory.py`
- public observer installation contract in `operational_memory_factory_command.py`
  (consume natural events only)
- Source Governor owners
- migrations / schema
- authorization / wrapper / marker law
- financial, retrieval, decision, longer-window surfaces

`scheduler.py` itself should remain untouched if exact-id `claim_due_job` already
satisfies the contract (current static reading: it does). A Scheduler change is
not approved by this design unless implementation discovers a genuine primitive
bug that prevents exact-id claim of a newly enqueued due job; that would require
a separate fail-closed design amendment.

### 11.3 Import surface

Implementation should call the existing committed owner:

```text
from printer_v1.scheduler.scheduler import claim_due_job
# or package export equivalent
```

and continue using parity terminal helpers already imported by the executor.

## 12. Focused future tests and offline proof

Later sequence only:

```text
implementation -> focused offline proof -> closeout
```

before any fresh authorization or live attempt.

### 12.1 Focused unit/integration tests (future)

Must prove:

1. Every non-cancelled discovery job created through `_create_work` shows durable
   transitions in order: `SCHEDULER_ENQUEUE` → `SCHEDULER_CLAIM` →
   `SCHEDULER_TERMINAL`.
2. After claim and before/at work start, durable row has:
   - `status=RUNNING`
   - `lock_owner=discovery-work:{discovery_work_id}`
   - `locked_at` and `started_at` present
3. Claim targets only the linked job id; no unrelated pending Scheduler job becomes
   `RUNNING`/`locked` as a side effect of discovery claim.
4. Pure cancellation / abandon-from-never-started remains claim-exempt under
   accounting when terminal state is `CANCELLED`.
5. Claim omission (negative probe) fails closed and does not reach successful
   governed completion for that unit.
6. Identity mismatch after claim fails closed.
7. `ALREADY_LOCKED` / `NOT_DUE` / `NOT_FOUND` fail closed with residue rules.
8. Parity + cleanup leave zero active/locked discovery residue after terminal
   batch paths.
9. Lifecycle snapshot/window-close claim behavior remains unchanged
   (factory still claims its own jobs; no discovery claim steals them).
10. Repeated terminalization remains idempotent.

### 12.2 Offline exact public composition proof (future)

Disposable Migration-050 only; frozen transports; no network; no authoritative DB.

Must prove:

- exact public coordinator → authoritative owner → origin driver → one-command
  factory composition still runs;
- two `WINDOW_15M` closes succeed;
- zero active/locked residue;
- discovery accountable jobs have real ENQUEUE/CLAIM/TERMINAL with no injected
  events;
- `scheduler_transition_coverage.complete is True`;
- campaign acceptance no longer fails solely on discovery claim coverage;
- integrity/FK clean;
- protected capability tables remain zero for locked financial surfaces.

### 12.3 Explicit non-proofs

- synthetic claim injection;
- provider/live source contact;
- reusing `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`;
- live ordinary campaign;
- 1h+ windows.

## 13. Money-usefulness contribution

Without real discovery claim-at-work-start, Printer can complete two disposable
`WINDOW_15M` closes and still fail honest full-run acceptance. That blocks trust
in the restored operational factory as a clean-memory growth machine. This design
restores the missing ownership boundary so later offline proof can honestly pass
transition coverage without forging evidence or unlocking financial behavior.

## 14. What the repair improves

- Real Scheduler claim ownership for synchronous discovery work units.
- Natural observer evidence for `SCHEDULER_CLAIM` on discovery jobs.
- Alignment between discovery execution model and full-run transition coverage.
- Fail-closed exact-id claim with deterministic lock ownership.
- Preservation of V2-9.7E.47 terminal parity and cancel exemption semantics.
- Clear implementation/proof boundary that does not weaken accounting law.

## 15. What it still does not unlock

- implementation in this design lane;
- live or disposable campaign execution in this lane;
- fresh authorization or reuse of the consumed authorization;
- clean-memory creation beyond existing locked policy;
- retrieval activation;
- paper decisions;
- BUY / SELL / HOLD;
- paper positions, trades, audits, PnL;
- wallets, private keys, live execution;
- paid APIs;
- scoring / ranking / confidence / weighted logic;
- embeddings / vectors;
- 1h / 4h / 12h / 24h production main windows;
- N2/N7 candidate-acquisition operational prerequisite restoration;
- Source Governor or Central Scheduler architecture rewrites.

## 16. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Detail |
| --- | --- |
| Functionality risk | If claim uses a different clock than enqueue `scheduled_for`, `NOT_DUE` can fail closed spuriously; implementation must share the discovery `now` |
| Functionality risk | Duplicate-active rebind must not claim an already-owned or terminal job; equality gates are mandatory |
| Setback risk | Terminal-only claim would green coverage while lying about work-start ownership; explicitly rejected |
| Efficiency blocker | Broad Scheduler rewrite is unnecessary; exact-id claim already exists |
| Efficiency blocker | Broad full-suite runs are not required for design; later implementation should stay focused |
| Residue risk | Claim-then-crash before work insert must terminalize the claimed job or cleanup will see RUNNING/locked residue |
| Observer risk | Forged ledger claims would desynchronize action-local evidence from durable rows; rejected |
| Lifecycle isolation risk | Discovery lock_owner namespace must remain distinct from factory `v2_4:{run_id}` owners so cross-family claim confusion is detectable |
| Proof risk | Fixture tests that inject CLAIM must not be treated as production proof; exact public composition remains required later |

## 17. Later required sequence

```text
1. implementation (narrow, design-conformant)
2. focused offline proof (unit/parity + exact public composition)
3. independent closeout
4. only then: fresh readiness / fresh exact-HEAD authorization / one live attempt
```

No step may reuse `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`.
No live attempt is authorized by this design.

## 18. Implementation sketch (non-normative pseudo-order)

Illustrative only; not code authorization:

```text
job_name = f"{work_type}:{discovery_batch_id}"
work_id = f"work:{work_type}:{discovery_batch_id}"
lock_owner = f"discovery-work:{work_id}"

result, job_id = enqueue_job(... scheduled_for=discovery_now ...)
if job_id is None:
    job_id = exact_lawful_rebind_or_fail(...)

claim = claim_due_job(connection, job_id=job_id, lock_owner=lock_owner, now=discovery_now)
if claim != LockResult.ACQUIRED:
    residue_terminalize_unstarted(job_id)
    raise CombinedDiscoveryError(<claim cause>)

assert_post_claim_equality(job_id, job_name, lock_owner, work_type)

insert_discovery_work(..., discovery_work_id=work_id, scheduler_job_id=job_id,
                      work_state="RUNNING", ...)
assert_work_link_equality(...)
return work_id
```

## 19. Design checklist (acceptance of this document)

| # | Requirement | Design decision |
| --- | ---: | --- |
| 1 | Exact canonical claim owner | `CombinedDiscoveryExecutor._create_work` (+ optional narrow helper) |
| 2 | Exact order | enqueue → exact claim → work RUNNING → governed work → terminal |
| 3 | Exact-id claim guarantee | existing `claim_due_job(job_id=...)` is job-id exact |
| 4 | No unrelated due-job claim | forbid `select_next_jobs`/due-order; fail closed on non-ACQUIRED |
| 5 | Deterministic lock_owner | `discovery-work:{discovery_work_id}` |
| 6 | Equality checks | job id/kind/name/status/lock fields and work link |
| 7 | Fail closed | typed causes; no proceed; no steal; residue via Scheduler owners |
| 8 | State matrix | covered for pre-claim, post-claim, governed, success, cancel, reconcile, repeat |
| 9 | Terminal owners | preserve complete/fail/cancel + natural observers |
| 10 | Rejected forgeries | synthetic claim, raw SQL, accounting weaken, terminal-only claim |
| 11 | File boundary | primarily `combined_executor.py`; accounting/lifecycle law untouched |
| 12 | Future proof | ENQUEUE→CLAIM→TERMINAL, durable lock fields, public composition, coverage complete |
| 13–16 | Value, locks, risks, sequence | documented above |

## 20. Final statement

The approved repair is a work-start exact claim of the linked discovery Scheduler
job by the Combined Discovery Executor through the existing Central Scheduler
`claim_due_job` owner, using a deterministic discovery work lock identity, strict
post-claim equality, fail-closed non-acquisition semantics, and unchanged parity
terminalization. This produces real `SCHEDULER_CLAIM` evidence for non-cancelled
discovery jobs without synthetic events, without claiming unrelated jobs, and
without weakening accounting.

Verdict:

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_AT_WORK_START_REPAIR_DESIGN_PASS`
