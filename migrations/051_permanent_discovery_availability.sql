-- V2-9.8B permanent discovery availability.
--
-- Adds one exact mint+pool operational projection, append-only categorical
-- transition history, and the three durable reserve layers owned by the active
-- Eligible Token Supply service. Historical pool identities are retained.
--
-- Locked: no score/rank/confidence/weight, retrieval, decision, position,
-- trade, audit, PnL, wallet, signing, transaction or live-execution surface.

CREATE TABLE printer_exact_market_states (
    network TEXT NOT NULL CHECK (network = 'solana-mainnet'),
    mint_identity TEXT NOT NULL,
    pool_address TEXT NOT NULL,
    token_program_id TEXT NOT NULL,
    pool_program_id TEXT NOT NULL,
    base_mint TEXT NOT NULL,
    quote_mint TEXT NOT NULL,
    venue TEXT NOT NULL,
    current_state TEXT NOT NULL CHECK (current_state IN (
        'CURRENT_VISIBLE',
        'BELOW_LIQUIDITY_FLOOR',
        'EXACT_POOL_NO_MATCH',
        'POOL_RECONCILIATION_DUE',
        'SAME_POOL_REOBSERVED',
        'NEW_POOL_PENDING_PROOF',
        'CURRENT_POOL_CONFIRMED',
        'NO_SUPPORTED_CURRENT_POOL',
        'SOURCE_UNAVAILABLE',
        'IDENTITY_CONFLICT',
        'UNSUPPORTED_VENUE',
        'CONTRACT_BLOCKED'
    )),
    current_reason TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    last_visible_at TEXT,
    last_no_match_at TEXT,
    no_match_count INTEGER NOT NULL DEFAULT 0 CHECK (no_match_count >= 0),
    no_match_streak INTEGER NOT NULL DEFAULT 0 CHECK (no_match_streak >= 0),
    next_lawful_action_at TEXT,
    latest_source_provenance_json TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (network, mint_identity, pool_address),
    CHECK (length(trim(mint_identity)) > 0),
    CHECK (length(trim(pool_address)) > 0),
    CHECK (length(trim(token_program_id)) > 0),
    CHECK (length(trim(pool_program_id)) > 0),
    CHECK (length(trim(base_mint)) > 0),
    CHECK (length(trim(quote_mint)) > 0),
    CHECK (length(trim(venue)) > 0),
    CHECK (length(trim(current_reason)) > 0),
    CHECK (length(trim(latest_source_provenance_json)) > 0),
    CHECK (length(trim(contract_version)) > 0)
);

CREATE INDEX printer_exact_market_state_due
    ON printer_exact_market_states(current_state, next_lawful_action_at);
CREATE INDEX printer_exact_market_state_mint
    ON printer_exact_market_states(network, mint_identity, last_observed_at);

CREATE TABLE printer_exact_market_state_transitions (
    transition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    network TEXT NOT NULL,
    mint_identity TEXT NOT NULL,
    pool_address TEXT NOT NULL,
    prior_state TEXT CHECK (prior_state IS NULL OR prior_state IN (
        'CURRENT_VISIBLE', 'BELOW_LIQUIDITY_FLOOR', 'EXACT_POOL_NO_MATCH',
        'POOL_RECONCILIATION_DUE', 'SAME_POOL_REOBSERVED',
        'NEW_POOL_PENDING_PROOF', 'CURRENT_POOL_CONFIRMED',
        'NO_SUPPORTED_CURRENT_POOL', 'SOURCE_UNAVAILABLE',
        'IDENTITY_CONFLICT', 'UNSUPPORTED_VENUE', 'CONTRACT_BLOCKED'
    )),
    new_state TEXT NOT NULL CHECK (new_state IN (
        'CURRENT_VISIBLE', 'BELOW_LIQUIDITY_FLOOR', 'EXACT_POOL_NO_MATCH',
        'POOL_RECONCILIATION_DUE', 'SAME_POOL_REOBSERVED',
        'NEW_POOL_PENDING_PROOF', 'CURRENT_POOL_CONFIRMED',
        'NO_SUPPORTED_CURRENT_POOL', 'SOURCE_UNAVAILABLE',
        'IDENTITY_CONFLICT', 'UNSUPPORTED_VENUE', 'CONTRACT_BLOCKED'
    )),
    reason_code TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    next_lawful_action_at TEXT,
    source_provenance_json TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    CHECK (length(trim(reason_code)) > 0),
    CHECK (length(trim(source_provenance_json)) > 0),
    CHECK (length(trim(contract_version)) > 0),
    FOREIGN KEY (network, mint_identity, pool_address)
        REFERENCES printer_exact_market_states(network, mint_identity, pool_address)
);

CREATE INDEX printer_exact_market_transition_identity
    ON printer_exact_market_state_transitions(
        network, mint_identity, pool_address, transition_id
    );

CREATE TRIGGER printer_exact_market_transition_update_block
BEFORE UPDATE ON printer_exact_market_state_transitions
BEGIN
    SELECT RAISE(ABORT, 'exact market transition history is append-only');
END;
CREATE TRIGGER printer_exact_market_transition_delete_block
BEFORE DELETE ON printer_exact_market_state_transitions
BEGIN
    SELECT RAISE(ABORT, 'exact market transition history is append-only');
END;

CREATE TRIGGER printer_exact_market_identity_immutable
BEFORE UPDATE OF network, mint_identity, pool_address, created_at
ON printer_exact_market_states
BEGIN
    SELECT RAISE(ABORT, 'exact market identity is immutable');
END;

CREATE TRIGGER printer_exact_market_delete_block
BEFORE DELETE ON printer_exact_market_states
BEGIN
    SELECT RAISE(ABORT, 'historical exact market identity cannot be deleted');
END;

CREATE TABLE printer_discovery_reserve_layers (
    network TEXT NOT NULL,
    mint_identity TEXT NOT NULL,
    pool_address TEXT NOT NULL,
    reserve_layer TEXT NOT NULL CHECK (reserve_layer IN (
        'BROAD_NOMINATED', 'MARKET_READY', 'FULLY_ELIGIBLE'
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
