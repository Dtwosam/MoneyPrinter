CREATE TABLE IF NOT EXISTS printer_validation_runs (
    id INTEGER PRIMARY KEY,
    validation_scope_label TEXT NOT NULL CHECK (validation_scope_label IN ('VALIDATION_SCHEMA', 'VALIDATION_CONTRACTS', 'VALIDATION_MIGRATIONS', 'VALIDATION_SYNTHETIC_DISCOVERY', 'VALIDATION_SYNTHETIC_SNAPSHOTS', 'VALIDATION_SYNTHETIC_CONTEXT', 'VALIDATION_SYNTHETIC_MEMORY', 'VALIDATION_SYNTHETIC_RETRIEVAL', 'VALIDATION_SYNTHETIC_PAPER_DECISION', 'VALIDATION_SYNTHETIC_PAPER_MONITOR', 'VALIDATION_SYNTHETIC_PAPER_AUDIT', 'VALIDATION_SYNTHETIC_OPERATOR_REPORT', 'VALIDATION_FULL_SYNTHETIC_FLOW', 'VALIDATION_UNKNOWN_SCOPE')),
    validation_result_label TEXT NOT NULL CHECK (validation_result_label IN ('VALIDATION_PASS', 'VALIDATION_PASS_WITH_WARNINGS', 'VALIDATION_FAIL', 'VALIDATION_SKIPPED', 'VALIDATION_INCOMPLETE', 'VALIDATION_UNKNOWN')),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    synthetic_only INTEGER NOT NULL DEFAULT 1 CHECK (synthetic_only IN (0, 1)),
    temp_db_only INTEGER NOT NULL DEFAULT 1 CHECK (temp_db_only IN (0, 1)),
    project_db_created INTEGER NOT NULL DEFAULT 0 CHECK (project_db_created IN (0, 1)),
    validation_summary_json TEXT,
    validation_report_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (validation_scope_label, started_at)
);

CREATE TABLE IF NOT EXISTS printer_validation_items (
    id INTEGER PRIMARY KEY,
    validation_run_id INTEGER NOT NULL,
    validation_scope_label TEXT NOT NULL CHECK (validation_scope_label IN ('VALIDATION_SCHEMA', 'VALIDATION_CONTRACTS', 'VALIDATION_MIGRATIONS', 'VALIDATION_SYNTHETIC_DISCOVERY', 'VALIDATION_SYNTHETIC_SNAPSHOTS', 'VALIDATION_SYNTHETIC_CONTEXT', 'VALIDATION_SYNTHETIC_MEMORY', 'VALIDATION_SYNTHETIC_RETRIEVAL', 'VALIDATION_SYNTHETIC_PAPER_DECISION', 'VALIDATION_SYNTHETIC_PAPER_MONITOR', 'VALIDATION_SYNTHETIC_PAPER_AUDIT', 'VALIDATION_SYNTHETIC_OPERATOR_REPORT', 'VALIDATION_FULL_SYNTHETIC_FLOW', 'VALIDATION_UNKNOWN_SCOPE')),
    validation_result_label TEXT NOT NULL CHECK (validation_result_label IN ('VALIDATION_PASS', 'VALIDATION_PASS_WITH_WARNINGS', 'VALIDATION_FAIL', 'VALIDATION_SKIPPED', 'VALIDATION_INCOMPLETE', 'VALIDATION_UNKNOWN')),
    validation_issue_label TEXT NOT NULL CHECK (validation_issue_label IN ('VALIDATION_ISSUE_NONE', 'VALIDATION_ISSUE_MISSING_TABLE', 'VALIDATION_ISSUE_MISSING_COLUMN', 'VALIDATION_ISSUE_FORBIDDEN_COLUMN', 'VALIDATION_ISSUE_LABEL_MISMATCH', 'VALIDATION_ISSUE_MIGRATION_FAILURE', 'VALIDATION_ISSUE_DIRTY_MEMORY_ALLOWED', 'VALIDATION_ISSUE_DECISION_WITHOUT_CLEAN_MEMORY', 'VALIDATION_ISSUE_POSITION_WITHOUT_VALID_DECISION', 'VALIDATION_ISSUE_LIVE_CAPABILITY_FOUND', 'VALIDATION_ISSUE_RUNTIME_LOOP_FOUND', 'VALIDATION_ISSUE_PROJECT_DB_CREATED_IN_TEST', 'VALIDATION_ISSUE_UNKNOWN')),
    flow_stage_label TEXT NOT NULL CHECK (flow_stage_label IN ('FLOW_STAGE_DB_INIT', 'FLOW_STAGE_DISCOVERY', 'FLOW_STAGE_SNAPSHOTS', 'FLOW_STAGE_CONTEXT', 'FLOW_STAGE_MEMORY', 'FLOW_STAGE_RETRIEVAL', 'FLOW_STAGE_PAPER_DECISION', 'FLOW_STAGE_PAPER_POSITION', 'FLOW_STAGE_PAPER_MONITOR', 'FLOW_STAGE_PAPER_AUDIT', 'FLOW_STAGE_OPERATOR_REVIEW', 'FLOW_STAGE_COMPLETE', 'FLOW_STAGE_UNKNOWN')),
    related_table TEXT,
    related_row_id INTEGER,
    item_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (validation_run_id) REFERENCES printer_validation_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_validation_runs_scope ON printer_validation_runs(validation_scope_label);
CREATE INDEX IF NOT EXISTS idx_printer_validation_runs_result ON printer_validation_runs(validation_result_label);
CREATE INDEX IF NOT EXISTS idx_printer_validation_runs_started ON printer_validation_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_printer_validation_runs_completed ON printer_validation_runs(completed_at);
CREATE INDEX IF NOT EXISTS idx_printer_validation_runs_synthetic ON printer_validation_runs(synthetic_only);
CREATE INDEX IF NOT EXISTS idx_printer_validation_runs_temp_db ON printer_validation_runs(temp_db_only);
CREATE INDEX IF NOT EXISTS idx_printer_validation_runs_project_db ON printer_validation_runs(project_db_created);
CREATE INDEX IF NOT EXISTS idx_printer_validation_runs_created ON printer_validation_runs(created_at);

CREATE INDEX IF NOT EXISTS idx_printer_validation_items_run_id ON printer_validation_items(validation_run_id);
CREATE INDEX IF NOT EXISTS idx_printer_validation_items_scope ON printer_validation_items(validation_scope_label);
CREATE INDEX IF NOT EXISTS idx_printer_validation_items_result ON printer_validation_items(validation_result_label);
CREATE INDEX IF NOT EXISTS idx_printer_validation_items_issue ON printer_validation_items(validation_issue_label);
CREATE INDEX IF NOT EXISTS idx_printer_validation_items_stage ON printer_validation_items(flow_stage_label);
CREATE INDEX IF NOT EXISTS idx_printer_validation_items_related ON printer_validation_items(related_table, related_row_id);
CREATE INDEX IF NOT EXISTS idx_printer_validation_items_created ON printer_validation_items(created_at);
