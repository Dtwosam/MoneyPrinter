# Printer V1 V2-9.8B Post-DTW100 1h Checkpoint 4 Close-Boundary Audit

## Verdict

`V2_9_8B_POST_DTW100_1H_CHECKPOINT_4_CLOSE_BOUNDARY_AUDIT_BLOCKED_CLOSE_TRUTH_REPAIR_REQUIRED`

The current first-hour close machinery is largely reusable and correctly anchored to the clean 15m predecessor, but the current runtime does not yet make the close boundary truthful enough to proceed directly to Checkpoint 5.

A bounded design/implementation/proof repair is required before the genuine-1h memory-construction checkpoint.

## Baseline and scope

- Baseline: `61473b57da334def1ad52ae97d1f11c74bf93f41` — Checkpoint-3 exact-closeout PASS.
- Branch: `agent/v2-9-8b-post-dtw100-1h-checkpoint4-close-boundary`.
- Starting state: exact owned `WINDOW_1H` is `COLLECTING`; remaining-45m jobs are Scheduler-owned, campaign-projected, Source-Governed, and lifecycle-accounted.
- Audit scope: exact `CONTINUATION_CLOSE` scheduling/execution, fixed first-hour deadline, closing snapshot truth, campaign-window close state, memory-window row creation/binding, Scheduler close cleanup, and failure behavior.

No live runtime, source call, authorization, authoritative-DB mutation, 4h activation, retrieval, decision, position, trade, audit, or PnL action occurred.

## Current reusable path

The current implementation already has the correct core pieces:

1. `_plan_continuation_jobs()` schedules exactly one `CONTINUATION_CLOSE` at `15m close + 2700s`.
2. Central Scheduler owns the close job and does not make it claimable before its scheduled deadline.
3. `_execute_continuation_close()` reuses `_execute_snapshot()` for the closing observation, preserving exact token/pair targeting and Source Governor execution.
4. `close_1h_memory_window_from_snapshot()` reuses the established 1h close owner and links the exact current-run clean 15m predecessor.
5. `evaluate_15m_to_1h_continuity()` verifies exact predecessor window, exact predecessor closing snapshot, no historical reuse, no interpolated first snapshot, fixed deadline metadata, and transition-gap quality.
6. The `WINDOW_1H` cadence policy already defines the correct 2700-second continuation duration and 24 FAST / 13 NORMAL expected snapshots.
7. Checkpoint 3 now synchronizes the close Scheduler job to its exact campaign ownership row on claim and terminalization.

These pieces should be reused; a new 1h close engine is neither necessary nor desirable.

## Blocker 1 — campaign close state is not advanced at the real close boundary

Checkpoint 3 truthfully advances the campaign `WINDOW_1H` from `PLANNED` to `COLLECTING` on the first continuation snapshot.

However, when the Scheduler claims `CONTINUATION_CLOSE`, the runtime does not advance the exact campaign window from:

`COLLECTING -> CLOSE_PENDING`

The later `bind_1h_memory_window()` helper can walk `PLANNED -> COLLECTING -> CLOSE_PENDING -> AUDITING` retroactively. That compatibility behavior can hide whether the close states were actually reached at the correct runtime boundaries.

Checkpoint 4 must make `CLOSE_PENDING` a real-time transition owned by the close job, not a retrospective reporting repair.

## Blocker 2 — successful close row is not bound to the campaign window at close time

`close_1h_memory_window_from_snapshot()` creates or resolves the genuine `printer_memory_windows` `WINDOW_1H` row, and `_execute_continuation_close()` returns `memory_window_id`.

The exact existing campaign `WINDOW_1H` successor already has the correct token/pair/window identity, but its `memory_window_row_id` remains unbound until later terminal/audit handling.

This creates a temporary ownership gap where the physical closed 1h row exists but the campaign graph does not yet identify it.

The existing canonical `campaign_ownership.bind_window_memory_row_id()` owner should be reused immediately after a successful close and before the close job is terminalized.

## Blocker 3 — close failure can leave the campaign window nonterminal

Checkpoint 3 terminalizes the affected exact campaign window on a token-local `CONTINUATION_SNAPSHOT` failure.

The current failure path is narrower than required: a failed `CONTINUATION_CLOSE` is not equivalently terminalized. The Scheduler job can become `FAILED` while the campaign window remains `COLLECTING` or, after the required state repair, `CLOSE_PENDING`.

A failed close must fail closed on that token's exact `WINDOW_1H` and must not affect the peer token.

