# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Holder Fixture Measured-Identity Repair Closeout

Date: 2026-08-07

Verdict: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_HOLDER_FIXTURE_MEASURED_IDENTITY_REPAIR_OFFLINE_PASS`

Linear: `DTW-48`

## Lineage

- consumed post-DTW47 proof HEAD: `841f96634f4e7efa7fd70bef7fc3984f8279e746`
- audit: `adb2c4cc5bd7906b00b98535d1e5b504b6ec6e05`
- design: `675e3de9c5cb2c2d7aa064a3fb0014679a9c71f9`
- repair: `a54a80673f359d8e7e4db20b0c838d782f5ce699`

The consumed proof remains historical and is not rerunnable.

## Retained-run cause

Read-only inspection of the retained disposable proof DB established:

- integrity check `ok` and zero foreign-key violations;
- four governed GoPlus holder requests/responses were produced and were clean exact-target responses;
- the first three holder evidence rows recorded `underlying_operation_count=0`;
- the fourth governed request/response survived its separately committed Source-Governor write while the holder-side mutation rolled back when later stage sealing failed;
- the holder campaign ledger remained at 16 measured transports, fully explained by pre-holder discovery/verification/market work;
- the C8 GoPlus fixture ignored the `measured_transport_ledger` passed by the real holder funnel;
- production GoPlus already has the correct one-transport measured identity contract.

Classification: `CHECKPOINT8_HOLDER_FIXTURE_MEASURED_TRANSPORT_IDENTITY_MISSING`.

## Deterministic RED

At design HEAD `675e3de9c5cb2c2d7aa064a3fb0014679a9c71f9`, the approved offline RED proved:

- source status `COMPLETE`;
- data quality `CLEAN_DATA`;
- exact returned mint;
- holder-ledger transport count `0`;
- payload transport-identity count `0`;
- payload transport operations used `None`;
- network attempts `0`;
- `DTW48_GOPLUS_FIXTURE_MEASURED_IDENTITY_RED_CONFIRMED`;
- no controlling sentinel and no controlling proof.

## Implementation

Repair commit `a54a80673f359d8e7e4db20b0c838d782f5ce699` changed exactly:

1. `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
2. `src/printer_v1/operator_cli/checkpoint8_real_consumer_compatibility.py`
3. `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`

The repair:

- replaces the generic C8 GoPlus fixture adapter with the real GoPlus adapter shape backed by a deterministic local transport;
- requires an exact known fixture mint;
- reuses the caller-provided holder measured ledger;
- records exactly one `HOLDER_SAFETY / goplus / safety_reference / GET_TOKEN_SECURITY` transport identity per actual fixture execution;
- writes the same identity to the normalized payload with `transport_operations_used=1` and `underlying_operation_count=1`;
- preserves the healthy deterministic holder payload;
- makes the real-consumer compatibility gate require exactly one ledger identity, exactly one payload identity, canonical parity, exact target mint, and exact holder identity fields;
- adds an exact governed GoPlus holder regression under the network tripwire.

No production GoPlus, holder-budget, six-unit, Source Governor, Scheduler, provider, memory, retrieval, decision, or trading file changed.

## Offline GREEN

Minimum sufficient verification passed:

- changed-file `py_compile`: PASS;
- exact GoPlus holder identity regression: `1 passed`;
- full real-consumer compatibility file: `9 passed`;
- full focused Checkpoint 8 suite: `100 passed`;
- `git diff --check`: PASS;
- exact three-file manifest: PASS;
- provider/network execution: NONE;
- controlling proof run: NONE.

No broad repository suite was required by the approved risk-based verification plan.

## Money-usefulness contribution

The repair restores truthful holder-source accounting so clean holder evidence can progress toward ordinary clean 15m memory instead of being falsely represented as holder no-work.

## What this lane improves

- C8 holder request/response/transport parity;
- holder-stage measured identity completeness;
- exact mint targeting for fixture holder evidence;
- real-consumer verification of ledger/payload identity parity;
- six-unit evidence readiness without weakening six-unit validation.

## What this lane still does not unlock

This closeout does not authorize or unlock:

- another C8 controlling proof;
- operational WINDOW_15M memory growth;
- provider/network access;
- authoritative DB use;
- WINDOW_1H+;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, paper trade audits, or PnL.

## Proof required before Checkpoint 8 completion

Checkpoint 8 still requires a separately authorized fresh one-shot controlling proof on a newly reviewed immutable HEAD. A PASS candidate must then undergo independent frozen-evidence inspection against the full C8 acceptance law before any Checkpoint 8 closeout.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Historical consumed attempts:** remain non-rerunnable and must never be reused.
2. **Fixture/production drift:** reduced by using the real GoPlus adapter shape and exact production-equivalent identity fields, but future fixture changes still require compatibility coverage.
3. **Double counting risk:** bounded by one identity per one governed fixture execution and canonical ledger/payload parity checks.
4. **Genuine later-stage zero-transport semantics:** remains a separate latent question; it did not cause the consumed proof and was intentionally not used to weaken `PRE_OPERATION_NO_WORK` validation.
5. **C8 remains unproven end-to-end:** this offline repair removes the known holder-fixture blocker only.

No new Checkpoint 8 controlling proof is authorized by this closeout.
