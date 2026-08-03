# Printer V1 V2-9.8B Post-Rollover-2 End-to-End Pre-Lifecycle Failure Propagation Design

Date: 2026-08-03

Baseline: `2e11f1304c3ba7151ef21f27e0db4fec88890ec1`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_END_TO_END_PRE_LIFECYCLE_FAILURE_PROPAGATION_DESIGN_PASS`

## Canonical contract

### Authoritative terminal

The returned activation/origin result is authoritative until a later lawful
stage begins. Its exact terminal status, first cause, cancellation reason,
`fault_details`, lifecycle-start truth, and retry/restart/successor flags are
copied without translation. The first cause is immutable.

The existing result types gain only attempt-local accountable-stage truth; this
is not a new status system. `accountable_stage_started` means actual work crossed
a real owner boundary (for discovery, a real Scheduler claim/work start), not
that activation succeeded.

### Stage evidence

`stage_evidences` contains only non-empty real evidence mappings. Collection
normalizes `None` to absence, never to a sequence item. Observer invocation,
owner stage count, actual evidence collection length, and the authoritative
result carry the separate state needed to decide whether evidence is required.

No empty evidence, synthetic Scheduler identity, reconstructed transition, or
`None` sentinel is permitted.

### Failed-stage observation

When activation fails after durable accountable discovery work, the origin
driver may project the same real durable Scheduler rows used by the successful
observer and mark the stage terminal with the real failure/cancellation cause.
When rows were rolled back or evidence is otherwise absent, it must not rebuild
them. It returns the original terminal with `accountable_stage_started=True` and
an evidence-missing diagnostic so the public finalizer fails closed secondarily.

An observer exception after an already-existing activation failure is recorded
as a secondary propagation diagnostic. If activation succeeded, the observer
exception is the first failure and continues to raise normally.

### Public finalizer decision

```text
authoritative non-success + no accountable stage
  -> do not invoke six-unit accounting
  -> cleanup/reconcile/report summary as returned failure
  -> preserve original terminal and require offline failure capture

authoritative non-success + accountable stage + complete real evidence
  -> run unchanged strict accounting
  -> preserve terminal and evidence
  -> report returned failure

authoritative non-success + accountable stage + missing/malformed evidence
  -> invoke unchanged strict accounting/fail closed
  -> keep original terminal primary
  -> attach accounting/projection failure secondarily
  -> require offline failure capture

successful activation + real evidence
  -> existing lifecycle/accounting/acceptance path unchanged
```

The public returned-failure finalizer receives the authoritative result and
owns cleanup, terminal reconciliation, reporting decision, summary write, and
secondary diagnostics. It never becomes a Scheduler or stage-accounting owner.

### Failure evidence helper

The proof-only helper accepts every returned non-success composition terminal,
not successful results. It derives an allowlisted first-failure record from
`fault_details` when available and otherwise from exact public terminal fields.
It retains status/cause/cancellation, discovery diagnostics, rollback result,
structured JSON, closed disposable DB copy, SHA-256, Migration-050 status,
integrity/FK results, sidecars, zero-network boundary, and retry state.

The exact harness invokes it after the public owner returns and all DB owners
close, but before `TemporaryDirectory` cleanup. A helper failure remains
secondary and is printed/attached without changing the operational cause.

### Exception precedence

1. original operational failure/cancellation/blocked terminal;
2. observer, projection, accounting, reconciliation, report, or finalizer
   propagation failure;
3. evidence-copy/artifact failure;
4. temporary cleanup failure.

If no operational failure existed, the first observer/finalizer exception is
primary as today.

## Bounded implementation owners

| Owner | Change |
| --- | --- |
| `CampaignExecutionResult` / `ActivationResult` | Add accountable-stage truth and preserve restart/successor truth |
| `CombinedPumpfunCampaignExecutor.execute` | Set accountable-stage truth from real claim/work state; preserve existing exact terminal fields |
| `OriginToLifecycleCampaignDriver.run` | Propagate truth; observe real durable failed stages; preserve observer failures secondarily |
| public stage observer | Honor record terminal status/cause; record invocation state; return no evidence sentinel |
| public collector/finalizer | Remove `(None,)`; make claimed-stage decision before accounting; dedicate returned-failure finalization |
| offline failure helper | Widen from SHARED-only to any non-success returned terminal while keeping success rejection and authoritative-DB prohibition |
| exact harness | Invoke helper for every returned non-success before temp cleanup; preserve helper error as secondary |

No change is permitted in `campaign_six_unit_accounting.py`, Scheduler claim or
terminal owners, Source Governor, schema/migrations, provider contracts, or
downstream capability locks.

## Focused proof contract

The focused module must cover success, pre-stage failure/cancellation/blocked,
post-stage failure, observer absence/real/`None`/malformed behavior, empty or
malformed claimed-stage fail-close, first-cause precedence across finalizer,
helper and cleanup diagnostics, failure-copy survival and DB verification.
Existing claim-at-work-start, Scheduler isolation, origin integration,
terminal/accounting, SHARED capture, full-run wiring, and token-slot projection
suites remain directly affected regressions.

## Money-usefulness contribution

The design makes failed acquisition as auditable as successful collection. That
reduces false repair cycles and ensures future memory-growth acceptance is based
on the real first failure and real evidence, not a later accounting artifact.

## What improves

- Exact first terminal propagation across every public pre-lifecycle owner.
- Truthful evidence requirement based on actual claimed work.
- Durable failure evidence before disposable cleanup.
- Existing success and strict accounting behavior remain intact.

## What remains locked

No live attempt or authorization, longer window, retrieval, decision,
BUY/SELL/HOLD, position, trade, audit, PnL, wallet, key, signing, paid API,
score/rank/confidence/weight, embedding/vector, retry, restart, resume, or
successor is enabled.

## Required proof

All focused tests, compilation, diff checks, and exact changed-file review must
pass before one exact public composition is allowed. The composition may run
once only and may not be repaired or rerun afterward.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Design response |
| --- | --- |
| False stage-start inference | Base it on real owner state and observer invocation, not terminal label |
| Failed-stage projection manufactures evidence | Project only durable exact rows; otherwise record missing evidence and fail closed |
| No-stage reporting appears accounted | Explicitly report accounting as not required; never create a stage evidence object |
| Success regression | Keep existing success path and its terminal stage/full-run acceptance unchanged |
| Helper expansion leaks secrets | Retain current bounded redaction and allowlists |
| Test scope becomes broad | Run only new focused and directly relevant suites; no full pytest |
