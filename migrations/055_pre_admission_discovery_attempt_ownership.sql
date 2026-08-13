-- V2-9.8B: durable pre-admission discovery-attempt ownership.
--
-- Additive only. This ledger owns one Scheduler-governed discovery/selection
-- opportunity before proposed cycle 2 exists. Existing cycle-rooted discovery
-- tables remain unchanged and authoritative after atomic admission.

BEGIN IMMEDIATE;

CREATE TABLE printer_pre_admission_discovery_attempts (
    attempt_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    campaign_run_id TEXT NOT NULL,
    configuration_id TEXT NOT NULL,
    authoritative_factory_run_id TEXT NOT NULL,
    proposed_cycle_ordinal INTEGER NOT NULL CHECK (proposed_cycle_ordinal = 2),
    proposed_cycle_id TEXT NOT NULL,
    scheduler_job_id INTEGER NOT NULL UNIQUE,
    cycle_cutoff TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    selection_seed_identity TEXT NOT NULL,
    attempt_state TEXT NOT NULL CHECK (attempt_state IN (
        'PLANNED', 'RUNNING', 'PAIR_READY', 'NO_PAIR', 'BLOCKED',
        'FAILED', 'CANCELLED', 'CONSUMED'
    )),
    first_terminal_cause TEXT,
    terminal_at TEXT,
    consumed_cycle_id TEXT,
    consumed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (
        campaign_id, campaign_run_id, authoritative_factory_run_id,
        proposed_cycle_ordinal
    ),
    UNIQUE (attempt_id, campaign_id, campaign_run_id, authoritative_factory_run_id),
    CHECK (length(trim(attempt_id)) > 0),
    CHECK (length(trim(proposed_cycle_id)) > 0),
    CHECK (length(trim(cycle_cutoff)) > 0),
    CHECK (length(trim(evaluated_at)) > 0),
    CHECK (length(trim(selection_seed_identity)) > 0),
    CHECK (
        (attempt_state IN ('PLANNED', 'RUNNING')
            AND first_terminal_cause IS NULL
            AND terminal_at IS NULL
            AND consumed_cycle_id IS NULL
            AND consumed_at IS NULL)
        OR
        (attempt_state IN (
            'PAIR_READY', 'NO_PAIR', 'BLOCKED', 'FAILED', 'CANCELLED'
        )
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0
            AND terminal_at IS NOT NULL
            AND consumed_cycle_id IS NULL
            AND consumed_at IS NULL)
        OR
        (attempt_state = 'CONSUMED'
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0
            AND terminal_at IS NOT NULL
            AND consumed_cycle_id IS NOT NULL
            AND length(trim(consumed_cycle_id)) > 0
            AND consumed_at IS NOT NULL)
    ),
    FOREIGN KEY (campaign_id)
        REFERENCES printer_memory_factory_campaigns(campaign_id),
    FOREIGN KEY (campaign_run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_runs(run_id, campaign_id),
    FOREIGN KEY (configuration_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_configurations(
            configuration_id, campaign_id
        ),
    FOREIGN KEY (authoritative_factory_run_id)
        REFERENCES printer_memory_factory_runs(run_id),
    FOREIGN KEY (scheduler_job_id)
        REFERENCES printer_scheduler_jobs(id),
    FOREIGN KEY (consumed_cycle_id, campaign_run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_cycles(
            cycle_id, run_id, campaign_id
        )
);

CREATE TABLE printer_pre_admission_discovery_attempt_items (
    attempt_id TEXT NOT NULL,
    slot_ordinal INTEGER NOT NULL CHECK (slot_ordinal IN (1, 2)),
    token_identity TEXT NOT NULL,
    token_row_id INTEGER NOT NULL,
    mint_identity TEXT NOT NULL,
    pair_identity TEXT NOT NULL,
    pair_row_id INTEGER NOT NULL,
    lifecycle_identity TEXT NOT NULL,
    canonical_market_identity TEXT NOT NULL,
    canonical_pool_identity TEXT NOT NULL,
    canonical_evidence_json TEXT NOT NULL
        CHECK (json_valid(canonical_evidence_json) = 1),
    canonical_evidence_hash TEXT NOT NULL CHECK (
        length(canonical_evidence_hash) = 64
        AND canonical_evidence_hash NOT GLOB '*[^0-9a-f]*'
    ),
    evidence_version TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (attempt_id, slot_ordinal),
    UNIQUE (attempt_id, token_identity),
    UNIQUE (attempt_id, token_row_id),
    UNIQUE (attempt_id, mint_identity),
    UNIQUE (attempt_id, pair_identity),
    UNIQUE (attempt_id, pair_row_id),
    CHECK (length(trim(token_identity)) > 0),
    CHECK (length(trim(mint_identity)) > 0),
    CHECK (length(trim(pair_identity)) > 0),
    CHECK (length(trim(lifecycle_identity)) > 0),
    CHECK (length(trim(canonical_market_identity)) > 0),
    CHECK (length(trim(canonical_pool_identity)) > 0),
    CHECK (length(trim(evidence_version)) > 0),
    FOREIGN KEY (attempt_id)
        REFERENCES printer_pre_admission_discovery_attempts(attempt_id),
    FOREIGN KEY (token_row_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_row_id) REFERENCES printer_pairs(id)
);

CREATE TABLE printer_pre_admission_discovery_attempt_source_links (
    attempt_id TEXT NOT NULL,
    link_ordinal INTEGER NOT NULL CHECK (link_ordinal > 0),
    logical_stage TEXT NOT NULL,
    source_request_id INTEGER NOT NULL,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (attempt_id, link_ordinal),
    UNIQUE (
        attempt_id, logical_stage, source_request_id,
        source_response_id, source_failure_id
    ),
    CHECK (length(trim(logical_stage)) > 0),
    CHECK (source_response_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_failure_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_response_id IS NULL OR source_failure_id IS NULL),
    FOREIGN KEY (attempt_id)
        REFERENCES printer_pre_admission_discovery_attempts(attempt_id),
    FOREIGN KEY (source_request_id) REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id) REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id) REFERENCES printer_source_failures(id)
);

CREATE INDEX idx_pre_admission_attempt_scope_state
    ON printer_pre_admission_discovery_attempts(
        campaign_id, campaign_run_id, authoritative_factory_run_id,
        proposed_cycle_ordinal, attempt_state
    );

CREATE TRIGGER printer_pre_admission_attempt_owner_match
BEFORE INSERT ON printer_pre_admission_discovery_attempts
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_runs
        WHERE run_id = NEW.campaign_run_id
          AND campaign_id = NEW.campaign_id
          AND authoritative_run_id = NEW.authoritative_factory_run_id
    ) THEN RAISE(ABORT, 'pre-admission authoritative factory ownership mismatch') END;
