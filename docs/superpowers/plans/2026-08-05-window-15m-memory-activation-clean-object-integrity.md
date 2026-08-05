# WINDOW_15M Memory Activation and Clean Object Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the five audited WINDOW_15M memory-path defects while preserving the frozen selection authority, governed evidence provenance, atomic tracking handoff, clean-object integrity, and all V1 locks.

**Architecture:** Add one immutable memory-observation activation contract used by readiness and the existing combined executor, with retained request/response references validated before projection and no new source rows. Add one transaction owner that gates a window, creates its clean episode and canonical fingerprint, validates exact identity, and commits both or neither; E2Z and Lane K become compatibility callers of that owner.

**Tech Stack:** Python 3.12, dataclasses/enums, SQLite migration head 052 as already present, pytest, existing Source Governor/Central Scheduler owners.

## Global Constraints

- Start from tracked baseline `3f4a7ad4ea653fec7ece4e6a469643898260cd87` on the requested repair branch.
- Use isolated temporary databases only; never connect tests to `data/printer_v1.sqlite3`.
- No migration, provider contact, authorization, proof, runtime, retry, alternate substitution, retrieval, financial capability, scoring, ranking, weighting, embeddings, or vectors.
- Preserve legacy non-memory behavior and report-only zero-source/zero-write behavior.
- Make one final logical commit only after all focused verification passes.

---

### Task 1: Immutable memory-observation activation contract

**Files:**
- Create: `src/printer_v1/discovery/memory_observation_activation.py`
- Create: `tests/test_v2_9_8b_window_15m_memory_activation_clean_object_integrity_repair.py`

**Interfaces:**
- Produces: `ActivationPurpose`, `RetainedEvidenceReference`, `TrackingFeasibility`, `FrozenMemoryActivationCandidate`, `FrozenMemoryActivationSet`, and exact validation/reconciliation functions.
- Consumes: existing `printer_source_requests`, `printer_source_responses`, manifest entries, and measured transport identity keys.

- [x] Write tests constructing an exact two-candidate frozen set and asserting holder pass/fail/unavailable/budget-unknown remain valid memory context, exact order is retained, tracking-ineligible candidates fail, and malformed identity/expiry/manifest/transport references fail closed.
- [x] Run the new test module and confirm collection/import fails because the contract module does not exist.
- [x] Implement frozen dataclasses plus runtime validation; use categorical error codes and reject `UNKNOWN` identity fields.
- [x] Run the new contract tests and confirm they pass.

### Task 2: Tracking-before-freeze and truthful readiness carrier

**Files:**
- Modify: `src/printer_v1/operator_cli/authoritative_live_operational_campaign.py`
- Modify: `src/printer_v1/discovery/permanent_discovery_availability.py`
- Modify: `src/printer_v1/operator_cli/pilot_input_readiness.py`
- Test: `tests/test_v2_9_8b_window_15m_memory_activation_clean_object_integrity_repair.py`

**Interfaces:**
- Consumes: `TrackingFeasibility` and the existing `assess_tracking_handoff_by_identity()` result.
- Produces: exact ordered `FrozenMemoryActivationSet`, `ordered_selected_candidates`, positional-only legacy role labels, exact liquidity timestamp, and categorical tracking exclusions.

- [x] Add failing tests showing tracking-ineligible rows cannot enter freeze, exact selected order becomes slot ordinals 1/2, and readiness uses retained `liquidity_observed_at` rather than report time.
- [x] Run those nodes and verify expected failures.
- [x] Project current tracking assessment into observation rows, require eligible/no requalification in freeze, build readiness directly from `freeze.selected`, and persist ordered reporting without changing legacy columns.
- [x] Run the focused nodes and nearest freeze/readiness regressions.

### Task 3: Retained-evidence combined activation

**Files:**
- Modify: `src/printer_v1/discovery/combined_executor.py`
- Modify: `src/printer_v1/operator_cli/origin_lifecycle_campaign.py` only if result/report propagation requires it.
- Test: `tests/test_v2_9_8b_window_15m_memory_activation_clean_object_integrity_repair.py`

**Interfaces:**
- Consumes: `FrozenMemoryActivationSet` on `CombinedDiscoveryFixtures.memory_activation_set`.
- Produces: retained provider projections linked to original request/response IDs and reconciliation with `new_source_request_ids=[]`, `new_source_response_ids=[]`.

- [x] Add failing tests that patch `_governed_request`, `_store_response`, `_select`, and alternate activation to raise, then activate a retained pair and assert original IDs/order reach handoff with zero source deltas.
- [x] Add negative tests for request/response ownership, manifest, transport, mint, pool, and post-freeze tracking mismatch.
- [x] Run the nodes and confirm failures identify the legacy source and selector paths.
- [x] Add the typed memory mode to fixtures; create Scheduler-owned retained projection work, validate exact DB rows, skip source creation/holder gating/normal selector, and atomically revalidate both tracking identities before handoff.
- [x] Run focused activation tests and legacy combined-executor regressions.

### Task 4: Atomic clean episode and fingerprint owner

**Files:**
- Create: `src/printer_v1/memory/clean_object_promotion.py`
- Modify: `src/printer_v1/operator_cli/e2z_clean_memory_creation.py`
- Modify: `src/printer_v1/operator_cli/lane_k_e2z_pipeline_wiring.py`
- Modify: `src/printer_v1/memory/fingerprints.py`
- Modify: `src/printer_v1/operator_cli/one_command_15m_factory.py` only for exact integrity-blocker reporting.
- Test: `tests/test_v2_9_8b_window_15m_memory_activation_clean_object_integrity_repair.py`

**Interfaces:**
- Produces: `promote_clean_object(connection, window_id, ..., fingerprint_writer=record_memory_fingerprint)` returning episode/fingerprint IDs, created/idempotent status, or an exact blocker.
- Preserves: `create_clean_memory_from_window()` public result fields while adding `fingerprint_id`, `atomic_status`, and `idempotent`.

- [x] Add failing tests for atomic creation, injected fingerprint failure rollback, complete-pair replay, incomplete episode block, identity mismatch block, and exact non-UNKNOWN identity payload.
- [x] Run those nodes and confirm the current split-connection path fails them.
- [x] Implement one borrowed-connection transaction owner; validate pre-existing state before mutation and fingerprint identity before commit.
- [x] Refactor E2Z/Lane K to call it and remove `_attach_fingerprint_for_episode()`; categorize clean-object integrity failures while preserving honest dirty/no-promotion closes.
- [x] Run clean-object tests plus E2Z, Lane K, factory, and fingerprint regressions.

### Task 5: Closeout and final verification

**Files:**
- Create: `docs/printer-v1-v2-9-8b-window-15m-memory-activation-clean-object-integrity-repair-closeout.md`
- Include: both operator-supplied audit/design documents and this plan in the final commit.

- [x] Run focused repair tests and directly affected authorization/retention, freeze/holder-budget, holder accounting, combined activation/handoff, Lane K/E2Z/fingerprint, and terminal acceptance regressions.
- [x] Run Python compilation for changed Python files and `git diff --check`.
- [x] Verify the authoritative DB size/mtime/SHA-256 exactly match the baseline and no process/handle is active.
- [x] Write the closeout with exact commands, source reconciliation, atomic evidence, locks, risks, independent-review requirement, and explicit no-proof/no-authorization statement.
- [x] Review the diff against all design requirements, stage only lane files, commit `Repair WINDOW_15M memory activation and clean object integrity`, push only the repair branch, and stop.
