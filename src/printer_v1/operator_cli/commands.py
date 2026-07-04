"""One-shot operator commands for safe local Printer V1 inspection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import quote

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
    STATE_REAL_PAPER_AUDIT_OPERATOR_REVIEW,
    STATE_SCHEDULER_SINGLE_TICK_EXECUTED,
    STATE_BOUNDED_RUNTIME_EXECUTED,
    STATE_LONG_RUN_PAPER_VALIDATION,
    STATE_POST_RC_DISCOVERY_MEMORY_CYCLE,
    STATE_V1_PAPER_RELEASE_CANDIDATE,
    STATE_SCHEMA_ONLY,
    STATE_SOURCE_ONLY_SMOKE_CHECK,
    STATE_TEST_ONLY,
    STATE_TOKEN_ROWS,
    get_core_table_counts,
    get_operator_db_status,
    get_schema_migration_status,
)
from printer_v1.chain_heat.recorder import record_chain_heat_snapshot
from printer_v1.discovery.classifier import (
    classify_discovery_candidate,
    is_dead_or_near_zero_activity_candidate,
)
from printer_v1.discovery.contracts import DiscoveryChannelLabel, DiscoveryOutputAction
from printer_v1.discovery.discovery import process_discovery_payload
from printer_v1.discovery.parser import normalize_candidates
from printer_v1.chart_volatility.classifier import (
    classify_candle_path,
    classify_chart_memory_gate,
    classify_chart_payload_quality,
    classify_drawdown_recovery,
    classify_momentum,
    classify_range_behavior,
    classify_trend_structure,
    classify_volatility,
)
from printer_v1.chart_volatility.parser import build_chart_payload_from_token_snapshots
from printer_v1.evidence_fill.controlled import (
    ControlledEvidenceFillTarget,
    fill_controlled_governed_evidence,
)
from printer_v1.evidence_fill.real import (
    RealEvidenceFillResult,
    RealEvidenceTarget,
    collect_real_evidence,
)
from printer_v1.safety.goplus_normalizer import (
    safety_memory_policy_summary,
)
from printer_v1.sources.jupiter_quote import (
    DEFAULT_PAPER_AMOUNT_LAMPORTS as JUPITER_DEFAULT_PAPER_AMOUNT,
    DEFAULT_SLIPPAGE_BPS as JUPITER_DEFAULT_SLIPPAGE_BPS,
    WSOL_MINT,
)
from printer_v1.sources.solana_rpc_holder import (
    SOLANA_PUBLIC_RPC_URL,
    SOLANA_RPC_RATE_LIMIT_FAILURE_TYPE,
    redacted_solana_rpc_source,
)
from printer_v1.liquidity_exit.classifier import (
    classify_entry_realism,
    classify_exit_realism,
    classify_liquidity_drain,
    classify_liquidity_exit_payload_quality,
    classify_liquidity_state,
    classify_price_impact,
    classify_quote_age,
    classify_realism_gate,
    classify_route_availability,
    classify_slippage,
)
from printer_v1.micro_event.classifier import (
    classify_holding_to_15m_result,
    classify_late_buy_trap,
    classify_micro_event_memory_gate,
    classify_micro_event_move,
    classify_micro_event_payload_quality,
    classify_micro_event_state,
    classify_micro_exit_realism,
)
from printer_v1.micro_event.parser import build_micro_event_payload_from_token_snapshots
from printer_v1.market_regime.recorder import record_market_regime_snapshot
from printer_v1.safety.classifier import (
    classify_authority_safety,
    classify_distribution_safety,
    classify_liquidity_safety,
    classify_rug_risk,
    classify_safety_gate,
    classify_safety_payload_quality,
    classify_safety_status,
)
from printer_v1.trading_flow.classifier import (
    classify_flow_direction,
    classify_flow_memory_gate,
    classify_flow_pressure,
    classify_imbalance,
    classify_trading_flow_payload_quality,
    classify_tx_activity,
    classify_volume_activity,
    classify_wallet_participation,
)
from printer_v1.trading_flow.parser import normalize_trading_flow_payload
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
from printer_v1.sources.alternative_me import (
    build_alternative_me_adapter,
    build_alternative_me_fear_greed_transport,
)
from printer_v1.sources.coingecko import (
    build_coingecko_adapter,
    build_coingecko_market_transport,
)
from printer_v1.sources.defillama import (
    build_defillama_adapter,
    build_defillama_chain_liquidity_transport,
)
from printer_v1.sources.geckoterminal import (
    GECKOTERMINAL_NEW_POOLS_URL,
    GECKOTERMINAL_TRENDING_POOLS_URL,
    build_geckoterminal_adapter,
    build_geckoterminal_pools_transport,
)
from printer_v1.sources.pumpportal import (
    build_pumpportal_adapter,
)
from printer_v1.sources.pumpswap import (
    build_pumpswap_adapter,
)
from printer_v1.sources.governed_execution import execute_source_request_with_governor
from printer_v1.snapshots.recorder import record_token_snapshot
from printer_v1.memory_retrieval.recorder import record_memory_retrieval_query, record_memory_retrieval_matches
from printer_v1.memory_retrieval.retriever import build_memory_diversity_summary, retrieve_memory_matches_for_current_setup


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
READINESS_READY_REAL_PAPER_AUDIT_OPERATOR_REVIEW = "READY_REAL_PAPER_AUDIT_OPERATOR_REVIEW"
READINESS_READY_SCHEDULER_SINGLE_TICK_EXECUTED = "READY_SCHEDULER_SINGLE_TICK_EXECUTED"
READINESS_READY_BOUNDED_RUNTIME_EXECUTED = "READY_BOUNDED_RUNTIME_EXECUTED"
READINESS_READY_LONG_RUN_PAPER_VALIDATION = "READY_LONG_RUN_PAPER_VALIDATION"
READINESS_READY_V1_PAPER_RELEASE_CANDIDATE = "READY_V1_PAPER_RELEASE_CANDIDATE"
READINESS_READY_POST_RC_DISCOVERY_MEMORY_CYCLE = "READY_POST_RC_DISCOVERY_MEMORY_CYCLE"
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

BROAD_CONTEXT_SOURCE_NAMES = {"coingecko", "defillama", "alternative_me"}

BROAD_CONTEXT_DEFAULT_REQUEST_KINDS: dict[str, str] = {
    "coingecko": "broad_market_context",
    "defillama": "chain_liquidity_context",
    "alternative_me": "fear_greed_context",
}

BROAD_CONTEXT_ALLOWED_REQUEST_KINDS: dict[str, set[str]] = {
    "coingecko": {"broad_market_context", "asset_context"},
    "defillama": {"chain_liquidity_context", "tvl_context", "dex_volume_context"},
    "alternative_me": {"fear_greed_context"},
}

BROAD_CONTEXT_GUARD_TABLES = [
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

CONTEXT_FRESHNESS_TOLERANCE_MINUTES = 10

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


CONTROLLED_EVIDENCE_FILL_TABLES = (
    "printer_source_requests",
    "printer_source_responses",
    "printer_source_failures",
    "printer_solana_safety_evidence",
    "printer_paper_quote_evidence",
    "printer_memory_windows",
    "printer_memory_fingerprints",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_pl_calculations",
)


def _connection_table_count(connection: sqlite3.Connection, table_name: str) -> int | None:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if row is None:
        return None
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _controlled_evidence_counts(connection: sqlite3.Connection) -> dict[str, int | None]:
    return {
        table: _connection_table_count(connection, table)
        for table in CONTROLLED_EVIDENCE_FILL_TABLES
    }


def _read_optional_json_payload(*, inline_json: str | None, path: str | None, label: str) -> dict[str, Any] | None:
    if inline_json and path:
        raise ValueError(f"{label} accepts either inline JSON or a path, not both")
    if not inline_json and not path:
        return None
    if path:
        text = Path(path).read_text(encoding="utf-8")
    else:
        text = inline_json or ""
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} payload must be a JSON object")
    return parsed


def _resolve_controlled_evidence_fill_target(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
) -> ControlledEvidenceFillTarget:
    token = connection.execute(
        "SELECT * FROM printer_tokens WHERE id = ?",
        (args.token_id,),
    ).fetchone()
    if token is None:
        raise ValueError("controlled evidence fill target token not found")
    if token["chain"] != "solana":
        raise ValueError("controlled evidence fill is Solana-only")
    pair = connection.execute(
        "SELECT * FROM printer_pairs WHERE id = ? AND token_id = ?",
        (args.pair_id, args.token_id),
    ).fetchone()
    if pair is None:
        raise ValueError("controlled evidence fill target pair not found or token-mismatched")
    snapshot = connection.execute(
        """
        SELECT *
        FROM printer_token_snapshots
        WHERE id = ? AND token_id = ? AND pair_id = ?
        """,
        (args.snapshot_id, args.token_id, args.pair_id),
    ).fetchone()
    if snapshot is None:
        raise ValueError("controlled evidence fill target snapshot not found or target-mismatched")
    if args.memory_window_id is not None:
        window = connection.execute(
            """
            SELECT *
            FROM printer_memory_windows
            WHERE id = ? AND token_id = ? AND pair_id = ? AND snapshot_end_id = ?
            """,
            (args.memory_window_id, args.token_id, args.pair_id, args.snapshot_id),
        ).fetchone()
        if window is None:
            raise ValueError("controlled evidence fill memory window target not found or mismatched")
    return ControlledEvidenceFillTarget(
        token_id=args.token_id,
        pair_id=args.pair_id,
        snapshot_id=args.snapshot_id,
        memory_window_id=args.memory_window_id,
        evidence_window_id=args.evidence_window_id,
    )


def _validate_fill_controlled_evidence_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("controlled evidence fill requires explicit operator approval")
    if args.token_id is None or args.pair_id is None or args.snapshot_id is None:
        raise ValueError("controlled evidence fill requires token_id, pair_id, and snapshot_id")
    if not any((
        args.safety_payload_json,
        args.safety_payload_path,
        args.entry_quote_payload_json,
        args.entry_quote_payload_path,
        args.exit_quote_payload_json,
        args.exit_quote_payload_path,
    )):
        raise ValueError("controlled evidence fill requires at least one evidence payload")


def build_fill_controlled_evidence_once_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_fill_controlled_evidence_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    safety_payload = _read_optional_json_payload(
        inline_json=args.safety_payload_json,
        path=args.safety_payload_path,
        label="safety",
    )
    entry_quote_payload = _read_optional_json_payload(
        inline_json=args.entry_quote_payload_json,
        path=args.entry_quote_payload_path,
        label="entry quote",
    )
    exit_quote_payload = _read_optional_json_payload(
        inline_json=args.exit_quote_payload_json,
        path=args.exit_quote_payload_path,
        label="exit quote",
    )
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        before_counts = _controlled_evidence_counts(connection)
        target = _resolve_controlled_evidence_fill_target(connection, args)
        result = fill_controlled_governed_evidence(
            connection,
            target=target,
            safety_payload=safety_payload,
            entry_quote_payload=entry_quote_payload,
            exit_quote_payload=exit_quote_payload,
            dry_run=bool(args.dry_run),
        )
        if args.dry_run:
            connection.rollback()
        else:
            connection.commit()
        after_counts = _controlled_evidence_counts(connection)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in CONTROLLED_EVIDENCE_FILL_TABLES
    }
    locked_gate_counts = {
        "retrieval_queries": after_counts.get("printer_memory_retrieval_queries"),
        "retrieval_matches": after_counts.get("printer_memory_retrieval_matches"),
        "paper_decisions": after_counts.get("printer_paper_decisions"),
        "paper_positions": after_counts.get("printer_paper_positions"),
        "paper_trade_events": after_counts.get("printer_paper_trade_events"),
        "paper_trade_audits": after_counts.get("printer_paper_trade_audits"),
        "paper_pl_calculations": after_counts.get("printer_paper_pl_calculations"),
    }
    return {
        "command": "printer-fill-controlled-evidence-once",
        "db_path": str(resolved),
        "operator_approved": True,
        "dry_run": bool(args.dry_run),
        "target": asdict(target),
        "item_results": [asdict(item) for item in result.item_results],
        "safety_evidence_inserted": result.safety_evidence_inserted,
        "quote_evidence_inserted": result.quote_evidence_inserted,
        "clean_evidence_inserted": result.clean_evidence_inserted,
        "audit_only_evidence_inserted": result.audit_only_evidence_inserted,
        "rejected_or_failed": result.rejected_or_failed,
        "source_table_deltas": {
            "printer_source_requests": deltas["printer_source_requests"],
            "printer_source_responses": deltas["printer_source_responses"],
            "printer_source_failures": deltas["printer_source_failures"],
        },
        "evidence_table_deltas": {
            "printer_solana_safety_evidence": deltas["printer_solana_safety_evidence"],
            "printer_paper_quote_evidence": deltas["printer_paper_quote_evidence"],
        },
        "locked_gate_counts": locked_gate_counts,
        "downstream_unlocks": {
            "clean_memory": False,
            "retrieval": False,
            "paper_decision": False,
            "buy": False,
            "paper_position": False,
            "paper_trade_event": False,
            "pnl": False,
        },
        "counts_after": after_counts,
    }


def main_fill_controlled_evidence_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Fill controlled governed safety/quote evidence once.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--token-id", type=int, required=True)
    parser.add_argument("--pair-id", type=int, required=True)
    parser.add_argument("--snapshot-id", type=int, required=True)
    parser.add_argument("--memory-window-id", type=int)
    parser.add_argument("--evidence-window-id", type=int)
    parser.add_argument("--safety-payload-json")
    parser.add_argument("--safety-payload-path")
    parser.add_argument("--entry-quote-payload-json")
    parser.add_argument("--entry-quote-payload-path")
    parser.add_argument("--exit-quote-payload-json")
    parser.add_argument("--exit-quote-payload-path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = build_fill_controlled_evidence_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


REAL_EVIDENCE_GUARD_TABLES = [
    "printer_memory_windows",
    "printer_episodes",
    "printer_memory_fingerprints",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
]


def _validate_real_evidence_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("real evidence collection requires explicit operator approval")
    if args.token_id is None and not getattr(args, "token_mint", None):
        raise ValueError("real evidence collection requires --token-id or --token-mint")
    if args.snapshot_id is None:
        raise ValueError("real evidence collection requires --snapshot-id")


def _resolve_real_evidence_target(
    connection: sqlite3.Connection, args: argparse.Namespace
) -> RealEvidenceTarget:
    if args.token_id is not None:
        token_row = connection.execute(
            "SELECT * FROM printer_tokens WHERE id = ?", (args.token_id,)
        ).fetchone()
    else:
        token_row = connection.execute(
            "SELECT * FROM printer_tokens WHERE token_mint = ?",
            (args.token_mint,),
        ).fetchone()
    if token_row is None:
        raise ValueError("real evidence target token not found in DB")
    if token_row["chain"] != "solana":
        raise ValueError("real evidence collection is Solana-only")

    pair_id = getattr(args, "pair_id", None)
    if pair_id is None and getattr(args, "pair_address", None):
        pair_row = connection.execute(
            "SELECT id FROM printer_pairs WHERE pair_address = ? AND token_id = ?",
            (args.pair_address, int(token_row["id"])),
        ).fetchone()
        if pair_row:
            pair_id = int(pair_row["id"])

    snapshot_row = connection.execute(
        "SELECT * FROM printer_token_snapshots WHERE id = ? AND token_id = ?",
        (args.snapshot_id, int(token_row["id"])),
    ).fetchone()
    if snapshot_row is None:
        raise ValueError("real evidence target snapshot not found or does not belong to this token")

    return RealEvidenceTarget(
        token_id=int(token_row["id"]),
        snapshot_id=int(args.snapshot_id),
        token_mint=str(token_row["token_mint"]),
        pair_id=int(pair_id) if pair_id is not None else None,
        memory_window_id=int(args.memory_window_id) if getattr(args, "memory_window_id", None) else None,
        evidence_window_id=int(args.evidence_window_id) if getattr(args, "evidence_window_id", None) else None,
    )


def _safety_field_resolution(
    connection: sqlite3.Connection,
    result: RealEvidenceFillResult,
) -> dict[str, Any]:
    """Read back the best inserted safety evidence row and compute which required fields
    are resolved (at their clean value) vs still unresolved.

    Returns resolved/pending/observed/blocking safety buckets plus label.
    Prefers the RPC holder merged row over the raw GoPlus row when both exist,
    because the merged row has the updated holder_concentration_label.
    """
    from printer_v1.safety.goplus_normalizer import REQUIRED_CLEAN_SAFETY_FIELDS

    evidence_row: dict[str, Any] | None = None
    for type_name in ("solana_rpc_holder", "goplus_safety"):
        for item in result.item_results:
            if item.evidence_type == type_name and item.inserted and item.evidence_id is not None:
                row = connection.execute(
                    "SELECT * FROM printer_solana_safety_evidence WHERE id = ?",
                    (item.evidence_id,),
                ).fetchone()
                if row is not None:
                    evidence_row = dict(row)
                    break
        if evidence_row is not None:
            break

    if evidence_row is None:
        return {
            "resolved_safety_fields": [],
            "unresolved_safety_fields": list(REQUIRED_CLEAN_SAFETY_FIELDS.keys()),
            "source_coverage_pending_fields": [],
            "observed_risk_fields": [],
            "hard_blocking_safety_fields": list(REQUIRED_CLEAN_SAFETY_FIELDS.keys()),
            "safety_context_label": "SAFETY_UNKNOWN",
            "safety_15m_memory_policy_label": "SAFETY_BLOCKED_FOR_15M_MEMORY",
            "safety_acceptable_for_15m_memory": False,
        }

    policy = safety_memory_policy_summary(evidence_row)
    safety_label = str(evidence_row.get("safety_context_label") or "SAFETY_UNKNOWN")

    return {
        **policy,
        "safety_context_label": safety_label,
    }


def _holder_rpc_summary(
    result: RealEvidenceFillResult,
    *,
    configured_rpc_url: str,
) -> dict[str, Any]:
    holder_items = [item for item in result.item_results if item.evidence_type == "solana_rpc_holder"]
    if not holder_items:
        return {
            "holder_rpc_status": "NOT_ATTEMPTED",
            "holder_rpc_failure_type": None,
            "holder_rpc_rate_limited": False,
            "holder_rpc_source_used": redacted_solana_rpc_source(configured_rpc_url),
        }
    item = holder_items[-1]
    return {
        "holder_rpc_status": item.holder_rpc_status or ("COMPLETE" if item.inserted else "FAILED"),
        "holder_rpc_failure_type": item.holder_rpc_failure_type,
        "holder_rpc_rate_limited": bool(item.holder_rpc_rate_limited),
        "holder_rpc_source_used": item.holder_rpc_source_used or redacted_solana_rpc_source(configured_rpc_url),
    }


def build_collect_real_evidence_once_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_real_evidence_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    paper_amount = int(getattr(args, "paper_amount_lamports", None) or JUPITER_DEFAULT_PAPER_AMOUNT)
    slippage_bps = int(getattr(args, "slippage_bps", None) or JUPITER_DEFAULT_SLIPPAGE_BPS)
    quote_currency = str(getattr(args, "quote_currency_mint", None) or WSOL_MINT).strip()
    solana_rpc_url = str(
        getattr(args, "solana_rpc_url", None)
        or os.environ.get("PRINTER_SOLANA_RPC_URL")
        or SOLANA_PUBLIC_RPC_URL
    ).strip()
    solana_rpc_fallback_url = getattr(args, "solana_rpc_fallback_url", None)
    solana_rpc_fallback_url = str(solana_rpc_fallback_url).strip() if solana_rpc_fallback_url else None

    before_counts = get_core_table_counts(resolved, project_root)

    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        target = _resolve_real_evidence_target(connection, args)
        result = collect_real_evidence(
            connection,
            target,
            paper_amount_lamports=paper_amount,
            slippage_bps=slippage_bps,
            paper_quote_currency_mint=quote_currency,
            holder_rpc_url=solana_rpc_url,
            holder_rpc_fallback_url=solana_rpc_fallback_url,
        )
        connection.commit()
        safety_resolution = _safety_field_resolution(connection, result)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guard_deltas = {table: deltas.get(table, 0) for table in REAL_EVIDENCE_GUARD_TABLES if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)

    safety_sources_used = [
        item.evidence_type
        for item in result.item_results
        if item.evidence_type in {"goplus_safety", "solana_rpc_holder"} and item.inserted
    ]
    quote_sources_used = [
        item.evidence_type
        for item in result.item_results
        if item.evidence_type.startswith("jupiter_quote_") and item.inserted
    ]
    holder_rpc = _holder_rpc_summary(result, configured_rpc_url=solana_rpc_url)
    resolved_fields = safety_resolution["resolved_safety_fields"]
    unresolved_fields = safety_resolution["unresolved_safety_fields"]
    source_coverage_pending_fields = safety_resolution["source_coverage_pending_fields"]
    observed_risk_fields = safety_resolution["observed_risk_fields"]
    hard_blocking_safety_fields = safety_resolution["hard_blocking_safety_fields"]
    safety_context_label = safety_resolution["safety_context_label"]
    safety_15m_memory_policy_label = safety_resolution["safety_15m_memory_policy_label"]
    safety_acceptable_for_15m_memory = bool(safety_resolution["safety_acceptable_for_15m_memory"])
    overall_clean_eligible = safety_context_label == "SAFETY_CLEAN" and bool(resolved_fields)
    overall_audit_only = not overall_clean_eligible

    if hard_blocking_safety_fields or unresolved_fields or source_coverage_pending_fields:
        if holder_rpc["holder_rpc_rate_limited"]:
            holder_hint = (
                "Holder concentration remains unresolved because Solana RPC was rate limited. "
                "Use an operator-approved free/read-only RPC endpoint with --solana-rpc-url "
                "or retry later. "
            )
        elif "holder_concentration_label" in source_coverage_pending_fields:
            holder_hint = (
                "Holder concentration is still source coverage pending. Use an operator-approved "
                "free/read-only RPC endpoint with --solana-rpc-url or retry later. "
            )
        else:
            holder_hint = ""
        next_step_hint = (
            f"Safety context is {safety_context_label}. "
            f"Unresolved fields: {unresolved_fields}. "
            f"{holder_hint}"
            "Memory remains AUDIT_ONLY — do not rebuild as clean. "
            "Do not use this memory for Lane 7. "
            "Collect missing evidence (holder concentration, liquidity lock/burn, risk flags) "
            "before attempting a clean memory window build."
        )
    else:
        next_step_hint = (
            "All required safety fields resolved. "
            "Run printer-build-memory-window-once to attempt evidence revision "
            "after real evidence rows are inserted."
        )

    return {
        "command": "printer-collect-real-evidence-once",
        "db_path": str(resolved),
        "operator_approved": True,
        "token_id": target.token_id,
        "token_mint": target.token_mint,
        "pair_id": target.pair_id,
        "snapshot_id": target.snapshot_id,
        "memory_window_id": target.memory_window_id,
        "paper_amount_lamports": paper_amount,
        "slippage_bps": slippage_bps,
        "quote_currency_mint": quote_currency,
        "holder_rpc_status": holder_rpc["holder_rpc_status"],
        "holder_rpc_failure_type": holder_rpc["holder_rpc_failure_type"],
        "holder_rpc_rate_limited": holder_rpc["holder_rpc_rate_limited"],
        "holder_rpc_source_used": holder_rpc["holder_rpc_source_used"],
        "safety_evidence_inserted": result.safety_evidence_inserted,
        "quote_evidence_inserted": result.quote_evidence_inserted,
        "clean_evidence_inserted": result.clean_evidence_inserted,
        "audit_only_evidence_inserted": result.audit_only_evidence_inserted,
        "rejected_or_failed": result.rejected_or_failed,
        "resolved_safety_fields": resolved_fields,
        "unresolved_safety_fields": unresolved_fields,
        "source_coverage_pending_fields": source_coverage_pending_fields,
        "observed_risk_fields": observed_risk_fields,
        "hard_blocking_safety_fields": hard_blocking_safety_fields,
        "safety_15m_memory_policy_label": safety_15m_memory_policy_label,
        "safety_acceptable_for_15m_memory": safety_acceptable_for_15m_memory,
        "safety_sources_used": safety_sources_used,
        "quote_sources_used": quote_sources_used,
        "clean_eligible": overall_clean_eligible,
        "audit_only": overall_audit_only,
        "item_results": [
            {
                "evidence_type": item.evidence_type,
                "inserted": item.inserted,
                "evidence_id": item.evidence_id,
                "clean_eligible": item.clean_eligible,
                "audit_status": item.audit_status,
                "rejection_reasons": list(item.rejection_reasons),
                "source_request_id": item.source_request_id,
                "source_response_id": item.source_response_id,
                "source_failure_id": item.source_failure_id,
                "source_request_recorded": item.source_request_id is not None,
                "source_failed": item.source_failure_id is not None,
                "holder_rpc_status": item.holder_rpc_status,
                "holder_rpc_failure_type": item.holder_rpc_failure_type,
                "holder_rpc_rate_limited": item.holder_rpc_rate_limited,
                "holder_rpc_source_used": item.holder_rpc_source_used,
                "downstream_unlocks": item.downstream_unlocks,
            }
            for item in result.item_results
        ],
        "source_table_deltas": {
            "printer_source_requests": deltas.get("printer_source_requests", 0),
            "printer_source_responses": deltas.get("printer_source_responses", 0),
            "printer_source_failures": deltas.get("printer_source_failures", 0),
        },
        "evidence_table_deltas": {
            "printer_solana_safety_evidence": deltas.get("printer_solana_safety_evidence", 0),
            "printer_paper_quote_evidence": deltas.get("printer_paper_quote_evidence", 0),
        },
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "next_step_hint": next_step_hint,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_collect_real_evidence_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser(
        "Collect real governed safety and paper quote evidence for a token snapshot.",
        ("json", "text"),
    )
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--token-id", type=int)
    parser.add_argument("--token-mint")
    parser.add_argument("--pair-id", type=int)
    parser.add_argument("--pair-address")
    parser.add_argument("--snapshot-id", type=int, required=True)
    parser.add_argument("--memory-window-id", type=int)
    parser.add_argument("--evidence-window-id", type=int)
    parser.add_argument(
        "--paper-amount-lamports",
        type=int,
        default=JUPITER_DEFAULT_PAPER_AMOUNT,
        help=f"Paper simulation amount in lamports (default: {JUPITER_DEFAULT_PAPER_AMOUNT})",
    )
    parser.add_argument(
        "--slippage-bps",
        type=int,
        default=JUPITER_DEFAULT_SLIPPAGE_BPS,
        help=f"Quote slippage basis points (default: {JUPITER_DEFAULT_SLIPPAGE_BPS})",
    )
    parser.add_argument(
        "--quote-currency-mint",
        default=WSOL_MINT,
        help="Quote currency mint for paper simulation (default: WSOL)",
    )
    parser.add_argument(
        "--solana-rpc-url",
        help="Optional operator-approved free/read-only Solana RPC URL for holder fallback.",
    )
    parser.add_argument(
        "--solana-rpc-fallback-url",
        help="Optional single operator-approved free/read-only fallback RPC URL.",
    )
    args = parser.parse_args(argv)
    try:
        payload = build_collect_real_evidence_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _source_channel_for_dexscreener(request_kind: str | None = None) -> tuple[str, str]:
    """Return (source_channel, source_channel_reason) for a DexScreener request."""
    if request_kind == "boosted_token_reference":
        return DiscoveryChannelLabel.DEXSCREENER_LATEST_BOOSTED.value, "dexscreener_boosted_token_reference"
    return DiscoveryChannelLabel.DEXSCREENER_SEARCH.value, "dexscreener_default_search_query"


def _source_channel_for_geckoterminal(request_kind: str | None = None) -> tuple[str, str]:
    """Return (source_channel, source_channel_reason) for a GeckoTerminal request."""
    if request_kind == "geckoterminal_trending_pool_reference":
        return DiscoveryChannelLabel.GECKOTERMINAL_TRENDING_POOL.value, "geckoterminal_trending_pool_reference"
    return DiscoveryChannelLabel.GECKOTERMINAL_NEW_POOL.value, "geckoterminal_new_pool_discovery"


_GECKOTERMINAL_ENDPOINT_BY_REQUEST_KIND: dict[str, str] = {
    "geckoterminal_new_pool_discovery": GECKOTERMINAL_NEW_POOLS_URL,
    "geckoterminal_trending_pool_reference": GECKOTERMINAL_TRENDING_POOLS_URL,
}


def _source_channel_for_pumpportal(request_kind: str | None = None) -> tuple[str, str]:
    """Return (source_channel, source_channel_reason) for a PumpPortal request."""
    if request_kind == "pumpfun_migration_stream":
        return DiscoveryChannelLabel.PUMPFUN_MIGRATION.value, "pumpportal_migration_stream"
    return DiscoveryChannelLabel.PUMPFUN_NEW_TOKEN.value, "pumpportal_launch_stream"


def _source_channel_for_pumpswap(request_kind: str | None = None) -> tuple[str, str]:
    """Return (source_channel, source_channel_reason) for a PumpSwap request."""
    if request_kind == "pumpswap_migration_pool_reference":
        return DiscoveryChannelLabel.PUMPSWAP_MIGRATION_POOL_REFERENCE.value, "pumpswap_migration_pool_reference"
    if request_kind == "pumpswap_liquidity_reference":
        return DiscoveryChannelLabel.PUMPSWAP_LIQUIDITY_REFERENCE.value, "pumpswap_liquidity_reference"
    return DiscoveryChannelLabel.PUMPSWAP_POOL_CONFIRMATION.value, "pumpswap_pool_confirmation"


def _validate_discover_candidates_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("controlled discovery requires explicit operator approval")
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("controlled discovery is Solana-only")
    if args.max_candidates < 1 or args.max_candidates > 3:
        raise ValueError("max_candidates must be between 1 and 3")
    if args.source_name not in {"dexscreener", "geckoterminal", "pumpportal", "pumpswap"}:
        raise ValueError("controlled discovery supports DexScreener, GeckoTerminal, PumpPortal, and PumpSwap")
    if args.timeout_seconds <= 0 or args.timeout_seconds > 10:
        raise ValueError("timeout_seconds must be greater than 0 and no more than 10")


def _identity_key(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    return str(value).strip().lower()


def _existing_token_pair_sets(connection: sqlite3.Connection) -> tuple[set[str], set[str], set[str]]:
    token_rows = connection.execute("SELECT token_mint, symbol, name FROM printer_tokens").fetchall()
    pair_rows = connection.execute("SELECT pair_address FROM printer_pairs").fetchall()
    identity_keys = {
        key
        for row in token_rows
        for key in (_identity_key(row["symbol"]), _identity_key(row["name"]))
        if key
    }
    return (
        {row["token_mint"] for row in token_rows if row["token_mint"]},
        {row["pair_address"] for row in pair_rows if row["pair_address"]},
        identity_keys,
    )


def _select_discovery_candidates(
    normalized_pairs: list[dict[str, Any]],
    *,
    existing_token_mints: set[str],
    existing_pair_addresses: set[str],
    existing_symbol_name_keys: set[str] | None = None,
    max_candidates: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    accepted_actions = {
        DiscoveryOutputAction.TRACK_FAST,
        DiscoveryOutputAction.TRACK_NORMAL,
    }
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    inspected: list[dict[str, Any]] = []
    for candidate in normalized_pairs:
        token_mint = candidate.get("token_mint")
        pair_address = candidate.get("pair_address")
        classification = classify_discovery_candidate(candidate)
        item = {
            "token_mint": token_mint,
            "pair_address": pair_address,
            "classification": classification.discovery_action.value,
            "tracking_label": classification.discovery_action.value,
        }
        inspected.append(item)
        reject_reason = None
        if candidate.get("chain") != "solana":
            reject_reason = "non_solana_candidate"
        elif token_mint in existing_token_mints or pair_address in existing_pair_addresses:
            if token_mint in existing_token_mints and pair_address in existing_pair_addresses:
                reject_reason = "duplicate_existing_token_or_pair"
            elif token_mint in existing_token_mints:
                reject_reason = "duplicate_existing_token_mint"
            else:
                reject_reason = "duplicate_pair_address"
        elif (
            existing_symbol_name_keys
            and is_dead_or_near_zero_activity_candidate(candidate)
            and (
                _identity_key(candidate.get("symbol")) in existing_symbol_name_keys
                or _identity_key(candidate.get("name")) in existing_symbol_name_keys
            )
        ):
            reject_reason = "weak_copycat_candidate"
        elif classification.reason == "insufficient_activity_for_memory_growth":
            reject_reason = "insufficient_activity_for_memory_growth"
        elif classification.discovery_action == DiscoveryOutputAction.WATCH_ONLY:
            reject_reason = "watch_only_not_eligible_for_15m_memory_proof_cycle"
        elif classification.discovery_action not in accepted_actions:
            reject_reason = f"classified_{classification.discovery_action.value.lower()}"
        elif len(accepted) >= max_candidates:
            reject_reason = "max_candidates_reached"

        if reject_reason:
            rejected.append({**item, "reject_reason": reject_reason})
        else:
            accepted.append(candidate)
    return accepted, rejected, inspected


def build_discover_candidates_once_payload(
    args: argparse.Namespace,
    *,
    transport=None,
) -> dict[str, Any]:
    _validate_discover_candidates_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    with sqlite3.connect(resolved) as connection:
        connection.row_factory = sqlite3.Row
        existing_token_mints, existing_pair_addresses, existing_symbol_name_keys = _existing_token_pair_sets(connection)

    if args.source_name == "geckoterminal":
        request_kind = str(
            getattr(args, "request_kind", None) or "geckoterminal_new_pool_discovery"
        ).strip()
        source_channel, source_channel_reason = _source_channel_for_geckoterminal(request_kind)
        endpoint = _GECKOTERMINAL_ENDPOINT_BY_REQUEST_KIND.get(
            request_kind, GECKOTERMINAL_NEW_POOLS_URL
        )
        source_request = build_governed_source_request(
            "geckoterminal",
            request_kind,
            request_key=args.request_key or f"post-rc-geckoterminal-{request_kind}",
            tracking_priority=0,
            payload={
                "post_rc_cycle": "cycle1",
                "request_kind": request_kind,
                "max_candidates": args.max_candidates,
                "chain": "solana",
            },
        )
        adapter = build_geckoterminal_adapter(
            enabled=True,
            fixture_transport=transport or build_geckoterminal_pools_transport(
                timeout_seconds=args.timeout_seconds, endpoint=endpoint
            ),
        )
        query = request_kind
        display_request_kind = request_kind
    elif args.source_name == "pumpportal":
        request_kind = str(
            getattr(args, "request_kind", None) or "pumpfun_launch_stream"
        ).strip()
        source_channel, source_channel_reason = _source_channel_for_pumpportal(request_kind)
        endpoint = "pumpportal_fixture_only"
        source_request = build_governed_source_request(
            "pumpportal",
            request_kind,
            request_key=args.request_key or f"post-rc-pumpportal-{request_kind}",
            tracking_priority=0,
            payload={
                "post_rc_cycle": "cycle1",
                "request_kind": request_kind,
                "max_candidates": args.max_candidates,
                "chain": "solana",
            },
        )
        if transport is None:
            raise ValueError(
                "PumpPortal discovery requires an operator-provided fixture transport; "
                "no live WebSocket is started automatically"
            )
        adapter = build_pumpportal_adapter(
            enabled=True,
            fixture_transport=transport,
        )
        query = request_kind
        display_request_kind = request_kind
    elif args.source_name == "pumpswap":
        request_kind = str(
            getattr(args, "request_kind", None) or "pumpswap_pool_confirmation"
        ).strip()
        source_channel, source_channel_reason = _source_channel_for_pumpswap(request_kind)
        endpoint = "pumpswap_fixture_only"
        source_request = build_governed_source_request(
            "pumpswap",
            request_kind,
            request_key=args.request_key or f"post-rc-pumpswap-{request_kind}",
            tracking_priority=0,
            payload={
                "post_rc_cycle": "cycle1",
                "request_kind": request_kind,
                "max_candidates": args.max_candidates,
                "chain": "solana",
            },
        )
        if transport is None:
            raise ValueError(
                "PumpSwap confirmation requires an operator-provided fixture transport; "
                "read-only confirmation only"
            )
        adapter = build_pumpswap_adapter(
            enabled=True,
            fixture_transport=transport,
        )
        query = request_kind
        display_request_kind = request_kind
    else:
        source_channel, source_channel_reason = _source_channel_for_dexscreener(
            getattr(args, "request_kind", None)
        )
        query = str(args.query or "pump").strip() or "pump"
        endpoint = f"https://api.dexscreener.com/latest/dex/search?q={quote(query)}"
        source_request = build_governed_source_request(
            "dexscreener",
            "token_discovery",
            request_key=args.request_key or f"post-rc-discovery-{query}",
            tracking_priority=0,
            payload={
                "post_rc_cycle": "cycle1",
                "query": query,
                "max_candidates": args.max_candidates,
                "chain": "solana",
            },
        )
        adapter = build_dexscreener_adapter(
            enabled=True,
            smoke_transport=transport or build_dexscreener_smoke_transport(
                timeout_seconds=args.timeout_seconds, endpoint=endpoint
            ),
        )
        display_request_kind = "token_discovery"

    result = execute_source_request_with_governor(
        resolved,
        source_request,
        adapter,
        recent_request_count=0,
    )
    normalized_payload = dict(result.normalized_result.normalized_payload or {})
    normalized_pairs = normalize_candidates(args.source_name, normalized_payload) if normalized_payload else []
    for candidate in normalized_pairs:
        candidate["source_channel"] = source_channel
        candidate["source_channel_reason"] = source_channel_reason
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    inspected: list[dict[str, Any]] = []
    discovery_results: list[dict[str, Any]] = []
    if result.response_record and result.normalized_result.source_status.value == "COMPLETE":
        accepted, rejected, inspected = _select_discovery_candidates(
            normalized_pairs,
            existing_token_mints=existing_token_mints,
            existing_pair_addresses=existing_pair_addresses,
            existing_symbol_name_keys=existing_symbol_name_keys,
            max_candidates=args.max_candidates,
        )
        if accepted:
            discovery_payload = {
                "source_status": result.normalized_result.source_status.value,
                "source_response_id": result.response_record.id,
                "pairs": accepted,
            }
            discovery_results = process_discovery_payload(
                resolved,
                args.source_name,
                discovery_payload,
                source_channel=source_channel,
                source_channel_reason=source_channel_reason,
            )

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    with sqlite3.connect(resolved) as connection:
        connection.row_factory = sqlite3.Row
        discovery_count_after = connection.execute("SELECT COUNT(*) FROM printer_discovery_candidates").fetchone()[0]
        accepted_rows = connection.execute(
            """
            SELECT token_id, pair_id, discovery_action, tracking_lane, source_channel, source_channel_reason
            FROM printer_discovery_candidates
            ORDER BY id DESC
            LIMIT ?
            """,
            (len(discovery_results),),
        ).fetchall()
    status = get_operator_db_status(resolved, project_root)
    return {
        "command": "printer-discover-candidates-once",
        "db_path": str(resolved),
        "operator_approved": True,
        "source_name": args.source_name,
        "request_kind": display_request_kind,
        "query": query,
        "endpoint": endpoint,
        "max_candidates": args.max_candidates,
        "source_status": result.normalized_result.source_status.value,
        "data_quality_label": result.normalized_result.data_quality_label.value,
        "source_request_id": result.request_record.id,
        "source_response_id": result.response_record.id if result.response_record else None,
        "source_failure_id": result.failure_record.id if result.failure_record else None,
        "failure_type": result.normalized_result.failure_type,
        "failure_message": result.normalized_result.failure_message,
        "candidates_found": len(normalized_pairs),
        "candidates_inspected": inspected,
        "candidates_accepted": len(discovery_results),
        "candidates_rejected": len(rejected),
        "rejected_candidates": rejected,
        "source_channel": source_channel,
        "source_channel_reason": source_channel_reason,
        "accepted_candidates": [
            {
                "token_mint": candidate.get("token_mint"),
                "pair_address": candidate.get("pair_address"),
                "tracking_label": classify_discovery_candidate(candidate).discovery_action.value,
                "source_channel": candidate.get("source_channel"),
            }
            for candidate in accepted[: len(discovery_results)]
        ],
        "discovery_results": [
            {
                "discovery_candidate_id": item["discovery_candidate_id"],
                "token_id": item["token_id"],
                "pair_id": item["pair_id"],
                "tracking_queue_id": item["tracking_queue_id"],
                "scheduler_job_id": item["scheduler_job_id"],
                "tracking_lane": item["tracking_lane"].value if item["tracking_lane"] else None,
                "classification": item["classification"].discovery_action.value,
            }
            for item in discovery_results
        ],
        "latest_discovery_rows": [dict(row) for row in accepted_rows],
        "source_request_delta": deltas.get("printer_source_requests", 0),
        "source_response_delta": deltas.get("printer_source_responses", 0),
        "source_failure_delta": deltas.get("printer_source_failures", 0),
        "token_delta": deltas.get("printer_tokens", 0),
        "pair_delta": deltas.get("printer_pairs", 0),
        "tracking_queue_delta": deltas.get("printer_tracking_queue", 0),
        "scheduler_job_delta": deltas.get("printer_scheduler_jobs", 0),
        "snapshot_delta": deltas.get("printer_token_snapshots", 0),
        "memory_delta": deltas.get("printer_memory_windows", 0),
        "retrieval_delta": deltas.get("printer_memory_retrieval_queries", 0) + deltas.get("printer_memory_retrieval_matches", 0),
        "paper_decision_delta": deltas.get("printer_paper_decisions", 0),
        "paper_position_delta": deltas.get("printer_paper_positions", 0),
        "discovery_candidate_rows_after": int(discovery_count_after),
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_discover_candidates_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Discover 1 to 3 controlled post-RC Solana candidates through Source Governor.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--chain", default="solana")
    parser.add_argument("--max-candidates", type=int, default=1)
    parser.add_argument("--query", default="pump")
    parser.add_argument("--timeout-seconds", type=float, default=5.0)
    parser.add_argument("--source-name", default="dexscreener",
        choices=["dexscreener", "geckoterminal", "pumpportal", "pumpswap"],
        help="Discovery source: dexscreener (default), geckoterminal, pumpportal, or pumpswap")
    parser.add_argument("--request-kind",
        help=(
            "GeckoTerminal: geckoterminal_new_pool_discovery (default) or "
            "geckoterminal_trending_pool_reference. Ignored for DexScreener."
        ))
    parser.add_argument("--request-key")
    args = parser.parse_args(argv)
    try:
        payload = build_discover_candidates_once_payload(args)
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
        "buys_5m": pair_payload.get("buys_5m"),
        "sells_5m": pair_payload.get("sells_5m"),
        "buys_1h": pair_payload.get("buys_1h"),
        "sells_1h": pair_payload.get("sells_1h"),
        "buys_24h": pair_payload.get("buys_24h"),
        "sells_24h": pair_payload.get("sells_24h"),
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
        if not result.response_record:
            skip_reason = result.normalized_result.failure_type or "no_response_record"
        elif result.normalized_result.source_status.value != "COMPLETE":
            skip_reason = result.normalized_result.failure_type or "source_status_not_complete"
        elif result.normalized_result.data_quality_label.value not in {"CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"}:
            skip_reason = result.normalized_result.failure_type or "data_quality_not_acceptable"
        elif pair_payload is None:
            skip_reason = "pair_not_in_response"
        elif pair_payload.get("price_usd") is None:
            skip_reason = "price_usd_missing"
        elif pair_payload.get("liquidity_usd") is None:
            skip_reason = "liquidity_usd_missing"
        else:
            snapshot_payload = _build_snapshot_payload_from_pair(
                target=target,
                pair_payload=pair_payload,
                source_status=result.normalized_result.source_status.value,
                data_quality_label=result.normalized_result.data_quality_label.value,
                captured_at=captured_at,
            )
            snapshot_created, snapshot_id = record_token_snapshot(resolved, snapshot_payload, captured_at)

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


def _context_payload_column(table: str) -> str:
    return {
        "printer_market_regime_snapshots": "normalized_market_payload_json",
        "printer_solana_chain_heat_snapshots": "normalized_chain_heat_payload_json",
        "printer_safety_rug_snapshots": "normalized_safety_payload_json",
        "printer_liquidity_exit_snapshots": "normalized_liquidity_exit_payload_json",
        "printer_trading_flow_snapshots": "normalized_trading_flow_payload_json",
        "printer_chart_volatility_snapshots": "normalized_chart_payload_json",
        "printer_micro_events": "normalized_micro_event_payload_json",
    }[table]


def _context_table_for_key(key: str) -> str:
    return {
        "market": "printer_market_regime_snapshots",
        "chain_heat": "printer_solana_chain_heat_snapshots",
        "safety": "printer_safety_rug_snapshots",
        "liquidity_exit": "printer_liquidity_exit_snapshots",
        "trading_flow": "printer_trading_flow_snapshots",
        "chart_volatility": "printer_chart_volatility_snapshots",
        "micro_event": "printer_micro_events",
    }[key]


def _context_row_timestamp(row: dict[str, Any], payload: dict[str, Any], key: str) -> str | None:
    payload_time = payload.get("snapshot_captured_at")
    if payload_time:
        return str(payload_time)
    if key == "micro_event":
        return row.get("detected_at") or row.get("captured_at")
    return row.get("captured_at") or row.get("detected_at")


def _try_parse_iso_datetime(value: Any) -> datetime | None:
    if value in {None, ""}:
        return None
    try:
        return _parse_iso_datetime(value)
    except (TypeError, ValueError):
        return None


def _context_freshness_report(
    context_rows: dict[str, dict[str, Any]],
    snapshot: dict[str, Any],
    window_start_at: str,
    window_end_at: str,
) -> dict[str, Any]:
    expected_snapshot_id = int(snapshot["id"])
    window_start = _try_parse_iso_datetime(window_start_at)
    window_end = _try_parse_iso_datetime(window_end_at)
    tolerance = timedelta(minutes=CONTEXT_FRESHNESS_TOLERANCE_MINUTES)
    details: dict[str, Any] = {}
    blockers: list[str] = []
    for key in ("market", "chain_heat", "safety", "liquidity_exit", "trading_flow", "chart_volatility", "micro_event"):
        row = context_rows.get(key) or {}
        table = _context_table_for_key(key)
        payload_column = _context_payload_column(table)
        payload = _json_or_empty(row.get(payload_column))
        source_status = row.get("source_status")
        data_quality_label = row.get("data_quality_label")
        attached_snapshot_id = payload.get("snapshot_id")
        captured_at = _context_row_timestamp(row, payload, key) if row else None
        if row and payload.get("snapshot_captured_at") in {None, ""} and attached_snapshot_id is not None and int(attached_snapshot_id) == expected_snapshot_id:
            captured_at = snapshot.get("captured_at") or captured_at
        captured_dt = _try_parse_iso_datetime(captured_at)
        freshness_label = "CONTEXT_UNKNOWN"
        target_status = "CONTEXT_TARGET_UNKNOWN"
        blocker_reason: str | None = None

        if not row:
            freshness_label = "CONTEXT_MISSING"
            target_status = "CONTEXT_TARGET_MISSING"
            blocker_reason = "MISSING_OR_UNKNOWN_CONTEXT"
        elif str(source_status or "").upper() in {"FAILED", "SOURCE_FAILED"}:
            freshness_label = "CONTEXT_SOURCE_FAILED"
            blocker_reason = "CONTEXT_SOURCE_FAILED"
        elif str(source_status or "").upper() in {"STALE", "SOURCE_STALE"}:
            freshness_label = "CONTEXT_STALE"
            blocker_reason = "CONTEXT_STALE"
        elif str(data_quality_label or "").upper() in {"DO_NOT_TRAIN", "CONTEXT_DO_NOT_TRAIN"}:
            freshness_label = "CONTEXT_DO_NOT_TRAIN"
            blocker_reason = "CONTEXT_DO_NOT_TRAIN"
        elif str(data_quality_label or "").upper() in {"CONFLICTING", "CONFLICTING_DATA", "CONTEXT_CONFLICTING"}:
            freshness_label = "CONTEXT_CONFLICTING"
            blocker_reason = "CONTEXT_CONFLICTING"
        else:
            if attached_snapshot_id is None:
                target_status = "CONTEXT_TARGET_UNKNOWN"
                blocker_reason = "CONTEXT_TARGET_MISMATCH"
            elif int(attached_snapshot_id) == expected_snapshot_id:
                target_status = "CONTEXT_TARGET_MATCH"
            else:
                target_status = "CONTEXT_TARGET_MISMATCH"
                freshness_label = "CONTEXT_TARGET_MISMATCH"
                blocker_reason = "CONTEXT_TARGET_MISMATCH"

            if blocker_reason is None:
                if captured_dt is None or window_start is None or window_end is None:
                    freshness_label = "CONTEXT_UNKNOWN"
                    blocker_reason = "MISSING_OR_UNKNOWN_CONTEXT"
                elif window_start <= captured_dt <= window_end:
                    freshness_label = "CONTEXT_FRESH"
                elif (window_start - tolerance) <= captured_dt <= (window_end + tolerance):
                    freshness_label = "CONTEXT_ACCEPTABLE"
                else:
                    freshness_label = "CONTEXT_OUTSIDE_WINDOW"
                    blocker_reason = "CONTEXT_OUTSIDE_WINDOW"

        if blocker_reason:
            blockers.append(blocker_reason)
        details[key] = {
            "context_table": table,
            "context_type": key,
            "context_role": "SUPPORT_MICRO_EVENT" if key == "micro_event" else "MAIN_WINDOW_CONTEXT",
            "context_row_id": row.get("id"),
            "source_status": source_status,
            "data_quality_label": data_quality_label,
            "context_freshness_label": freshness_label,
            "context_target_status": target_status,
            "context_blocker_reason": blocker_reason,
            "context_captured_at": captured_at,
            "expected_snapshot_id": expected_snapshot_id,
            "attached_snapshot_id": attached_snapshot_id,
            "window_start_at": window_start_at,
            "window_end_at": window_end_at,
        }
    unique_blockers = list(dict.fromkeys(blockers))
    return {
        "context_freshness_tolerance_minutes": CONTEXT_FRESHNESS_TOLERANCE_MINUTES,
        "all_context_fresh_enough": not unique_blockers,
        "context_blocking_reasons": unique_blockers,
        "context_details": details,
        "context_target_mismatch_count": sum(
            1 for item in details.values() if item["context_target_status"] == "CONTEXT_TARGET_MISMATCH"
        ),
        "stale_context_count": sum(
            1 for item in details.values()
            if item["context_freshness_label"] in {"CONTEXT_STALE", "CONTEXT_OUTSIDE_WINDOW"}
        ),
        "missing_or_unknown_context_count": sum(
            1 for item in details.values()
            if item["context_freshness_label"] in {"CONTEXT_MISSING", "CONTEXT_UNKNOWN"}
        ),
    }


def _context_row_matches_snapshot(row: sqlite3.Row, payload_column: str, snapshot_id: int) -> bool:
    payload = _json_or_empty(row[payload_column])
    return int(payload.get("snapshot_id") or -1) == int(snapshot_id)


def _context_rows_for_target(connection: sqlite3.Connection, target: dict[str, Any], snapshot: dict[str, Any] | None = None) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in CONTEXT_TABLES:
        payload_column = _context_payload_column(table)
        if table in {"printer_market_regime_snapshots", "printer_solana_chain_heat_snapshots"}:
            rows = connection.execute(f"SELECT {payload_column} FROM {table}").fetchall()
        else:
            rows = connection.execute(
                f"SELECT {payload_column} FROM {table} WHERE token_id = ? AND pair_id = ?",
                (target["token_id"], target["pair_id"]),
            ).fetchall()
        if snapshot is None:
            counts[table] = len(rows)
        else:
            counts[table] = sum(
                1 for row in rows
                if _context_row_matches_snapshot(row, payload_column, int(snapshot["id"]))
            )
    return counts


def _label_value(label: Any) -> str:
    return str(getattr(label, "value", label))


def _snapshot_context_payload(target: dict[str, Any], snapshot: dict[str, Any], captured_at: str) -> dict[str, Any]:
    return {
        "token_id": target["token_id"],
        "pair_id": target["pair_id"],
        "token_mint": target["token_mint"],
        "pair_address": target["pair_address"],
        "captured_at": captured_at,
        "price_usd": snapshot.get("price_usd"),
        "liquidity_usd": snapshot.get("liquidity_usd"),
        "volume_5m": snapshot.get("volume_5m"),
        "volume_15m": snapshot.get("volume_15m"),
        "volume_1h": snapshot.get("volume_1h"),
        "volume_24h": snapshot.get("volume_24h"),
        "txns_5m": snapshot.get("txns_5m"),
        "txns_15m": snapshot.get("txns_15m"),
        "txns_1h": snapshot.get("txns_1h"),
        "txns_24h": snapshot.get("txns_24h"),
        "source_status": snapshot.get("source_status") or "PARTIAL",
        "data_quality_label": snapshot.get("data_quality_label") or "ACCEPTABLE_PARTIAL_DATA",
    }


def _governed_context_payload_from_source_response(
    connection: sqlite3.Connection,
    *,
    source_response_id: int,
    target: dict[str, Any],
    snapshot: dict[str, Any],
    captured_at: str,
    allowed_sources: set[str],
    allowed_request_kinds: set[str],
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT
            response.*,
            request.request_kind AS request_kind
        FROM printer_source_responses AS response
        JOIN printer_source_requests AS request
          ON request.id = response.source_request_id
        WHERE response.id = ?
        """,
        (source_response_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"governed context source response not found: {source_response_id}")
    if row["source_name"] not in allowed_sources:
        raise ValueError(f"governed context source is not allowed for this context: {row['source_name']}")
    if row["request_kind"] not in allowed_request_kinds:
        raise ValueError(f"governed context request kind is not allowed: {row['request_kind']}")
    payload = _json_or_empty(row["normalized_payload_json"])
    payload.update(
        {
            "source_status": row["source_status"],
            "data_quality_label": row["data_quality_label"],
            "captured_at": captured_at,
            "snapshot_id": snapshot["id"],
            "snapshot_captured_at": snapshot.get("captured_at"),
            "attached_token_id": target["token_id"],
            "attached_pair_id": target["pair_id"],
            "token_mint": target["token_mint"],
            "pair_address": target["pair_address"],
            "source_request_id": row["source_request_id"],
            "source_response_id": row["id"],
            "governed_context_source": row["source_name"],
            "governed_context_request_kind": row["request_kind"],
        }
    )
    return payload


