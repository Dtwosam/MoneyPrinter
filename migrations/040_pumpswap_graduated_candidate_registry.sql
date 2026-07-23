-- V2-9.7E.42 Direct Pump Migration Discovery — Graduated Candidate Registry
--
-- Durable, batch-independent registry of Pump.fun tokens whose graduation to the
-- post-bonding-curve PumpSwap AMM has been proven end-to-end from a PumpPortal
-- subscribeMigration event: a finalized migration transaction that (a) succeeded,
-- (b) references the exact mint, (c) invokes the adopted Pump.fun program and the
-- adopted PumpSwap AMM program, and (d) creates exactly one PumpSwap pool whose
-- owner is the PumpSwap program and whose base_mint@43 equals the exact mint.
--
-- This is the graduation-evidence persistence owner that V2-9.7E.41's
-- export_graduated_pilot_candidates required but could not read (BL-41-04): the
-- pre-existing printer_pumpfun_finalized_origin_registry stores only pre-graduation
-- origins. This registry stores only confirmed graduated candidates.
--
-- Graduation evidence is immutable. Only the cross-cycle observation fields
-- (latest_observed_at, latest_channel, observation_count) may change. Migration
-- block time is graduation evidence ONLY and NEVER becomes token_created_at — there
-- is intentionally no token_created_at / token_age column here.
--
-- Locked: no retrieval, decision, position, trade, audit, PnL, wallet, or signing
-- surface is created or altered here.

CREATE TABLE printer_pumpswap_graduated_candidate_registry (
    mint_identity TEXT PRIMARY KEY,
    migration_signature TEXT NOT NULL UNIQUE,
    migration_provenance TEXT NOT NULL,
    pumpswap_pool TEXT NOT NULL,
    -- Adopted PumpSwap AMM program (verified on-chain 2026-07-12).
    pumpswap_program_id TEXT NOT NULL CHECK (
        pumpswap_program_id = 'pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA'
    ),
    -- Adopted Pump.fun program (create/migration authority program).
    pump_program_id TEXT NOT NULL CHECK (
        pump_program_id = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
    ),
    base_mint_offset INTEGER NOT NULL CHECK (base_mint_offset >= 0),
    graduation_block_time INTEGER NOT NULL,
    graduation_slot INTEGER CHECK (graduation_slot IS NULL OR graduation_slot >= 0),
    -- Confirmed graduated candidates only; an unconfirmed mint is absent.
    lifecycle_state TEXT NOT NULL DEFAULT 'PUMPSWAP_GRADUATED_CONFIRMED'
        CHECK (lifecycle_state = 'PUMPSWAP_GRADUATED_CONFIRMED'),
    market_identity TEXT NOT NULL,
    discovery_channel TEXT NOT NULL,
    -- sha256 of the canonical graduation-evidence payload. Never a raw RPC response.
    confirmation_evidence_hash TEXT NOT NULL CHECK (
        length(confirmation_evidence_hash) = 64
    ),
    contract_version TEXT NOT NULL,
    first_observed_at TEXT NOT NULL,
    latest_observed_at TEXT NOT NULL,
    latest_channel TEXT NOT NULL,
    observation_count INTEGER NOT NULL DEFAULT 1 CHECK (observation_count >= 1),
    CHECK (length(trim(mint_identity)) > 0),
    CHECK (length(trim(migration_signature)) > 0),
    CHECK (length(trim(pumpswap_pool)) > 0),
    CHECK (length(trim(market_identity)) > 0),
    CHECK (length(trim(discovery_channel)) > 0)
);

CREATE INDEX printer_pumpswap_graduated_registry_block_time
    ON printer_pumpswap_graduated_candidate_registry(graduation_block_time);

CREATE INDEX printer_pumpswap_graduated_registry_channel
    ON printer_pumpswap_graduated_candidate_registry(discovery_channel);

-- Graduation evidence is a permanent fact. Only the observation fields may change.
CREATE TRIGGER printer_pumpswap_graduated_registry_immutable_evidence
BEFORE UPDATE ON printer_pumpswap_graduated_candidate_registry
FOR EACH ROW WHEN (
    OLD.mint_identity != NEW.mint_identity
    OR OLD.migration_signature != NEW.migration_signature
    OR OLD.migration_provenance != NEW.migration_provenance
    OR OLD.pumpswap_pool != NEW.pumpswap_pool
    OR OLD.pumpswap_program_id != NEW.pumpswap_program_id
    OR OLD.pump_program_id != NEW.pump_program_id
    OR OLD.base_mint_offset != NEW.base_mint_offset
    OR OLD.graduation_block_time != NEW.graduation_block_time
    OR OLD.lifecycle_state != NEW.lifecycle_state
    OR OLD.market_identity != NEW.market_identity
    OR OLD.confirmation_evidence_hash != NEW.confirmation_evidence_hash
    OR OLD.contract_version != NEW.contract_version
    OR OLD.first_observed_at != NEW.first_observed_at
    OR OLD.discovery_channel != NEW.discovery_channel
)
BEGIN
    SELECT RAISE(ABORT, 'graduated candidate graduation evidence is immutable');
END;

CREATE TRIGGER printer_pumpswap_graduated_registry_immutable_delete
BEFORE DELETE ON printer_pumpswap_graduated_candidate_registry
BEGIN
    SELECT RAISE(ABORT, 'printer_pumpswap_graduated_candidate_registry is immutable');
END;
