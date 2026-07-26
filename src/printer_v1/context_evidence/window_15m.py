"""Resolve shared WINDOW_15M context from governed stored evidence only.

This module does not fetch sources, schedule work, create memory, or write to
the database. Collection remains owned by Source Governor and Central
Scheduler paths. The resolver is deliberately fail-closed and never selects
evidence observed after the target window.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from typing import Any

from printer_v1.chain_heat.lookup import chain_heat_snapshot_is_valid_for_memory
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
from printer_v1.market_regime.lookup import market_snapshot_is_valid_for_memory
from printer_v1.paper_quote.evidence import row_level_clean_eligible as quote_row_is_clean
from printer_v1.safety.evidence import row_level_clean_eligible as safety_row_is_clean
from printer_v1.safety.goplus_normalizer import safety_memory_policy_summary
from printer_v1.safety.composite import (
    composite_row_is_acceptable,
    effective_safety_context_report,
)
from printer_v1.snapshots.cadence_policy import get_policy
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


WINDOW_KIND = "WINDOW_15M"
WINDOW_SECONDS = 900
CLEAN_SOURCE_STATUSES = {"COMPLETE", "PARTIAL"}
CLEAN_DATA_QUALITY = {"CLEAN_DATA", "ACCEPTABLE_PARTIAL_DATA"}


def _parse_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _dict(row: sqlite3.Row | None) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone() is not None


def _source_trace_is_clean(
    connection: sqlite3.Connection,
    *,
    source_request_id: Any,
    source_response_id: Any,
    expected_source: str | None = None,
) -> bool:
    if source_request_id is None or source_response_id is None:
        return False
    row = connection.execute(
        """
        SELECT response.source_name,
               response.source_status AS response_status,
               response.data_quality_label AS response_quality,
               request.source_status AS request_status,
               request.data_quality_label AS request_quality
        FROM printer_source_responses response
        JOIN printer_source_requests request
          ON request.id = response.source_request_id
        WHERE response.id = ? AND request.id = ?
        """,
        (source_response_id, source_request_id),
    ).fetchone()
    if row is None or (expected_source and row["source_name"] != expected_source):
        return False
    return (
        row["response_status"] in CLEAN_SOURCE_STATUSES
        and row["request_status"] in CLEAN_SOURCE_STATUSES
        and row["response_quality"] in CLEAN_DATA_QUALITY
        and row["request_quality"] in CLEAN_DATA_QUALITY
    )


def _snapshot_trace(connection: sqlite3.Connection, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    raw = _json_object(snapshot.get("raw_snapshot_payload_json"))
    normalized = _json_object(snapshot.get("normalized_snapshot_payload_json"))
    request_id = raw.get("source_request_id") or normalized.get("source_request_id")
    response_id = raw.get("source_response_id") or normalized.get("source_response_id")
    source_name = raw.get("source_name") or normalized.get("source_name")
    if request_id is None and _table_exists(connection, "printer_memory_factory_run_steps"):
        step = connection.execute(
            """
            SELECT source_request_id, source_response_id
            FROM printer_memory_factory_run_steps
            WHERE snapshot_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (snapshot["id"],),
        ).fetchone()
        if step:
            request_id = step["source_request_id"]
            response_id = step["source_response_id"]
    clean = _source_trace_is_clean(
        connection,
        source_request_id=request_id,
        source_response_id=response_id,
        expected_source=source_name,
    )
    return {
        "source_name": source_name,
        "source_request_id": request_id,
        "source_response_id": response_id,
        "source_trace_clean": clean,
    }


