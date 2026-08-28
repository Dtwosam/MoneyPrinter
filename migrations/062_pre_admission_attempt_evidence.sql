-- V2-9.8B 4/2/2: append-only attempt-owned acquisition evidence.
--
-- This is intentionally not a Scheduler/job/quantum table.  Existing attempt,
-- Scheduler, temporal-refresh, Source-Governor, and deterministic request-key
-- owners remain authoritative.  The ledger preserves categorical facts across
-- cooperative claims so terminal reporting can reduce durable history.

BEGIN IMMEDIATE;

CREATE TABLE printer_pre_admission_attempt_evidence (
    attempt_id TEXT NOT NULL,
    event_key TEXT NOT NULL,
    opportunity_ordinal INTEGER NOT NULL CHECK (opportunity_ordinal BETWEEN 0 AND 3),
    claim_ordinal INTEGER NOT NULL CHECK (claim_ordinal > 0),
    evidence_kind TEXT NOT NULL CHECK (evidence_kind IN (
        'OPPORTUNITY_SCHEDULED', 'OPPORTUNITY_EXECUTED',
        'SOURCE_REQUEST_TERMINAL', 'PROVIDER_FAILURE',
        'CANDIDATE_OBSERVED', 'CANDIDATE_REOBSERVED',
        'CANDIDATE_REJECTED', 'DUPLICATE_OR_ALREADY_USED',
        'EXACT_PAIR_RESULT', 'PUMPSWAP_RESULT', 'LIQUIDITY_RESULT',
        'SAFETY_EVIDENCE_RESULT', 'INVENTORY_RESULT',
        'REFRESH_ROUND', 'ATTEMPT_DISPOSITION'
    )),
    mint_identity TEXT,
    pair_identity TEXT,
    categorical_reason TEXT,
    source_request_id INTEGER,
    source_response_id INTEGER,
    source_failure_id INTEGER,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json) = 1),
    payload_hash TEXT NOT NULL CHECK (
        length(payload_hash) = 64
        AND payload_hash NOT GLOB '*[^0-9a-f]*'
    ),
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (attempt_id, event_key),
    CHECK (length(trim(event_key)) > 0),
    CHECK (length(trim(evidence_kind)) > 0),
    CHECK (mint_identity IS NULL OR length(trim(mint_identity)) > 0),
    CHECK (pair_identity IS NULL OR length(trim(pair_identity)) > 0),
    CHECK (categorical_reason IS NULL OR length(trim(categorical_reason)) > 0),
    CHECK (source_response_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_failure_id IS NULL OR source_request_id IS NOT NULL),
    CHECK (source_response_id IS NULL OR source_failure_id IS NULL),
    FOREIGN KEY (attempt_id)
        REFERENCES printer_pre_admission_discovery_attempts(attempt_id),
    FOREIGN KEY (source_request_id) REFERENCES printer_source_requests(id),
    FOREIGN KEY (source_response_id) REFERENCES printer_source_responses(id),
    FOREIGN KEY (source_failure_id) REFERENCES printer_source_failures(id)
);

CREATE INDEX idx_pre_admission_attempt_evidence_reduce
    ON printer_pre_admission_attempt_evidence(
        attempt_id, opportunity_ordinal, claim_ordinal, evidence_kind
    );

CREATE TRIGGER printer_pre_admission_attempt_evidence_immutable_update
BEFORE UPDATE ON printer_pre_admission_attempt_evidence
BEGIN
    SELECT RAISE(ABORT, 'pre-admission attempt evidence is immutable');
END;

CREATE TRIGGER printer_pre_admission_attempt_evidence_immutable_delete
BEFORE DELETE ON printer_pre_admission_attempt_evidence
BEGIN
    SELECT RAISE(ABORT, 'pre-admission attempt evidence is immutable');
END;

CREATE TRIGGER printer_pre_admission_attempt_evidence_response_match
BEFORE INSERT ON printer_pre_admission_attempt_evidence
WHEN NEW.source_response_id IS NOT NULL
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_source_responses
        WHERE id = NEW.source_response_id
          AND source_request_id = NEW.source_request_id
    ) THEN RAISE(ABORT, 'attempt evidence response/request mismatch') END;
END;

CREATE TRIGGER printer_pre_admission_attempt_evidence_failure_match
BEFORE INSERT ON printer_pre_admission_attempt_evidence
WHEN NEW.source_failure_id IS NOT NULL
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM printer_source_failures
        WHERE id = NEW.source_failure_id
          AND source_request_id = NEW.source_request_id
    ) THEN RAISE(ABORT, 'attempt evidence failure/request mismatch') END;
END;

COMMIT;
