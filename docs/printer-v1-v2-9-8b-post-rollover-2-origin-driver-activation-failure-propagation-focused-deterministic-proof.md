# Printer V1 V2-9.8B Post-Rollover-2 Origin Driver Activation-Failure Propagation Focused Deterministic Proof

Date: 2026-08-03

Lane:
`V2-9.8B Post-Rollover-2 Origin Driver Activation-Failure Propagation Focused Deterministic Proof`

Lane type: proof and documentation only.

## 1. Verdict

`V2_9_8B_POST_ROLLOVER_2_ORIGIN_DRIVER_ACTIVATION_FAILURE_PROPAGATION_FOCUSED_DETERMINISTIC_PROOF_PASS`

The focused deterministic proof passes. A non-completed activation reaches the
origin driver's caller with its original terminal status, immutable first cause,
cancellation reason, and `fault_details`, before any discovery-selection stage
observer or lifecycle owner can run. A completed two-slot activation emits one
real accountable discovery-selection observation before lifecycle start. Strict
accounting, claim-at-work-start, no-retry/no-successor, and locked-capability
invariants remain intact.

This PASS does not execute or authorize the exact public composition. That
composition remains reserved for the exact next lane.

## 2. Baseline and preflight

| Item | Exact result |
| --- | --- |
| Required baseline HEAD | `3f1be84ceccf35dad809e239d60847f68cfe066e` |
| Baseline commit | `Repair origin driver activation failure propagation` |
| Branch | `agent/v2-9-8b-post-rollover-2-exact-public-composition-scheduler-claim-coverage-audit` |
| Tracked tree | Clean at lane start |
| Preserved untracked state | Pre-existing `.DS_Store` and operator-run/authorization artifacts only |
| Upstream refresh | `git fetch origin --prune` completed |
| Ahead / behind after refresh | 6 ahead / 0 behind |
| Relevant processes | None matched `printer_v1`, `MoneyPrinter`, `operational_memory_factory`, or `memory_factory` |
| Comparison worktree | `/private/tmp/mp-preclaim`, clean, detached at `8fb4256c70d4e81660c177238253322cb37ae947` |

The comparison worktree was not modified, executed, removed, or used as proof
evidence.

## 3. Source stack and lane evidence used

The proof followed the active Printer V1 source stack in `AGENTS.md`, including
the Clean Master Spec, Post-RC Build Order, Memory Factory Guide, active
memory-growth build order, assistant anchor, and Python Builder Guide.

The tracked causal lane chain used was:

- `docs/printer-v1-v2-9-8b-post-rollover-2-discovery-scheduler-claim-coverage-blocker-audit.md`;
- `docs/printer-v1-v2-9-8b-post-rollover-2-discovery-scheduler-claim-at-work-start-repair-design.md`;
- `docs/printer-v1-v2-9-8b-post-rollover-2-origin-driver-activation-failure-propagation-repair-implementation.md`;
- `docs/printer-v1-v2-9-8b-post-rollover-2-discovery-scheduler-claim-at-work-start-shared-failure-bounded-offline-evidence-capture-proof.md`.

The baseline contains no separately tracked origin-driver audit or repair-design
file. The repair implementation report records that fact. The bounded offline
proof contains the confirmed origin-driver ordering defect and the required
future audit boundary; the tracked claim audit/design and repair implementation
provide the accepted causal and implementation chain. No missing document was
invented or reconstructed.

Inspection stayed within:

- `OriginToLifecycleCampaignDriver.run` and its activation result contract;
- the directly affected origin integration tests;
- the offline shared-failure evidence owner and tests;
- discovery claim-at-work-start regressions;
- six-unit accounting and the malformed empty-stage regression;
- full-run wiring and accounting semantics directly affected by the repair.

## 4. Exact tests and counts

The focused pytest command was exactly:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q \
  tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py \
  tests/test_v2_9_8b_shared_failure_evidence_capture.py \
  tests/test_v2_9_8b_discovery_scheduler_claim_at_work_start.py \
  tests/test_v2_9_8b_full_run_wiring_integration.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py \
  tests/test_v2_9_8b_terminal_safety_accounting_finalization.py::test_accounting_rejects_absence_malformed_duplicate_mismatch_and_accepts_explicit_no_work
