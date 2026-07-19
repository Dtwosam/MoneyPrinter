-- V2-9.7D.6B.1: campaign-rooted ownership and immutable object linkage.
-- B.1-B.5 records remain authoritative; this graph stores only exact links.

BEGIN IMMEDIATE;

CREATE TABLE printer_memory_factory_campaign_runs (
    run_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    run_ordinal INTEGER NOT NULL CHECK (run_ordinal > 0),
    run_state TEXT NOT NULL CHECK (run_state IN (
        'DRAFT', 'PREFLIGHT', 'RUNNING', 'STOP_REQUESTED',
        'TERMINAL_COMPLETED', 'TERMINAL_STOPPED',
        'TERMINAL_BLOCKED', 'TERMINAL_FAILED'
    )),
    authoritative_run_id TEXT,
    proof_supervision_id INTEGER,
    first_terminal_cause TEXT,
    terminal_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (campaign_id, run_ordinal),
    UNIQUE (run_id, campaign_id),
    FOREIGN KEY (campaign_id)
        REFERENCES printer_memory_factory_campaigns(campaign_id),
    FOREIGN KEY (authoritative_run_id)
        REFERENCES printer_memory_factory_runs(run_id),
    FOREIGN KEY (proof_supervision_id)
        REFERENCES printer_proof_run_supervision(id),
    CHECK (
        (run_state IN ('DRAFT', 'PREFLIGHT', 'RUNNING', 'STOP_REQUESTED')
            AND first_terminal_cause IS NULL AND terminal_at IS NULL)
        OR
        (run_state LIKE 'TERMINAL_%'
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0 AND terminal_at IS NOT NULL)
    )
);