def _broad_context(
    connection: sqlite3.Connection,
    *,
    table: str,
    payload_column: str,
    target_time: datetime,
    valid_for_memory,
) -> dict[str, Any]:
    rows = connection.execute(
        f"SELECT * FROM {table} WHERE captured_at <= ? ORDER BY captured_at DESC, id DESC",
        (target_time.isoformat(),),
    ).fetchall()
    for row in rows:
        item = dict(row)
        if not valid_for_memory(item, target_time):
            continue
        payload = _json_object(item.get(payload_column))
        request_id = payload.get("source_request_id")
        response_id = payload.get("source_response_id")
        source_name = payload.get("governed_context_source")
        if not _source_trace_is_clean(
            connection,
            source_request_id=request_id,
            source_response_id=response_id,
            expected_source=source_name,
        ):
            continue
        item["source_request_id"] = request_id
        item["source_response_id"] = response_id
        item["source_name"] = source_name
        return item
    return {}


def _latest_exact_evidence(
    connection: sqlite3.Connection,
    *,
    table: str,
    token_id: int,
    pair_id: int,
    snapshot_id: int,
    target_time: datetime | None,
    direction: str | None = None,
) -> dict[str, Any]:
    """Latest evidence bound to the exact target snapshot.

    target_time is the approved closing-evidence cutoff. Passing None removes
    the upper bound and is used only to probe whether evidence exists beyond
    the cutoff, so an absent row can be reported differently from a late one.
    """
    clauses = [
        "token_id = ?",
        "pair_id = ?",
        "snapshot_id = ?",
    ]
    params: list[Any] = [token_id, pair_id, snapshot_id]
    if target_time is not None:
        clauses.append("datetime(evidence_captured_at) <= datetime(?)")
        params.append(target_time.isoformat())
    if direction is not None:
        clauses.append("quote_direction = ?")
        params.append(direction)
    row = connection.execute(
        f"""
        SELECT * FROM {table}
        WHERE {' AND '.join(clauses)}
        ORDER BY datetime(evidence_captured_at) DESC, id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    return _dict(row)


def _latest_safety_composite(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    snapshot_id: int,
    target_time: datetime | None,
) -> dict[str, Any]:
    if not _table_exists(connection, "printer_safety_evidence_composites"):
        return {}
    clauses = ["token_id=?", "pair_id=?", "snapshot_id=?"]
    params: list[Any] = [token_id, pair_id, snapshot_id]
    if target_time is not None:
        clauses.append("datetime(evidence_captured_at) <= datetime(?)")
        params.append(target_time.isoformat())
    row = connection.execute(
        f"""
        SELECT * FROM printer_safety_evidence_composites
        WHERE {' AND '.join(clauses)}
        ORDER BY datetime(evidence_captured_at) DESC, id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    if row is None:
        return {}
    result = dict(row)
    result["contributions"] = [
        dict(item) for item in connection.execute(
            """
            SELECT * FROM printer_safety_evidence_contributions
            WHERE composite_id=? ORDER BY id
            """,
            (result["id"],),
        ).fetchall()
    ]
    return result


def _label(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _section(*, status: str, clean: bool, blockers: list[str], **payload: Any) -> dict[str, Any]:
    return {
        "status": status,
        "can_support_clean_memory": clean,
        "blockers": list(dict.fromkeys(blockers)),
        **payload,
    }


def _build_window_context_evidence(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    snapshot_start_id: int,
    snapshot_end_id: int,
    window_start_at: str | datetime,
    window_end_at: str | datetime,
    window_kind: str,
    minimum_seconds: int,
    entry_snapshot_id: int,
    tracking_lane: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build read-only exact-target context for an approved main window."""

    connection.row_factory = sqlite3.Row
    window_start = _parse_time(window_start_at)
    window_end = _parse_time(window_end_at)
    if window_end <= window_start:
        raise ValueError(f"{window_kind} end must be after start")
    if (window_end - window_start).total_seconds() < minimum_seconds:
        raise ValueError(
            f"{window_kind} evidence must span at least {minimum_seconds} seconds"
        )

    # V2-9.4.6: window_end_at stays the immutable logical deadline used for
    # identity, duration, cadence and deadline drift. The approved closing
    # allowance is a separate, evidence-only cutoff: governed closing work
    # legitimately completes a few seconds after the deadline, and rejecting it
    # produced Attempt 6's false "no exact-target evidence" blockers. When no
    # lane is supplied the allowance is zero, which is the stricter behaviour.
    policy = get_policy(window_kind, tracking_lane) if tracking_lane else None
    closing_allowance_seconds = int(policy.closing_clean_late_seconds) if policy else 0
    closing_evidence_cutoff = window_end + timedelta(seconds=closing_allowance_seconds)

    # V2-9.4.6: select the exact current-run ledger set by snapshot id, never by
    # a token/pair wall-clock scan. The old scan admitted the predecessor
    # captured exactly at window_start_at and excluded a slightly-late closing
    # snapshot while coincidentally preserving the expected count.
    snapshots = [
        dict(row)
        for row in connection.execute(
            """
            SELECT * FROM printer_token_snapshots
            WHERE token_id = ? AND pair_id = ?
              AND id >= ? AND id <= ?
            ORDER BY id
            """,
            (token_id, pair_id, snapshot_start_id, snapshot_end_id),
        ).fetchall()
    ]
    # The current run ledger is the authoritative identity source: any row in
    # the id range that this run did not record is not this window's evidence.
    non_ledger_ids: list[int] = []
    if run_id and _table_exists(connection, "printer_memory_factory_run_steps"):
        ledger_ids = {
            int(row[0])
            for row in connection.execute(
                "SELECT snapshot_id FROM printer_memory_factory_run_steps"
                " WHERE run_id = ? AND snapshot_id IS NOT NULL",
                (run_id,),
            ).fetchall()
        }
        non_ledger_ids = [int(r["id"]) for r in snapshots if int(r["id"]) not in ledger_ids]
        snapshots = [r for r in snapshots if int(r["id"]) in ledger_ids]

    ids = [int(row["id"]) for row in snapshots]
    exact_bounds = bool(ids) and ids[0] == snapshot_start_id and ids[-1] == snapshot_end_id
    snapshot_traces = [_snapshot_trace(connection, row) for row in snapshots]
    snapshots_clean = (
        exact_bounds
        and len(snapshots) >= 2
        and all(row.get("source_status") in CLEAN_SOURCE_STATUSES for row in snapshots)
        and all(row.get("data_quality_label") in CLEAN_DATA_QUALITY for row in snapshots)
        and all(row.get("price_usd") is not None and row.get("liquidity_usd") is not None for row in snapshots)
        and all(trace["source_trace_clean"] for trace in snapshot_traces)
    )
    snapshot_blockers: list[str] = []
    if non_ledger_ids:
        snapshot_blockers.append("SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER")
    if not exact_bounds:
        snapshot_blockers.append("SNAPSHOT_BOUNDARY_MISMATCH")
    if len(snapshots) < 2:
        snapshot_blockers.append("INSUFFICIENT_WINDOW_SNAPSHOTS")
    if any(row.get("source_status") not in CLEAN_SOURCE_STATUSES for row in snapshots):
        snapshot_blockers.append("SNAPSHOT_SOURCE_NOT_CLEAN")
    if any(row.get("data_quality_label") not in CLEAN_DATA_QUALITY for row in snapshots):
        snapshot_blockers.append("SNAPSHOT_DATA_NOT_CLEAN")
    if any(row.get("price_usd") is None or row.get("liquidity_usd") is None for row in snapshots):
        snapshot_blockers.append("SNAPSHOT_CRITICAL_FIELDS_MISSING")
    if not snapshots or any(not trace["source_trace_clean"] for trace in snapshot_traces):
        snapshot_blockers.append("SNAPSHOT_SOURCE_TRACE_MISSING_OR_INVALID")

    market = _broad_context(
        connection,
        table="printer_market_regime_snapshots",
        payload_column="normalized_market_payload_json",
        target_time=window_end,
        valid_for_memory=market_snapshot_is_valid_for_memory,
    )
    market_section = _section(
        status="READY" if market else "UNKNOWN_MARKET_REGIME",
        clean=bool(market),
        blockers=[] if market else ["NO_CLEAN_GOVERNED_MARKET_CONTEXT_AT_OR_BEFORE_WINDOW_END"],
        row=market,
        labels={
            "market_regime_label": market.get("market_regime_label", "UNKNOWN"),
            "market_transition_label": market.get("market_transition_label", "UNKNOWN_TRANSITION"),
            "market_payload_quality_label": market.get("market_payload_quality_label", "MARKET_CONTEXT_UNKNOWN"),
        },
    )

    chain = _broad_context(
        connection,
        table="printer_solana_chain_heat_snapshots",
        payload_column="normalized_chain_heat_payload_json",
        target_time=window_end,
        valid_for_memory=chain_heat_snapshot_is_valid_for_memory,
    )
    chain_section = _section(
        status="READY" if chain else "SOLANA_UNKNOWN",
        clean=bool(chain),
        blockers=[] if chain else ["NO_CLEAN_GOVERNED_CHAIN_CONTEXT_AT_OR_BEFORE_WINDOW_END"],
        row=chain,
        labels={
            "chain_heat_label": chain.get("chain_heat_label", "SOLANA_UNKNOWN"),
            "chain_heat_transition_label": chain.get("chain_heat_transition_label", "SOLANA_TRANSITION_UNKNOWN"),
            "chain_heat_payload_quality_label": chain.get("chain_heat_payload_quality_label", "CHAIN_HEAT_CONTEXT_UNKNOWN"),
        },
    )

    # Closing safety is bound to the exact closing snapshot and accepted only
    # inside the approved allowance after the logical deadline.
    safety_composite = _latest_safety_composite(
        connection,
        token_id=token_id,
        pair_id=pair_id,
        snapshot_id=snapshot_end_id,
        target_time=closing_evidence_cutoff,
    )
    safety = safety_composite or _latest_exact_evidence(
        connection,
        table="printer_solana_safety_evidence",
        token_id=token_id,
        pair_id=pair_id,
        snapshot_id=snapshot_end_id,
        target_time=closing_evidence_cutoff,
    )
    safety_late = not safety and bool(
        _latest_safety_composite(
            connection, token_id=token_id, pair_id=pair_id,
            snapshot_id=snapshot_end_id, target_time=None,
        )
        or _latest_exact_evidence(
            connection, table="printer_solana_safety_evidence", token_id=token_id,
            pair_id=pair_id, snapshot_id=snapshot_end_id, target_time=None,
        )
    )
    safety_policy = safety_memory_policy_summary(safety) if safety else {}
    safety_trace_clean = (
        bool(safety_composite and safety_composite.get("provenance_complete"))
        if safety_composite
        else bool(safety) and _source_trace_is_clean(
            connection,
            source_request_id=safety.get("source_request_id"),
            source_response_id=safety.get("source_response_id"),
            expected_source=safety.get("source_name"),
        )
    )
    composite_acceptable = (
        composite_row_is_acceptable(safety_composite)
        if safety_composite
        else False
    )
    safety_base_clean = bool(
        safety
        and safety_trace_clean
        and (
            composite_acceptable
            or safety.get("source_status") in CLEAN_SOURCE_STATUSES
        )
        and (
            composite_acceptable
            or safety.get("data_quality_label") in CLEAN_DATA_QUALITY
        )
        and safety.get("target_status") == "TARGET_MATCH"
        and safety.get("freshness_label") in {"SAFETY_EVIDENCE_FRESH", "SAFETY_EVIDENCE_ACCEPTABLE"}
        and bool(safety.get("paper_only_context"))
        and (safety_composite or safety.get("source_failure_id") is None)
    )
    safety_clean = bool(
        safety_base_clean
        and (
            composite_acceptable
            if safety_composite
            else safety_row_is_clean(safety)
            or safety_policy.get("safety_acceptable_for_15m_memory")
        )
    )
    # V2-9.4.6: name the real cause instead of a generic "no valid evidence".
    safety_blockers: list[str] = []
    if not safety_clean:
        if safety_late:
            safety_blockers.append("CLOSING_EVIDENCE_AFTER_APPROVED_CUTOFF")
        elif not safety:
            safety_blockers.append("CLOSING_SAFETY_EVIDENCE_ABSENT_FOR_EXACT_SNAPSHOT")
        elif safety.get("target_status") not in (None, "TARGET_MATCH"):
            safety_blockers.append("CLOSING_EVIDENCE_TARGET_MISMATCH")
        elif safety_composite:
            composite_blockers = json.loads(
                str(safety_composite.get("blockers_json") or "[]")
            )
            if "HOLDER_EVIDENCE_TARGET_MISMATCH" in composite_blockers:
                safety_blockers.append("HOLDER_EVIDENCE_TARGET_MISMATCH")
            elif (
                "HOLDER_EVIDENCE_PROVENANCE_INVALID" in composite_blockers
                or "SAFETY_COMPOSITE_PROVENANCE_INCOMPLETE" in composite_blockers
            ):
                safety_blockers.append("HOLDER_EVIDENCE_PROVENANCE_INVALID")
            else:
                safety_blockers.append("NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE")
        else:
            safety_blockers.append("NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE")
    safety_effective = effective_safety_context_report(
        safety,
        gate_accepted=safety_clean,
        window_kind=window_kind,
    )
    safety_effective_labels = {
        key: value
        for key, value in safety_effective.items()
        if key != "window_kind"
    }
    safety_section = _section(
        status="READY" if safety_clean else "UNKNOWN_SAFETY",
        clean=safety_clean,
        blockers=safety_blockers,
        row=safety,
        policy=safety_policy,
        effective_context=safety_effective,
        labels={
            "safety_status_label": safety.get(
                "safety_contract_label",
                safety.get("safety_context_label", "UNKNOWN_SAFETY"),
            ),
            "safety_action_label": safety_effective[
                "effective_safety_context_result"
            ],
            **safety_effective_labels,
        },
    )

    quotes: dict[str, dict[str, Any]] = {}
    quote_blockers: list[str] = []
    for direction in ("ENTRY", "EXIT"):
        quote_snapshot_id = entry_snapshot_id if direction == "ENTRY" else snapshot_end_id
        quote = _latest_exact_evidence(
            connection,
            table="printer_paper_quote_evidence",
            token_id=token_id,
            pair_id=pair_id,
            snapshot_id=quote_snapshot_id,
            target_time=closing_evidence_cutoff,
            direction=direction,
        )
        quote_late = not quote and bool(
            _latest_exact_evidence(
                connection,
                table="printer_paper_quote_evidence",
                token_id=token_id,
                pair_id=pair_id,
                snapshot_id=quote_snapshot_id,
                target_time=None,
                direction=direction,
            )
        )
        trace_clean = bool(quote) and _source_trace_is_clean(
            connection,
            source_request_id=quote.get("source_request_id"),
            source_response_id=quote.get("source_response_id"),
            expected_source=quote.get("source_name"),
        )
        if not quote or not trace_clean or quote.get("source_failure_id") is not None or not quote_row_is_clean(quote):
            if quote_late:
                quote_blockers.append("CLOSING_EVIDENCE_AFTER_APPROVED_CUTOFF")
            elif not quote and direction == "EXIT":
                quote_blockers.append("CLOSING_EXIT_QUOTE_ABSENT_FOR_EXACT_SNAPSHOT")
            elif quote and quote.get("target_status") not in (None, "TARGET_MATCH"):
                quote_blockers.append("CLOSING_EVIDENCE_TARGET_MISMATCH")
            else:
                quote_blockers.append(f"NO_VALID_EXACT_TARGET_{direction}_QUOTE_EVIDENCE")
        quotes[direction.lower()] = quote
    quote_clean = not quote_blockers
    liquidity_section = _section(
        status="READY" if quote_clean else "LIQUIDITY_REALISM_UNKNOWN",
        clean=quote_clean,
        blockers=quote_blockers,
        entry_quote=quotes["entry"],
        exit_quote=quotes["exit"],
        labels={
            "liquidity_state_label": (quotes["entry"] or quotes["exit"]).get("liquidity_context_label", "LIQUIDITY_UNKNOWN"),
            "entry_realism_label": quotes["entry"].get("entry_realism_label", "ENTRY_UNKNOWN"),
            "exit_realism_label": quotes["exit"].get("exit_realism_label", "EXIT_UNKNOWN"),
            "slippage_context_label": quotes["entry"].get("slippage_context_label", "SLIPPAGE_UNKNOWN"),
            "price_impact_context_label": quotes["entry"].get("price_impact_context_label", "PRICE_IMPACT_UNKNOWN"),
        },
    )

    flow_payload = normalize_trading_flow_payload(snapshots[-1], window_end) if snapshots else {}
    flow_labels = {
        "flow_direction_label": _label(classify_flow_direction(flow_payload)),
        "flow_pressure_label": _label(classify_flow_pressure(flow_payload)),
        "imbalance_label": _label(classify_imbalance(flow_payload)),
        "volume_activity_label": _label(classify_volume_activity(flow_payload)),
        "tx_activity_label": _label(classify_tx_activity(flow_payload)),
        "wallet_participation_label": _label(classify_wallet_participation(flow_payload)),
        "trading_flow_payload_quality_label": _label(classify_trading_flow_payload_quality(flow_payload, window_end)),
        "flow_memory_gate_label": _label(classify_flow_memory_gate(flow_payload, window_end)),
    }
    flow_clean = bool(
        snapshots_clean
        and flow_labels["flow_direction_label"] != "FLOW_UNKNOWN"
        and flow_labels["flow_pressure_label"] != "PRESSURE_UNKNOWN"
        and flow_labels["flow_memory_gate_label"] not in {"FLOW_CONTEXT_AUDIT_ONLY", "FLOW_CONTEXT_DO_NOT_TRAIN"}
    )
    # V2-9.4.6: when the snapshot set itself is the problem, its precise blocker
    # already says so. Appending the generic flow reason masked that cause in
    # Attempt 6, where direction and pressure were in fact known.
    flow_blockers = list(snapshot_blockers)
    if not flow_clean and snapshots_clean:
        flow_blockers.append("FLOW_DIRECTION_OR_PRESSURE_NOT_CLEAN")
    flow_section = _section(
        status="READY" if flow_clean else "FLOW_UNKNOWN",
        clean=flow_clean,
        blockers=[] if flow_clean else flow_blockers,
        source_snapshot_id=snapshot_end_id if snapshots else None,
        source_trace=snapshot_traces[-1] if snapshot_traces else {},
        payload=flow_payload,
        labels=flow_labels,
    )

    chart_payload = build_chart_payload_from_token_snapshots(snapshots, window_end) if snapshots else {}
    chart_labels = {
        "trend_structure_label": _label(classify_trend_structure(chart_payload)),
        "volatility_label": _label(classify_volatility(chart_payload)),
        "range_behavior_label": _label(classify_range_behavior(chart_payload)),
        "momentum_label": _label(classify_momentum(chart_payload)),
        "drawdown_recovery_label": _label(classify_drawdown_recovery(chart_payload)),
        "candle_path_label": _label(classify_candle_path(chart_payload)),
        "chart_payload_quality_label": _label(classify_chart_payload_quality(chart_payload, window_end)),
        "chart_memory_gate_label": _label(classify_chart_memory_gate(chart_payload, window_end)),
    }
    chart_clean = bool(
        snapshots_clean
        and chart_labels["trend_structure_label"] != "TREND_UNKNOWN"
        and chart_labels["volatility_label"] != "VOLATILITY_UNKNOWN"
        and chart_labels["chart_memory_gate_label"] not in {"CHART_CONTEXT_AUDIT_ONLY", "CHART_CONTEXT_DO_NOT_TRAIN"}
    )
    chart_blockers = list(snapshot_blockers)
    if not chart_clean and snapshots_clean:
        chart_blockers.append("CHART_OR_VOLATILITY_NOT_CLEAN")
    chart_section = _section(
        status="READY" if chart_clean else "CHART_VOLATILITY_UNKNOWN",
        clean=chart_clean,
        blockers=[] if chart_clean else chart_blockers,
        source_snapshot_ids=ids,
        source_traces=snapshot_traces,
        payload=chart_payload,
        labels=chart_labels,
    )

    sections = {
        "market_regime": market_section,
        "solana_chain_heat": chain_section,
        "safety_rug": safety_section,
        "liquidity_exit_realism": liquidity_section,
        "trading_flow": flow_section,
        "chart_volatility": chart_section,
    }
    blockers = [blocker for section in sections.values() for blocker in section["blockers"]]
    return {
        "window_kind": window_kind,
        "token_id": token_id,
        "pair_id": pair_id,
        "snapshot_start_id": snapshot_start_id,
        "snapshot_end_id": snapshot_end_id,
        "window_start_at": window_start.isoformat(),
        "window_end_at": window_end.isoformat(),
        # The logical deadline is unchanged; the cutoff bounds closing evidence
        # only and never extends the window, its duration, or deadline drift.
        "closing_evidence_cutoff_at": closing_evidence_cutoff.isoformat(),
        "closing_evidence_allowance_seconds": closing_allowance_seconds,
        "evidence_duration_seconds": int((window_end - window_start).total_seconds()),
        "snapshot_ids": ids,
        "non_ledger_snapshot_ids": non_ledger_ids,
        "snapshot_source_traces": snapshot_traces,
        "sections": sections,
        "clean_memory_context_ready": all(section["can_support_clean_memory"] for section in sections.values()),
        "blockers": list(dict.fromkeys(blockers)),
        "writes_performed": False,
        "downstream_unlocks": {
            "retrieval": False,
            "paper_decisions": False,
            "buy_sell_hold": False,
            "positions": False,
            "trades": False,
            "audits": False,
            "pnl": False,
        },
    }


def build_window_15m_context_evidence(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    snapshot_start_id: int,
    snapshot_end_id: int,
    window_start_at: str | datetime,
    window_end_at: str | datetime,
    tracking_lane: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    return _build_window_context_evidence(
        connection,
        token_id=token_id,
        pair_id=pair_id,
        snapshot_start_id=snapshot_start_id,
        snapshot_end_id=snapshot_end_id,
        window_start_at=window_start_at,
        window_end_at=window_end_at,
        window_kind=WINDOW_KIND,
        minimum_seconds=WINDOW_SECONDS,
        entry_snapshot_id=snapshot_end_id,
        tracking_lane=tracking_lane,
        run_id=run_id,
    )


def build_window_4h_context_evidence(
    connection: sqlite3.Connection,
    *,
    token_id: int,
    pair_id: int,
    snapshot_start_id: int,
    snapshot_end_id: int,
    window_start_at: str | datetime,
    window_end_at: str | datetime,
    tracking_lane: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    return _build_window_context_evidence(
        connection,
        token_id=token_id,
        pair_id=pair_id,
        snapshot_start_id=snapshot_start_id,
        snapshot_end_id=snapshot_end_id,
        window_start_at=window_start_at,
        window_end_at=window_end_at,
        window_kind="WINDOW_4H",
        minimum_seconds=10_800,
        entry_snapshot_id=snapshot_start_id,
        tracking_lane=tracking_lane,
        run_id=run_id,
    )
