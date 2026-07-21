-- V2-9.7D.7B.4C: discovery persistence ownership reconciliation.
-- Cycle-rooted discovery batch/work/observation/merge/selection/report links.
-- Does not execute discovery, activate tracking, or unlock financial capability.
-- Existing campaign, Scheduler, Source Governor, and selection owners remain
-- authoritative. Prefer junction links over copied transport payloads.

BEGIN IMMEDIATE;

-- ---------------------------------------------------------------------------
-- 1. Discovery batch (campaign/run/cycle rooted; no token/window fabrication)
-- ---------------------------------------------------------------------------

CREATE TABLE printer_discovery_batches (
    discovery_batch_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    configuration_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    cycle_cutoff TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    provider_contract_versions_json TEXT NOT NULL
        CHECK (json_valid(provider_contract_versions_json) = 1),
    git_provenance_identity TEXT NOT NULL,
    campaign_selection_seed_identity TEXT NOT NULL,
    cycle_seed_hash TEXT NOT NULL
        CHECK (
            length(cycle_seed_hash) = 64
            AND cycle_seed_hash NOT GLOB '*[^0-9a-f]*'
        ),
    pump_cursor_slot INTEGER,
    pump_cursor_signature TEXT,
    pump_continuity_state TEXT NOT NULL CHECK (
        pump_continuity_state IN ('NONE', 'CONTIGUOUS', 'GAPPED', 'UNKNOWN')
    ),
    batch_state TEXT NOT NULL CHECK (
        batch_state IN (
            'PLANNED',
            'DISCOVERING',
            'MERGING',
            'VERIFYING',
            'SELECTING',
            'TRACKING',
            'TERMINAL_COMPLETED',
            'TERMINAL_STOPPED',
            'TERMINAL_BLOCKED',
            'TERMINAL_FAILED'
        )
    ),
    canonical_hash TEXT NOT NULL
        CHECK (
            length(canonical_hash) = 64
            AND canonical_hash NOT GLOB '*[^0-9a-f]*'
        ),
    first_terminal_cause TEXT,
    created_at TEXT NOT NULL,
    terminal_at TEXT,
    UNIQUE (cycle_id),
    UNIQUE (discovery_batch_id, campaign_id, run_id, cycle_id),
    UNIQUE (discovery_batch_id, campaign_id),
    CHECK (length(trim(discovery_batch_id)) > 0),
    CHECK (length(trim(cycle_cutoff)) > 0),
    CHECK (length(trim(policy_version)) > 0),
    CHECK (length(trim(git_provenance_identity)) > 0),
    CHECK (length(trim(campaign_selection_seed_identity)) > 0),
    CHECK (
        (pump_cursor_slot IS NULL AND pump_cursor_signature IS NULL)
        OR
        (pump_cursor_slot IS NOT NULL AND pump_cursor_slot >= 0
            AND pump_cursor_signature IS NOT NULL
            AND length(trim(pump_cursor_signature)) > 0)
    ),
    CHECK (
        (batch_state NOT LIKE 'TERMINAL_%'
            AND first_terminal_cause IS NULL
            AND terminal_at IS NULL)
        OR
        (batch_state LIKE 'TERMINAL_%'
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0
            AND terminal_at IS NOT NULL)
    ),
    FOREIGN KEY (cycle_id, run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_cycles(
            cycle_id, run_id, campaign_id
        ),
    FOREIGN KEY (configuration_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_configurations(
            configuration_id, campaign_id
        )
);

-- ---------------------------------------------------------------------------
-- 2. Pre-selection discovery work (cycle-rooted; no token/window overload)
-- ---------------------------------------------------------------------------

CREATE TABLE printer_discovery_work (
    discovery_work_id TEXT PRIMARY KEY,
    discovery_batch_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    scheduler_job_id INTEGER NOT NULL,
    work_type TEXT NOT NULL CHECK (
        work_type IN (
            'DISCOVERY_PUMPFUN_LATEST',
            'DISCOVERY_DEXSCREENER_ACTIVE',
            'DISCOVERY_GECKOTERMINAL_TRENDING_ACTIVE',
            'DISCOVERY_SOLANA_TRACKER_TRENDING_TOP',
            'DISCOVERY_IDENTITY_MERGE',
            'DISCOVERY_ORIGIN_VERIFICATION',
            'DISCOVERY_PUMPSWAP_CONFIRMATION',
            'DISCOVERY_FIXED_ELIGIBILITY_GATES',
            'DISCOVERY_UNIFORM_SELECTION',
            'DISCOVERY_TRACKING_HANDOFF_SLOT_1',
            'DISCOVERY_TRACKING_HANDOFF_SLOT_2'
        )
    ),
    work_state TEXT NOT NULL CHECK (
        work_state IN (
            'PENDING',
            'RUNNING',
            'SUCCEEDED',
            'FAILED',
            'SKIPPED',
            'CANCELLED'
        )
    ),
    deadline_at TEXT NOT NULL,
    first_terminal_cause TEXT,
    terminal_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (discovery_batch_id, work_type),
    UNIQUE (discovery_work_id, discovery_batch_id, campaign_id, run_id, cycle_id),
    CHECK (length(trim(discovery_work_id)) > 0),
    CHECK (length(trim(deadline_at)) > 0),
    CHECK (
        (work_state IN ('PENDING', 'RUNNING')
            AND first_terminal_cause IS NULL
            AND terminal_at IS NULL)
        OR
        (work_state IN ('SUCCEEDED', 'FAILED', 'SKIPPED', 'CANCELLED')
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0
            AND terminal_at IS NOT NULL)
    ),
    FOREIGN KEY (discovery_batch_id, campaign_id, run_id, cycle_id)
        REFERENCES printer_discovery_batches(
            discovery_batch_id, campaign_id, run_id, cycle_id
        ),
    FOREIGN KEY (scheduler_job_id)
        REFERENCES printer_scheduler_jobs(id)
);

-- ---------------------------------------------------------------------------
-- 3. Work-to-source provenance (one-to-many junction; no payload copy)
-- ---------------------------------------------------------------------------

CREATE TABLE printer_discovery_work_source_links (
    discovery_work_id TEXT NOT NULL,
    link_ordinal INTEGER NOT NULL CHECK (link_ordinal > 0),
    source_request_id INTEGER,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (discovery_work_id, link_ordinal),
    CHECK (
        source_request_id IS NOT NULL
        OR source_response_id IS NOT NULL
        OR source_failure_id IS NOT NULL
    ),
    CHECK (source_response_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_failure_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_response_id IS NULL OR source_failure_id IS NULL),
    FOREIGN KEY (discovery_work_id)
        REFERENCES printer_discovery_work(discovery_work_id),
    FOREIGN KEY (source_request_id)
        REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id)
        REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id)
        REFERENCES printer_source_failures(id)
);

