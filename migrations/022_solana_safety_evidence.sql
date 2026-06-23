CREATE TABLE IF NOT EXISTS printer_solana_safety_evidence (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    snapshot_id INTEGER NOT NULL,
    memory_window_id INTEGER,
    evidence_window_id INTEGER,
    safety_evidence_role TEXT NOT NULL CHECK (safety_evidence_role IN ('TOKEN_SAFETY_CONTEXT')),
    source_name TEXT NOT NULL,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    target_status TEXT NOT NULL CHECK (target_status IN ('TARGET_MATCH', 'TARGET_MISMATCH', 'TARGET_UNKNOWN')),
    evidence_captured_at TEXT NOT NULL,
    freshness_label TEXT NOT NULL CHECK (freshness_label IN ('SAFETY_EVIDENCE_FRESH', 'SAFETY_EVIDENCE_ACCEPTABLE', 'SAFETY_EVIDENCE_STALE', 'SAFETY_EVIDENCE_UNKNOWN')),
    mint_authority_status TEXT NOT NULL CHECK (mint_authority_status IN ('MINT_AUTHORITY_RENOUNCED', 'MINT_AUTHORITY_PRESENT', 'MINT_AUTHORITY_UNKNOWN')),
    freeze_authority_status TEXT NOT NULL CHECK (freeze_authority_status IN ('FREEZE_AUTHORITY_DISABLED', 'FREEZE_AUTHORITY_PRESENT', 'FREEZE_AUTHORITY_UNKNOWN')),
    metadata_mutability_status TEXT NOT NULL CHECK (metadata_mutability_status IN ('METADATA_IMMUTABLE', 'METADATA_MUTABLE', 'METADATA_UNKNOWN')),
    supply_sanity_label TEXT NOT NULL CHECK (supply_sanity_label IN ('SUPPLY_SANITY_OK', 'SUPPLY_SANITY_CAUTION', 'SUPPLY_SANITY_UNKNOWN')),
    holder_concentration_label TEXT NOT NULL CHECK (holder_concentration_label IN ('HOLDER_CONCENTRATION_HEALTHY', 'HOLDER_CONCENTRATION_CONCENTRATED', 'HOLDER_CONCENTRATION_EXTREME', 'HOLDER_CONCENTRATION_UNKNOWN')),
    liquidity_lock_or_burn_label TEXT NOT NULL CHECK (liquidity_lock_or_burn_label IN ('LIQUIDITY_LOCK_OR_BURN_CONFIRMED', 'LIQUIDITY_LOCK_OR_BURN_UNKNOWN', 'LIQUIDITY_UNLOCKED_OR_DANGEROUS')),
    known_risk_flag_label TEXT NOT NULL CHECK (known_risk_flag_label IN ('NO_KNOWN_RISK_FLAGS', 'KNOWN_RISK_FLAGS_PRESENT', 'KNOWN_RISK_FLAGS_UNKNOWN')),
    token_program_label TEXT NOT NULL CHECK (token_program_label IN ('SPL_TOKEN_OR_TOKEN_2022_VERIFIED', 'TOKEN_PROGRAM_UNKNOWN', 'TOKEN_PROGRAM_UNSUPPORTED')),
    safety_context_label TEXT NOT NULL CHECK (safety_context_label IN ('SAFETY_CLEAN', 'SAFETY_CAUTION', 'SAFETY_SUSPICIOUS', 'SAFETY_UNSAFE', 'SAFETY_UNKNOWN', 'SAFETY_DO_NOT_USE_FOR_MEMORY')),
    source_request_id INTEGER,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    paper_only_context INTEGER NOT NULL DEFAULT 1 CHECK (paper_only_context = 1),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id),
    FOREIGN KEY (snapshot_id) REFERENCES printer_token_snapshots(id),
    FOREIGN KEY (memory_window_id) REFERENCES printer_memory_windows(id),
    FOREIGN KEY (source_request_id) REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id) REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id) REFERENCES printer_source_failures(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_token_id
ON printer_solana_safety_evidence(token_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_pair_id
ON printer_solana_safety_evidence(pair_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_snapshot_id
ON printer_solana_safety_evidence(snapshot_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_memory_window_id
ON printer_solana_safety_evidence(memory_window_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_source_request_id
ON printer_solana_safety_evidence(source_request_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_source_response_id
ON printer_solana_safety_evidence(source_response_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_source_failure_id
ON printer_solana_safety_evidence(source_failure_id);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_source_status
ON printer_solana_safety_evidence(source_status);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_data_quality_label
ON printer_solana_safety_evidence(data_quality_label);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_freshness_label
ON printer_solana_safety_evidence(freshness_label);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_target_status
ON printer_solana_safety_evidence(target_status);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_safety_context_label
ON printer_solana_safety_evidence(safety_context_label);

CREATE INDEX IF NOT EXISTS idx_printer_solana_safety_evidence_created_at
ON printer_solana_safety_evidence(created_at);
