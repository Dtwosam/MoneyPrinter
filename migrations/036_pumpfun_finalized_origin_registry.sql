-- V2-9.7E.5 Pump Origin Acquisition Architecture Reset
--
-- Durable, batch-independent, immutable registry of finalized Pump origins
-- captured prospectively by signature-anchored acquisition.
--
-- Required because printer_discovery_origin_verifications (migration 034) is
-- NOT NULL FK'd to printer_discovery_batches and uniquely keyed by
-- (discovery_batch_id, merged_candidate_id). A confirmed origin there is an
-- artifact of one batch and cannot be read by a later campaign cycle, which
-- forced campaign-time historical rediscovery onto the critical activation
-- path. This migration removes that requirement.
--
-- Locked: no retrieval, decision, position, trade, audit, PnL, wallet, or
-- signing surface is created or altered here.

-- ---------------------------------------------------------------------------
-- 1. Confirmed finalized origin registry
-- ---------------------------------------------------------------------------

CREATE TABLE printer_pumpfun_finalized_origin_registry (
    mint_identity TEXT PRIMARY KEY,
    transaction_signature TEXT NOT NULL UNIQUE,
    slot INTEGER NOT NULL CHECK (slot >= 0),
    block_time INTEGER NOT NULL,
    program_id TEXT NOT NULL CHECK (
        program_id = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
    ),
    bonding_curve TEXT NOT NULL,
    associated_bonding_curve TEXT NOT NULL,
    creator_address TEXT NOT NULL,
    creator_evidence_scope TEXT NOT NULL DEFAULT 'OBSERVED_EVIDENCE_ONLY'
        CHECK (creator_evidence_scope = 'OBSERVED_EVIDENCE_ONLY'),
    -- Confirmed-only registry: an unconfirmed mint is absent, never a row.
    origin_state TEXT NOT NULL DEFAULT 'PUMPFUN_ORIGIN_CONFIRMED'
        CHECK (origin_state = 'PUMPFUN_ORIGIN_CONFIRMED'),
    acquisition_mode TEXT NOT NULL CHECK (
        acquisition_mode IN (
            'SIGNATURE_ANCHORED_PROSPECTIVE',
            'SUPPORT_ONLY_HISTORICAL'
        )
    ),
    -- V2-9.7E.6: which adopted Pump create layout established this origin.
    -- Both are decoded from the same pinned IDL revision recorded below.
    create_layout TEXT NOT NULL CHECK (
        create_layout IN ('PUMP_CREATE_V1', 'PUMP_CREATE_V2')
    ),
    create_discriminator_hex TEXT NOT NULL CHECK (
        length(create_discriminator_hex) = 16
    ),
    token_program TEXT NOT NULL,
    index_address TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    idl_sha256 TEXT NOT NULL,
    -- sha256 of the canonical decoded payload. Never a raw RPC response.
    evidence_hash TEXT NOT NULL CHECK (length(evidence_hash) = 64),
    first_confirmed_at TEXT NOT NULL,
    CHECK (length(trim(mint_identity)) > 0),
    CHECK (length(trim(transaction_signature)) > 0),
    CHECK (length(trim(bonding_curve)) > 0),
    CHECK (length(trim(associated_bonding_curve)) > 0),
    CHECK (length(trim(creator_address)) > 0)
);

CREATE INDEX printer_pumpfun_origin_registry_slot
    ON printer_pumpfun_finalized_origin_registry(slot);

CREATE INDEX printer_pumpfun_origin_registry_mode
    ON printer_pumpfun_finalized_origin_registry(acquisition_mode);

CREATE INDEX printer_pumpfun_origin_registry_layout
    ON printer_pumpfun_finalized_origin_registry(create_layout);

-- A confirmed finalized origin is a permanent fact. Immutable by construction.

CREATE TRIGGER printer_pumpfun_origin_registry_immutable_update
BEFORE UPDATE ON printer_pumpfun_finalized_origin_registry
BEGIN
    SELECT RAISE(ABORT, 'printer_pumpfun_finalized_origin_registry is immutable');
END;

CREATE TRIGGER printer_pumpfun_origin_registry_immutable_delete
BEFORE DELETE ON printer_pumpfun_finalized_origin_registry
BEGIN
    SELECT RAISE(ABORT, 'printer_pumpfun_finalized_origin_registry is immutable');
END;

-- ---------------------------------------------------------------------------
-- 2. Per-index-address acquisition cursor (high-water mark)
-- ---------------------------------------------------------------------------

CREATE TABLE printer_pumpfun_origin_cursor (
    index_address TEXT PRIMARY KEY,
    boundary_slot INTEGER CHECK (boundary_slot IS NULL OR boundary_slot >= 0),
    boundary_signature TEXT,
    continuity_state TEXT NOT NULL CHECK (
        continuity_state IN ('CONTIGUOUS', 'GAPPED', 'UNKNOWN', 'UNAVAILABLE')
    ),
    updated_at TEXT NOT NULL,
    CHECK (length(trim(index_address)) > 0),
    -- Boundary is all-or-nothing.
    CHECK (
        (boundary_slot IS NULL AND boundary_signature IS NULL)
        OR (boundary_slot IS NOT NULL AND length(trim(boundary_signature)) > 0)
    )
);
