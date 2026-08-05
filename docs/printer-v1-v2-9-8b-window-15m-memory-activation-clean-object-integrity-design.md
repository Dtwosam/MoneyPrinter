# Printer V1 V2-9.8B — WINDOW_15M Memory-to-Activation and Clean-Object Integrity Design

## 1. Design status

**Design date:** 2026-08-05  
**Baseline branch:** `agent/v2-9-8b-window-15m-authorization-retention-integration-repair`  
**Baseline HEAD:** `3f4a7ad4ea653fec7ece4e6a469643898260cd87`  
**Predecessor audit verdict:** `V2_9_8B_WINDOW_15M_FULL_MEMORY_PATH_READINESS_AUDIT_BLOCKED`  
**Design verdict:** `V2_9_8B_WINDOW_15M_MEMORY_ACTIVATION_CLEAN_OBJECT_INTEGRITY_DESIGN_READY`

This is a design/specification artifact only. It authorizes no proof, provider contact, discovery run, Central Scheduler runtime, memory generation, operational authorization, authoritative-database mutation, retrieval, paper decision, BUY/SELL/HOLD, position, trade, audit, PnL, wallet, signing, funding, or live execution.

## 2. Goal

Repair the complete operational `WINDOW_15M` memory path so that:

1. memory-observation eligibility remains independent from holder-pass eligibility;
2. the neutral four-candidate freeze is the only post-filter selection authority;
3. activation reuses exact retained source evidence rather than manufacturing new request/response rows;
4. present tracking feasibility is enforced before freeze and revalidated atomically at handoff;
5. a clean episode and its exact canonical fingerprint are committed as one clean object.

A later `WINDOW_15M` authorization remains prohibited until implementation, focused offline verification, independent read-only review, and repair closeout all pass.

## 3. Source-stack alignment

This design sits inside the active V2-9.8B lane and preserves the required major-section order:

```text
audit/readiness
→ design/specification
→ implementation
→ focused offline test
→ independent read-only review
→ closeout
→ separately explicit authorization only after all gates pass
```

It preserves:

- Solana-only and Solana memecoin-only;
- paper-only V1;
- Source Governor ownership;
- Central Scheduler ownership;
- `WINDOW_15M` as the only operational main window;
- `WINDOW_5M_MICRO_EVENT` as support-only;
- longer-window locks;
- no scoring, ranking, confidence, weighting, embeddings or vectors;
- no retrieval, paper decisions, BUY/SELL/HOLD, positions, trades, audits or PnL.

## 4. Approaches considered

### Approach A — Purpose-scoped path inside the existing combined activation owner

Add one typed `MEMORY_OBSERVATION` activation contract to the existing combined executor. The executor keeps ownership of persistence, exact gates, Scheduler work and atomic handoff, but it uses a mode-specific retained-evidence projection and does not rerun holder admission or selection.

**Advantages**

- preserves the existing authoritative handoff owner;
- preserves Scheduler and cleanup behavior;
- avoids duplicating tracking, slot, batch and terminal logic;
- allows legacy modes to remain unchanged;
- keeps the repair narrowly scoped.

**Cost**

- requires a clearly separated mode path inside a large existing module.

### Approach B — New dedicated memory activation executor

Create a second executor that owns retained-evidence projection, gates and handoff.

**Rejected for this repair:** it would duplicate mature batch, slot, tracking, Scheduler, rollback and terminal behavior, creating two activation authorities.

### Approach C — Directly write the frozen pair into tracking and lifecycle

Bypass the combined executor and materialize the handoff from the authoritative campaign.

**Rejected:** this would weaken the Central Scheduler/activation ownership architecture and make source, gate and rollback parity harder to audit.

### Decision

Use **Approach A**, supported by two focused helper modules:

- a typed immutable memory-activation contract;
- a single transactional clean-object promotion owner.

## 5. End-to-end target flow

```text
measured graduated supply
→ exact market/protocol candidate facts
→ current tracking-feasibility assessment
→ holder context enrichment
→ MEMORY_OBSERVATION_ELIGIBLE rows
→ neutral four-candidate freeze
→ immutable ordered selected pair + report-only alternates
→ readiness bundle with exact retained-evidence references
→ combined executor in MEMORY_OBSERVATION mode
→ retained-evidence projection with zero new source operations
→ exact gate validation, no holder gate and no second selector
→ atomic two-slot handoff in frozen order
→ WINDOW_15M factory
→ exact snapshots and close
→ context + E2Q
→ atomic clean episode + fingerprint
→ terminal acceptance requires a complete current-run clean object
```

