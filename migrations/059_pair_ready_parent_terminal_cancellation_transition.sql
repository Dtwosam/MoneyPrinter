-- V2-9.8B: allow the exact parent-terminal owner to revoke an unconsumed
-- frozen PAIR_READY admission authority without weakening any other durable
-- pre-admission transition.

BEGIN IMMEDIATE;

DROP TRIGGER printer_pre_admission_attempt_transition;

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
        (OLD.attempt_state = 'PAIR_READY' AND NEW.attempt_state IN (
            'CONSUMED', 'CANCELLED'
        ))
    ) THEN RAISE(ABORT, 'invalid pre-admission attempt transition') END;
END;

COMMIT;
