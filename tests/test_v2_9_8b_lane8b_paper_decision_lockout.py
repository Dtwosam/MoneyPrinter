"""V2-9.8B regression for the legacy post-RC Lane 8B decision bypass."""

from __future__ import annotations

import argparse
import sqlite3

import pytest

from printer_v1.contracts import capability_locks
from printer_v1.contracts.capability_locks import CapabilityLockedError
from printer_v1.db import apply_migrations
from printer_v1.operator_cli import commands


def _args(db_path: str) -> argparse.Namespace:
    return argparse.Namespace(
        db_path=db_path,
        project_root=None,
        format="json",
        no_color=True,
        operator_approved=True,
        chain="solana",
        decision="WAIT",
        token_id=10,
        pair_id=10,
        memory_window_id=23,
        window_kind="WINDOW_15M",
    )


def _legacy_args(db_path: str) -> argparse.Namespace:
    return argparse.Namespace(
        db_path=db_path,
        project_root=None,
        format="json",
        no_color=True,
        operator_approved=True,
        retrieval_query_id=1,
        snapshot_id=None,
        token_mint=None,
        token_id=None,
        pair_address=None,
        pair_id=None,
        chain="solana",
    )


def _decision_count(db_path) -> int:
    connection = sqlite3.connect(db_path)
    try:
        return int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_paper_decisions"
            ).fetchone()[0]
        )
    finally:
        connection.close()


def _assert_decision_lock(exc: pytest.ExceptionInfo[CapabilityLockedError]) -> None:
    assert exc.value.code == "PAPER_DECISIONS_LOCKED"
    assert str(exc.value) == "PAPER_DECISIONS_LOCKED"


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "lane8b-lockout.sqlite3"
    apply_migrations(path)
    monkeypatch.setattr(capability_locks, "PAPER_DECISIONS_ENABLED", False)
    return path


def test_lane8b_builder_fails_before_db_resolution_when_decisions_locked(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(capability_locks, "PAPER_DECISIONS_ENABLED", False)
    missing = tmp_path / "must-not-be-opened.sqlite3"

    with pytest.raises(CapabilityLockedError) as exc:
        commands.build_conservative_paper_decision_payload(_args(str(missing)))

    _assert_decision_lock(exc)
    assert not missing.exists()


def test_lane8b_private_insert_fails_before_sql_when_decisions_locked(db_path) -> None:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        with pytest.raises(CapabilityLockedError) as exc:
            commands._lane8b_insert_conservative_decision(
                connection,
                token_id=10,
                pair_id=10,
                memory_window_id=23,
                action="WAIT",
                window_kind="WINDOW_15M",
            )
        _assert_decision_lock(exc)
    finally:
        connection.close()

    assert _decision_count(db_path) == 0


def test_lane8b_public_builder_writes_no_decision_rows_while_locked(db_path) -> None:
    before = _decision_count(db_path)

    with pytest.raises(CapabilityLockedError) as exc:
        commands.build_conservative_paper_decision_payload(_args(str(db_path)))

    _assert_decision_lock(exc)
    assert _decision_count(db_path) == before == 0


def test_legacy_decision_builder_fails_before_db_resolution_when_locked(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(capability_locks, "PAPER_DECISIONS_ENABLED", False)
    missing = tmp_path / "legacy-must-not-be-opened.sqlite3"

    with pytest.raises(CapabilityLockedError) as exc:
        commands.build_create_paper_decision_once_payload(
            _legacy_args(str(missing))
        )

    _assert_decision_lock(exc)
    assert not missing.exists()


def test_legacy_private_insert_fails_before_sql_when_locked(db_path) -> None:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        with pytest.raises(CapabilityLockedError) as exc:
            commands._insert_blocked_paper_decision(
                connection,
                target={},
                gate_summary={},
                report={},
            )
        _assert_decision_lock(exc)
    finally:
        connection.close()

    assert _decision_count(db_path) == 0


def test_legacy_cli_emits_only_lock_error_and_writes_nothing(
    db_path,
    capsys,
) -> None:
    exit_code = commands.main_create_paper_decision_once(
        [
            "--db-path",
            str(db_path),
            "--format",
            "json",
            "--no-color",
            "--operator-approved",
            "--retrieval-query-id",
            "1",
            "--chain",
            "solana",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "PAPER_DECISIONS_LOCKED" in captured.out
    assert "PAPER_DECISION_PROPOSED" not in captured.out
    assert "paper_decision_id" not in captured.out
    assert captured.err == ""
    assert _decision_count(db_path) == 0


def test_lane8b_cli_emits_only_lock_error_and_writes_nothing(
    db_path,
    capsys,
) -> None:
    exit_code = commands.main_create_conservative_paper_decision_once(
        [
            "--db-path",
            str(db_path),
            "--format",
            "json",
            "--no-color",
            "--operator-approved",
            "--chain",
            "solana",
            "--decision",
            "WAIT",
            "--token-id",
            "10",
            "--pair-id",
            "10",
            "--memory-window-id",
            "23",
            "--window-kind",
            "WINDOW_15M",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "PAPER_DECISIONS_LOCKED" in captured.out
    assert "PAPER_DECISION_PROPOSED" not in captured.out
    assert "paper_decision_created" not in captured.out
    assert captured.err == ""
    assert _decision_count(db_path) == 0
