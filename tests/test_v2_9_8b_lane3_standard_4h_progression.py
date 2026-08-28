"""Focused Lane-3 durable Standard-4H progression contracts.

Disposable SQLite databases only. No providers, campaign runtime, authorization,
retrieval, decisions, positions, trades, audits, or PnL.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib
import inspect
import json
import sqlite3
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.db.migrate import canonical_migration_count, canonical_migration_names
from printer_v1.operator_cli.campaign_supervision import acquire_campaign_supervision
from printer_v1.operator_cli.operational_database_target_binding import (
    PRODUCTION_AUTHORITATIVE,
    build_durable_operational_database_target_expectation,
    build_operational_database_target_binding,
)
from printer_v1.memory.clean_object_promotion import promote_clean_object
from printer_v1.sources.governed_execution import build_fixture_source_adapter
from tests import (
    test_v2_9_8b_post_dtw100_standard_four_hour_activation_factory_barrier
    as activation_fixture,
)
from tests import (
    test_v2_9_8b_post_dtw100_standard_four_hour_campaign_handoff
    as handoff_fixture,
)
from tests.test_v2_9_8b_operational_selective_1h import Selective1hFixture


ATTEMPTS = "printer_memory_factory_standard_4h_progression_attempts"
TOKENS = "printer_memory_factory_standard_4h_progression_tokens"


class _FactoryLoopClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant
        self.elapsed = 0.0

    def now(self) -> datetime:
        value = self.instant
        self.instant += timedelta(microseconds=1)
        return value

    def monotonic(self) -> float:
        return self.elapsed

    def sleep(self, seconds: float) -> None:
        self.elapsed += seconds
        self.instant += timedelta(seconds=seconds)


class _FactoryLoopDateTime(datetime):
    clock: _FactoryLoopClock

    @classmethod
    def now(cls, tz=None):
        value = cls.clock.now()
        return value if tz is None else value.astimezone(tz)


class _HandoffCommittedAtFactoryLoop(RuntimeError):
    post_handoff_proof_fault = True

    def __init__(self, barrier: dict) -> None:
        self.barrier = barrier
        super().__init__("LANE3_HANDOFF_COMMITTED_AT_FACTORY_LOOP")


def _factory_loop_snapshot_adapter(*, token_mint, timeout_seconds):
    del timeout_seconds
    return build_fixture_source_adapter(
        "dexscreener",
        fixture_payload={
            "pairs": [
                {
                    "chain": "solana",
                    "token_mint": token_mint,
                    "pair_address": "pool-1" if token_mint == "mint-1" else "pool-2",
                    "price_usd": 1.0,
                    "liquidity_usd": 10_000.0,
                    "volume_5m": 500.0,
                    "volume_1h": 2_000.0,
                    "volume_24h": 10_000.0,
                    "txns_5m": 10,
                    "txns_1h": 50,
                    "txns_24h": 500,
                    "buys_5m": 7,
                    "sells_5m": 3,
                    "buys_1h": 30,
                    "sells_1h": 20,
                    "buys_24h": 280,
                    "sells_24h": 220,
                    "price_change_5m": 1.0,
                    "price_change_1h": 2.0,
                    "price_change_24h": 3.0,
                }
            ]
        },
    )


def _factory_loop_context_adapters(clock: _FactoryLoopClock):
    def market(**_kwargs):
        return build_fixture_source_adapter(
            "coingecko",
            fixture_payload={
                "captured_at": clock.now().isoformat(),
                "assets": {
                    "bitcoin": {"price_usd": 65_000, "change_24h": 2.5},
                    "ethereum": {"price_usd": 3_500, "change_24h": 1.5},
                    "solana": {
                        "price_usd": 150,
                        "change_24h": 4.0,
                        "volume_24h": 2_000_000_000,
                    },
                },
            },
        )

    def safety(**kwargs):
        return build_fixture_source_adapter(
            "goplus",
            fixture_payload={
                "token_mint": kwargs.get("token_mint"),
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "total_supply": "1000000000",
                "top_10_holders": [{"percent": "3"} for _ in range(10)],
                "lp_info": [{"locked": True}],
                "risk_flags": [],
            },
        )

    def quote(**kwargs):
        return build_fixture_source_adapter(
            "jupiter_quote",
            fixture_payload={
                "route_available": True,
                "route_plan_present": True,
                "slippage_bps": 50,
                "price_impact_bps": 5,
                "freshness_label": "QUOTE_FRESH",
                "target_status": "TARGET_MATCH",
                "paper_only_context": True,
                "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
                "input_mint": kwargs["input_mint"],
                "output_mint": kwargs["output_mint"],
            },
        )

    return {"coingecko": market, "goplus": safety, "jupiter_quote": quote}


def _ready_progression_fixture():
    case = activation_fixture.StandardFourHourActivationFactoryBarrierTests()
    case.setUp()
    return case, case.binding


def test_migration_061_creates_exact_progression_aggregate(tmp_path) -> None:
    db = tmp_path / "lane3.sqlite3"
    apply_migrations(db)
    connection = sqlite3.connect(db)
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert ATTEMPTS in tables
        assert TOKENS in tables
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        connection.close()


def test_migration_061_exposes_only_accepted_state_vocabularies(tmp_path) -> None:
    db = tmp_path / "lane3-vocabulary.sqlite3"
    apply_migrations(db)
    connection = sqlite3.connect(db)
    try:
        attempt_row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (ATTEMPTS,),
        ).fetchone()
        token_row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (TOKENS,),
        ).fetchone()
        assert attempt_row is not None
        assert token_row is not None
        attempt_sql = str(attempt_row[0])
        token_sql = str(token_row[0])
        for state in (
            "WAITING_FOR_PREDECESSORS",
            "EVALUATING",
            "ELIGIBILITY_COMPLETE",
            "HANDOFF_COMMITTED",
            "TERMINAL_FAILED",
            "TERMINAL_CANCELLED",
            "INTERRUPTED_REVIEW",
        ):
            assert state in attempt_sql
        for disposition in (
            "WAITING_FOR_PREDECESSOR",
            "ELIGIBLE_PENDING_HANDOFF",
            "INELIGIBLE",
            "HANDOFF_CREATED",
            "TERMINAL_FAILED",
        ):
            assert disposition in token_sql
    finally:
        connection.close()


def test_standard_first_hour_handoff_creates_one_attempt_and_two_exact_rows() -> None:
    fx = handoff_fixture.StandardFourHourCampaignHandoffTests()._prepared_closed_first_hour()
    try:
        attempts = fx.connection.execute(
            f"SELECT * FROM {ATTEMPTS} ORDER BY progression_attempt_id"
        ).fetchall()
        tokens = fx.connection.execute(
            f"SELECT * FROM {TOKENS} ORDER BY slot_ordinal"
        ).fetchall()
        assert len(attempts) == 1
        assert str(attempts[0]["attempt_state"]) == "WAITING_FOR_PREDECESSORS"
        assert str(attempts[0]["factory_run_id"]) == "factory-run-1"
        assert len(tokens) == 2
        assert [int(row["tracking_queue_id"]) for row in tokens] == [1, 2]
        assert [str(row["tracking_lane"]) for row in tokens] == [
            "TRACK_FAST",
            "TRACK_NORMAL",
        ]
        assert all(
            str(row["token_disposition"]) == "WAITING_FOR_PREDECESSOR"
            for row in tokens
        )
        assert all(row["predecessor_window_1h_id"] is not None for row in tokens)
    finally:
        fx.close()


def test_no_first_hour_predecessors_are_immediately_terminally_ineligible() -> None:
    fx = Selective1hFixture(standard_four_hour_campaign=True)
    try:
        fx.prepare_eligible(token_id=1, window_id=81, promote=False)
        fx.prepare_eligible(token_id=2, window_id=82, promote=False)
        result = fx.evaluate()
        assert result["continue_count"] == 0
        attempt = fx.connection.execute(
            f"SELECT attempt_state FROM {ATTEMPTS}"
        ).fetchone()
        tokens = fx.connection.execute(
            f"""SELECT token_disposition,predecessor_window_1h_id,
                       disposition_reasons_json
                FROM {TOKENS} ORDER BY slot_ordinal"""
        ).fetchall()
        assert str(attempt[0]) == "ELIGIBILITY_COMPLETE"
        assert [str(row[0]) for row in tokens] == ["INELIGIBLE", "INELIGIBLE"]
        assert all(row[1] is None for row in tokens)
        assert all(
            json.loads(str(row[2])) == ["NO_WINDOW_1H_PLANNED"]
            for row in tokens
        )
        acquire_campaign_supervision(
            fx.db,
            lock_path=fx.db.with_suffix(".zero.lease.json"),
            supervision_id="lane3-zero-supervision",
            campaign_id="campaign-1h",
            configuration_id="config-1h",
            run_id="run-1h",
            owner_id="lane3-zero-owner",
            lease_seconds=3600,
        )
        binding = build_operational_database_target_binding(
            target_kind=PRODUCTION_AUTHORITATIVE,
            resolved_db_path=fx.db,
            authorized_pre_mutation_sha256="a" * 64,
            migration_count=canonical_migration_count(),
            migration_head=canonical_migration_names()[-1],
            authorization_id="lane3-authorization",
            authorization_marker_sha256="b" * 64,
            application_marker_sha256="c" * 64,
            execution_id="lane3-execution",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            configuration_id="config-1h",
            authorization_consumed_once=True,
            invocation_count=1,
            allowed_invocation_count=1,
            automatic_retry_allowed=False,
            manual_rerun_allowed=False,
            resume_allowed=False,
            restart_allowed=False,
            successor_allowed=False,
        )
        from printer_v1.operator_cli.operational_standard_4h import (
            run_standard_four_hour_campaign_barrier,
        )

        barrier = run_standard_four_hour_campaign_barrier(
            fx.connection,
            db_path=fx.db,
            campaign_id="campaign-1h",
            configuration_id="config-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            operational_db_binding=binding,
            canonical_authoritative_db_path=fx.db,
            cancellation_probe=lambda: None,
        )
        assert barrier["plan"]["no_op"] is True
        assert fx.connection.execute(
            f"SELECT attempt_state FROM {ATTEMPTS}"
        ).fetchone()[0] == "HANDOFF_COMMITTED"
        assert fx.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind='WINDOW_4H'"
        ).fetchone()[0] == 0
    finally:
        fx.close()


def test_progression_module_exposes_shared_durable_read_contract() -> None:
    module = importlib.import_module(
        "printer_v1.operator_cli.standard_4h_progression"
    )
    assert callable(getattr(module, "derive_standard_4h_progression_status", None))


def test_real_authority_reads_produce_durable_eligibility_and_not_created_truth() -> None:
    case, binding = _ready_progression_fixture()
    try:
        progression = importlib.import_module(
            "printer_v1.operator_cli.standard_4h_progression"
        )
        result = progression.evaluate_standard_4h_progression(
            case.fx.connection,
            db_path=case.fx.db,
            campaign_id="campaign-1h",
            configuration_id="config-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            operational_db_binding=binding,
            canonical_authoritative_db_path=case.fx.db,
            cancellation_probe=lambda: None,
        )
        assert result["attempt_state"] == "ELIGIBILITY_COMPLETE"
        assert result["eligible_token_slot_ids"] == ["slot-1", "slot-2"]
        evidence = result["authority_evidence"]
        assert evidence["database"]["binding_validation"] == "VALID"
        assert evidence["supervision"]["supervision_id"] == "lane3-supervision"
        assert evidence["scheduler"]["integrity_healthy"] is True
        assert evidence["campaign_budget"]["available"] is True
        assert [item["tracking_queue_id"] for item in result["tokens"]] == [1, 2]

        status = progression.derive_standard_4h_progression_status(
            case.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
        )
        assert status["complete"] is False
        assert status["aggregate_state"] == "ELIGIBILITY_COMPLETE"
        assert [item["outcome"] for item in status["per_token"]] == [
            "ELIGIBLE_NOT_CREATED",
            "ELIGIBLE_NOT_CREATED",
        ]
        stopped_status = progression.derive_standard_4h_progression_status(
            case.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            ownership_active=False,
        )
        assert stopped_status["aggregate_state"] == "ELIGIBILITY_COMPLETE"
        assert [item["outcome"] for item in stopped_status["per_token"]] == [
            "ELIGIBLE_NOT_CREATED",
            "ELIGIBLE_NOT_CREATED",
        ]
    finally:
        case.tearDown()


def _evaluate(case, binding, *, cancellation_probe=lambda: None, now=None):
    from printer_v1.operator_cli.standard_4h_progression import (
        evaluate_standard_4h_progression,
    )

    return evaluate_standard_4h_progression(
        case.fx.connection,
        db_path=case.fx.db,
        campaign_id="campaign-1h",
        configuration_id="config-1h",
        campaign_run_id="run-1h",
        cycle_id="cycle-1h",
        factory_run_id="factory-run-1",
        operational_db_binding=binding,
        canonical_authoritative_db_path=case.fx.db,
        cancellation_probe=cancellation_probe,
        now=now,
    )


def _dispositions(case) -> dict[str, str]:
    return {
        str(row[0]): str(row[1])
        for row in case.fx.connection.execute(
            f"SELECT token_slot_id,token_disposition FROM {TOKENS}"
        )
    }


def _break_queue_identity(case, queue_id: int) -> None:
    with case.fx.connection:
        case.fx.connection.execute(
            "UPDATE printer_tracking_queue SET pair_id=? WHERE id=?",
            (2 if queue_id == 1 else 1, queue_id),
        )


def _block_memory_gate(case, token_id: int) -> None:
    with case.fx.connection:
        case.fx.connection.execute(
            "UPDATE printer_memory_windows SET supporting_context_json='{}' "
            "WHERE token_id=? AND window_kind='WINDOW_1H'",
            (token_id,),
        )


def _insert_run_requests(case, *, count: int, step_prefix: str) -> None:
    with case.fx.connection:
        case.fx.connection.executemany(
            """INSERT INTO printer_source_requests(
                   source_name,request_kind,requested_at,request_key,
                   source_status,data_quality_label
               ) VALUES ('fixture','lane3_budget',?,?,
                   'COMPLETE','CLEAN_DATA')""",
            (
                (
                    "2026-08-23T00:00:00+00:00",
                    f"factory-run-1:{step_prefix}{ordinal}:request",
                )
                for ordinal in range(count)
            ),
        )


def test_campaign_stop_requested_is_real_shared_cancellation_authority() -> None:
    case, binding = _ready_progression_fixture()
    try:
        with case.fx.connection:
            case.fx.connection.execute(
                "UPDATE printer_memory_factory_campaigns "
                "SET campaign_state='STOP_REQUESTED' "
                "WHERE campaign_id='campaign-1h'"
            )
        result = _evaluate(case, binding)
        assert result["attempt_state"] == "TERMINAL_CANCELLED"
        attempt = case.fx.connection.execute(
            f"SELECT first_terminal_cause FROM {ATTEMPTS}"
        ).fetchone()
        assert str(attempt[0]) == "CAMPAIGN_STOP_REQUESTED"
    finally:
        case.tearDown()


def test_expired_real_supervision_lease_terminalizes_shared_attempt() -> None:
    case, binding = _ready_progression_fixture()
    try:
        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        result = _evaluate(case, binding, now=future)
        assert result["attempt_state"] == "TERMINAL_FAILED"
        assert result["authority_evidence"]["supervision"]["lease_expired"] is True
        attempt = case.fx.connection.execute(
            f"SELECT first_terminal_cause FROM {ATTEMPTS}"
        ).fetchone()
        assert str(attempt[0]) == "STANDARD_4H_SUPERVISION_OR_LEASE_NOT_HEALTHY"
    finally:
        case.tearDown()


def test_mismatched_real_database_binding_terminalizes_shared_attempt() -> None:
    case, binding = _ready_progression_fixture()
    try:
        wrong = replace(binding, resolved_db_path=str(case.fx.db) + ".wrong")
        result = _evaluate(case, wrong)
        assert result["attempt_state"] == "TERMINAL_FAILED"
        assert result["authority_evidence"]["database"]["binding_validation"] != "VALID"
        assert set(_dispositions(case).values()) == {"WAITING_FOR_PREDECESSOR"}
    finally:
        case.tearDown()


def test_real_global_budget_usage_terminalizes_attempt_not_tokens() -> None:
    case, binding = _ready_progression_fixture()
    try:
        _insert_run_requests(case, count=81, step_prefix="unowned_budget_")
        result = _evaluate(case, binding)
        assert result["attempt_state"] == "TERMINAL_FAILED"
        budget = result["authority_evidence"]["campaign_budget"]
        assert budget["available"] is False
        assert budget["continuing_mask"] == [True, True]
        assert set(_dispositions(case).values()) == {"WAITING_FOR_PREDECESSOR"}
        attempt = case.fx.connection.execute(
            f"SELECT first_terminal_cause FROM {ATTEMPTS}"
        ).fetchone()
        assert str(attempt[0]) == "STANDARD_4H_GLOBAL_BUDGET_UNAVAILABLE"
    finally:
        case.tearDown()


def test_exact_cycle_token_budget_makes_only_exhausted_token_ineligible() -> None:
    case, binding = _ready_progression_fixture()
    try:
        _insert_run_requests(case, count=50, step_prefix="t1_existing_")
        result = _evaluate(case, binding)
        assert result["eligible_token_slot_ids"] == ["slot-2"]
        assert _dispositions(case) == {
            "slot-1": "INELIGIBLE",
            "slot-2": "ELIGIBLE_PENDING_HANDOFF",
        }
        evidence = result["authority_evidence"]["campaign_budget"]
        assert evidence["continuing_mask"] == [False, True]
        token_evidence = case.fx.connection.execute(
            f"SELECT eligibility_evidence_json FROM {TOKENS} "
            "WHERE token_slot_id='slot-1'"
        ).fetchone()
        budget = json.loads(str(token_evidence[0]))["token_budget"]
        assert budget["actual_requests"] == 52
        assert budget["available"] is False
    finally:
        case.tearDown()


def test_token_local_integrity_failure_does_not_block_eligible_peer_handoff() -> None:
    case, binding = _ready_progression_fixture()
    try:
        _break_queue_identity(case, 1)
        result = _evaluate(case, binding)
        assert result["eligible_token_slot_ids"] == ["slot-2"]
        assert _dispositions(case) == {
            "slot-1": "TERMINAL_FAILED",
            "slot-2": "ELIGIBLE_PENDING_HANDOFF",
        }
        progression = importlib.import_module(
            "printer_v1.operator_cli.standard_4h_progression"
        )
        plan = progression.commit_standard_4h_progression_handoff(
            case.fx.connection,
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            db_path=case.fx.db,
            configuration_id="config-1h",
            operational_db_binding=binding,
            canonical_authoritative_db_path=case.fx.db,
            cancellation_probe=lambda: None,
        )
        assert plan["continuation_count"] == 1
        assert _dispositions(case) == {
            "slot-1": "TERMINAL_FAILED",
            "slot-2": "HANDOFF_CREATED",
        }
        status = progression.derive_standard_4h_progression_status(
            case.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
        )
        outcomes = {row["token_slot_id"]: row["outcome"] for row in status["per_token"]}
        assert outcomes["slot-1"] == "FAILED"
        assert outcomes["slot-2"] == "CREATED_PENDING"
    finally:
        case.tearDown()


def test_terminal_failed_plus_ineligible_commits_truthful_zero_token_noop() -> None:
    case, binding = _ready_progression_fixture()
    try:
        _break_queue_identity(case, 1)
        _block_memory_gate(case, 2)
        result = _evaluate(case, binding)
        assert result["eligible_token_slot_ids"] == []
        assert _dispositions(case) == {
            "slot-1": "TERMINAL_FAILED",
            "slot-2": "INELIGIBLE",
        }
        progression = importlib.import_module(
            "printer_v1.operator_cli.standard_4h_progression"
        )
        plan = progression.commit_standard_4h_progression_handoff(
            case.fx.connection,
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            db_path=case.fx.db,
            configuration_id="config-1h",
            operational_db_binding=binding,
            canonical_authoritative_db_path=case.fx.db,
            cancellation_probe=lambda: None,
        )
        assert plan["no_op"] is True
        assert plan["continuation_count"] == 0
        assert case.fx.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind='WINDOW_4H'"
        ).fetchone()[0] == 0
    finally:
        case.tearDown()


def test_two_token_local_failures_commit_truthful_zero_token_noop() -> None:
    case, binding = _ready_progression_fixture()
    try:
        _break_queue_identity(case, 1)
        _break_queue_identity(case, 2)
        result = _evaluate(case, binding)
        assert result["eligible_token_slot_ids"] == []
        assert set(_dispositions(case).values()) == {"TERMINAL_FAILED"}
        progression = importlib.import_module(
            "printer_v1.operator_cli.standard_4h_progression"
        )
        plan = progression.commit_standard_4h_progression_handoff(
            case.fx.connection,
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            db_path=case.fx.db,
            configuration_id="config-1h",
            operational_db_binding=binding,
            canonical_authoritative_db_path=case.fx.db,
            cancellation_probe=lambda: None,
        )
        assert plan["no_op"] is True
        status = progression.derive_standard_4h_progression_status(
            case.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
        )
        assert [row["outcome"] for row in status["per_token"]] == ["FAILED", "FAILED"]
        assert status["complete"] is True
    finally:
        case.tearDown()


def test_shared_cancellation_terminalizes_attempt_not_tokens() -> None:
    case, binding = _ready_progression_fixture()
    try:
        result = _evaluate(
            case,
            binding,
            cancellation_probe=lambda: "OPERATOR_EXTERNAL_STOP",
        )
        assert result["attempt_state"] == "TERMINAL_CANCELLED"
        assert set(_dispositions(case).values()) == {"WAITING_FOR_PREDECESSOR"}
        attempt = case.fx.connection.execute(
            f"SELECT first_terminal_cause FROM {ATTEMPTS}"
        ).fetchone()
        assert str(attempt[0]) == "OPERATOR_EXTERNAL_STOP"
        progression = importlib.import_module(
            "printer_v1.operator_cli.standard_4h_progression"
        )
        status = progression.derive_standard_4h_progression_status(
            case.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
        )
        assert [row["outcome"] for row in status["per_token"]] == [
            "CANCELLED",
            "CANCELLED",
        ]
    finally:
        case.tearDown()


def test_cancelled_predecessor_is_ineligible_and_valid_peer_remains_eligible() -> None:
    case, binding = _ready_progression_fixture()
    try:
        close = case.fx.connection.execute(
            """SELECT scheduler_job_id
               FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND token_id=1
                 AND step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')"""
        ).fetchone()
        assert close is not None
        with case.fx.connection:
            case.fx.connection.execute(
                "UPDATE printer_scheduler_jobs SET status='CANCELLED' WHERE id=?",
                (int(close[0]),),
            )
        result = _evaluate(case, binding)
        assert result["eligible_token_slot_ids"] == ["slot-2"]
        assert _dispositions(case) == {
            "slot-1": "INELIGIBLE",
            "slot-2": "ELIGIBLE_PENDING_HANDOFF",
        }
        token = case.fx.connection.execute(
            f"SELECT disposition_reasons_json,eligibility_evidence_json "
            f"FROM {TOKENS} WHERE token_slot_id='slot-1'"
        ).fetchone()
        assert json.loads(str(token[0])) == ["PREDECESSOR_1H_CANCELLED"]
        predecessor = json.loads(str(token[1]))
        assert predecessor["predecessor_reference"]["scheduler_status"] == "CANCELLED"
        assert predecessor["predecessor_terminal_cause"] is not None
    finally:
        case.tearDown()


