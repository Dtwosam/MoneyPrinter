-- V2-9.8B: campaign Scheduler ownership scope schema migration.
--
-- Rebuilds printer_memory_factory_campaign_scheduler_work from a window-only
-- lifecycle table (V1_WINDOW_BOUND) into a single stage-scoped Scheduler
-- ownership authority that can also represent V2_STAGE_SCOPED discovery,
-- selection, first-15m handoff, and terminal cleanup work without fabricating a
-- window, slot, or factory run-step.
--
-- Historical rows are copied exactly and tagged V1_WINDOW_BOUND. New repaired
-- operational rows must be V2_STAGE_SCOPED. Historical V1 rows are never
-- upgraded into V2 proof merely because the schema was migrated.
--
-- Forward-only. Do NOT apply this migration to the authoritative database in the
-- implementation or disposable-proof lanes. The rebuild rolls back completely on
-- any duplicate-readiness, copy, invariant, foreign-key, integrity, or trigger
-- failure because COMMIT is reached only after every guard passes.

-- Foreign-key enforcement can only be toggled outside a transaction. Disable it
-- for the table rebuild and re-enable it after COMMIT. The pragma guards below
-- (pragma_foreign_key_check / pragma_integrity_check) re-verify integrity while
-- enforcement is off, so nothing is trusted silently.
PRAGMA foreign_keys = OFF;

BEGIN IMMEDIATE;

-- 1. Migration-readiness invariant: block on any existing duplicate non-null
--    Scheduler job ownership. Historical conflicts are not auto-repaired.
CREATE TEMP TABLE _mig050_guard_duplicate_job (ok INTEGER NOT NULL CHECK (ok = 1));
INSERT INTO _mig050_guard_duplicate_job(ok)
SELECT CASE WHEN NOT EXISTS (
    SELECT 1
    FROM printer_memory_factory_campaign_scheduler_work
    WHERE scheduler_job_id IS NOT NULL
    GROUP BY scheduler_job_id
    HAVING COUNT(*) > 1
) THEN 1 ELSE 0 END;

-- 2. Replacement table with the stage-scoped ownership contract.
CREATE TABLE printer_memory_factory_campaign_scheduler_work__v2_9_8b_050 (
    scheduler_work_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    token_slot_id TEXT,
    window_id TEXT,
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
    ownership_contract_version TEXT NOT NULL CHECK (
        ownership_contract_version IN ('V1_WINDOW_BOUND', 'V2_STAGE_SCOPED')
    ),
    stage_id TEXT,
    work_scope TEXT CHECK (
        work_scope IS NULL OR work_scope IN (
            'DISCOVERY_SELECTION', 'FIRST_15M_HANDOFF',
            'WINDOW_LIFECYCLE', 'TERMINAL_CLEANUP'
        )
    ),
    target_category TEXT,
    target_identity TEXT,
    factory_run_id TEXT,
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
    FOREIGN KEY (factory_run_id) REFERENCES printer_memory_factory_runs(run_id),
    -- Source provenance ordering (preserved from V2-9.7D.6B.1).
    CHECK (source_response_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_failure_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_response_id IS NULL OR source_failure_id IS NULL),
    -- Work-state / terminal-cause invariant (preserved).
    CHECK (
        (work_state IN ('PENDING', 'RUNNING', 'COOLDOWN')
            AND first_terminal_cause IS NULL AND terminal_at IS NULL)
        OR
        (work_state IN ('SUCCEEDED', 'FAILED', 'SKIPPED', 'CANCELLED')
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0 AND terminal_at IS NOT NULL)
    ),
    -- V1_WINDOW_BOUND: exact historical window-bound shape, no V2 identity.
    CHECK (
        ownership_contract_version <> 'V1_WINDOW_BOUND'
        OR (
            window_id IS NOT NULL AND token_slot_id IS NOT NULL
            AND work_scope IS NULL AND stage_id IS NULL
            AND target_category IS NULL AND target_identity IS NULL
            AND factory_run_id IS NULL
        )
    ),
    -- V2_STAGE_SCOPED: common mandatory identity for every repaired row.
    CHECK (
        ownership_contract_version <> 'V2_STAGE_SCOPED'
        OR (
            work_scope IS NOT NULL
            AND stage_id IS NOT NULL AND length(trim(stage_id)) > 0
            AND target_category IS NOT NULL AND length(trim(target_category)) > 0
            AND target_identity IS NOT NULL AND length(trim(target_identity)) > 0
            AND scheduler_job_id IS NOT NULL
        )
    ),
    -- WINDOW_LIFECYCLE: exact factory run, token slot, and window linkage.
    CHECK (
        NOT (ownership_contract_version = 'V2_STAGE_SCOPED'
             AND work_scope = 'WINDOW_LIFECYCLE')
        OR (
            factory_run_id IS NOT NULL
            AND token_slot_id IS NOT NULL
            AND window_id IS NOT NULL
        )
    ),
    -- FIRST_15M_HANDOFF: no fabricated window or factory run-step link.
    CHECK (
        NOT (ownership_contract_version = 'V2_STAGE_SCOPED'
             AND work_scope = 'FIRST_15M_HANDOFF')
        OR (window_id IS NULL AND factory_run_id IS NULL)
    ),
    -- DISCOVERY_SELECTION: no fabricated slot, window, or factory run-step link.
    CHECK (
        NOT (ownership_contract_version = 'V2_STAGE_SCOPED'
             AND work_scope = 'DISCOVERY_SELECTION')
        OR (window_id IS NULL AND token_slot_id IS NULL AND factory_run_id IS NULL)
    ),
    -- TERMINAL_CLEANUP: no fabricated window or factory run-step link.
    CHECK (
        NOT (ownership_contract_version = 'V2_STAGE_SCOPED'
             AND work_scope = 'TERMINAL_CLEANUP')
        OR (window_id IS NULL AND factory_run_id IS NULL)
    )
);