CREATE TABLE printer_memory_factory_campaign_cycles (
    cycle_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_ordinal INTEGER NOT NULL CHECK (cycle_ordinal > 0),
    cycle_state TEXT NOT NULL CHECK (cycle_state IN (
        'PLANNED', 'DISCOVERING', 'SELECTING', 'TRACKING', 'CLOSING',
        'AUDITING', 'ROTATING', 'TERMINAL_COMPLETED', 'TERMINAL_STOPPED',
        'TERMINAL_BLOCKED', 'TERMINAL_FAILED'
    )),
    first_terminal_cause TEXT,
    terminal_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (run_id, cycle_ordinal),
    UNIQUE (cycle_id, run_id, campaign_id),
    FOREIGN KEY (run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_runs(run_id, campaign_id),
    CHECK (
        (cycle_state NOT LIKE 'TERMINAL_%'
            AND first_terminal_cause IS NULL AND terminal_at IS NULL)
        OR
        (cycle_state LIKE 'TERMINAL_%'
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0 AND terminal_at IS NOT NULL)
    )
);

CREATE TABLE printer_memory_factory_campaign_token_slots (
    token_slot_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    slot_ordinal INTEGER NOT NULL CHECK (slot_ordinal IN (1, 2)),
    token_identity TEXT NOT NULL,
    token_row_id INTEGER NOT NULL,
    mint_identity TEXT NOT NULL,
    pair_identity TEXT NOT NULL,
    pair_row_id INTEGER NOT NULL,
    lifecycle_identity TEXT NOT NULL,
    tracking_queue_id INTEGER,
    replacement_predecessor_slot_id TEXT,
    token_state TEXT NOT NULL CHECK (token_state IN (
        'SELECTED', 'WINDOW_15M_ACTIVE', 'WINDOW_15M_CLOSED',
        'WINDOW_1H_CONTINUING', 'WINDOW_1H_CLOSED',
        'WINDOW_4H_CONTINUING', 'WINDOW_4H_CLOSED',
        'COOLDOWN', 'ARCHIVED', 'MANUAL_REVIEW', 'FAILED'
    )),
    first_terminal_cause TEXT,
    terminal_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (cycle_id, slot_ordinal),
    UNIQUE (cycle_id, token_row_id),
    UNIQUE (token_slot_id, campaign_id),
    UNIQUE (token_slot_id, cycle_id, run_id, campaign_id),
    FOREIGN KEY (cycle_id, run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_cycles(
            cycle_id, run_id, campaign_id
        ),
    FOREIGN KEY (token_row_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_row_id) REFERENCES printer_pairs(id),
    FOREIGN KEY (tracking_queue_id) REFERENCES printer_tracking_queue(id),
    FOREIGN KEY (replacement_predecessor_slot_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_token_slots(
            token_slot_id, campaign_id
        ),
    CHECK (
        (token_state NOT IN ('COOLDOWN', 'ARCHIVED', 'MANUAL_REVIEW', 'FAILED')
            AND first_terminal_cause IS NULL AND terminal_at IS NULL)
        OR
        (token_state IN ('COOLDOWN', 'ARCHIVED', 'MANUAL_REVIEW', 'FAILED')
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0 AND terminal_at IS NOT NULL)
    )
);

CREATE TABLE printer_memory_factory_campaign_windows (
    window_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    token_slot_id TEXT NOT NULL,
    token_row_id INTEGER NOT NULL,
    pair_row_id INTEGER NOT NULL,
    window_kind TEXT NOT NULL CHECK (window_kind IN (
        'WINDOW_5M_MICRO_EVENT', 'WINDOW_15M', 'WINDOW_1H', 'WINDOW_4H'
    )),
    window_state TEXT NOT NULL CHECK (window_state IN (
        'PLANNED', 'COLLECTING', 'CLOSE_PENDING', 'AUDITING',
        'CLEAN_PROMOTED', 'DIRTY', 'BLOCKED', 'NO_PROMOTION',
        'ALREADY_EXISTS_IDEMPOTENT', 'CANCELLED'
    )),
    root_15m_lifecycle_identity TEXT NOT NULL,
    predecessor_window_id TEXT,
    containing_main_window_id TEXT,
    memory_window_row_id INTEGER,
    checkpoint_cutoff TEXT NOT NULL,
    support_only INTEGER NOT NULL CHECK (support_only IN (0, 1)),
    first_terminal_cause TEXT,
    terminal_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (window_id, token_slot_id, cycle_id, run_id, campaign_id),
    FOREIGN KEY (token_slot_id, cycle_id, run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_token_slots(
            token_slot_id, cycle_id, run_id, campaign_id
        ),
    FOREIGN KEY (predecessor_window_id, token_slot_id, cycle_id, run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_windows(
            window_id, token_slot_id, cycle_id, run_id, campaign_id
        ),
    FOREIGN KEY (containing_main_window_id, token_slot_id, cycle_id, run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_windows(
            window_id, token_slot_id, cycle_id, run_id, campaign_id
        ),
    FOREIGN KEY (memory_window_row_id) REFERENCES printer_memory_windows(id),
    CHECK (
        (window_kind = 'WINDOW_5M_MICRO_EVENT'
            AND support_only = 1 AND containing_main_window_id IS NOT NULL)
        OR
        (window_kind <> 'WINDOW_5M_MICRO_EVENT'
            AND support_only = 0 AND containing_main_window_id IS NULL)
    ),
    CHECK (
        (window_state IN ('PLANNED', 'COLLECTING', 'CLOSE_PENDING', 'AUDITING')
            AND first_terminal_cause IS NULL AND terminal_at IS NULL)
        OR
        (window_state IN (
            'CLEAN_PROMOTED', 'DIRTY', 'BLOCKED', 'NO_PROMOTION',
            'ALREADY_EXISTS_IDEMPOTENT', 'CANCELLED'
        ) AND first_terminal_cause IS NOT NULL
          AND length(trim(first_terminal_cause)) > 0 AND terminal_at IS NOT NULL)
    )
);

CREATE TABLE printer_memory_factory_campaign_scheduler_work (
    scheduler_work_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    token_slot_id TEXT NOT NULL,
    window_id TEXT NOT NULL,
    work_intent TEXT NOT NULL,
    deadline_at TEXT NOT NULL,
    work_state TEXT NOT NULL CHECK (work_state IN (
        'PENDING', 'RUNNING', 'COOLDOWN', 'SUCCEEDED', 'FAILED',
        'SKIPPED', 'CANCELLED'
    )),
    scheduler_job_id INTEGER,
    source_request_id INTEGER,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    first_terminal_cause TEXT,
    terminal_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (scheduler_work_id, window_id, token_slot_id, cycle_id, run_id, campaign_id),
    FOREIGN KEY (window_id, token_slot_id, cycle_id, run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_windows(
            window_id, token_slot_id, cycle_id, run_id, campaign_id
        ),
    FOREIGN KEY (scheduler_job_id) REFERENCES printer_scheduler_jobs(id),
    FOREIGN KEY (source_request_id) REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id) REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id) REFERENCES printer_source_failures(id),
    CHECK (source_response_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_failure_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_response_id IS NULL OR source_failure_id IS NULL),
    CHECK (
        (work_state IN ('PENDING', 'RUNNING', 'COOLDOWN')
            AND first_terminal_cause IS NULL AND terminal_at IS NULL)
        OR
        (work_state IN ('SUCCEEDED', 'FAILED', 'SKIPPED', 'CANCELLED')
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0 AND terminal_at IS NOT NULL)
    )
);

CREATE TABLE printer_memory_factory_campaign_objects (
    object_id TEXT PRIMARY KEY,
    object_kind TEXT NOT NULL CHECK (object_kind IN (
        'CONTINUATION_4A', 'SUPPORT_EVIDENCE_4B', 'TRAJECTORY_5A',
        'CHECKPOINT_5A', 'MANIPULATION_CONTEXT_5B',
        'OPPORTUNITY_SEGMENT_5C'
    )),
    campaign_id TEXT NOT NULL,
    configuration_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    token_slot_id TEXT NOT NULL,
    window_id TEXT NOT NULL,
    scheduler_work_id TEXT,
    object_hash TEXT NOT NULL CHECK (
        length(object_hash) = 64 AND object_hash NOT GLOB '*[^0-9a-f]*'
    ),
    object_json TEXT NOT NULL CHECK (json_valid(object_json) = 1),
    authoritative_episode_id INTEGER,
    safety_composite_id INTEGER,
    lifecycle_event_id INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (configuration_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_configurations(
            configuration_id, campaign_id
        ),
    FOREIGN KEY (window_id, token_slot_id, cycle_id, run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_windows(
            window_id, token_slot_id, cycle_id, run_id, campaign_id
        ),
    FOREIGN KEY (scheduler_work_id, window_id, token_slot_id, cycle_id, run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_scheduler_work(
            scheduler_work_id, window_id, token_slot_id, cycle_id, run_id, campaign_id
        ),
    FOREIGN KEY (authoritative_episode_id) REFERENCES printer_episodes(id),
    FOREIGN KEY (safety_composite_id) REFERENCES printer_safety_evidence_composites(id),
    FOREIGN KEY (lifecycle_event_id) REFERENCES printer_token_lifecycle_events(id)
);

CREATE TABLE printer_memory_factory_campaign_report_objects (
    report_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    configuration_id TEXT NOT NULL,
    object_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (report_id, object_id),
    FOREIGN KEY (report_id, campaign_id, configuration_id)
        REFERENCES printer_memory_factory_campaign_reports(
            report_id, campaign_id, configuration_id
        ),
    FOREIGN KEY (object_id) REFERENCES printer_memory_factory_campaign_objects(object_id)
);

CREATE INDEX idx_campaign_cycles_owner
    ON printer_memory_factory_campaign_cycles(campaign_id, run_id, cycle_ordinal);
CREATE INDEX idx_campaign_slots_owner
    ON printer_memory_factory_campaign_token_slots(campaign_id, run_id, cycle_id);
CREATE INDEX idx_campaign_windows_owner
    ON printer_memory_factory_campaign_windows(campaign_id, run_id, cycle_id, token_slot_id);
CREATE INDEX idx_campaign_work_owner
    ON printer_memory_factory_campaign_scheduler_work(campaign_id, run_id, cycle_id, token_slot_id);
CREATE INDEX idx_campaign_objects_owner
    ON printer_memory_factory_campaign_objects(campaign_id, run_id, cycle_id, token_slot_id, window_id);
CREATE INDEX idx_campaign_objects_content
    ON printer_memory_factory_campaign_objects(object_kind, object_hash);

CREATE TRIGGER printer_campaign_slot_exact_identity_insert
BEFORE INSERT ON printer_memory_factory_campaign_token_slots
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_tokens
        WHERE id = NEW.token_row_id AND token_mint = NEW.mint_identity
    ) THEN RAISE(ABORT, 'token and mint identity mismatch') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_pairs
        WHERE id = NEW.pair_row_id AND token_id = NEW.token_row_id
          AND pair_address = NEW.pair_identity
    ) THEN RAISE(ABORT, 'token and pair identity mismatch') END;
    SELECT CASE WHEN NEW.tracking_queue_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM printer_tracking_queue
        WHERE id = NEW.tracking_queue_id AND token_id = NEW.token_row_id
          AND pair_id = NEW.pair_row_id
    ) THEN RAISE(ABORT, 'tracking queue identity mismatch') END;
END;

CREATE TRIGGER printer_campaign_window_exact_identity_insert
BEFORE INSERT ON printer_memory_factory_campaign_windows
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_token_slots
        WHERE token_slot_id = NEW.token_slot_id
          AND token_row_id = NEW.token_row_id AND pair_row_id = NEW.pair_row_id
    ) THEN RAISE(ABORT, 'window token or pair identity mismatch') END;
    SELECT CASE WHEN NEW.memory_window_row_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM printer_memory_windows
        WHERE id = NEW.memory_window_row_id AND token_id = NEW.token_row_id
          AND pair_id = NEW.pair_row_id AND window_kind = NEW.window_kind
    ) THEN RAISE(ABORT, 'memory window identity mismatch') END;
    SELECT CASE WHEN NEW.predecessor_window_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_windows
        WHERE window_id = NEW.predecessor_window_id
          AND root_15m_lifecycle_identity = NEW.root_15m_lifecycle_identity
          AND ((NEW.window_kind = 'WINDOW_1H' AND window_kind = 'WINDOW_15M')
            OR (NEW.window_kind = 'WINDOW_4H' AND window_kind = 'WINDOW_1H'))
    ) THEN RAISE(ABORT, 'window predecessor mismatch') END;
    SELECT CASE WHEN NEW.window_kind = 'WINDOW_15M'
        AND NEW.predecessor_window_id IS NOT NULL
    THEN RAISE(ABORT, '15m window cannot have predecessor') END;
    SELECT CASE WHEN NEW.window_kind = 'WINDOW_5M_MICRO_EVENT' AND NOT EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_windows
        WHERE window_id = NEW.containing_main_window_id
          AND window_kind <> 'WINDOW_5M_MICRO_EVENT'
          AND root_15m_lifecycle_identity = NEW.root_15m_lifecycle_identity
    ) THEN RAISE(ABORT, 'support containing window mismatch') END;
END;

CREATE TRIGGER printer_campaign_cycle_requires_two_slots
BEFORE UPDATE OF cycle_state ON printer_memory_factory_campaign_cycles
WHEN OLD.cycle_state = 'PLANNED' AND NEW.cycle_state <> 'PLANNED'
BEGIN
    SELECT CASE WHEN (
        SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots
        WHERE cycle_id = OLD.cycle_id
    ) <> 2 THEN RAISE(ABORT, 'campaign cycle requires exactly two token slots') END;
END;

CREATE TRIGGER printer_campaign_work_provenance_insert
BEFORE INSERT ON printer_memory_factory_campaign_scheduler_work
BEGIN
    SELECT CASE WHEN NEW.source_response_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM printer_source_responses
        WHERE id = NEW.source_response_id
          AND source_request_id = NEW.source_request_id
    ) THEN RAISE(ABORT, 'source response provenance mismatch') END;
