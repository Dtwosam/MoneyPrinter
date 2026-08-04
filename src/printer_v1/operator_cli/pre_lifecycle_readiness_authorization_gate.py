"""Final-authorization preparation gate requiring a valid readiness artifact.

Formal owners:

* Preparation / independent-review procedures call
  ``evaluate_authorization_preparation_readiness_gate`` before a future
  authorization package may PASS.
* Package apply-time structure remains
  ``git_provenance_authorization_manifest`` / one-shot wrapper (unchanged).

This module does not create authorizations, contact providers, or run the
wrapper. Historical packages that predate the gate are not mutated here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from printer_v1.operator_cli.pre_lifecycle_readiness_artifact import (
    SCHEMA_VERSION as READINESS_SCHEMA_VERSION,
    validate_pre_lifecycle_readiness_artifact,
)


GATE_SCHEMA_VERSION = "PRINTER_V1_AUTHORIZATION_PREPARATION_READINESS_GATE_V1"


def evaluate_authorization_preparation_readiness_gate(
    *,
    readiness_artifact: Mapping[str, Any] | None,
    now: str | datetime,
    expected_head: str,
    expected_db_identity: Mapping[str, Any],
    expected_candidates: Sequence[Mapping[str, Any]] | None = None,
    candidate_state: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fail closed unless a valid full pre-lifecycle readiness artifact is bound.

    Returns a structured gate result. ``status`` ends with ``_PASS`` only when
    every readiness validation check succeeds. Never emits an authorization
    package.
    """
    validation = validate_pre_lifecycle_readiness_artifact(
        readiness_artifact,
        now=now,
        expected_head=expected_head,
        expected_db_identity=expected_db_identity,
        expected_candidates=expected_candidates,
        candidate_state=candidate_state,
    )
    valid = bool(validation.get("valid"))
    blockers = list(validation.get("blockers") or [])
    if readiness_artifact is None:
        status = "AUTHORIZATION_PREPARATION_READINESS_GATE_BLOCKED_ABSENT"
    elif valid:
        status = "AUTHORIZATION_PREPARATION_READINESS_GATE_PASS"
    else:
        status = "AUTHORIZATION_PREPARATION_READINESS_GATE_BLOCKED"

    return {
        "schema_version": GATE_SCHEMA_VERSION,
        "readiness_schema_version": READINESS_SCHEMA_VERSION,
        "valid": valid,
        "status": status,
        "blockers": blockers,
        "readiness_validation": validation,
        "authorization_emitted": False,
        "wrapper_invoked": False,
        "provider_contacted": False,
    }


def assert_authorization_preparation_readiness_gate(**kwargs: Any) -> dict[str, Any]:
    """Raise ``ValueError`` when the preparation readiness gate does not PASS."""
    result = evaluate_authorization_preparation_readiness_gate(**kwargs)
    if not result.get("valid") or not str(result.get("status", "")).endswith("_PASS"):
        blockers = ", ".join(result.get("blockers") or ["unknown"])
        raise ValueError(
            "authorization preparation readiness gate blocked: " + blockers
        )
    return result


__all__ = [
    "GATE_SCHEMA_VERSION",
    "evaluate_authorization_preparation_readiness_gate",
    "assert_authorization_preparation_readiness_gate",
]
