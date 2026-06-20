CREATE TABLE IF NOT EXISTS printer_chart_volatility_snapshots (
    id INTEGER PRIMARY KEY,
    token_id INTEGER,
    pair_id INTEGER,
    token_mint TEXT,
    pair_address TEXT,
    captured_at TEXT NOT NULL,
    window_start_at TEXT,
    window_end_at TEXT,
    price_open REAL,
    price_high REAL,
    price_low REAL,
    price_close REAL,
    price_change_percent REAL,
    max_runup_percent REAL,
    max_drawdown_percent REAL,
    recovery_from_low_percent REAL,
    high_to_close_fade_percent REAL,
    open_to_low_drop_percent REAL,
    volatility_percent REAL,
    candle_count INTEGER,
    green_candle_count INTEGER,
    red_candle_count INTEGER,
    flat_candle_count INTEGER,
    largest_green_candle_percent REAL,
    largest_red_candle_percent REAL,
    consecutive_green_candles INTEGER,
    consecutive_red_candles INTEGER,
    higher_high_count INTEGER,
    lower_low_count INTEGER,
    range_high REAL,
    range_low REAL,
    range_width_percent REAL,
    breakout_percent REAL,
    breakdown_percent REAL,
    round_trip_percent REAL,
    trend_structure_label TEXT NOT NULL CHECK (trend_structure_label IN ('TREND_UP', 'TREND_DOWN', 'TREND_SIDEWAYS', 'TREND_PARABOLIC_UP', 'TREND_PARABOLIC_DOWN', 'TREND_CHOPPY', 'TREND_UNKNOWN')),
    volatility_label TEXT NOT NULL CHECK (volatility_label IN ('VOLATILITY_LOW', 'VOLATILITY_NORMAL', 'VOLATILITY_ELEVATED', 'VOLATILITY_HIGH', 'VOLATILITY_EXTREME', 'VOLATILITY_UNKNOWN')),
    range_behavior_label TEXT NOT NULL CHECK (range_behavior_label IN ('RANGE_EXPANDING', 'RANGE_COMPRESSING', 'RANGE_BREAKOUT', 'RANGE_BREAKDOWN', 'RANGE_FAKEOUT', 'RANGE_UNKNOWN')),
    momentum_label TEXT NOT NULL CHECK (momentum_label IN ('MOMENTUM_ACCELERATING_UP', 'MOMENTUM_ACCELERATING_DOWN', 'MOMENTUM_FADING', 'MOMENTUM_STABLE', 'MOMENTUM_EXHAUSTED', 'MOMENTUM_UNKNOWN')),
    drawdown_recovery_label TEXT NOT NULL CHECK (drawdown_recovery_label IN ('DRAWDOWN_NONE', 'DRAWDOWN_MINOR', 'DRAWDOWN_MODERATE', 'DRAWDOWN_SEVERE', 'RECOVERY_STRONG', 'RECOVERY_WEAK', 'RECOVERY_FAILED', 'DRAWDOWN_RECOVERY_UNKNOWN')),
    candle_path_label TEXT NOT NULL CHECK (candle_path_label IN ('PATH_STEADY_CLIMB', 'PATH_SPIKE_AND_HOLD', 'PATH_SPIKE_AND_FADE', 'PATH_GRIND_DOWN', 'PATH_V_SHAPED_RECOVERY', 'PATH_ROUND_TRIP', 'PATH_CHOPPY_NOISE', 'PATH_UNKNOWN')),
    chart_payload_quality_label TEXT NOT NULL CHECK (chart_payload_quality_label IN ('CHART_CONTEXT_CLEAN', 'CHART_CONTEXT_PARTIAL', 'CHART_CONTEXT_STALE', 'CHART_CONTEXT_CONFLICTING', 'CHART_CONTEXT_UNKNOWN', 'CHART_CONTEXT_DO_NOT_USE_FOR_MEMORY')),
    chart_memory_gate_label TEXT NOT NULL CHECK (chart_memory_gate_label IN ('CHART_CONTEXT_ACCEPTABLE', 'CHART_CONTEXT_CAUTION', 'CHART_CONTEXT_AUDIT_ONLY', 'CHART_CONTEXT_DO_NOT_TRAIN')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    raw_chart_payload_json TEXT,
    normalized_chart_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_token_id
ON printer_chart_volatility_snapshots(token_id);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_pair_id
ON printer_chart_volatility_snapshots(pair_id);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_token_mint
ON printer_chart_volatility_snapshots(token_mint);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_pair_address
ON printer_chart_volatility_snapshots(pair_address);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_captured_at
ON printer_chart_volatility_snapshots(captured_at);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_window_start
ON printer_chart_volatility_snapshots(window_start_at);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_window_end
ON printer_chart_volatility_snapshots(window_end_at);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_trend
ON printer_chart_volatility_snapshots(trend_structure_label);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_volatility
ON printer_chart_volatility_snapshots(volatility_label);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_range
ON printer_chart_volatility_snapshots(range_behavior_label);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_momentum
ON printer_chart_volatility_snapshots(momentum_label);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_path
ON printer_chart_volatility_snapshots(candle_path_label);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_gate
ON printer_chart_volatility_snapshots(chart_memory_gate_label);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_source_status
ON printer_chart_volatility_snapshots(source_status);

CREATE INDEX IF NOT EXISTS idx_printer_chart_volatility_snapshots_data_quality
ON printer_chart_volatility_snapshots(data_quality_label);
