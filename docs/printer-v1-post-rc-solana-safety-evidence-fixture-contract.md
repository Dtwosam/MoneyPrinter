# Solana Safety Evidence Fixture Contract

This is a pre-Lane-7 Post-RC fixture contract.

It is not Lane 7. It is not source adapter implementation. It does not call Solana RPC, GoPlus, RugCheck, Jupiter, DexScreener, or any external API. It does not mutate the persistent DB, create source rows, create snapshots, create context rows, build memory, run retrieval, create paper decisions, unlock BUY, open paper positions, create paper trade events, or create PnL.

## Current Blocker Summary

Current validated state:

- Clean memory count remains `0`.
- Clean eligible memory count remains `0`.
- Retrieval remains blocked.
- Paper decisions remain blocked.
- BUY remains locked.
- Paper positions remain `0`.
- Paper trade events remain `0`.
- PnL remains unavailable.
- Lane 7 remains blocked.

The next hard clean-memory blocker is:

- `safety_status_label: SAFETY_UNKNOWN`

Safety is a protection gate. Printer cannot train clean memory from a token when authority, freeze authority, distribution, liquidity lock/burn, token-program, source trace, or known-risk evidence is missing, stale, failed, mismatched, or invalid for paper-only context.

This contract defines fixture-only evidence states so a later governed source task can be reviewed without inventing safety context.

## Paper-Only Safety Evidence Contract

These are candidate fields for future Solana safety evidence. They are not a migration and are not a runtime implementation. No single future source is assumed to provide all fields.

| Field | Purpose | Notes |
|---|---|---|
| `token_id` | Link evidence to tracked token | Required for target linkage. |
| `pair_id` | Link evidence to tracked pair | Required when pair-scoped safety/liquidity evidence is used. |
| `snapshot_id` | Link evidence to token snapshot | Required for window auditability where available. |
| `safety_evidence_role` | Categorize evidence | Candidate value: `TOKEN_SAFETY_CONTEXT`. |
| `source_name` | Identify governed source | Candidate source only; must be Source Governor routed later. |
| `source_status` | Source result status | Existing labels such as `COMPLETE`, `PARTIAL`, `FAILED`, `STALE`, `CONFLICTING`. |
| `data_quality_label` | Normalized data quality | Existing labels such as `CLEAN_DATA`, `ACCEPTABLE_PARTIAL_DATA`, `STALE_DATA`, `MISSING_CRITICAL_DATA`, `DO_NOT_TRAIN`. |
| `target_status` | Whether evidence targets the intended token/pair/snapshot/window | Candidate values: `TARGET_MATCH`, `TARGET_MISMATCH`, `TARGET_UNKNOWN`. |
| `evidence_captured_at` | Evidence capture timestamp | Missing timestamp remains unknown. |
| `freshness_label` | Evidence freshness | Candidate values: `SAFETY_EVIDENCE_FRESH`, `SAFETY_EVIDENCE_ACCEPTABLE`, `SAFETY_EVIDENCE_STALE`, `SAFETY_EVIDENCE_UNKNOWN`. |
| `mint_authority_status` | Mint authority evidence | Candidate values: `MINT_AUTHORITY_RENOUNCED`, `MINT_AUTHORITY_PRESENT`, `MINT_AUTHORITY_UNKNOWN`. |
| `freeze_authority_status` | Freeze authority evidence | Candidate values: `FREEZE_AUTHORITY_DISABLED`, `FREEZE_AUTHORITY_PRESENT`, `FREEZE_AUTHORITY_UNKNOWN`. |
| `metadata_mutability_status` | Metadata mutability evidence | Candidate values: `METADATA_IMMUTABLE`, `METADATA_MUTABLE`, `METADATA_UNKNOWN`. |
| `supply_sanity_label` | Supply sanity evidence | Candidate values: `SUPPLY_SANITY_OK`, `SUPPLY_SANITY_CAUTION`, `SUPPLY_SANITY_UNKNOWN`. |
| `holder_concentration_label` | Holder distribution evidence | Candidate values: `HOLDER_CONCENTRATION_HEALTHY`, `HOLDER_CONCENTRATION_CONCENTRATED`, `HOLDER_CONCENTRATION_EXTREME`, `HOLDER_CONCENTRATION_UNKNOWN`. |
| `liquidity_lock_or_burn_label` | Lock/burn evidence | Candidate values: `LIQUIDITY_LOCK_OR_BURN_CONFIRMED`, `LIQUIDITY_LOCK_OR_BURN_UNKNOWN`, `LIQUIDITY_UNLOCKED_OR_DANGEROUS`. |
| `known_risk_flag_label` | Known risk evidence | Candidate values: `NO_KNOWN_RISK_FLAGS`, `KNOWN_RISK_FLAGS_PRESENT`, `KNOWN_RISK_FLAGS_UNKNOWN`. |
| `token_program_label` | Token program evidence | Candidate values: `SPL_TOKEN_OR_TOKEN_2022_VERIFIED`, `TOKEN_PROGRAM_UNKNOWN`, `TOKEN_PROGRAM_UNSUPPORTED`. |
| `source_request_id` | Source Governor request trace | Required for future governed evidence. |
| `source_response_id` | Source Governor response trace | Required when source succeeds. |
| `source_failure_id` | Source Governor failure trace | Required when source fails. |
| `paper_only_context` | Explicitly marks evidence as paper-only context | Must be true. |
| `created_at` | Local record timestamp | Not a meaningful differentiator by itself. |

