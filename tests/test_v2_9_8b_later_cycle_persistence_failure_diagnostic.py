from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

import pytest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
    finalize_four_token_shared_terminal,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    LaterCycleCandidateSupply,
    LaterCycleDiscoveryCandidate,
    LaterCycleSourceEvidence,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
)
from printer_v1.operator_cli import pre_admission_discovery_attempt as attempts
from printer_v1.scheduler import scheduler
from printer_v1.scheduler.contracts import JobKind, JobStatus, LockResult


NOW = datetime(2026, 8, 24, 13, 0, tzinfo=timezone.utc)
FAILURE = "LATER_CYCLE_ATTEMPT_PERSISTENCE_FAILED"
SCHEMA = "PRE_ADMISSION_PERSISTENCE_DIAGNOSTIC_V1"
GOVERNOR = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCHEDULER = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)
HEALTH = MultiCycleAdmissionHealth(
    source_budget_available=True,
    provider_budgets_available=True,
    scheduler_budget_available=True,
    scheduler_due_work_healthy=True,
    close_reserve_available=True,
    campaign_supervision_healthy=True,
    lease_healthy=True,
    db_healthy=True,
    shared_terminal_condition=False,
    cancellation_requested=False,
    discovery_capacity_available=True,
    protected_work_capacity_available=True,
)


@pytest.fixture()
def database(tmp_path: Path) -> tuple[Path, int, int]:
    path = tmp_path / "bounded-persistence-diagnostic.sqlite3"
    apply_migrations(path)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version) "
        "VALUES ('campaign-1','RUNNING','OPERATIONAL_PERSISTENT','db-1','policy-1')"
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json) VALUES (?,?,?,?,?)",
        ("configuration-1", "campaign-1", "a" * 64, "{}", "{}"),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_runs("
        "run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "factory-1",
            "RUNNING",
            "WINDOW_15M",
            "OPERATIONAL_PERSISTENT",
            "a" * 64,
            "{}",
            NOW.isoformat(),
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (
            "campaign-run-1",
            "campaign-1",
            1,
            "RUNNING",
            "factory-1",
            NOW.isoformat(),
            NOW.isoformat(),
        ),
    )
    for slot in (1, 2):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,chain) VALUES (?,?, 'solana')",
            (slot, f"mint-{slot}"),
        )
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address) VALUES (?,?,?)",
            (slot, slot, f"pool-{slot}"),
        )
    request_id = connection.execute(
        "INSERT INTO printer_source_requests("
        "source_name,request_kind,requested_at,source_status,data_quality_label) "
        "VALUES ('dexscreener','fresh_profiles',?,'COMPLETE','CLEAN_DATA')",
        (NOW.isoformat(),),
    ).lastrowid
    response_id = connection.execute(
        "INSERT INTO printer_source_responses("
        "source_request_id,source_name,received_at,source_status,data_quality_label) "
        "VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA')",
        (request_id, NOW.isoformat()),
    ).lastrowid
    connection.commit()
    connection.close()
    return path, int(request_id), int(response_id)


def _candidate(slot: int) -> LaterCycleDiscoveryCandidate:
    evidence = {
        "candidate": {
            "source_name": "dexscreener",
            "captured_at": NOW.isoformat(),
            "price_usd": 0.001,
            "liquidity_usd": 5000,
            "volume_5m": 10,
            "volume_1h": 200,
            "volume_24h": 500,
            "txns_5m": 1,
            "txns_1h": 4,
            "txns_24h": 10,
            "source_channel": "PUMPFUN_MIGRATION",
        }
    }
    canonical = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    return LaterCycleDiscoveryCandidate(
        token_identity=f"solana-mainnet:mint-{slot}",
        token_row_id=slot,
        mint_identity=f"mint-{slot}",
        pair_identity=f"pool-{slot}",
        pair_row_id=slot,
        lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
        canonical_market_identity=f"solana-mainnet:pumpswap:pool-{slot}",
        canonical_pool_identity=f"pool-{slot}",
        channels=frozenset({"LATEST_PUMPFUN" if slot == 1 else "TOP_PUMPFUN"}),
        holder_evidence_eligible=True,
        canonical_evidence_json=canonical,
        canonical_evidence_hash=str(slot) * 64,
        evidence_version="v1",
        observed_at=NOW,
    )


