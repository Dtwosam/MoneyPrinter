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
    STATE_MEMORY_ROWS,
    STATE_NO_DB,
    STATE_PAPER_ROWS,
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


READINESS_NEEDS_DB_INIT = "NEEDS_DB_INIT"
READINESS_READY_SCHEMA_ONLY = "READY_SCHEMA_ONLY"
READINESS_READY_SOURCE_ONLY_SMOKE_CHECK = "READY_SOURCE_ONLY_SMOKE_CHECK"
READINESS_READY_CONTROLLED_INTAKE = "READY_CONTROLLED_INTAKE"
READINESS_READY_CONTROLLED_SNAPSHOTS = "READY_CONTROLLED_SNAPSHOTS"
READINESS_READY_CONTROLLED_CONTEXT = "READY_CONTROLLED_CONTEXT"
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
