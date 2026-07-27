-- V2-9.8B.21 Eligible Token Supply architecture
--
-- Durable eligible reserve and discovery exhaustion certificates for the
-- persistent multi-round discovery loop. Graduation evidence remains immutable
-- in printer_pumpswap_graduated_candidate_registry. Market floor cooldown remains
-- in printer_graduated_market_floor_state.
--
-- Locked: no scores, ranks, confidence, weights, retrieval, decisions, positions,
-- trades, audits, PnL, wallets, or signing surfaces.

CREATE TABLE printer_eligible_token_reserve (
    mint_identity TEXT PRIMARY KEY,
    pumpswap_pool TEXT NOT NULL,
    market_identity TEXT NOT NULL,
    provenance TEXT NOT NULL,
    liquidity_usd REAL,
    liquidity_status TEXT NOT NULL CHECK (
        liquidity_status IN (
            'LIQUIDITY_PROVEN',
            'LIQUIDITY_BELOW_SELECTION_FLOOR',
            'LIQUIDITY_UNPROVEN'
        )
    ),
    eligibility_status TEXT NOT NULL CHECK (
        eligibility_status IN (
            'ELIGIBLE_FRESH',
            'ELIGIBLE_STALE',
            'REMOVED',
            'EXCLUDED'
        )
    ),
    last_validated_at TEXT NOT NULL,
    source_provenance TEXT,
    last_campaign_id TEXT,
    exclusion_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (length(trim(mint_identity)) > 0),
    CHECK (length(trim(pumpswap_pool)) > 0),
    CHECK (length(trim(market_identity)) > 0),
    CHECK (
        liquidity_usd IS NULL
        OR (typeof(liquidity_usd) = 'real' AND liquidity_usd >= 0)
    ),
    FOREIGN KEY (mint_identity)
        REFERENCES printer_pumpswap_graduated_candidate_registry(mint_identity)
);

CREATE INDEX printer_eligible_token_reserve_status
    ON printer_eligible_token_reserve(eligibility_status);

CREATE INDEX printer_eligible_token_reserve_validated
    ON printer_eligible_token_reserve(last_validated_at);

CREATE TABLE printer_discovery_exhaustion_certificates (
    certificate_id TEXT PRIMARY KEY,
    campaign_id TEXT,
    execution_id TEXT,
    run_id TEXT,
    cycle_id TEXT,
    required_eligible_capacity INTEGER NOT NULL CHECK (required_eligible_capacity >= 1),
    eligible_reserve_count INTEGER NOT NULL CHECK (eligible_reserve_count >= 0),
    shortage_classification TEXT NOT NULL CHECK (
        shortage_classification IN (
            'TRUE_MARKET_SUPPLY_SHORTAGE',
            'SOURCE_VISIBILITY_SHORTAGE',
            'SOURCE_AVAILABILITY_FAILURE',
            'BUDGET_EXHAUSTION',
            'DURATION_EXHAUSTION',
            'STALE_EVIDENCE_SHORTAGE',
            'DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE'
        )
    ),
    certificate_json TEXT NOT NULL,
    certificate_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK (length(trim(certificate_id)) > 0),
    CHECK (length(trim(certificate_json)) > 0)
);

CREATE INDEX printer_discovery_exhaustion_campaign
    ON printer_discovery_exhaustion_certificates(campaign_id);

CREATE INDEX printer_discovery_exhaustion_class
    ON printer_discovery_exhaustion_certificates(shortage_classification);