Existing runtime-compatible labels should be preserved:

- `SAFETY_CLEAN`
- `SAFETY_CAUTION`
- `SAFETY_SUSPICIOUS`
- `SAFETY_UNSAFE`
- `SAFETY_UNKNOWN`
- `SAFETY_DO_NOT_USE_FOR_MEMORY`
- `SAFETY_CONTEXT_CLEAN`
- `SAFETY_CONTEXT_PARTIAL`
- `SAFETY_CONTEXT_STALE`
- `SAFETY_CONTEXT_CONFLICTING`
- `SAFETY_CONTEXT_UNKNOWN`
- `SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY`

No safety score, ranking, confidence percentage, weighted label, numeric decision score, or BUY signal is part of this contract.

## Fixture States

| Fixture state | Expected safety result | Expected payload quality | Clean-memory effect |
|---|---|---|---|
| Complete known safety evidence | `SAFETY_CLEAN` or conservative known safety label | `SAFETY_CONTEXT_CLEAN` | May satisfy the safety portion only; cannot make memory clean alone. |
| Caution safety evidence | `SAFETY_CAUTION` or `SAFETY_SUSPICIOUS` | `SAFETY_CONTEXT_PARTIAL` or clean-with-caution label if later approved | Audit-visible caution; cannot unlock clean memory alone. |
| Blocked/high-risk safety evidence | `SAFETY_UNSAFE` or `SAFETY_DO_NOT_USE_FOR_MEMORY` | `SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY` | Blocks clean eligibility. |
| Missing safety evidence | `SAFETY_UNKNOWN` | `SAFETY_CONTEXT_UNKNOWN` | Blocks clean eligibility. |
| Stale safety evidence | Existing safety label may be retained for audit | `SAFETY_CONTEXT_STALE` | Audit-only; blocks clean eligibility. |
| Failed source safety evidence | `SAFETY_UNKNOWN` or `SAFETY_DO_NOT_USE_FOR_MEMORY` | `SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY` | Audit-only; blocks clean eligibility. |
| Target mismatch | `SAFETY_UNKNOWN` or previous label only for audit | `SAFETY_CONTEXT_CONFLICTING` | Blocks clean eligibility. |
| Missing Source Governor trace | `SAFETY_UNKNOWN` | `SAFETY_CONTEXT_UNKNOWN` | Blocks clean eligibility. |
| Non-paper-context evidence | `SAFETY_DO_NOT_USE_FOR_MEMORY` | `SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY` | Invalid for V1 memory. |

## Label Mapping

This fixture contract maps evidence categorically:

- `SAFETY_CONTEXT_KNOWN` maps to existing `SAFETY_CLEAN` only when source status, data quality, target status, freshness, authority, holder distribution, liquidity lock/burn, risk flags, and token program evidence are all acceptable.
- `SAFETY_CONTEXT_CAUTION` maps to existing `SAFETY_CAUTION` or `SAFETY_SUSPICIOUS` when evidence is known but contains cautionary non-fatal issues.
- `SAFETY_CONTEXT_BLOCKED` maps to existing `SAFETY_UNSAFE` or `SAFETY_DO_NOT_USE_FOR_MEMORY` when risk is high, source trace is invalid, target mismatch exists, or non-paper context is used.
- `SAFETY_UNKNOWN` remains `SAFETY_UNKNOWN` when required evidence is missing, unknown, stale, failed, or untraceable.

