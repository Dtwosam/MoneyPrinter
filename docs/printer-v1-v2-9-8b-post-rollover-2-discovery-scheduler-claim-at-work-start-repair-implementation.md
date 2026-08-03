# Printer V1 V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start Repair Implementation

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start Repair Implementation`

Lane type: implementation and focused deterministic tests only.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_AT_WORK_START_REPAIR_IMPLEMENTATION_PASS`

The Combined Discovery Executor now claims each linked `DISCOVERY_REFRESH`
Scheduler job through the exact-id Central Scheduler owner `claim_due_job` before
discovery work becomes `RUNNING` and before any governed discovery work proceeds.
Natural `SCHEDULER_CLAIM` observer events are emitted. Accounting claim law,
lifecycle factory claim behavior, schema, authorization, and financial locks are
unchanged.

This lane did **not** run the exact public-composition proof.

## 2. Baseline

| Item | Value |
| --- | --- |
| Starting HEAD | `9c69228ca67d7a281799abb043180b051293509c` |
| Starting commit | `Design discovery Scheduler claim-at-work-start repair` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Parent design | `docs/printer-v1-v2-9-8b-post-rollover-2-discovery-scheduler-claim-at-work-start-repair-design.md` |
| Parent audit | `docs/printer-v1-v2-9-8b-post-rollover-2-discovery-scheduler-claim-coverage-blocker-audit.md` |
| Accepted classification | `COMMITTED_CODE_DEFECT` |
| Consumed authorization | `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` (permanently non-reusable) |

Untracked operator-runs evidence directories were preserved and not committed.

## 3. Accepted defect

Discovery `_create_work` enqueued real Scheduler jobs and terminalized them through
parity, but never called `claim_due_job`. Non-cancelled discovery jobs therefore
lacked durable/observed `SCHEDULER_CLAIM` and correctly failed full-run transition
coverage after otherwise successful two-token `WINDOW_15M` closeout.

## 4. Files changed

| File | Role |
| --- | --- |
| `src/printer_v1/discovery/combined_executor.py` | Production claim-at-work-start owner |
| `tests/test_v2_9_8b_discovery_scheduler_claim_at_work_start.py` | Focused claim/order/fail-closed/residue tests |
| `docs/printer-v1-v2-9-8b-post-rollover-2-discovery-scheduler-claim-at-work-start-repair-implementation.md` | This report |

No changes to `scheduler.py`, accounting coverage law, lifecycle factory claim
path, migrations/schema, authorization, Source Governor, or provider contracts.

## 5. Canonical owner

`CombinedDiscoveryExecutor._create_work` in
`src/printer_v1/discovery/combined_executor.py`.

Helpers colocated in the same owner:

- `_require_claimed_discovery_scheduler_identity`
- `_require_discovery_work_link`
- `_terminalize_unstarted_discovery_scheduler_job`

## 6. Exact transition order

For every discovery work unit that will execute:

```text
1. precompute work_id and lock_owner
2. enqueue_job(... DISCOVERY_REFRESH ..., scheduled_for=discovery_now)
   or exact lawful rebind of same job_name/job_kind when still claimable
3. claim_due_job(connection, job_id=<linked id>, lock_owner=..., now=discovery_now)
4. verify claimed Scheduler identity/ownership
5. insert_discovery_work(... work_state="RUNNING", scheduler_job_id=<linked id>)
6. verify discovery-work-to-Scheduler-job linkage
7. return work_id; governed discovery work may proceed
8. later terminalization remains:
   _terminalize_work / reconcile_discovery_work_jobs
     -> terminalize_scheduler_job_for_work
     -> complete_job | fail_job | cancel_job
```

## 7. Claim and lock identity

| Field | Value |
| --- | --- |
| Discovery work id | `work:{work_type}:{discovery_batch_id}` |
| Lock owner | `discovery-work:{discovery_work_id}` |
| Claim primitive | existing exact-id `claim_due_job` |
| Claim clock | same discovery `now` used for enqueue `scheduled_for` |

Post-claim equality requires:

- exact Scheduler job id;
- `job_kind == DISCOVERY_REFRESH`;
- expected job name `{work_type}:{discovery_batch_id}`;
- `status == RUNNING`;
- exact `lock_owner`;
- non-null `locked_at` and `started_at`.

Post-insert equality requires matching work id, batch/campaign/run/cycle,
`scheduler_job_id`, work type, and `work_state == RUNNING`.

## 8. Failure and cleanup behavior

| Condition | Behavior |
| --- | --- |
| Enqueue fails with no lawful rebind | `SCHEDULER_JOB_CREATE_FAILED`; no work |
| Rebind locked / RUNNING owned by another | `DISCOVERY_SCHEDULER_CLAIM_ALREADY_OWNED`; no steal |
| Claim `NOT_FOUND` / `NOT_DUE` / `ALREADY_LOCKED` / other non-ACQUIRED | typed fail-closed; no governed work; cancel only unclaimed unit residue or this unit's claimed job |
| Post-claim identity mismatch | `DISCOVERY_SCHEDULER_CLAIM_IDENTITY_MISMATCH`; cancel this unit's claimed job; no work insert |
| Insert/link failure after claim | `DISCOVERY_SCHEDULER_JOB_LINK_MISMATCH`; cancel claimed job; clear lock; no orphan RUNNING work |
| Normal success/fail/cancel | existing parity terminal owners only |
| Pure cancel of never-started unclaimed job | remains claim-exempt under accounting |
| Repeated terminalization | parity still no-ops already-terminal jobs |

