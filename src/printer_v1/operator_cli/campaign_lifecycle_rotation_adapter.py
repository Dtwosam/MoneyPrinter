"""Campaign-owned adapter to the existing B.3 lifecycle authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import sqlite3
from typing import Any

from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
    _ACTIVE_JOB_STATUSES,
    _ACTIVE_QUEUE_STATUSES,
)
from printer_v1.operator_cli.tracking_lifecycle_reconciliation import (
    reconcile_factory_post_cycle_lifecycle,
)


class CampaignTerminalOutcome(StrEnum):
    NATURAL = "NATURAL"
    DIRTY = "DIRTY"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


_OUTCOME_TO_B3 = {
    CampaignTerminalOutcome.NATURAL: ("CLEAN", True),
    CampaignTerminalOutcome.DIRTY: ("DIRTY", True),
    CampaignTerminalOutcome.BLOCKED: ("TOKEN_LOCAL_FAILED", False),
    CampaignTerminalOutcome.CANCELLED: ("CANCELLED", False),
}
_CLOSED_TOKEN_STATES = frozenset({
    "WINDOW_15M_CLOSED", "WINDOW_1H_CLOSED", "WINDOW_4H_CLOSED",
})
_EXPECTED_TOKEN_STATES = {
    CampaignTerminalOutcome.NATURAL: _CLOSED_TOKEN_STATES,
    CampaignTerminalOutcome.DIRTY: _CLOSED_TOKEN_STATES,
    CampaignTerminalOutcome.BLOCKED: frozenset({"FAILED"}),
    CampaignTerminalOutcome.CANCELLED: frozenset({"MANUAL_REVIEW"}),
}


class CampaignLifecycleAdapterError(ValueError):
    """Raised when campaign/B.3 ownership or terminal evidence fails closed."""


@dataclass(frozen=True)
class TerminalCampaignToken:
    campaign_id: str
    run_id: str
    cycle_id: str
    token_slot_id: str
    token_identity: str
    mint_identity: str
    pair_identity: str
    lifecycle_identity: str
    outcome: CampaignTerminalOutcome | str


def _open_database(db_path: str | Path, *, read_only: bool) -> sqlite3.Connection:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise CampaignLifecycleAdapterError(f"database missing: {path}")
    if read_only:
        connection = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.0
        )
        connection.execute("PRAGMA query_only=ON")
    else:
        connection = sqlite3.connect(path, timeout=0.0)
        connection.execute("PRAGMA foreign_keys=ON")
    connection.row_factory = sqlite3.Row
    return connection


def _load_slot(
    connection: sqlite3.Connection, token: TerminalCampaignToken,
) -> dict[str, Any]:
    rows = connection.execute(
        """
        SELECT c.campaign_id, r.run_id, r.authoritative_run_id, y.cycle_id,
               s.token_slot_id, s.token_identity, s.token_row_id,
               s.mint_identity, s.pair_identity, s.pair_row_id,
               s.lifecycle_identity, s.tracking_queue_id, s.token_state,
               q.tracking_lane, q.queue_status
        FROM printer_memory_factory_campaigns AS c
        JOIN printer_memory_factory_campaign_runs AS r
          ON r.campaign_id=c.campaign_id
        JOIN printer_memory_factory_campaign_cycles AS y
          ON y.campaign_id=r.campaign_id AND y.run_id=r.run_id
        JOIN printer_memory_factory_campaign_token_slots AS s
          ON s.campaign_id=y.campaign_id AND s.run_id=y.run_id
         AND s.cycle_id=y.cycle_id
        LEFT JOIN printer_tracking_queue AS q
          ON q.id=s.tracking_queue_id AND q.token_id=s.token_row_id
         AND q.pair_id=s.pair_row_id
        WHERE c.campaign_id=? AND r.run_id=? AND y.cycle_id=?
          AND s.token_slot_id=?
        """,
        (token.campaign_id, token.run_id, token.cycle_id, token.token_slot_id),
    ).fetchall()
    if len(rows) != 1:
        raise CampaignLifecycleAdapterError(
            "campaign/run/cycle/token-slot ownership mismatch"
        )
    slot = dict(rows[0])
    expected = {
        "token_identity": token.token_identity,
        "mint_identity": token.mint_identity,
        "pair_identity": token.pair_identity,
        "lifecycle_identity": token.lifecycle_identity,
    }
    if any(slot[field] != value for field, value in expected.items()):
        raise CampaignLifecycleAdapterError(
            "token/mint/pair/lifecycle identity mismatch"
        )
    if not slot["authoritative_run_id"]:
        raise CampaignLifecycleAdapterError("campaign run lacks B.3 run identity")
    if slot["tracking_queue_id"] is None or slot["tracking_lane"] is None:
        raise CampaignLifecycleAdapterError(
            "campaign token lacks exact B.3 tracking queue identity"
        )
    return slot


def _reconciliation_key(slot: dict[str, Any]) -> str:
    return (
        f"{slot['authoritative_run_id']}:"
        f"{int(slot['token_row_id'])}:{int(slot['pair_row_id'])}"
    )


def _event_rows(
    connection: sqlite3.Connection, slot: dict[str, Any],
) -> list[sqlite3.Row]:
    key = _reconciliation_key(slot)
    return connection.execute(
        """
        SELECT * FROM printer_token_lifecycle_events
        WHERE token_id=? AND pair_id=?
          AND json_extract(event_payload_json, '$.factory_reconciliation_key')=?
        ORDER BY id
        """,
        (slot["token_row_id"], slot["pair_row_id"], key),
    ).fetchall()


def _active_associated_work(
    connection: sqlite3.Connection, slot: dict[str, Any],
) -> dict[str, int]:
    queue_jobs = int(connection.execute(
        """SELECT COUNT(*) FROM printer_scheduler_jobs
           WHERE target_table='printer_tracking_queue' AND target_id=?
             AND status IN (?,?,?)""",
        (slot["tracking_queue_id"], *_ACTIVE_JOB_STATUSES),
    ).fetchone()[0])
    campaign_work = int(connection.execute(
        """SELECT COUNT(*)
           FROM printer_memory_factory_campaign_scheduler_work AS work
           LEFT JOIN printer_scheduler_jobs AS job
             ON job.id=work.scheduler_job_id
           WHERE work.campaign_id=? AND work.run_id=? AND work.cycle_id=?
             AND work.token_slot_id=?
             AND (
                 work.work_state IN ('PENDING','RUNNING','COOLDOWN')
                 OR job.status IN ('PENDING','RUNNING','COOLDOWN')
             )""",
        (
            slot["campaign_id"], slot["run_id"], slot["cycle_id"],
            slot["token_slot_id"],
        ),
    ).fetchone()[0])
    support_steps = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_run_steps
           WHERE run_id=? AND token_id=? AND pair_id=? AND step_kind='SUPPORT_5M'
             AND step_status IN ('PENDING','RUNNING')""",
        (
            slot["authoritative_run_id"], slot["token_row_id"],
            slot["pair_row_id"],
        ),
    ).fetchone()[0])
    return {
        "active_queue_jobs": queue_jobs,
        "active_campaign_work": campaign_work,
        "active_support_steps": support_steps,
        "total": queue_jobs + campaign_work + support_steps,
    }