CREATE UNIQUE INDEX idx_discovery_work_source_fact_unique
    ON printer_discovery_work_source_links(
        discovery_work_id,
        ifnull(source_request_id, -1),
        ifnull(source_response_id, -1),
        ifnull(source_failure_id, -1)
    );

-- ---------------------------------------------------------------------------
-- 4. Immutable normalized provider observations
-- ---------------------------------------------------------------------------

CREATE TABLE printer_discovery_provider_observations (
    observation_id TEXT PRIMARY KEY,
    discovery_batch_id TEXT NOT NULL,
    discovery_work_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    request_kind TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (
        channel IN (
            'LATEST_PUMPFUN',
            'TRENDING_PUMPFUN',
            'TOP_PUMPFUN',
            'ACTIVE_PUMPFUN'
        )
    ),
    mint_identity TEXT NOT NULL,
    market_identity TEXT,
    lifecycle_identity TEXT,
    observed_at TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    raw_payload_hash TEXT NOT NULL
        CHECK (
            length(raw_payload_hash) = 64
            AND raw_payload_hash NOT GLOB '*[^0-9a-f]*'
        ),
    source_request_id INTEGER,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    factual_payload_json TEXT NOT NULL
        CHECK (json_valid(factual_payload_json) = 1),
    observation_hash TEXT NOT NULL
        CHECK (
            length(observation_hash) = 64
            AND observation_hash NOT GLOB '*[^0-9a-f]*'
        ),
    created_at TEXT NOT NULL,
    UNIQUE (discovery_batch_id, observation_hash),
    UNIQUE (observation_id, discovery_batch_id),
    CHECK (length(trim(observation_id)) > 0),
    CHECK (length(trim(mint_identity)) > 0),
    CHECK (length(trim(source_name)) > 0),
    CHECK (length(trim(request_kind)) > 0),
    CHECK (source_response_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_failure_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_response_id IS NULL OR source_failure_id IS NULL),
    FOREIGN KEY (discovery_batch_id, campaign_id, run_id, cycle_id)
        REFERENCES printer_discovery_batches(
            discovery_batch_id, campaign_id, run_id, cycle_id
        ),
    FOREIGN KEY (discovery_work_id, discovery_batch_id, campaign_id, run_id, cycle_id)
        REFERENCES printer_discovery_work(
            discovery_work_id, discovery_batch_id, campaign_id, run_id, cycle_id
        ),
    FOREIGN KEY (source_request_id)
        REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id)
        REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id)
        REFERENCES printer_source_failures(id)
);

