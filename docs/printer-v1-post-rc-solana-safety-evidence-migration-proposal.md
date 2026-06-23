# Solana Safety Evidence Migration Proposal

This is a proposal-only pre-Lane-7 planning artifact. It does not start Lane 7, does not implement a migration, does not mutate the persistent database, and does not add any source adapter or runtime behavior.

## Current State Summary

Printer V1 remains in the post-RC pre-Lane-7 safety-blocker path.

- Clean memory count remains `0`.
- Clean eligible memory count remains `0`.
- Lane 7 remains blocked.
- Retrieval remains blocked.
- Paper decisions remain blocked.
- BUY remains locked.
- Paper position rows remain `0`.
- Paper trade event rows remain `0`.
- PnL rows remain `0`.
- This document proposes a future migration only.
- No migration file is added by this task.
- No persistent DB mutation is performed by this task.

The immediate blocker addressed here is `safety_status_label: SAFETY_UNKNOWN`. Safety evidence needs durable source traceability, evidence-window targeting, freshness labels, and paper-only guardrails before it can safely help a future clean-memory audit.

## Proposed Future Migration Name

Proposed future migration file:

`migrations/022_solana_safety_evidence.sql`

This filename follows the current numbered migration pattern after `migrations/021_repeatable_evidence_windows.sql`. The file is not created by this task.

## Proposed Future Table

Proposed table:

`printer_solana_safety_evidence`

This table should store source-governed, paper-only Solana token safety evidence that can be linked to a token snapshot and, where available, a memory or evidence window. It is deliberately separate from the existing `printer_safety_rug_snapshots` table so older context snapshot behavior can remain intact while future clean-memory gates get explicit source trace and window targeting.

| Column | Proposed meaning |
| --- | --- |
| `id` | Primary key. |
| `token_id` | Required token target. |
| `pair_id` | Optional pair target when safety evidence is pair/liquidity scoped. |
| `snapshot_id` | Required token snapshot target for clean eligibility. |
| `memory_window_id` | Optional memory window target. |
| `evidence_window_id` | Optional future evidence-window target if represented separately. |
| `safety_evidence_role` | Paper-only safety context role. |
| `source_name` | Source Governor source name. |
| `source_status` | Source status from governed source result. |
| `data_quality_label` | Data quality label from governed source normalization. |
| `target_status` | Whether evidence targets the correct token/snapshot/window. |
| `evidence_captured_at` | When the evidence was captured. |
| `freshness_label` | Freshness status relative to the snapshot/window. |
| `mint_authority_status` | Mint authority evidence label. |
| `freeze_authority_status` | Freeze authority evidence label. |
| `metadata_mutability_status` | Metadata mutability evidence label. |
| `supply_sanity_label` | Supply sanity evidence label. |
| `holder_concentration_label` | Holder concentration evidence label. |
| `liquidity_lock_or_burn_label` | Liquidity lock/burn evidence label when available. |
| `known_risk_flag_label` | Known risk flag evidence label. |
| `token_program_label` | Token program evidence label. |
| `safety_context_label` | Overall categorical safety context label. |
| `source_request_id` | Optional link to `printer_source_requests`. Required for clean eligibility. |
| `source_response_id` | Optional link to `printer_source_responses`. Required for successful clean eligibility. |
| `source_failure_id` | Optional link to `printer_source_failures` for failed evidence. |
| `paper_only_context` | Must be true for V1 safety evidence. |
| `created_at` | Insert timestamp. |

## Proposed Constraints

Future migration and audit logic should enforce these constraints:

- `token_id` is required.
- `snapshot_id` is required.
- `paper_only_context` must be true for V1 clean eligibility.
- Source trace is required for clean eligibility.
- Successful clean eligibility requires a governed source request and response link.
- Failed evidence should link to a governed source failure where available.
- `target_status` must be target-matched for clean eligibility.
- `source_status` must be complete or explicitly acceptable for clean eligibility.
- Stale evidence must not become clean.
- Failed evidence must not become clean.
- Blocked or high-risk evidence must not become clean.
- Caution evidence does not unlock clean memory by itself.
- Unknown evidence remains blocking or audit-only.
- Safety evidence alone cannot make memory clean.
- No score, rank, confidence, weighted, numeric decision, or combined decision field is allowed.
- No wallet, private-key, signature, signing, transaction, live-execution, BUY-unlock, retrieval-ready shortcut, paper-position, trade-event, or PnL field is allowed.

## Proposed Indexes

Future migration should add indexes for:

