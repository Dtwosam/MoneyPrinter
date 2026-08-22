"""Truthful clean-dispatch deadline projection for Scheduler-owned evidence.

This owner derives deadlines from exact ACTUAL captured snapshots.  It never
enqueues, claims, executes, fetches, persists memory quality, or replaces the
Lane-1 cadence evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import sqlite3

from printer_v1.operator_cli.cadence_authority import (
    CADENCE_AUTHORITY_RESOLVED,
    resolve_campaign_slot_cadence_authority,
)
from printer_v1.snapshots.cadence_policy import get_policy


class EvidenceDeadlineStatus(StrEnum):
    RESOLVED = "RESOLVED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class EvidenceDeadlineProjection:
    status: EvidenceDeadlineStatus
    last_actual_snapshot_captured_at: datetime | None
    deadline_at: datetime | None
    block_boundary_at: datetime | None
    reason_code: str | None


_FORCED_CLOSE_STEP_KINDS = frozenset(
    {
        "WINDOW_CLOSE",
        "CONTINUATION_CLOSE",
        "LONG_CONTINUATION_CLOSE",
        "WINDOW_CLOSE_EVIDENCE",
        "CONTINUATION_CLOSE_EVIDENCE",
        "LONG_CONTINUATION_CLOSE_EVIDENCE",
    }
)


def _utc(value: datetime | str) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _unknown(
    reason_code: str,
    *,
    last_actual: datetime | None = None,
) -> EvidenceDeadlineProjection:
    return EvidenceDeadlineProjection(
        status=EvidenceDeadlineStatus.UNKNOWN,
        last_actual_snapshot_captured_at=last_actual,
        deadline_at=None,
        block_boundary_at=None,
        reason_code=reason_code,
    )


def project_last_actual_capture_deadline(
    *,
    last_actual_snapshot_captured_at: datetime | str | None,
    window_kind: str,
    tracking_lane: str | None,
    forced_close: bool = False,
    window_end_at: datetime | str | None = None,
) -> EvidenceDeadlineProjection:
    """Project distinct dirty and block boundaries from one actual capture."""
    if last_actual_snapshot_captured_at is None:
        return _unknown("MISSING_PRIOR_ACTUAL_CAPTURE")
    try:
        actual = _utc(last_actual_snapshot_captured_at)
    except (TypeError, ValueError):
        return _unknown("INVALID_PRIOR_ACTUAL_CAPTURE")

    policy = get_policy(str(window_kind), tracking_lane)
    if policy is None:
        return _unknown("CADENCE_POLICY_UNKNOWN", last_actual=actual)

    dirty_deadline = actual + timedelta(seconds=policy.dirty_above_gap_seconds)
    block_boundary = actual + timedelta(
        seconds=policy.max_clean_snapshot_gap_seconds
    )
    deadline = dirty_deadline
    if forced_close:
        if window_end_at is None:
            return _unknown("WINDOW_END_AT_UNKNOWN", last_actual=actual)
        try:
            closing_deadline = _utc(window_end_at) + timedelta(
                seconds=policy.closing_clean_late_seconds
            )
        except (TypeError, ValueError):
            return _unknown("WINDOW_END_AT_INVALID", last_actual=actual)
        deadline = min(dirty_deadline, closing_deadline)

    return EvidenceDeadlineProjection(
        status=EvidenceDeadlineStatus.RESOLVED,
        last_actual_snapshot_captured_at=actual,
        deadline_at=deadline,
        block_boundary_at=block_boundary,
        reason_code=None,
    )


def project_scheduler_job_evidence_deadline(
    connection: sqlite3.Connection,
    *,
    factory_run_id: str,
    scheduler_job_id: int,
) -> EvidenceDeadlineProjection:
    """Resolve and project from the prior exact Scheduler-owned ACTUAL capture.

    The current job must have one exact V2 WINDOW_LIFECYCLE owner.  Candidate
    prior captures must share the exact campaign window, campaign/run/cycle/
    token-slot/factory-run, canonical Lane-1 cadence authority, token/pair, and
    precede the current Scheduler plan position. A token snapshot without that
    complete linkage is never used as a substitute.
    """
    current_rows = connection.execute(
        """SELECT s.id AS step_id,s.run_id AS factory_run_id,s.step_kind,
                  s.token_id,s.pair_id,s.tracking_lane,
                  j.id AS scheduler_job_id,j.scheduled_for,
                  sw.campaign_id,sw.run_id AS campaign_run_id,sw.cycle_id,
                  sw.token_slot_id,sw.window_id,w.window_kind,
                  slot.token_row_id AS slot_token_id,
                  slot.pair_row_id AS slot_pair_id
           FROM printer_memory_factory_run_steps AS s
           JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
           JOIN printer_memory_factory_campaign_scheduler_work AS sw
             ON sw.scheduler_job_id=j.id
           JOIN printer_memory_factory_campaign_windows AS w
             ON w.window_id=sw.window_id
            AND w.campaign_id=sw.campaign_id
            AND w.run_id=sw.run_id
            AND w.cycle_id=sw.cycle_id
            AND w.token_slot_id=sw.token_slot_id
           JOIN printer_memory_factory_campaign_token_slots AS slot
             ON slot.token_slot_id=sw.token_slot_id
            AND slot.campaign_id=sw.campaign_id
            AND slot.run_id=sw.run_id
            AND slot.cycle_id=sw.cycle_id
           WHERE s.run_id=? AND j.id=?
             AND sw.ownership_contract_version='V2_STAGE_SCOPED'
             AND sw.work_scope='WINDOW_LIFECYCLE'
             AND sw.target_category='CAMPAIGN_WINDOW'
             AND sw.target_identity=sw.window_id
             AND sw.factory_run_id=s.run_id
             AND sw.stage_id=w.window_kind""",
        (str(factory_run_id), int(scheduler_job_id)),
    ).fetchall()
    if not current_rows:
        return _unknown("EXACT_SCHEDULER_WORK_OWNER_MISSING")
    if len(current_rows) != 1:
        return _unknown("EXACT_SCHEDULER_WORK_OWNER_AMBIGUOUS")
    current = current_rows[0]
    if (
        current["token_id"] is None
        or current["pair_id"] is None
        or int(current["token_id"]) != int(current["slot_token_id"])
        or int(current["pair_id"]) != int(current["slot_pair_id"])
    ):
        return _unknown("EXACT_SCHEDULER_WORK_IDENTITY_MISMATCH")

    cadence_authority = resolve_campaign_slot_cadence_authority(
        connection,
        campaign_window_id=str(current["window_id"]),
        campaign_id=str(current["campaign_id"]),
        campaign_run_id=str(current["campaign_run_id"]),
        cycle_id=str(current["cycle_id"]),
        token_slot_id=str(current["token_slot_id"]),
    )
    if (
        cadence_authority.status != CADENCE_AUTHORITY_RESOLVED
        or cadence_authority.tracking_lane is None
        or cadence_authority.tracking_queue_id is None
    ):
        return _unknown(
            cadence_authority.reason_code or "CADENCE_AUTHORITY_UNKNOWN"
        )
    canonical_tracking_lane = str(cadence_authority.tracking_lane)
    carrier_tracking_lane = str(current["tracking_lane"] or "").strip()
    if (
        carrier_tracking_lane in {"TRACK_FAST", "TRACK_NORMAL"}
        and carrier_tracking_lane != canonical_tracking_lane
    ):
        return _unknown("CADENCE_EVIDENCE_CONFLICT")

    try:
        current_scheduled_for = _utc(str(current["scheduled_for"]))
    except (TypeError, ValueError):
        return _unknown("CURRENT_SCHEDULED_FOR_INVALID")

    prior_rows = connection.execute(
        """SELECT ps.id AS step_id,pj.id AS scheduler_job_id,
                  pj.scheduled_for,ts.id AS snapshot_id,ts.captured_at,
                  ts.token_id,ts.pair_id,ts.tracking_lane
           FROM printer_memory_factory_run_steps AS ps
           JOIN printer_scheduler_jobs AS pj ON pj.id=ps.scheduler_job_id
           JOIN printer_token_snapshots AS ts ON ts.id=ps.snapshot_id
           JOIN printer_memory_factory_campaign_scheduler_work AS psw
             ON psw.scheduler_job_id=pj.id
           JOIN printer_memory_factory_campaign_windows AS pw
             ON pw.window_id=psw.window_id
            AND pw.campaign_id=psw.campaign_id
            AND pw.run_id=psw.run_id
            AND pw.cycle_id=psw.cycle_id
            AND pw.token_slot_id=psw.token_slot_id
           JOIN printer_memory_factory_campaign_token_slots AS pslot
             ON pslot.token_slot_id=psw.token_slot_id
            AND pslot.campaign_id=psw.campaign_id
            AND pslot.run_id=psw.run_id
            AND pslot.cycle_id=psw.cycle_id
           WHERE ps.run_id=? AND ps.snapshot_id IS NOT NULL
             AND ps.token_id=? AND ps.pair_id=? AND ps.tracking_lane=?
             AND ts.token_id=ps.token_id AND ts.pair_id=ps.pair_id
             AND ts.tracking_lane=ps.tracking_lane
             AND psw.campaign_id=? AND psw.run_id=? AND psw.cycle_id=?
             AND psw.token_slot_id=? AND psw.window_id=?
             AND psw.factory_run_id=ps.run_id
             AND pw.token_row_id=? AND pw.pair_row_id=?
             AND pslot.token_row_id=? AND pslot.pair_row_id=?
             AND pslot.tracking_queue_id=?
             AND psw.ownership_contract_version='V2_STAGE_SCOPED'
             AND psw.work_scope='WINDOW_LIFECYCLE'
             AND psw.target_category='CAMPAIGN_WINDOW'
             AND psw.target_identity=psw.window_id
             AND psw.stage_id=pw.window_kind""",
        (
            str(factory_run_id),
            int(current["token_id"]),
            int(current["pair_id"]),
            canonical_tracking_lane,
            str(current["campaign_id"]),
            str(current["campaign_run_id"]),
            str(current["cycle_id"]),
            str(current["token_slot_id"]),
            str(current["window_id"]),
            int(current["token_id"]),
            int(current["pair_id"]),
            int(current["token_id"]),
            int(current["pair_id"]),
            int(cadence_authority.tracking_queue_id),
        ),
    ).fetchall()

    actual_candidates: list[tuple[datetime, int]] = []
    for row in prior_rows:
        try:
            prior_scheduled_for = _utc(str(row["scheduled_for"]))
            captured_at = _utc(str(row["captured_at"]))
        except (TypeError, ValueError):
            return _unknown("PRIOR_ACTUAL_CAPTURE_PROVENANCE_INVALID")
        planned_before_current = prior_scheduled_for < current_scheduled_for or (
            prior_scheduled_for == current_scheduled_for
            and int(row["scheduler_job_id"]) < int(current["scheduler_job_id"])
        )
        if planned_before_current:
            actual_candidates.append((captured_at, int(row["snapshot_id"])))

    if not actual_candidates:
        return _unknown("MISSING_PRIOR_ACTUAL_CAPTURE")
    last_actual, _ = max(actual_candidates, key=lambda value: (value[0], value[1]))
    forced_close = str(current["step_kind"]) in _FORCED_CLOSE_STEP_KINDS
    # For the existing unsplit close steps, scheduled_for is the canonical
    # planned window end.  It is only the closing-freshness input here; it is
    # never substituted for the prior ACTUAL capture above.
    return project_last_actual_capture_deadline(
        last_actual_snapshot_captured_at=last_actual,
        window_kind=str(current["window_kind"]),
        tracking_lane=canonical_tracking_lane,
        forced_close=forced_close,
        window_end_at=current_scheduled_for if forced_close else None,
    )


def deadline_order_value(projection: EvidenceDeadlineProjection) -> str:
    """Sort resolved deadlines first; UNKNOWN remains non-preferential."""
    if projection.deadline_at is None:
        return "9999-12-31T23:59:59.999999+00:00"
    return _utc(projection.deadline_at).isoformat()
