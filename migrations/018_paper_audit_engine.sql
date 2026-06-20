CREATE TABLE IF NOT EXISTS printer_paper_audit_reports (
    id INTEGER PRIMARY KEY,
    paper_position_id INTEGER,
    paper_decision_id INTEGER,
    retrieval_query_id INTEGER,
    token_id INTEGER,
    pair_id INTEGER,
    token_mint TEXT,
    pair_address TEXT,
    audit_at TEXT NOT NULL,
    audit_scope_label TEXT NOT NULL CHECK (audit_scope_label IN ('AUDIT_PAPER_DECISION', 'AUDIT_PAPER_ENTRY', 'AUDIT_PAPER_MONITORING', 'AUDIT_PAPER_EXIT', 'AUDIT_PAPER_PNL', 'AUDIT_RULE_COMPLIANCE', 'AUDIT_FULL_PAPER_TRADE', 'AUDIT_UNKNOWN_SCOPE')),
    paper_audit_result_label TEXT NOT NULL CHECK (paper_audit_result_label IN ('PAPER_AUDIT_PASS', 'PAPER_AUDIT_PASS_WITH_WARNINGS', 'PAPER_AUDIT_FAIL', 'PAPER_AUDIT_INCOMPLETE', 'PAPER_AUDIT_AUDIT_ONLY', 'PAPER_AUDIT_UNKNOWN')),
    paper_rule_compliance_label TEXT NOT NULL CHECK (paper_rule_compliance_label IN ('RULES_COMPLIANT', 'RULES_COMPLIANT_WITH_WARNINGS', 'RULES_VIOLATION', 'RULES_INCOMPLETE_EVIDENCE', 'RULES_UNKNOWN')),
    paper_realism_label TEXT NOT NULL CHECK (paper_realism_label IN ('PAPER_REALISM_CLEAN', 'PAPER_REALISM_ACCEPTABLE', 'PAPER_REALISM_WEAK', 'PAPER_REALISM_UNREALISTIC', 'PAPER_REALISM_UNKNOWN')),
    paper_outcome_review_label TEXT NOT NULL CHECK (paper_outcome_review_label IN ('PAPER_OUTCOME_WORKED', 'PAPER_OUTCOME_FAILED', 'PAPER_OUTCOME_PROTECTED_CAPITAL', 'PAPER_OUTCOME_MISSED_UPSIDE', 'PAPER_OUTCOME_NO_ACTION_VALID', 'PAPER_OUTCOME_INCONCLUSIVE', 'PAPER_OUTCOME_UNKNOWN')),
    paper_data_quality_audit_label TEXT NOT NULL CHECK (paper_data_quality_audit_label IN ('PAPER_AUDIT_DATA_CLEAN', 'PAPER_AUDIT_DATA_PARTIAL', 'PAPER_AUDIT_DATA_STALE', 'PAPER_AUDIT_DATA_CONFLICTING', 'PAPER_AUDIT_DATA_MISSING', 'PAPER_AUDIT_DATA_UNKNOWN')),
    audit_issues_json TEXT,
    decision_audit_json TEXT,
    entry_audit_json TEXT,
    monitoring_audit_json TEXT,
    exit_audit_json TEXT,
    pnl_audit_json TEXT,
    rule_compliance_json TEXT,
    audit_report_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (paper_position_id) REFERENCES printer_paper_positions(id),
    FOREIGN KEY (paper_decision_id) REFERENCES printer_paper_decisions(id),
    FOREIGN KEY (retrieval_query_id) REFERENCES printer_memory_retrieval_queries(id),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_position_id ON printer_paper_audit_reports(paper_position_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_decision_id ON printer_paper_audit_reports(paper_decision_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_retrieval_query ON printer_paper_audit_reports(retrieval_query_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_token_id ON printer_paper_audit_reports(token_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_pair_id ON printer_paper_audit_reports(pair_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_token_mint ON printer_paper_audit_reports(token_mint);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_pair_address ON printer_paper_audit_reports(pair_address);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_audit_at ON printer_paper_audit_reports(audit_at);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_scope ON printer_paper_audit_reports(audit_scope_label);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_result ON printer_paper_audit_reports(paper_audit_result_label);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_rules ON printer_paper_audit_reports(paper_rule_compliance_label);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_realism ON printer_paper_audit_reports(paper_realism_label);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_outcome ON printer_paper_audit_reports(paper_outcome_review_label);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_data ON printer_paper_audit_reports(paper_data_quality_audit_label);
CREATE INDEX IF NOT EXISTS idx_printer_paper_audit_reports_created ON printer_paper_audit_reports(created_at);
