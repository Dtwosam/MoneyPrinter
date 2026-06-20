"""One-shot operator commands for safe local Printer V1 inspection."""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from printer_v1.db.migrate import MIGRATIONS_DIR
from printer_v1.hardening.flow_validation import (
    initialize_temp_validation_db,
    run_full_synthetic_validation_flow,
)
from printer_v1.hardening.schema_checks import (
    check_no_live_capability_terms_in_source,
    check_no_runtime_loop_terms_in_source,
)
from printer_v1.operator_cli.formatting import (
    format_counts_table,
    format_json_output,
    format_migration_summary,
    format_readiness_summary,
    format_status_summary,
    format_text_output,
)
from printer_v1.operator_db.bootstrap import initialize_operator_db
from printer_v1.operator_db.paths import resolve_operator_db_path
from printer_v1.operator_db.status import (
    STATE_CONTROLLED_INTAKE,
    STATE_CONTROLLED_CONTEXT,
    STATE_CONTROLLED_SNAPSHOTS,
    STATE_FIRST_MEMORY_WINDOW,
    STATE_MEMORY_QUALITY_AUDITED,
    STATE_MEMORY_ROWS,
    STATE_NO_DB,
    STATE_PAPER_ROWS,
    STATE_REAL_MEMORY_RETRIEVAL,
    STATE_REAL_DATA_PAPER_DECISION,
    STATE_SCHEMA_ONLY,
    STATE_SOURCE_ONLY_SMOKE_CHECK,
    STATE_TEST_ONLY,
    STATE_TOKEN_ROWS,
    get_core_table_counts,
    get_operator_db_status,
    get_schema_migration_status,
)
from printer_v1.operator_review.contracts import ReportFormatLabel, ReportScopeLabel
from printer_v1.operator_review.evidence import (
    collect_db_state_evidence,
    collect_full_operator_review_evidence,
    collect_memory_evidence,
    collect_paper_decision_evidence,
    collect_paper_position_evidence,
    collect_system_health_evidence,
    collect_token_snapshot_evidence,
)
from printer_v1.operator_review.exports import (
    export_report_as_json_payload,
    export_report_as_markdown_text,
    export_report_as_plain_text,
)
from printer_v1.operator_review.recorder import (
    build_and_record_operator_review_report,
)
from printer_v1.operator_review.reports import build_operator_report_payload
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.dexscreener import (
    build_dexscreener_adapter,
    build_dexscreener_pair_snapshot_transport,
    build_dexscreener_smoke_transport,
)
from printer_v1.sources.governed_execution import execute_source_request_with_governor
from printer_v1.snapshots.recorder import record_token_snapshot
from printer_v1.memory_retrieval.recorder import record_memory_retrieval_query, record_memory_retrieval_matches
from printer_v1.memory_retrieval.retriever import retrieve_memory_matches_for_current_setup


READINESS_NEEDS_DB_INIT = "NEEDS_DB_INIT"
READINESS_READY_SCHEMA_ONLY = "READY_SCHEMA_ONLY"
READINESS_READY_SOURCE_ONLY_SMOKE_CHECK = "READY_SOURCE_ONLY_SMOKE_CHECK"
READINESS_READY_CONTROLLED_INTAKE = "READY_CONTROLLED_INTAKE"
READINESS_READY_CONTROLLED_SNAPSHOTS = "READY_CONTROLLED_SNAPSHOTS"
READINESS_READY_CONTROLLED_CONTEXT = "READY_CONTROLLED_CONTEXT"
READINESS_READY_FIRST_MEMORY_WINDOW = "READY_FIRST_MEMORY_WINDOW"
READINESS_READY_MEMORY_QUALITY_AUDITED = "READY_MEMORY_QUALITY_AUDITED"
READINESS_READY_REAL_MEMORY_RETRIEVAL = "READY_REAL_MEMORY_RETRIEVAL"
READINESS_READY_REAL_DATA_PAPER_DECISION = "READY_REAL_DATA_PAPER_DECISION"
READINESS_READY_WITH_LOCAL_DATA = "READY_WITH_LOCAL_DATA"
READINESS_BLOCKED = "BLOCKED"
READINESS_STATE_UNKNOWN = "STATE_UNKNOWN"

SOURCE_ONLY_TABLES = {
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
}

DOWNSTREAM_GUARD_TABLES = [
    "printer_tokens",
    "printer_pairs",
    "printer_tracking_queue",
    "printer_scheduler_jobs",
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
    "printer_episode_snapshots",
    "printer_episode_outcomes",
    "printer_memory_fingerprints",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
]

MANUAL_INTAKE_GUARD_TABLES = [
    "printer_tracking_queue",
    "printer_scheduler_jobs",
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
    "printer_episode_snapshots",
    "printer_episode_outcomes",
    "printer_memory_fingerprints",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
]

CONTROLLED_SNAPSHOT_GUARD_TABLES = [
    "printer_tracking_queue",
    "printer_scheduler_jobs",
    "printer_market_regime_snapshots",
    "printer_solana_chain_heat_snapshots",
    "printer_safety_rug_snapshots",
    "printer_liquidity_exit_snapshots",
    "printer_trading_flow_snapshots",
    "printer_chart_volatility_snapshots",
    "printer_micro_events",
    "printer_memory_windows",
    "printer_episodes",
    "printer_episode_snapshots",
    "printer_episode_outcomes",
    "printer_memory_fingerprints",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
]

CONTEXT_TABLES = [
    "printer_market_regime_snapshots",
    "printer_solana_chain_heat_snapshots",
    "printer_safety_rug_snapshots",
    "printer_liquidity_exit_snapshots",
    "printer_trading_flow_snapshots",
    "printer_chart_volatility_snapshots",
    "printer_micro_events",
]

CONTROLLED_CONTEXT_GUARD_TABLES = [
    "printer_tracking_queue",
    "printer_scheduler_jobs",
    "printer_memory_windows",
    "printer_episodes",
    "printer_episode_snapshots",
    "printer_episode_outcomes",
    "printer_memory_fingerprints",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
]

FIRST_MEMORY_GUARD_TABLES = [
    "printer_tracking_queue",
    "printer_scheduler_jobs",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
]

MEMORY_OUTPUT_TABLES = [
    "printer_memory_windows",
    "printer_episodes",
    "printer_episode_snapshots",
    "printer_episode_outcomes",
    "printer_memory_fingerprints",
]

MEMORY_AUDIT_TABLES = [
    "printer_memory_audit_reports",
]


def _project_root(value: str | None) -> Path | None:
    return Path(value).resolve(strict=False) if value else None


def _base_parser(description: str, output_formats: tuple[str, ...] = ("json", "text")) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--db-path")
    parser.add_argument("--project-root")
    parser.add_argument("--format", choices=output_formats, default=output_formats[0])
    parser.add_argument("--no-color", action="store_true")
    return parser


