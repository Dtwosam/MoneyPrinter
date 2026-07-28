-- V2-9.8B operational selective 1h: one-shot campaign linkage binds.
-- Campaign runs are created before the factory UUID exists. Allow binding
-- authoritative_run_id exactly once when currently NULL. Same for late
-- memory_window_row_id and scheduler/source provenance ids on graph rows.
-- True identity columns remain immutable. Forward-only; do not apply to the
-- live authoritative DB in this implementation lane.

BEGIN IMMEDIATE;

DROP TRIGGER IF EXISTS printer_campaign_run_identity_immutable;
CREATE TRIGGER printer_campaign_run_identity_immutable
BEFORE UPDATE OF run_id, campaign_id, run_ordinal, authoritative_run_id, proof_supervision_id
ON printer_memory_factory_campaign_runs
BEGIN
    SELECT CASE
        WHEN OLD.run_id IS NOT NEW.run_id
          OR OLD.campaign_id IS NOT NEW.campaign_id
          OR OLD.run_ordinal IS NOT NEW.run_ordinal
          OR (
                OLD.proof_supervision_id IS NOT NEW.proof_supervision_id
                AND NOT (
                    OLD.proof_supervision_id IS NULL
                    AND NEW.proof_supervision_id IS NOT NULL
                )
             )
        THEN RAISE(ABORT, 'campaign run identity is immutable')
    END;
    SELECT CASE
        WHEN OLD.authoritative_run_id IS NOT NULL
         AND (
                OLD.authoritative_run_id IS NOT NEW.authoritative_run_id
             )
        THEN RAISE(ABORT, 'authoritative_run_id is immutable once bound')
    END;
    SELECT CASE
        WHEN OLD.authoritative_run_id IS NULL
         AND NEW.authoritative_run_id IS NOT NULL
         AND NOT EXISTS (
                SELECT 1 FROM printer_memory_factory_runs
                WHERE run_id = NEW.authoritative_run_id
             )
        THEN RAISE(ABORT, 'authoritative_run_id must reference a factory run')
    END;
END;

DROP TRIGGER IF EXISTS printer_campaign_window_identity_immutable;
CREATE TRIGGER printer_campaign_window_identity_immutable
BEFORE UPDATE OF window_id, campaign_id, run_id, cycle_id, token_slot_id,
    token_row_id, pair_row_id, window_kind, root_15m_lifecycle_identity,
    predecessor_window_id, containing_main_window_id, memory_window_row_id,
    checkpoint_cutoff, support_only
ON printer_memory_factory_campaign_windows
BEGIN
    SELECT CASE
        WHEN OLD.window_id IS NOT NEW.window_id
          OR OLD.campaign_id IS NOT NEW.campaign_id
          OR OLD.run_id IS NOT NEW.run_id
          OR OLD.cycle_id IS NOT NEW.cycle_id
          OR OLD.token_slot_id IS NOT NEW.token_slot_id
          OR OLD.token_row_id IS NOT NEW.token_row_id
          OR OLD.pair_row_id IS NOT NEW.pair_row_id
          OR OLD.window_kind IS NOT NEW.window_kind
          OR OLD.root_15m_lifecycle_identity IS NOT NEW.root_15m_lifecycle_identity
          OR OLD.predecessor_window_id IS NOT NEW.predecessor_window_id
          OR OLD.containing_main_window_id IS NOT NEW.containing_main_window_id
          OR OLD.checkpoint_cutoff IS NOT NEW.checkpoint_cutoff
          OR OLD.support_only IS NOT NEW.support_only
        THEN RAISE(ABORT, 'campaign window identity is immutable')
    END;
    SELECT CASE
        WHEN OLD.memory_window_row_id IS NOT NULL
         AND OLD.memory_window_row_id IS NOT NEW.memory_window_row_id
        THEN RAISE(ABORT, 'memory_window_row_id is immutable once bound')
    END;
END;

DROP TRIGGER IF EXISTS printer_campaign_work_identity_immutable;
CREATE TRIGGER printer_campaign_work_identity_immutable
BEFORE UPDATE OF scheduler_work_id, campaign_id, run_id, cycle_id,
    token_slot_id, window_id, work_intent, deadline_at, scheduler_job_id,
    source_request_id, source_response_id, source_failure_id
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

COMMIT;
