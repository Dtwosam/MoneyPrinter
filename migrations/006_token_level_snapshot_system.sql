ALTER TABLE printer_token_snapshots ADD COLUMN pair_age_seconds INTEGER;
ALTER TABLE printer_token_snapshots ADD COLUMN token_age_seconds INTEGER;
ALTER TABLE printer_token_snapshots ADD COLUMN quote_status TEXT;
ALTER TABLE printer_token_snapshots ADD COLUMN route_status TEXT;
ALTER TABLE printer_token_snapshots ADD COLUMN snapshot_quality_label TEXT;
ALTER TABLE printer_token_snapshots ADD COLUMN snapshot_gap_label TEXT;
ALTER TABLE printer_token_snapshots ADD COLUMN coverage_label TEXT;
ALTER TABLE printer_token_snapshots ADD COLUMN raw_snapshot_payload_json TEXT;
ALTER TABLE printer_token_snapshots ADD COLUMN normalized_snapshot_payload_json TEXT;

CREATE TABLE IF NOT EXISTS printer_snapshot_gap_audits (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    tracking_lane TEXT NOT NULL,
    snapshot_mode TEXT NOT NULL,
    expected_captured_at TEXT NOT NULL,
    actual_captured_at TEXT,
    gap_seconds INTEGER NOT NULL,
    snapshot_gap_label TEXT NOT NULL,
    coverage_label TEXT NOT NULL,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE TABLE IF NOT EXISTS printer_snapshot_window_coverage (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    window_kind TEXT NOT NULL,
    tracking_lane TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT NOT NULL,
    expected_snapshot_count INTEGER NOT NULL,
    actual_snapshot_count INTEGER NOT NULL,
    missing_snapshot_count INTEGER NOT NULL,
    max_gap_seconds INTEGER NOT NULL,
    coverage_label TEXT NOT NULL,
    memory_status TEXT NOT NULL CHECK (memory_status IN ('CLEAN_MEMORY', 'PARTIAL_MEMORY', 'DIRTY_MEMORY', 'DO_NOT_TRAIN', 'AUDIT_ONLY')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    do_not_train INTEGER NOT NULL DEFAULT 0 CHECK (do_not_train IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_token_snapshots_token_pair_captured
ON printer_token_snapshots(token_id, pair_id, captured_at);

CREATE INDEX IF NOT EXISTS idx_printer_token_snapshots_tracking_lane
ON printer_token_snapshots(tracking_lane);

CREATE INDEX IF NOT EXISTS idx_printer_token_snapshots_snapshot_mode
ON printer_token_snapshots(snapshot_mode);

CREATE INDEX IF NOT EXISTS idx_printer_token_snapshots_quality
ON printer_token_snapshots(snapshot_quality_label);

CREATE INDEX IF NOT EXISTS idx_printer_token_snapshots_coverage
ON printer_token_snapshots(coverage_label);

CREATE INDEX IF NOT EXISTS idx_printer_snapshot_gap_audits_token_pair_expected
ON printer_snapshot_gap_audits(token_id, pair_id, expected_captured_at);

CREATE INDEX IF NOT EXISTS idx_printer_snapshot_gap_audits_tracking_lane
ON printer_snapshot_gap_audits(tracking_lane);

CREATE INDEX IF NOT EXISTS idx_printer_snapshot_gap_audits_mode
ON printer_snapshot_gap_audits(snapshot_mode);

CREATE INDEX IF NOT EXISTS idx_printer_snapshot_gap_audits_gap_label
ON printer_snapshot_gap_audits(snapshot_gap_label);

CREATE INDEX IF NOT EXISTS idx_printer_snapshot_gap_audits_coverage
ON printer_snapshot_gap_audits(coverage_label);

CREATE INDEX IF NOT EXISTS idx_printer_snapshot_window_coverage_token_pair_window
ON printer_snapshot_window_coverage(token_id, pair_id, opened_at, closed_at);

CREATE INDEX IF NOT EXISTS idx_printer_snapshot_window_coverage_tracking_lane
ON printer_snapshot_window_coverage(tracking_lane);

CREATE INDEX IF NOT EXISTS idx_printer_snapshot_window_coverage_coverage
ON printer_snapshot_window_coverage(coverage_label);