def _callback(path: Path, supply) -> object:
    return AuthoritativeLiveOperationalCampaignOwner(
        later_cycle_candidate_supply=supply
    )._build_later_cycle_discovery_callback(
        db_path=path, configuration_id="configuration-1"
    )


def _failing_source_evidence(
    request_id: int, response_id: int
) -> tuple[LaterCycleSourceEvidence, LaterCycleSourceEvidence]:
    return (
        LaterCycleSourceEvidence("ELIGIBLE_SUPPLY", request_id, response_id),
        LaterCycleSourceEvidence("ELIGIBLE_SUPPLY", request_id, 999_999),
    )


def _invoke(callback):
    return callback(
        campaign_id="campaign-1",
        campaign_run_id="campaign-run-1",
        authoritative_factory_run_id="factory-1",
        cycle_id="cycle-2",
        cycle_ordinal=2,
        cycle_cutoff=NOW.isoformat(),
        evaluated_at=NOW.isoformat(),
        selection_seed="seed-2",
        source_governor=GOVERNOR,
        central_scheduler=SCHEDULER,
        admission_health=HEALTH,
    )


def _rows(path: Path) -> tuple[sqlite3.Row, sqlite3.Row]:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        attempt = connection.execute(
            "SELECT * FROM printer_pre_admission_discovery_attempts"
        ).fetchone()
        job = connection.execute("SELECT * FROM printer_scheduler_jobs").fetchone()
        assert attempt is not None and job is not None
        return attempt, job
    finally:
        connection.close()


def _assert_terminal(path: Path, *, producer: str, category: str, phase: str) -> dict:
    attempt, job = _rows(path)
    assert (attempt["attempt_state"], attempt["first_terminal_cause"]) == (
        "FAILED",
        FAILURE,
    )
    assert job["status"] == "FAILED"
    assert job["locked_at"] is None and job["lock_owner"] is None
    diagnostic = json.loads(job["last_error"])
    assert diagnostic["diagnostic_schema"] == SCHEMA
    assert diagnostic["failure_code"] == FAILURE
    assert diagnostic["producer_code"] == producer
    assert diagnostic["failure_category"] == category
    assert diagnostic["operation_phase"] == phase
    assert job["last_error"] == json.dumps(
        diagnostic, sort_keys=True, separators=(",", ":")
    )
    assert len(job["last_error"]) <= 1536
    connection = sqlite3.connect(path)
    try:
        decoded = attempts.load_pre_admission_persistence_diagnostic(
            connection, attempt_id=attempt["attempt_id"]
        )
        assert isinstance(decoded, attempts.PreAdmissionPersistenceDiagnostic)
        assert decoded.as_dict() == diagnostic
    finally:
        connection.close()
    return diagnostic


def _assert_no_retry_or_successor_authority(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts"
        ).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status IN "
            "('PENDING','RUNNING','COOLDOWN') OR locked_at IS NOT NULL "
            "OR lock_owner IS NOT NULL"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles WHERE cycle_ordinal=2"
        ).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM printer_tracking_queue").fetchone()[0] == 0
    finally:
        connection.close()


def test_a_source_link_insert_constraint_retains_stable_subcause_and_no_authority(
    database,
) -> None:
    path, request_id, response_id = database
    callback = _callback(
        path,
        lambda **_: LaterCycleCandidateSupply(
            (), _failing_source_evidence(request_id, response_id), "NO_PAIR"
        ),
    )

    first = _invoke(callback)
    second = _invoke(callback)

    assert first == second
    diagnostic = _assert_terminal(
        path,
        producer="SOURCE_EVIDENCE_LINK_INSERT",
        category="CONSTRAINT_OR_INTEGRITY",
        phase="SOURCE_LINK",
    )
    assert diagnostic["exception_type"] == "IntegrityError"
    assert diagnostic["reason_code"].startswith("SQLITE_CONSTRAINT")
    assert "UNIQUE constraint" not in json.dumps(diagnostic)
    _assert_no_retry_or_successor_authority(path)


