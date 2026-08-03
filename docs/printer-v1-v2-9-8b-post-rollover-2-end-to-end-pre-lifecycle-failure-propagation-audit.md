# Printer V1 V2-9.8B Post-Rollover-2 End-to-End Pre-Lifecycle Failure Propagation Audit

Date: 2026-08-03

Baseline: `2e11f1304c3ba7151ef21f27e0db4fec88890ec1`

Lane: `V2-9.8B Post-Rollover-2 End-to-End Pre-Lifecycle Failure Propagation Audit, Design, Repair, Proof and Conditional Closeout`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_END_TO_END_PRE_LIFECYCLE_FAILURE_PROPAGATION_AUDIT_PASS`

Primary classification: `COMMITTED_CODE_DEFECT`.

All confirmed defects are repairable inside the approved public pre-lifecycle
composition boundary. The repair needs no six-unit-law change, Scheduler-law
change, Source Governor change, schema/migration, retry/restart, synthetic
identity, or campaign-result redesign.

## Source-grounded blocker investigation

```text
BLOCKER CLASSIFICATION: COMMITTED_CODE_DEFECT
EVIDENCE: exact 2e11f13 traceback/report, current call path, result dataclasses,
public accounting finalizer, origin observer, failure helper, and focused tests
OFFICIAL-SOURCE COMPARISON: ordinary Python exception propagation is not the cause
PRINTER-CONTRACT COMPARISON: first terminal cause is immutable; real claimed work
requires evidence; no claimed work requires no stage accounting
ROOT CAUSE: the public coordinator encodes absent evidence as (None,) and invokes
strict accounting before it propagates a returned pre-lifecycle terminal
CODE CHANGE JUSTIFIED: YES
MINIMUM SAFE RESPONSE: explicit claimed-stage decision, real-evidence-only
collection, first-failure-preserving finalization, and failure-copy invocation
FOCUSED PROOF: bounded deterministic pre-lifecycle matrix plus affected suites
UNTOUCHED SCOPE: Scheduler/Source Governor/schema/retries/financial capabilities
AUTHORIZATION STATUS: consumed live authorization remains non-reusable
NEXT ROADMAP-COMPLIANT STEP: canonical design, bounded repair, focused proof
```

## Producer / consumer map

| Owner / function | Inputs | Outputs | Lifecycle / stage truth | Evidence | Exception / retention / cleanup behavior |
| --- | --- | --- | --- | --- | --- |
| `CombinedPumpfunCampaignExecutor.execute` | command, fixtures, Governor, Scheduler | `CampaignExecutionResult`: status, first cause, cancellation, usage, retry/successor flags, optional `fault_details` | Claim-at-work-start can occur before activation succeeds | No sealed campaign stage is returned | Expected `CombinedDiscoveryError` loses pre-rollback detail; unexpected exceptions retain SHARED diagnostics; connection closes after rollback/commit |
| `OriginToLifecycleCampaignDriver.run` | campaign execution result | `ActivationResult`, lifecycle mapping, `lifecycle_started` | Current result says only lifecycle truth, not whether accountable discovery work began | Successful activation invokes observer; every non-completed activation returns before observer | Correctly prevents empty completed stage, but also suppresses truthful failed-stage observation and claimed-stage state |
| `AuthoritativeLiveOperationalCampaignOwner.run_operational` | pre-admission/source stages and driver | `OriginLifecycleResult` | Can return before driver for zero/insufficient pool or holder/cancellation terminals | Earlier source stages may already seal evidence through sink | Returned terminal fields remain available in result/lifecycle |
| public `_observe_full_run_stage` | driver observer record | mutates action-local ledger and `CampaignSixUnitOwner` | Invocation itself proves a stage was presented | Seals real Scheduler and slot validation identities; return value is `None` by design | A raised seal/observer error currently escapes; invocation/secondary state is not retained |
| public evidence collector | lifecycle report plus owner | `exposed_stage_evidences` | Does not first distinguish no stage from missing evidence | Current fallback constructs `(stage_evidence,)`; when absent this is `(None,)` | Creates the visible malformed-input masking defect |
| `_finalize_operational_six_unit_accounting` | owner, evidence sequence, independent identities | closed/reconciled owner or exception | Correctly strict when called | Rejects absent, empty, `None`, malformed, duplicate, or mismatched evidence | Law is correct and must not change |
| public `_run_operational_campaign` | authoritative result | terminal/report/summary | Uses `result.lifecycle_started`, but not accountable-stage-started or observer state | Calls accounting for every non-lifecycle result | Accounting/cleanup/report exceptions can replace an earlier returned operational terminal; exact activation status/cancellation are not exposed in terminal mapping |
| `_terminalize_initialized_failure` | an exception plus campaign owners | failure cleanup/report terminal | Derives lifecycle start from allocated factory-run id rather than authoritative returned result | Requires evidence or explicit old no-work evidence | Useful for exception-first paths, but cannot recover a returned result already masked by finalizer; later errors are closure diagnostics |
| `preserve_failed_offline_composition_evidence` | returned terminal and closed disposable DB | DB copy, JSON, hash, integrity/FK | N/A | Currently accepts only nested `first_failure.classification=SHARED_FAILURE` | Other returned non-success terminals bypass it; a helper failure is secondary but no generic returned-failure copy exists |
| exact test harness / `TemporaryDirectory` | public return or raised exception | assertions and printed proof | N/A | Calls helper only for returned SHARED failure | Any other returned failure or escaping propagation exception reaches temp cleanup without DB preservation |

## Required state matrix

| Outcome | Stage began? | Evidence exists? | Accounting required? | Required public result |
| --- | ---: | ---: | ---: | --- |
| Successful two-slot activation | Yes | Yes | Yes | Continue unchanged |
| Partial supported activation | Contract-dependent; operational initial handoff remains atomic two-slot | Only if an earlier source/accountable stage sealed | Exactly when a stage began | Preserve the existing lawful terminal; no partial lifecycle |
| Failed activation before accountable stage | No | No | No | Propagate exact failure and invoke failure evidence owner |
| Failed activation after accountable work | Yes | Yes when durable projection/seal completed | Yes | Seal truthful failed stage, account strictly, then propagate |
| Explicit cancellation before stage | No | No | No | Propagate exact cancellation |
| Explicit cancellation after stage work | Yes | Yes | Yes | Preserve cancellation and evidence |
| Zero-slot failed activation | Depends on whether discovery/source work actually began; zero slots alone is not the discriminator | Same | Same | Propagate failure, never start lifecycle |
| Claimed stage with missing evidence | Yes | No | Yes, fail closed | Original terminal remains primary; evidence defect is secondary |
| Observer not invoked | No observer claim | No observer evidence | No solely because of observer absence | Never encode as `(None,)` |
| Observer raised after earlier failure | Depends on pre-existing stage truth | Possibly partial | Same as stage truth | Earlier operational failure primary; observer error secondary |
| Helper or DB-copy failure | N/A | N/A | N/A | Operational failure primary; helper failure secondary |

## Complete path findings

### Success

A two-slot completed activation materializes a real handoff, projects real
Scheduler identities, invokes the observer once, seals real evidence, starts the
lifecycle, runs strict accounting and full-run acceptance, writes the terminal
report, closes both 15-minute windows, and cleans supervision. This behavior is
lawful and must remain unchanged.

### Expected returned failure, cancellation, blocked, or stopped terminal

The executor and authoritative owner return categorical terminals rather than
raising for ordinary operational outcomes. The origin driver now preserves
status/cause/cancellation/fault details and avoids a false completed observer,
but it does not expose whether accountable discovery work had already been
claimed. The public coordinator then always enters the non-lifecycle accounting
branch. With no sealed evidence it turns absence into `(None,)`, so strict
accounting raises and replaces the returned terminal.

### Exception path

An exception before an authoritative result is legitimately primary and reaches
the existing exception terminalizer. An observer, finalizer, report, evidence
copy, or cleanup exception after a returned non-success result is secondary by
Printer first-cause law. Current public code does not preserve that ordering for
the returned-result path.

### Evidence and database lifetime

The executor closes its connection before returning. Public supervision cleanup
does not delete the disposable database. The exact harness owns temporary-root
deletion. Therefore the required safe order is public returned-failure
finalization, helper invocation/copy after connections close, then temporary
cleanup. Current harness invokes the helper only for SHARED failure, so other
failures lose the database.

## Confirmed defect inventory

1. `None` is wrapped into `stage_evidences=(None,)`.
2. Observer absence is conflated with malformed stage evidence.
3. Public finalization runs accounting before deciding whether an accountable
   stage began.
4. The origin result does not carry accountable-stage-start truth, so failed
   work after a real Scheduler claim is indistinguishable from pre-work failure.
5. The origin driver suppresses every failed-stage observation; a failure after
   durable accountable discovery work cannot seal truthful failed evidence.
6. A claimed stage whose transaction rolled back can reach the public owner with
   no stage evidence, but that projection defect replaces rather than annotates
   the original terminal.
7. Observer/finalizer/report/cleanup exceptions after a returned non-success can
   replace the earlier operational failure.
8. The public terminal mapping omits exact activation terminal status and
   cancellation, and can lose activation `fault_details` behind lifecycle-only
   reporting.
9. Cleanup is labelled from lifecycle `run_status` only; `NOT_STARTED` returned
   failures are not explicitly treated as failed cleanup terminals.
10. The public path has no dedicated returned-pre-lifecycle failure finalizer;
    the exception terminalizer cannot restore a result that was already masked.
11. The failure helper is restricted to SHARED failure instead of every returned
    non-success activation required by this proof boundary.
12. The exact harness calls the helper only for SHARED failure, allowing other
    returned failures to be deleted by temporary cleanup.
13. Helper failure is not attached to a returned terminal in the harness before
    cleanup.
14. Existing strict malformed-stage rejection is correct; weakening it would
    conceal defects and is explicitly not a repair.

No synthetic Scheduler transition or identity was found in the current path.
No retry, restart, resume, or successor path is created. Source Governor,
Scheduler claim-at-work-start, and capability locks remain intact.

## Audit gate

The defects can be repaired by adding attempt-local stage truth to existing
results, observing only real durable failed-stage identities, introducing a
dedicated first-cause-preserving returned pre-lifecycle finalizer, removing the
`None` fallback, and widening the proof-only failure-copy gate. The accounting
owner remains unchanged and still rejects claimed-stage evidence loss.

## Money-usefulness contribution

The audit prevents Printer from losing the real reason a bounded campaign could
not begin its lifecycle. Honest failure identity and retained database evidence
are prerequisites for trusting later memory growth; hiding them behind an
accounting exception would encourage speculative repairs and contaminated
readiness claims.

## What improves

- Full, explicit pre-lifecycle success/failure/cancellation ownership.
- Correct separation of no stage from missing stage evidence.
- First-cause and database evidence survival.
- Strict accounting remains meaningful instead of being invoked on a sentinel.

## What remains locked

Retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, wallets,
signing, live execution, paid APIs, scoring/ranking/confidence/weights,
embeddings/vectors, longer windows, retries, and live authorization remain
locked.

## Required proof

Focused deterministic coverage must exercise the complete matrix, strict
malformed rejection, helper/copy ordering, claim isolation, no lifecycle after
failure, and zero capability deltas before the single exact public composition.

## Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Control |
| --- | --- |
| A failed stage is inferred from mere result failure | Require actual claim/work/observer state; never infer from status alone |
| Rolled-back work is called durable | Keep transaction-local labels and fail closed when real sealed evidence is absent |
| Failure reporting weakens accounting | Skip only when no accountable stage began; otherwise keep strict rejection |
| Observer exception overwrites failure | Store it as secondary when an operational terminal already exists |
| Failure copy touches production DB | Keep canonical authoritative-path rejection and proof-only invocation |
| Scope grows into lifecycle/accounting redesign | Limit changes to result truth, pre-lifecycle finalizer, observer boundary, helper and exact harness |
