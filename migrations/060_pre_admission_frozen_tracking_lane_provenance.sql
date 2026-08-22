-- V2-9.8B Design Lane 1 cadence-authority provenance amendment.
-- Additive only: freeze exact TRACK_FAST/TRACK_NORMAL + provenance onto
-- pre-admission attempt items at PAIR_READY. Do not edit migration 055.
-- Historical rows retain NULL frozen fields and are non-reusable for admit.

BEGIN IMMEDIATE;

ALTER TABLE printer_pre_admission_discovery_attempt_items
    ADD COLUMN frozen_tracking_lane TEXT
    CHECK (
        frozen_tracking_lane IS NULL
        OR frozen_tracking_lane IN ('TRACK_FAST', 'TRACK_NORMAL')
    );

ALTER TABLE printer_pre_admission_discovery_attempt_items
    ADD COLUMN frozen_discovery_action TEXT
    CHECK (
        frozen_discovery_action IS NULL
        OR frozen_discovery_action IN ('TRACK_FAST', 'TRACK_NORMAL')
    );

ALTER TABLE printer_pre_admission_discovery_attempt_items
    ADD COLUMN frozen_discovery_label TEXT;

ALTER TABLE printer_pre_admission_discovery_attempt_items
    ADD COLUMN frozen_classification_reason TEXT;

ALTER TABLE printer_pre_admission_discovery_attempt_items
    ADD COLUMN frozen_lane_evidence_hash TEXT
    CHECK (
        frozen_lane_evidence_hash IS NULL
        OR (
            length(frozen_lane_evidence_hash) = 64
            AND frozen_lane_evidence_hash NOT GLOB '*[^0-9a-f]*'
        )
    );

ALTER TABLE printer_pre_admission_discovery_attempt_items
    ADD COLUMN frozen_lane_decided_at TEXT;

ALTER TABLE printer_pre_admission_discovery_attempt_items
    ADD COLUMN frozen_lane_decision_owner TEXT;

-- New PAIR_READY rows must carry a complete frozen-lane provenance set.
-- Historical NULL rows remain readable but non-admissible.
CREATE TRIGGER printer_pre_admission_item_frozen_lane_complete
BEFORE INSERT ON printer_pre_admission_discovery_attempt_items
BEGIN
    SELECT CASE
        WHEN NEW.frozen_tracking_lane IS NULL
          OR NEW.frozen_discovery_action IS NULL
          OR NEW.frozen_discovery_label IS NULL
          OR NEW.frozen_classification_reason IS NULL
          OR NEW.frozen_lane_evidence_hash IS NULL
          OR NEW.frozen_lane_decided_at IS NULL
          OR NEW.frozen_lane_decision_owner IS NULL
        THEN RAISE(
            ABORT,
            'pre-admission item requires complete frozen tracking-lane provenance'
        )
        WHEN NEW.frozen_tracking_lane IS NOT NEW.frozen_discovery_action
        THEN RAISE(
            ABORT,
            'pre-admission frozen tracking lane/action mismatch'
        )
    END;
END;

COMMIT;