def test_primary_fault_is_immutable_when_secondary_reporting_fault_arrives() -> None:
    case, _binding = _ready_progression_fixture()
    try:
        result = _evaluate(case, None)
        assert result["attempt_state"] == "TERMINAL_FAILED"
        progression = importlib.import_module(
            "printer_v1.operator_cli.standard_4h_progression"
        )
        with case.fx.connection:
            progression.terminalize_stopped_standard_4h_progression(
                case.fx.connection,
                campaign_id="campaign-1h",
                campaign_run_id="run-1h",
                cycle_id="cycle-1h",
                stop_cause="REPORT_RECONCILIATION_FAILED",
            )
        row = case.fx.connection.execute(
            f"SELECT first_terminal_cause,fault_details_json FROM {ATTEMPTS}"
        ).fetchone()
        faults = json.loads(str(row[1]))
        assert str(row[0]) == "OPERATIONAL_DB_BINDING_MISSING"
        assert faults["primary"]["cause"] == "OPERATIONAL_DB_BINDING_MISSING"
        assert [item["cause"] for item in faults["secondary"]] == [
            "REPORT_RECONCILIATION_FAILED"
        ]
    finally:
        case.tearDown()


def test_progression_fault_envelope_redacts_secrets_urls_and_local_paths() -> None:
    case, _binding = _ready_progression_fixture()
    try:
        progression = importlib.import_module(
            "printer_v1.operator_cli.standard_4h_progression"
        )
        attempt_id = case.fx.connection.execute(
            f"SELECT progression_attempt_id FROM {ATTEMPTS}"
        ).fetchone()[0]
        with case.fx.connection:
            progression.persist_progression_primary_fault(
                case.fx.connection,
                progression_attempt_id=str(attempt_id),
                cause="SAFE_INTERNAL_CAUSE",
                safe_message=(
                    "https://provider.invalid/private api_key=supersecret "
                    "/Users/operator/private.sqlite3"
                ),
            )
        raw = str(case.fx.connection.execute(
            f"SELECT fault_details_json FROM {ATTEMPTS}"
        ).fetchone()[0])
        assert "supersecret" not in raw
        assert "provider.invalid" not in raw
        assert "/Users/operator" not in raw
        assert "<redacted>" in raw
    finally:
        case.tearDown()