END;

CREATE TRIGGER printer_pre_admission_attempt_identity_immutable
BEFORE UPDATE OF attempt_id, campaign_id, campaign_run_id, configuration_id,
    authoritative_factory_run_id, proposed_cycle_ordinal, proposed_cycle_id,
    scheduler_job_id, cycle_cutoff, evaluated_at, selection_seed_identity,
    created_at, first_terminal_cause
ON printer_pre_admission_discovery_attempts
BEGIN
    SELECT CASE
        WHEN OLD.attempt_id IS NOT NEW.attempt_id
          OR OLD.campaign_id IS NOT NEW.campaign_id
          OR OLD.campaign_run_id IS NOT NEW.campaign_run_id
          OR OLD.configuration_id IS NOT NEW.configuration_id
          OR OLD.authoritative_factory_run_id IS NOT NEW.authoritative_factory_run_id
          OR OLD.proposed_cycle_ordinal IS NOT NEW.proposed_cycle_ordinal
          OR OLD.proposed_cycle_id IS NOT NEW.proposed_cycle_id
          OR OLD.scheduler_job_id IS NOT NEW.scheduler_job_id
          OR OLD.cycle_cutoff IS NOT NEW.cycle_cutoff
          OR OLD.evaluated_at IS NOT NEW.evaluated_at
          OR OLD.selection_seed_identity IS NOT NEW.selection_seed_identity
          OR OLD.created_at IS NOT NEW.created_at
        THEN RAISE(ABORT, 'pre-admission attempt identity is immutable')
    END;
    SELECT CASE
        WHEN OLD.first_terminal_cause IS NOT NULL
         AND OLD.first_terminal_cause IS NOT NEW.first_terminal_cause
        THEN RAISE(ABORT, 'first_terminal_cause is immutable once recorded')
    END;
END;

CREATE TRIGGER printer_pre_admission_attempt_transition
BEFORE UPDATE OF attempt_state ON printer_pre_admission_discovery_attempts
BEGIN
    SELECT CASE WHEN NOT (
        (OLD.attempt_state = 'PLANNED' AND NEW.attempt_state IN (
            'RUNNING', 'CANCELLED', 'BLOCKED'
        ))
        OR
        (OLD.attempt_state = 'RUNNING' AND NEW.attempt_state IN (
            'PAIR_READY', 'NO_PAIR', 'BLOCKED', 'FAILED', 'CANCELLED'
        ))
        OR
        (OLD.attempt_state = 'PAIR_READY' AND NEW.attempt_state = 'CONSUMED')
    ) THEN RAISE(ABORT, 'invalid pre-admission attempt transition') END;
END;

CREATE TRIGGER printer_pre_admission_attempt_item_immutable_update
BEFORE UPDATE ON printer_pre_admission_discovery_attempt_items
BEGIN
    SELECT RAISE(ABORT, 'pre-admission attempt item is immutable');
END;

CREATE TRIGGER printer_pre_admission_attempt_item_immutable_delete
BEFORE DELETE ON printer_pre_admission_discovery_attempt_items
BEGIN
    SELECT RAISE(ABORT, 'pre-admission attempt item is immutable');
END;

CREATE TRIGGER printer_pre_admission_source_response_match
BEFORE INSERT ON printer_pre_admission_discovery_attempt_source_links
WHEN NEW.source_response_id IS NOT NULL
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_source_responses
        WHERE id = NEW.source_response_id
          AND source_request_id = NEW.source_request_id
    ) THEN RAISE(ABORT, 'pre-admission response/request mismatch') END;
END;

CREATE TRIGGER printer_pre_admission_source_failure_match
BEFORE INSERT ON printer_pre_admission_discovery_attempt_source_links
WHEN NEW.source_failure_id IS NOT NULL
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_source_failures
        WHERE id = NEW.source_failure_id
          AND source_request_id = NEW.source_request_id
    ) THEN RAISE(ABORT, 'pre-admission failure/request mismatch') END;
END;

COMMIT;