def reconcile_terminal_campaign_token(
    db_path: str | Path,
    *,
    token: TerminalCampaignToken,
    stop_reason: str,
    archive_policy: str = "cooldown",
) -> dict[str, Any]:
    """Validate one terminal token and delegate all lifecycle writes to B.3."""
    try:
        outcome = CampaignTerminalOutcome(token.outcome)
    except ValueError as exc:
        raise CampaignLifecycleAdapterError("unsupported terminal campaign outcome") from exc
    if archive_policy not in {"cooldown", "archive"}:
        raise CampaignLifecycleAdapterError("unsupported B.3 archive policy")
    reason = str(stop_reason).strip()
    if not reason:
        raise CampaignLifecycleAdapterError("terminal stop reason is required")
    connection = _open_database(db_path, read_only=False)
    try:
        connection.execute("BEGIN IMMEDIATE")
        slot = _load_slot(connection, token)
        if slot["token_state"] not in _EXPECTED_TOKEN_STATES[outcome]:
            raise CampaignLifecycleAdapterError(
                "campaign token state does not match terminal outcome"
            )
        terminal_status, reached_terminal_window = _OUTCOME_TO_B3[outcome]
        target = {
            "token_id": int(slot["token_row_id"]),
            "pair_id": int(slot["pair_row_id"]),
            "token_mint": slot["mint_identity"],
            "pair_address": slot["pair_identity"],
            "tracking_lane": slot["tracking_lane"],
            "tracking_queue_id": int(slot["tracking_queue_id"]),
        }
        result = reconcile_factory_post_cycle_lifecycle(
            connection,
            run_id=str(slot["authoritative_run_id"]),
            selected_tokens=[target],
            discovery_results=[target],
            per_token_outcomes=[{
                "token_id": target["token_id"],
                "pair_id": target["pair_id"],
                "terminal_status": terminal_status,
                "reached_terminal_window": reached_terminal_window,
            }],
            stop_reason=reason,
            archive_policy=archive_policy,
        )
        transitions = result.get("transitions", [])
        if len(transitions) != 1 or not result.get(
            "exactly_one_disposition_per_selected_token"
        ):
            raise CampaignLifecycleAdapterError(
                "B.3 did not return exactly one disposition"
            )
        transition = transitions[0]
        if (
            int(transition["token_id"]) != target["token_id"]
            or int(transition["pair_id"]) != target["pair_id"]
        ):
            raise CampaignLifecycleAdapterError("B.3 disposition identity mismatch")
        events = _event_rows(connection, slot)
        if len(events) != 1 or int(events[0]["id"]) != int(
            transition["lifecycle_event_id"]
        ):
            raise CampaignLifecycleAdapterError(
                "B.3 lifecycle event is missing or ambiguous"
            )
        queue = connection.execute(
            "SELECT queue_status FROM printer_tracking_queue WHERE id=?",
            (slot["tracking_queue_id"],),
        ).fetchone()
        if queue is None or str(queue["queue_status"]) != str(
            transition["terminal_disposition"]
        ):
            raise CampaignLifecycleAdapterError("B.3 queue disposition mismatch")
        connection.execute(
            """UPDATE printer_memory_factory_campaign_scheduler_work
               SET work_state='CANCELLED',first_terminal_cause=COALESCE(
                       first_terminal_cause,?
                   ),terminal_at=COALESCE(terminal_at,?),updated_at=?
               WHERE campaign_id=? AND run_id=? AND cycle_id=?
                 AND token_slot_id=?
                 AND work_state IN ('PENDING','RUNNING','COOLDOWN')""",
            (
                reason, events[0]["created_at"], events[0]["created_at"],
                slot["campaign_id"], slot["run_id"], slot["cycle_id"],
                slot["token_slot_id"],
            ),
        )
        active = _active_associated_work(connection, slot)
        if active["total"] != 0:
            raise CampaignLifecycleAdapterError(
                "B.3 cleanup left active associated work"
            )
        connection.commit()
        return {
            "authority": "B.3_LIFECYCLE_RECONCILIATION",
            "campaign_id": token.campaign_id,
            "run_id": token.run_id,
            "authoritative_run_id": slot["authoritative_run_id"],
            "cycle_id": token.cycle_id,
            "token_slot_id": token.token_slot_id,
            "token_identity": token.token_identity,
            "token_row_id": int(slot["token_row_id"]),
            "mint_identity": token.mint_identity,
            "pair_identity": token.pair_identity,
            "pair_row_id": int(slot["pair_row_id"]),
            "lifecycle_identity": token.lifecycle_identity,
            "terminal_outcome": outcome.value,
            "archive_policy": archive_policy,
            "terminal_disposition": transition["terminal_disposition"],
            "lifecycle_event": transition["lifecycle_event"],
            "lifecycle_event_id": int(transition["lifecycle_event_id"]),
            "tracking_queue_id": int(slot["tracking_queue_id"]),
            "cancelled_scheduler_job_ids": transition[
                "cancelled_scheduler_job_ids"
            ],
            "active_associated_work": active,
            "slot_vacant": True,
            "idempotent_replay": bool(transition["idempotent_replay"]),
            "support_5m": transition["support_5m"],
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def evaluate_slot_replacement(
    db_path: str | Path,
    *,
    token: TerminalCampaignToken,
    candidate_token_row_id: int,
    candidate_mint_identity: str,
    candidate_pair_row_id: int,
    candidate_pair_identity: str,
) -> dict[str, Any]:
    """Read-only eligibility gate; it never creates a replacement slot."""
    connection = _open_database(db_path, read_only=True)
    try:
        slot = _load_slot(connection, token)
        reasons: list[str] = []
        events = _event_rows(connection, slot)
        if len(events) != 1:
            reasons.append("terminal_token_not_successfully_reconciled")
        active = _active_associated_work(connection, slot)
        if active["total"] != 0:
            reasons.append("active_associated_work_remains")

        candidate = connection.execute(
            """SELECT t.id AS token_row_id, t.token_mint,
                      p.id AS pair_row_id, p.pair_address, p.token_id
               FROM printer_tokens AS t
               JOIN printer_pairs AS p ON p.token_id=t.id
               WHERE t.id=? AND t.token_mint=?
                 AND p.id=? AND p.pair_address=?""",
            (
                candidate_token_row_id, candidate_mint_identity,
                candidate_pair_row_id, candidate_pair_identity,
            ),
        ).fetchone()
        if candidate is None:
            reasons.append("candidate_token_mint_pair_identity_mismatch")
        if (
            candidate_pair_row_id == int(slot["pair_row_id"])
            or candidate_pair_identity == str(slot["pair_identity"])
        ):
            reasons.append("same_pair_recycling_blocked")

        assigned = connection.execute(
            """SELECT 1 FROM printer_memory_factory_campaign_token_slots
               WHERE campaign_id=? AND cycle_id=? AND pair_row_id=?
               LIMIT 1""",
            (token.campaign_id, token.cycle_id, candidate_pair_row_id),
        ).fetchone()
        if assigned is not None:
            reasons.append("candidate_pair_already_assigned_in_cycle")

        latest_queue = connection.execute(
            """SELECT queue_status FROM printer_tracking_queue
               WHERE token_id=? AND pair_id=? ORDER BY id DESC LIMIT 1""",
            (candidate_token_row_id, candidate_pair_row_id),
        ).fetchone()
        if latest_queue is not None:
            queue_status = str(latest_queue["queue_status"])
            if queue_status == "COOLDOWN":
                reasons.append("candidate_pair_cooldown_active")
            elif queue_status == "ARCHIVED":
                reasons.append("candidate_pair_requires_existing_reopen_policy")
            elif queue_status in _ACTIVE_QUEUE_STATUSES:
                reasons.append("candidate_pair_already_active")

        return {
            "authority": "B.3_REPLACEMENT_GATE",
            "campaign_id": token.campaign_id,
            "run_id": token.run_id,
            "cycle_id": token.cycle_id,
            "token_slot_id": token.token_slot_id,
            "reconciled_lifecycle_event_id": (
                int(events[0]["id"]) if len(events) == 1 else None
            ),
            "active_associated_work": active,
            "candidate_token_row_id": candidate_token_row_id,
            "candidate_mint_identity": candidate_mint_identity,
            "candidate_pair_row_id": candidate_pair_row_id,
            "candidate_pair_identity": candidate_pair_identity,
            "slot_vacant": not reasons,
            "replacement_allowed": not reasons,
            "reasons": list(dict.fromkeys(reasons)),
            "archive_is_permanent_rejection": False,
            "read_only": True,
        }
    finally:
        connection.close()