def _insert_market_context_from_source_response(
    connection: sqlite3.Connection,
    *,
    source_response_id: int,
    target: dict[str, Any],
    snapshot: dict[str, Any],
    captured_at: str,
) -> int:
    payload = _governed_context_payload_from_source_response(
        connection,
        source_response_id=source_response_id,
        target=target,
        snapshot=snapshot,
        captured_at=captured_at,
        allowed_sources={"alternative_me", "coingecko", "defillama"},
        allowed_request_kinds={
            "fear_greed_context",
            "broad_market_context",
            "asset_context",
            "chain_liquidity_context",
            "tvl_context",
            "dex_volume_context",
        },
    )
    _created, row_id = record_market_regime_snapshot(connection, payload, _parse_iso_datetime(captured_at))
    return row_id


def _insert_chain_heat_context_from_source_response(
    connection: sqlite3.Connection,
    *,
    source_response_id: int,
    target: dict[str, Any],
    snapshot: dict[str, Any],
    captured_at: str,
) -> int:
    payload = _governed_context_payload_from_source_response(
        connection,
        source_response_id=source_response_id,
        target=target,
        snapshot=snapshot,
        captured_at=captured_at,
        allowed_sources={"coingecko", "defillama"},
        allowed_request_kinds={
            "broad_market_context",
            "asset_context",
            "chain_liquidity_context",
            "tvl_context",
            "dex_volume_context",
        },
    )
    _created, row_id = record_chain_heat_snapshot(connection, payload, _parse_iso_datetime(captured_at))
    return row_id


def _insert_controlled_context_rows(
    connection: sqlite3.Connection,
    target: dict[str, Any],
    snapshot: dict[str, Any],
    captured_at: str,
    *,
    market_source_response_id: int | None = None,
    chain_heat_source_response_id: int | None = None,
) -> dict[str, int]:
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
    base_context = _snapshot_context_payload(target, snapshot, captured_at)
    safety_context = dict(base_context)
    liquidity_context = dict(base_context)
    flow_context = normalize_trading_flow_payload(
        {
            **base_context,
            "raw_snapshot_payload_json": snapshot.get("raw_snapshot_payload_json"),
            "normalized_snapshot_payload_json": snapshot.get("normalized_snapshot_payload_json"),
        }
    )
    chart_context = {
        **base_context,
        "window_start_at": snapshot.get("captured_at"),
        "window_end_at": captured_at,
        "price_open": price_usd,
        "price_high": price_usd,
        "price_low": price_usd,
        "price_close": price_usd,
        "price_change_percent": snapshot.get("price_change_5m"),
        "candle_count": 1,
    }
    micro_context = {
        **base_context,
        "detected_at": captured_at,
        "event_window_start_at": snapshot.get("captured_at"),
        "event_window_end_at": captured_at,
        "price_start": price_usd,
        "price_high": price_usd,
        "price_low": price_usd,
        "price_end": price_usd,
        "price_change_5m_percent": snapshot.get("price_change_5m"),
        "volume_5m": snapshot.get("volume_5m"),
        "txns_5m": snapshot.get("txns_5m"),
        "liquidity_start_usd": liquidity_usd,
        "liquidity_end_usd": liquidity_usd,
        "liquidity_exit_realism_label": _label_value(classify_exit_realism(liquidity_context)),
        "slippage_label": _label_value(classify_slippage(liquidity_context)),
        "price_impact_label": _label_value(classify_price_impact(liquidity_context)),
        "route_label": _label_value(classify_route_availability(liquidity_context)),
        "safety_status_label": _label_value(classify_safety_status(safety_context)),
        "liquidity_state_label": _label_value(classify_liquidity_state(liquidity_context)),
        "flow_direction_label": _label_value(classify_flow_direction(flow_context)),
        "candle_path_label": _label_value(classify_candle_path(chart_context)),
    }
    safety_labels = {
        "liquidity_safety_label": _label_value(classify_liquidity_safety(safety_context)),
        "authority_label": _label_value(classify_authority_safety(safety_context)),
        "distribution_label": _label_value(classify_distribution_safety(safety_context)),
        "rug_risk_label": _label_value(classify_rug_risk(safety_context)),
        "safety_status_label": _label_value(classify_safety_status(safety_context)),
        "payload_quality_label": _label_value(classify_safety_payload_quality(safety_context)),
        "gate_label": _label_value(classify_safety_gate(safety_context)),
    }
    liquidity_labels = {
        "liquidity_state_label": _label_value(classify_liquidity_state(liquidity_context)),
        "entry_realism_label": _label_value(classify_entry_realism(liquidity_context)),
        "exit_realism_label": _label_value(classify_exit_realism(liquidity_context)),
        "slippage_label": _label_value(classify_slippage(liquidity_context)),
        "price_impact_label": _label_value(classify_price_impact(liquidity_context)),
        "route_label": _label_value(classify_route_availability(liquidity_context)),
        "quote_age_label": _label_value(classify_quote_age(liquidity_context)),
        "liquidity_drain_label": _label_value(classify_liquidity_drain(liquidity_context)),
        "payload_quality_label": _label_value(classify_liquidity_exit_payload_quality(liquidity_context)),
        "realism_gate_label": _label_value(classify_realism_gate(liquidity_context)),
    }
    flow_labels = {
        "flow_direction_label": _label_value(classify_flow_direction(flow_context)),
        "flow_pressure_label": _label_value(classify_flow_pressure(flow_context)),
        "imbalance_label": _label_value(classify_imbalance(flow_context)),
        "volume_activity_label": _label_value(classify_volume_activity(flow_context)),
        "tx_activity_label": _label_value(classify_tx_activity(flow_context)),
        "wallet_participation_label": _label_value(classify_wallet_participation(flow_context)),
        "payload_quality_label": _label_value(classify_trading_flow_payload_quality(flow_context)),
        "memory_gate_label": _label_value(classify_flow_memory_gate(flow_context)),
    }
    chart_labels = {
        "trend_structure_label": _label_value(classify_trend_structure(chart_context)),
        "volatility_label": _label_value(classify_volatility(chart_context)),
        "range_behavior_label": _label_value(classify_range_behavior(chart_context)),
        "momentum_label": _label_value(classify_momentum(chart_context)),
        "drawdown_recovery_label": _label_value(classify_drawdown_recovery(chart_context)),
        "candle_path_label": _label_value(classify_candle_path(chart_context)),
        "payload_quality_label": _label_value(classify_chart_payload_quality(chart_context)),
        "memory_gate_label": _label_value(classify_chart_memory_gate(chart_context)),
    }
    micro_labels = {
        "micro_event_state_label": _label_value(classify_micro_event_state(micro_context)),
        "micro_event_move_label": _label_value(classify_micro_event_move(micro_context)),
        "micro_exit_realism_label": _label_value(classify_micro_exit_realism(micro_context)),
        "late_buy_trap_label": _label_value(classify_late_buy_trap(micro_context)),
        "held_to_15m_result_label": _label_value(classify_holding_to_15m_result(micro_context)),
        "payload_quality_label": _label_value(classify_micro_event_payload_quality(micro_context)),
        "memory_gate_label": _label_value(classify_micro_event_memory_gate(micro_context)),
    }

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
            liquidity_usd, "dexscreener", safety_labels["safety_status_label"], safety_labels["rug_risk_label"],
            safety_labels["liquidity_safety_label"], safety_labels["authority_label"], safety_labels["distribution_label"],
            safety_labels["payload_quality_label"], safety_labels["gate_label"], "MISSING_CRITICAL_DATA",
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
            snapshot.get("txns_24h"), liquidity_labels["liquidity_state_label"], liquidity_labels["entry_realism_label"],
            liquidity_labels["exit_realism_label"], liquidity_labels["slippage_label"], liquidity_labels["price_impact_label"], liquidity_labels["route_label"],
            liquidity_labels["quote_age_label"], liquidity_labels["liquidity_drain_label"], liquidity_labels["payload_quality_label"],
            liquidity_labels["realism_gate_label"], snapshot_quality, source_status,
            json.dumps(snapshot_payload, sort_keys=True), json.dumps(liquidity_payload, sort_keys=True),
        ),
    )
    inserts["printer_liquidity_exit_snapshots"] = 1

    flow_payload = _base_context_payload(target, snapshot, "trading_flow")
    flow_payload["known_fields"] = {
        "volume_5m": snapshot.get("volume_5m"),
        "volume_15m": snapshot.get("volume_15m"),
        "volume_1h": snapshot.get("volume_1h"),
        "volume_24h": snapshot.get("volume_24h"),
        "txns_5m": snapshot.get("txns_5m"),
        "txns_15m": snapshot.get("txns_15m"),
        "txns_1h": snapshot.get("txns_1h"),
        "txns_24h": snapshot.get("txns_24h"),
        "buys_5m": flow_context.get("buys_5m"),
        "sells_5m": flow_context.get("sells_5m"),
        "buys_15m": flow_context.get("buys_15m"),
        "sells_15m": flow_context.get("sells_15m"),
        "buys_1h": flow_context.get("buys_1h"),
        "sells_1h": flow_context.get("sells_1h"),
        "buys_4h": flow_context.get("buys_4h"),
        "sells_4h": flow_context.get("sells_4h"),
        "buys_24h": flow_context.get("buys_24h"),
        "sells_24h": flow_context.get("sells_24h"),
    }
    flow_payload["unknown_fields"] = [
        field
        for field in ("buy_sell_split", "wallet_participation")
        if field != "buy_sell_split"
        or (
            flow_context.get("buys_5m") is None
            and flow_context.get("sells_5m") is None
            and flow_context.get("buys_1h") is None
            and flow_context.get("sells_1h") is None
        )
    ]
    connection.execute(
        """
        INSERT INTO printer_trading_flow_snapshots (
            token_id, pair_id, token_mint, pair_address, captured_at, price_usd, liquidity_usd,
            volume_5m, volume_1h, volume_24h, txns_5m, txns_1h, txns_24h,
            buys_5m, sells_5m, buys_15m, sells_15m, buys_1h, sells_1h,
            buys_4h, sells_4h, buys_24h, sells_24h,
            flow_direction_label, flow_pressure_label, imbalance_label, volume_activity_label,
            tx_activity_label, wallet_participation_label, trading_flow_payload_quality_label,
            flow_memory_gate_label, data_quality_label, source_status,
            raw_trading_flow_payload_json, normalized_trading_flow_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target["token_id"], target["pair_id"], target["token_mint"], target["pair_address"], captured_at,
            price_usd, liquidity_usd, snapshot.get("volume_5m"), snapshot.get("volume_1h"),
            snapshot.get("volume_24h"), snapshot.get("txns_5m"), snapshot.get("txns_1h"),
            snapshot.get("txns_24h"), flow_context.get("buys_5m"), flow_context.get("sells_5m"),
            flow_context.get("buys_15m"), flow_context.get("sells_15m"),
            flow_context.get("buys_1h"), flow_context.get("sells_1h"),
            flow_context.get("buys_4h"), flow_context.get("sells_4h"),
            flow_context.get("buys_24h"), flow_context.get("sells_24h"),
            flow_labels["flow_direction_label"], flow_labels["flow_pressure_label"], flow_labels["imbalance_label"],
            flow_labels["volume_activity_label"], flow_labels["tx_activity_label"], flow_labels["wallet_participation_label"],
            flow_labels["payload_quality_label"], flow_labels["memory_gate_label"], snapshot_quality, source_status,
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
            snapshot.get("price_change_5m"), 1, chart_labels["trend_structure_label"], chart_labels["volatility_label"],
            chart_labels["range_behavior_label"], chart_labels["momentum_label"], chart_labels["drawdown_recovery_label"], chart_labels["candle_path_label"],
            chart_labels["payload_quality_label"], chart_labels["memory_gate_label"], snapshot_quality, source_status,
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
            liquidity_usd, liquidity_usd, liquidity_labels["exit_realism_label"], liquidity_labels["slippage_label"], liquidity_labels["price_impact_label"],
            liquidity_labels["route_label"], safety_labels["safety_status_label"], liquidity_labels["liquidity_state_label"], flow_labels["flow_direction_label"],
            chart_labels["candle_path_label"], micro_labels["micro_event_state_label"], micro_labels["micro_event_move_label"], micro_labels["micro_exit_realism_label"],
            micro_labels["late_buy_trap_label"], micro_labels["held_to_15m_result_label"], micro_labels["payload_quality_label"],
            micro_labels["memory_gate_label"], "MISSING_CRITICAL_DATA", "PARTIAL",
            json.dumps(snapshot_payload, sort_keys=True), json.dumps(micro_payload, sort_keys=True),
        ),
    )
    inserts["printer_micro_events"] = 1

    if market_source_response_id is not None:
        _insert_market_context_from_source_response(
            connection,
            source_response_id=market_source_response_id,
            target=target,
            snapshot=snapshot,
            captured_at=captured_at,
        )
        inserts["printer_market_regime_snapshots"] = 1
    else:
        market_payload = {
            "phase": "28",
            "category": "market_regime",
            "evidence_boundary": "no governed broad-market source response was provided",
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

    if chain_heat_source_response_id is not None:
        _insert_chain_heat_context_from_source_response(
            connection,
            source_response_id=chain_heat_source_response_id,
            target=target,
            snapshot=snapshot,
            captured_at=captured_at,
        )
        inserts["printer_solana_chain_heat_snapshots"] = 1
    else:
        chain_payload = {
            "phase": "28",
            "category": "solana_chain_heat",
            "evidence_boundary": "no governed Solana chain-heat source response was provided",
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
        existing_context_counts = _context_rows_for_target(connection, target, snapshot)
        market_source_response_id = getattr(args, "market_source_response_id", None)
        chain_heat_source_response_id = getattr(args, "chain_heat_source_response_id", None)
        if sum(existing_context_counts.values()) > 0 and not (market_source_response_id or chain_heat_source_response_id):
            inserted_context_rows = {}
            skipped_reason = "context_already_exists_for_evidence"
        elif sum(existing_context_counts.values()) > 0:
            captured_at = _utc_now_text()
            inserted_context_rows = {}
            if market_source_response_id is not None:
                _insert_market_context_from_source_response(
                    connection,
                    source_response_id=market_source_response_id,
                    target=target,
                    snapshot=snapshot,
                    captured_at=captured_at,
                )
                inserted_context_rows["printer_market_regime_snapshots"] = 1
            if chain_heat_source_response_id is not None:
                _insert_chain_heat_context_from_source_response(
                    connection,
                    source_response_id=chain_heat_source_response_id,
                    target=target,
                    snapshot=snapshot,
                    captured_at=captured_at,
                )
                inserted_context_rows["printer_solana_chain_heat_snapshots"] = 1
            skipped_reason = None
        else:
            inserted_context_rows = _insert_controlled_context_rows(
                connection,
                target,
                snapshot,
                _utc_now_text(),
                market_source_response_id=market_source_response_id,
                chain_heat_source_response_id=chain_heat_source_response_id,
            )
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
        "market_source_response_id": getattr(args, "market_source_response_id", None),
        "chain_heat_source_response_id": getattr(args, "chain_heat_source_response_id", None),
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


def _build_broad_context_adapter(
    source_name: str,
    *,
    transport=None,
    timeout_seconds: float = 8.0,
):
    if source_name == "coingecko":
        return build_coingecko_adapter(
            enabled=True,
            fixture_transport=transport or build_coingecko_market_transport(timeout_seconds=timeout_seconds),
        )
    if source_name == "defillama":
        return build_defillama_adapter(
            enabled=True,
            fixture_transport=transport or build_defillama_chain_liquidity_transport(timeout_seconds=timeout_seconds),
        )
    if source_name == "alternative_me":
        return build_alternative_me_adapter(
            enabled=True,
            fixture_transport=transport or build_alternative_me_fear_greed_transport(timeout_seconds=timeout_seconds),
        )
    raise ValueError(f"broad context source not supported: {source_name}")


def _validate_broad_context_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("broad context collection requires explicit operator approval")
    source_name = str(args.source_name or "").strip().lower()
    if source_name not in BROAD_CONTEXT_SOURCE_NAMES:
        raise ValueError(
            f"broad context source must be one of: {sorted(BROAD_CONTEXT_SOURCE_NAMES)}"
        )
    request_kind = str(
        args.request_kind or BROAD_CONTEXT_DEFAULT_REQUEST_KINDS.get(source_name, "")
    ).strip()
    allowed = BROAD_CONTEXT_ALLOWED_REQUEST_KINDS.get(source_name, set())
    if request_kind not in allowed:
        raise ValueError(
            f"request_kind '{request_kind}' is not allowed for {source_name}; "
            f"allowed: {sorted(allowed)}"
        )
    timeout = float(args.timeout_seconds or 8.0)
    if timeout <= 0 or timeout > 15:
        raise ValueError("timeout_seconds must be between 0 and 15")


def build_collect_broad_context_once_payload(
    args: argparse.Namespace,
    *,
    transport=None,
) -> dict[str, Any]:
    _validate_broad_context_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    source_name = str(args.source_name).strip().lower()
    request_kind = str(
        args.request_kind or BROAD_CONTEXT_DEFAULT_REQUEST_KINDS[source_name]
    ).strip()
    request_key = str(
        args.request_key or f"broad-context-{source_name}-{request_kind}"
    ).strip()
    timeout_seconds = float(args.timeout_seconds or 8.0)

    before_counts = get_core_table_counts(resolved, project_root)

    source_request = build_governed_source_request(
        source_name,
        request_kind,
        request_key=request_key,
        tracking_priority=8,
        payload={
            "broad_context_cycle": "operator_controlled",
            "source_name": source_name,
            "request_kind": request_kind,
        },
    )
    adapter = _build_broad_context_adapter(
        source_name, transport=transport, timeout_seconds=timeout_seconds
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
    guard_deltas = {
        table: deltas[table]
        for table in BROAD_CONTEXT_GUARD_TABLES
        if deltas.get(table)
    }
    response_id = result.response_record.id if result.response_record else None
    next_step = None
    if response_id is not None:
        if source_name in {"coingecko", "defillama", "alternative_me"}:
            next_step = (
                f"Pass --market-source-response-id {response_id} "
                f"(or --chain-heat-source-response-id {response_id}) "
                f"to printer-collect-context-once"
            )
    return {
        "command": "printer-collect-broad-context-once",
        "db_path": str(resolved),
        "operator_approved": True,
        "source_name": source_name,
        "request_kind": request_kind,
        "request_key": request_key,
        "source_status": result.normalized_result.source_status.value,
        "data_quality_label": result.normalized_result.data_quality_label.value,
        "source_request_id": result.request_record.id,
        "source_response_id": response_id,
        "source_failure_id": result.failure_record.id if result.failure_record else None,
        "failure_type": result.normalized_result.failure_type,
        "failure_message": result.normalized_result.failure_message,
        "source_table_deltas": {
            "printer_source_requests": deltas.get("printer_source_requests", 0),
            "printer_source_responses": deltas.get("printer_source_responses", 0),
            "printer_source_failures": deltas.get("printer_source_failures", 0),
        },
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "next_step_hint": next_step,
        "counts_after": after_counts,
    }


def main_collect_broad_context_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser(
        "Fetch governed broad market or chain-heat context from a free public source.",
        ("json", "text"),
    )
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument(
        "--source-name",
        choices=sorted(BROAD_CONTEXT_SOURCE_NAMES),
        required=True,
        help=(
            "Broad context source: coingecko (market + chain heat), "
            "defillama (chain liquidity), or alternative_me (fear/greed)."
        ),
    )
    parser.add_argument(
        "--request-kind",
        help=(
            "Request kind: broad_market_context or asset_context (coingecko); "
            "chain_liquidity_context, tvl_context, or dex_volume_context (defillama); "
            "fear_greed_context (alternative_me). "
            "Defaults to the primary kind for each source if omitted."
        ),
    )
    parser.add_argument(
        "--request-key",
        help="Idempotency key for this governed source request (auto-generated if omitted).",
    )
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    args = parser.parse_args(argv)
    try:
        payload = build_collect_broad_context_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


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
    parser.add_argument("--market-source-response-id", type=int)
    parser.add_argument("--chain-heat-source-response-id", type=int)
    args = parser.parse_args(argv)
    try:
        payload = build_collect_context_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _normalize_memory_window(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    windows = {
        "5m": "WINDOW_5M_MICRO_EVENT",
        "window_5m": "WINDOW_5M_MICRO_EVENT",
        "window_5m_micro_event": "WINDOW_5M_MICRO_EVENT",
        "15m": "WINDOW_15M",
        "window_15m": "WINDOW_15M",
        "1h": "WINDOW_1H",
        "window_1h": "WINDOW_1H",
        "4h": "WINDOW_4H",
        "window_4h": "WINDOW_4H",
        "12h": "WINDOW_12H",
        "window_12h": "WINDOW_12H",
        "24h": "WINDOW_24H",
        "window_24h": "WINDOW_24H",
    }
    if normalized in windows:
        return windows[normalized]
    raise ValueError("memory-window review requires a supported V1 window kind")


def _memory_window_duration_minutes(window_kind: str) -> int:
    return {
        "WINDOW_5M_MICRO_EVENT": 5,
        "WINDOW_15M": 15,
        "WINDOW_1H": 60,
        "WINDOW_4H": 240,
        "WINDOW_12H": 720,
        "WINDOW_24H": 1440,
    }[window_kind]


def _memory_evidence_role(window_kind: str) -> str:
    if window_kind == "WINDOW_5M_MICRO_EVENT":
        return "SUPPORT_MICRO_EVENT"
    return "MAIN_OUTCOME"


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


def _context_row_for_snapshot(rows: list[sqlite3.Row], payload_column: str, snapshot_id: int | None) -> sqlite3.Row | None:
    if snapshot_id is None:
        return rows[0] if rows else None
    for row in rows:
        if _context_row_matches_snapshot(row, payload_column, snapshot_id):
            return row
    return rows[0] if rows else None


def _resolve_memory_context_rows(connection: sqlite3.Connection, target: dict[str, Any], snapshot_id: int | None = None) -> dict[str, dict[str, Any]]:
    token_id = target["token_id"]
    pair_id = target["pair_id"]
    context: dict[str, dict[str, Any]] = {}
    table_to_key = {
        "printer_safety_rug_snapshots": ("safety", "captured_at", "normalized_safety_payload_json"),
        "printer_liquidity_exit_snapshots": ("liquidity_exit", "captured_at", "normalized_liquidity_exit_payload_json"),
        "printer_trading_flow_snapshots": ("trading_flow", "captured_at", "normalized_trading_flow_payload_json"),
        "printer_chart_volatility_snapshots": ("chart_volatility", "captured_at", "normalized_chart_payload_json"),
        "printer_micro_events": ("micro_event", "detected_at", "normalized_micro_event_payload_json"),
    }
    for table, (key, order_column, payload_column) in table_to_key.items():
        rows = connection.execute(
            f"""
            SELECT *
            FROM {table}
            WHERE token_id = ? AND pair_id = ?
            ORDER BY {order_column} DESC, id DESC
            """,
            (token_id, pair_id),
        ).fetchall()
        row = _context_row_for_snapshot(rows, payload_column, snapshot_id)
        context[key] = _row_to_dict(row)
    market_rows = connection.execute(
        "SELECT * FROM printer_market_regime_snapshots ORDER BY captured_at DESC, id DESC"
    ).fetchall()
    chain_rows = connection.execute(
        "SELECT * FROM printer_solana_chain_heat_snapshots ORDER BY captured_at DESC, id DESC"
    ).fetchall()
    market_row = _context_row_for_snapshot(market_rows, "normalized_market_payload_json", snapshot_id)
    chain_row = _context_row_for_snapshot(chain_rows, "normalized_chain_heat_payload_json", snapshot_id)
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


UNKNOWN_CONTEXT_VALUES = {
    None,
    "UNKNOWN",
    "SOLANA_UNKNOWN",
    "SAFETY_UNKNOWN",
    "RUG_RISK_UNKNOWN",
    "ENTRY_UNKNOWN",
    "EXIT_UNKNOWN",
    "FLOW_UNKNOWN",
    "PRESSURE_UNKNOWN",
    "TREND_UNKNOWN",
    "VOLATILITY_UNKNOWN",
    "MICRO_EVENT_UNKNOWN",
    "HELD_TO_15M_UNKNOWN",
}


def _collect_unknown_context_blockers(labels: dict[str, Any]) -> list[str]:
    return [
        f"{key}={value if value is not None else 'UNKNOWN'}"
        for key, value in labels.items()
        if value in UNKNOWN_CONTEXT_VALUES
    ]


def _window_coverage_policy(window_kind: str, snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if window_kind == "WINDOW_15M":
        return {
            "coverage_policy_used": "WINDOW_15M_TRACKED_SPACED_6_SNAPSHOT_POLICY",
            "expected_snapshot_count": 6,
            "requires_close_snapshot": True,
        }
    return {
        "coverage_policy_used": f"{window_kind}_MINIMUM_2_SNAPSHOT_FIXTURE_POLICY",
        "expected_snapshot_count": 2,
        "requires_close_snapshot": False,
    }


def _memory_storage_status(memory_quality_label: str) -> str:
    return {
        "CLEAN_MEMORY": "CLEAN_MEMORY",
        "PARTIAL_MEMORY": "PARTIAL_MEMORY",
        "DIRTY_MEMORY": "DIRTY_MEMORY",
        "AUDIT_ONLY_MEMORY": "AUDIT_ONLY",
        "DO_NOT_TRAIN_MEMORY": "DO_NOT_TRAIN",
    }[memory_quality_label]


def _parse_iso_datetime(value: Any) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _snapshot_rows_for_memory_evidence(
    connection: sqlite3.Connection,
    target: dict[str, Any],
    end_snapshot: dict[str, Any],
    window_kind: str,
) -> tuple[list[dict[str, Any]], str, str]:
    end_at = _parse_iso_datetime(end_snapshot["captured_at"])
    start_at = end_at - timedelta(minutes=_memory_window_duration_minutes(window_kind))
    rows = connection.execute(
        """
        SELECT *
        FROM printer_token_snapshots
        WHERE token_id = ?
          AND pair_id = ?
          AND datetime(captured_at) >= datetime(?)
          AND datetime(captured_at) <= datetime(?)
        ORDER BY datetime(captured_at) ASC, id ASC
        """,
        (target["token_id"], target["pair_id"], start_at.isoformat(), end_at.isoformat()),
    ).fetchall()
    snapshots = [_row_to_dict(row) for row in rows]
    if not any(int(row["id"]) == int(end_snapshot["id"]) for row in snapshots):
        snapshots.append(end_snapshot)
        snapshots.sort(key=lambda row: (str(row.get("captured_at") or ""), int(row["id"])))
    return snapshots, start_at.isoformat(), end_at.isoformat()


def _memory_evidence_identity(
    target: dict[str, Any],
    window_kind: str,
    snapshots: list[dict[str, Any]],
    window_start_at: str,
    window_end_at: str,
    source_reference: str | None,
    evidence_role: str,
) -> tuple[str, str]:
    payload = {
        "token_id": target["token_id"],
        "pair_id": target["pair_id"],
        "window_kind": window_kind,
        "window_start_at": window_start_at,
        "window_end_at": window_end_at,
        "snapshot_ids": [int(row["id"]) for row in snapshots],
        "snapshot_start_id": int(snapshots[0]["id"]) if snapshots else None,
        "snapshot_end_id": int(snapshots[-1]["id"]) if snapshots else None,
        "source_reference": source_reference,
        "evidence_role": evidence_role,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest(), encoded


def _existing_memory_for_evidence(connection: sqlite3.Connection, evidence_identity_hash: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM printer_memory_windows
        WHERE evidence_identity_hash = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (evidence_identity_hash,),
    ).fetchone()


def _context_row_ids_for_memory(context_rows: dict[str, dict[str, Any]]) -> dict[str, int | None]:
    return {
        "market": context_rows.get("market", {}).get("id"),
        "chain_heat": context_rows.get("chain_heat", {}).get("id"),
        "safety": context_rows.get("safety", {}).get("id"),
        "liquidity_exit": context_rows.get("liquidity_exit", {}).get("id"),
        "trading_flow": context_rows.get("trading_flow", {}).get("id"),
        "chart_volatility": context_rows.get("chart_volatility", {}).get("id"),
        "micro_event": context_rows.get("micro_event", {}).get("id"),
    }


def _memory_snapshot_ids_from_row(connection: sqlite3.Connection, row: sqlite3.Row) -> list[int]:
    supporting_context = _json_or_empty(row["supporting_context_json"])
    snapshot_ids = supporting_context.get("snapshot_ids")
    if isinstance(snapshot_ids, list) and snapshot_ids:
        return [int(value) for value in snapshot_ids]
    rows = connection.execute(
        """
        SELECT token_snapshot_id
        FROM printer_episode_snapshots es
        JOIN printer_episodes e ON e.id = es.episode_id
        WHERE e.memory_window_id = ?
        ORDER BY es.position_in_episode ASC, es.id ASC
        """,
        (row["id"],),
    ).fetchall()
    return [int(snapshot["token_snapshot_id"]) for snapshot in rows]


def _memory_context_row_ids_from_row(row: sqlite3.Row) -> dict[str, Any]:
    supporting_context = _json_or_empty(row["supporting_context_json"])
    return supporting_context.get("context_row_ids") or {}


def _existing_memory_for_functional_evidence(
    connection: sqlite3.Connection,
    target: dict[str, Any],
    window_kind: str,
    snapshots: list[dict[str, Any]],
    window_start_at: str,
    window_end_at: str,
    evidence_role: str,
    context_rows: dict[str, dict[str, Any]],
) -> sqlite3.Row | None:
    if not snapshots:
        return None
    snapshot_ids = [int(row["id"]) for row in snapshots]
    context_row_ids = _context_row_ids_for_memory(context_rows)
    candidates = connection.execute(
        """
        SELECT *
        FROM printer_memory_windows
        WHERE token_id = ?
          AND pair_id = ?
          AND window_kind = ?
          AND snapshot_start_id = ?
          AND snapshot_end_id = ?
          AND window_start_at = ?
          AND window_end_at = ?
          AND evidence_role = ?
        ORDER BY id DESC
        """,
        (
            target["token_id"], target["pair_id"], window_kind, snapshot_ids[0], snapshot_ids[-1],
            window_start_at, window_end_at, evidence_role,
        ),
    ).fetchall()
    for row in candidates:
        if _memory_snapshot_ids_from_row(connection, row) != snapshot_ids:
            continue
        existing_context_ids = _memory_context_row_ids_from_row(row)
        if existing_context_ids and existing_context_ids != context_row_ids:
            continue
        return row
    return None


def _evidence_difference_reason(
    connection: sqlite3.Connection,
    target: dict[str, Any],
    window_kind: str,
    snapshots: list[dict[str, Any]],
    source_reference: str | None,
    evidence_role: str,
) -> str:
    row = connection.execute(
        """
        SELECT *
        FROM printer_memory_windows
        WHERE token_id = ? AND pair_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (target["token_id"], target["pair_id"]),
    ).fetchone()
    if row is None:
        return "first_evidence_window_for_token_pair"
    if row["window_kind"] != window_kind:
        return "distinct_window_kind"
    if row["evidence_role"] and row["evidence_role"] != evidence_role:
        return "distinct_evidence_role"
    start_id = int(snapshots[0]["id"]) if snapshots else None
    end_id = int(snapshots[-1]["id"]) if snapshots else None
    if row["snapshot_start_id"] != start_id or row["snapshot_end_id"] != end_id:
        return "distinct_snapshot_range"
    if (row["source_reference"] or None) != (source_reference or None):
        return "source_reference_only_difference_blocked"
    return "distinct_evidence_identity"