- `token_id`
- `pair_id`
- `snapshot_id`
- `memory_window_id`
- `source_request_id`
- `source_response_id`
- `source_failure_id`
- `source_status`
- `data_quality_label`
- `freshness_label`
- `target_status`
- `safety_context_label`
- `created_at`

## Source Governor Linkage

All future safety evidence must be created from the Source Governor path.

- Source request rows must be recorded before source collection.
- Source response rows must be recorded for successful responses.
- Source failure rows must remain visible for failed attempts.
- Evidence without source trace is audit-only and cannot support clean eligibility.
- The memory engine must not call safety sources directly.
- The paper decision engine must not call safety sources directly.
- Scheduler jobs must not bypass the Source Governor.
- A future source adapter, if approved, must remain free/public and optional within V1 constraints.

## Central Scheduler Boundary

Future safety evidence collection must be scheduled through Central Scheduler.

- Manual proof collection must be operator-approved.
- Jobs must be bounded.
- No source loop is allowed.
- No source spam is allowed.
- No daemon, cron, Celery, APScheduler, or always-on behavior is allowed.
- Runtime expansion is not part of this proposal.
- Safety evidence collection must not compete with higher-priority token-level snapshot or paper-monitor work.

## Clean-Memory Gate Preservation

This proposed table does not unlock clean memory by itself.

- Storage rows alone cannot make memory clean.
- Source rows alone cannot unlock retrieval.
- Safety evidence only helps the safety blocker.
- Market regime, Solana chain heat, flow, entry realism, exit realism, snapshot coverage, freshness, and window targeting still apply.
- Dirty, stale, failed, target-mismatched, or audit-only evidence remains blocked.
- Dirty memory remains blocked from retrieval and decisions.
- No paper decision, BUY, position, trade event, or PnL can be created from safety evidence storage alone.

## Draft SQL Sketch

Draft only - not applied.

