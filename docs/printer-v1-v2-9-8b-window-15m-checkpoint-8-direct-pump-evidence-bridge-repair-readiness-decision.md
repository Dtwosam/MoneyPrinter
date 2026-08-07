# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-47 Independent Review and Re-Proof Readiness Decision

Date: 2026-08-07

Independent repair verdict: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_DTW_47_REPAIR_CLOSEOUT_INDEPENDENT_REVIEW_PASS`

Checkpoint 8 readiness verdict: `V2_9_8B_WINDOW_15M_CHECKPOINT_8_POST_DTW47_REPROOF_READINESS_PASS_AWAITING_EXPLICIT_OPERATOR_AUTHORIZATION`

Linear: `DTW-47` under parent `DTW-34`

## Reviewed lineage

- Consumed post-DTW-46 proof HEAD: `ecd399ef4f4aeee6cf541e4292bb6a5229c943b2`
- DTW-47 V3 design: `ea6a856d3386050eb4c84710a0aadf3f8a7a9f9a`
- DTW-47 repair: `986f1b1e839c91203d0781e5f7357f7ee64b7243`
- DTW-47 closeout: `4f9675d60275d6c1ef6a3e620741498049b90bec`

GitHub independently confirmed the repair is exactly one commit over V3 design HEAD with the exact six-file approved manifest, and the closeout is exactly one documentation-only commit over the repair.

## Independent repair review

PASS.

The repair matches the approved design without policy weakening:

- exact carried `direct_pump_evidence` is preserved through the permanent exact-mint bridge;
- protocol-confirmation stage usage is derived from exact existing PumpSwap verification coverage identities;
- stage reservations are unchanged;
- deterministic C8 reserve depth is four while final neutral selected supply remains exactly two;
- lifecycle market fixtures bind to the requested mint+pool and fail closed on mismatch;
- stale two-candidate proof assertions were updated only where the permanent four-reserve contract required it.

The production admission gate remains fail-closed and still requires exact mint, pool, PumpSwap program ID, confirmation, migration signature and valid graduation time from carried evidence.

## Offline proof review

Minimum sufficient risk-based verification is satisfied:

- deterministic missing-evidence RED: PASS, zero network;
- deterministic four-reserve false-shortage RED: PASS, zero network;
- changed-file `py_compile`: PASS;
- real-consumer compatibility: `8 passed`;
- nearest Eligible Token Supply architecture: `26 passed`;
- complete focused C8 suite: `99 passed`;
- exact six-file manifest: PASS;
- diff checks: PASS;
- explicit zero-network tripwire regressions: PASS.

No broad repository suite is required for this bounded repair.

## Active source-stack lock review

The active Printer V1 source stack continues to require:

- Solana-only, memecoin-only, paper-only V1;
- no Source Governor bypass;
- no Central Scheduler bypass;
- first automated main outcome target remains `WINDOW_15M`;
- `WINDOW_5M_MICRO_EVENT` remains support-only;
- no `WINDOW_1H` proof until its later E2Q/audit repair lane;
- retrieval remains locked;
- paper decisions and BUY/SELL/HOLD remain locked;
- positions, trades, audits and PnL remain locked;
- terminal failure must never auto-restart.

DTW-47 changed none of these rules.

## Complete C8 historical-attempt rule

Every prior C8 controlling attempt remains consumed historical evidence. No prior proof may be retried, rerun, resumed, restarted or reused.

The consumed post-DTW-46 attempt `C8_REPROOF_AFTER_DTW46_20260807` remains failed with a claimed sentinel and first exception `DIRECT_PUMP_EVIDENCE_MISSING`. DTW-47 repairs the proven cause; it does not alter that historical attempt.

Any future C8 proof must use a new proof ID, fresh disposable DB, fresh artifact namespace and fresh one-shot sentinel under a separately explicit operator authorization.

## Fresh re-proof readiness review

Read-only review finds no remaining **known** blocker from the consumed C8 history after DTW-47:

- DTW-46 measured-market identity blocker: closed and independently reviewed;
- direct Pump evidence bridge blocker: repaired and focused-GREEN;
- four-reserve false-shortage stage attribution: repaired without raising ceilings;
- four-reserve fixture contract: focused-GREEN;
- exact-target lifecycle fixture binding: focused-GREEN;
- real-consumer fixture matrix: focused-GREEN;
- complete focused C8 regression set: GREEN.

The deterministic proof capability remains zero-provider/network and provider fallback remains forbidden. No temporary GitHub Actions workflow or temporary branch infrastructure is required by this proof path; the accepted execution model remains a local isolated worktree pinned to an exact reviewed Git SHA.

## Checkpoint 8 acceptance law remains unchanged

A future controlling proof is successful only if the complete approved acceptance law holds, including:

- ordinary bounded `WINDOW_15M` public composition;
- complete campaign acceptance exactly `CAMPAIGN_PASS`;
- exact two selected lifecycle tokens despite four-deep reserve supply;
- required clean terminal `WINDOW_15M` closure;
- required clean episode memories/fingerprints;
- canonical Scheduler and Source Governor ownership/accounting;
- valid six-unit evidence and exact ownership identities;
- canonical report parity;
- exact cleanup, lease release and zero active/orphan/locked residue;
- report-only replay with zero source calls, zero Scheduler runtime calls and zero DB writes;
- zero provider/network attempts;
- clean disposable DB integrity and foreign-key state;
- zero protected downstream deltas;
- no `WINDOW_1H+`;
- no retry, rerun, resume, restart or successor.

`CAMPAIGN_PASS` alone is not sufficient; the frozen evidence must independently satisfy the entire acceptance law.

## Exact next boundary

DTW-47 is ready to close.

Checkpoint 8 / `DTW-34` remains OPEN.

The independent-review prerequisite for **considering** one later fresh C8 controlling re-proof authorization is satisfied. This document does **not** authorize that proof.

Before any later C8 attempt:

1. the operator must explicitly authorize exactly one fresh C8 controlling re-proof;
2. a documentation-only authorization record must be created on the then-current reviewed branch tip;
3. the authorization commit lineage/diff must be independently verified;
4. the attempt must use completely fresh disposable resources;
5. exactly one attempt may execute.

If that attempt blocks or fails, preserve the evidence and stop. If it produces a PASS candidate, stop runtime and perform independent frozen-evidence inspection before any Checkpoint 8 closeout.

## Money-usefulness contribution

The repaired path can now carry exact Pump/PumpSwap provenance into a resilient four-deep candidate reserve without wasting protocol budget on intake operations, while still selecting only two tokens for bounded 15m learning. This improves the trustworthiness and diversity of future memory evidence without weakening safety.

## What this review still does not unlock

- a new C8 proof without explicit authorization;
- Checkpoint 8 completion;
- operational `WINDOW_15M` memory growth outside the approved proof capability;
- provider/network access;
- authoritative DB use;
- `WINDOW_1H+`;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions, trades, audits or PnL.

## Functionality Risks / Setbacks / Efficiency Blockers

1. A future one-shot proof may reveal a genuinely new contract defect not covered by the focused suite; that would require a new narrow audit/design/repair lane, not a rerun.
2. Four reserve candidates must remain supply resilience only; active lifecycle selection remains two.
3. Exact coverage attribution depends on truthful request coverage identities and must fail closed if those identities become missing or ambiguous.
4. No current evidence justifies broader verification, provider access, stage-ceiling changes, or later-window activation.

Stop here. No Checkpoint 8 proof is authorized by this readiness decision.
