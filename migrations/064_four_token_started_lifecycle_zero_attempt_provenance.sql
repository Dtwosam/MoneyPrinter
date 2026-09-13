-- V2-9.8B immutable provenance for a one-cycle terminal after Cycle-1
-- lifecycle execution has started but before any Cycle-2 attempt exists.
BEGIN IMMEDIATE;

CREATE TABLE printer_four_token_started_lifecycle_zero_attempt_terminal_provenance (
    campaign_id TEXT NOT NULL,
    campaign_run_id TEXT NOT NULL,
    authoritative_factory_run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    cycle_ordinal INTEGER NOT NULL CHECK (cycle_ordinal = 1),
    proposed_cycle_ordinal INTEGER NOT NULL CHECK (proposed_cycle_ordinal = 2),
    terminal_phase TEXT NOT NULL CHECK (
        terminal_phase = 'CYCLE1_LIFECYCLE_STARTED_PRE_CYCLE2_ATTEMPT'
    ),
    first_terminal_cause TEXT NOT NULL CHECK (
        length(trim(first_terminal_cause)) > 0
        AND first_terminal_cause <> 'COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED'
    ),
    recorded_at TEXT NOT NULL CHECK (length(trim(recorded_at)) > 0),
    PRIMARY KEY (
        campaign_id, campaign_run_id, authoritative_factory_run_id,
        proposed_cycle_ordinal
    ),
    FOREIGN KEY (campaign_id) REFERENCES printer_memory_factory_campaigns(campaign_id),
    FOREIGN KEY (campaign_run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_runs(run_id, campaign_id),
    FOREIGN KEY (authoritative_factory_run_id) REFERENCES printer_memory_factory_runs(run_id),
    FOREIGN KEY (cycle_id, campaign_run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_cycles(cycle_id, run_id, campaign_id)
);

CREATE TRIGGER printer_four_token_started_lifecycle_zero_attempt_provenance_exact_shape
BEFORE INSERT ON printer_four_token_started_lifecycle_zero_attempt_terminal_provenance
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_runs
        WHERE run_id = NEW.campaign_run_id AND campaign_id = NEW.campaign_id
          AND authoritative_run_id = NEW.authoritative_factory_run_id AND run_state = 'RUNNING'
    ) THEN RAISE(ABORT, 'four-token started-lifecycle provenance owner mismatch') END;
    SELECT CASE WHEN (SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles
        WHERE campaign_id = NEW.campaign_id AND run_id = NEW.campaign_run_id
    ) != 1 THEN RAISE(ABORT, 'four-token started-lifecycle provenance requires exactly one cycle') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_cycles
        WHERE cycle_id = NEW.cycle_id AND campaign_id = NEW.campaign_id
          AND run_id = NEW.campaign_run_id AND cycle_ordinal = 1
          AND cycle_state NOT LIKE 'TERMINAL_%'
    ) THEN RAISE(ABORT, 'four-token started-lifecycle provenance requires live Cycle 1') END;
    SELECT CASE WHEN (SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots
        WHERE campaign_id = NEW.campaign_id AND run_id = NEW.campaign_run_id
          AND cycle_id = NEW.cycle_id AND slot_ordinal IN (1,2)
          AND token_state = 'SELECTED' AND tracking_queue_id IS NOT NULL
    ) != 2 THEN RAISE(ABORT, 'four-token started-lifecycle provenance requires exact selected Cycle-1 slots') END;
    SELECT CASE WHEN EXISTS (SELECT 1 FROM printer_memory_factory_campaign_cycles
        WHERE campaign_id = NEW.campaign_id AND run_id = NEW.campaign_run_id AND cycle_ordinal = 2
    ) THEN RAISE(ABORT, 'four-token started-lifecycle provenance forbids Cycle 2') END;
    SELECT CASE WHEN EXISTS (SELECT 1 FROM printer_pre_admission_discovery_attempts
        WHERE campaign_id = NEW.campaign_id AND campaign_run_id = NEW.campaign_run_id
          AND authoritative_factory_run_id = NEW.authoritative_factory_run_id AND proposed_cycle_ordinal = 2
    ) THEN RAISE(ABORT, 'four-token started-lifecycle provenance forbids Cycle-2 attempt evidence') END;
    SELECT CASE WHEN EXISTS (SELECT 1 FROM printer_four_token_pre_lifecycle_terminal_provenance
        WHERE campaign_id = NEW.campaign_id AND campaign_run_id = NEW.campaign_run_id
          AND authoritative_factory_run_id = NEW.authoritative_factory_run_id AND proposed_cycle_ordinal = 2
    ) THEN RAISE(ABORT, 'four-token started-lifecycle provenance contradicts pre-lifecycle provenance') END;
    SELECT CASE WHEN EXISTS (SELECT 1 FROM printer_four_token_zero_attempt_terminal_provenance
        WHERE campaign_id = NEW.campaign_id AND campaign_run_id = NEW.campaign_run_id
          AND authoritative_factory_run_id = NEW.authoritative_factory_run_id AND proposed_cycle_ordinal = 2
    ) THEN RAISE(ABORT, 'four-token started-lifecycle provenance contradicts planned-lifecycle provenance') END;
    SELECT CASE WHEN (SELECT COUNT(*) FROM printer_memory_factory_campaign_windows
        WHERE campaign_id = NEW.campaign_id AND run_id = NEW.campaign_run_id AND cycle_id = NEW.cycle_id
    ) != 2 THEN RAISE(ABORT, 'four-token started-lifecycle provenance requires exact Cycle-1 windows') END;
    SELECT CASE WHEN EXISTS (SELECT 1 FROM printer_memory_factory_campaign_windows
        WHERE campaign_id = NEW.campaign_id AND run_id = NEW.campaign_run_id AND cycle_id = NEW.cycle_id
          AND (window_kind <> 'WINDOW_15M' OR window_state NOT IN ('PLANNED','COLLECTING','CLOSE_PENDING','AUDITING'))
    ) THEN RAISE(ABORT, 'four-token started-lifecycle provenance requires live 15m windows') END;
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_memory_factory_campaign_scheduler_work AS w
        JOIN printer_memory_factory_run_steps AS s
          ON s.scheduler_job_id = w.scheduler_job_id AND s.run_id = NEW.authoritative_factory_run_id
        WHERE w.campaign_id = NEW.campaign_id AND w.run_id = NEW.campaign_run_id
          AND w.cycle_id = NEW.cycle_id AND w.ownership_contract_version = 'V2_STAGE_SCOPED'
          AND w.work_scope = 'WINDOW_LIFECYCLE' AND w.stage_id = 'WINDOW_15M'
          AND s.step_kind = 'SNAPSHOT' AND s.started_at IS NOT NULL
    ) THEN RAISE(ABORT, 'four-token started-lifecycle provenance requires started lifecycle work') END;
