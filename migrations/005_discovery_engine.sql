CREATE TABLE IF NOT EXISTS printer_discovery_candidates (
    id INTEGER PRIMARY KEY,
    source_response_id INTEGER,
    token_id INTEGER,
    pair_id INTEGER,
    source_name TEXT NOT NULL,
    discovery_label TEXT NOT NULL,
    discovery_action TEXT NOT NULL,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    raw_candidate_payload_json TEXT,
    normalized_candidate_payload_json TEXT,
    lifecycle_state TEXT,
    tracking_lane TEXT,
    priority_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (source_response_id) REFERENCES printer_source_responses(id),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_discovery_candidates_source_name
ON printer_discovery_candidates(source_name);

CREATE INDEX IF NOT EXISTS idx_printer_discovery_candidates_token_id
ON printer_discovery_candidates(token_id);

CREATE INDEX IF NOT EXISTS idx_printer_discovery_candidates_pair_id
ON printer_discovery_candidates(pair_id);

CREATE INDEX IF NOT EXISTS idx_printer_discovery_candidates_label
ON printer_discovery_candidates(discovery_label);

CREATE INDEX IF NOT EXISTS idx_printer_discovery_candidates_action
ON printer_discovery_candidates(discovery_action);

CREATE INDEX IF NOT EXISTS idx_printer_discovery_candidates_created_at
ON printer_discovery_candidates(created_at);
