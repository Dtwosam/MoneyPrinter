"""Exact WINDOW_1H safety-composite binding for the 1h→4h authority handoff.

This module is deliberately source-free. Provider collection and safety
composition remain owned by the Scheduler-led one-command factory orchestration.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Mapping


class FirstHourSafetyBindingError(ValueError):
    """Fail-closed first-hour safety binding contract fault."""


def attach_first_hour_safety_overlay(
    connection: sqlite3.Connection,
    *,
    step: Mapping[str, Any],
    memory_window_id: int,
    closing_snapshot_id: int,
    persisted_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one exact fresh safety composite to one exact WINDOW_1H memory.

    No safety state is inferred here. The referenced composite must already have
    been produced by the governed first-hour close context path against the exact
    closing snapshot. Existing supporting context and overlay keys are preserved.
    """

    safety = persisted_context.get("safety_composite")
    if not isinstance(safety, Mapping):
        raise FirstHourSafetyBindingError("FIRST_HOUR_SAFETY_COMPOSITE_MISSING")
    composite_id = safety.get("composite_id")
    if isinstance(composite_id, bool) or composite_id is None:
        raise FirstHourSafetyBindingError("FIRST_HOUR_SAFETY_COMPOSITE_ID_MISSING")
    try:
        composite_id = int(composite_id)
    except (TypeError, ValueError) as exc:
        raise FirstHourSafetyBindingError(
            "FIRST_HOUR_SAFETY_COMPOSITE_ID_INVALID"
        ) from exc

    window = connection.execute(
        """SELECT id,token_id,pair_id,window_kind,snapshot_end_id,
                  supporting_context_json
           FROM printer_memory_windows WHERE id=?""",
        (int(memory_window_id),),
    ).fetchone()
    if window is None:
        raise FirstHourSafetyBindingError("FIRST_HOUR_MEMORY_WINDOW_MISSING")
    if str(window["window_kind"]) != "WINDOW_1H":
        raise FirstHourSafetyBindingError("FIRST_HOUR_MEMORY_WINDOW_KIND_MISMATCH")

    step_token_id = int(step["token_id"])
    step_pair_id = int(step["pair_id"])
    if int(window["token_id"]) != step_token_id or int(window["pair_id"]) != step_pair_id:
        raise FirstHourSafetyBindingError("FIRST_HOUR_MEMORY_TARGET_MISMATCH")
    if window["snapshot_end_id"] is None or int(window["snapshot_end_id"]) != int(
        closing_snapshot_id
    ):
        raise FirstHourSafetyBindingError("FIRST_HOUR_MEMORY_CLOSE_SNAPSHOT_MISMATCH")

    composite = connection.execute(
        """SELECT id,token_id,pair_id,snapshot_id,token_mint,pair_address
           FROM printer_safety_evidence_composites WHERE id=?""",
        (composite_id,),
    ).fetchone()
    if composite is None:
        raise FirstHourSafetyBindingError("FIRST_HOUR_SAFETY_COMPOSITE_NOT_FOUND")
    if int(composite["token_id"]) != step_token_id or int(composite["pair_id"]) != step_pair_id:
        raise FirstHourSafetyBindingError("FIRST_HOUR_SAFETY_COMPOSITE_TARGET_MISMATCH")
    if int(composite["snapshot_id"]) != int(closing_snapshot_id):
        raise FirstHourSafetyBindingError("FIRST_HOUR_SAFETY_COMPOSITE_SNAPSHOT_MISMATCH")
    if str(composite["token_mint"]).lower() != str(step["token_mint"]).lower():
        raise FirstHourSafetyBindingError("FIRST_HOUR_SAFETY_COMPOSITE_MINT_MISMATCH")
    if str(composite["pair_address"]).lower() != str(step["pair_address"]).lower():
        raise FirstHourSafetyBindingError("FIRST_HOUR_SAFETY_COMPOSITE_PAIR_MISMATCH")

    try:
        supporting = json.loads(str(window["supporting_context_json"] or "{}"))
    except (TypeError, json.JSONDecodeError) as exc:
        raise FirstHourSafetyBindingError(
            "FIRST_HOUR_SUPPORTING_CONTEXT_MALFORMED"
        ) from exc
    if not isinstance(supporting, dict):
        raise FirstHourSafetyBindingError("FIRST_HOUR_SUPPORTING_CONTEXT_MALFORMED")

    raw_overlays = supporting.get("memory_build_evidence_overlays")
    if raw_overlays is None:
        overlays: dict[str, Any] = {}
    elif isinstance(raw_overlays, dict):
        overlays = dict(raw_overlays)
    else:
        raise FirstHourSafetyBindingError("FIRST_HOUR_SAFETY_OVERLAY_MALFORMED")

    existing = overlays.get("safety_composite_id")
    if existing is not None and int(existing) != composite_id:
        raise FirstHourSafetyBindingError("FIRST_HOUR_SAFETY_BINDING_CONFLICT")
    overlays["safety_composite_id"] = composite_id
    supporting["memory_build_evidence_overlays"] = overlays

    updated = connection.execute(
        """UPDATE printer_memory_windows
           SET supporting_context_json=?
           WHERE id=? AND token_id=? AND pair_id=? AND window_kind='WINDOW_1H'
             AND snapshot_end_id=?""",
        (
            json.dumps(supporting, sort_keys=True, default=str),
            int(memory_window_id),
            step_token_id,
            step_pair_id,
            int(closing_snapshot_id),
        ),
    )
    if int(updated.rowcount or 0) != 1:
        raise FirstHourSafetyBindingError("FIRST_HOUR_SAFETY_BINDING_UPDATE_FAILED")

    return {
        "bound": True,
        "memory_window_id": int(memory_window_id),
        "closing_snapshot_id": int(closing_snapshot_id),
        "safety_composite_id": composite_id,
        "token_id": step_token_id,
        "pair_id": step_pair_id,
    }
