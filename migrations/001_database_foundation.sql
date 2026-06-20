CREATE TABLE IF NOT EXISTS printer_schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS printer_tokens (
    id INTEGER PRIMARY KEY,
    token_mint TEXT NOT NULL UNIQUE,
    chain TEXT NOT NULL DEFAULT 'solana' CHECK (chain = 'solana'),
    symbol TEXT,
    name TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    token_status TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS printer_pairs (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_address TEXT NOT NULL UNIQUE,
    dex TEXT,
    pool_source TEXT,
    base_token_mint TEXT,
    quote_token_mint TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id)
);

CREATE TABLE IF NOT EXISTS printer_source_requests (
    id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL,
    request_kind TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    request_key TEXT,
    tracking_priority INTEGER,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS printer_source_responses (
    id INTEGER PRIMARY KEY,
    source_request_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    received_at TEXT NOT NULL,
    status_code INTEGER,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    response_hash TEXT,
    normalized_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_request_id) REFERENCES printer_source_requests(id)
);

CREATE TABLE IF NOT EXISTS printer_source_failures (
    id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL,
    request_kind TEXT NOT NULL,
    failed_at TEXT NOT NULL,
    failure_type TEXT NOT NULL,
    failure_message TEXT,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    retry_after_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS printer_tracking_queue (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    tracking_lane TEXT NOT NULL,
    tracking_action TEXT NOT NULL,
    priority_reason TEXT,
    next_check_at TEXT,
    last_checked_at TEXT,
    queue_status TEXT,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE TABLE IF NOT EXISTS printer_scheduler_jobs (
    id INTEGER PRIMARY KEY,
    job_name TEXT NOT NULL,
    job_kind TEXT NOT NULL,
    target_table TEXT,
    target_id INTEGER,
    priority INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    locked_at TEXT,
    lock_owner TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS printer_token_snapshots (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    captured_at TEXT NOT NULL,
    tracking_lane TEXT NOT NULL,
    snapshot_mode TEXT NOT NULL,
    price_usd REAL,
    price_native REAL,
    liquidity_usd REAL,
    volume_5m REAL,
    volume_15m REAL,
    volume_1h REAL,
    volume_4h REAL,
    volume_12h REAL,
    volume_24h REAL,
    txns_5m INTEGER,
    txns_15m INTEGER,
    txns_1h INTEGER,
    txns_4h INTEGER,
    txns_12h INTEGER,
    txns_24h INTEGER,
    fdv REAL,
    market_cap REAL,
    price_change_5m REAL,
    price_change_15m REAL,
    price_change_1h REAL,
    price_change_4h REAL,
    price_change_12h REAL,
    price_change_24h REAL,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE TABLE IF NOT EXISTS printer_engine_outputs (
    id INTEGER PRIMARY KEY,
    token_id INTEGER,
    pair_id INTEGER,
    engine_name TEXT NOT NULL,
    output_kind TEXT NOT NULL,
    output_label TEXT,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    output_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE TABLE IF NOT EXISTS printer_memory_windows (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    window_kind TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    expected_snapshot_count INTEGER,
    actual_snapshot_count INTEGER,
    missing_snapshot_count INTEGER,
    coverage_state TEXT,
    memory_status TEXT NOT NULL CHECK (memory_status IN ('CLEAN_MEMORY', 'PARTIAL_MEMORY', 'DIRTY_MEMORY', 'DO_NOT_TRAIN', 'AUDIT_ONLY')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    do_not_train INTEGER NOT NULL DEFAULT 0 CHECK (do_not_train IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE TABLE IF NOT EXISTS printer_episodes (
    id INTEGER PRIMARY KEY,
    memory_window_id INTEGER NOT NULL,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    episode_kind TEXT NOT NULL,
    episode_status TEXT NOT NULL,
    memory_status TEXT NOT NULL CHECK (memory_status IN ('CLEAN_MEMORY', 'PARTIAL_MEMORY', 'DIRTY_MEMORY', 'DO_NOT_TRAIN', 'AUDIT_ONLY')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    do_not_train INTEGER NOT NULL DEFAULT 0 CHECK (do_not_train IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (memory_window_id) REFERENCES printer_memory_windows(id),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE TABLE IF NOT EXISTS printer_episode_snapshots (
    id INTEGER PRIMARY KEY,
    episode_id INTEGER NOT NULL,
    token_snapshot_id INTEGER NOT NULL,
    position_in_episode INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (episode_id) REFERENCES printer_episodes(id),
    FOREIGN KEY (token_snapshot_id) REFERENCES printer_token_snapshots(id)
);

CREATE TABLE IF NOT EXISTS printer_memory_fingerprints (
    id INTEGER PRIMARY KEY,
    episode_id INTEGER NOT NULL,
    fingerprint_kind TEXT NOT NULL,
    fingerprint_payload_json TEXT NOT NULL,
    memory_status TEXT NOT NULL CHECK (memory_status IN ('CLEAN_MEMORY', 'PARTIAL_MEMORY', 'DIRTY_MEMORY', 'DO_NOT_TRAIN', 'AUDIT_ONLY')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    do_not_train INTEGER NOT NULL DEFAULT 0 CHECK (do_not_train IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (episode_id) REFERENCES printer_episodes(id)
);

CREATE TABLE IF NOT EXISTS printer_paper_decisions (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    decision_action TEXT NOT NULL CHECK (decision_action IN ('BUY', 'SELL', 'HOLD', 'WAIT', 'AVOID', 'NO_ACTION')),
    decision_status TEXT NOT NULL,
    memory_window_id INTEGER,
    episode_id INTEGER,
    explanation_json TEXT,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id),
    FOREIGN KEY (memory_window_id) REFERENCES printer_memory_windows(id),
    FOREIGN KEY (episode_id) REFERENCES printer_episodes(id)
);

CREATE TABLE IF NOT EXISTS printer_paper_positions (
    id INTEGER PRIMARY KEY,
    paper_decision_id INTEGER NOT NULL,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    position_status TEXT NOT NULL,
    opened_at TEXT,
    closed_at TEXT,
    paper_entry_price REAL,
    paper_exit_price REAL,
    paper_size_usd REAL,
    paper_pnl_usd REAL,
    paper_pnl_percent REAL,
    realism_status TEXT,
    audit_status TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (paper_decision_id) REFERENCES printer_paper_decisions(id),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE TABLE IF NOT EXISTS printer_paper_trade_events (
    id INTEGER PRIMARY KEY,
    paper_position_id INTEGER NOT NULL,
    event_kind TEXT NOT NULL,
    event_at TEXT NOT NULL,
    price_usd REAL,
    liquidity_usd REAL,
    event_payload_json TEXT,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (paper_position_id) REFERENCES printer_paper_positions(id)
);

CREATE TABLE IF NOT EXISTS printer_paper_trade_audits (
    id INTEGER PRIMARY KEY,
    paper_position_id INTEGER NOT NULL,
    audited_at TEXT NOT NULL,
    audit_status TEXT NOT NULL,
    entry_realism_state TEXT,
    exit_realism_state TEXT,
    slippage_state TEXT,
    liquidity_state TEXT,
    audit_payload_json TEXT,
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (paper_position_id) REFERENCES printer_paper_positions(id)
);

CREATE TABLE IF NOT EXISTS printer_run_logs (
    id INTEGER PRIMARY KEY,
    run_kind TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_printer_tokens_token_mint ON printer_tokens(token_mint);
CREATE INDEX IF NOT EXISTS idx_printer_pairs_pair_address ON printer_pairs(pair_address);
CREATE INDEX IF NOT EXISTS idx_printer_token_snapshots_captured_at ON printer_token_snapshots(captured_at);
CREATE INDEX IF NOT EXISTS idx_printer_tracking_queue_next_check_at ON printer_tracking_queue(next_check_at);
CREATE INDEX IF NOT EXISTS idx_printer_scheduler_jobs_scheduled_for_status ON printer_scheduler_jobs(scheduled_for, status);
CREATE INDEX IF NOT EXISTS idx_printer_memory_windows_token_pair ON printer_memory_windows(token_id, pair_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_token_pair ON printer_paper_decisions(token_id, pair_id);
CREATE INDEX IF NOT EXISTS idx_printer_source_requests_source_status ON printer_source_requests(source_name, source_status);
