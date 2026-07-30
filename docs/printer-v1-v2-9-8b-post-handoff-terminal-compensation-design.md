# Printer V1 V2-9.8B Post-Handoff Terminal Compensation Design

Date: 2026-07-30

Lane: `V2-9.8B Post-Handoff Terminal Compensation Repair`

Status: `FINAL_DESIGN_FOR_IMPLEMENTATION`

Supersedes, for the post-handoff surface only, the campaign-accounting lane's
D6 treatment (which deleted deletable residue and *reported* the pinned handoff
as surviving-active). The accounting, safe-stop, owner-authority, terminal
enforcement, and replay repairs (repairs 1–10, 13) are unchanged.

## Accepted invariant

```text
after a post-handoff failure:
  zero active, runnable, leased, reusable, or orphan work;
  immutable terminal handoff audit evidence may remain
```

The immutable selected-item links and their FK-pinned rows (slots, first-15m
jobs) are preserved as terminal audit evidence. They are not deleted or
deferred; the protected atomic two-token handoff and its FK audit chain stay
intact. The repair moves the pinned rows into a lawful **non-runnable terminal
state** rather than deleting them.

## C1 — one compensation owner, existing authorities only

`operator_cli/origin_lifecycle_campaign._compensate_post_handoff_teardown` stays
the single canonical post-handoff compensation owner. It introduces no second
cleanup authority: slot / tracking / cycle / run / campaign terminalization,
campaign-scoped Scheduler cancellation, window terminalization, and the
zero-active-work proof are delegated to the existing
`reconcile_campaign_terminal`. The owner adds only what that authority does not
reach:

1. deleting legally deletable lifecycle-materialization residue;
2. cancelling the executor's **cycle-scoped** first-15m Scheduler jobs (reached
   through the immutable link, re-cancelling any whose in-handoff cancellation
   rolled back);
3. releasing/terminalizing active leases (safety net).