Never:

- claim an alternate due job;
- inject synthetic `SCHEDULER_CLAIM` events;
- raw-update Scheduler status/locks;
- cancel another worker's locked job.

## 9. Focused tests and results

### 9.1 New focused module

`tests/test_v2_9_8b_discovery_scheduler_claim_at_work_start.py`

Covers:

1. ENQUEUE → CLAIM → TERMINAL order on success;
2. durable RUNNING / lock_owner / locked_at / started_at;
3. exact linked claim; unrelated pending job untouched;
4. no work insert before successful claim;
5. NOT_DUE / NOT_FOUND / already-owned / identity mismatch fail closed;
6. post-claim pre-insert failure clears lock and leaves no active residue;
7. success/fail/cancel/reconcile/repeat terminal idempotency;
8. pure cancel without claim remains valid;
9. lifecycle exact-id claim isolation on shared Scheduler primitive;
10. real `NOT_DUE` probe on future-scheduled job.

### 9.2 Verification commands and results

```text
.venv/bin/python -m py_compile \
  src/printer_v1/discovery/combined_executor.py \
  tests/test_v2_9_8b_discovery_scheduler_claim_at_work_start.py
Result: exit 0

.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_discovery_scheduler_claim_at_work_start.py \
  tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py \
  tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py \
  tests/test_phase3_scheduler_resource_governor.py
Result: 82 passed, 30 subtests passed

.venv/bin/python -m pytest -q \
  tests/test_v2_9_8b_full_run_wiring_integration.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py
Result: 30 passed, 6 subtests passed

git diff --check
Result: clean
```

Combined focused totals for this lane: **112 passed, 36 subtests passed**.

### 9.3 Not run

- broad/full pytest;
- exact public composition;
- live/operational discovery;
- Memory Factory operational commands;
- wrappers;
- provider/RPC/WebSocket contact;
- authoritative DB mutation.

No unrelated pre-existing failures were observed in the focused suite above.

## 10. Money-usefulness contribution

Discovery jobs can now emit real claim ownership evidence required by full-run
acceptance. That unblocks the next offline exact-public-composition proof from
being blocked solely by missing `SCHEDULER_CLAIM` after successful two-token
`WINDOW_15M` closeout, without forging accounting events or unlocking financial
behavior.

## 11. What the repair improves

- Real claim-at-work-start for synchronous discovery Scheduler units;
- Natural observer `SCHEDULER_CLAIM` emission;
- Fail-closed exact-id ownership with deterministic lock identity;
- Residue cleanup for pre-work claim failures without stealing foreign locks;
- Preservation of parity terminalization and pure-cancel claim exemption.

## 12. What remains locked

- exact public-composition proof (next lane);
- live ordinary `WINDOW_15M` campaign;
- reuse of `V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z`;
- fresh authorization;
- clean-memory creation beyond existing locks;
- retrieval, paper decisions, BUY/SELL/HOLD;
- positions, trades, audits, PnL;
- wallets/private keys/live execution;
- paid APIs, scoring/ranking/confidence/weights;
- embeddings/vectors;
- 1h+ production main windows;
- accounting claim-law weakening;
- synthetic transition injection.

## 13. Functionality Risks / Setbacks / Efficiency Blockers

| Item | Detail |
| --- | --- |
| Functionality risk | Discovery `now` must remain the claim clock; mismatched wall-clock could produce honest `NOT_DUE` |
| Functionality risk | Duplicate-active rebind remains fail-closed when the rebound job is already owned/terminal |
| Setback risk | Exact public composition still required before readiness/authorization; this lane does not prove it |
| Efficiency | No Scheduler rewrite required; exact-id claim primitive reused |
| Residue | Claim-then-insert-failure path cancels the claimed job; execute-level rollback still undoes uncommitted work |

## 14. Proof still required

Next permitted lane:

```text
V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start Focused Offline Proof
```

Must prove on disposable Migration-050 with frozen transports and no network:

- exact public coordinator → owner → origin driver → factory composition;
- every non-cancelled discovery job ENQUEUE → CLAIM → TERMINAL without injection;
- two `WINDOW_15M` closes;
- zero active/locked residue;
- `scheduler_transition_coverage.complete is True`;
- lifecycle claim behavior unchanged;
- no financial unlock deltas.

Then: independent closeout → only later fresh readiness/authorization/live attempt.

## 15. Next permitted lane

`V2-9.8B Post-Rollover-2 Discovery Scheduler Claim-at-Work-Start Focused Offline Proof`

## 16. Final statement

Implementation follows the approved design boundary exactly: claim the linked
discovery Scheduler job at work start through the committed exact-id claim owner,
verify ownership, mark work RUNNING, preserve parity terminals, and fail closed
without synthetic evidence or scope expansion.

Verdict:

`V2_9_8B_POST_ROLLOVER_2_DISCOVERY_SCHEDULER_CLAIM_AT_WORK_START_REPAIR_IMPLEMENTATION_PASS`