```

Result:

```text
65 passed, 6 subtests passed in 20.30s
```

Collected test counts:

| Surface | Count |
| --- | ---: |
| Repaired origin-to-lifecycle integration | 16 |
| Shared-failure evidence capture | 9 |
| Discovery Scheduler claim-at-work-start | 9 |
| Directly affected full-run wiring | 10 |
| Full-run six-unit accounting semantics | 20 |
| Exact selected terminal-safety accounting regression | 1 |
| Total | 65 tests plus 6 subtests |

`pytest --collect-only -q` independently confirmed exactly 65 collected nodes.

Three additional disposable, assertion-only Python probes ran outside the
repository test tree and created no repository artifact:

1. five cases passed: `FAILED`, `CANCELLED`, `BLOCKED`, and `STOPPED`
   propagation plus returned-SHARED-failure helper reachability;
2. one completed two-slot observer-order case passed;
3. one exact malformed empty-started-stage accounting case passed with
   `SIX_UNIT_STAGE_EVIDENCE_MALFORMED:EMPTY_STARTED_STAGE_EVIDENCE`.

The first draft of the helper-reachability probe incorrectly expected the
origin integration's simple `force_shared_fault` fixture to populate
`fault_details`; it does not. That draft stopped on a local `TypeError`, mutated
no product state, and was replaced with the dedicated shared-failure diagnostic
fixture that actually returns captured `fault_details`. The corrected probe
passed. This was a proof-harness assumption, not a product-code failure.

## 5. Failure-path results

| Activation case | Preserved result | Observer / lifecycle result |
| --- | --- | --- |
| Generic `FAILED` | Exact status, first cause, cancellation reason, and same `fault_details` mapping | No `DISCOVERY_SELECTION_TERMINAL`; lifecycle runner not called |
| `CANCELLED` | Exact status, first cause, cancellation reason, and same `fault_details` mapping | No observer; lifecycle runner not called |
| `BLOCKED` | Exact status, first cause, cancellation reason, and same `fault_details` mapping | No observer; lifecycle runner not called |
| `STOPPED` | Exact status, first cause, cancellation reason, and same `fault_details` mapping | No observer; lifecycle runner not called |
| Insufficient two-slot pool | `FAILED` / `INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL`, zero slots, no selection batch | No observer; no lifecycle steps or selection items |
| Zero-origin / zero-slot activation | Zero activated slots and `lifecycle_started=False` | No lifecycle Scheduler work |
| Captured SHARED failure | `FAILED` / `SHARED_FAILURE`, cancellation `SHARED_FAILURE`, captured first failure/stage/claim/rollback `fault_details` preserved through the driver | No observer; no lifecycle; helper successfully preserved and inspected a closed disposable database |

The non-completed return occurs before database capture, batch materialization,
accountable work projection, stage sealing, and lifecycle invocation. It
therefore cannot create a retry, restart, resume, or successor. Focused
accounting and wiring tests also retain the explicit
`no_retry_restart_resume_successor` gate, and the evidence helper artifact
contract recorded zero retries, restarts, and successors.

## 6. Cancellation and `fault_details` preservation

The proof confirms two preservation levels:

- `ActivationResult` returns the activation's original terminal status, first
  terminal cause, optional cancellation reason, and original `fault_details`
  mapping;
- the non-started lifecycle projection repeats the exact first cause and copies
  cancellation and failure details without replacing the activation result.

The dedicated diagnostic case preserved:

- first failure classification and sanitized exception;
- exact discovery stage, batch, work, Scheduler job, expected lock owner, and
  claim result;
- transaction-local pre-rollback visibility;
- rollback start/completion;
- secondary failures separately from the immutable first failure.

## 7. Successful two-slot observer evidence

The completed-path integration and explicit order probe proved:

- exactly two real activated slots;
- exactly one `DISCOVERY_SELECTION_TERMINAL` callback;
- a non-empty `scheduler_work_identities` collection;
- every observed identity had a positive durable Scheduler job id, non-empty
  deterministic stage id, non-empty target identity, and non-empty work scope;
- callback order was exactly
  `DISCOVERY_SELECTION_TERMINAL` then `LIFECYCLE_START`;
- lifecycle targeted only the two activated identities and did not reselect.

No empty or synthetic identity was accepted as successful stage evidence.

## 8. Strict accounting result

The selected accounting regression passed, preserving rejection of absent,
empty, malformed, duplicate, and identity-mismatched evidence while retaining
the explicit pre-operation no-work contract.

The separate exact probe deliberately sealed a completed
`DISCOVERY_SELECTION_SCHEDULER` stage with empty transport, Scheduler,
reservation, and validation evidence. It failed closed with exactly:

```text
SIX_UNIT_STAGE_EVIDENCE_MALFORMED:EMPTY_STARTED_STAGE_EVIDENCE
```

The accounting owner, six-unit model, stage weights, reconstruction law, and
acceptance gate were not modified.

## 9. Claim-at-work-start and Scheduler invariants

The nine-test claim module and six subtests passed. They prove:

- the exact linked discovery job is claimed;
- an unrelated pending job is not claimed or changed;
- real Scheduler owner observations occur in order:
  `SCHEDULER_ENQUEUE` -> `SCHEDULER_CLAIM` -> `SCHEDULER_TERMINAL`;
- the job is `RUNNING` with deterministic lock owner, `locked_at`, and
  `started_at` before work insertion;
- work cannot be inserted before successful claim;
- not-found, not-due, already-owned, and identity-mismatch cases fail closed;
- claim-then-insert failure clears the owned lock;
- success, failure, cancellation, reconcile, and repeated terminalization remain
  idempotent;
- lifecycle exact-id claim remains isolated from discovery claim ownership.

All transitions came from committed Scheduler owners. No synthetic
`SCHEDULER_CLAIM`, raw Scheduler SQL transition, alternate-job claim, accounting
weakening, or terminal-time claim was introduced.

## 10. Failure evidence-helper reachability

The corrected disposable helper probe used the dedicated shared-failure
diagnostic seam to produce a real failed activation result with populated
`fault_details`, passed that result through `OriginToLifecycleCampaignDriver`,
then invoked `preserve_failed_offline_composition_evidence` from the returned
failure mapping after closing the database owner.

The helper created its execution-scoped JSON and database copy in a disposable
temporary directory, reported `PRAGMA integrity_check = ok`, reported an empty
foreign-key check, and completed before automatic temporary cleanup. This proves
the helper is reachable once the repaired driver returns the failed activation.
It is not a substitute for the forbidden exact public-composition execution.

## 11. No retry, restart, or successor

Failure and zero-slot paths returned synchronously without calling the lifecycle
runner. No test or probe invoked a retry, rerun, resume, restart, recovery, or
successor owner. No scheduler identity was invented to compensate for absent
work. Directly affected full-run tests continue to fail closed when retry or
lock state is introduced deliberately.

## 12. Zero-network and locked-capability boundary

All tests and probes used disposable databases, frozen clocks/transports,
dependency-injected fixture adapters, and proof-local owners. No operational
Source Governor command, provider, RPC, WebSocket, wallet, or external network
transport was configured or called. The success integration's snapshot and
context sources were fixture adapters; the shared-failure probe used the
dedicated deterministic diagnostic seam.

The directly affected regressions also proved zero forbidden deltas for
retrieval and financial tables. No retrieval, paper-decision, position, trade,
paper-trade-audit, or PnL path was activated. This is an injected-transport
boundary, not packet-level host monitoring, and it makes no broader host-wide
network claim.

## 13. Python compilation and repository checks

Compilation passed for the covered owners and tests:

```text
PYTHONPYCACHEPREFIX=/private/tmp/mp-origin-driver-proof-pycache-3f1be84 \
  .venv/bin/python -m py_compile \
  src/printer_v1/operator_cli/origin_lifecycle_campaign.py \
  src/printer_v1/operator_cli/offline_shared_failure_evidence.py \
  src/printer_v1/discovery/combined_executor.py \
  src/printer_v1/sources/campaign_six_unit_accounting.py \
  src/printer_v1/operator_cli/campaign_full_run_accounting.py \
  tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py \
  tests/test_v2_9_8b_shared_failure_evidence_capture.py \
  tests/test_v2_9_8b_discovery_scheduler_claim_at_work_start.py \
  tests/test_v2_9_8b_full_run_wiring_integration.py \
  tests/test_v2_9_8b_full_run_accounting_semantics_correction.py \
  tests/test_v2_9_8b_terminal_safety_accounting_finalization.py
