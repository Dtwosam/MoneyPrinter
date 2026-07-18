-- V2-9.7D.2A: campaign/configuration/report persistence only.
-- This migration does not schedule, collect, continue, replay, or run work.

BEGIN IMMEDIATE;

CREATE TABLE printer_memory_factory_campaigns (
    id INTEGER PRIMARY KEY,
    campaign_id TEXT NOT NULL UNIQUE,
    campaign_state TEXT NOT NULL CHECK (
        campaign_state IN (
            'DRAFT',
            'PREFLIGHT',
            'RUNNING',
            'STOP_REQUESTED',
            'TERMINAL_COMPLETED',
            'TERMINAL_STOPPED',
            'TERMINAL_BLOCKED',
            'TERMINAL_FAILED'
        )
    ),
    db_mode TEXT NOT NULL CHECK (
        db_mode IN ('PROOF_ISOLATED', 'OPERATIONAL_PERSISTENT')
    ),
    db_target_identity TEXT NOT NULL,
    proof_source_db_identity TEXT,
    policy_version TEXT NOT NULL,
    first_terminal_cause TEXT,
    terminal_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (length(trim(campaign_id)) > 0),
    CHECK (length(trim(db_target_identity)) > 0),
    CHECK (length(trim(policy_version)) > 0),
    CHECK (
        (db_mode = 'PROOF_ISOLATED'
            AND proof_source_db_identity IS NOT NULL
            AND length(trim(proof_source_db_identity)) > 0
            AND proof_source_db_identity <> db_target_identity)
        OR
        (db_mode = 'OPERATIONAL_PERSISTENT'
            AND proof_source_db_identity IS NULL)
    ),
    CHECK (
        (campaign_state IN (
            'DRAFT', 'PREFLIGHT', 'RUNNING', 'STOP_REQUESTED'
        )
            AND first_terminal_cause IS NULL
            AND terminal_at IS NULL)
        OR
        (campaign_state IN (
            'TERMINAL_COMPLETED',
            'TERMINAL_STOPPED',
            'TERMINAL_BLOCKED',
            'TERMINAL_FAILED'
        )
            AND first_terminal_cause IS NOT NULL
            AND length(trim(first_terminal_cause)) > 0
            AND terminal_at IS NOT NULL)
    )
);

CREATE TABLE printer_memory_factory_campaign_configurations (
    id INTEGER PRIMARY KEY,
    configuration_id TEXT NOT NULL UNIQUE,
    campaign_id TEXT NOT NULL UNIQUE,
    configuration_hash TEXT NOT NULL,
    configuration_json TEXT NOT NULL,
    launch_provenance_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (configuration_id, campaign_id),
    CHECK (length(trim(configuration_id)) > 0),
    CHECK (
        length(configuration_hash) = 64
        AND configuration_hash NOT GLOB '*[^0-9a-f]*'
    ),
    CHECK (length(trim(configuration_json)) > 0),
    CHECK (length(trim(launch_provenance_json)) > 0),
    FOREIGN KEY (campaign_id)
        REFERENCES printer_memory_factory_campaigns(campaign_id)
);

