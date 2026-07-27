-- V2-9.8B.18: immutable first heartbeat-renewal failure evidence.

BEGIN IMMEDIATE;

CREATE TABLE printer_memory_factory_campaign_heartbeat_failures (
    supervision_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    configuration_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    safe_error_type TEXT NOT NULL,
    safe_error_category TEXT NOT NULL CHECK (safe_error_category IN (
        'SQLITE_LOCK_CONTENTION', 'LEASE_EXPIRED', 'OWNERSHIP_MISMATCH',
        'LEASE_RENEWAL_ERROR'
    )),
    safe_message TEXT NOT NULL,
    sqlite_locked INTEGER NOT NULL CHECK (sqlite_locked IN (0, 1)),
    attempted_at TEXT NOT NULL,
    prior_heartbeat_at TEXT,
    prior_lease_expires_at TEXT,
    renewal_confirmed INTEGER NOT NULL CHECK (renewal_confirmed IN (0, 1)),
    terminal_cause TEXT NOT NULL CHECK (terminal_cause IN (
        'LEASE_RENEWAL_SQLITE_LOCKED', 'LEASE_RENEWAL_LEASE_EXPIRED',
        'LEASE_RENEWAL_OWNERSHIP_MISMATCH', 'LEASE_RENEWAL_UNCONFIRMED'
    )),
    created_at TEXT NOT NULL,
    UNIQUE (supervision_id, campaign_id, configuration_id, run_id, owner_id),
    FOREIGN KEY (supervision_id, campaign_id, configuration_id, run_id)
        REFERENCES printer_memory_factory_campaign_supervision(
            supervision_id, campaign_id, configuration_id, run_id
        )
);

CREATE TRIGGER printer_campaign_heartbeat_failure_immutable_update
BEFORE UPDATE ON printer_memory_factory_campaign_heartbeat_failures
BEGIN SELECT RAISE(ABORT, 'first heartbeat-renewal failure is immutable'); END;

CREATE TRIGGER printer_campaign_heartbeat_failure_immutable_delete
BEFORE DELETE ON printer_memory_factory_campaign_heartbeat_failures
BEGIN SELECT RAISE(ABORT, 'first heartbeat-renewal failure is immutable'); END;

COMMIT;