```

`git diff --check` and final status checks are required after this report is
written and before its sole-file commit.

## 14. Money-usefulness contribution

The repair proof protects money-usefulness by preserving the truthful reason
that no two-token lifecycle began. It prevents an empty accountable stage from
masking discovery failure, prevents synthetic work from greening campaign
accounting, and keeps captured first-cause evidence available for later corpus
quality and campaign-acceptance review. This improves the reliability of future
paper-only memory growth; it makes no profit claim and unlocks no financial
capability.

## 15. What is improved

- Failed and otherwise non-completed activation is terminally classified before
  stage observation.
- Cancellation and diagnostic `fault_details` reach the caller unchanged.
- The failure-only evidence helper is reachable from a returned captured
  failure.
- Successful observation is restricted to a real completed two-slot handoff.
- Observer-before-lifecycle ordering is deterministic and proven.
- Strict accounting and real Scheduler transition ownership remain intact.
- No retry, restart, resume, successor, or synthetic work is created.

## 16. What remains locked

- the exact public composition in this lane;
- any retry or comparison execution;
- fresh authorization or reuse of consumed authorization;
- live/operational Source Governor, Central Scheduler, discovery, Memory
  Factory, or campaign execution;
- provider, RPC, or WebSocket contact;
- authoritative database mutation;
- memory generation, promotion, or longer-window activation;
- retrieval and paper decisions;
- BUY, SELL, HOLD, positions, trade events, paper trade audits, and PnL;
- wallets, private keys, signing, execution, and real funds;
- paid APIs, scoring, ranking, confidence, weighted logic, embeddings, and
  vectors.

Closeout remains prohibited until the later exact public-composition proof
passes.

## 17. Authorization and preserved state

`V2_9_8B_WINDOW_15M_AUTH_20260802T210122Z` remains consumed and permanently
non-reusable. This lane issued, refreshed, applied, and consumed no authorization.

The authoritative database was not opened or mutated. Only disposable test
databases were used. `/private/tmp/mp-preclaim` remains detached and clean at
`8fb4256c70d4e81660c177238253322cb37ae947`.

## 18. Tests and operations not run

- broad or full pytest;
- the exact public-composition test;
- any live, operational, provider, RPC, WebSocket, Source Governor, Central
  Scheduler, Memory Factory, campaign, recovery, or comparison command;
- any authoritative-database command;
- any retrieval, decision, position, trade, audit, PnL, wallet, or financial
  operation.

## 19. Functionality Risks / Setbacks / Efficiency Blockers

| Area | Finding |
| --- | --- |
| Functionality risk | This focused proof establishes the repaired owner boundary, but the exact public composition remains unexecuted by design |
| Product-proof blocker | Public coordinator-to-owner-to-driver-to-factory composition still requires its separately permitted one-time offline proof |
| Underlying failure risk | The repair preserves the underlying activation cause; it does not reclassify or repair whatever discovery cause may be returned |
| Evidence boundary | Zero-network proof is based on frozen/injected transports, not host-wide packet capture |
| Accounting risk | Strict empty-stage rejection remains intentionally fail-closed; any future identity omission will still block |
| Scheduler risk | Real claim ownership remains required; synthetic transition injection is still prohibited |
| Documentation gap | No standalone origin-driver audit/design files exist at this baseline; the tracked bounded-proof finding and implementation report preserve the accepted ordering defect and repair |
| Proof-harness setback | One initial supplemental probe used the wrong fixture for populated `fault_details`; the dedicated diagnostic fixture corrected the assumption and passed without product changes |
| Worktree hygiene | Pre-existing untracked operator artifacts remain present and must continue to be preserved |
| Efficiency blocker | Broad suites or another composition run would add cost without permission; the next lane alone may run the exact composition once |

## 20. Files changed

Only this proof report:

```text
docs/printer-v1-v2-9-8b-post-rollover-2-origin-driver-activation-failure-propagation-focused-deterministic-proof.md
```

No production source, test, accounting, Scheduler, Source Governor, schema,
migration, authorization, or operator artifact was modified.

## 21. Exact next lane

```text
V2-9.8B Post-Rollover-2 Exact Public Composition Post-Origin-Driver Repair Bounded Offline Proof
```

That later lane may execute the exact public composition once. It may not reuse
the consumed authorization or imply closeout before its own proof passes.

## 22. Final statement

The focused deterministic evidence proves faithful activation-failure
propagation, real successful-stage observation, strict accounting, exact
Scheduler claim ownership, failure-helper reachability, no lifecycle on failed
activation, no retry/successor, and zero live-network/financial activation.

Verdict:

`V2_9_8B_POST_ROLLOVER_2_ORIGIN_DRIVER_ACTIVATION_FAILURE_PROPAGATION_FOCUSED_DETERMINISTIC_PROOF_PASS`
