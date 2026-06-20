"""Build deterministic current setup fingerprints from local labels."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus


FINGERPRINT_FIELDS = (
    "window_kind", "market_regime_label", "chain_heat_label", "safety_status_label",
    "rug_risk_label", "liquidity_state_label", "exit_realism_label",
    "realism_gate_label", "flow_direction_label", "flow_pressure_label",
    "trend_structure_label", "volatility_label", "candle_path_label",
    "micro_event_state_label", "held_to_15m_result_label", "token_age_bucket",
    "pair_age_bucket", "discovery_label", "tracking_lane", "source_status",
    "data_quality_label",
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


def normalize_fingerprint_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    fingerprint = {field: payload.get(field) for field in FINGERPRINT_FIELDS}
    fingerprint["source_status"] = SourceStatus(fingerprint.get("source_status") or SourceStatus.COMPLETE).value
    fingerprint["data_quality_label"] = DataQualityLabel(fingerprint.get("data_quality_label") or DataQualityLabel.CLEAN_DATA).value
    return fingerprint


def build_current_setup_fingerprint(payload: Mapping[str, Any]) -> dict[str, Any]:
    context = dict(payload.get("context") or {})
    merged = dict(payload)
    merged.update(context)
    return normalize_fingerprint_payload(merged)


def latest_row(connection: sqlite3.Connection, table: str, token_id: int, pair_id: int | None, time_field: str = "captured_at") -> dict[str, Any]:
    row = connection.execute(
        f"""
        SELECT * FROM {table}
        WHERE token_id = ?
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
        ORDER BY {time_field} DESC, id DESC
        LIMIT 1
        """,
        (token_id, pair_id),
    ).fetchone()
    return dict(row) if row else {}


def build_current_setup_fingerprint_from_db(
    db_path_or_conn: str | Path | sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    target_time=None,
) -> dict[str, Any]:
    del target_time
    payload: dict[str, Any] = {"source_status": SourceStatus.COMPLETE.value, "data_quality_label": DataQualityLabel.CLEAN_DATA.value}
    with connect(db_path_or_conn) as connection:
        market = connection.execute("SELECT * FROM printer_market_regime_snapshots ORDER BY captured_at DESC, id DESC LIMIT 1").fetchone()
        chain = connection.execute("SELECT * FROM printer_solana_chain_heat_snapshots ORDER BY captured_at DESC, id DESC LIMIT 1").fetchone()
        payload.update(dict(market) if market else {})
        payload.update(dict(chain) if chain else {})
        payload.update(latest_row(connection, "printer_safety_rug_snapshots", token_id, pair_id))
        payload.update(latest_row(connection, "printer_liquidity_exit_snapshots", token_id, pair_id))
        payload.update(latest_row(connection, "printer_trading_flow_snapshots", token_id, pair_id))
        payload.update(latest_row(connection, "printer_chart_volatility_snapshots", token_id, pair_id))
        micro = latest_row(connection, "printer_micro_events", token_id, pair_id, "detected_at")
        payload.update(micro)
    return normalize_fingerprint_payload(payload)


def fingerprint_has_required_context(fingerprint: Mapping[str, Any]) -> bool:
    return any(fingerprint.get(field) for field in ("safety_status_label", "liquidity_state_label", "flow_direction_label", "trend_structure_label"))


def fingerprint_is_clean_enough_for_retrieval(fingerprint: Mapping[str, Any]) -> bool:
    return (
        SourceStatus(fingerprint.get("source_status") or SourceStatus.COMPLETE) == SourceStatus.COMPLETE
        and DataQualityLabel(fingerprint.get("data_quality_label") or DataQualityLabel.CLEAN_DATA) == DataQualityLabel.CLEAN_DATA
    )
