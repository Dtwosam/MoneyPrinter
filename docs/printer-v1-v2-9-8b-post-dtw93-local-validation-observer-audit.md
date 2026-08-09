# Printer V1 V2-9.8B — Post-DTW93 Local-Validation Observer Audit

Date: 2026-08-09

## Verdict

`V2_9_8B_POST_DTW93_LOCAL_VALIDATION_OBSERVER_AUDIT_PASS_COMMITTED_WIRING_DEFECT_CONFIRMED`

Static/offline audit only. No source fetching, authoritative DB mutation, Printer runtime, Scheduler runtime, memory generation, authorization, or live `WINDOW_15M` attempt occurred.

## Question audited

Why did DTW93 full-run reconciliation report:

- owner `LOCAL_VALIDATION_STEP = 80`
- action-local `LOCAL_VALIDATION_STEP = 67`
- difference `13`
- mismatch `LOCAL_VALIDATION_STEP:UNIT_IDENTITY_SET_MISMATCH`?

## Finding

The 13 missing action-local identities are the 13 `PROTOCOL_CONFIRMATION` PumpSwap account validations sealed into owner evidence.

The ordinary campaign correctly creates an action-local validation observer and passes it into the graduated/eligible supply composition.

The eligible-supply function accepts that observer and forwards it to direct-migration discovery. However, its calls to `process_protocol_confirmation_queue(...)` forward stage evidence and transport observation but not the local-validation observer.

`process_protocol_confirmation_queue(...)` itself has no local-validation observer parameter. It creates one `LocalValidationIdentity` for each normalized protocol member, binds those identities to the `PROTOCOL_CONFIRMATION` stage, and seals them into owner-side stage evidence. Because no independent observer callback exists at this boundary, those identities never enter the action-local ledger.

DTW93 recorded 13 protocol-confirmation validation identities in owner evidence. `80 - 67 = 13`, exactly matching the omitted family.

## Classification

`COMMITTED_CODE_DEFECT`

This is independent of the controlling live terminal cause `LEASE_RENEWAL_LEASE_EXPIRED`.

The host-awake failure stopped DTW93 before 15m closeout, but it did not create this 13-identity discrepancy. A future caffeinated run could still fail the required owner/action-local equality gate unless this wiring defect is repaired and proved offline first.

## Scope of safe repair design

The later design lane should preserve the current owner/action-local separation:

1. add an optional local-validation observer at the protocol-confirmation boundary;
2. notify it exactly once for each real `LocalValidationIdentity`, before/independently of sealed owner evidence;
3. thread the existing observer through eligible-supply protocol-confirmation call sites;
4. do not reconstruct action-local identities from sealed stage evidence;
5. do not change PumpSwap confirmation semantics, discovery eligibility, selection, provider calls, budgets, Scheduler behavior, lease timing, or memory rules.

The repair must not add any registry-membership confirmation. These are exact PumpSwap pool-account validations, not migration-registry admission checks.

## Money-usefulness contribution

Exact independent accounting lets operators trust that the source/protocol work used to build a 15m memory is represented consistently by both the campaign owner and the action-local execution ledger. It improves evidence trust, not token ranking, profitability prediction, or BUY readiness.

## What this audit improves

- identifies the exact missing accounting boundary instead of blaming the mismatch on host sleep;
- preserves independent owner/action-local evidence rather than weakening equality checks;
- narrows the repair to observer propagation only.

## What remains locked

This audit unlocks no runtime capability. Still locked:

- another real `WINDOW_15M` authorization/run;
- `WINDOW_1H+`;
- retrieval;
- paper decisions / BUY / SELL / HOLD;
- positions, trades, audits, PnL;
- wallets, signing, real funds, live execution;
- paid API dependencies;
- scoring/ranking/confidence/weighted systems;
- embeddings/vectors.

## Proof required after implementation

Minimum sufficient offline proof must demonstrate:

- protocol-confirmation owner local-validation identities equal independently observed action-local identities for success and categorical mismatch outcomes;
- no duplicate callback on sealing/finalization;
- zero-transport/local-only protocol outcomes remain truthful;
- existing transport accounting remains unchanged;
- a focused full-run accounting fixture reaches owner/action-local equality when this is the only mismatch;
- no Source Governor, Scheduler, selection, memory, or financial behavior changes.

## Functionality Risks / Setbacks / Efficiency Blockers

- Mirroring identities from sealed owner evidence would create self-comparison and is forbidden.
- Calling the observer both during member processing and again during stage sealing would double-count.
- Expanding this repair into protocol eligibility or registry logic would violate scope.
- A live rerun before offline repair/proof would waste another one-use authorization and still carry a known acceptance blocker.

## Next permitted lane

Design/specify the narrow `PROTOCOL_CONFIRMATION` local-validation observer propagation repair. No production implementation or live attempt in this audit lane.