-- 3. Copy every historical row exactly and tag it V1_WINDOW_BOUND. No existing
--    identity, linkage, status, terminal cause, or timestamp is altered; the new
--    V2 columns are NULL for historical rows.
INSERT INTO printer_memory_factory_campaign_scheduler_work__v2_9_8b_050 (
    scheduler_work_id, campaign_id, run_id, cycle_id, token_slot_id, window_id,
    work_intent, deadline_at, work_state, scheduler_job_id, source_request_id,
    source_response_id, source_failure_id, ownership_contract_version,
    stage_id, work_scope, target_category, target_identity, factory_run_id,
    first_terminal_cause, terminal_at, created_at, updated_at
)
SELECT
    scheduler_work_id, campaign_id, run_id, cycle_id, token_slot_id, window_id,
    work_intent, deadline_at, work_state, scheduler_job_id, source_request_id,
    source_response_id, source_failure_id, 'V1_WINDOW_BOUND',
    NULL, NULL, NULL, NULL, NULL,
    first_terminal_cause, terminal_at, created_at, updated_at
FROM printer_memory_factory_campaign_scheduler_work;

-- 4. Row-count equality guard: no historical row added or lost.
CREATE TEMP TABLE _mig050_guard_rowcount (ok INTEGER NOT NULL CHECK (ok = 1));
INSERT INTO _mig050_guard_rowcount(ok)
SELECT CASE WHEN
    (SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work__v2_9_8b_050)
    = (SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work)
THEN 1 ELSE 0 END;

-- 5. Exact field-equality guard on every preserved column, both directions.
--    Compound EXCEPT treats NULLs as equal, so null source ids match exactly.
CREATE TEMP TABLE _mig050_guard_fields (ok INTEGER NOT NULL CHECK (ok = 1));
INSERT INTO _mig050_guard_fields(ok)
SELECT CASE WHEN
    NOT EXISTS (
        SELECT scheduler_work_id, campaign_id, run_id, cycle_id, token_slot_id,
               window_id, work_intent, deadline_at, work_state, scheduler_job_id,
               source_request_id, source_response_id, source_failure_id,
               first_terminal_cause, terminal_at, created_at, updated_at
        FROM printer_memory_factory_campaign_scheduler_work
        EXCEPT
        SELECT scheduler_work_id, campaign_id, run_id, cycle_id, token_slot_id,
               window_id, work_intent, deadline_at, work_state, scheduler_job_id,
               source_request_id, source_response_id, source_failure_id,
               first_terminal_cause, terminal_at, created_at, updated_at
        FROM printer_memory_factory_campaign_scheduler_work__v2_9_8b_050
    )
    AND NOT EXISTS (
        SELECT scheduler_work_id, campaign_id, run_id, cycle_id, token_slot_id,
               window_id, work_intent, deadline_at, work_state, scheduler_job_id,
               source_request_id, source_response_id, source_failure_id,
               first_terminal_cause, terminal_at, created_at, updated_at
        FROM printer_memory_factory_campaign_scheduler_work__v2_9_8b_050
        EXCEPT
        SELECT scheduler_work_id, campaign_id, run_id, cycle_id, token_slot_id,
               window_id, work_intent, deadline_at, work_state, scheduler_job_id,
               source_request_id, source_response_id, source_failure_id,
               first_terminal_cause, terminal_at, created_at, updated_at
        FROM printer_memory_factory_campaign_scheduler_work
    )
THEN 1 ELSE 0 END;

-- 6. Swap the rebuilt table into place.
DROP TABLE printer_memory_factory_campaign_scheduler_work;
ALTER TABLE printer_memory_factory_campaign_scheduler_work__v2_9_8b_050
    RENAME TO printer_memory_factory_campaign_scheduler_work;

-- 7. Recreate indexes, including the one-job-to-one-ownership partial unique.
CREATE INDEX idx_campaign_work_owner
    ON printer_memory_factory_campaign_scheduler_work(
        campaign_id, run_id, cycle_id, token_slot_id
    );
