"""SQLite-backed simulated paper trade monitor recorder."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.paper_monitor.contracts import (
    PaperEntryStatusLabel,
    PaperMonitorStateLabel,
    PaperPositionStatusLabel,
    PaperTradeEventLabel,
)
from printer_v1.paper_monitor.evidence import collect_paper_entry_evidence
from printer_v1.paper_monitor.events import build_paper_trade_event_payload
from printer_v1.paper_monitor.monitor import build_monitor_update, build_paper_exit_payload
from printer_v1.paper_monitor.positions import build_paper_position_payload
from printer_v1.scheduler.contracts import JobKind, LockResult
from printer_v1.scheduler.scheduler import enqueue_job


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def record_paper_position(db_path_or_conn: str | Path | sqlite3.Connection, position_payload: Mapping[str, Any]) -> int:
    with connect(db_path_or_conn) as connection:
        existing = connection.execute(
            """
            SELECT id
            FROM printer_paper_positions
            WHERE paper_decision_id = ?
              AND paper_position_status_label IN ('PAPER_POSITION_OPEN', 'PAPER_POSITION_MONITORING', 'PAPER_POSITION_EXIT_WATCH')
            LIMIT 1
            """,
            (position_payload.get("paper_decision_id"),),
        ).fetchone()
        if existing:
            return int(existing["id"])
        cursor = connection.execute(
            """
            INSERT INTO printer_paper_positions (
                paper_decision_id, retrieval_query_id, token_id, pair_id, token_mint,
                pair_address, position_status, opened_at, entry_price_usd,
                paper_entry_price, paper_size_usd, paper_token_amount,
                current_price_usd, unrealized_pnl_usd, unrealized_pnl_percent,
                max_runup_percent, max_drawdown_percent, entry_status_label,
                paper_position_status_label, paper_monitor_state_label,
                paper_exit_reason_label, paper_pnl_state_label, entry_context_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                position_payload.get("paper_decision_id"),
                position_payload.get("retrieval_query_id"),
                position_payload.get("token_id"),
                position_payload.get("pair_id"),
                position_payload.get("token_mint"),
                position_payload.get("pair_address"),
                position_payload.get("paper_position_status_label"),
                position_payload.get("opened_at"),
                position_payload.get("entry_price_usd"),
                position_payload.get("entry_price_usd"),
                position_payload.get("paper_size_usd"),
                position_payload.get("paper_token_amount"),
                position_payload.get("current_price_usd"),
                position_payload.get("unrealized_pnl_usd"),
                position_payload.get("unrealized_pnl_percent"),
                position_payload.get("max_runup_percent"),
                position_payload.get("max_drawdown_percent"),
                PaperEntryStatusLabel(position_payload["entry_status_label"]).value,
                PaperPositionStatusLabel(position_payload["paper_position_status_label"]).value,
                PaperMonitorStateLabel(position_payload["paper_monitor_state_label"]).value,
                position_payload.get("paper_exit_reason_label"),
                position_payload.get("paper_pnl_state_label"),
                json.dumps(position_payload.get("entry_context", {}), sort_keys=True),
            ),
        )
        return int(cursor.lastrowid)


def record_paper_trade_event(db_path_or_conn: str | Path | sqlite3.Connection, event_payload: Mapping[str, Any]) -> int:
    with connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_paper_trade_events (
                paper_position_id, paper_decision_id, token_id, pair_id, event_kind,
                event_at, paper_trade_event_label, paper_monitor_state_label,
                paper_exit_reason_label, paper_pnl_state_label, event_payload_json,
                source_status, data_quality_label
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_payload.get("paper_position_id"),
                event_payload.get("paper_decision_id"),
                event_payload.get("token_id"),
                event_payload.get("pair_id"),
                event_payload.get("paper_trade_event_label"),
                event_payload.get("event_at"),
                PaperTradeEventLabel(event_payload["paper_trade_event_label"]).value,
                event_payload.get("paper_monitor_state_label"),
                event_payload.get("paper_exit_reason_label"),
                event_payload.get("paper_pnl_state_label"),
                json.dumps(event_payload.get("event_payload", {}), sort_keys=True),
                SourceStatus.COMPLETE.value,
                DataQualityLabel.CLEAN_DATA.value,
            ),
        )
        return int(cursor.lastrowid)


