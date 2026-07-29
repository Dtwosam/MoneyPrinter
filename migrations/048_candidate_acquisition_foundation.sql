-- V2-9.8B factory-wide candidate-acquisition foundation.
--
-- Capacity-neutral only. Active Memory Factory runtime remains exactly two.
-- No retrieval, decision, position, trade, audit, PnL, wallet, signing, score,
-- rank, confidence, weight, embedding, or vector surface is introduced.

-- Repair the migration-046 code/schema mismatch without editing the applied
-- migration or changing any existing row value.
ALTER TABLE printer_discovery_exhaustion_certificates
    RENAME TO printer_discovery_exhaustion_certificates_047_backup;

CREATE TABLE printer_discovery_exhaustion_certificates (
    certificate_id TEXT PRIMARY KEY,
    campaign_id TEXT,
    execution_id TEXT,
    run_id TEXT,
    cycle_id TEXT,
    required_eligible_capacity INTEGER NOT NULL CHECK (required_eligible_capacity >= 1),
    eligible_reserve_count INTEGER NOT NULL CHECK (eligible_reserve_count >= 0),
    shortage_classification TEXT NOT NULL CHECK (
        shortage_classification IN (
            'TRUE_MARKET_SUPPLY_SHORTAGE',
            'SOURCE_VISIBILITY_SHORTAGE',
            'SOURCE_AVAILABILITY_FAILURE',
            'BUDGET_EXHAUSTION',
            'DURATION_EXHAUSTION',
            'STALE_EVIDENCE_SHORTAGE',
            'DISCOVERY_ARCHITECTURE_FALSE_SHORTAGE',
            'TRACKING_STATE_CAPACITY_BLOCKED'
        )
    ),
    certificate_json TEXT NOT NULL,
    certificate_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK (length(trim(certificate_id)) > 0),
    CHECK (length(trim(certificate_json)) > 0)
);

INSERT INTO printer_discovery_exhaustion_certificates(
    certificate_id, campaign_id, execution_id, run_id, cycle_id,
    required_eligible_capacity, eligible_reserve_count,
    shortage_classification, certificate_json, certificate_version, created_at
)
SELECT
    certificate_id, campaign_id, execution_id, run_id, cycle_id,
    required_eligible_capacity, eligible_reserve_count,
    shortage_classification, certificate_json, certificate_version, created_at
FROM printer_discovery_exhaustion_certificates_047_backup;

DROP TABLE printer_discovery_exhaustion_certificates_047_backup;

CREATE INDEX printer_discovery_exhaustion_campaign
    ON printer_discovery_exhaustion_certificates(campaign_id);
CREATE INDEX printer_discovery_exhaustion_class
    ON printer_discovery_exhaustion_certificates(shortage_classification);

CREATE TABLE printer_candidate_acquisition_policies (
    policy_id TEXT PRIMARY KEY,
    policy_hash TEXT NOT NULL UNIQUE,
    schema_version TEXT NOT NULL,
    network TEXT NOT NULL CHECK (network = 'solana-mainnet'),
    selection_capacity INTEGER NOT NULL CHECK (selection_capacity BETWEEN 1 AND 16),
    candidate_acquisition_capacity INTEGER NOT NULL,
    candidate_reserve_target INTEGER NOT NULL,
    approved_active_memory_capacity INTEGER NOT NULL CHECK (approved_active_memory_capacity = 2),
    selection_seed TEXT NOT NULL,
    seed_domain TEXT NOT NULL,
    allowed_sources_json TEXT NOT NULL,
    source_budgets_json TEXT NOT NULL,
    scheduler_owner TEXT NOT NULL CHECK (scheduler_owner = 'Central Scheduler'),
    scheduler_job_kind TEXT NOT NULL CHECK (scheduler_job_kind = 'DISCOVERY_REFRESH'),
    source_governor_required INTEGER NOT NULL CHECK (source_governor_required = 1),
    no_retry INTEGER NOT NULL CHECK (no_retry = 1),
    no_reconnect INTEGER NOT NULL CHECK (no_reconnect = 1),
    git_provenance TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK (candidate_acquisition_capacity = selection_capacity * 2),
    CHECK (candidate_reserve_target = selection_capacity + ((selection_capacity + 1) / 2)),
    CHECK (length(policy_hash) = 64),
    CHECK (length(trim(selection_seed)) > 0),
    CHECK (length(trim(git_provenance)) > 0)
);

