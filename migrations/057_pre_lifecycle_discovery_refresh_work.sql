PRAGMA foreign_keys = ON;

CREATE TABLE printer_pre_lifecycle_discovery_refresh_work (
    refresh_work_id TEXT PRIMARY KEY,
    wait_id TEXT NOT NULL UNIQUE,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    supervision_id TEXT NOT NULL,
    scheduler_job_id INTEGER NOT NULL UNIQUE,
    refresh_ordinal INTEGER NOT NULL CHECK (refresh_ordinal > 0),
    work_state TEXT NOT NULL CHECK (work_state IN ('RUNNING','SUCCEEDED','FAILED','CANCELLED')),
    work_deadline_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    terminal_at TEXT,
    first_terminal_cause TEXT,
    UNIQUE (campaign_id, run_id, cycle_id, refresh_ordinal),
    FOREIGN KEY (wait_id)
        REFERENCES printer_pre_lifecycle_discovery_refresh_waits(wait_id),
    FOREIGN KEY (scheduler_job_id)
        REFERENCES printer_scheduler_jobs(id)
);

CREATE UNIQUE INDEX idx_pre_lifecycle_refresh_work_one_active_scope
ON printer_pre_lifecycle_discovery_refresh_work(campaign_id, run_id, cycle_id)
WHERE work_state = 'RUNNING';

CREATE INDEX idx_pre_lifecycle_refresh_work_scope_state
ON printer_pre_lifecycle_discovery_refresh_work(campaign_id, run_id, cycle_id, work_state);

CREATE TRIGGER trg_pre_lifecycle_refresh_work_parent_claimed
BEFORE INSERT ON printer_pre_lifecycle_discovery_refresh_work
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM printer_pre_lifecycle_discovery_refresh_waits AS w
        WHERE w.wait_id = NEW.wait_id
          AND w.campaign_id = NEW.campaign_id
          AND w.run_id = NEW.run_id
          AND w.cycle_id = NEW.cycle_id
          AND w.supervision_id = NEW.supervision_id
          AND w.scheduler_job_id = NEW.scheduler_job_id
          AND w.refresh_ordinal = NEW.refresh_ordinal
          AND w.wait_state = 'CLAIMED'
    ) THEN RAISE(ABORT, 'PRE_LIFECYCLE_REFRESH_WORK_PARENT_NOT_EXACT_CLAIM') END;
END;

CREATE TRIGGER trg_pre_lifecycle_refresh_work_identity_immutable
BEFORE UPDATE OF wait_id, campaign_id, run_id, cycle_id, supervision_id,
                 scheduler_job_id, refresh_ordinal, work_deadline_at, created_at
ON printer_pre_lifecycle_discovery_refresh_work
BEGIN
    SELECT RAISE(ABORT, 'PRE_LIFECYCLE_REFRESH_WORK_IDENTITY_IMMUTABLE');
END;

CREATE TRIGGER trg_pre_lifecycle_refresh_work_no_terminal_reopen
BEFORE UPDATE OF work_state ON printer_pre_lifecycle_discovery_refresh_work
WHEN OLD.work_state IN ('SUCCEEDED','FAILED','CANCELLED')
 AND NEW.work_state <> OLD.work_state
BEGIN
    SELECT RAISE(ABORT, 'PRE_LIFECYCLE_REFRESH_WORK_TERMINAL_IMMUTABLE');
END;

CREATE TRIGGER trg_pre_lifecycle_refresh_work_terminal_shape
BEFORE UPDATE OF work_state, terminal_at, first_terminal_cause
ON printer_pre_lifecycle_discovery_refresh_work
WHEN NEW.work_state IN ('SUCCEEDED','FAILED','CANCELLED')
 AND (NEW.terminal_at IS NULL OR NEW.first_terminal_cause IS NULL OR trim(NEW.first_terminal_cause) = '')
BEGIN
    SELECT RAISE(ABORT, 'PRE_LIFECYCLE_REFRESH_WORK_TERMINAL_EVIDENCE_REQUIRED');
END;

CREATE TRIGGER trg_pre_lifecycle_refresh_work_first_terminal_cause_immutable
BEFORE UPDATE OF first_terminal_cause ON printer_pre_lifecycle_discovery_refresh_work
WHEN OLD.first_terminal_cause IS NOT NULL
 AND NEW.first_terminal_cause <> OLD.first_terminal_cause
BEGIN
    SELECT RAISE(ABORT, 'PRE_LIFECYCLE_REFRESH_WORK_FIRST_TERMINAL_CAUSE_IMMUTABLE');
END;