def test_b_d_pair_item_two_constraint_rolls_back_pair_but_diagnostic_survives(
    database,
) -> None:
    path, request_id, response_id = database
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TRIGGER fixture_fail_pair_item_two BEFORE INSERT ON "
        "printer_pre_admission_discovery_attempt_items "
        "WHEN NEW.slot_ordinal=2 BEGIN "
        "SELECT RAISE(ABORT,'fixture slot two constraint'); END"
    )
    connection.commit()
    connection.close()
    callback = _callback(
        path,
        lambda **_: LaterCycleCandidateSupply(
            (_candidate(1), _candidate(2)),
            (
                LaterCycleSourceEvidence(
                    "ELIGIBLE_SUPPLY", request_id, response_id
                ),
            ),
            None,
        ),
    )

    result = _invoke(callback)

    assert result.state == "FAILED"
    diagnostic = _assert_terminal(
        path,
        producer="PAIR_ITEM_INSERT",
        category="CONSTRAINT_OR_INTEGRITY",
        phase="PAIR_ITEM_2",
    )
    assert diagnostic["reason_code"].startswith("SQLITE_CONSTRAINT")
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempt_items"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempts "
            "WHERE attempt_state='PAIR_READY'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_cycles WHERE cycle_ordinal=2"
        ).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM printer_tracking_queue").fetchone()[0] == 0
    finally:
        connection.close()
    _assert_no_retry_or_successor_authority(path)


class UnmappedPersistenceFault(RuntimeError):
    pass


class _FaultingConnection(sqlite3.Connection):
    def execute(self, sql, parameters=(), /):
        if "INSERT INTO printer_pre_admission_discovery_attempt_source_links" in sql:
            raise UnmappedPersistenceFault("secret query payload must not survive")
        return super().execute(sql, parameters)


def test_c_unknown_exception_fails_closed_with_safe_bounded_diagnostic(
    database, monkeypatch
) -> None:
    path, request_id, response_id = database
    from printer_v1.db import sqlite_write_contracts

    def connect_faulting(db_path, *, busy_timeout_ms=2000, row_factory=True):
        connection = sqlite3.connect(db_path, factory=_FaultingConnection)
        if row_factory:
            connection.row_factory = sqlite3.Row
        return sqlite_write_contracts.configure_operational_connection(
            connection, busy_timeout_ms=busy_timeout_ms
        )

    monkeypatch.setattr(sqlite_write_contracts, "connect_operational", connect_faulting)
    callback = _callback(
        path,
        lambda **_: LaterCycleCandidateSupply(
            (),
            (LaterCycleSourceEvidence("ELIGIBLE_SUPPLY", request_id, response_id),),
            "NO_PAIR",
        ),
    )

    result = _invoke(callback)

    assert result.first_terminal_cause == FAILURE
    diagnostic = _assert_terminal(
        path,
        producer="SOURCE_EVIDENCE_LINK_INSERT",
        category="UNKNOWN_PERSISTENCE_FAILURE",
        phase="SOURCE_LINK",
    )
    assert diagnostic["exception_type"] == "UnmappedPersistenceFault"
    assert diagnostic["reason_code"] == "UNKNOWN_PERSISTENCE_REASON"
    assert "secret" not in json.dumps(diagnostic)
    _assert_no_retry_or_successor_authority(path)


