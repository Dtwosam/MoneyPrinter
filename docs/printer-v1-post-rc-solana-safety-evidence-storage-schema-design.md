# Solana Safety Evidence Storage Schema Design

This is a pre-Lane-7 Post-RC storage schema design.

It is not Lane 7. It is not a real migration. It is not source adapter implementation. It does not call Solana RPC, GoPlus, RugCheck, or any external API. It does not mutate the persistent DB, create source rows, create token snapshots, create context rows, build memory windows, run retrieval, create paper decisions, unlock BUY, create paper positions, create paper trade events, or create PnL.

## Current Blocker Summary

Current state:

- `SAFETY_UNKNOWN` remains a hard clean-memory blocker.
- `clean_memory_count` remains `0`.
- Clean eligible memory count remains `0`.
- Lane 7 remains blocked.
- Retrieval remains blocked.
- Paper decisions remain blocked.
- Paper positions remain `0`.
- Paper trade events remain `0`.
- PnL remains unavailable.

The previous Solana safety evidence fixture contract defined the evidence semantics. This document proposes how a future storage shape could preserve that evidence, link it to governed source traces, attach it to token/pair/snapshot/window evidence, and keep stale, failed, missing, high-risk, mismatched, or non-paper-context evidence audit-only.

## Proposed Future Table Shape

Proposed future table name:

- `printer_solana_safety_evidence`

This is only a proposed design. It is not a migration.

The current `printer_safety_rug_snapshots` table already stores useful safety/rug context fields. A future table or migration should be considered only if the existing table cannot cleanly represent governed source trace linkage, snapshot/window targeting, paper-only context, freshness, and target-match audit states.

| Candidate field | Suggested requirement | Purpose |
|---|---:|---|
| `id` | Required | Primary key. |
| `token_id` | Required | Links safety evidence to the tracked Solana token. |
| `pair_id` | Nullable | Required for pair-scoped liquidity/lock evidence; nullable only for token-level-only evidence. |
| `snapshot_id` | Required when evidence is attached to an evidence window | Links evidence to the token snapshot used by a memory window. |
| `memory_window_id` | Nullable | Links directly to a memory window when available. |
| `evidence_window_id` | Nullable | Optional future link if evidence-window abstraction is used separately from memory windows. |
| `safety_evidence_role` | Required | Candidate value: `TOKEN_SAFETY_CONTEXT`. |
| `source_name` | Required | Governed source name, such as a future Solana RPC or GoPlus-style source. |
| `source_status` | Required | Existing source status label: `COMPLETE`, `PARTIAL`, `FAILED`, `STALE`, or `CONFLICTING`. |
| `data_quality_label` | Required | Existing data quality label: `CLEAN_DATA`, `ACCEPTABLE_PARTIAL_DATA`, `DIRTY_DATA`, `STALE_DATA`, `MISSING_CRITICAL_DATA`, `CONFLICTING_DATA`, or `DO_NOT_TRAIN`. |
| `target_status` | Required | Candidate values: `TARGET_MATCH`, `TARGET_MISMATCH`, `TARGET_UNKNOWN`. |
| `evidence_captured_at` | Required for clean eligibility | Source evidence capture timestamp. Missing capture time remains unknown/audit-only. |
| `freshness_label` | Required | Candidate values: `SAFETY_EVIDENCE_FRESH`, `SAFETY_EVIDENCE_ACCEPTABLE`, `SAFETY_EVIDENCE_STALE`, `SAFETY_EVIDENCE_UNKNOWN`. |
| `mint_authority_status` | Candidate safety field | Candidate values: `MINT_AUTHORITY_RENOUNCED`, `MINT_AUTHORITY_PRESENT`, `MINT_AUTHORITY_UNKNOWN`. |
| `freeze_authority_status` | Candidate safety field | Candidate values: `FREEZE_AUTHORITY_DISABLED`, `FREEZE_AUTHORITY_PRESENT`, `FREEZE_AUTHORITY_UNKNOWN`. |
| `metadata_mutability_status` | Candidate safety field | Candidate values: `METADATA_IMMUTABLE`, `METADATA_MUTABLE`, `METADATA_UNKNOWN`. |
| `supply_sanity_label` | Candidate safety field | Candidate values: `SUPPLY_SANITY_OK`, `SUPPLY_SANITY_CAUTION`, `SUPPLY_SANITY_UNKNOWN`. |
| `holder_concentration_label` | Candidate safety field | Candidate values: `HOLDER_CONCENTRATION_HEALTHY`, `HOLDER_CONCENTRATION_CONCENTRATED`, `HOLDER_CONCENTRATION_EXTREME`, `HOLDER_CONCENTRATION_UNKNOWN`. |
| `liquidity_lock_or_burn_label` | Candidate safety field | Candidate values: `LIQUIDITY_LOCK_OR_BURN_CONFIRMED`, `LIQUIDITY_LOCK_OR_BURN_UNKNOWN`, `LIQUIDITY_UNLOCKED_OR_DANGEROUS`. |
| `known_risk_flag_label` | Candidate safety field | Candidate values: `NO_KNOWN_RISK_FLAGS`, `KNOWN_RISK_FLAGS_PRESENT`, `KNOWN_RISK_FLAGS_UNKNOWN`. |
| `token_program_label` | Candidate safety field | Candidate values: `SPL_TOKEN_OR_TOKEN_2022_VERIFIED`, `TOKEN_PROGRAM_UNKNOWN`, `TOKEN_PROGRAM_UNSUPPORTED`. |
| `safety_context_label` | Required normalized context label | Existing-compatible label such as `SAFETY_CLEAN`, `SAFETY_CAUTION`, `SAFETY_SUSPICIOUS`, `SAFETY_UNSAFE`, `SAFETY_UNKNOWN`, or `SAFETY_DO_NOT_USE_FOR_MEMORY`. |
| `source_request_id` | Nullable, required for clean eligibility | Future foreign-key style link to `printer_source_requests`. |
| `source_response_id` | Nullable | Future link to `printer_source_responses` when a response exists. |
| `source_failure_id` | Nullable | Future link to `printer_source_failures` when collection fails. |
| `paper_only_context` | Required | Must be true. Non-paper context is invalid for V1 memory. |
| `created_at` | Required | Local row creation timestamp; not a clean-evidence differentiator by itself. |

