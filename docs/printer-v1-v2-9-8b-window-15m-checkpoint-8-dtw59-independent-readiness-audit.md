# Printer V1 V2-9.8B WINDOW_15M Checkpoint 8 — DTW-59 Independent Readiness Audit

Date: 2026-08-08

Linear: `DTW-59`

Implementation baseline:

`7f6bcbd574257ba19ec20a0c35217685a2ffce91`

Predecessors:

- DTW-55 structural audit — complete
- DTW-56 durable reconstruction design — complete
- DTW-57 representative deterministic RED — complete
- DTW-58 implementation GREEN — complete

## Verdict

`DTW59_INDEPENDENT_READINESS_BLOCKED_REQUIRED_REPORT_REPLAY_IDENTITY_PRESENCE_NOT_FAIL_CLOSED`

DTW-58 materially repairs the original Checkpoint 8 independent-inspector defect and passes both the representative real-schema fixture and read-only inspection of the consumed DTW-54 artifact. However, the implementation is not yet ready to authorize another controlling proof because three required identity-presence boundaries remain fail-open.

No new Checkpoint 8 proof is authorized by this audit.

## Verified implementation strengths

Static inspection plus the controlling DTW-58 verification confirms that the repaired inspector now correctly:

- resolves campaign run -> `authoritative_run_id` -> factory run UUID;
- keeps campaign-run and factory-run identities separate;
- starts the main acceptance graph from campaign-owned `WINDOW_15M` rows;
- preserves the truthful `PARTIAL_MEMORY` window-layer / `CLEAN_MEMORY` episode-layer separation;
- joins fingerprints through `episode_id` and validates fingerprint payload identity instead of inventing a fingerprint SHA column;
- corroborates exactly 18 factory-run steps using the resolved factory UUID;
- reconstructs 28 campaign Scheduler-work rows and joins them to 28 Scheduler jobs without literal owner-name heuristics;
- validates lifecycle/discovery Scheduler correspondence and lifecycle factory-run identity;
- validates persisted governed source request/response relationships;
- recomputes terminal report hash and byte-equality with the frozen report artifact;
- compares non-vacuous owner/action-local source-transport identity sets;
- understands canonical `report_only.requested_identity`;
- preserves read-only DB safety and frozen safety checks.

DTW-58 controlling verification was run `31237237210`, job `93051907381`: `23 passed in 16.80s`. The consumed historical DTW-54 artifact `9014056017` also returned `CHECKPOINT8_INDEPENDENT_INSPECTION_PASS` under read-only inspection. This is strong implementation evidence, but it is not a fresh controlling Checkpoint 8 proof.

## Blocker 1 — terminal report identity presence is conditional

DTW-56 requires the parsed terminal report identity to contain the exact independently reconstructed:

- campaign id;
- campaign-run id;
- configuration id;
- cycle id;
- factory-run id;
- execution id;
- supervision id.

The committed DTW-58 implementation builds the independently reconstructed identity correctly, but when validating the parsed report it collects only identity fields that are present and non-empty. It raises on mismatch only when at least one value exists.

Therefore a required field can be absent from both inspected report identity carriers without causing a failure.

`execution_id` has a separate non-empty requirement, but its fallback may be taken from replay identity. That means the terminal report itself can omit execution identity while another carrier supplies it.

This violates DTW-56 Section 9, which requires the parsed report identity itself to contain the reconstructed identity set.

Required repair: durable-mode terminal-report validation must require every canonical reconstructed identity field to be present and equal. Missing and mismatched are both failures.

## Blocker 2 — replay full-run identity presence is conditional

DTW-56 requires replay `full_run_terminal_evidence.identity` to match the independently reconstructed graph.

The committed implementation checks campaign/run only if the replay identity object is truthy. In the later reconstructed-identity loop it fails only when both `expected` and `observed` are non-empty and differ.

Consequences:

- a missing replay identity object can bypass the nested identity comparison;
- a missing configuration, cycle, factory-run, supervision, or execution id can bypass its comparison;
- only a present-but-wrong value is guaranteed to fail.

This is fail-open relative to DTW-56 Section 10.

Required repair: in durable mode, replay `full_run_terminal_evidence.identity` must exist and must contain every required reconstructed field. Each field must equal the independently reconstructed value. Missing and mismatched are both failures.

## Blocker 3 — replay proof/manifest authorization identity presence is optional

DTW-56 requires replay fixture/proof identity inside `full_run_terminal_evidence.authorization_and_invocation` to match the frozen proof id and fixture manifest.