def test_e_later_terminal_reporting_failure_cannot_replace_first_cause(database) -> None:
    path, request_id, response_id = database
    _invoke(
        _callback(
            path,
            lambda **_: LaterCycleCandidateSupply(
                (), _failing_source_evidence(request_id, response_id), "NO_PAIR"
            ),
        )
    )
    before_attempt, before_job = _rows(path)
    connection = sqlite3.connect(path)
    try:
        with pytest.raises(FourTokenFactoryAdapterError):
            finalize_four_token_shared_terminal(
                connection,
                campaign_id="campaign-1",
                campaign_run_id="campaign-run-1",
                factory_run_id="factory-1",
                shared_terminalizer=lambda **_: (_ for _ in ()).throw(
                    RuntimeError("later report failure")
                ),
                configuration_id="configuration-1",
            )
    finally:
        connection.close()
    after_attempt, after_job = _rows(path)
    assert after_attempt["first_terminal_cause"] == before_attempt["first_terminal_cause"]
    assert after_job["last_error"] == before_job["last_error"]


def test_f_successful_pair_emits_no_failure_diagnostic(database) -> None:
    path, request_id, response_id = database
    result = _invoke(
        _callback(
            path,
            lambda **_: LaterCycleCandidateSupply(
                (_candidate(1), _candidate(2)),
                (LaterCycleSourceEvidence("ELIGIBLE_SUPPLY", request_id, response_id),),
                None,
            ),
        )
    )
    attempt, job = _rows(path)
    assert result.state == "PAIR_READY" and result.selected_count == 2
    assert attempt["attempt_state"] == "PAIR_READY"
    assert job["status"] == "SUCCEEDED" and job["last_error"] is None
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_pre_admission_discovery_attempt_items"
        ).fetchone()[0] == 2
        assert attempts.load_pre_admission_persistence_diagnostic(
            connection, attempt_id=attempt["attempt_id"]
        ) == attempts.DIAGNOSTIC_UNAVAILABLE
    finally:
        connection.close()


def _valid_payload() -> dict[str, str]:
    return {
        "diagnostic_schema": SCHEMA,
        "failure_code": FAILURE,
        "producer_code": "SOURCE_EVIDENCE_LINK_INSERT",
        "failure_category": "CONSTRAINT_OR_INTEGRITY",
        "operation_phase": "SOURCE_LINK",
        "exception_type": "IntegrityError",
        "reason_code": "SQLITE_CONSTRAINT_UNIQUE",
    }


@pytest.mark.parametrize(
    "last_error",
    [
        None,
        FAILURE,
        "{malformed",
        json.dumps({"oversized": "x" * 1600}),
        json.dumps({**_valid_payload(), "extra": "field"}),
        json.dumps({k: v for k, v in _valid_payload().items() if k != "reason_code"}),
        json.dumps({**_valid_payload(), "diagnostic_schema": "WRONG"}),
        json.dumps({**_valid_payload(), "failure_code": "OTHER"}),
        json.dumps({**_valid_payload(), "failure_category": "INVALID"}),
        json.dumps({**_valid_payload(), "producer_code": "INVALID"}),
        json.dumps({**_valid_payload(), "exception_type": "bad.type"}),
        json.dumps({**_valid_payload(), "exception_type": 123}),
        json.dumps({**_valid_payload(), "reason_code": "lowercase"}),
    ],
)
def test_g_decoder_returns_unavailable_for_legacy_or_malformed_evidence(
    database, last_error
) -> None:
    path, request_id, response_id = database
    _invoke(
        _callback(
            path,
            lambda **_: LaterCycleCandidateSupply(
                (), _failing_source_evidence(request_id, response_id), "NO_PAIR"
            ),
        )
    )
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        attempt_id, job_id = connection.execute(
            "SELECT attempt_id,scheduler_job_id FROM printer_pre_admission_discovery_attempts"
        ).fetchone()
        connection.execute(
            "UPDATE printer_scheduler_jobs SET last_error=? WHERE id=?",
            (last_error, job_id),
        )
        connection.commit()
        changes = connection.total_changes
        assert attempts.load_pre_admission_persistence_diagnostic(
            connection, attempt_id=attempt_id
        ) == attempts.DIAGNOSTIC_UNAVAILABLE
        assert connection.total_changes == changes
    finally:
        connection.close()


