-- V2-9.7E.1: allow zero-slot PLANNED cycles to terminalize on insufficient-pool stop.
-- Root cause of pilot IntegrityError: printer_campaign_cycle_requires_two_slots
-- aborted any leave from PLANNED when slot_count <> 2, including TERMINAL_*.
-- Non-terminal transitions from PLANNED still require exactly two slots.

DROP TRIGGER IF EXISTS printer_campaign_cycle_requires_two_slots;

CREATE TRIGGER printer_campaign_cycle_requires_two_slots
BEFORE UPDATE OF cycle_state ON printer_memory_factory_campaign_cycles
WHEN OLD.cycle_state = 'PLANNED'
 AND NEW.cycle_state <> 'PLANNED'
 AND NEW.cycle_state NOT LIKE 'TERMINAL_%'
BEGIN
    SELECT CASE WHEN (
        SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots
        WHERE cycle_id = OLD.cycle_id
    ) <> 2 THEN RAISE(ABORT, 'campaign cycle requires exactly two token slots') END;
END;
