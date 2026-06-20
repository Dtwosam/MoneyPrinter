"""Local evidence collection for simulated paper monitoring."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.paper_monitor.contracts import PaperMonitorQualityLabel


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


def latest_row(
    connection: sqlite3.Connection,
    table: str,
    token_id: int,
    pair_id: int | None,
    time_field: str,
    target_time: str | None = None,
) -> dict[str, Any]:
    time_filter = f"AND {time_field} <= ?" if target_time else ""
    params: list[Any] = [token_id, pair_id]
    if target_time:
        params.append(target_time)
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
    return dict(row) if row else {}


def collect_latest_token_snapshot_context(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    target_time: str | None = None,
) -> dict[str, Any]:
    with connect(db_path_or_conn) as connection:
        return latest_row(connection, "printer_token_snapshots", token_id, pair_id, "captured_at", target_time)


def collect_latest_liquidity_exit_context(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    target_time: str | None = None,
) -> dict[str, Any]:
    with connect(db_path_or_conn) as connection:
        return latest_row(connection, "printer_liquidity_exit_snapshots", token_id, pair_id, "captured_at", target_time)


def collect_latest_safety_context(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    target_time: str | None = None,
) -> dict[str, Any]:
    with connect(db_path_or_conn) as connection:
        return latest_row(connection, "printer_safety_rug_snapshots", token_id, pair_id, "captured_at", target_time)


def collect_paper_entry_evidence(
    db_path_or_conn: str | Path | sqlite3.Connection,
    paper_decision_id: int,
) -> dict[str, Any]:
    with connect(db_path_or_conn) as connection:
        decision = connection.execute(
            "SELECT * FROM printer_paper_decisions WHERE id = ?",
            (paper_decision_id,),
        ).fetchone()
        if decision is None:
            return normalize_paper_monitor_evidence({"paper_decision": None})
        decision_payload = dict(decision)
    token_id = int(decision_payload["token_id"])
    pair_id = decision_payload["pair_id"]
    evidence = {
        "paper_decision": decision_payload,
        "token_snapshot": collect_latest_token_snapshot_context(db_path_or_conn, token_id, pair_id),
        "liquidity_exit": collect_latest_liquidity_exit_context(db_path_or_conn, token_id, pair_id),
        "safety": collect_latest_safety_context(db_path_or_conn, token_id, pair_id),
    }
    return normalize_paper_monitor_evidence(evidence)


def collect_paper_monitor_evidence(
    db_path_or_conn: str | Path | sqlite3.Connection,
    paper_position_id: int,
    target_time: str | None = None,
) -> dict[str, Any]:
    with connect(db_path_or_conn) as connection:
        position = connection.execute(
            "SELECT * FROM printer_paper_positions WHERE id = ?",
            (paper_position_id,),
        ).fetchone()
        if position is None:
            return normalize_paper_monitor_evidence({"paper_position": None})
        position_payload = dict(position)
    token_id = int(position_payload["token_id"])
    pair_id = position_payload["pair_id"]
    evidence = {
        "paper_position": position_payload,
        "token_snapshot": collect_latest_token_snapshot_context(db_path_or_conn, token_id, pair_id, target_time),
        "liquidity_exit": collect_latest_liquidity_exit_context(db_path_or_conn, token_id, pair_id, target_time),
        "safety": collect_latest_safety_context(db_path_or_conn, token_id, pair_id, target_time),
    }
    return normalize_paper_monitor_evidence(evidence)


def classify_monitor_quality(evidence: Mapping[str, Any]) -> PaperMonitorQualityLabel:
    contexts = [evidence.get("token_snapshot") or {}, evidence.get("liquidity_exit") or {}, evidence.get("safety") or {}]
    values = [value for context in contexts for value in context.values()]
    if SourceStatus.CONFLICTING.value in values or DataQualityLabel.CONFLICTING_DATA.value in values:
        return PaperMonitorQualityLabel.PAPER_MONITOR_CONTEXT_CONFLICTING
    if SourceStatus.STALE.value in values or DataQualityLabel.STALE_DATA.value in values:
        return PaperMonitorQualityLabel.PAPER_MONITOR_CONTEXT_STALE
    if SourceStatus.FAILED.value in values or DataQualityLabel.DO_NOT_TRAIN.value in values or DataQualityLabel.DIRTY_DATA.value in values:
        return PaperMonitorQualityLabel.PAPER_MONITOR_CONTEXT_DO_NOT_USE
    if not any(contexts):
        return PaperMonitorQualityLabel.PAPER_MONITOR_CONTEXT_UNKNOWN
    if any(not context for context in contexts):
        return PaperMonitorQualityLabel.PAPER_MONITOR_CONTEXT_PARTIAL
    return PaperMonitorQualityLabel.PAPER_MONITOR_CONTEXT_CLEAN


def normalize_paper_monitor_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(evidence)
    normalized["paper_monitor_quality_label"] = classify_monitor_quality(normalized).value
    return normalized


def paper_monitor_evidence_is_clean(evidence: Mapping[str, Any]) -> bool:
    return evidence.get("paper_monitor_quality_label") in {
        PaperMonitorQualityLabel.PAPER_MONITOR_CONTEXT_CLEAN.value,
        PaperMonitorQualityLabel.PAPER_MONITOR_CONTEXT_PARTIAL.value,
    }
