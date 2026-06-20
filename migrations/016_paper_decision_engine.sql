ALTER TABLE printer_paper_decisions ADD COLUMN decided_at TEXT;
ALTER TABLE printer_paper_decisions ADD COLUMN token_mint TEXT;
ALTER TABLE printer_paper_decisions ADD COLUMN pair_address TEXT;
ALTER TABLE printer_paper_decisions ADD COLUMN requested_action_label TEXT CHECK (requested_action_label IN ('BUY', 'SELL', 'HOLD', 'WAIT', 'AVOID', 'NO_ACTION'));
ALTER TABLE printer_paper_decisions ADD COLUMN final_action_label TEXT CHECK (final_action_label IN ('BUY', 'SELL', 'HOLD', 'WAIT', 'AVOID', 'NO_ACTION'));
ALTER TABLE printer_paper_decisions ADD COLUMN decision_gate_label TEXT CHECK (decision_gate_label IN ('DECISION_ALLOWED', 'DECISION_BLOCKED_NO_CLEAN_MEMORY', 'DECISION_BLOCKED_DIRTY_CURRENT_CONTEXT', 'DECISION_BLOCKED_UNSAFE_TOKEN', 'DECISION_BLOCKED_UNREALISTIC_EXIT', 'DECISION_BLOCKED_NO_ROUTE', 'DECISION_BLOCKED_STALE_DATA', 'DECISION_BLOCKED_CONFLICTING_DATA', 'DECISION_BLOCKED_INSUFFICIENT_EVIDENCE', 'DECISION_AUDIT_ONLY'));
ALTER TABLE printer_paper_decisions ADD COLUMN memory_evidence_gate_label TEXT CHECK (memory_evidence_gate_label IN ('MEMORY_GATE_CLEAN_MATCH', 'MEMORY_GATE_MIXED_MATCH', 'MEMORY_GATE_WEAK_MATCH', 'MEMORY_GATE_NO_MATCH', 'MEMORY_GATE_DIRTY_ONLY', 'MEMORY_GATE_BLOCKED'));
ALTER TABLE printer_paper_decisions ADD COLUMN paper_decision_status_label TEXT CHECK (paper_decision_status_label IN ('PAPER_DECISION_PROPOSED', 'PAPER_DECISION_BLOCKED', 'PAPER_DECISION_AUDIT_ONLY', 'PAPER_DECISION_EXPIRED', 'PAPER_DECISION_SUPERSEDED'));
ALTER TABLE printer_paper_decisions ADD COLUMN retrieval_query_id INTEGER REFERENCES printer_memory_retrieval_queries(id);
ALTER TABLE printer_paper_decisions ADD COLUMN matched_episode_ids_json TEXT;
ALTER TABLE printer_paper_decisions ADD COLUMN supporting_memory_match_ids_json TEXT;
ALTER TABLE printer_paper_decisions ADD COLUMN decision_reasons_json TEXT;
ALTER TABLE printer_paper_decisions ADD COLUMN blocking_reasons_json TEXT;
ALTER TABLE printer_paper_decisions ADD COLUMN current_context_json TEXT;
ALTER TABLE printer_paper_decisions ADD COLUMN memory_evidence_summary_json TEXT;
ALTER TABLE printer_paper_decisions ADD COLUMN decision_report_json TEXT;
ALTER TABLE printer_paper_decisions ADD COLUMN expires_at TEXT;

CREATE TABLE IF NOT EXISTS printer_paper_decision_audits (
    id INTEGER PRIMARY KEY,
    paper_decision_id INTEGER NOT NULL,
    token_id INTEGER,
    pair_id INTEGER,
    audit_label TEXT NOT NULL,
    audit_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (paper_decision_id) REFERENCES printer_paper_decisions(id),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_token_id ON printer_paper_decisions(token_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_pair_id ON printer_paper_decisions(pair_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_token_mint ON printer_paper_decisions(token_mint);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_pair_address ON printer_paper_decisions(pair_address);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_decided_at ON printer_paper_decisions(decided_at);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_requested_action ON printer_paper_decisions(requested_action_label);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_final_action ON printer_paper_decisions(final_action_label);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_gate ON printer_paper_decisions(decision_gate_label);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_memory_gate ON printer_paper_decisions(memory_evidence_gate_label);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_status_label ON printer_paper_decisions(paper_decision_status_label);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_retrieval_query ON printer_paper_decisions(retrieval_query_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decisions_created ON printer_paper_decisions(created_at);

CREATE INDEX IF NOT EXISTS idx_printer_paper_decision_audits_decision_id ON printer_paper_decision_audits(paper_decision_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decision_audits_token_id ON printer_paper_decision_audits(token_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decision_audits_pair_id ON printer_paper_decision_audits(pair_id);
CREATE INDEX IF NOT EXISTS idx_printer_paper_decision_audits_created ON printer_paper_decision_audits(created_at);