These mappings are not scores and do not rank tokens.

## Blocking Rules

- Missing safety evidence remains `SAFETY_UNKNOWN`.
- Stale safety evidence remains audit-only.
- Failed source evidence remains audit-only.
- Target mismatch blocks clean eligibility.
- Missing source request/response/failure trace blocks clean eligibility.
- Non-paper-only evidence is invalid for Printer V1 memory.
- High-risk or blocked safety evidence cannot become clean.
- Caution evidence does not unlock clean memory by itself.
- Complete safety evidence only satisfies the safety portion of the clean-memory gate.
- Unknown market, chain, entry realism, exit realism, flow direction, or flow pressure can still block memory even if safety becomes known.

## Source Governor Requirements

Future safety evidence must be source-governed:

- Source request recorded before external collection.
- Source response recorded when data is received.
- Source failure recorded when source fails, rate-limits, times out, or returns malformed data.
- Evidence linked to token/pair/snapshot/window where available.
- Stale, failed, no-data, and malformed evidence remain visible.
- Memory engine must not call Solana RPC, GoPlus, RugCheck, or any source directly.
- Paper decision engine must not call safety sources directly.
- Scheduler must not bypass Source Governor.
- Public/free source limits must be respected.
- Any source that requires paid access remains disallowed for V1.

## Central Scheduler Requirements

Future safety collection must be scheduler-controlled:

- Bounded job only.
- Operator-approved during manual proof.
- No continuous source loop.
- No source spam.
- No runtime expansion without roadmap approval.
- Safety refresh must respect existing priority order, behind open paper monitoring and token snapshots when those exist.
- Safety evidence collection cannot directly unlock decisions or BUY.

## Clean-Memory Gate Preservation

Safety evidence alone cannot make memory clean.

Clean memory still requires:

- Complete evidence window coverage.
- Fresh targeted context.
- Known acceptable safety context.
- Known entry/exit realism where required.
- Known flow where required.
- Market and chain context handled according to roadmap.
- Source failures visible.
- Audit pass.
- Retrieval clean-only.

Dirty memory, audit-only memory, stale safety evidence, failed safety evidence, and target-mismatched safety evidence must not enter retrieval or decisions.

## Fixture-Only Test Plan

Fixture-only tests should prove:

- Complete known fixture maps to a known acceptable safety label.
- Caution fixture maps to caution without unlocking clean memory alone.
- High-risk fixture blocks clean eligibility.
- Missing fixture remains `SAFETY_UNKNOWN`.
- Stale fixture remains audit-only.
- Failed fixture remains audit-only.
- Target mismatch blocks clean eligibility.
- Missing Source Governor trace blocks clean eligibility.
- Non-paper-only evidence blocks clean eligibility.
- Safety evidence alone does not make memory clean.
- Safety evidence alone does not unlock retrieval.
- Safety evidence does not create paper decisions.
- Safety evidence does not create positions.
- Safety evidence does not create trade events.
- Safety evidence does not create PnL.
- No scoring, ranking, confidence, weighted, wallet, signing, transaction, or live-trading fields are introduced.

## Non-Goals

This task does not:

- Add a Solana RPC adapter.
- Add a GoPlus adapter.
- Add a RugCheck adapter.
- Fetch live data.
- Call external APIs.
- Add paid dependencies.
- Add a migration.
- Mutate the persistent DB.
- Create source request, response, or failure rows.
- Create token snapshots.
- Create context rows.
- Build memory windows.
- Run retrieval.
- Create paper decisions.
- Unlock BUY.
- Create paper positions.
- Create paper trade events.
- Create PnL.
- Start Lane 7.

## Recommended Next Safe Task

Recommended next safe task:

- `Solana Safety Evidence Storage Schema Design`

Why:

- This fixture contract defines the evidence semantics.
- The next safe step is to compare those semantics against the existing `printer_safety_rug_snapshots` table and decide whether current storage is sufficient or whether a minimal future migration proposal is justified.
- No source adapter, live RPC call, or DB mutation is needed for that next task.

Lane 7 remains blocked until clean eligible memory exists.
