"""Canonical Lane-2 close-phase identities and dependency resolution.

The existing factory run-step, Scheduler-job, and campaign Scheduler-work rows
remain the persistence owners.  This module only derives phase semantics from
``step_kind`` and validates exact predecessor provenance; it creates no second
scheduler or source authority.
"""

from __future__ import annotations

import json
import sqlite3
from types import MappingProxyType
from typing import Any, Mapping


CLOSE_PHASE_CONTRACT_VERSION = "LANE2_CLOSE_PHASE_V1"

CLOSE_PHASE_STEP_KINDS = MappingProxyType(
    {
        "WINDOW_CLOSE_EVIDENCE": ("WINDOW_CLOSE", "EVIDENCE"),
        "WINDOW_CLOSE_CONTEXT": ("WINDOW_CLOSE", "CONTEXT"),
        "WINDOW_CLOSE_AUDIT": ("WINDOW_CLOSE", "AUDIT"),
        "CONTINUATION_CLOSE_EVIDENCE": (
            "CONTINUATION_CLOSE",
            "EVIDENCE",
        ),
        "CONTINUATION_CLOSE_CONTEXT": (
            "CONTINUATION_CLOSE",
            "CONTEXT",
        ),
        "CONTINUATION_CLOSE_AUDIT": (
            "CONTINUATION_CLOSE",
            "AUDIT",
        ),
        "LONG_CONTINUATION_CLOSE_EVIDENCE": (
            "LONG_CONTINUATION_CLOSE",
            "EVIDENCE",
        ),
        "LONG_CONTINUATION_CLOSE_CONTEXT": (
            "LONG_CONTINUATION_CLOSE",
            "CONTEXT",
        ),
        "LONG_CONTINUATION_CLOSE_AUDIT": (
            "LONG_CONTINUATION_CLOSE",
            "AUDIT",
        ),
    }
)

EVIDENCE_STEP_KINDS = frozenset(
    kind for kind, (_, phase) in CLOSE_PHASE_STEP_KINDS.items() if phase == "EVIDENCE"
)
CONTEXT_STEP_KINDS = frozenset(
    kind for kind, (_, phase) in CLOSE_PHASE_STEP_KINDS.items() if phase == "CONTEXT"
)
AUDIT_STEP_KINDS = frozenset(
    kind for kind, (_, phase) in CLOSE_PHASE_STEP_KINDS.items() if phase == "AUDIT"
)

LEGACY_CLOSE_STEP_KINDS = frozenset(
    {"WINDOW_CLOSE", "CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE"}
)
TERMINAL_CLOSE_STEP_KINDS = LEGACY_CLOSE_STEP_KINDS | AUDIT_STEP_KINDS


def close_phase_metadata(
    *,
    family: str,
    phase: str,
    evidence_step_key: str,
    context_step_key: str,
) -> dict[str, str | None]:
    """Return the immutable phase/dependency projection stored in result_json."""
    normalized_phase = str(phase).upper()
    if normalized_phase not in {"EVIDENCE", "CONTEXT", "AUDIT"}:
        raise ValueError(f"unsupported close phase: {phase}")
    if family not in LEGACY_CLOSE_STEP_KINDS:
        raise ValueError(f"unsupported close family: {family}")
    if not evidence_step_key or not context_step_key:
        raise ValueError("close phase dependency keys must be non-empty")
    return {
        "close_phase_contract_version": CLOSE_PHASE_CONTRACT_VERSION,
        "close_family": family,
        "close_phase": normalized_phase,
        "evidence_step_key": evidence_step_key,
        "context_step_key": context_step_key,
        "predecessor_step_key": (
            None
            if normalized_phase == "EVIDENCE"
            else evidence_step_key
            if normalized_phase == "CONTEXT"
            else context_step_key
        ),
    }


def close_phase_order(step_kind: str) -> int:
    """Return the accepted intra-close ordering; legacy close stays compatible."""
    phase = CLOSE_PHASE_STEP_KINDS.get(str(step_kind), (None, None))[1]
    return {"EVIDENCE": 1, "CONTEXT": 2, "AUDIT": 3}.get(phase, 3)


def is_close_phase_step(step_kind: str) -> bool:
    return str(step_kind) in CLOSE_PHASE_STEP_KINDS


