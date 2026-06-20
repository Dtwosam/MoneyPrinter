"""Local-only evidence collection for operator review reports."""

from pathlib import Path
import sqlite3
from typing import Any

from printer_v1.operator_db.paths import resolve_operator_db_path
from printer_v1.operator_db.status import (
    STATE_NO_DB,
    STATE_SCHEMA_ONLY,
    connect_read_only,
    get_core_table_counts,
    get_operator_db_status,
    table_exists,
)


def resolve_existing_db(db_path: str | Path | None = None, project_root: str | Path | None = None) -> Path:
    return resolve_operator_db_path(db_path, project_root)


def base_evidence(db_path: str | Path | None = None, project_root: str | Path | None = None) -> dict[str, Any]:
    resolved = resolve_existing_db(db_path, project_root)
    state = get_operator_db_status(resolved, project_root)
    return {
        "db_path": str(resolved),
        "db_exists": resolved.is_file(),
        "db_state": state,
        "state_classification": state["state_classification"],
    }


def empty_if_no_db(evidence: dict[str, Any], scope: str) -> dict[str, Any] | None:
    if evidence["state_classification"] in {STATE_NO_DB, STATE_SCHEMA_ONLY}:
        return {**evidence, "scope": scope, "rows": [], "counts": evidence["db_state"].get("table_counts", {})}
    return None


def fetch_rows(
    db_path: str | Path,
    table_name: str,
    *,
    where: str = "",
    params: tuple[Any, ...] = (),
    order_by: str = "id DESC",
    limit: int = 10,
) -> list[dict[str, Any]]:
    with connect_read_only(db_path) as connection:
        if not table_exists(connection, table_name):
            return []
        query = f"SELECT * FROM {table_name}"
        if where:
            query += f" WHERE {where}"
        query += f" ORDER BY {order_by} LIMIT ?"
        return [dict(row) for row in connection.execute(query, (*params, limit)).fetchall()]


def count_where(db_path: str | Path, table_name: str, where: str = "", params: tuple[Any, ...] = ()) -> int:
    with connect_read_only(db_path) as connection:
        if not table_exists(connection, table_name):
            return 0
        query = f"SELECT COUNT(*) FROM {table_name}"
        if where:
            query += f" WHERE {where}"
        return int(connection.execute(query, params).fetchone()[0])


def token_pair_filter(token_id: int | None = None, pair_id: int | None = None) -> tuple[str, tuple[Any, ...]]:
    clauses: list[str] = []
    params: list[Any] = []
    if token_id is not None:
        clauses.append("token_id = ?")
        params.append(token_id)
    if pair_id is not None:
        clauses.append("COALESCE(pair_id, -1) = COALESCE(?, -1)")
        params.append(pair_id)
    return " AND ".join(clauses), tuple(params)


