"""Deterministic zero-source readiness projection from durable SQLite facts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any


FORBIDDEN_CAPABILITY_TABLES = (
    "printer_memory_windows",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)


def _rows(connection: sqlite3.Connection, sql: str, values=()) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(sql, values).fetchall()]


def build_bounded_readiness_report(
    db_path: str | Path, *, run_id: str, cycle_id: str
) -> dict[str, Any]:
    """Open the DB read-only and return only canonical stored-fact evidence."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        external = _rows(
            connection,
            """SELECT operation_ordinal,source_name,request_purpose,endpoint_role,
                      redacted_host,rpc_method,commitment,started_at,finished_at,
                      operation_state,failure_subtype
               FROM printer_external_source_operations
               WHERE run_id=? AND cycle_id=? ORDER BY operation_ordinal""",
            (run_id, cycle_id),
        )
        holder = _rows(
            connection,
            """SELECT source_name,endpoint_role,redacted_host,source_status,
                      data_quality_label,exact_target,holder_concentration_label,
                      rpc_method,commitment,context_slot,underlying_operation_count,
                      failure_subtype,retry_after_at,captured_at,received_at
               FROM printer_holder_evidence_attempts
               WHERE run_id=? AND cycle_id=? ORDER BY evidence_id""",
            (run_id, cycle_id),
        )
        ledger_columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(printer_holder_campaign_operation_ledgers)"
            ).fetchall()
        }
        if "reserved_snapshot_completion_operations" in ledger_columns:
            ledgers = _rows(
                connection,
                """SELECT operation_ceiling,governed_requests,
                          underlying_transport_operations,zero_transport_operations,
                          reserved_snapshot_operations,
                          reserved_snapshot_completion_operations,
                          (reserved_snapshot_operations +
                           reserved_snapshot_completion_operations)
                              AS total_readiness_snapshot_reservation,
                          deadline_at
                   FROM printer_holder_campaign_operation_ledgers
                   WHERE run_id=? AND cycle_id=?""",
                (run_id, cycle_id),
            )
        else:
            ledgers = _rows(
                connection,
                """SELECT operation_ceiling,governed_requests,
                          underlying_transport_operations,zero_transport_operations,
                          reserved_snapshot_operations,deadline_at
                   FROM printer_holder_campaign_operation_ledgers
                   WHERE run_id=? AND cycle_id=?""",
                (run_id, cycle_id),
            )
        active_queue = int(connection.execute(
            """SELECT COUNT(*) FROM printer_tracking_queue
               WHERE queue_status IN ('PENDING','ACTIVE','TRACK_FAST','TRACK_NORMAL')"""
        ).fetchone()[0])
        active_scheduler = int(connection.execute(
            """SELECT COUNT(*) FROM printer_scheduler_jobs
               WHERE status IN ('PENDING','RUNNING','COOLDOWN')"""
        ).fetchone()[0])
        forbidden = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in FORBIDDEN_CAPABILITY_TABLES
        }
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        readiness_snapshots = []
        if "reserved_snapshot_completion_operations" in ledger_columns:
            readiness_snapshots = _rows(
                connection,
                """SELECT s.id,s.captured_at,s.price_usd,s.liquidity_usd,
                          s.price_change_5m,s.price_change_15m,
                          s.volume_5m,s.volume_15m,s.volume_1h,
                          s.txns_5m,s.txns_15m,s.txns_1h,
                          s.source_status,s.data_quality_label,
                          json_extract(s.normalized_snapshot_payload_json,
                            '$.snapshot_readiness_contract.label')
                              AS readiness_label
                   FROM printer_token_snapshots AS s
                   WHERE json_extract(s.normalized_snapshot_payload_json,
                            '$.snapshot_readiness_contract.label') =
                         'SNAPSHOT_READINESS_COMPLETE'
                   ORDER BY s.id""",
            )
    finally:
        connection.close()
    return {
        "schema": "printer-v1-e24-readiness-report-v1",
        "run_id": run_id,
        "cycle_id": cycle_id,
        "external_pump_operations": external,
        "holder_attempts": holder,
        "campaign_ledgers": ledgers,
        "cleanup": {
            "active_tracking_queue": active_queue,
            "active_scheduler_jobs": active_scheduler,
        },
        "integrity": integrity,
        "foreign_key_violations": foreign_keys,
        "forbidden_capability_counts": forbidden,
        "source_requests_made_by_replay": 0,
        **(
            {"readiness_snapshots": readiness_snapshots}
            if "reserved_snapshot_completion_operations" in ledger_columns
            else {}
        ),
    }


def canonical_report_bytes(report: dict[str, Any]) -> bytes:
    return json.dumps(
        report, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def canonical_report_sha256(report: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_report_bytes(report)).hexdigest()