def test_sqlite_primary_write_failure_leaves_evaluating_and_never_uses_lease_channel() -> None:
    case, _binding = _ready_progression_fixture()
    try:
        lease_path = case.fx.db.with_suffix(".lease.json")
        before_lease = lease_path.read_text(encoding="utf-8")
        case.fx.connection.execute(
            f"""CREATE TRIGGER lane3_fail_primary_write
                BEFORE UPDATE ON {ATTEMPTS}
                WHEN NEW.first_terminal_cause IS NOT NULL
                BEGIN SELECT RAISE(ABORT, 'injected_progression_sqlite_failure'); END"""
        )
        case.fx.connection.commit()
        from printer_v1.operator_cli.operational_standard_4h import (
            run_standard_four_hour_campaign_barrier,
        )

        try:
            run_standard_four_hour_campaign_barrier(
                case.fx.connection,
                db_path=case.fx.db,
                campaign_id="campaign-1h",
                configuration_id="config-1h",
                run_id="run-1h",
                cycle_id="cycle-1h",
                factory_run_id="factory-run-1",
                operational_db_binding=None,
                canonical_authoritative_db_path=case.fx.db,
                cancellation_probe=lambda: None,
            )
            raise AssertionError("canonical progression SQLite write unexpectedly succeeded")
        except sqlite3.IntegrityError as exc:
            assert "injected_progression_sqlite_failure" in str(exc)
        row = case.fx.connection.execute(
            f"SELECT attempt_state,first_terminal_cause FROM {ATTEMPTS}"
        ).fetchone()
        assert tuple(row) == ("EVALUATING", None)
        assert lease_path.read_text(encoding="utf-8") == before_lease
        assert case.fx.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind='WINDOW_4H'"
        ).fetchone()[0] == 0
        progression = importlib.import_module(
            "printer_v1.operator_cli.standard_4h_progression"
        )
        status = progression.derive_standard_4h_progression_status(
            case.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            ownership_active=False,
        )
        assert status["aggregate_state"] == "INTERRUPTED_AMBIGUOUS"
        assert status["requires_review"] is True
        assert status["complete"] is False
        assert {row["outcome"] for row in status["per_token"]} == {
            "INTERRUPTED_AMBIGUOUS"
        }
    finally:
        case.tearDown()


