# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-60 Required Identity-Presence Repair Design

Date: 2026-08-08

Linear: `DTW-60`

Audit baseline:

`b1b046ddc201337e692691d3bb1068458ff7e409`

Implementation under repair:

`7f6bcbd574257ba19ec20a0c35217685a2ffce91`

Audit verdict:

`DTW59_INDEPENDENT_READINESS_BLOCKED_REQUIRED_REPORT_REPLAY_IDENTITY_PRESENCE_NOT_FAIL_CLOSED`

## Verdict

`DTW60_REQUIRED_IDENTITY_PRESENCE_REPAIR_DESIGN_READY_FOR_RED`

This lane is design-only. It narrows the remaining Checkpoint 8 inspector work to three fail-closed identity-presence boundaries and does not reopen campaign runtime, discovery, Source Governor, Scheduler, memory generation, or proof execution.

## Goal

Make absence fail exactly as safely as mismatch for the canonical identities that bind a frozen proof to:

1. its terminal report;
2. its REPORT_ONLY replay;
3. its replay proof/fixture authorization identity.

The already-correct DTW-58 durable reconstruction remains unchanged in intent.

## 1. Canonical terminal-report full-run identity

For durable reconstruction, the canonical terminal-report identity carrier is:

`report_json.full_run_terminal_evidence.identity`.

It must be a dictionary and must contain non-empty values for all of:

- `campaign_id`;
- `campaign_run_id`;
- `configuration_id`;
- `cycle_id`;
- `factory_run_id`;
- `execution_id`;
- `supervision_id`.

Each value must exactly equal the independently reconstructed identity before the report can contribute to acceptance.

Missing carrier or missing/blank field must fail closed with:

`TERMINAL_REPORT_IDENTITY_MISSING`

Present-but-wrong value must continue to fail with:

`TERMINAL_REPORT_IDENTITY_MISMATCH`

The outer report `identity` object may be checked for parity if present, but it must never substitute for a missing canonical `full_run_terminal_evidence.identity` field.

`execution_id` must come from the canonical terminal-report full-run identity for terminal-report acceptance. Replay identity must not backfill a missing terminal-report execution id.

## 2. Canonical REPORT_ONLY replay identity

The public replay request identity remains:

`report_only.requested_identity`.

It must continue to contain exact `campaign_id` and public campaign `run_id`.

In addition, durable-mode replay acceptance must require:

`report_only.full_run_terminal_evidence.identity`.

That identity must be a dictionary and contain non-empty exact values for:

- `campaign_id`;
- `campaign_run_id`;
- `configuration_id`;
- `cycle_id`;
- `factory_run_id`;
- `execution_id`;
- `supervision_id`.

Missing carrier or missing/blank required field must fail with:

`REPORT_REPLAY_IDENTITY_MISSING`

Present-but-wrong values continue to fail with:

`REPORT_REPLAY_IDENTITY_MISMATCH`

The replay full-run identity must be compared to the independently reconstructed identity, not copied into it.

## 3. Replay proof/fixture authorization identity

Durable replay must also require:

`report_only.full_run_terminal_evidence.authorization_and_invocation.proof_expectation`.

The object must exist and contain non-empty:

- `proof_id`;
- `fixture_composition_manifest_sha256`.

Required equality:

- `proof_expectation.proof_id == frozen_summary.proof_id`;
- `proof_expectation.fixture_composition_manifest_sha256 == frozen_summary.fixture_composition_manifest_sha256`.

Missing carrier or missing/blank field must fail with:

`REPORT_REPLAY_PROOF_EXPECTATION_IDENTITY_MISSING`

Present-but-wrong proof id or manifest continues to fail with:

`FIXTURE_MANIFEST_IDENTITY_MISMATCH`

No top-level replay convenience field may substitute for the nested proof expectation.

## 4. Durable-mode boundary and legacy direct-validator compatibility

The strict presence contract applies when the inspector has an independently reconstructed identity, i.e. the normal end-to-end frozen-proof path.

Existing standalone unit tests that call validation helpers without `reconstructed_identity` may retain their legacy synthetic shape where necessary. That compatibility must not become an end-to-end durable acceptance path.

Implementation rule:

- durable path: strict canonical carrier presence + exact equality;
- isolated legacy helper path: existing fallback behavior may remain only when no reconstructed durable identity was supplied.

Do not weaken the DTW-58 database reconstruction or reintroduce owner-string/fingerprint-SHA/flat-run assumptions to preserve old tests.

## 5. Deterministic RED design

The next lane must add focused RED cases before implementation.

### A. Terminal-report identity presence RED

Build otherwise-valid representative fixture variants where the canonical DB terminal report and byte-identical report artifact are generated with one required `full_run_terminal_evidence.identity` field omitted.

Parameterize across the seven required fields so every field is protected.

