CREATE TABLE IF NOT EXISTS printer_token_lifecycle_events (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    previous_state TEXT,
    new_state TEXT NOT NULL,
    lifecycle_event TEXT NOT NULL,
    priority_reason TEXT,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    event_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_token_lifecycle_events_token_id
ON printer_token_lifecycle_events(token_id);

CREATE INDEX IF NOT EXISTS idx_printer_token_lifecycle_events_pair_id
ON printer_token_lifecycle_events(pair_id);

CREATE INDEX IF NOT EXISTS idx_printer_token_lifecycle_events_event
ON printer_token_lifecycle_events(lifecycle_event);

CREATE INDEX IF NOT EXISTS idx_printer_token_lifecycle_events_created_at
ON printer_token_lifecycle_events(created_at);

CREATE INDEX IF NOT EXISTS idx_printer_token_lifecycle_events_state_change
ON printer_token_lifecycle_events(previous_state, new_state);
