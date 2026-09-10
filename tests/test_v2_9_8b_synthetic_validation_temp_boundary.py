"""V2-9.8B synthetic-validation disposable-state boundary regression."""

from __future__ import annotations

import argparse
import contextlib
import io
from pathlib import Path
import sqlite3

import pytest

from printer_v1.contracts import capability_locks
from printer_v1.db import apply_migrations
from printer_v1.hardening import flow_validation
from printer_v1.operator_cli import commands


LOCK_ERROR = "FULL_SYNTHETIC_VALIDATION_REQUIRES_REGISTERED_TEMP_DB"
MUTATING_STAGE_TABLES = (
    "printer_tokens",
    "printer_pairs",
    "printer_discovery_candidates",
    "printer_token_snapshots",
    "printer_market_regime_snapshots",
    "printer_solana_chain_heat_snapshots",
    "printer_safety_rug_snapshots",
    "printer_liquidity_exit_snapshots",
    "printer_trading_flow_snapshots",
    "printer_chart_volatility_snapshots",
    "printer_micro_events",
    "printer_memory_windows",
    "printer_episodes",
    "printer_memory_retrieval_queries",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_audit_reports",
    "printer_validation_runs",
)


def _counts(db_path: Path) -> dict[str, int]:
    connection = sqlite3.connect(db_path)
    try:
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in MUTATING_STAGE_TABLES
        }
    finally:
        connection.close()


def _enable_future_synthetic_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capability_locks, "RETRIEVAL_ACTIVATION_ENABLED", True)
    monkeypatch.setattr(capability_locks, "PAPER_DECISIONS_ENABLED", True)
    monkeypatch.setattr(capability_locks, "PAPER_POSITIONS_ENABLED", True)
    monkeypatch.setattr(capability_locks, "PAPER_AUDITS_ENABLED", True)
    monkeypatch.setattr(capability_locks, "PAPER_PNL_ENABLED", True)


def test_unregistered_full_flow_path_fails_before_stage_one(tmp_path: Path) -> None:
    db_path = tmp_path / "operator-supplied.sqlite3"
    apply_migrations(db_path)
    before = _counts(db_path)

    with pytest.raises(ValueError, match=LOCK_ERROR):
        flow_validation.run_full_synthetic_validation_flow(db_path)

    assert _counts(db_path) == before
    assert before == {table: 0 for table in MUTATING_STAGE_TABLES}


def test_raw_sqlite_connection_cannot_bypass_temp_registration(tmp_path: Path) -> None:
    db_path = tmp_path / "connection-target.sqlite3"
    apply_migrations(db_path)
    before = _counts(db_path)
    connection = sqlite3.connect(db_path)
    try:
        with pytest.raises(ValueError, match=LOCK_ERROR):
            flow_validation.run_full_synthetic_validation_flow(connection)
    finally:
        connection.close()

    assert _counts(db_path) == before


def test_cli_explicit_db_path_fails_without_mutating_target(tmp_path: Path) -> None:
    db_path = tmp_path / "explicit-cli-target.sqlite3"
    apply_migrations(db_path)
    before = _counts(db_path)
    args = argparse.Namespace(
        project_root=None,
        db_path=str(db_path),
        temp_only=True,
    )

    with pytest.raises(ValueError, match=LOCK_ERROR):
        commands.build_synthetic_validation_payload(args)

    assert _counts(db_path) == before

    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        exit_code = commands.main_synthetic_validation(
            ["--db-path", str(db_path), "--format", "json"]
        )
    assert exit_code == 1
    assert LOCK_ERROR in stream.getvalue()
    assert _counts(db_path) == before


def test_temp_initializer_rejects_non_temp_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    declared_system_temp = tmp_path / "declared-system-temp"
    declared_system_temp.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(flow_validation.tempfile, "gettempdir", lambda: str(declared_system_temp))

    with pytest.raises(ValueError, match=LOCK_ERROR):
        flow_validation.initialize_temp_validation_db(outside)

    assert not (outside / "printer_v1_phase20_validation.sqlite3").exists()


def test_registered_temp_full_flow_remains_testable_and_one_shot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _enable_future_synthetic_capabilities(monkeypatch)
    db_path = flow_validation.initialize_temp_validation_db(tmp_path)

    payload = flow_validation.run_full_synthetic_validation_flow(
        db_path,
        project_root=tmp_path,
    )
    assert payload["completed_stage"] == "FLOW_STAGE_COMPLETE"
    assert payload["synthetic_only"] is True
    assert payload["temp_db_only"] is True
    assert payload["project_db_created"] is False
    after_first = _counts(db_path)
    assert after_first["printer_validation_runs"] == 1
    assert after_first["printer_tokens"] == 1
    assert after_first["printer_paper_decisions"] == 1

    with pytest.raises(ValueError, match=LOCK_ERROR):
        flow_validation.run_full_synthetic_validation_flow(db_path, project_root=tmp_path)

    assert _counts(db_path) == after_first