def record_paper_trade_audit(db_path_or_conn: str | Path | sqlite3.Connection, audit_payload: Mapping[str, Any]) -> int:
    with connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_paper_trade_audits (
                paper_position_id, paper_decision_id, token_id, pair_id, audited_at,
                audit_status, audit_label, audit_payload_json, data_quality_label
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                audit_payload.get("paper_position_id"),
                audit_payload.get("paper_decision_id"),
                audit_payload.get("token_id"),
                audit_payload.get("pair_id"),
                audit_payload.get("audited_at") or utc_now().isoformat(),
                audit_payload.get("audit_label", "PAPER_MONITOR_AUDIT"),
                audit_payload.get("audit_label", "PAPER_MONITOR_AUDIT"),
                json.dumps(dict(audit_payload), sort_keys=True),
                DataQualityLabel.CLEAN_DATA.value,
            ),
        )
        return int(cursor.lastrowid)


def open_paper_position_from_decision(
    db_path_or_conn: str | Path | sqlite3.Connection,
    paper_decision_id: int,
    now: datetime | None = None,
) -> tuple[int | None, dict[str, Any]]:
    evidence = collect_paper_entry_evidence(db_path_or_conn, paper_decision_id)
    decision = evidence.get("paper_decision")
    if not decision:
        payload = {"paper_decision_id": paper_decision_id, "entry_status_label": PaperEntryStatusLabel.PAPER_ENTRY_BLOCKED_NO_DECISION.value}
        return None, payload
    payload = build_paper_position_payload(decision, evidence, now)
    if payload["paper_position_status_label"] != PaperPositionStatusLabel.PAPER_POSITION_OPEN.value:
        event = build_paper_trade_event_payload(
            0,
            paper_decision_id,
            decision.get("token_id"),
            decision.get("pair_id"),
            "entry_blocked",
            payload,
            now,
        )
        record_paper_trade_event(db_path_or_conn, event)
        return None, payload
    position_id = record_paper_position(db_path_or_conn, payload)
    event = build_paper_trade_event_payload(
        position_id,
        paper_decision_id,
        decision.get("token_id"),
        decision.get("pair_id"),
        "position_opened",
        {**payload, "paper_position_id": position_id},
        now,
    )
    record_paper_trade_event(db_path_or_conn, event)
    return position_id, payload


def monitor_paper_position(
    db_path_or_conn: str | Path | sqlite3.Connection,
    paper_position_id: int,
    target_time: str | None = None,
) -> dict[str, Any]:
    update = build_monitor_update(db_path_or_conn, paper_position_id, target_time)
    with connect(db_path_or_conn) as connection:
        row = connection.execute("SELECT * FROM printer_paper_positions WHERE id = ?", (paper_position_id,)).fetchone()
        if row is None:
            return update
        connection.execute(
            """
            UPDATE printer_paper_positions
            SET current_price_usd = ?,
                unrealized_pnl_usd = ?,
                unrealized_pnl_percent = ?,
                max_runup_percent = ?,
                max_drawdown_percent = ?,
                paper_monitor_state_label = ?,
                paper_exit_reason_label = ?,
                paper_pnl_state_label = ?,
                latest_monitor_context_json = ?,
                position_status = ?,
                paper_position_status_label = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                update.get("current_price_usd"),
                update.get("unrealized_pnl_usd"),
                update.get("unrealized_pnl_percent"),
                update.get("max_runup_percent"),
                update.get("max_drawdown_percent"),
                update.get("paper_monitor_state_label"),
                update.get("paper_exit_reason_label"),
                update.get("paper_pnl_state_label"),
                json.dumps(update.get("monitor_evidence", {}), sort_keys=True),
                PaperPositionStatusLabel.PAPER_POSITION_EXIT_WATCH.value if update.get("should_close") else PaperPositionStatusLabel.PAPER_POSITION_MONITORING.value,
                PaperPositionStatusLabel.PAPER_POSITION_EXIT_WATCH.value if update.get("should_close") else PaperPositionStatusLabel.PAPER_POSITION_MONITORING.value,
                paper_position_id,
            ),
        )
    event_kind = "exit_risk" if update.get("should_close") else "snapshot_monitored"
    event = build_paper_trade_event_payload(
        paper_position_id,
        (update.get("monitor_evidence", {}).get("paper_position") or {}).get("paper_decision_id"),
        (update.get("monitor_evidence", {}).get("paper_position") or {}).get("token_id"),
        (update.get("monitor_evidence", {}).get("paper_position") or {}).get("pair_id"),
        event_kind,
        update,
    )
    record_paper_trade_event(db_path_or_conn, event)
    return update


def close_paper_position(
    db_path_or_conn: str | Path | sqlite3.Connection,
    paper_position_id: int,
    exit_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or utc_now()
    with connect(db_path_or_conn) as connection:
        row = connection.execute("SELECT * FROM printer_paper_positions WHERE id = ?", (paper_position_id,)).fetchone()
        if row is None:
            return dict(exit_payload)
        position = dict(row)
        payload = dict(exit_payload)
        payload.setdefault("closed_at", current_time.isoformat())
        connection.execute(
            """
            UPDATE printer_paper_positions
            SET closed_at = ?,
                exit_price_usd = ?,
                paper_exit_price = ?,
                realized_pnl_usd = ?,
                realized_pnl_percent = ?,
                paper_pnl_usd = ?,
                paper_pnl_percent = ?,
                paper_pnl_state_label = ?,
                paper_exit_reason_label = ?,
                paper_monitor_state_label = ?,
                paper_position_status_label = ?,
                position_status = ?,
                exit_context_json = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                payload.get("closed_at"),
                payload.get("exit_price_usd"),
                payload.get("exit_price_usd"),
                payload.get("realized_pnl_usd"),
                payload.get("realized_pnl_percent"),
                payload.get("realized_pnl_usd"),
                payload.get("realized_pnl_percent"),
                payload.get("paper_pnl_state_label"),
                payload.get("paper_exit_reason_label"),
                PaperMonitorStateLabel.MONITOR_CLOSED.value,
                PaperPositionStatusLabel.PAPER_POSITION_CLOSED.value,
                PaperPositionStatusLabel.PAPER_POSITION_CLOSED.value,
                json.dumps(payload.get("exit_context", {}), sort_keys=True),
                paper_position_id,
            ),
        )
    event = build_paper_trade_event_payload(
        paper_position_id,
        position.get("paper_decision_id"),
        position.get("token_id"),
        position.get("pair_id"),
        "position_closed",
        {**dict(exit_payload), "paper_monitor_state_label": PaperMonitorStateLabel.MONITOR_CLOSED.value},
        current_time,
    )
    record_paper_trade_event(db_path_or_conn, event)
    return {**dict(exit_payload), "closed_at": current_time.isoformat()}


