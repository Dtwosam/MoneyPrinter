# Printer V1 V2-9.8B Post-Rollover-2 Origin Driver Activation-Failure Propagation Repair Implementation

**Lane:** `V2-9.8B Post-Rollover-2 Origin Driver Activation-Failure Propagation Repair Implementation`

**Verdict:** `V2_9_8B_POST_ROLLOVER_2_ORIGIN_DRIVER_ACTIVATION_FAILURE_PROPAGATION_REPAIR_IMPLEMENTATION_PASS`

**Baseline:** `f225c2bee93233e22b9845c7cadf20f84297de29`

**Branch:** `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit`

## 1. Exact root cause repaired

The origin driver invoked the successful `DISCOVERY_SELECTION_TERMINAL` stage
observer before it classified the activation terminal. A failed or zero-slot
activation could therefore advertise an empty completed started stage to strict
public accounting. The accounting owner correctly rejected that malformed empty
stage, but its later exception masked the activation's original terminal result,
first cause, cancellation reason, and `fault_details` before those facts reached
the public coordinator.

This was a `COMMITTED_CODE_DEFECT` in the canonical
`OriginToLifecycleCampaignDriver` ordering. It was not an accounting defect, a
Scheduler identity gap, or permission to synthesize accountable work.

## 2. Files changed

- `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
- `tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py`
- `docs/printer-v1-v2-9-8b-post-rollover-2-origin-driver-activation-failure-propagation-repair-implementation.md`

The supplied repair script changed exactly the first two approved files. This
implementation report is the separately required lane document. No approved
audit or design document was untracked, so none was added to the commit scope.

## 3. Activation-result ordering

The origin driver now inspects `activation.terminal_status` immediately after
activation and before it opens, projects, observes, or seals an accountable
discovery-selection stage.

- A non-`COMPLETED` activation is returned directly as the authoritative
  terminal result.
- Its activated slots are empty and its selection batch is absent.
- Lifecycle output is categorical `NOT_STARTED` and
  `lifecycle_started=False`.
- No `DISCOVERY_SELECTION_TERMINAL` observer is invoked.
- No lifecycle Scheduler work is started.
- Only a completed activation that produced a real batch and two activated
  slots can reach the successful stage-observer path.

This ordering covers failed, cancelled, blocked, stopped, insufficient-slot,
and other non-completed activation terminals without replacing their category.

## 4. Cancellation and `fault_details` preservation

`ActivationResult` now carries `cancellation_reason` in addition to the existing
`fault_details`. The early non-completed return preserves:

- the exact activation `terminal_status`;
- the immutable `first_terminal_cause`;
- the activation `cancellation_reason`, when present; and
- the activation `fault_details`, when present.

The lifecycle projection repeats the exact first cause and conditionally exposes
the cancellation reason and a copied `fault_details` mapping. No later observer,
cleanup, reporting, or accounting result overwrites the first terminal cause.

## 5. Successful-path preservation

Completed two-slot activation retains the existing handoff, stage projection,
lifecycle start, and result construction. The successful observer is now
additionally guarded by a real non-null selection batch. Focused proof confirms
that the success path still emits exactly one non-empty
`DISCOVERY_SELECTION_TERMINAL` stage with two slots and non-empty accountable
Scheduler work identities, then starts the existing lifecycle.

## 6. Accounting and Scheduler boundaries

The repair does not modify the public accounting owner, its strict rejection of
malformed empty started-stage evidence, the six-unit accounting model, stage
weights, or reconciliation law. It adds no synthetic Scheduler work identity,
validation identity, enqueue, claim, retry, or transition.

Claim-at-work-start behavior remains owned by the existing Central Scheduler
path and passes its focused regression module. Source Governor and Central
Scheduler ownership are unchanged. No source call, source contact, lifecycle
retry, restart, successor, financial capability, or independent scheduling path
was introduced.

## 7. Focused verification

Executed exactly:

```text
.venv/bin/python -m pytest -q \
  tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py \
  tests/test_v2_9_8b_shared_failure_evidence_capture.py \
  tests/test_v2_9_8b_discovery_scheduler_claim_at_work_start.py \
  tests/test_v2_9_8b_full_run_wiring_integration.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py
