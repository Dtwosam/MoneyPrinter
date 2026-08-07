# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 Post-Fixture-Repair Re-proof Readiness Decision

## Verdict

`V2_9_8B_WINDOW_15M_CHECKPOINT_8_NEXT_REPROOF_PROPOSAL_READY_AWAITING_NEW_EXPLICIT_OPERATOR_AUTHORIZATION`

Checkpoint 8 remains incomplete. The consumed fresh re-proof failed on a proof-fixture argument-order defect, that defect has now passed the full offline repair cycle, and the clean repaired state is technically ready for one new re-proof to be proposed. No proof is authorized by this decision.

## Governing boundary

This decision remains subordinate to the active Printer V1 source stack and all V1 capability locks. It changes no provider contract, production discovery behavior, Source Governor ownership, Central Scheduler ownership, budget, timeframe, memory-quality rule, or financial capability.

## Evidence reviewed

Consumed fresh proof:

- authorized HEAD: `319e842d9b7e6b2e89f4609924341e02017795df`;
- proof ID: `C8_REPROOF_AFTER_OFFLINE_REPAIR_20260807`;
- Actions run: `31187598614`;
- result: `CHECKPOINT8_PUMPSWAP_FIXTURE_TARGET_MISSING`;
- entitlement permanently consumed.

Repair lineage:

- failure audit: `99208dc9bd22da17f29de8cf4a3280089f0f4dc0`;
- repair design: `8612633da618776b735280375e81a084989dea3f`;
- implementation: `5788988c79da6a2889699b4006cee090d9c445d5`;
- repair closeout: `cdf7eb3bc42ca3e2f69b8aa3c70846addb25d27d`;
- clean compatibility verification: `3/3` PASS;
- clean focused C8 suite: `94/94` PASS;
- compile/static/diff checks: PASS;
- production discovery file unchanged.

The new regression exercises the canonical production call contract `verifier_transport_factory(mint, signature)` through the real PumpSwap adapter boundary and fails closed on reversed ordering.

## Readiness decision

A future operator may authorize exactly one new ordinary `WINDOW_15M` controlling proof after this repair.

A future authorization must:

1. explicitly state that one new Checkpoint 8 re-proof attempt is authorized after the fixture argument-order repair;
2. pin the exact authorization-time repository HEAD;
3. use a new proof identity and fresh one-shot sentinel namespace;
4. use a fresh canonically migrated disposable SQLite DB and fresh disposable artifact root;
5. retain the exact canonical deterministic offline fixture composition and process-local external-network tripwire;
6. permit no provider fallback and no retry/rerun/resume/restart/successor path.

Any runtime/source-owner change after this reviewed repair/readiness lineage requires another readiness review before proof execution.

## Acceptance law remains unchanged

A later proof must still establish, in one attempt:

- exactly one public `run_operational_campaign()` call;
- real Source Governor and Central Scheduler ownership;
- deterministic offline fixture transports only;
- zero external-network/provider attempts;
- exactly two distinct current-run terminal ordinary `WINDOW_15M` windows;
- both terminal memories `CLEAN_MEMORY` with fingerprints;
- `CAMPAIGN_PASS`;
- cleanup complete and lease released;
- zero active/orphan Scheduler/discovery residue;
- exactly one report-only replay with zero source calls, Scheduler calls, and DB writes;
- frozen-summary/hash identity parity;
- independent read-only inspection PASS;
- zero protected downstream capability deltas;
- no `WINDOW_1H`, `WINDOW_4H`, `WINDOW_12H`, or `WINDOW_24H` activation.

`WINDOW_5M_MICRO_EVENT` remains support-only.

## Operator-authorization boundary

The operator authorization that launched Actions run `31187598614` is spent and cannot be reused.

Generic instructions such as continue, handle everything, finish the checkpoint, or rerun are not sufficient for a new proof. A new explicit one-shot authorization is required after this readiness decision.

## Money-usefulness contribution

This readiness decision allows progress toward proving reliable clean `WINDOW_15M` memory creation while preserving the evidentiary value of both failed attempts. It prevents harness debugging from silently becoming repeated proof execution and keeps the eventual automation claim tied to one deliberate bounded attempt.

## What this improves

- confirms the newly discovered fixture-contract blocker completed audit, design, implementation, focused proof/test, and closeout;
- confirms the repaired fixture now matches the production PumpSwap verifier call shape;
- provides a clean authorization boundary for any next proof;
- prevents the prior authorization from being stretched across multiple attempts.

## What remains locked

Until a new explicit authorization is recorded, remain locked:

- another Checkpoint 8 controlling proof;
- public campaign runtime;
- provider/network execution;
- memory generation outside offline tests;
- `WINDOW_1H+` activation;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- paper positions;
- trade events;
- paper-trade audits;
- PnL;
- wallets/private keys/real funds/live execution;
- paid APIs, scoring/ranking/confidence/weighted logic, embeddings, or vectors.

## Proof/test needed before completion

Checkpoint 8 can close only after a separately authorized new one-shot proof satisfies the unchanged C8 acceptance law and its frozen output passes independent read-only inspection.

## Functionality Risks / Setbacks / Efficiency Blockers

- Two prior controlling attempts failed on proof infrastructure rather than completing the intended acceptance path. A next attempt must remain strictly one-shot and cannot become another debugging loop.
- `94/94` focused offline coverage reduces known harness risk but cannot guarantee that no unexercised full-composition defect remains.
- Any code drift after readiness invalidates the reviewed proof candidate.
- This readiness is for ordinary `WINDOW_15M` only and gives no evidence for longer windows or financial capability.

## Stop condition

Readiness decision complete. Stop before runtime and await a new explicit operator authorization for one new Checkpoint 8 re-proof attempt after the fixture argument-order repair.
