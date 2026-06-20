"""Static condition fingerprint payloads for later Printer V1 use."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel
from printer_v1.memory.contracts import MemoryQualityLabel


def storage_memory_status(memory_quality_label: str | MemoryQualityLabel) -> str:
    quality = MemoryQualityLabel(memory_quality_label)
    return {
        MemoryQualityLabel.CLEAN_MEMORY: "CLEAN_MEMORY",
        MemoryQualityLabel.PARTIAL_MEMORY: "PARTIAL_MEMORY",
        MemoryQualityLabel.DIRTY_MEMORY: "DIRTY_MEMORY",
        MemoryQualityLabel.AUDIT_ONLY_MEMORY: "AUDIT_ONLY",
        MemoryQualityLabel.DO_NOT_TRAIN_MEMORY: "DO_NOT_TRAIN",
    }[quality]


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


def build_memory_fingerprint_payload(episode_payload: Mapping[str, Any]) -> dict[str, Any]:
    context = episode_payload.get("supporting_context") or {}
    liquidity = context.get("liquidity_exit") or {}
    flow = context.get("trading_flow") or {}
    chart = context.get("chart_volatility") or {}
    safety = context.get("safety") or {}
    market = context.get("market") or {}
    chain = context.get("chain_heat") or {}
    micro_events = context.get("micro_events") or []
    first_micro = micro_events[0] if micro_events else {}
    return {
        "window_kind": episode_payload.get("window", {}).get("window_kind"),
        "outcome_label": episode_payload.get("outcome_label"),
        "memory_quality_label": episode_payload.get("memory_quality_label"),
        "market_regime_label": market.get("market_regime_label"),
        "chain_heat_label": chain.get("chain_heat_label"),
        "safety_status_label": safety.get("safety_status_label"),
        "rug_risk_label": safety.get("rug_risk_label"),
        "liquidity_state_label": liquidity.get("liquidity_state_label"),
        "exit_realism_label": liquidity.get("exit_realism_label"),
        "realism_gate_label": liquidity.get("realism_gate_label"),
        "flow_direction_label": flow.get("flow_direction_label"),
        "flow_pressure_label": flow.get("flow_pressure_label"),
        "trend_structure_label": chart.get("trend_structure_label"),
        "volatility_label": chart.get("volatility_label"),
        "candle_path_label": chart.get("candle_path_label"),
        "micro_event_state_label": first_micro.get("micro_event_state_label"),
        "held_to_15m_result_label": first_micro.get("held_to_15m_result_label"),
        "token_age_bucket": episode_payload.get("token_age_bucket"),
        "pair_age_bucket": episode_payload.get("pair_age_bucket"),
        "discovery_label": episode_payload.get("discovery_label"),
        "tracking_lane": (episode_payload.get("window") or {}).get("supporting_context_json"),
    }


def fingerprint_can_be_indexed_later(memory_quality_label: str | MemoryQualityLabel) -> bool:
    return MemoryQualityLabel(memory_quality_label) == MemoryQualityLabel.CLEAN_MEMORY


def record_memory_fingerprint(
    db_path_or_conn: str | Path | sqlite3.Connection,
    episode_id: int,
    fingerprint_payload: Mapping[str, Any],
    memory_quality_label: str | MemoryQualityLabel,
) -> int:
    status = storage_memory_status(memory_quality_label)
    do_not_train = 0 if fingerprint_can_be_indexed_later(memory_quality_label) else 1
    with connect(db_path_or_conn) as connection:
        cursor = connection.execute(
            """
            INSERT INTO printer_memory_fingerprints (
                episode_id, fingerprint_kind, fingerprint_payload_json,
                memory_status, data_quality_label, do_not_train
            )
            VALUES (?, 'STATIC_CONDITION_SUMMARY', ?, ?, ?, ?)
            """,
            (
                episode_id,
                json.dumps(dict(fingerprint_payload), sort_keys=True),
                status,
                DataQualityLabel.CLEAN_DATA.value,
                do_not_train,
            ),
        )
        return int(cursor.lastrowid)