The committed implementation compares `proof_expectation.fixture_composition_manifest_sha256` and `proof_expectation.proof_id` only if those values are present. If either is absent, no failure is raised.

That means a replay can omit the required proof/fixture binding and still satisfy this part of the inspector.

Required repair: in durable mode, `authorization_and_invocation.proof_expectation` must exist and must contain both the proof id and fixture manifest identity. Both must exactly match the frozen summary. Missing and mismatched are both failures.

## Other reviewed boundaries

### Campaign/factory identity graph

PASS for the currently designed schema. The implementation uses the canonical campaign-run bridge and exact campaign/run/cycle filters. It does not return to the original flat run-id assumption.

### Campaign-owned memory graph

PASS. The implementation starts from campaign windows and requires exact memory-window, clean-episode, and fingerprint linkage. It correctly does not require the memory-window layer itself to claim `CLEAN_MEMORY`.

### Factory-step corroboration

PASS. Factory steps are queried only under the resolved factory UUID and are corroborative rather than the owner of campaign identity.

### Scheduler reconstruction

PASS for DTW-56's current successful C8 shape. The implementation performs exact campaign Scheduler-work -> Scheduler-job joins, validates work families and lifecycle factory UUIDs, and requires terminal/unlocked joined jobs.

### Source Governor/source accounting

PASS for the current design contract. The implementation reconstructs source evidence from canonical report identity sets plus DB request/response/source-link relationships rather than owner-label strings.

### Cleanup/residue

No new blocker was established in this audit. The exact current campaign graph, Scheduler joins, supervision terminal/cleanup fields, unlocked jobs, and no-retry/restart/successor checks are preserved. `orphan_owned_work_count` is materialized as zero after the exact current-run correspondence checks; no contradictory current-run orphan evidence was found. This should remain in the later focused repair regression surface but does not currently justify widening the repair.

### Legacy compatibility fallbacks

The standalone graph/governance validators retain legacy synthetic fallbacks for pre-existing direct unit tests. The durable DB reconstruction supplies the new durable fields, so those fallbacks do not replace the canonical reconstruction path in the successful real-schema flow. No blocker was established here.

## Money-usefulness contribution

This readiness gate protects the usefulness of later memory comparison by ensuring a clean-memory proof cannot be accepted when its terminal report or zero-work replay has lost the exact identity binding to the campaign, factory run, lifecycle, and proof fixture being evaluated. Preventing identity drift is necessary before Printer can trust memory as evidence for later paper-only decisions.

## What this lane improves

DTW-59 distinguishes a successful historical artifact replay from a genuinely fail-closed acceptance contract. It narrows the remaining repair to required identity-presence enforcement instead of reopening discovery, Scheduler, memory generation, or campaign runtime.

## What this lane still does not unlock

This audit does not unlock:

- another Checkpoint 8 proof;
- WINDOW_15M operational activation;
- WINDOW_1H or longer windows;
- retrieval;
- paper decisions;
- BUY/SELL/HOLD;
- positions;
- trade events;
- paper trade audits;
- PnL;
- wallet/private-key/real-fund/live execution capability.

## Minimum next proof/test requirement

Before any fresh Checkpoint 8 authorization may be requested:

1. design the narrow identity-presence repair;
2. add deterministic RED cases proving missing required terminal-report identity, replay full-run identity, and replay proof/manifest identity are currently accepted or fail at the wrong boundary;
3. implement the minimum inspector-only repair;
4. turn those RED cases GREEN while preserving the DTW-57 representative real-schema fixture and nearest inspector compatibility tests;
5. inspect the consumed DTW-54 artifact read-only again;
6. complete a separate closeout/readiness review.

Only after that readiness review passes may a new one-shot Checkpoint 8 authorization be requested from the operator.

## Functionality Risks / Setbacks / Efficiency Blockers

- The main risk is false acceptance caused by absence being treated differently from mismatch.
- The repair must not weaken report hash/artifact parity, campaign/factory cardinality, clean-memory linkage, Scheduler correspondence, Source Governor accounting, or frozen safety.
- Do not broaden the repair into production campaign/runtime/source code; current evidence localizes the remaining issue to independent-inspector identity-presence enforcement and its focused tests.
- Do not rerun the controlling proof to compensate for an inspector contract gap.
- Use the minimum focused regression set; a broad suite is not warranted until a later readiness/closeout checkpoint requires it.

## Stop condition

DTW-59 stops here with readiness blocked. The next lawful lane is a targeted design for the three fail-open identity-presence boundaries. No new controlling proof or authorization request may occur before that repair reaches independent readiness PASS.
