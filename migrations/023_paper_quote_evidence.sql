CREATE TABLE IF NOT EXISTS printer_paper_quote_evidence (
    id INTEGER PRIMARY KEY,
    token_id INTEGER NOT NULL,
    pair_id INTEGER,
    snapshot_id INTEGER NOT NULL,
    memory_window_id INTEGER,
    evidence_window_id INTEGER,
    quote_evidence_role TEXT NOT NULL CHECK (quote_evidence_role IN ('ENTRY_QUOTE_CONTEXT', 'EXIT_QUOTE_CONTEXT', 'PAPER_QUOTE_CONTEXT')),
    quote_direction TEXT NOT NULL CHECK (quote_direction IN ('ENTRY', 'EXIT')),
    quote_purpose TEXT NOT NULL CHECK (quote_purpose = 'PAPER_REALISM_ONLY'),
    source_name TEXT NOT NULL,
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    target_status TEXT NOT NULL CHECK (target_status IN ('TARGET_MATCH', 'TARGET_MISMATCH', 'TARGET_UNKNOWN')),
    evidence_captured_at TEXT NOT NULL,
    freshness_label TEXT NOT NULL CHECK (freshness_label IN ('QUOTE_FRESH', 'QUOTE_ACCEPTABLE', 'QUOTE_STALE', 'QUOTE_UNKNOWN', 'QUOTE_FAILED')),
    quote_context_label TEXT NOT NULL CHECK (quote_context_label IN ('QUOTE_ROUTE_AVAILABLE', 'QUOTE_ROUTE_UNAVAILABLE', 'QUOTE_STALE', 'QUOTE_FAILED', 'QUOTE_UNKNOWN', 'QUOTE_TARGET_MISMATCH', 'QUOTE_NOT_PAPER_ONLY', 'QUOTE_DO_NOT_USE_FOR_MEMORY')),
    entry_realism_label TEXT NOT NULL CHECK (entry_realism_label IN ('ENTRY_REALISTIC', 'ENTRY_CAUTION', 'ENTRY_UNKNOWN', 'ENTRY_ROUTE_AVAILABLE', 'ENTRY_ROUTE_UNAVAILABLE', 'ENTRY_REALISM_CAUTION', 'ENTRY_REALISM_UNKNOWN')),
    exit_realism_label TEXT NOT NULL CHECK (exit_realism_label IN ('EXIT_REALISTIC', 'EXIT_CAUTION', 'EXIT_UNKNOWN', 'EXIT_ROUTE_AVAILABLE', 'EXIT_ROUTE_UNAVAILABLE', 'EXIT_REALISM_CAUTION', 'EXIT_REALISM_UNKNOWN')),
    route_available_label TEXT NOT NULL CHECK (route_available_label IN ('ROUTE_AVAILABLE', 'ROUTE_UNAVAILABLE', 'ROUTE_UNKNOWN')),
    slippage_context_label TEXT NOT NULL CHECK (slippage_context_label IN ('SLIPPAGE_ACCEPTABLE', 'SLIPPAGE_CAUTION', 'SLIPPAGE_UNKNOWN')),
    price_impact_context_label TEXT NOT NULL CHECK (price_impact_context_label IN ('PRICE_IMPACT_ACCEPTABLE', 'PRICE_IMPACT_CAUTION', 'PRICE_IMPACT_UNKNOWN')),
    liquidity_context_label TEXT CHECK (liquidity_context_label IN ('LIQUIDITY_CONTEXT_ACCEPTABLE', 'LIQUIDITY_CONTEXT_CAUTION', 'LIQUIDITY_CONTEXT_UNKNOWN')),
    quote_failure_label TEXT CHECK (quote_failure_label IN ('NO_ROUTE_AVAILABLE', 'QUOTE_SOURCE_FAILED', 'QUOTE_STALE_FAILURE', 'QUOTE_TARGET_MISMATCH_FAILURE', 'QUOTE_NOT_PAPER_ONLY_FAILURE', 'QUOTE_UNKNOWN_FAILURE')),
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

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_token_id
ON printer_paper_quote_evidence(token_id);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_pair_id
ON printer_paper_quote_evidence(pair_id);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_snapshot_id
ON printer_paper_quote_evidence(snapshot_id);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_memory_window_id
ON printer_paper_quote_evidence(memory_window_id);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_source_request_id
ON printer_paper_quote_evidence(source_request_id);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_source_response_id
ON printer_paper_quote_evidence(source_response_id);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_source_failure_id
ON printer_paper_quote_evidence(source_failure_id);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_source_status
ON printer_paper_quote_evidence(source_status);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_data_quality_label
ON printer_paper_quote_evidence(data_quality_label);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_target_status
ON printer_paper_quote_evidence(target_status);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_freshness_label
ON printer_paper_quote_evidence(freshness_label);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_entry_realism_label
ON printer_paper_quote_evidence(entry_realism_label);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_exit_realism_label
ON printer_paper_quote_evidence(exit_realism_label);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_quote_context_label
ON printer_paper_quote_evidence(quote_context_label);

CREATE INDEX IF NOT EXISTS idx_printer_paper_quote_evidence_created_at
ON printer_paper_quote_evidence(created_at);
