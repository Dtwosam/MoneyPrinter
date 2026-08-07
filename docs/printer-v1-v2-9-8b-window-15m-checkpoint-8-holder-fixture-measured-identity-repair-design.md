# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Holder Fixture Measured-Identity Repair Design

Date: 2026-08-07

Status: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_HOLDER_FIXTURE_MEASURED_IDENTITY_REPAIR_APPROVED_FOR_OFFLINE_IMPLEMENTATION_ONLY`

Audit HEAD: `adb2c4cc5bd7906b00b98535d1e5b504b6ec6e05`
Linear: `DTW-48`

## Decision

Repair only the C8 GoPlus fixture measurement contract.

The retained proof proved four clean governed GoPlus holder executions but zero holder measured transport identities. Production already supplies the correct measurement contract through `build_goplus_token_safety_transport()`; no production holder, budget, Source Governor, Scheduler, or six-unit change is justified.

## Approved implementation surface

Exactly these three files may change:

1. `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
2. `src/printer_v1/operator_cli/checkpoint8_real_consumer_compatibility.py`
3. `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`

No other file is approved.

## Required C8 GoPlus fixture behavior

When `lifecycle.context_adapter_factories.goplus` is called by the real holder funnel:

1. require/use the supplied exact `token_mint`;
2. accept the supplied `measured_transport_ledger` without creating a second owner;
3. return the real GoPlus adapter shape, backed only by a deterministic local fixture transport;
4. on adapter execution, create exactly one truthful `TransportOperationIdentity` matching the production GoPlus holder contract:
   - stage `HOLDER_SAFETY`
   - source `goplus`
   - endpoint owner `api.gopluslabs.io`
   - governed request kind `safety_reference`
   - method/endpoint `GET_TOKEN_SECURITY`
   - within-request ordinal `1`
   - target category `TOKEN_MINT`
   - target identity equal to the requested mint
   - positive deterministic response byte count
   - normalized rows `1`
   - result `COMPLETED`
5. record that exact identity into the supplied measured ledger when one is provided;
6. put the same identity into `transport_operation_identities` and set `transport_operations_used=1` in the fixture payload;
7. preserve the existing healthy deterministic GoPlus safety payload and exact-target behavior;
8. perform zero network/provider work.

No identity may be fabricated without one actual governed fixture adapter execution.

## Compatibility gate repair

The C8 real-consumer compatibility checker must no longer accept the GoPlus lifecycle route merely because the normalized source result is clean.

For `preclose_goplus_safety`, it must:

- create a fresh `MeasuredTransportLedger` with deterministic campaign/run/cycle identity;
- pass that ledger through the real factory call shape;
- execute the returned adapter through the existing governed-context contract used by the matrix;
- require exactly one ledger transport identity;
- require exactly one payload transport identity;
- require canonical identity parity between ledger and payload;
- require exact `HOLDER_SAFETY / goplus / safety_reference / requested mint` fields;
- preserve the existing accepted-source-result requirement.

The remaining 19 composition labels keep their current behavior.

## Deterministic RED

Before implementation, reproduce the exact contract gap offline:

- fresh disposable C8 preparation;
- materialize the full fixture composition;
- select the C8 GoPlus lifecycle factory;
- pass a fresh holder `MeasuredTransportLedger` through the real factory call shape;
- execute one governed GoPlus `safety_reference` request against the disposable DB;
- prove the source response is CLEAN/exact-target while:
  - holder ledger transport count is `0`;
  - payload transport identity count is `0`;
- network tripwire remains `0`.

Expected RED classification:

`DTW48_GOPLUS_FIXTURE_MEASURED_IDENTITY_RED_CONFIRMED`

This RED does not claim a C8 controlling sentinel and is not a controlling proof.

## Minimum sufficient GREEN

After the three-file repair:

- changed-file `py_compile` PASS;
- same exact offline contract path proves:
  - CLEAN/exact-target GoPlus response;
  - holder ledger transport count exactly `1`;
  - payload identity count exactly `1`;
  - canonical ledger/payload identity parity;
  - exact requested mint target;
  - zero network attempts;
- C8 real-consumer compatibility suite PASS;
- focused Eligible Token Supply architecture suite remains PASS only if touched transitively by the C8 fixture composition; otherwise no rerun is required;
- full focused `tests/test_v2_9_8b_window_15m_checkpoint8_*.py` PASS;
- `git diff --check` PASS;
- exact three-file changed manifest.

No broad repository suite is required.

## Explicit non-changes

Do not change:

- `src/printer_v1/sources/goplus.py`;
- `authoritative_live_operational_campaign.py`;
- `operational_memory_factory_command.py`;
- `campaign_six_unit_accounting.py`;
- holder ceilings/reservations;
- Source Governor or Central Scheduler;
- production provider behavior;
- admission rules;
- memory/retrieval/decision/trade code.

The latent question of how a genuine later holder stage with lawful zero transport should be represented is separate. It must not be used to weaken `PRE_OPERATION_NO_WORK` validation in this repair.

## Stop conditions

Stop and return to audit/design if:

- any production file becomes necessary;
- the repair requires changing six-unit validation;
- any identity would need to be synthesized without a fixture execution;
- any network/provider call is required;
- any fourth file is needed;
- focused GREEN still exposes a different holder-stage defect.

## Money-usefulness contribution

This restores truthful holder-source accounting so clean holder evidence can reach the ordinary 15m memory path without being falsely classified as no-work.

## What this improves

- exact holder measured-transport truth in C8;
- request/response/transport parity;
- six-unit holder-stage evidence completeness;
- real-consumer compatibility coverage for the measurement contract.

## What this still does not unlock

- another C8 controlling proof;
- operational WINDOW_15M memory growth;
- provider/network access;
- authoritative DB use;
- WINDOW_1H+;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions/trades/audits/PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

1. **Source-result-only compatibility:** repaired by requiring measured identity parity.
2. **Double counting:** prevented by exactly one identity per one governed GoPlus fixture execution.
3. **Target drift:** prevented by exact requested-mint identity checks.
4. **Production-policy weakening:** prohibited; proof-only scope.
5. **Latent genuine zero-work semantics:** explicitly deferred because it did not cause the consumed attempt.

No new Checkpoint 8 controlling proof is authorized by this design.