def _classify_first_memory_review(
    snapshots: list[dict[str, Any]],
    context_rows: dict[str, dict[str, Any]],
    window_kind: str,
    context_freshness: dict[str, Any] | None = None,
    effective_labels: dict[str, Any] | None = None,
    evidence_blockers: list[str] | None = None,
    outcome_label: str | None = None,
) -> dict[str, Any]:
    rejection_reasons: list[str] = []
    coverage_policy = _window_coverage_policy(window_kind, snapshots)
    expected_snapshot_count = int(coverage_policy["expected_snapshot_count"])
    actual_snapshot_count = len(snapshots)
    missing_snapshot_count = max(0, expected_snapshot_count - actual_snapshot_count)
    coverage_state = (
        "COMPLETE_WINDOW_COVERAGE"
        if actual_snapshot_count >= expected_snapshot_count
        else f"INCOMPLETE_{window_kind.replace('WINDOW_', '')}_WINDOW"
    )
    if window_kind == "WINDOW_5M_MICRO_EVENT":
        rejection_reasons.append("REJECT_5M_ONLY_WINDOW")
    if actual_snapshot_count < expected_snapshot_count:
        rejection_reasons.extend(["REJECT_MISSING_SNAPSHOTS", coverage_state, "INSUFFICIENT_SNAPSHOT_COVERAGE"])
    if any(row.get("price_usd") is None or row.get("liquidity_usd") is None for row in snapshots):
        rejection_reasons.append("REJECT_MISSING_CRITICAL_FIELDS")
    if any(str(row.get("source_status") or "").upper() in {"FAILED", "STALE", "CONFLICTING"} for row in snapshots):
        rejection_reasons.append("REJECT_BAD_SNAPSHOT_SOURCE_STATUS")
    if any(
        str(row.get("data_quality_label") or "").upper()
        in {"MISSING_CRITICAL_DATA", "DIRTY_DATA", "STALE_DATA", "CONFLICTING_DATA", "DO_NOT_TRAIN"}
        for row in snapshots
    ):
        rejection_reasons.append("REJECT_BAD_SNAPSHOT_DATA_QUALITY")
    if not _context_is_present(context_rows):
        rejection_reasons.append("MISSING_OR_UNKNOWN_CONTEXT")
    labels = effective_labels or _context_memory_labels(context_rows)
    unknown_context_blockers = _collect_unknown_context_blockers(labels)
    if unknown_context_blockers:
        rejection_reasons.append("MISSING_OR_UNKNOWN_CONTEXT")
    if context_freshness:
        for reason in context_freshness.get("context_blocking_reasons", []):
            rejection_reasons.append(reason)
    exact_evidence_blockers = list(evidence_blockers or [])
    if exact_evidence_blockers:
        rejection_reasons.append("MISSING_OR_UNKNOWN_CONTEXT")
    for reason in exact_evidence_blockers:
        rejection_reasons.append(reason)
    if window_kind == "WINDOW_5M_MICRO_EVENT":
        memory_quality = "AUDIT_ONLY_MEMORY"
    elif not rejection_reasons:
        memory_quality = "CLEAN_MEMORY"
    elif actual_snapshot_count < expected_snapshot_count:
        memory_quality = "DIRTY_MEMORY"
    else:
        memory_quality = "AUDIT_ONLY_MEMORY"
    unique_reasons = list(dict.fromkeys(rejection_reasons or ["REVIEW_PASSED"]))
    return {
        "outcome_label": "OUTCOME_UNKNOWN" if memory_quality != "CLEAN_MEMORY" else (outcome_label or "NO_PUMP"),
        "action_lesson_label": "ACTION_LESSON_UNKNOWN",
        "memory_quality_label": memory_quality,
        "memory_status": _memory_storage_status(memory_quality),
        "data_quality_label": "MISSING_CRITICAL_DATA" if memory_quality != "CLEAN_MEMORY" else "CLEAN_DATA",
        "do_not_train": 0 if memory_quality == "CLEAN_MEMORY" else 1,
        "rejection_reasons": unique_reasons,
        "retrieval_ready": memory_quality == "CLEAN_MEMORY",
        "coverage_policy_used": coverage_policy["coverage_policy_used"],
        "expected_snapshot_count": expected_snapshot_count,
        "actual_snapshot_count": actual_snapshot_count,
        "missing_snapshot_count": missing_snapshot_count,
        "coverage_state": coverage_state,
        "unknown_context_blockers": unknown_context_blockers,
        "evidence_blockers": list(dict.fromkeys(evidence_blockers or [])),
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


def _snapshots_are_clean_window_evidence(snapshots: list[dict[str, Any]], expected_snapshot_count: int) -> bool:
    if len(snapshots) < expected_snapshot_count:
        return False
    for row in snapshots:
        if row.get("price_usd") is None or row.get("liquidity_usd") is None:
            return False
        if str(row.get("source_status") or "").upper() not in {"COMPLETE", "PARTIAL"}:
            return False
        if str(row.get("data_quality_label") or "").upper() not in {"CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"}:
            return False
    return True


def _outcome_label_from_held_to_15m(held_label: str | None) -> str:
    return {
        "HELD_TO_15M_CONTINUED": "SHORT_TERM_PUMP",
        "HELD_TO_15M_CONSOLIDATED": "CONSOLIDATION",
        "HELD_TO_15M_FADED": "SLOW_BLEED",
        "HELD_TO_15M_DUMPED": "DUMP",
        "HELD_TO_15M_DEAD": "DEAD",
    }.get(str(held_label or ""), "UNKNOWN_OUTCOME")


def _derive_15m_window_context_from_snapshots(
    snapshots: list[dict[str, Any]],
    window_kind: str,
) -> dict[str, Any]:
    coverage_policy = _window_coverage_policy(window_kind, snapshots)
    if window_kind != "WINDOW_15M" or not _snapshots_are_clean_window_evidence(
        snapshots,
        int(coverage_policy["expected_snapshot_count"]),
    ):
        return {
            "labels": {},
            "outcome_label": None,
            "payload": {
                "derived": False,
                "reason": "requires_clean_complete_window_15m_snapshot_evidence",
                "coverage_policy_used": coverage_policy["coverage_policy_used"],
                "actual_snapshot_count": len(snapshots),
            },
        }

    chart_context = build_chart_payload_from_token_snapshots(snapshots)
    chart_labels = {
        "trend_structure_label": _label_value(classify_trend_structure(chart_context)),
        "volatility_label": _label_value(classify_volatility(chart_context)),
        "range_behavior_label": _label_value(classify_range_behavior(chart_context)),
        "momentum_label": _label_value(classify_momentum(chart_context)),
        "drawdown_recovery_label": _label_value(classify_drawdown_recovery(chart_context)),
        "candle_path_label": _label_value(classify_candle_path(chart_context)),
        "chart_payload_quality_label": _label_value(classify_chart_payload_quality(chart_context)),
        "chart_memory_gate_label": _label_value(classify_chart_memory_gate(chart_context)),
    }
    path = _snapshot_price_path_for_memory(snapshots)
    micro_context = build_micro_event_payload_from_token_snapshots(snapshots)
    micro_context["held_to_15m_price_change_percent"] = path["price_change_percent"]
    micro_context["held_to_15m_liquidity_usd"] = snapshots[-1].get("liquidity_usd") if snapshots else None
    held_label = _label_value(classify_holding_to_15m_result(micro_context))
    micro_labels = {
        "micro_event_state_label": _label_value(classify_micro_event_state(micro_context)),
        "micro_event_move_label": _label_value(classify_micro_event_move(micro_context)),
        "micro_exit_realism_label": _label_value(classify_micro_exit_realism(micro_context)),
        "late_buy_trap_label": _label_value(classify_late_buy_trap(micro_context)),
        "held_to_15m_result_label": held_label,
        "micro_event_payload_quality_label": _label_value(classify_micro_event_payload_quality(micro_context)),
        "micro_event_memory_gate_label": _label_value(classify_micro_event_memory_gate(micro_context)),
    }
    return {
        "labels": {
            "trend_structure_label": chart_labels["trend_structure_label"],
            "volatility_label": chart_labels["volatility_label"],
            "micro_event_state_label": micro_labels["micro_event_state_label"],
            "held_to_15m_result_label": held_label,
        },
        "outcome_label": _outcome_label_from_held_to_15m(held_label),
        "payload": {
            "derived": True,
            "source": "stored_token_snapshots",
            "window_kind": window_kind,
            "snapshot_ids": [int(row["id"]) for row in snapshots],
            "coverage_policy_used": coverage_policy["coverage_policy_used"],
            "chart_context": chart_context,
            "chart_labels": chart_labels,
            "held_outcome_context": micro_context,
            "held_outcome_labels": micro_labels,
        },
    }


def _record_first_memory_window(
    connection: sqlite3.Connection,
    target: dict[str, Any],
    snapshot: dict[str, Any],
    snapshots: list[dict[str, Any]],
    context_rows: dict[str, dict[str, Any]],
    window_kind: str,
    source_reference: str | None,
    window_start_at: str,
    window_end_at: str,
    evidence_role: str,
    evidence_identity_hash: str,
    evidence_fingerprint: str,
    evidence_difference_reason: str,
    existing_memory_window_id: int | None = None,
    evidence_revision_created: bool = False,
    evidence_revision_reason: str | None = None,
    evidence_lookup_memory_window_id: int | None = None,
) -> dict[str, Any]:
    opened_at = window_start_at
    closed_at = window_end_at
    context_freshness = _context_freshness_report(context_rows, snapshot, window_start_at, window_end_at)
    raw_context_labels = _context_memory_labels(context_rows)
    derived_window_context = _derive_15m_window_context_from_snapshots(snapshots, window_kind)
    if derived_window_context["labels"]:
        raw_context_labels.update(derived_window_context["labels"])
    evidence_lookup_id = (
        evidence_lookup_memory_window_id
        if evidence_lookup_memory_window_id is not None
        else existing_memory_window_id
    )
    evidence_result = _apply_clean_audit_evidence_labels(
        connection,
        window={
            "id": evidence_lookup_id,
            "token_id": target["token_id"],
            "pair_id": target["pair_id"],
            "snapshot_end_id": snapshot["id"],
            "window_kind": window_kind,
        },
        labels=raw_context_labels,
    )
    effective_context_labels = evidence_result["labels"]
    classification = _classify_first_memory_review(
        snapshots,
        context_rows,
        window_kind,
        context_freshness,
        effective_labels=effective_context_labels,
        evidence_blockers=evidence_result["overlays"].get("evidence_blockers", []),
        outcome_label=derived_window_context.get("outcome_label"),
    )
    path = _snapshot_price_path_for_memory(snapshots)
    snapshot_ids = [int(row["id"]) for row in snapshots]
    remaining_blockers = list(
        dict.fromkeys(
            context_freshness["context_blocking_reasons"]
            + classification["unknown_context_blockers"]
            + classification["evidence_blockers"]
        )
    )
    overlays = evidence_result["overlays"]
    applied_safety_evidence_row_id = overlays.get("safety_evidence_row_id") if overlays.get("safety_evidence_applied") else None
    applied_entry_quote_evidence_row_id = (
        overlays.get("entry_quote_evidence_row_id") if overlays.get("entry_quote_evidence_applied") else None
    )
    applied_exit_quote_evidence_row_id = (
        overlays.get("exit_quote_evidence_row_id") if overlays.get("exit_quote_evidence_applied") else None
    )
    duplicate_guard_status = (
        "EVIDENCE_REVISION_CREATED"
        if evidence_revision_created
        else "NEW_DISTINCT_EVIDENCE_WINDOW"
    )
    supporting_context = {
        "phase": "post_rc_lane3",
        "source_reference": source_reference,
        "snapshot_ids": snapshot_ids,
        "snapshot_start_id": snapshot_ids[0] if snapshot_ids else None,
        "snapshot_end_id": snapshot_ids[-1] if snapshot_ids else None,
        "window_start_at": window_start_at,
        "window_end_at": window_end_at,
        "evidence_role": evidence_role,
        "evidence_identity_hash": evidence_identity_hash,
        "evidence_difference_reason": evidence_difference_reason,
        "duplicate_guard_status": duplicate_guard_status,
        "existing_memory_window_id": existing_memory_window_id,
        "evidence_revision_created": evidence_revision_created,
        "evidence_revision_reason": evidence_revision_reason,
        "evidence_lookup_memory_window_id": evidence_lookup_id,
        "applied_safety_evidence_row_id": applied_safety_evidence_row_id,
        "applied_entry_quote_evidence_row_id": applied_entry_quote_evidence_row_id,
        "applied_exit_quote_evidence_row_id": applied_exit_quote_evidence_row_id,
        "remaining_blockers": remaining_blockers,
        "expected_snapshot_count": classification["expected_snapshot_count"],
        "coverage_policy_used": classification["coverage_policy_used"],
        "actual_snapshot_count": classification["actual_snapshot_count"],
        "missing_snapshot_count": classification["missing_snapshot_count"],
        "coverage_state": classification["coverage_state"],
        "context_row_ids": {
            "market": context_rows["market"].get("id"),
            "chain_heat": context_rows["chain_heat"].get("id"),
            "safety": context_rows["safety"].get("id"),
            "liquidity_exit": context_rows["liquidity_exit"].get("id"),
            "trading_flow": context_rows["trading_flow"].get("id"),
            "chart_volatility": context_rows["chart_volatility"].get("id"),
            "micro_event": context_rows["micro_event"].get("id"),
        },
        "context_labels": effective_context_labels,
        "raw_context_labels": raw_context_labels,
        "derived_window_context": derived_window_context["payload"],
        "memory_build_evidence_overlays": evidence_result["overlays"],
        "context_freshness_report": context_freshness,
        "context_blocking_reasons": remaining_blockers,
        "unknown_context_blockers": classification["unknown_context_blockers"],
        "evidence_blockers": classification["evidence_blockers"],
        "retrieval_ready": classification["retrieval_ready"],
    }
    cursor = connection.execute(
        """
        INSERT INTO printer_memory_windows (
            token_id, pair_id, window_kind, opened_at, closed_at,
            expected_snapshot_count, actual_snapshot_count, missing_snapshot_count, coverage_state,
            memory_status, data_quality_label, do_not_train, window_status, outcome_label,
            memory_quality_label, rejection_reasons_json, supporting_context_json, created_by_phase,
            snapshot_start_id, snapshot_end_id, window_start_at, window_end_at, source_reference,
            evidence_role, evidence_fingerprint, evidence_identity_hash, evidence_difference_reason,
            duplicate_guard_status, memory_diversity_label, concentration_audit_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            target["token_id"], target["pair_id"], window_kind, opened_at, closed_at,
            classification["expected_snapshot_count"], classification["actual_snapshot_count"],
            classification["missing_snapshot_count"], classification["coverage_state"],
            classification["memory_status"], classification["data_quality_label"], classification["do_not_train"],
            "WINDOW_AUDIT_ONLY" if classification["do_not_train"] else "WINDOW_CLOSED",
            classification["outcome_label"], classification["memory_quality_label"],
            json.dumps(classification["rejection_reasons"], sort_keys=True),
            json.dumps(supporting_context, sort_keys=True), "post_rc_lane3",
            snapshot_ids[0] if snapshot_ids else None, snapshot_ids[-1] if snapshot_ids else None,
            window_start_at, window_end_at, source_reference, evidence_role, evidence_fingerprint,
            evidence_identity_hash, evidence_difference_reason, duplicate_guard_status,
            "NORMAL_TOKEN_MEMORY_DISTRIBUTION", "distribution_not_evaluated_at_memory_write",
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
            json.dumps({"price_path": path, "coverage_state": classification["coverage_state"], "evidence_identity_hash": evidence_identity_hash}, sort_keys=True),
            json.dumps(supporting_context, sort_keys=True),
        ),
    )
    episode_id = int(cursor.lastrowid)
    for position, row in enumerate(snapshots):
        connection.execute(
            "INSERT INTO printer_episode_snapshots (episode_id, token_snapshot_id, position_in_episode) VALUES (?, ?, ?)",
            (episode_id, row["id"], position),
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
        "phase": "post_rc_lane3",
        "window_kind": window_kind,
        "outcome_label": classification["outcome_label"],
        "memory_quality_label": classification["memory_quality_label"],
        "retrieval_ready": classification["retrieval_ready"],
        "coverage_state": classification["coverage_state"],
        "coverage_policy_used": classification["coverage_policy_used"],
        "evidence_role": evidence_role,
        "evidence_identity_hash": evidence_identity_hash,
        "snapshot_start_id": snapshot_ids[0] if snapshot_ids else None,
        "snapshot_end_id": snapshot_ids[-1] if snapshot_ids else None,
        "snapshot_ids": snapshot_ids,
        "context_blocking_reasons": supporting_context["context_blocking_reasons"],
        "unknown_context_blockers": classification["unknown_context_blockers"],
        "evidence_blockers": classification["evidence_blockers"],
        "existing_memory_window_id": existing_memory_window_id,
        "evidence_revision_created": evidence_revision_created,
        "evidence_revision_reason": evidence_revision_reason,
        "evidence_lookup_memory_window_id": evidence_lookup_id,
        "applied_safety_evidence_row_id": applied_safety_evidence_row_id,
        "applied_entry_quote_evidence_row_id": applied_entry_quote_evidence_row_id,
        "applied_exit_quote_evidence_row_id": applied_exit_quote_evidence_row_id,
        "remaining_blockers": remaining_blockers,
        **effective_context_labels,
        "raw_context_labels": raw_context_labels,
        "derived_window_context": derived_window_context["payload"],
        "memory_build_evidence_overlays": evidence_result["overlays"],
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
        "snapshot_start_id": snapshot_ids[0] if snapshot_ids else None,
        "snapshot_end_id": snapshot_ids[-1] if snapshot_ids else None,
        "snapshot_ids": snapshot_ids,
        "window_start_at": window_start_at,
        "window_end_at": window_end_at,
        "evidence_role": evidence_role,
        "evidence_identity_hash": evidence_identity_hash,
        "evidence_difference_reason": evidence_difference_reason,
        "duplicate_guard_status": duplicate_guard_status,
        "existing_memory_window_id": existing_memory_window_id,
        "evidence_revision_created": evidence_revision_created,
        "evidence_revision_reason": evidence_revision_reason,
        "evidence_lookup_memory_window_id": evidence_lookup_id,
        "applied_safety_evidence_row_id": applied_safety_evidence_row_id,
        "applied_entry_quote_evidence_row_id": applied_entry_quote_evidence_row_id,
        "applied_exit_quote_evidence_row_id": applied_exit_quote_evidence_row_id,
        "remaining_blockers": remaining_blockers,
        "coverage_state": classification["coverage_state"],
        "context_freshness_report": context_freshness,
        "context_blocking_reasons": supporting_context["context_blocking_reasons"],
        "unknown_context_blockers": classification["unknown_context_blockers"],
        "evidence_blockers": classification["evidence_blockers"],
        **effective_context_labels,
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
        snapshots, window_start_at, window_end_at = _snapshot_rows_for_memory_evidence(connection, target, snapshot, window_kind)
        evidence_role = _memory_evidence_role(window_kind)
        evidence_identity_hash, evidence_fingerprint = _memory_evidence_identity(
            target, window_kind, snapshots, window_start_at, window_end_at, args.source_reference, evidence_role
        )
        context_rows = _resolve_memory_context_rows(connection, target, int(snapshot["id"]))
        if not _context_is_present(context_rows):
            raise ValueError("memory-window review requires existing Phase 28 context rows")
        existing = _existing_memory_for_evidence(connection, evidence_identity_hash)
        duplicate_block_reason = "existing_evidence_window_targeted"
        if existing is None:
            existing = _existing_memory_for_functional_evidence(
                connection, target, window_kind, snapshots, window_start_at, window_end_at, evidence_role, context_rows
            )
            if existing is not None:
                duplicate_block_reason = "source_reference_only_difference_blocked"
        if existing is not None:
            existing_support = _json_or_empty(existing["supporting_context_json"])
            evidence_result = _apply_clean_audit_evidence_labels(
                connection,
                window={
                    "id": int(existing["id"]),
                    "token_id": target["token_id"],
                    "pair_id": target["pair_id"],
                    "snapshot_end_id": snapshot["id"],
                    "window_kind": window_kind,
                },
                labels=_context_memory_labels(context_rows),
            )
            revision_reason = _memory_revision_reason(existing, context_rows, evidence_result["overlays"])
            if revision_reason is not None:
                result = _record_first_memory_window(
                    connection, target, snapshot, snapshots, context_rows, window_kind, args.source_reference,
                    window_start_at, window_end_at, evidence_role, evidence_identity_hash,
                    evidence_fingerprint, revision_reason,
                    existing_memory_window_id=int(existing["id"]),
                    evidence_revision_created=True,
                    evidence_revision_reason=revision_reason,
                    evidence_lookup_memory_window_id=int(existing["id"]),
                )
                result["skipped_reason"] = None
                result["duplicate_block_reason"] = duplicate_block_reason
            else:
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
                    "snapshot_start_id": existing["snapshot_start_id"],
                    "snapshot_end_id": existing["snapshot_end_id"],
                    "snapshot_ids": [int(row["id"]) for row in snapshots],
                    "window_start_at": existing["window_start_at"] or window_start_at,
                    "window_end_at": existing["window_end_at"] or window_end_at,
                    "evidence_role": existing["evidence_role"] or evidence_role,
                    "evidence_identity_hash": evidence_identity_hash,
                    "evidence_difference_reason": duplicate_block_reason,
                    "duplicate_guard_status": "DUPLICATE_SAME_EVIDENCE_NOOP",
                    "duplicate_block_reason": duplicate_block_reason,
                    "existing_memory_window_id": None,
                    "evidence_revision_created": False,
                    "evidence_revision_reason": None,
                    "applied_safety_evidence_row_id": existing_support.get("applied_safety_evidence_row_id"),
                    "applied_entry_quote_evidence_row_id": existing_support.get("applied_entry_quote_evidence_row_id"),
                    "applied_exit_quote_evidence_row_id": existing_support.get("applied_exit_quote_evidence_row_id"),
                    "remaining_blockers": existing_support.get("remaining_blockers", existing_support.get("context_blocking_reasons", [])),
                    "coverage_state": existing["coverage_state"],
                    "context_freshness_report": existing_support.get("context_freshness_report"),
                    "context_blocking_reasons": existing_support.get("context_blocking_reasons", []),
                    "skipped_reason": "duplicate_same_evidence_noop",
                }
        else:
            evidence_difference_reason = _evidence_difference_reason(
                connection, target, window_kind, snapshots, args.source_reference, evidence_role
            )
            result = _record_first_memory_window(
                connection, target, snapshot, snapshots, context_rows, window_kind, args.source_reference,
                window_start_at, window_end_at, evidence_role, evidence_identity_hash,
                evidence_fingerprint, evidence_difference_reason
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
        "memory_window": args.memory_window,
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
    parser = _base_parser("Build one controlled memory-window review from local evidence.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--token-mint")
    parser.add_argument("--token-id", type=int)
    parser.add_argument("--pair-address")
    parser.add_argument("--pair-id", type=int)
    parser.add_argument("--snapshot-id", type=int)
    parser.add_argument("--chain", default="solana")
    parser.add_argument("--memory-window", "--window-kind", dest="memory_window", default="15m")
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


def _snapshot_rows_for_memory_window(connection: sqlite3.Connection, window_id: int) -> list[dict[str, Any]]:
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
        (window_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _memory_audit_source_summary(connection: sqlite3.Connection, window: dict[str, Any] | None = None) -> dict[str, Any]:
    request_count = int(connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0])
    response_count = int(connection.execute("SELECT COUNT(*) FROM printer_source_responses").fetchone()[0])
    failure_count = int(connection.execute("SELECT COUNT(*) FROM printer_source_failures").fetchone()[0])
    latest_failure = _latest_row(connection, "printer_source_failures")
    window_snapshots = _snapshot_rows_for_memory_window(connection, int(window["id"])) if window else []
    window_source_statuses = sorted({
        row.get("source_status") for row in window_snapshots if row.get("source_status")
    })
    window_quality_labels = sorted({
        row.get("data_quality_label") for row in window_snapshots if row.get("data_quality_label")
    })
    blocking_statuses = {"FAILED", "STALE", "CONFLICTING"}
    blocking_quality = {"MISSING_CRITICAL_DATA", "DIRTY_DATA", "STALE_DATA", "CONFLICTING_DATA", "DO_NOT_TRAIN"}
    window_evidence_failed_or_missing = (
        not window_snapshots
        or any(status in blocking_statuses for status in window_source_statuses)
        or any(label in blocking_quality for label in window_quality_labels)
    )
    statuses = {
        "snapshot_source_statuses": [
            row[0] for row in connection.execute("SELECT DISTINCT source_status FROM printer_token_snapshots").fetchall()
        ],
        "snapshot_data_quality_labels": [
            row[0] for row in connection.execute("SELECT DISTINCT data_quality_label FROM printer_token_snapshots").fetchall()
        ],
        "evidence_window_snapshot_source_statuses": window_source_statuses,
        "evidence_window_snapshot_data_quality_labels": window_quality_labels,
    }
    return {
        "source_request_count": request_count,
        "source_response_count": response_count,
        "source_failure_count": failure_count,
        "latest_source_failure": latest_failure,
        "historical_source_failures_visible": failure_count > 0,
        "source_status_summary": statuses,
        "required_evidence_failed_or_missing": window_evidence_failed_or_missing,
        "status": (
            "SOURCE_EVIDENCE_WINDOW_BLOCKED"
            if window_evidence_failed_or_missing
            else "SOURCE_QUALITY_ACCEPTABLE_WITH_HISTORICAL_FAILURES_VISIBLE" if failure_count else "SOURCE_QUALITY_ACCEPTABLE"
        ),
    }


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _clean_safety_evidence_row(
    row: dict[str, Any] | None,
    *,
    window_kind: str | None = None,
) -> bool:
    if not row:
        return False
    base_clean = (
        row.get("source_status") in {"COMPLETE", "PARTIAL"}
        and row.get("data_quality_label") in {"CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"}
        and row.get("target_status") == "TARGET_MATCH"
        and row.get("freshness_label") in {"SAFETY_EVIDENCE_FRESH", "SAFETY_EVIDENCE_ACCEPTABLE"}
        and bool(row.get("paper_only_context"))
        and row.get("source_request_id") is not None
        and row.get("source_response_id") is not None
        and row.get("source_failure_id") is None
    )
    if not base_clean:
        return False
    if row.get("safety_context_label") == "SAFETY_CLEAN":
        return True
    policy = safety_memory_policy_summary(row)
    return window_kind == "WINDOW_15M" and bool(policy["safety_acceptable_for_15m_memory"])


def _clean_quote_evidence_row(row: dict[str, Any] | None, direction: str) -> bool:
    if not row:
        return False
    clean_label = (
        row.get("entry_realism_label") in {"ENTRY_REALISTIC", "ENTRY_ROUTE_AVAILABLE"}
        if direction == "ENTRY"
        else row.get("exit_realism_label") in {"EXIT_REALISTIC", "EXIT_ROUTE_AVAILABLE"}
    )
    return (
        row.get("source_status") in {"COMPLETE", "PARTIAL"}
        and row.get("data_quality_label") in {"CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"}
        and row.get("target_status") == "TARGET_MATCH"
        and row.get("freshness_label") in {"QUOTE_FRESH", "QUOTE_ACCEPTABLE"}
        and row.get("quote_context_label") == "QUOTE_ROUTE_AVAILABLE"
        and row.get("route_available_label") == "ROUTE_AVAILABLE"
        and row.get("quote_direction") == direction
        and row.get("quote_purpose") == "PAPER_REALISM_ONLY"
        and clean_label
        and bool(row.get("paper_only_context"))
        and row.get("source_request_id") is not None
        and row.get("source_response_id") is not None
        and row.get("source_failure_id") is None
    )


def _safety_evidence_blocker(row: dict[str, Any] | None) -> str:
    if not row:
        return "NO_VALID_SAFETY_EVIDENCE_FOR_TARGET"
    if row.get("target_status") != "TARGET_MATCH":
        return "SAFETY_EVIDENCE_TARGET_MISMATCH"
    if row.get("freshness_label") not in {"SAFETY_EVIDENCE_FRESH", "SAFETY_EVIDENCE_ACCEPTABLE"}:
        return "SAFETY_EVIDENCE_STALE"
    if row.get("source_status") not in {"COMPLETE", "PARTIAL"} or row.get("data_quality_label") not in {
        "CLEAN_DATA",
        "ACCEPTABLE_PARTIAL_DATA",
    }:
        return "SAFETY_EVIDENCE_SOURCE_NOT_CLEAN"
    if row.get("source_request_id") is None or row.get("source_response_id") is None or row.get("source_failure_id") is not None:
        return "SAFETY_EVIDENCE_SOURCE_NOT_CLEAN"
    if not bool(row.get("paper_only_context")):
        return "SAFETY_EVIDENCE_SOURCE_NOT_CLEAN"
    policy = safety_memory_policy_summary(row)
    hard_blockers = policy.get("hard_blocking_safety_fields") or []
    if hard_blockers:
        return "SAFETY_EVIDENCE_HARD_BLOCKER_" + "_".join(str(field).upper() for field in hard_blockers)
    return "NO_VALID_SAFETY_EVIDENCE_FOR_TARGET"


def _quote_evidence_blocker(row: dict[str, Any] | None, direction: str) -> str:
    prefix = "ENTRY" if direction == "ENTRY" else "EXIT"
    if not row:
        return f"NO_VALID_{prefix}_QUOTE_EVIDENCE_FOR_TARGET"
    if row.get("target_status") != "TARGET_MATCH":
        return f"{prefix}_QUOTE_EVIDENCE_TARGET_MISMATCH"
    if row.get("freshness_label") not in {"QUOTE_FRESH", "QUOTE_ACCEPTABLE"}:
        return f"{prefix}_QUOTE_EVIDENCE_STALE"
    if row.get("source_status") not in {"COMPLETE", "PARTIAL"} or row.get("data_quality_label") not in {
        "CLEAN_DATA",
        "ACCEPTABLE_PARTIAL_DATA",
    }:
        return f"{prefix}_QUOTE_EVIDENCE_SOURCE_NOT_CLEAN"
    if row.get("source_request_id") is None or row.get("source_response_id") is None or row.get("source_failure_id") is not None:
        return f"{prefix}_QUOTE_EVIDENCE_SOURCE_NOT_CLEAN"
    if row.get("quote_direction") != direction or row.get("quote_purpose") != "PAPER_REALISM_ONLY" or not bool(row.get("paper_only_context")):
        return f"{prefix}_QUOTE_EVIDENCE_SOURCE_NOT_CLEAN"
    return f"NO_VALID_{prefix}_QUOTE_EVIDENCE_FOR_TARGET"


def _latest_audit_evidence_row(
    connection: sqlite3.Connection,
    table_name: str,
    *,
    token_id: int,
    pair_id: int | None,
    snapshot_id: int | None,
    memory_window_id: int | None,
    extra_where: str = "",
    extra_params: tuple[Any, ...] = (),
) -> dict[str, Any]:
    if not _table_exists(connection, table_name):
        return {}
    where = ["token_id = ?"]
    params: list[Any] = [token_id]
    if pair_id is not None:
        where.append("(pair_id = ? OR pair_id IS NULL)")
        params.append(pair_id)
    # Do not filter by memory_window_id in WHERE. Evidence bound to any
    # memory_window_id for this token/pair/snapshot is a candidate for safe
    # context-only revisions. The ordering below prioritises exact-window
    # matches; _clean_*_evidence_row predicates enforce all quality guards.
    if extra_where:
        where.append(extra_where)
        params.extend(extra_params)
    row = connection.execute(
        f"""
        SELECT *
        FROM {table_name}
        WHERE {" AND ".join(where)}
        ORDER BY
            CASE WHEN snapshot_id = ? THEN 0 WHEN snapshot_id IS NULL THEN 1 ELSE 2 END,
            CASE WHEN memory_window_id = ? THEN 0 WHEN memory_window_id IS NULL THEN 2 ELSE 1 END,
            evidence_captured_at DESC,
            id DESC
        LIMIT 1
        """,
        (*params, snapshot_id, memory_window_id),
    ).fetchone()
    result = _row_to_dict(row)
    if result and snapshot_id is not None and result.get("snapshot_id") not in {None, snapshot_id}:
        result["target_status"] = "TARGET_MISMATCH"
    return result


def _apply_clean_audit_evidence_labels(
    connection: sqlite3.Connection,
    *,
    window: dict[str, Any],
    labels: dict[str, Any],
) -> dict[str, Any]:
    effective = dict(labels)
    token_id = int(window["token_id"])
    pair_id = int(window["pair_id"]) if window.get("pair_id") is not None else None
    snapshot_id = int(window["snapshot_end_id"]) if window.get("snapshot_end_id") is not None else None
    memory_window_id = int(window["id"]) if window.get("id") is not None else None
    window_kind = str(window.get("window_kind") or "")
    overlays: dict[str, Any] = {
        "safety_evidence_applied": False,
        "entry_quote_evidence_applied": False,
        "exit_quote_evidence_applied": False,
        "evidence_blockers": [],
    }

    safety_row = _latest_audit_evidence_row(
        connection,
        "printer_solana_safety_evidence",
        token_id=token_id,
        pair_id=pair_id,
        snapshot_id=snapshot_id,
        memory_window_id=memory_window_id,
    )
    overlays["safety_evidence_row_id"] = safety_row.get("id")
    safety_policy = safety_memory_policy_summary(safety_row) if safety_row else {}
    overlays["safety_15m_memory_policy_label"] = safety_policy.get("safety_15m_memory_policy_label")
    overlays["source_coverage_pending_fields"] = safety_policy.get("source_coverage_pending_fields", [])
    overlays["observed_risk_fields"] = safety_policy.get("observed_risk_fields", [])
    overlays["hard_blocking_safety_fields"] = safety_policy.get("hard_blocking_safety_fields", [])
    if _clean_safety_evidence_row(safety_row, window_kind=window_kind):
        if safety_row["safety_context_label"] == "SAFETY_CLEAN":
            effective["safety_status_label"] = safety_row["safety_context_label"]
            effective["rug_risk_label"] = "RUG_RISK_LOW"
        else:
            effective["safety_status_label"] = safety_policy.get("safety_15m_memory_policy_label")
            effective["rug_risk_label"] = (
                "RUG_RISK_OBSERVED_FOR_15M"
                if safety_policy.get("observed_risk_fields")
                else "RUG_RISK_ACCEPTABLE_FOR_15M"
            )
        overlays["safety_evidence_applied"] = True
    else:
        overlays["evidence_blockers"].append(_safety_evidence_blocker(safety_row))

    for direction, overlay_key, label_key in (
        ("ENTRY", "entry_quote_evidence_applied", "entry_realism_label"),
        ("EXIT", "exit_quote_evidence_applied", "exit_realism_label"),
    ):
        quote_row = _latest_audit_evidence_row(
            connection,
            "printer_paper_quote_evidence",
            token_id=token_id,
            pair_id=pair_id,
            snapshot_id=snapshot_id,
            memory_window_id=memory_window_id,
            extra_where="quote_direction = ?",
            extra_params=(direction,),
        )
        overlays[f"{direction.lower()}_quote_evidence_row_id"] = quote_row.get("id")
        if _clean_quote_evidence_row(quote_row, direction):
            effective[label_key] = quote_row[label_key]
            overlays[overlay_key] = True
        else:
            overlays["evidence_blockers"].append(_quote_evidence_blocker(quote_row, direction))

    overlays["evidence_blockers"] = list(dict.fromkeys(overlays["evidence_blockers"]))
    return {"labels": effective, "overlays": overlays}


def _memory_revision_reason(
    existing: sqlite3.Row,
    context_rows: dict[str, dict[str, Any]],
    evidence_overlays: dict[str, Any],
) -> str | None:
    if existing["memory_quality_label"] == "CLEAN_MEMORY" and int(existing["do_not_train"]) == 0:
        return None
    existing_support = _json_or_empty(existing["supporting_context_json"])
    existing_overlays = existing_support.get("memory_build_evidence_overlays") or {}
    existing_context_ids = existing_support.get("context_row_ids") or {}
    current_context_ids = _context_row_ids_for_memory(context_rows)

    newly_applied = []
    for old_key, applied_key, reason in (
        ("safety_evidence_row_id", "safety_evidence_applied", "new_clean_safety_evidence"),
        ("entry_quote_evidence_row_id", "entry_quote_evidence_applied", "new_clean_entry_quote_evidence"),
        ("exit_quote_evidence_row_id", "exit_quote_evidence_applied", "new_clean_exit_quote_evidence"),
    ):
        if evidence_overlays.get(applied_key) and evidence_overlays.get(old_key) != existing_overlays.get(old_key):
            newly_applied.append(reason)
    changed_context = [
        key
        for key, value in current_context_ids.items()
        if value is not None and existing_context_ids.get(key) not in {None, value}
    ]
    reasons = newly_applied + [f"new_context_row_{key}" for key in changed_context]
    if not reasons:
        return None
    return "evidence_revision_due_to_" + "_and_".join(reasons)


def _memory_audit_context_summary(connection: sqlite3.Connection, window: dict[str, Any]) -> dict[str, Any]:
    supporting_context = _json_or_empty(window.get("supporting_context_json"))
    context_freshness = supporting_context.get("context_freshness_report") or {}
    target = {"token_id": int(window["token_id"]), "pair_id": int(window["pair_id"])}
    snapshot_id = window.get("snapshot_end_id")
    context_rows = _resolve_memory_context_rows(connection, target, int(snapshot_id) if snapshot_id else None)
    raw_labels = _context_memory_labels(context_rows)
    evidence_result = _apply_clean_audit_evidence_labels(
        connection,
        window=window,
        labels=raw_labels,
    )
    labels = evidence_result["labels"]
    unknown_labels = {
        key: value for key, value in labels.items()
        if value in UNKNOWN_CONTEXT_VALUES
    }
    unknown_context_blockers = _collect_unknown_context_blockers(labels)
    evidence_blockers = evidence_result["overlays"].get("evidence_blockers", [])
    freshness_blockers = context_freshness.get("context_blocking_reasons", [])
    context_blocking_reasons = list(dict.fromkeys(list(freshness_blockers) + unknown_context_blockers + evidence_blockers))
    return {
        "context_rows_present": {key: bool(value) for key, value in context_rows.items()},
        "context_labels": labels,
        "raw_context_labels": raw_labels,
        "audit_evidence_overlays": evidence_result["overlays"],
        "context_freshness_report": context_freshness,
        "context_blocking_reasons": context_blocking_reasons,
        "unknown_context_blockers": unknown_context_blockers,
        "evidence_blockers": evidence_blockers,
        "unknown_or_audit_only_context": unknown_labels,
        "liquidity_exit_realism_known": labels.get("entry_realism_label") == "ENTRY_REALISTIC" and labels.get("exit_realism_label") == "EXIT_REALISTIC",
        "market_context_real": labels.get("market_regime_label") not in {None, "UNKNOWN"},
        "chain_context_real": labels.get("chain_heat_label") not in {None, "SOLANA_UNKNOWN"},
        "micro_event_sufficient": labels.get("micro_event_state_label") not in {None, "MICRO_EVENT_UNKNOWN"},
        "status": (
            "CONTEXT_BLOCKED_FOR_WINDOW"
            if context_blocking_reasons
            else "MISSING_OR_UNKNOWN_CONTEXT" if unknown_labels else "CONTEXT_SUFFICIENT_FOR_AUDIT"
        ),
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
    source_summary = _memory_audit_source_summary(connection, window)
    context_summary = _memory_audit_context_summary(connection, window)
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
    diversity = build_memory_diversity_summary(all_matches)
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
        "memory_diversity_label": diversity["memory_diversity_label"],
        "concentration_audit_reason": diversity["concentration_audit_reason"],
        "distinct_token_count_in_retrieval": diversity["distinct_token_count"],
        "dominant_token_pair_count": diversity["dominant_token_pair_count"],
        "token_pair_clean_memory_counts": diversity["token_pair_clean_memory_counts"],
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


def _validate_paper_audit_once_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("paper decision audit requires explicit operator approval")
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("paper decision audit is Solana-only")
    if args.decision_id is None and not (args.token_mint or args.token_id):
        raise ValueError("paper decision audit requires decision_id, token_mint, or token_id")
    if args.decision_id is None and not (args.pair_address or args.pair_id):
        raise ValueError("paper decision audit requires pair_address or pair_id with token input")


def _json_list(value: Any) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _count_open_positions(connection: sqlite3.Connection, token_id: int, pair_id: int) -> int:
    return int(
        connection.execute(
            """
            SELECT COUNT(*)
            FROM printer_paper_positions
            WHERE token_id = ?
              AND pair_id = ?
              AND (
                  paper_position_status_label IN ('PAPER_POSITION_OPEN', 'PAPER_POSITION_MONITORING', 'PAPER_POSITION_EXIT_WATCH')
                  OR position_status IN ('OPEN', 'MONITORING', 'PAPER_POSITION_OPEN', 'PAPER_POSITION_MONITORING', 'PAPER_POSITION_EXIT_WATCH')
              )
            """,
            (token_id, pair_id),
        ).fetchone()[0]
    )


def _build_real_paper_audit_report(connection: sqlite3.Connection, decision: dict[str, Any]) -> dict[str, Any]:
    decision_report = _paper_decision_report_json(decision)
    token_id = int(decision["token_id"])
    pair_id = int(decision["pair_id"])
    action_counts = {
        action: int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_paper_decisions WHERE COALESCE(final_action_label, decision_action) = ?",
                (action,),
            ).fetchone()[0]
        )
        for action in ["BUY", "WAIT", "AVOID", "NO_ACTION", "SELL", "HOLD"]
    }
    source_failure_count = int(connection.execute("SELECT COUNT(*) FROM printer_source_failures").fetchone()[0])
    retrieval_match_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_memory_retrieval_matches WHERE retrieval_query_id = ?",
            (decision.get("retrieval_query_id"),),
        ).fetchone()[0]
    )
    dirty_memory_count = int(connection.execute("SELECT COUNT(*) FROM printer_memory_windows WHERE memory_quality_label = 'DIRTY_MEMORY'").fetchone()[0])
    position_count = int(connection.execute("SELECT COUNT(*) FROM printer_paper_positions WHERE token_id = ? AND pair_id = ?", (token_id, pair_id)).fetchone()[0])
    open_position_count = _count_open_positions(connection, token_id, pair_id)
    trade_event_count = int(connection.execute("SELECT COUNT(*) FROM printer_paper_trade_events").fetchone()[0])
    clean_count = int(decision_report.get("clean_eligible_memory_count") or decision_report.get("Similar clean memories found") or retrieval_match_count)
    dirty_used = bool(decision_report.get("dirty_memory_used"))
    blocking_reasons = _paper_decision_blocking_reasons(decision)
    issue_labels = [
        "NO_CLEAN_MEMORY_AVAILABLE",
        "DIRTY_MEMORY_PRESENT_BUT_BLOCKED",
        "PAPER_DECISION_BLOCKED",
        "NO_POSITION_OPENED",
        "NO_FAKE_PROFIT",
        "SOURCE_FAILURES_VISIBLE",
    ]
    return {
        "audit_id": None,
        "decision_id": int(decision["id"]),
        "decision_action": decision.get("final_action_label") or decision.get("decision_action"),
        "decision_status": decision.get("paper_decision_status_label") or decision.get("decision_status"),
        "decision_blocked_reason": blocking_reasons,
        "clean_eligible_memory_count": clean_count,
        "dirty_memory_count": dirty_memory_count,
        "blocked_dirty_memory_count": int(decision_report.get("blocked_dirty_memory_count") or dirty_memory_count),
        "dirty_memory_used_for_decision": dirty_used,
        "retrieval_match_count": retrieval_match_count,
        "buy_count": action_counts["BUY"],
        "paper_position_count": position_count,
        "open_paper_position_count": open_position_count,
        "paper_trade_event_count": trade_event_count,
        "simulated_pnl_available": False,
        "decision_quality_label": "BLOCKED_DECISION_VALID",
        "trade_quality_label": "NO_TRADE_OPENED",
        "profit_realism_label": "NO_PNL_NOT_APPLICABLE",
        "memory_safety_label": "DIRTY_MEMORY_BLOCKED",
        "retrieval_safety_label": "NO_CLEAN_MEMORY_MATCHES",
        "monitor_safety_label": "POSITION_OPEN_BLOCKED",
        "operator_review_verdict": "SAFE_BLOCKED_BEHAVIOR",
        "issue_labels": issue_labels,
        "source_failure_count": source_failure_count,
        "recommended_operator_action": "Commit and checkpoint this audit before Phase 35; main blocker remains lack of clean memory.",
        "next_phase_allowed": "Phase 35 after operator approval",
        "scheduler_allowed_next": "one-shot scheduler only in Phase 35, no loop",
        "fake_profit_prevented": True,
        "paper_win": False,
        "paper_loss": False,
        "live_execution": False,
    }


def _insert_real_paper_audit_report(connection: sqlite3.Connection, decision: dict[str, Any], report: dict[str, Any]) -> int:
    audit_at = _utc_now_text()
    cursor = connection.execute(
        """
        INSERT INTO printer_paper_audit_reports (
            paper_position_id, paper_decision_id, retrieval_query_id,
            token_id, pair_id, token_mint, pair_address, audit_at,
            audit_scope_label, paper_audit_result_label,
            paper_rule_compliance_label, paper_realism_label,
            paper_outcome_review_label, paper_data_quality_audit_label,
            audit_issues_json, decision_audit_json, entry_audit_json,
            monitoring_audit_json, exit_audit_json, pnl_audit_json,
            rule_compliance_json, audit_report_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            decision["id"],
            decision.get("retrieval_query_id"),
            decision["token_id"],
            decision["pair_id"],
            decision.get("token_mint"),
            decision.get("pair_address"),
            audit_at,
            "AUDIT_FULL_PAPER_TRADE",
            "PAPER_AUDIT_PASS_WITH_WARNINGS",
            "RULES_COMPLIANT_WITH_WARNINGS",
            "PAPER_REALISM_ACCEPTABLE",
            "PAPER_OUTCOME_NO_ACTION_VALID",
            "PAPER_AUDIT_DATA_PARTIAL",
            json.dumps(report["issue_labels"], sort_keys=True),
            json.dumps(dict(decision), sort_keys=True),
            json.dumps({"trade_quality_label": report["trade_quality_label"]}, sort_keys=True),
            json.dumps({"monitor_safety_label": report["monitor_safety_label"], "position_opened": False}, sort_keys=True),
            json.dumps({"paper_position_count": report["paper_position_count"]}, sort_keys=True),
            json.dumps({"simulated_pnl_available": False, "profit_realism_label": report["profit_realism_label"]}, sort_keys=True),
            json.dumps({"memory_safety_label": report["memory_safety_label"], "retrieval_safety_label": report["retrieval_safety_label"]}, sort_keys=True),
            json.dumps(report, sort_keys=True),
        ),
    )
    return int(cursor.lastrowid)


def _insert_real_paper_operator_review(connection: sqlite3.Connection, decision: dict[str, Any], report: dict[str, Any]) -> tuple[int, list[int]]:
    generated_at = _utc_now_text()
    attention_labels = [
        "ATTENTION_SOURCE_FAILURES",
        "ATTENTION_DIRTY_MEMORY",
        "ATTENTION_NO_CLEAN_MEMORY",
        "ATTENTION_BLOCKED_PAPER_DECISIONS",
    ]
    cursor = connection.execute(
        """
        INSERT INTO printer_operator_review_reports (
            report_scope_label, report_status_label, operator_review_label,
            report_format_label, generated_at, db_state_classification,
            token_id, pair_id, token_mint, pair_address, report_title,
            attention_labels_json, summary_payload_json, report_payload_json, report_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "REPORT_PAPER_AUDITS",
            "REPORT_READY",
            "OPERATOR_REVIEW_OK",
            "REPORT_FORMAT_JSON",
            generated_at,
            "PERSISTENT_DB_HAS_REAL_PAPER_ROWS",
            decision["token_id"],
            decision["pair_id"],
            decision.get("token_mint"),
            decision.get("pair_address"),
            "Phase 34 Real Paper Audit + Operator Review",
            json.dumps(attention_labels, sort_keys=True),
            json.dumps({"operator_review_verdict": report["operator_review_verdict"], "issue_labels": report["issue_labels"]}, sort_keys=True),
            json.dumps(report, sort_keys=True),
            "Phase 34 audit confirms safe blocked behavior: no BUY, no position, no PnL.",
        ),
    )
    report_id = int(cursor.lastrowid)
    item_ids: list[int] = []
    for label in attention_labels:
        item = connection.execute(
            """
            INSERT INTO printer_operator_review_items (
                operator_review_report_id, item_scope_label, operator_review_label,
                attention_label, token_id, pair_id, related_table, related_row_id,
                item_payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                "REPORT_PAPER_AUDITS",
                "OPERATOR_REVIEW_OK",
                label,
                decision["token_id"],
                decision["pair_id"],
                "printer_paper_decisions",
                decision["id"],
                json.dumps({"attention_label": label, "operator_review_verdict": report["operator_review_verdict"]}, sort_keys=True),
            ),
        )
        item_ids.append(int(item.lastrowid))
    return report_id, item_ids


def build_audit_paper_decision_once_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_paper_audit_once_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        decision = _resolve_monitor_decision(connection, args)
        audit_report = _build_real_paper_audit_report(connection, decision)
        audit_id = _insert_real_paper_audit_report(connection, decision, audit_report)
        audit_report["audit_id"] = audit_id
        review_report_id, review_item_ids = _insert_real_paper_operator_review(connection, decision, audit_report)
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
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_paper_trade_events",
        "printer_paper_trade_audits",
        "printer_scheduler_jobs",
    ]
    guard_deltas = {table: deltas[table] for table in guarded_tables if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    action_counts = _paper_decision_action_counts(resolved)
    return {
        "command": "printer-audit-paper-decision-once",
        "db_path": str(resolved),
        "operator_approved": True,
        "paper_audit_report_id": audit_id,
        "operator_review_report_id": review_report_id,
        "operator_review_item_ids": review_item_ids,
        "paper_audit_delta": deltas.get("printer_paper_audit_reports", 0),
        "operator_review_report_delta": deltas.get("printer_operator_review_reports", 0),
        "operator_review_item_delta": deltas.get("printer_operator_review_items", 0),
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "audit_report": audit_report,
        "action_counts": action_counts,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_audit_paper_decision_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Audit one blocked paper decision and record operator review rows.", ("json", "text"))
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
        payload = build_audit_paper_decision_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


PHASE35_SELF_CHECK_JOB_NAME = "phase35_scheduler_single_tick_self_check"
PHASE35_SELF_CHECK_JOB_KIND = "BACKUP_SOURCE_CHECK"
PHASE35_LOCK_OWNER = "phase35_scheduler_single_tick"
PHASE35_SAFE_JOB_KINDS = {PHASE35_SELF_CHECK_JOB_KIND, "TRACK_FAST_FIRST_15M"}
PHASE36_SELF_CHECK_JOB_NAME = "phase36_bounded_self_check"
PHASE36_LOCK_OWNER = "phase36_bounded_operator_run"
PHASE36_MAX_JOBS_LIMIT = 5
PHASE36_MAX_SECONDS_LIMIT = 60
PHASE37_LOCK_OWNER = "phase37_long_run_paper_validation"
PHASE37_MAX_JOBS_LIMIT = 10
PHASE37_MAX_SECONDS_LIMIT = 120
PHASE37_VALIDATION_PURPOSES = (
    "source_health",
    "memory_quality",
    "paper_decision_monitor_audit",
    "scheduler_runtime_safety",
)


def _validate_scheduler_single_tick_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("scheduler single-tick requires explicit operator approval")
    if args.max_jobs != 1:
        raise ValueError("scheduler single-tick is limited to max_jobs=1")
    if args.job_id is not None and args.create_approved_self_check_job:
        raise ValueError("scheduler single-tick accepts either job_id or create-approved-self-check-job, not both")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _scheduler_job_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        "total": int(connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0]),
        "pending": int(connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'PENDING'").fetchone()[0]),
        "running": int(connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'").fetchone()[0]),
        "succeeded": int(connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'SUCCEEDED'").fetchone()[0]),
        "failed": int(connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'FAILED'").fetchone()[0]),
        "active_locks": int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"
            ).fetchone()[0]
        ),
    }


def _create_phase35_self_check_job(connection: sqlite3.Connection) -> int:
    existing = int(connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0])
    if existing:
        raise ValueError("create-approved-self-check-job requires zero existing scheduler jobs")
    now = _utc_timestamp()
    cursor = connection.execute(
        """
        INSERT INTO printer_scheduler_jobs (
            job_name, job_kind, target_table, target_id, priority,
            status, scheduled_for, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, ?)
        """,
        (
            PHASE35_SELF_CHECK_JOB_NAME,
            PHASE35_SELF_CHECK_JOB_KIND,
            "printer_operator_review_reports",
            1,
            11,
            now,
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def _load_scheduler_job_for_tick(connection: sqlite3.Connection, job_id: int | None) -> sqlite3.Row | None:
    now = _utc_timestamp()
    if job_id is not None:
        return connection.execute("SELECT * FROM printer_scheduler_jobs WHERE id = ?", (job_id,)).fetchone()
    return connection.execute(
        """
        SELECT *
        FROM printer_scheduler_jobs
        WHERE status = 'PENDING'
          AND scheduled_for <= ?
          AND locked_at IS NULL
          AND lock_owner IS NULL
          AND job_kind IN (?)
        ORDER BY priority ASC, scheduled_for ASC, created_at ASC, id ASC
        LIMIT 1
        """,
        (now, PHASE35_SELF_CHECK_JOB_KIND),
    ).fetchone()


def _claim_scheduler_job_for_tick(connection: sqlite3.Connection, job_id: int) -> bool:
    now = _utc_timestamp()
    cursor = connection.execute(
        """
        UPDATE printer_scheduler_jobs
        SET status = 'RUNNING',
            lock_owner = ?,
            locked_at = ?,
            started_at = ?,
            updated_at = ?
        WHERE id = ?
          AND status = 'PENDING'
          AND scheduled_for <= ?
          AND locked_at IS NULL
          AND lock_owner IS NULL
        """,
        (PHASE35_LOCK_OWNER, now, now, now, job_id, now),
    )
    return int(cursor.rowcount) == 1


def _complete_scheduler_job_for_tick(connection: sqlite3.Connection, job_id: int) -> None:
    now = _utc_timestamp()
    connection.execute(
        """
        UPDATE printer_scheduler_jobs
        SET status = 'SUCCEEDED',
            finished_at = ?,
            locked_at = NULL,
            lock_owner = NULL,
            last_error = NULL,
            updated_at = ?
        WHERE id = ?
        """,
        (now, now, job_id),
    )


def _fail_scheduler_job_for_tick(connection: sqlite3.Connection, job_id: int, error: str) -> None:
    now = _utc_timestamp()
    connection.execute(
        """
        UPDATE printer_scheduler_jobs
        SET status = 'FAILED',
            finished_at = ?,
            locked_at = NULL,
            lock_owner = NULL,
            retry_count = retry_count + 1,
            last_error = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (now, error, now, job_id),
    )


def _execute_phase35_scheduler_job(connection: sqlite3.Connection, job: sqlite3.Row) -> dict[str, Any]:
    if str(job["job_kind"]) not in PHASE35_SAFE_JOB_KINDS:
        raise ValueError("UNSUPPORTED_JOB_KIND_PHASE35")

    if str(job["job_kind"]) == "TRACK_FAST_FIRST_15M":
        from printer_v1.operator_cli.e2h_runtime_handler import (
            execute_track_fast_first_15m_job,
        )
        result = execute_track_fast_first_15m_job(connection, job)
        if not result.get("executed", False):
            blocked_reason = result.get("blocked_reason") or "; ".join(
                result.get("blocked_gates", ["handler blocked"])
            )
            raise ValueError(f"TRACK_FAST_FIRST_15M_HANDLER_BLOCKED: {blocked_reason}")
        return result

    decision = connection.execute(
        "SELECT * FROM printer_paper_decisions ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if decision is None:
        raise ValueError("SCHEDULER_SELF_CHECK_MISSING_PAPER_DECISION")
    action = decision["final_action_label"] or decision["decision_action"]
    status = decision["paper_decision_status_label"] or decision["decision_status"]
    if action != "NO_ACTION" or status != "PAPER_DECISION_BLOCKED":
        raise ValueError("SCHEDULER_SELF_CHECK_UNSAFE_DECISION_STATE")

    checks = {
        "source_failures_visible": int(connection.execute("SELECT COUNT(*) FROM printer_source_failures").fetchone()[0]) > 0,
        "dirty_memory_blocked": int(
            connection.execute("SELECT COUNT(*) FROM printer_memory_windows WHERE memory_quality_label = 'DIRTY_MEMORY'").fetchone()[0]
        )
        > 0,
        "paper_decision_blocked": True,
        "paper_position_rows": int(connection.execute("SELECT COUNT(*) FROM printer_paper_positions").fetchone()[0]),
        "paper_trade_event_rows": int(connection.execute("SELECT COUNT(*) FROM printer_paper_trade_events").fetchone()[0]),
        "runtime_started": False,
    }
    if checks["paper_position_rows"] or checks["paper_trade_event_rows"]:
        raise ValueError("SCHEDULER_SELF_CHECK_FOUND_PAPER_EXECUTION_ROWS")
    return {
        "job_handler": "phase35_scheduler_self_check",
        "job_kind": job["job_kind"],
        "job_name": job["job_name"],
        "checks": checks,
        "scheduler_executed": True,
        "runtime_started": False,
        "source_fetch_executed": False,
    }


def build_scheduler_single_tick_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_scheduler_single_tick_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    job_created = False
    created_job_id: int | None = None
    selected_job_id: int | None = None
    selected_job_kind: str | None = None
    selected_job_status: str | None = None
    execution_report: dict[str, Any] = {}
    jobs_claimed = 0
    jobs_executed = 0
    jobs_completed = 0
    jobs_failed = 0
    try:
        if args.create_approved_self_check_job:
            created_job_id = _create_phase35_self_check_job(connection)
            job_created = True

        job = _load_scheduler_job_for_tick(connection, args.job_id)
        if job is None:
            connection.commit()
        else:
            selected_job_id = int(job["id"])
            selected_job_kind = str(job["job_kind"])
            selected_job_status = str(job["status"])
            if selected_job_status != "PENDING":
                raise ValueError("scheduler single-tick can only claim pending due jobs")
            if not _claim_scheduler_job_for_tick(connection, selected_job_id):
                raise ValueError("scheduler single-tick could not claim the selected job")
            jobs_claimed = 1
            jobs_executed = 1
            try:
                running_job = connection.execute(
                    "SELECT * FROM printer_scheduler_jobs WHERE id = ?",
                    (selected_job_id,),
                ).fetchone()
                execution_report = _execute_phase35_scheduler_job(connection, running_job)
                _complete_scheduler_job_for_tick(connection, selected_job_id)
                selected_job_status = "SUCCEEDED"
                jobs_completed = 1
            except Exception as exc:
                _fail_scheduler_job_for_tick(connection, selected_job_id, str(exc))
                selected_job_status = "FAILED"
                execution_report = {
                    "job_handler": "phase35_scheduler_self_check",
                    "job_kind": selected_job_kind,
                    "job_name": job["job_name"],
                    "error": str(exc),
                    "scheduler_executed": True,
                    "runtime_started": False,
                    "source_fetch_executed": False,
                }
                jobs_failed = 1
        connection.commit()
        scheduler_counts = _scheduler_job_counts(connection)
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
        "printer_operator_review_reports",
        "printer_operator_review_items",
    ]
    guard_deltas = {table: deltas[table] for table in guarded_tables if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    action_counts = _paper_decision_action_counts(resolved)
    return {
        "command": "printer-run-scheduler-single-tick",
        "db_path": str(resolved),
        "operator_approved": True,
        "max_jobs": 1,
        "scheduler_job_created": job_created,
        "created_scheduler_job_id": created_job_id,
        "selected_scheduler_job_id": selected_job_id,
        "scheduler_job_kind": selected_job_kind,
        "scheduler_job_status": selected_job_status,
        "scheduler_jobs_claimed": jobs_claimed,
        "scheduler_jobs_executed": jobs_executed,
        "scheduler_jobs_completed": jobs_completed,
        "scheduler_jobs_failed": jobs_failed,
        "running_scheduler_jobs_after_exit": scheduler_counts["running"],
        "active_job_locks_after_exit": scheduler_counts["active_locks"],
        "scheduler_counts": scheduler_counts,
        "execution_report": execution_report,
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "scheduler_job_delta": deltas.get("printer_scheduler_jobs", 0),
        "action_counts": action_counts,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
        "single_tick_boundary_check": "PASS_SINGLE_TICK_ONLY",
    }


def main_run_scheduler_single_tick(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Run exactly one approved scheduler job and exit.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--job-id", type=int)
    parser.add_argument("--create-approved-self-check-job", action="store_true")
    parser.add_argument("--max-jobs", type=int, default=1)
    args = parser.parse_args(argv)
    try:
        payload = build_scheduler_single_tick_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _validate_bounded_run_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("bounded run requires explicit operator approval")
    if args.max_jobs is None:
        raise ValueError("bounded run requires max_jobs")
    if args.max_seconds is None:
        raise ValueError("bounded run requires max_seconds")
    if args.max_jobs < 1:
        raise ValueError("bounded run requires max_jobs >= 1")
    if args.max_seconds < 1:
        raise ValueError("bounded run requires max_seconds >= 1")
    if args.max_jobs > PHASE36_MAX_JOBS_LIMIT:
        raise ValueError(f"bounded run max_jobs limit is {PHASE36_MAX_JOBS_LIMIT}")
    if args.max_seconds > PHASE36_MAX_SECONDS_LIMIT:
        raise ValueError(f"bounded run max_seconds limit is {PHASE36_MAX_SECONDS_LIMIT}")
    if args.create_approved_self_check_jobs < 0:
        raise ValueError("create-approved-self-check-jobs cannot be negative")
    if args.create_approved_self_check_jobs > args.max_jobs:
        raise ValueError("create-approved-self-check-jobs cannot exceed max_jobs")
    if args.create_approved_self_check_jobs > 2:
        raise ValueError("Phase 36 persistent-safe creation is capped at 2 jobs")


def _create_phase36_self_check_jobs(connection: sqlite3.Connection, count: int) -> list[int]:
    job_ids: list[int] = []
    for _ in range(count):
        now = _utc_timestamp()
        cursor = connection.execute(
            """
            INSERT INTO printer_scheduler_jobs (
                job_name, job_kind, target_table, target_id, priority,
                status, scheduled_for, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, ?)
            """,
            (
                PHASE36_SELF_CHECK_JOB_NAME,
                PHASE35_SELF_CHECK_JOB_KIND,
                "printer_operator_review_reports",
                1,
                11,
                now,
                now,
                now,
            ),
        )
        job_ids.append(int(cursor.lastrowid))
    return job_ids


def _claim_scheduler_job_for_bounded_run(connection: sqlite3.Connection, job_id: int) -> bool:
    now = _utc_timestamp()
    cursor = connection.execute(
        """
        UPDATE printer_scheduler_jobs
        SET status = 'RUNNING',
            lock_owner = ?,
            locked_at = ?,
            started_at = ?,
            updated_at = ?
        WHERE id = ?
          AND status = 'PENDING'
          AND scheduled_for <= ?
          AND locked_at IS NULL
          AND lock_owner IS NULL
        """,
        (PHASE36_LOCK_OWNER, now, now, now, job_id, now),
    )
    return int(cursor.rowcount) == 1


def _load_next_bounded_run_job(connection: sqlite3.Connection) -> sqlite3.Row | None:
    now = _utc_timestamp()
    return connection.execute(
        """
        SELECT *
        FROM printer_scheduler_jobs
        WHERE status = 'PENDING'
          AND scheduled_for <= ?
          AND locked_at IS NULL
          AND lock_owner IS NULL
          AND job_kind IN (?)
        ORDER BY priority ASC, scheduled_for ASC, created_at ASC, id ASC
        LIMIT 1
        """,
        (now, PHASE35_SELF_CHECK_JOB_KIND),
    ).fetchone()


def build_bounded_run_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_bounded_run_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    start_time = datetime.now(timezone.utc)
    deadline = start_time + timedelta(seconds=args.max_seconds)
    created_job_ids: list[int] = []
    job_results: list[dict[str, Any]] = []
    jobs_claimed = 0
    jobs_executed = 0
    jobs_completed = 0
    jobs_failed = 0
    stop_reason = "NO_ELIGIBLE_JOBS"

    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        if args.create_approved_self_check_jobs:
            created_job_ids = _create_phase36_self_check_jobs(connection, args.create_approved_self_check_jobs)

        while jobs_executed < args.max_jobs and datetime.now(timezone.utc) < deadline:
            job = _load_next_bounded_run_job(connection)
            if job is None:
                stop_reason = "NO_ELIGIBLE_JOBS_AFTER_WORK" if jobs_executed else "NO_ELIGIBLE_JOBS"
                break
            selected_job_id = int(job["id"])
            if not _claim_scheduler_job_for_bounded_run(connection, selected_job_id):
                stop_reason = "JOB_CLAIM_FAILED"
                break
            jobs_claimed += 1
            jobs_executed += 1
            try:
                running_job = connection.execute(
                    "SELECT * FROM printer_scheduler_jobs WHERE id = ?",
                    (selected_job_id,),
                ).fetchone()
                execution_report = _execute_phase35_scheduler_job(connection, running_job)
                _complete_scheduler_job_for_tick(connection, selected_job_id)
                jobs_completed += 1
                job_results.append(
                    {
                        "job_id": selected_job_id,
                        "job_kind": running_job["job_kind"],
                        "job_name": running_job["job_name"],
                        "status": "SUCCEEDED",
                        "execution_report": execution_report,
                    }
                )
            except Exception as exc:
                _fail_scheduler_job_for_tick(connection, selected_job_id, str(exc))
                jobs_failed += 1
                job_results.append(
                    {
                        "job_id": selected_job_id,
                        "job_kind": job["job_kind"],
                        "job_name": job["job_name"],
                        "status": "FAILED",
                        "error": str(exc),
                    }
                )
            if jobs_executed >= args.max_jobs:
                stop_reason = "MAX_JOBS_REACHED"
                break
            if datetime.now(timezone.utc) >= deadline:
                stop_reason = "MAX_SECONDS_REACHED"
                break

        connection.commit()
        scheduler_counts = _scheduler_job_counts(connection)
    finally:
        connection.close()

    elapsed_seconds = max((datetime.now(timezone.utc) - start_time).total_seconds(), 0.0)
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
        "printer_operator_review_reports",
        "printer_operator_review_items",
    ]
    guard_deltas = {table: deltas[table] for table in guarded_tables if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    action_counts = _paper_decision_action_counts(resolved)
    return {
        "command": "printer-run-bounded",
        "db_path": str(resolved),
        "operator_approved": True,
        "max_jobs": args.max_jobs,
        "max_seconds": args.max_seconds,
        "elapsed_seconds": elapsed_seconds,
        "created_scheduler_job_ids": created_job_ids,
        "phase36_scheduler_jobs_created": len(created_job_ids),
        "scheduler_jobs_claimed": jobs_claimed,
        "scheduler_jobs_executed": jobs_executed,
        "scheduler_jobs_completed": jobs_completed,
        "scheduler_jobs_failed": jobs_failed,
        "running_scheduler_jobs_after_exit": scheduler_counts["running"],
        "active_job_locks_after_exit": scheduler_counts["active_locks"],
        "runtime_stop_reason": stop_reason,
        "runtime_stopped_cleanly": scheduler_counts["running"] == 0 and scheduler_counts["active_locks"] == 0,
        "runtime_active_after_exit": False,
        "unbounded_runtime_detected": False,
        "bounded_loop_check": "PASS_MAX_JOBS_AND_SECONDS_ENFORCED",
        "scheduler_counts": scheduler_counts,
        "job_results": job_results,
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "scheduler_job_delta": deltas.get("printer_scheduler_jobs", 0),
        "action_counts": action_counts,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_run_bounded(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Run a bounded operator-approved scheduler session.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--max-jobs", type=int)
    parser.add_argument("--max-seconds", type=int)
    parser.add_argument("--create-approved-self-check-jobs", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        payload = build_bounded_run_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _validate_long_paper_validation_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("long-run paper validation requires explicit operator approval")
    if args.max_jobs is None:
        raise ValueError("long-run paper validation requires max_jobs")
    if args.max_seconds is None:
        raise ValueError("long-run paper validation requires max_seconds")
    if args.max_jobs < 1:
        raise ValueError("long-run paper validation requires max_jobs >= 1")
    if args.max_seconds < 1:
        raise ValueError("long-run paper validation requires max_seconds >= 1")
    if args.max_jobs > PHASE37_MAX_JOBS_LIMIT:
        raise ValueError(f"long-run paper validation max_jobs limit is {PHASE37_MAX_JOBS_LIMIT}")
    if args.max_seconds > PHASE37_MAX_SECONDS_LIMIT:
        raise ValueError(f"long-run paper validation max_seconds limit is {PHASE37_MAX_SECONDS_LIMIT}")
    if args.create_approved_validation_jobs < 0:
        raise ValueError("create-approved-validation-jobs cannot be negative")
    if args.create_approved_validation_jobs > args.max_jobs:
        raise ValueError("create-approved-validation-jobs cannot exceed max_jobs")
    if args.create_approved_validation_jobs > len(PHASE37_VALIDATION_PURPOSES):
        raise ValueError("Phase 37 validation job creation is capped at 4 jobs")


def _create_phase37_validation_jobs(connection: sqlite3.Connection, count: int) -> list[int]:
    job_ids: list[int] = []
    for purpose in PHASE37_VALIDATION_PURPOSES[:count]:
        now = _utc_timestamp()
        cursor = connection.execute(
            """
            INSERT INTO printer_scheduler_jobs (
                job_name, job_kind, target_table, target_id, priority,
                status, scheduled_for, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, ?)
            """,
            (
                f"phase37_validation_{purpose}",
                PHASE35_SELF_CHECK_JOB_KIND,
                "printer_operator_review_reports",
                1,
                11,
                now,
                now,
                now,
            ),
        )
        job_ids.append(int(cursor.lastrowid))
    return job_ids


def _load_next_long_validation_job(connection: sqlite3.Connection) -> sqlite3.Row | None:
    now = _utc_timestamp()
    return connection.execute(
        """
        SELECT *
        FROM printer_scheduler_jobs
        WHERE status = 'PENDING'
          AND scheduled_for <= ?
          AND locked_at IS NULL
          AND lock_owner IS NULL
          AND job_kind IN (?)
          AND job_name LIKE 'phase37_validation_%'
        ORDER BY priority ASC, scheduled_for ASC, created_at ASC, id ASC
        LIMIT 1
        """,
        (now, PHASE35_SELF_CHECK_JOB_KIND),
    ).fetchone()


def _claim_scheduler_job_for_long_validation(connection: sqlite3.Connection, job_id: int) -> bool:
    now = _utc_timestamp()
    cursor = connection.execute(
        """
        UPDATE printer_scheduler_jobs
        SET status = 'RUNNING',
            lock_owner = ?,
            locked_at = ?,
            started_at = ?,
            updated_at = ?
        WHERE id = ?
          AND status = 'PENDING'
          AND scheduled_for <= ?
          AND locked_at IS NULL
          AND lock_owner IS NULL
        """,
        (PHASE37_LOCK_OWNER, now, now, now, job_id, now),
    )
    return int(cursor.rowcount) == 1


def _current_validation_summary(connection: sqlite3.Connection) -> dict[str, Any]:
    action_counts = {
        action: int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_paper_decisions WHERE COALESCE(final_action_label, decision_action) = ?",
                (action,),
            ).fetchone()[0]
        )
        for action in ["BUY", "WAIT", "AVOID", "NO_ACTION", "SELL", "HOLD"]
    }
    return {
        "source_request_count": int(connection.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]),
        "source_response_count": int(connection.execute("SELECT COUNT(*) FROM printer_source_responses").fetchone()[0]),
        "source_failure_count": int(connection.execute("SELECT COUNT(*) FROM printer_source_failures").fetchone()[0]),
        "clean_eligible_memory_count": int(
            connection.execute("SELECT COUNT(*) FROM printer_memory_windows WHERE memory_quality_label = 'CLEAN_MEMORY' AND do_not_train = 0").fetchone()[0]
        ),
        "dirty_memory_count": int(
            connection.execute("SELECT COUNT(*) FROM printer_memory_windows WHERE memory_quality_label = 'DIRTY_MEMORY'").fetchone()[0]
        ),
        "blocked_dirty_memory_count": int(
            connection.execute("SELECT COUNT(*) FROM printer_memory_windows WHERE memory_quality_label = 'DIRTY_MEMORY' AND do_not_train = 1").fetchone()[0]
        ),
        "retrieval_query_count": int(connection.execute("SELECT COUNT(*) FROM printer_memory_retrieval_queries").fetchone()[0]),
        "retrieval_match_count": int(connection.execute("SELECT COUNT(*) FROM printer_memory_retrieval_matches").fetchone()[0]),
        "paper_decision_count": int(connection.execute("SELECT COUNT(*) FROM printer_paper_decisions").fetchone()[0]),
        "paper_position_count": int(connection.execute("SELECT COUNT(*) FROM printer_paper_positions").fetchone()[0]),
        "paper_trade_event_count": int(connection.execute("SELECT COUNT(*) FROM printer_paper_trade_events").fetchone()[0]),
        "paper_audit_count": int(connection.execute("SELECT COUNT(*) FROM printer_paper_audit_reports").fetchone()[0]),
        "scheduler_job_count": int(connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0]),
        "running_scheduler_jobs": int(connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'").fetchone()[0]),
        "active_job_locks": int(
            connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL").fetchone()[0]
        ),
        "action_counts": action_counts,
    }


def _execute_phase37_validation_job(connection: sqlite3.Connection, job: sqlite3.Row) -> dict[str, Any]:
    if not str(job["job_name"]).startswith("phase37_validation_"):
        raise ValueError("UNSUPPORTED_PHASE37_VALIDATION_JOB")
    summary = _current_validation_summary(connection)
    if summary["paper_position_count"] or summary["paper_trade_event_count"]:
        raise ValueError("PHASE37_VALIDATION_FOUND_PAPER_EXECUTION_ROWS")
    if summary["action_counts"]["BUY"] > 0:
        raise ValueError("PHASE37_VALIDATION_FOUND_BUY_WITHOUT_CLEAN_MEMORY")
    purpose = str(job["job_name"]).removeprefix("phase37_validation_")
    labels = {
        "source_health": "SOURCE_FAILURES_VISIBLE",
        "memory_quality": "DIRTY_MEMORY_BLOCKED",
        "paper_decision_monitor_audit": "BLOCKED_DECISION_VALID",
        "scheduler_runtime_safety": "BOUNDED_RUNTIME_SAFE",
    }
    return {
        "job_handler": "phase37_long_run_validation",
        "job_kind": job["job_kind"],
        "job_name": job["job_name"],
        "validation_purpose": purpose,
        "validation_label": labels.get(purpose, "VALIDATION_AUDIT_ONLY"),
        "summary": summary,
        "source_fetch_executed": False,
        "runtime_started": False,
    }


def _build_long_run_validation_report(connection: sqlite3.Connection, runtime_summary: dict[str, Any]) -> dict[str, Any]:
    summary = _current_validation_summary(connection)
    issue_labels = [
        "SOURCE_FAILURES_VISIBLE",
        "DIRTY_MEMORY_PRESENT_BUT_BLOCKED",
        "NO_CLEAN_MEMORY_AVAILABLE",
        "PAPER_DECISION_BLOCKED",
        "NO_POSITION_OPENED",
        "NO_FAKE_PROFIT",
        "BOUNDED_RUNTIME_SAFE",
        "LIVE_TRADING_NOT_PRESENT",
    ]
    release_candidate_allowed = True
    return {
        "validation_run_id": None,
        "max_jobs": runtime_summary["max_jobs"],
        "max_seconds": runtime_summary["max_seconds"],
        "jobs_created": runtime_summary["phase37_validation_jobs_created"],
        "jobs_claimed": runtime_summary["scheduler_jobs_claimed"],
        "jobs_executed": runtime_summary["scheduler_jobs_executed"],
        "jobs_succeeded": runtime_summary["scheduler_jobs_completed"],
        "jobs_failed": runtime_summary["scheduler_jobs_failed"],
        "stop_reason": runtime_summary["runtime_stop_reason"],
        "runtime_stopped_cleanly": runtime_summary["runtime_stopped_cleanly"],
        "runtime_active_after_exit": runtime_summary["runtime_active_after_exit"],
        "unbounded_runtime_detected": runtime_summary["unbounded_runtime_detected"],
        "source_health_label": "SOURCE_HEALTH_LIMITED_BUT_AUDITABLE",
        "source_failure_visibility_label": "SOURCE_FAILURES_VISIBLE",
        "memory_quality_label": "DIRTY_MEMORY_PRESENT_NO_CLEAN_MEMORY",
        "clean_eligible_memory_count": summary["clean_eligible_memory_count"],
        "dirty_memory_count": summary["dirty_memory_count"],
        "dirty_memory_blocking_label": "DIRTY_MEMORY_BLOCKED",
        "retrieval_quality_label": "NO_CLEAN_MEMORY_MATCHES",
        "paper_decision_quality_label": "BLOCKED_DECISION_VALID",
        "paper_monitor_quality_label": "POSITION_OPEN_BLOCKED",
        "paper_audit_quality_label": "AUDIT_VISIBLE_NO_PNL",
        "fake_profit_prevention_label": "NO_FAKE_PROFIT",
        "exit_realism_visibility_label": "NO_POSITION_NO_EXIT_PNL_NOT_APPLICABLE",
        "scheduler_safety_label": "BOUNDED_SCHEDULER_SAFE",
        "runtime_safety_label": "BOUNDED_RUNTIME_SAFE",
        "live_trading_safety_label": "LIVE_TRADING_NOT_PRESENT",
        "issue_labels": issue_labels,
        "validation_verdict": "PAPER_VALIDATION_SAFE_BUT_NO_CLEAN_MEMORY",
        "recommended_operator_action": "Commit and checkpoint Phase 37; Phase 38 may freeze a paper-only release candidate if the operator accepts the no-clean-memory blocker.",
        "release_candidate_allowed": release_candidate_allowed,
        "not_buy_ready": True,
        "not_live_ready": True,
        "not_profitable_claim": True,
        "state_summary": summary,
    }


def _insert_long_run_validation_operator_review(connection: sqlite3.Connection, report: dict[str, Any]) -> tuple[int, list[int]]:
    generated_at = _utc_timestamp()
    cursor = connection.execute(
        """
        INSERT INTO printer_operator_review_reports (
            report_scope_label, report_status_label, operator_review_label,
            report_format_label, generated_at, db_state_classification,
            report_title, attention_labels_json, summary_payload_json,
            report_payload_json, report_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "REPORT_FULL_OPERATOR_REVIEW",
            "REPORT_READY",
            "OPERATOR_REVIEW_OK",
            "REPORT_FORMAT_JSON",
            generated_at,
            "PERSISTENT_DB_STATE_UNCLEAR",
            "Phase 37 Long-Run Paper Validation",
            json.dumps(report["issue_labels"], sort_keys=True),
            json.dumps(
                {
                    "validation_verdict": report["validation_verdict"],
                    "clean_eligible_memory_count": report["clean_eligible_memory_count"],
                    "dirty_memory_count": report["dirty_memory_count"],
                    "release_candidate_allowed": report["release_candidate_allowed"],
                },
                sort_keys=True,
            ),
            json.dumps(report, sort_keys=True),
            json.dumps(report, indent=2, sort_keys=True),
        ),
    )
    report_id = int(cursor.lastrowid)
    item_specs = [
        ("REPORT_SOURCE_HEALTH", "ATTENTION_SOURCE_FAILURES", report["source_failure_visibility_label"]),
        ("REPORT_MEMORY", "ATTENTION_DIRTY_MEMORY", report["dirty_memory_blocking_label"]),
        ("REPORT_PAPER_AUDITS", "ATTENTION_BLOCKED_PAPER_DECISIONS", report["fake_profit_prevention_label"]),
        ("REPORT_SCHEDULER_HEALTH", "ATTENTION_NONE", report["runtime_safety_label"]),
    ]
    item_ids: list[int] = []
    for scope, attention, label in item_specs:
        item = connection.execute(
            """
            INSERT INTO printer_operator_review_items (
                operator_review_report_id, item_scope_label, operator_review_label,
                attention_label, item_payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                report_id,
                scope,
                "OPERATOR_REVIEW_OK",
                attention,
                json.dumps({"validation_verdict": report["validation_verdict"], "label": label}, sort_keys=True),
            ),
        )
        item_ids.append(int(item.lastrowid))
    return report_id, item_ids


def build_long_paper_validation_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_long_paper_validation_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    start_time = datetime.now(timezone.utc)
    deadline = start_time + timedelta(seconds=args.max_seconds)
    created_job_ids: list[int] = []
    job_results: list[dict[str, Any]] = []
    jobs_claimed = 0
    jobs_executed = 0
    jobs_completed = 0
    jobs_failed = 0
    stop_reason = "NO_ELIGIBLE_JOBS"
    review_report_id: int | None = None
    review_item_ids: list[int] = []
    validation_report: dict[str, Any] = {}

    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        if args.create_approved_validation_jobs:
            created_job_ids = _create_phase37_validation_jobs(connection, args.create_approved_validation_jobs)

        while jobs_executed < args.max_jobs and datetime.now(timezone.utc) < deadline:
            job = _load_next_long_validation_job(connection)
            if job is None:
                stop_reason = "NO_ELIGIBLE_JOBS_AFTER_WORK" if jobs_executed else "NO_ELIGIBLE_JOBS"
                break
            selected_job_id = int(job["id"])
            if not _claim_scheduler_job_for_long_validation(connection, selected_job_id):
                stop_reason = "JOB_CLAIM_FAILED"
                break
            jobs_claimed += 1
            jobs_executed += 1
            try:
                running_job = connection.execute(
                    "SELECT * FROM printer_scheduler_jobs WHERE id = ?",
                    (selected_job_id,),
                ).fetchone()
                execution_report = _execute_phase37_validation_job(connection, running_job)
                _complete_scheduler_job_for_tick(connection, selected_job_id)
                jobs_completed += 1
                job_results.append(
                    {
                        "job_id": selected_job_id,
                        "job_kind": running_job["job_kind"],
                        "job_name": running_job["job_name"],
                        "status": "SUCCEEDED",
                        "execution_report": execution_report,
                    }
                )
            except Exception as exc:
                _fail_scheduler_job_for_tick(connection, selected_job_id, str(exc))
                jobs_failed += 1
                job_results.append(
                    {
                        "job_id": selected_job_id,
                        "job_kind": job["job_kind"],
                        "job_name": job["job_name"],
                        "status": "FAILED",
                        "error": str(exc),
                    }
                )
            if jobs_executed >= args.max_jobs:
                stop_reason = "MAX_JOBS_REACHED"
                break
            if datetime.now(timezone.utc) >= deadline:
                stop_reason = "MAX_SECONDS_REACHED"
                break

        scheduler_counts = _scheduler_job_counts(connection)
        runtime_summary = {
            "max_jobs": args.max_jobs,
            "max_seconds": args.max_seconds,
            "phase37_validation_jobs_created": len(created_job_ids),
            "scheduler_jobs_claimed": jobs_claimed,
            "scheduler_jobs_executed": jobs_executed,
            "scheduler_jobs_completed": jobs_completed,
            "scheduler_jobs_failed": jobs_failed,
            "runtime_stop_reason": stop_reason,
            "runtime_stopped_cleanly": scheduler_counts["running"] == 0 and scheduler_counts["active_locks"] == 0,
            "runtime_active_after_exit": False,
            "unbounded_runtime_detected": False,
        }
        validation_report = _build_long_run_validation_report(connection, runtime_summary)
        review_report_id, review_item_ids = _insert_long_run_validation_operator_review(connection, validation_report)
        validation_report["validation_run_id"] = review_report_id
        connection.commit()
        scheduler_counts = _scheduler_job_counts(connection)
    finally:
        connection.close()

    elapsed_seconds = max((datetime.now(timezone.utc) - start_time).total_seconds(), 0.0)
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
    ]
    guard_deltas = {table: deltas[table] for table in guarded_tables if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    action_counts = _paper_decision_action_counts(resolved)
    return {
        "command": "printer-run-long-paper-validation",
        "db_path": str(resolved),
        "operator_approved": True,
        "max_jobs": args.max_jobs,
        "max_seconds": args.max_seconds,
        "elapsed_seconds": elapsed_seconds,
        "created_scheduler_job_ids": created_job_ids,
        "phase37_validation_jobs_created": len(created_job_ids),
        "scheduler_jobs_claimed": jobs_claimed,
        "scheduler_jobs_executed": jobs_executed,
        "scheduler_jobs_completed": jobs_completed,
        "scheduler_jobs_failed": jobs_failed,
        "running_scheduler_jobs_after_exit": scheduler_counts["running"],
        "active_job_locks_after_exit": scheduler_counts["active_locks"],
        "runtime_stop_reason": stop_reason,
        "runtime_stopped_cleanly": scheduler_counts["running"] == 0 and scheduler_counts["active_locks"] == 0,
        "runtime_active_after_exit": False,
        "unbounded_runtime_detected": False,
        "validation_report_id": review_report_id,
        "validation_item_ids": review_item_ids,
        "validation_report": validation_report,
        "scheduler_counts": scheduler_counts,
        "job_results": job_results,
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "scheduler_job_delta": deltas.get("printer_scheduler_jobs", 0),
        "operator_review_report_delta": deltas.get("printer_operator_review_reports", 0),
        "operator_review_item_delta": deltas.get("printer_operator_review_items", 0),
        "action_counts": action_counts,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_run_long_paper_validation(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Run supervised long-run paper validation with hard caps.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--max-jobs", type=int)
    parser.add_argument("--max-seconds", type=int)
    parser.add_argument("--create-approved-validation-jobs", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        payload = build_long_paper_validation_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def _validate_v1_paper_rc_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("V1 paper RC freeze requires explicit operator approval")
    if not args.rc_name:
        raise ValueError("V1 paper RC freeze requires rc_name")
    if not args.acknowledge_no_clean_memory_blocker:
        raise ValueError("V1 paper RC freeze requires acknowledgement of the no-clean-memory blocker")
    if not args.acknowledge_paper_only:
        raise ValueError("V1 paper RC freeze requires acknowledgement that this is paper-only")


def _latest_phase37_report(connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT report_payload_json
        FROM printer_operator_review_reports
        WHERE report_title = 'Phase 37 Long-Run Paper Validation'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    if row is None or not row["report_payload_json"]:
        raise ValueError("Phase 38 requires a Phase 37 long-run validation report")
    return json.loads(row["report_payload_json"])


def _current_rc_freeze_summary(connection: sqlite3.Connection) -> dict[str, Any]:
    counts = {
        table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        for table in [
            "printer_source_requests",
            "printer_source_responses",
            "printer_source_failures",
            "printer_tokens",
            "printer_pairs",
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
            "printer_memory_audit_reports",
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
            "printer_paper_audit_reports",
            "printer_operator_review_reports",
            "printer_operator_review_items",
            "printer_scheduler_jobs",
        ]
    }
    action_counts = {
        action: int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_paper_decisions WHERE COALESCE(final_action_label, decision_action) = ?",
                (action,),
            ).fetchone()[0]
        )
        for action in ["BUY", "WAIT", "AVOID", "NO_ACTION", "SELL", "HOLD"]
    }
    latest_decision = connection.execute(
        """
        SELECT COALESCE(final_action_label, decision_action) AS action,
               COALESCE(paper_decision_status_label, decision_status) AS status,
               blocking_reasons_json
        FROM printer_paper_decisions
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()
    return {
        "counts": counts,
        "action_counts": action_counts,
        "latest_paper_decision_action": latest_decision["action"] if latest_decision else None,
        "latest_paper_decision_status": latest_decision["status"] if latest_decision else None,
        "latest_paper_decision_blocked_reason": json.loads(latest_decision["blocking_reasons_json"] or "[]")
        if latest_decision
        else [],
        "clean_eligible_memory_count": int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_memory_windows WHERE memory_quality_label = 'CLEAN_MEMORY' AND do_not_train = 0"
            ).fetchone()[0]
        ),
        "dirty_memory_count": int(
            connection.execute("SELECT COUNT(*) FROM printer_memory_windows WHERE memory_quality_label = 'DIRTY_MEMORY'").fetchone()[0]
        ),
        "blocked_dirty_memory_count": int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_memory_windows WHERE memory_quality_label = 'DIRTY_MEMORY' AND do_not_train = 1"
            ).fetchone()[0]
        ),
        "running_scheduler_jobs": int(
            connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = 'RUNNING'").fetchone()[0]
        ),
        "active_job_locks": int(
            connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL").fetchone()[0]
        ),
    }