END;

CREATE TRIGGER printer_campaign_object_authority_insert
BEFORE INSERT ON printer_memory_factory_campaign_objects
BEGIN
    SELECT CASE WHEN NEW.authoritative_episode_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM printer_episodes AS e
        JOIN printer_memory_factory_campaign_windows AS w
          ON w.window_id = NEW.window_id
        WHERE e.id = NEW.authoritative_episode_id
          AND e.token_id = w.token_row_id AND e.pair_id = w.pair_row_id
          AND e.memory_window_id = w.memory_window_row_id
    ) THEN RAISE(ABORT, 'authoritative episode identity mismatch') END;
    SELECT CASE WHEN NEW.safety_composite_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM printer_safety_evidence_composites AS s
        JOIN printer_memory_factory_campaign_windows AS w
          ON w.window_id = NEW.window_id
        WHERE s.id = NEW.safety_composite_id
          AND s.token_id = w.token_row_id AND s.pair_id = w.pair_row_id
    ) THEN RAISE(ABORT, 'safety composite identity mismatch') END;
    SELECT CASE WHEN NEW.lifecycle_event_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM printer_token_lifecycle_events AS e
        JOIN printer_memory_factory_campaign_windows AS w
          ON w.window_id = NEW.window_id
        WHERE e.id = NEW.lifecycle_event_id
          AND e.token_id = w.token_row_id AND e.pair_id = w.pair_row_id
    ) THEN RAISE(ABORT, 'lifecycle event identity mismatch') END;
