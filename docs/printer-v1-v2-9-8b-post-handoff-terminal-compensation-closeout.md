# Printer V1 V2-9.8B Post-Handoff Terminal Compensation Closeout

Date: 2026-07-30

Lane: `V2-9.8B Post-Handoff Terminal Compensation Repair`

Verdict:
`V2_9_8B_POST_HANDOFF_TERMINAL_COMPENSATION_PASS`

## Sequence executed

```text
readiness confirmation → final compensation design → implementation
→ frozen disposable-DB proof → closeout
```

## Baseline

- Branch: `master`
- Start HEAD: `e864463472ad8c1db6f171847caac885940445fd`
- Authoritative DB SHA-256 (unchanged, never opened for write):
  `e748ba505cb8c7d67b8feb3a09b97719a0f3560e41dfb9242570cff3157962e6`
- Migration head remains `049`
- No live provider/RPC/WebSocket, campaign, N2/N7, cursor, recovery, retrieval,
  or financial capability was authorized or run. All proof used frozen inputs
  and fresh disposable migration-049 databases only.
- The prior lane's campaign-accounting / terminal-enforcement uncommitted
  changes were preserved (not reset, discarded, stashed, or overwritten).

## Accepted invariant (resolves prior D-1)

```text
after a post-handoff failure:
  zero active, runnable, leased, reusable, or orphan work;
  immutable terminal handoff audit evidence may remain
```

The prior lane sought literal row-zero and was correctly BLOCKED by the
append-only immutable selected-item link that FK-pins the token slots and the
first-15m job. This lane instead **terminalizes** those pinned rows into a
lawful non-runnable state and preserves the immutable links untouched.

## Money-usefulness contribution

Failed campaigns cannot silently resume or duplicate tracking. After any
post-handoff fault the two token slots are terminal (`MANUAL_REVIEW`), their
tracking rows are `SKIPPED`, every first-15m and campaign-scoped Scheduler job is
cancelled, and the cycle/run/campaign are terminalized — so nothing remains for a
scheduler pass, promotion, or re-selection to pick up, while the immutable
handoff audit chain is preserved for review.

## What this repair improves

- The canonical post-handoff compensation owner
  (`origin_lifecycle_campaign._compensate_post_handoff_teardown`) now drives the
  campaign to **zero active work** instead of leaving the pinned handoff active
  and merely reporting it.
- Terminalization is delegated to the single existing authority
  (`reconcile_campaign_terminal` → `transition_state` / `cancel_job` /
  `campaign_active_work_report`); no second cleanup authority was introduced.
- The executor's cycle-scoped first-15m jobs (unreachable by the campaign-scoped
  job scan) are re-cancelled through the immutable link's
  `first_window_15m_scheduler_job_id`, covering the rolled-back in-handoff
  cancellation.
- A deterministic compensation report distinguishes immutable retained evidence,
  terminalized pinned rows, deleted lifecycle residue, and zero remaining active
  work; the owner is idempotent.

## What this repair still does not unlock

- D-2: stages 4–5 (`LIFECYCLE_OBJECT_MATERIALIZATION`,
  `POST_ACTIVATION_STATE_TRANSITION`) are still applied as driver-level
  representative objects/transitions, not faults inside the real
  `run_one_command_15m_factory` runner. Compensation is proven against that
  representative state.
- The selective-1h provider-failure truthfulness defect
  (`test_v2_9_8b_selective_1h_liquidity_evidence_repair.py`, 3 pre-existing
  baseline failures at `e864463`) is untouched.
- No longer-window activation, live providers/RPC/WebSockets/campaign, immutable
  link schema redesign, or N2/N7/cursor/recovery/backfill. No ceiling raised. No
  retrieval, decision, position, trade, audit, or PnL capability.

Both remaining items are reported as blockers for any subsequent operator review.

## Repair (mapped to the lane's 1–10)

| # | Requirement | Resolution |
|---|---|---|
| 1 | Terminalize both surviving slots (lawful non-runnable state) | `reconcile_campaign_terminal` 4a: `SELECTED → MANUAL_REVIEW` per slot |
| 2 | Record exact post-handoff terminal cause per slot | `first_terminal_cause = POST_HANDOFF_<STAGE>`, `terminal_at` set |
| 3 | Terminalize every linked tracking row | slot-linked `QUEUED → SKIPPED` (`MANUAL_REVIEW` action) |
| 4 | Cancel every first-15m job incl. rolled-back cancellations | cycle-scoped via immutable-link job id; `cancel_job` on still-active jobs |
| 5 | Cancel/terminalize other pre-fault lifecycle jobs | `reconcile_campaign_terminal` step 2 (campaign-scoped job scan) |
| 6 | Release/terminalize active leases | `ACTIVE`/`STOPPING → TERMINAL` (`CANCELLED`); zero-row safety net |
| 7 | Delete only deletable lifecycle residue | origin-activated batch + items, run steps, snapshots, lifecycle-event objects |
| 8 | Preserve immutable links + FK-pinned rows | links never updated/deleted; pinned rows terminalized, not removed |
| 9 | Deterministic compensation report | retained / terminalized / deleted / zero-active sections |
| 10 | Idempotent | state-guarded steps; second pass `mutations_this_pass` all zero |

