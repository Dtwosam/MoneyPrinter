"""E2M Snapshot Persistence Boundary.

Converts a clean, governed DexScreener source response into exactly one
printer_token_snapshots row for the approved token.

Hard locks (permanent):
- No BUY/SELL/HOLD, paper decisions, positions, or PnL.
- No memory or memory_window creation.
- No retrieval activation.
- No wallet/private keys/live trading/real funds.
- No paid APIs, scoring, ranking, confidence, embeddings, or vectors.
- No generic search or broad discovery.
- No direct source calls.
- One token only. Source Governor boundary respected.
- Fail closed on missing, dirty, stale, failed, mismatched, or non-Solana evidence.
"""

from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


E2M_SOURCE_NAME: str = "dexscreener"
# V2-9.5: the exact-pair snapshot may be served by the DexScreener primary or
# the governed GeckoTerminal fallback. Both are free/public Solana sources and
# both produce the identical normalized exact-pair contract. Any other source
# remains blocked. E.30 adds a distinct governed GeckoTerminal readiness kind.
E2M_ALLOWED_SOURCE_NAMES: frozenset[str] = frozenset({"dexscreener", "geckoterminal"})
E2M_REQUEST_KIND: str = "pair_market_snapshot"
E2M_ALLOWED_REQUEST_KINDS: frozenset[str] = frozenset({
    E2M_REQUEST_KIND,
    "geckoterminal_readiness_base_snapshot",
})
E2M_REQUIRED_SOURCE_STATUS: str = "COMPLETE"
E2M_REQUIRED_QUALITY: str = "CLEAN_DATA"
E2M_REQUIRED_CHAIN: str = "solana"
E2M_TRACKING_LANE: str = "TRACK_FAST"
E2M_SNAPSHOT_MODE: str = "FIRST_15M_CYCLE"
E2M_STATUS_PERSISTED: str = "E2M_SNAPSHOT_PERSISTED"
E2M_STATUS_DUPLICATE: str = "E2M_SNAPSHOT_DUPLICATE"
E2M_STATUS_BLOCKED: str = "E2M_SNAPSHOT_BLOCKED"

