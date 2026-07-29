-- V2-9.8B post-foundation candidate-acquisition integration.
-- Acquisition-only supervision and work; no campaign, tracking, lifecycle,
-- memory, retrieval, decision, position, trade, audit, or PnL authority.

BEGIN IMMEDIATE;

CREATE TABLE printer_candidate_acquisition_integrations (
    integration_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL CHECK (mode IN ('ACQUISITION_ONLY_N2', 'ACQUISITION_ONLY_N7')),
    selection_capacity INTEGER NOT NULL CHECK (
        (mode = 'ACQUISITION_ONLY_N2' AND selection_capacity = 2) OR
        (mode = 'ACQUISITION_ONLY_N7' AND selection_capacity = 7)
    ),
    owner_id TEXT NOT NULL,
    authorization_confirmed INTEGER NOT NULL CHECK (authorization_confirmed = 1),
    preflight_hash TEXT NOT NULL CHECK (length(preflight_hash) = 64),
    policy_json TEXT NOT NULL CHECK (json_valid(policy_json) = 1),
    integration_state TEXT NOT NULL CHECK (
        integration_state IN ('AUTHORIZED', 'RUNNING', 'STOPPING', 'TERMINAL')
    ),
    terminal_status TEXT CHECK (
        terminal_status IS NULL OR terminal_status IN ('COMPLETED', 'BLOCKED', 'FAILED', 'CANCELLED')
    ),
    first_terminal_cause TEXT,
    foundation_execution_id TEXT,
    manifest_id TEXT,
    projection_count INTEGER NOT NULL DEFAULT 0 CHECK (
        projection_count IN (0, 2) AND
        (projection_count = 0 OR mode = 'ACQUISITION_ONLY_N2')
    ),
    runtime_handoff_count INTEGER NOT NULL DEFAULT 0 CHECK (runtime_handoff_count = 0),
    scheduler_jobs_created INTEGER NOT NULL DEFAULT 0 CHECK (scheduler_jobs_created >= 0),
    governed_requests_used INTEGER NOT NULL DEFAULT 0 CHECK (governed_requests_used >= 0),
    transport_operations_used INTEGER NOT NULL DEFAULT 0 CHECK (transport_operations_used >= 0),
    bytes_used INTEGER NOT NULL DEFAULT 0 CHECK (bytes_used >= 0),
    rows_used INTEGER NOT NULL DEFAULT 0 CHECK (rows_used >= 0),
    started_at TEXT NOT NULL,
    terminal_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (length(trim(owner_id)) > 0),
    CHECK (
        (integration_state <> 'TERMINAL' AND terminal_status IS NULL
            AND first_terminal_cause IS NULL AND terminal_at IS NULL)
        OR
        (integration_state = 'TERMINAL' AND terminal_status IS NOT NULL
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0 AND terminal_at IS NOT NULL)
    ),
    FOREIGN KEY (foundation_execution_id)
        REFERENCES printer_candidate_acquisition_executions(execution_id),
    FOREIGN KEY (manifest_id) REFERENCES printer_candidate_manifests(manifest_id)
);

CREATE TABLE printer_candidate_acquisition_leases (
    lease_id TEXT PRIMARY KEY,
    integration_id TEXT NOT NULL UNIQUE,
    execution_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('ACQUISITION_ONLY_N2', 'ACQUISITION_ONLY_N7')),
    lease_state TEXT NOT NULL CHECK (lease_state IN ('ACTIVE', 'STOPPING', 'TERMINAL')),
    heartbeat_at TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    cancellation_requested_at TEXT,
    cancellation_reason TEXT,
    terminal_status TEXT CHECK (
        terminal_status IS NULL OR terminal_status IN ('COMPLETED', 'BLOCKED', 'FAILED', 'CANCELLED')
    ),
    first_terminal_cause TEXT,
    released_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (integration_id)
        REFERENCES printer_candidate_acquisition_integrations(integration_id),
    CHECK (
        (lease_state IN ('ACTIVE', 'STOPPING') AND terminal_status IS NULL
            AND first_terminal_cause IS NULL AND released_at IS NULL)
        OR
        (lease_state = 'TERMINAL' AND terminal_status IS NOT NULL
            AND first_terminal_cause IS NOT NULL AND released_at IS NOT NULL)
    ),
    CHECK (
        (cancellation_requested_at IS NULL AND cancellation_reason IS NULL)
        OR
        (cancellation_requested_at IS NOT NULL AND cancellation_reason IS NOT NULL
            AND length(trim(cancellation_reason)) > 0)
    )
);

