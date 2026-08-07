# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-49 Holder Coverage Transport-Identity Projection Repair Design V2

Date: 2026-08-07

Prior design: `d12f97f7285e7668330d4f5bd63abe338f4f4ab0`
Linear: `DTW-49`

Status:

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW49_HOLDER_COVERAGE_TRANSPORT_IDENTITY_PROJECTION_REPAIR_V2_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

## Refinement

The production decision is unchanged. V2 changes only the focused test location so the DTW-49 contract is isolated rather than expanding the existing broad real-consumer compatibility file.

Exactly these two implementation files are approved:

1. `src/printer_v1/operator_cli/holder_reliability_budget_control.py`
2. `tests/test_v2_9_8b_window_15m_checkpoint8_holder_coverage_transport_identity.py`

The new test filename remains inside the existing `tests/test_v2_9_8b_window_15m_checkpoint8_*.py` focused gate.

No third implementation file is approved.

## Production contract

Unchanged from the prior design:

- preserve exact per-request `transport_identity_keys` from the real normalized holder execution payload;
- never derive a key from a count;
- explicit empty key list for lawful zero transport;
- count/key parity in exact mode;
- existing source/request/target correspondence and duplicate checks remain fail-closed;
- no budget, six-unit, Source Governor, Scheduler, provider, memory, schema, retrieval, or trading change.

## Focused RED/GREEN contract

The dedicated C8 regression must exercise the real holder persistence carrier with a deterministic execution shape containing one valid measured `HOLDER_SAFETY` identity.

RED at the V2 design baseline must show that the returned holder coverage row declares one transport but omits exact keys, causing exact campaign transport-manifest validation to block.

GREEN must prove:

- exactly one coverage row for the exact governed request;
- `transport_identity_count == 1`;
- exactly one canonical `transport_identity_key`;
- key parity with the normalized payload identity;
- exact holder source/request/target ownership;
- campaign transport identity manifest status `OK`;
- lawful zero-transport case exposes `transport_identity_keys=[]`;
- zero provider/network execution.

Then require:

- changed-file `py_compile`;
- the dedicated DTW-49 test file;
- existing C8 real-consumer compatibility file;
- complete `tests/test_v2_9_8b_window_15m_checkpoint8_*.py` suite;
- `git diff --check`;
- exact two-file manifest.

No broad repository suite is required.

## Stop conditions and locks

All prior design stop conditions and V1 capability locks remain unchanged. No Checkpoint 8 controlling proof is authorized by this design.

## Money-usefulness contribution

The dedicated regression makes the holder provenance carrier independently reviewable and prevents future fixture/accounting changes from silently dropping per-request transport ownership before memory lifecycle admission.

## Functionality Risks / Setbacks / Efficiency Blockers

- Dedicated testing must not become a duplicate production path; it tests the canonical holder owner only.
- Partial/blocked holder-key preservation remains out of scope unless the focused test proves it is required.
- Checkpoint 8 remains open and unproven end-to-end until a later separately authorized one-shot proof passes the full acceptance law.