END;

CREATE TRIGGER printer_campaign_report_object_owner_insert
BEFORE INSERT ON printer_memory_factory_campaign_report_objects
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_objects
        WHERE object_id = NEW.object_id
          AND campaign_id = NEW.campaign_id
          AND configuration_id = NEW.configuration_id
    ) THEN RAISE(ABORT, 'report object campaign mismatch') END;
END;

CREATE TRIGGER printer_campaign_run_identity_immutable
BEFORE UPDATE OF run_id, campaign_id, run_ordinal, authoritative_run_id, proof_supervision_id
ON printer_memory_factory_campaign_runs
BEGIN SELECT RAISE(ABORT, 'campaign run identity is immutable'); END;
CREATE TRIGGER printer_campaign_cycle_identity_immutable
BEFORE UPDATE OF cycle_id, campaign_id, run_id, cycle_ordinal
ON printer_memory_factory_campaign_cycles
BEGIN SELECT RAISE(ABORT, 'campaign cycle identity is immutable'); END;
CREATE TRIGGER printer_campaign_slot_identity_immutable
BEFORE UPDATE OF token_slot_id, campaign_id, run_id, cycle_id, slot_ordinal,
    token_identity, token_row_id, mint_identity, pair_identity, pair_row_id,
    lifecycle_identity, tracking_queue_id, replacement_predecessor_slot_id