def test_atomic_handoff_projection_failure_rolls_back_to_complete_eligibility() -> None:
    case, binding = _ready_progression_fixture()
    try:
        _evaluate(case, binding)
        progression = importlib.import_module(
            "printer_v1.operator_cli.standard_4h_progression"
        )
        from printer_v1.operator_cli import campaign_ownership

        real = campaign_ownership.project_campaign_scheduler_job
        calls = 0

        def fail_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise campaign_ownership.CampaignOwnershipError(
                    "injected_projection_failure"
                )
            return real(*args, **kwargs)

        with patch.object(
            campaign_ownership,
            "project_campaign_scheduler_job",
            side_effect=fail_second,
        ):
            try:
                progression.commit_standard_4h_progression_handoff(
                    case.fx.connection,
                    campaign_id="campaign-1h",
                    campaign_run_id="run-1h",
                    cycle_id="cycle-1h",
                    factory_run_id="factory-run-1",
                    db_path=case.fx.db,
                    configuration_id="config-1h",
                    operational_db_binding=binding,
                    canonical_authoritative_db_path=case.fx.db,
                    cancellation_probe=lambda: None,
                )
                raise AssertionError("injected projection failure did not abort")
            except progression.StandardFourHourProgressionError as exc:
                assert "injected_projection_failure" in str(exc)
        assert case.fx.connection.execute(
            f"SELECT attempt_state FROM {ATTEMPTS}"
        ).fetchone()[0] == "ELIGIBILITY_COMPLETE"
        assert case.fx.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind='WINDOW_4H'"
        ).fetchone()[0] == 0
        assert set(_dispositions(case).values()) == {"ELIGIBLE_PENDING_HANDOFF"}
    finally:
        case.tearDown()


def test_postcommit_progression_failure_cannot_rewrite_predecessor_truth() -> None:
    case, _binding = _ready_progression_fixture()
    try:
        before = [
            tuple(row)
            for row in case.fx.connection.execute(
                """SELECT s.id,s.step_status,j.status,w.work_state,cw.window_state
                   FROM printer_memory_factory_run_steps AS s
                   JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
                   JOIN printer_memory_factory_campaign_scheduler_work AS w
                     ON w.scheduler_job_id=s.scheduler_job_id
                   JOIN printer_memory_factory_campaign_windows AS cw
                     ON cw.window_id=w.window_id
                   WHERE s.run_id='factory-run-1'
                     AND s.step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')
                   ORDER BY s.id"""
            )
        ]
        from printer_v1.operator_cli.operational_standard_4h import (
            StandardFourHourOperationalError,
            run_standard_four_hour_campaign_barrier,
        )

        try:
            run_standard_four_hour_campaign_barrier(
                case.fx.connection,
                db_path=case.fx.db,
                campaign_id="campaign-1h",
                configuration_id="config-1h",
                run_id="run-1h",
                cycle_id="cycle-1h",
                factory_run_id="factory-run-1",
                operational_db_binding=None,
                canonical_authoritative_db_path=case.fx.db,
                cancellation_probe=lambda: None,
            )
            raise AssertionError("real post-commit progression failure did not surface")
        except StandardFourHourOperationalError as exc:
            assert "OPERATIONAL_DB_BINDING_MISSING" in str(exc)
            from printer_v1.operator_cli.one_command_15m_factory import (
                _durable_standard_4h_progression_stop_cause,
            )

            assert _durable_standard_4h_progression_stop_cause(
                case.fx.connection,
                campaign_id="campaign-1h",
                campaign_run_id="run-1h",
                cycle_id="cycle-1h",
                exc=exc,
            ) == "OPERATIONAL_DB_BINDING_MISSING"
        attempt = case.fx.connection.execute(
            f"SELECT attempt_state,first_terminal_cause FROM {ATTEMPTS}"
        ).fetchone()
        assert tuple(attempt) == ("TERMINAL_FAILED", "OPERATIONAL_DB_BINDING_MISSING")
        after = [
            tuple(row)
            for row in case.fx.connection.execute(
                """SELECT s.id,s.step_status,j.status,w.work_state,cw.window_state
                   FROM printer_memory_factory_run_steps AS s
                   JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
                   JOIN printer_memory_factory_campaign_scheduler_work AS w
                     ON w.scheduler_job_id=s.scheduler_job_id
                   JOIN printer_memory_factory_campaign_windows AS cw
                     ON cw.window_id=w.window_id
                   WHERE s.run_id='factory-run-1'
                     AND s.step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')
                   ORDER BY s.id"""
            )
        ]
        assert after == before
        assert all(row[1:] == ("SUCCEEDED", "SUCCEEDED", "SUCCEEDED", "CLEAN_PROMOTED") for row in after)
    finally:
        case.tearDown()


