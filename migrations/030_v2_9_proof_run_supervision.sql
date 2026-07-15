-- V2-9.4: durable, proof-only host-process supervision.
-- This ledger coordinates one bounded V2-9 proof. It does not schedule work.

CREATE TABLE IF NOT EXISTS printer_proof_run_supervision (
    id INTEGER PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    proof_scope TEXT NOT NULL CHECK (proof_scope = 'V2_9'),
    owner_launcher_type TEXT NOT NULL CHECK (
        owner_launcher_type IN ('MANUAL_POWERSHELL', 'TEST_FIXTURE')
    ),
    process_id INTEGER CHECK (process_id IS NULL OR process_id > 0),
    run_id TEXT UNIQUE,
    execution_status TEXT NOT NULL CHECK (
        execution_status IN ('STARTING', 'RUNNING', 'TERMINAL')
    ),
    terminal_status TEXT CHECK (
        terminal_status IS NULL OR terminal_status IN (
            'COMPLETED',
            'GOVERNED_SAFE_STOP',
            'OPERATOR_CANCELLED',
            'SOURCE_FAILURE',
            'BUDGET_STOP',
            'HOST_PROCESS_DISAPPEARED'
        )
    ),
    first_stop_reason TEXT,
    heartbeat_at TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    proof_db_path TEXT NOT NULL,
    backup_db_path TEXT NOT NULL,
    one_proof_lock_path TEXT NOT NULL,
    stdout_log_path TEXT NOT NULL,
    stderr_log_path TEXT NOT NULL,
    recovery_report_json TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (
        (execution_status IN ('STARTING', 'RUNNING')
            AND terminal_status IS NULL
            AND first_stop_reason IS NULL
            AND finished_at IS NULL)
        OR
        (execution_status = 'TERMINAL'
            AND terminal_status IS NOT NULL
            AND first_stop_reason IS NOT NULL
            AND finished_at IS NOT NULL)
    ),
    FOREIGN KEY (run_id) REFERENCES printer_memory_factory_runs(run_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_proof_supervision_one_active_scope
    ON printer_proof_run_supervision(proof_scope)
    WHERE execution_status IN ('STARTING', 'RUNNING');

CREATE INDEX IF NOT EXISTS idx_proof_supervision_lease
    ON printer_proof_run_supervision(execution_status, lease_expires_at);

CREATE INDEX IF NOT EXISTS idx_proof_supervision_run
    ON printer_proof_run_supervision(run_id);
