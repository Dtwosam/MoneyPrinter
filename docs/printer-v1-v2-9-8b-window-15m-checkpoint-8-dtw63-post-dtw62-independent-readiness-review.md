# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-63 Post-DTW62 Independent Readiness Review

Date: 2026-08-08

Linear: `DTW-63`

Implementation baseline:

`092a738c2226766aac078036f79ab7d9a901a58e`

## Verdict

`DTW63_INDEPENDENT_READINESS_BLOCKED_CANONICAL_REQUESTED_IDENTITY_HAS_DURABLE_LEGACY_FALLBACK`

DTW-62 closes the three DTW-59 identity-presence gaps and preserves the durable reconstruction built in DTW-58. One remaining fail-open path prevents readiness for another Checkpoint 8 controlling proof: the canonical REPORT_ONLY request identity is still optional in the durable end-to-end path.

No fresh Checkpoint 8 proof is authorized by this review.

## Verified strengths

The committed inspector now fail-closes the previously identified durable identity surfaces:

- canonical terminal `full_run_terminal_evidence.identity` must exist and contain campaign, campaign-run, configuration, cycle, factory-run, supervision, and execution identities;
- terminal execution identity no longer falls back to outer report or replay identity;
- replay `full_run_terminal_evidence.identity` must exist and contain the full independently reconstructed identity when durable `reconstructed_identity` is supplied;
- replay `authorization_and_invocation.proof_expectation` must exist in durable mode and contain exact proof id and fixture manifest identity;
- present-but-wrong values continue to fail at mismatch boundaries;
- the end-to-end inspector supplies `reconstructed_identity=projections.get("identity")`, so the strict durable branches are used by normal frozen-proof inspection;
- campaign-run -> authoritative factory-run resolution, campaign-owned WINDOW_15M graph, PARTIAL_MEMORY window / CLEAN_MEMORY episode separation, fingerprint episode linkage, 18 factory-step corroboration, 28 Scheduler-work -> Scheduler-job correspondence, governed source accounting, terminal report hash/artifact parity, cleanup/residue checks, and frozen safety remain intact.

Controlling DTW-62 verification remains:

- workflow run `31238096105`;
- job `93054290080`;
- `44 passed in 29.19s`;
- consumed DTW-54 artifact `9014056017` returned `CHECKPOINT8_INDEPENDENT_INSPECTION_PASS` under read-only inspection.

That historical-artifact PASS is implementation evidence only; it is not a fresh controlling proof and does not override this readiness blocker.

## Remaining blocker — canonical `report_only.requested_identity` is still optional in durable mode

DTW-60 design defines the public replay request identity as:

`report_only.requested_identity`

and requires it to contain exact:

- `campaign_id`;
- public campaign `run_id`.

The current DTW-62 implementation does this:

1. if `requested_identity` is a dictionary, it requires replay `status == REPLAYED`, `mode == REPORT_ONLY`, and exact campaign/run;
2. otherwise it falls back to top-level `report_only.campaign_id` and `report_only.run_id`.

That fallback executes before the later durable `reconstructed_identity` branch and is not conditioned on legacy/helper mode.

Therefore an end-to-end durable inspection can still accept a replay where:

- canonical `report_only.requested_identity` is absent;
- legacy top-level `campaign_id` and `run_id` are present and exact.

The fallback path also does not require `status == REPLAYED` or `mode == REPORT_ONLY`, so absence of the canonical carrier can bypass both replay-mode checks.

This violates DTW-60's durable-mode rule:

- canonical carriers are mandatory in the end-to-end reconstructed path;
- legacy convenience fallbacks may remain only when no reconstructed durable identity is supplied.

## Required narrow repair

The next repair must change only REPORT_ONLY requested-identity presence semantics.

When `reconstructed_identity is not None`:

1. `report_only.requested_identity` must be a dictionary;
2. it must contain non-empty `campaign_id` and `run_id`;
3. replay `status` must equal `REPLAYED`;
4. replay `mode` must equal `REPORT_ONLY`;
5. requested campaign/run must exactly equal the frozen campaign/run.