def test_handoff_rereads_cancellation_and_persists_progression_primary() -> None:
    case, binding = _ready_progression_fixture()
    try:
        calls = 0

        def cancellation_changes_after_evaluation():
            nonlocal calls
            calls += 1
            return None if calls <= 2 else "OPERATOR_EXTERNAL_STOP"

        from printer_v1.operator_cli.operational_standard_4h import (
            StandardFourHourOperationalError,
            run_standard_four_hour_campaign_barrier,
        )

        try:
            run_standard_four_hour_campaign_barrier(
                case.fx.connection,
                db_path=case.fx.db,
                campaign_id="campaign-1h",
                configuration_id="config-1h",
                run_id="run-1h",
                cycle_id="cycle-1h",
                factory_run_id="factory-run-1",
                operational_db_binding=binding,
                canonical_authoritative_db_path=case.fx.db,
                cancellation_probe=cancellation_changes_after_evaluation,
            )
            raise AssertionError("handoff cancellation recheck did not fail closed")
        except StandardFourHourOperationalError as exc:
            assert "OPERATOR_EXTERNAL_STOP" in str(exc)
        attempt = case.fx.connection.execute(
            f"SELECT attempt_state,first_terminal_cause FROM {ATTEMPTS}"
        ).fetchone()
        assert tuple(attempt) == (
            "TERMINAL_CANCELLED",
            "OPERATOR_EXTERNAL_STOP",
        )
        assert case.fx.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind='WINDOW_4H'"
        ).fetchone()[0] == 0
    finally:
        case.tearDown()


def test_atomic_handoff_cancellation_recheck_rolls_back_before_any_child() -> None:
    case, binding = _ready_progression_fixture()
    try:
        calls = 0

        def cancellation_changes_inside_atomic_handoff():
            nonlocal calls
            calls += 1
            return None if calls <= 3 else "OPERATOR_EXTERNAL_STOP"

        from printer_v1.operator_cli.operational_standard_4h import (
            StandardFourHourOperationalError,
            run_standard_four_hour_campaign_barrier,
        )

        try:
            run_standard_four_hour_campaign_barrier(
                case.fx.connection,
                db_path=case.fx.db,
                campaign_id="campaign-1h",
                configuration_id="config-1h",
                run_id="run-1h",
                cycle_id="cycle-1h",
                factory_run_id="factory-run-1",
                operational_db_binding=binding,
                canonical_authoritative_db_path=case.fx.db,
                cancellation_probe=cancellation_changes_inside_atomic_handoff,
            )
            raise AssertionError("atomic cancellation did not fail closed")
        except StandardFourHourOperationalError as exc:
            assert "OPERATOR_EXTERNAL_STOP" in str(exc)
        assert tuple(case.fx.connection.execute(
            f"SELECT attempt_state,first_terminal_cause FROM {ATTEMPTS}"
        ).fetchone()) == ("TERMINAL_CANCELLED", "OPERATOR_EXTERNAL_STOP")
        assert case.fx.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind='WINDOW_4H'"
        ).fetchone()[0] == 0
        assert set(_dispositions(case).values()) == {"ELIGIBLE_PENDING_HANDOFF"}
    finally:
        case.tearDown()


def test_handoff_rereads_exact_token_budget_before_creating_children() -> None:
    case, binding = _ready_progression_fixture()
    try:
        result = _evaluate(case, binding)
        assert result["eligible_token_slot_ids"] == ["slot-1", "slot-2"]
        _insert_run_requests(case, count=50, step_prefix="t1_late_")

        from printer_v1.operator_cli.operational_standard_4h import (
            StandardFourHourOperationalError,
            run_standard_four_hour_campaign_barrier,
        )

        try:
            run_standard_four_hour_campaign_barrier(
                case.fx.connection,
                db_path=case.fx.db,
                campaign_id="campaign-1h",
                configuration_id="config-1h",
                run_id="run-1h",
                cycle_id="cycle-1h",
                factory_run_id="factory-run-1",
                operational_db_binding=binding,
                canonical_authoritative_db_path=case.fx.db,
                cancellation_probe=lambda: None,
            )
            raise AssertionError("late token-budget breach did not fail closed")
        except StandardFourHourOperationalError:
            pass
        attempt = case.fx.connection.execute(
            f"SELECT attempt_state,first_terminal_cause FROM {ATTEMPTS}"
        ).fetchone()
        assert str(attempt[0]) == "TERMINAL_FAILED"
        assert "standard 4h token slot-1 request" in str(attempt[1])
        assert case.fx.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind='WINDOW_4H'"
        ).fetchone()[0] == 0
    finally:
        case.tearDown()


def test_claimed_four_hour_work_is_running_or_interrupted_from_real_ownership() -> None:
    case, binding = _ready_progression_fixture()
    try:
        progression = importlib.import_module(
            "printer_v1.operator_cli.standard_4h_progression"
        )
        _evaluate(case, binding)
        progression.commit_standard_4h_progression_handoff(
            case.fx.connection,
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            factory_run_id="factory-run-1",
            db_path=case.fx.db,
            configuration_id="config-1h",
            operational_db_binding=binding,
            canonical_authoritative_db_path=case.fx.db,
            cancellation_probe=lambda: None,
        )
        job = case.fx.connection.execute(
            """SELECT s.scheduler_job_id
               FROM printer_memory_factory_run_steps AS s
               WHERE s.run_id='factory-run-1' AND s.token_id=1
                 AND s.step_kind LIKE 'LONG_CONTINUATION_%'
               ORDER BY s.id LIMIT 1"""
        ).fetchone()
        with case.fx.connection:
            case.fx.connection.execute(
                "UPDATE printer_scheduler_jobs SET status='RUNNING',"
                "locked_at=?,lock_owner='lane3-worker' WHERE id=?",
                ("2026-08-23T00:00:00+00:00", int(job[0])),
            )
        active = progression.derive_standard_4h_progression_status(
            case.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            ownership_active=True,
        )
        stopped = progression.derive_standard_4h_progression_status(
            case.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
            ownership_active=False,
        )
        active_by_slot = {row["token_slot_id"]: row["outcome"] for row in active["per_token"]}
        stopped_by_slot = {row["token_slot_id"]: row["outcome"] for row in stopped["per_token"]}
        assert active_by_slot["slot-1"] == "RUNNING"
        assert stopped_by_slot["slot-1"] == "INTERRUPTED_AMBIGUOUS"
        assert active_by_slot["slot-2"] == "CREATED_PENDING"
    finally:
        case.tearDown()


def test_scheduler_failure_and_cancellation_remain_distinct_in_shared_read() -> None:
    for scheduler_state, expected in (("FAILED", "FAILED"), ("CANCELLED", "CANCELLED")):
        case, binding = _ready_progression_fixture()
        try:
            progression = importlib.import_module(
                "printer_v1.operator_cli.standard_4h_progression"
            )
            _evaluate(case, binding)
            progression.commit_standard_4h_progression_handoff(
                case.fx.connection,
                campaign_id="campaign-1h",
                campaign_run_id="run-1h",
                cycle_id="cycle-1h",
                factory_run_id="factory-run-1",
                db_path=case.fx.db,
                configuration_id="config-1h",
                operational_db_binding=binding,
                canonical_authoritative_db_path=case.fx.db,
                cancellation_probe=lambda: None,
            )
            job = case.fx.connection.execute(
                """SELECT s.scheduler_job_id
                   FROM printer_memory_factory_run_steps AS s
                   WHERE s.run_id='factory-run-1' AND s.token_id=1
                     AND s.step_kind LIKE 'LONG_CONTINUATION_%'
                   ORDER BY s.id LIMIT 1"""
            ).fetchone()
            with case.fx.connection:
                case.fx.connection.execute(
                    "UPDATE printer_scheduler_jobs SET status=? WHERE id=?",
                    (scheduler_state, int(job[0])),
                )
            status = progression.derive_standard_4h_progression_status(
                case.fx.connection,
                factory_run_id="factory-run-1",
                campaign_id="campaign-1h",
                campaign_run_id="run-1h",
                cycle_id="cycle-1h",
                ownership_active=True,
            )
            by_slot = {
                row["token_slot_id"]: row["outcome"]
                for row in status["per_token"]
            }
            assert by_slot["slot-1"] == expected
            assert by_slot["slot-2"] == "CREATED_PENDING"
        finally:
            case.tearDown()