CREATE TABLE printer_candidate_acquisition_executions (
    execution_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    replay_identity TEXT NOT NULL UNIQUE,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    cutoff_at TEXT NOT NULL,
    finalized_cutoff_slot INTEGER NOT NULL CHECK (finalized_cutoff_slot >= 0),
    execution_status TEXT NOT NULL CHECK (
        execution_status IN ('COMPLETED_SUCCESS', 'COMPLETED_FAILURE')
    ),
    failure_family TEXT CHECK (
        failure_family IS NULL OR failure_family IN (
            'COVERAGE_FAILURE',
            'SOURCE_PROVIDER_FAILURE',
            'BUDGET_EXHAUSTION',
            'STALE_OR_INCOMPLETE_EVIDENCE',
            'UNSUPPORTED_CONTRACT',
            'IDENTITY_MERGE_FAILURE',
            'ADMISSION_FAILURE',
            'INSUFFICIENT_ELIGIBLE_POOL'
        )
    ),
    observed_unique_count INTEGER NOT NULL CHECK (observed_unique_count >= 0),
    certificate_count INTEGER NOT NULL CHECK (certificate_count >= 0),
    admitted_count INTEGER NOT NULL CHECK (admitted_count >= 0),
    selected_count INTEGER NOT NULL CHECK (selected_count >= 0),
    manifest_id TEXT,
    runtime_handoff_count INTEGER NOT NULL DEFAULT 0 CHECK (runtime_handoff_count = 0),
    created_at TEXT NOT NULL,
    FOREIGN KEY (policy_id) REFERENCES printer_candidate_acquisition_policies(policy_id)
);

CREATE INDEX printer_candidate_execution_policy
    ON printer_candidate_acquisition_executions(policy_id);

CREATE TABLE printer_candidate_source_rounds (
    round_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    round_ordinal INTEGER NOT NULL CHECK (round_ordinal >= 1),
    round_mode TEXT NOT NULL CHECK (
        round_mode IN ('FROZEN_OFFLINE', 'LIVE_TAIL', 'BACKFILL')
    ),
    source_name TEXT NOT NULL,
    request_kind TEXT NOT NULL,
    source_status TEXT NOT NULL,
    failure_reason TEXT,
    governed_requests_used INTEGER NOT NULL CHECK (governed_requests_used >= 0),
    transport_operations_used INTEGER NOT NULL CHECK (transport_operations_used >= 0),
    bytes_used INTEGER NOT NULL CHECK (bytes_used >= 0),
    rows_used INTEGER NOT NULL CHECK (rows_used >= 0),
    duration_milliseconds INTEGER NOT NULL CHECK (duration_milliseconds >= 0),
    scheduler_job_kind TEXT NOT NULL CHECK (scheduler_job_kind = 'DISCOVERY_REFRESH'),
    source_governor_allowed INTEGER NOT NULL CHECK (source_governor_allowed IN (0, 1)),
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (execution_id, round_ordinal),
    CHECK (length(content_hash) = 64),
    FOREIGN KEY (execution_id) REFERENCES printer_candidate_acquisition_executions(execution_id)
);

CREATE TABLE printer_candidate_source_observations (
    observation_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    round_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    request_kind TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    source_status TEXT NOT NULL,
    mint_identity TEXT,
    pool_address TEXT,
    pool_program_id TEXT,
    base_mint TEXT,
    quote_mint TEXT,
    venue_label TEXT,
    lineage_claim TEXT,
    facts_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (execution_id, source_name, content_hash),
    CHECK (length(content_hash) = 64),
    FOREIGN KEY (execution_id) REFERENCES printer_candidate_acquisition_executions(execution_id),
    FOREIGN KEY (round_id) REFERENCES printer_candidate_source_rounds(round_id)
);

CREATE INDEX printer_candidate_observation_mint
    ON printer_candidate_source_observations(execution_id, mint_identity);

CREATE TABLE printer_candidate_identities (
    candidate_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    mint_identity TEXT NOT NULL,
    pool_address TEXT,
    pool_program_id TEXT,
    base_mint TEXT,
    quote_mint TEXT,
    token_program_id TEXT,
    lineage_state TEXT NOT NULL CHECK (
        lineage_state IN (
            'PUMP_ORIGIN_CONFIRMED',
            'PUMP_GRADUATION_CONFIRMED',
            'NON_PUMP_POOL_CONFIRMED',
            'UNKNOWN_ORIGIN',
            'CONFLICTING_LINEAGE',
            'UNSUPPORTED_LINEAGE'
        )
    ),
    identity_status TEXT NOT NULL CHECK (
        identity_status IN ('IDENTITY_MERGED', 'IDENTITY_INCOMPLETE', 'IDENTITY_CONFLICT')
    ),
    identity_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (execution_id, mint_identity),
    UNIQUE (execution_id, pool_address),
    CHECK (length(identity_hash) = 64),
    FOREIGN KEY (execution_id) REFERENCES printer_candidate_acquisition_executions(execution_id)
);

