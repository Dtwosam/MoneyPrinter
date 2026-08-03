# Printer V1 V2-9.8B Post-Rollover-2 End-to-End Pre-Lifecycle Failure Propagation Focused Proof

Date: 2026-08-03

Baseline: `2e11f1304c3ba7151ef21f27e0db4fec88890ec1`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_END_TO_END_PRE_LIFECYCLE_FAILURE_PROPAGATION_FOCUSED_PROOF_PASS`

The complete focused deterministic gate passed. The exact public composition
was not executed by this proof.

## Final focused result

One deduplicated focused command ran 13 directly affected modules:

```text
tests/test_v2_9_8b_end_to_end_pre_lifecycle_failure_propagation.py
tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py
tests/test_v2_9_8b_shared_failure_evidence_capture.py
tests/test_v2_9_8b_token_slot_id_projection_repair.py
tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py
tests/test_v2_9_8b_discovery_scheduler_claim_at_work_start.py
tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py
tests/test_v2_9_7e_47_lifecycle_and_clean_memory_repair.py
tests/test_phase3_scheduler_resource_governor.py
tests/test_v2_9_8b_terminal_safety_accounting_finalization.py
tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py
tests/test_v2_9_8b_full_run_wiring_integration.py
tests/test_v2_9_8b_full_run_accounting_semantics_correction.py
```

Result:

```text
243 passed, 36 subtests passed in 224.90s
```

No broad/full pytest ran.

## Required contract coverage

| # | Requirement | Proof |
| ---: | --- | --- |
| 1 | Successful two-slot activation | origin integration, authoritative owner, token-slot projection and full-run wiring PASS |
| 2 | Failed activation before stage | new no-stage/public coordinator cases PASS |
| 3 | Zero-slot failure | exact terminal/no lifecycle/no accounting case PASS |
| 4 | Insufficient eligible pool | real origin driver seals truthful failed Scheduler stage; no lifecycle PASS |
| 5 | SHARED failure | exact status/cancellation/fault preservation and helper PASS |
| 6 | Explicit cancellation | before-stage exact cancellation and public propagation PASS |
| 7 | Blocked/stopped terminal | blocked and lease-unconfirmed categorical cases PASS |
| 8 | No observer invocation | no-stage decision and empty evidence tuple PASS |
| 9 | Observer returns real evidence | strict failed-stage accounting and report PASS |
| 10 | Observer returns `None` | notification state recorded; no sentinel constructed PASS |
| 11 | Observer list contains `None` | collection rejected secondarily; original terminal primary PASS |
| 12 | Claimed stage with empty evidence | strict blocked result PASS |
| 13 | Claimed stage with malformed evidence | strict blocked result PASS |
| 14 | Accounting remains strict | terminal safety/accounting enforcement suites PASS |
| 15 | Failure helper on returned failure | generic and SHARED returned failures PASS |
| 16 | DB copy survives cleanup | source temporary root deleted; evidence DB and JSON survive PASS |
| 17 | Integrity/FK | preserved copy `ok` / empty FK list PASS |
| 18 | First failure primary across later faults | cleanup, observer/accounting and helper-write secondary tests PASS |
| 19 | Claim-at-work-start exact | discovery claim suite PASS |
| 20 | No unrelated Scheduler claim | claim isolation and unrelated-job tests PASS |
| 21 | No lifecycle after failed pre-lifecycle outcome | origin integration PASS |
| 22 | No retry/restart/successor | result/public/helper assertions PASS |
| 23 | Locked capabilities remain zero | full-run/token-slot/terminal regression assertions PASS |

## Static verification

Python compilation passed for every changed Python source and test file.

`git diff --check` passed.

An exact placeholder scan found no production `stage_evidences=(None,)`,
`stage_evidences=[None]`, or equivalent construction in the changed boundary.

Exact changed-file review confirmed:

- no six-unit accounting-law change;
- no Scheduler or Source Governor change;
- no schema/migration change;
- no synthetic identity/transition;
- no retry/restart/resume/successor;
- no downstream capability change;
- no authoritative DB or network operation;
- no modification of `/private/tmp/mp-preclaim`.

## Preliminary test correction

An initial new test used an unsealed aggregate directly against the strict stage
owner and failed with `MISSING_STAGE_ID`. This was classified
`TEST_HARNESS_DEFECT`; the fixture was corrected to use the canonical stage
sealer. The corrected focused set passed. No product law was weakened.

## Money-usefulness contribution

The proof shows Printer can preserve the true reason acquisition did not reach
memory lifecycle while still strictly accounting real claimed work. That is a
necessary trust boundary for repeatable money-useful memory growth.

## What improves

- Deterministic public failure propagation across all pre-lifecycle outcomes.
- Complete first-cause/cancellation/fault evidence retention.
- Strict claimed-stage evidence enforcement without no-stage false positives.
- Failure database preservation before cleanup.

## What remains locked

The exact public composition remains the next and only allowed execution.
Live/authoritative operation, authorization reuse, provider/RPC/WebSocket work,
longer windows, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits,
PnL, wallets, signing, paid APIs, scoring/ranking/confidence/weights,
embeddings/vectors, retries and successors remain locked.

## Required proof

Exactly one execution of the named exact public composition node is now allowed.
It may not be rerun, compared, restarted, resumed, or repaired afterward.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status |
| --- | --- |
| Underlying historical activation failure | Still unknown until the one exact composition returns/captures it |
| Claimed work rolled back before seal | Correctly remains accounting-blocked with original cause primary |
| Frozen transport boundary | Not packet-level proof; exact harness retains patched/fake boundary |
| Exact proof failure | Must stop with preserved root cause; no post-composition fix cycle |
| Runtime cost | Focused scope only; no broad suite or live source cost |
