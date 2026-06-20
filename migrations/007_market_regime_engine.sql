CREATE TABLE IF NOT EXISTS printer_market_regime_snapshots (
    id INTEGER PRIMARY KEY,
    captured_at TEXT NOT NULL,
    btc_price_usd REAL,
    btc_change_1h REAL,
    btc_change_24h REAL,
    btc_change_7d REAL,
    eth_price_usd REAL,
    eth_change_24h REAL,
    eth_change_7d REAL,
    sol_price_usd REAL,
    sol_change_1h REAL,
    sol_change_24h REAL,
    sol_change_7d REAL,
    sol_volume_24h REAL,
    fear_greed_value INTEGER,
    fear_greed_label TEXT,
    fear_greed_previous_value INTEGER,
    fear_greed_previous_label TEXT,
    solana_tvl_usd REAL,
    solana_dex_volume_context TEXT,
    stablecoin_context TEXT,
    tracked_solana_meme_volume REAL,
    tracked_solana_meme_liquidity REAL,
    tracked_solana_hot_pair_count INTEGER,
    tracked_solana_new_pair_count INTEGER,
    market_regime_label TEXT NOT NULL CHECK (market_regime_label IN ('EXTREME_FEAR', 'FEAR', 'NEUTRAL', 'GREED', 'EXTREME_GREED', 'RISK_ON', 'RISK_OFF', 'CHOPPY', 'VOLATILE', 'UNKNOWN')),
    market_transition_label TEXT NOT NULL CHECK (market_transition_label IN ('FEAR_TO_NEUTRAL', 'NEUTRAL_TO_GREED', 'GREED_TO_EXTREME_GREED', 'EXTREME_GREED_TO_GREED', 'GREED_TO_NEUTRAL', 'NEUTRAL_TO_FEAR', 'FEAR_TO_EXTREME_FEAR', 'RISK_OFF_TO_RISK_ON', 'RISK_ON_TO_RISK_OFF', 'CHOPPY_TO_TRENDING', 'TRENDING_TO_CHOPPY', 'UNKNOWN_TRANSITION')),
    market_payload_quality_label TEXT NOT NULL CHECK (market_payload_quality_label IN ('MARKET_CONTEXT_CLEAN', 'MARKET_CONTEXT_PARTIAL', 'MARKET_CONTEXT_STALE', 'MARKET_CONTEXT_CONFLICTING', 'MARKET_CONTEXT_UNKNOWN', 'MARKET_CONTEXT_DO_NOT_USE_FOR_MEMORY')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    raw_market_payload_json TEXT,
    normalized_market_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_printer_market_regime_snapshots_captured_at
ON printer_market_regime_snapshots(captured_at);

CREATE INDEX IF NOT EXISTS idx_printer_market_regime_snapshots_regime
ON printer_market_regime_snapshots(market_regime_label);

CREATE INDEX IF NOT EXISTS idx_printer_market_regime_snapshots_transition
ON printer_market_regime_snapshots(market_transition_label);

CREATE INDEX IF NOT EXISTS idx_printer_market_regime_snapshots_source_status
ON printer_market_regime_snapshots(source_status);

CREATE INDEX IF NOT EXISTS idx_printer_market_regime_snapshots_data_quality
ON printer_market_regime_snapshots(data_quality_label);
