CREATE TABLE IF NOT EXISTS printer_liquidity_exit_snapshots (
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
    volume_24h REAL,
    txns_5m INTEGER,
    txns_15m INTEGER,
    txns_1h INTEGER,
    txns_24h INTEGER,
    expected_entry_size_usd REAL,
    expected_exit_size_usd REAL,
    estimated_entry_slippage_percent REAL,
    estimated_exit_slippage_percent REAL,
    estimated_entry_price_impact_percent REAL,
    estimated_exit_price_impact_percent REAL,
    route_available INTEGER CHECK (route_available IN (0, 1) OR route_available IS NULL),
    route_source TEXT,
    quote_captured_at TEXT,
    quote_age_seconds INTEGER,
    quote_status TEXT,
    route_status TEXT,
    liquidity_before_usd REAL,
    liquidity_after_usd REAL,
    liquidity_change_percent REAL,
    liquidity_state_label TEXT NOT NULL CHECK (liquidity_state_label IN ('LIQUIDITY_DEEP', 'LIQUIDITY_USABLE', 'LIQUIDITY_THIN', 'LIQUIDITY_UNSTABLE', 'LIQUIDITY_DRAINING', 'LIQUIDITY_DANGEROUS', 'LIQUIDITY_UNKNOWN')),
    entry_realism_label TEXT NOT NULL CHECK (entry_realism_label IN ('ENTRY_REALISTIC', 'ENTRY_POSSIBLE_WITH_SLIPPAGE', 'ENTRY_UNREALISTIC', 'ENTRY_BLOCKED_BY_ROUTE', 'ENTRY_UNKNOWN')),
    exit_realism_label TEXT NOT NULL CHECK (exit_realism_label IN ('EXIT_REALISTIC', 'EXIT_POSSIBLE_WITH_SLIPPAGE', 'EXIT_AT_RISK', 'EXIT_UNREALISTIC', 'EXIT_BLOCKED_BY_ROUTE', 'EXIT_UNKNOWN')),
    slippage_label TEXT NOT NULL CHECK (slippage_label IN ('SLIPPAGE_LOW', 'SLIPPAGE_MODERATE', 'SLIPPAGE_HIGH', 'SLIPPAGE_EXTREME', 'SLIPPAGE_UNKNOWN')),
    price_impact_label TEXT NOT NULL CHECK (price_impact_label IN ('PRICE_IMPACT_LOW', 'PRICE_IMPACT_MODERATE', 'PRICE_IMPACT_HIGH', 'PRICE_IMPACT_EXTREME', 'PRICE_IMPACT_UNKNOWN')),
    route_label TEXT NOT NULL CHECK (route_label IN ('ROUTE_AVAILABLE', 'ROUTE_LIMITED', 'ROUTE_STALE', 'ROUTE_FAILED', 'ROUTE_NOT_AVAILABLE', 'ROUTE_UNKNOWN')),
    quote_age_label TEXT NOT NULL CHECK (quote_age_label IN ('QUOTE_FRESH', 'QUOTE_ACCEPTABLE', 'QUOTE_STALE', 'QUOTE_EXPIRED', 'QUOTE_MISSING')),
    liquidity_drain_label TEXT NOT NULL CHECK (liquidity_drain_label IN ('NO_LIQUIDITY_DRAIN', 'MINOR_LIQUIDITY_DRAIN', 'MAJOR_LIQUIDITY_DRAIN', 'SEVERE_LIQUIDITY_DRAIN', 'LIQUIDITY_DRAIN_UNKNOWN')),
    liquidity_exit_payload_quality_label TEXT NOT NULL CHECK (liquidity_exit_payload_quality_label IN ('LIQUIDITY_EXIT_CONTEXT_CLEAN', 'LIQUIDITY_EXIT_CONTEXT_PARTIAL', 'LIQUIDITY_EXIT_CONTEXT_STALE', 'LIQUIDITY_EXIT_CONTEXT_CONFLICTING', 'LIQUIDITY_EXIT_CONTEXT_UNKNOWN', 'LIQUIDITY_EXIT_CONTEXT_DO_NOT_USE_FOR_MEMORY')),
    realism_gate_label TEXT NOT NULL CHECK (realism_gate_label IN ('REALISM_CONTEXT_ACCEPTABLE', 'REALISM_CONTEXT_CAUTION', 'REALISM_CONTEXT_BLOCKED', 'REALISM_CONTEXT_AUDIT_ONLY', 'REALISM_CONTEXT_DO_NOT_TRAIN')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    raw_liquidity_exit_payload_json TEXT,
    normalized_liquidity_exit_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_liquidity_exit_snapshots_token_id
ON printer_liquidity_exit_snapshots(token_id);

CREATE INDEX IF NOT EXISTS idx_printer_liquidity_exit_snapshots_pair_id
ON printer_liquidity_exit_snapshots(pair_id);

CREATE INDEX IF NOT EXISTS idx_printer_liquidity_exit_snapshots_token_mint
ON printer_liquidity_exit_snapshots(token_mint);

CREATE INDEX IF NOT EXISTS idx_printer_liquidity_exit_snapshots_pair_address
ON printer_liquidity_exit_snapshots(pair_address);

CREATE INDEX IF NOT EXISTS idx_printer_liquidity_exit_snapshots_captured_at
ON printer_liquidity_exit_snapshots(captured_at);

CREATE INDEX IF NOT EXISTS idx_printer_liquidity_exit_snapshots_liquidity_state
ON printer_liquidity_exit_snapshots(liquidity_state_label);

CREATE INDEX IF NOT EXISTS idx_printer_liquidity_exit_snapshots_entry
ON printer_liquidity_exit_snapshots(entry_realism_label);

CREATE INDEX IF NOT EXISTS idx_printer_liquidity_exit_snapshots_exit
ON printer_liquidity_exit_snapshots(exit_realism_label);

CREATE INDEX IF NOT EXISTS idx_printer_liquidity_exit_snapshots_gate
ON printer_liquidity_exit_snapshots(realism_gate_label);

CREATE INDEX IF NOT EXISTS idx_printer_liquidity_exit_snapshots_source_status
ON printer_liquidity_exit_snapshots(source_status);

CREATE INDEX IF NOT EXISTS idx_printer_liquidity_exit_snapshots_data_quality
ON printer_liquidity_exit_snapshots(data_quality_label);
