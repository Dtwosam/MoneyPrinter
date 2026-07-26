-- V2-9.8B.6/7: durable categorical market-floor revalidation state for graduated
-- candidates. Graduation evidence remains immutable in
-- printer_pumpswap_graduated_candidate_registry. This table only stores the last
-- exact-pool liquidity classification and a below-floor cooldown clock so a
-- recently failed mint does not re-consume a DexScreener call every campaign.
--
-- Locked: no scores, ranks, confidence, weights, retrieval, decisions, positions,
-- trades, audits, PnL, wallets, or signing surfaces.

CREATE TABLE printer_graduated_market_floor_state (
    mint_identity TEXT PRIMARY KEY,
    pumpswap_pool TEXT NOT NULL,
    liquidity_status TEXT NOT NULL CHECK (
        liquidity_status IN (
            'LIQUIDITY_PROVEN',
            'LIQUIDITY_BELOW_SELECTION_FLOOR',
            'LIQUIDITY_UNPROVEN'
        )
    ),
    liquidity_usd REAL,
    last_checked_at TEXT NOT NULL,
    cooldown_until TEXT,
    updated_at TEXT NOT NULL,
    CHECK (length(trim(mint_identity)) > 0),
    CHECK (length(trim(pumpswap_pool)) > 0),
    CHECK (
        liquidity_usd IS NULL
        OR (typeof(liquidity_usd) = 'real' AND liquidity_usd >= 0)
    ),
    FOREIGN KEY (mint_identity)
        REFERENCES printer_pumpswap_graduated_candidate_registry(mint_identity)
);

CREATE INDEX printer_graduated_market_floor_cooldown
    ON printer_graduated_market_floor_state(cooldown_until);
