# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-64 Canonical REPORT_ONLY Requested-Identity Repair Design

Date: 2026-08-08

Linear: `DTW-64`

Audit baseline:

`07c323084993cc9bd119f218cff991e435af5122`

Implementation under repair:

`092a738c2226766aac078036f79ab7d9a901a58e`

## Verdict

`DTW64_CANONICAL_REPORT_ONLY_REQUESTED_IDENTITY_REPAIR_DESIGN_READY_FOR_RED`

This lane is design-only. It repairs only the remaining DTW-63 durable fallback around `report_only.requested_identity`.

## Canonical durable contract

When `reconstructed_identity is not None`, `report_only.requested_identity` is mandatory.

It must be a dictionary containing non-empty:

- `campaign_id`;
- `run_id`.

Required equality:

- `requested_identity.campaign_id == frozen_summary.campaign_id`;
- `requested_identity.run_id == frozen_summary.run_id`.

The same durable replay must also require:

- `report_only.status == REPLAYED`;
- `report_only.mode == REPORT_ONLY`.

Top-level `report_only.campaign_id` and `report_only.run_id` must never substitute for the canonical requested-identity carrier in durable mode.

## Fail-closed boundaries

Missing `requested_identity`, or missing/blank `campaign_id` / `run_id` inside it:

`REPORT_REPLAY_REQUESTED_IDENTITY_MISSING`

Present-but-wrong requested campaign/run, or wrong/missing replay status/mode:

`REPORT_REPLAY_IDENTITY_MISMATCH`

## Legacy compatibility boundary

Only when `reconstructed_identity is None` may the existing direct-helper fallback remain:

- use canonical `requested_identity` when present;
- otherwise permit legacy top-level replay campaign/run validation.

That fallback must not be reachable from `inspect_checkpoint8_frozen_proof_directory`, which supplies reconstructed durable identity.

## Deterministic RED design

The next lane must add focused RED before implementation.

Minimum required cases:

1. Remove `report_only.requested_identity`, add exact top-level `report_only.campaign_id` and `report_only.run_id`, keep all other evidence valid. Current inspector should incorrectly accept; repaired inspector must fail `REPORT_REPLAY_REQUESTED_IDENTITY_MISSING`.
2. Same missing canonical carrier plus exact top-level campaign/run, but make replay `status` or `mode` wrong. Repaired durable path must still fail closed; top-level fallback must not bypass replay-mode validation.
3. Canonical requested identity present but missing `campaign_id`.
4. Canonical requested identity present but missing `run_id`.
5. Preserve a direct-helper compatibility case with `reconstructed_identity=None` proving the legacy top-level fallback still works where intentionally allowed.
6. Preserve present-but-wrong canonical requested campaign/run or wrong status/mode at `REPORT_REPLAY_IDENTITY_MISMATCH`.

For summary mutations, recompute `frozen_evidence_sha256` so RED is about requested-identity semantics rather than frozen-summary integrity.

## Minimum implementation design

Expected production edit remains only:

`scripts/v2_9_8b_checkpoint8_independent_inspection.py`

Preferred change:

1. move requested-identity handling under a durable-vs-legacy conditional;
2. durable branch requires canonical carrier, its two fields, and exact status/mode before equality comparison;
3. legacy branch retains current helper-only fallback;
4. leave DTW-62 terminal identity, replay nested identity, proof expectation, graph, Scheduler, source accounting, report hash/artifact, cleanup, and frozen-safety logic unchanged.

## Focused GREEN requirement

After implementation, run only:

- the new DTW-64/65 requested-identity RED test;
- DTW-61 required identity-presence tests;
- DTW-57 representative real-schema tests;
- existing independent-inspection completion tests;
- existing independent-inspection integration tests.

Then inspect consumed DTW-54 artifact `9014056017` read-only again and require `CHECKPOINT8_INDEPENDENT_INSPECTION_PASS`.

A separate independent readiness review remains mandatory after GREEN.

## Money-usefulness contribution

The canonical replay request identity proves which campaign/run the zero-work replay was requested for. Making it mandatory prevents identity drift from weakening the evidence chain that later clean-memory comparison depends on.

## What this lane improves

It removes the final known durable legacy fallback without reopening any already-correct reconstruction surface.

## What this lane still does not unlock

This design does not unlock another Checkpoint 8 proof, WINDOW_15M activation, longer windows, retrieval, paper decisions, BUY/SELL/HOLD, positions, trade events, audits, PnL, or any live-funds capability.

## Proof/test needed before completion

Design is complete only as a specification. The next lane must demonstrate deterministic RED, followed by minimum inspector-only implementation, focused GREEN, consumed-artifact read-only PASS, and a separate readiness review.

## Functionality Risks / Setbacks / Efficiency Blockers

- Do not remove the legacy helper fallback outside durable mode.
- Do not let top-level replay campaign/run satisfy durable acceptance.
- Do not broaden the repair to nested replay identity or proof expectation; DTW-62 already closed those gaps.
- Keep frozen-summary hashes valid in RED mutations.
- No broad regression suite is warranted for this one conditional branch.

## Stop condition

DTW-64 stops at design. No implementation and no fresh controlling proof are authorized by this document.