## Exact proof performed

Focused compensation suite
`tests/test_v2_9_8b_post_handoff_terminal_compensation.py` — **12 collected, 12
passed** (5 per-injection terminalization proofs + 5 idempotency proofs + 1
normal-success proof + the unittest harness `runTest` no-op, matching the
established harness convention).

For every one of the five injections
(`LIFECYCLE_SELECTION_BATCH_CREATION`, `EXECUTOR_JOB_CANCELLATION`,
`LIFECYCLE_JOB_REPLANNING`, `LIFECYCLE_OBJECT_MATERIALIZATION`,
`POST_ACTIVATION_STATE_TRANSITION`) on a fresh disposable migration-049 database:

- surviving token slots (2) are terminal and non-runnable; `first_terminal_cause
  == POST_HANDOFF_<STAGE>`; `terminal_at` set; zero slots remain `SELECTED`;
- zero linked tracking rows remain `QUEUED`/`ACTIVE`/`PAUSED`/`COOLDOWN`;
- zero Scheduler jobs remain `PENDING`/`RUNNING`/`COOLDOWN` or locked; zero
  1h/4h/micro jobs ever existed;
- zero active leases;
- zero deletable residue (origin-activated batch, run steps, lifecycle events);
- exactly two immutable selected-item links present and unchanged
  (`HANDOFF_RECORDED`, non-null first-15m job id);
- `PRAGMA integrity_check = ok`, `PRAGMA foreign_key_check = []`, migration head
  `049`;
- cycle terminalized (`TERMINAL_*`) with the exact fault cause;
- `remaining_active_work` all-zero and `clean_zero_active_work is True`;
- `reconciliation.restart_created` / `successor_created` are `False`; every
  retrieval / decision / position / trade / audit / PnL table is empty;
- second compensation pass: `mutations_this_pass` all zero and a content
  snapshot (slots, tracking, jobs, links, cycle) is byte-identical before/after.

Normal success re-proven unchanged (`test_normal_success_unchanged`): exactly two
distinct mint/pair slots, two immutable links, no 1h/4h/micro job, no financial
table populated, integrity/FK clean.

Broad affected 15m operational suite
`tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py` — **14 passed** (the
driver-handler change introduces zero regressions).

Preceding campaign-accounting suite
`tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py` — **25 passed**
(its post-handoff proof updated from "pinned residual survives active" to the
repaired "terminalized, zero active work" invariant).

Combined run of the three suites — **51 passed**.

## Functionality Risks / Setbacks / Efficiency Blockers

- **Functionality risk:** compensation now terminalizes cycle/run/campaign via
  the shared authority. In production the coordinator later re-invokes
  `reconcile_campaign_terminal` with the same `POST_HANDOFF_<STAGE>` cause; this
  is idempotent (first cause immutable), so no double transition — but any future
  caller passing a *different* cause after compensation would be rejected by the
  first-cause-immutable guard (correct fail-closed behavior).
- **Setback (D-2):** stages 4–5 remain representative driver-level state, not
  real-runner-internal faults; a complete proof must fault inside
  `run_one_command_15m_factory` mid-materialization.
- **Setback (selective-1h):** the pre-existing provider-failure truthfulness
  defect is unrepaired and remains a separate blocker.
- **Efficiency blocker:** the compensation opens three short-lived connections
  (delete/cancel/lease, then `reconcile_campaign_terminal`, then the report read)
  to avoid write-lock contention across authorities; acceptable for a
  once-per-fault teardown, not a hot path.

## Commit

On this PASS the lane-owned uncommitted campaign-accounting changes and this
compensation repair are committed together as:

`Repair post-handoff terminal compensation`

No tag, no push.

## Exact next permitted task

Independent read-only review of this repair and of the remaining blockers (D-2;
selective-1h truthfulness defect). PASS authorizes only that review — not D-2
implementation, a live probe, or a Memory Factory campaign.
