# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — Post-DTW-48 Re-Proof Readiness Decision

Date: 2026-08-07

Verdict: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_DTW48_REPROOF_READINESS_PASS_AWAITING_EXPLICIT_OPERATOR_AUTHORIZATION`

Linear parent: `DTW-34`
Repair lane: `DTW-48`

## Reviewed lineage

- consumed post-DTW47 authorization/proof HEAD: `841f96634f4e7efa7fd70bef7fc3984f8279e746`
- DTW-48 audit: `adb2c4cc5bd7906b00b98535d1e5b504b6ec6e05`
- DTW-48 design: `675e3de9c5cb2c2d7aa064a3fb0014679a9c71f9`
- DTW-48 repair: `a54a80673f359d8e7e4db20b0c838d782f5ce699`
- DTW-48 closeout: `7b1ee07f7b68eef12d63e95095df8fc0169ae848`

All prior Checkpoint 8 controlling attempts remain historical, consumed, and no-rerun.

## Source-stack review

The active Printer V1 stack continues to require:

- Solana-only / Solana-memecoin-only;
- paper-only operation;
- no wallet, private keys, real funds, live execution, or paid API dependency;
- no scoring/ranking/confidence/weighted systems;
- no Source Governor or Central Scheduler bypass;
- clean completed memory before later decision use;
- 5m support-only;
- retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits, and PnL remain locked unless their explicit later lanes approve them.

The active memory-growth build order keeps V2-9.8B as the bounded memory-growth operations lane and requires audit/readiness -> design -> implementation -> bounded proof/test -> closeout with lock preservation and money-usefulness checks.

No reviewed DTW-48 change weakens these rules.

## Independent repair verification

GitHub inspection establishes repair commit `a54a80673f359d8e7e4db20b0c838d782f5ce699` is exactly one commit over the approved DTW-48 design and changes exactly three proof-only files:

1. `scripts/v2_9_8b_checkpoint8_controlling_public_composition_proof.py`
2. `src/printer_v1/operator_cli/checkpoint8_real_consumer_compatibility.py`
3. `tests/test_v2_9_8b_window_15m_checkpoint8_real_consumer_compatibility.py`

The repair does not touch production GoPlus, holder budget, six-unit accounting, Source Governor, Central Scheduler, memory, retrieval, decision, position, trade, audit, or PnL code.

The repaired C8 GoPlus fixture:

- uses the real GoPlus adapter shape;
- requires an exact known C8 target mint;
- uses the holder ledger supplied by the real funnel;
- records exactly one measured `HOLDER_SAFETY` transport identity for one actual governed fixture execution;
- writes the same identity into the normalized payload;
- reports one underlying/transport operation;
- remains deterministic and zero-network.

The real-consumer compatibility matrix now fails closed unless the GoPlus holder ledger and payload each contain exactly one canonical matching identity with the exact production-equivalent holder fields.

## Why the consumed failure is addressed

The consumed post-DTW47 attempt failed because the holder stage had four clean governed GoPlus requests/responses but its C8 fixture added zero measured holder identities. `_seal_holder_stage()` therefore treated the holder ledger as empty and constructed campaign-global `PRE_OPERATION_NO_WORK` evidence. The six-unit owner correctly rejected that evidence because earlier stages had already been ingested.

After DTW-48, one successful C8 GoPlus holder fixture execution records one holder identity into the caller-owned ledger. Therefore the holder sealer receives a non-empty ledger and follows ordinary holder-stage evidence sealing instead of the invalid pre-operation no-work branch. Six-unit validation itself remains unchanged.

## Verification evidence

Deterministic RED at design HEAD:

- CLEAN exact-target GoPlus result;
- holder ledger identities: `0`;
- payload identities: `0`;
- network attempts: `0`;
- expected RED classification confirmed.

Offline GREEN at repair commit:

- changed-file compile: PASS;
- exact GoPlus holder identity regression: `1 passed`;
- real-consumer compatibility: `9 passed`;
- full focused C8 suite: `100 passed`;
- exact three-file manifest: PASS;
- diff check: PASS;
- provider/network execution: NONE;
- controlling proof: NONE.

## Known-blocker review

The known C8 blocker sequence has been addressed through its required audit/design/implementation/offline-proof/closeout pattern, including:

- malformed direct Pump RPC fixture;
- PumpSwap fixture argument order;
- market fixture transport-identity accounting;
- canonical policy overlay loss;
- measured market fixture identities;
- direct Pump evidence bridge / four-reserve exact budget attribution / exact-target lifecycle fixture;
- GoPlus holder measured-transport identity loss.

No remaining known blocker was identified in this read-only review.

This is not a guarantee that a future controlling attempt will pass; a new failure must fail closed and create a new audit lane rather than trigger a rerun.

## Conditions for any future controlling attempt

A future Checkpoint 8 attempt is permitted only after a new explicit operator authorization. That authorization must create a documentation-only authorization commit directly over the reviewed readiness lineage and use that resulting SHA as the immutable proof HEAD.

Any authorized attempt must still be:

- exactly one attempt;
- fresh disposable DB/artifact/proof-root/sentinel namespaces;
- deterministic fixture-backed;
- zero-provider/network;
- ordinary public campaign composition through the real authoritative campaign owner;
- WINDOW_15M only;
- no retry/rerun/resume/restart/successor;
- evidence-preserving on block/failure;
- followed by independent frozen-evidence inspection before any Checkpoint 8 closeout if it produces a PASS candidate.

## Money-usefulness contribution

Readiness now includes truthful holder-source transport accounting, allowing valid clean holder evidence to progress toward a trustworthy 15m memory proof instead of failing on false accounting.

## What this improves

- confidence in the C8 proof harness's source-accounting fidelity;
- holder-stage six-unit readiness without weakening validation;
- exact-target and canonical identity parity in holder fixtures;
- readiness for one future bounded proof attempt if explicitly authorized.

## What this still does not unlock

This decision does not authorize or unlock:

- a controlling C8 proof by itself;
- operational WINDOW_15M memory growth;
- provider/network access;
- authoritative DB use;
- WINDOW_1H+;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits, or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

1. A future controlling attempt may reveal a different previously unobserved blocker; it must stop with no rerun.
2. Historical attempts remain unusable as proof retries even though their defects are repaired.
3. The genuine semantics of a later holder stage with truly lawful zero transport remain a separate latent issue and must not weaken current six-unit rules without its own evidence and lane.
4. Full Checkpoint 8 acceptance still requires actual controlling proof evidence plus independent frozen-evidence inspection.

No new Checkpoint 8 controlling proof is authorized by this readiness decision.