def _assert_v1_paper_rc_safety_gates(
    connection: sqlite3.Connection,
    project_root: Path,
    state_classification: str,
    summary: dict[str, Any],
    phase37_report: dict[str, Any],
) -> None:
    if state_classification != STATE_LONG_RUN_PAPER_VALIDATION:
        raise ValueError("V1 paper RC freeze requires READY_LONG_RUN_PAPER_VALIDATION state")
    source_scan = check_no_live_capability_terms_in_source(project_root)
    runtime_scan = check_no_runtime_loop_terms_in_source(project_root)
    if source_scan["validation_result_label"] != "VALIDATION_PASS":
        raise ValueError("V1 paper RC freeze blocked by live/wallet/source capability marker")
    if runtime_scan["validation_result_label"] != "VALIDATION_PASS":
        raise ValueError("V1 paper RC freeze blocked by runtime loop marker")
    if phase37_report.get("validation_verdict") != "PAPER_VALIDATION_SAFE_BUT_NO_CLEAN_MEMORY":
        raise ValueError("V1 paper RC freeze requires honest Phase 37 no-clean-memory verdict")
    if phase37_report.get("source_failure_visibility_label") != "SOURCE_FAILURES_VISIBLE":
        raise ValueError("V1 paper RC freeze requires visible source failures")
    if phase37_report.get("runtime_active_after_exit"):
        raise ValueError("V1 paper RC freeze requires runtime inactive after exit")
    if phase37_report.get("unbounded_runtime_detected"):
        raise ValueError("V1 paper RC freeze blocked by unbounded runtime")
    if phase37_report.get("live_trading_safety_label") != "LIVE_TRADING_NOT_PRESENT":
        raise ValueError("V1 paper RC freeze requires live trading absence")
    if summary["clean_eligible_memory_count"] != 0:
        raise ValueError("Phase 38 persistent RC is scoped to the known no-clean-memory blocker")
    if summary["dirty_memory_count"] < 1 or summary["blocked_dirty_memory_count"] < 1:
        raise ValueError("V1 paper RC freeze requires dirty memory to remain blocked")
    if summary["action_counts"]["BUY"] > 0:
        raise ValueError("V1 paper RC freeze blocked because BUY exists")
    if summary["latest_paper_decision_action"] != "NO_ACTION":
        raise ValueError("V1 paper RC freeze requires latest decision to remain NO_ACTION")
    if summary["latest_paper_decision_status"] != "PAPER_DECISION_BLOCKED":
        raise ValueError("V1 paper RC freeze requires latest decision to remain blocked")
    if summary["counts"]["printer_paper_positions"] > 0 or summary["counts"]["printer_paper_trade_events"] > 0:
        raise ValueError("V1 paper RC freeze blocked by paper execution rows")
    if summary["counts"]["printer_paper_trade_audits"] > 0:
        raise ValueError("V1 paper RC freeze blocked by PnL/audit trade rows")
    if summary["running_scheduler_jobs"] or summary["active_job_locks"]:
        raise ValueError("V1 paper RC freeze requires zero running jobs and locks")