def test_terminal_validator_uses_shared_eligible_not_created_truth() -> None:
    case, binding = _ready_progression_fixture()
    try:
        _evaluate(case, binding)
        from printer_v1.operator_cli.one_command_15m_factory import (
            _standard_campaign_four_hour_terminal_validation,
        )

        validation = _standard_campaign_four_hour_terminal_validation(
            case.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            run_id="run-1h",
            cycle_id="cycle-1h",
        )
        assert validation["complete"] is False
        assert validation["aggregate_state"] == "ELIGIBILITY_COMPLETE"
        assert [row["outcome"] for row in validation["per_token"]] == [
            "ELIGIBLE_NOT_CREATED",
            "ELIGIBLE_NOT_CREATED",
        ]
    finally:
        case.tearDown()


def test_stopped_ownership_terminalizes_stranded_evaluation_for_review() -> None:
    case, binding = _ready_progression_fixture()
    try:
        progression = importlib.import_module(
            "printer_v1.operator_cli.standard_4h_progression"
        )
        with patch.object(
            progression,
            "load_durable_operational_database_target_expectation",
            side_effect=RuntimeError("injected_authority_read_interruption"),
        ):
            try:
                _evaluate(case, binding)
                raise AssertionError("authority read interruption did not propagate")
            except RuntimeError as exc:
                assert "injected_authority_read_interruption" in str(exc)
        assert case.fx.connection.execute(
            f"SELECT attempt_state FROM {ATTEMPTS}"
        ).fetchone()[0] == "EVALUATING"
        with case.fx.connection:
            progression.terminalize_stopped_standard_4h_progression(
                case.fx.connection,
                campaign_id="campaign-1h",
                campaign_run_id="run-1h",
                cycle_id="cycle-1h",
                stop_cause="SAFE_STOP_OPERATOR_INTERRUPTED",
            )
        row = case.fx.connection.execute(
            f"SELECT attempt_state,first_terminal_cause FROM {ATTEMPTS}"
        ).fetchone()
        assert tuple(row) == (
            "INTERRUPTED_REVIEW",
            "SAFE_STOP_OPERATOR_INTERRUPTED",
        )
        status = progression.derive_standard_4h_progression_status(
            case.fx.connection,
            factory_run_id="factory-run-1",
            campaign_id="campaign-1h",
            campaign_run_id="run-1h",
            cycle_id="cycle-1h",
        )
        assert status["aggregate_state"] == "INTERRUPTED_AMBIGUOUS"
        assert status["requires_review"] is True
        assert status["complete"] is False
    finally:
        case.tearDown()


def test_migration_does_not_backfill_legacy_standard_campaigns(tmp_path) -> None:
    db = tmp_path / "legacy-no-inference.sqlite3"
    migrations = canonical_migration_names()
    assert migrations[-2] == "061_standard_4h_progression_fault_preservation.sql"
    assert migrations[-1] == "062_pre_admission_attempt_evidence.sql"
    connection = sqlite3.connect(db)
    try:
        from printer_v1.db import migrate as migration_runner

        connection.execute(
            "CREATE TABLE printer_schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
        )
        for name in migrations[:-2]:
            connection.executescript(
                (migration_runner.MIGRATIONS_DIR / name).read_text(encoding="utf-8")
            )
            connection.execute(
                "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                (name,),
            )
        connection.commit()
        before = connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaigns"
        ).fetchone()[0]
    finally:
        connection.close()

    apply_migrations(db)
    connection = sqlite3.connect(db)
    try:
        assert connection.execute(f"SELECT COUNT(*) FROM {ATTEMPTS}").fetchone()[0] == 0
        assert connection.execute(f"SELECT COUNT(*) FROM {TOKENS}").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaigns"
        ).fetchone()[0] == before
    finally:
        connection.close()


def _factory_loop_operational_binding(db) -> object:
    from tests.test_v2_9_8b_four_token_factory_wake_ordering import (
        CAMPAIGN_ID,
        CAMPAIGN_RUN_ID,
        CONFIGURATION_ID,
        CYCLE_ID,
    )

    values = {
        "target_kind": PRODUCTION_AUTHORITATIVE,
        "resolved_db_path": str(db.resolve()),
        "authorized_pre_mutation_sha256": "a" * 64,
        "migration_count": canonical_migration_count(),
        "migration_head": canonical_migration_names()[-1],
        "authorization_id": "lane3-factory-loop-authorization",
        "authorization_marker_sha256": "b" * 64,
        "application_marker_sha256": "c" * 64,
        "execution_id": "lane3-factory-loop-execution",
        "campaign_id": CAMPAIGN_ID,
        "campaign_run_id": CAMPAIGN_RUN_ID,
        "cycle_id": CYCLE_ID,
        "configuration_id": CONFIGURATION_ID,
        "authorization_consumed_once": True,
        "invocation_count": 1,
        "allowed_invocation_count": 1,
        "automatic_retry_allowed": False,
        "manual_rerun_allowed": False,
        "resume_allowed": False,
        "restart_allowed": False,
        "successor_allowed": False,
    }
    expectation = build_durable_operational_database_target_expectation(
        **values,
        durable_db_target_identity="sha256:" + "a" * 64,
    )
    connection = sqlite3.connect(db)
    try:
        row = connection.execute(
            "SELECT configuration_json FROM "
            "printer_memory_factory_campaign_configurations "
            "WHERE campaign_id=? AND configuration_id=?",
            (CAMPAIGN_ID, CONFIGURATION_ID),
        ).fetchone()
        configuration = json.loads(str(row[0]))
        configuration["operational_database_target_expectation"] = expectation
        immutable_triggers = connection.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='trigger' "
            "AND tbl_name='printer_memory_factory_campaign_configurations'"
        ).fetchall()
        for trigger in immutable_triggers:
            connection.execute(f'DROP TRIGGER "{str(trigger[0])}"')
        connection.execute(
            "UPDATE printer_memory_factory_campaign_configurations "
            "SET configuration_json=? WHERE campaign_id=? AND configuration_id=?",
            (
                json.dumps(configuration, sort_keys=True),
                CAMPAIGN_ID,
                CONFIGURATION_ID,
            ),
        )
        for trigger in immutable_triggers:
            connection.execute(str(trigger[1]))
        connection.commit()
    finally:
        connection.close()
    return build_operational_database_target_binding(**values)


def _promote_factory_window(connection, *, window_id: int, snapshot_id: int) -> None:
    if connection.execute(
        "SELECT 1 FROM printer_episodes WHERE memory_window_id=?",
        (int(window_id),),
    ).fetchone() is not None:
        return
    row = connection.execute(
        "SELECT supporting_context_json FROM printer_memory_windows WHERE id=?",
        (int(window_id),),
    ).fetchone()
    context = json.loads(str(row[0]))
    context["e2q_audited"] = True
    context["e2q_audited_by"] = "lane_e2q"
    context.setdefault("snapshot_id", int(snapshot_id))
    connection.execute(
        "UPDATE printer_memory_windows SET memory_status='PARTIAL_MEMORY', "
        "data_quality_label='CLEAN_DATA', "
        "memory_quality_label='PARTIAL_MEMORY', do_not_train=0, "
        "outcome_label='CONSOLIDATION', supporting_context_json=? WHERE id=?",
        (json.dumps(context, sort_keys=True), int(window_id)),
    )
    promote_clean_object(connection, window_id=int(window_id))


