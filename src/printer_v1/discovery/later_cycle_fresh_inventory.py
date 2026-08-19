"""Later-cycle rehydration of fresh protocol-confirmed observation inventory.

This module is deliberately narrower than the historical PumpSwap graduated
registry.  It exposes only current-campaign, unexpired, exact PumpSwap evidence
that already reached MEMORY_OBSERVATION_ELIGIBLE.  It performs no source I/O,
selection, freeze, tracking claim, scoring, ranking, or admission.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Mapping

NETWORK = "solana-mainnet"
MOE_LAYER = "MEMORY_OBSERVATION_ELIGIBLE"
VISIBLE_STATES = frozenset({"CURRENT_VISIBLE", "CURRENT_POOL_CONFIRMED", "SAME_POOL_REOBSERVED"})
PUMPSWAP_VENUE = "pumpswap"


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _mapping_json(raw: object) -> dict[str, Any]:
    try:
        value = json.loads(str(raw or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(value) if isinstance(value, Mapping) else {}


def _source_name(provenance: Mapping[str, Any]) -> str | None:
    observations = provenance.get("observations")
    candidates: list[Mapping[str, Any]] = []
    if isinstance(observations, list):
        candidates.extend(item for item in observations if isinstance(item, Mapping))
    candidates.append(provenance)
    for item in reversed(candidates):
        source = str(item.get("source") or item.get("source_name") or "").strip().lower()
        if source in {"dexscreener", "geckoterminal"}:
            return source
    return None


def load_campaign_fresh_moe_candidates(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    at: str,
) -> list[dict[str, Any]]:
    """Return lawful fresh MOE carriers for one exact campaign, zero-source.

    Returned rows are candidate carriers only.  Callers must still apply the
    existing tracking precheck, freeze-depth requirement, selection authority,
    holder context and admission gates.
    """
    if not str(campaign_id or "").strip():
        return []
    instant = _parse_iso(at)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT r.mint_identity,r.pool_address,r.reserve_state,r.observed_at,
                  r.evidence_expires_at,r.source_provenance_json,r.evidence_json,
                  m.token_program_id,m.pool_program_id,m.base_mint,m.quote_mint,
                  m.venue,m.current_state,m.last_observed_at
           FROM printer_discovery_reserve_layers AS r
           JOIN printer_exact_market_states AS m
             ON m.network=r.network
            AND m.mint_identity=r.mint_identity
            AND m.pool_address=r.pool_address
           WHERE r.network=? AND r.reserve_layer=? AND r.last_campaign_id=?
           ORDER BY r.observed_at,r.mint_identity,r.pool_address""",
        (NETWORK, MOE_LAYER, str(campaign_id)),
    ).fetchall()
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        mint = str(row["mint_identity"] or "").strip()
        pool = str(row["pool_address"] or "").strip()
        if not mint or not pool or (mint, pool) in seen:
            continue
        if str(row["current_state"] or "") not in VISIBLE_STATES:
            continue
        venue = str(row["venue"] or "").strip().lower()
        if venue != PUMPSWAP_VENUE:
            continue
        token_program = str(row["token_program_id"] or "").strip()
        pool_program = str(row["pool_program_id"] or "").strip()
        if not token_program or not pool_program:
            continue
        if token_program.startswith(("UNRESOLVED_", "UNKNOWN_")) or pool_program.startswith(("UNRESOLVED_", "UNKNOWN_")):
            continue
        expiry_raw = row["evidence_expires_at"]
        if expiry_raw is None or not str(expiry_raw).strip():
            continue
        try:
            expiry = _parse_iso(str(expiry_raw))
        except ValueError:
            continue
        if expiry <= instant:
            continue
        provenance = _mapping_json(row["source_provenance_json"])
        evidence = _mapping_json(row["evidence_json"])
        source = _source_name(provenance)
        if source is None:
            continue
        liquidity = evidence.get("liquidity")
        liquidity_map = dict(liquidity) if isinstance(liquidity, Mapping) else {}
        liquidity_usd = liquidity_map.get("liquidity_usd", evidence.get("liquidity_usd"))
        observed_at = liquidity_map.get("liquidity_observed_at") or evidence.get("liquidity_observed_at")
        if liquidity_usd is None or observed_at is None:
            continue
        base_mint = str(row["base_mint"] or evidence.get("base_mint") or "").strip()
        quote_mint = str(row["quote_mint"] or evidence.get("quote_mint") or "").strip()
        if not base_mint or not quote_mint:
            continue
        candidate = {
            "mint": mint,
            "pool": pool,
            "pumpswap_pool": pool,
            "market_identity": f"{NETWORK}:{PUMPSWAP_VENUE}:{pool}",
            "provenance": source,
            "nomination_source": source,
            "admission_authority": "MARKET_PRESENT_POOL",
            "lineage_state": "UNKNOWN_ORIGIN",
            "exact_present_pool_confirmed": True,
            "present_pool_confirmed": True,
            "memory_observation_eligible": True,
            "token_program": token_program,
            "pool_program": pool_program,
            "base_mint": base_mint,
            "quote_mint": quote_mint,
            "venue_label": venue,
            "liquidity_usd": float(liquidity_usd),
            "liquidity_status": "LIQUIDITY_PROVEN",
            "liquidity_observed_at": str(observed_at),
            "evidence_expires_at": str(expiry_raw),
            "eligible": True,
            "rejection": None,
            "current_eligibility_status": "ELIGIBLE_FRESH",
            "source_path": "campaign_fresh_protocol_confirmed_moe_rehydration",
            "raw": {"reserve_evidence": evidence, "reserve_provenance": provenance},
        }
        result.append(candidate)
        seen.add((mint, pool))
    result.sort(key=lambda item: (str(item["mint"]), str(item["pool"])))
    return result