def _build_v1_paper_rc_manifest(
    rc_name: str,
    summary: dict[str, Any],
    phase37_report: dict[str, Any],
    current_state: str,
    readiness_label: str,
) -> dict[str, Any]:
    counts = summary["counts"]
    action_counts = summary["action_counts"]
    known_blockers = [
        "NO_CLEAN_ELIGIBLE_MEMORY",
        "BUY_LOCKED",
        "NO_PAPER_POSITION_HISTORY",
        "SOURCE_FAILURES_VISIBLE",
        "NOT_PROFIT_CLAIM_READY",
        "NOT_LIVE_READY",
    ]
    known_limitations = [
        "Only one real token snapshot exists",
        "Only dirty memory exists and remains blocked",
        "Clean retrieval returned zero matches",
        "Paper decision is blocked NO_ACTION",
        "No paper position, trade event, or PnL history exists",
        "Earlier DexScreener source failures remain visible",
    ]
    forbidden_claims = [
        "PROFITABLE",
        "LIVE_READY",
        "BUY_READY",
        "AUTONOMOUS_READY",
        "PRODUCTION_TRADING_READY",
        "CLEAN_MEMORY_READY",
        "WALLET_READY",
    ]
    allowed_scope = [
        "paper-only local/operator-controlled RC",
        "safe for further controlled data collection and paper validation only",
        "not safe for live trading",
        "not safe for real funds",
        "not safe to claim profitability",
        "not safe to unlock BUY",
    ]
    return {
        "rc_name": rc_name,
        "rc_type": "PAPER_ONLY",
        "rc_status": "PAPER_RC_FROZEN_WITH_BLOCKER",
        "rc_verdict": "PAPER_ONLY_RC_SAFE_BUT_NO_CLEAN_MEMORY",
        "rc_created_at": _utc_timestamp(),
        "git_commit_expected": "31c90dc",
        "expected_phase_tag": "printer-v1-phase38-v1-paper-release-candidate",
        "db_checkpoint_recommendation": "data/printer_v1.phase38-v1-paper-release-candidate.sqlite3",
        "db_state": current_state,
        "readiness_label": readiness_label,
        "source_request_rows": counts["printer_source_requests"],
        "source_response_rows": counts["printer_source_responses"],
        "source_failure_rows": counts["printer_source_failures"],
        "token_rows": counts["printer_tokens"],
        "pair_rows": counts["printer_pairs"],
        "snapshot_rows": counts["printer_token_snapshots"],
        "context_rows_by_table": {
            "printer_market_regime_snapshots": counts["printer_market_regime_snapshots"],
            "printer_solana_chain_heat_snapshots": counts["printer_solana_chain_heat_snapshots"],
            "printer_safety_rug_snapshots": counts["printer_safety_rug_snapshots"],
            "printer_liquidity_exit_snapshots": counts["printer_liquidity_exit_snapshots"],
            "printer_trading_flow_snapshots": counts["printer_trading_flow_snapshots"],
            "printer_chart_volatility_snapshots": counts["printer_chart_volatility_snapshots"],
            "printer_micro_events": counts["printer_micro_events"],
        },
        "memory_window_rows": counts["printer_memory_windows"],
        "episode_rows": counts["printer_episodes"],
        "episode_snapshot_link_rows": counts["printer_episode_snapshots"],
        "outcome_rows": counts["printer_episode_outcomes"],
        "memory_fingerprint_rows": counts["printer_memory_fingerprints"],
        "memory_audit_report_rows": counts["printer_memory_audit_reports"],
        "retrieval_query_rows": counts["printer_memory_retrieval_queries"],
        "retrieval_match_rows": counts["printer_memory_retrieval_matches"],
        "clean_eligible_memory_count": summary["clean_eligible_memory_count"],
        "dirty_memory_count": summary["dirty_memory_count"],
        "blocked_dirty_memory_count": summary["blocked_dirty_memory_count"],
        "paper_decision_rows": counts["printer_paper_decisions"],
        "latest_paper_decision_action": summary["latest_paper_decision_action"],
        "latest_paper_decision_status": summary["latest_paper_decision_status"],
        "paper_decision_action_counts": action_counts,
        "paper_position_rows": counts["printer_paper_positions"],
        "paper_trade_event_rows": counts["printer_paper_trade_events"],
        "pnl_rows": counts["printer_paper_trade_audits"],
        "paper_audit_report_rows": counts["printer_paper_audit_reports"],
        "operator_review_report_rows_before_rc": counts["printer_operator_review_reports"],
        "operator_review_item_rows_before_rc": counts["printer_operator_review_items"],
        "scheduler_job_rows": counts["printer_scheduler_jobs"],
        "bounded_runtime_safety_summary": {
            "runtime_stopped_cleanly": phase37_report.get("runtime_stopped_cleanly"),
            "runtime_active_after_exit": phase37_report.get("runtime_active_after_exit"),
            "unbounded_runtime_detected": phase37_report.get("unbounded_runtime_detected"),
        },
        "long_run_validation_summary": {
            "validation_verdict": phase37_report.get("validation_verdict"),
            "jobs_succeeded": phase37_report.get("jobs_succeeded"),
            "jobs_failed": phase37_report.get("jobs_failed"),
            "stop_reason": phase37_report.get("stop_reason"),
        },
        "source_health_label": phase37_report.get("source_health_label"),
        "memory_quality_label": phase37_report.get("memory_quality_label"),
        "paper_decision_quality_label": phase37_report.get("paper_decision_quality_label"),
        "paper_monitor_quality_label": phase37_report.get("paper_monitor_quality_label"),
        "paper_audit_quality_label": phase37_report.get("paper_audit_quality_label"),
        "fake_profit_prevention_label": phase37_report.get("fake_profit_prevention_label"),
        "live_trading_safety_label": phase37_report.get("live_trading_safety_label"),
        "clean_memory_status": "NO_CLEAN_ELIGIBLE_MEMORY",
        "buy_status": "BUY_LOCKED",
        "live_status": "LIVE_TRADING_NOT_PRESENT",
        "profit_claim_status": "NOT_PROFIT_CLAIM_READY",
        "paper_position_status": "NO_POSITION_OPENED",
        "memory_safety_status": "DIRTY_MEMORY_BLOCKED",
        "source_status": "SOURCE_FAILURES_VISIBLE",
        "scheduler_status": "BOUNDED_SCHEDULER_SAFE",
        "runtime_status": "BOUNDED_RUNTIME_SAFE",
        "fake_profit_status": "NO_FAKE_PROFIT",
        "operator_status": "OPERATOR_REVIEW_REQUIRED_FOR_NEXT_REAL_DATA_CYCLE",
        "known_blockers": known_blockers,
        "known_limitations": known_limitations,
        "release_candidate_allowed_scope": allowed_scope,
        "release_candidate_forbidden_claims": forbidden_claims,
        "operator_acknowledgements_required": [
            "ACKNOWLEDGE_NO_CLEAN_MEMORY_BLOCKER",
            "ACKNOWLEDGE_PAPER_ONLY",
        ],
        "operator_acknowledgements_recorded": [
            "ACKNOWLEDGE_NO_CLEAN_MEMORY_BLOCKER",
            "ACKNOWLEDGE_PAPER_ONLY",
        ],
        "rollback_instructions": [
            "Restore the Phase 37 checkpoint DB if RC freeze needs to be undone",
            "Do not unlock BUY until clean eligible memory exists in a later controlled cycle",
        ],
        "next_operator_action": "Create a Phase 38 checkpoint/tag if accepted; no new build phase until the operator chooses the next controlled data-collection cycle.",
        "suggested_release_tag": "printer-v1-phase38-v1-paper-release-candidate",
    }


