CREATE TABLE IF NOT EXISTS printer_safety_evidence_composites (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER NOT NULL,
    snapshot_id INTEGER NOT NULL,
    memory_window_id INTEGER,
    policy_version TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    pair_address TEXT NOT NULL,
    evidence_captured_at TEXT NOT NULL,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    target_status TEXT NOT NULL CHECK (target_status IN ('TARGET_MATCH', 'TARGET_MISMATCH', 'TARGET_UNKNOWN')),
    freshness_label TEXT NOT NULL CHECK (freshness_label IN ('SAFETY_EVIDENCE_FRESH', 'SAFETY_EVIDENCE_ACCEPTABLE', 'SAFETY_EVIDENCE_STALE', 'SAFETY_EVIDENCE_UNKNOWN')),
    mint_authority_status TEXT NOT NULL,
    freeze_authority_status TEXT NOT NULL,
    metadata_mutability_status TEXT NOT NULL,
    supply_sanity_label TEXT NOT NULL,
    holder_concentration_label TEXT NOT NULL,
    liquidity_lock_or_burn_label TEXT NOT NULL,
    known_risk_flag_label TEXT NOT NULL,
    token_program_label TEXT NOT NULL,
    safety_context_label TEXT NOT NULL,
    safety_contract_label TEXT NOT NULL CHECK (safety_contract_label IN ('SAFETY_CLEAN', 'SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY', 'SAFETY_BLOCKED_FOR_15M_MEMORY')),
    provenance_complete INTEGER NOT NULL CHECK (provenance_complete IN (0, 1)),
    conflicts_json TEXT NOT NULL DEFAULT '[]',
    blockers_json TEXT NOT NULL DEFAULT '[]',
    optional_unknowns_json TEXT NOT NULL DEFAULT '[]',
    field_bindings_json TEXT NOT NULL DEFAULT '{}',
    paper_only_context INTEGER NOT NULL DEFAULT 1 CHECK (paper_only_context = 1),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id),
    FOREIGN KEY (snapshot_id) REFERENCES printer_token_snapshots(id),
    FOREIGN KEY (memory_window_id) REFERENCES printer_memory_windows(id),
    UNIQUE (token_id, pair_id, snapshot_id, policy_version)
);

CREATE TABLE IF NOT EXISTS printer_safety_evidence_contributions (
    id INTEGER PRIMARY KEY,
    composite_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,
    evidence_category TEXT NOT NULL,
    source_request_id INTEGER NOT NULL,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    captured_at TEXT NOT NULL,
    freshness_label TEXT NOT NULL,
    token_mint TEXT NOT NULL,
    pair_address TEXT NOT NULL,
    fields_supplied_json TEXT NOT NULL DEFAULT '{}',
    source_status TEXT NOT NULL,
    data_quality_label TEXT NOT NULL,
    target_status TEXT NOT NULL,
    rejection_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (composite_id) REFERENCES printer_safety_evidence_composites(id),
    FOREIGN KEY (source_request_id) REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id) REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id) REFERENCES printer_source_failures(id),
    UNIQUE (composite_id, source_name, evidence_category, source_request_id)
);

CREATE INDEX IF NOT EXISTS idx_printer_safety_composites_target
ON printer_safety_evidence_composites(token_id, pair_id, snapshot_id);

CREATE INDEX IF NOT EXISTS idx_printer_safety_contributions_composite
ON printer_safety_evidence_contributions(composite_id);
