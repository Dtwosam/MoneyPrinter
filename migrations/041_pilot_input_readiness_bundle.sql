-- V2-9.7E.45 Repair 6 — Pilot input readiness bundle
--
-- One immutable PILOT_INPUT_READY bundle per readiness identity, written only when
-- DISCOVERY_READY + SELECTION_READY + MARKET_READY + HOLDER_READY + ACTIVATION_READY
-- are all simultaneously true for one lawful LATEST + one lawful PERSISTED graduated
-- candidate. The bundle cannot be edited, partially replaced or silently reselected;
-- if mandatory evidence expires, a NEW readiness identity is built (the old bundle
-- is never mutated). No sustained attempt is consumed before this bundle exists.
--
-- Locked: this table carries readiness *inputs* only. It never carries campaign
-- authorization, lifecycle state, snapshots, memory, retrieval, decisions,
-- positions, trades, audits or PnL. No wallet/signing surface is created here.

CREATE TABLE printer_pilot_input_readiness_bundle (
    readiness_id TEXT PRIMARY KEY,
    readiness_state TEXT NOT NULL DEFAULT 'PILOT_INPUT_READY'
        CHECK (readiness_state = 'PILOT_INPUT_READY'),

    latest_mint TEXT NOT NULL,
    latest_pool TEXT NOT NULL,
    latest_market_identity TEXT NOT NULL,
    latest_liquidity_usd REAL NOT NULL CHECK (latest_liquidity_usd >= 3000.0),
    latest_liquidity_observed_at TEXT NOT NULL,
    latest_activation_route TEXT NOT NULL CHECK (
        latest_activation_route IN ('GRADUATION_NATIVE', 'PUMP_CREATE')
    ),

    persisted_mint TEXT NOT NULL,
    persisted_pool TEXT NOT NULL,
    persisted_market_identity TEXT NOT NULL,
    persisted_liquidity_usd REAL NOT NULL CHECK (persisted_liquidity_usd >= 3000.0),
    persisted_liquidity_observed_at TEXT NOT NULL,
    persisted_activation_route TEXT NOT NULL CHECK (
        persisted_activation_route IN ('GRADUATION_NATIVE', 'PUMP_CREATE')
    ),

    holder_evidence_json TEXT NOT NULL
        CHECK (json_valid(holder_evidence_json) = 1),
    source_ledger_json TEXT NOT NULL
        CHECK (json_valid(source_ledger_json) = 1),
    latest_persisted_provenance_json TEXT NOT NULL
        CHECK (json_valid(latest_persisted_provenance_json) = 1),

    selection_seed TEXT NOT NULL,
    git_provenance_identity TEXT NOT NULL,
    configuration_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    -- sha256 of the canonical readiness payload. Binds the identity to its content.
    bundle_hash TEXT NOT NULL CHECK (length(bundle_hash) = 64),
    created_at TEXT NOT NULL,

    CHECK (latest_mint != persisted_mint),
    CHECK (length(trim(readiness_id)) > 0),
    CHECK (length(trim(latest_mint)) > 0),
    CHECK (length(trim(persisted_mint)) > 0)
);

CREATE INDEX printer_pilot_input_readiness_created
    ON printer_pilot_input_readiness_bundle(created_at);

-- The bundle is immutable once written.
CREATE TRIGGER printer_pilot_input_readiness_immutable_update
BEFORE UPDATE ON printer_pilot_input_readiness_bundle
BEGIN
    SELECT RAISE(ABORT, 'pilot input readiness bundle is immutable');
END;

CREATE TRIGGER printer_pilot_input_readiness_immutable_delete
BEFORE DELETE ON printer_pilot_input_readiness_bundle
BEGIN
    SELECT RAISE(ABORT, 'pilot input readiness bundle is immutable');
END;