ON printer_memory_factory_campaign_token_slots
BEGIN SELECT RAISE(ABORT, 'campaign token slot identity is immutable'); END;
CREATE TRIGGER printer_campaign_window_identity_immutable
BEFORE UPDATE OF window_id, campaign_id, run_id, cycle_id, token_slot_id,
    token_row_id, pair_row_id, window_kind, root_15m_lifecycle_identity,
    predecessor_window_id, containing_main_window_id, memory_window_row_id,
    checkpoint_cutoff, support_only
ON printer_memory_factory_campaign_windows
BEGIN SELECT RAISE(ABORT, 'campaign window identity is immutable'); END;
CREATE TRIGGER printer_campaign_work_identity_immutable
BEFORE UPDATE OF scheduler_work_id, campaign_id, run_id, cycle_id,
    token_slot_id, window_id, work_intent, deadline_at, scheduler_job_id,
    source_request_id, source_response_id, source_failure_id
ON printer_memory_factory_campaign_scheduler_work
BEGIN SELECT RAISE(ABORT, 'campaign scheduler work identity is immutable'); END;
CREATE TRIGGER printer_campaign_object_immutable_update
BEFORE UPDATE ON printer_memory_factory_campaign_objects
BEGIN SELECT RAISE(ABORT, 'campaign object is immutable'); END;
CREATE TRIGGER printer_campaign_object_immutable_delete
BEFORE DELETE ON printer_memory_factory_campaign_objects
BEGIN SELECT RAISE(ABORT, 'campaign object is immutable'); END;
CREATE TRIGGER printer_campaign_report_object_immutable_update
BEFORE UPDATE ON printer_memory_factory_campaign_report_objects
BEGIN SELECT RAISE(ABORT, 'campaign report object link is immutable'); END;
CREATE TRIGGER printer_campaign_report_object_immutable_delete
BEFORE DELETE ON printer_memory_factory_campaign_report_objects
BEGIN SELECT RAISE(ABORT, 'campaign report object link is immutable'); END;

COMMIT;