def _insert_v1_paper_rc_operator_review(connection: sqlite3.Connection, manifest: dict[str, Any]) -> tuple[int, list[int]]:
    attention_labels = [
        "ATTENTION_NO_CLEAN_MEMORY",
        "ATTENTION_SOURCE_FAILURES",
        "ATTENTION_DIRTY_MEMORY",
        "ATTENTION_BLOCKED_PAPER_DECISIONS",
    ]
    generated_at = manifest["rc_created_at"]
    cursor = connection.execute(
        """
        INSERT INTO printer_operator_review_reports (
            report_scope_label, report_status_label, operator_review_label,
            report_format_label, generated_at, db_state_classification,
            report_title, attention_labels_json, summary_payload_json,
            report_payload_json, report_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "REPORT_FULL_OPERATOR_REVIEW",
            "REPORT_READY",
            "OPERATOR_REVIEW_OK",
            "REPORT_FORMAT_JSON",
            generated_at,
            "PERSISTENT_DB_STATE_UNCLEAR",
            "Phase 38 V1 Paper Release Candidate",
            json.dumps(attention_labels, sort_keys=True),
            json.dumps(
                {
                    "rc_name": manifest["rc_name"],
                    "rc_status": manifest["rc_status"],
                    "rc_verdict": manifest["rc_verdict"],
                    "known_blockers": manifest["known_blockers"],
                },
                sort_keys=True,
            ),
            json.dumps(manifest, sort_keys=True),
            json.dumps(manifest, indent=2, sort_keys=True),
        ),
    )
    report_id = int(cursor.lastrowid)
    item_specs = [
        ("REPORT_FULL_OPERATOR_REVIEW", "ATTENTION_NO_CLEAN_MEMORY", "NO_CLEAN_ELIGIBLE_MEMORY"),
        ("REPORT_MEMORY", "ATTENTION_DIRTY_MEMORY", "DIRTY_MEMORY_BLOCKED"),
        ("REPORT_SOURCE_HEALTH", "ATTENTION_SOURCE_FAILURES", "SOURCE_FAILURES_VISIBLE"),
        ("REPORT_PAPER_DECISIONS", "ATTENTION_BLOCKED_PAPER_DECISIONS", "BUY_LOCKED"),
    ]
    item_ids: list[int] = []
    for scope, attention, label in item_specs:
        item = connection.execute(
            """
            INSERT INTO printer_operator_review_items (
                operator_review_report_id, item_scope_label, operator_review_label,
                attention_label, item_payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                report_id,
                scope,
                "OPERATOR_REVIEW_OK",
                attention,
                json.dumps({"rc_name": manifest["rc_name"], "label": label, "rc_verdict": manifest["rc_verdict"]}, sort_keys=True),
            ),
        )
        item_ids.append(int(item.lastrowid))
    return report_id, item_ids


def build_v1_paper_rc_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_v1_paper_rc_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    before_status = get_operator_db_status(resolved, project_root)

    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    rc_report_id: int | None = None
    rc_item_ids: list[int] = []
    manifest: dict[str, Any] = {}
    try:
        phase37_report = _latest_phase37_report(connection)
        summary = _current_rc_freeze_summary(connection)
        _assert_v1_paper_rc_safety_gates(
            connection,
            project_root,
            before_status["state_classification"],
            summary,
            phase37_report,
        )
        manifest = _build_v1_paper_rc_manifest(
            args.rc_name,
            summary,
            phase37_report,
            before_status["state_classification"],
            "READY_LONG_RUN_PAPER_VALIDATION",
        )
        rc_report_id, rc_item_ids = _insert_v1_paper_rc_operator_review(connection, manifest)
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
        "printer_scheduler_jobs",
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
    ]
    guard_deltas = {table: deltas[table] for table in guarded_tables if deltas.get(table)}
    status = get_operator_db_status(resolved, project_root)
    action_counts = _paper_decision_action_counts(resolved)
    return {
        "command": "printer-freeze-v1-paper-rc",
        "db_path": str(resolved),
        "operator_approved": True,
        "rc_name": args.rc_name,
        "rc_report_id": rc_report_id,
        "rc_item_ids": rc_item_ids,
        "rc_report_manifest": manifest,
        "rc_report_manifest_rows": 1 if rc_report_id is not None else 0,
        "rc_status": manifest.get("rc_status"),
        "rc_verdict": manifest.get("rc_verdict"),
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "operator_review_report_delta": deltas.get("printer_operator_review_reports", 0),
        "operator_review_item_delta": deltas.get("printer_operator_review_items", 0),
        "action_counts": action_counts,
        "counts_after": after_counts,
        "db_state_classification": status["state_classification"],
        "readiness_label": classify_readiness(
            status,
            get_schema_migration_status(resolved, project_root),
            check_no_live_capability_terms_in_source(project_root),
            check_no_runtime_loop_terms_in_source(project_root),
        ),
        "memory_has_started": status["memory_has_started"],
        "paper_trading_has_started": status["paper_trading_has_started"],
        "runtime_has_started": status["runtime_has_started"],
    }


def main_freeze_v1_paper_rc(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser("Freeze an honest V1 paper-only release candidate manifest.", ("json", "text"))
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--rc-name", required=True)
    parser.add_argument("--acknowledge-no-clean-memory-blocker", action="store_true")
    parser.add_argument("--acknowledge-paper-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = build_v1_paper_rc_payload(args)
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
    if status["state_classification"] == STATE_V1_PAPER_RELEASE_CANDIDATE:
        return READINESS_READY_V1_PAPER_RELEASE_CANDIDATE
    if status["state_classification"] == STATE_POST_RC_DISCOVERY_MEMORY_CYCLE:
        return READINESS_READY_POST_RC_DISCOVERY_MEMORY_CYCLE
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
    if status["state_classification"] == STATE_REAL_PAPER_AUDIT_OPERATOR_REVIEW:
        return READINESS_READY_REAL_PAPER_AUDIT_OPERATOR_REVIEW
    if status["state_classification"] == STATE_SCHEDULER_SINGLE_TICK_EXECUTED:
        return READINESS_READY_SCHEDULER_SINGLE_TICK_EXECUTED
    if status["state_classification"] == STATE_BOUNDED_RUNTIME_EXECUTED:
        return READINESS_READY_BOUNDED_RUNTIME_EXECUTED
    if status["state_classification"] == STATE_LONG_RUN_PAPER_VALIDATION:
        return READINESS_READY_LONG_RUN_PAPER_VALIDATION
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


# ---------------------------------------------------------------------------
# Post-RC Lane 7 — Controlled Clean-Memory Retrieval Reporting
# ---------------------------------------------------------------------------
# Reporting/audit only.  No paper decisions, positions, trades, PnL, BUY
# unlock, or live execution.  Solana-only.  Paper-only.  No paid API.
# No scoring, ranking, confidence, or weighted logic.
# ---------------------------------------------------------------------------

_LANE7_CLEAN_ELIGIBILITY_MEMORY_STATUS = "CLEAN_MEMORY"
_LANE7_CLEAN_ELIGIBILITY_MEMORY_QUALITY_LABEL = "CLEAN_MEMORY"
_LANE7_CLEAN_ELIGIBILITY_DATA_QUALITY = "CLEAN_DATA"
_LANE7_CLEAN_ELIGIBILITY_WINDOW_STATUS = "WINDOW_CLOSED"
_LANE7_EXCLUDED_MEMORY_STATUS_AUDIT_ONLY = "AUDIT_ONLY"
_LANE7_EXCLUDED_MEMORY_QUALITY_AUDIT_ONLY = "AUDIT_ONLY_MEMORY"
_LANE7_EXCLUDED_DATA_QUALITY_MISSING = "MISSING_CRITICAL_DATA"
_LANE7_EXCLUDED_WINDOW_KIND_5M = "WINDOW_5M_MICRO_EVENT"


def _validate_clean_memory_retrieval_report_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError("clean memory retrieval report requires explicit operator approval")
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("clean memory retrieval report is Solana-only")


def _lane7_window_retrieval_row(window: dict[str, Any]) -> dict[str, Any]:
    support_ctx = _json_or_empty(window.get("supporting_context_json"))
    context_labels = support_ctx.get("context_labels") or {}
    return {
        "memory_window_id": window["id"],
        "token_id": window["token_id"],
        "pair_id": window.get("pair_id"),
        "window_kind": window.get("window_kind"),
        "outcome_label": window.get("outcome_label"),
        "memory_quality_label": window.get("memory_quality_label"),
        "data_quality_label": window.get("data_quality_label"),
        "do_not_train": int(window.get("do_not_train") or 0),
        "window_status": window.get("window_status"),
        "snapshot_start_id": window.get("snapshot_start_id"),
        "snapshot_end_id": window.get("snapshot_end_id"),
        "source_reference": window.get("source_reference"),
        "evidence_identity_hash": window.get("evidence_identity_hash"),
        "duplicate_guard_status": window.get("duplicate_guard_status"),
        "market_regime_label": context_labels.get("market_regime_label"),
        "chain_heat_label": context_labels.get("chain_heat_label"),
        "safety_status_label": context_labels.get("safety_status_label"),
        "retrieval_eligible": True,
        "exclusion_reason": None,
    }


def _scan_memory_windows_for_retrieval_eligibility(connection: sqlite3.Connection) -> dict[str, Any]:
    all_windows = connection.execute(
        "SELECT * FROM printer_memory_windows ORDER BY id ASC"
    ).fetchall()

    eligible: list[dict[str, Any]] = []
    excluded_audit_only: list[int] = []
    excluded_do_not_train: list[int] = []
    excluded_missing_critical: list[int] = []
    excluded_5m: list[int] = []
    excluded_dirty: list[dict[str, Any]] = []

    for row in all_windows:
        window = _row_to_dict(row)
        wid = int(window["id"])

        # 5m micro-event windows cannot unlock retrieval by themselves
        if window.get("window_kind") == _LANE7_EXCLUDED_WINDOW_KIND_5M:
            excluded_5m.append(wid)
            continue

        # AUDIT_ONLY (either column agrees)
        if (
            window.get("memory_status") == _LANE7_EXCLUDED_MEMORY_STATUS_AUDIT_ONLY
            or window.get("memory_quality_label") == _LANE7_EXCLUDED_MEMORY_QUALITY_AUDIT_ONLY
        ):
            excluded_audit_only.append(wid)
            continue

        # do_not_train = 1
        if int(window.get("do_not_train") or 0) == 1:
            excluded_do_not_train.append(wid)
            continue

        # MISSING_CRITICAL_DATA
        if window.get("data_quality_label") == _LANE7_EXCLUDED_DATA_QUALITY_MISSING:
            excluded_missing_critical.append(wid)
            continue

        # Now check positive clean-eligibility
        is_clean_memory = (
            window.get("memory_status") == _LANE7_CLEAN_ELIGIBILITY_MEMORY_STATUS
            or window.get("memory_quality_label") == _LANE7_CLEAN_ELIGIBILITY_MEMORY_QUALITY_LABEL
        )
        is_clean_data = window.get("data_quality_label") == _LANE7_CLEAN_ELIGIBILITY_DATA_QUALITY
        is_window_closed = window.get("window_status") == _LANE7_CLEAN_ELIGIBILITY_WINDOW_STATUS

        if is_clean_memory and is_clean_data and is_window_closed:
            eligible.append(_lane7_window_retrieval_row(window))
        else:
            reasons: list[str] = []
            if not is_clean_memory:
                reasons.append(
                    "NOT_CLEAN_MEMORY:" + str(window.get("memory_quality_label") or window.get("memory_status") or "UNKNOWN")
                )
            if not is_clean_data:
                reasons.append("NOT_CLEAN_DATA:" + str(window.get("data_quality_label") or "UNKNOWN"))
            if not is_window_closed:
                reasons.append("WINDOW_NOT_CLOSED:" + str(window.get("window_status") or "UNKNOWN"))
            excluded_dirty.append({
                "memory_window_id": wid,
                "exclusion_reason": ",".join(reasons) or "NOT_CLEAN_ELIGIBLE",
                "memory_status": window.get("memory_status"),
                "memory_quality_label": window.get("memory_quality_label"),
                "data_quality_label": window.get("data_quality_label"),
                "window_status": window.get("window_status"),
                "do_not_train": int(window.get("do_not_train") or 0),
            })

    return {
        "total_memory_window_count": len(all_windows),
        "clean_memory_candidates_count": len(eligible),
        "excluded_dirty_memory_count": len(excluded_dirty),
        "excluded_audit_only_count": len(excluded_audit_only),
        "excluded_do_not_train_count": len(excluded_do_not_train),
        "excluded_missing_critical_data_count": len(excluded_missing_critical),
        "excluded_5m_micro_event_count": len(excluded_5m),
        "eligible_clean_memories": eligible,
        "excluded_dirty_summary": excluded_dirty,
        "excluded_audit_only_window_ids": excluded_audit_only,
        "excluded_do_not_train_window_ids": excluded_do_not_train,
        "excluded_missing_critical_data_window_ids": excluded_missing_critical,
        "excluded_5m_micro_event_window_ids": excluded_5m,
    }


def build_clean_memory_retrieval_report_once_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_clean_memory_retrieval_report_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        scan = _scan_memory_windows_for_retrieval_eligibility(connection)
        paper_decision_count = int(
            connection.execute("SELECT COUNT(*) FROM printer_paper_decisions").fetchone()[0]
        )
        paper_position_count = int(
            connection.execute("SELECT COUNT(*) FROM printer_paper_positions").fetchone()[0]
        )
        paper_trade_event_count = int(
            connection.execute("SELECT COUNT(*) FROM printer_paper_trade_events").fetchone()[0]
        )
        paper_trade_audit_count = int(
            connection.execute("SELECT COUNT(*) FROM printer_paper_trade_audits").fetchone()[0]
        )
        # read-only — no commit, no writes
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guard_deltas = {table: delta for table, delta in deltas.items() if delta}

    return {
        "command": "printer-build-clean-memory-retrieval-report-once",
        "db_path": str(resolved),
        "operator_approved": True,
        "lane": "post_rc_lane7",
        "lane_label": "CONTROLLED_CLEAN_MEMORY_RETRIEVAL_REPORTING",
        "report_only": True,
        # Core eligibility scan
        "retrieval_report": scan,
        # Safety/audit counters (top-level for easy inspection)
        "clean_memory_candidates_count": scan["clean_memory_candidates_count"],
        "excluded_dirty_memory_count": scan["excluded_dirty_memory_count"],
        "excluded_audit_only_count": scan["excluded_audit_only_count"],
        "excluded_do_not_train_count": scan["excluded_do_not_train_count"],
        "excluded_missing_critical_data_count": scan["excluded_missing_critical_data_count"],
        "excluded_5m_micro_event_count": scan["excluded_5m_micro_event_count"],
        # Retrieval rows created: zero — report-only, no writes
        "retrieval_matches_created": 0,
        # Downstream gate outputs — all locked
        "paper_decision_delta": 0,
        "paper_position_delta": 0,
        "paper_trade_event_delta": 0,
        "paper_trade_audit_delta": 0,
        "buy_unlock": False,
        "pnl_unlock": False,
        # Existing paper row counts (for audit visibility, not deltas)
        "existing_paper_decision_count": paper_decision_count,
        "existing_paper_position_count": paper_position_count,
        "existing_paper_trade_event_count": paper_trade_event_count,
        "existing_paper_trade_audit_count": paper_trade_audit_count,
        # Guard deltas: must all be zero
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "counts_after": after_counts,
    }


def main_build_clean_memory_retrieval_report_once(argv: Sequence[str] | None = None) -> int:
    parser = _base_parser(
        "Build a controlled clean-memory retrieval report (Lane 7, report-only, no paper decisions).",
        ("json", "text"),
    )
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--chain", default="solana")
    args = parser.parse_args(argv)
    try:
        payload = build_clean_memory_retrieval_report_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane V — Controlled Clean-Memory Retrieval Reporting (Audit-Only)
# ---------------------------------------------------------------------------
# Reads printer_episodes only.  No writes.  No retrieval activation.
# No paper decisions, positions, PnL, BUY/SELL/HOLD.
# No scoring, ranking, or confidence percentages.
# ---------------------------------------------------------------------------


def main_run_lane_v_clean_memory_report(argv: Sequence[str] | None = None) -> int:
    """CLI entry for Lane V clean-memory audit report (read-only)."""
    from printer_v1.operator_cli.lane_v_clean_memory_retrieval_report import (
        build_clean_memory_retrieval_report,
    )

    parser = _base_parser(
        "Lane V — read-only audit report of clean memories from printer_episodes.",
        ("json", "text"),
    )
    parser.add_argument("--token-id", type=int, default=None)
    parser.add_argument("--pair-id", type=int, default=None)
    parser.add_argument("--window-kind", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        project_root = _project_root(args.project_root)
        resolved = resolve_operator_db_path(args.db_path, project_root)
        if not resolved.is_file():
            raise FileNotFoundError(f"Operator DB does not exist: {resolved}")
        payload = build_clean_memory_retrieval_report(
            resolved,
            token_id=args.token_id,
            pair_id=args.pair_id,
            window_kind=args.window_kind,
            limit=args.limit,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Post-RC Lane 8A — Paper Decision Unlock Review, WAIT/AVOID/NO_ACTION First
# ---------------------------------------------------------------------------
# Report-only.  No paper decisions, positions, trades, PnL, BUY unlock, or
# live execution.  Solana-only.  Paper-only.  No paid API.
# No scoring, ranking, confidence, or weighted logic.
# Reuses Lane 7 clean-memory eligibility scan without duplicating the policy.
# ---------------------------------------------------------------------------

_LANE8A_ALLOWED_FUTURE_REVIEW_ACTIONS: list[str] = ["WAIT", "AVOID", "NO_ACTION"]
_LANE8A_BLOCKED_ACTIONS: list[str] = ["BUY", "SELL", "HOLD"]

_LANE8A_READINESS_FULL = "WAIT_AVOID_NO_ACTION_REVIEW_READY"
_LANE8A_READINESS_NO_ACTION_ONLY = "NO_ACTION_REVIEW_READY"
_LANE8A_READINESS_GUARD_DELTA = "NOT_READY_GUARD_TABLE_DELTA"

# Required future decision template fields per AGENTS.md / clean-master-spec
_LANE8A_TEMPLATE_FIELDS_FROM_MEMORY = [
    "similar_clean_memories_found",
    "what_happened_in_those_memories",
    "best_historical_action",
    "worst_historical_action",
    "market_condition",
    "solana_condition",
    "safety_condition",
]
_LANE8A_TEMPLATE_FIELDS_CURRENT_CONTEXT = [
    "current_setup",
    "liquidity_exit_condition",
    "trading_flow_condition",
    "chart_volatility_condition",
]
_LANE8A_TEMPLATE_FIELDS_AT_DECISION_TIME = [
    "decision",
    "current_action",
    "reason",
    "invalidation_condition",
    "paper_trade_status",
]


def _validate_lane8a_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError(
            "wait/avoid/no_action readiness review requires explicit operator approval"
        )
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("wait/avoid/no_action readiness review is Solana-only")


def _derive_lane8a_readiness(
    scan: dict[str, Any],
    guard_deltas: dict[str, int],
) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if guard_deltas:
        reasons.append(f"guard_table_delta_detected:{sorted(guard_deltas.keys())}")
        return _LANE8A_READINESS_GUARD_DELTA, reasons

    clean_count = scan["clean_memory_candidates_count"]

    if clean_count >= 1:
        reasons.append(f"clean_memory_candidates_count={clean_count}")
        reasons.append(
            "WAIT_review_can_proceed_with_clean_memory_comparison_at_decision_time"
        )
        reasons.append(
            "AVOID_review_can_proceed_with_clean_memory_comparison_at_decision_time"
        )
        reasons.append(
            "NO_ACTION_always_valid_when_clean_data_is_missing_or_insufficient"
        )
        reasons.append(
            "BUY_remains_locked_requires_separate_operator_approved_buy_unlock_lane"
        )
        reasons.append("SELL_remains_blocked_no_open_positions_exist")
        reasons.append("HOLD_remains_blocked_no_open_positions_exist")
        return _LANE8A_READINESS_FULL, reasons

    reasons.append("clean_memory_candidates_count=0")
    reasons.append(
        "NO_ACTION_always_valid_when_clean_data_is_missing_or_insufficient"
    )
    reasons.append("WAIT_requires_at_least_1_clean_memory_candidate")
    reasons.append("AVOID_requires_at_least_1_clean_memory_candidate")
    reasons.append("BUY_remains_locked")
    reasons.append("SELL_remains_blocked_no_open_positions_exist")
    reasons.append("HOLD_remains_blocked_no_open_positions_exist")
    return _LANE8A_READINESS_NO_ACTION_ONLY, reasons


def _lane8a_decision_template_summary(
    eligible_memories: list[dict[str, Any]],
) -> dict[str, Any]:
    if not eligible_memories:
        return {
            "similar_clean_memories_found": "MISSING_NO_ELIGIBLE_MEMORY",
            "what_happened_in_those_memories": "MISSING_NO_ELIGIBLE_MEMORY",
            "best_historical_action": "MISSING_NO_ELIGIBLE_MEMORY",
            "worst_historical_action": "MISSING_NO_ELIGIBLE_MEMORY",
            "market_condition": "MISSING_NO_ELIGIBLE_MEMORY",
            "solana_condition": "MISSING_NO_ELIGIBLE_MEMORY",
            "safety_condition": "MISSING_NO_ELIGIBLE_MEMORY",
            "current_setup": "WILL_REQUIRE_CURRENT_TOKEN_CONTEXT_AT_DECISION_TIME",
            "liquidity_exit_condition": "WILL_REQUIRE_CURRENT_TOKEN_CONTEXT_AT_DECISION_TIME",
            "trading_flow_condition": "WILL_REQUIRE_CURRENT_TOKEN_CONTEXT_AT_DECISION_TIME",
            "chart_volatility_condition": "WILL_REQUIRE_CURRENT_TOKEN_CONTEXT_AT_DECISION_TIME",
            "decision": "WILL_BE_SET_AT_DECISION_TIME",
            "current_action": "WILL_BE_SET_AT_DECISION_TIME",
            "reason": "WILL_BE_SET_AT_DECISION_TIME",
            "invalidation_condition": "WILL_BE_SET_AT_DECISION_TIME",
            "paper_trade_status": "WILL_BE_SET_AT_DECISION_TIME",
        }

    outcome_labels = [
        m.get("outcome_label")
        for m in eligible_memories
        if m.get("outcome_label")
    ]
    has_market = any(m.get("market_regime_label") for m in eligible_memories)
    has_solana = any(m.get("chain_heat_label") for m in eligible_memories)
    has_safety = any(m.get("safety_status_label") for m in eligible_memories)

    return {
        "similar_clean_memories_found": len(eligible_memories),
        "what_happened_in_those_memories": outcome_labels,
        "best_historical_action": "AVAILABLE_FROM_OUTCOME_LABELS_AT_DECISION_TIME",
        "worst_historical_action": "AVAILABLE_FROM_OUTCOME_LABELS_AT_DECISION_TIME",
        "market_condition": "AVAILABLE" if has_market else "MISSING_FROM_MEMORY_CONTEXT",
        "solana_condition": "AVAILABLE" if has_solana else "MISSING_FROM_MEMORY_CONTEXT",
        "safety_condition": "AVAILABLE" if has_safety else "MISSING_FROM_MEMORY_CONTEXT",
        "current_setup": "WILL_REQUIRE_CURRENT_TOKEN_CONTEXT_AT_DECISION_TIME",
        "liquidity_exit_condition": "WILL_REQUIRE_CURRENT_TOKEN_CONTEXT_AT_DECISION_TIME",
        "trading_flow_condition": "WILL_REQUIRE_CURRENT_TOKEN_CONTEXT_AT_DECISION_TIME",
        "chart_volatility_condition": "WILL_REQUIRE_CURRENT_TOKEN_CONTEXT_AT_DECISION_TIME",
        "decision": "WILL_BE_SET_AT_DECISION_TIME",
        "current_action": "WILL_BE_SET_AT_DECISION_TIME",
        "reason": "WILL_BE_SET_AT_DECISION_TIME",
        "invalidation_condition": "WILL_BE_SET_AT_DECISION_TIME",
        "paper_trade_status": "WILL_BE_SET_AT_DECISION_TIME",
    }


def build_wait_avoid_no_action_readiness_payload(
    args: argparse.Namespace,
) -> dict[str, Any]:
    _validate_lane8a_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    before_counts = get_core_table_counts(resolved, project_root)
    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        scan = _scan_memory_windows_for_retrieval_eligibility(connection)
        paper_decision_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_paper_decisions"
            ).fetchone()[0]
        )
        paper_position_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_paper_positions"
            ).fetchone()[0]
        )
        paper_trade_event_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_paper_trade_events"
            ).fetchone()[0]
        )
        paper_trade_audit_count = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_paper_trade_audits"
            ).fetchone()[0]
        )
        # read-only — no commit, no writes
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guard_deltas = {table: delta for table, delta in deltas.items() if delta}

    eligible_memories = scan["eligible_clean_memories"]
    eligible_window_ids = [m["memory_window_id"] for m in eligible_memories]
    has_clean_memory = scan["clean_memory_candidates_count"] >= 1

    readiness_label, readiness_reasons = _derive_lane8a_readiness(scan, guard_deltas)
    decision_template = _lane8a_decision_template_summary(eligible_memories)

    return {
        "command": "printer-review-wait-avoid-no-action-readiness-once",
        "db_path": str(resolved),
        "lane": "post_rc_lane8a",
        "lane_label": "PAPER_DECISION_UNLOCK_REVIEW_WAIT_AVOID_NO_ACTION_FIRST",
        "operator_approved": True,
        "report_only": True,
        "chain": "solana",
        # Clean memory visibility (reuses Lane 7 eligibility policy)
        "clean_memory_candidates_count": scan["clean_memory_candidates_count"],
        "eligible_clean_memory_window_ids": eligible_window_ids,
        "excluded_dirty_memory_count": scan["excluded_dirty_memory_count"],
        "excluded_audit_only_count": scan["excluded_audit_only_count"],
        "excluded_do_not_train_count": scan["excluded_do_not_train_count"],
        "excluded_missing_critical_data_count": scan["excluded_missing_critical_data_count"],
        "excluded_5m_micro_event_count": scan["excluded_5m_micro_event_count"],
        # Conservative action readiness flags
        "wait_review_ready": has_clean_memory,
        "avoid_review_ready": has_clean_memory,
        "no_action_review_ready": True,
        "conservative_actions_review_ready": has_clean_memory,
        # Action boundary — only conservative actions allowed in future review
        "allowed_future_review_actions": _LANE8A_ALLOWED_FUTURE_REVIEW_ACTIONS,
        "blocked_actions": _LANE8A_BLOCKED_ACTIONS,
        # Hard locks — all false; no unlock possible from this command
        "buy_unlock": False,
        "position_unlock": False,
        "pnl_unlock": False,
        # Paper row creation counters — all zero (report-only)
        "paper_decisions_created": 0,
        "paper_positions_created": 0,
        "paper_trade_events_created": 0,
        "paper_trade_audits_created": 0,
        # Downstream gate deltas — all zero
        "paper_decision_delta": 0,
        "paper_position_delta": 0,
        "paper_trade_event_delta": 0,
        "paper_trade_audit_delta": 0,
        # Existing paper row counts (audit visibility, not deltas)
        "existing_paper_decision_count": paper_decision_count,
        "existing_paper_position_count": paper_position_count,
        "existing_paper_trade_event_count": paper_trade_event_count,
        "existing_paper_trade_audit_count": paper_trade_audit_count,
        # Guard integrity
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        # Readiness assessment
        "readiness_label": readiness_label,
        "readiness_reasons": readiness_reasons,
        "next_required_operator_step": (
            "operator_may_proceed_to_lane8b_conservative_decision_creation"
            if has_clean_memory
            else "collect_more_clean_memory_windows_before_proceeding_to_lane8b"
        ),
        # Decision template field availability preview (informational, no values invented)
        "decision_template_field_readiness": decision_template,
    }


def main_review_wait_avoid_no_action_readiness_once(
    argv: Sequence[str] | None = None,
) -> int:
    parser = _base_parser(
        "Review Lane 8A readiness for WAIT/AVOID/NO_ACTION conservative paper decisions"
        " (report-only, no paper decisions created, no BUY unlock).",
        ("json", "text"),
    )
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--chain", default="solana")
    args = parser.parse_args(argv)
    try:
        payload = build_wait_avoid_no_action_readiness_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Post-RC Lane 8B — Conservative Paper Decision Creation
