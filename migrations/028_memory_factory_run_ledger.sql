-- V2-4: durable one-command WINDOW_15M orchestration ledger.
-- These tables coordinate existing governed components only.

CREATE TABLE IF NOT EXISTS printer_memory_factory_runs (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    run_status TEXT NOT NULL,
    stop_reason TEXT,
    window_kind TEXT NOT NULL CHECK (window_kind = 'WINDOW_15M'),
    db_mode TEXT NOT NULL CHECK (db_mode = 'PROOF_ONLY'),
    config_hash TEXT NOT NULL,
    config_json TEXT NOT NULL,
    selection_seed TEXT,
    selection_batch_id TEXT,
    eligible_pool_size INTEGER,
    selected_token_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    final_report_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS printer_memory_factory_run_steps (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_key TEXT NOT NULL,
    step_kind TEXT NOT NULL,
    step_status TEXT NOT NULL,
    token_id INTEGER,
    pair_id INTEGER,
    token_mint TEXT,
    pair_address TEXT,
    tracking_lane TEXT,
    scheduled_for TEXT,
    scheduler_job_id INTEGER,
    source_request_id INTEGER,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    snapshot_id INTEGER,
    memory_window_id INTEGER,
    result_json TEXT,
    error_or_skip_reason TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (run_id, step_key),
    FOREIGN KEY (run_id) REFERENCES printer_memory_factory_runs(run_id),
    FOREIGN KEY (token_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_id) REFERENCES printer_pairs(id),
    FOREIGN KEY (scheduler_job_id) REFERENCES printer_scheduler_jobs(id),
    FOREIGN KEY (source_request_id) REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id) REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id) REFERENCES printer_source_failures(id),
    FOREIGN KEY (snapshot_id) REFERENCES printer_token_snapshots(id),
    FOREIGN KEY (memory_window_id) REFERENCES printer_memory_windows(id)
);

CREATE INDEX IF NOT EXISTS idx_memory_factory_runs_status
    ON printer_memory_factory_runs(run_status, started_at);
CREATE INDEX IF NOT EXISTS idx_memory_factory_steps_run_status
    ON printer_memory_factory_run_steps(run_id, step_status, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_memory_factory_steps_job
    ON printer_memory_factory_run_steps(scheduler_job_id);
