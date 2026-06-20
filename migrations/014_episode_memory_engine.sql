ALTER TABLE printer_memory_windows ADD COLUMN window_status TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN outcome_label TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN memory_quality_label TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN rejection_reasons_json TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN supporting_context_json TEXT;
ALTER TABLE printer_memory_windows ADD COLUMN created_by_phase TEXT;

ALTER TABLE printer_episodes ADD COLUMN window_kind TEXT;
ALTER TABLE printer_episodes ADD COLUMN episode_outcome_label TEXT;
ALTER TABLE printer_episodes ADD COLUMN memory_quality_label TEXT;
ALTER TABLE printer_episodes ADD COLUMN action_lesson_label TEXT;
ALTER TABLE printer_episodes ADD COLUMN rejection_reasons_json TEXT;
ALTER TABLE printer_episodes ADD COLUMN episode_summary_json TEXT;
ALTER TABLE printer_episodes ADD COLUMN supporting_context_json TEXT;

CREATE TABLE IF NOT EXISTS printer_episode_outcomes (
    id INTEGER PRIMARY KEY,
    episode_id INTEGER,
    memory_window_id INTEGER,
    token_id INTEGER,
    pair_id INTEGER,
    window_kind TEXT,
    outcome_label TEXT NOT NULL,
    action_lesson_label TEXT NOT NULL,
    price_start REAL,
    price_high REAL,
    price_low REAL,
    price_end REAL,
    price_change_percent REAL,
    max_runup_percent REAL,
    max_drawdown_percent REAL,
    realistic_entry_available INTEGER NOT NULL DEFAULT 0 CHECK (realistic_entry_available IN (0, 1)),
    realistic_exit_available INTEGER NOT NULL DEFAULT 0 CHECK (realistic_exit_available IN (0, 1)),
    realistic_profit_possible INTEGER NOT NULL DEFAULT 0 CHECK (realistic_profit_possible IN (0, 1)),
    capital_protection_possible INTEGER NOT NULL DEFAULT 0 CHECK (capital_protection_possible IN (0, 1)),
    memory_quality_label TEXT NOT NULL,
    rejection_reasons_json TEXT,
    outcome_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (episode_id) REFERENCES printer_episodes(id),
    FOREIGN KEY (memory_window_id) REFERENCES printer_memory_windows(id),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE TABLE IF NOT EXISTS printer_memory_audit_reports (
    id INTEGER PRIMARY KEY,
    episode_id INTEGER,
    memory_window_id INTEGER,
    token_id INTEGER,
    pair_id INTEGER,
    audit_status TEXT NOT NULL,
    memory_quality_label TEXT NOT NULL,
    rejection_reasons_json TEXT,
    audit_payload_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (episode_id) REFERENCES printer_episodes(id),
    FOREIGN KEY (memory_window_id) REFERENCES printer_memory_windows(id),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id)
);

CREATE INDEX IF NOT EXISTS idx_printer_episode_outcomes_episode_id ON printer_episode_outcomes(episode_id);
CREATE INDEX IF NOT EXISTS idx_printer_episode_outcomes_window_id ON printer_episode_outcomes(memory_window_id);
CREATE INDEX IF NOT EXISTS idx_printer_episode_outcomes_token_id ON printer_episode_outcomes(token_id);
CREATE INDEX IF NOT EXISTS idx_printer_episode_outcomes_pair_id ON printer_episode_outcomes(pair_id);
CREATE INDEX IF NOT EXISTS idx_printer_episode_outcomes_window_kind ON printer_episode_outcomes(window_kind);
CREATE INDEX IF NOT EXISTS idx_printer_episode_outcomes_outcome ON printer_episode_outcomes(outcome_label);
CREATE INDEX IF NOT EXISTS idx_printer_episode_outcomes_quality ON printer_episode_outcomes(memory_quality_label);
CREATE INDEX IF NOT EXISTS idx_printer_episode_outcomes_lesson ON printer_episode_outcomes(action_lesson_label);
CREATE INDEX IF NOT EXISTS idx_printer_episode_outcomes_created ON printer_episode_outcomes(created_at);

CREATE INDEX IF NOT EXISTS idx_printer_memory_audit_reports_episode_id ON printer_memory_audit_reports(episode_id);
CREATE INDEX IF NOT EXISTS idx_printer_memory_audit_reports_window_id ON printer_memory_audit_reports(memory_window_id);
CREATE INDEX IF NOT EXISTS idx_printer_memory_audit_reports_token_id ON printer_memory_audit_reports(token_id);
CREATE INDEX IF NOT EXISTS idx_printer_memory_audit_reports_pair_id ON printer_memory_audit_reports(pair_id);
CREATE INDEX IF NOT EXISTS idx_printer_memory_audit_reports_quality ON printer_memory_audit_reports(memory_quality_label);
CREATE INDEX IF NOT EXISTS idx_printer_memory_audit_reports_created ON printer_memory_audit_reports(created_at);

CREATE INDEX IF NOT EXISTS idx_printer_memory_windows_opened_at ON printer_memory_windows(opened_at);
CREATE INDEX IF NOT EXISTS idx_printer_memory_windows_closed_at ON printer_memory_windows(closed_at);
CREATE INDEX IF NOT EXISTS idx_printer_memory_windows_window_status ON printer_memory_windows(window_status);
CREATE INDEX IF NOT EXISTS idx_printer_memory_windows_quality ON printer_memory_windows(memory_quality_label);
CREATE INDEX IF NOT EXISTS idx_printer_episodes_window_kind ON printer_episodes(window_kind);
CREATE INDEX IF NOT EXISTS idx_printer_episodes_quality ON printer_episodes(memory_quality_label);
CREATE INDEX IF NOT EXISTS idx_printer_episodes_outcome ON printer_episodes(episode_outcome_label);
CREATE INDEX IF NOT EXISTS idx_printer_episodes_lesson ON printer_episodes(action_lesson_label);