CREATE TABLE printer_candidate_observation_links (
    candidate_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    contribution_role TEXT NOT NULL,
    PRIMARY KEY (candidate_id, observation_id),
    FOREIGN KEY (candidate_id) REFERENCES printer_candidate_identities(candidate_id),
    FOREIGN KEY (observation_id) REFERENCES printer_candidate_source_observations(observation_id)
);

CREATE TABLE printer_candidate_cursor_ranges (
    range_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    network TEXT NOT NULL CHECK (network = 'solana-mainnet'),
    indexed_address TEXT NOT NULL,
    contract_pin TEXT NOT NULL,
    decoder_version TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('FORWARD', 'BACKWARD')),
    start_slot INTEGER,
    start_signature TEXT,
    end_slot INTEGER,
    end_signature TEXT,
    continuity_state TEXT NOT NULL CHECK (
        continuity_state IN ('CONTIGUOUS', 'GAPPED', 'UNKNOWN', 'BLOCKED_CONTRACT')
    ),
    cursor_advanced INTEGER NOT NULL CHECK (cursor_advanced IN (0, 1)),
    unresolved_reason TEXT,
    range_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    CHECK (cursor_advanced = 0 OR continuity_state = 'CONTIGUOUS'),
    CHECK (length(range_hash) = 64),
    FOREIGN KEY (execution_id) REFERENCES printer_candidate_acquisition_executions(execution_id)
);

CREATE TABLE printer_candidate_evidence (
    evidence_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    stage_ordinal INTEGER NOT NULL CHECK (stage_ordinal BETWEEN 1 AND 11),
    stage_name TEXT NOT NULL,
    stage_outcome TEXT NOT NULL CHECK (stage_outcome IN ('PASS', 'FAIL', 'NOT_REACHED')),
    reason_code TEXT NOT NULL,
    evidence_hash TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (candidate_id, stage_ordinal),
    CHECK (length(evidence_hash) = 64),
    FOREIGN KEY (candidate_id) REFERENCES printer_candidate_identities(candidate_id)
);

CREATE TABLE printer_candidate_certificates (
    certificate_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    execution_id TEXT NOT NULL,
    certificate_version TEXT NOT NULL,
    policy_hash TEXT NOT NULL,
    admission_outcome TEXT NOT NULL CHECK (admission_outcome IN ('ADMITTED', 'REJECTED')),
    admission_reason TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    certificate_json TEXT NOT NULL,
    certificate_hash TEXT NOT NULL UNIQUE,
    contains_financial_fields INTEGER NOT NULL DEFAULT 0 CHECK (contains_financial_fields = 0),
    created_at TEXT NOT NULL,
    CHECK (length(certificate_hash) = 64),
    FOREIGN KEY (candidate_id) REFERENCES printer_candidate_identities(candidate_id),
    FOREIGN KEY (execution_id) REFERENCES printer_candidate_acquisition_executions(execution_id)
);

CREATE TABLE printer_candidate_reserve (
    mint_identity TEXT NOT NULL,
    pool_address TEXT NOT NULL,
    current_certificate_id TEXT NOT NULL,
    current_certificate_hash TEXT NOT NULL,
    reserve_version INTEGER NOT NULL CHECK (reserve_version >= 1),
    reserve_status TEXT NOT NULL CHECK (
        reserve_status IN ('ELIGIBLE_FRESH', 'ELIGIBLE_EXPIRED', 'EXCLUDED', 'CLAIMED_NEUTRAL')
    ),
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_requalified_at TEXT NOT NULL,
    claimed_manifest_id TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (mint_identity, pool_address),
    FOREIGN KEY (current_certificate_id) REFERENCES printer_candidate_certificates(certificate_id)
);

CREATE INDEX printer_candidate_reserve_status
    ON printer_candidate_reserve(reserve_status, expires_at);

CREATE TABLE printer_candidate_manifests (
    manifest_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL UNIQUE,
    policy_id TEXT NOT NULL,
    selection_capacity INTEGER NOT NULL CHECK (selection_capacity BETWEEN 1 AND 16),
    expected_item_count INTEGER NOT NULL,
    item_count INTEGER NOT NULL,
    readiness_status TEXT NOT NULL CHECK (
        readiness_status IN ('READY_EXACT_NO_SPARE', 'READY_WITH_RESERVE')
    ),
    runtime_neutral INTEGER NOT NULL CHECK (runtime_neutral = 1),
    approved_active_memory_capacity INTEGER NOT NULL CHECK (approved_active_memory_capacity = 2),
    selection_seed TEXT NOT NULL,
    ordered_item_hashes_json TEXT NOT NULL,
    manifest_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    CHECK (expected_item_count = selection_capacity),
    CHECK (item_count = selection_capacity),
    CHECK (length(manifest_hash) = 64),
    FOREIGN KEY (execution_id) REFERENCES printer_candidate_acquisition_executions(execution_id),
    FOREIGN KEY (policy_id) REFERENCES printer_candidate_acquisition_policies(policy_id)
);