def test_g_decoder_rejects_active_lock_even_with_valid_terminal_envelope(database) -> None:
    path, request_id, response_id = database
    _invoke(
        _callback(
            path,
            lambda **_: LaterCycleCandidateSupply(
                (), _failing_source_evidence(request_id, response_id), "NO_PAIR"
            ),
        )
    )
    attempt, job = _rows(path)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "UPDATE printer_scheduler_jobs SET locked_at=?,lock_owner=? WHERE id=?",
            (NOW.isoformat(), "stale-active-lock", job["id"]),
        )
        connection.commit()
        changes = connection.total_changes
        assert attempts.load_pre_admission_persistence_diagnostic(
            connection, attempt_id=attempt["attempt_id"]
        ) == attempts.DIAGNOSTIC_UNAVAILABLE
        assert connection.total_changes == changes
    finally:
        connection.close()


def _running_scheduler_job(path: Path, name: str) -> int:
    result, job_id = scheduler.enqueue_job(
        path,
        job_name=name,
        job_kind=JobKind.PRE_ADMISSION_DISCOVERY_SELECTION,
        scheduled_for=NOW,
    )
    assert result is LockResult.ACQUIRED and job_id is not None
    assert scheduler.claim_due_job(
        path, job_id=job_id, lock_owner=f"lock:{name}", now=NOW
    ) is LockResult.ACQUIRED
    return int(job_id)


def test_scheduler_staging_is_first_write_wins_isolated_and_consumed_once(tmp_path) -> None:
    path = tmp_path / "scheduler-staging.sqlite3"
    apply_migrations(path)
    job_a = _running_scheduler_job(path, "a")
    job_b = _running_scheduler_job(path, "b")
    first = _valid_payload()
    second = {**first, "producer_code": "PAIR_ITEM_INSERT", "operation_phase": "PAIR_ITEM_2"}
    scheduler.stage_job_failure_diagnostic(job_id=job_a, failure_code=FAILURE, context=first)
    scheduler.stage_job_failure_diagnostic(job_id=job_a, failure_code=FAILURE, context=second)
    scheduler.stage_job_failure_diagnostic(job_id=job_b, failure_code=FAILURE, context=second)

    assert scheduler.fail_job(
        path, job_id=job_a, error=FAILURE, now=NOW, max_retries=0
    ) is JobStatus.FAILED
    assert scheduler.fail_job(
        path, job_id=job_b, error="OTHER_FAILURE", now=NOW, max_retries=0
    ) is JobStatus.FAILED
    connection = sqlite3.connect(path)
    try:
        assert json.loads(connection.execute(
            "SELECT last_error FROM printer_scheduler_jobs WHERE id=?", (job_a,)
        ).fetchone()[0]) == first
        assert connection.execute(
            "SELECT last_error FROM printer_scheduler_jobs WHERE id=?", (job_b,)
        ).fetchone()[0] == "OTHER_FAILURE"
    finally:
        connection.close()
    staged = scheduler._JOB_FAILURE_DIAGNOSTICS.get()
    assert job_a not in staged and job_b not in staged


@pytest.mark.parametrize("terminal", ["complete", "cancel"])
def test_successful_or_cancelled_job_discards_staged_failure(tmp_path, terminal) -> None:
    path = tmp_path / f"scheduler-{terminal}.sqlite3"
    apply_migrations(path)
    job_id = _running_scheduler_job(path, terminal)
    scheduler.stage_job_failure_diagnostic(
        job_id=job_id, failure_code=FAILURE, context=_valid_payload()
    )
    getattr(scheduler, f"{terminal}_job")(path, job_id=job_id, now=NOW)
    assert job_id not in scheduler._JOB_FAILURE_DIAGNOSTICS.get()
    connection = sqlite3.connect(path)
    try:
        status, last_error = connection.execute(
            "SELECT status,last_error FROM printer_scheduler_jobs WHERE id=?", (job_id,)
        ).fetchone()
        assert status == ("SUCCEEDED" if terminal == "complete" else "CANCELLED")
        assert last_error is None
    finally:
        connection.close()
