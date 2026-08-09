# Printer V1 V2-9.8B — Post-DTW93 Local-Validation Observer Repair Design

Date: 2026-08-09

## Verdict

`V2_9_8B_POST_DTW93_LOCAL_VALIDATION_OBSERVER_REPAIR_DESIGN_READY`

Design/specification only. No production code, runtime, source fetching, authoritative DB mutation, authorization, or live `WINDOW_15M` work occurs in this lane.

## Confirmed defect

DTW93 proved a committed accounting-wiring gap at `PROTOCOL_CONFIRMATION`:

- owner local validations: `80`
- action-local local validations: `67`
- exact missing family: `13` protocol-confirmation PumpSwap account validations.

The protocol-confirmation owner creates and seals those validation identities, but the existing action-local validation observer is not threaded into that boundary.

## Exact repair

### 1. Protocol-confirmation function

Extend `process_protocol_confirmation_queue(...)` with one optional parameter:

`local_validation_identity_observer`

Keep the existing local `LocalValidationIdentity` construction and stage binding authoritative.

At `_finalize_report`, after `bound_validations` are built with the canonical `PROTOCOL_CONFIRMATION` stage id and **before** `seal_campaign_stage_evidence(...)`, invoke the observer exactly once for every bound validation identity.

The callback must receive the real `LocalValidationIdentity` object. It must not receive a reconstruction copied from sealed evidence.

### 2. Eligible-supply composition

Thread the already-existing `local_validation_identity_observer` argument unchanged into every operational `process_protocol_confirmation_queue(...)` call, including:

- early protocol confirmation;
- residual/final protocol confirmation.

No new observer owner is introduced.

### 3. Failure and zero-work behavior

- No protocol validation identity -> no callback.
- Local-only protocol outcomes that genuinely create validation identities use the same callback rule.
- Source/measurement failure before a validation identity exists -> no fabricated callback.
- If later owner sealing fails, action-local evidence may truthfully contain a validation that occurred; the campaign remains fail-closed. Do not erase or backfill identities to force equality.
- Never callback a second time during report assembly or replay.

## Explicitly unchanged

This repair must not change:

- PumpSwap account validation semantics;
- candidate admission or selection;
- the no-registry-confirmation rule;
- provider endpoints or source request count;
- Source Governor ownership;
- Central Scheduler ownership;
- holder eligibility;
- liquidity floor;
- source/Scheduler budgets;
- lease/heartbeat timing;
- lifecycle cadence;
- memory quality/promotion logic;
- retry/restart/resume/successor rules;
- any retrieval or paper/financial surface.

`PROTOCOL_CONFIRMATION` remains exact current-pool/account evidence. It must not become a migration-registry membership check.

## Minimum sufficient implementation proof

Focused offline tests only:

1. successful protocol batch with N members -> N owner validation identities and the exact same N independently observed action-local identities;
2. mixed categorical PumpSwap outcomes -> exact identity/kind/ordinal equality;
3. observer called once per validation, never during sealing/replay duplication;
4. source failure before member validation -> zero fabricated validation callbacks;
5. early and residual eligible-supply protocol call sites both propagate the observer;
6. focused full-run accounting fixture previously exposing only this mismatch reaches owner/action-local local-validation equality;
7. existing transport/source-operation totals unchanged.

Use temporary/fixture databases only. No broad regression suite is required for implementation; reserve broader validation for proof/closeout if risk warrants it.

## Money-usefulness contribution

The repair makes protocol evidence independently accountable on both sides of the campaign acceptance contract, improving trust in which exact market/protocol facts support a memory. It adds no profitability signal or decision authority.

## What this improves

- exact owner/action-local accounting equality for PumpSwap protocol validation;
- trustworthy full-run acceptance evidence;
- replayability of the same independently observed identities.

## What this still does not unlock

- another live `WINDOW_15M` run;
- `WINDOW_1H+`;
- retrieval;
- paper decisions / BUY / SELL / HOLD;
- positions, trades, audits, PnL;
- wallets, signing, real funds, live execution;
- paid APIs;
- scoring/ranking/confidence/weighted systems;
- embeddings/vectors.

## Functionality Risks / Setbacks / Efficiency Blockers

- Callback after sealed-evidence reconstruction would violate independent accounting; callback must consume the pre-seal bound identity objects.
- Double-callback across early/residual finalization would overcount and fail equality in the opposite direction.
- Fabricating callbacks on source failure would make evidence dishonest.
- Expanding into discovery/protocol admission logic would create roadmap drift.
- Even after this repair, the DTW93 host-awake failure remains a separate operational issue; any later real attempt must use the approved `caffeinate -dimsu` safeguard.

## Next permitted lane

Implement this exact observer-propagation repair with focused offline tests only. No real source run or new authorization in the implementation lane.