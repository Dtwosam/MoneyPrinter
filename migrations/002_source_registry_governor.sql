CREATE TABLE IF NOT EXISTS printer_source_registry (
    id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL UNIQUE,
    purpose TEXT NOT NULL,
    dependency_type TEXT NOT NULL,
    requires_paid_plan INTEGER NOT NULL DEFAULT 0 CHECK (requires_paid_plan = 0),
    supports_solana TEXT NOT NULL,
    allowed_request_kinds_json TEXT NOT NULL,
    default_rate_limit_per_minute INTEGER NOT NULL,
    stale_after_seconds INTEGER NOT NULL,
    retry_after_seconds INTEGER NOT NULL,
    max_retries INTEGER NOT NULL,
    priority_class TEXT NOT NULL,
    restriction TEXT,
    is_enabled INTEGER NOT NULL DEFAULT 1 CHECK (is_enabled IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS printer_source_health (
    id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL UNIQUE,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    last_success_at TEXT,
    last_failure_at TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    cooldown_until TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS printer_source_rate_limits (
    id INTEGER PRIMARY KEY,
    source_name TEXT NOT NULL,
    window_started_at TEXT NOT NULL,
    window_seconds INTEGER NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 0,
    request_limit INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (source_name, window_started_at)
);

CREATE INDEX IF NOT EXISTS idx_printer_source_health_status ON printer_source_health(source_name, source_status);
CREATE INDEX IF NOT EXISTS idx_printer_source_rate_limits_source_window ON printer_source_rate_limits(source_name, window_started_at);
