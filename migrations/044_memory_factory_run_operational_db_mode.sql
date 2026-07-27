-- V2-9.8B.10: allow operational-persistent factory-run ledger rows.
--
-- Root cause (execution 20260727T001520Z-d513e21260b5):
-- run_one_command_15m_factory inserts db_mode='OPERATIONAL_PERSISTENT' when
-- operational_persistent_mode is true, but migration 028 only allowed
-- CHECK (db_mode = 'PROOF_ONLY'). Lifecycle entry therefore raised
-- IntegrityError after two-token selection, with zero WINDOW_15M rows.
--
-- Campaign tables already allow OPERATIONAL_PERSISTENT (migration 031).
-- This migration only widens the factory-run ledger to match that lawful mode.
-- No second lifecycle owner. No retrieval/financial unlock.

PRAGMA foreign_keys = OFF;

CREATE TABLE printer_memory_factory_runs__v2_9_8b_10 (
    id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    run_status TEXT NOT NULL,
    stop_reason TEXT,
    window_kind TEXT NOT NULL CHECK (window_kind = 'WINDOW_15M'),
    db_mode TEXT NOT NULL CHECK (
        db_mode IN ('PROOF_ONLY', 'OPERATIONAL_PERSISTENT')
    ),
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

INSERT INTO printer_memory_factory_runs__v2_9_8b_10 (
    id, run_id, run_status, stop_reason, window_kind, db_mode,
    config_hash, config_json, selection_seed, selection_batch_id,
    eligible_pool_size, selected_token_count, started_at, finished_at,
    final_report_json, created_at, updated_at
)
SELECT
    id, run_id, run_status, stop_reason, window_kind, db_mode,
    config_hash, config_json, selection_seed, selection_batch_id,
    eligible_pool_size, selected_token_count, started_at, finished_at,
    final_report_json, created_at, updated_at
FROM printer_memory_factory_runs;

DROP TABLE printer_memory_factory_runs;

ALTER TABLE printer_memory_factory_runs__v2_9_8b_10
    RENAME TO printer_memory_factory_runs;

CREATE INDEX IF NOT EXISTS idx_memory_factory_runs_status
    ON printer_memory_factory_runs(run_status, started_at);

PRAGMA foreign_keys = ON;