No field above assumes that one future source provides everything. Source-specific fields must be verified during a later governed source task.

## Required Constraints

Future storage should enforce or audit these constraints:

- `token_id` is required.
- `snapshot_id` is required when evidence is attached to an evidence window.
- `pair_id` is optional only when the evidence is genuinely token-level and not pair/liquidity scoped.
- `paper_only_context` must be true.
- Source trace is required for clean eligibility.
- If source succeeds, `source_request_id` and `source_response_id` should be present.
- If source fails, `source_request_id` and `source_failure_id` should be present.
- Stale evidence cannot be clean.
- Failed evidence cannot be clean.
- Missing evidence remains `SAFETY_UNKNOWN`.
- Target mismatch cannot be clean.
- High-risk or blocked evidence cannot become clean.
- Caution evidence cannot unlock clean memory by itself.
- No live execution fields.
- No wallet, private key, signing, signature, or transaction fields.
- No score, ranking, confidence, weighted, or numeric decision fields.

## Label Mapping From Storage

Stored evidence can later support categorical labels only:

| Storage state | Existing-compatible label |
|---|---|
| Complete, fresh, target-matched, governed source trace, paper-only, no known risk, authority/distribution/liquidity evidence acceptable | `SAFETY_CLEAN` plus `SAFETY_CONTEXT_CLEAN` |
| Known cautionary evidence, such as mutable metadata, present authority, concentrated holders, or partial-but-auditable fields | `SAFETY_CAUTION` or `SAFETY_SUSPICIOUS` plus `SAFETY_CONTEXT_PARTIAL` |
| High-risk, dangerous, unsupported, non-paper-context, missing source trace, or do-not-train evidence | `SAFETY_UNSAFE` or `SAFETY_DO_NOT_USE_FOR_MEMORY` plus `SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY` |
| Missing, unknown, untraceable, or incomplete critical safety evidence | `SAFETY_UNKNOWN` plus `SAFETY_CONTEXT_UNKNOWN` |
| Stale evidence | Existing safety label may remain visible for audit, but payload quality must be `SAFETY_CONTEXT_STALE` |
| Target mismatch or source conflict | `SAFETY_UNKNOWN` plus `SAFETY_CONTEXT_CONFLICTING` |

There is no safety score, ranking, confidence percentage, weighted safety system, or BUY signal in this storage design.