## 6. Immutable memory-activation contract

Create a focused contract module, preferably:

`src/printer_v1/discovery/memory_observation_activation.py`

### 6.1 `RetainedEvidenceReference`

One exact reference to evidence already produced by a governed source operation.

Required fields:

- `evidence_role`
  - `ORIGIN_LINEAGE`
  - `PUMPSWAP_CONFIRMATION`
  - `MARKET_OBSERVATION`
- `source_name`
- `request_kind`
- `source_request_id`
- `source_response_id`
- `source_failure_id` — must be `None` for activation-eligible retained evidence
- `transport_identity_keys`
- `observed_at`
- `raw_payload_hash`
- `target_mint`
- `target_pool`
- `campaign_id`
- `campaign_run_id`
- `cycle_id`

The contract must not contain secrets, URLs, hostnames, API keys, authorization headers, wallet material, scores, ranks, confidence values, or financial instructions.

### 6.2 `TrackingFeasibility`

Required fields:

- `eligible`
- `reason_code`
- `tracking_queue_id`
- `tracking_queue_status`
- `requalification_required`
- `cooldown_until`
- `assessed_at`

The boolean must come from the existing exact tracking-handoff assessment. Do not infer eligibility by parsing a category string.

### 6.3 `FrozenMemoryActivationCandidate`

Required fields:

- `slot_ordinal`
- `mint`
- `pool`
- `market_identity`
- `lifecycle_identity`
- `activation_route`
- `provenance`
- `memory_observation_eligible`
- `fully_eligible`
- `holder_condition`
- `holder_evidence_status`
- `future_action_eligibility`
- `evidence_expires_at`
- `liquidity_observed_at`
- `tracking_feasibility`
- `retained_evidence_references`

Hard requirements:

- exact Solana mint/pool identity;
- exact Pump/PumpSwap lifecycle;
- `memory_observation_eligible=True`;
- holder status may be pass, fail or categorical unknown;
- `fully_eligible=True` only after an actual holder pass;
- slot ordinals exactly `1` and `2`;
- selected candidates distinct by mint and pool;
- evidence unexpired at freeze time;
- current tracking feasibility eligible.

### 6.4 `FrozenMemoryActivationSet`

Required fields:

- `activation_purpose="MEMORY_OBSERVATION"`
- `readiness_id`
- `selection_seed`
- `selected` — exactly two candidates in authoritative slot order
- `alternates` — exactly two report-only candidates when freeze succeeds
- `manifest_request_ids`
- `manifest_transport_identity_keys`
- `frozen_at`
- `expires_at`

The combined executor receives only `selected` as activation authority. Alternates remain reporting evidence and may never be substituted automatically.

## 7. Pre-freeze tracking-feasibility repair

The existing exact tracking-handoff assessment must be projected separately from holder concentration.

Before constructing `observation_rows`:

1. derive `TrackingFeasibility` from the existing exact assessment;
2. require `eligible=True`;
3. require `requalification_required=False`;
4. require the evidence to be current at the same admission cutoff;
5. exclude/defer ineligible candidates before freeze;
6. persist the categorical reason in diagnostics and existing candidate/reserve evidence;
7. do not convert a tracking-ineligible candidate into `MEMORY_OBSERVATION_ELIGIBLE`.

Holder concentration remains non-blocking for memory. Tracking feasibility remains mandatory because it determines whether the selected identity can lawfully enter the existing tracking lifecycle.

At atomic handoff, re-run the existing identity-based tracking assessment for both selected candidates. If either no longer passes, rollback the complete two-slot handoff and return the exact first blocker. Do not select an alternate.

## 8. Single post-filter selection authority

`freeze_eligible_reserve()` remains the only post-filter selector.

The authoritative campaign must create `FrozenMemoryActivationSet.selected` directly from the freeze's ordered selected rows.

In `MEMORY_OBSERVATION` mode, the combined executor must:

- validate the frozen pair;
- preserve its order;
- skip `_select()` and `_categorical_two_slot()`;
- skip latest/non-latest quotas and provider-channel ordering;
- never substitute an alternate;
- block the entire pair if one candidate fails an exact gate;
- use selection reason `memory_observation_frozen_selection`;
- persist exact slot ordinal and frozen identity in handoff/report evidence.