CREATE UNIQUE INDEX printer_candidate_acquisition_one_active_lease
    ON printer_candidate_acquisition_leases((1))
    WHERE lease_state IN ('ACTIVE', 'STOPPING');

CREATE TABLE printer_candidate_acquisition_work (
    work_id TEXT PRIMARY KEY,
    integration_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    work_ordinal INTEGER NOT NULL CHECK (work_ordinal >= 1),
    source_name TEXT NOT NULL,
    request_kind TEXT NOT NULL,
    required_source INTEGER NOT NULL CHECK (required_source IN (0, 1)),
    round_mode TEXT NOT NULL CHECK (round_mode IN ('FROZEN_OFFLINE', 'LIVE_TAIL', 'BACKFILL')),
    work_state TEXT NOT NULL CHECK (
        work_state IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED')
    ),
    scheduler_job_id INTEGER NOT NULL,
    source_request_id INTEGER NOT NULL,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    governed_requests_used INTEGER NOT NULL CHECK (governed_requests_used >= 0),
    transport_operations_used INTEGER NOT NULL CHECK (transport_operations_used >= 0),
    bytes_used INTEGER NOT NULL CHECK (bytes_used >= 0),
    rows_used INTEGER NOT NULL CHECK (rows_used >= 0),
    duration_milliseconds INTEGER NOT NULL CHECK (duration_milliseconds >= 0),
    cursor_range_json TEXT CHECK (
        cursor_range_json IS NULL OR json_valid(cursor_range_json) = 1
    ),
    first_terminal_cause TEXT,
    terminal_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (integration_id, work_ordinal),
    UNIQUE (scheduler_job_id),
    UNIQUE (source_request_id),
    CHECK (source_response_id IS NULL OR source_failure_id IS NULL),
    CHECK (
        (work_state IN ('PENDING', 'RUNNING') AND first_terminal_cause IS NULL AND terminal_at IS NULL)
        OR
        (work_state IN ('SUCCEEDED', 'FAILED', 'CANCELLED')
            AND first_terminal_cause IS NOT NULL AND terminal_at IS NOT NULL)
    ),
    FOREIGN KEY (integration_id)
        REFERENCES printer_candidate_acquisition_integrations(integration_id),
    FOREIGN KEY (scheduler_job_id) REFERENCES printer_scheduler_jobs(id),
    FOREIGN KEY (source_request_id) REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id) REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id) REFERENCES printer_source_failures(id)
);

CREATE TABLE printer_candidate_acquisition_transport_operations (
    operation_id TEXT PRIMARY KEY,
    work_id TEXT NOT NULL,
    operation_ordinal INTEGER NOT NULL CHECK (operation_ordinal >= 1),
    source_name TEXT NOT NULL,
    request_kind TEXT NOT NULL,
    operation_kind TEXT NOT NULL,
    operation_state TEXT NOT NULL CHECK (operation_state IN ('COMPLETE', 'FAILED')),
    redacted_endpoint_role TEXT NOT NULL,
    bytes_used INTEGER NOT NULL CHECK (bytes_used >= 0),
    created_at TEXT NOT NULL,
    UNIQUE (work_id, operation_ordinal),
    FOREIGN KEY (work_id) REFERENCES printer_candidate_acquisition_work(work_id)
);