```sql
CREATE TABLE IF NOT EXISTS printer_solana_safety_evidence (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    snapshot_id INTEGER NOT NULL,
    memory_window_id INTEGER,
    evidence_window_id INTEGER,
    safety_evidence_role TEXT NOT NULL
        CHECK (safety_evidence_role IN ('TOKEN_SAFETY_CONTEXT')),
    source_name TEXT NOT NULL,
    source_status TEXT NOT NULL
        CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'UNKNOWN')),
    data_quality_label TEXT NOT NULL
        CHECK (data_quality_label IN ('CLEAN_DATA', 'PARTIAL_DATA', 'DIRTY_DATA', 'UNKNOWN_DATA')),
    target_status TEXT NOT NULL
        CHECK (target_status IN ('TARGET_MATCH', 'TARGET_MISMATCH', 'TARGET_UNKNOWN')),
    evidence_captured_at TEXT NOT NULL,
    freshness_label TEXT NOT NULL
        CHECK (freshness_label IN (
            'SAFETY_EVIDENCE_FRESH',
            'SAFETY_EVIDENCE_ACCEPTABLE',
            'SAFETY_EVIDENCE_STALE',
            'SAFETY_EVIDENCE_UNKNOWN'
        )),
    mint_authority_status TEXT NOT NULL
        CHECK (mint_authority_status IN (
            'MINT_AUTHORITY_RENOUNCED',
            'MINT_AUTHORITY_PRESENT',
            'MINT_AUTHORITY_UNKNOWN'
        )),
    freeze_authority_status TEXT NOT NULL
        CHECK (freeze_authority_status IN (
            'FREEZE_AUTHORITY_DISABLED',
            'FREEZE_AUTHORITY_PRESENT',
            'FREEZE_AUTHORITY_UNKNOWN'
        )),
    metadata_mutability_status TEXT NOT NULL
        CHECK (metadata_mutability_status IN (
            'METADATA_IMMUTABLE',
            'METADATA_MUTABLE',
            'METADATA_MUTABILITY_UNKNOWN'
        )),
    supply_sanity_label TEXT NOT NULL
        CHECK (supply_sanity_label IN (
            'SUPPLY_SANITY_OK',
            'SUPPLY_SANITY_CAUTION',
            'SUPPLY_SANITY_UNKNOWN',
            'SUPPLY_SANITY_UNSAFE'
        )),
    holder_concentration_label TEXT NOT NULL
        CHECK (holder_concentration_label IN (
            'HOLDER_CONCENTRATION_ACCEPTABLE',
            'HOLDER_CONCENTRATION_CAUTION',
            'HOLDER_CONCENTRATION_UNKNOWN',
            'HOLDER_CONCENTRATION_UNSAFE'
        )),
    liquidity_lock_or_burn_label TEXT NOT NULL
        CHECK (liquidity_lock_or_burn_label IN (
            'LIQUIDITY_LOCK_OR_BURN_PRESENT',
            'LIQUIDITY_LOCK_OR_BURN_ABSENT',
            'LIQUIDITY_LOCK_OR_BURN_UNKNOWN',
            'LIQUIDITY_LOCK_OR_BURN_UNSAFE'
        )),
    known_risk_flag_label TEXT NOT NULL
        CHECK (known_risk_flag_label IN (
            'KNOWN_RISK_NONE',
            'KNOWN_RISK_CAUTION',
            'KNOWN_RISK_PRESENT',
            'KNOWN_RISK_UNKNOWN'
        )),
    token_program_label TEXT NOT NULL
        CHECK (token_program_label IN (
            'TOKEN_PROGRAM_STANDARD',
            'TOKEN_PROGRAM_TOKEN_2022',
            'TOKEN_PROGRAM_UNKNOWN',
            'TOKEN_PROGRAM_UNSAFE'
        )),
    safety_context_label TEXT NOT NULL
        CHECK (safety_context_label IN (
            'SAFETY_CLEAN',
            'SAFETY_CAUTION',
            'SAFETY_SUSPICIOUS',
            'SAFETY_UNSAFE',
            'SAFETY_UNKNOWN',
            'SAFETY_DO_NOT_USE_FOR_MEMORY'
        )),
    source_request_id INTEGER,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    paper_only_context INTEGER NOT NULL DEFAULT 1
        CHECK (paper_only_context = 1),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id),
    FOREIGN KEY (snapshot_id) REFERENCES printer_token_snapshots(id),
    FOREIGN KEY (memory_window_id) REFERENCES printer_memory_windows(id),
    FOREIGN KEY (source_request_id) REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id) REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id) REFERENCES printer_source_failures(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_token_id
    ON printer_solana_safety_evidence(token_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_pair_id
    ON printer_solana_safety_evidence(pair_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_snapshot_id
    ON printer_solana_safety_evidence(snapshot_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_memory_window_id
    ON printer_solana_safety_evidence(memory_window_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_source_request_id
    ON printer_solana_safety_evidence(source_request_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_source_response_id
    ON printer_solana_safety_evidence(source_response_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_source_failure_id
    ON printer_solana_safety_evidence(source_failure_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_source_status
    ON printer_solana_safety_evidence(source_status);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_data_quality_label
    ON printer_solana_safety_evidence(data_quality_label);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_freshness_label
    ON printer_solana_safety_evidence(freshness_label);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_target_status
    ON printer_solana_safety_evidence(target_status);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_safety_context_label
    ON printer_solana_safety_evidence(safety_context_label);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_created_at
    ON printer_solana_safety_evidence(created_at);
```

## Migration Readiness Verdict

`READY_FOR_FUTURE_MIGRATION_IMPLEMENTATION`

The proposed table is narrow, uses existing migration conventions, preserves source traceability, keeps safety evidence paper-only, and does not introduce decision shortcuts or live-trading concepts.

## Implementation Status

Implemented as schema-only storage in:

`migrations/022_solana_safety_evidence.sql`

Status:

- Migration implemented.
- Schema-only.
- No source adapter added.
- No Solana RPC, GoPlus, RugCheck, Helius, Jupiter, or live API call added.
- No source collection added.
- No persistent evidence rows created by this task.
- No runtime clean-memory behavior changed.
- No retrieval behavior changed.
- No paper decision behavior changed.
- No BUY unlock added.
- No paper position, trade event, or PnL behavior added.
- Lane 7 remains blocked.

## Recommended Next Safe Task

Add fixture-only migration/readiness review for the next approved evidence blocker, or add source-governed safety evidence write-path design in a separate task. The next task still must not add a source adapter, fetch live data, mutate persistent evidence, unlock clean memory, run retrieval, or start Lane 7.

## Non-Goals

- No migration file is created here.
- No persistent DB mutation.
- No source adapter.
- No live data fetch.
- No Solana RPC call.
- No GoPlus, RugCheck, Helius, or Jupiter integration.
- No Source Governor bypass.
- No Central Scheduler bypass.
- No memory rebuild.
- No retrieval.
- No paper decision.
- No BUY.
- No paper position.
- No paper trade event.
- No PnL.
- No scoring, ranking, confidence, weighted, or numeric decision system.
- No wallet, private key, signing, transaction, or live trading behavior.
- No Lane 7 activation.