## Blocker 4 — fixed deadline metadata is stronger than observed closing-snapshot proof

The most important evidence-quality gap is in the current 1h close boundary.

`close_1h_memory_window_from_snapshot()` correctly computes the authoritative deadline as:

`15m close + 2700s`

and writes that fixed deadline into `window_end_at`.

But the writer does not require the actual closing snapshot's `captured_at` to reach that deadline. Therefore a direct/incorrect early close can create a row whose metadata says the continuation lasted 2700 seconds even when its closing evidence did not.

The current E2Q genuine-1h structural gate checks the stored `window_start_at -> window_end_at` duration, so the fixed metadata alone can satisfy the 2700-second structural duration floor. The cadence evaluator already has a stronger generic forced-closing-snapshot contract, but `WINDOW_1H` does not currently enable it.

This is an evidence-truth gap even though the normal Central Scheduler path schedules the close at the correct deadline. The close/memory-quality boundary must not rely solely on the Scheduler to make fabricated or excessively late close evidence impossible.

## Required repair direction

The smallest safe repair is:

1. add an exact campaign-window close-boundary helper in the existing factory owner that moves only an owned `WINDOW_1H` from `COLLECTING` to `CLOSE_PENDING` when `CONTINUATION_CLOSE` is claimed;
2. after a successful close returns a `memory_window_id`, bind that exact row to the exact owned campaign `WINDOW_1H` using `bind_window_memory_row_id()` before completing the Scheduler job;
3. terminalize the exact campaign `WINDOW_1H` as `BLOCKED` on `CONTINUATION_CLOSE` failure, preserving peer-token isolation;
4. make the 1h close writer fail closed if the actual closing snapshot precedes the fixed deadline;
5. record closing-snapshot lateness explicitly;
6. enable the existing `require_full_anchored_duration` and `require_forced_closing_snapshot` cadence-policy controls for `WINDOW_1H`, so a close at/just after the deadline is judged honestly and an excessively late close cannot become clean memory.

No new collector, Scheduler, source adapter, retry path, table, migration, or second memory writer is justified.

## Money-usefulness contribution

A clean first-hour memory is useful only if Printer really observed the token through the fixed first-hour boundary. This repair prevents an early or excessively delayed closing observation from masquerading as a clean full first-hour observation and makes the campaign graph identify the exact close row at the moment it exists.

That improves historical-memory trustworthiness. It does not prove profitability or authorize any decision or trade behavior.

## What this checkpoint improves after repair

- real-time campaign close-state truth;
- exact campaign-window-to-memory-window identity at close;
- token-local close-failure isolation;
- actual closing-snapshot proof against the fixed first-hour deadline;
- reuse of the shared cadence closing-freshness machinery.

## What remains locked

This audit and its repair do not unlock live first-hour execution, authorization/wrapper work, 4h, 12h/24h, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, paper-trade audits, PnL, live wallet/private keys/real funds/execution, paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Proof required

Focused offline RED/GREEN proof must establish at minimum:

- close claim advances only the exact owned first-hour window `COLLECTING -> CLOSE_PENDING`;
- exact closing `printer_memory_windows` row binds to that campaign window before Scheduler success;
- a close snapshot before the fixed deadline creates no 1h row;
- an at-deadline close is admissible;
- closing lateness is evaluated by the existing cadence policy (clean/dirty/blocked according to the policy rather than clamped away);
- a failed close blocks only that token's exact campaign window and leaves its peer intact;
- Checkpoints 1-3 and existing first-hour/Scheduler ownership regressions remain green.

## Functionality Risks / Setbacks / Efficiency Blockers

- `lane_e2o_1h_window_close.py` is an older proof-era owner; the repair must remain additive and must not duplicate it.
- Enabling forced-close freshness for 1h tightens clean-memory truth and may expose stale fixtures that previously relied only on anchored metadata. Such failures must be classified rather than weakened away.
- Close-row binding must remain one-shot/idempotent and exact-token/exact-pair/exact-window; no retrospective nearest-window matching is allowed.
- The runtime currently proceeds from close into E2Q/E2Z inside `_execute_continuation_close()`. Checkpoint 4 must not redesign that downstream pipeline; Checkpoint 5 will audit its memory-construction semantics separately.

## Next permitted action

Design the bounded Checkpoint-4 close-boundary truth repair, then implement it with focused TDD proof. Do not move to Checkpoint 5 until this checkpoint closes PASS.
