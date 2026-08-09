-- V2-9.8B Post-DTW98: pre-lifecycle discovery-refresh wait ownership.
--
-- Adds exactly one narrow table so a future-dated PENDING DISCOVERY_REFRESH
-- Scheduler job is attributable to its exact campaign/run/cycle *before* it
-- becomes due, without creating discovery work ahead of the claim.
--
-- The approved claim-at-work-start law is unchanged:
--   enqueue -> due -> exact Scheduler claim -> discovery work RUNNING ->
--   governed work -> terminalization.
--
-- A WAITING row is ownership evidence only. It carries no source payload, no
-- ranking, no score, no confidence, no weight and no financial field. It never
-- authorizes source work, and it never substitutes for printer_discovery_work.
--
-- Forward-only and purely additive: no existing table, index, trigger or row is
-- read, rebuilt, altered or dropped. Do NOT apply this migration to the
-- authoritative database in the implementation or focused-proof lanes.

BEGIN IMMEDIATE;

CREATE TABLE printer_pre_lifecycle_discovery_refresh_waits (
    wait_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    supervision_id TEXT NOT NULL,
    scheduler_job_id INTEGER NOT NULL UNIQUE,
    refresh_ordinal INTEGER NOT NULL CHECK (refresh_ordinal > 0),
    wait_state TEXT NOT NULL CHECK (
        wait_state IN ('WAITING', 'CLAIMED', 'SUCCEEDED', 'FAILED', 'CANCELLED')
    ),
    scheduled_for TEXT NOT NULL,
    acquisition_deadline_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    terminal_at TEXT,
    first_terminal_cause TEXT,

    -- One row per exact campaign/run/cycle/refresh ordinal, and (via the
    -- column-level UNIQUE above) one row per Scheduler job.
    UNIQUE (campaign_id, run_id, cycle_id, refresh_ordinal),

    CHECK (length(trim(wait_id)) > 0),
    CHECK (length(trim(campaign_id)) > 0),
    CHECK (length(trim(run_id)) > 0),
    CHECK (length(trim(cycle_id)) > 0),
    CHECK (length(trim(supervision_id)) > 0),
    CHECK (length(trim(scheduled_for)) > 0),
    CHECK (length(trim(acquisition_deadline_at)) > 0),

    -- Terminal-consistency invariant, matching the existing discovery-work and
    -- campaign-scheduler-work contracts.
    CHECK (
        (wait_state IN ('WAITING', 'CLAIMED')
            AND terminal_at IS NULL AND first_terminal_cause IS NULL)
        OR
        (wait_state IN ('SUCCEEDED', 'FAILED', 'CANCELLED')
            AND terminal_at IS NOT NULL
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0)
    ),

    FOREIGN KEY (scheduler_job_id) REFERENCES printer_scheduler_jobs(id)
);

-- Exact-campaign active-work accounting and terminal cleanup capture read the
-- waits by campaign scope and by Scheduler job.
CREATE INDEX idx_pre_lifecycle_refresh_wait_scope
    ON printer_pre_lifecycle_discovery_refresh_waits(
        campaign_id, run_id, cycle_id, wait_state
    );
CREATE INDEX idx_pre_lifecycle_refresh_wait_job
    ON printer_pre_lifecycle_discovery_refresh_waits(scheduler_job_id);

-- Identity is immutable once written. Only the wait lifecycle columns
-- (wait_state, updated_at, terminal_at, first_terminal_cause) may change, and a
-- recorded first terminal cause is never rewritten.
CREATE TRIGGER printer_pre_lifecycle_refresh_wait_identity_immutable
BEFORE UPDATE OF wait_id, campaign_id, run_id, cycle_id, supervision_id,
    scheduler_job_id, refresh_ordinal, scheduled_for, acquisition_deadline_at,
    created_at, first_terminal_cause
ON printer_pre_lifecycle_discovery_refresh_waits
BEGIN
    SELECT CASE
        WHEN OLD.wait_id IS NOT NEW.wait_id
          OR OLD.campaign_id IS NOT NEW.campaign_id
          OR OLD.run_id IS NOT NEW.run_id
          OR OLD.cycle_id IS NOT NEW.cycle_id
          OR OLD.supervision_id IS NOT NEW.supervision_id
          OR OLD.scheduler_job_id IS NOT NEW.scheduler_job_id
          OR OLD.refresh_ordinal IS NOT NEW.refresh_ordinal
          OR OLD.scheduled_for IS NOT NEW.scheduled_for
          OR OLD.acquisition_deadline_at IS NOT NEW.acquisition_deadline_at
          OR OLD.created_at IS NOT NEW.created_at
        THEN RAISE(ABORT, 'pre-lifecycle refresh wait identity is immutable')
    END;
    SELECT CASE
        WHEN OLD.first_terminal_cause IS NOT NULL
         AND OLD.first_terminal_cause IS NOT NEW.first_terminal_cause
        THEN RAISE(ABORT, 'first_terminal_cause is immutable once recorded')
    END;
END;

-- A terminalized wait never returns to an active state.
CREATE TRIGGER printer_pre_lifecycle_refresh_wait_no_terminal_reopen
BEFORE UPDATE OF wait_state
ON printer_pre_lifecycle_discovery_refresh_waits
BEGIN
    SELECT CASE
        WHEN OLD.wait_state IN ('SUCCEEDED', 'FAILED', 'CANCELLED')
         AND NEW.wait_state IS NOT OLD.wait_state
        THEN RAISE(ABORT, 'terminal pre-lifecycle refresh wait cannot reopen')
    END;
    SELECT CASE
        WHEN OLD.wait_state = 'CLAIMED' AND NEW.wait_state = 'WAITING'
        THEN RAISE(ABORT, 'claimed pre-lifecycle refresh wait cannot unclaim')
    END;
END;

COMMIT;
