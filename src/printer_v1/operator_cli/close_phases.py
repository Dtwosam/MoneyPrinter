"""Canonical Lane-2 close-phase identities and dependency resolution.

The existing factory run-step, Scheduler-job, and campaign Scheduler-work rows
remain the persistence owners.  This module only derives phase semantics from
``step_kind`` and validates exact predecessor provenance; it creates no second
scheduler or source authority.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping


CLOSE_PHASE_CONTRACT_VERSION = "LANE2_CLOSE_PHASE_V2"

CLOSE_PHASE_STEP_KINDS = MappingProxyType(
    {
        "WINDOW_CLOSE_PRE_CLOSE_CRITICAL": ("WINDOW_CLOSE", "PRE_CLOSE"),
        "WINDOW_CLOSE_EVIDENCE": ("WINDOW_CLOSE", "EVIDENCE"),
        "WINDOW_CLOSE_CONTEXT": ("WINDOW_CLOSE", "CONTEXT"),
        "WINDOW_CLOSE_AUDIT": ("WINDOW_CLOSE", "AUDIT"),
        "CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL": (
            "CONTINUATION_CLOSE",
            "PRE_CLOSE",
        ),
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
        "LONG_CONTINUATION_CLOSE_PRE_CLOSE_CRITICAL": (
            "LONG_CONTINUATION_CLOSE",
            "PRE_CLOSE",
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

PRE_CLOSE_STEP_KINDS = frozenset(
    kind for kind, (_, phase) in CLOSE_PHASE_STEP_KINDS.items() if phase == "PRE_CLOSE"
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
    preclose_step_key: str | None = None,
) -> dict[str, str | None]:
    """Return the immutable phase/dependency projection stored in result_json."""
    normalized_phase = str(phase).upper()
    if normalized_phase not in {"PRE_CLOSE", "EVIDENCE", "CONTEXT", "AUDIT"}:
        raise ValueError(f"unsupported close phase: {phase}")
    if family not in LEGACY_CLOSE_STEP_KINDS:
        raise ValueError(f"unsupported close family: {family}")
    inferred_preclose_key = str(
        preclose_step_key
        or (
            evidence_step_key[: -len("_evidence")] + "_pre_close_critical"
            if evidence_step_key.endswith("_evidence")
            else f"{evidence_step_key}_pre_close_critical"
        )
    )
    if not inferred_preclose_key or not evidence_step_key or not context_step_key:
        raise ValueError("close phase dependency keys must be non-empty")
    return {
        "close_phase_contract_version": CLOSE_PHASE_CONTRACT_VERSION,
        "close_family": family,
        "close_phase": normalized_phase,
        "preclose_step_key": inferred_preclose_key,
        "evidence_step_key": evidence_step_key,
        "context_step_key": context_step_key,
        "predecessor_step_key": (
            None
            if normalized_phase in {"PRE_CLOSE", "EVIDENCE"}
            else evidence_step_key
            if normalized_phase == "CONTEXT"
            else context_step_key
        ),
    }


def close_phase_order(step_kind: str) -> int:
    """Return the accepted intra-close ordering; legacy close stays compatible."""
    phase = CLOSE_PHASE_STEP_KINDS.get(str(step_kind), (None, None))[1]
    return {"EVIDENCE": 1, "PRE_CLOSE": 2, "CONTEXT": 3, "AUDIT": 4}.get(
        phase, 4
    )


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
    )
    if any(str(row[field]) != str(current[field]) for field in identity_fields):
        return None
    if expected_phase != "PRE_CLOSE" and str(row["scheduled_for"]) != str(
        current["scheduled_for"]
    ):
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


def _preclose_manifest_is_terminal(payload: Mapping[str, Any]) -> bool:
    if payload.get("preclose_plan_state") == "TIMELY_ACQUISITION_NOT_PRODUCIBLE":
        return True
    units = payload.get("source_unit_manifest")
    if not isinstance(units, list) or not units:
        return False
    return all(
        isinstance(unit, Mapping)
        and str(unit.get("state"))
        not in {"PENDING", "BLOCKED_DEPENDENCY", ""}
        for unit in units
    )


def resolve_preclose_manifest(
    connection: sqlite3.Connection,
    step: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve one exact terminal pre-close manifest for post-capture join."""
    metadata = _payload(step)
    expected = CLOSE_PHASE_STEP_KINDS.get(str(step["step_kind"]))
    if (
        expected is None
        or metadata.get("close_phase_contract_version")
        != CLOSE_PHASE_CONTRACT_VERSION
        or metadata.get("close_family") != expected[0]
    ):
        return {"resolved": False, "reason": "CLOSE_PHASE_METADATA_INVALID"}
    preclose = _exact_step(
        connection,
        current=step,
        step_key=str(metadata.get("preclose_step_key") or ""),
        expected_phase="PRE_CLOSE",
    )
    if preclose is None or str(preclose["step_status"]) not in {"SUCCEEDED", "SKIPPED"}:
        return {"resolved": False, "reason": "PRE_CLOSE_MANIFEST_NOT_TERMINAL"}
    if not _same_campaign_window_owner(connection, step, preclose):
        return {"resolved": False, "reason": "PRE_CLOSE_OWNER_MISMATCH"}
    payload = _payload(preclose)
    if not _preclose_manifest_is_terminal(payload):
        return {"resolved": False, "reason": "PRE_CLOSE_MANIFEST_NOT_TERMINAL"}
    return {
        "resolved": True,
        "reason": None,
        "preclose_step": preclose,
        "preclose_manifest": payload,
    }


