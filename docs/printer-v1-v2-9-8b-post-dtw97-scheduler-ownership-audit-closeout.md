# Printer V1 V2-9.8B — Post-DTW97 Scheduler Ownership Audit Closeout

Date: 2026-08-09

Lane: `V2-9.8B Post-DTW97 Scheduler Ownership Audit`

Baseline: `d7dd83d0150187a84d55ac899cf31a3b00aa4fda`

## Verdict

`V2_9_8B_POST_DTW97_SCHEDULER_OWNERSHIP_AUDIT_PASS_EXPECTED_INTERRUPTION_BEHAVIOR_NO_REPAIR`

No production repair is justified by DTW97 Scheduler ownership evidence.

DTW97 remains a consumed, operator-interrupted attempt and is not an operational PASS. Authorization `V2_9_8B_WINDOW_15M_AUTH_20260809T120100Z` is permanently non-reusable.

## Evidence

Read-only DTW97 ownership capture inspected Scheduler jobs `1442` through `1459`.

- 18/18 jobs exist and are terminal/unlocked.
- 18/18 are referenced by `printer_memory_factory_run_steps` for factory run `e96e7985-ec74-472e-9ad3-b785aec86cee`.
- 0/18 have a `printer_discovery_work` exact owner.
- 0/18 have a `V2_STAGE_SCOPED printer_memory_factory_campaign_scheduler_work` exact owner.
- 0/18 have a selected-item first-15m handoff owner.
- 4 jobs had succeeded before the operator interruption; the remainder were terminally cancelled during safe-stop cleanup.
- authoritative DB integrity is `ok`, foreign keys are clean, the audit made zero writes, and target jobs are neither active nor locked.

## Static causal classification

The missing exact-scope ownership is expected for this interrupted lifecycle and is not evidence of a production ownership defect.

`one_command_15m_factory._insert_step_and_job()` creates each canonical Scheduler job and its factory run-step linkage. It does not create a campaign `WINDOW_LIFECYCLE` ownership row at enqueue time.

The approved full-run accounting owner intentionally performs lifecycle Scheduler ownership projection later, inside `finalize_full_run_ownership_and_report()`. Before projection it requires a successful `WINDOW_CLOSE` so it can establish the exact campaign window and token-slot identity. `project_campaign_scheduler_job()` then projects each existing factory Scheduler job into `printer_memory_factory_campaign_scheduler_work` with the required `V2_STAGE_SCOPED / WINDOW_LIFECYCLE` linkage.

The migration-050 scope contract likewise requires `WINDOW_LIFECYCLE` rows to carry slot + window + factory linkage. A factory run-step alone is not sufficient exact campaign/run/cycle ownership because it does not establish the campaign window/cycle ownership surface.

DTW97 was explicitly operator-interrupted before any `WINDOW_CLOSE` succeeded. Its terminal evidence reports zero terminal windows. Therefore no lawful campaign window existed to which jobs `1442`–`1459` could be projected. The full-run gate correctly surfaced `missing_ownership` and refused `CAMPAIGN_PASS` rather than fabricating ownership.

The four snapshot jobs that had already succeeded before interruption do not change this classification: job execution success is not the approved ownership-projection boundary. Successful window close and exact campaign-window registration are prerequisites to lifecycle ownership projection.

## Safe-stop result

The separate consumed-attempt read-only audit proved:

- first terminal cause `SAFE_STOP_OPERATOR_INTERRUPTED`;
- zero active campaign/run/supervision/discovery/Scheduler residue;
- zero active Printer process matches;
- cleanup completed;
- lease released and lock absent;
- all Scheduler jobs terminal;
- DB integrity `ok` and zero FK violations;
- locked capability baseline PASS;
- no retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit or PnL unlock;
- no retry, rerun, resume, restart or successor.

The missing wrapper terminal is attributable to the outer wrapper being interrupted while its child output was redirected; it does not invalidate the durable child/campaign terminal evidence or clean safe-stop state.

## Roadmap decision

Do **not** change lifecycle ownership timing merely to make an interrupted run show exact `WINDOW_LIFECYCLE` ownership. Doing so would redesign the approved post-close compensation architecture without a proven defect and would violate the no-speculative-repair rule.

Do **not** rerun DTW97 or reuse its authorization.

The next permitted step is a fresh post-DTW97 read-only `WINDOW_15M` rereadiness review against the new authoritative DB identity. Only after rereadiness and its closeout pass may a new one-use authorization be prepared and independently reviewed.

## Money-usefulness contribution

This audit prevents an unnecessary ownership rewrite and preserves the already-proven Scheduler/window identity architecture while confirming that an operator-interrupted run fails closed without fabricating a lifecycle success. That protects future memory evidence from false ownership and false completion claims.

## What this lane improves

- distinguishes real ownership facts from a production defect;
- proves DTW97 safe-stop cleanup left no active residue;
- preserves exact slot/window/factory lifecycle ownership semantics;
- preserves the one-job-one-owner migration-050 contract;
- prevents an unnecessary production repair before the next bounded attempt.

## What this lane does not unlock

- no new authorization;
- no WINDOW_15M rerun;
- no WINDOW_1H/4H/12H/24H activation;
- no retrieval;
- no paper decisions or BUY/SELL/HOLD;
- no positions, trade events, audits or PnL;
- no live wallet, private keys, real funds or live execution.

## Proof required before completion / next capability

This audit is complete on static source inspection plus the read-only DTW97 DB/artifact facts. Before any new runtime authorization, the next lane must independently re-establish post-DTW97 authoritative DB readiness, zero residue, migration/integrity/FK truth, source/composition/dependency/holder-budget readiness, locked capabilities, and consumed-authorization non-reuse.

## Functionality Risks / Setbacks / Efficiency Blockers

- DTW97 produced no terminal WINDOW_15M memory because it was operator interrupted.
- Authorization `...120100Z` is permanently consumed, so a later attempt requires a fresh authorization package and independent review.
- The wrapper terminal artifact is absent for DTW97 because the outer wrapper was interrupted; durable child/campaign evidence is available and controls attempt classification.
- A future run must be allowed to remain attached to its terminal until the wrapper returns; operator input into that terminal can consume another one-use authorization without completing the 15-minute proof.