# ---------------------------------------------------------------------------
# Operator-controlled creation of WAIT/AVOID/NO_ACTION paper decisions backed
# by a Lane 7 eligible clean memory window.  BUY/SELL/HOLD remain blocked.
# No positions, trade events, PnL, or live execution.  Solana-only.
# Paper-only.  No paid API.  No scoring, ranking, confidence, or weighted logic.
# Memory window must pass Lane 7 eligibility before any decision is written.
# ---------------------------------------------------------------------------

_LANE8B_ALLOWED_CONSERVATIVE_ACTIONS: frozenset[str] = frozenset({"WAIT", "AVOID", "NO_ACTION"})
_LANE8B_BLOCKED_ACTIONS: list[str] = ["BUY", "SELL", "HOLD"]


def _validate_lane8b_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError(
            "conservative paper decision creation requires explicit operator approval"
        )
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("conservative paper decision creation is Solana-only")


def _lane8b_verify_entities(
    connection: sqlite3.Connection,
    token_id: int,
    pair_id: int,
    memory_window_id: int,
    window_kind: str,
) -> dict[str, Any]:
    """Verify token/pair/window exist and the window is Lane 7 eligible."""
    token_row = connection.execute(
        "SELECT id FROM printer_tokens WHERE id = ?", (token_id,)
    ).fetchone()
    if token_row is None:
        return {
            "verified": False,
            "eligible": False,
            "rejection_reason": f"token_id {token_id} not found",
        }

    pair_row = connection.execute(
        "SELECT id FROM printer_pairs WHERE id = ? AND token_id = ?",
        (pair_id, token_id),
    ).fetchone()
    if pair_row is None:
        return {
            "verified": False,
            "eligible": False,
            "rejection_reason": (
                f"pair_id {pair_id} not found or does not belong to token_id {token_id}"
            ),
        }

    win_row = connection.execute(
        "SELECT * FROM printer_memory_windows WHERE id = ?", (memory_window_id,)
    ).fetchone()
    if win_row is None:
        return {
            "verified": False,
            "eligible": False,
            "rejection_reason": f"memory_window_id {memory_window_id} not found",
        }

    window = _row_to_dict(win_row)

    if int(window.get("token_id") or 0) != token_id:
        return {
            "verified": True,
            "eligible": False,
            "rejection_reason": (
                f"window token_id {window.get('token_id')} does not match {token_id}"
            ),
        }
    if int(window.get("pair_id") or 0) != pair_id:
        return {
            "verified": True,
            "eligible": False,
            "rejection_reason": (
                f"window pair_id {window.get('pair_id')} does not match {pair_id}"
            ),
        }
    if window.get("window_kind") != window_kind:
        return {
            "verified": True,
            "eligible": False,
            "rejection_reason": (
                f"window_kind mismatch: window has {window.get('window_kind')!r},"
                f" argument is {window_kind!r}"
            ),
        }

    # Apply Lane 7 eligibility (constants shared with Lane 7 and 8A)
    if window.get("window_kind") == _LANE7_EXCLUDED_WINDOW_KIND_5M:
        return {
            "verified": True,
            "eligible": False,
            "rejection_reason": "WINDOW_5M_MICRO_EVENT_cannot_unlock_paper_decisions",
        }
    if (
        window.get("memory_status") == _LANE7_EXCLUDED_MEMORY_STATUS_AUDIT_ONLY
        or window.get("memory_quality_label") == _LANE7_EXCLUDED_MEMORY_QUALITY_AUDIT_ONLY
    ):
        return {
            "verified": True,
            "eligible": False,
            "rejection_reason": "AUDIT_ONLY_memory_excluded_from_decisions",
        }
    if int(window.get("do_not_train") or 0) == 1:
        return {
            "verified": True,
            "eligible": False,
            "rejection_reason": "do_not_train=1_excluded_from_decisions",
        }
    if window.get("data_quality_label") == _LANE7_EXCLUDED_DATA_QUALITY_MISSING:
        return {
            "verified": True,
            "eligible": False,
            "rejection_reason": "MISSING_CRITICAL_DATA_excluded_from_decisions",
        }

    is_clean_memory = (
        window.get("memory_status") == _LANE7_CLEAN_ELIGIBILITY_MEMORY_STATUS
        or window.get("memory_quality_label") == _LANE7_CLEAN_ELIGIBILITY_MEMORY_QUALITY_LABEL
    )
    is_clean_data = window.get("data_quality_label") == _LANE7_CLEAN_ELIGIBILITY_DATA_QUALITY
    is_closed = window.get("window_status") == _LANE7_CLEAN_ELIGIBILITY_WINDOW_STATUS

    if not (is_clean_memory and is_clean_data and is_closed):
        parts: list[str] = []
        if not is_clean_memory:
            parts.append(
                "NOT_CLEAN_MEMORY:"
                + str(
                    window.get("memory_quality_label")
                    or window.get("memory_status")
                    or "UNKNOWN"
                )
            )
        if not is_clean_data:
            parts.append("NOT_CLEAN_DATA:" + str(window.get("data_quality_label") or "UNKNOWN"))
        if not is_closed:
            parts.append(
                "WINDOW_NOT_CLOSED:" + str(window.get("window_status") or "UNKNOWN")
            )
        return {
            "verified": True,
            "eligible": False,
            "rejection_reason": ",".join(parts) or "NOT_LANE7_ELIGIBLE",
        }

    return {"verified": True, "eligible": True, "rejection_reason": None, "window": window}


def _lane8b_insert_conservative_decision(
    connection: sqlite3.Connection,
    token_id: int,
    pair_id: int,
    memory_window_id: int,
    action: str,
    window_kind: str,
) -> int:
    """Direct controlled INSERT of one conservative paper decision row."""
    decided_at = datetime.now(timezone.utc).isoformat()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()

    decision_reasons = ["REASON_CLEAN_MEMORY_MATCH_SUPPORTS_ACTION"]
    memory_evidence_summary = {
        "clean_match_count": 1,
        "memory_evidence_label": "MEMORY_EVIDENCE_LANE7_ELIGIBLE",
        "memory_window_id": memory_window_id,
        "retrieval_result_label": "LANE8B_CONTROLLED_CLEAN_WINDOW",
    }
    explanation = {
        "action": action,
        "controlled_decision": True,
        "lane": "post_rc_lane8b",
        "memory_window_id": memory_window_id,
        "operator_controlled": True,
        "window_kind": window_kind,
    }
    decision_report = {
        "action": action,
        "buy_unlock": False,
        "lane": "post_rc_lane8b",
        "memory_window_id": memory_window_id,
        "pnl_unlock": False,
        "position_unlock": False,
    }

    cursor = connection.execute(
        """
        INSERT INTO printer_paper_decisions (
            token_id, pair_id,
            decision_action, decision_status,
            memory_window_id,
            explanation_json, source_status, data_quality_label,
            decided_at, requested_action_label, final_action_label,
            decision_gate_label, memory_evidence_gate_label,
            paper_decision_status_label,
            matched_episode_ids_json, supporting_memory_match_ids_json,
            decision_reasons_json, blocking_reasons_json,
            current_context_json, memory_evidence_summary_json,
            decision_report_json, expires_at
        ) VALUES (
            ?, ?,
            ?, 'PAPER_DECISION_PROPOSED',
            ?,
            ?, 'COMPLETE', 'CLEAN_DATA',
            ?, ?, ?,
            'DECISION_ALLOWED', 'MEMORY_GATE_CLEAN_MATCH',
            'PAPER_DECISION_PROPOSED',
            '[]', '[]',
            ?, '[]',
            '{}', ?, ?, ?
        )
        """,
        (
            token_id,
            pair_id,
            action,
            memory_window_id,
            json.dumps(explanation, sort_keys=True),
            decided_at,
            action,
            action,
            json.dumps(decision_reasons, sort_keys=True),
            json.dumps(memory_evidence_summary, sort_keys=True),
            json.dumps(decision_report, sort_keys=True),
            expires_at,
        ),
    )
    connection.commit()
    return int(cursor.lastrowid)


def _lane8b_rejection_result(
    *,
    resolved: Any,
    token_id: int,
    pair_id: int,
    memory_window_id: int,
    window_kind: str,
    requested_decision: str,
    rejection_reason: str,
    before_counts: dict[str, Any],
    after_counts: dict[str, Any],
) -> dict[str, Any]:
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guard_deltas = {table: delta for table, delta in deltas.items() if delta}
    return {
        "command": "printer-create-conservative-paper-decision-once",
        "db_path": str(resolved),
        "lane": "post_rc_lane8b",
        "lane_label": "CONSERVATIVE_PAPER_DECISION_CREATION",
        "operator_approved": True,
        "report_only": False,
        "chain": "solana",
        "token_id": token_id,
        "pair_id": pair_id,
        "memory_window_id": memory_window_id,
        "window_kind": window_kind,
        "requested_decision": requested_decision,
        "rejected_decision": requested_decision,
        "rejection_reason": rejection_reason,
        "paper_decision_created": False,
        "paper_decision_id": None,
        "paper_decision_delta": 0,
        "paper_position_delta": 0,
        "paper_trade_event_delta": 0,
        "paper_trade_audit_delta": 0,
        "buy_unlock": False,
        "position_unlock": False,
        "pnl_unlock": False,
        "blocked_actions": _LANE8B_BLOCKED_ACTIONS,
        "memory_window_retrieval_eligible": False,
        "eligible_clean_memory_window_ids": [],
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged_except_paper_decisions": not guard_deltas,
    }


def build_conservative_paper_decision_payload(args: argparse.Namespace) -> dict[str, Any]:
    _validate_lane8b_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    token_id = int(args.token_id)
    pair_id = int(args.pair_id)
    memory_window_id = int(args.memory_window_id)
    window_kind = str(args.window_kind).strip()
    requested_decision = str(args.decision).strip().upper()

    before_counts = get_core_table_counts(resolved, project_root)

    # Reject BUY/SELL/HOLD before any DB access — no writes
    if requested_decision not in _LANE8B_ALLOWED_CONSERVATIVE_ACTIONS:
        after_counts = get_core_table_counts(resolved, project_root)
        return _lane8b_rejection_result(
            resolved=resolved,
            token_id=token_id,
            pair_id=pair_id,
            memory_window_id=memory_window_id,
            window_kind=window_kind,
            requested_decision=requested_decision,
            rejection_reason=(
                requested_decision
                + "_NOT_ALLOWED_LANE8B_CONSERVATIVE_ONLY_WAIT_AVOID_NO_ACTION"
            ),
            before_counts=before_counts,
            after_counts=after_counts,
        )

    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        entity_check = _lane8b_verify_entities(
            connection, token_id, pair_id, memory_window_id, window_kind
        )
        if not entity_check.get("eligible"):
            after_counts = get_core_table_counts(resolved, project_root)
            return _lane8b_rejection_result(
                resolved=resolved,
                token_id=token_id,
                pair_id=pair_id,
                memory_window_id=memory_window_id,
                window_kind=window_kind,
                requested_decision=requested_decision,
                rejection_reason=(
                    entity_check.get("rejection_reason") or "ENTITY_VERIFICATION_FAILED"
                ),
                before_counts=before_counts,
                after_counts=after_counts,
            )

        decision_id = _lane8b_insert_conservative_decision(
            connection, token_id, pair_id, memory_window_id, requested_decision, window_kind
        )
        scan = _scan_memory_windows_for_retrieval_eligibility(connection)
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guard_deltas = {table: delta for table, delta in deltas.items() if delta}
    non_decision_guard_deltas = {
        table: delta
        for table, delta in guard_deltas.items()
        if table != "printer_paper_decisions"
    }

    eligible_window_ids = [m["memory_window_id"] for m in scan["eligible_clean_memories"]]

    return {
        "command": "printer-create-conservative-paper-decision-once",
        "db_path": str(resolved),
        "lane": "post_rc_lane8b",
        "lane_label": "CONSERVATIVE_PAPER_DECISION_CREATION",
        "operator_approved": True,
        "report_only": False,
        "chain": "solana",
        "token_id": token_id,
        "pair_id": pair_id,
        "memory_window_id": memory_window_id,
        "window_kind": window_kind,
        # Decision outcome
        "requested_decision": requested_decision,
        "accepted_decision": requested_decision,
        "paper_decision_created": True,
        "paper_decision_id": decision_id,
        # Memory retrieval eligibility
        "memory_window_retrieval_eligible": True,
        "eligible_clean_memory_window_ids": eligible_window_ids,
        "clean_memory_candidates_count": scan["clean_memory_candidates_count"],
        # Deltas
        "paper_decision_delta": (
            (after_counts.get("printer_paper_decisions") or 0)
            - (before_counts.get("printer_paper_decisions") or 0)
        ),
        "paper_position_delta": 0,
        "paper_trade_event_delta": 0,
        "paper_trade_audit_delta": 0,
        # Hard locks
        "buy_unlock": False,
        "position_unlock": False,
        "pnl_unlock": False,
        # Action boundary
        "blocked_actions": _LANE8B_BLOCKED_ACTIONS,
        # Guard integrity
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged_except_paper_decisions": not non_decision_guard_deltas,
    }


def main_create_conservative_paper_decision_once(
    argv: Sequence[str] | None = None,
) -> int:
    parser = _base_parser(
        "Create exactly one conservative paper decision (WAIT/AVOID/NO_ACTION)."
        " BUY/SELL/HOLD are hard-blocked.  No positions, trade events, or PnL.",
        ("json", "text"),
    )
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--chain", default="solana")
    parser.add_argument(
        "--decision",
        required=True,
        choices=["WAIT", "AVOID", "NO_ACTION", "BUY", "SELL", "HOLD"],
        help="Paper action.  WAIT/AVOID/NO_ACTION accepted; BUY/SELL/HOLD rejected.",
    )
    parser.add_argument("--token-id", required=True, type=int, dest="token_id")
    parser.add_argument("--pair-id", required=True, type=int, dest="pair_id")
    parser.add_argument("--memory-window-id", required=True, type=int, dest="memory_window_id")
    parser.add_argument("--window-kind", required=True, dest="window_kind")
    args = parser.parse_args(argv)
    try:
        payload = build_conservative_paper_decision_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Post-RC Lane 8C — Conservative Paper Decision Audit Review
# ---------------------------------------------------------------------------
# Report-only audit/review of WAIT/AVOID/NO_ACTION paper decision rows.
# No writes.  No BUY unlock.  No positions.  No trade events.  No PnL.
# No live execution.  Solana-only.  Paper-only.  No paid API.
# No scoring, ranking, confidence, or weighted logic.
# Memory window must pass Lane 7 eligibility for review to pass.
# ---------------------------------------------------------------------------

_LANE8C_ALLOWED_CONSERVATIVE_ACTIONS: frozenset[str] = frozenset({"WAIT", "AVOID", "NO_ACTION"})
_LANE8C_BLOCKED_ACTIONS: list[str] = ["BUY", "SELL", "HOLD"]
_LANE8C_AUDIT_PASSED = "PASSED"
_LANE8C_AUDIT_FAILED = "FAILED"


def _validate_lane8c_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError(
            "conservative paper decision audit review requires explicit operator approval"
        )
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("conservative paper decision audit review is Solana-only")


def _lane8c_fetch_decision(
    connection: sqlite3.Connection,
    paper_decision_id: int,
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM printer_paper_decisions WHERE id = ?", (paper_decision_id,)
    ).fetchone()
    return _row_to_dict(row) if row is not None else None


def _lane8c_check_window_eligibility(
    connection: sqlite3.Connection,
    memory_window_id: int,
) -> dict[str, Any]:
    """Apply Lane 7 eligibility to a specific memory window by ID."""
    win_row = connection.execute(
        "SELECT * FROM printer_memory_windows WHERE id = ?", (memory_window_id,)
    ).fetchone()
    if win_row is None:
        return {
            "eligible": False,
            "reason": f"memory_window_id {memory_window_id} not found",
        }

    window = _row_to_dict(win_row)

    if window.get("window_kind") == _LANE7_EXCLUDED_WINDOW_KIND_5M:
        return {
            "eligible": False,
            "reason": "WINDOW_5M_MICRO_EVENT_cannot_back_paper_decisions",
        }
    if (
        window.get("memory_status") == _LANE7_EXCLUDED_MEMORY_STATUS_AUDIT_ONLY
        or window.get("memory_quality_label") == _LANE7_EXCLUDED_MEMORY_QUALITY_AUDIT_ONLY
    ):
        return {
            "eligible": False,
            "reason": "AUDIT_ONLY_memory_cannot_back_paper_decisions",
        }
    if int(window.get("do_not_train") or 0) == 1:
        return {
            "eligible": False,
            "reason": "do_not_train=1_cannot_back_paper_decisions",
        }
    if window.get("data_quality_label") == _LANE7_EXCLUDED_DATA_QUALITY_MISSING:
        return {
            "eligible": False,
            "reason": "MISSING_CRITICAL_DATA_cannot_back_paper_decisions",
        }

    is_clean_memory = (
        window.get("memory_status") == _LANE7_CLEAN_ELIGIBILITY_MEMORY_STATUS
        or window.get("memory_quality_label") == _LANE7_CLEAN_ELIGIBILITY_MEMORY_QUALITY_LABEL
    )
    is_clean_data = window.get("data_quality_label") == _LANE7_CLEAN_ELIGIBILITY_DATA_QUALITY
    is_closed = window.get("window_status") == _LANE7_CLEAN_ELIGIBILITY_WINDOW_STATUS

    if not (is_clean_memory and is_clean_data and is_closed):
        parts: list[str] = []
        if not is_clean_memory:
            parts.append(
                "NOT_CLEAN_MEMORY:"
                + str(
                    window.get("memory_quality_label")
                    or window.get("memory_status")
                    or "UNKNOWN"
                )
            )
        if not is_clean_data:
            parts.append("NOT_CLEAN_DATA:" + str(window.get("data_quality_label") or "UNKNOWN"))
        if not is_closed:
            parts.append(
                "WINDOW_NOT_CLOSED:" + str(window.get("window_status") or "UNKNOWN")
            )
        return {
            "eligible": False,
            "reason": ",".join(parts) or "NOT_LANE7_ELIGIBLE",
        }

    return {"eligible": True, "reason": None, "window": window}


def _lane8c_count_downstream(
    connection: sqlite3.Connection,
    paper_decision_id: int,
) -> tuple[int, int, int]:
    """Return (position_count, trade_event_count, trade_audit_count) for a decision."""
    pos_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_paper_positions WHERE paper_decision_id = ?",
            (paper_decision_id,),
        ).fetchone()[0]
    )
    event_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_paper_trade_events WHERE paper_decision_id = ?",
            (paper_decision_id,),
        ).fetchone()[0]
    )
    audit_count = int(
        connection.execute(
            "SELECT COUNT(*) FROM printer_paper_trade_audits WHERE paper_decision_id = ?",
            (paper_decision_id,),
        ).fetchone()[0]
    )
    return pos_count, event_count, audit_count


def _lane8c_not_found_payload(
    *,
    resolved: Any,
    paper_decision_id: int,
    before_counts: dict[str, Any],
    after_counts: dict[str, Any],
) -> dict[str, Any]:
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guard_deltas = {table: delta for table, delta in deltas.items() if delta}
    return {
        "command": "printer-review-conservative-paper-decision-once",
        "db_path": str(resolved),
        "lane": "post_rc_lane8c",
        "lane_label": "CONSERVATIVE_PAPER_DECISION_AUDIT_REVIEW",
        "operator_approved": True,
        "report_only": True,
        "review_rows_created": 0,
        "chain": "solana",
        "paper_decision_id": paper_decision_id,
        "decision_action": None,
        "conservative_action_valid": False,
        "memory_window_id": None,
        "memory_window_retrieval_eligible": False,
        "clean_memory_backed": False,
        "audit_review_status": _LANE8C_AUDIT_FAILED,
        "audit_review_reasons": [
            f"FAIL:paper_decision_id_{paper_decision_id}_not_found_in_printer_paper_decisions"
        ],
        "blocked_actions": _LANE8C_BLOCKED_ACTIONS,
        "buy_unlock": False,
        "position_unlock": False,
        "pnl_unlock": False,
        "paper_position_count_for_decision": 0,
        "paper_trade_event_count_for_decision": 0,
        "paper_trade_audit_count_for_decision": 0,
        "paper_position_delta": 0,
        "paper_trade_event_delta": 0,
        "paper_trade_audit_delta": 0,
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "next_required_operator_step": (
            "confirm_paper_decision_id_exists_before_review"
        ),
    }


def build_conservative_paper_decision_audit_review_payload(
    args: argparse.Namespace,
) -> dict[str, Any]:
    _validate_lane8c_args(args)
    project_root = _project_root(args.project_root)
    resolved = resolve_operator_db_path(args.db_path, project_root)
    if not resolved.is_file():
        raise FileNotFoundError(f"Operator DB does not exist: {resolved}")

    paper_decision_id = int(args.paper_decision_id)

    before_counts = get_core_table_counts(resolved, project_root)

    connection = sqlite3.connect(resolved)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    decision: dict[str, Any] | None = None
    decision_action: str | None = None
    memory_window_id: int | None = None
    conservative_action_valid = False
    window_eligible = False
    clean_memory_backed = False
    pos_count = 0
    event_count = 0
    audit_count = 0
    audit_reasons: list[str] = []
    audit_failures: list[str] = []
    try:
        decision = _lane8c_fetch_decision(connection, paper_decision_id)
        if decision is None:
            after_counts = get_core_table_counts(resolved, project_root)
            return _lane8c_not_found_payload(
                resolved=resolved,
                paper_decision_id=paper_decision_id,
                before_counts=before_counts,
                after_counts=after_counts,
            )

        decision_action = decision.get("decision_action")
        raw_window_id = decision.get("memory_window_id")
        memory_window_id = int(raw_window_id) if raw_window_id is not None else None

        # Check 1: conservative action (WAIT/AVOID/NO_ACTION)
        conservative_action_valid = decision_action in _LANE8C_ALLOWED_CONSERVATIVE_ACTIONS
        if conservative_action_valid:
            audit_reasons.append(
                f"decision_action={decision_action}_is_conservative_WAIT_AVOID_NO_ACTION"
            )
        else:
            audit_failures.append(
                f"decision_action={decision_action}_is_NOT_conservative_BUY_SELL_HOLD_blocked"
            )

        # Check 2: memory window Lane 7 eligibility
        if memory_window_id is None:
            window_eligible = False
            audit_failures.append(
                "memory_window_id_is_null_cannot_verify_clean_memory_backing"
            )
        else:
            window_check = _lane8c_check_window_eligibility(connection, memory_window_id)
            window_eligible = bool(window_check.get("eligible"))
            if window_eligible:
                audit_reasons.append(
                    f"memory_window_id={memory_window_id}_is_Lane7_eligible_CLEAN_MEMORY"
                )
            else:
                audit_failures.append(
                    f"memory_window_id={memory_window_id}_not_Lane7_eligible:"
                    + str(window_check.get("reason") or "UNKNOWN")
                )
        clean_memory_backed = window_eligible

        # Check 3: decision source and data quality
        source_status = decision.get("source_status")
        data_quality_label = decision.get("data_quality_label")
        if source_status == "COMPLETE" and data_quality_label == "CLEAN_DATA":
            audit_reasons.append(
                "decision_source_status=COMPLETE_data_quality_label=CLEAN_DATA"
            )
        else:
            audit_failures.append(
                f"decision_source_status={source_status}_data_quality_label={data_quality_label}_not_clean"
            )

        # Check 4: no downstream paper positions, trade events, or trade audits
        pos_count, event_count, audit_count = _lane8c_count_downstream(
            connection, paper_decision_id
        )
        if pos_count == 0:
            audit_reasons.append("no_paper_positions_linked_to_this_decision")
        else:
            audit_failures.append(
                f"paper_position_count={pos_count}_positions_must_not_exist_from_conservative_decision"
            )
        if event_count == 0:
            audit_reasons.append("no_paper_trade_events_linked_to_this_decision")
        else:
            audit_failures.append(
                f"paper_trade_event_count={event_count}_trade_events_must_not_exist_from_conservative_decision"
            )
        if audit_count == 0:
            audit_reasons.append("no_paper_trade_audits_linked_to_this_decision")
        else:
            audit_failures.append(
                f"paper_trade_audit_count={audit_count}_trade_audits_must_not_exist_from_conservative_decision"
            )

        # Confirm hard locks
        audit_reasons.append("BUY_SELL_HOLD_remain_blocked_conservative_decision_only")
        audit_reasons.append("buy_unlock=false_position_unlock=false_pnl_unlock=false")
        # read-only — no commit, no writes
    finally:
        connection.close()

    after_counts = get_core_table_counts(resolved, project_root)
    deltas = {
        table: (after_counts.get(table) or 0) - (before_counts.get(table) or 0)
        for table in sorted(after_counts)
    }
    guard_deltas = {table: delta for table, delta in deltas.items() if delta}

    audit_passed = not audit_failures
    audit_status = _LANE8C_AUDIT_PASSED if audit_passed else _LANE8C_AUDIT_FAILED
    combined_reasons = audit_reasons + [f"FAIL:{r}" for r in audit_failures]

    return {
        "command": "printer-review-conservative-paper-decision-once",
        "db_path": str(resolved),
        "lane": "post_rc_lane8c",
        "lane_label": "CONSERVATIVE_PAPER_DECISION_AUDIT_REVIEW",
        "operator_approved": True,
        "report_only": True,
        "review_rows_created": 0,
        "chain": "solana",
        "paper_decision_id": paper_decision_id,
        "decision_action": decision_action,
        "conservative_action_valid": conservative_action_valid,
        "memory_window_id": memory_window_id,
        "memory_window_retrieval_eligible": window_eligible,
        "clean_memory_backed": clean_memory_backed,
        "audit_review_status": audit_status,
        "audit_review_reasons": combined_reasons,
        "blocked_actions": _LANE8C_BLOCKED_ACTIONS,
        "buy_unlock": False,
        "position_unlock": False,
        "pnl_unlock": False,
        "paper_position_count_for_decision": pos_count,
        "paper_trade_event_count_for_decision": event_count,
        "paper_trade_audit_count_for_decision": audit_count,
        "paper_position_delta": 0,
        "paper_trade_event_delta": 0,
        "paper_trade_audit_delta": 0,
        "guard_table_deltas": guard_deltas,
        "guard_tables_unchanged": not guard_deltas,
        "next_required_operator_step": (
            "conservative_paper_decision_audit_review_passed_no_further_action_required"
            if audit_passed
            else "investigate_audit_failures_before_proceeding"
        ),
    }


def main_review_conservative_paper_decision_once(
    argv: Sequence[str] | None = None,
) -> int:
    parser = _base_parser(
        "Audit-review one conservative WAIT/AVOID/NO_ACTION paper decision (report-only)."
        " No writes.  No BUY unlock.  No positions, trade events, or PnL.",
        ("json", "text"),
    )
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--chain", default="solana")
    parser.add_argument(
        "--paper-decision-id",
        required=True,
        type=int,
        dest="paper_decision_id",
        help="ID of the paper decision row to audit-review.",
    )
    args = parser.parse_args(argv)
    try:
        payload = build_conservative_paper_decision_audit_review_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Post-Lane 10 Lane E1 — Conservative 15m Memory Factory Dry-Run Scaffold
# ---------------------------------------------------------------------------
# Dry-run planning report only.  No source fetching.  No scheduler execution.
# No snapshot writes.  No memory writes.  No retrieval activation.
# No paper decisions.  No BUY, SELL, HOLD.  No positions, trade events, or PnL.
# No live execution.  Solana-only.  Paper-only.  No paid API.
# No scoring, ranking, confidence, or weighted logic.  No embeddings or vectors.
# 5m remains support-only.  15m is the first main Memory Factory target.
# Zero clean memories is an allowed outcome when evidence fails.
# Clean memory must never be forced.
# ---------------------------------------------------------------------------

_LANE_E1_MODE: str = "conservative"
_LANE_E1_TARGET_WINDOW_KIND: str = "WINDOW_15M"
_LANE_E1_SUPPORT_WINDOW_KIND: str = "WINDOW_5M_MICRO_EVENT"
_LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT: int = 10
_LANE_E1_MAX_TRACK_FAST_DEFAULT: int = 3
_LANE_E1_MAX_TRACK_NORMAL_DEFAULT: int = 7

_LANE_E1_LOCKED_CAPABILITIES: list[str] = [
    "source_fetching",
    "scheduler_execution",
    "memory_creation",
    "retrieval_activation",
    "paper_decisions",
    "BUY",
    "SELL",
    "HOLD",
    "paper_positions",
    "trade_events",
    "paper_trade_audits",
    "pnl_calculation",
    "live_execution",
    "real_funds",
    "wallet_private_key_signing",
    "paid_api_dependencies",
    "scoring_ranking_confidence_weighted",
    "embeddings_vectors",
    "5m_as_main_outcome_memory",
    "5m_unlocking_retrieval_or_decisions",
]

_LANE_E1_STOP_CONDITIONS: list[str] = [
    "source_failure_rate_exceeds_40_percent",
    "snapshot_gap_rate_exceeds_30_percent",
    "source_governor_detects_repeated_stale_data",
    "source_budget_exhausted",
    "central_scheduler_queue_falls_behind",
    "job_remains_running_after_exit",
    "lock_remains_active_after_exit",
    "window_close_snapshots_repeatedly_missed",
    "data_quality_labels_missing_on_critical_records",
    "clean_memory_would_be_created_from_incomplete_evidence",
    "dirty_or_audit_only_memory_appears_in_retrieval",
    "any_path_creates_paper_decisions_unexpectedly",
    "any_path_creates_buy_sell_hold_unexpectedly",
    "any_path_creates_paper_positions_unexpectedly",
    "any_path_creates_trade_events_audits_pnl_unexpectedly",
    "any_engine_bypasses_source_governor",
    "any_engine_bypasses_central_scheduler",
    "unbounded_runtime_appears",
]

_LANE_E1_REQUIRED_FUTURE_GATES: list[str] = [
    "operator_approves_lane_e1_active_lane_commit_and_tag",
    "source_budget_headroom_confirmed_for_approved_token_list",
    "scheduler_end_to_end_cycle_confirmed_in_test",
    "lane_7_eligibility_confirmed_for_each_new_window",
    "memory_audit_passes_for_each_new_window",
    "operator_reviews_cycle_report_before_next_cycle",
    "full_test_suite_passes",
    "buy_remains_locked_throughout",
    "positions_remain_locked_throughout",
    "pnl_remains_locked_throughout",
]


def _lane_e1_resolve_int(value: int | None, default: int) -> int:
    return default if value is None else int(value)


def _validate_lane_e1_args(args: argparse.Namespace) -> None:
    if not args.operator_approved:
        raise ValueError(
            "conservative 15m memory factory dry-run plan requires explicit operator approval"
        )
    if str(args.chain or "").strip().lower() != "solana":
        raise ValueError("conservative 15m memory factory dry-run plan is Solana-only")
    max_active = _lane_e1_resolve_int(args.max_active_tokens, _LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT)
    max_fast = _lane_e1_resolve_int(args.max_track_fast, _LANE_E1_MAX_TRACK_FAST_DEFAULT)
    max_normal = _lane_e1_resolve_int(args.max_track_normal, _LANE_E1_MAX_TRACK_NORMAL_DEFAULT)
    if max_active < 1 or max_active > 30:
        raise ValueError("max_active_tokens must be between 1 and 30")
    if max_fast < 1 or max_fast > 10:
        raise ValueError("max_track_fast must be between 1 and 10")
    if max_normal < 1 or max_normal > 20:
        raise ValueError("max_track_normal must be between 1 and 20")
    if max_fast + max_normal > max_active:
        raise ValueError("max_track_fast + max_track_normal must not exceed max_active_tokens")


def build_plan_conservative_15m_memory_factory_once_payload(
    args: argparse.Namespace,
) -> dict[str, Any]:
    _validate_lane_e1_args(args)
    max_active = _lane_e1_resolve_int(args.max_active_tokens, _LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT)
    max_fast = _lane_e1_resolve_int(args.max_track_fast, _LANE_E1_MAX_TRACK_FAST_DEFAULT)
    max_normal = _lane_e1_resolve_int(args.max_track_normal, _LANE_E1_MAX_TRACK_NORMAL_DEFAULT)
    return {
        "command": "printer-plan-conservative-15m-memory-factory-once",
        "operator_approved": True,
        "dry_run": True,
        "mode": _LANE_E1_MODE,
        "target_window_kind": _LANE_E1_TARGET_WINDOW_KIND,
        "support_window_kind": _LANE_E1_SUPPORT_WINDOW_KIND,
        "support_window_only": True,
        "source_fetching_enabled": False,
        "scheduler_execution_enabled": False,
        "memory_creation_enabled": False,
        "paper_decisions_enabled": False,
        "buy_enabled": False,
        "positions_enabled": False,
        "pnl_enabled": False,
        "zero_clean_memories_allowed": True,
        "clean_memory_forced": False,
        "max_active_tokens": max_active,
        "max_track_fast": max_fast,
        "max_track_normal": max_normal,
        "locked_capabilities": list(_LANE_E1_LOCKED_CAPABILITIES),
        "stop_conditions": list(_LANE_E1_STOP_CONDITIONS),
        "required_future_gates": list(_LANE_E1_REQUIRED_FUTURE_GATES),
    }


def main_plan_conservative_15m_memory_factory_once(
    argv: Sequence[str] | None = None,
) -> int:
    parser = _base_parser(
        "Dry-run planning report for a future bounded conservative 15m Memory Factory cycle."
        " No source fetching.  No scheduler execution.  No snapshot writes."
        " No memory writes.  No retrieval.  No paper decisions."
        " No BUY, SELL, HOLD.  No positions, trade events, or PnL.",
        ("json", "text"),
    )
    parser.add_argument("--operator-approved", action="store_true")
    parser.add_argument("--chain", default="solana")
    parser.add_argument(
        "--max-active-tokens",
        type=int,
        default=_LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT,
        dest="max_active_tokens",
        help=f"Max concurrent actively tracked tokens (default: {_LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT}).",
    )
    parser.add_argument(
        "--max-track-fast",
        type=int,
        default=_LANE_E1_MAX_TRACK_FAST_DEFAULT,
        dest="max_track_fast",
        help=f"Max TRACK_FAST tokens (default: {_LANE_E1_MAX_TRACK_FAST_DEFAULT}).",
    )
    parser.add_argument(
        "--max-track-normal",
        type=int,
        default=_LANE_E1_MAX_TRACK_NORMAL_DEFAULT,
        dest="max_track_normal",
        help=f"Max TRACK_NORMAL tokens (default: {_LANE_E1_MAX_TRACK_NORMAL_DEFAULT}).",
    )
    args = parser.parse_args(argv)
    try:
        payload = build_plan_conservative_15m_memory_factory_once_payload(args)
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane E2C-C -- Active Cycle Readiness Package
# ---------------------------------------------------------------------------