## Audit Behavior

Future audit should treat storage states as follows:

- Complete known safety evidence: may satisfy only the safety portion of clean-memory eligibility if all other context gates also pass.
- Caution safety evidence: visible caution; cannot unlock clean memory by itself.
- Blocked/high-risk safety evidence: blocks clean eligibility and remains audit-visible.
- Missing safety evidence: remains `SAFETY_UNKNOWN` and blocks clean eligibility.
- Stale safety evidence: remains audit-only and blocks clean eligibility.
- Failed source safety evidence: remains audit-only and blocks clean eligibility.
- Target mismatch: blocks clean eligibility and should report the intended target versus evidence target when available.
- Missing Source Governor trace: blocks clean eligibility even if the payload looks complete.
- Non-paper-context evidence: invalid for V1 memory and must not become clean.

Audit output should not hide source failures, stale evidence, target mismatch, or unknown labels.

## Source Governor Linkage

Future safety evidence must link to governed source records:

- `source_request_id` links to the approved source request.
- `source_response_id` links to the normalized response when collection succeeds.
- `source_failure_id` links to the failure when collection fails.

Safety evidence without proper governed source trace must remain audit-only. The memory engine, paper decision engine, retrieval engine, and scheduler job handler must not call safety sources directly.

## Central Scheduler Linkage

Future safety evidence collection must be:

- Scheduled.
- Bounded.
- Operator-approved during manual proof.
- Non-continuous.
- Non-spammy.
- Governed by existing scheduler priority.
- Safe under `TRACKED_TOKEN_SAFETY_LIQUIDITY_REFRESH` or a later explicitly approved equivalent.

No runtime expansion, source loop, source spam, paper decision unlock, BUY unlock, paper position, trade event, or PnL may come from safety storage.

## Clean-Memory Gate Preservation

Safety evidence alone cannot make memory clean.

Safety evidence only helps resolve the `SAFETY_UNKNOWN` blocker. These blockers can still prevent clean memory:

- `ENTRY_UNKNOWN`
- `EXIT_UNKNOWN`
- `FLOW_UNKNOWN`
- `UNKNOWN` market regime
- `SOLANA_UNKNOWN` chain heat
- stale source evidence
- failed source evidence
- target mismatch
- incomplete memory window evidence

Dirty, stale, failed, target-mismatched, high-risk, non-paper-context, or audit-only safety evidence cannot enter retrieval. Safety evidence alone cannot create paper decisions, BUY, paper positions, paper trade events, or PnL.

## Fixture-Only Test Plan

Fixture-only tests should prove:

- Proposed required fields are present.
- `token_id` is required.
- Snapshot linkage is required for evidence-window clean eligibility.
- `paper_only_context` must be true.
- Source trace is required for clean eligibility.
- Stale evidence maps to audit-only.
- Failed evidence maps to audit-only.
- Missing evidence remains `SAFETY_UNKNOWN`.
- Target mismatch blocks clean eligibility.
- High-risk/blocked fixture blocks clean eligibility.
- Caution fixture does not unlock clean memory alone.
- No score, ranking, confidence, or weighted fields are present.
- No wallet, private-key, signature, transaction, or live-execution fields are present.
- Safety evidence alone does not unlock clean memory.
- Safety evidence alone does not unlock retrieval.
- Safety evidence alone does not create paper decisions.
- Safety evidence alone does not create positions, trade events, or PnL.

## Non-Goals

This task does not:

- Add a real migration.
- Mutate the DB.
- Add a source adapter.
- Call a live API.
- Call live RPC.
- Collect source data.
- Create source request, response, or failure rows.
- Build or rebuild memory.
- Run retrieval.
- Create a paper decision.
- Unlock BUY.
- Create paper positions.
- Create paper trade events.
- Create PnL.
- Activate Lane 7.

## Recommended Next Safe Task

Recommended next safe task:

- `Flow Evidence Fixture Contract`

Why:

- Safety now has fixture semantics and a storage proposal.
- Entry/exit quote evidence already has fixture and storage design.
- Flow direction and flow pressure remain blockers, and the build order says existing DexScreener raw/normalized data may already help.
- The next shortest safe step is fixture-only flow evidence mapping, without live fetches, source adapter changes, DB mutation, retrieval, paper decisions, BUY, positions, or PnL.

Lane 7 remains blocked until clean eligible memory exists.
