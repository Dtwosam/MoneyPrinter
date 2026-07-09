"""Staged derivation of price_change_15m from two clean governed snapshots."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from datetime import datetime, timezone
from typing import Any

from printer_v1.snapshots.quality import parse_timestamp

DERIVATION_KIND_STAGED_SNAPSHOT_PRICE_CHANGE_15M = "STAGED_SNAPSHOT_PRICE_CHANGE_15M"

_INTERVAL_MIN = 720
_INTERVAL_MAX = 1080
_TARGET_INTERVAL = 900

_DISQUALIFYING_QUALITY_LABELS = frozenset({
    "DIRTY_SNAPSHOT",
    "STALE_SNAPSHOT",
    "MISSING_CRITICAL_FIELDS",
    "CONFLICTING_SNAPSHOT",
})


@dataclass(frozen=True)
class StagedDerivationResult:
    derived_price_change_15m: float
    provenance: dict


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def derive_price_change_15m(
    start_snapshot: Mapping[str, Any],
    end_snapshot: Mapping[str, Any],
) -> StagedDerivationResult | None:
    """
    Pure computation. No DB writes. No source calls. No memory/retrieval/paper paths.
    Returns StagedDerivationResult when eligible, None when rejected.
    """
    # Identity: same non-null token_id
    start_token = start_snapshot.get("token_id")
    end_token = end_snapshot.get("token_id")
    if start_token is None or end_token is None or start_token != end_token:
        return None

    # Identity: same non-null pair_id
    start_pair = start_snapshot.get("pair_id")
    end_pair = end_snapshot.get("pair_id")
    if start_pair is None or end_pair is None or start_pair != end_pair:
        return None

    # Identity: same source_name
    if start_snapshot.get("source_name") != end_snapshot.get("source_name"):
        return None

    # Quality: both source_status must be COMPLETE
    if start_snapshot.get("source_status") != "COMPLETE":
        return None
    if end_snapshot.get("source_status") != "COMPLETE":
        return None

    # Quality: both data_quality_label must be CLEAN_DATA
    if start_snapshot.get("data_quality_label") != "CLEAN_DATA":
        return None
    if end_snapshot.get("data_quality_label") != "CLEAN_DATA":
        return None

    # Reject disqualifying snapshot_quality_label; PARTIAL_SNAPSHOT is allowed
    if start_snapshot.get("snapshot_quality_label") in _DISQUALIFYING_QUALITY_LABELS:
        return None
    if end_snapshot.get("snapshot_quality_label") in _DISQUALIFYING_QUALITY_LABELS:
        return None

    # Price: both price_usd must be non-null; start must be > 0
    start_price_raw = start_snapshot.get("price_usd")
    end_price_raw = end_snapshot.get("price_usd")
    if start_price_raw is None or end_price_raw is None:
        return None
    try:
        start_price = float(start_price_raw)
        end_price = float(end_price_raw)
    except (ValueError, TypeError):
        return None
    if start_price <= 0:
        return None

    # Timestamps: both must be parseable; end must be strictly after start
    start_ts = parse_timestamp(start_snapshot.get("captured_at"))
    end_ts = parse_timestamp(end_snapshot.get("captured_at"))
    if start_ts is None or end_ts is None:
        return None
    if end_ts <= start_ts:
        return None

    # Interval must fall within [720, 1080] seconds inclusive
    interval = (end_ts - start_ts).total_seconds()
    if interval < _INTERVAL_MIN or interval > _INTERVAL_MAX:
        return None

    # Formula: percentage change, rounded to 6 decimal places
    derived = round(((end_price - start_price) / start_price) * 100, 6)

    provenance = {
        "derivation_kind": DERIVATION_KIND_STAGED_SNAPSHOT_PRICE_CHANGE_15M,
        "start_snapshot_id": start_snapshot.get("id"),
        "end_snapshot_id": end_snapshot.get("id"),
        "token_id": start_token,
        "pair_id": start_pair,
        "source_name": start_snapshot.get("source_name"),
        "start_captured_at": str(start_snapshot.get("captured_at")),
        "end_captured_at": str(end_snapshot.get("captured_at")),
        "interval_seconds": interval,
        "start_price_usd": start_price,
        "end_price_usd": end_price,
        "derived_price_change_15m": derived,
        "start_data_quality_label": start_snapshot.get("data_quality_label"),
        "end_data_quality_label": end_snapshot.get("data_quality_label"),
        "start_source_status": start_snapshot.get("source_status"),
        "end_source_status": end_snapshot.get("source_status"),
        "derived_at": _utc_now_iso(),
    }

    return StagedDerivationResult(derived_price_change_15m=derived, provenance=provenance)


def find_eligible_snapshot_pairs(
    db_conn: sqlite3.Connection,
    token_id: int,
    pair_id: int | None,
    source_name: str | None,
    end_snapshot: Mapping[str, Any],
    target_interval_seconds: int = _TARGET_INTERVAL,
    tolerance_seconds: int = 180,
) -> list[sqlite3.Row]:
    """
    Returns eligible start snapshot candidates ordered by closest interval to target.
    Tie-break: later captured_at (more recent start wins). Does not mutate DB.
    """
    end_ts = parse_timestamp(end_snapshot.get("captured_at"))
    if end_ts is None:
        return []

    min_interval = target_interval_seconds - tolerance_seconds  # 720
    max_interval = target_interval_seconds + tolerance_seconds  # 1080

    # Compute the acceptable captured_at range using timedelta (avoids SQLite date fn quirks)
    earliest_start = (end_ts - timedelta(seconds=max_interval)).isoformat()
    latest_start = (end_ts - timedelta(seconds=min_interval)).isoformat()

    params: list[Any] = [token_id, pair_id, earliest_start, latest_start]
    source_clause = ""
    if source_name is not None:
        source_clause = (
            "AND json_extract(normalized_snapshot_payload_json, '$.source_name') = ?"
        )
        params.append(source_name)

    rows = db_conn.execute(
        f"""
        SELECT *
        FROM printer_token_snapshots
        WHERE token_id = ?
          AND COALESCE(pair_id, -1) = COALESCE(?, -1)
          AND captured_at >= ?
          AND captured_at <= ?
          {source_clause}
          AND source_status = 'COMPLETE'
          AND data_quality_label = 'CLEAN_DATA'
        """,
        params,
    ).fetchall()

    # Sort Python-side: closest to target first; later captured_at wins ties
    def _sort_key(row: sqlite3.Row) -> tuple[float, float]:
        start_ts = parse_timestamp(row["captured_at"])
        if start_ts is None:
            return (float("inf"), 0.0)
        interval = (end_ts - start_ts).total_seconds()
        return (abs(interval - target_interval_seconds), -start_ts.timestamp())

    return sorted(rows, key=_sort_key)


def apply_staged_derivation(
    connection: sqlite3.Connection,
    snapshot_id: int,
    normalized: Mapping[str, Any],
) -> bool:
    """
    Post-insert hook called within the same DB connection/transaction as the INSERT.
    Tries to derive price_change_15m for the newly inserted snapshot.
    Updates only the end snapshot row if derivation succeeds.
    Does not create memory, retrieval, paper decision, or trading rows.
    Returns True if an update was applied, False otherwise.
    """
    token_id = normalized.get("token_id")
    pair_id = normalized.get("pair_id")
    source_name = normalized.get("source_name")

    if token_id is None or pair_id is None:
        return False

    end_snapshot: dict[str, Any] = dict(normalized)
    end_snapshot["id"] = snapshot_id

    candidates = find_eligible_snapshot_pairs(
        connection,
        token_id=int(token_id),
        pair_id=int(pair_id),
        source_name=source_name,
        end_snapshot=end_snapshot,
    )

    if not candidates:
        return False

    for candidate_row in candidates:
        start_snapshot: dict[str, Any] = dict(candidate_row)
        # source_name is not a DB column; extract from stored JSON payload
        raw_json = start_snapshot.get("normalized_snapshot_payload_json")
        if raw_json:
            try:
                start_payload = json.loads(raw_json)
                start_snapshot.setdefault("source_name", start_payload.get("source_name"))
            except (json.JSONDecodeError, TypeError):
                pass

        result = derive_price_change_15m(start_snapshot, end_snapshot)
        if result is None:
            continue

        # Load existing normalized_snapshot_payload_json and merge derivation keys
        existing_json_str = normalized.get("normalized_snapshot_payload_json")
        try:
            merged = json.loads(existing_json_str) if existing_json_str else {}
        except (json.JSONDecodeError, TypeError):
            merged = {}

        # Never overwrite a pre-existing native-source annotation
        if merged.get("price_change_15m_source_kind") == "NATIVE_SOURCE":
            return False

        merged["price_change_15m_source_kind"] = "DERIVED_STAGED_SNAPSHOT"
        merged["price_change_15m_provenance"] = result.provenance
        updated_json = json.dumps(merged, sort_keys=True)

        connection.execute(
            """
            UPDATE printer_token_snapshots
            SET price_change_15m = ?,
                normalized_snapshot_payload_json = ?
            WHERE id = ?
            """,
            (result.derived_price_change_15m, updated_json, snapshot_id),
        )
        return True

    return False
