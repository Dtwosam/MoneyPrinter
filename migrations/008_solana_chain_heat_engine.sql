CREATE TABLE IF NOT EXISTS printer_solana_chain_heat_snapshots (
    id INTEGER PRIMARY KEY,
    captured_at TEXT NOT NULL,
    sol_price_usd REAL,
    sol_change_1h REAL,
    sol_change_24h REAL,
    sol_change_7d REAL,
    sol_volume_24h REAL,
    solana_tvl_usd REAL,
    solana_dex_volume_24h REAL,
    solana_stablecoin_supply REAL,
    solana_active_addresses INTEGER,
    solana_tx_count_24h INTEGER,
    solana_priority_fee_context TEXT,
    solana_congestion_context TEXT,
    solana_new_token_count INTEGER,
    solana_hot_pair_count INTEGER,
    solana_meme_volume_24h REAL,
    solana_meme_liquidity_usd REAL,
    solana_meme_new_pair_count INTEGER,
    solana_meme_graduation_count INTEGER,
    solana_meme_failed_pair_count INTEGER,
    chain_heat_label TEXT NOT NULL CHECK (chain_heat_label IN ('SOLANA_HOT', 'SOLANA_WARM', 'SOLANA_NEUTRAL', 'SOLANA_COOL', 'SOLANA_COLD', 'SOLANA_CONGESTED', 'SOLANA_QUIET', 'SOLANA_UNKNOWN')),
    activity_label TEXT NOT NULL CHECK (activity_label IN ('ACTIVITY_SURGING', 'ACTIVITY_ELEVATED', 'ACTIVITY_NORMAL', 'ACTIVITY_WEAK', 'ACTIVITY_DEAD', 'ACTIVITY_UNKNOWN')),
    liquidity_label TEXT NOT NULL CHECK (liquidity_label IN ('LIQUIDITY_EXPANDING', 'LIQUIDITY_STABLE', 'LIQUIDITY_THINNING', 'LIQUIDITY_STRESSED', 'LIQUIDITY_UNKNOWN')),
    congestion_label TEXT NOT NULL CHECK (congestion_label IN ('CONGESTION_LOW', 'CONGESTION_NORMAL', 'CONGESTION_HIGH', 'CONGESTION_SEVERE', 'CONGESTION_UNKNOWN')),
    chain_heat_payload_quality_label TEXT NOT NULL CHECK (chain_heat_payload_quality_label IN ('CHAIN_HEAT_CONTEXT_CLEAN', 'CHAIN_HEAT_CONTEXT_PARTIAL', 'CHAIN_HEAT_CONTEXT_STALE', 'CHAIN_HEAT_CONTEXT_CONFLICTING', 'CHAIN_HEAT_CONTEXT_UNKNOWN', 'CHAIN_HEAT_CONTEXT_DO_NOT_USE_FOR_MEMORY')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    raw_chain_heat_payload_json TEXT,
    normalized_chain_heat_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_printer_solana_chain_heat_snapshots_captured_at
ON printer_solana_chain_heat_snapshots(captured_at);

CREATE INDEX IF NOT EXISTS idx_printer_solana_chain_heat_snapshots_heat
ON printer_solana_chain_heat_snapshots(chain_heat_label);

CREATE INDEX IF NOT EXISTS idx_printer_solana_chain_heat_snapshots_activity
ON printer_solana_chain_heat_snapshots(activity_label);

CREATE INDEX IF NOT EXISTS idx_printer_solana_chain_heat_snapshots_liquidity
ON printer_solana_chain_heat_snapshots(liquidity_label);

CREATE INDEX IF NOT EXISTS idx_printer_solana_chain_heat_snapshots_congestion
ON printer_solana_chain_heat_snapshots(congestion_label);

CREATE INDEX IF NOT EXISTS idx_printer_solana_chain_heat_snapshots_source_status
ON printer_solana_chain_heat_snapshots(source_status);

CREATE INDEX IF NOT EXISTS idx_printer_solana_chain_heat_snapshots_data_quality
ON printer_solana_chain_heat_snapshots(data_quality_label);