_HARD_LOCKS: dict[str, bool] = {
    "no_buy_sell_hold": True,
    "no_paper_decisions": True,
    "no_positions": True,
    "no_pnl": True,
    "no_memory_creation": True,
    "no_memory_window_creation": True,
    "no_retrieval_activation": True,
    "no_live_trading": True,
    "no_paid_api": True,
    "no_generic_search": True,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _select_primary_pair(
    pairs: list[dict[str, Any]],
    approved_mint: str,
    expected_pair_address: str | None = None,
) -> dict[str, Any] | None:
    """Pick the primary pair deterministically.

    Filters for chain=solana, token_mint matches approved_mint, pair_address
    present. Sorts by liquidity_usd DESC then pair_address ASC for determinism.
    Returns the first qualifying pair or None.
    """
    candidates = [
        p for p in pairs
        if (
            p.get("chain") == E2M_REQUIRED_CHAIN
            and p.get("token_mint", "").lower() == approved_mint.lower()
            and p.get("pair_address")
            and (
                expected_pair_address is None
                or str(p.get("pair_address", "")).lower()
                == expected_pair_address.lower()
            )
        )
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda p: (-(p.get("liquidity_usd") or 0.0), p.get("pair_address") or "")
    )
    return candidates[0]


_INACTIVITY_FIELDS = (
    "volume_5m", "volume_15m", "txns_5m", "txns_15m",
    "price_change_5m", "price_change_15m",
)


def _finite_number(value: Any, *, positive: bool = False) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    numeric = float(value)
    return math.isfinite(numeric) and (numeric > 0.0 if positive else numeric >= 0.0)


def _normalize_verified_inactivity(pair_data: dict[str, Any]) -> dict[str, Any]:
    """Fill absent short-window activity only from positive inactivity evidence."""
    normalized = dict(pair_data)
    predicate = (
        _finite_number(pair_data.get("price_usd"), positive=True)
        and _finite_number(pair_data.get("liquidity_usd"), positive=True)
        and _finite_number(pair_data.get("volume_1h"))
        and _finite_number(pair_data.get("txns_1h"))
        and float(pair_data["volume_1h"]) == 0.0
        and float(pair_data["txns_1h"]) == 0.0
    )
    converted = [
        field_name for field_name in _INACTIVITY_FIELDS
        if predicate and pair_data.get(field_name) is None
    ]
    for field_name in converted:
        normalized[field_name] = 0
    if converted:
        normalized["snapshot_inactivity_evidence"] = {
            "label": "SNAPSHOT_VERIFIED_INACTIVE",
            "converted_fields": converted,
            "predicate": {
                "exact_pair_and_target_validated": True,
                "source_complete_clean": True,
                "price_and_liquidity_positive": True,
                "wider_activity_present_and_inactive": True,
            },
        }
    return normalized


def _upsert_token(
    connection: sqlite3.Connection,
    token_mint: str,
    symbol: str | None,
    name: str | None,
    now: str,
) -> int:
    """Upsert printer_tokens row. Returns token_id."""
    row = connection.execute(
        "SELECT id FROM printer_tokens WHERE token_mint = ?", (token_mint,)
    ).fetchone()
    if row:
        connection.execute(
            "UPDATE printer_tokens SET last_seen_at = ?, updated_at = ? WHERE id = ?",
            (now, now, int(row["id"])),
        )
        return int(row["id"])
    cursor = connection.execute(
        "INSERT INTO printer_tokens"
        " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
        "  token_status, created_at, updated_at)"
        " VALUES (?, 'solana', ?, ?, ?, ?, 'TRACKING', ?, ?)",
        (token_mint, symbol, name, now, now, now, now),
    )
    return int(cursor.lastrowid)


def _upsert_pair(
    connection: sqlite3.Connection,
    token_id: int,
    pair_address: str,
    now: str,
) -> int:
    """Upsert printer_pairs row. Returns pair_id."""
    row = connection.execute(
        "SELECT id FROM printer_pairs WHERE pair_address = ?", (pair_address,)
    ).fetchone()
    if row:
        connection.execute(
            "UPDATE printer_pairs SET last_seen_at = ?, updated_at = ? WHERE id = ?",
            (now, now, int(row["id"])),
        )
        return int(row["id"])
    cursor = connection.execute(
        "INSERT INTO printer_pairs"
        " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
        "  created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (token_id, pair_address, pair_address, now, now, now, now),
    )
    return int(cursor.lastrowid)


def _find_existing_snapshot(
    connection: sqlite3.Connection,
    token_id: int,
    pair_id: int,
    source_response_id: int,
) -> int | None:
    """Return existing snapshot id if already created from this source_response."""
    row = connection.execute(
        "SELECT id FROM printer_token_snapshots"
        " WHERE token_id = ?"
        "   AND COALESCE(pair_id, -1) = COALESCE(?, -1)"
        "   AND json_extract(normalized_snapshot_payload_json, '$.source_response_id') = ?"
        " LIMIT 1",
        (token_id, pair_id, source_response_id),
    ).fetchone()
    return int(row["id"]) if row else None


def _insert_snapshot(
    connection: sqlite3.Connection,
    token_id: int,
    pair_id: int,
    pair_data: dict[str, Any],
    source_request_id: int,
    source_response_id: int,
    captured_at: str,
    now: str,
    tracking_lane: str,
    source_name: str = E2M_SOURCE_NAME,
) -> int:
    """Insert one printer_token_snapshots row. Returns snapshot_id."""
    readiness_provenance_fields = {
        key: pair_data.get(key)
        for key in (
            "price_change_15m_source_kind", "price_change_15m_provenance",
            "volume_15m_source_kind", "volume_15m_provenance",
            "txns_15m_source_kind", "txns_15m_completeness",
            "txns_15m_provenance",
            "unique_wallets_15m",
            "buys_15m",
            "sells_15m",
            "buy_volume_15m",
            "sell_volume_15m",
            "wallet_identity_semantics_15m",
            "wallet_flow_provenance_15m",
        )
    }
    normalized_json = json.dumps(
        {
            "source_name": source_name,
            "request_kind": E2M_REQUEST_KIND,
            "source_request_id": source_request_id,
            "source_response_id": source_response_id,
            "chain": E2M_REQUIRED_CHAIN,
            "pair_address": pair_data.get("pair_address"),
            "token_mint": pair_data.get("token_mint"),
            "buys_5m": pair_data.get("buys_5m"),
            "sells_5m": pair_data.get("sells_5m"),
            "buys_1h": pair_data.get("buys_1h"),
            "sells_1h": pair_data.get("sells_1h"),
            "buys_24h": pair_data.get("buys_24h"),
            "sells_24h": pair_data.get("sells_24h"),
            "snapshot_inactivity_evidence": pair_data.get(
                "snapshot_inactivity_evidence"
            ),
            "snapshot_readiness_contract": pair_data.get(
                "snapshot_readiness_contract"
            ),
            **readiness_provenance_fields,
        },
        sort_keys=True,
    )
    cursor = connection.execute(
        """
        INSERT INTO printer_token_snapshots (
            token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
            price_usd, price_native, liquidity_usd,
            volume_5m, volume_15m, volume_1h, volume_4h, volume_12h, volume_24h,
            txns_5m, txns_15m, txns_1h, txns_4h, txns_12h, txns_24h,
            fdv, market_cap,
            price_change_5m, price_change_15m, price_change_1h,
            price_change_4h, price_change_12h, price_change_24h,
            source_status, data_quality_label,
            normalized_snapshot_payload_json, created_at
        ) VALUES (
            ?, ?, ?, ?, ?,
            ?, NULL, ?,
            ?, ?, ?, NULL, NULL, ?,
            ?, ?, ?, NULL, NULL, ?,
            ?, ?,
            ?, ?, ?,
            NULL, NULL, ?,
            'COMPLETE', 'CLEAN_DATA',
            ?, ?
        )
        """,
        (
            token_id,
            pair_id,
            captured_at,
            tracking_lane,
            E2M_SNAPSHOT_MODE,
            pair_data.get("price_usd"),
            pair_data.get("liquidity_usd"),
            pair_data.get("volume_5m"),
            pair_data.get("volume_15m"),
            pair_data.get("volume_1h"),
            pair_data.get("volume_24h"),
            pair_data.get("txns_5m"),
            pair_data.get("txns_15m"),
            pair_data.get("txns_1h"),
            pair_data.get("txns_24h"),
            pair_data.get("fdv"),
            pair_data.get("market_cap"),
            pair_data.get("price_change_5m"),
            pair_data.get("price_change_15m"),
            pair_data.get("price_change_1h"),
            pair_data.get("price_change_24h"),
            normalized_json,
            now,
        ),
    )
    return int(cursor.lastrowid)


def _load_source_response_row(
    connection: sqlite3.Connection,
    source_response_id: int,
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM printer_source_responses WHERE id = ?",
        (source_response_id,),
    ).fetchone()


def _load_source_request_row(
    connection: sqlite3.Connection,
    source_request_id: int,
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM printer_source_requests WHERE id = ?",
        (source_request_id,),
    ).fetchone()


def persist_snapshot_from_source_response(
    connection: sqlite3.Connection,
    source_response_id: int,
    approved_mint: str,
    *,
    expected_pair_address: str | None = None,
    tracking_lane: str = E2M_TRACKING_LANE,
    supplemental_15m_evidence: dict[str, Any] | None = None,
    require_readiness_contract: bool = False,
    evaluated_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Persist exactly one token snapshot from a clean governed DexScreener response.

    Validates source_name, request_kind, source_status, data_quality_label,
    chain, and token_mint before writing. Idempotent: a second call with the
    same source_response_id returns E2M_SNAPSHOT_DUPLICATE.

    Returns an audit dict. Does NOT commit — caller is responsible.
    """
    blocked_reasons: list[str] = []

    resp_row = _load_source_response_row(connection, source_response_id)
    if resp_row is None:
        return {
            "e2m_status": E2M_STATUS_BLOCKED,
            "persisted": False,
            "blocked_reasons": [f"source_response_id {source_response_id} not found"],
            "approved_mint": approved_mint,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memory_created": 0,
            "memory_windows_created": 0,
        }

    if resp_row["source_name"] not in E2M_ALLOWED_SOURCE_NAMES:
        blocked_reasons.append(
            f"source_name must be one of {sorted(E2M_ALLOWED_SOURCE_NAMES)!r};"
            f" got {resp_row['source_name']!r}"
        )
    if resp_row["source_status"] != E2M_REQUIRED_SOURCE_STATUS:
        blocked_reasons.append(
            f"source_status must be {E2M_REQUIRED_SOURCE_STATUS!r};"
            f" got {resp_row['source_status']!r}"
        )
    if resp_row["data_quality_label"] != E2M_REQUIRED_QUALITY:
        blocked_reasons.append(
            f"data_quality_label must be {E2M_REQUIRED_QUALITY!r};"
            f" got {resp_row['data_quality_label']!r}"
        )

    req_row = _load_source_request_row(connection, int(resp_row["source_request_id"]))
    if req_row is None:
        blocked_reasons.append(
            f"source_request_id {resp_row['source_request_id']} not found"
        )
    elif req_row["request_kind"] not in E2M_ALLOWED_REQUEST_KINDS:
        blocked_reasons.append(
            f"request_kind must be one of {sorted(E2M_ALLOWED_REQUEST_KINDS)!r};"
            f" got {req_row['request_kind']!r}"
        )

    if blocked_reasons:
        return {
            "e2m_status": E2M_STATUS_BLOCKED,
            "persisted": False,
            "blocked_reasons": blocked_reasons,
            "approved_mint": approved_mint,
            "source_response_id": source_response_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memory_created": 0,
            "memory_windows_created": 0,
        }

    raw_json = resp_row["normalized_payload_json"] or ""
    try:
        payload = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return {
            "e2m_status": E2M_STATUS_BLOCKED,
            "persisted": False,
            "blocked_reasons": ["normalized_payload_json is not valid JSON"],
            "approved_mint": approved_mint,
            "source_response_id": source_response_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memory_created": 0,
            "memory_windows_created": 0,
        }

    pairs = payload.get("pairs") if isinstance(payload, dict) else None
    if not isinstance(pairs, list) or not pairs:
        return {
            "e2m_status": E2M_STATUS_BLOCKED,
            "persisted": False,
            "blocked_reasons": ["normalized_payload_json missing 'pairs' list"],
            "approved_mint": approved_mint,
            "source_response_id": source_response_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memory_created": 0,
            "memory_windows_created": 0,
        }

    if tracking_lane not in {"TRACK_FAST", "TRACK_NORMAL"}:
        return {
            "e2m_status": E2M_STATUS_BLOCKED,
            "persisted": False,
            "blocked_reasons": [f"unsupported tracking_lane: {tracking_lane!r}"],
            "approved_mint": approved_mint,
            "source_response_id": source_response_id,
            "hard_locks": dict(_HARD_LOCKS),
        }

    primary_pair = _select_primary_pair(
        pairs, approved_mint, expected_pair_address
    )
    if primary_pair is None:
        return {
            "e2m_status": E2M_STATUS_BLOCKED,
            "persisted": False,
            "blocked_reasons": [
                f"no Solana pair found for approved_mint={approved_mint!r}"
                + (
                    f" and expected_pair_address={expected_pair_address!r}"
                    if expected_pair_address is not None else ""
                )
            ],
            "approved_mint": approved_mint,
            "source_response_id": source_response_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memory_created": 0,
            "memory_windows_created": 0,
        }

    if require_readiness_contract and str(resp_row["source_name"]) != "geckoterminal":
        return {
            "e2m_status": E2M_STATUS_BLOCKED,
            "persisted": False,
            "blocked_reasons": ["readiness primary source must be geckoterminal"],
            "approved_mint": approved_mint,
            "source_response_id": source_response_id,
            "hard_locks": dict(_HARD_LOCKS),
        }

    if require_readiness_contract and expected_pair_address is None:
        return {
            "e2m_status": E2M_STATUS_BLOCKED,
            "persisted": False,
            "blocked_reasons": ["readiness contract requires exact pair identity"],
            "approved_mint": approved_mint,
            "source_response_id": source_response_id,
            "hard_locks": dict(_HARD_LOCKS),
        }

    if require_readiness_contract:
        from printer_v1.operator_cli.snapshot_readiness_contract import (
            READINESS_PRIMARY_TTL_SECONDS,
            merge_exact_15m_evidence,
            snapshot_readiness_blockers,
        )

        primary_pair, merge_blockers = merge_exact_15m_evidence(
            primary_pair,
            supplemental_15m_evidence,
            expected_mint=approved_mint,
            expected_pair=str(expected_pair_address),
        )
        if not merge_blockers and supplemental_15m_evidence:
            lineage_kinds = {
                "price_change_15m_provenance": "geckoterminal_ohlcv_15m",
                "volume_15m_provenance": "geckoterminal_ohlcv_15m",
                "txns_15m_provenance": "geckoterminal_pool_trades_15m",
            }
            for field, request_kind in lineage_kinds.items():
                provenance = primary_pair.get(field)
                if not isinstance(provenance, dict):
                    continue
                request_id = provenance.get("source_request_id")
                response_id = provenance.get("source_response_id")
                lineage = connection.execute(
                    """SELECT 1 FROM printer_source_responses AS response
                       JOIN printer_source_requests AS request
                         ON request.id=response.source_request_id
                       WHERE response.id=? AND request.id=?
                         AND response.source_name='geckoterminal'
                         AND request.source_name='geckoterminal'
                         AND request.request_kind=?
                         AND response.source_status='COMPLETE'
                         AND response.data_quality_label='CLEAN_DATA'""",
                    (response_id, request_id, request_kind),
                ).fetchone()
                if lineage is None:
                    merge_blockers.append(
                        f"READINESS_15M_PROVENANCE:{field}:lineage_missing"
                    )
        if merge_blockers:
            return {
                "e2m_status": E2M_STATUS_BLOCKED,
                "persisted": False,
                "blocked_reasons": sorted(set(merge_blockers)),
                "approved_mint": approved_mint,
                "source_response_id": source_response_id,
                "hard_locks": dict(_HARD_LOCKS),
            }

    primary_pair = _normalize_verified_inactivity(primary_pair)

    if require_readiness_contract:
        check_time = evaluated_at or datetime.now(timezone.utc)
        try:
            received = datetime.fromisoformat(
                str(resp_row["received_at"]).replace("Z", "+00:00")
            )
            if received.tzinfo is None:
                received = received.replace(tzinfo=timezone.utc)
            current = (
                check_time if isinstance(check_time, datetime)
                else datetime.fromisoformat(str(check_time).replace("Z", "+00:00"))
            )
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            primary_age = (
                current.astimezone(timezone.utc) - received.astimezone(timezone.utc)
            ).total_seconds()
        except (TypeError, ValueError):
            primary_age = float("inf")
        readiness_blockers = snapshot_readiness_blockers(
            primary_pair,
            expected_mint=approved_mint,
            expected_pair=str(expected_pair_address),
            evaluated_at=check_time,
        )
        if not -5 <= primary_age <= READINESS_PRIMARY_TTL_SECONDS:
            readiness_blockers.append("READINESS_PRIMARY_STALE")
        if readiness_blockers:
            return {
                "e2m_status": E2M_STATUS_BLOCKED,
                "persisted": False,
                "blocked_reasons": sorted(set(readiness_blockers)),
                "approved_mint": approved_mint,
                "source_response_id": source_response_id,
                "hard_locks": dict(_HARD_LOCKS),
            }
        primary_pair["snapshot_readiness_contract"] = {
            "label": "SNAPSHOT_READINESS_COMPLETE",
            "primary_source": str(resp_row["source_name"]),
            "primary_source_request_id": int(req_row["id"]),
            "primary_source_response_id": source_response_id,
            "exact_mint_and_pair": True,
            "required_fields_complete": True,
            "operation_reservation": 6,
        }

    now = _utc_now()
    captured_at = str(resp_row["received_at"] or now)
    source_request_id = int(req_row["id"])  # type: ignore[index]

    token_mint = str(primary_pair["token_mint"])
    symbol = primary_pair.get("symbol")
    name = primary_pair.get("name")
    pair_address = str(primary_pair["pair_address"])

    token_id = _upsert_token(connection, token_mint, symbol, name, now)
    pair_id = _upsert_pair(connection, token_id, pair_address, now)

    existing_id = _find_existing_snapshot(
        connection, token_id, pair_id, source_response_id
    )
    if existing_id is not None:
        return {
            "e2m_status": E2M_STATUS_DUPLICATE,
            "persisted": False,
            "duplicate": True,
            "existing_snapshot_id": existing_id,
            "token_id": token_id,
            "pair_id": pair_id,
            "approved_mint": approved_mint,
            "source_request_id": source_request_id,
            "source_response_id": source_response_id,
            "hard_locks": dict(_HARD_LOCKS),
            "paper_decisions_created": 0,
            "positions_created": 0,
            "pnl_created": 0,
            "memory_created": 0,
            "memory_windows_created": 0,
        }

    snapshot_id = _insert_snapshot(
        connection,
        token_id,
        pair_id,
        primary_pair,
        source_request_id,
        source_response_id,
        captured_at,
        now,
        tracking_lane,
        source_name=str(resp_row["source_name"]),
    )

    return {
        "e2m_status": E2M_STATUS_PERSISTED,
        "persisted": True,
        "snapshot_id": snapshot_id,
        "token_id": token_id,
        "pair_id": pair_id,
        "approved_mint": approved_mint,
        "token_mint_persisted": token_mint,
        "pair_address_persisted": pair_address,
        "source_name_persisted": str(resp_row["source_name"]),
        "source_request_id": source_request_id,
        "source_response_id": source_response_id,
        "captured_at": captured_at,
        "hard_locks": dict(_HARD_LOCKS),
        "paper_decisions_created": 0,
        "positions_created": 0,
        "pnl_created": 0,
        "memory_created": 0,
        "memory_windows_created": 0,
    }