def _payload(step: Mapping[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(str(step["result_json"] or "{}"))
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _exact_step(
    connection: sqlite3.Connection,
    *,
    current: Mapping[str, Any],
    step_key: str,
    expected_phase: str,
) -> sqlite3.Row | None:
    rows = connection.execute(
        """SELECT * FROM printer_memory_factory_run_steps
           WHERE run_id=? AND step_key=? ORDER BY id""",
        (str(current["run_id"]), str(step_key)),
    ).fetchall()
    if len(rows) != 1:
        return None
    row = rows[0]
    identity_fields = (
        "run_id",
        "token_id",
        "pair_id",
        "token_mint",
        "pair_address",
        "tracking_lane",
        "scheduled_for",
    )
    if any(str(row[field]) != str(current[field]) for field in identity_fields):
        return None
    family_phase = CLOSE_PHASE_STEP_KINDS.get(str(row["step_kind"]))
    current_family_phase = CLOSE_PHASE_STEP_KINDS.get(str(current["step_kind"]))
    if (
        family_phase is None
        or current_family_phase is None
        or family_phase[0] != current_family_phase[0]
        or family_phase[1] != expected_phase
    ):
        return None
    predecessor_payload = _payload(row)
    if (
        predecessor_payload.get("close_phase_contract_version")
        != CLOSE_PHASE_CONTRACT_VERSION
        or predecessor_payload.get("close_family") != family_phase[0]
        or predecessor_payload.get("close_phase") != expected_phase
    ):
        return None
    return row


def _campaign_owners(
    connection: sqlite3.Connection, scheduler_job_id: int
) -> list[sqlite3.Row]:
    return list(connection.execute(
        """SELECT * FROM printer_memory_factory_campaign_scheduler_work
           WHERE scheduler_job_id=? AND ownership_contract_version='V2_STAGE_SCOPED'
           ORDER BY scheduler_work_id""",
        (int(scheduler_job_id),),
    ).fetchall())


def _same_campaign_window_owner(
    connection: sqlite3.Connection,
    current: Mapping[str, Any],
    predecessor: Mapping[str, Any],
) -> bool:
    if current["scheduler_job_id"] is None or predecessor["scheduler_job_id"] is None:
        return False
    current_owners = _campaign_owners(
        connection, int(current["scheduler_job_id"])
    )
    predecessor_owners = _campaign_owners(
        connection, int(predecessor["scheduler_job_id"])
    )
    if len(current_owners) > 1 or len(predecessor_owners) > 1:
        return False
    if not current_owners and not predecessor_owners:
        return True
    if not current_owners or not predecessor_owners:
        return False
    current_owner = current_owners[0]
    predecessor_owner = predecessor_owners[0]
    exact_fields = (
        "campaign_id",
        "run_id",
        "cycle_id",
        "token_slot_id",
        "window_id",
        "factory_run_id",
        "stage_id",
        "work_scope",
        "target_category",
        "target_identity",
    )
    return all(
        str(current_owner[field]) == str(predecessor_owner[field])
        for field in exact_fields
    )


def resolve_close_evidence(
    connection: sqlite3.Connection,
    step: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve the exact successful closing evidence for context/audit."""
    metadata = _payload(step)
    expected = CLOSE_PHASE_STEP_KINDS.get(str(step["step_kind"]))
    if (
        expected is None
        or metadata.get("close_phase_contract_version")
        != CLOSE_PHASE_CONTRACT_VERSION
        or metadata.get("close_family") != expected[0]
        or metadata.get("close_phase") != expected[1]
    ):
        return {"resolved": False, "reason": "CLOSE_PHASE_METADATA_INVALID"}
    evidence_key = str(metadata.get("evidence_step_key") or "")
    evidence = _exact_step(
        connection,
        current=step,
        step_key=evidence_key,
        expected_phase="EVIDENCE",
    )
    if evidence is None or str(evidence["step_status"]) != "SUCCEEDED":
        return {"resolved": False, "reason": "CLOSE_EVIDENCE_NOT_SUCCEEDED"}
    if not _same_campaign_window_owner(connection, step, evidence):
        return {"resolved": False, "reason": "CLOSE_EVIDENCE_OWNER_MISMATCH"}
    if evidence["snapshot_id"] is None:
        return {"resolved": False, "reason": "CLOSE_EVIDENCE_SNAPSHOT_MISSING"}
    snapshot = connection.execute(
        """SELECT id,token_id,pair_id,captured_at FROM printer_token_snapshots
           WHERE id=?""",
        (int(evidence["snapshot_id"]),),
    ).fetchone()
    if (
        snapshot is None
        or int(snapshot["token_id"]) != int(step["token_id"])
        or int(snapshot["pair_id"]) != int(step["pair_id"])
        or not str(snapshot["captured_at"] or "")
    ):
        return {"resolved": False, "reason": "CLOSE_EVIDENCE_SNAPSHOT_MISMATCH"}
    return {
        "resolved": True,
        "reason": None,
        "evidence_step": evidence,
        "snapshot_id": int(snapshot["id"]),
        "evidence_captured_at": str(snapshot["captured_at"]),
        "metadata": metadata,
    }


def resolve_close_context(
    connection: sqlite3.Connection,
    step: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve the exact successful context predecessor required by audit."""
    evidence = resolve_close_evidence(connection, step)
    if not evidence["resolved"]:
        return evidence
    metadata = evidence["metadata"]
    context = _exact_step(
        connection,
        current=step,
        step_key=str(metadata.get("context_step_key") or ""),
        expected_phase="CONTEXT",
    )
    if context is None or str(context["step_status"]) != "SUCCEEDED":
        return {"resolved": False, "reason": "CLOSE_CONTEXT_NOT_SUCCEEDED"}
    if not _same_campaign_window_owner(connection, step, context):
        return {"resolved": False, "reason": "CLOSE_CONTEXT_OWNER_MISMATCH"}
    return {**evidence, "context_step": context}


def close_phase_dependency_ready(
    connection: sqlite3.Connection,
    step: Mapping[str, Any],
) -> bool:
    """Return whether the phase is lawfully claimable through Scheduler."""
    phase = CLOSE_PHASE_STEP_KINDS.get(str(step["step_kind"]), (None, None))[1]
    if phase is None or phase == "EVIDENCE":
        return True
    if phase == "CONTEXT":
        return bool(resolve_close_evidence(connection, step)["resolved"])
    return bool(resolve_close_context(connection, step)["resolved"])