-- ---------------------------------------------------------------------------
-- 5. Merged candidates and provider contribution links
-- ---------------------------------------------------------------------------

CREATE TABLE printer_discovery_merged_candidates (
    merged_candidate_id TEXT PRIMARY KEY,
    discovery_batch_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    candidate_identity_key TEXT NOT NULL,
    mint_identity TEXT NOT NULL,
    market_identity TEXT,
    lifecycle_identity TEXT,
    channel_labels_json TEXT NOT NULL
        CHECK (json_valid(channel_labels_json) = 1),
    identity_conflicts_json TEXT NOT NULL
        CHECK (json_valid(identity_conflicts_json) = 1),
    evidence_gaps_json TEXT NOT NULL
        CHECK (json_valid(evidence_gaps_json) = 1),
    origin_verification_state TEXT NOT NULL CHECK (
        origin_verification_state IN (
            'NOT_REQUIRED',
            'PENDING',
            'ADMITTED',
            'NOT_ADMITTED_CEILING',
            'CONFIRMED',
            'FAILED',
            'AMBIGUOUS',
            'UNKNOWN'
        )
    ),
    pumpswap_confirmation_state TEXT NOT NULL CHECK (
        pumpswap_confirmation_state IN (
            'NOT_REQUIRED',
            'PENDING',
            'ADMITTED',
            'NOT_ADMITTED_CEILING',
            'CONFIRMED',
            'FAILED',
            'AMBIGUOUS',
            'UNKNOWN'
        )
    ),
    first_failed_eligibility_gate TEXT,
    merged_candidate_hash TEXT NOT NULL
        CHECK (
            length(merged_candidate_hash) = 64
            AND merged_candidate_hash NOT GLOB '*[^0-9a-f]*'
        ),
    created_at TEXT NOT NULL,
    UNIQUE (discovery_batch_id, candidate_identity_key),
    UNIQUE (discovery_batch_id, merged_candidate_hash),
    UNIQUE (merged_candidate_id, discovery_batch_id),
    CHECK (length(trim(merged_candidate_id)) > 0),
    CHECK (length(trim(candidate_identity_key)) > 0),
    CHECK (length(trim(mint_identity)) > 0),
    FOREIGN KEY (discovery_batch_id, campaign_id, run_id, cycle_id)
        REFERENCES printer_discovery_batches(
            discovery_batch_id, campaign_id, run_id, cycle_id
        )
);

CREATE TABLE printer_discovery_candidate_contributions (
    merged_candidate_id TEXT NOT NULL,
    observation_id TEXT NOT NULL,
    contribution_ordinal INTEGER NOT NULL CHECK (contribution_ordinal > 0),
    created_at TEXT NOT NULL,
    PRIMARY KEY (merged_candidate_id, observation_id),
    UNIQUE (merged_candidate_id, contribution_ordinal),
    FOREIGN KEY (merged_candidate_id)
        REFERENCES printer_discovery_merged_candidates(merged_candidate_id),
    FOREIGN KEY (observation_id)
        REFERENCES printer_discovery_provider_observations(observation_id)
);

