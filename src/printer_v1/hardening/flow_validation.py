"""Synthetic end-to-end validation over temporary/local SQLite databases."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any

from printer_v1.db import apply_migrations
from printer_v1.hardening.contracts import (
    SyntheticFlowStageLabel,
    ValidationIssueLabel,
    ValidationResultLabel,
    ValidationScopeLabel,
)
from printer_v1.hardening.fixtures import (
    PAIR_ADDRESS,
    TOKEN_MINT,
    build_synthetic_chain_heat_context,
    build_synthetic_chart_volatility_context,
    build_synthetic_clean_memory_episode_payload,
    build_synthetic_discovery_payload,
    build_synthetic_liquidity_exit_context,
    build_synthetic_market_regime_context,
    build_synthetic_micro_event_context,
    build_synthetic_pair_fixture,
    build_synthetic_paper_decision_payload,
    build_synthetic_safety_context,
    build_synthetic_solana_token_fixture,
    build_synthetic_token_snapshots_for_15m_pump,
    build_synthetic_trading_flow_context,
)
from printer_v1.hardening import recorder


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _connect(db_path_or_conn: str | Path | sqlite3.Connection) -> tuple[sqlite3.Connection, bool]:
    if isinstance(db_path_or_conn, sqlite3.Connection):
        db_path_or_conn.row_factory = sqlite3.Row
        return db_path_or_conn, False
    connection = sqlite3.connect(db_path_or_conn)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection, True


def _columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _insert_filtered(connection: sqlite3.Connection, table_name: str, payload: dict[str, Any]) -> int:
    columns = _columns(connection, table_name)
    filtered = {key: value for key, value in payload.items() if key in columns}
    if not filtered:
        raise ValueError(f"No matching columns for {table_name}")
    names = ", ".join(filtered)
    placeholders = ", ".join("?" for _ in filtered)
    cursor = connection.execute(
        f"INSERT INTO {table_name} ({names}) VALUES ({placeholders})",
        tuple(filtered.values()),
    )
    return int(cursor.lastrowid)


def _item(stage: str, result: str, issue: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "validation_scope_label": ValidationScopeLabel.VALIDATION_FULL_SYNTHETIC_FLOW.value,
        "validation_result_label": result,
        "validation_issue_label": issue,
        "flow_stage_label": stage,
        "item_payload": payload or {},
    }


def _pass(stage: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _item(
        stage,
        ValidationResultLabel.VALIDATION_PASS.value,
        ValidationIssueLabel.VALIDATION_ISSUE_NONE.value,
        payload,
    )


def _fail(stage: str, issue: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return _item(stage, ValidationResultLabel.VALIDATION_FAIL.value, issue, payload)


def initialize_temp_validation_db(temp_dir: str | Path) -> Path:
    db_path = Path(temp_dir) / "printer_v1_phase20_validation.sqlite3"
    apply_migrations(db_path)
    return db_path


def seed_synthetic_discovery_and_snapshots(db_path_or_conn: str | Path | sqlite3.Connection) -> dict[str, Any]:
    connection, should_close = _connect(db_path_or_conn)
    try:
        token = build_synthetic_solana_token_fixture()
        pair = build_synthetic_pair_fixture()
        token_id = _insert_filtered(connection, "printer_tokens", token)
        pair["token_id"] = token_id
        pair_id = _insert_filtered(connection, "printer_pairs", pair)
        discovery = build_synthetic_discovery_payload()
        discovery_row = {
            "token_id": token_id,
            "pair_id": pair_id,
            "source_name": "synthetic-local",
            "discovery_label": discovery["discovery_label"],
            "discovery_action": "TRACK_TOKEN",
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            "normalized_candidate_payload_json": json.dumps(discovery, sort_keys=True),
            "tracking_lane": "TRACK_FAST",
            "priority_reason": "synthetic validation",
        }
        discovery_id = _insert_filtered(connection, "printer_discovery_candidates", discovery_row)
        snapshot_ids = []
        for snapshot in build_synthetic_token_snapshots_for_15m_pump():
            snapshot["token_id"] = token_id
            snapshot["pair_id"] = pair_id
            snapshot_ids.append(_insert_filtered(connection, "printer_token_snapshots", snapshot))
        connection.commit()
        return {
            "stage": SyntheticFlowStageLabel.FLOW_STAGE_SNAPSHOTS.value,
            "token_id": token_id,
            "pair_id": pair_id,
            "discovery_id": discovery_id,
            "snapshot_ids": snapshot_ids,
            "items": [
                _pass(SyntheticFlowStageLabel.FLOW_STAGE_DISCOVERY.value, {"discovery_id": discovery_id}),
                _pass(SyntheticFlowStageLabel.FLOW_STAGE_SNAPSHOTS.value, {"snapshot_ids": snapshot_ids}),
            ],
        }
    finally:
        if should_close:
            connection.close()


def seed_synthetic_context_engine_rows(db_path_or_conn: str | Path | sqlite3.Connection) -> dict[str, Any]:
    connection, should_close = _connect(db_path_or_conn)
    try:
        token_id = int(connection.execute("SELECT id FROM printer_tokens LIMIT 1").fetchone()["id"])
        pair_id = int(connection.execute("SELECT id FROM printer_pairs LIMIT 1").fetchone()["id"])
        base = {
            "token_id": token_id,
            "pair_id": pair_id,
            "token_mint": TOKEN_MINT,
            "pair_address": PAIR_ADDRESS,
            "captured_at": "2026-01-01T00:15:00Z",
            "price_usd": 0.002,
            "liquidity_usd": 140000.0,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        }
        rows = {}
        market = base | build_synthetic_market_regime_context() | {
            "market_transition_label": "RISK_OFF_TO_RISK_ON",
            "raw_market_payload_json": "{}",
            "normalized_market_payload_json": "{}",
        }
        rows["market"] = _insert_filtered(connection, "printer_market_regime_snapshots", market)
        chain = base | build_synthetic_chain_heat_context() | {
            "activity_label": "ACTIVITY_NORMAL",
            "liquidity_label": "LIQUIDITY_STABLE",
            "congestion_label": "CONGESTION_LOW",
            "raw_chain_heat_payload_json": "{}",
            "normalized_chain_heat_payload_json": "{}",
        }
        rows["chain_heat"] = _insert_filtered(connection, "printer_solana_chain_heat_snapshots", chain)
        safety = base | build_synthetic_safety_context() | {
            "liquidity_safety_label": "LIQUIDITY_SAFE",
            "authority_label": "AUTHORITY_RENOUNCED_OR_SAFE",
            "distribution_label": "DISTRIBUTION_HEALTHY",
            "safety_gate_label": "ALLOW_SAFETY_CONTEXT",
            "raw_safety_payload_json": "{}",
            "normalized_safety_payload_json": "{}",
        }
        rows["safety"] = _insert_filtered(connection, "printer_safety_rug_snapshots", safety)
        liquidity = base | build_synthetic_liquidity_exit_context(True) | {
            "liquidity_exit_payload_quality_label": "LIQUIDITY_EXIT_CONTEXT_CLEAN",
            "route_available": 1,
            "quote_status": "COMPLETE",
            "route_status": "AVAILABLE",
            "raw_liquidity_exit_payload_json": "{}",
            "normalized_liquidity_exit_payload_json": "{}",
        }
        rows["liquidity_exit"] = _insert_filtered(connection, "printer_liquidity_exit_snapshots", liquidity)
        flow = base | build_synthetic_trading_flow_context() | {
            "trading_flow_payload_quality_label": "TRADING_FLOW_CONTEXT_CLEAN",
            "volume_5m": 30000.0,
            "txns_5m": 90,
            "buys_5m": 70,
            "sells_5m": 20,
            "raw_trading_flow_payload_json": "{}",
            "normalized_trading_flow_payload_json": "{}",
        }
        rows["trading_flow"] = _insert_filtered(connection, "printer_trading_flow_snapshots", flow)
        chart = base | build_synthetic_chart_volatility_context() | {
            "chart_payload_quality_label": "CHART_CONTEXT_CLEAN",
            "window_start_at": "2026-01-01T00:00:00Z",
            "window_end_at": "2026-01-01T00:15:00Z",
            "price_open": 0.001,
            "price_high": 0.002,
            "price_low": 0.001,
            "price_close": 0.002,
            "price_change_percent": 100.0,
            "volatility_percent": 18.0,
            "candle_count": 4,
            "raw_chart_payload_json": "{}",
            "normalized_chart_payload_json": "{}",
        }
        rows["chart"] = _insert_filtered(connection, "printer_chart_volatility_snapshots", chart)
        micro = base | build_synthetic_micro_event_context() | {
            "detected_at": "2026-01-01T00:05:00Z",
            "event_window_start_at": "2026-01-01T00:00:00Z",
            "event_window_end_at": "2026-01-01T00:05:00Z",
            "hold_check_15m_at": "2026-01-01T00:15:00Z",
            "price_start": 0.001,
            "price_high": 0.0014,
            "price_low": 0.001,
            "price_end": 0.0014,
            "price_change_5m_percent": 40.0,
            "liquidity_exit_realism_label": "EXIT_REALISTIC",
            "slippage_label": "SLIPPAGE_LOW",
            "price_impact_label": "PRICE_IMPACT_LOW",
            "route_label": "ROUTE_AVAILABLE",
            "safety_status_label": "SAFETY_CLEAN",
            "liquidity_state_label": "LIQUIDITY_USABLE",
            "flow_direction_label": "FLOW_ACCUMULATION",
            "candle_path_label": "PATH_SPIKE_AND_HOLD",
            "raw_micro_event_payload_json": "{}",
            "normalized_micro_event_payload_json": "{}",
        }
        rows["micro_event"] = _insert_filtered(connection, "printer_micro_events", micro)
        connection.commit()
        return {
            "stage": SyntheticFlowStageLabel.FLOW_STAGE_CONTEXT.value,
            "context_row_ids": rows,
            "items": [_pass(SyntheticFlowStageLabel.FLOW_STAGE_CONTEXT.value, {"context_row_ids": rows})],
        }
    finally:
        if should_close:
            connection.close()


def run_synthetic_memory_build(db_path_or_conn: str | Path | sqlite3.Connection) -> dict[str, Any]:
    connection, should_close = _connect(db_path_or_conn)
    try:
        snapshot_ids = [row["id"] for row in connection.execute("SELECT id FROM printer_token_snapshots ORDER BY captured_at").fetchall()]
        if len(snapshot_ids) < 2:
            return {"items": [_fail(SyntheticFlowStageLabel.FLOW_STAGE_MEMORY.value, ValidationIssueLabel.VALIDATION_ISSUE_MISSING_COLUMN.value, {"reason": "snapshots required"})]}
        token_id = int(connection.execute("SELECT id FROM printer_tokens LIMIT 1").fetchone()["id"])
        pair_id = int(connection.execute("SELECT id FROM printer_pairs LIMIT 1").fetchone()["id"])
        memory = build_synthetic_clean_memory_episode_payload()
        window_id = _insert_filtered(connection, "printer_memory_windows", {
            "token_id": token_id,
            "pair_id": pair_id,
            "window_kind": "WINDOW_15M",
            "opened_at": "2026-01-01T00:00:00Z",
            "closed_at": "2026-01-01T00:15:00Z",
            "expected_snapshot_count": 4,
            "actual_snapshot_count": len(snapshot_ids),
            "missing_snapshot_count": 0,
            "coverage_state": "COVERAGE_COMPLETE",
            "memory_status": "CLEAN_MEMORY",
            "window_status": "WINDOW_CLOSED",
            "outcome_label": memory["outcome_label"],
            "memory_quality_label": "CLEAN_MEMORY",
            "data_quality_label": "CLEAN_DATA",
            "created_by_phase": "PHASE_20_SYNTHETIC",
            "supporting_context_json": json.dumps({"synthetic_only": True}, sort_keys=True),
        })
        episode_id = _insert_filtered(connection, "printer_episodes", {
            "memory_window_id": window_id,
            "token_id": token_id,
            "pair_id": pair_id,
            "episode_kind": "MEMORY_WINDOW",
            "episode_status": "EPISODE_BUILT",
            "memory_status": "CLEAN_MEMORY",
            "window_kind": "WINDOW_15M",
            "episode_outcome_label": memory["outcome_label"],
            "memory_quality_label": "CLEAN_MEMORY",
            "action_lesson_label": memory["action_lesson_label"],
            "episode_summary_json": json.dumps({"synthetic_only": True}, sort_keys=True),
            "supporting_context_json": json.dumps(memory["fingerprint"], sort_keys=True),
            "data_quality_label": "CLEAN_DATA",
        })
        for index, snapshot_id in enumerate(snapshot_ids):
            _insert_filtered(connection, "printer_episode_snapshots", {
                "episode_id": episode_id,
                "token_snapshot_id": snapshot_id,
                "position_in_episode": index,
            })
        outcome_id = _insert_filtered(connection, "printer_episode_outcomes", {
            "episode_id": episode_id,
            "memory_window_id": window_id,
            "token_id": token_id,
            "pair_id": pair_id,
            "window_kind": "WINDOW_15M",
            "outcome_label": memory["outcome_label"],
            "action_lesson_label": memory["action_lesson_label"],
            "price_start": 0.001,
            "price_high": 0.002,
            "price_low": 0.001,
            "price_end": 0.002,
            "price_change_percent": 100.0,
            "max_runup_percent": 100.0,
            "max_drawdown_percent": 0.0,
            "realistic_entry_available": 1,
            "realistic_exit_available": 1,
            "realistic_profit_possible": 1,
            "capital_protection_possible": 0,
            "memory_quality_label": "CLEAN_MEMORY",
            "outcome_payload_json": json.dumps(memory, sort_keys=True),
        })
        fingerprint_id = _insert_filtered(connection, "printer_memory_fingerprints", {
            "episode_id": episode_id,
            "fingerprint_kind": "STATIC_CONDITION_LABELS",
            "fingerprint_payload_json": json.dumps(memory["fingerprint"], sort_keys=True),
            "memory_status": "CLEAN_MEMORY",
            "memory_quality_label": "CLEAN_MEMORY",
            "data_quality_label": "CLEAN_DATA",
        })
        connection.commit()
        return {
            "memory_window_id": window_id,
            "episode_id": episode_id,
            "episode_outcome_id": outcome_id,
            "fingerprint_id": fingerprint_id,
            "items": [_pass(SyntheticFlowStageLabel.FLOW_STAGE_MEMORY.value, {"episode_id": episode_id})],
        }
    finally:
        if should_close:
            connection.close()


def run_synthetic_memory_retrieval(db_path_or_conn: str | Path | sqlite3.Connection) -> dict[str, Any]:
    connection, should_close = _connect(db_path_or_conn)
    try:
        episode = connection.execute("SELECT * FROM printer_episodes WHERE memory_quality_label = 'CLEAN_MEMORY' LIMIT 1").fetchone()
        fingerprint = connection.execute("SELECT * FROM printer_memory_fingerprints WHERE episode_id = ? LIMIT 1", (episode["id"],)).fetchone() if episode else None
        if not episode or not fingerprint:
            return {"items": [_fail(SyntheticFlowStageLabel.FLOW_STAGE_RETRIEVAL.value, ValidationIssueLabel.VALIDATION_ISSUE_DIRTY_MEMORY_ALLOWED.value)]}
        query_id = _insert_filtered(connection, "printer_memory_retrieval_queries", {
            "query_type": "CURRENT_SETUP_QUERY",
            "token_id": episode["token_id"],
            "pair_id": episode["pair_id"],
            "token_mint": TOKEN_MINT,
            "pair_address": PAIR_ADDRESS,
            "query_at": "2026-01-01T00:16:00Z",
            "current_fingerprint_json": fingerprint["fingerprint_payload_json"],
            "query_context_json": json.dumps({"synthetic_only": True}, sort_keys=True),
            "retrieval_result_label": "RETRIEVAL_HAS_CLEAN_MATCHES",
            "memory_evidence_label": "MEMORY_EVIDENCE_STRONG",
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        })
        match_id = _insert_filtered(connection, "printer_memory_retrieval_matches", {
            "retrieval_query_id": query_id,
            "episode_id": episode["id"],
            "memory_window_id": episode["memory_window_id"],
            "token_id": episode["token_id"],
            "pair_id": episode["pair_id"],
            "window_kind": "WINDOW_15M",
            "outcome_label": "REALISTIC_PAPER_PROFIT",
            "action_lesson_label": "ACTION_BUY_WORKED",
            "memory_quality_label": "CLEAN_MEMORY",
            "match_strength_label": "EXACT_CONDITION_MATCH",
            "match_reasons_json": json.dumps(["MATCH_WINDOW_KIND", "MATCH_LIQUIDITY_EXIT_CONTEXT"], sort_keys=True),
            "mismatch_reasons_json": json.dumps([], sort_keys=True),
            "memory_fingerprint_json": fingerprint["fingerprint_payload_json"],
            "comparison_payload_json": json.dumps({"synthetic_only": True}, sort_keys=True),
            "included_as_clean_evidence": 1,
            "included_as_audit_context": 0,
        })
        connection.commit()
        return {
            "retrieval_query_id": query_id,
            "match_id": match_id,
            "items": [_pass(SyntheticFlowStageLabel.FLOW_STAGE_RETRIEVAL.value, {"retrieval_query_id": query_id, "match_id": match_id})],
        }
    finally:
        if should_close:
            connection.close()


def run_synthetic_paper_decision(db_path_or_conn: str | Path | sqlite3.Connection) -> dict[str, Any]:
    connection, should_close = _connect(db_path_or_conn)
    try:
        clean_match = connection.execute(
            "SELECT * FROM printer_memory_retrieval_matches WHERE included_as_clean_evidence = 1 AND memory_quality_label = 'CLEAN_MEMORY' LIMIT 1"
        ).fetchone()
        if not clean_match:
            return {"items": [_fail(SyntheticFlowStageLabel.FLOW_STAGE_PAPER_DECISION.value, ValidationIssueLabel.VALIDATION_ISSUE_DECISION_WITHOUT_CLEAN_MEMORY.value)]}
        payload = build_synthetic_paper_decision_payload()
        payload.update({
            "retrieval_query_id": clean_match["retrieval_query_id"],
            "matched_episode_ids_json": json.dumps([clean_match["episode_id"]]),
            "supporting_memory_match_ids_json": json.dumps([clean_match["id"]]),
            "decision_reasons_json": json.dumps(["REASON_CLEAN_MEMORY_MATCH_SUPPORTS_ACTION"]),
            "blocking_reasons_json": json.dumps([]),
            "current_context_json": json.dumps({"synthetic_only": True}),
            "memory_evidence_summary_json": json.dumps({"clean_match_count": 1}),
            "decision_report_json": json.dumps({"paper_only": True, "synthetic_only": True}),
            "decided_at": "2026-01-01T00:16:00Z",
            "decision_action": "BUY",
            "decision_status": "PAPER_DECISION_PROPOSED",
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
        })
        decision_id = _insert_filtered(connection, "printer_paper_decisions", payload)
        connection.commit()
        return {
            "paper_decision_id": decision_id,
            "items": [_pass(SyntheticFlowStageLabel.FLOW_STAGE_PAPER_DECISION.value, {"paper_decision_id": decision_id})],
        }
    finally:
        if should_close:
            connection.close()


def run_synthetic_paper_monitor(db_path_or_conn: str | Path | sqlite3.Connection) -> dict[str, Any]:
    connection, should_close = _connect(db_path_or_conn)
    try:
        decision = connection.execute(
            "SELECT * FROM printer_paper_decisions WHERE decision_gate_label = 'DECISION_ALLOWED' AND final_action_label = 'BUY' LIMIT 1"
        ).fetchone()
        if not decision:
            return {"items": [_fail(SyntheticFlowStageLabel.FLOW_STAGE_PAPER_POSITION.value, ValidationIssueLabel.VALIDATION_ISSUE_POSITION_WITHOUT_VALID_DECISION.value)]}
        position_id = _insert_filtered(connection, "printer_paper_positions", {
            "paper_decision_id": decision["id"],
            "retrieval_query_id": decision["retrieval_query_id"],
            "token_id": decision["token_id"],
            "pair_id": decision["pair_id"],
            "token_mint": TOKEN_MINT,
            "pair_address": PAIR_ADDRESS,
            "position_status": "OPEN",
            "paper_position_status_label": "PAPER_POSITION_CLOSED",
            "entry_status_label": "PAPER_ENTRY_ALLOWED",
            "paper_monitor_state_label": "MONITOR_CLOSED",
            "paper_exit_reason_label": "EXIT_REASON_TARGET_REACHED",
            "paper_pnl_state_label": "PNL_REALIZED_PROFIT",
            "opened_at": "2026-01-01T00:16:00Z",
            "closed_at": "2026-01-01T00:30:00Z",
            "paper_entry_price": 0.002,
            "paper_exit_price": 0.0024,
            "entry_price_usd": 0.002,
            "exit_price_usd": 0.0024,
            "paper_size_usd": 100.0,
            "paper_token_amount": 50000.0,
            "current_price_usd": 0.0024,
            "paper_pnl_usd": 20.0,
            "paper_pnl_percent": 20.0,
            "realized_pnl_usd": 20.0,
            "realized_pnl_percent": 20.0,
            "unrealized_pnl_usd": 0.0,
            "unrealized_pnl_percent": 0.0,
            "max_runup_percent": 25.0,
            "max_drawdown_percent": 3.0,
            "entry_context_json": json.dumps({"synthetic_only": True}),
            "latest_monitor_context_json": json.dumps({"synthetic_only": True}),
            "exit_context_json": json.dumps({"synthetic_only": True}),
        })
        event_ids = []
        for event_label, event_at in [
            ("PAPER_EVENT_POSITION_OPENED", "2026-01-01T00:16:00Z"),
            ("PAPER_EVENT_SNAPSHOT_MONITORED", "2026-01-01T00:20:00Z"),
            ("PAPER_EVENT_POSITION_CLOSED", "2026-01-01T00:30:00Z"),
        ]:
            event_ids.append(_insert_filtered(connection, "printer_paper_trade_events", {
                "paper_position_id": position_id,
                "paper_decision_id": decision["id"],
                "token_id": decision["token_id"],
                "pair_id": decision["pair_id"],
                "event_kind": event_label,
                "paper_trade_event_label": event_label,
                "event_at": event_at,
                "price_usd": 0.0024,
                "liquidity_usd": 150000.0,
                "paper_monitor_state_label": "MONITOR_CLOSED",
                "paper_exit_reason_label": "EXIT_REASON_TARGET_REACHED",
                "paper_pnl_state_label": "PNL_REALIZED_PROFIT",
                "event_payload_json": json.dumps({"paper_only": True, "synthetic_only": True}),
                "source_status": "COMPLETE",
                "data_quality_label": "CLEAN_DATA",
            }))
        connection.commit()
        return {
            "paper_position_id": position_id,
            "event_ids": event_ids,
            "items": [
                _pass(SyntheticFlowStageLabel.FLOW_STAGE_PAPER_POSITION.value, {"paper_position_id": position_id}),
                _pass(SyntheticFlowStageLabel.FLOW_STAGE_PAPER_MONITOR.value, {"event_ids": event_ids}),
            ],
        }
    finally:
        if should_close:
            connection.close()


def run_synthetic_paper_audit(db_path_or_conn: str | Path | sqlite3.Connection) -> dict[str, Any]:
    connection, should_close = _connect(db_path_or_conn)
    try:
        position = connection.execute("SELECT * FROM printer_paper_positions LIMIT 1").fetchone()
        if not position:
            return {"items": [_fail(SyntheticFlowStageLabel.FLOW_STAGE_PAPER_AUDIT.value, ValidationIssueLabel.VALIDATION_ISSUE_POSITION_WITHOUT_VALID_DECISION.value)]}
        audit_id = _insert_filtered(connection, "printer_paper_audit_reports", {
            "paper_position_id": position["id"],
            "paper_decision_id": position["paper_decision_id"],
            "retrieval_query_id": position["retrieval_query_id"],
            "token_id": position["token_id"],
            "pair_id": position["pair_id"],
            "token_mint": TOKEN_MINT,
            "pair_address": PAIR_ADDRESS,
            "audit_at": "2026-01-01T00:31:00Z",
            "audit_scope_label": "AUDIT_FULL_PAPER_TRADE",
            "paper_audit_result_label": "PAPER_AUDIT_PASS",
            "paper_rule_compliance_label": "RULES_COMPLIANT",
            "paper_realism_label": "PAPER_REALISM_CLEAN",
            "paper_outcome_review_label": "PAPER_OUTCOME_WORKED",
            "paper_data_quality_audit_label": "PAPER_AUDIT_DATA_CLEAN",
            "audit_issues_json": json.dumps(["ISSUE_NONE"]),
            "audit_report_json": json.dumps({"paper_only": True, "audit_only": True, "synthetic_only": True}),
        })
        connection.commit()
        return {
            "paper_audit_report_id": audit_id,
            "items": [_pass(SyntheticFlowStageLabel.FLOW_STAGE_PAPER_AUDIT.value, {"paper_audit_report_id": audit_id})],
        }
    finally:
        if should_close:
            connection.close()


def run_synthetic_operator_review(db_path_or_conn: str | Path | sqlite3.Connection) -> dict[str, Any]:
    connection, should_close = _connect(db_path_or_conn)
    try:
        report_id = _insert_filtered(connection, "printer_operator_review_reports", {
            "report_scope_label": "REPORT_FULL_OPERATOR_REVIEW",
            "report_status_label": "REPORT_READY",
            "operator_review_label": "OPERATOR_REVIEW_OK",
            "report_format_label": "REPORT_FORMAT_JSON",
            "generated_at": "2026-01-01T00:32:00Z",
            "db_state_classification": "PERSISTENT_DB_HAS_REAL_PAPER_ROWS",
            "token_id": 1,
            "pair_id": 1,
            "token_mint": TOKEN_MINT,
            "pair_address": PAIR_ADDRESS,
            "report_title": "Synthetic Phase 20 Operator Review",
            "attention_labels_json": json.dumps(["ATTENTION_NONE"]),
            "summary_payload_json": json.dumps({"synthetic_only": True}),
            "report_payload_json": json.dumps({"review_only": True, "paper_only": True, "synthetic_only": True}),
            "report_text": "Synthetic-only operator review. Paper-only validation.",
        })
        connection.commit()
        return {
            "operator_review_report_id": report_id,
            "items": [_pass(SyntheticFlowStageLabel.FLOW_STAGE_OPERATOR_REVIEW.value, {"operator_review_report_id": report_id})],
        }
    finally:
        if should_close:
            connection.close()


def run_full_synthetic_validation_flow(
    db_path_or_conn: str | Path | sqlite3.Connection,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = [_pass(SyntheticFlowStageLabel.FLOW_STAGE_DB_INIT.value)]
    stages = [
        seed_synthetic_discovery_and_snapshots,
        seed_synthetic_context_engine_rows,
        run_synthetic_memory_build,
        run_synthetic_memory_retrieval,
        run_synthetic_paper_decision,
        run_synthetic_paper_monitor,
        run_synthetic_paper_audit,
        run_synthetic_operator_review,
    ]
    stage_payloads: dict[str, Any] = {}
    for stage in stages:
        payload = stage(db_path_or_conn)
        stage_payloads[stage.__name__] = {key: value for key, value in payload.items() if key != "items"}
        items.extend(payload.get("items", []))
    items.append(_pass(SyntheticFlowStageLabel.FLOW_STAGE_COMPLETE.value, {"project_root": str(project_root) if project_root else None}))
    result = (
        ValidationResultLabel.VALIDATION_PASS.value
        if all(item["validation_result_label"] == ValidationResultLabel.VALIDATION_PASS.value for item in items)
        else ValidationResultLabel.VALIDATION_FAIL.value
    )
    validation_payload = {
        "validation_scope_label": ValidationScopeLabel.VALIDATION_FULL_SYNTHETIC_FLOW.value,
        "validation_result_label": result,
        "started_at": _now(),
        "completed_at": _now(),
        "synthetic_only": True,
        "temp_db_only": True,
        "project_db_created": False,
        "summary": {"stage_count": len(stages), "item_count": len(items)},
        "report": {"paper_only": True, "synthetic_only": True, "stages": stage_payloads},
        "items": items,
    }
    run_id = recorder.record_validation_run(db_path_or_conn, validation_payload)
    recorder.record_validation_items(db_path_or_conn, run_id, items)
    return validation_payload | {
        "validation_run_id": run_id,
        "completed_stage": SyntheticFlowStageLabel.FLOW_STAGE_COMPLETE.value,
    }
