"""Authorization-preparation readiness gate (non-mandatory for WINDOW_15M).

Formal owners:

* Preparation / independent-review procedures may call
  ``evaluate_authorization_preparation_readiness_gate`` as an optional
  integrity check when a readiness artifact is supplied.
* Normal ``WINDOW_15M`` authorization preparation and independent review
  **do not require** a separate live pre-lifecycle readiness artifact,
  discovery-only qualification, readiness campaign, or readiness certificate.
  The real ``WINDOW_15M`` command remains responsible for discovering and
  validating candidates before lifecycle entry.
* Package apply-time structure remains
  ``git_provenance_authorization_manifest`` / one-shot wrapper (unchanged).

This module does not create authorizations, contact providers, or run the
wrapper. Historical packages that predate the gate are not mutated here.
The readiness artifact implementation may remain dormant; it is not called
or required by the normal authorization/run path.
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
    """Evaluate optional readiness binding for authorization preparation.

    Normal WINDOW_15M preparation/review PASSes when no readiness artifact is
    supplied (``status`` ends with ``_PASS`` / ``_NOT_REQUIRED``). A separate
    live pre-lifecycle readiness proof is not mandatory.

    If a readiness artifact *is* supplied, it is validated fail-closed for
    integrity of that optional binding only. Never emits an authorization
    package, contacts providers, or invokes the wrapper.
    """
    if readiness_artifact is None:
        # Non-mandatory: absent artifact does not block normal authorization.
        return {
            "schema_version": GATE_SCHEMA_VERSION,
            "readiness_schema_version": READINESS_SCHEMA_VERSION,
            "valid": True,
            "status": "AUTHORIZATION_PREPARATION_READINESS_GATE_NOT_REQUIRED",
            "blockers": [],
            "readiness_validation": {
                "valid": True,
                "blockers": [],
                "status": "READINESS_ARTIFACT_NOT_REQUIRED",
            },
            "readiness_required": False,
            "authorization_emitted": False,
            "wrapper_invoked": False,
            "provider_contacted": False,
        }

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
    if valid:
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
        "readiness_required": False,
        "authorization_emitted": False,
        "wrapper_invoked": False,
        "provider_contacted": False,
    }


def assert_authorization_preparation_readiness_gate(**kwargs: Any) -> dict[str, Any]:
    """Raise ``ValueError`` only when an *optional* supplied artifact fails validation.

    Absent readiness is allowed (non-mandatory). Does not contact providers.
    """
    result = evaluate_authorization_preparation_readiness_gate(**kwargs)
    if not result.get("valid") or not (
        str(result.get("status", "")).endswith("_PASS")
        or str(result.get("status", "")).endswith("_NOT_REQUIRED")
    ):
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
