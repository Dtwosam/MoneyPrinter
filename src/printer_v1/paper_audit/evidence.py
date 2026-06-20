"""Local-only paper audit evidence collection."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus


@contextmanager
def connect(db_or_connection: str | Path | sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    if isinstance(db_or_connection, sqlite3.Connection):
        db_or_connection.row_factory = sqlite3.Row
        yield db_or_connection
        return
    connection = sqlite3.connect(Path(db_or_connection))
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def collect_decision_audit_evidence(db_path_or_conn: str | Path | sqlite3.Connection, paper_decision_id: int) -> dict[str, Any]:
    with connect(db_path_or_conn) as connection:
        return row_to_dict(connection.execute("SELECT * FROM printer_paper_decisions WHERE id = ?", (paper_decision_id,)).fetchone())


def collect_position_audit_evidence(db_path_or_conn: str | Path | sqlite3.Connection, paper_position_id: int) -> dict[str, Any]:
    with connect(db_path_or_conn) as connection:
        return row_to_dict(connection.execute("SELECT * FROM printer_paper_positions WHERE id = ?", (paper_position_id,)).fetchone())


def collect_monitoring_events_for_position(db_path_or_conn: str | Path | sqlite3.Connection, paper_position_id: int) -> list[dict[str, Any]]:
    with connect(db_path_or_conn) as connection:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM printer_paper_trade_events
                WHERE paper_position_id = ?
                ORDER BY event_at ASC, id ASC
                """,
                (paper_position_id,),
            ).fetchall()
        ]


def latest_context(
    connection: sqlite3.Connection,
    table: str,
    token_id: int,
    pair_id: int | None,
    time_field: str,
    at_time: str | None,
) -> dict[str, Any]:
    time_filter = f"AND {time_field} <= ?" if at_time else ""
    params: list[Any] = [token_id, pair_id]
    if at_time:
        params.append(at_time)
    row = connection.execute(
        f"""
        SELECT *
        FROM {table}
        WHERE token_id = ?
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
          {time_filter}
        ORDER BY {time_field} DESC, id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    return row_to_dict(row)


def collect_local_context_around_entry(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    entry_time: str | None,
) -> dict[str, Any]:
    with connect(db_path_or_conn) as connection:
        return {
            "token_snapshot": latest_context(connection, "printer_token_snapshots", token_id, pair_id, "captured_at", entry_time),
            "liquidity_exit": latest_context(connection, "printer_liquidity_exit_snapshots", token_id, pair_id, "captured_at", entry_time),
            "safety": latest_context(connection, "printer_safety_rug_snapshots", token_id, pair_id, "captured_at", entry_time),
        }


def collect_local_context_around_exit(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    exit_time: str | None,
) -> dict[str, Any]:
    return collect_local_context_around_entry(db_path_or_conn, token_id, pair_id, exit_time)


def collect_paper_audit_evidence(
    db_path_or_conn: str | Path | sqlite3.Connection,
    paper_position_id: int | None = None,
    paper_decision_id: int | None = None,
    target_time: str | None = None,
) -> dict[str, Any]:
    position = collect_position_audit_evidence(db_path_or_conn, paper_position_id) if paper_position_id is not None else {}
    decision_id = paper_decision_id or position.get("paper_decision_id")
    decision = collect_decision_audit_evidence(db_path_or_conn, int(decision_id)) if decision_id else {}
    token_id = position.get("token_id") or decision.get("token_id")
    pair_id = position.get("pair_id") or decision.get("pair_id")
    entry_time = position.get("opened_at") or decision.get("decided_at") or target_time
    exit_time = position.get("closed_at") or target_time
    context_entry = collect_local_context_around_entry(db_path_or_conn, int(token_id), pair_id, entry_time) if token_id else {}
    context_exit = collect_local_context_around_exit(db_path_or_conn, int(token_id), pair_id, exit_time) if token_id else {}
    evidence = {
        "paper_position": position,
        "paper_decision": decision,
        "monitoring_events": collect_monitoring_events_for_position(db_path_or_conn, int(paper_position_id)) if paper_position_id is not None else [],
        "entry_context": context_entry,
        "exit_context": context_exit,
        "target_time": target_time,
    }
    return normalize_paper_audit_evidence(evidence)


def context_values(evidence: Mapping[str, Any]) -> list[Any]:
    values: list[Any] = []
    for key in ("entry_context", "exit_context"):
        for context in (evidence.get(key) or {}).values():
            values.extend((context or {}).values())
    return values


def normalize_paper_audit_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(evidence)
    values = context_values(normalized)
    if SourceStatus.CONFLICTING.value in values or DataQualityLabel.CONFLICTING_DATA.value in values:
        normalized["data_quality_audit_hint"] = "CONFLICTING"
    elif SourceStatus.STALE.value in values or DataQualityLabel.STALE_DATA.value in values:
        normalized["data_quality_audit_hint"] = "STALE"
    elif not normalized.get("paper_decision") and not normalized.get("paper_position"):
        normalized["data_quality_audit_hint"] = "MISSING"
    elif any(not (normalized.get(key) or {}) for key in ("entry_context", "exit_context")):
        normalized["data_quality_audit_hint"] = "PARTIAL"
    else:
        normalized["data_quality_audit_hint"] = "CLEAN"
    return normalized


def paper_audit_evidence_is_complete(evidence: Mapping[str, Any]) -> bool:
    return bool(evidence.get("paper_decision")) and bool(evidence.get("paper_position")) and bool(evidence.get("monitoring_events"))