CREATE TABLE printer_memory_factory_campaign_reports (
    id INTEGER PRIMARY KEY,
    report_id TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    configuration_id TEXT NOT NULL,
    report_kind TEXT NOT NULL CHECK (
        report_kind IN ('TERMINAL', 'REPLAY')
    ),
    report_state TEXT NOT NULL CHECK (
        report_state IN (
            'REPORT_PENDING',
            'REPORT_TERMINAL',
            'REPLAY_VERIFIED',
            'REPLAY_BLOCKED'
        )
    ),
    replay_of_report_id TEXT,
    report_hash TEXT,
    report_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (report_id),
    UNIQUE (report_id, campaign_id),
    UNIQUE (report_id, campaign_id, configuration_id),
    CHECK (length(trim(report_id)) > 0),
    CHECK (
        report_hash IS NULL
        OR (
            length(report_hash) = 64
            AND report_hash NOT GLOB '*[^0-9a-f]*'
        )
    ),
    CHECK (
        (report_kind = 'TERMINAL'
            AND report_state IN ('REPORT_PENDING', 'REPORT_TERMINAL')
            AND replay_of_report_id IS NULL)
        OR
        (report_kind = 'REPLAY'
            AND report_state IN ('REPLAY_VERIFIED', 'REPLAY_BLOCKED')
            AND replay_of_report_id IS NOT NULL)
    ),
    CHECK (
        (report_state = 'REPORT_PENDING'
            AND report_hash IS NULL
            AND report_json IS NULL)
        OR
        (report_state <> 'REPORT_PENDING'
            AND report_hash IS NOT NULL
            AND report_json IS NOT NULL
            AND length(trim(report_json)) > 0)
    ),
    FOREIGN KEY (campaign_id)
        REFERENCES printer_memory_factory_campaigns(campaign_id),
    FOREIGN KEY (configuration_id, campaign_id)
        REFERENCES printer_memory_factory_campaign_configurations(
            configuration_id, campaign_id
        ),
    FOREIGN KEY (replay_of_report_id, campaign_id, configuration_id)
        REFERENCES printer_memory_factory_campaign_reports(
            report_id, campaign_id, configuration_id
        )
);

CREATE INDEX idx_memory_factory_campaigns_state
    ON printer_memory_factory_campaigns(campaign_state, created_at);
CREATE INDEX idx_memory_factory_campaigns_db_mode
    ON printer_memory_factory_campaigns(db_mode, db_target_identity);
CREATE INDEX idx_memory_factory_campaign_reports_campaign
    ON printer_memory_factory_campaign_reports(
        campaign_id, report_kind, report_state
    );

CREATE TRIGGER printer_campaign_identity_immutable
BEFORE UPDATE OF
    campaign_id,
    db_mode,
    db_target_identity,
    proof_source_db_identity,
    policy_version
ON printer_memory_factory_campaigns
BEGIN
    SELECT RAISE(ABORT, 'campaign identity is immutable');
END;

CREATE TRIGGER printer_campaign_configuration_immutable_update
BEFORE UPDATE ON printer_memory_factory_campaign_configurations
BEGIN
    SELECT RAISE(ABORT, 'campaign configuration is immutable');
END;

CREATE TRIGGER printer_campaign_configuration_immutable_delete
BEFORE DELETE ON printer_memory_factory_campaign_configurations
BEGIN
    SELECT RAISE(ABORT, 'campaign configuration is immutable');
END;

CREATE TRIGGER printer_campaign_report_replay_target
BEFORE INSERT ON printer_memory_factory_campaign_reports
WHEN NEW.report_kind = 'REPLAY'
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1
        FROM printer_memory_factory_campaign_reports AS target
        WHERE target.report_id = NEW.replay_of_report_id
          AND target.campaign_id = NEW.campaign_id
          AND target.configuration_id = NEW.configuration_id
          AND target.report_kind = 'TERMINAL'
          AND target.report_state = 'REPORT_TERMINAL'
    )
    THEN RAISE(ABORT, 'replay target must be a terminal report in the same campaign')
    END;
END;

CREATE TRIGGER printer_campaign_report_immutable_update
BEFORE UPDATE ON printer_memory_factory_campaign_reports
WHEN OLD.report_state <> 'REPORT_PENDING'
BEGIN
    SELECT RAISE(ABORT, 'terminal report or replay is immutable');
END;

CREATE TRIGGER printer_campaign_report_identity_immutable
BEFORE UPDATE OF
    report_id,
    campaign_id,
    configuration_id,
    report_kind,
    replay_of_report_id
ON printer_memory_factory_campaign_reports
BEGIN
    SELECT RAISE(ABORT, 'report identity is immutable');
END;

CREATE TRIGGER printer_campaign_report_immutable_delete
BEFORE DELETE ON printer_memory_factory_campaign_reports
BEGIN
    SELECT RAISE(ABORT, 'campaign report identity is immutable');
END;