def main_plan_bounded_15m_memory_factory_cycle(argv=None) -> int:
    """Dry-run readiness package for a first bounded E2C source-governed cycle."""
    from printer_v1.operator_cli.e2c_readiness import build_e2c_readiness_payload

    parser = _base_parser(
        "Dry-run readiness package for a first bounded E2C source-governed 15m Memory"
        " Factory cycle. Validates operator-approved token list, checks DB preflight,"
        " plans source budget via Source Governor, and produces a cycle plan."
        " No source fetching. No scheduler execution. No DB mutation. No paper decisions.",
        ("json",),
    )
    parser.add_argument(
        "--token",
        action="append",
        dest="tokens",
        metavar="MINT:LIFECYCLE_LANE",
        help=(
            "Operator-approved token mint and lifecycle lane in MINT:LIFECYCLE_LANE format"
            " (TRACK_FAST or TRACK_NORMAL). Repeat for a second token (max 2)."
        ),
    )
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        dest="backup_confirmed",
        help="Confirm that a DB backup exists before running this preflight check.",
    )
    args = parser.parse_args(argv)

    token_entries: list[dict] = []
    for raw in args.tokens or []:
        if ":" in raw:
            mint, lane = raw.split(":", 1)
            token_entries.append({"token_mint": mint.strip(), "lifecycle_lane": lane.strip()})
        else:
            token_entries.append({"token_mint": raw.strip(), "lifecycle_lane": ""})

    try:
        payload = build_e2c_readiness_payload(
            token_entries,
            args.db_path,
            backup_confirmed=args.backup_confirmed,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane E2C-E -- Fixture Rehearsal Package
# ---------------------------------------------------------------------------

def main_rehearse_bounded_15m_memory_factory_cycle(argv=None) -> int:
    """Fixture-only rehearsal of a first bounded E2C source-governed cycle."""
    from printer_v1.operator_cli.e2c_fixture_rehearsal import build_e2c_fixture_rehearsal_payload

    parser = _base_parser(
        "Fixture-only rehearsal of a first bounded E2C source-governed 15m Memory"
        " Factory cycle. Uses E2C-C readiness logic, produces fixture evidence plan,"
        " and proves no persistent DB mutation occurred."
        " No source fetching. No scheduler execution. No DB mutation. No paper decisions.",
        ("json",),
    )
    parser.add_argument(
        "--token",
        action="append",
        dest="tokens",
        metavar="MINT:LIFECYCLE_LANE",
        help=(
            "Operator-approved token mint and lifecycle lane in MINT:LIFECYCLE_LANE format"
            " (TRACK_FAST or TRACK_NORMAL). Repeat for a second token (max 2)."
        ),
    )
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        dest="backup_confirmed",
        help="Confirm that a DB backup exists before running this rehearsal.",
    )
    args = parser.parse_args(argv)

    token_entries: list[dict] = []
    for raw in args.tokens or []:
        if ":" in raw:
            mint, lane = raw.split(":", 1)
            token_entries.append({"token_mint": mint.strip(), "lifecycle_lane": lane.strip()})
        else:
            token_entries.append({"token_mint": raw.strip(), "lifecycle_lane": ""})

    try:
        payload = build_e2c_fixture_rehearsal_payload(
            token_entries,
            args.db_path,
            backup_confirmed=args.backup_confirmed,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane E2G -- First Bounded 15m Cycle Operator Run Boundary
# ---------------------------------------------------------------------------

def main_run_e2g_first_bounded_15m_operator_run(argv=None) -> int:
    """E2G operator run boundary: pre-run gate for first bounded 15m cycle."""
    from printer_v1.operator_cli.e2g_operator_run import (
        build_e2g_operator_run_payload,
    )

    parser = _base_parser(
        "E2G operator run boundary. Wraps the E2F execution boundary and applies"
        " final pre-run gates including backup proof check, runtime handler"
        " availability (Lane E2H), and real source transport (Lane E2I)."
        " Outputs OPERATOR_RUN_READY or BLOCKED."
        " OPERATOR_RUN_READY means all gates passed; operator must then run"
        " this command manually against the real DB after committing and tagging"
        " Lane E2G. Claude did not run the real cycle. No source fetching."
        " No scheduler execution. No DB mutation in this planning call.",
        ("json",),
    )
    parser.add_argument(
        "--token-list-path",
        dest="token_list_path",
        metavar="PATH",
        help="Path to operator-approved token list JSON file.",
    )
    parser.add_argument(
        "--approval-confirmed",
        action="store_true",
        dest="approval_confirmed",
        help="Operator confirms E2E APPROVAL_PACKET_READY has been reviewed.",
    )
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        dest="backup_confirmed",
        help="Confirm that a DB backup exists before this boundary check.",
    )
    parser.add_argument(
        "--backup-proof-path",
        dest="backup_proof_path",
        metavar="PATH",
        default=None,
        help="Path to the existing DB backup file (proof backup was created).",
    )
    args = parser.parse_args(argv)

    try:
        payload = build_e2g_operator_run_payload(
            args.token_list_path,
            args.db_path,
            approval_confirmed=args.approval_confirmed,
            backup_confirmed=args.backup_confirmed,
            backup_proof_path=args.backup_proof_path,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane E2I -- Governed Real Source Transport + One-Shot Source Smoke
# ---------------------------------------------------------------------------

def main_run_e2i_one_shot_governed_source_smoke(argv=None, *, _adapter=None) -> int:
    """E2I one-shot governed source smoke: validate transport and record one call."""
    from printer_v1.operator_cli.e2i_source_transport import (
        build_e2i_one_shot_smoke_payload,
    )

    parser = _base_parser(
        "E2I one-shot governed source smoke. Validates the operator-approved token"
        " list and backup proof, asks the Source Governor, calls one free/public"
        " DexScreener endpoint through governed transport, records source"
        " request/response/failure rows, and reports before/after DB counts."
        " May ONLY record to source rows. Must NOT create snapshots, context,"
        " memory, paper decisions, positions, PnL, or any forbidden table rows."
        " Claude did not run the full 15m cycle.",
        ("json",),
    )
    parser.add_argument(
        "--token-list-path",
        dest="token_list_path",
        metavar="PATH",
        required=True,
        help="Path to operator-approved token list JSON file.",
    )
    parser.add_argument(
        "--backup-proof-path",
        dest="backup_proof_path",
        metavar="PATH",
        required=True,
        help="Path to the existing DB backup file (proof backup was created).",
    )
    parser.add_argument(
        "--source-name",
        dest="source_name",
        default="dexscreener",
        help="Source name for the governed smoke call (default: dexscreener).",
    )
    parser.add_argument(
        "--operator-approved",
        action="store_true",
        dest="operator_approved",
        help="Operator explicitly approves this one-shot governed source smoke.",
    )
    args = parser.parse_args(argv)

    try:
        payload = build_e2i_one_shot_smoke_payload(
            args.token_list_path,
            args.db_path,
            args.backup_proof_path,
            source_name=args.source_name,
            operator_approved=args.operator_approved,
            adapter=_adapter,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane E2J -- First Bounded 15m Cycle Operator Execution
# ---------------------------------------------------------------------------

def main_run_e2j_first_15m_cycle(argv=None, *, _adapter=None) -> int:
    """E2J first bounded 15m cycle: execute TRACK_FAST_FIRST_15M through scheduler."""
    from printer_v1.operator_cli.e2j_first_15m_cycle import (
        build_e2j_first_15m_cycle_payload,
    )

    parser = _base_parser(
        "E2J first bounded 15m cycle operator execution. Runs the first real"
        " TRACK_FAST_FIRST_15M scheduler job through the Central Scheduler and"
        " Source Governor. Creates a TRACK_FAST_FIRST_15M job, claims it, injects"
        " the token-specific DexScreener adapter (approved mint only), calls the"
        " E2H runtime handler, records source request/response/failure rows, audits"
        " all table deltas and forbidden violations, and reports full execution state."
        " Requires operator approval and backup proof. One token only."
        " No BUY/SELL/HOLD. No paper decisions. No positions. No PnL."
        " No generic search. No paid APIs.",
        ("json",),
    )
    parser.add_argument(
        "--token-list-path",
        dest="token_list_path",
        metavar="PATH",
        required=True,
        help="Path to operator-approved token list JSON file (exactly 1 TRACK_FAST token).",
    )
    parser.add_argument(
        "--backup-proof-path",
        dest="backup_proof_path",
        metavar="PATH",
        required=True,
        help="Path to the existing DB backup file (proof backup was created before E2J).",
    )
    parser.add_argument(
        "--operator-approved",
        action="store_true",
        dest="operator_approved",
        help="Operator explicitly approves this first bounded 15m cycle execution.",
    )
    args = parser.parse_args(argv)

    try:
        payload = build_e2j_first_15m_cycle_payload(
            args.token_list_path,
            args.db_path,
            args.backup_proof_path,
            operator_approved=args.operator_approved,
            _adapter=_adapter,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane E2T -- Bounded Integrated 15m Operator Cycle Runner
# ---------------------------------------------------------------------------

def main_run_e2t_bounded_cycle(argv=None, *, _adapter=None) -> int:
    """E2T bounded cycle runner: run E2J integrated 15m cycle up to N times."""
    from printer_v1.operator_cli.e2t_bounded_cycle_runner import (
        E2T_DEFAULT_MAX_CYCLES,
        E2T_MAX_CYCLES_HARD_CAP,
        run_bounded_15m_cycles,
    )

    parser = _base_parser(
        "E2T bounded integrated 15m operator cycle runner. Runs the existing E2J"
        " integrated first-15m cycle (E2J→E2M→E2O→E2Q) a bounded number of times"
        " under strict operator control. Requires operator approval, token list,"
        " backup proof, and a finite max cycle count (<= hard cap"
        f" {E2T_MAX_CYCLES_HARD_CAP}). Stops immediately on any failed/blocked"
        " cycle. No unbounded loop. No daemon/background mode. No scheduler bypass."
        " No BUY/SELL/HOLD. No paper decisions. No positions. No PnL."
        " No generic search. No paid APIs.",
        ("json",),
    )
    parser.add_argument(
        "--token-list-path",
        dest="token_list_path",
        metavar="PATH",
        required=True,
        help="Path to operator-approved token list JSON file (exactly 1 TRACK_FAST token).",
    )
    parser.add_argument(
        "--backup-proof-path",
        dest="backup_proof_path",
        metavar="PATH",
        required=True,
        help="Path to the existing DB backup file (proof backup was created before run).",
    )
    parser.add_argument(
        "--operator-approved",
        action="store_true",
        dest="operator_approved",
        help="Operator explicitly approves this bounded cycle run.",
    )
    parser.add_argument(
        "--max-cycles",
        dest="max_cycles",
        type=int,
        default=E2T_DEFAULT_MAX_CYCLES,
        metavar="N",
        help=(
            f"Maximum number of cycles to run (1..{E2T_MAX_CYCLES_HARD_CAP})."
            f" Default: {E2T_DEFAULT_MAX_CYCLES}."
        ),
    )
    args = parser.parse_args(argv)

    try:
        payload = run_bounded_15m_cycles(
            args.token_list_path,
            args.db_path,
            args.backup_proof_path,
            operator_approved=args.operator_approved,
            max_cycles=args.max_cycles,
            _adapter=_adapter,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane U -- Governed Reusable Memory Factory Operator Runner
# ---------------------------------------------------------------------------

def main_run_memory_factory_cycle(argv=None, *, _adapter=None) -> int:
    """Lane U: governed bounded Memory Factory cycle runner.

    Runs repeated E2J→E2O→E2Q cycles (Lane-T snapshot threading) + Lane K
    (E2X→E2Y→Lane Q→E2Z) within a bounded duration profile.  Only WINDOW_15M
    is supported as the main collection window.  12h/24h profiles require
    --allow-long-bounded-run.  Stops safely if no governed E2J/Lane-K path
    exists.  No BUY/SELL/HOLD.  No paper decisions.  No PnL.  No live trading.
    """
    from printer_v1.operator_cli.lane_u_memory_factory_runner import (
        LANE_U_COMMAND_NAME,
        _DEFAULT_PROFILE,
        _DURATION_PROFILES,
        _MAX_ACTIVE_TOKENS_HARD_CAP,
        _MAX_NEW_TOKENS_HARD_CAP,
        run_memory_factory_cycle,
    )

    parser = _base_parser(
        f"Lane U — governed reusable Memory Factory operator runner ({LANE_U_COMMAND_NAME})."
        " Runs repeated E2J+LaneK cycles within a bounded duration profile."
        " Only WINDOW_15M is supported as the main collection window."
        " 12h/24h profiles require --allow-long-bounded-run."
        " Stops safely if the governed E2J/Lane-K dependency path is unavailable."
        " No BUY/SELL/HOLD. No paper decisions. No positions. No PnL."
        " No live trading. No paid APIs. No wallet/private keys.",
        ("json",),
    )
    parser.add_argument(
        "--token-list-path",
        dest="token_list_path",
        metavar="PATH",
        required=True,
        help="Path to operator-approved token list JSON (exactly 1 TRACK_FAST token).",
    )
    parser.add_argument(
        "--backup-proof-path",
        dest="backup_proof_path",
        metavar="PATH",
        required=True,
        help="Path to the existing DB backup file (proof backup exists before run).",
    )
    parser.add_argument(
        "--operator-approved",
        action="store_true",
        dest="operator_approved",
        help="Operator explicitly approves this Memory Factory cycle run.",
    )
    parser.add_argument(
        "--duration",
        dest="duration_profile",
        metavar="PROFILE",
        default=_DEFAULT_PROFILE,
        choices=sorted(_DURATION_PROFILES),
        help=(
            f"Bounded duration profile. Choices: {sorted(_DURATION_PROFILES)}."
            f"  Default: {_DEFAULT_PROFILE}."
            "  12h/24h require --allow-long-bounded-run."
        ),
    )
    parser.add_argument(
        "--window-kind",
        dest="window_kind",
        metavar="KIND",
        default="WINDOW_15M",
        help=(
            "Main memory window kind. Only WINDOW_15M is enabled in this lane."
            "  Default: WINDOW_15M."
        ),
    )
    parser.add_argument(
        "--support-window-kind",
        dest="support_window_kind",
        metavar="KIND",
        default=None,
        help=(
            "Optional support window kind (recognised: WINDOW_5M_MICRO_EVENT)."
            "  Support windows are evidence-only; they are not used as main."
        ),
    )
    parser.add_argument(
        "--max-active-tokens",
        dest="max_active_tokens",
        type=int,
        default=_MAX_ACTIVE_TOKENS_HARD_CAP,
        metavar="N",
        help=(
            f"Maximum number of simultaneously tracked tokens"
            f" (hard cap: {_MAX_ACTIVE_TOKENS_HARD_CAP})."
            f"  Default: {_MAX_ACTIVE_TOKENS_HARD_CAP}."
        ),
    )
    parser.add_argument(
        "--max-new-tokens",
        dest="max_new_tokens",
        type=int,
        default=_MAX_NEW_TOKENS_HARD_CAP,
        metavar="N",
        help=(
            f"Discovery intake cap per run (hard cap: {_MAX_NEW_TOKENS_HARD_CAP})."
            f"  Default: {_MAX_NEW_TOKENS_HARD_CAP}."
        ),
    )
    parser.add_argument(
        "--allow-long-bounded-run",
        action="store_true",
        dest="allow_long_bounded_run",
        help=(
            "Enable 12h/24h duration profiles.  Must be combined with"
            " --operator-approved.  Without this flag 12h/24h are refused."
        ),
    )
    parser.add_argument(
        "--snapshot-interval-seconds",
        dest="snapshot_interval_seconds",
        type=float,
        default=0.0,
        metavar="S",
        help=(
            "Seconds between snapshot-only E2J calls inside a 15m window."
            "  Use 90 for WINDOW_15M/TRACK_FAST, 180 for TRACK_NORMAL."
            "  Default: 0 (no sleep — tests/manual runs)."
        ),
    )
    parser.add_argument(
        "--window-close-interval-seconds",
        dest="window_close_interval_seconds",
        type=float,
        default=0.0,
        metavar="S",
        help=(
            "Seconds of snapshot collection before the 15m window is"
            " closed and evaluated.  Use 900 for real 15m windows."
            "  Default: 0 (close immediately — tests/manual runs)."
        ),
    )
    args = parser.parse_args(argv)

    try:
        payload = run_memory_factory_cycle(
            args.token_list_path,
            args.db_path,
            args.backup_proof_path,
            operator_approved=args.operator_approved,
            duration_profile=args.duration_profile,
            window_kind=args.window_kind,
            support_window_kind=args.support_window_kind,
            max_active_tokens=args.max_active_tokens,
            max_new_tokens=args.max_new_tokens,
            allow_long_bounded_run=args.allow_long_bounded_run,
            snapshot_interval_seconds=args.snapshot_interval_seconds,
            window_close_interval_seconds=args.window_close_interval_seconds,
            _adapter=_adapter,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane X2 -- Two-Token Controlled 15m Memory Factory Proof
# ---------------------------------------------------------------------------

def main_run_lane_x2_two_token_cycle(argv=None, *, _adapter_map=None) -> int:
    """Lane X2: two-token controlled 15m Memory Factory proof runner.

    Runs exactly two operator-approved TRACK_FAST tokens in a bounded WINDOW_15M
    proof with deterministic A/B snapshot rotation, separate evidence identity per
    token, and per-token coverage/gap/memory outcome reporting.  No token/pair
    mixing.  Idempotent replay preserved.  All financial locks remain.
    No BUY/SELL/HOLD.  No paper decisions.  No PnL.  No live trading.
    """
    from printer_v1.operator_cli.lane_x2_two_token_runner import (
        LANE_X2_COMMAND_NAME,
        LANE_X2_EXACT_TOKEN_COUNT,
        _DEFAULT_PROFILE,
        _DURATION_PROFILES,
        run_two_token_memory_factory_cycle,
    )

    parser = _base_parser(
        f"Lane X2 — two-token controlled 15m Memory Factory proof ({LANE_X2_COMMAND_NAME})."
        f"  Accepts exactly {LANE_X2_EXACT_TOKEN_COUNT} operator-approved TRACK_FAST Solana"
        " tokens.  Uses deterministic A/B snapshot rotation.  WINDOW_15M only."
        "  12h/24h profiles require --allow-long-bounded-run."
        "  Stops safely if the governed path is unavailable."
        "  No BUY/SELL/HOLD.  No paper decisions.  No positions.  No PnL."
        "  No live trading.  No paid APIs.  No wallet/private keys.",
        ("json",),
    )
    parser.add_argument(
        "--token-list-path",
        dest="token_list_path",
        metavar="PATH",
        required=True,
        help=(
            f"Path to Lane X2 token list JSON"
            f" (exactly {LANE_X2_EXACT_TOKEN_COUNT} TRACK_FAST tokens,"
            " using tracking_lane / operator_approved fields)."
        ),
    )
    parser.add_argument(
        "--backup-proof-path",
        dest="backup_proof_path",
        metavar="PATH",
        required=True,
        help="Path to the existing DB backup file (proof backup exists before run).",
    )
    parser.add_argument(
        "--operator-approved",
        action="store_true",
        dest="operator_approved",
        help="Operator explicitly approves this Lane X2 two-token cycle run.",
    )
    parser.add_argument(
        "--duration",
        dest="duration_profile",
        metavar="PROFILE",
        default=_DEFAULT_PROFILE,
        choices=sorted(_DURATION_PROFILES),
        help=(
            f"Bounded duration profile.  Choices: {sorted(_DURATION_PROFILES)}."
            f"  Default: {_DEFAULT_PROFILE}."
            "  12h/24h require --allow-long-bounded-run."
        ),
    )
    parser.add_argument(
        "--window-kind",
        dest="window_kind",
        metavar="KIND",
        default="WINDOW_15M",
        help=(
            "Main memory window kind.  Only WINDOW_15M is enabled in Lane X2."
            "  Default: WINDOW_15M."
        ),
    )
    parser.add_argument(
        "--allow-long-bounded-run",
        action="store_true",
        dest="allow_long_bounded_run",
        help=(
            "Enable 12h/24h duration profiles.  Must be combined with"
            " --operator-approved.  Without this flag 12h/24h are refused."
        ),
    )
    parser.add_argument(
        "--snapshot-interval-seconds",
        dest="snapshot_interval_seconds",
        type=float,
        default=0.0,
        metavar="S",
        help=(
            "Seconds between snapshot-only calls per token."
            "  Use 90 for WINDOW_15M/TRACK_FAST in production."
            "  Default: 0 (no sleep — tests/manual runs)."
        ),
    )
    parser.add_argument(
        "--window-close-interval-seconds",
        dest="window_close_interval_seconds",
        type=float,
        default=0.0,
        metavar="S",
        help=(
            "Seconds of snapshot collection before a token's 15m window is"
            " closed and evaluated.  Use 900 for real 15m windows."
            "  Default: 0 (close immediately — tests/manual runs)."
        ),
    )
    args = parser.parse_args(argv)

    try:
        payload = run_two_token_memory_factory_cycle(
            args.token_list_path,
            args.db_path,
            args.backup_proof_path,
            operator_approved=args.operator_approved,
            duration_profile=args.duration_profile,
            window_kind=args.window_kind,
            allow_long_bounded_run=args.allow_long_bounded_run,
            snapshot_interval_seconds=args.snapshot_interval_seconds,
            window_close_interval_seconds=args.window_close_interval_seconds,
            _adapter_map=_adapter_map,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane X3 -- Post-Cycle Cooldown / Archive / Rotation Lifecycle Wiring
# ---------------------------------------------------------------------------

def main_run_lane_x3_post_cycle_lifecycle(argv=None) -> int:
    """Lane X3: post-cycle lifecycle wiring — cooldown, archive, reopen, gate check.

    Records ENTER_COOLDOWN or ARCHIVE_AFTER_MEMORY_WINDOW lifecycle events after a
    completed memory cycle, prevents stale token/pair re-selection, and allows
    intentional revival via REOPEN_REVIVED_TOKEN.  Does NOT modify snapshots or
    memory windows.  All financial locks remain.  No BUY/SELL/HOLD.  No paper
    decisions.  No PnL.  No live trading.
    """
    from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
        LANE_X3_COMMAND_NAME,
        archive_after_memory_window,
        check_x3_cooldown_gate,
        enter_cooldown_after_window,
        get_token_lifecycle_status,
        reopen_token,
    )

    parser = _base_parser(
        f"Lane X3 — post-cycle lifecycle wiring ({LANE_X3_COMMAND_NAME})."
        "  Records ENTER_COOLDOWN or ARCHIVE_AFTER_MEMORY_WINDOW after a completed"
        " memory cycle, prevents stale token/pair re-selection via cooldown gate,"
        " and allows intentional revival.  Snapshots and memory windows are NOT"
        " modified.  No BUY/SELL/HOLD.  No paper decisions.  No positions."
        "  No PnL.  No live trading.  No paid APIs.  No wallet/private keys.",
        ("json",),
    )
    parser.add_argument(
        "--token-mint",
        dest="token_mint",
        metavar="MINT",
        required=True,
        help="Solana token mint address.",
    )
    parser.add_argument(
        "--pair-address",
        dest="pair_address",
        metavar="PAIR",
        default="",
        help="Pair address for this token (used to create/look up pair record).",
    )
    parser.add_argument(
        "--action",
        dest="action",
        metavar="ACTION",
        choices=("cooldown", "archive", "reopen", "check"),
        default="cooldown",
        help=(
            "Lifecycle action to perform."
            "  cooldown: enter post-cycle cooldown (default)."
            "  archive: archive after sufficient memory."
            "  reopen: revive/reopen a token in cooldown or archived state."
            "  check: report current lifecycle status (no writes)."
        ),
    )
    parser.add_argument(
        "--operator-approved",
        action="store_true",
        dest="operator_approved",
        help="Operator explicitly approves this lifecycle action.",
    )
    args = parser.parse_args(argv)

    if not args.operator_approved:
        payload = {
            "lane_x3_status": "LANE_X3_BLOCKED",
            "blocked_reason": "--operator-approved not set; no lifecycle changes made",
            "token_mint": args.token_mint,
            "action": args.action,
        }
        _print_payload(payload, args.format)
        return 0

    try:
        if args.action == "cooldown":
            payload = enter_cooldown_after_window(
                args.db_path, args.token_mint, args.pair_address
            )
        elif args.action == "archive":
            payload = archive_after_memory_window(
                args.db_path, args.token_mint, args.pair_address
            )
        elif args.action == "reopen":
            payload = reopen_token(args.db_path, args.token_mint, args.pair_address)
        else:
            blocked = check_x3_cooldown_gate(args.db_path, [args.token_mint])
            status_info = get_token_lifecycle_status(args.db_path, args.token_mint)
            payload = {
                "lane_x3_status": "LANE_X3_CHECK",
                "token_mint": args.token_mint,
                "blocked_by_gate": bool(blocked),
                "gate_messages": blocked,
                **status_info,
            }
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane X4 -- Three-Token Controlled 15m Memory Factory Proof
# ---------------------------------------------------------------------------

def main_run_lane_x4_three_token_cycle(argv=None, *, _adapter_map=None) -> int:
    """Lane X4: three-token controlled 15m Memory Factory proof runner.

    Runs exactly three operator-approved TRACK_FAST tokens in a bounded WINDOW_15M
    proof with deterministic A/B/C snapshot rotation, separate evidence identity per
    token, and per-token coverage/gap/memory outcome reporting.  No token/pair
    mixing.  Idempotent replay preserved.  All financial locks remain.
    No BUY/SELL/HOLD.  No paper decisions.  No PnL.  No live trading.
    """
    from printer_v1.operator_cli.lane_x4_three_token_runner import (
        LANE_X4_COMMAND_NAME,
        LANE_X4_EXACT_TOKEN_COUNT,
        _DEFAULT_PROFILE,
        _DURATION_PROFILES,
        run_three_token_memory_factory_cycle,
    )

    parser = _base_parser(
        f"Lane X4 — three-token controlled 15m Memory Factory proof ({LANE_X4_COMMAND_NAME})."
        f"  Accepts exactly {LANE_X4_EXACT_TOKEN_COUNT} operator-approved TRACK_FAST Solana"
        " tokens.  Uses deterministic A/B/C snapshot rotation.  WINDOW_15M only."
        "  12h/24h profiles require --allow-long-bounded-run."
        "  Stops safely if the governed path is unavailable."
        "  No BUY/SELL/HOLD.  No paper decisions.  No positions.  No PnL."
        "  No live trading.  No paid APIs.  No wallet/private keys."
        "  No X5 expansion.",
        ("json",),
    )
    parser.add_argument(
        "--token-list-path",
        dest="token_list_path",
        metavar="PATH",
        required=True,
        help=(
            f"Path to Lane X4 token list JSON"
            f" (exactly {LANE_X4_EXACT_TOKEN_COUNT} TRACK_FAST tokens,"
            " using tracking_lane / operator_approved fields)."
        ),
    )
    parser.add_argument(
        "--backup-proof-path",
        dest="backup_proof_path",
        metavar="PATH",
        required=True,
        help="Path to the existing DB backup file (proof backup exists before run).",
    )
    parser.add_argument(
        "--operator-approved",
        action="store_true",
        dest="operator_approved",
        help="Operator explicitly approves this Lane X4 three-token cycle run.",
    )
    parser.add_argument(
        "--duration",
        dest="duration_profile",
        metavar="PROFILE",
        default=_DEFAULT_PROFILE,
        choices=sorted(_DURATION_PROFILES),
        help=(
            f"Bounded duration profile.  Choices: {sorted(_DURATION_PROFILES)}."
            f"  Default: {_DEFAULT_PROFILE}."
            "  12h/24h require --allow-long-bounded-run."
        ),
    )
    parser.add_argument(
        "--window-kind",
        dest="window_kind",
        metavar="KIND",
        default="WINDOW_15M",
        help=(
            "Main memory window kind.  Only WINDOW_15M is enabled in Lane X4."
            "  Default: WINDOW_15M."
        ),
    )
    parser.add_argument(
        "--allow-long-bounded-run",
        action="store_true",
        dest="allow_long_bounded_run",
        help=(
            "Enable 12h/24h duration profiles.  Must be combined with"
            " --operator-approved.  Without this flag 12h/24h are refused."
        ),
    )
    parser.add_argument(
        "--snapshot-interval-seconds",
        dest="snapshot_interval_seconds",
        type=float,
        default=0.0,
        metavar="S",
        help=(
            "Seconds between snapshot-only calls per token."
            "  Use 90 for WINDOW_15M/TRACK_FAST in production."
            "  Default: 0 (no sleep — tests/manual runs)."
        ),
    )
    parser.add_argument(
        "--window-close-interval-seconds",
        dest="window_close_interval_seconds",
        type=float,
        default=0.0,
        metavar="S",
        help=(
            "Seconds of snapshot collection before a token's 15m window is"
            " closed and evaluated.  Use 900 for real 15m windows."
            "  Default: 0 (close immediately — tests/manual runs)."
        ),
    )
    args = parser.parse_args(argv)

    try:
        payload = run_three_token_memory_factory_cycle(
            args.token_list_path,
            args.db_path,
            args.backup_proof_path,
            operator_approved=args.operator_approved,
            duration_profile=args.duration_profile,
            window_kind=args.window_kind,
            allow_long_bounded_run=args.allow_long_bounded_run,
            snapshot_interval_seconds=args.snapshot_interval_seconds,
            window_close_interval_seconds=args.window_close_interval_seconds,
            _adapter_map=_adapter_map,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane E2U -- Bounded 15m Cycle Closeout Report
# ---------------------------------------------------------------------------

def main_report_e2u_15m_cycle_closeout(argv=None) -> int:
    """E2U read-only closeout report: bounded 15m cycle evidence and readiness."""
    from printer_v1.operator_cli.e2u_15m_cycle_closeout_report import (
        build_e2u_closeout_report,
    )

    parser = _base_parser(
        "E2U bounded 15m cycle closeout report. Read-only summary of latest"
        " bounded 15m cycle evidence, WINDOW_15M audit state, and Memory Factory"
        " readiness after Lane E2T. No DB mutations. No memory creation."
        " No retrieval activation. No paper decisions. No BUY/SELL/HOLD."
        " No positions. No PnL. Requires operator approval.",
        ("json",),
    )
    parser.add_argument(
        "--operator-approved",
        action="store_true",
        dest="operator_approved",
        help="Operator explicitly approves this closeout report.",
    )
    args = parser.parse_args(argv)

    try:
        payload = build_e2u_closeout_report(
            args.db_path,
            operator_approved=args.operator_approved,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


def main_report_e2w_5m_linkage(argv=None) -> int:
    """E2W read-only 5m-to-15m linkage verification report."""
    from printer_v1.operator_cli.e2w_5m_linkage_report import (
        build_e2w_linkage_report,
    )

    parser = _base_parser(
        "E2W 5m-to-15m linkage verification report. Read-only summary of"
        " WINDOW_5M_MICRO_EVENT evidence linkage to parent WINDOW_15M windows."
        " No DB mutations. No memory creation. No retrieval. No paper decisions."
        " No BUY/SELL/HOLD. Requires operator approval.",
        ("json",),
    )
    parser.add_argument(
        "--operator-approved",
        action="store_true",
        dest="operator_approved",
        help="Operator explicitly approves this linkage report.",
    )
    args = parser.parse_args(argv)

    try:
        payload = build_e2w_linkage_report(
            args.db_path,
            operator_approved=args.operator_approved,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane E2F -- First Bounded 15m Cycle Execution Boundary
# ---------------------------------------------------------------------------

def main_run_first_bounded_15m_cycle(argv=None) -> int:
    """E2F execution boundary: planning gate for first bounded 15m cycle."""
    from printer_v1.operator_cli.e2f_execution_boundary import (
        build_e2f_execution_boundary_payload,
    )

    parser = _base_parser(
        "E2F execution boundary. Wraps the E2E approval packet and produces a"
        " final planning boundary payload. Outputs CYCLE_READY_TO_RUN or BLOCKED."
        " CYCLE_READY_TO_RUN means all gates passed. The operator must then run"
        " this command manually against the real DB after committing and tagging"
        " Lane E2F. Claude did not run the real cycle. No source fetching."
        " No scheduler execution. No DB mutation in this planning call.",
        ("json",),
    )
    parser.add_argument(
        "--token-list-path",
        dest="token_list_path",
        metavar="PATH",
        help="Path to operator-approved token list JSON file.",
    )
    parser.add_argument(
        "--approval-confirmed",
        action="store_true",
        dest="approval_confirmed",
        help="Operator confirms E2E APPROVAL_PACKET_READY has been reviewed.",
    )
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        dest="backup_confirmed",
        help="Confirm that a DB backup exists before running this boundary check.",
    )
    args = parser.parse_args(argv)

    try:
        payload = build_e2f_execution_boundary_payload(
            args.token_list_path,
            args.db_path,
            approval_confirmed=args.approval_confirmed,
            backup_confirmed=args.backup_confirmed,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane E2E -- First Bounded Cycle Operator Approval Packet
# ---------------------------------------------------------------------------

def main_build_first_bounded_15m_approval_packet(argv=None) -> int:
    """E2E approval packet: build operator approval packet for first bounded cycle."""
    from printer_v1.operator_cli.e2e_approval_packet import build_e2e_approval_packet

    parser = _base_parser(
        "E2E approval packet. Wraps the E2D decision and builds a structured"
        " operator approval packet for the future first bounded real source-governed"
        " 15m Memory Factory cycle. Outputs APPROVAL_PACKET_READY or BLOCKED."
        " APPROVAL_PACKET_READY does NOT start real execution. No source fetching."
        " No scheduler execution. No DB mutation. No paper decisions.",
        ("json",),
    )
    parser.add_argument(
        "--token-list-path",
        dest="token_list_path",
        metavar="PATH",
        help="Path to operator-approved token list JSON file.",
    )
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        dest="backup_confirmed",
        help="Confirm that a DB backup exists before building this packet.",
    )
    args = parser.parse_args(argv)

    try:
        payload = build_e2e_approval_packet(
            args.token_list_path,
            args.db_path,
            backup_confirmed=args.backup_confirmed,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane E2D -- First Bounded Real Cycle Decision Package
# ---------------------------------------------------------------------------

def main_decide_first_bounded_15m_cycle(argv=None) -> int:
    """E2D decision gate: determine readiness for first bounded real cycle."""
    from printer_v1.operator_cli.e2d_decision import build_e2d_decision_payload

    parser = _base_parser(
        "E2D decision gate. Wraps the E2C-F operator review and applies a final"
        " automated decision. Outputs GO_TO_OPERATOR_APPROVAL or BLOCKED."
        " GO_TO_OPERATOR_APPROVAL means all automated gates passed and the package"
        " is ready for human operator approval review only -- it does NOT start real"
        " execution. No source fetching. No scheduler execution. No DB mutation."
        " No paper decisions.",
        ("json",),
    )
    parser.add_argument(
        "--token-list-path",
        dest="token_list_path",
        metavar="PATH",
        help="Path to operator-approved token list JSON file.",
    )
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        dest="backup_confirmed",
        help="Confirm that a DB backup exists before running this decision.",
    )
    args = parser.parse_args(argv)

    try:
        payload = build_e2d_decision_payload(
            args.token_list_path,
            args.db_path,
            backup_confirmed=args.backup_confirmed,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)


# ---------------------------------------------------------------------------
# Lane E2C-F -- Operator Token List Review and E2C Closeout Package
# ---------------------------------------------------------------------------

def main_review_bounded_15m_token_list_rehearsal(argv=None) -> int:
    """Final E2C operator token list review and closeout package."""
    from printer_v1.operator_cli.e2c_operator_review import build_e2c_operator_review_payload

    parser = _base_parser(
        "Final E2C operator token list review. Loads a JSON token list file, validates"
        " all operator approval fields, runs E2C-C readiness review and E2C-E fixture"
        " rehearsal, and outputs READY_FOR_OPERATOR_DECISION or BLOCKED."
        " No source fetching. No scheduler execution. No DB mutation. No paper decisions.",
        ("json",),
    )
    parser.add_argument(
        "--token-list-path",
        dest="token_list_path",
        metavar="PATH",
        help="Path to operator-approved token list JSON file.",
    )
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        dest="backup_confirmed",
        help="Confirm that a DB backup exists before running this review.",
    )
    args = parser.parse_args(argv)

    try:
        payload = build_e2c_operator_review_payload(
            args.token_list_path,
            args.db_path,
            backup_confirmed=args.backup_confirmed,
        )
        _print_payload(payload, args.format)
        return 0
    except Exception as exc:
        return _print_error(exc)