Legacy initial/replacement modes keep their current selector and holder contract.

## 9. Holder-context separation

In `MEMORY_OBSERVATION` mode:

- do not append `HOLDER_EVIDENCE_INELIGIBLE`;
- do not treat holder fail, unavailable or budget-bound unknown as an evidence-quality failure for memory activation;
- preserve holder facts in candidate evidence and readiness reporting;
- keep `FULLY_ELIGIBLE` limited to actual holder pass;
- keep `future_action_eligibility` blocked or unknown when holder evidence does not pass;
- do not unlock any action, retrieval or financial capability.

Evidence-quality gates still reject dirty, stale, failed, mismatched, untraceable or expired source evidence.

## 10. Retained-evidence projection

### 10.1 Rule

A retained fact is not a new source operation.

The combined executor must not call `_governed_request()` or `_store_response()` for evidence already produced during measured graduated supply.

### 10.2 Validation

Before projection, validate each `RetainedEvidenceReference` against the authoritative database and immutable manifest:

- request row exists;
- response row exists and belongs to that request;
- request/response source name and request kind match;
- response is complete and clean;
- no source failure is being presented as a successful response;
- mint/pool/role match the selected candidate;
- request ID is in `manifest_request_ids`;
- transport identity keys are present in `manifest_transport_identity_keys`;
- campaign/run/cycle ownership matches;
- raw hash and observation time match retained evidence;
- no request or response row is inserted during validation.

Any mismatch blocks before handoff.

### 10.3 Projection

A mode-specific retained-evidence work item may create:

- discovery work and Scheduler ownership rows;
- provider-observation projection rows;
- merged-candidate rows;
- origin-verification rows;
- PumpSwap-confirmation rows;
- selection/handoff rows.

Those rows must reference the original source request/response IDs. They may not manufacture a new source operation.

Use a categorical payload marker such as:

`evidence_reuse_kind="RETAINED_GOVERNED_EVIDENCE_REFERENCE"`

This marker is audit metadata, not a source or transport.

### 10.4 Reconciliation

Capture source request/response counts immediately before retained projection and after atomic handoff.

Required report:

- `manifest_request_ids`
- `activation_reference_request_ids`
- `new_source_request_ids`
- `new_source_response_ids`
- `unmanifested_reference_ids`
- `missing_transport_identity_keys`
- `reconciliation_status`

PASS requires:

- zero new source request IDs;
- zero new source response IDs;
- every activation reference in the manifest;
- every required measured transport identity present;
- no whole-table inference;
- no count-only transport acceptance.

## 11. Readiness carrier repair

Keep existing `latest` and `persisted` database fields for compatibility; do not add a migration solely to rename them.

The readiness payload and terminal report must add:

- `ordered_selected_candidates`
- explicit `slot_ordinal`
- exact mint/pool/market identity
- true provenance
- `legacy_role_field` marked as positional compatibility only
- holder condition and future-action status
- tracking feasibility
- retained evidence reference IDs

`liquidity_observed_at` must come from the candidate's exact retained market evidence, not report generation time.

The readiness bundle must fail closed when selected order, retained evidence, tracking feasibility, expiry or identity is incomplete.

## 12. Combined executor mode

Add a typed mode/purpose field to `CombinedDiscoveryFixtures` or a dedicated input object. Avoid a loose boolean collection.

Suggested value:

`activation_purpose="MEMORY_OBSERVATION"`

Mode-specific work plan:

1. retained-evidence projection;
2. identity merge;
3. origin verification;
4. PumpSwap confirmation;
5. fixed eligibility validation;
6. frozen-selection validation;
7. slot-1 handoff;
8. slot-2 handoff.

Every work item remains owned by Central Scheduler and follows existing terminal parity.

The mode must not:

- contact a source;
- run direct or secondary provider lanes;
- create a source request/response/failure;
- perform a second selection;
- invoke holder gating;
- activate an alternate.

## 13. Atomic clean-object promotion

Create one transactional owner, preferably:

`src/printer_v1/memory/clean_object_promotion.py`

This becomes the only path used by E2Z/Lane K to create a new `CLEAN_MEMORY` episode.

### 13.1 Transaction

For one window:

