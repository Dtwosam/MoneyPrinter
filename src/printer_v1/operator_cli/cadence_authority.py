"""Campaign-slot-bound cadence authority for Printer V1 operational windows.

Canonical authority graph (Design Lane 1):

    campaign window
    → exact campaign/run/cycle/token-slot identity
    → campaign token slot
    → exact token_slot.tracking_queue_id
    → printer_tracking_queue row
    → tracking_queue.tracking_lane

``printer_tokens.token_status`` is a compatibility projection only.
Snapshot / supporting_context ``tracking_lane`` values are corroborating
evidence only and must never self-authorize when queue authority is absent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Any, Mapping, Sequence

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.lifecycle.contracts import LifecycleEvent, TokenLifecycleState
from printer_v1.lifecycle.tracking_queue import claim_tracking_item


CADENCE_AUTHORITY_RESOLVED: str = "CADENCE_AUTHORITY_RESOLVED"
CADENCE_AUTHORITY_UNKNOWN: str = "CADENCE_AUTHORITY_UNKNOWN"
CADENCE_AUTHORITY_CONFLICT: str = "CADENCE_AUTHORITY_CONFLICT"

_VALID_CADENCE_LANES: frozenset[str] = frozenset({"TRACK_FAST", "TRACK_NORMAL"})


class CadenceAuthorityError(ValueError):
    """Fail-closed cadence authority / activation error."""


@dataclass(frozen=True)
class CadenceAuthorityResolution:
    status: str
    tracking_lane: str | None
    reason_code: str | None
    campaign_window_id: str | None = None
    token_slot_id: str | None = None
    tracking_queue_id: int | None = None
    token_row_id: int | None = None
    pair_row_id: int | None = None
    token_status: str | None = None
    corroborating_lanes: tuple[str, ...] = ()
    compatibility_projection_missing: bool = False


def _as_valid_lane(value: Any) -> str | None:
    text = str(value or "").strip()
    if text in _VALID_CADENCE_LANES:
        return text
    return None


def _parse_supporting_context_lane(raw: Any) -> str | None:
    if raw is None:
        return None
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, Mapping):
        return None
    return _as_valid_lane(payload.get("tracking_lane"))


def _snapshot_lanes(snapshots: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    lanes: list[str] = []
    seen: set[str] = set()
    for snap in snapshots:
        lane = _as_valid_lane(snap.get("tracking_lane"))
        if lane is not None and lane not in seen:
            seen.add(lane)
            lanes.append(lane)
    return tuple(lanes)


def resolve_campaign_slot_cadence_authority(
    connection: sqlite3.Connection,
    *,
    memory_window_row_id: int,
    snapshots: Sequence[Mapping[str, Any]] | None = None,
) -> CadenceAuthorityResolution:
    """Resolve cadence lane from exact campaign-slot tracking ownership.

    Missing canonical queue binding → UNKNOWN (never TRACK_FAST fallback).
    Conflicting truthful cadence evidence → CONFLICT.
    """
    window_id = int(memory_window_row_id)
    campaign_window = connection.execute(
        """
        SELECT window_id, campaign_id, run_id, cycle_id, token_slot_id,
               token_row_id, pair_row_id
        FROM printer_memory_factory_campaign_windows
        WHERE memory_window_row_id = ?
        LIMIT 1
        """,
        (window_id,),
    ).fetchone()
    if campaign_window is None:
        return CadenceAuthorityResolution(
            status=CADENCE_AUTHORITY_UNKNOWN,
            tracking_lane=None,
            reason_code="CAMPAIGN_WINDOW_BINDING_MISSING",
        )

    token_slot_id = str(campaign_window["token_slot_id"])
    slot = connection.execute(
        """
        SELECT token_slot_id, campaign_id, run_id, cycle_id, token_row_id,
               pair_row_id, tracking_queue_id, mint_identity, pair_identity
        FROM printer_memory_factory_campaign_token_slots
        WHERE token_slot_id = ?
          AND campaign_id = ?
          AND run_id = ?
          AND cycle_id = ?
        LIMIT 1
        """,
        (
            token_slot_id,
            str(campaign_window["campaign_id"]),
            str(campaign_window["run_id"]),
            str(campaign_window["cycle_id"]),
        ),
    ).fetchone()
    if slot is None:
        return CadenceAuthorityResolution(
            status=CADENCE_AUTHORITY_UNKNOWN,
            tracking_lane=None,
            reason_code="CAMPAIGN_TOKEN_SLOT_MISSING",
            campaign_window_id=str(campaign_window["window_id"]),
            token_slot_id=token_slot_id,
        )

    token_row_id = int(slot["token_row_id"])
    pair_row_id = int(slot["pair_row_id"])
    if (
        int(campaign_window["token_row_id"]) != token_row_id
        or int(campaign_window["pair_row_id"]) != pair_row_id
    ):
        return CadenceAuthorityResolution(
            status=CADENCE_AUTHORITY_CONFLICT,
            tracking_lane=None,
            reason_code="CAMPAIGN_WINDOW_SLOT_IDENTITY_MISMATCH",
            campaign_window_id=str(campaign_window["window_id"]),
            token_slot_id=token_slot_id,
            token_row_id=token_row_id,
            pair_row_id=pair_row_id,
        )

    queue_id_raw = slot["tracking_queue_id"]
    if queue_id_raw is None:
        return CadenceAuthorityResolution(
            status=CADENCE_AUTHORITY_UNKNOWN,
            tracking_lane=None,
            reason_code="TRACKING_QUEUE_BINDING_MISSING",
            campaign_window_id=str(campaign_window["window_id"]),
            token_slot_id=token_slot_id,
            token_row_id=token_row_id,
            pair_row_id=pair_row_id,
        )

    tracking_queue_id = int(queue_id_raw)
    queue = connection.execute(
        """
        SELECT id, token_id, pair_id, tracking_lane, queue_status
        FROM printer_tracking_queue
        WHERE id = ?
        LIMIT 1
        """,
        (tracking_queue_id,),
    ).fetchone()
    if queue is None:
        return CadenceAuthorityResolution(
            status=CADENCE_AUTHORITY_UNKNOWN,
            tracking_lane=None,
            reason_code="TRACKING_QUEUE_ROW_MISSING",
            campaign_window_id=str(campaign_window["window_id"]),
            token_slot_id=token_slot_id,
            tracking_queue_id=tracking_queue_id,
            token_row_id=token_row_id,
            pair_row_id=pair_row_id,
        )

    if int(queue["token_id"]) != token_row_id or (
        queue["pair_id"] is not None and int(queue["pair_id"]) != pair_row_id
    ):
        return CadenceAuthorityResolution(
            status=CADENCE_AUTHORITY_CONFLICT,
            tracking_lane=None,
            reason_code="TRACKING_QUEUE_IDENTITY_MISMATCH",
            campaign_window_id=str(campaign_window["window_id"]),
            token_slot_id=token_slot_id,
            tracking_queue_id=tracking_queue_id,
            token_row_id=token_row_id,
            pair_row_id=pair_row_id,
        )

    canonical_lane = _as_valid_lane(queue["tracking_lane"])
    if canonical_lane is None:
        return CadenceAuthorityResolution(
            status=CADENCE_AUTHORITY_UNKNOWN,
            tracking_lane=None,
            reason_code="TRACKING_QUEUE_LANE_INVALID",
            campaign_window_id=str(campaign_window["window_id"]),
            token_slot_id=token_slot_id,
            tracking_queue_id=tracking_queue_id,
            token_row_id=token_row_id,
            pair_row_id=pair_row_id,
        )

    token_status_row = connection.execute(
        "SELECT token_status FROM printer_tokens WHERE id = ? LIMIT 1",
        (token_row_id,),
    ).fetchone()
    token_status = (
        None
        if token_status_row is None or token_status_row[0] is None
        else str(token_status_row[0])
    )
    token_lane = _as_valid_lane(token_status)
    compatibility_missing = token_lane is None

    memory_window = connection.execute(
        "SELECT supporting_context_json FROM printer_memory_windows WHERE id = ?",
        (window_id,),
    ).fetchone()
    context_lane = _parse_supporting_context_lane(
        None if memory_window is None else memory_window[0]
    )
    snap_lanes = _snapshot_lanes(snapshots or ())
    corroborating = tuple(
        lane
        for lane in (context_lane, *snap_lanes)
        if lane is not None
    )
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique_corroborating: list[str] = []
    for lane in corroborating:
        if lane not in seen:
            seen.add(lane)
            unique_corroborating.append(lane)

    if token_lane is not None and token_lane != canonical_lane:
        return CadenceAuthorityResolution(
            status=CADENCE_AUTHORITY_CONFLICT,
            tracking_lane=None,
            reason_code="TOKEN_STATUS_CADENCE_CONFLICT",
            campaign_window_id=str(campaign_window["window_id"]),
            token_slot_id=token_slot_id,
            tracking_queue_id=tracking_queue_id,
            token_row_id=token_row_id,
            pair_row_id=pair_row_id,
            token_status=token_status,
            corroborating_lanes=tuple(unique_corroborating),
            compatibility_projection_missing=False,
        )

    conflicting_evidence = [
        lane for lane in unique_corroborating if lane != canonical_lane
    ]
    if conflicting_evidence:
        return CadenceAuthorityResolution(
            status=CADENCE_AUTHORITY_CONFLICT,
            tracking_lane=None,
            reason_code="CADENCE_EVIDENCE_CONFLICT",
            campaign_window_id=str(campaign_window["window_id"]),
            token_slot_id=token_slot_id,
            tracking_queue_id=tracking_queue_id,
            token_row_id=token_row_id,
            pair_row_id=pair_row_id,
            token_status=token_status,
            corroborating_lanes=tuple(unique_corroborating),
            compatibility_projection_missing=compatibility_missing,
        )

    return CadenceAuthorityResolution(
        status=CADENCE_AUTHORITY_RESOLVED,
        tracking_lane=canonical_lane,
        reason_code=None,
        campaign_window_id=str(campaign_window["window_id"]),
        token_slot_id=token_slot_id,
        tracking_queue_id=tracking_queue_id,
        token_row_id=token_row_id,
        pair_row_id=pair_row_id,
        token_status=token_status,
        corroborating_lanes=tuple(unique_corroborating),
        compatibility_projection_missing=compatibility_missing,
    )


def claim_tracking_authority_for_slot_insert(
    connection: sqlite3.Connection,
    *,
    token_row_id: int,
    pair_row_id: int,
    tracking_lane: str = "TRACK_NORMAL",
    now: datetime | None = None,
    priority_reason: str = "campaign_slot_tracking_activation",
) -> int:
    """Claim exact tracking authority for a campaign slot INSERT.

    ``printer_memory_factory_campaign_token_slots.tracking_queue_id`` is
    identity-immutable after insert (migration 032). Canonical Cycle-N
    activation must therefore claim the queue and project ``token_status``
    before ``create_cycle_with_two_slots`` / handoff INSERT binds the id.
    """
    lane = _as_valid_lane(tracking_lane)
    if lane is None:
        raise CadenceAuthorityError("TRACKING_LANE_INVALID")
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    else:
        instant = instant.astimezone(timezone.utc)
    timestamp = instant.isoformat()

    connection.execute(
        """
        UPDATE printer_tokens
        SET token_status = ?, updated_at = ?
        WHERE id = ?
        """,
        (lane, timestamp, int(token_row_id)),
    )
    created, queue_id = claim_tracking_item(
        connection,
        token_id=int(token_row_id),
        pair_id=int(pair_row_id),
        tracking_lane=TokenLifecycleState(lane),
        tracking_action=(
            LifecycleEvent.PROMOTE_TO_TRACK_FAST
            if lane == "TRACK_FAST"
            else LifecycleEvent.PROMOTE_TO_TRACK_NORMAL
        ),
        priority_reason=priority_reason,
        next_check_at=instant,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        assessed_at=instant,
    )
    if not created or queue_id is None:
        raise CadenceAuthorityError("TRACKING_QUEUE_CLAIM_FAILED")
    return int(queue_id)


def require_campaign_slot_tracking_authority(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    token_slot_id: str,
    tracking_lane: str | None = None,
    now: datetime | None = None,
) -> int:
    """Verify exact insert-time tracking authority for one campaign slot.

    Projects missing compatibility ``token_status`` when the bound queue lane is
    valid. Never attempts to UPDATE immutable ``tracking_queue_id``.
    """
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    else:
        instant = instant.astimezone(timezone.utc)
    timestamp = instant.isoformat()

    slot = connection.execute(
        """
        SELECT token_slot_id, token_row_id, pair_row_id, tracking_queue_id, token_state
        FROM printer_memory_factory_campaign_token_slots
        WHERE token_slot_id = ?
          AND campaign_id = ?
          AND run_id = ?
          AND cycle_id = ?
        LIMIT 1
        """,
        (token_slot_id, campaign_id, run_id, cycle_id),
    ).fetchone()
    if slot is None:
        raise CadenceAuthorityError("CAMPAIGN_TOKEN_SLOT_MISSING")
    if str(slot["token_state"]) not in {"SELECTED", "WINDOW_15M_ACTIVE"}:
        raise CadenceAuthorityError(
            f"CAMPAIGN_TOKEN_SLOT_STATE_FORBIDDEN:{slot['token_state']}"
        )
    if slot["tracking_queue_id"] is None:
        raise CadenceAuthorityError("TRACKING_QUEUE_BINDING_MISSING")

    token_row_id = int(slot["token_row_id"])
    pair_row_id = int(slot["pair_row_id"])
    tracking_queue_id = int(slot["tracking_queue_id"])
    queue = connection.execute(
        """
        SELECT id, token_id, pair_id, tracking_lane
        FROM printer_tracking_queue
        WHERE id = ?
        LIMIT 1
        """,
        (tracking_queue_id,),
    ).fetchone()
    if queue is None:
        raise CadenceAuthorityError("TRACKING_QUEUE_ROW_MISSING")
    if int(queue["token_id"]) != token_row_id or (
        queue["pair_id"] is not None and int(queue["pair_id"]) != pair_row_id
    ):
        raise CadenceAuthorityError("TRACKING_QUEUE_IDENTITY_MISMATCH")
    lane = _as_valid_lane(queue["tracking_lane"])
    if lane is None:
        raise CadenceAuthorityError("TRACKING_QUEUE_LANE_INVALID")
    if tracking_lane is not None and _as_valid_lane(tracking_lane) != lane:
        raise CadenceAuthorityError("TRACKING_LANE_MISMATCH")

    connection.execute(
        """
        UPDATE printer_tokens
        SET token_status = ?, updated_at = ?
        WHERE id = ?
          AND (token_status IS NULL OR token_status != ?)
        """,
        (lane, timestamp, token_row_id, lane),
    )
    return tracking_queue_id


def require_cycle_slot_tracking_authorities(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
    tracking_lane: str | None = None,
    now: datetime | None = None,
) -> tuple[int, ...]:
    """Require exact insert-time tracking authority for every cycle slot."""
    rows = connection.execute(
        """
        SELECT token_slot_id
        FROM printer_memory_factory_campaign_token_slots
        WHERE campaign_id = ?
          AND run_id = ?
          AND cycle_id = ?
        ORDER BY slot_ordinal ASC
        """,
        (campaign_id, run_id, cycle_id),
    ).fetchall()
    if len(rows) != 2:
        raise CadenceAuthorityError("CYCLE_SLOT_COUNT_INVALID")
    return tuple(
        require_campaign_slot_tracking_authority(
            connection,
            campaign_id=campaign_id,
            run_id=run_id,
            cycle_id=cycle_id,
            token_slot_id=str(
                row[0] if not isinstance(row, sqlite3.Row) else row["token_slot_id"]
            ),
            tracking_lane=tracking_lane,
            now=now,
        )
        for row in rows
    )