For each variant:

- generate the terminal report without the selected field before insertion;
- recompute valid `report_hash`;
- write the matching artifact bytes;
- keep all other graph/accounting/safety evidence valid;
- expect `TERMINAL_REPORT_IDENTITY_MISSING`.

The fixture must not mutate an immutable persisted report row after insertion merely to manufacture RED.

### B. Replay full-run identity presence RED

Starting from an otherwise-valid summary, remove one required field at a time from:

`report_only.full_run_terminal_evidence.identity`.

Recompute `frozen_evidence_sha256` after each mutation.

Expect:

`REPORT_REPLAY_IDENTITY_MISSING`.

Parameterize across all seven required fields.

### C. Replay proof-expectation identity presence RED

Add variants for:

- missing `authorization_and_invocation`;
- missing `proof_expectation`;
- missing `proof_id`;
- missing `fixture_composition_manifest_sha256`.

Recompute frozen-summary hash after each summary mutation.

Expect:

`REPORT_REPLAY_PROOF_EXPECTATION_IDENTITY_MISSING`.

### D. Mismatch preservation

Keep or add minimum checks proving present-but-wrong values still fail at the existing mismatch boundaries rather than being converted into generic missing errors.

At minimum retain:

- wrong replay campaign run / reconstructed identity -> `REPORT_REPLAY_IDENTITY_MISMATCH`;
- wrong replay proof id or manifest -> `FIXTURE_MANIFEST_IDENTITY_MISMATCH`.

## 6. Minimum implementation design

Expected production edit remains only:

`scripts/v2_9_8b_checkpoint8_independent_inspection.py`.

Preferred implementation shape:

1. add one small helper that requires a mapping to contain a specified identity field set and checks exact equality against an independently constructed expected mapping;
2. use that helper for canonical terminal-report full-run identity;
3. derive terminal `execution_id` from the now-required terminal full-run identity only;
4. in `validate_checkpoint8_report_and_manifest_identity(..., reconstructed_identity=...)`, require the replay full-run identity and all reconstructed fields before comparison;
5. in that same durable path, require `authorization_and_invocation.proof_expectation.proof_id` and fixture manifest before equality checks;
6. preserve legacy direct-validator behavior only when `reconstructed_identity is None`;
7. do not touch campaign runtime, source/provider code, Scheduler runtime, memory promotion, or database schema.

No test expectation may be weakened merely to obtain GREEN.

## 7. Focused GREEN requirement

After implementation, run only the minimum sufficient set:

- the new DTW-60 identity-presence RED file;
- `tests/test_v2_9_8b_window_15m_checkpoint8_dtw57_durable_reconstruction_red.py`;
- `tests/test_v2_9_8b_window_15m_checkpoint8_independent_inspection_completion.py`;
- `tests/test_v2_9_8b_window_15m_checkpoint8_independent_inspection_integration.py`.

Also inspect consumed DTW-54 artifact `9014056017` read-only with the repaired inspector again and require `CHECKPOINT8_INDEPENDENT_INSPECTION_PASS`.

No broad regression suite is required for this narrow inspector-only repair unless focused evidence exposes unrelated impact.

## Money-usefulness contribution

The repair prevents a clean-memory proof from losing its identity link while still appearing acceptable. Later paper-only comparison is only useful if the report and replay demonstrably refer to the exact campaign/factory/lifecycle/proof evidence that produced the memory.

## What this lane improves

It converts the final known report/replay identity checks from mismatch-only safety to true missing-or-mismatch fail-closed safety.

## What this lane still does not unlock

This design does not unlock:

- a fresh Checkpoint 8 proof;
- WINDOW_15M operational activation;
- WINDOW_1H+;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions;
- trade events;
- paper trade audits;
- PnL;
- wallet/private-key/real-fund/live execution.

## Proof/test needed before completion

DTW-60 design completes only when the next lane demonstrates valid RED for missing required identities. Implementation then requires focused GREEN, consumed-artifact read-only PASS, and a separate readiness review before any one-shot proof authorization may be requested.

## Functionality Risks / Setbacks / Efficiency Blockers

- A repair that accepts outer report identity as a substitute for missing canonical nested full-run identity would preserve the fail-open gap.
- A repair that requires fabricated top-level REPORT_ONLY campaign/run fields would regress DTW-55/DTW-56 correctness.
- A repair that makes all legacy direct helper tests strict without distinguishing durable mode may create unnecessary compatibility churn.
- Report hash and artifact parity must remain valid in RED fixtures so identity absence, not artifact corruption, is the observed failure reason.
- The repair should remain one inspector file plus focused tests; widening into runtime or schema work is not justified by current evidence.

## Stop condition

This lane stops at design. The next lawful lane is deterministic RED for the required identity-presence contract. No implementation or new controlling proof is authorized by this document.