CREATE UNIQUE INDEX idx_campaign_work_scheduler_job_unique
    ON printer_memory_factory_campaign_scheduler_work(scheduler_job_id)
    WHERE scheduler_job_id IS NOT NULL;
CREATE INDEX idx_campaign_work_scope_stage
    ON printer_memory_factory_campaign_scheduler_work(
        campaign_id, work_scope, stage_id
    );

-- 8. Recreate the source-provenance insert trigger unchanged.
DROP TRIGGER IF EXISTS printer_campaign_work_provenance_insert;
CREATE TRIGGER printer_campaign_work_provenance_insert
BEFORE INSERT ON printer_memory_factory_campaign_scheduler_work
BEGIN
    SELECT CASE WHEN NEW.source_response_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM printer_source_responses
        WHERE id = NEW.source_response_id
          AND source_request_id = NEW.source_request_id
    ) THEN RAISE(ABORT, 'source response provenance mismatch') END;
END;

-- 9. Recreate the amended immutability trigger. Base identity, ownership
--    contract, scope, stage, target, and factory-run linkage are immutable;
--    scheduler and source ids remain immutable once bound (from 047).
DROP TRIGGER IF EXISTS printer_campaign_work_identity_immutable;
CREATE TRIGGER printer_campaign_work_identity_immutable
BEFORE UPDATE OF scheduler_work_id, campaign_id, run_id, cycle_id,
    token_slot_id, window_id, work_intent, deadline_at, scheduler_job_id,
    source_request_id, source_response_id, source_failure_id,
    ownership_contract_version, stage_id, work_scope, target_category,
    target_identity, factory_run_id
ON printer_memory_factory_campaign_scheduler_work
BEGIN
    SELECT CASE
        WHEN OLD.scheduler_work_id IS NOT NEW.scheduler_work_id
          OR OLD.campaign_id IS NOT NEW.campaign_id
          OR OLD.run_id IS NOT NEW.run_id
          OR OLD.cycle_id IS NOT NEW.cycle_id
          OR OLD.token_slot_id IS NOT NEW.token_slot_id
          OR OLD.window_id IS NOT NEW.window_id
          OR OLD.work_intent IS NOT NEW.work_intent
          OR OLD.deadline_at IS NOT NEW.deadline_at
          OR OLD.ownership_contract_version IS NOT NEW.ownership_contract_version
          OR OLD.stage_id IS NOT NEW.stage_id
          OR OLD.work_scope IS NOT NEW.work_scope
          OR OLD.target_category IS NOT NEW.target_category
          OR OLD.target_identity IS NOT NEW.target_identity
          OR OLD.factory_run_id IS NOT NEW.factory_run_id
        THEN RAISE(ABORT, 'campaign scheduler work identity is immutable')
    END;
    SELECT CASE
        WHEN OLD.scheduler_job_id IS NOT NULL
         AND OLD.scheduler_job_id IS NOT NEW.scheduler_job_id
        THEN RAISE(ABORT, 'scheduler_job_id is immutable once bound')
    END;
    SELECT CASE
        WHEN OLD.source_request_id IS NOT NULL
         AND OLD.source_request_id IS NOT NEW.source_request_id
        THEN RAISE(ABORT, 'source_request_id is immutable once bound')
    END;
    SELECT CASE
        WHEN OLD.source_response_id IS NOT NULL
         AND OLD.source_response_id IS NOT NEW.source_response_id
        THEN RAISE(ABORT, 'source_response_id is immutable once bound')
    END;
    SELECT CASE
        WHEN OLD.source_failure_id IS NOT NULL
         AND OLD.source_failure_id IS NOT NEW.source_failure_id
        THEN RAISE(ABORT, 'source_failure_id is immutable once bound')
    END;
END;

-- 10. Post-rebuild integrity guards while enforcement is off.
CREATE TEMP TABLE _mig050_guard_foreign_keys (ok INTEGER NOT NULL CHECK (ok = 1));
INSERT INTO _mig050_guard_foreign_keys(ok)
SELECT CASE WHEN NOT EXISTS (
    SELECT 1 FROM pragma_foreign_key_check
) THEN 1 ELSE 0 END;

CREATE TEMP TABLE _mig050_guard_integrity (ok INTEGER NOT NULL CHECK (ok = 1));
INSERT INTO _mig050_guard_integrity(ok)
SELECT CASE WHEN (
    SELECT COUNT(*) FROM pragma_integrity_check WHERE integrity_check <> 'ok'
) = 0 THEN 1 ELSE 0 END;

-- 11. Drop disposable guard scaffolding and commit only if every guard passed.
DROP TABLE _mig050_guard_duplicate_job;
DROP TABLE _mig050_guard_rowcount;
DROP TABLE _mig050_guard_fields;
DROP TABLE _mig050_guard_foreign_keys;
DROP TABLE _mig050_guard_integrity;

COMMIT;

PRAGMA foreign_keys = ON;