def close_from_monitor_update(db_path_or_conn: str | Path | sqlite3.Connection, paper_position_id: int, now: datetime | None = None) -> dict[str, Any]:
    with connect(db_path_or_conn) as connection:
        row = connection.execute("SELECT * FROM printer_paper_positions WHERE id = ?", (paper_position_id,)).fetchone()
        position = dict(row) if row else {}
    update = build_monitor_update(db_path_or_conn, paper_position_id)
    exit_payload = build_paper_exit_payload(position, update.get("monitor_evidence", {}), now)
    return close_paper_position(db_path_or_conn, paper_position_id, exit_payload, now)


def get_open_paper_positions(db_path_or_conn: str | Path | sqlite3.Connection) -> list[sqlite3.Row]:
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            """
            SELECT *
            FROM printer_paper_positions
            WHERE paper_position_status_label IN ('PAPER_POSITION_OPEN', 'PAPER_POSITION_MONITORING', 'PAPER_POSITION_EXIT_WATCH')
            ORDER BY opened_at ASC, id ASC
            """
        ).fetchall()


def get_latest_paper_position(db_path_or_conn: str | Path | sqlite3.Connection, token_id: int | None = None, pair_id: int | None = None) -> sqlite3.Row | None:
    clauses: list[str] = []
    params: list[Any] = []
    if token_id is not None:
        clauses.append("token_id = ?")
        params.append(token_id)
    if pair_id is not None:
        clauses.append("COALESCE(pair_id, -1) = COALESCE(?, -1)")
        params.append(pair_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path_or_conn) as connection:
        return connection.execute(
            f"SELECT * FROM printer_paper_positions {where} ORDER BY opened_at DESC, id DESC LIMIT 1",
            params,
        ).fetchone()


def enqueue_paper_monitor_job(
    db_path_or_conn: str | Path | sqlite3.Connection,
    paper_position_id: int,
    scheduled_for: datetime,
    reason: str | None = None,
) -> tuple[LockResult, int | None]:
    suffix = reason or "scheduled"
    return enqueue_job(
        db_path_or_conn,
        job_name=f"paper_monitor_{paper_position_id}_{suffix}",
        job_kind=JobKind.OPEN_PAPER_TRADE_MONITOR,
        target_table="printer_paper_positions",
        target_id=paper_position_id,
        scheduled_for=scheduled_for,
    )