-- ---------------------------------------------------------------------------
-- 6. Origin verification and PumpSwap confirmation links
-- ---------------------------------------------------------------------------

CREATE TABLE printer_discovery_origin_verifications (
    origin_verification_id TEXT PRIMARY KEY,
    discovery_batch_id TEXT NOT NULL,
    merged_candidate_id TEXT NOT NULL,
    mint_identity TEXT NOT NULL,
    admission_state TEXT NOT NULL CHECK (
        admission_state IN (
            'ADMITTED',
            'NOT_ADMITTED_CEILING',
            'NOT_REQUIRED',
            'FAILED',
            'UNKNOWN'
        )
    ),
    verification_state TEXT NOT NULL CHECK (
        verification_state IN (
            'PENDING',
            'CONFIRMED',
            'FAILED',
            'AMBIGUOUS',
            'UNKNOWN',
            'NOT_ATTEMPTED'
        )
    ),
    source_request_id INTEGER,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    transaction_signature TEXT,
    program_id TEXT,
    slot INTEGER,
    evidence_detail_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(evidence_detail_json) = 1),
    created_at TEXT NOT NULL,
    UNIQUE (discovery_batch_id, merged_candidate_id),
    CHECK (length(trim(origin_verification_id)) > 0),
    CHECK (length(trim(mint_identity)) > 0),
    CHECK (source_response_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_failure_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_response_id IS NULL OR source_failure_id IS NULL),
    FOREIGN KEY (discovery_batch_id)
        REFERENCES printer_discovery_batches(discovery_batch_id),
    FOREIGN KEY (merged_candidate_id, discovery_batch_id)
        REFERENCES printer_discovery_merged_candidates(
            merged_candidate_id, discovery_batch_id
        ),
    FOREIGN KEY (source_request_id)
        REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id)
        REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id)
        REFERENCES printer_source_failures(id)
);

CREATE TABLE printer_discovery_pumpswap_confirmations (
    pumpswap_confirmation_id TEXT PRIMARY KEY,
    discovery_batch_id TEXT NOT NULL,
    merged_candidate_id TEXT NOT NULL,
    mint_identity TEXT NOT NULL,
    market_identity TEXT,
    admission_state TEXT NOT NULL CHECK (
        admission_state IN (
            'ADMITTED',
            'NOT_ADMITTED_CEILING',
            'NOT_REQUIRED',
            'FAILED',
            'UNKNOWN'
        )
    ),
    confirmation_state TEXT NOT NULL CHECK (
        confirmation_state IN (
            'PENDING',
            'CONFIRMED',
            'FAILED',
            'AMBIGUOUS',
            'UNKNOWN',
            'NOT_ATTEMPTED'
        )
    ),
    source_request_id INTEGER,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    pool_address TEXT,
    program_id TEXT,
    evidence_detail_json TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(evidence_detail_json) = 1),
    created_at TEXT NOT NULL,
    UNIQUE (discovery_batch_id, merged_candidate_id),
    CHECK (length(trim(pumpswap_confirmation_id)) > 0),
    CHECK (length(trim(mint_identity)) > 0),
    CHECK (source_response_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_failure_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_response_id IS NULL OR source_failure_id IS NULL),
    FOREIGN KEY (discovery_batch_id)
        REFERENCES printer_discovery_batches(discovery_batch_id),
    FOREIGN KEY (merged_candidate_id, discovery_batch_id)
        REFERENCES printer_discovery_merged_candidates(
            merged_candidate_id, discovery_batch_id
        ),
    FOREIGN KEY (source_request_id)
        REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id)
        REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id)
        REFERENCES printer_source_failures(id)
);

-- ---------------------------------------------------------------------------
-- 7. Selection / handoff linkage (links only; no runtime activation)
-- ---------------------------------------------------------------------------

