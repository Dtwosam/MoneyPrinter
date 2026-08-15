-- V2-9.8B immutable provenance for a legitimate Cycle-1 pre-lifecycle
-- terminal before any Cycle-2 pre-admission attempt exists.
BEGIN IMMEDIATE;

CREATE TABLE printer_four_token_pre_lifecycle_terminal_provenance (
    campaign_id TEXT NOT NULL,
    campaign_run_id TEXT NOT NULL,
    authoritative_factory_run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    cycle_ordinal INTEGER NOT NULL CHECK (cycle_ordinal = 1),
    proposed_cycle_ordinal INTEGER NOT NULL CHECK (proposed_cycle_ordinal = 2),
    terminal_phase TEXT NOT NULL CHECK (terminal_phase = 'CAMPAIGN_PRE_LIFECYCLE'),
    first_terminal_cause TEXT NOT NULL CHECK (length(trim(first_terminal_cause)) > 0),
    recorded_at TEXT NOT NULL CHECK (length(trim(recorded_at)) > 0),
    PRIMARY KEY (
        campaign_id, campaign_run_id, authoritative_factory_run_id,
        proposed_cycle_ordinal
    ),
    FOREIGN KEY (campaign_id)
        REFERENCES printer_memory_factory_campaigns(campaign_id),
    FOREIGN KEY (campaign_run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_runs(run_id, campaign_id),
    FOREIGN KEY (authoritative_factory_run_id)
        REFERENCES printer_memory_factory_runs(run_id),
    FOREIGN KEY (cycle_id, campaign_run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_cycles(cycle_id, run_id, campaign_id)
);

CREATE TRIGGER printer_four_token_pre_lifecycle_provenance_exact_shape
BEFORE INSERT ON printer_four_token_pre_lifecycle_terminal_provenance
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_runs
        WHERE run_id = NEW.campaign_run_id
          AND campaign_id = NEW.campaign_id
          AND authoritative_run_id = NEW.authoritative_factory_run_id
          AND run_state = 'RUNNING'
    ) THEN RAISE(ABORT, 'four-token pre-lifecycle provenance owner mismatch') END;

    SELECT CASE WHEN (
        SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles
        WHERE campaign_id = NEW.campaign_id AND run_id = NEW.campaign_run_id
    ) != 1 THEN RAISE(ABORT, 'four-token pre-lifecycle provenance requires exactly one cycle') END;

    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_cycles
        WHERE cycle_id = NEW.cycle_id
          AND campaign_id = NEW.campaign_id
          AND run_id = NEW.campaign_run_id
          AND cycle_ordinal = 1
          AND cycle_state NOT LIKE 'TERMINAL_%'
    ) THEN RAISE(ABORT, 'four-token pre-lifecycle provenance requires live Cycle 1') END;

    SELECT CASE WHEN (
        SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots
        WHERE campaign_id = NEW.campaign_id
          AND run_id = NEW.campaign_run_id
          AND cycle_id = NEW.cycle_id
    ) != 2 THEN RAISE(ABORT, 'four-token pre-lifecycle provenance requires exact Cycle-1 slots') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_cycles
        WHERE campaign_id = NEW.campaign_id
          AND run_id = NEW.campaign_run_id
          AND cycle_ordinal = 2
    ) THEN RAISE(ABORT, 'four-token pre-lifecycle provenance forbids Cycle 2') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM printer_pre_admission_discovery_attempts
        WHERE campaign_id = NEW.campaign_id
          AND campaign_run_id = NEW.campaign_run_id
          AND authoritative_factory_run_id = NEW.authoritative_factory_run_id
          AND proposed_cycle_ordinal = 2
    ) THEN RAISE(ABORT, 'four-token pre-lifecycle provenance forbids Cycle-2 attempt evidence') END;

    SELECT CASE WHEN EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_windows
        WHERE campaign_id = NEW.campaign_id
          AND run_id = NEW.campaign_run_id
          AND cycle_id = NEW.cycle_id
    ) THEN RAISE(ABORT, 'four-token pre-lifecycle provenance forbids lifecycle windows') END;
END;

CREATE TRIGGER printer_four_token_pre_lifecycle_provenance_immutable_update
BEFORE UPDATE ON printer_four_token_pre_lifecycle_terminal_provenance
BEGIN
    SELECT RAISE(ABORT, 'four-token pre-lifecycle provenance is immutable');
END;

CREATE TRIGGER printer_four_token_pre_lifecycle_provenance_immutable_delete
BEFORE DELETE ON printer_four_token_pre_lifecycle_terminal_provenance
BEGIN
    SELECT RAISE(ABORT, 'four-token pre-lifecycle provenance is immutable');
END;

CREATE TRIGGER printer_pre_admission_attempt_forbids_pre_lifecycle_provenance
BEFORE INSERT ON printer_pre_admission_discovery_attempts
WHEN EXISTS (
    SELECT 1 FROM printer_four_token_pre_lifecycle_terminal_provenance AS p
    WHERE p.campaign_id = NEW.campaign_id
      AND p.campaign_run_id = NEW.campaign_run_id
      AND p.authoritative_factory_run_id = NEW.authoritative_factory_run_id
      AND p.proposed_cycle_ordinal = NEW.proposed_cycle_ordinal
)
BEGIN
    SELECT RAISE(ABORT, 'pre-admission attempt contradicts pre-lifecycle provenance');
END;

CREATE TRIGGER printer_pre_admission_attempt_immutable_delete
BEFORE DELETE ON printer_pre_admission_discovery_attempts
BEGIN
    SELECT RAISE(ABORT, 'pre-admission attempt is immutable');
END;

COMMIT;
