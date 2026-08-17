-- 058_direct_pump_migration_cursor.sql
--
-- Durable backward-traversal cursor owned by the ACTIVE direct Pump canonical
-- migration feeder.
--
-- This is deliberately NOT `printer_candidate_cursor_ranges`: that table belongs
-- to the separate candidate-acquisition foundation/execution subsystem and has
-- execution-level foreign-key ownership. The direct canonical migration feeder
-- owns its own restart-safe cursor here and writes nothing into that table.
--
-- Identity is scoped to the exact Pump contract hash AND the exact migration
-- decoder version. A future contract/decoder revision therefore creates a NEW
-- cursor row that starts UNINITIALIZED, instead of blindly continuing from a
-- position produced by an older decoder which may have skipped migration
-- evidence it could not yet validate.
--
-- No financial, selection, admission or lifecycle field belongs here. This is a
-- mutable traversal projection only.

CREATE TABLE printer_direct_pump_migration_cursor (
    network TEXT NOT NULL CHECK (network = 'solana-mainnet'),
    indexed_address TEXT NOT NULL CHECK (length(trim(indexed_address)) > 0),
    pump_contract_hash TEXT NOT NULL CHECK (length(trim(pump_contract_hash)) > 0),
    decoder_version TEXT NOT NULL CHECK (length(trim(decoder_version)) > 0),

    next_before_signature TEXT,
    next_before_slot INTEGER,

    continuity_state TEXT NOT NULL CHECK (
        continuity_state IN (
            'UNINITIALIZED',
            'CONTIGUOUS',
            'EXHAUSTED',
            'BLOCKED_CONTRACT'
        )
    ),

    pages_advanced INTEGER NOT NULL DEFAULT 0 CHECK (pages_advanced >= 0),
    signatures_covered INTEGER NOT NULL DEFAULT 0 CHECK (signatures_covered >= 0),

    last_live_tail_at TEXT,
    last_backfill_at TEXT,
    last_block_reason TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    PRIMARY KEY (
        network,
        indexed_address,
        pump_contract_hash,
        decoder_version
    ),

    CHECK (next_before_slot IS NULL OR next_before_slot >= 0),

    -- The traversal position is one fact, never half a fact.
    CHECK (
        (next_before_signature IS NULL AND next_before_slot IS NULL)
        OR (next_before_signature IS NOT NULL AND next_before_slot IS NOT NULL)
    ),

    -- A CONTIGUOUS cursor must name the exact signature/slot a later bounded
    -- backfill will continue strictly before.
    CHECK (
        continuity_state <> 'CONTIGUOUS'
        OR (next_before_signature IS NOT NULL AND next_before_slot IS NOT NULL)
    ),

    -- A blocked cursor must carry its bounded categorical block reason.
    CHECK (
        continuity_state <> 'BLOCKED_CONTRACT'
        OR (last_block_reason IS NOT NULL AND length(trim(last_block_reason)) > 0)
    )
);

CREATE INDEX idx_direct_pump_migration_cursor_state
    ON printer_direct_pump_migration_cursor (continuity_state, updated_at);