CREATE TABLE printer_discovery_selection_links (
    discovery_batch_id TEXT NOT NULL,
    selection_batch_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (discovery_batch_id, selection_batch_id),
    UNIQUE (selection_batch_id),
    FOREIGN KEY (discovery_batch_id, campaign_id, run_id, cycle_id)
        REFERENCES printer_discovery_batches(
            discovery_batch_id, campaign_id, run_id, cycle_id
        ),
    FOREIGN KEY (selection_batch_id)
        REFERENCES printer_selection_batches(batch_id)
);

CREATE TABLE printer_discovery_selected_item_links (
    discovery_batch_id TEXT NOT NULL,
    selection_batch_id TEXT NOT NULL,
    selection_item_id INTEGER NOT NULL,
    merged_candidate_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    token_slot_id TEXT,
    tracking_handoff_state TEXT NOT NULL DEFAULT 'NOT_ACTIVATED'
        CHECK (
            tracking_handoff_state IN (
                'NOT_ACTIVATED',
                'LINKED_ONLY',
                'HANDOFF_RECORDED'
            )
        ),
    first_window_15m_scheduler_job_id INTEGER,
    created_at TEXT NOT NULL,
    PRIMARY KEY (discovery_batch_id, selection_item_id),
    UNIQUE (discovery_batch_id, merged_candidate_id),
    FOREIGN KEY (discovery_batch_id, selection_batch_id)
        REFERENCES printer_discovery_selection_links(
            discovery_batch_id, selection_batch_id
        ),
    FOREIGN KEY (discovery_batch_id, campaign_id, run_id, cycle_id)
        REFERENCES printer_discovery_batches(
            discovery_batch_id, campaign_id, run_id, cycle_id
        ),
    FOREIGN KEY (selection_item_id)
        REFERENCES printer_selection_batch_items(id),
    FOREIGN KEY (merged_candidate_id, discovery_batch_id)
        REFERENCES printer_discovery_merged_candidates(
            merged_candidate_id, discovery_batch_id
        ),
    FOREIGN KEY (token_slot_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_token_slots(
            token_slot_id, campaign_id
        ),
    FOREIGN KEY (first_window_15m_scheduler_job_id)
        REFERENCES printer_scheduler_jobs(id)
);

-- ---------------------------------------------------------------------------
-- 8. Provider contribution report links (factual diagnostics only)
-- ---------------------------------------------------------------------------

CREATE TABLE printer_discovery_provider_report_links (
    report_link_id TEXT PRIMARY KEY,
    discovery_batch_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    configuration_id TEXT NOT NULL,
    report_id TEXT,
    discovery_work_id TEXT,
    report_payload_json TEXT NOT NULL
        CHECK (json_valid(report_payload_json) = 1),
    report_hash TEXT NOT NULL
        CHECK (
            length(report_hash) = 64
            AND report_hash NOT GLOB '*[^0-9a-f]*'
        ),
    created_at TEXT NOT NULL,
    UNIQUE (discovery_batch_id, report_hash),
    CHECK (length(trim(report_link_id)) > 0),
    FOREIGN KEY (discovery_batch_id, campaign_id)
        REFERENCES printer_discovery_batches(
            discovery_batch_id, campaign_id
        ),
    FOREIGN KEY (configuration_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_configurations(
            configuration_id, campaign_id
        ),
    FOREIGN KEY (report_id, campaign_id, configuration_id)
        REFERENCES printer_memory_factory_campaign_reports(
            report_id, campaign_id, configuration_id
        ),
    FOREIGN KEY (discovery_work_id)
        REFERENCES printer_discovery_work(discovery_work_id)
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX idx_discovery_batches_owner
    ON printer_discovery_batches(campaign_id, run_id, cycle_id);
CREATE INDEX idx_discovery_work_owner
    ON printer_discovery_work(discovery_batch_id, work_type, work_state);
CREATE INDEX idx_discovery_work_scheduler
    ON printer_discovery_work(scheduler_job_id);
CREATE INDEX idx_discovery_work_source_request
    ON printer_discovery_work_source_links(source_request_id);
CREATE INDEX idx_discovery_observations_batch_order
    ON printer_discovery_provider_observations(
        discovery_batch_id, source_name, request_kind, observed_at, observation_id
    );
CREATE INDEX idx_discovery_observations_mint
    ON printer_discovery_provider_observations(discovery_batch_id, mint_identity);
CREATE INDEX idx_discovery_merged_candidates_batch
    ON printer_discovery_merged_candidates(discovery_batch_id, mint_identity);
CREATE INDEX idx_discovery_origin_batch
    ON printer_discovery_origin_verifications(discovery_batch_id, admission_state);
CREATE INDEX idx_discovery_pumpswap_batch
    ON printer_discovery_pumpswap_confirmations(discovery_batch_id, admission_state);
CREATE INDEX idx_discovery_selection_links_batch
    ON printer_discovery_selection_links(campaign_id, run_id, cycle_id);
CREATE INDEX idx_discovery_report_links_batch
    ON printer_discovery_provider_report_links(discovery_batch_id, campaign_id);

-- ---------------------------------------------------------------------------
-- Provenance integrity triggers
-- ---------------------------------------------------------------------------

CREATE TRIGGER printer_discovery_work_source_response_match
BEFORE INSERT ON printer_discovery_work_source_links
WHEN NEW.source_response_id IS NOT NULL
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_source_responses
        WHERE id = NEW.source_response_id
          AND source_request_id = NEW.source_request_id
    ) THEN RAISE(ABORT, 'discovery work source response provenance mismatch') END;
END;

CREATE TRIGGER printer_discovery_observation_response_match
BEFORE INSERT ON printer_discovery_provider_observations
WHEN NEW.source_response_id IS NOT NULL
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_source_responses
        WHERE id = NEW.source_response_id
          AND source_request_id = NEW.source_request_id
    ) THEN RAISE(ABORT, 'discovery observation source response provenance mismatch') END;
END;

CREATE TRIGGER printer_discovery_contribution_same_batch
BEFORE INSERT ON printer_discovery_candidate_contributions
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM printer_discovery_merged_candidates AS c
        JOIN printer_discovery_provider_observations AS o
          ON o.observation_id = NEW.observation_id
        WHERE c.merged_candidate_id = NEW.merged_candidate_id
          AND c.discovery_batch_id = o.discovery_batch_id
    ) THEN RAISE(ABORT, 'discovery contribution cross-batch mismatch') END;