def collect_db_state_evidence(db_path=None, project_root=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    evidence.update({"scope": "db_state", "now": now, "counts": evidence["db_state"].get("table_counts", {})})
    return evidence


def collect_system_health_evidence(db_path=None, project_root=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "system_health")
    if no_data:
        return no_data
    counts = get_core_table_counts(evidence["db_path"], project_root)
    evidence.update({"scope": "system_health", "now": now, "counts": counts})
    return evidence


def collect_source_health_evidence(db_path=None, project_root=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "source_health")
    if no_data:
        return no_data
    db_file = evidence["db_path"]
    evidence.update(
        {
            "scope": "source_health",
            "now": now,
            "latest_requests": fetch_rows(db_file, "printer_source_requests", order_by="requested_at DESC, id DESC"),
            "latest_responses": fetch_rows(db_file, "printer_source_responses", order_by="received_at DESC, id DESC"),
            "latest_failures": fetch_rows(db_file, "printer_source_failures", order_by="failed_at DESC, id DESC"),
            "failure_count": count_where(db_file, "printer_source_failures"),
        }
    )
    return evidence


def collect_scheduler_health_evidence(db_path=None, project_root=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "scheduler_health")
    if no_data:
        return no_data
    db_file = evidence["db_path"]
    evidence.update(
        {
            "scope": "scheduler_health",
            "now": now,
            "latest_jobs": fetch_rows(db_file, "printer_scheduler_jobs", order_by="scheduled_for DESC, id DESC"),
            "pending_jobs": count_where(db_file, "printer_scheduler_jobs", "status IN ('PENDING', 'COOLDOWN')"),
            "running_jobs": count_where(db_file, "printer_scheduler_jobs", "status = 'RUNNING'"),
            "failed_jobs": count_where(db_file, "printer_scheduler_jobs", "status = 'FAILED'"),
        }
    )
    return evidence


def collect_lifecycle_queue_evidence(db_path=None, project_root=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "lifecycle_queue")
    if no_data:
        return no_data
    db_file = evidence["db_path"]
    evidence.update(
        {
            "scope": "lifecycle_queue",
            "now": now,
            "queue_items": fetch_rows(db_file, "printer_tracking_queue", order_by="updated_at DESC, id DESC"),
            "lifecycle_events": fetch_rows(db_file, "printer_token_lifecycle_events", order_by="created_at DESC, id DESC"),
        }
    )
    return evidence


def collect_discovery_evidence(db_path=None, project_root=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "discovery")
    if no_data:
        return no_data
    evidence.update(
        {
            "scope": "discovery",
            "now": now,
            "discoveries": fetch_rows(evidence["db_path"], "printer_discovery_candidates", order_by="created_at DESC, id DESC"),
        }
    )
    return evidence


def collect_token_snapshot_evidence(db_path=None, project_root=None, token_id=None, pair_id=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "token_snapshots")
    if no_data:
        return no_data
    where, params = token_pair_filter(token_id, pair_id)
    evidence.update(
        {
            "scope": "token_snapshots",
            "now": now,
            "token_id": token_id,
            "pair_id": pair_id,
            "snapshots": fetch_rows(evidence["db_path"], "printer_token_snapshots", where=where, params=params, order_by="captured_at DESC, id DESC"),
            "stale_count": count_where(evidence["db_path"], "printer_token_snapshots", "data_quality_label = 'STALE_DATA'"),
        }
    )
    return evidence


def collect_context_engine_evidence(db_path=None, project_root=None, token_id=None, pair_id=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "context_engines")
    if no_data:
        return no_data
    where, params = token_pair_filter(token_id, pair_id)
    db_file = evidence["db_path"]
    evidence.update(
        {
            "scope": "context_engines",
            "now": now,
            "market": fetch_rows(db_file, "printer_market_regime_snapshots", order_by="captured_at DESC, id DESC"),
            "chain_heat": fetch_rows(db_file, "printer_solana_chain_heat_snapshots", order_by="captured_at DESC, id DESC"),
            "safety": fetch_rows(db_file, "printer_safety_rug_snapshots", where=where, params=params, order_by="captured_at DESC, id DESC"),
            "liquidity_exit": fetch_rows(db_file, "printer_liquidity_exit_snapshots", where=where, params=params, order_by="captured_at DESC, id DESC"),
            "trading_flow": fetch_rows(db_file, "printer_trading_flow_snapshots", where=where, params=params, order_by="captured_at DESC, id DESC"),
            "chart_volatility": fetch_rows(db_file, "printer_chart_volatility_snapshots", where=where, params=params, order_by="captured_at DESC, id DESC"),
            "micro_events": fetch_rows(db_file, "printer_micro_events", where=where, params=params, order_by="detected_at DESC, id DESC"),
        }
    )
    return evidence


def collect_memory_evidence(db_path=None, project_root=None, token_id=None, pair_id=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "memory")
    if no_data:
        return no_data
    where, params = token_pair_filter(token_id, pair_id)
    db_file = evidence["db_path"]
    evidence.update(
        {
            "scope": "memory",
            "now": now,
            "windows": fetch_rows(db_file, "printer_memory_windows", where=where, params=params, order_by="created_at DESC, id DESC"),
            "episodes": fetch_rows(db_file, "printer_episodes", where=where, params=params, order_by="created_at DESC, id DESC"),
            "dirty_memory_count": count_where(db_file, "printer_memory_windows", "memory_quality_label IN ('DIRTY_MEMORY', 'DO_NOT_TRAIN_MEMORY') OR memory_status IN ('DIRTY_MEMORY', 'DO_NOT_TRAIN')"),
            "clean_memory_count": count_where(db_file, "printer_memory_windows", "memory_quality_label = 'CLEAN_MEMORY' OR memory_status = 'CLEAN_MEMORY'"),
        }
    )
    return evidence


def collect_memory_retrieval_evidence(db_path=None, project_root=None, token_id=None, pair_id=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "memory_retrieval")
    if no_data:
        return no_data
    where, params = token_pair_filter(token_id, pair_id)
    db_file = evidence["db_path"]
    evidence.update(
        {
            "scope": "memory_retrieval",
            "now": now,
            "queries": fetch_rows(db_file, "printer_memory_retrieval_queries", where=where, params=params, order_by="query_at DESC, id DESC"),
            "matches": fetch_rows(db_file, "printer_memory_retrieval_matches", where=where, params=params, order_by="created_at DESC, id DESC"),
        }
    )
    return evidence


def collect_paper_decision_evidence(db_path=None, project_root=None, token_id=None, pair_id=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "paper_decisions")
    if no_data:
        return no_data
    where, params = token_pair_filter(token_id, pair_id)
    evidence.update(
        {
            "scope": "paper_decisions",
            "now": now,
            "decisions": fetch_rows(evidence["db_path"], "printer_paper_decisions", where=where, params=params, order_by="decided_at DESC, id DESC"),
            "blocked_count": count_where(evidence["db_path"], "printer_paper_decisions", "paper_decision_status_label = 'PAPER_DECISION_BLOCKED' OR decision_gate_label LIKE 'DECISION_BLOCKED%'"),
        }
    )
    return evidence


def collect_paper_position_evidence(db_path=None, project_root=None, token_id=None, pair_id=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "paper_positions")
    if no_data:
        return no_data
    where, params = token_pair_filter(token_id, pair_id)
    db_file = evidence["db_path"]
    evidence.update(
        {
            "scope": "paper_positions",
            "now": now,
            "positions": fetch_rows(db_file, "printer_paper_positions", where=where, params=params, order_by="opened_at DESC, id DESC"),
            "events": fetch_rows(db_file, "printer_paper_trade_events", where=where, params=params, order_by="event_at DESC, id DESC"),
            "open_count": count_where(db_file, "printer_paper_positions", "paper_position_status_label IN ('PAPER_POSITION_OPEN', 'PAPER_POSITION_MONITORING', 'PAPER_POSITION_EXIT_WATCH')"),
            "exit_risk_count": count_where(db_file, "printer_paper_positions", "paper_monitor_state_label IN ('MONITOR_EXIT_RISK', 'MONITOR_ROUTE_RISK', 'MONITOR_LIQUIDITY_RISK', 'MONITOR_SAFETY_RISK')"),
        }
    )
    return evidence


def collect_paper_audit_evidence(db_path=None, project_root=None, token_id=None, pair_id=None, now=None) -> dict[str, Any]:
    evidence = base_evidence(db_path, project_root)
    no_data = empty_if_no_db(evidence, "paper_audits")
    if no_data:
        return no_data
    where, params = token_pair_filter(token_id, pair_id)
    evidence.update(
        {
            "scope": "paper_audits",
            "now": now,
            "audits": fetch_rows(evidence["db_path"], "printer_paper_audit_reports", where=where, params=params, order_by="audit_at DESC, id DESC"),
            "failure_count": count_where(evidence["db_path"], "printer_paper_audit_reports", "paper_audit_result_label = 'PAPER_AUDIT_FAIL'"),
        }
    )
    return evidence


def collect_full_operator_review_evidence(db_path=None, project_root=None, token_id=None, pair_id=None, now=None) -> dict[str, Any]:
    return {
        "scope": "full_operator_review",
        "db_state": collect_db_state_evidence(db_path, project_root, now),
        "system_health": collect_system_health_evidence(db_path, project_root, now),
        "source_health": collect_source_health_evidence(db_path, project_root, now),
        "scheduler_health": collect_scheduler_health_evidence(db_path, project_root, now),
        "lifecycle_queue": collect_lifecycle_queue_evidence(db_path, project_root, now),
        "discovery": collect_discovery_evidence(db_path, project_root, now),
        "token_snapshots": collect_token_snapshot_evidence(db_path, project_root, token_id, pair_id, now),
        "context_engines": collect_context_engine_evidence(db_path, project_root, token_id, pair_id, now),
        "memory": collect_memory_evidence(db_path, project_root, token_id, pair_id, now),
        "memory_retrieval": collect_memory_retrieval_evidence(db_path, project_root, token_id, pair_id, now),
        "paper_decisions": collect_paper_decision_evidence(db_path, project_root, token_id, pair_id, now),
        "paper_positions": collect_paper_position_evidence(db_path, project_root, token_id, pair_id, now),
        "paper_audits": collect_paper_audit_evidence(db_path, project_root, token_id, pair_id, now),
    }