def _attach_factory_acceptable_safety(connection, *, window_id: int) -> None:
    window = connection.execute(
        """SELECT w.token_id,w.pair_id,w.snapshot_end_id,w.window_end_at,
                  t.token_mint,p.pair_address,w.supporting_context_json
             FROM printer_memory_windows AS w
             JOIN printer_tokens AS t ON t.id=w.token_id
             JOIN printer_pairs AS p ON p.id=w.pair_id
            WHERE w.id=?""",
        (int(window_id),),
    ).fetchone()
    observed_at = (
        datetime.fromisoformat(str(window[3])) - timedelta(seconds=60)
    ).isoformat()
    request = connection.execute(
        """INSERT INTO printer_source_requests(
               source_name,request_kind,requested_at,source_status,data_quality_label
           ) VALUES ('goplus','SAFETY',?,'COMPLETE','CLEAN_DATA')""",
        (observed_at,),
    )
    response = connection.execute(
        """INSERT INTO printer_source_responses(
               source_request_id,source_name,received_at,source_status,
               data_quality_label
           ) VALUES (?,'goplus',?,'COMPLETE','CLEAN_DATA')""",
        (int(request.lastrowid), observed_at),
    )
    composite = connection.execute(
        """INSERT INTO printer_safety_evidence_composites(
               token_id,pair_id,snapshot_id,memory_window_id,policy_version,
               token_mint,pair_address,evidence_captured_at,source_status,
               data_quality_label,target_status,freshness_label,
               mint_authority_status,freeze_authority_status,
               metadata_mutability_status,supply_sanity_label,
               holder_concentration_label,liquidity_lock_or_burn_label,
               known_risk_flag_label,token_program_label,safety_context_label,
               safety_contract_label,provenance_complete,conflicts_json,
               blockers_json,optional_unknowns_json,field_bindings_json,
               paper_only_context
           ) VALUES (?,?,?,?, 'lane3-factory-boundary',?,?,?,
               'COMPLETE','CLEAN_DATA','TARGET_MATCH','SAFETY_EVIDENCE_FRESH',
               'MINT_AUTHORITY_RENOUNCED','FREEZE_AUTHORITY_DISABLED',
               'METADATA_IMMUTABLE','SUPPLY_SANITY_OK',
               'HOLDER_CONCENTRATION_HEALTHY','LIQUIDITY_LOCK_OR_BURN_UNKNOWN',
               'KNOWN_RISK_FLAGS_UNKNOWN','SPL_TOKEN_OR_TOKEN_2022_VERIFIED',
               'SAFETY_UNKNOWN','SAFETY_ACCEPTABLE_FOR_15M_MEMORY_ONLY',1,
               '[]','[]','["liquidity_lock_or_burn_label"]','{}',1)""",
        (
            int(window[0]),
            int(window[1]),
            int(window[2]),
            int(window_id),
            str(window[4]),
            str(window[5]),
            observed_at,
        ),
    )
    connection.execute(
        """INSERT INTO printer_safety_evidence_contributions(
               composite_id,source_name,evidence_category,source_request_id,
               source_response_id,captured_at,freshness_label,token_mint,
               pair_address,fields_supplied_json,source_status,
               data_quality_label,target_status
           ) VALUES (?,'goplus','TOKEN_SAFETY',?,?,?,
               'SAFETY_EVIDENCE_FRESH',?,?,'{}','COMPLETE','CLEAN_DATA',
               'TARGET_MATCH')""",
        (
            int(composite.lastrowid),
            int(request.lastrowid),
            int(response.lastrowid),
            observed_at,
            str(window[4]),
            str(window[5]),
        ),
    )
    context = json.loads(str(window[6]))
    overlays = dict(context.get("memory_build_evidence_overlays") or {})
    overlays["safety_composite_id"] = int(composite.lastrowid)
    context["memory_build_evidence_overlays"] = overlays
    connection.execute(
        "UPDATE printer_memory_windows SET supporting_context_json=? WHERE id=?",
        (json.dumps(context, sort_keys=True), int(window_id)),
    )


def _run_standard_factory_loop(
    tmp_path,
    monkeypatch,
    *,
    operational_binding,
    disposable_binding,
    fail_progression_binding=False,
    progression_predecessor_observations=None,
):
    from printer_v1.operator_cli import one_command_15m_factory as factory
    from printer_v1.operator_cli import operational_standard_4h as standard
    from tests.test_v2_9_8b_four_token_factory_terminal_integration import (
        _discovery,
    )
    from tests.test_v2_9_8b_four_token_factory_wake_ordering import (
        CAMPAIGN_ID,
        CAMPAIGN_RUN_ID,
        CONFIGURATION_ID,
        CYCLE_ID,
        FACTORY_RUN_ID,
        START,
        _prepare,
    )

    db, backup, prepared_disposable = _prepare(tmp_path)
    if disposable_binding == "PREPARED":
        disposable_binding = prepared_disposable
    if operational_binding == "VALID":
        operational_binding = _factory_loop_operational_binding(db)
    configuration_id = CONFIGURATION_ID
    acquire_campaign_supervision(
        db,
        lock_path=tmp_path / "lane3-factory-loop.lease.json",
        supervision_id="lane3-factory-loop-supervision",
        campaign_id=CAMPAIGN_ID,
        configuration_id=configuration_id,
        run_id=CAMPAIGN_RUN_ID,
        owner_id="lane3-factory-loop-owner",
        lease_seconds=30_000,
        now=datetime.now(timezone.utc),
    )
    clock = _FactoryLoopClock(START)
    _FactoryLoopDateTime.clock = clock
    monkeypatch.setattr(factory, "_now", clock.now)
    monkeypatch.setattr("printer_v1.sources.contracts.datetime", _FactoryLoopDateTime)
    monkeypatch.setattr(
        "printer_v1.operator_cli.proof_db_schema_readiness.CANONICAL_PERSISTENT_DB",
        db,
    )
    real_selective_barrier = factory._run_selective_1h_campaign_barrier

    def selective_barrier_with_clean_predecessors(
        connection, *, db_path, run_id, config, continuation_seconds, cycle_id=None
    ):
        closes = factory._authoritative_terminal_15m_closes(
            connection, run_id, cycle_id=cycle_id
        )
        expected = factory._operational_activated_token_count(
            connection, run_id, cycle_id=cycle_id
        )
        if len(closes) == expected:
            for close in closes:
                window_id = int(close["memory_window_id"])
                _promote_factory_window(
                    connection,
                    window_id=window_id,
                    snapshot_id=int(close["snapshot_id"] or 1),
                )
            connection.commit()
        return real_selective_barrier(
            connection,
            db_path=db_path,
            run_id=run_id,
            config=config,
            continuation_seconds=continuation_seconds,
            cycle_id=cycle_id,
        )

    monkeypatch.setattr(
        factory,
        "_run_selective_1h_campaign_barrier",
        selective_barrier_with_clean_predecessors,
    )
    real_campaign_work_sync = factory._sync_owned_campaign_scheduler_job

    def preserve_running_campaign_work_across_scheduler_yield(
        connection, *, scheduler_job_id
    ):
        state = connection.execute(
            "SELECT j.status,w.work_state FROM printer_scheduler_jobs AS j "
            "JOIN printer_memory_factory_campaign_scheduler_work AS w "
            "ON w.scheduler_job_id=j.id WHERE j.id=?",
            (int(scheduler_job_id),),
        ).fetchone()
        if state is not None and tuple(state) == ("PENDING", "RUNNING"):
            return "RUNNING"
        return real_campaign_work_sync(
            connection, scheduler_job_id=int(scheduler_job_id)
        )

    monkeypatch.setattr(
        factory,
        "_sync_owned_campaign_scheduler_job",
        preserve_running_campaign_work_across_scheduler_yield,
    )
    monkeypatch.setattr(
        factory,
        "_capture_same_stream_5m_support",
        lambda *_args, **_kwargs: {
            "captured": False,
            "verdict": "VALID_NO_CAPTURE",
            "reason": "LANE3_FACTORY_BOUNDARY_FIXTURE_NO_MICRO_EVENT",
            "window_5m_id": None,
        },
    )
    real_opening_planner = factory._plan_opening_jobs

    def plan_owned_cycle_one_opening(
        connection,
        run_id,
        targets,
        scheduled_for,
        first_commit_callback=None,
        operation_observer=None,
        cycle_ordinal=1,
        four_token_proof=False,
    ):
        del four_token_proof
        row = connection.execute(
            "SELECT config_json FROM printer_memory_factory_runs WHERE run_id=?",
            (run_id,),
        ).fetchone()
        run_config = json.loads(str(row[0]))
        run_config["four_token_proof"] = True
        connection.execute(
            "UPDATE printer_memory_factory_runs SET config_json=? WHERE run_id=?",
            (json.dumps(run_config, sort_keys=True), run_id),
        )
        return real_opening_planner(
            connection,
            run_id,
            targets,
            scheduled_for,
            first_commit_callback=first_commit_callback,
            operation_observer=operation_observer,
            cycle_ordinal=cycle_ordinal,
            four_token_proof=True,
        )

    monkeypatch.setattr(
        factory, "_plan_opening_jobs", plan_owned_cycle_one_opening
    )
    real_close_audit = factory._execute_close_audit_phase

    def close_audit_with_clean_first_hour(connection, step, **kwargs):
        result = real_close_audit(connection, step, **kwargs)
        if (
            str(step["step_kind"]) == "CONTINUATION_CLOSE_AUDIT"
            and result.get("ok")
            and result.get("memory_window_id") is not None
        ):
            _attach_factory_acceptable_safety(
                connection, window_id=int(result["memory_window_id"])
            )
            _promote_factory_window(
                connection,
                window_id=int(result["memory_window_id"]),
                snapshot_id=int(result.get("snapshot_id") or 1),
            )
        return result

    monkeypatch.setattr(
        factory, "_execute_close_audit_phase", close_audit_with_clean_first_hour
    )
    if fail_progression_binding:
        real_progression_barrier = standard.run_standard_four_hour_campaign_barrier

        def progression_barrier_with_missing_binding(*args, **kwargs):
            if progression_predecessor_observations is not None:
                progression_predecessor_observations.extend(
                    tuple(row)
                    for row in args[0].execute(
                        """SELECT s.id,s.step_status,s.scheduler_job_id,
                                  j.status,w.work_state,
                                  cw.window_state,cw.first_terminal_cause
                             FROM printer_memory_factory_run_steps AS s
                             JOIN printer_scheduler_jobs AS j
                               ON j.id=s.scheduler_job_id
                             JOIN printer_memory_factory_campaign_scheduler_work AS w
                               ON w.scheduler_job_id=s.scheduler_job_id
                              AND w.ownership_contract_version='V2_STAGE_SCOPED'
                             JOIN printer_memory_factory_campaign_windows AS cw
                               ON cw.window_id=w.window_id
                            WHERE s.run_id=?
                              AND s.step_kind IN (
                                  'CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT'
                              )
                              AND s.step_status='SUCCEEDED'
                            ORDER BY s.id""",
                        (kwargs["factory_run_id"],),
                    ).fetchall()
                )
            kwargs["operational_db_binding"] = None
            return real_progression_barrier(*args, **kwargs)

        monkeypatch.setattr(
            standard,
            "run_standard_four_hour_campaign_barrier",
            progression_barrier_with_missing_binding,
        )
    report = factory.run_one_command_15m_factory(
        db,
        backup,
        operator_approved=True,
        proof_mode=False,
        operational_persistent_mode=True,
        operational_database_target_binding=operational_binding,
        disposable_public_composition_proof_binding=disposable_binding,
        discovery_runner=_discovery(db),
        snapshot_adapter_factory=_factory_loop_snapshot_adapter,
        context_adapter_factories=_factory_loop_context_adapters(clock),
        launch_provenance={
            "git_head": "d" * 40,
            "git_tracked_tree_clean": True,
            "git_staged_changes_present": False,
            "git_unstaged_changes_present": False,
            "git_untracked_present": True,
            "git_provenance_captured_at": START.isoformat(),
        },
        standard_four_hour_campaign=True,
        selective_1h_continuation=True,
        continuous_first_hour=True,
        continuous_four_hour=True,
        total_duration_seconds=20_000,
        _window_seconds=900,
        _continuation_seconds=3_600,
        max_selected_tokens=2,
        max_source_requests=2,
        campaign_id=CAMPAIGN_ID,
        campaign_run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        configuration_id=configuration_id,
        factory_run_id=FACTORY_RUN_ID,
        _sleep=clock.sleep,
        _monotonic=clock.monotonic,
    )
    return db, report