CREATE TABLE printer_candidate_acquisition_cursors (
    network TEXT NOT NULL CHECK (network = 'solana-mainnet'),
    indexed_address TEXT NOT NULL,
    contract_pin TEXT NOT NULL,
    decoder_version TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('FORWARD', 'BACKWARD')),
    boundary_slot INTEGER,
    boundary_signature TEXT,
    last_range_id TEXT NOT NULL,
    last_execution_id TEXT NOT NULL,
    cursor_version INTEGER NOT NULL CHECK (cursor_version >= 1),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (network, indexed_address, contract_pin, decoder_version, direction),
    FOREIGN KEY (last_range_id) REFERENCES printer_candidate_cursor_ranges(range_id),
    FOREIGN KEY (last_execution_id)
        REFERENCES printer_candidate_acquisition_executions(execution_id)
);

CREATE TABLE printer_candidate_acquisition_integration_reports (
    integration_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL CHECK (mode IN ('ACQUISITION_ONLY_N2', 'ACQUISITION_ONLY_N7')),
    manifest_id TEXT,
    report_json TEXT NOT NULL CHECK (json_valid(report_json) = 1),
    report_hash TEXT NOT NULL UNIQUE CHECK (length(report_hash) = 64),
    replay_identity TEXT NOT NULL UNIQUE CHECK (length(replay_identity) = 64),
    reliability_claim_status TEXT NOT NULL CHECK (
        reliability_claim_status = 'UNPROVEN_NO_INDEPENDENT_SAMPLE'
    ),
    created_at TEXT NOT NULL,
    FOREIGN KEY (integration_id)
        REFERENCES printer_candidate_acquisition_integrations(integration_id),
    FOREIGN KEY (manifest_id) REFERENCES printer_candidate_manifests(manifest_id)
);

CREATE TRIGGER printer_candidate_integration_identity_immutable
BEFORE UPDATE OF integration_id, execution_id, mode, selection_capacity, owner_id,
    authorization_confirmed, preflight_hash, policy_json, started_at, created_at
ON printer_candidate_acquisition_integrations
BEGIN SELECT RAISE(ABORT, 'candidate acquisition integration identity is immutable'); END;

CREATE TRIGGER printer_candidate_integration_terminal_immutable
BEFORE UPDATE ON printer_candidate_acquisition_integrations
WHEN OLD.integration_state = 'TERMINAL'
BEGIN SELECT RAISE(ABORT, 'candidate acquisition integration terminal state is immutable'); END;

CREATE TRIGGER printer_candidate_lease_identity_immutable
BEFORE UPDATE OF lease_id, integration_id, execution_id, owner_id, mode, created_at
ON printer_candidate_acquisition_leases
BEGIN SELECT RAISE(ABORT, 'candidate acquisition lease identity is immutable'); END;

CREATE TRIGGER printer_candidate_lease_terminal_immutable
BEFORE UPDATE ON printer_candidate_acquisition_leases
WHEN OLD.lease_state = 'TERMINAL'
BEGIN SELECT RAISE(ABORT, 'candidate acquisition lease terminal state is immutable'); END;

CREATE TRIGGER printer_candidate_work_update_block
BEFORE UPDATE
ON printer_candidate_acquisition_work
BEGIN SELECT RAISE(ABORT, 'candidate acquisition work is immutable'); END;

CREATE TRIGGER printer_candidate_work_delete_block
BEFORE DELETE ON printer_candidate_acquisition_work
BEGIN SELECT RAISE(ABORT, 'candidate acquisition work is immutable'); END;

CREATE TRIGGER printer_candidate_transport_operation_update_block
BEFORE UPDATE ON printer_candidate_acquisition_transport_operations
BEGIN SELECT RAISE(ABORT, 'candidate acquisition transport operation is immutable'); END;

CREATE TRIGGER printer_candidate_transport_operation_delete_block
BEFORE DELETE ON printer_candidate_acquisition_transport_operations
BEGIN SELECT RAISE(ABORT, 'candidate acquisition transport operation is immutable'); END;

CREATE TRIGGER printer_candidate_integration_report_update_block
BEFORE UPDATE ON printer_candidate_acquisition_integration_reports
BEGIN SELECT RAISE(ABORT, 'candidate acquisition integration report is immutable'); END;

CREATE TRIGGER printer_candidate_integration_report_delete_block
BEFORE DELETE ON printer_candidate_acquisition_integration_reports
BEGIN SELECT RAISE(ABORT, 'candidate acquisition integration report is immutable'); END;

COMMIT;