CREATE TABLE printer_candidate_manifest_items (
    manifest_id TEXT NOT NULL,
    item_ordinal INTEGER NOT NULL CHECK (item_ordinal >= 1),
    certificate_id TEXT NOT NULL,
    mint_identity TEXT NOT NULL,
    pool_address TEXT NOT NULL,
    certificate_hash TEXT NOT NULL,
    item_hash TEXT NOT NULL,
    PRIMARY KEY (manifest_id, item_ordinal),
    UNIQUE (manifest_id, mint_identity),
    UNIQUE (manifest_id, pool_address),
    UNIQUE (manifest_id, item_hash),
    CHECK (length(item_hash) = 64),
    FOREIGN KEY (manifest_id) REFERENCES printer_candidate_manifests(manifest_id),
    FOREIGN KEY (certificate_id) REFERENCES printer_candidate_certificates(certificate_id)
);

CREATE TABLE printer_candidate_acquisition_failures (
    failure_id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    failure_family TEXT NOT NULL CHECK (
        failure_family IN (
            'COVERAGE_FAILURE',
            'SOURCE_PROVIDER_FAILURE',
            'BUDGET_EXHAUSTION',
            'STALE_OR_INCOMPLETE_EVIDENCE',
            'UNSUPPORTED_CONTRACT',
            'IDENTITY_MERGE_FAILURE',
            'ADMISSION_FAILURE',
            'INSUFFICIENT_ELIGIBLE_POOL'
        )
    ),
    reason_code TEXT NOT NULL,
    stage_name TEXT,
    source_name TEXT,
    failure_json TEXT NOT NULL,
    failure_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    CHECK (length(failure_hash) = 64),
    FOREIGN KEY (execution_id) REFERENCES printer_candidate_acquisition_executions(execution_id)
);

CREATE TABLE printer_candidate_acquisition_reports (
    execution_id TEXT PRIMARY KEY,
    policy_hash TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    replay_identity TEXT NOT NULL UNIQUE,
    report_json TEXT NOT NULL,
    report_hash TEXT NOT NULL UNIQUE,
    reliability_claim_status TEXT NOT NULL CHECK (
        reliability_claim_status = 'UNPROVEN_NO_INDEPENDENT_SAMPLE'
    ),
    created_at TEXT NOT NULL,
    CHECK (length(report_hash) = 64),
    FOREIGN KEY (execution_id) REFERENCES printer_candidate_acquisition_executions(execution_id)
);

-- Immutable evidence and manifest artifacts. Requalification creates new rows.
CREATE TRIGGER printer_candidate_certificate_update_block
BEFORE UPDATE ON printer_candidate_certificates
BEGIN
    SELECT RAISE(ABORT, 'candidate certificate is immutable');
END;

CREATE TRIGGER printer_candidate_certificate_delete_block
BEFORE DELETE ON printer_candidate_certificates
BEGIN
    SELECT RAISE(ABORT, 'candidate certificate is immutable');
END;

CREATE TRIGGER printer_candidate_manifest_update_block
BEFORE UPDATE ON printer_candidate_manifests
BEGIN
    SELECT RAISE(ABORT, 'candidate manifest is immutable');
END;

CREATE TRIGGER printer_candidate_manifest_delete_block
BEFORE DELETE ON printer_candidate_manifests
BEGIN
    SELECT RAISE(ABORT, 'candidate manifest is immutable');
END;

CREATE TRIGGER printer_candidate_manifest_item_update_block
BEFORE UPDATE ON printer_candidate_manifest_items
BEGIN
    SELECT RAISE(ABORT, 'candidate manifest item is immutable');
END;

CREATE TRIGGER printer_candidate_manifest_item_delete_block
BEFORE DELETE ON printer_candidate_manifest_items
BEGIN
    SELECT RAISE(ABORT, 'candidate manifest item is immutable');
END;

CREATE TRIGGER printer_candidate_report_update_block
BEFORE UPDATE ON printer_candidate_acquisition_reports
BEGIN
    SELECT RAISE(ABORT, 'candidate acquisition report is immutable');
END;

CREATE TRIGGER printer_candidate_report_delete_block
BEFORE DELETE ON printer_candidate_acquisition_reports
BEGIN
    SELECT RAISE(ABORT, 'candidate acquisition report is immutable');
END;