```text
BEGIN
→ load and gate exact window
→ inspect existing episode/fingerprint state
→ insert episode when absent
→ build exact fingerprint from window + episode
→ validate fingerprint identity
→ insert fingerprint
→ validate complete pair
→ COMMIT
```

Any failure before commit rolls back both new rows.

### 13.2 Exact clean-object invariant

A complete clean object requires:

- one `CLEAN_MEMORY` episode;
- one `STATIC_CONDITION_SUMMARY` fingerprint;
- episode links exact window;
- episode/window token and pair match;
- fingerprint payload episode/window/token/pair IDs match;
- identity fields are never `UNKNOWN`;
- window kind matches;
- memory quality is clean;
- no duplicate episode or fingerprint.

Non-identity categorical context may remain `UNKNOWN` only when the clean-context gates allow it.

### 13.3 Existing-state behavior

- no episode and no fingerprint: create both atomically;
- exact complete pair: return idempotent already-exists;
- existing clean episode without fingerprint: block as `EXISTING_INCOMPLETE_CLEAN_OBJECT`;
- fingerprint without exact episode: block;
- any identity mismatch: block;
- do not silently backfill or rewrite historical incomplete clean objects in this repair.

### 13.4 Integration

Refactor `create_clean_memory_from_window()` into a compatibility wrapper around the atomic owner, preserving existing return fields and adding `fingerprint_id`.

Remove the separate post-episode `_attach_fingerprint_for_episode()` path from Lane K.

For each current-window promotion result, Lane K reports:

- episode ID;
- fingerprint ID;
- atomic status;
- idempotent status;
- exact blocker when blocked.

## 14. Factory close and campaign acceptance

`_execute_close()` must distinguish:

1. legitimate dirty/partial/no-promotion outcome;
2. clean candidate blocked by an atomic integrity failure.

A clean-object integrity failure sets the close result to blocked/failed with the exact categorical cause. A legitimate dirty or partial window may still close honestly without a clean episode.

Current-run campaign acceptance must require:

- no incomplete clean object for the run;
- each promoted current-run clean episode has one exact fingerprint;
- exact selected slot identity reaches the matching window/episode/fingerprint;
- no unrelated promotion;
- no financial or retrieval deltas.

## 15. Idempotency and failure behavior

- repeated retained-evidence validation performs no source write;
- repeated activation over an already active/conflicting target blocks through existing tracking rules;
- repeated complete clean-object promotion creates no new row;
- first terminal cause remains immutable;
- no automatic retry, alternate substitution, resume, restart or successor;
- cleanup reaches all campaign-owned Scheduler work and locks;
- report-only replay performs zero source requests and zero writes.

## 16. Expected file scope

### New focused modules

- `src/printer_v1/discovery/memory_observation_activation.py`
- `src/printer_v1/memory/clean_object_promotion.py`

### Likely modifications

