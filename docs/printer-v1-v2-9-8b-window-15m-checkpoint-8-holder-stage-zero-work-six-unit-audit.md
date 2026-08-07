# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Holder-Stage Zero-Work Six-Unit Audit

Date: 2026-08-07

Status: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_HOLDER_STAGE_ZERO_WORK_AUDIT_COMPLETE`

Linear: `DTW-48`

Consumed proof:

- proof ID: `C8_REPROOF_AFTER_DTW47_20260807`
- immutable proof HEAD: `841f96634f4e7efa7fd70bef7fc3984f8279e746`
- sentinel claimed: true
- process exit code: 1
- first failure: `SIX_UNIT_STAGE_EVIDENCE_MALFORMED:PRE_OPERATION_NO_WORK_CONTRACT`
- no retry/rerun/resume/restart/successor authorized or performed

## Retained-proof findings

Read-only inspection of the retained disposable DB proved:

- `PRAGMA integrity_check = ok`
- zero foreign-key violations
- holder campaign ledger persisted with 15 governed requests, 16 underlying transport operations, 9 zero-transport validation operations, and the unchanged 2 + 4 snapshot reservations
- four holder maturation rows exist
- first three holder maturation rows reached `COMPLETED / EVIDENCE_EVALUATED`
- fourth holder maturation row remained `DUE` because the later stage-seal exception rolled back the holder-side transaction
- four governed GoPlus holder requests exist (`printer_source_requests` IDs 13–16)
- four clean GoPlus responses exist (`printer_source_responses` IDs 13–16)
- all four responses are exact-target, clean, healthy holder fixtures
- no source failures exist
- first three durable holder evidence-attempt rows have `underlying_operation_count = 0`
- the fourth source request/response survived because the Source-Governor request/response writes are separately committed; its holder evidence/maturation mutation did not survive the later exception

The 16 underlying transport operations in the holder campaign ledger are fully explained by pre-holder work:

- 1 DexScreener fresh-profile transport
- 1 direct migration signature-page transport
- 4 direct migration transaction transports
- 8 PumpSwap exact-verification transports (2 per four candidates)
- 1 GeckoTerminal fresh nomination transport
- 1 DexScreener mint-batch transport

Therefore holder safety added zero measured transport identities despite four actual governed holder source executions.

## Exact static cause

The real holder funnel calls the configured GoPlus factory with `measured_transport_ledger=holder_transport_ledger`.

The production GoPlus transport owner, `build_goplus_token_safety_transport()`, uses that ledger to record one exact `TransportOperationIdentity` with:

- stage `HOLDER_SAFETY`
- source `goplus`
- endpoint owner `api.gopluslabs.io`
- governed request kind `safety_reference`
- method/endpoint `GET_TOKEN_SECURITY`
- target category `TOKEN_MINT`
- exact target mint
- one measured transport operation

It also places the same transport identity and `transport_operations_used=1` into the returned payload.

The C8 fixture factory does not preserve this contract. Its `lifecycle.context_adapter_factories.goplus` route ignores the supplied `measured_transport_ledger` and returns a generic `build_fixture_source_adapter("goplus", fixture_payload=...)`. That generic fixture adapter returns the safety payload but records no measured transport identity.

As a result:

1. four real governed fixture source requests/responses occur;
2. the holder measured ledger remains empty;
3. holder persistence records zero underlying operation count;
4. `_seal_holder_stage()` sees no holder ledger transports and constructs `PRE_OPERATION_NO_WORK` evidence;
5. `CampaignSixUnitOwner` correctly rejects that evidence because earlier campaign stages have already been sealed.

## Classification

This consumed failure is classified as:

`CHECKPOINT8_HOLDER_FIXTURE_MEASURED_TRANSPORT_IDENTITY_MISSING`

It is not:

- holder budget exhaustion;
- maturation refusal;
- true holder no-work;
- provider failure;
- Source Governor failure;
- six-unit validation-policy defect;
- a reason to raise any budget or stage ceiling.

The later-stage `PRE_OPERATION_NO_WORK` incompatibility remains a latent fail-closed edge for genuine later-stage zero-work situations, but it is not the factual cause that should be repaired for this consumed C8 attempt. No six-unit validation weakening is justified.

## Why prior focused tests missed it

The C8 real-consumer compatibility matrix calls the lifecycle GoPlus factory and verifies only that the returned adapter produces an accepted normalized source result. It does not provide a measured holder ledger and does not assert that the factory records exactly one holder transport identity into that ledger or that the normalized payload carries the same identity.

Thus the fixture could be source-result compatible while still violating the holder-stage accounting contract.

## Required next lane

DTW-48 may proceed to design only.

The design should remain proof-only unless RED evidence demonstrates otherwise. It should require:

- C8 GoPlus fixture factory to honor the supplied `measured_transport_ledger`;
- exactly one truthful `HOLDER_SAFETY` measured identity per governed GoPlus fixture execution;
- identity payload/ledger parity;
- exact target mint binding;
- no fabricated source requests or transports;
- compatibility regression through the real holder factory call shape;
- deterministic zero-network RED/GREEN through the retained C8 fixture composition or equivalent disposable DB path;
- no change to holder budgets, six-unit validation, Source Governor, Scheduler, production provider transport, memory, or downstream capability locks.

No new Checkpoint 8 controlling proof is authorized by this audit.

## Money-usefulness contribution

Truthful holder-stage measured accounting is necessary before healthy holder evidence can safely support clean 15m memory. This repair prevents valid holder evidence from being misclassified as zero-work while preserving strict Source Governor and six-unit accounting.

## What this improves

- holder fixture transport identity truth;
- holder-stage six-unit evidence completeness;
- exact request/response/transport parity in C8;
- proof fidelity to the real production GoPlus holder boundary.

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

1. **Generic fixture success hiding missing measurement:** addressed by requiring ledger/payload identity parity.
2. **Fabricated accounting:** prohibited; each identity must correspond to one actual governed fixture execution.
3. **Budget inflation:** prohibited; no ceiling or reservation changes.
4. **Production scope creep:** no production holder or six-unit change is justified by current evidence.
5. **Latent later-stage zero-work semantics:** noted separately; do not conflate it with this consumed proof blocker.
