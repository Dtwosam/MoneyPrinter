-- V2-9.8B Lane 3: durable post-1h Standard-4H progression aggregate.
-- Forward-only and inference-free. Historical campaigns are not backfilled.

BEGIN IMMEDIATE;

CREATE TABLE printer_memory_factory_standard_4h_progression_attempts (
    progression_attempt_id TEXT PRIMARY KEY NOT NULL,
    campaign_id TEXT NOT NULL,
    configuration_id TEXT NOT NULL,
    campaign_run_id TEXT NOT NULL,
    factory_run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    policy_version TEXT NOT NULL CHECK (
        policy_version = 'STANDARD_4H_PROGRESSION_V1'
    ),
    attempt_state TEXT NOT NULL CHECK (attempt_state IN (
        'WAITING_FOR_PREDECESSORS', 'EVALUATING', 'ELIGIBILITY_COMPLETE',
        'HANDOFF_COMMITTED', 'TERMINAL_FAILED', 'TERMINAL_CANCELLED',
        'INTERRUPTED_REVIEW'
    )),
    authority_evidence_json TEXT NOT NULL CHECK (
        json_valid(authority_evidence_json) = 1
        AND json_type(authority_evidence_json) = 'object'
    ),
    first_terminal_cause TEXT,
    fault_details_json TEXT NOT NULL CHECK (
        json_valid(fault_details_json) = 1
        AND json_type(fault_details_json) = 'object'
        AND json_type(fault_details_json, '$.secondary') = 'array'
        AND (
            json_type(fault_details_json, '$.primary') = 'null'
            OR json_type(fault_details_json, '$.primary') = 'object'
        )
        AND (
            json_type(fault_details_json, '$.primary') = 'null'
            OR (
                coalesce(json_type(
                    fault_details_json, '$.primary.cause'
                ), 'missing') = 'text'
                AND length(trim(json_extract(
                    fault_details_json, '$.primary.cause'
                ))) > 0
                AND coalesce(json_type(
                    fault_details_json, '$.primary.scope'
                ), 'missing') = 'text'
                AND coalesce(json_type(
                    fault_details_json, '$.primary.stage'
                ), 'missing') = 'text'
                AND coalesce(json_type(
                    fault_details_json, '$.primary.safe_message'
                ), 'missing') = 'text'
                AND coalesce(json_type(
                    fault_details_json, '$.primary.observed_at'
                ), 'missing') = 'text'
                AND coalesce(json_type(
                    fault_details_json, '$.primary.exception_class'
                ), 'missing') IN ('text', 'null')
                AND coalesce(json_type(
                    fault_details_json, '$.primary.source_reference'
                ), 'missing') IN ('text', 'null')
            )
        )
        AND (
            (first_terminal_cause IS NULL
             AND json_type(fault_details_json, '$.primary') = 'null')
            OR
            (first_terminal_cause IS NOT NULL
             AND length(trim(first_terminal_cause)) > 0
             AND json_extract(fault_details_json, '$.primary.cause')
                 = first_terminal_cause)
        )
    ),
    eligibility_completed_at TEXT,
    handoff_committed_at TEXT,
    terminal_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (campaign_id, campaign_run_id, cycle_id),
    UNIQUE (
        progression_attempt_id, campaign_id, campaign_run_id, cycle_id,
        factory_run_id
    ),
    FOREIGN KEY (configuration_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_configurations(
            configuration_id, campaign_id
        ),
    FOREIGN KEY (campaign_run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_runs(run_id, campaign_id),
    FOREIGN KEY (cycle_id, campaign_run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_cycles(
            cycle_id, run_id, campaign_id
        ),
    FOREIGN KEY (factory_run_id)
        REFERENCES printer_memory_factory_runs(run_id),
    CHECK (
        (attempt_state IN (
            'WAITING_FOR_PREDECESSORS', 'EVALUATING', 'ELIGIBILITY_COMPLETE'
         )
         AND first_terminal_cause IS NULL
         AND terminal_at IS NULL
         AND handoff_committed_at IS NULL)
        OR
        (attempt_state = 'HANDOFF_COMMITTED'
         AND first_terminal_cause IS NULL
         AND handoff_committed_at IS NOT NULL
         AND terminal_at IS NOT NULL)
        OR
        (attempt_state IN (
            'TERMINAL_FAILED', 'TERMINAL_CANCELLED', 'INTERRUPTED_REVIEW'
         )
         AND first_terminal_cause IS NOT NULL
         AND terminal_at IS NOT NULL
         AND handoff_committed_at IS NULL)
    ),
    CHECK (
        (attempt_state = 'ELIGIBILITY_COMPLETE'
         AND eligibility_completed_at IS NOT NULL)
        OR attempt_state <> 'ELIGIBILITY_COMPLETE'
    )
);

CREATE TABLE printer_memory_factory_standard_4h_progression_tokens (
    progression_token_id TEXT PRIMARY KEY NOT NULL,
    progression_attempt_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    campaign_run_id TEXT NOT NULL,
    factory_run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    slot_ordinal INTEGER NOT NULL CHECK (slot_ordinal IN (1, 2)),
    token_slot_id TEXT NOT NULL,
    token_identity TEXT NOT NULL,
    token_row_id INTEGER NOT NULL,
    mint_identity TEXT NOT NULL,
    pair_identity TEXT NOT NULL,
    pair_row_id INTEGER NOT NULL,
    lifecycle_identity TEXT NOT NULL,
    tracking_queue_id INTEGER NOT NULL,
    tracking_lane TEXT NOT NULL CHECK (
        tracking_lane IN ('TRACK_FAST', 'TRACK_NORMAL')
    ),
    predecessor_window_1h_id TEXT,
    predecessor_memory_window_id INTEGER,
    token_disposition TEXT NOT NULL CHECK (token_disposition IN (
        'WAITING_FOR_PREDECESSOR', 'ELIGIBLE_PENDING_HANDOFF',
        'INELIGIBLE', 'HANDOFF_CREATED', 'TERMINAL_FAILED'
    )),
    disposition_reasons_json TEXT NOT NULL CHECK (
        json_valid(disposition_reasons_json) = 1
        AND json_type(disposition_reasons_json) = 'array'
    ),
    eligibility_evidence_json TEXT NOT NULL CHECK (
        json_valid(eligibility_evidence_json) = 1
        AND json_type(eligibility_evidence_json) = 'object'
    ),
    successor_window_4h_id TEXT,
    first_terminal_cause TEXT,
    fault_details_json TEXT NOT NULL CHECK (
        json_valid(fault_details_json) = 1
        AND json_type(fault_details_json) = 'object'
        AND json_type(fault_details_json, '$.secondary') = 'array'
        AND (
            json_type(fault_details_json, '$.primary') = 'null'
            OR json_type(fault_details_json, '$.primary') = 'object'
        )
        AND (
            json_type(fault_details_json, '$.primary') = 'null'
            OR (
                coalesce(json_type(
                    fault_details_json, '$.primary.cause'
                ), 'missing') = 'text'
                AND length(trim(json_extract(
                    fault_details_json, '$.primary.cause'
                ))) > 0
                AND coalesce(json_type(
                    fault_details_json, '$.primary.scope'
                ), 'missing') = 'text'
                AND coalesce(json_type(
                    fault_details_json, '$.primary.stage'
                ), 'missing') = 'text'
                AND coalesce(json_type(
                    fault_details_json, '$.primary.safe_message'
                ), 'missing') = 'text'
                AND coalesce(json_type(
                    fault_details_json, '$.primary.observed_at'
                ), 'missing') = 'text'
                AND coalesce(json_type(
                    fault_details_json, '$.primary.exception_class'
                ), 'missing') IN ('text', 'null')
                AND coalesce(json_type(
                    fault_details_json, '$.primary.source_reference'
                ), 'missing') IN ('text', 'null')
            )
        )
        AND (
            (first_terminal_cause IS NULL
             AND json_type(fault_details_json, '$.primary') = 'null')
            OR
            (first_terminal_cause IS NOT NULL
             AND length(trim(first_terminal_cause)) > 0
             AND json_extract(fault_details_json, '$.primary.cause')
                 = first_terminal_cause)
        )
    ),
    evaluated_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (progression_attempt_id, slot_ordinal),
    UNIQUE (progression_attempt_id, token_slot_id),
    UNIQUE (progression_token_id, progression_attempt_id),
    FOREIGN KEY (
        progression_attempt_id, campaign_id, campaign_run_id, cycle_id,
        factory_run_id
    ) REFERENCES printer_memory_factory_standard_4h_progression_attempts(
        progression_attempt_id, campaign_id, campaign_run_id, cycle_id,
        factory_run_id
    ),
    FOREIGN KEY (token_slot_id, cycle_id, campaign_run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_token_slots(
            token_slot_id, cycle_id, run_id, campaign_id
        ),
    FOREIGN KEY (token_row_id) REFERENCES printer_tokens(id),
    FOREIGN KEY (pair_row_id) REFERENCES printer_pairs(id),
    FOREIGN KEY (tracking_queue_id) REFERENCES printer_tracking_queue(id),
    FOREIGN KEY (
        predecessor_window_1h_id, token_slot_id, cycle_id,
        campaign_run_id, campaign_id
    ) REFERENCES printer_memory_factory_campaign_windows(
        window_id, token_slot_id, cycle_id, run_id, campaign_id
    ),
    FOREIGN KEY (predecessor_memory_window_id)
        REFERENCES printer_memory_windows(id),
    FOREIGN KEY (
        successor_window_4h_id, token_slot_id, cycle_id,
        campaign_run_id, campaign_id
    ) REFERENCES printer_memory_factory_campaign_windows(
        window_id, token_slot_id, cycle_id, run_id, campaign_id
    ),
    CHECK (
        (token_disposition = 'WAITING_FOR_PREDECESSOR'
         AND evaluated_at IS NULL
         AND successor_window_4h_id IS NULL
         AND first_terminal_cause IS NULL)
        OR
        (token_disposition = 'ELIGIBLE_PENDING_HANDOFF'
         AND evaluated_at IS NOT NULL
         AND predecessor_window_1h_id IS NOT NULL
         AND predecessor_memory_window_id IS NOT NULL
         AND successor_window_4h_id IS NULL
         AND first_terminal_cause IS NULL)
        OR
        (token_disposition = 'INELIGIBLE'
         AND evaluated_at IS NOT NULL
         AND successor_window_4h_id IS NULL
         AND first_terminal_cause IS NULL)
        OR
        (token_disposition = 'HANDOFF_CREATED'
         AND evaluated_at IS NOT NULL
         AND predecessor_window_1h_id IS NOT NULL
         AND predecessor_memory_window_id IS NOT NULL
         AND successor_window_4h_id IS NOT NULL
         AND first_terminal_cause IS NULL)
        OR
        (token_disposition = 'TERMINAL_FAILED'
         AND evaluated_at IS NOT NULL
         AND successor_window_4h_id IS NULL
         AND first_terminal_cause IS NOT NULL)
    )
);

CREATE INDEX idx_standard_4h_progression_attempt_scope
    ON printer_memory_factory_standard_4h_progression_attempts(
        campaign_id, campaign_run_id, cycle_id, attempt_state
    );
CREATE INDEX idx_standard_4h_progression_token_disposition
    ON printer_memory_factory_standard_4h_progression_tokens(
        progression_attempt_id, token_disposition, slot_ordinal
    );
CREATE INDEX idx_standard_4h_progression_successor
    ON printer_memory_factory_standard_4h_progression_tokens(
        successor_window_4h_id
    ) WHERE successor_window_4h_id IS NOT NULL;

CREATE TRIGGER printer_standard_4h_progression_attempt_identity_immutable
BEFORE UPDATE OF progression_attempt_id, campaign_id, configuration_id,
    campaign_run_id, factory_run_id, cycle_id, policy_version, created_at
ON printer_memory_factory_standard_4h_progression_attempts
BEGIN SELECT RAISE(ABORT, 'standard 4h progression attempt identity is immutable'); END;

CREATE TRIGGER printer_standard_4h_progression_attempt_terminal_immutable
BEFORE UPDATE OF attempt_state, first_terminal_cause, eligibility_completed_at,
    handoff_committed_at, terminal_at, authority_evidence_json
ON printer_memory_factory_standard_4h_progression_attempts
WHEN OLD.attempt_state IN (
    'HANDOFF_COMMITTED', 'TERMINAL_FAILED', 'TERMINAL_CANCELLED',
    'INTERRUPTED_REVIEW'
)
BEGIN SELECT RAISE(ABORT, 'standard 4h progression attempt terminal state is immutable'); END;

CREATE TRIGGER printer_standard_4h_progression_attempt_primary_immutable
BEFORE UPDATE OF first_terminal_cause, fault_details_json
ON printer_memory_factory_standard_4h_progression_attempts
WHEN OLD.first_terminal_cause IS NOT NULL AND (
    NEW.first_terminal_cause IS NOT OLD.first_terminal_cause
    OR json_extract(NEW.fault_details_json, '$.primary')
       IS NOT json_extract(OLD.fault_details_json, '$.primary')
)
BEGIN SELECT RAISE(ABORT, 'standard 4h progression attempt primary fault is immutable'); END;

CREATE TRIGGER printer_standard_4h_progression_attempt_authority_immutable
BEFORE UPDATE OF authority_evidence_json
ON printer_memory_factory_standard_4h_progression_attempts
WHEN OLD.attempt_state NOT IN ('WAITING_FOR_PREDECESSORS', 'EVALUATING')
 AND NEW.authority_evidence_json IS NOT OLD.authority_evidence_json
BEGIN SELECT RAISE(ABORT, 'standard 4h progression authority evidence is immutable'); END;

CREATE TRIGGER printer_standard_4h_progression_token_identity_immutable
BEFORE UPDATE OF progression_token_id, progression_attempt_id, campaign_id,
    campaign_run_id, factory_run_id, cycle_id, slot_ordinal, token_slot_id,
    token_identity, token_row_id, mint_identity, pair_identity, pair_row_id,
    lifecycle_identity, tracking_queue_id, tracking_lane, created_at
ON printer_memory_factory_standard_4h_progression_tokens
BEGIN SELECT RAISE(ABORT, 'standard 4h progression token identity is immutable'); END;

CREATE TRIGGER printer_standard_4h_progression_token_terminal_immutable
BEFORE UPDATE OF token_disposition, predecessor_memory_window_id,
    successor_window_4h_id, first_terminal_cause, evaluated_at,
    disposition_reasons_json, eligibility_evidence_json
ON printer_memory_factory_standard_4h_progression_tokens
WHEN OLD.token_disposition IN ('INELIGIBLE', 'HANDOFF_CREATED', 'TERMINAL_FAILED')
BEGIN SELECT RAISE(ABORT, 'standard 4h progression token terminal disposition is immutable'); END;

CREATE TRIGGER printer_standard_4h_progression_token_primary_immutable
BEFORE UPDATE OF first_terminal_cause, fault_details_json
ON printer_memory_factory_standard_4h_progression_tokens
WHEN OLD.first_terminal_cause IS NOT NULL AND (
    NEW.first_terminal_cause IS NOT OLD.first_terminal_cause
    OR json_extract(NEW.fault_details_json, '$.primary')
       IS NOT json_extract(OLD.fault_details_json, '$.primary')
)
BEGIN SELECT RAISE(ABORT, 'standard 4h progression token primary fault is immutable'); END;

CREATE TRIGGER printer_standard_4h_progression_token_evidence_immutable
BEFORE UPDATE OF disposition_reasons_json, eligibility_evidence_json,
    predecessor_memory_window_id
ON printer_memory_factory_standard_4h_progression_tokens
WHEN OLD.token_disposition <> 'WAITING_FOR_PREDECESSOR' AND (
    NEW.disposition_reasons_json IS NOT OLD.disposition_reasons_json
    OR NEW.eligibility_evidence_json IS NOT OLD.eligibility_evidence_json
    OR NEW.predecessor_memory_window_id IS NOT OLD.predecessor_memory_window_id
)
BEGIN SELECT RAISE(ABORT, 'standard 4h progression token evaluation is immutable'); END;

COMMIT;
