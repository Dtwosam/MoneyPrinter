-- V2-9.8B post-DTW89 — widen durable pilot-input activation-route domain.
--
-- Migration 041 created the immutable PILOT_INPUT_READY bundle when only the
-- legacy GRADUATION_NATIVE / PUMP_CREATE route vocabulary existed. Current
-- MEMORY_OBSERVATION readiness truthfully permits source-specific
-- MARKET_PRESENT_POOL authority/route, so the durable representation must be a
-- superset without changing FUTURE_ACTION policy or historical bundle values.
--
-- Preserve every column, value, bundle hash, index and immutability trigger.
-- The only semantic schema change is adding MARKET_PRESENT_POOL to both route
-- CHECK domains. No authority backfill or route transformation is performed.

CREATE TABLE printer_pilot_input_readiness_bundle_053 (
    readiness_id TEXT PRIMARY KEY,
    readiness_state TEXT NOT NULL DEFAULT 'PILOT_INPUT_READY'
        CHECK (readiness_state = 'PILOT_INPUT_READY'),

    latest_mint TEXT NOT NULL,
    latest_pool TEXT NOT NULL,
    latest_market_identity TEXT NOT NULL,
    latest_liquidity_usd REAL NOT NULL CHECK (latest_liquidity_usd >= 3000.0),
    latest_liquidity_observed_at TEXT NOT NULL,
    latest_activation_route TEXT NOT NULL CHECK (
        latest_activation_route IN (
            'GRADUATION_NATIVE', 'PUMP_CREATE', 'MARKET_PRESENT_POOL'
        )
    ),

    persisted_mint TEXT NOT NULL,
    persisted_pool TEXT NOT NULL,
    persisted_market_identity TEXT NOT NULL,
    persisted_liquidity_usd REAL NOT NULL CHECK (persisted_liquidity_usd >= 3000.0),
    persisted_liquidity_observed_at TEXT NOT NULL,
    persisted_activation_route TEXT NOT NULL CHECK (
        persisted_activation_route IN (
            'GRADUATION_NATIVE', 'PUMP_CREATE', 'MARKET_PRESENT_POOL'
        )
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
    bundle_hash TEXT NOT NULL CHECK (length(bundle_hash) = 64),
    created_at TEXT NOT NULL,

    CHECK (latest_mint != persisted_mint),
    CHECK (length(trim(readiness_id)) > 0),
    CHECK (length(trim(latest_mint)) > 0),
    CHECK (length(trim(persisted_mint)) > 0)
);

INSERT INTO printer_pilot_input_readiness_bundle_053 (
    readiness_id,
    readiness_state,
    latest_mint,
    latest_pool,
    latest_market_identity,
    latest_liquidity_usd,
    latest_liquidity_observed_at,
    latest_activation_route,
    persisted_mint,
    persisted_pool,
    persisted_market_identity,
    persisted_liquidity_usd,
    persisted_liquidity_observed_at,
    persisted_activation_route,
    holder_evidence_json,
    source_ledger_json,
    latest_persisted_provenance_json,
    selection_seed,
    git_provenance_identity,
    configuration_hash,
    expires_at,
    bundle_hash,
    created_at
)
SELECT
    readiness_id,
    readiness_state,
    latest_mint,
    latest_pool,
    latest_market_identity,
    latest_liquidity_usd,
    latest_liquidity_observed_at,
    latest_activation_route,
    persisted_mint,
    persisted_pool,
    persisted_market_identity,
    persisted_liquidity_usd,
    persisted_liquidity_observed_at,
    persisted_activation_route,
    holder_evidence_json,
    source_ledger_json,
    latest_persisted_provenance_json,
    selection_seed,
    git_provenance_identity,
    configuration_hash,
    expires_at,
    bundle_hash,
    created_at
FROM printer_pilot_input_readiness_bundle;

DROP TABLE printer_pilot_input_readiness_bundle;

ALTER TABLE printer_pilot_input_readiness_bundle_053
    RENAME TO printer_pilot_input_readiness_bundle;

CREATE INDEX printer_pilot_input_readiness_created
    ON printer_pilot_input_readiness_bundle(created_at);

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
