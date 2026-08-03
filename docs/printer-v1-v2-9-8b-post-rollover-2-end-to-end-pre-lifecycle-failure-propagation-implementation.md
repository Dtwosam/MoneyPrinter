# Printer V1 V2-9.8B Post-Rollover-2 End-to-End Pre-Lifecycle Failure Propagation Implementation

Date: 2026-08-03

Baseline: `2e11f1304c3ba7151ef21f27e0db4fec88890ec1`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_END_TO_END_PRE_LIFECYCLE_FAILURE_PROPAGATION_IMPLEMENTATION_PASS`

The bounded implementation closes every confirmed defect from the companion
audit while preserving strict accounting, claim-at-work-start, Scheduler and
Source Governor ownership, schema, retry policy, and capability locks.

## Implemented contract

1. `CampaignExecutionResult` and `ActivationResult` carry
   `accountable_stage_started` separately from success and lifecycle start.
2. The Combined Discovery Executor derives that truth only from a real claim,
   work insertion, observed claim transition, or previously completed work.
3. The origin driver preserves terminal status, immutable first cause,
   cancellation, `fault_details`, accountable-stage truth, and
   retry/restart/successor truth.
4. Failed activation after durable accountable work projects only real durable
   Scheduler identities and observes a truthful failed stage. Rolled-back or
   absent identities are never reconstructed.
5. Observer return `None` is explicitly notification-only and never becomes
   stage evidence.
6. The public coordinator records observer invocation/completion/failure state.
7. The `(None,)` fallback is removed. Every exposed evidence sequence contains
   only real non-empty mappings.
8. A dedicated returned pre-lifecycle finalizer decides whether accounting is
   required before invoking the unchanged strict accounting owner.
9. No accountable stage skips accounting and propagates the original terminal.
10. Claimed stage plus real evidence accounts strictly and then propagates.
11. Claimed stage plus missing, empty, `None`, or malformed evidence fails
    closed, but the accounting defect is secondary to the original terminal.
12. Cleanup, reconciliation, report, summary, observer, and accounting errors
    are attached as ordered propagation diagnostics.
13. The public returned terminal exposes exact activation status, first cause,
    cancellation, `fault_details`, lifecycle/stage truth, accounting decision,
    cleanup/reconciliation, no retry/successor, and failure-copy requirement.
14. The proof-only failure helper now accepts every returned non-success
    composition while still rejecting success and the authoritative database.
15. The exact harness invokes that helper before temporary cleanup for every
    returned non-success; helper failure remains a secondary diagnostic.

## Files changed

| File | Purpose |
| --- | --- |
| `src/printer_v1/operator_cli/abstract_campaign_command.py` | Attempt-local accountable-stage result truth |
| `src/printer_v1/discovery/combined_executor.py` | Real claim/work-derived stage-start truth |
| `src/printer_v1/operator_cli/origin_lifecycle_campaign.py` | Failed-stage projection/observation and complete terminal propagation |
| `src/printer_v1/operator_cli/operational_memory_factory_command.py` | Real-evidence-only collection and returned pre-lifecycle finalizer |
| `src/printer_v1/operator_cli/offline_shared_failure_evidence.py` | Generic returned-failure DB/JSON preservation |
| `tests/test_v2_9_8b_end_to_end_pre_lifecycle_failure_propagation.py` | Complete new deterministic contract matrix |
| `tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py` | Truthful failed-stage observer expectation |
| `tests/test_v2_9_8b_token_slot_id_exact_public_composition.py` | Pre-cleanup failure capture for every returned non-success |
| companion audit/design/implementation/focused-proof documents | Lane record |

## Defects repaired

- `None` placeholder construction and consumption;
- observer absence/evidence-malformation conflation;
- unconditional pre-lifecycle accounting;
- missing accountable-stage truth;
- suppression of durable failed-stage evidence;
- first-failure replacement by observer/accounting/finalizer/cleanup;
- cancellation and `fault_details` loss at the public surface;
- no returned-result failure finalizer;
- SHARED-only evidence-helper reachability;
- disposable DB deletion for other returned failures.

Strict rejection of claimed-stage evidence loss remains intentionally unchanged.

## Money-usefulness contribution

Printer can now explain and preserve why an acquisition failed before memory
lifecycle work, while still accounting every real claimed stage. This prevents
speculative fixes and keeps future memory-growth acceptance tied to real
Scheduler/source evidence.

## What improves

- End-to-end terminal fidelity and failure classification.
- Real failed-stage accounting instead of false empty-stage success.
- Evidence and database survival after returned failures.
- Deterministic distinction between no work and missing evidence.

## What remains locked

Six-unit law, Scheduler semantics, Source Governor, schema/migrations,
authorization, live providers, retries/restarts/resumes/successors, longer
windows, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL,
wallets, signing, paid APIs, scoring/ranking/confidence/weights, embeddings and
vectors remain unchanged and locked.

## Required proof

The final focused command must pass the new matrix plus all directly affected
origin, discovery claim/parity, Scheduler, terminal/accounting, public observer,
full-run wiring, authoritative owner, and failure-copy suites. Compilation,
`git diff --check`, exact changed-file review, and the single exact composition
remain subsequent gates.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Disposition |
| --- | --- |
| Failed transaction has no durable rows | Mark claimed evidence missing; do not reconstruct |
| Public report requires stage evidence | Persist strict report only when real stage accounting completed; no-stage summary remains explicit |
| Observer side effects precede seal failure | Record invocation and retain original terminal; missing owner evidence stays blocked |
| Helper name retains historical SHARED wording | Behavior/schema now truthfully cover all returned pre-lifecycle failures; compatibility symbols remain |
| Success-path regression | Direct origin, authoritative owner, full-run wiring and token-slot suites are mandatory |