END;

CREATE TRIGGER printer_discovery_selected_item_slot_cycle
BEFORE INSERT ON printer_discovery_selected_item_links
WHEN NEW.token_slot_id IS NOT NULL
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_token_slots
        WHERE token_slot_id = NEW.token_slot_id
          AND campaign_id = NEW.campaign_id
          AND run_id = NEW.run_id
          AND cycle_id = NEW.cycle_id
    ) THEN RAISE(ABORT, 'discovery selected item slot cycle mismatch') END;
END;

-- ---------------------------------------------------------------------------
-- Immutability triggers (append-only identity and factual rows)
-- ---------------------------------------------------------------------------

CREATE TRIGGER printer_discovery_batch_identity_immutable
BEFORE UPDATE OF
    discovery_batch_id, campaign_id, configuration_id, run_id, cycle_id,
    cycle_cutoff, policy_version, provider_contract_versions_json,
    git_provenance_identity, campaign_selection_seed_identity, cycle_seed_hash,
    pump_cursor_slot, pump_cursor_signature, canonical_hash, created_at
ON printer_discovery_batches
BEGIN
    SELECT RAISE(ABORT, 'discovery batch identity is immutable');
END;

CREATE TRIGGER printer_discovery_work_identity_immutable
BEFORE UPDATE OF
    discovery_work_id, discovery_batch_id, campaign_id, run_id, cycle_id,
    scheduler_job_id, work_type, deadline_at, created_at
ON printer_discovery_work
BEGIN
    SELECT RAISE(ABORT, 'discovery work identity is immutable');
END;

CREATE TRIGGER printer_discovery_work_source_immutable_update
BEFORE UPDATE ON printer_discovery_work_source_links
BEGIN
    SELECT RAISE(ABORT, 'discovery work source link is immutable');