Recommended fail-closed boundaries:

- missing carrier or missing/blank required requested-identity field -> `REPORT_REPLAY_REQUESTED_IDENTITY_MISSING`;
- present-but-wrong campaign/run, status, or mode -> existing `REPORT_REPLAY_IDENTITY_MISMATCH`.

Only when `reconstructed_identity is None` may the existing top-level campaign/run fallback remain for legacy direct-helper compatibility.

## Other reviewed boundaries

### Terminal canonical identity

PASS. The nested terminal full-run identity is mandatory in durable reconstruction; outer report identity is supplemental parity only and cannot backfill missing canonical values.

### Replay nested full-run identity

PASS. Durable mode requires the nested identity and all seven reconstructed fields. Legacy fallback is isolated to calls without reconstructed identity.

### Replay proof expectation

PASS. Durable mode requires nested authorization/proof expectation plus proof id and fixture manifest. Top-level replay manifest fields do not substitute for missing nested proof expectation.

### Campaign/factory graph, memory, Scheduler, and source accounting

No new blocker found. DTW-58/62 behavior remains consistent with DTW-55/56 and the accepted DTW-57 contract.

### Cleanup/residue and frozen safety

No new blocker found. Current-run Scheduler/work termination, lease release, retry/reuse locks, zero protected-capability deltas, zero longer-window counts, and read-only DB safety remain enforced.

### End-to-end durable-mode wiring

PASS. `inspect_checkpoint8_frozen_proof_directory` invokes `validate_checkpoint8_report_and_manifest_identity(..., reconstructed_identity=projections.get("identity"))`; therefore fixing the conditional requested-identity branch will affect the real durable acceptance path.

## Money-usefulness contribution

A replay request identity binds the zero-work replay to the exact campaign/run being reviewed. Requiring the canonical carrier prevents a later memory proof from appearing trustworthy when the replay request itself has drifted into a legacy or ambiguous identity shape. That protects the reliability of later clean-memory comparison before any paper-only decision lane.

## What this lane improves

DTW-63 narrows the final known inspector readiness issue to one canonical REPORT_ONLY carrier. It avoids reopening the already-correct campaign graph, Scheduler/source accounting, memory linkage, or runtime architecture.

## What this lane still does not unlock

This review does not unlock:

- a fresh Checkpoint 8 proof;
- WINDOW_15M operational activation;
- WINDOW_1H or longer windows;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions;
- trade events;
- paper trade audits;
- PnL;
- wallet/private-key/real-fund/live execution.

## Minimum next proof/test requirement

Before another Checkpoint 8 authorization may be requested:

1. design the narrow canonical requested-identity repair;
2. add deterministic RED proving a missing `requested_identity` cannot be substituted by exact top-level campaign/run fields in durable mode;
3. include a case proving the legacy fallback cannot bypass `REPLAYED` / `REPORT_ONLY` in durable mode;
4. implement the minimum inspector-only repair;
5. run the new RED-to-GREEN cases plus DTW-61, DTW-57, and the nearest existing inspector compatibility tests;
6. inspect the consumed DTW-54 artifact read-only again;
7. complete a separate independent readiness review.

Only after that review passes may a new one-shot Checkpoint 8 authorization be requested from the operator.

## Functionality Risks / Setbacks / Efficiency Blockers

- Do not remove legacy direct-helper fallback globally; scope strictness to durable mode using `reconstructed_identity`.
- Do not let top-level replay campaign/run substitute for missing canonical `requested_identity` in durable mode.
- Preserve the existing mismatch boundary for wrong status/mode/campaign/run.
- Do not broaden the repair into campaign runtime, discovery, Source Governor, Scheduler, memory generation, schema, or provider code.
- Use only the focused regression surface needed for this one conditional acceptance path.

## Stop condition

DTW-63 stops here with readiness blocked. The next lawful lane is a narrow design for canonical REPORT_ONLY requested-identity presence. No fresh controlling proof or authorization request may occur before that repair reaches independent readiness PASS.
