CREATE TABLE IF NOT EXISTS printer_trading_flow_snapshots (
    id INTEGER PRIMARY KEY,
    token_id INTEGER,
    pair_id INTEGER,
    token_mint TEXT,
    pair_address TEXT,
    captured_at TEXT NOT NULL,
    price_usd REAL,
    liquidity_usd REAL,
    volume_5m REAL,
    volume_15m REAL,
    volume_1h REAL,
    volume_4h REAL,
    volume_24h REAL,
    txns_5m INTEGER,
    txns_15m INTEGER,
    txns_1h INTEGER,
    txns_4h INTEGER,
    txns_24h INTEGER,
    buys_5m INTEGER,
    sells_5m INTEGER,
    buys_15m INTEGER,
    sells_15m INTEGER,
    buys_1h INTEGER,
    sells_1h INTEGER,
    buys_4h INTEGER,
    sells_4h INTEGER,
    buys_24h INTEGER,
    sells_24h INTEGER,
    buy_volume_5m REAL,
    sell_volume_5m REAL,
    buy_volume_15m REAL,
    sell_volume_15m REAL,
    buy_volume_1h REAL,
    sell_volume_1h REAL,
    buy_volume_4h REAL,
    sell_volume_4h REAL,
    buy_volume_24h REAL,
    sell_volume_24h REAL,
    unique_wallets_5m INTEGER,
    unique_wallets_15m INTEGER,
    unique_wallets_1h INTEGER,
    unique_wallets_24h INTEGER,
    new_wallets_5m INTEGER,
    new_wallets_15m INTEGER,
    repeat_wallets_5m INTEGER,
    repeat_wallets_15m INTEGER,
    flow_direction_label TEXT NOT NULL CHECK (flow_direction_label IN ('FLOW_ACCUMULATION', 'FLOW_DISTRIBUTION', 'FLOW_ROTATION', 'FLOW_EXHAUSTION', 'FLOW_CHOPPY', 'FLOW_WASH_LIKE', 'FLOW_UNKNOWN')),
    flow_pressure_label TEXT NOT NULL CHECK (flow_pressure_label IN ('PRESSURE_STRONG_INFLOW', 'PRESSURE_MODERATE_INFLOW', 'PRESSURE_BALANCED', 'PRESSURE_MODERATE_OUTFLOW', 'PRESSURE_STRONG_OUTFLOW', 'PRESSURE_UNKNOWN')),
    imbalance_label TEXT NOT NULL CHECK (imbalance_label IN ('IMBALANCE_BUY_HEAVY', 'IMBALANCE_SELL_HEAVY', 'IMBALANCE_BALANCED', 'IMBALANCE_NOISY', 'IMBALANCE_UNKNOWN')),
    volume_activity_label TEXT NOT NULL CHECK (volume_activity_label IN ('VOLUME_SURGING', 'VOLUME_ELEVATED', 'VOLUME_NORMAL', 'VOLUME_WEAK', 'VOLUME_DEAD', 'VOLUME_UNKNOWN')),
    tx_activity_label TEXT NOT NULL CHECK (tx_activity_label IN ('TX_ACTIVITY_SURGING', 'TX_ACTIVITY_ELEVATED', 'TX_ACTIVITY_NORMAL', 'TX_ACTIVITY_WEAK', 'TX_ACTIVITY_DEAD', 'TX_ACTIVITY_UNKNOWN')),
    wallet_participation_label TEXT NOT NULL CHECK (wallet_participation_label IN ('WALLETS_BROAD_PARTICIPATION', 'WALLETS_NARROW_PARTICIPATION', 'WALLETS_CONCENTRATED', 'WALLETS_WASH_LIKE', 'WALLETS_UNKNOWN')),
    trading_flow_payload_quality_label TEXT NOT NULL CHECK (trading_flow_payload_quality_label IN ('TRADING_FLOW_CONTEXT_CLEAN', 'TRADING_FLOW_CONTEXT_PARTIAL', 'TRADING_FLOW_CONTEXT_STALE', 'TRADING_FLOW_CONTEXT_CONFLICTING', 'TRADING_FLOW_CONTEXT_UNKNOWN', 'TRADING_FLOW_CONTEXT_DO_NOT_USE_FOR_MEMORY')),
    flow_memory_gate_label TEXT NOT NULL CHECK (flow_memory_gate_label IN ('FLOW_CONTEXT_ACCEPTABLE', 'FLOW_CONTEXT_CAUTION', 'FLOW_CONTEXT_AUDIT_ONLY', 'FLOW_CONTEXT_DO_NOT_TRAIN')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    raw_trading_flow_payload_json TEXT,
    normalized_trading_flow_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_token_id
ON printer_trading_flow_snapshots(token_id);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_pair_id
ON printer_trading_flow_snapshots(pair_id);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_token_mint
ON printer_trading_flow_snapshots(token_mint);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_pair_address
ON printer_trading_flow_snapshots(pair_address);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_captured_at
ON printer_trading_flow_snapshots(captured_at);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_direction
ON printer_trading_flow_snapshots(flow_direction_label);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_pressure
ON printer_trading_flow_snapshots(flow_pressure_label);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_imbalance
ON printer_trading_flow_snapshots(imbalance_label);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_volume
ON printer_trading_flow_snapshots(volume_activity_label);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_tx
ON printer_trading_flow_snapshots(tx_activity_label);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_wallets
ON printer_trading_flow_snapshots(wallet_participation_label);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_gate
ON printer_trading_flow_snapshots(flow_memory_gate_label);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_source_status
ON printer_trading_flow_snapshots(source_status);

CREATE INDEX IF NOT EXISTS idx_printer_trading_flow_snapshots_data_quality
ON printer_trading_flow_snapshots(data_quality_label);