- `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- `src/printer_v1/discovery/permanent_discovery_availability.py`
- `src/printer_v1/operator_cli/pilot_input_readiness.py`
- `src/printer_v1/discovery/combined_executor.py`
- `src/printer_v1/operator_cli/origin_lifecycle_campaign.py`
- `src/printer_v1/operator_cli/one_command_15m_factory.py`
- `src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py`
- `src/printer_v1/operator_cli/e2z_clean_memory_creation.py`
- `src/printer_v1/memory/fingerprints.py`
- current-run acceptance/reporting modules only where exact new fields are required

### Tests

Create one main focused repair suite and extend only directly owned unit suites where useful.

No migration is expected. If exact retained-evidence reference cannot be represented with the existing schema, stop and report the schema design blocker rather than manufacturing source rows or adding an unreviewed migration.

## 17. Focused offline verification

Use isolated temporary databases only.

Required cases:

1. holder-pass selected candidate activates;
2. holder-fail selected candidate activates for memory but stays future-action blocked;
3. holder-unavailable candidate activates for memory;
4. budget-bound holder unknown activates for memory;
5. legacy non-memory holder behavior is unchanged;
6. frozen order reaches slots 1 and 2 unchanged;
7. same-category frozen pair is not reordered;
8. no alternate substitution;
9. one selected candidate gate failure rolls back the pair;
10. tracking-ineligible candidate cannot enter freeze;
11. post-freeze tracking-state change blocks atomically;
12. retained activation uses original request/response IDs;
13. activation source request/response deltas are zero;
14. missing manifest request blocks;
15. missing transport identity blocks;
16. mismatched mint/pool/source reference blocks;
17. final request manifest is exact and deduplicated;
18. exact liquidity observation time survives readiness;
19. episode and fingerprint commit together;
20. injected fingerprint failure leaves zero new episode and fingerprint;
21. existing complete pair is idempotent;
22. existing incomplete clean episode blocks without mutation;
23. episode/window/token/pair mismatch blocks;
24. factory treats atomic integrity failure as a close blocker;
25. legitimate dirty/no-promotion close remains honest;
26. current-window scope prevents unrelated promotion;
27. report-only replay remains zero-source and zero-write;
28. `WINDOW_15M` only and every permanent lock remains unchanged.

After those pass, run directly affected regression suites only. Do not run a broad repository suite unless a focused failure proves a broader architectural change.

## 18. Acceptance gate

Implementation PASS requires all of the following:

- exact frozen pair and order survive to handoff;
- holder context does not become a memory gate;
- tracking feasibility is mandatory and exact;
- no retained fact creates a false new source request/response;
- request and transport identity reconciliation is exact;
- every new clean episode has its exact fingerprint in the same commit;
- no incomplete clean object remains after injected failures;
- legacy modes remain unchanged;
- authoritative database identity is unchanged;
- no proof, authorization or provider/runtime action occurred;
- all permanent locks remain intact.

## 19. Stop conditions

Stop and return BLOCKED when:

- the repository baseline or branch is wrong;
- the tracked worktree is dirty before work;
- the authoritative database is active or changed;
- exact retained evidence cannot be represented without an unapproved migration;
- source provenance would require a synthetic request/response;
- the frozen pair cannot be preserved without bypassing the existing activation owner;
- a tracking failure would require automatic alternate substitution;
- atomic episode/fingerprint creation cannot use one transaction;
- focused tests expose a conflict with the active source stack;
- any change touches retrieval, decisions, trading, wallets, paid APIs, scoring or longer-window activation.

## 20. Money-usefulness contribution

The design lets Printer learn from real manipulated, concentrated, failed and uncertain Solana memecoin conditions instead of filtering them as if holder concentration proved whether a coin was organic. It also guarantees that selection remains neutral, evidence provenance remains truthful, and a clean memory is never half-created.

## 21. What this design improves

- end-to-end separation between memory usefulness and future-action eligibility;
- stable and auditable token diet;
- exact source provenance;
- lawful tracking handoff;
- clean corpus integrity;
- failure diagnosis without spending another authorization.

## 22. What this design still does not unlock

- no new `WINDOW_15M` authorization;
- no proof;
- no provider contact;
- no discovery or Scheduler runtime;
- no memory generation;
- no longer windows;
- no retrieval;
- no paper decisions;
- no BUY/SELL/HOLD;
- no positions, trades, audits or PnL;
- no wallet, key, signing, funding or live execution.

## 23. Functionality Risks / Setbacks / Efficiency Blockers

| Risk | Impact | Required mitigation |
|---|---|---|
| Purpose mode leaks into legacy selection | Existing paths change unexpectedly | Typed purpose and explicit legacy regression tests |
| Retained references lack enough exact identity | Source provenance cannot be proven | Fail closed; no synthetic source rows |
| Tracking state changes after freeze | Frozen pair becomes unlawful | Atomic handoff revalidation; no reselection |
| Large combined executor becomes harder to reason about | Repair defects hide in mode branches | Put contracts/validators in focused helper module |
| Episode/fingerprint transaction refactor affects legacy tests | Broad churn | Compatibility wrapper and focused regression set |
| Existing incomplete historical clean object exists | New owner cannot safely infer intent | Block and report; separate repair if later approved |
| Mutation-recorder diagnostics fail after a committed complete pair | Campaign acceptance may block despite corpus consistency | Report diagnostic failure separately; never misclassify the pair as incomplete |
| Broad test selection exposes unrelated failures | Scope drift | Document pre-existing failures and stay with minimum sufficient tests |

## 24. Final design verdict

`V2_9_8B_WINDOW_15M_MEMORY_ACTIVATION_CLEAN_OBJECT_INTEGRITY_DESIGN_READY`

This design is sufficient for one bounded implementation branch with focused offline verification. It does not authorize proof or a new operational `WINDOW_15M` attempt.
