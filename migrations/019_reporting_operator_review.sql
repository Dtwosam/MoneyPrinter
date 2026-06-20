CREATE TABLE IF NOT EXISTS printer_operator_review_reports (
    id INTEGER PRIMARY KEY,
    report_scope_label TEXT NOT NULL CHECK (report_scope_label IN ('REPORT_DB_STATE', 'REPORT_SYSTEM_HEALTH', 'REPORT_SOURCE_HEALTH', 'REPORT_SCHEDULER_HEALTH', 'REPORT_LIFECYCLE_QUEUE', 'REPORT_DISCOVERY', 'REPORT_TOKEN_SNAPSHOTS', 'REPORT_CONTEXT_ENGINES', 'REPORT_MEMORY', 'REPORT_MEMORY_RETRIEVAL', 'REPORT_PAPER_DECISIONS', 'REPORT_PAPER_POSITIONS', 'REPORT_PAPER_AUDITS', 'REPORT_FULL_OPERATOR_REVIEW', 'REPORT_UNKNOWN_SCOPE')),
    report_status_label TEXT NOT NULL CHECK (report_status_label IN ('REPORT_READY', 'REPORT_PARTIAL', 'REPORT_EMPTY', 'REPORT_STALE', 'REPORT_CONFLICTING', 'REPORT_FAILED', 'REPORT_NO_DB', 'REPORT_SCHEMA_ONLY', 'REPORT_UNKNOWN')),
    operator_review_label TEXT NOT NULL CHECK (operator_review_label IN ('OPERATOR_REVIEW_OK', 'OPERATOR_REVIEW_NEEDS_ATTENTION', 'OPERATOR_REVIEW_BLOCKED', 'OPERATOR_REVIEW_AUDIT_ONLY', 'OPERATOR_REVIEW_NO_DB', 'OPERATOR_REVIEW_SCHEMA_ONLY', 'OPERATOR_REVIEW_NO_DATA', 'OPERATOR_REVIEW_UNKNOWN')),
    report_format_label TEXT NOT NULL CHECK (report_format_label IN ('REPORT_FORMAT_JSON', 'REPORT_FORMAT_MARKDOWN', 'REPORT_FORMAT_TEXT')),
    generated_at TEXT NOT NULL,
    db_state_classification TEXT CHECK (db_state_classification IN ('NO_PERSISTENT_DB_FOUND', 'PERSISTENT_DB_EMPTY_SCHEMA_ONLY', 'PERSISTENT_DB_HAS_TEST_ONLY_ROWS', 'PERSISTENT_DB_HAS_REAL_TOKEN_ROWS', 'PERSISTENT_DB_HAS_REAL_MEMORY_ROWS', 'PERSISTENT_DB_HAS_REAL_PAPER_ROWS', 'PERSISTENT_DB_STATE_UNCLEAR')),
    token_id INTEGER,
    pair_id INTEGER,
    token_mint TEXT,
    pair_address TEXT,
    report_title TEXT NOT NULL,
    attention_labels_json TEXT,
    summary_payload_json TEXT,
    report_payload_json TEXT,
    report_text TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE TABLE IF NOT EXISTS printer_operator_review_items (
    id INTEGER PRIMARY KEY,
    operator_review_report_id INTEGER NOT NULL,
    item_scope_label TEXT NOT NULL CHECK (item_scope_label IN ('REPORT_DB_STATE', 'REPORT_SYSTEM_HEALTH', 'REPORT_SOURCE_HEALTH', 'REPORT_SCHEDULER_HEALTH', 'REPORT_LIFECYCLE_QUEUE', 'REPORT_DISCOVERY', 'REPORT_TOKEN_SNAPSHOTS', 'REPORT_CONTEXT_ENGINES', 'REPORT_MEMORY', 'REPORT_MEMORY_RETRIEVAL', 'REPORT_PAPER_DECISIONS', 'REPORT_PAPER_POSITIONS', 'REPORT_PAPER_AUDITS', 'REPORT_FULL_OPERATOR_REVIEW', 'REPORT_UNKNOWN_SCOPE')),
    operator_review_label TEXT NOT NULL CHECK (operator_review_label IN ('OPERATOR_REVIEW_OK', 'OPERATOR_REVIEW_NEEDS_ATTENTION', 'OPERATOR_REVIEW_BLOCKED', 'OPERATOR_REVIEW_AUDIT_ONLY', 'OPERATOR_REVIEW_NO_DB', 'OPERATOR_REVIEW_SCHEMA_ONLY', 'OPERATOR_REVIEW_NO_DATA', 'OPERATOR_REVIEW_UNKNOWN')),
    attention_label TEXT NOT NULL CHECK (attention_label IN ('ATTENTION_NONE', 'ATTENTION_NO_PERSISTENT_DB', 'ATTENTION_SCHEMA_ONLY_DB', 'ATTENTION_SOURCE_FAILURES', 'ATTENTION_SCHEDULER_BACKLOG', 'ATTENTION_STALE_SNAPSHOTS', 'ATTENTION_BROKEN_MEMORY_WINDOWS', 'ATTENTION_DIRTY_MEMORY', 'ATTENTION_NO_CLEAN_MEMORY', 'ATTENTION_BLOCKED_PAPER_DECISIONS', 'ATTENTION_OPEN_PAPER_POSITION', 'ATTENTION_PAPER_EXIT_RISK', 'ATTENTION_PAPER_AUDIT_FAILURE', 'ATTENTION_DATA_QUALITY_ISSUE', 'ATTENTION_UNKNOWN')),
    token_id INTEGER,
    pair_id INTEGER,
    related_table TEXT,
    related_row_id INTEGER,
    item_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (operator_review_report_id) REFERENCES printer_operator_review_reports(id),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_operator_review_reports_scope ON printer_operator_review_reports(report_scope_label);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_reports_status ON printer_operator_review_reports(report_status_label);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_reports_review ON printer_operator_review_reports(operator_review_label);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_reports_format ON printer_operator_review_reports(report_format_label);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_reports_generated ON printer_operator_review_reports(generated_at);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_reports_db_state ON printer_operator_review_reports(db_state_classification);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_reports_token_id ON printer_operator_review_reports(token_id);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_reports_pair_id ON printer_operator_review_reports(pair_id);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_reports_token_mint ON printer_operator_review_reports(token_mint);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_reports_pair_address ON printer_operator_review_reports(pair_address);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_reports_created ON printer_operator_review_reports(created_at);

CREATE INDEX IF NOT EXISTS idx_printer_operator_review_items_report_id ON printer_operator_review_items(operator_review_report_id);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_items_attention ON printer_operator_review_items(attention_label);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_items_related ON printer_operator_review_items(related_table, related_row_id);
CREATE INDEX IF NOT EXISTS idx_printer_operator_review_items_created ON printer_operator_review_items(created_at);