def context_binding_failure_is_exact(
    connection: sqlite3.Connection,
    context_step: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    evidence: Mapping[str, Any] | None = None,
    preclose: Mapping[str, Any] | None = None,
) -> bool:
    """Validate the sole audit-preserving failed-context producer contract."""
    expected = CLOSE_PHASE_STEP_KINDS.get(str(context_step["step_kind"]))
    if expected is None or expected[1] != "CONTEXT":
        return False
    resolved_evidence = evidence or resolve_close_evidence(connection, context_step)
    resolved_preclose = preclose or resolve_preclose_manifest(
        connection, context_step
    )
    if not resolved_evidence.get("resolved") or not resolved_preclose.get(
        "resolved"
    ):
        return False
    envelope = payload.get("closing_context_envelope")
    collection = payload.get("governed_context_collection")
    persistence = payload.get("governed_context_persistence")
    if (
        not isinstance(envelope, Mapping)
        or not isinstance(collection, Mapping)
        or not isinstance(persistence, Mapping)
    ):
        return False
    failed_at = envelope.get("failed_at")
    try:
        parsed_failure_at = datetime.fromisoformat(str(failed_at))
    except (TypeError, ValueError):
        return False
    if parsed_failure_at.tzinfo is None:
        return False
    snapshot_id = int(resolved_evidence["snapshot_id"])
    evidence_step = resolved_evidence["evidence_step"]
    preclose_step = resolved_preclose["preclose_step"]
    required = {
        "context_state": "CONTEXT_BINDING_FAILED",
        "failure_type": "CONTEXT_BINDING_FAILED",
        "factory_run_id": str(context_step["run_id"]),
        "token_id": int(context_step["token_id"]),
        "pair_id": int(context_step["pair_id"]),
        "token_mint": str(context_step["token_mint"]),
        "pair_address": str(context_step["pair_address"]),
        "tracking_lane": str(context_step["tracking_lane"]),
        "window_family": expected[0],
        "context_step_id": int(context_step["id"]),
        "context_step_key": str(context_step["step_key"]),
        "context_step_kind": str(context_step["step_kind"]),
        "context_scheduler_job_id": int(context_step["scheduler_job_id"]),
        "evidence_step_id": int(evidence_step["id"]),
        "evidence_step_key": str(evidence_step["step_key"]),
        "evidence_scheduler_job_id": int(evidence_step["scheduler_job_id"]),
        "preclose_manifest_step_id": int(preclose_step["id"]),
        "preclose_step_key": str(preclose_step["step_key"]),
        "preclose_scheduler_job_id": int(preclose_step["scheduler_job_id"]),
        "closing_snapshot_id": snapshot_id,
        "closing_snapshot_captured_at": str(
            resolved_evidence["evidence_captured_at"]
        ),
    }
    if any(str(envelope.get(key)) != str(value) for key, value in required.items()):
        return False
    if (
        payload.get("ok") is not False
        or payload.get("audit_preserving_context_failure") is not True
        or str(payload.get("blocked_reason")) != "CONTEXT_BINDING_FAILED"
        or int(payload.get("closing_snapshot_id") or -1) != snapshot_id
        or envelope.get("unit_results") != collection.get("unit_results")
        or not isinstance(envelope.get("unit_results"), list)
        or not str(envelope.get("failure_reason") or "")
        or str(payload.get("binding_failed_at")) != str(failed_at)
        or str(persistence.get("status")) != "FAILED"
        or persistence.get("persisted") is not False
        or str(persistence.get("reason"))
        != str(envelope.get("failure_reason"))
        or int(payload.get("preclose_manifest_step_id") or -1)
        != int(preclose_step["id"])
        or str(payload.get("evidence_captured_at"))
        != str(resolved_evidence["evidence_captured_at"])
        or int(collection.get("post_capture_main_window_provider_calls") or 0)
        != 0
        or payload.get("snapshot_id") is not None
        or payload.get("evidence_bound_at") is not None
    ):
        return False

    owners = _campaign_owners(
        connection, int(context_step["scheduler_job_id"])
    )
    if len(owners) > 1:
        return False
    campaign_identity_keys = (
        "campaign_id",
        "campaign_run_id",
        "cycle_id",
        "token_slot_id",
        "campaign_window_id",
        "campaign_scheduler_work_id",
        "campaign_stage_id",
        "campaign_work_scope",
        "campaign_target_category",
        "campaign_target_identity",
    )
    if owners:
        owner = owners[0]
        campaign_identity = {
            "campaign_id": str(owner["campaign_id"]),
            "campaign_run_id": str(owner["run_id"]),
            "cycle_id": str(owner["cycle_id"]),
            "token_slot_id": str(owner["token_slot_id"]),
            "campaign_window_id": str(owner["window_id"]),
            "campaign_scheduler_work_id": str(owner["scheduler_work_id"]),
            "campaign_stage_id": str(owner["stage_id"]),
            "campaign_work_scope": str(owner["work_scope"]),
            "campaign_target_category": str(owner["target_category"]),
            "campaign_target_identity": str(owner["target_identity"]),
        }
        if any(
            str(envelope.get(key)) != value
            for key, value in campaign_identity.items()
        ):
            return False
    elif any(key in envelope for key in campaign_identity_keys):
        return False
    return True


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
    if context is None or str(context["step_status"]) not in {"SUCCEEDED", "FAILED"}:
        return {"resolved": False, "reason": "CLOSE_CONTEXT_NOT_SUCCEEDED"}
    if not _same_campaign_window_owner(connection, step, context):
        return {"resolved": False, "reason": "CLOSE_CONTEXT_OWNER_MISMATCH"}
    if str(context["step_status"]) == "SUCCEEDED":
        return {**evidence, "context_step": context, "typed_context_failure": False}
    payload = _payload(context)
    envelope = payload.get("closing_context_envelope")
    allowed_states = {
        "CONTEXT_PARTIAL",
        "CONTEXT_PROVIDER_FAILED",
        "CONTEXT_BINDING_FAILED",
        "CONTEXT_UNKNOWN",
    }
    preclose = resolve_preclose_manifest(connection, step)
    if (
        isinstance(envelope, Mapping)
        and str(envelope.get("context_state") or "")
        == "CONTEXT_BINDING_FAILED"
        and not context_binding_failure_is_exact(
            connection,
            context,
            payload,
            evidence=evidence,
            preclose=preclose,
        )
    ):
        return {"resolved": False, "reason": "CLOSE_CONTEXT_FAILURE_ENVELOPE_INVALID"}
    if (
        payload.get("ok") is not False
        or int(payload.get("closing_snapshot_id") or -1) != int(evidence["snapshot_id"])
        or not isinstance(envelope, Mapping)
        or str(envelope.get("context_state") or "") not in allowed_states
        or int(envelope.get("closing_snapshot_id") or -1)
        != int(evidence["snapshot_id"])
        or not isinstance(envelope.get("unit_results"), list)
        or not preclose.get("resolved")
        or int(envelope.get("preclose_manifest_step_id") or -1)
        != int(preclose["preclose_step"]["id"])
    ):
        return {"resolved": False, "reason": "CLOSE_CONTEXT_FAILURE_ENVELOPE_INVALID"}
    return {**evidence, "context_step": context, "typed_context_failure": True}


def close_phase_dependency_ready(
    connection: sqlite3.Connection,
    step: Mapping[str, Any],
) -> bool:
    """Return whether the phase is lawfully claimable through Scheduler."""
    phase = CLOSE_PHASE_STEP_KINDS.get(str(step["step_kind"]), (None, None))[1]
    if phase is None or phase == "EVIDENCE":
        return True
    if phase == "PRE_CLOSE":
        return True
    if phase == "CONTEXT":
        return bool(
            resolve_close_evidence(connection, step)["resolved"]
            and resolve_preclose_manifest(connection, step)["resolved"]
        )
    return bool(resolve_close_context(connection, step)["resolved"])
