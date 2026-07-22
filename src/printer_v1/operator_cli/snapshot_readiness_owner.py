"""One-shot governed owner for a readiness-only exact-pair snapshot bundle."""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from typing import Any, Callable, Mapping

from printer_v1.operator_cli.e2m_snapshot_persistence import (
    E2M_STATUS_PERSISTED,
    _normalize_verified_inactivity,
    _select_primary_pair,
    persist_snapshot_from_source_response,
)
from printer_v1.operator_cli.snapshot_readiness_contract import (
    readiness_base_blockers,
    snapshot_readiness_blockers,
)


def execute_readiness_snapshot_bundle(
    connection: sqlite3.Connection,
    step: Mapping[str, Any],
    *,
    dexscreener_adapter_factory: Callable[..., Any],
    timeout_seconds: float,
    geckoterminal_transports: Mapping[str, Any] | None = None,
    evaluated_at: str | datetime | None = None,
    request_pacer: Any | None = None,
) -> dict[str, Any]:
    """Run DexScreener once, then at most two exact-pool 15m requests.

    Missing base liquidity/5m/wider evidence blocks before GeckoTerminal.  The
    two completion requests are made only when E.19 verified inactivity cannot
    already prove the absent 15m fields.  There is no retry, rotation, metadata
    fallback, or lifecycle activation.
    """
    from printer_v1.operator_cli.commands import (
        enrich_eligible_geckoterminal_candidate_15m,
    )
    from printer_v1.operator_cli.holder_reliability_budget_control import SequentialRequestPacer
    from printer_v1.sources.budget_accounting import count_recent_source_requests
    from printer_v1.sources.contracts import build_governed_source_request
    from printer_v1.sources.governed_execution import (
        execute_source_request_with_governor,
    )

    mint = str(step.get("token_mint") or "").strip()
    pair_address = str(step.get("pair_address") or "").strip()
    run_id = str(step.get("run_id") or "").strip()
    step_key = str(step.get("step_key") or "readiness_snapshot").strip()
    tracking_lane = str(step.get("tracking_lane") or "TRACK_FAST")
    if not mint or not pair_address or not run_id:
        return {
            "ok": False,
            "blocked_reasons": ["READINESS_EXACT_IDENTITY_REQUIRED"],
            "operations_attempted": 0,
        }

    pacer = request_pacer or SequentialRequestPacer()
    pacer.pace("dexscreener")
    request = build_governed_source_request(
        "dexscreener",
        "pair_market_snapshot",
        request_key=f"{run_id}:{step_key}:dexscreener",
        payload={"token_mint": mint, "pair_address": pair_address},
    )
    execution = execute_source_request_with_governor(
        connection,
        request,
        dexscreener_adapter_factory(
            token_mint=mint, timeout_seconds=timeout_seconds
        ),
        recent_request_count=count_recent_source_requests(connection, "dexscreener"),
    )
    result: dict[str, Any] = {
        "ok": False,
        "operations_attempted": 1,
        "primary_source_request_id": int(execution.request_record.id),
        "primary_source_response_id": (
            int(execution.response_record.id) if execution.response_record else None
        ),
        "primary_source_failure_id": (
            int(execution.failure_record.id) if execution.failure_record else None
        ),
        "completion_records": [],
    }
    if execution.response_record is None:
        result["blocked_reasons"] = [
            execution.normalized_result.failure_type or "READINESS_PRIMARY_FAILED"
        ]
        return result

    payload = dict(execution.normalized_result.normalized_payload or {})
    pairs = payload.get("pairs")
    base_pair = _select_primary_pair(
        list(pairs) if isinstance(pairs, list) else [], mint, pair_address
    )
    if base_pair is None:
        result["blocked_reasons"] = ["READINESS_PRIMARY_EXACT_PAIR_MISSING"]
        return result
    normalized_base = _normalize_verified_inactivity(base_pair)
    base_blockers = readiness_base_blockers(normalized_base)
    if base_blockers:
        result["blocked_reasons"] = base_blockers
        return result

    checked_at = evaluated_at or datetime.now(timezone.utc)
    already_ready = snapshot_readiness_blockers(
        normalized_base,
        expected_mint=mint,
        expected_pair=pair_address,
        evaluated_at=checked_at,
    )
    evidence: Mapping[str, Any] | None = None
    if already_ready:
        candidate = dict(base_pair)
        candidate.update({
            "chain": "solana",
            "token_mint": mint,
            "pair_address": pair_address,
        })
        completion = enrich_eligible_geckoterminal_candidate_15m(
            connection,
            candidate,
            timeout_seconds=timeout_seconds,
            request_key_prefix=f"{run_id}:{step_key}:completion",
            transports=geckoterminal_transports,
            request_pacer=pacer,
        )
        evidence = completion.get("evidence")
        result["operations_attempted"] += int(completion.get("requests_attempted") or 0)
        result["completion_records"] = list(completion.get("records") or [])

    persisted = persist_snapshot_from_source_response(
        connection,
        int(execution.response_record.id),
        mint,
        expected_pair_address=pair_address,
        tracking_lane=tracking_lane,
        supplemental_15m_evidence=dict(evidence or {}),
        require_readiness_contract=True,
        evaluated_at=checked_at,
    )
    result["persistence"] = persisted
    result["snapshot_id"] = persisted.get("snapshot_id")
    result["ok"] = persisted.get("e2m_status") == E2M_STATUS_PERSISTED
    if not result["ok"]:
        result["blocked_reasons"] = list(persisted.get("blocked_reasons") or [])
    return result