def _print_payload(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(format_json_output(payload))
    elif output_format == "markdown":
        print(payload.get("report_text") or format_text_output(payload))
    else:
        print(format_text_output(payload))


def _print_error(exc: Exception) -> int:
    print(f"Error: {exc}")
    return 1


def _migration_files() -> list[str]:
    return [path.name for path in sorted(MIGRATIONS_DIR.glob("*.sql"))]


def build_migration_status(db_path: str | Path | None = None, project_root: str | Path | None = None) -> dict[str, Any]:
    resolved = resolve_operator_db_path(db_path, project_root)
    schema = get_schema_migration_status(resolved, project_root)
    expected = _migration_files()
    applied = schema.get("applied_migrations") or []
    missing = [version for version in expected if version not in applied]
    return {
        "db_path": str(resolved),
        "exists": bool(schema.get("exists")),
        "applied_migrations": applied,
        "applied_count": len(applied),
        "expected_count": len(expected),
        "latest_migration": schema.get("latest_migration"),
        "missing_migrations": missing,
    }


def _evidence_for_report(scope: ReportScopeLabel, db_path: str | Path, project_root: str | Path | None, token_id=None, pair_id=None) -> dict[str, Any]:
    if scope == ReportScopeLabel.REPORT_DB_STATE:
        return collect_db_state_evidence(db_path, project_root)
    if scope == ReportScopeLabel.REPORT_TOKEN_SNAPSHOTS:
        return collect_token_snapshot_evidence(db_path, project_root, token_id=token_id, pair_id=pair_id)
    if scope == ReportScopeLabel.REPORT_MEMORY:
        return collect_memory_evidence(db_path, project_root, token_id=token_id, pair_id=pair_id)
    if scope == ReportScopeLabel.REPORT_PAPER_DECISIONS:
        return collect_paper_decision_evidence(db_path, project_root, token_id=token_id, pair_id=pair_id)
    if scope == ReportScopeLabel.REPORT_PAPER_POSITIONS:
        return {
            "paper_decisions": collect_paper_decision_evidence(db_path, project_root, token_id=token_id, pair_id=pair_id),
            "paper_positions": collect_paper_position_evidence(db_path, project_root, token_id=token_id, pair_id=pair_id),
            "paper_audits": collect_db_state_evidence(db_path, project_root),
        }
    if scope == ReportScopeLabel.REPORT_FULL_OPERATOR_REVIEW:
        return collect_full_operator_review_evidence(db_path, project_root, token_id=token_id, pair_id=pair_id)
    return collect_system_health_evidence(db_path, project_root)


def _format_report_payload(report_payload: dict[str, Any], output_format: str) -> dict[str, Any]:
    if output_format == "markdown":
        report_payload["report_text"] = export_report_as_markdown_text(report_payload)
    elif output_format == "text":
        report_payload["report_text"] = export_report_as_plain_text(report_payload)
    else:
        report_payload = export_report_as_json_payload(report_payload)
    return report_payload


def build_init_db_payload(args: argparse.Namespace) -> dict[str, Any]:
    project_root = _project_root(args.project_root)
    report = initialize_operator_db(args.db_path, project_root)
    return {
        "command": "printer-init-db",
        "db_path": report["db_path"],
        "latest_migration": report["schema"]["latest_migration"],
        "state_classification": report["status"]["state_classification"],
        "table_counts": report["status"].get("table_counts", {}),
    }


def main_init_db(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Initialize the local operator DB schema.")
    args = parser.parse_args(argv)
    try:
        _print_payload(build_init_db_payload(args), args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def build_db_status_payload(args: argparse.Namespace) -> dict[str, Any]:
    project_root = _project_root(args.project_root)
    status = get_operator_db_status(args.db_path, project_root)
    return {"command": "printer-db-status", **status}


def main_db_status(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Show local operator DB status.")
    args = parser.parse_args(argv)
    try:
        payload = build_db_status_payload(args)
        if args.format == "json":
            print(format_json_output(payload))
        else:
            print(format_status_summary(payload))
        return 0
    except Exception as exc:
        return _print_error(exc)


def build_db_counts_payload(args: argparse.Namespace) -> dict[str, Any]:
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    status = get_operator_db_status(resolved, project_root)
    counts = get_core_table_counts(resolved, project_root)
    return {
        "command": "printer-db-counts",
        "db_path": str(resolved),
        "exists": resolved.is_file(),
        "state_classification": status["state_classification"],
        "counts": counts,
    }


def main_db_counts(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Show local operator DB core table counts.")
    args = parser.parse_args(argv)
    try:
        payload = build_db_counts_payload(args)
        if args.format == "json":
            print(format_json_output(payload))
        else:
            print(format_counts_table(payload["counts"]))
        return 0
    except Exception as exc:
        return _print_error(exc)


def build_migration_status_payload(args: argparse.Namespace) -> dict[str, Any]:
    project_root = _project_root(args.project_root)
    return {"command": "printer-migration-status", **build_migration_status(args.db_path, project_root)}


def main_migration_status(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Show local operator DB migration status.")
    args = parser.parse_args(argv)
    try:
        payload = build_migration_status_payload(args)
        if args.format == "json":
            print(format_json_output(payload))
        else:
            print(format_migration_summary(payload))
        return 0
    except Exception as exc:
        return _print_error(exc)


def build_operator_report_payload_from_args(args: argparse.Namespace) -> dict[str, Any]:
    project_root = _project_root(args.project_root)
    db_path = resolve_operator_db_path(args.db_path, project_root)
    scope = ReportScopeLabel(args.scope)
    report_format = {
        "json": ReportFormatLabel.REPORT_FORMAT_JSON,
        "markdown": ReportFormatLabel.REPORT_FORMAT_MARKDOWN,
        "text": ReportFormatLabel.REPORT_FORMAT_TEXT,
    }[args.format]
    if args.record:
        report_id, payload = build_and_record_operator_review_report(
            db_path,
            scope,
            token_id=args.token_id,
            pair_id=args.pair_id,
            report_format_label=report_format,
        )
        payload["operator_review_report_id"] = report_id
        payload["recorded"] = True
    else:
        evidence = _evidence_for_report(scope, db_path, project_root, args.token_id, args.pair_id)
        payload = build_operator_report_payload(scope, evidence)
        payload["token_id"] = args.token_id
        payload["pair_id"] = args.pair_id
        payload["report_format_label"] = report_format.value
        payload["recorded"] = False
    return _format_report_payload(payload, args.format)


def main_operator_report(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Build or record a local operator review report.", ("json", "markdown", "text"))
    parser.add_argument("--scope", default=ReportScopeLabel.REPORT_FULL_OPERATOR_REVIEW.value)
    parser.add_argument("--token-id", type=int)
    parser.add_argument("--pair-id", type=int)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = build_operator_report_payload_from_args(args)
        if args.format == "json":
            print(format_json_output(payload))
        else:
            print(payload.get("report_text") or format_text_output(payload))
        return 0
    except Exception as exc:
        return _print_error(exc)


def build_synthetic_validation_payload(args: argparse.Namespace) -> dict[str, Any]:
    project_root = _project_root(args.project_root)
    if args.db_path:
        db_path = resolve_operator_db_path(args.db_path, project_root)
        payload = run_full_synthetic_validation_flow(db_path, project_root=project_root)
        payload["used_explicit_db_path"] = True
    else:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = initialize_temp_validation_db(temp_dir)
            payload = run_full_synthetic_validation_flow(db_path, project_root=project_root)
            payload["used_explicit_db_path"] = False
            payload["temp_db_path"] = str(db_path)
    payload["command"] = "printer-synthetic-validation"
    payload["temp_only_requested"] = bool(args.temp_only)
    return payload


def main_synthetic_validation(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Run synthetic local validation.", ("json", "text"))
    parser.add_argument("--temp-only", action="store_true", default=True)
    args = parser.parse_args(argv)
    try:
        payload = build_synthetic_validation_payload(args)
        if args.format == "json":
            print(format_json_output(payload))
        else:
            print(
                "\n".join(
                    [
                        f"Validation: {payload.get('validation_result_label')}",
                        f"Completed stage: {payload.get('completed_stage')}",
                        f"Synthetic only: {payload.get('synthetic_only')}",
                        f"Temp DB only: {payload.get('temp_db_only')}",
                        f"Project DB created: {payload.get('project_db_created')}",
                    ]
                )
            )
        return 0
    except Exception as exc:
        return _print_error(exc)


def build_source_smoke_dexscreener_payload(
    args: argparse.Namespace,
    *,
    transport=None,
) -> dict[str, Any]:
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    source_request = build_governed_source_request(
        "dexscreener",
        "token_discovery",
        request_key=args.request_key,
        tracking_priority=0,
        payload={"smoke_check": True, "source": "dexscreener"},
    )
    adapter = build_dexscreener_adapter(
        enabled=True,
        smoke_transport=transport or build_dexscreener_smoke_transport(timeout_seconds=args.timeout_seconds),
    )
    result = execute_source_request_with_governor(
        resolved,
        source_request,
        adapter,
        recent_request_count=0,
    )
    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    downstream_changed = {
        table: deltas[table]
        for table in DOWNSTREAM_GUARD_TABLES
        if deltas.get(table)
    }
    status = get_operator_db_status(resolved, project_root)
    return {
        "command": "printer-source-smoke-dexscreener",
        "db_path": str(resolved),
        "source_name": "dexscreener",
        "request_kind": "token_discovery",
        "one_shot": True,
        "bounded_request_count": 1,
        "source_status": result.normalized_result.source_status.value,
        "data_quality_label": result.normalized_result.data_quality_label.value,
        "source_request_id": result.request_record.id,
        "source_response_id": result.response_record.id if result.response_record else None,
        "source_failure_id": result.failure_record.id if result.failure_record else None,
        "failure_type": result.normalized_result.failure_type,
        "failure_message": result.normalized_result.failure_message,
        "source_table_deltas": {table: deltas[table] for table in sorted(SOURCE_ONLY_TABLES)},
        "downstream_table_deltas": downstream_changed,
        "downstream_unchanged": not downstream_changed,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_source_smoke_dexscreener(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Run one bounded DexScreener source smoke check.", ("json", "text"))
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--request-key", default="dexscreener-source-smoke")
    args = parser.parse_args(argv)
    try:
        payload = build_source_smoke_dexscreener_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_intake_items(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.intake_json:
        parsed = json.loads(args.intake_json)
        if isinstance(parsed, dict):
            items = [parsed]
        elif isinstance(parsed, list):
            items = parsed
        else:
            raise ValueError("manual intake JSON must be an object or list")
    else:
        items = [
            {
                "token_mint": args.token_mint,
                "pair_address": args.pair_address or args.pool_address,
                "chain": args.chain,
                "intake_reason": args.intake_reason,
                "source_reference": args.source_reference,
                "source_request_id": args.source_request_id,
                "token_symbol": args.token_symbol,
                "token_name": args.token_name,
                "dex_id": args.dex_id,
            }
        ]
    if not 1 <= len(items) <= 3:
        raise ValueError("manual intake accepts 1 to 3 token/pair items")
    return [dict(item) for item in items]


def _validate_manual_intake_item(item: dict[str, Any], operator_approved: bool) -> dict[str, Any]:
    if not operator_approved:
        raise ValueError("manual intake requires explicit operator approval")
    token_mint = str(item.get("token_mint") or "").strip()
    pair_address = str(item.get("pair_address") or item.get("pool_address") or "").strip()
    chain = str(item.get("chain") or "solana").strip().lower()
    intake_reason = str(item.get("intake_reason") or "").strip()
    source_reference = item.get("source_reference")
    source_request_id = item.get("source_request_id")
    if chain != "solana":
        raise ValueError("manual intake is Solana-only")
    if not token_mint:
        raise ValueError("manual intake requires token_mint")
    if not pair_address:
        raise ValueError("manual intake requires pair_address or pool_address")
    if not intake_reason:
        raise ValueError("manual intake requires intake_reason")
    if not source_reference and source_request_id is None:
        raise ValueError("manual intake requires source_reference or source_request_id")
    return {
        "token_mint": token_mint,
        "pair_address": pair_address,
        "chain": chain,
        "intake_reason": intake_reason,
        "source_reference": source_reference,
        "source_request_id": source_request_id,
        "token_symbol": item.get("token_symbol") or item.get("symbol"),
        "token_name": item.get("token_name") or item.get("name"),
        "dex_id": item.get("dex_id") or item.get("dex"),
    }


def _connect_manual_intake(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _upsert_manual_token_pair(connection: sqlite3.Connection, item: dict[str, Any]) -> dict[str, Any]:
    now_text = _utc_now_text()
    token_row = connection.execute(
        "SELECT id FROM printer_tokens WHERE token_mint = ?",
        (item["token_mint"],),
    ).fetchone()
    token_created = token_row is None
    if token_created:
        cursor = connection.execute(
            """
            INSERT INTO printer_tokens (
                token_mint,
                chain,
                symbol,
                name,
                first_seen_at,
                last_seen_at,
                token_status
            ) VALUES (?, 'solana', ?, ?, ?, ?, ?)
            """,
            (
                item["token_mint"],
                item.get("token_symbol"),
                item.get("token_name"),
                now_text,
                now_text,
                "MANUAL_INTAKE_PENDING_SNAPSHOT",
            ),
        )
        token_id = int(cursor.lastrowid)
    else:
        token_id = int(token_row["id"])

    pair_row = connection.execute(
        "SELECT id FROM printer_pairs WHERE pair_address = ?",
        (item["pair_address"],),
    ).fetchone()
    pair_created = pair_row is None
    if pair_created:
        cursor = connection.execute(
            """
            INSERT INTO printer_pairs (
                token_id,
                pair_address,
                dex,
                pool_source,
                base_token_mint,
                first_seen_at,
                last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id,
                item["pair_address"],
                item.get("dex_id"),
                "manual_operator_intake",
                item["token_mint"],
                now_text,
                now_text,
            ),
        )
        pair_id = int(cursor.lastrowid)
    else:
        pair_id = int(pair_row["id"])

    return {
        "token_id": token_id,
        "pair_id": pair_id,
        "token_mint": item["token_mint"],
        "pair_address": item["pair_address"],
        "token_created": token_created,
        "pair_created": pair_created,
        "intake_reason": item["intake_reason"],
        "source_reference": item.get("source_reference"),
        "source_request_id": item.get("source_request_id"),
    }


def build_manual_intake_token_pair_payload(args: argparse.Namespace) -> dict[str, Any]:
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    items = [
        _validate_manual_intake_item(item, args.operator_approved)
        for item in _parse_intake_items(args)
    ]

    connection = _connect_manual_intake(resolved)
    try:
        results = [_upsert_manual_token_pair(connection, item) for item in items]
        connection.commit()
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guard_deltas = {table: deltas[table] for table in MANUAL_INTAKE_GUARD_TABLES if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    return {
        "command": "printer-manual-intake-token-pair",
        "db_path": str(resolved),
        "operator_approved": True,
        "intake_count": len(items),
        "results": results,
        "token_delta": deltas.get("printer_tokens", 0),
        "pair_delta": deltas.get("printer_pairs", 0),
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_manual_intake_token_pair(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Manually intake 1 to 3 operator-approved Solana token/pair rows.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--token-mint")
    parser.add_argument("--pair-address")
    parser.add_argument("--pool-address")
    parser.add_argument("--chain", default="solana")
    parser.add_argument("--intake-reason")
    parser.add_argument("--source-reference")
    parser.add_argument("--source-request-id", type=int)
    parser.add_argument("--token-symbol")
    parser.add_argument("--token-name")
    parser.add_argument("--dex-id")
    parser.add_argument("--intake-json")
    args = parser.parse_args(argv)
    try:
        payload = build_manual_intake_token_pair_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _validate_snapshot_command_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("snapshot collection requires explicit operator approval")
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("snapshot collection is Solana-only")
    if args.snapshot_count < 1 or args.snapshot_count > 3:
        raise ValueError("snapshot_count must be between 1 and 3")
    if args.max_seconds <= 0 or args.max_seconds > 30:
        raise ValueError("max_seconds must be greater than 0 and no more than 30")
    if args.source_name != "dexscreener":
        raise ValueError("Phase 27 snapshot collection supports DexScreener only")
    if not (args.token_mint or args.token_id):
        raise ValueError("snapshot collection requires token_mint or token_id")
    if not (args.pair_address or args.pair_id):
        raise ValueError("snapshot collection requires pair_address or pair_id")


def _resolve_approved_snapshot_target(connection: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    token_clause = "id = ?" if args.token_id is not None else "token_mint = ?"
    token_value = args.token_id if args.token_id is not None else args.token_mint
    token_row = connection.execute(
        f"SELECT * FROM printer_tokens WHERE {token_clause}",
        (token_value,),
    ).fetchone()
    if token_row is None:
        raise ValueError("snapshot target token is not already approved in DB")

    pair_clause = "id = ?" if args.pair_id is not None else "pair_address = ?"
    pair_value = args.pair_id if args.pair_id is not None else args.pair_address
    pair_row = connection.execute(
        f"SELECT * FROM printer_pairs WHERE {pair_clause}",
        (pair_value,),
    ).fetchone()
    if pair_row is None:
        raise ValueError("snapshot target pair is not already approved in DB")
    if int(pair_row["token_id"]) != int(token_row["id"]):
        raise ValueError("snapshot target pair does not belong to the approved token")
    if token_row["chain"] != "solana":
        raise ValueError("approved snapshot target must be Solana")

    return {
        "token_id": int(token_row["id"]),
        "pair_id": int(pair_row["id"]),
        "token_mint": token_row["token_mint"],
        "pair_address": pair_row["pair_address"],
    }


def _pick_snapshot_pair(normalized_payload: dict[str, Any], token_mint: str, pair_address: str) -> dict[str, Any] | None:
    for item in normalized_payload.get("pairs") or []:
        if (
            item.get("chain") == "solana"
            and item.get("token_mint") == token_mint
            and item.get("pair_address") == pair_address
        ):
            return dict(item)
    return None


def _build_snapshot_payload_from_pair(
    *,
    target: dict[str, Any],
    pair_payload: dict[str, Any],
    source_status: str,
    data_quality_label: str,
    captured_at: datetime,
) -> dict[str, Any]:
    return {
        "token_id": target["token_id"],
        "pair_id": target["pair_id"],
        "token_mint": target["token_mint"],
        "pair_address": target["pair_address"],
        "captured_at": captured_at.isoformat(),
        "tracking_lane": "TRACK_NORMAL",
        "snapshot_mode": "NORMAL_MODE",
        "price_usd": pair_payload.get("price_usd"),
        "liquidity_usd": pair_payload.get("liquidity_usd"),
        "volume_5m": pair_payload.get("volume_5m"),
        "volume_1h": pair_payload.get("volume_1h"),
        "volume_24h": pair_payload.get("volume_24h"),
        "txns_5m": pair_payload.get("txns_5m"),
        "txns_1h": pair_payload.get("txns_1h"),
        "txns_24h": pair_payload.get("txns_24h"),
        "fdv": pair_payload.get("fdv"),
        "market_cap": pair_payload.get("market_cap"),
        "price_change_5m": pair_payload.get("price_change_5m"),
        "price_change_1h": pair_payload.get("price_change_1h"),
        "price_change_24h": pair_payload.get("price_change_24h"),
        "source_status": source_status,
        "data_quality_label": data_quality_label,
    }


def build_collect_token_snapshots_once_payload(
    args: argparse.Namespace,
    *,
    transport=None,
) -> dict[str, Any]:
    _validate_snapshot_command_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    try:
        target = _resolve_approved_snapshot_target(connection, args)
    finally:
        connection.close()

    adapter_transport = transport or build_dexscreener_pair_snapshot_transport(
        target["pair_address"],
        timeout_seconds=args.max_seconds,
    )
    adapter = build_dexscreener_adapter(enabled=True, smoke_transport=adapter_transport)
    snapshot_results: list[dict[str, Any]] = []

    for index in range(args.snapshot_count):
        captured_at = datetime.now(timezone.utc) + timedelta(microseconds=index)
        source_request = build_governed_source_request(
            "dexscreener",
            "pair_market_snapshot",
            request_key=f"dexscreener-pair-snapshot-{target['pair_address']}-{index + 1}",
            tracking_priority=0,
            payload={
                "phase": "27",
                "token_mint": target["token_mint"],
                "pair_address": target["pair_address"],
                "snapshot_count": args.snapshot_count,
            },
        )
        result = execute_source_request_with_governor(
            resolved,
            source_request,
            adapter,
            recent_request_count=0,
        )
        normalized = dict(result.normalized_result.normalized_payload or {})
        pair_payload = _pick_snapshot_pair(normalized, target["token_mint"], target["pair_address"])
        snapshot_created = False
        snapshot_id = None
        skip_reason = None
        if (
            result.response_record
            and result.normalized_result.source_status.value == "COMPLETE"
            and result.normalized_result.data_quality_label.value in {"CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"}
            and pair_payload
            and pair_payload.get("price_usd") is not None
            and pair_payload.get("liquidity_usd") is not None
        ):
            snapshot_payload = _build_snapshot_payload_from_pair(
                target=target,
                pair_payload=pair_payload,
                source_status=result.normalized_result.source_status.value,
                data_quality_label=result.normalized_result.data_quality_label.value,
                captured_at=captured_at,
            )
            snapshot_created, snapshot_id = record_token_snapshot(resolved, snapshot_payload, captured_at)
        else:
            skip_reason = result.normalized_result.failure_type or "missing_snapshot_required_fields"

        snapshot_results.append(
            {
                "source_request_id": result.request_record.id,
                "source_response_id": result.response_record.id if result.response_record else None,
                "source_failure_id": result.failure_record.id if result.failure_record else None,
                "source_status": result.normalized_result.source_status.value,
                "data_quality_label": result.normalized_result.data_quality_label.value,
                "snapshot_created": snapshot_created,
                "snapshot_id": snapshot_id,
                "skip_reason": skip_reason,
            }
        )

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guard_deltas = {table: deltas[table] for table in CONTROLLED_SNAPSHOT_GUARD_TABLES if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    return {
        "command": "printer-collect-token-snapshots-once",
        "db_path": str(resolved),
        "source_name": "dexscreener",
        "operator_approved": True,
        "token_id": target["token_id"],
        "pair_id": target["pair_id"],
        "token_mint": target["token_mint"],
        "pair_address": target["pair_address"],
        "snapshot_count_requested": args.snapshot_count,
        "snapshot_rows_created": sum(1 for item in snapshot_results if item["snapshot_created"]),
        "results": snapshot_results,
        "source_request_delta": deltas.get("printer_source_requests", 0),
        "source_response_delta": deltas.get("printer_source_responses", 0),
        "source_failure_delta": deltas.get("printer_source_failures", 0),
        "token_delta": deltas.get("printer_tokens", 0),
        "pair_delta": deltas.get("printer_pairs", 0),
        "snapshot_delta": deltas.get("printer_token_snapshots", 0),
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_collect_token_snapshots_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Collect controlled one-shot DexScreener token snapshots.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--token-mint")
    parser.add_argument("--token-id", type=int)
    parser.add_argument("--pair-address")
    parser.add_argument("--pair-id", type=int)
    parser.add_argument("--chain", default="solana")
    parser.add_argument("--snapshot-count", type=int, default=1)
    parser.add_argument("--max-seconds", type=float, default=5.0)
    parser.add_argument("--source-name", default="dexscreener")
    parser.add_argument("--source-reference")
    args = parser.parse_args(argv)
    try:
        payload = build_collect_token_snapshots_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _validate_context_command_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("context collection requires explicit operator approval")
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("context collection is Solana-only")
    if args.source_name != "dexscreener":
        raise ValueError("Phase 28 context collection supports DexScreener evidence only")
    if not (args.token_mint or args.token_id):
        raise ValueError("context collection requires token_mint or token_id")
    if not (args.pair_address or args.pair_id):
        raise ValueError("context collection requires pair_address or pair_id")


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _resolve_approved_context_target(connection: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    return _resolve_approved_snapshot_target(connection, args)


def _resolve_context_snapshot(connection: sqlite3.Connection, args: argparse.Namespace, target: dict[str, Any]) -> dict[str, Any]:
    if args.snapshot_id is not None:
        row = connection.execute(
            """
            SELECT *
            FROM printer_token_snapshots
            WHERE id = ? AND token_id = ? AND pair_id = ?
            """,
            (args.snapshot_id, target["token_id"], target["pair_id"]),
        ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT *
            FROM printer_token_snapshots
            WHERE token_id = ? AND pair_id = ?
            ORDER BY captured_at DESC, id DESC
            LIMIT 1
            """,
            (target["token_id"], target["pair_id"]),
        ).fetchone()
    if row is None:
        raise ValueError("context collection requires an existing approved token snapshot")
    return _row_to_dict(row)


def _json_or_empty(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _base_context_payload(target: dict[str, Any], snapshot: dict[str, Any], category: str) -> dict[str, Any]:
    return {
        "phase": "28",
        "category": category,
        "token_id": target["token_id"],
        "pair_id": target["pair_id"],
        "token_mint": target["token_mint"],
        "pair_address": target["pair_address"],
        "snapshot_id": snapshot["id"],
        "snapshot_captured_at": snapshot.get("captured_at"),
        "source_name": "dexscreener",
        "source_status": snapshot.get("source_status"),
        "snapshot_data_quality_label": snapshot.get("data_quality_label"),
        "evidence_boundary": "existing_snapshot_and_recorded_source_evidence_only",
    }


def _context_rows_for_target(connection: sqlite3.Connection, target: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in CONTEXT_TABLES:
        if table in {"printer_market_regime_snapshots", "printer_solana_chain_heat_snapshots"}:
            counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        else:
            counts[table] = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE token_id = ? AND pair_id = ?",
                    (target["token_id"], target["pair_id"]),
                ).fetchone()[0]
            )
    return counts


def _liquidity_state_label(liquidity_usd: Any) -> str:
    if liquidity_usd is None:
        return "LIQUIDITY_UNKNOWN"
    try:
        value = float(liquidity_usd)
    except (TypeError, ValueError):
        return "LIQUIDITY_UNKNOWN"
    if value <= 0:
        return "LIQUIDITY_DANGEROUS"
    if value < 5_000:
        return "LIQUIDITY_THIN"
    if value < 25_000:
        return "LIQUIDITY_USABLE"
    return "LIQUIDITY_DEEP"


def _insert_controlled_context_rows(connection: sqlite3.Connection, target: dict[str, Any], snapshot: dict[str, Any], captured_at: str) -> dict[str, int]:
    raw_snapshot = _json_or_empty(snapshot.get("raw_snapshot_payload_json"))
    normalized_snapshot = _json_or_empty(snapshot.get("normalized_snapshot_payload_json"))
    price_usd = snapshot.get("price_usd")
    liquidity_usd = snapshot.get("liquidity_usd")
    source_status = snapshot.get("source_status") or "PARTIAL"
    snapshot_quality = snapshot.get("data_quality_label") or "ACCEPTABLE_PARTIAL_DATA"
    snapshot_payload = {
        "raw_snapshot": raw_snapshot,
        "normalized_snapshot": normalized_snapshot,
        "limitations": [
            "one real token snapshot is not enough for trend, micro-event, holder, authority, or broad-market claims",
            "no quote source is available in Phase 28, so route, slippage, and price impact remain unknown",
        ],
    }

    inserts: dict[str, int] = {}

    safety_payload = _base_context_payload(target, snapshot, "safety_rug")
    safety_payload["known_fields"] = {"liquidity_usd": liquidity_usd}
    safety_payload["missing_fields"] = ["holder_distribution", "mint_authority", "freeze_authority", "liquidity_lock"]
    connection.execute(
        """
        INSERT INTO printer_safety_rug_snapshots (
            token_id, pair_id, token_mint, pair_address, captured_at, liquidity_usd, source_name,
            safety_status_label, rug_risk_label, liquidity_safety_label, authority_label,
            distribution_label, safety_payload_quality_label, safety_gate_label, data_quality_label,
            source_status, raw_safety_payload_json, normalized_safety_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target["token_id"], target["pair_id"], target["token_mint"], target["pair_address"], captured_at,
            liquidity_usd, "dexscreener", "SAFETY_UNKNOWN", "RUG_RISK_UNKNOWN",
            "LIQUIDITY_SAFETY_UNKNOWN", "AUTHORITY_UNKNOWN", "DISTRIBUTION_UNKNOWN",
            "SAFETY_CONTEXT_UNKNOWN", "MANUAL_REVIEW_REQUIRED", "MISSING_CRITICAL_DATA",
            "PARTIAL", json.dumps(snapshot_payload, sort_keys=True), json.dumps(safety_payload, sort_keys=True),
        ),
    )
    inserts["printer_safety_rug_snapshots"] = 1

    liquidity_payload = _base_context_payload(target, snapshot, "liquidity_exit")
    liquidity_payload["known_fields"] = {
        "price_usd": price_usd,
        "liquidity_usd": liquidity_usd,
        "volume_5m": snapshot.get("volume_5m"),
        "volume_1h": snapshot.get("volume_1h"),
        "volume_24h": snapshot.get("volume_24h"),
        "txns_5m": snapshot.get("txns_5m"),
        "txns_1h": snapshot.get("txns_1h"),
        "txns_24h": snapshot.get("txns_24h"),
    }
    liquidity_payload["unknown_fields"] = ["route", "quote", "slippage", "price_impact"]
    connection.execute(
        """
        INSERT INTO printer_liquidity_exit_snapshots (
            token_id, pair_id, token_mint, pair_address, captured_at, price_usd, liquidity_usd,
            volume_5m, volume_1h, volume_24h, txns_5m, txns_1h, txns_24h,
            liquidity_state_label, entry_realism_label, exit_realism_label, slippage_label,
            price_impact_label, route_label, quote_age_label, liquidity_drain_label,
            liquidity_exit_payload_quality_label, realism_gate_label, data_quality_label, source_status,
            raw_liquidity_exit_payload_json, normalized_liquidity_exit_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target["token_id"], target["pair_id"], target["token_mint"], target["pair_address"], captured_at,
            price_usd, liquidity_usd, snapshot.get("volume_5m"), snapshot.get("volume_1h"),
            snapshot.get("volume_24h"), snapshot.get("txns_5m"), snapshot.get("txns_1h"),
            snapshot.get("txns_24h"), _liquidity_state_label(liquidity_usd), "ENTRY_UNKNOWN",
            "EXIT_UNKNOWN", "SLIPPAGE_UNKNOWN", "PRICE_IMPACT_UNKNOWN", "ROUTE_UNKNOWN",
            "QUOTE_MISSING", "LIQUIDITY_DRAIN_UNKNOWN", "LIQUIDITY_EXIT_CONTEXT_PARTIAL",
            "REALISM_CONTEXT_AUDIT_ONLY", snapshot_quality, source_status,
            json.dumps(snapshot_payload, sort_keys=True), json.dumps(liquidity_payload, sort_keys=True),
        ),
    )
    inserts["printer_liquidity_exit_snapshots"] = 1

    flow_payload = _base_context_payload(target, snapshot, "trading_flow")
    flow_payload["known_fields"] = {
        "volume_5m": snapshot.get("volume_5m"),
        "volume_1h": snapshot.get("volume_1h"),
        "volume_24h": snapshot.get("volume_24h"),
        "txns_5m": snapshot.get("txns_5m"),
        "txns_1h": snapshot.get("txns_1h"),
        "txns_24h": snapshot.get("txns_24h"),
    }
    flow_payload["unknown_fields"] = ["buy_sell_split", "wallet_participation"]
    connection.execute(
        """
        INSERT INTO printer_trading_flow_snapshots (
            token_id, pair_id, token_mint, pair_address, captured_at, price_usd, liquidity_usd,
            volume_5m, volume_1h, volume_24h, txns_5m, txns_1h, txns_24h,
            flow_direction_label, flow_pressure_label, imbalance_label, volume_activity_label,
            tx_activity_label, wallet_participation_label, trading_flow_payload_quality_label,
            flow_memory_gate_label, data_quality_label, source_status,
            raw_trading_flow_payload_json, normalized_trading_flow_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target["token_id"], target["pair_id"], target["token_mint"], target["pair_address"], captured_at,
            price_usd, liquidity_usd, snapshot.get("volume_5m"), snapshot.get("volume_1h"),
            snapshot.get("volume_24h"), snapshot.get("txns_5m"), snapshot.get("txns_1h"),
            snapshot.get("txns_24h"), "FLOW_UNKNOWN", "PRESSURE_UNKNOWN", "IMBALANCE_UNKNOWN",
            "VOLUME_UNKNOWN", "TX_ACTIVITY_UNKNOWN", "WALLETS_UNKNOWN",
            "TRADING_FLOW_CONTEXT_PARTIAL", "FLOW_CONTEXT_AUDIT_ONLY", snapshot_quality, source_status,
            json.dumps(snapshot_payload, sort_keys=True), json.dumps(flow_payload, sort_keys=True),
        ),
    )
    inserts["printer_trading_flow_snapshots"] = 1

    chart_payload = _base_context_payload(target, snapshot, "chart_volatility")
    chart_payload["known_fields"] = {
        "price_usd": price_usd,
        "price_change_5m": snapshot.get("price_change_5m"),
        "price_change_1h": snapshot.get("price_change_1h"),
        "price_change_24h": snapshot.get("price_change_24h"),
    }
    chart_payload["unknown_fields"] = ["multi_candle_path", "trend", "volatility_window"]
    connection.execute(
        """
        INSERT INTO printer_chart_volatility_snapshots (
            token_id, pair_id, token_mint, pair_address, captured_at, window_start_at, window_end_at,
            price_open, price_high, price_low, price_close, price_change_percent, candle_count,
            trend_structure_label, volatility_label, range_behavior_label, momentum_label,
            drawdown_recovery_label, candle_path_label, chart_payload_quality_label, chart_memory_gate_label,
            data_quality_label, source_status, raw_chart_payload_json, normalized_chart_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target["token_id"], target["pair_id"], target["token_mint"], target["pair_address"], captured_at,
            snapshot.get("captured_at"), captured_at, price_usd, price_usd, price_usd, price_usd,
            snapshot.get("price_change_5m"), 1, "TREND_UNKNOWN", "VOLATILITY_UNKNOWN",
            "RANGE_UNKNOWN", "MOMENTUM_UNKNOWN", "DRAWDOWN_RECOVERY_UNKNOWN", "PATH_UNKNOWN",
            "CHART_CONTEXT_PARTIAL", "CHART_CONTEXT_AUDIT_ONLY", snapshot_quality, source_status,
            json.dumps(snapshot_payload, sort_keys=True), json.dumps(chart_payload, sort_keys=True),
        ),
    )
    inserts["printer_chart_volatility_snapshots"] = 1

    micro_payload = _base_context_payload(target, snapshot, "micro_event")
    micro_payload["known_fields"] = {
        "price_usd": price_usd,
        "price_change_5m": snapshot.get("price_change_5m"),
        "volume_5m": snapshot.get("volume_5m"),
        "txns_5m": snapshot.get("txns_5m"),
    }
    micro_payload["limitations"] = ["single snapshot is insufficient for 5m micro-event confirmation"]
    connection.execute(
        """
        INSERT INTO printer_micro_events (
            token_id, pair_id, token_mint, pair_address, detected_at, event_window_start_at, event_window_end_at,
            price_start, price_high, price_low, price_end, price_change_5m_percent, volume_5m, txns_5m,
            liquidity_start_usd, liquidity_end_usd, liquidity_exit_realism_label, slippage_label,
            price_impact_label, route_label, safety_status_label, liquidity_state_label, flow_direction_label,
            candle_path_label, micro_event_state_label, micro_event_move_label, micro_exit_realism_label,
            late_buy_trap_label, held_to_15m_result_label, micro_event_payload_quality_label,
            micro_event_memory_gate_label, data_quality_label, source_status,
            raw_micro_event_payload_json, normalized_micro_event_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target["token_id"], target["pair_id"], target["token_mint"], target["pair_address"], captured_at,
            snapshot.get("captured_at"), captured_at, price_usd, price_usd, price_usd, price_usd,
            snapshot.get("price_change_5m"), snapshot.get("volume_5m"), snapshot.get("txns_5m"),
            liquidity_usd, liquidity_usd, "EXIT_UNKNOWN", "SLIPPAGE_UNKNOWN", "PRICE_IMPACT_UNKNOWN",
            "ROUTE_UNKNOWN", "SAFETY_UNKNOWN", _liquidity_state_label(liquidity_usd), "FLOW_UNKNOWN",
            "PATH_UNKNOWN", "MICRO_EVENT_UNKNOWN", "MOVE_UNKNOWN", "MICRO_EXIT_UNKNOWN",
            "LATE_BUY_TRAP_UNKNOWN", "HELD_TO_15M_UNKNOWN", "MICRO_EVENT_CONTEXT_UNKNOWN",
            "MICRO_EVENT_AUDIT_ONLY", "MISSING_CRITICAL_DATA", "PARTIAL",
            json.dumps(snapshot_payload, sort_keys=True), json.dumps(micro_payload, sort_keys=True),
        ),
    )
    inserts["printer_micro_events"] = 1

    market_payload = {
        "phase": "28",
        "category": "market_regime",
        "evidence_boundary": "no governed broad-market source exists in Phase 28",
        "skip_reason": "missing_governed_market_source",
        "attached_token_id": target["token_id"],
        "attached_pair_id": target["pair_id"],
        "snapshot_id": snapshot["id"],
    }
    connection.execute(
        """
        INSERT INTO printer_market_regime_snapshots (
            captured_at, market_regime_label, market_transition_label, market_payload_quality_label,
            data_quality_label, source_status, raw_market_payload_json, normalized_market_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            captured_at, "UNKNOWN", "UNKNOWN_TRANSITION", "MARKET_CONTEXT_UNKNOWN",
            "MISSING_CRITICAL_DATA", "PARTIAL", json.dumps({}, sort_keys=True),
            json.dumps(market_payload, sort_keys=True),
        ),
    )
    inserts["printer_market_regime_snapshots"] = 1

    chain_payload = {
        "phase": "28",
        "category": "solana_chain_heat",
        "evidence_boundary": "no governed Solana chain-heat source exists in Phase 28",
        "skip_reason": "missing_governed_chain_heat_source",
        "attached_token_id": target["token_id"],
        "attached_pair_id": target["pair_id"],
        "snapshot_id": snapshot["id"],
    }
    connection.execute(
        """
        INSERT INTO printer_solana_chain_heat_snapshots (
            captured_at, chain_heat_label, activity_label, liquidity_label, congestion_label,
            chain_heat_payload_quality_label, data_quality_label, source_status,
            raw_chain_heat_payload_json, normalized_chain_heat_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            captured_at, "SOLANA_UNKNOWN", "ACTIVITY_UNKNOWN", "LIQUIDITY_UNKNOWN",
            "CONGESTION_UNKNOWN", "CHAIN_HEAT_CONTEXT_UNKNOWN", "MISSING_CRITICAL_DATA",
            "PARTIAL", json.dumps({}, sort_keys=True), json.dumps(chain_payload, sort_keys=True),
        ),
    )
    inserts["printer_solana_chain_heat_snapshots"] = 1

    return inserts


def build_collect_context_once_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_context_command_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        target = _resolve_approved_context_target(connection, args)
        snapshot = _resolve_context_snapshot(connection, args, target)
        existing_context_counts = _context_rows_for_target(connection, target)
        if sum(existing_context_counts.values()) > 0:
            inserted_context_rows = {}
            skipped_reason = "context_already_exists_for_target"
        else:
            inserted_context_rows = _insert_controlled_context_rows(connection, target, snapshot, _utc_now_text())
            skipped_reason = None
        connection.commit()
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guard_deltas = {table: deltas[table] for table in CONTROLLED_CONTEXT_GUARD_TABLES if deltas.get(table)}
    context_deltas = {table: deltas.get(table, 0) for table in CONTEXT_TABLES}
    status = get_operator_db_status(resolved, project_root)
    return {
        "command": "printer-collect-context-once",
        "db_path": str(resolved),
        "source_name": "dexscreener",
        "operator_approved": True,
        "token_id": target["token_id"],
        "pair_id": target["pair_id"],
        "token_mint": target["token_mint"],
        "pair_address": target["pair_address"],
        "snapshot_id": snapshot["id"],
        "inserted_context_rows": inserted_context_rows,
        "skipped_reason": skipped_reason,
        "context_table_deltas": context_deltas,
        "context_rows_created": sum(context_deltas.values()),
        "source_request_delta": deltas.get("printer_source_requests", 0),
        "source_response_delta": deltas.get("printer_source_responses", 0),
        "source_failure_delta": deltas.get("printer_source_failures", 0),
        "token_delta": deltas.get("printer_tokens", 0),
        "pair_delta": deltas.get("printer_pairs", 0),
        "snapshot_delta": deltas.get("printer_token_snapshots", 0),
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_collect_context_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Collect controlled context rows from approved snapshot evidence.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--token-mint")
    parser.add_argument("--token-id", type=int)
    parser.add_argument("--pair-address")
    parser.add_argument("--pair-id", type=int)
    parser.add_argument("--snapshot-id", type=int)
    parser.add_argument("--chain", default="solana")
    parser.add_argument("--source-name", default="dexscreener")
    args = parser.parse_args(argv)
    try:
        payload = build_collect_context_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _normalize_memory_window(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"15m", "window_15m"}:
        return "WINDOW_15M"
    raise ValueError("Phase 29 supports only the 15m memory window")


def _validate_memory_window_command_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("memory-window review requires explicit operator approval")
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("memory-window review is Solana-only")
    if not (args.token_mint or args.token_id):
        raise ValueError("memory-window review requires token_mint or token_id")
    if not (args.pair_address or args.pair_id):
        raise ValueError("memory-window review requires pair_address or pair_id")
    _normalize_memory_window(args.memory_window)


def _resolve_memory_context_rows(connection: sqlite3.Connection, target: dict[str, Any]) -> dict[str, dict[str, Any]]:
    token_id = target["token_id"]
    pair_id = target["pair_id"]
    context: dict[str, dict[str, Any]] = {}
    table_to_key = {
        "printer_safety_rug_snapshots": ("safety", "captured_at"),
        "printer_liquidity_exit_snapshots": ("liquidity_exit", "captured_at"),
        "printer_trading_flow_snapshots": ("trading_flow", "captured_at"),
        "printer_chart_volatility_snapshots": ("chart_volatility", "captured_at"),
        "printer_micro_events": ("micro_event", "detected_at"),
    }
    for table, (key, order_column) in table_to_key.items():
        row = connection.execute(
            f"""
            SELECT *
            FROM {table}
            WHERE token_id = ? AND pair_id = ?
            ORDER BY {order_column} DESC, id DESC
            LIMIT 1
            """,
            (token_id, pair_id),
        ).fetchone()
        context[key] = _row_to_dict(row)
    market_row = connection.execute(
        "SELECT * FROM printer_market_regime_snapshots ORDER BY captured_at DESC, id DESC LIMIT 1"
    ).fetchone()
    chain_row = connection.execute(
        "SELECT * FROM printer_solana_chain_heat_snapshots ORDER BY captured_at DESC, id DESC LIMIT 1"
    ).fetchone()
    context["market"] = _row_to_dict(market_row)
    context["chain_heat"] = _row_to_dict(chain_row)
    return context


def _context_is_present(context_rows: dict[str, dict[str, Any]]) -> bool:
    required = {"market", "chain_heat", "safety", "liquidity_exit", "trading_flow", "chart_volatility", "micro_event"}
    return all(context_rows.get(key) for key in required)


def _context_memory_labels(context_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "market_regime_label": context_rows.get("market", {}).get("market_regime_label"),
        "chain_heat_label": context_rows.get("chain_heat", {}).get("chain_heat_label"),
        "safety_status_label": context_rows.get("safety", {}).get("safety_status_label"),
        "rug_risk_label": context_rows.get("safety", {}).get("rug_risk_label"),
        "liquidity_state_label": context_rows.get("liquidity_exit", {}).get("liquidity_state_label"),
        "entry_realism_label": context_rows.get("liquidity_exit", {}).get("entry_realism_label"),
        "exit_realism_label": context_rows.get("liquidity_exit", {}).get("exit_realism_label"),
        "realism_gate_label": context_rows.get("liquidity_exit", {}).get("realism_gate_label"),
        "flow_direction_label": context_rows.get("trading_flow", {}).get("flow_direction_label"),
        "flow_pressure_label": context_rows.get("trading_flow", {}).get("flow_pressure_label"),
        "trend_structure_label": context_rows.get("chart_volatility", {}).get("trend_structure_label"),
        "volatility_label": context_rows.get("chart_volatility", {}).get("volatility_label"),
        "micro_event_state_label": context_rows.get("micro_event", {}).get("micro_event_state_label"),
        "held_to_15m_result_label": context_rows.get("micro_event", {}).get("held_to_15m_result_label"),
    }


def _memory_storage_status(memory_quality_label: str) -> str:
    return {
        "CLEAN_MEMORY": "CLEAN_MEMORY",
        "PARTIAL_MEMORY": "PARTIAL_MEMORY",
        "DIRTY_MEMORY": "DIRTY_MEMORY",
        "AUDIT_ONLY_MEMORY": "AUDIT_ONLY",
        "DO_NOT_TRAIN_MEMORY": "DO_NOT_TRAIN",
    }[memory_quality_label]


def _existing_memory_for_target(connection: sqlite3.Connection, target: dict[str, Any], window_kind: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM printer_memory_windows
        WHERE token_id = ? AND pair_id = ? AND window_kind = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (target["token_id"], target["pair_id"], window_kind),
    ).fetchone()


def _classify_first_memory_review(snapshots: list[dict[str, Any]], context_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rejection_reasons: list[str] = []
    if len(snapshots) < 2:
        rejection_reasons.extend(["REJECT_MISSING_SNAPSHOTS", "INCOMPLETE_15M_WINDOW", "INSUFFICIENT_SNAPSHOT_COVERAGE"])
    if any(row.get("price_usd") is None or row.get("liquidity_usd") is None for row in snapshots):
        rejection_reasons.append("REJECT_MISSING_CRITICAL_FIELDS")
    if not _context_is_present(context_rows):
        rejection_reasons.append("MISSING_OR_UNKNOWN_CONTEXT")
    labels = _context_memory_labels(context_rows)
    if any(value in {None, "UNKNOWN", "SOLANA_UNKNOWN", "SAFETY_UNKNOWN", "ENTRY_UNKNOWN", "EXIT_UNKNOWN", "FLOW_UNKNOWN", "TREND_UNKNOWN", "MICRO_EVENT_UNKNOWN"} for value in labels.values()):
        rejection_reasons.append("MISSING_OR_UNKNOWN_CONTEXT")
    if not rejection_reasons:
        memory_quality = "CLEAN_MEMORY"
    elif len(snapshots) < 2:
        memory_quality = "DIRTY_MEMORY"
    else:
        memory_quality = "AUDIT_ONLY_MEMORY"
    unique_reasons = list(dict.fromkeys(rejection_reasons or ["REVIEW_PASSED"]))
    return {
        "outcome_label": "OUTCOME_UNKNOWN" if memory_quality != "CLEAN_MEMORY" else "NO_PUMP",
        "action_lesson_label": "ACTION_LESSON_UNKNOWN",
        "memory_quality_label": memory_quality,
        "memory_status": _memory_storage_status(memory_quality),
        "data_quality_label": "MISSING_CRITICAL_DATA" if memory_quality != "CLEAN_MEMORY" else "CLEAN_DATA",
        "do_not_train": 0 if memory_quality == "CLEAN_MEMORY" else 1,
        "rejection_reasons": unique_reasons,
        "retrieval_ready": memory_quality == "CLEAN_MEMORY",
    }


def _snapshot_price_path_for_memory(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if len(snapshots) < 2:
        price = snapshots[0].get("price_usd") if snapshots else None
        return {
            "price_start": price,
            "price_high": price,
            "price_low": price,
            "price_end": price,
            "price_change_percent": None,
            "max_runup_percent": None,
            "max_drawdown_percent": None,
        }
    prices = [float(row["price_usd"]) for row in snapshots if row.get("price_usd") is not None]
    if not prices:
        return {
            "price_start": None,
            "price_high": None,
            "price_low": None,
            "price_end": None,
            "price_change_percent": None,
            "max_runup_percent": None,
            "max_drawdown_percent": None,
        }
    start, end = prices[0], prices[-1]
    high, low = max(prices), min(prices)
    pct = None if start == 0 else ((end - start) / start) * 100.0
    runup = None if start == 0 else ((high - start) / start) * 100.0
    drawdown = None if start == 0 else ((low - start) / start) * 100.0
    return {
        "price_start": start,
        "price_high": high,
        "price_low": low,
        "price_end": end,
        "price_change_percent": pct,
        "max_runup_percent": runup,
        "max_drawdown_percent": drawdown,
    }


def _record_first_memory_window(
    connection: sqlite3.Connection,
    target: dict[str, Any],
    snapshot: dict[str, Any],
    context_rows: dict[str, dict[str, Any]],
    window_kind: str,
    source_reference: str | None,
) -> dict[str, Any]:
    opened_at = snapshot["captured_at"]
    closed_at = (datetime.fromisoformat(str(opened_at).replace("Z", "+00:00")) + timedelta(minutes=15)).isoformat()
    snapshots = [snapshot]
    classification = _classify_first_memory_review(snapshots, context_rows)
    path = _snapshot_price_path_for_memory(snapshots)
    supporting_context = {
        "phase": "29",
        "source_reference": source_reference,
        "snapshot_ids": [snapshot["id"]],
        "expected_snapshot_count": 2,
        "actual_snapshot_count": len(snapshots),
        "context_row_ids": {
            "market": context_rows["market"].get("id"),
            "chain_heat": context_rows["chain_heat"].get("id"),
            "safety": context_rows["safety"].get("id"),
            "liquidity_exit": context_rows["liquidity_exit"].get("id"),
            "trading_flow": context_rows["trading_flow"].get("id"),
            "chart_volatility": context_rows["chart_volatility"].get("id"),
            "micro_event": context_rows["micro_event"].get("id"),
        },
        "context_labels": _context_memory_labels(context_rows),
        "retrieval_ready": classification["retrieval_ready"],
    }
    cursor = connection.execute(
        """
        INSERT INTO printer_memory_windows (
            token_id, pair_id, window_kind, opened_at, closed_at,
            expected_snapshot_count, actual_snapshot_count, missing_snapshot_count, coverage_state,
            memory_status, data_quality_label, do_not_train, window_status, outcome_label,
            memory_quality_label, rejection_reasons_json, supporting_context_json, created_by_phase
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target["token_id"], target["pair_id"], window_kind, opened_at, closed_at,
            2, len(snapshots), max(0, 2 - len(snapshots)), "INCOMPLETE_15M_WINDOW",
            classification["memory_status"], classification["data_quality_label"], classification["do_not_train"],
            "WINDOW_AUDIT_ONLY" if classification["do_not_train"] else "WINDOW_CLOSED",
            classification["outcome_label"], classification["memory_quality_label"],
            json.dumps(classification["rejection_reasons"], sort_keys=True),
            json.dumps(supporting_context, sort_keys=True), "phase29",
        ),
    )
    memory_window_id = int(cursor.lastrowid)
    episode_status = "EPISODE_DIRTY" if classification["memory_quality_label"] == "DIRTY_MEMORY" else "EPISODE_AUDIT_ONLY"
    cursor = connection.execute(
        """
        INSERT INTO printer_episodes (
            memory_window_id, token_id, pair_id, episode_kind, episode_status,
            memory_status, data_quality_label, do_not_train, window_kind,
            episode_outcome_label, memory_quality_label, action_lesson_label,
            rejection_reasons_json, episode_summary_json, supporting_context_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            memory_window_id, target["token_id"], target["pair_id"], "TOKEN_WINDOW_EPISODE",
            episode_status, classification["memory_status"], classification["data_quality_label"],
            classification["do_not_train"], window_kind, classification["outcome_label"],
            classification["memory_quality_label"], classification["action_lesson_label"],
            json.dumps(classification["rejection_reasons"], sort_keys=True),
            json.dumps({"price_path": path, "coverage_state": "INCOMPLETE_15M_WINDOW"}, sort_keys=True),
            json.dumps(supporting_context, sort_keys=True),
        ),
    )
    episode_id = int(cursor.lastrowid)
    connection.execute(
        "INSERT INTO printer_episode_snapshots (episode_id, token_snapshot_id, position_in_episode) VALUES (?, ?, 0)",
        (episode_id, snapshot["id"]),
    )
    cursor = connection.execute(
        """
        INSERT INTO printer_episode_outcomes (
            episode_id, memory_window_id, token_id, pair_id, window_kind,
            outcome_label, action_lesson_label, price_start, price_high,
            price_low, price_end, price_change_percent, max_runup_percent,
            max_drawdown_percent, realistic_entry_available, realistic_exit_available,
            realistic_profit_possible, capital_protection_possible, memory_quality_label,
            rejection_reasons_json, outcome_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, ?, ?, ?)
        """,
        (
            episode_id, memory_window_id, target["token_id"], target["pair_id"], window_kind,
            classification["outcome_label"], classification["action_lesson_label"],
            path["price_start"], path["price_high"], path["price_low"], path["price_end"],
            path["price_change_percent"], path["max_runup_percent"], path["max_drawdown_percent"],
            classification["memory_quality_label"],
            json.dumps(classification["rejection_reasons"], sort_keys=True),
            json.dumps({"price_path": path, "outcome_determinable": False}, sort_keys=True),
        ),
    )
    outcome_id = int(cursor.lastrowid)
    fingerprint_payload = {
        "phase": "29",
        "window_kind": window_kind,
        "outcome_label": classification["outcome_label"],
        "memory_quality_label": classification["memory_quality_label"],
        "retrieval_ready": classification["retrieval_ready"],
        "coverage_state": "INCOMPLETE_15M_WINDOW",
        **_context_memory_labels(context_rows),
    }
    cursor = connection.execute(
        """
        INSERT INTO printer_memory_fingerprints (
            episode_id, fingerprint_kind, fingerprint_payload_json,
            memory_status, data_quality_label, do_not_train
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            episode_id, "STATIC_CONDITION_SUMMARY",
            json.dumps(fingerprint_payload, sort_keys=True),
            classification["memory_status"], classification["data_quality_label"],
            classification["do_not_train"],
        ),
    )
    fingerprint_id = int(cursor.lastrowid)
    return {
        "memory_window_id": memory_window_id,
        "episode_id": episode_id,
        "outcome_id": outcome_id,
        "fingerprint_id": fingerprint_id,
        **classification,
    }


def build_memory_window_once_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_memory_window_command_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    window_kind = _normalize_memory_window(args.memory_window)
    before_counts = get_core_table_counts(resolved, project_root)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        target = _resolve_approved_context_target(connection, args)
        snapshot = _resolve_context_snapshot(connection, args, target)
        context_rows = _resolve_memory_context_rows(connection, target)
        if not _context_is_present(context_rows):
            raise ValueError("memory-window review requires existing Phase 28 context rows")
        existing = _existing_memory_for_target(connection, target, window_kind)
        if existing is not None:
            result = {
                "memory_window_id": int(existing["id"]),
                "episode_id": None,
                "outcome_id": None,
                "fingerprint_id": None,
                "memory_quality_label": existing["memory_quality_label"],
                "memory_status": existing["memory_status"],
                "data_quality_label": existing["data_quality_label"],
                "do_not_train": int(existing["do_not_train"]),
                "rejection_reasons": json.loads(existing["rejection_reasons_json"] or "[]"),
                "retrieval_ready": int(existing["do_not_train"]) == 0 and existing["memory_quality_label"] == "CLEAN_MEMORY",
                "outcome_label": existing["outcome_label"],
                "action_lesson_label": "ACTION_LESSON_UNKNOWN",
                "skipped_reason": "memory_window_already_exists_for_target",
            }
        else:
            result = _record_first_memory_window(
                connection, target, snapshot, context_rows, window_kind, args.source_reference
            )
            result["skipped_reason"] = None
        connection.commit()
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    memory_deltas = {table: deltas.get(table, 0) for table in MEMORY_OUTPUT_TABLES}
    context_deltas = {table: deltas.get(table, 0) for table in CONTEXT_TABLES}
    guard_deltas = {table: deltas[table] for table in FIRST_MEMORY_GUARD_TABLES if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    return {
        "command": "printer-build-memory-window-once",
        "db_path": str(resolved),
        "operator_approved": True,
        "token_id": target["token_id"],
        "pair_id": target["pair_id"],
        "token_mint": target["token_mint"],
        "pair_address": target["pair_address"],
        "snapshot_id": snapshot["id"],
        "memory_window": "15m",
        "window_kind": window_kind,
        "memory_result": result,
        "memory_table_deltas": memory_deltas,
        "context_table_deltas": context_deltas,
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "source_request_delta": deltas.get("printer_source_requests", 0),
        "source_response_delta": deltas.get("printer_source_responses", 0),
        "source_failure_delta": deltas.get("printer_source_failures", 0),
        "token_delta": deltas.get("printer_tokens", 0),
        "pair_delta": deltas.get("printer_pairs", 0),
        "snapshot_delta": deltas.get("printer_token_snapshots", 0),
        "context_delta_total": sum(context_deltas.values()),
        "retrieval_delta": deltas.get("printer_memory_retrieval_queries", 0) + deltas.get("printer_memory_retrieval_matches", 0),
        "paper_decision_delta": deltas.get("printer_paper_decisions", 0),
        "paper_position_delta": deltas.get("printer_paper_positions", 0),
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_build_memory_window_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Build one controlled 15m memory-window review from local evidence.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--token-mint")
    parser.add_argument("--token-id", type=int)
    parser.add_argument("--pair-address")
    parser.add_argument("--pair-id", type=int)
    parser.add_argument("--snapshot-id", type=int)
    parser.add_argument("--chain", default="solana")
    parser.add_argument("--memory-window", default="15m")
    parser.add_argument("--source-reference")
    args = parser.parse_args(argv)
    try:
        payload = build_memory_window_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _validate_memory_audit_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("memory quality audit requires explicit operator approval")
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("memory quality audit is Solana-only")
    if not (args.memory_window_id or args.episode_id or args.token_mint or args.token_id):
        raise ValueError("memory quality audit requires memory_window_id, episode_id, token_mint, or token_id")


def _resolve_memory_audit_target(connection: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    if args.memory_window_id:
        window = connection.execute("SELECT * FROM printer_memory_windows WHERE id = ?", (args.memory_window_id,)).fetchone()
    elif args.episode_id:
        episode_row = connection.execute("SELECT memory_window_id FROM printer_episodes WHERE id = ?", (args.episode_id,)).fetchone()
        if episode_row is None:
            raise ValueError("memory quality audit target episode not found")
        window = connection.execute("SELECT * FROM printer_memory_windows WHERE id = ?", (episode_row["memory_window_id"],)).fetchone()
    else:
        target = _resolve_approved_context_target(connection, args)
        window = connection.execute(
            """
            SELECT *
            FROM printer_memory_windows
            WHERE token_id = ? AND pair_id = ? AND window_kind = 'WINDOW_15M'
            ORDER BY id DESC
            LIMIT 1
            """,
            (target["token_id"], target["pair_id"]),
        ).fetchone()
    if window is None:
        raise ValueError("memory quality audit target memory window not found")

    token = connection.execute("SELECT * FROM printer_tokens WHERE id = ?", (window["token_id"],)).fetchone()
    pair = connection.execute("SELECT * FROM printer_pairs WHERE id = ?", (window["pair_id"],)).fetchone()
    episode = connection.execute(
        "SELECT * FROM printer_episodes WHERE memory_window_id = ? ORDER BY id DESC LIMIT 1",
        (window["id"],),
    ).fetchone()
    if token is None or pair is None or episode is None:
        raise ValueError("memory quality audit requires token, pair, and episode rows")
    if token["chain"] != "solana":
        raise ValueError("memory quality audit target must be Solana")
    return {
        "window": _row_to_dict(window),
        "token": _row_to_dict(token),
        "pair": _row_to_dict(pair),
        "episode": _row_to_dict(episode),
    }


def _latest_row(connection: sqlite3.Connection, table: str, where: str = "", params: tuple[Any, ...] = ()) -> dict[str, Any]:
    query = f"SELECT * FROM {table} {where} ORDER BY id DESC LIMIT 1"
    return _row_to_dict(connection.execute(query, params).fetchone())


def _memory_audit_snapshot_summary(connection: sqlite3.Connection, window: dict[str, Any]) -> dict[str, Any]:
    rows = connection.execute(
        """
        SELECT s.*
        FROM printer_episode_snapshots es
        JOIN printer_token_snapshots s ON s.id = es.token_snapshot_id
        WHERE es.episode_id = (
            SELECT id FROM printer_episodes WHERE memory_window_id = ? ORDER BY id DESC LIMIT 1
        )
        ORDER BY es.position_in_episode ASC, s.captured_at ASC
        """,
        (window["id"],),
    ).fetchall()
    snapshots = [_row_to_dict(row) for row in rows]
    expected = int(window.get("expected_snapshot_count") or 2)
    actual = len(snapshots)
    times = [row.get("captured_at") for row in snapshots if row.get("captured_at")]
    observed_span = None
    if len(times) >= 2:
        observed_span = (
            datetime.fromisoformat(times[-1].replace("Z", "+00:00"))
            - datetime.fromisoformat(times[0].replace("Z", "+00:00"))
        ).total_seconds()
    return {
        "snapshot_count": actual,
        "expected_min_snapshot_count": expected,
        "missing_snapshot_count": max(0, expected - actual),
        "observed_window_span_seconds": observed_span,
        "missing_start_coverage": actual < 2,
        "missing_mid_window_coverage": actual < 2,
        "missing_end_coverage": actual < 2,
        "incomplete_15m_window": bool(window.get("coverage_state") == "INCOMPLETE_15M_WINDOW" or actual < expected),
        "insufficient_snapshot_coverage": actual < expected,
        "status": "INSUFFICIENT_SNAPSHOT_COVERAGE" if actual < expected else "SNAPSHOT_COVERAGE_SUFFICIENT",
        "snapshot_ids": [row["id"] for row in snapshots],
    }


def _memory_audit_source_summary(connection: sqlite3.Connection) -> dict[str, Any]:
    request_count = int(connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0])
    response_count = int(connection.execute("SELECT COUNT(*) FROM printer_source_responses").fetchone()[0])
    failure_count = int(connection.execute("SELECT COUNT(*) FROM printer_source_failures").fetchone()[0])
    latest_failure = _latest_row(connection, "printer_source_failures")
    statuses = {
        "snapshot_source_statuses": [
            row[0] for row in connection.execute("SELECT DISTINCT source_status FROM printer_token_snapshots").fetchall()
        ],
        "snapshot_data_quality_labels": [
            row[0] for row in connection.execute("SELECT DISTINCT data_quality_label FROM printer_token_snapshots").fetchall()
        ],
    }
    return {
        "source_request_count": request_count,
        "source_response_count": response_count,
        "source_failure_count": failure_count,
        "latest_source_failure": latest_failure,
        "source_status_summary": statuses,
        "required_evidence_failed_or_missing": failure_count > 0,
        "status": "SOURCE_ISSUES_VISIBLE" if failure_count else "SOURCE_QUALITY_ACCEPTABLE",
    }


def _memory_audit_context_summary(connection: sqlite3.Connection, token_id: int, pair_id: int) -> dict[str, Any]:
    context_rows = _resolve_memory_context_rows(connection, {"token_id": token_id, "pair_id": pair_id})
    labels = _context_memory_labels(context_rows)
    unknown_labels = {
        key: value for key, value in labels.items()
        if value in {None, "UNKNOWN", "SOLANA_UNKNOWN", "SAFETY_UNKNOWN", "ENTRY_UNKNOWN", "EXIT_UNKNOWN", "FLOW_UNKNOWN", "TREND_UNKNOWN", "MICRO_EVENT_UNKNOWN"}
    }
    return {
        "context_rows_present": {key: bool(value) for key, value in context_rows.items()},
        "context_labels": labels,
        "unknown_or_audit_only_context": unknown_labels,
        "liquidity_exit_realism_known": labels.get("entry_realism_label") == "ENTRY_REALISTIC" and labels.get("exit_realism_label") == "EXIT_REALISTIC",
        "market_context_real": labels.get("market_regime_label") not in {None, "UNKNOWN"},
        "chain_context_real": labels.get("chain_heat_label") not in {None, "SOLANA_UNKNOWN"},
        "micro_event_sufficient": labels.get("micro_event_state_label") not in {None, "MICRO_EVENT_UNKNOWN"},
        "status": "MISSING_OR_UNKNOWN_CONTEXT" if unknown_labels else "CONTEXT_SUFFICIENT_FOR_AUDIT",
    }


def _memory_audit_outcome_summary(connection: sqlite3.Connection, window_id: int) -> dict[str, Any]:
    outcome = _latest_row(connection, "printer_episode_outcomes", "WHERE memory_window_id = ?", (window_id,))
    return {
        "outcome_exists": bool(outcome),
        "outcome_label": outcome.get("outcome_label"),
        "action_lesson_label": outcome.get("action_lesson_label"),
        "realistic_profit_possible": bool(outcome.get("realistic_profit_possible")) if outcome else False,
        "capital_protection_possible": bool(outcome.get("capital_protection_possible")) if outcome else False,
        "status": "OUTCOME_NOT_DETERMINABLE" if outcome.get("outcome_label") == "OUTCOME_UNKNOWN" else "OUTCOME_REVIEW_REQUIRED",
        "no_paper_result": True,
    }


def _memory_audit_fingerprint_summary(connection: sqlite3.Connection, episode_id: int) -> dict[str, Any]:
    fingerprint = _latest_row(connection, "printer_memory_fingerprints", "WHERE episode_id = ?", (episode_id,))
    payload = _json_or_empty(fingerprint.get("fingerprint_payload_json"))
    return {
        "fingerprint_exists": bool(fingerprint),
        "fingerprint_memory_status": fingerprint.get("memory_status"),
        "fingerprint_do_not_train": bool(fingerprint.get("do_not_train")) if fingerprint else True,
        "fingerprint_retrieval_ready": bool(payload.get("retrieval_ready")) if payload else False,
        "learned_representation_present": False,
        "numeric_similarity_artifact_present": False,
        "decision_metric_artifact_present": False,
        "similarity_retrieval_executed": False,
        "status": "FINGERPRINT_NOT_RETRIEVAL_READY" if not payload.get("retrieval_ready") else "FINGERPRINT_RETRIEVAL_READY",
    }


def _build_memory_quality_audit_report(connection: sqlite3.Connection, target: dict[str, Any]) -> dict[str, Any]:
    window = target["window"]
    token = target["token"]
    pair = target["pair"]
    episode = target["episode"]
    dirty_reasons = json.loads(window.get("rejection_reasons_json") or "[]")
    snapshot_summary = _memory_audit_snapshot_summary(connection, window)
    source_summary = _memory_audit_source_summary(connection)
    context_summary = _memory_audit_context_summary(connection, int(window["token_id"]), int(window["pair_id"]))
    outcome_summary = _memory_audit_outcome_summary(connection, int(window["id"]))
    fingerprint_summary = _memory_audit_fingerprint_summary(connection, int(episode["id"]))
    retrieval_ready = not bool(window.get("do_not_train")) and window.get("memory_quality_label") == "CLEAN_MEMORY" and fingerprint_summary["fingerprint_retrieval_ready"]
    clean_eligible = window.get("memory_quality_label") == "CLEAN_MEMORY" and not dirty_reasons and retrieval_ready
    audit_verdict = [
        "DIRTY_MEMORY_CONFIRMED" if window.get("memory_quality_label") == "DIRTY_MEMORY" else "MEMORY_QUALITY_REVIEW_REQUIRED",
        "CLEAN_MEMORY_BLOCKED" if not clean_eligible else "CLEAN_MEMORY_ELIGIBLE",
        "MEMORY_NOT_TRUSTWORTHY_FOR_RETRIEVAL" if not retrieval_ready else "MEMORY_RETRIEVAL_READY",
        "RETRIEVAL_NOT_ALLOWED" if not retrieval_ready else "RETRIEVAL_ALLOWED",
        "PAPER_DECISION_NOT_ALLOWED" if not retrieval_ready else "PAPER_DECISION_REQUIRES_PHASE_32",
    ]
    return {
        "memory_window_id": window["id"],
        "episode_id": episode["id"],
        "token_id": window["token_id"],
        "pair_id": window["pair_id"],
        "token_mint": token["token_mint"],
        "pair_address": pair["pair_address"],
        "memory_window_label": window["window_kind"],
        "memory_quality_label": window["memory_quality_label"],
        "retrieval_ready": retrieval_ready,
        "audit_status": "PHASE30_MEMORY_QUALITY_AUDIT",
        "audit_verdict": audit_verdict,
        "dirty_reasons": dirty_reasons,
        "snapshot_coverage_status": snapshot_summary["status"],
        "snapshot_gap_summary": snapshot_summary,
        "source_quality_summary": source_summary,
        "context_quality_summary": context_summary,
        "outcome_quality_summary": outcome_summary,
        "fingerprint_quality_summary": fingerprint_summary,
        "clean_memory_eligible": clean_eligible,
        "retrieval_allowed": False,
        "paper_decision_allowed": False,
        "recommended_next_action": "Collect enough complete 15m snapshot coverage and replace unknown/audit-only context before Phase 31 retrieval testing.",
    }


def _record_memory_quality_audit_report(connection: sqlite3.Connection, report: dict[str, Any]) -> tuple[bool, int]:
    existing = connection.execute(
        """
        SELECT id
        FROM printer_memory_audit_reports
        WHERE memory_window_id = ? AND audit_status = 'PHASE30_MEMORY_QUALITY_AUDIT'
        ORDER BY id DESC
        LIMIT 1
        """,
        (report["memory_window_id"],),
    ).fetchone()
    if existing:
        return False, int(existing["id"])
    cursor = connection.execute(
        """
        INSERT INTO printer_memory_audit_reports (
            episode_id, memory_window_id, token_id, pair_id, audit_status,
            memory_quality_label, rejection_reasons_json, audit_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            report["episode_id"],
            report["memory_window_id"],
            report["token_id"],
            report["pair_id"],
            report["audit_status"],
            report["memory_quality_label"],
            json.dumps(report["dirty_reasons"], sort_keys=True),
            json.dumps(report, sort_keys=True),
        ),
    )
    return True, int(cursor.lastrowid)


def build_memory_quality_audit_once_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_memory_audit_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        target = _resolve_memory_audit_target(connection, args)
        report = _build_memory_quality_audit_report(connection, target)
        created, audit_report_id = _record_memory_quality_audit_report(connection, report)
        connection.commit()
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guarded_tables = [
        "printer_tokens",
        "printer_pairs",
        "printer_source_requests",
        "printer_source_responses",
        "printer_source_failures",
        "printer_token_snapshots",
        *CONTEXT_TABLES,
        *MEMORY_OUTPUT_TABLES,
        "printer_memory_retrieval_queries",
        "printer_memory_retrieval_matches",
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_scheduler_jobs",
    ]
    guard_deltas = {table: deltas[table] for table in guarded_tables if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    return {
        "command": "printer-audit-memory-quality-once",
        "db_path": str(resolved),
        "operator_approved": True,
        "audit_report_id": audit_report_id,
        "audit_report_created": created,
        "audit_report": report,
        "memory_audit_report_delta": deltas.get("printer_memory_audit_reports", 0),
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_audit_memory_quality_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Audit one existing memory window without retrieval or paper decisions.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--memory-window-id", type=int)
    parser.add_argument("--episode-id", type=int)
    parser.add_argument("--token-mint")
    parser.add_argument("--token-id", type=int)
    parser.add_argument("--pair-address")
    parser.add_argument("--pair-id", type=int)
    parser.add_argument("--chain", default="solana")
    args = parser.parse_args(argv)
    try:
        payload = build_memory_quality_audit_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _validate_clean_memory_retrieval_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("clean memory retrieval requires explicit operator approval")
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("clean memory retrieval is Solana-only")
    if args.snapshot_id is None and not (args.token_mint or args.token_id):
        raise ValueError("clean memory retrieval requires snapshot_id, token_mint, or token_id")
    if args.snapshot_id is None and not (args.pair_address or args.pair_id):
        raise ValueError("clean memory retrieval requires pair_address or pair_id with token input")


def _resolve_memory_retrieval_target(connection: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    if args.snapshot_id is not None:
        row = connection.execute(
            """
            SELECT s.*, t.token_mint, t.chain, p.pair_address
            FROM printer_token_snapshots s
            JOIN printer_tokens t ON t.id = s.token_id
            JOIN printer_pairs p ON p.id = s.pair_id
            WHERE s.id = ?
            """,
            (args.snapshot_id,),
        ).fetchone()
        if row is None:
            raise ValueError("clean memory retrieval requires an existing approved snapshot")
        if row["chain"] != "solana":
            raise ValueError("clean memory retrieval target must be Solana")
        return {
            "token_id": int(row["token_id"]),
            "pair_id": int(row["pair_id"]),
            "token_mint": row["token_mint"],
            "pair_address": row["pair_address"],
            "snapshot_id": int(row["id"]),
        }
    target = _resolve_approved_context_target(connection, args)
    snapshot = _resolve_context_snapshot(connection, args, target)
    return {
        **target,
        "snapshot_id": int(snapshot["id"]),
    }


def _build_current_retrieval_context(connection: sqlite3.Connection, target: dict[str, Any]) -> dict[str, Any]:
    context_rows = _resolve_memory_context_rows(connection, target)
    labels = _context_memory_labels(context_rows)
    window = _latest_row(
        connection,
        "printer_memory_windows",
        "WHERE token_id = ? AND pair_id = ?",
        (target["token_id"], target["pair_id"]),
    )
    latest_audit = _latest_row(
        connection,
        "printer_memory_audit_reports",
        "WHERE token_id = ? AND pair_id = ?",
        (target["token_id"], target["pair_id"]),
    )
    current_fingerprint = {
        **labels,
        "window_kind": window.get("window_kind") or "WINDOW_15M",
        "memory_quality_label": window.get("memory_quality_label"),
        "retrieval_ready": False,
        "source_status": "PARTIAL",
        "data_quality_label": window.get("data_quality_label") or "MISSING_CRITICAL_DATA",
        "snapshot_id": target.get("snapshot_id"),
    }
    return {
        "context_rows_present": {key: bool(value) for key, value in context_rows.items()},
        "current_fingerprint": current_fingerprint,
        "latest_memory_quality_label": window.get("memory_quality_label"),
        "latest_memory_retrieval_ready": False,
        "latest_audit_status": latest_audit.get("audit_status"),
        "latest_audit_id": latest_audit.get("id"),
    }


def _dirty_block_reasons(match: dict[str, Any]) -> list[str]:
    reasons = []
    if match.get("memory_quality_label") == "DIRTY_MEMORY":
        reasons.append("DIRTY_MEMORY_NOT_RETRIEVAL_READY")
    if match.get("match_strength_label") == "DO_NOT_TRAIN_EXCLUDED":
        reasons.append("DO_NOT_TRAIN")
    payload = match.get("memory_fingerprint") or {}
    if payload.get("retrieval_ready") is False:
        reasons.append("RETRIEVAL_READY_FALSE")
    if payload.get("coverage_state") == "INCOMPLETE_15M_WINDOW":
        reasons.append("INSUFFICIENT_SNAPSHOT_COVERAGE")
    return list(dict.fromkeys(reasons or ["NOT_CLEAN_MEMORY"]))


def _build_clean_memory_retrieval_report(
    connection: sqlite3.Connection,
    target: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    context = _build_current_retrieval_context(connection, target)
    query_payload = {
        "query_type": "CLEAN_MEMORY_ONLY_QUERY",
        "token_id": target["token_id"],
        "pair_id": target["pair_id"],
        "token_mint": target["token_mint"],
        "pair_address": target["pair_address"],
        "query_at": _utc_now_text(),
        "context": context["current_fingerprint"],
        "source_status": "PARTIAL",
        "data_quality_label": "MISSING_CRITICAL_DATA",
    }
    all_matches = retrieve_memory_matches_for_current_setup(connection, query_payload)
    clean_matches = [match for match in all_matches if match.get("included_as_clean_evidence")]
    dirty_matches = [match for match in all_matches if match.get("memory_quality_label") == "DIRTY_MEMORY"]
    blocked_reasons: dict[str, list[str]] = {
        str(match.get("memory_window_id")): _dirty_block_reasons(match)
        for match in dirty_matches
    }
    retrieval_result_label = "RETRIEVAL_HAS_CLEAN_MATCHES" if clean_matches else "RETRIEVAL_BLOCKED_NO_CLEAN_MEMORY"
    memory_evidence_label = "MEMORY_EVIDENCE_STRONG" if clean_matches else "MEMORY_EVIDENCE_NOT_ENOUGH"
    report = {
        "token_id": target["token_id"],
        "pair_id": target["pair_id"],
        "token_mint": target["token_mint"],
        "pair_address": target["pair_address"],
        "snapshot_id": target["snapshot_id"],
        "query_type": "CLEAN_MEMORY_ONLY_QUERY",
        "retrieval_result_label": retrieval_result_label,
        "memory_evidence_label": memory_evidence_label,
        "clean_memory_count": int(connection.execute("SELECT COUNT(*) FROM printer_memory_windows WHERE memory_quality_label = 'CLEAN_MEMORY'").fetchone()[0]),
        "clean_eligible_memory_count": len(clean_matches),
        "dirty_memory_count": len(dirty_matches),
        "blocked_dirty_memory_count": len(dirty_matches),
        "retrieval_ready_false_count": len([match for match in all_matches if (match.get("memory_fingerprint") or {}).get("retrieval_ready") is False]),
        "clean_matches_returned": len(clean_matches),
        "dirty_or_audit_only_matches_returned_as_clean": 0,
        "blocked_match_reasons": blocked_reasons,
        "retrieval_allowed": bool(clean_matches),
        "paper_decision_allowed": False,
        "decision_allowed": False,
        "similar_clean_memories_found": len(clean_matches),
        "memory_evidence_summary": "memory evidence is insufficient for decision support" if not clean_matches else "clean memory evidence exists",
        "dirty_memory_blocked": bool(dirty_matches),
        "current_setup_context": context,
    }
    result_payload = {
        "current_fingerprint": context["current_fingerprint"],
        "retrieval_result_label": retrieval_result_label,
        "memory_evidence_label": memory_evidence_label,
        "report": report,
    }
    return report, clean_matches, {"query_payload": query_payload, "result_payload": result_payload}


def build_retrieve_clean_memory_once_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_clean_memory_retrieval_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        target = _resolve_memory_retrieval_target(connection, args)
        report, clean_matches, payloads = _build_clean_memory_retrieval_report(connection, target)
        query_id = record_memory_retrieval_query(connection, payloads["query_payload"], payloads["result_payload"])
        record_memory_retrieval_matches(connection, query_id, clean_matches)
        connection.commit()
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guarded_tables = [
        "printer_tokens",
        "printer_pairs",
        "printer_source_requests",
        "printer_source_responses",
        "printer_source_failures",
        "printer_token_snapshots",
        *CONTEXT_TABLES,
        *MEMORY_OUTPUT_TABLES,
        "printer_memory_audit_reports",
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_scheduler_jobs",
    ]
    guard_deltas = {table: deltas[table] for table in guarded_tables if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    return {
        "command": "printer-retrieve-clean-memory-once",
        "db_path": str(resolved),
        "operator_approved": True,
        "retrieval_query_id": query_id,
        "retrieval_report": report,
        "retrieval_query_delta": deltas.get("printer_memory_retrieval_queries", 0),
        "retrieval_match_delta": deltas.get("printer_memory_retrieval_matches", 0),
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_retrieve_clean_memory_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Retrieve clean eligible memory for one approved setup without paper decisions.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--snapshot-id", type=int)
    parser.add_argument("--token-mint")
    parser.add_argument("--token-id", type=int)
    parser.add_argument("--pair-address")
    parser.add_argument("--pair-id", type=int)
    parser.add_argument("--chain", default="solana")
    args = parser.parse_args(argv)
    try:
        payload = build_retrieve_clean_memory_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _validate_paper_decision_once_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("paper decision activation requires explicit operator approval")
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("paper decision activation is Solana-only")
    if args.retrieval_query_id is None and args.snapshot_id is None and not (args.token_mint or args.token_id):
        raise ValueError("paper decision activation requires retrieval_query_id, snapshot_id, token_mint, or token_id")
    if args.retrieval_query_id is None and args.snapshot_id is None and not (args.pair_address or args.pair_id):
        raise ValueError("paper decision activation requires pair_address or pair_id with token input")


def _resolve_paper_decision_target(connection: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    if args.retrieval_query_id is not None:
        query = connection.execute(
            "SELECT * FROM printer_memory_retrieval_queries WHERE id = ?",
            (args.retrieval_query_id,),
        ).fetchone()
        if query is None:
            raise ValueError("paper decision activation requires an existing retrieval query")
        token = connection.execute("SELECT * FROM printer_tokens WHERE id = ?", (query["token_id"],)).fetchone()
        pair = connection.execute("SELECT * FROM printer_pairs WHERE id = ?", (query["pair_id"],)).fetchone()
        if token is None or pair is None:
            raise ValueError("retrieval query must reference an approved token and pair")
        if token["chain"] != "solana":
            raise ValueError("paper decision target must be Solana")
        snapshot = _resolve_context_snapshot(
            connection,
            argparse.Namespace(snapshot_id=args.snapshot_id, **{
                "token_id": int(token["id"]),
                "token_mint": None,
                "pair_id": int(pair["id"]),
                "pair_address": None,
            }),
            {
                "token_id": int(token["id"]),
                "pair_id": int(pair["id"]),
                "token_mint": token["token_mint"],
                "pair_address": pair["pair_address"],
            },
        )
        return {
            "token_id": int(token["id"]),
            "pair_id": int(pair["id"]),
            "token_mint": token["token_mint"],
            "pair_address": pair["pair_address"],
            "snapshot_id": int(snapshot["id"]),
            "retrieval_query_id": int(query["id"]),
        }
    target = _resolve_memory_retrieval_target(connection, args)
    query = _latest_row(
        connection,
        "printer_memory_retrieval_queries",
        "WHERE token_id = ? AND pair_id = ?",
        (target["token_id"], target["pair_id"]),
    )
    if not query:
        raise ValueError("paper decision activation requires an existing real retrieval query")
    return {
        **target,
        "retrieval_query_id": int(query["id"]),
    }


def _summarize_decision_retrieval_gate(connection: sqlite3.Connection, retrieval_query_id: int) -> dict[str, Any]:
    query = _latest_row(connection, "printer_memory_retrieval_queries", "WHERE id = ?", (retrieval_query_id,))
    matches = [
        _row_to_dict(row)
        for row in connection.execute(
            """
            SELECT *
            FROM printer_memory_retrieval_matches
            WHERE retrieval_query_id = ?
            ORDER BY id ASC
            """,
            (retrieval_query_id,),
        ).fetchall()
    ]
    clean_matches = [match for match in matches if int(match.get("included_as_clean_evidence") or 0) == 1]
    dirty_memory_count = int(connection.execute("SELECT COUNT(*) FROM printer_memory_windows WHERE memory_quality_label = 'DIRTY_MEMORY'").fetchone()[0])
    retrieval_ready_false_count = int(connection.execute("SELECT COUNT(*) FROM printer_memory_fingerprints WHERE do_not_train = 1 OR memory_status != 'CLEAN_MEMORY'").fetchone()[0])
    blocked_dirty_count = dirty_memory_count if query.get("retrieval_result_label") == "RETRIEVAL_BLOCKED_NO_CLEAN_MEMORY" else 0
    return {
        "retrieval_query": query,
        "clean_matches": clean_matches,
        "clean_eligible_memory_count": len(clean_matches),
        "dirty_memory_count": dirty_memory_count,
        "blocked_dirty_memory_count": blocked_dirty_count,
        "clean_matches_returned": len(clean_matches),
        "dirty_matches_used_for_decision": 0,
        "dirty_memory_used": False,
        "retrieval_ready_false_count": retrieval_ready_false_count,
        "retrieval_allowed": bool(clean_matches),
        "decision_allowed": False,
        "buy_allowed": False,
        "paper_position_allowed": False,
        "blocked_reason": "BLOCKED_NO_CLEAN_MEMORY",
    }


def _latest_snapshot_for_target(connection: sqlite3.Connection, target: dict[str, Any]) -> dict[str, Any]:
    return _resolve_context_snapshot(
        connection,
        argparse.Namespace(snapshot_id=target.get("snapshot_id")),
        target,
    )


def _build_paper_decision_report(connection: sqlite3.Connection, target: dict[str, Any], gate_summary: dict[str, Any]) -> dict[str, Any]:
    snapshot = _latest_snapshot_for_target(connection, target)
    context_rows = _resolve_memory_context_rows(connection, target)
    labels = _context_memory_labels(context_rows)
    return {
        "Decision": "NO_ACTION",
        "Current setup": {
            "token_id": target["token_id"],
            "pair_id": target["pair_id"],
            "token_mint": target["token_mint"],
            "pair_address": target["pair_address"],
            "snapshot_id": snapshot.get("id"),
        },
        "Market condition": labels.get("market_regime_label") or "UNKNOWN",
        "Solana condition": labels.get("chain_heat_label") or "SOLANA_UNKNOWN",
        "Safety condition": labels.get("safety_status_label") or "SAFETY_UNKNOWN",
        "Liquidity / exit condition": {
            "liquidity_state_label": labels.get("liquidity_state_label"),
            "entry_realism_label": labels.get("entry_realism_label"),
            "exit_realism_label": labels.get("exit_realism_label"),
            "realism_gate_label": labels.get("realism_gate_label"),
        },
        "Trading flow condition": {
            "flow_direction_label": labels.get("flow_direction_label"),
            "flow_pressure_label": labels.get("flow_pressure_label"),
        },
        "Chart / volatility condition": {
            "trend_structure_label": labels.get("trend_structure_label"),
            "volatility_label": labels.get("volatility_label"),
        },
        "Similar clean memories found": gate_summary["clean_eligible_memory_count"],
        "What happened in those memories": "NO_CLEAN_MEMORY_AVAILABLE",
        "Best historical action": "NOT_AVAILABLE",
        "Worst historical action": "NOT_AVAILABLE",
        "Current action": "NO_ACTION",
        "Reason": "Clean memory retrieval returned zero eligible matches; dirty memory remains blocked.",
        "Invalidation condition": "Revisit only after clean retrieval evidence exists.",
        "Paper trade status": "NO_POSITION_OPENED",
        "Audit plan": "Review decision after additional clean 15m memory evidence is available.",
        "blocked_reason": gate_summary["blocked_reason"],
        "clean_eligible_memory_count": gate_summary["clean_eligible_memory_count"],
        "dirty_memory_count": gate_summary["dirty_memory_count"],
        "blocked_dirty_memory_count": gate_summary["blocked_dirty_memory_count"],
        "dirty_memory_used": False,
        "buy_allowed": False,
        "paper_position_allowed": False,
    }


def _insert_blocked_paper_decision(
    connection: sqlite3.Connection,
    target: dict[str, Any],
    gate_summary: dict[str, Any],
    report: dict[str, Any],
) -> int:
    decided_at = _utc_now_text()
    reasons = ["REASON_NOT_ENOUGH_CLEAN_MEMORY"]
    blocking = [
        "BLOCKED_NO_CLEAN_MEMORY",
        "BLOCKED_RETRIEVAL_NOT_ALLOWED",
        "BLOCKED_DIRTY_MEMORY_ONLY",
    ]
    cursor = connection.execute(
        """
        INSERT INTO printer_paper_decisions (
            token_id, pair_id, token_mint, pair_address, decided_at,
            requested_action_label, final_action_label, decision_gate_label,
            memory_evidence_gate_label, paper_decision_status_label,
            retrieval_query_id, matched_episode_ids_json,
            supporting_memory_match_ids_json, decision_reasons_json,
            blocking_reasons_json, current_context_json,
            memory_evidence_summary_json, decision_report_json, expires_at,
            decision_action, decision_status, source_status, data_quality_label
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target["token_id"],
            target["pair_id"],
            target["token_mint"],
            target["pair_address"],
            decided_at,
            "NO_ACTION",
            "NO_ACTION",
            "DECISION_BLOCKED_NO_CLEAN_MEMORY",
            "MEMORY_GATE_DIRTY_ONLY",
            "PAPER_DECISION_BLOCKED",
            target["retrieval_query_id"],
            json.dumps([], sort_keys=True),
            json.dumps([], sort_keys=True),
            json.dumps(reasons, sort_keys=True),
            json.dumps(blocking, sort_keys=True),
            json.dumps(report.get("Current setup", {}), sort_keys=True),
            json.dumps(
                {
                    "retrieval_result_label": gate_summary["retrieval_query"].get("retrieval_result_label"),
                    "memory_evidence_label": gate_summary["retrieval_query"].get("memory_evidence_label"),
                    "clean_eligible_memory_count": gate_summary["clean_eligible_memory_count"],
                    "dirty_memory_count": gate_summary["dirty_memory_count"],
                    "blocked_dirty_memory_count": gate_summary["blocked_dirty_memory_count"],
                    "dirty_memory_used": False,
                },
                sort_keys=True,
            ),
            json.dumps(report, sort_keys=True),
            decided_at,
            "NO_ACTION",
            "PAPER_DECISION_BLOCKED",
            "PARTIAL",
            "MISSING_CRITICAL_DATA",
        ),
    )
    return int(cursor.lastrowid)


def build_create_paper_decision_once_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_paper_decision_once_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        target = _resolve_paper_decision_target(connection, args)
        gate_summary = _summarize_decision_retrieval_gate(connection, target["retrieval_query_id"])
        report = _build_paper_decision_report(connection, target, gate_summary)
        decision_id = _insert_blocked_paper_decision(connection, target, gate_summary, report)
        connection.commit()
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guarded_tables = [
        "printer_tokens",
        "printer_pairs",
        "printer_source_requests",
        "printer_source_responses",
        "printer_source_failures",
        "printer_token_snapshots",
        *CONTEXT_TABLES,
        *MEMORY_OUTPUT_TABLES,
        "printer_memory_audit_reports",
        "printer_memory_retrieval_queries",
        "printer_memory_retrieval_matches",
        "printer_paper_positions",
        "printer_paper_trade_events",
        "printer_scheduler_jobs",
    ]
    guard_deltas = {table: deltas[table] for table in guarded_tables if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    action_counts = _paper_decision_action_counts(resolved)
    return {
        "command": "printer-create-paper-decision-once",
        "db_path": str(resolved),
        "operator_approved": True,
        "paper_decision_id": decision_id,
        "paper_decision_delta": deltas.get("printer_paper_decisions", 0),
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "decision_report": report,
        "decision_action": "NO_ACTION",
        "paper_decision_status_label": "PAPER_DECISION_BLOCKED",
        "decision_gate_label": "DECISION_BLOCKED_NO_CLEAN_MEMORY",
        "memory_evidence_gate_label": "MEMORY_GATE_DIRTY_ONLY",
        "retrieval_summary": gate_summary,
        "action_counts": action_counts,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def _paper_decision_action_counts(db_path: Path) -> dict[str, int]:
    actions = ["BUY", "WAIT", "AVOID", "NO_ACTION", "SELL", "HOLD"]
    connection = sqlite3.connect(db_path)
    try:
        return {
            action: int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_paper_decisions WHERE COALESCE(final_action_label, decision_action) = ?",
                    (action,),
                ).fetchone()[0]
            )
            for action in actions
        }
    finally:
        connection.close()


def main_create_paper_decision_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Create one paper-only decision after real clean-memory retrieval gates.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--retrieval-query-id", type=int)
    parser.add_argument("--snapshot-id", type=int)
    parser.add_argument("--token-mint")
    parser.add_argument("--token-id", type=int)
    parser.add_argument("--pair-address")
    parser.add_argument("--pair-id", type=int)
    parser.add_argument("--chain", default="solana")
    args = parser.parse_args(argv)
    try:
        payload = build_create_paper_decision_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _validate_simulated_monitor_once_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("simulated paper position monitor requires explicit operator approval")
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("simulated paper position monitor is Solana-only")
    if args.decision_id is None and not (args.token_mint or args.token_id):
        raise ValueError("simulated paper position monitor requires decision_id, token_mint, or token_id")
    if args.decision_id is None and not (args.pair_address or args.pair_id):
        raise ValueError("simulated paper position monitor requires pair_address or pair_id with token input")


def _resolve_monitor_decision(connection: sqlite3.Connection, args: argparse.Namespace) -> dict[str, Any]:
    if args.decision_id is not None:
        decision = _latest_row(connection, "printer_paper_decisions", "WHERE id = ?", (args.decision_id,))
        if not decision:
            raise ValueError("simulated paper position monitor requires an existing paper decision")
    else:
        target = _resolve_approved_snapshot_target(connection, args)
        decision = _latest_row(
            connection,
            "printer_paper_decisions",
            "WHERE token_id = ? AND pair_id = ?",
            (target["token_id"], target["pair_id"]),
        )
        if not decision:
            raise ValueError("simulated paper position monitor requires an existing paper decision")
    token = connection.execute("SELECT * FROM printer_tokens WHERE id = ?", (decision["token_id"],)).fetchone()
    pair = connection.execute("SELECT * FROM printer_pairs WHERE id = ?", (decision["pair_id"],)).fetchone()
    if token is None or pair is None:
        raise ValueError("paper decision must reference an approved token and pair")
    if token["chain"] != "solana":
        raise ValueError("simulated paper position monitor target must be Solana")
    if args.snapshot_id is not None:
        snapshot = connection.execute(
            """
            SELECT *
            FROM printer_token_snapshots
            WHERE id = ? AND token_id = ? AND pair_id = ?
            """,
            (args.snapshot_id, decision["token_id"], decision["pair_id"]),
        ).fetchone()
        if snapshot is None:
            raise ValueError("snapshot_id must belong to the paper decision token/pair")
    return {
        **decision,
        "token_mint": decision.get("token_mint") or token["token_mint"],
        "pair_address": decision.get("pair_address") or pair["pair_address"],
    }


def _paper_decision_report_json(decision: dict[str, Any]) -> dict[str, Any]:
    raw = decision.get("decision_report_json")
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _paper_decision_blocking_reasons(decision: dict[str, Any]) -> list[str]:
    raw = decision.get("blocking_reasons_json")
    if not raw:
        return []
    try:
        values = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(value) for value in values if value]


def _open_paper_position_count(connection: sqlite3.Connection, token_id: int, pair_id: int) -> int:
    return int(
        connection.execute(
            """
            SELECT COUNT(*)
            FROM printer_paper_positions
            WHERE token_id = ?
              AND pair_id = ?
              AND (
                  paper_position_status_label IN ('PAPER_POSITION_OPEN', 'PAPER_POSITION_MONITORING', 'PAPER_POSITION_EXIT_WATCH')
                  OR position_status IN ('PAPER_POSITION_OPEN', 'PAPER_POSITION_MONITORING', 'PAPER_POSITION_EXIT_WATCH', 'OPEN', 'MONITORING')
              )
            """,
            (token_id, pair_id),
        ).fetchone()[0]
    )


def _build_simulated_position_monitor_report(connection: sqlite3.Connection, decision: dict[str, Any]) -> dict[str, Any]:
    report = _paper_decision_report_json(decision)
    decision_action = decision.get("final_action_label") or decision.get("decision_action")
    decision_status = decision.get("paper_decision_status_label") or decision.get("decision_status")
    decision_gate = decision.get("decision_gate_label")
    clean_count = int(report.get("clean_eligible_memory_count") or report.get("Similar clean memories found") or 0)
    dirty_memory_used = bool(report.get("dirty_memory_used"))
    paper_position_allowed = bool(report.get("paper_position_allowed"))
    existing_open_count = _open_paper_position_count(connection, int(decision["token_id"]), int(decision["pair_id"]))
    blocking_reasons = _paper_decision_blocking_reasons(decision)
    buy_allowed = decision_action == "BUY" and decision_status == "DECISION_ALLOWED" and decision_gate == "DECISION_ALLOWED"
    buy_unlocked = buy_allowed and clean_count > 0 and not dirty_memory_used
    position_allowed = buy_unlocked and paper_position_allowed and existing_open_count == 0
    blocked_reasons: list[str] = []
    if decision_action != "BUY":
        blocked_reasons.append("BLOCKED_DECISION_NOT_BUY")
    if decision_status != "DECISION_ALLOWED" or decision_gate != "DECISION_ALLOWED":
        blocked_reasons.append("BLOCKED_DECISION_NOT_ALLOWED")
    if clean_count <= 0:
        blocked_reasons.append("BLOCKED_NO_CLEAN_MEMORY")
    if not paper_position_allowed:
        blocked_reasons.append("BLOCKED_PAPER_POSITION_NOT_ALLOWED")
    if dirty_memory_used:
        blocked_reasons.append("BLOCKED_DIRTY_MEMORY_USED")
    if existing_open_count > 0:
        blocked_reasons.append("BLOCKED_EXISTING_OPEN_POSITION")
    monitor_action = "POSITION_ALLOWED" if position_allowed else "POSITION_BLOCKED"
    return {
        "monitor_action": monitor_action,
        "decision_id": int(decision["id"]),
        "decision_action": decision_action,
        "decision_status": decision_status,
        "decision_gate_label": decision_gate,
        "decision_blocked_reason": blocking_reasons,
        "buy_allowed": buy_allowed,
        "buy_unlocked": buy_unlocked,
        "clean_eligible_memory_count": clean_count,
        "dirty_memory_used": dirty_memory_used,
        "paper_position_allowed": paper_position_allowed,
        "existing_open_position_count": existing_open_count,
        "position_opened": False,
        "position_id": None,
        "blocked_reason": blocked_reasons,
        "paper_trade_event_created": False,
        "simulated_pnl_created": False,
        "runtime_started": False,
        "scheduler_executed": False,
        "report_mode": "OUTPUT_ONLY_BLOCKED_MONITOR" if not position_allowed else "OUTPUT_ONLY_POSITION_GATE_PASSED",
    }


def build_monitor_simulated_paper_position_once_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_simulated_monitor_once_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    try:
        decision = _resolve_monitor_decision(connection, args)
        monitor_report = _build_simulated_position_monitor_report(connection, decision)
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guarded_tables = [
        "printer_tokens",
        "printer_pairs",
        "printer_source_requests",
        "printer_source_responses",
        "printer_source_failures",
        "printer_token_snapshots",
        *CONTEXT_TABLES,
        *MEMORY_OUTPUT_TABLES,
        "printer_memory_audit_reports",
        "printer_memory_retrieval_queries",
        "printer_memory_retrieval_matches",
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_paper_trade_events",
        "printer_paper_trade_audits",
        "printer_paper_audit_reports",
        "printer_scheduler_jobs",
    ]
    guard_deltas = {table: deltas[table] for table in guarded_tables if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    action_counts = _paper_decision_action_counts(resolved)
    return {
        "command": "printer-monitor-simulated-paper-position-once",
        "db_path": str(resolved),
        "operator_approved": True,
        "monitor_attempt_recorded": False,
        "monitor_attempt_rows": 0,
        "monitor_report": monitor_report,
        "monitor_action": monitor_report["monitor_action"],
        "monitor_blocked_reason": monitor_report["blocked_reason"],
        "position_opened": monitor_report["position_opened"],
        "position_id": monitor_report["position_id"],
        "paper_trade_event_created": monitor_report["paper_trade_event_created"],
        "simulated_pnl_created": monitor_report["simulated_pnl_created"],
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "action_counts": action_counts,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_monitor_simulated_paper_position_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Check one paper decision for simulated paper position eligibility.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--decision-id", type=int)
    parser.add_argument("--snapshot-id", type=int)
    parser.add_argument("--token-mint")
    parser.add_argument("--token-id", type=int)
    parser.add_argument("--pair-address")
    parser.add_argument("--pair-id", type=int)
    parser.add_argument("--chain", default="solana")
    args = parser.parse_args(argv)
    try:
        payload = build_monitor_simulated_paper_position_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def classify_readiness(status: dict[str, Any], migration_status: dict[str, Any], source_scan: dict[str, Any], runtime_scan: dict[str, Any]) -> str:
    if status["state_classification"] == STATE_NO_DB:
        return READINESS_NEEDS_DB_INIT
    if status.get("runtime_has_started"):
        return READINESS_BLOCKED
    if migration_status.get("missing_migrations"):
        return READINESS_BLOCKED
    if source_scan.get("validation_result_label") != "VALIDATION_PASS":
        return READINESS_BLOCKED
    if runtime_scan.get("validation_result_label") != "VALIDATION_PASS":
        return READINESS_BLOCKED
    if status["state_classification"] == STATE_SCHEMA_ONLY:
        return READINESS_READY_SCHEMA_ONLY
    if status["state_classification"] == STATE_SOURCE_ONLY_SMOKE_CHECK:
        return READINESS_READY_SOURCE_ONLY_SMOKE_CHECK
    if status["state_classification"] == STATE_CONTROLLED_INTAKE:
        return READINESS_READY_CONTROLLED_INTAKE
    if status["state_classification"] == STATE_CONTROLLED_SNAPSHOTS:
        return READINESS_READY_CONTROLLED_SNAPSHOTS
    if status["state_classification"] == STATE_CONTROLLED_CONTEXT:
        return READINESS_READY_CONTROLLED_CONTEXT
    if status["state_classification"] == STATE_FIRST_MEMORY_WINDOW:
        return READINESS_READY_FIRST_MEMORY_WINDOW
    if status["state_classification"] == STATE_MEMORY_QUALITY_AUDITED:
        return READINESS_READY_MEMORY_QUALITY_AUDITED
    if status["state_classification"] == STATE_REAL_MEMORY_RETRIEVAL:
        return READINESS_READY_REAL_MEMORY_RETRIEVAL
    if status["state_classification"] == STATE_REAL_DATA_PAPER_DECISION:
        return READINESS_READY_REAL_DATA_PAPER_DECISION
    if status["state_classification"] in {STATE_TOKEN_ROWS, STATE_TEST_ONLY, STATE_MEMORY_ROWS, STATE_PAPER_ROWS}:
        return READINESS_READY_WITH_LOCAL_DATA
    return READINESS_STATE_UNKNOWN


def build_readiness_check_payload(args: argparse.Namespace) -> dict[str, Any]:
    project_root = _project_root(args.project_root)
    status = get_operator_db_status(args.db_path, project_root)
    migration_status = build_migration_status(args.db_path, project_root)
    counts = get_core_table_counts(args.db_path, project_root)
    scan_root = project_root or Path(__file__).resolve().parents[3]
    source_scan = check_no_live_capability_terms_in_source(scan_root)
    runtime_scan = check_no_runtime_loop_terms_in_source(scan_root)
    readiness = classify_readiness(status, migration_status, source_scan, runtime_scan)
    return {
        "command": "printer-readiness-check",
        "readiness_label": readiness,
        "db_path": status["db_path"],
        "db_state_classification": status["state_classification"],
        "latest_migration": migration_status["latest_migration"],
        "missing_migrations": migration_status["missing_migrations"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
        "counts": counts,
        "source_scan_result": source_scan["validation_result_label"],
        "runtime_scan_result": runtime_scan["validation_result_label"],
    }


def main_readiness_check(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Run a local read-only operator readiness check.")
    args = parser.parse_args(argv)
    try:
        payload = build_readiness_check_payload(args)
        if args.format == "json":
            print(format_json_output(payload))
        else:
            print(format_readiness_summary(payload))
        return 0
    except Exception as exc:
        return _print_error(exc)
