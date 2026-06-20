CREATE TABLE IF NOT EXISTS printer_memory_retrieval_queries (
    id INTEGER PRIMARY KEY,
    query_type TEXT NOT NULL CHECK (query_type IN ('CURRENT_SETUP_QUERY', 'TOKEN_PAIR_HISTORY_QUERY', 'OUTCOME_LOOKBACK_QUERY', 'CLEAN_MEMORY_ONLY_QUERY', 'AUDIT_MEMORY_REVIEW_QUERY')),
    token_id INTEGER,
    pair_id INTEGER,
    token_mint TEXT,
    pair_address TEXT,
    query_at TEXT NOT NULL,
    current_fingerprint_json TEXT,
    query_context_json TEXT,
    retrieval_result_label TEXT NOT NULL CHECK (retrieval_result_label IN ('RETRIEVAL_HAS_CLEAN_MATCHES', 'RETRIEVAL_HAS_PARTIAL_MATCHES_ONLY', 'RETRIEVAL_HAS_AUDIT_ONLY_MATCHES', 'RETRIEVAL_NO_MATCHES', 'RETRIEVAL_BLOCKED_NO_CLEAN_MEMORY', 'RETRIEVAL_BLOCKED_DIRTY_CURRENT_CONTEXT')),
    memory_evidence_label TEXT NOT NULL CHECK (memory_evidence_label IN ('MEMORY_EVIDENCE_STRONG', 'MEMORY_EVIDENCE_MIXED', 'MEMORY_EVIDENCE_WEAK', 'MEMORY_EVIDENCE_CONFLICTING', 'MEMORY_EVIDENCE_NOT_ENOUGH')),
    data_quality_label TEXT NOT NULL CHECK (data_quality_label IN ('CLEAN_DATA', 'ACCEPTABLE_PARTIAL_DATA', 'DIRTY_DATA', 'STALE_DATA', 'MISSING_CRITICAL_DATA', 'CONFLICTING_DATA', 'DO_NOT_TRAIN')),
    source_status TEXT NOT NULL CHECK (source_status IN ('COMPLETE', 'PARTIAL', 'FAILED', 'STALE', 'CONFLICTING')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE TABLE IF NOT EXISTS printer_memory_retrieval_matches (
    id INTEGER PRIMARY KEY,
    retrieval_query_id INTEGER NOT NULL,
    episode_id INTEGER,
    memory_window_id INTEGER,
    token_id INTEGER,
    pair_id INTEGER,
    window_kind TEXT,
    outcome_label TEXT,
    action_lesson_label TEXT,
    memory_quality_label TEXT,
    match_strength_label TEXT NOT NULL CHECK (match_strength_label IN ('EXACT_CONDITION_MATCH', 'STRONG_CONDITION_MATCH', 'PARTIAL_CONDITION_MATCH', 'WEAK_CONDITION_MATCH', 'NO_USABLE_MATCH', 'DIRTY_MEMORY_EXCLUDED', 'DO_NOT_TRAIN_EXCLUDED')),
    match_reasons_json TEXT,
    mismatch_reasons_json TEXT,
    memory_fingerprint_json TEXT,
    comparison_payload_json TEXT,
    included_as_clean_evidence INTEGER NOT NULL DEFAULT 0 CHECK (included_as_clean_evidence IN (0, 1)),
    included_as_audit_context INTEGER NOT NULL DEFAULT 0 CHECK (included_as_audit_context IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (retrieval_query_id) REFERENCES printer_memory_retrieval_queries(id),
    FOREIGN KEY (episode_id) REFERENCES printer_episodes(id),
    FOREIGN KEY (memory_window_id) REFERENCES printer_memory_windows(id),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_queries_token_id ON printer_memory_retrieval_queries(token_id);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_queries_pair_id ON printer_memory_retrieval_queries(pair_id);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_queries_query_at ON printer_memory_retrieval_queries(query_at);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_queries_result ON printer_memory_retrieval_queries(retrieval_result_label);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_queries_evidence ON printer_memory_retrieval_queries(memory_evidence_label);

CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_matches_query_id ON printer_memory_retrieval_matches(retrieval_query_id);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_matches_episode_id ON printer_memory_retrieval_matches(episode_id);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_matches_window_id ON printer_memory_retrieval_matches(memory_window_id);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_matches_token_id ON printer_memory_retrieval_matches(token_id);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_matches_pair_id ON printer_memory_retrieval_matches(pair_id);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_matches_window_kind ON printer_memory_retrieval_matches(window_kind);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_matches_outcome ON printer_memory_retrieval_matches(outcome_label);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_matches_lesson ON printer_memory_retrieval_matches(action_lesson_label);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_matches_quality ON printer_memory_retrieval_matches(memory_quality_label);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_matches_strength ON printer_memory_retrieval_matches(match_strength_label);
CREATE INDEX IF NOT EXISTS idx_printer_memory_retrieval_matches_created ON printer_memory_retrieval_matches(created_at);
