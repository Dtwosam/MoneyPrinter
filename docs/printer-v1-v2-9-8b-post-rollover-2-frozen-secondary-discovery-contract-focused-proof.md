# Printer V1 V2-9.8B Post-Rollover-2 Frozen Secondary Discovery Contract Focused Proof

Date: 2026-08-03

Baseline: `63799afa600ed490de2d74fbe1c331efb7d23774`

## Verdict

`V2_9_8B_POST_ROLLOVER_2_FROZEN_SECONDARY_CONTRACT_FOCUSED_PROOF_PASS`

The complete focused deterministic gate passed. The exact public-composition
node was not executed during this phase.

## Final focused command and result

The deduplicated command ran fourteen directly relevant modules:

```text
tests/test_v2_9_8b_frozen_secondary_discovery_contract.py
tests/test_v2_9_7d_7b_4b_secondary_discovery_adapters.py
tests/test_v2_9_7d_7b_4d_combined_discovery_executor.py
tests/test_v2_9_7e_11_authoritative_live_operational_campaign.py
tests/test_v2_9_8b_end_to_end_pre_lifecycle_failure_propagation.py
tests/test_v2_9_8b_discovery_scheduler_claim_at_work_start.py
tests/test_v2_9_7e_8_origin_to_lifecycle_integration.py
tests/test_v2_9_8b_shared_failure_evidence_capture.py
tests/test_v2_9_8b_token_slot_id_projection_repair.py
tests/test_v2_9_8b_terminal_safety_accounting_finalization.py
tests/test_v2_9_8b_campaign_accounting_terminal_enforcement.py
tests/test_v2_9_8b_full_run_wiring_integration.py
tests/test_v2_9_8b_full_run_accounting_semantics_correction.py
tests/test_phase3_scheduler_resource_governor.py
```

Result:

```text
224 passed, 9 subtests passed in 69.96s
```

No broad/full pytest and no exact public composition ran.

## Required coverage

| # | Requirement | Result |
| ---: | --- | --- |
| 1 | Lawful Gecko trending response | PASS, exact JSON:API pool identity |
| 2 | Lawful Gecko active response | PASS, exact pool/mint and positive m5 activity |
| 3 | Empty lawful response | PASS, trending `data=[]` returns zero observations |
| 4 | Missing pool object | PASS, exact `MALFORMED_RESPONSE` detail |
| 5 | Malformed pool object | PASS, missing attributes rejected |
| 6 | Wrong response envelope | PASS, duplicate/body wrapper rejected |
| 7 | Stale contract version | PASS, frozen builder rejects before transport |
| 8 | Fixture transport wrapping | PASS, decoded body passed once; unmatched URL is named failure |
| 9 | Adapter decoding | PASS, live adapter emits governed facts |
| 10 | Normalization | PASS, adopted fields and stripping retained |
| 11 | Candidate extraction | PASS, combined executor completes with exact identities |
| 12 | Exact error classification | PASS, provider failure is `MALFORMED_RESPONSE` |
| 13 | Transaction rollback | PASS, existing SHARED diagnostic/rollback regression unchanged |
| 14 | Exact Scheduler claim | PASS, claim-at-work-start suite |
| 15 | Attempt-evidence preservation | PASS, JSON/copy and pre-rollback diagnostic suites |
| 16 | No synthetic terminal transition | PASS, rollback evidence stays transaction-local; repaired local failure uses real Scheduler owner |
| 17 | Strict claimed/missing accounting | PASS, accounting enforcement and pre-lifecycle suites |
| 18 | End-to-end pre-lifecycle regression | PASS |
| 19 | Exact fixture setup without exact node | PASS, frozen Pump IDs feed live adapter and real normalizer; version recorded |

The provider-local malformed-response proof also confirms one real Scheduler
job, terminal `FAILED`, no duplicate job, exact source failure, two lawful
directly selected slots, and no shared rollback.

## Static verification

- Python compilation passed for every changed Python source and test file.
- `git diff --check` passed.
- Exact changed-file review found no modification to six-unit accounting,
  Scheduler implementation/parity law, Source Governor, schemas, migrations,
  claimed-stage evidence, retry/restart/successor, or capability locks.
- The exact test file was inspected and compiled but its exact node was not run.
- `/private/tmp/mp-preclaim` and preserved operator evidence were untouched.

## Money-usefulness contribution

The proof shows Printer can reject malformed optional provider data without
discarding sound direct-origin acquisition, and can distinguish a lawful empty
feed from a missing fixture. This improves the reliability and auditability of
future money-useful memory inputs without expanding financial authority.

## What improves

- Producer and consumer share one pinned envelope contract.
- Missing fixtures and malformed responses have deterministic classifications.
- Secondary failure isolation and Scheduler terminal parity are proven.
- The exact success fixture is ready without bypassing real parsing.

## What remains locked

The exact composition is the only next authorized execution. Live providers,
authorization reuse, authoritative database, retries/restarts/successors,
longer windows, retrieval, decisions, BUY/SELL/HOLD, positions, trades, audits,
PnL, wallets, signing, funds, paid APIs, scoring/ranking/confidence/weights,
embeddings, and vectors remain locked.

## Proof required

After the repair commit, exactly one execution of the named exact offline public
composition is permitted. It may not be retried, rerun, compared, repaired,
resumed, restarted, or succeeded by another run in this lane.

## Functionality Risks / Setbacks / Efficiency Blockers

| Item | Status |
| --- | --- |
| Application-level fake transport boundary | Deterministic and patched, but not packet capture |
| Provider-local work terminal is FAILED | Intentional; valid peer/direct facts survive without calling the bad response successful |
| Future schema drift | Remains fail-closed under the pinned contract |
| Exact composition outcome | Still unknown until the single authorized execution |
| Exact failure | Must preserve evidence and stop; no post-composition repair cycle |
