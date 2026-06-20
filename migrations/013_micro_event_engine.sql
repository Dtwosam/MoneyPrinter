CREATE TABLE IF NOT EXISTS printer_micro_events (
    id INTEGER PRIMARY KEY,
    token_id INTEGER,
    pair_id INTEGER,
    token_mint TEXT,
    pair_address TEXT,
    detected_at TEXT NOT NULL,
    event_window_start_at TEXT,
    event_window_end_at TEXT,
    hold_check_15m_at TEXT,
    price_start REAL,
    price_high REAL,
    price_low REAL,
    price_end REAL,
    price_change_5m_percent REAL,
    high_to_end_fade_percent REAL,
    max_drawdown_5m_percent REAL,
    wick_percent REAL,
    volume_5m REAL,
    volume_change_5m_percent REAL,
    txns_5m INTEGER,
    txns_change_5m_percent REAL,
    buys_5m INTEGER,
    sells_5m INTEGER,
    buy_volume_5m REAL,
    sell_volume_5m REAL,
    liquidity_start_usd REAL,
    liquidity_end_usd REAL,
    liquidity_change_5m_percent REAL,
    liquidity_exit_realism_label TEXT,
    slippage_label TEXT,
    price_impact_label TEXT,
    route_label TEXT,
    safety_status_label TEXT,
    liquidity_state_label TEXT,
    flow_direction_label TEXT,
    candle_path_label TEXT,
    micro_event_state_label TEXT NOT NULL CHECK (micro_event_state_label IN ('NO_MICRO_EVENT', 'FAST_MICRO_PUMP', 'TRADABLE_MICRO_PUMP', 'UNTRADABLE_MICRO_PUMP', 'FAKE_PUMP_WITH_EXIT', 'FAKE_PUMP_NO_EXIT', 'FAST_PUMP_DUMP', 'WICK_PUMP', 'WICK_ONLY_PUMP', 'LATE_BUY_TRAP', 'MICRO_PUMP_TO_SUSTAINED_PUMP', 'MICRO_PUMP_TO_CONSOLIDATION', 'MICRO_PUMP_TO_DEAD_TOKEN', 'MICRO_EVENT_UNKNOWN')),
    micro_event_move_label TEXT NOT NULL CHECK (micro_event_move_label IN ('MOVE_FAST_UP', 'MOVE_FAST_DOWN', 'MOVE_SPIKE_AND_HOLD', 'MOVE_SPIKE_AND_FADE', 'MOVE_WICK_ONLY', 'MOVE_ROUND_TRIP', 'MOVE_NO_CLEAR_EVENT', 'MOVE_UNKNOWN')),
    micro_exit_realism_label TEXT NOT NULL CHECK (micro_exit_realism_label IN ('MICRO_EXIT_REALISTIC', 'MICRO_EXIT_POSSIBLE_WITH_SLIPPAGE', 'MICRO_EXIT_FRAGILE', 'MICRO_EXIT_UNREALISTIC', 'MICRO_EXIT_NO_EXIT', 'MICRO_EXIT_UNKNOWN')),
    late_buy_trap_label TEXT NOT NULL CHECK (late_buy_trap_label IN ('NO_LATE_BUY_TRAP', 'POSSIBLE_LATE_BUY_TRAP', 'CONFIRMED_LATE_BUY_TRAP', 'LATE_BUY_TRAP_UNKNOWN')),
    held_to_15m_result_label TEXT NOT NULL CHECK (held_to_15m_result_label IN ('HELD_TO_15M_CONTINUED', 'HELD_TO_15M_CONSOLIDATED', 'HELD_TO_15M_FADED', 'HELD_TO_15M_DUMPED', 'HELD_TO_15M_DEAD', 'HELD_TO_15M_UNKNOWN')),
    micro_event_payload_quality_label TEXT NOT NULL CHECK (micro_event_payload_quality_label IN ('MICRO_EVENT_CONTEXT_CLEAN', 'MICRO_EVENT_CONTEXT_PARTIAL', 'MICRO_EVENT_CONTEXT_STALE', 'MICRO_EVENT_CONTEXT_CONFLICTING', 'MICRO_EVENT_CONTEXT_UNKNOWN', 'MICRO_EVENT_CONTEXT_DO_NOT_USE_FOR_MEMORY')),
    micro_event_memory_gate_label TEXT NOT NULL CHECK (micro_event_memory_gate_label IN ('MICRO_EVENT_SUPPORT_EVIDENCE', 'MICRO_EVENT_AUDIT_ONLY', 'MICRO_EVENT_DO_NOT_TRAIN', 'MICRO_EVENT_IGNORE')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    raw_micro_event_payload_json TEXT,
    normalized_micro_event_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_micro_events_token_id ON printer_micro_events(token_id);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_pair_id ON printer_micro_events(pair_id);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_token_mint ON printer_micro_events(token_mint);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_pair_address ON printer_micro_events(pair_address);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_detected_at ON printer_micro_events(detected_at);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_window_start ON printer_micro_events(event_window_start_at);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_window_end ON printer_micro_events(event_window_end_at);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_state ON printer_micro_events(micro_event_state_label);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_move ON printer_micro_events(micro_event_move_label);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_exit ON printer_micro_events(micro_exit_realism_label);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_late_buy ON printer_micro_events(late_buy_trap_label);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_hold_15m ON printer_micro_events(held_to_15m_result_label);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_gate ON printer_micro_events(micro_event_memory_gate_label);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_source_status ON printer_micro_events(source_status);
CREATE INDEX IF NOT EXISTS idx_printer_micro_events_data_quality ON printer_micro_events(data_quality_label);