END;

CREATE TRIGGER printer_four_token_started_lifecycle_zero_attempt_provenance_immutable_update
BEFORE UPDATE ON printer_four_token_started_lifecycle_zero_attempt_terminal_provenance
BEGIN SELECT RAISE(ABORT, 'four-token started-lifecycle provenance is immutable'); END;

CREATE TRIGGER printer_four_token_started_lifecycle_zero_attempt_provenance_immutable_delete
BEFORE DELETE ON printer_four_token_started_lifecycle_zero_attempt_terminal_provenance
BEGIN SELECT RAISE(ABORT, 'four-token started-lifecycle provenance is immutable'); END;

CREATE TRIGGER printer_pre_admission_attempt_forbids_started_lifecycle_zero_attempt_provenance
BEFORE INSERT ON printer_pre_admission_discovery_attempts
WHEN EXISTS (SELECT 1 FROM printer_four_token_started_lifecycle_zero_attempt_terminal_provenance AS p
    WHERE p.campaign_id = NEW.campaign_id AND p.campaign_run_id = NEW.campaign_run_id
      AND p.authoritative_factory_run_id = NEW.authoritative_factory_run_id
      AND p.proposed_cycle_ordinal = NEW.proposed_cycle_ordinal)
BEGIN SELECT RAISE(ABORT, 'pre-admission attempt contradicts started-lifecycle zero-attempt provenance'); END;

CREATE TRIGGER printer_pre_lifecycle_provenance_forbids_started_lifecycle_zero_attempt_provenance
BEFORE INSERT ON printer_four_token_pre_lifecycle_terminal_provenance
WHEN EXISTS (SELECT 1 FROM printer_four_token_started_lifecycle_zero_attempt_terminal_provenance AS p
    WHERE p.campaign_id = NEW.campaign_id AND p.campaign_run_id = NEW.campaign_run_id
      AND p.authoritative_factory_run_id = NEW.authoritative_factory_run_id
      AND p.proposed_cycle_ordinal = NEW.proposed_cycle_ordinal)
BEGIN SELECT RAISE(ABORT, 'pre-lifecycle provenance contradicts started-lifecycle zero-attempt provenance'); END;

CREATE TRIGGER printer_planned_lifecycle_provenance_forbids_started_lifecycle_zero_attempt_provenance
BEFORE INSERT ON printer_four_token_zero_attempt_terminal_provenance
WHEN EXISTS (SELECT 1 FROM printer_four_token_started_lifecycle_zero_attempt_terminal_provenance AS p
    WHERE p.campaign_id = NEW.campaign_id AND p.campaign_run_id = NEW.campaign_run_id
      AND p.authoritative_factory_run_id = NEW.authoritative_factory_run_id
      AND p.proposed_cycle_ordinal = NEW.proposed_cycle_ordinal)
BEGIN SELECT RAISE(ABORT, 'planned-lifecycle provenance contradicts started-lifecycle zero-attempt provenance'); END;

COMMIT;
