# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Direct Pump Evidence Bridge Repair Design V3

Date: 2026-08-07

Status: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_DIRECT_PUMP_EVIDENCE_BRIDGE_REPAIR_V3_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

Prior design HEAD: `2d8d172513faa4835974a2198469a6ae6d34618d`
Linear: `DTW-47`

## Why V3 is required

The approved V2 implementation passed the focused real-consumer compatibility suite (`8 passed`) and nearest Eligible Token Supply contract suite (`26 passed`), then the full focused Checkpoint 8 suite stopped with four failures.

All four failures are stale proof-test expectations that still hardcode the pre-permanent-supply two-fixture-candidate model:

- `tests/test_v2_9_8b_window_15m_checkpoint8_blocked_proof_repair.py` expects two restored migration fixture signatures/mints/pools.
- `tests/test_v2_9_8b_window_15m_checkpoint8_fixture_response_semantics_gate.py` expects two fixture candidates, two Pump origin rows, and pre-run fixture candidate count two.

The revised permanent-supply contract deliberately requires four lawful reserve candidates while canonical neutral selection and final lifecycle remain exactly two tokens. These failures therefore prove an inseparable proof-test dependency outside the prior four-file manifest; they do not justify production-policy weakening.

No controlling proof is authorized by this design.

## Approved implementation surface

Exactly these six files may change:

1. `src/printer_v1/discovery/eligible_token_supply.py`
2. `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
3. `src/printer_v1/operator_cli/checkpoint8_real_consumer_compatibility.py`
4. `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`
5. `tests/test_v2_9_8b_window_15m_checkpoint8_blocked_proof_repair.py`
6. `tests/test_v2_9_8b_window_15m_checkpoint8_fixture_response_semantics_gate.py`

No other production, Scheduler, Source Governor, admission, memory, retrieval, decision, position, trade, audit, PnL, workflow, migration, provider, or runtime file is approved.

## Required test-only corrections

Update only stale reserve-depth expectations from 2 to 4 in the two newly approved test files.

Where useful, rename test functions/descriptions from `two_candidates` to `four_reserve_candidates` so the contract is explicit.

Do not change assertions that prove:

- exact 20-label composition coverage;
- fixture outputs are payloads rather than fixture self objects;
- provider fallback remains false;
- unready semantics block execution;
- Pump/migration adapter contracts remain real-consumer compatible;
- final selection/lifecycle remains exactly two tokens.

## Production repairs retained from V2

The implementation remains required to:

1. carry only existing exact `direct_pump_evidence` across the permanent exact-mint bridge;
2. count direct migration protocol-confirmation stage usage from existing exact `source_request_coverage` rows, not `source_requests - 1`;
3. keep the existing stage reservation unchanged;
4. use four deterministic lawful Pump/PumpSwap C8 reserve candidates;
5. make lifecycle market fixtures exact-target aware and fail closed on unknown/conflicting mint+pool identities;
6. preserve canonical neutral two-token selection.

No score/rank/confidence/weight system may be introduced.

## Minimum sufficient GREEN

- prior deterministic REDs remain the implementation evidence:
  - `DIRECT_PUMP_EVIDENCE_MISSING` with zero network;
  - four-reserve false-shortage RED with 9 direct-discovery requests, required capacity 4, 19 flat operations remaining, and zero network;
- `py_compile` all changed Python files;
- `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`;
- `tests/test_v2_9_8b_21_eligible_token_supply_architecture.py`;
- full focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py`;
- explicit zero-network tripwire regressions;
- `git diff --check`;
- exact six-file changed manifest.

No broad repository suite is required.

## Stop conditions

Stop and return to audit/design if:

- any failure remains after the six-file implementation;
- any seventh file is required;
- production admission or four-reserve law would need weakening;
- stage ceilings would need raising without separate proof/design;
- provider/network/runtime/authoritative DB access would be required.

## Money-usefulness contribution

This correction keeps the proof model aligned with the resilient four-deep eligible reserve while preserving exactly two active learning slots. It prevents stale proof assertions from forcing Printer back to an under-reserved supply model.

## What this improves

- exact Pump evidence continuity;
- truthful direct-migration stage accounting;
- four-reserve C8 realism;
- exact-target lifecycle fixture correctness;
- full focused C8 regression coherence.

## What this still does not unlock

- another Checkpoint 8 controlling proof;
- operational WINDOW_15M memory growth;
- provider/network access;
- authoritative DB use;
- WINDOW_1H+;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions/trades/audits/PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Stale tests mistaken for production regression:** mitigated by preserving all non-count behavioral assertions and changing only reserve-depth expectations.
2. **Four reserve mistaken for four active tokens:** final canonical neutral selection remains exactly two.
3. **Budget ceiling inflation:** prohibited; exact coverage attribution is used instead.
4. **Evidence reconstruction:** prohibited; only current-owner `direct_pump_evidence` is carried.
5. **Scope creep:** six exact files only; any seventh-file need stops implementation.