def test_factory_loop_progression_fault_occurs_only_after_committed_1h(
    tmp_path, monkeypatch
) -> None:
    committed_predecessors: list[tuple] = []
    db, report = _run_standard_factory_loop(
        tmp_path,
        monkeypatch,
        operational_binding="VALID",
        disposable_binding=None,
        fail_progression_binding=True,
        progression_predecessor_observations=committed_predecessors,
    )
    connection = sqlite3.connect(db)
    try:
        predecessors = connection.execute(
            """SELECT s.id,s.step_status,s.scheduler_job_id,j.status,w.work_state,
                      cw.window_state,cw.first_terminal_cause
                 FROM printer_memory_factory_run_steps AS s
                 JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
                 JOIN printer_memory_factory_campaign_scheduler_work AS w
                   ON w.scheduler_job_id=s.scheduler_job_id
                  AND w.ownership_contract_version='V2_STAGE_SCOPED'
                 JOIN printer_memory_factory_campaign_windows AS cw
                   ON cw.window_id=w.window_id
                WHERE s.run_id=?
                  AND s.step_kind IN ('CONTINUATION_CLOSE','CONTINUATION_CLOSE_AUDIT')
                  AND s.step_status='SUCCEEDED'
                ORDER BY s.id""",
            ("wake-order-factory",),
        ).fetchall()
        assert len(predecessors) == 2, report["stop_reason"]
        assert all(str(row[1]) == "SUCCEEDED" for row in predecessors)
        assert all(str(row[3]) == "SUCCEEDED" for row in predecessors)
        assert all(str(row[4]) == "SUCCEEDED" for row in predecessors)
        assert all(str(row[5]) == "CLEAN_PROMOTED" for row in predecessors)
        assert all(
            str(row[6]) == "window_1h_closed_clean_promoted"
            for row in predecessors
        )
        assert committed_predecessors[-2:] == [
            tuple(row) for row in predecessors
        ]
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND error_or_skip_reason LIKE '%TOKEN_LOCAL%'",
            ("wake-order-factory",),
        ).fetchone()[0] == 0
        progression = connection.execute(
            f"SELECT attempt_state,first_terminal_cause FROM {ATTEMPTS}"
        ).fetchone()
        assert tuple(progression) == (
            "TERMINAL_FAILED",
            "OPERATIONAL_DB_BINDING_MISSING",
        )
    finally:
        connection.close()
    assert report["stop_reason"] == "OPERATIONAL_DB_BINDING_MISSING"


def test_healthy_factory_loop_uses_one_postcommit_call_site_and_one_handoff(
    tmp_path, monkeypatch
) -> None:
    from printer_v1.operator_cli import operational_standard_4h as standard

    real_barrier = standard.run_standard_four_hour_campaign_barrier
    caller_lines: list[int] = []

    def observe_real_barrier(*args, **kwargs):
        caller_lines.append(int(inspect.currentframe().f_back.f_lineno))
        result = real_barrier(*args, **kwargs)
        if result.get("plan", {}).get("planned") and not result["plan"].get("replay"):
            args[0].commit()
            raise _HandoffCommittedAtFactoryLoop(result)
        return result

    monkeypatch.setattr(
        standard,
        "run_standard_four_hour_campaign_barrier",
        observe_real_barrier,
    )
    try:
        _db, report = _run_standard_factory_loop(
            tmp_path,
            monkeypatch,
            operational_binding="VALID",
            disposable_binding=None,
        )
        raise AssertionError(
            "factory loop did not reach the real Standard-4H handoff: "
            f"calls={caller_lines!r} stop_reason={report['stop_reason']!r}"
        )
    except _HandoffCommittedAtFactoryLoop as reached:
        db = tmp_path / "wake-order.sqlite3"
        barrier = reached.barrier

    assert len(caller_lines) == 2
    assert len(set(caller_lines)) == 1
    assert barrier["plan"]["replay"] is False
    connection = sqlite3.connect(db)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_windows "
            "WHERE window_kind='WINDOW_4H'"
        ).fetchone()[0] == 2
        assert connection.execute(
            f"SELECT COUNT(*) FROM {ATTEMPTS} WHERE attempt_state='HANDOFF_COMMITTED'"
        ).fetchone()[0] == 1
        assert connection.execute(
            f"SELECT COUNT(*) FROM {TOKENS} WHERE token_disposition='HANDOFF_CREATED'"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work "
            "WHERE stage_id='WINDOW_4H'"
        ).fetchone()[0] == int(barrier["planned_jobs"])
    finally:
        connection.close()