It runs in a **new independent transaction after the failed materialization
transaction has already rolled back** (the driver's `except
PostHandoffInjectedFault` handler; the failed `connection` was closed
uncommitted). The signature gains `campaign_id`, `run_id`, `terminal_cause`, and
an optional `now`.

## C2 — required actions (mapped to the lane's 1–10)

1. **Terminalize both surviving token slots.** `reconcile_campaign_terminal`
   step 4a transitions each `SELECTED` slot → `MANUAL_REVIEW`
   (`transition_state`, migration-032 lawful non-runnable terminal). Slots are
   never deleted, so the immutable-link FK pin and the exactly-two-slots cycle
   trigger stay satisfied.
2. **Record the exact post-handoff terminal cause on each slot.** The transition
   writes `first_terminal_cause = POST_HANDOFF_<STAGE>` and `terminal_at` on each
   slot (schema CHECK enforces a non-empty cause on any terminal slot).
3. **Terminalize every linked tracking-queue row.** Step 4a drives the
   slot-linked `QUEUED` row → `SKIPPED` (`tracking_action='MANUAL_REVIEW'`,
   `priority_reason='campaign_terminal:<cause>'`). None remains `QUEUED`, due,
   promotable, or eligible for another pass.
4. **Cancel every first-15m Scheduler job for the cycle, incl. rolled-back
   cancellations.** The owner reads
   `printer_discovery_selected_item_links.first_window_15m_scheduler_job_id`
   for the cycle and, for any job still in `ACTIVE_STATUS_VALUES`, calls
   `cancel_job` through the committed Scheduler owner. Because the executor's
   in-handoff cancellation rolled back with the failed transaction, these jobs
   are re-cancelled here.
5. **Cancel/terminalize additional pre-fault lifecycle Scheduler jobs.**
   `reconcile_campaign_terminal` step 2 cancels every campaign-scoped job
   (`campaign_scoped_job_ids` over discovery-work / campaign-scheduler-work /
   factory run-steps) that is `PENDING`/`RUNNING`/`COOLDOWN` or locked.
6. **Release/terminalize active leases.** Any
   `printer_candidate_acquisition_leases` row in `ACTIVE`/`STOPPING` →
   `TERMINAL` (`terminal_status='CANCELLED'`, `first_terminal_cause=<cause>`,
   `released_at=<now>`), satisfying the lease terminal CHECK. N2/N7 is out of
   scope, so in proof this is a zero-row safety net; audit rows are never
   deleted.
7. **Delete only legally deletable lifecycle-materialization residue:** the
   `origin-activated:<cycle>` selection batch and its items; runner steps
   (`printer_memory_factory_run_steps` by token); snapshots
   (`printer_token_snapshots`, `printer_episode_snapshots`); transient lifecycle
   objects (`printer_token_lifecycle_events`). The executor's audit selection
   batch items (FK-pinned by the immutable link) are **not** in scope — deletion
   is keyed to the origin-activated `batch_id` only.
8. **Preserve immutable selected-item links and their FK-pinned rows.** The
   owner never updates or deletes `printer_discovery_selected_item_links`; it
   only terminalizes the pinned slots/jobs it references.
9. **Deterministic compensation report.** The owner returns a stable-shaped
   dict distinguishing:
   - `immutable_retained_evidence` — links + FK-pinned first-15m job ids;
   - `terminalized_pinned_rows` — slots now terminal, first-15m jobs cancelled,
     tracking rows closed;
   - `deleted_lifecycle_residue` — per-table deleted row counts this pass;
   - `remaining_active_work` — active slots / tracking / first-15m jobs /
     campaign jobs / leases / deletable residue, all `0`, with
     `clean_zero_active_work=True`;
   - `mutations_this_pass` — the counters used to prove idempotency.
10. **Idempotent.** Every step is guarded by current row state:
    `transition_state` returns `already_terminal` on replay; `cancel_job` is
    only invoked for still-active jobs; deletes match zero rows; lease release
    skips already-`TERMINAL` rows. A second pass reports
    `mutations_this_pass == all-zero` and leaves the DB byte-identical.

## C3 — driver wiring

`OriginToLifecycleCampaignDriver.run`'s `except PostHandoffInjectedFault`
handler calls the owner with `campaign_id=command.campaign_id`,
`run_id=command.run_id`, `cycle_id=fixtures.cycle_id`,
`terminal_cause=f"POST_HANDOFF_{fault.stage}"`, and the pre-captured
`committed_slots`. The returned report is attached to the `FAILED`
`OriginLifecycleResult` under
`activation.fault_details.compensation_report` and
`lifecycle.post_handoff_compensation_report`. `first_terminal_cause` stays
`POST_HANDOFF_<STAGE>`; `lifecycle_started=False`. In production the coordinator
later re-invokes `reconcile_campaign_terminal` with the same cause — idempotent,
so no double transition.

## C4 — proof (frozen inputs, fresh disposable migration-049 DB per injection)

For each of the five post-handoff injections
(`LIFECYCLE_SELECTION_BATCH_CREATION`, `EXECUTOR_JOB_CANCELLATION`,
`LIFECYCLE_JOB_REPLANNING`, `LIFECYCLE_OBJECT_MATERIALIZATION`,
`POST_ACTIVATION_STATE_TRANSITION`) prove:

- surviving slots are terminal and non-runnable (`token_state` in the lawful
  terminal set; `first_terminal_cause = POST_HANDOFF_<STAGE>`; `terminal_at`
  set); zero slots remain `SELECTED`/continuation/reusable;
- zero linked tracking rows remain `QUEUED`/active/promotable;
- zero first-15m or campaign-scoped Scheduler jobs remain
  `PENDING`/`RUNNING`/`COOLDOWN`/claimable/locked;
- zero active leases;
- zero deletable lifecycle-materialization residue;
- immutable selected-item links present and unchanged (count and row content);
- retained slots and jobs remain FK-valid (`PRAGMA foreign_key_check` empty,
  `integrity_check = ok`, migration head `049`);
- the terminal cause is attributable to campaign/run/cycle/fault stage;
- the compensation report reconciles every retained, terminalized, and deleted
  row and asserts `clean_zero_active_work`;
- a second compensation pass is idempotent (`mutations_this_pass` all zero; DB
  content snapshot unchanged);
- no retry/restart/successor/retrieval/decision/position/trade/audit/PnL path is
  created.

Normal success is re-proven unchanged: exactly two distinct mint/pair slots,
exactly two ordinary first-15m jobs, immutable links present, and no 1h/4h/12h/
24h/retrieval/financial unlock.

Suites: the focused compensation suite
(`tests/test_v2_9_8b_post_handoff_terminal_compensation.py`) and one broad
affected 15m operational suite
(`tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py`, whose
post-handoff proof is updated from "pinned residual survives active" to
"pinned residual is terminalized, zero active work").

## Scope exclusions (re-reported as remaining blockers)

Not implemented: runner-internal D-2 fault points; selective-1h provider-failure
counting repair; longer-window activation; live providers/RPC/WebSockets/
campaign; schema redesign of the immutable links; N2/N7, cursors, recovery, or
backfill.

## Preserved locks

Solana memecoin-only, paper-only; direct stateless one-page Pump live tail;
25-role validation; canonical deterministic two-token selector; exactly two
active tokens; `WINDOW_15M` only; 5m support-only; migration head 049; Source
Governor + Central Scheduler; no automatic retry/restart/successor; no
providers/RPC/WebSockets during proof; no authoritative DB mutation; no
N2/N7/cursor/recovery/backfill; no retrieval, decisions, BUY/SELL/HOLD,
positions, trades, audits, PnL; no wallets/keys/signing/funding/paid APIs,
scoring, ranking, confidence, weighting, embeddings, or live execution. No
ceiling is raised.

## Implementation modules

| Module | Change |
|---|---|
| `operator_cli/origin_lifecycle_campaign.py` | rewrite `_compensate_post_handoff_teardown` to terminalize via `reconcile_campaign_terminal` + cancel cycle-scoped first-15m jobs + release leases + deterministic report; thread identities/cause through the driver handler |
| `tests/test_v2_9_8b_post_handoff_terminal_compensation.py` | new focused frozen offline proof (five injections + idempotency + normal success) |
| `tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py` | update the post-handoff proof to the repaired invariant |
| docs | readiness / design / closeout; active anchor update |
