"""Strict, source-owned readiness contract for a future 15-minute lifecycle.

This module is pure: it performs no transport and no database writes.  It
combines only exact-pair fields from already governed responses and fails
closed whenever price/liquidity, 5m activity, exact 15m evidence, wider
activity, freshness, identity, or provenance is incomplete.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Mapping


READINESS_PRIMARY_SOURCE = "geckoterminal"
READINESS_15M_SOURCE = "geckoterminal"
READINESS_PRIMARY_OPERATIONS_PER_TOKEN = 1
READINESS_15M_OPERATIONS_PER_TOKEN = 2
READINESS_OPERATIONS_PER_TOKEN = 3
READINESS_TOKEN_COUNT = 2
READINESS_OPERATION_RESERVATION = 6
READINESS_PRIMARY_TTL_SECONDS = 180
READINESS_15M_TTL_SECONDS = 180
READINESS_WINDOW_SECONDS = 900

PROVIDER_CANDLE_DERIVED = "PROVIDER_CANDLE_DERIVED"
PROVIDER_TRADES_WINDOW = "PROVIDER_TRADES_WINDOW"
TRADE_HISTORY_COMPLETE = "TRADE_HISTORY_COMPLETE"
VERIFIED_INACTIVITY = "SNAPSHOT_VERIFIED_INACTIVE"

_SHORT_FIELDS = (
    "price_change_5m", "volume_5m", "txns_5m",
    "price_change_15m", "volume_15m", "txns_15m",
)
_SUPPLEMENTAL_15M_FIELDS = (
    "price_change_15m", "price_change_15m_source_kind",
    "price_change_15m_provenance", "volume_15m",
    "volume_15m_source_kind", "volume_15m_provenance", "txns_15m",
    "txns_15m_source_kind", "txns_15m_completeness",
    "txns_15m_provenance",
)


def _time(value: str | datetime) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(
        str(value).replace("Z", "+00:00")
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _number(value: Any, *, positive: bool = False, integer: bool = False) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    numeric = float(value)
    if not math.isfinite(numeric):
        return False
    if positive and numeric <= 0:
        return False
    if not positive and numeric < 0:
        return False
    return not integer or numeric.is_integer()


def readiness_base_blockers(pair: Mapping[str, Any]) -> list[str]:
    """Validate fields owned by the exact-pair base snapshot."""
    blockers: list[str] = []
    for field in ("price_usd", "liquidity_usd"):
        if not _number(pair.get(field), positive=True):
            blockers.append(f"READINESS_MISSING_OR_INVALID:{field}")
    liquidity_provenance = pair.get("liquidity_provenance")
    if not isinstance(liquidity_provenance, Mapping):
        blockers.append("READINESS_LIQUIDITY_PROVENANCE:missing")
    else:
        if liquidity_provenance.get("source") != READINESS_PRIMARY_SOURCE:
            blockers.append("READINESS_LIQUIDITY_PROVENANCE:source")
        if liquidity_provenance.get("raw_field") != "reserve_in_usd":
            blockers.append("READINESS_LIQUIDITY_PROVENANCE:raw_field")
        if liquidity_provenance.get("network") != "solana":
            blockers.append("READINESS_LIQUIDITY_PROVENANCE:network")
        if str(liquidity_provenance.get("pool_address") or "") != str(pair.get("pair_address") or ""):
            blockers.append("READINESS_LIQUIDITY_PROVENANCE:pair")
        if str(liquidity_provenance.get("token_mint") or "").lower() != str(pair.get("token_mint") or "").lower():
            blockers.append("READINESS_LIQUIDITY_PROVENANCE:mint")
    if not isinstance(pair.get("price_change_5m"), (int, float)) or not math.isfinite(
        float(pair.get("price_change_5m") or 0)
    ):
        blockers.append("READINESS_MISSING_OR_INVALID:price_change_5m")
    for field in ("volume_5m", "volume_1h"):
        if not _number(pair.get(field)):
            blockers.append(f"READINESS_MISSING_OR_INVALID:{field}")
    for field in ("txns_5m", "txns_1h"):
        if not _number(pair.get(field), integer=True):
            blockers.append(f"READINESS_MISSING_OR_INVALID:{field}")
    return blockers


def merge_exact_15m_evidence(
    pair: Mapping[str, Any],
    evidence: Mapping[str, Any] | None,
    *,
    expected_mint: str,
    expected_pair: str,
) -> tuple[dict[str, Any], list[str]]:
    """Fill only missing 15m fields; reject overwrite, identity, or conflict."""
    merged = dict(pair)
    if not evidence:
        return merged, []
    blockers: list[str] = []
    for field in _SUPPLEMENTAL_15M_FIELDS:
        if field not in evidence:
            continue
        incoming = evidence[field]
        existing = merged.get(field)
        if existing is not None and existing != incoming:
            blockers.append(f"READINESS_EVIDENCE_CONFLICT:{field}")
        elif existing is None:
            merged[field] = incoming
    for field in (
        "price_change_15m_provenance", "volume_15m_provenance",
        "txns_15m_provenance",
    ):
        provenance = merged.get(field)
        if not isinstance(provenance, Mapping):
            continue
        if str(provenance.get("pool_address") or "") != expected_pair:
            blockers.append(f"READINESS_TARGET_MISMATCH:{field}:pair")
        mint = provenance.get("token_mint")
        if mint is not None and str(mint).lower() != expected_mint.lower():
            blockers.append(f"READINESS_TARGET_MISMATCH:{field}:mint")
    return merged, sorted(set(blockers))


def _valid_verified_inactivity(pair: Mapping[str, Any]) -> tuple[bool, set[str]]:
    provenance = pair.get("snapshot_inactivity_evidence")
    if not isinstance(provenance, Mapping) or provenance.get("label") != VERIFIED_INACTIVITY:
        return False, set()
    predicate = provenance.get("predicate")
    converted = provenance.get("converted_fields")
    if not isinstance(predicate, Mapping) or not isinstance(converted, list):
        return False, set()
    required = {
        "exact_pair_and_target_validated",
        "source_complete_clean",
        "price_and_liquidity_positive",
        "wider_activity_present_and_inactive",
    }
    fields = {str(field) for field in converted}
    valid = (
        required.issubset(predicate)
        and all(predicate.get(key) is True for key in required)
        and fields.issubset(_SHORT_FIELDS)
        and all(pair.get(field) == 0 for field in fields)
        and _number(pair.get("price_usd"), positive=True)
        and _number(pair.get("liquidity_usd"), positive=True)
        and pair.get("volume_1h") == 0
        and pair.get("txns_1h") == 0
    )
    return valid, fields


def _provenance_time_fresh(
    provenance: Mapping[str, Any], evaluated_at: datetime
) -> bool:
    raw = provenance.get("fetch_time_iso")
    if not isinstance(raw, str):
        return False
    try:
        age = (evaluated_at - _time(raw)).total_seconds()
    except (TypeError, ValueError):
        return False
    return -5 <= age <= READINESS_15M_TTL_SECONDS


def _exact_window(provenance: Mapping[str, Any]) -> tuple[datetime, datetime] | None:
    start_raw = provenance.get("candle_start_iso") or provenance.get("window_start_iso")
    end_raw = provenance.get("candle_end_iso") or provenance.get("window_end_iso")
    if not isinstance(start_raw, str) or not isinstance(end_raw, str):
        return None
    try:
        start, end = _time(start_raw), _time(end_raw)
    except (TypeError, ValueError):
        return None
    if (end - start).total_seconds() != READINESS_WINDOW_SECONDS:
        return None
    return start, end


def snapshot_readiness_blockers(
    pair: Mapping[str, Any],
    *,
    expected_mint: str,
    expected_pair: str,
    evaluated_at: str | datetime,
) -> list[str]:
    """Return factual blockers; an empty list is the only readiness PASS."""
    blockers = readiness_base_blockers(pair)
    if str(pair.get("chain") or "") != "solana":
        blockers.append("READINESS_TARGET_MISMATCH:chain")
    if str(pair.get("token_mint") or "").lower() != expected_mint.lower():
        blockers.append("READINESS_TARGET_MISMATCH:mint")
    if str(pair.get("pair_address") or "") != expected_pair:
        blockers.append("READINESS_TARGET_MISMATCH:pair")

    inactivity_valid, converted = _valid_verified_inactivity(pair)
    for field in ("price_change_15m", "volume_15m"):
        value = pair.get(field)
        if field in converted and inactivity_valid:
            continue
        if field == "price_change_15m":
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
                blockers.append(f"READINESS_MISSING_OR_INVALID:{field}")
        elif not _number(value):
            blockers.append(f"READINESS_MISSING_OR_INVALID:{field}")
    if "txns_15m" not in converted or not inactivity_valid:
        if not _number(pair.get("txns_15m"), integer=True):
            blockers.append("READINESS_MISSING_OR_INVALID:txns_15m")

    if inactivity_valid and {
        "price_change_15m", "volume_15m", "txns_15m"
    }.issubset(converted):
        return sorted(set(blockers))

    evaluated = _time(evaluated_at)
    price_prov = pair.get("price_change_15m_provenance")
    volume_prov = pair.get("volume_15m_provenance")
    txn_prov = pair.get("txns_15m_provenance")
    if pair.get("price_change_15m_source_kind") != PROVIDER_CANDLE_DERIVED:
        blockers.append("READINESS_15M_PROVENANCE:price_change_source_kind")
    if pair.get("volume_15m_source_kind") != PROVIDER_CANDLE_DERIVED:
        blockers.append("READINESS_15M_PROVENANCE:volume_source_kind")
    if pair.get("txns_15m_source_kind") != PROVIDER_TRADES_WINDOW:
        blockers.append("READINESS_15M_PROVENANCE:txns_source_kind")
    if pair.get("txns_15m_completeness") != TRADE_HISTORY_COMPLETE:
        blockers.append("READINESS_15M_PROVENANCE:trade_history_incomplete")

    provenances = (price_prov, volume_prov, txn_prov)
    windows: list[tuple[datetime, datetime]] = []
    for label, provenance in zip(("price", "volume", "txns"), provenances):
        if not isinstance(provenance, Mapping):
            blockers.append(f"READINESS_15M_PROVENANCE:{label}_missing")
            continue
        if provenance.get("source") != READINESS_15M_SOURCE:
            blockers.append(f"READINESS_15M_PROVENANCE:{label}_source")
        if provenance.get("network") != "solana":
            blockers.append(f"READINESS_15M_PROVENANCE:{label}_network")
        if str(provenance.get("pool_address") or "") != expected_pair:
            blockers.append(f"READINESS_TARGET_MISMATCH:{label}_pair")
        if not isinstance(provenance.get("source_request_id"), int) or not isinstance(
            provenance.get("source_response_id"), int
        ):
            blockers.append(f"READINESS_15M_PROVENANCE:{label}_lineage")
        if not _provenance_time_fresh(provenance, evaluated):
            blockers.append(f"READINESS_15M_PROVENANCE:{label}_stale")
        window = _exact_window(provenance)
        if window is None:
            blockers.append(f"READINESS_15M_PROVENANCE:{label}_window")
        else:
            windows.append(window)
    if len(windows) == 3 and not (windows[0] == windows[1] == windows[2]):
        blockers.append("READINESS_15M_PROVENANCE:window_conflict")
    return sorted(set(blockers))
