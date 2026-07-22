ALTER TABLE printer_source_failures
ADD COLUMN source_request_id INTEGER REFERENCES printer_source_requests(id);

CREATE INDEX idx_source_failures_request
ON printer_source_failures(source_request_id);

CREATE TABLE printer_holder_campaign_operation_ledgers (
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    operation_ceiling INTEGER NOT NULL CHECK (operation_ceiling = 45),
    governed_requests INTEGER NOT NULL DEFAULT 0 CHECK (governed_requests >= 0),
    underlying_transport_operations INTEGER NOT NULL DEFAULT 0
        CHECK (underlying_transport_operations >= 0),
    zero_transport_operations INTEGER NOT NULL DEFAULT 0
        CHECK (zero_transport_operations >= 0),
    reserved_snapshot_operations INTEGER NOT NULL
        CHECK (reserved_snapshot_operations = 2),
    deadline_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (run_id, cycle_id),
    FOREIGN KEY (run_id) REFERENCES printer_memory_factory_campaign_runs(run_id)
);

CREATE TABLE printer_holder_maturation_work (
    work_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    mint_identity TEXT NOT NULL CHECK (mint_identity = lower(mint_identity)),
    request_purpose TEXT NOT NULL,
    scheduled_for TEXT NOT NULL,
    deadline_at TEXT NOT NULL,
    work_state TEXT NOT NULL CHECK (work_state IN (
        'WAITING', 'DUE', 'CANCELLED', 'DEADLINE_REFUSED', 'COMPLETED'
    )),
    maturation_threshold_state TEXT NOT NULL CHECK (
        maturation_threshold_state IN ('UNPROVEN_DISABLED', 'EVIDENCE_BACKED')
    ),
    first_terminal_cause TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (run_id, cycle_id, mint_identity, request_purpose),
    FOREIGN KEY (run_id, cycle_id)
        REFERENCES printer_holder_campaign_operation_ledgers(run_id, cycle_id)
);

CREATE TABLE printer_holder_evidence_attempts (
    evidence_id INTEGER PRIMARY KEY,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    mint_identity TEXT NOT NULL CHECK (mint_identity = lower(mint_identity)),
    request_purpose TEXT NOT NULL,
    source_name TEXT NOT NULL,
    endpoint_role TEXT NOT NULL,
    redacted_host TEXT NOT NULL,
    source_request_id INTEGER,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    lineage_response_id INTEGER,
    reused_evidence_id INTEGER,
    captured_at TEXT,
    received_at TEXT,
    parser_version TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    source_status TEXT NOT NULL,
    data_quality_label TEXT NOT NULL,
    exact_target INTEGER NOT NULL CHECK (exact_target IN (0, 1)),
    holder_concentration_label TEXT,
    rpc_method TEXT,
    commitment TEXT,
    context_slot INTEGER,
    underlying_operation_count INTEGER NOT NULL
        CHECK (underlying_operation_count >= 0),
    failure_subtype TEXT,
    retry_after_at TEXT,
    created_at TEXT NOT NULL,
    CHECK (source_response_id IS NULL OR source_failure_id IS NULL),
    CHECK (reused_evidence_id IS NULL OR underlying_operation_count = 0),
    FOREIGN KEY (run_id, cycle_id)
        REFERENCES printer_holder_campaign_operation_ledgers(run_id, cycle_id),
    FOREIGN KEY (source_request_id) REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id) REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id) REFERENCES printer_source_failures(id),
    FOREIGN KEY (lineage_response_id) REFERENCES printer_source_responses(id),
    FOREIGN KEY (reused_evidence_id) REFERENCES printer_holder_evidence_attempts(evidence_id)
);

CREATE INDEX idx_holder_evidence_reuse
ON printer_holder_evidence_attempts(
    mint_identity, request_purpose, source_name, endpoint_role,
    parser_version, policy_version, received_at
);
