-- V2-9.8B graduated discovery memory-observation eligibility layers.
--
-- Extends printer_discovery_reserve_layers to represent:
--   ABOVE_FLOOR_NOMINATED      — exact-pool liquidity prefilter pass, protocol due
--   MEMORY_OBSERVATION_ELIGIBLE — identity+pool+liquidity ready for memory observation
--
-- FULLY_ELIGIBLE is retained for future action-specific policy only.
-- No authoritative row mutation beyond table recreation for CHECK expansion.

-- Locked: no score/rank/confidence/weight, retrieval, decision, position,
-- trade, audit, PnL, wallet, signing, transaction or live-execution surface.

CREATE TABLE printer_discovery_reserve_layers_052 (
    network TEXT NOT NULL,
    mint_identity TEXT NOT NULL,
    pool_address TEXT NOT NULL,
    reserve_layer TEXT NOT NULL CHECK (reserve_layer IN (
        'BROAD_NOMINATED',
        'ABOVE_FLOOR_NOMINATED',
        'MARKET_READY',
        'MEMORY_OBSERVATION_ELIGIBLE',
        'FULLY_ELIGIBLE'
    )),
    reserve_state TEXT NOT NULL CHECK (reserve_state IN (
        'ACTIVE', 'STALE', 'EXCLUDED', 'SELECTED', 'ALTERNATE'
    )),
    categorical_reason TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    next_lawful_action_at TEXT,
    evidence_expires_at TEXT,
    source_provenance_json TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    last_campaign_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (network, mint_identity, pool_address, reserve_layer),
    CHECK (length(trim(categorical_reason)) > 0),
    CHECK (length(trim(source_provenance_json)) > 0),
    CHECK (length(trim(evidence_json)) > 0),
    FOREIGN KEY (network, mint_identity, pool_address)
        REFERENCES printer_exact_market_states(network, mint_identity, pool_address)
);

INSERT INTO printer_discovery_reserve_layers_052 (
    network, mint_identity, pool_address, reserve_layer, reserve_state,
    categorical_reason, observed_at, next_lawful_action_at, evidence_expires_at,
    source_provenance_json, evidence_json, last_campaign_id, created_at, updated_at
)
SELECT
    network, mint_identity, pool_address, reserve_layer, reserve_state,
    categorical_reason, observed_at, next_lawful_action_at, evidence_expires_at,
    source_provenance_json, evidence_json, last_campaign_id, created_at, updated_at
FROM printer_discovery_reserve_layers;

DROP TABLE printer_discovery_reserve_layers;

ALTER TABLE printer_discovery_reserve_layers_052
    RENAME TO printer_discovery_reserve_layers;

CREATE INDEX printer_discovery_reserve_layer_due
    ON printer_discovery_reserve_layers(
        reserve_layer, reserve_state, next_lawful_action_at, observed_at,
        mint_identity, pool_address
    );
CREATE INDEX printer_discovery_reserve_layer_expiry
    ON printer_discovery_reserve_layers(
        reserve_layer, reserve_state, evidence_expires_at
    );

CREATE TRIGGER printer_discovery_reserve_identity_immutable
BEFORE UPDATE OF network, mint_identity, pool_address, reserve_layer, created_at
ON printer_discovery_reserve_layers
BEGIN
    SELECT RAISE(ABORT, 'discovery reserve identity is immutable');
END;

CREATE TRIGGER printer_discovery_reserve_delete_block
BEFORE DELETE ON printer_discovery_reserve_layers
BEGIN
    SELECT RAISE(ABORT, 'historical discovery reserve identity cannot be deleted');
END;