```

Result:

```text
64 passed, 6 subtests passed in 23.56s
```

The focused result proves:

- insufficient two-slot activation returns its original
  `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL` failure;
- SHARED failure preserves `SHARED_FAILURE` cancellation and the exact first
  cause;
- failed and zero-slot activation emit no
  `DISCOVERY_SELECTION_TERMINAL` observer event;
- failed activation starts no lifecycle and creates no lifecycle Scheduler
  work;
- successful activation emits one non-empty accountable discovery stage;
- strict accounting still rejects deliberately malformed empty started-stage
  evidence;
- claim-at-work-start behavior remains passing;
- full-run wiring and six-unit accounting semantics remain passing; and
- no retry, restart, successor, source contact, or financial capability was
  introduced.

Also executed:

```text
.venv/bin/python -m py_compile \
  src/printer_v1/operator_cli/origin_lifecycle_campaign.py \
  tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py

git diff --check
git status --short --untracked-files=all
```

Compilation and `git diff --check` passed. Status showed only the two approved
code/test modifications, this required report after creation, and preserved
pre-existing untracked evidence.

## 8. Tests and compositions not run

- Broad pytest was not run.
- The exact public composition was not run or retried.
- No live, provider, RPC, Source Governor, Central Scheduler, Memory Factory,
  campaign, comparison, recovery, or authoritative-database command was run.
- No comparison-worktree execution was run.

The requested focused suite is the minimum sufficient verification for this
narrow owner-ordering repair.

## 9. Money-usefulness contribution

The repair keeps a genuine discovery/activation failure from being hidden by a
later empty-stage accounting exception. That preserves honest evidence about
why no two-token lifecycle began and prevents zero-accountability work from
being presented as a completed discovery stage. Accurate first-cause and
failure-detail propagation protects later corpus-quality, campaign-acceptance,
and clean-memory claims from synthetic or misclassified progress.

## 10. Authorization and preserved comparison state

`V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` remains consumed and permanently
non-reusable. This offline repair and focused verification did not issue,
replace, refresh, or consume any authorization.

`/private/tmp/mp-preclaim` remains registered, clean, detached at
`8fb4256c70d4e81660c177238253322cb37ae947`, and was not modified or removed.

## 11. What remains locked

- exact public-composition retry, rerun, or comparison execution;
- fresh authorization or reuse of consumed authorization;
- live or operational discovery, source, Scheduler, Memory Factory, or campaign
  execution;
- provider/RPC contact and authoritative database mutation;
- automatic retry, restart, resume, recovery, or successor creation;
- memory generation and longer-window operation;
- retrieval and paper decisions;
- BUY, SELL, HOLD, positions, trades, paper audits, and PnL;
- wallets, private keys, signing, execution, and real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, and
  vectors.

The underlying discovery `SHARED_FAILURE` cause observed in the earlier bounded
evidence-capture proof is not reclassified by this repair. This lane repairs
only faithful propagation of whatever activation terminal already exists.

## 12. Functionality Risks / Setbacks / Efficiency Blockers

| Area | Finding |
| --- | --- |
| Functionality risk | The focused offline suite proves ordering and propagation, but no exact public composition was authorized or run in this lane |
| Residual classification risk | The underlying earlier discovery `SHARED_FAILURE` cause remains distinct from this repaired propagation boundary |
| Compatibility risk | `ActivationResult` gains an optional cancellation field with a default, preserving existing constructor compatibility; focused wiring tests pass |
| Accounting risk | Strict accounting was intentionally unchanged; malformed empty stage evidence continues to fail closed |
| Scheduler risk | No Scheduler owner or identity constructor changed; focused claim and six-unit accounting regressions pass |
| Tooling setback | The requested `python` alias was absent; that command made no changes, and the unchanged supplied Python 3 script was then applied with `/usr/bin/python3` |
| Efficiency blocker | Product/public-composition proof remains locked pending independent closeout and any later separately authorized lane |

## 13. Exact next lane

```text
V2-9.8B Post-Rollover-2 Origin Driver Activation-Failure Propagation Repair Independent Closeout
```

That lane may independently inspect this commit, diff, focused-test evidence,
scope, accounting/Scheduler boundaries, authorization status, and comparison
worktree preservation. It does not authorize the exact public composition, a
retry, providers, database mutation, a campaign, or any financial capability.
