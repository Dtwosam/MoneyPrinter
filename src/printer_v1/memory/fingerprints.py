"""Static condition fingerprint payloads for later Printer V1 use."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import json
import sqlite3
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel
from printer_v1.memory.contracts import MemoryQualityLabel

_CATEGORICAL_UNKNOWN = "UNKNOWN"


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


def _categorical_label(value: Any) -> str:
    """Return a categorical string label or explicit UNKNOWN.

    Mapping/list/object values are never stored in categorical fields.
    """
    if value is None:
        return _CATEGORICAL_UNKNOWN
    if isinstance(value, (dict, list, tuple, set)):
        return _CATEGORICAL_UNKNOWN
    text = str(value).strip()
    if not text or text.upper() in {"NONE", "NULL", "N/A"}:
        return _CATEGORICAL_UNKNOWN
    return text


def _parse_window_supporting_context(window: Mapping[str, Any]) -> dict[str, Any]:
    raw = window.get("supporting_context_json")
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        if isinstance(parsed, Mapping):
            return dict(parsed)
    return {}


def _resolve_tracking_lane(
    episode_payload: Mapping[str, Any],
    window: Mapping[str, Any],
    context: Mapping[str, Any],
) -> str:
    """Resolve a categorical tracking lane — never the full supporting context."""
    for candidate in (
        episode_payload.get("tracking_lane"),
        window.get("tracking_lane"),
        context.get("tracking_lane"),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    window_ctx = _parse_window_supporting_context(window)
    lane = window_ctx.get("tracking_lane")
    if isinstance(lane, str) and lane.strip():
        return lane.strip()
    return _CATEGORICAL_UNKNOWN


def build_memory_fingerprint_payload(
    episode_payload: Mapping[str, Any],
    *,
    episode_id: int | None = None,
) -> dict[str, Any]:
    """Build the canonical static-condition fingerprint payload.

    Identity and categorical fields are exact-linked. Unavailable facts are
    explicit categorical ``UNKNOWN``. No scoring, ranking, confidence,
    embedding, or vector fields are introduced.
    """
    context = episode_payload.get("supporting_context") or {}
    if not isinstance(context, Mapping):
        context = {}
    window = episode_payload.get("window") or {}
    if not isinstance(window, Mapping):
        window = {}
    liquidity = context.get("liquidity_exit") or {}
    if not isinstance(liquidity, Mapping):
        liquidity = {}
    flow = context.get("trading_flow") or {}
    if not isinstance(flow, Mapping):
        flow = {}
    chart = context.get("chart_volatility") or {}
    if not isinstance(chart, Mapping):
        chart = {}
    safety = context.get("safety") or {}
    if not isinstance(safety, Mapping):
        safety = {}
    market = context.get("market") or {}
    if not isinstance(market, Mapping):
        market = {}
    chain = context.get("chain_heat") or {}
    if not isinstance(chain, Mapping):
        chain = {}
    micro_events = context.get("micro_events") or []
    first_micro = micro_events[0] if micro_events else {}
    if not isinstance(first_micro, Mapping):
        first_micro = {}

    resolved_episode_id = episode_id
    if resolved_episode_id is None:
        raw_ep = episode_payload.get("episode_id")
        if raw_ep is not None:
            try:
                resolved_episode_id = int(raw_ep)
            except (TypeError, ValueError):
                resolved_episode_id = None

    window_id = window.get("id") if window.get("id") is not None else episode_payload.get("window_id")
    token_id = window.get("token_id") if window.get("token_id") is not None else episode_payload.get("token_id")
    pair_id = window.get("pair_id") if window.get("pair_id") is not None else episode_payload.get("pair_id")

    return {
        "episode_id": resolved_episode_id if resolved_episode_id is not None else _CATEGORICAL_UNKNOWN,
        "window_id": window_id if window_id is not None else _CATEGORICAL_UNKNOWN,
        "token_id": token_id if token_id is not None else _CATEGORICAL_UNKNOWN,
        "pair_id": pair_id if pair_id is not None else _CATEGORICAL_UNKNOWN,
        "window_kind": _categorical_label(window.get("window_kind")),
        "outcome_label": _categorical_label(episode_payload.get("outcome_label")),
        "memory_quality_label": _categorical_label(
            episode_payload.get("memory_quality_label")
        ),
        "market_regime_label": _categorical_label(market.get("market_regime_label")),
        "chain_heat_label": _categorical_label(chain.get("chain_heat_label")),
        "safety_status_label": _categorical_label(safety.get("safety_status_label")),
        "rug_risk_label": _categorical_label(safety.get("rug_risk_label")),
        "liquidity_state_label": _categorical_label(
            liquidity.get("liquidity_state_label")
        ),
        "exit_realism_label": _categorical_label(liquidity.get("exit_realism_label")),
        "realism_gate_label": _categorical_label(liquidity.get("realism_gate_label")),
        "flow_direction_label": _categorical_label(flow.get("flow_direction_label")),
        "flow_pressure_label": _categorical_label(flow.get("flow_pressure_label")),
        "trend_structure_label": _categorical_label(chart.get("trend_structure_label")),
        "volatility_label": _categorical_label(chart.get("volatility_label")),
        "candle_path_label": _categorical_label(chart.get("candle_path_label")),
        "micro_event_state_label": _categorical_label(
            first_micro.get("micro_event_state_label")
        ),
        "held_to_15m_result_label": _categorical_label(
            first_micro.get("held_to_15m_result_label")
        ),
        "token_age_bucket": _categorical_label(episode_payload.get("token_age_bucket")),
        "pair_age_bucket": _categorical_label(episode_payload.get("pair_age_bucket")),
        "discovery_label": _categorical_label(episode_payload.get("discovery_label")),
        "tracking_lane": _resolve_tracking_lane(episode_payload, window, context),
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
    # Exact-link episode identity into the stored payload when callers pass a
    # pre-built payload that omitted it.
    payload = dict(fingerprint_payload)
    if payload.get("episode_id") in (None, "", "UNKNOWN"):
        payload["episode_id"] = int(episode_id)
    with connect(db_path_or_conn) as connection:
        existing = connection.execute(
            """
            SELECT id FROM printer_memory_fingerprints
            WHERE episode_id = ? AND fingerprint_kind = 'STATIC_CONDITION_SUMMARY'
            LIMIT 1
            """,
            (int(episode_id),),
        ).fetchone()
        if existing is not None:
            return int(existing["id"] if isinstance(existing, sqlite3.Row) else existing[0])
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
                json.dumps(payload, sort_keys=True),
                status,
                DataQualityLabel.CLEAN_DATA.value,
                do_not_train,
            ),
        )
        return int(cursor.lastrowid)
