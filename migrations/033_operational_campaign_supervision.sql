-- V2-9.7D.6B.5: operational campaign lease and safe-stop ownership.
-- This is separate from migration 030's proof-only supervision ledger.

BEGIN IMMEDIATE;

CREATE TABLE printer_memory_factory_campaign_supervision (
    id INTEGER PRIMARY KEY,
    supervision_id TEXT NOT NULL UNIQUE,
    campaign_id TEXT NOT NULL,
    configuration_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    supervision_state TEXT NOT NULL CHECK (
        supervision_state IN ('ACTIVE', 'STOPPING', 'TERMINAL')
    ),
    terminal_status TEXT CHECK (
        terminal_status IS NULL OR terminal_status IN (
            'COMPLETED', 'FAILED', 'CANCELLED', 'LEASE_RENEWAL_UNCONFIRMED'
        )
    ),
    first_terminal_cause TEXT,
    heartbeat_at TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    lease_lock_path TEXT NOT NULL,
    cancellation_requested_at TEXT,
    cancellation_reason TEXT,
    cleanup_completed_at TEXT,
    lease_released_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (campaign_id, run_id),
    UNIQUE (supervision_id, campaign_id, configuration_id, run_id),
    FOREIGN KEY (configuration_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_configurations(
            configuration_id, campaign_id
        ),
    FOREIGN KEY (run_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_runs(run_id, campaign_id),
    CHECK (length(trim(supervision_id)) > 0),
    CHECK (length(trim(owner_id)) > 0),
    CHECK (length(trim(lease_lock_path)) > 0),
    CHECK (
        (supervision_state IN ('ACTIVE', 'STOPPING')
            AND terminal_status IS NULL
            AND first_terminal_cause IS NULL
            AND cleanup_completed_at IS NULL
            AND lease_released_at IS NULL)
        OR
        (supervision_state = 'TERMINAL'
            AND terminal_status IS NOT NULL
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0
            AND cleanup_completed_at IS NOT NULL)
    ),
    CHECK (
        (cancellation_requested_at IS NULL AND cancellation_reason IS NULL)
        OR
        (cancellation_requested_at IS NOT NULL
            AND cancellation_reason IS NOT NULL
            AND length(trim(cancellation_reason)) > 0)
    )
);

CREATE UNIQUE INDEX idx_campaign_supervision_one_active_run
    ON printer_memory_factory_campaign_supervision(campaign_id, run_id)
    WHERE supervision_state IN ('ACTIVE', 'STOPPING');

CREATE INDEX idx_campaign_supervision_lease
    ON printer_memory_factory_campaign_supervision(
        supervision_state, lease_expires_at
    );

CREATE TRIGGER printer_campaign_supervision_identity_immutable
BEFORE UPDATE OF supervision_id, campaign_id, configuration_id, run_id,
    owner_id, lease_lock_path
ON printer_memory_factory_campaign_supervision
BEGIN SELECT RAISE(ABORT, 'operational campaign supervision identity is immutable'); END;

CREATE TRIGGER printer_campaign_supervision_terminal_immutable
BEFORE UPDATE OF supervision_state, terminal_status, first_terminal_cause,
    cleanup_completed_at
ON printer_memory_factory_campaign_supervision
WHEN OLD.supervision_state = 'TERMINAL'
BEGIN SELECT RAISE(ABORT, 'operational campaign terminal cause is immutable'); END;

COMMIT;
