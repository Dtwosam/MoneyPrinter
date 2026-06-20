"""Assemble episodes from local Printer DB evidence only."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any

from printer_v1.memory.outcomes import calculate_window_price_path, classify_action_lesson, classify_episode_outcome
from printer_v1.memory.quality import (
    build_rejection_reasons,
    classify_memory_quality,
    evaluate_context_quality_gate,
    evaluate_realism_gate,
    evaluate_snapshot_coverage_gate,
    evaluate_source_quality_gate,
)


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


def attach_token_snapshots(connection: sqlite3.Connection, window: sqlite3.Row) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT * FROM printer_token_snapshots
        WHERE token_id = ?
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
          AND captured_at >= ?
          AND captured_at <= COALESCE(?, captured_at)
        ORDER BY captured_at ASC, id ASC
        """,
        (window["token_id"], window["pair_id"], window["opened_at"], window["closed_at"]),
    ).fetchall()


def latest_context(connection: sqlite3.Connection, table: str, token_id: int, pair_id: int | None) -> dict[str, Any]:
    rows = connection.execute(
        f"""
        SELECT * FROM {table}
        WHERE token_id = ?
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
        ORDER BY captured_at DESC, id DESC
        LIMIT 1
        """,
        (token_id, pair_id),
    ).fetchall()
    return dict(rows[0]) if rows else {}


def attach_market_regime_context(connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM printer_market_regime_snapshots ORDER BY captured_at DESC, id DESC LIMIT 1").fetchone()
    return dict(row) if row else {}


def attach_chain_heat_context(connection: sqlite3.Connection) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM printer_solana_chain_heat_snapshots ORDER BY captured_at DESC, id DESC LIMIT 1").fetchone()
    return dict(row) if row else {}


def attach_safety_context(connection: sqlite3.Connection, token_id: int, pair_id: int | None) -> dict[str, Any]:
    return latest_context(connection, "printer_safety_rug_snapshots", token_id, pair_id)


def attach_liquidity_exit_context(connection: sqlite3.Connection, token_id: int, pair_id: int | None) -> dict[str, Any]:
    return latest_context(connection, "printer_liquidity_exit_snapshots", token_id, pair_id)


def attach_trading_flow_context(connection: sqlite3.Connection, token_id: int, pair_id: int | None) -> dict[str, Any]:
    return latest_context(connection, "printer_trading_flow_snapshots", token_id, pair_id)


def attach_chart_volatility_context(connection: sqlite3.Connection, token_id: int, pair_id: int | None) -> dict[str, Any]:
    return latest_context(connection, "printer_chart_volatility_snapshots", token_id, pair_id)


def attach_micro_event_support_context(connection: sqlite3.Connection, token_id: int, pair_id: int | None, opened_at: str, closed_at: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT * FROM printer_micro_events
        WHERE token_id = ?
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
          AND detected_at >= ?
          AND detected_at <= ?
        ORDER BY detected_at ASC, id ASC
        """,
        (token_id, pair_id, opened_at, closed_at),
    ).fetchall()
    return [dict(row) for row in rows]


def collect_episode_evidence(db_path_or_conn: str | Path | sqlite3.Connection, memory_window_id: int) -> dict[str, Any]:
    with connect(db_path_or_conn) as connection:
        window = connection.execute("SELECT * FROM printer_memory_windows WHERE id = ?", (memory_window_id,)).fetchone()
        if window is None:
            raise ValueError(f"Memory window not found: {memory_window_id}")
        snapshots = attach_token_snapshots(connection, window)
        token_id = int(window["token_id"])
        pair_id = window["pair_id"]
        closed_at = window["closed_at"] or window["opened_at"]
        return {
            "window": dict(window),
            "snapshots": [dict(row) for row in snapshots],
            "market": attach_market_regime_context(connection),
            "chain_heat": attach_chain_heat_context(connection),
            "safety": attach_safety_context(connection, token_id, pair_id),
            "liquidity_exit": attach_liquidity_exit_context(connection, token_id, pair_id),
            "trading_flow": attach_trading_flow_context(connection, token_id, pair_id),
            "chart_volatility": attach_chart_volatility_context(connection, token_id, pair_id),
            "micro_events": attach_micro_event_support_context(connection, token_id, pair_id, window["opened_at"], closed_at),
        }


def build_episode_summary(evidence: dict[str, Any]) -> dict[str, Any]:
    snapshots = evidence["snapshots"]
    window = evidence["window"]
    liquidity = evidence["liquidity_exit"]
    micro_events = evidence["micro_events"]
    outcome = classify_episode_outcome(window["window_kind"], snapshots, liquidity, micro_events[0] if micro_events else None)
    path = calculate_window_price_path(snapshots)
    context = {}
    for section in ("market", "chain_heat", "safety", "liquidity_exit", "trading_flow", "chart_volatility"):
        context.update(evidence.get(section) or {})
    rejection_reasons = build_rejection_reasons(
        evaluate_snapshot_coverage_gate(snapshots),
        evaluate_source_quality_gate(snapshots),
        evaluate_context_quality_gate(context),
        evaluate_realism_gate(outcome, liquidity),
    )
    quality = classify_memory_quality(
        outcome_label=outcome,
        rejection_reasons=rejection_reasons,
        coverage_is_complete=len(snapshots) >= 2,
    )
    realistic_profit = outcome.value == "REALISTIC_PAPER_PROFIT"
    capital_protection = outcome.value in {"DUMP", "DEAD_TOKEN", "FAKE_PUMP", "PUMP_AND_DUMP"}
    return {
        "window": window,
        "price_path": path,
        "outcome_label": outcome.value,
        "action_lesson_label": classify_action_lesson(outcome, realistic_profit, capital_protection).value,
        "memory_quality_label": quality.value,
        "rejection_reasons": rejection_reasons,
        "supporting_context": {
            "market": evidence.get("market"),
            "chain_heat": evidence.get("chain_heat"),
            "safety": evidence.get("safety"),
            "liquidity_exit": liquidity,
            "trading_flow": evidence.get("trading_flow"),
            "chart_volatility": evidence.get("chart_volatility"),
            "micro_events": micro_events,
        },
        "snapshots": snapshots,
    }


def assemble_episode(db_path_or_conn: str | Path | sqlite3.Connection, memory_window_id: int, now=None) -> dict[str, Any]:
    del now
    evidence = collect_episode_evidence(db_path_or_conn, memory_window_id)
    return build_episode_summary(evidence)
