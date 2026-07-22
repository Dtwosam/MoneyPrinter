CREATE TABLE printer_external_source_operations (
    operation_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    operation_ordinal INTEGER NOT NULL CHECK (operation_ordinal > 0),
    source_name TEXT NOT NULL,
    request_purpose TEXT NOT NULL,
    endpoint_role TEXT NOT NULL,
    redacted_host TEXT NOT NULL,
    rpc_method TEXT NOT NULL,
    commitment TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    operation_state TEXT NOT NULL CHECK (
        operation_state IN ('STARTED', 'COMPLETE', 'FAILED')
    ),
    failure_subtype TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (run_id, cycle_id, operation_ordinal),
    FOREIGN KEY (run_id) REFERENCES printer_memory_factory_campaign_runs(run_id)
);

CREATE INDEX idx_external_source_operations_replay
ON printer_external_source_operations(run_id, cycle_id, operation_ordinal);