END;

CREATE TRIGGER printer_discovery_work_source_immutable_delete
BEFORE DELETE ON printer_discovery_work_source_links
BEGIN
    SELECT RAISE(ABORT, 'discovery work source link is immutable');
END;

CREATE TRIGGER printer_discovery_observation_immutable_update
BEFORE UPDATE ON printer_discovery_provider_observations
BEGIN
    SELECT RAISE(ABORT, 'discovery provider observation is immutable');
END;

CREATE TRIGGER printer_discovery_observation_immutable_delete
BEFORE DELETE ON printer_discovery_provider_observations
BEGIN
    SELECT RAISE(ABORT, 'discovery provider observation is immutable');
END;

CREATE TRIGGER printer_discovery_merged_candidate_immutable_update
BEFORE UPDATE ON printer_discovery_merged_candidates
BEGIN
    SELECT RAISE(ABORT, 'discovery merged candidate is immutable');
END;

CREATE TRIGGER printer_discovery_merged_candidate_immutable_delete
BEFORE DELETE ON printer_discovery_merged_candidates
BEGIN
    SELECT RAISE(ABORT, 'discovery merged candidate is immutable');
END;

CREATE TRIGGER printer_discovery_contribution_immutable_update
BEFORE UPDATE ON printer_discovery_candidate_contributions
BEGIN
    SELECT RAISE(ABORT, 'discovery candidate contribution is immutable');
END;

CREATE TRIGGER printer_discovery_contribution_immutable_delete
BEFORE DELETE ON printer_discovery_candidate_contributions
BEGIN
    SELECT RAISE(ABORT, 'discovery candidate contribution is immutable');
END;

CREATE TRIGGER printer_discovery_origin_immutable_update
BEFORE UPDATE ON printer_discovery_origin_verifications
BEGIN
    SELECT RAISE(ABORT, 'discovery origin verification is immutable');
END;

CREATE TRIGGER printer_discovery_origin_immutable_delete
BEFORE DELETE ON printer_discovery_origin_verifications
BEGIN
    SELECT RAISE(ABORT, 'discovery origin verification is immutable');
END;

CREATE TRIGGER printer_discovery_pumpswap_immutable_update
BEFORE UPDATE ON printer_discovery_pumpswap_confirmations
BEGIN
    SELECT RAISE(ABORT, 'discovery pumpswap confirmation is immutable');
END;

CREATE TRIGGER printer_discovery_pumpswap_immutable_delete
BEFORE DELETE ON printer_discovery_pumpswap_confirmations
BEGIN
    SELECT RAISE(ABORT, 'discovery pumpswap confirmation is immutable');
END;

CREATE TRIGGER printer_discovery_selection_link_immutable_update
BEFORE UPDATE ON printer_discovery_selection_links
BEGIN
    SELECT RAISE(ABORT, 'discovery selection link is immutable');
END;

CREATE TRIGGER printer_discovery_selection_link_immutable_delete
BEFORE DELETE ON printer_discovery_selection_links
BEGIN
    SELECT RAISE(ABORT, 'discovery selection link is immutable');
END;

CREATE TRIGGER printer_discovery_selected_item_immutable_update
BEFORE UPDATE ON printer_discovery_selected_item_links
BEGIN
    SELECT RAISE(ABORT, 'discovery selected item link is immutable');
END;

CREATE TRIGGER printer_discovery_selected_item_immutable_delete
BEFORE DELETE ON printer_discovery_selected_item_links
BEGIN
    SELECT RAISE(ABORT, 'discovery selected item link is immutable');
END;

CREATE TRIGGER printer_discovery_report_link_immutable_update
BEFORE UPDATE ON printer_discovery_provider_report_links
BEGIN
    SELECT RAISE(ABORT, 'discovery provider report link is immutable');
END;

CREATE TRIGGER printer_discovery_report_link_immutable_delete
BEFORE DELETE ON printer_discovery_provider_report_links
BEGIN
    SELECT RAISE(ABORT, 'discovery provider report link is immutable');
END;

COMMIT;
