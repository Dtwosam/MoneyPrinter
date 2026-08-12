"""V2-9.8B post-repair full-run WINDOW_15M accounting and terminal evidence.

This module composes the existing campaign ownership, six-unit accounting, and
tracking-reconciliation owners into the exact full-run terminal evidence the
campaign layer needs before it may accept a two-token ``WINDOW_15M`` lifecycle.
It creates no parallel ownership table, no second Scheduler, and no competing
terminal report; every fact is derived from durable rows and sealed identities.

Concerns owned here:

* the immutable ``OperationalLifecycleOwnershipContext`` passed coordinator ->
  factory (identity flow and factory-run drift detection);
* the exact campaign slot terminal disposition (COOLDOWN vs MANUAL_REVIEW);
* the quality-consistency gate between window quality and episode promotion;
* the canonical full-run terminal report and the campaign acceptance gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Callable, Mapping, Sequence

from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    campaign_scheduler_work_id,
    project_campaign_scheduler_job,
)
from printer_v1.operator_cli.campaign_persistence import (
    AUTHORIZATION_MARKER_KIND,
    AUTHORIZATION_MARKER_VERSION,
    build_authorization_marker_payload,
    campaign_evidence_sha256,
    canonical_campaign_evidence_json,
)
from printer_v1.operator_cli.campaign_supervision import (
    INVOCATION_MARKER_KIND,
    INVOCATION_MARKER_VERSION,
    build_invocation_marker_payload,
)
from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignActionLocalLedger,
    CampaignSixUnitOwner,
    build_campaign_stage_id,
    reconcile_full_run_owner_to_action_local,
    seal_campaign_stage_evidence,
)
from printer_v1.sources.measured_transport import (
    LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND,
    PRECLOSE_CONTEXT_REQUEST_COUNT,
    LifecycleReservationIdentity,
    LocalValidationIdentity,
    MeasuredTransportLedger,
    SchedulerWorkIdentity,
    TransportOperationIdentity,
    build_transport_identity,
    merge_transport_payload_metadata,
)
from printer_v1.snapshots.cadence_policy import get_policy as get_cadence_policy


class FullRunAccountingError(ValueError):
    """Fail-closed full-run accounting/ownership fault."""


# Mandatory sealed lifecycle stages for a lifecycle-started two-token run.
REQUIRED_LIFECYCLE_STAGE_KINDS = (
    "DISCOVERY_SELECTION_SCHEDULER",
    "WINDOW_15M_SLOT_1",
    "WINDOW_15M_SLOT_2",
    "CAMPAIGN_TERMINAL_RECONCILIATION",
)

# Terminal campaign-window states that count as a genuine closed lifecycle.
_OWNED_TERMINAL_WINDOW_STATES = frozenset(
    {"CLEAN_PROMOTED", "DIRTY", "NO_PROMOTION", "ALREADY_EXISTS_IDEMPOTENT"}
)

# Runtime acceptance verdicts kept distinct from runtime terminal + quality.
VERDICT_PASS = "CAMPAIGN_PASS"
VERDICT_HONEST_BLOCKED = "HONEST_BLOCKED"
VERDICT_BLOCKED_UNSAFE = "BLOCKED_UNSAFE"

EVIDENCE_MODE_AUTHORIZED_OPERATIONAL = "AUTHORIZED_OPERATIONAL"
EVIDENCE_MODE_DISPOSABLE_PUBLIC_COMPOSITION_PROOF = (
    "DISPOSABLE_PUBLIC_COMPOSITION_PROOF"
)

# Clean-memory promotion is only lawful for a fully clean window.
_CLEAN_MEMORY_STATUS = "CLEAN_MEMORY"
_CLEAN_DATA_LABEL = "CLEAN_DATA"
_CLEAN_EPISODE_KIND = "WINDOW_15M_CLEAN_MEMORY"


def _require(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise FullRunAccountingError(f"{label} is required")
    return text


def project_lifecycle_reservation_outcomes(
    *,
    transport_records: Sequence[Mapping[str, Any]],
    reserved_count: int,
    owned_lifecycle_stage_ids: Sequence[str],
    factory_run_id: str,
) -> dict[str, Any]:
    """Project lifecycle reservation outcomes without campaign-scope leakage.

    Campaign-wide transports remain untouched. Only transports owned by the two
    sealed WINDOW_15M lifecycle stages participate here, and every such attempt
    must carry an exact reservation linkage to the authoritative factory run.
    """
    reserved = int(reserved_count)
    if reserved < 0:
        raise FullRunAccountingError("negative lifecycle reservation count")
    factory = _require(factory_run_id, "factory_run_id")
    stage_ids = {
        str(value).strip()
        for value in owned_lifecycle_stage_ids
        if str(value).strip()
    }

    attempted = 0
    succeeded = 0
    failed = 0
    malformed_linkage_count = 0
    duplicate_reservation_linkage_count = 0
    unexpected_outcome_count = 0
    seen_links: set[str] = set()

    for item in transport_records:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("stage") or "") not in stage_ids:
            continue
        attempted += 1
        link = str(item.get("reserved_from") or "").strip()
        prefix = f"{factory}:"
        valid_link = link.startswith(prefix)
        if valid_link:
            remainder = link[len(prefix):]
            parts = remainder.rsplit(":reservation:", 1)
            valid_link = (
                len(parts) == 2
                and bool(parts[0].strip())
                and parts[1].isdigit()
                and int(parts[1]) > 0
            )
        if not valid_link:
            malformed_linkage_count += 1
        elif link in seen_links:
            duplicate_reservation_linkage_count += 1
            malformed_linkage_count += 1
        else:
            seen_links.add(link)

        result = str(item.get("result") or "")
        if result == "SUCCEEDED":
            succeeded += 1
        elif result == "FAILED":
            failed += 1
        else:
            unexpected_outcome_count += 1

    complete = bool(
        stage_ids
        and reserved >= attempted > 0
        and attempted == succeeded + failed
        and malformed_linkage_count == 0
        and unexpected_outcome_count == 0
    )
    return {
        "reserved": reserved,
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": failed,
        "malformed_linkage_count": malformed_linkage_count,
        "duplicate_reservation_linkage_count": (
            duplicate_reservation_linkage_count
        ),
        "unexpected_outcome_count": unexpected_outcome_count,
        "complete": complete,
    }


def _load_json_object(raw: Any) -> dict[str, Any] | None:
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def parse_durable_timestamp(value: Any) -> datetime | None:
    """Parse a durable ISO-8601 timestamp; ``None`` unless non-empty + tz-aware.

    This is the single owner of the durable cleanup/lease timestamp contract. A
    non-string, empty, malformed, or timezone-naive value returns ``None`` so the
    acceptance gate and the public replay gate reject it identically. No timestamp
    is ever invented here.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def durable_cleanup_release_timestamps_valid(
    cleanup_completed_at: Any, lease_released_at: Any
) -> bool:
    """True only when both durable timestamps parse tz-aware and release>=cleanup.

    Missing, null, malformed, timezone-naive, or chronologically inverted
    timestamps (a lease released before cleanup completion) all fail closed.
    """
    completed = parse_durable_timestamp(cleanup_completed_at)
    released = parse_durable_timestamp(lease_released_at)
    if completed is None or released is None:
        return False
    return released >= completed


def load_authorization_invocation_evidence(
    connection: sqlite3.Connection,
    *,
    context: "OperationalLifecycleOwnershipContext",
    execution_id: str,
    supervision_id: str,
) -> dict[str, Any]:
    """Load and reconstruct both markers from their existing durable owners."""
    connection.row_factory = sqlite3.Row
    config_row = connection.execute(
        """SELECT cfg.configuration_hash,cfg.configuration_json,
                  cfg.launch_provenance_json,c.policy_version,
                  c.db_target_identity
           FROM printer_memory_factory_campaign_configurations AS cfg
           JOIN printer_memory_factory_campaigns AS c
             ON c.campaign_id=cfg.campaign_id
           WHERE cfg.campaign_id=? AND cfg.configuration_id=?""",
        (context.campaign_id, context.configuration_id),
    ).fetchone()
    expected_authorization: dict[str, Any] | None = None
    stored_authorization: dict[str, Any] | None = None
    stored_authorization_sha256: str | None = None
    authorization_sha256: str | None = None
    marker_id_count = 0
    exact_authorization_count = 0
    authorization_marker_id = f"{execution_id}-authorization-marker"
    if config_row is not None:
        configuration = _load_json_object(config_row["configuration_json"])
        provenance = _load_json_object(config_row["launch_provenance_json"])
        if configuration is not None:
            candidate = configuration.get("authorization_marker")
            if isinstance(candidate, Mapping):
                stored_authorization = dict(candidate)
            candidate_digest = configuration.get("authorization_marker_sha256")
            if isinstance(candidate_digest, str):
                stored_authorization_sha256 = candidate_digest
        if provenance is not None:
            try:
                expected_authorization = build_authorization_marker_payload(
                    marker_id=authorization_marker_id,
                    execution_id=execution_id,
                    campaign_id=context.campaign_id,
                    configuration_id=context.configuration_id,
                    run_id=context.campaign_run_id,
                    policy_version=str(config_row["policy_version"]),
                    db_target_identity=str(config_row["db_target_identity"]),
                    launch_git_provenance=provenance,
                    operator_approved=True,
                )
                authorization_sha256 = campaign_evidence_sha256(
                    expected_authorization
                )
            except Exception:
                expected_authorization = None
                authorization_sha256 = None

    for row in connection.execute(
        """SELECT configuration_json
           FROM printer_memory_factory_campaign_configurations
           ORDER BY configuration_id"""
    ).fetchall():
        payload = _load_json_object(row["configuration_json"])
        marker = None if payload is None else payload.get("authorization_marker")
        if not isinstance(marker, Mapping):
            continue
        if str(marker.get("marker_id") or "") == authorization_marker_id:
            marker_id_count += 1
            if (
                expected_authorization is not None
                and canonical_campaign_evidence_json(marker)
                == canonical_campaign_evidence_json(expected_authorization)
                and payload.get("authorization_marker_sha256")
                == campaign_evidence_sha256(marker)
            ):
                exact_authorization_count += 1

    supervision_rows = connection.execute(
        """SELECT supervision_id,campaign_id,configuration_id,run_id,owner_id,
                  lease_lock_path,created_at,supervision_state,terminal_status,
                  cleanup_completed_at,lease_released_at
           FROM printer_memory_factory_campaign_supervision
           WHERE campaign_id=?
           ORDER BY created_at,supervision_id""",
        (context.campaign_id,),
    ).fetchall()
    exact_supervision_rows = [
        row for row in supervision_rows
        if str(row["supervision_id"]) == str(supervision_id)
        and str(row["configuration_id"]) == context.configuration_id
        and str(row["run_id"]) == context.campaign_run_id
    ]
    invocation_payload: dict[str, Any] | None = None
    invocation_sha256: str | None = None
    if len(exact_supervision_rows) == 1 and expected_authorization is not None:
        try:
            invocation_payload = build_invocation_marker_payload(
                dict(exact_supervision_rows[0]),
                authorization_marker_id=authorization_marker_id,
            )
            invocation_sha256 = campaign_evidence_sha256(invocation_payload)
        except Exception:
            invocation_payload = None
            invocation_sha256 = None

    binding_count = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_runs
           WHERE campaign_id=? AND run_id=? AND authoritative_run_id=?""",
        (context.campaign_id, context.campaign_run_id, context.factory_run_id),
    ).fetchone()[0])
    campaign_binding_history_count = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_runs
           WHERE campaign_id=? AND authoritative_run_id IS NOT NULL""",
        (context.campaign_id,),
    ).fetchone()[0])
    marker_correspondence_exact = bool(
        expected_authorization is not None
        and stored_authorization == expected_authorization
        and stored_authorization_sha256 == authorization_sha256
        and invocation_payload is not None
        and invocation_payload.get("authorization_marker_id")
        == authorization_marker_id
        and invocation_payload.get("campaign_id") == context.campaign_id
        and invocation_payload.get("configuration_id") == context.configuration_id
        and invocation_payload.get("run_id") == context.campaign_run_id
        and invocation_payload.get("supervision_id") == str(supervision_id)
    )
    return {
        "factory_config_hash": None,
        "campaign_configuration_hash": (
            None if config_row is None else str(config_row["configuration_hash"])
        ),
        "authorization_marker": stored_authorization,
        "expected_authorization_marker": expected_authorization,
        "authorization_marker_sha256": authorization_sha256,
        "stored_authorization_marker_sha256": stored_authorization_sha256,
        "authorization_marker_kind": AUTHORIZATION_MARKER_KIND,
        "authorization_marker_version": AUTHORIZATION_MARKER_VERSION,
        "authorization_count": marker_id_count,
        "exact_authorization_count": exact_authorization_count,
        "invocation_marker": invocation_payload,
        "invocation_marker_sha256": invocation_sha256,
        "invocation_marker_kind": INVOCATION_MARKER_KIND,
        "invocation_marker_version": INVOCATION_MARKER_VERSION,
        "invocation_count": len(exact_supervision_rows),
        "supervision_history_count": len(supervision_rows),
        "additional_supervision_history_count": max(0, len(supervision_rows) - 1),
        "factory_binding_count": binding_count,
        "campaign_factory_binding_history_count": campaign_binding_history_count,
        "marker_correspondence_exact": marker_correspondence_exact,
        "configuration_supervision_binding_correspondence_exact": bool(
            marker_correspondence_exact
            and len(exact_supervision_rows) == 1
            and binding_count == 1
            and campaign_binding_history_count == 1
        ),
    }


def load_invocation_authority_evidence(
    connection: sqlite3.Connection,
    *,
    context: "OperationalLifecycleOwnershipContext",
    execution_id: str,
    supervision_id: str,
) -> dict[str, Any]:
    """Load production authorization or C8 proof authority from durable owners.

    Dispatch is owned only by the configuration-owned database target kind.
    """
    from printer_v1.db.migrate import (
        canonical_migration_count,
        canonical_migration_names,
    )
    from printer_v1.operator_cli.operational_database_target_binding import (
        DISPOSABLE_PUBLIC_COMPOSITION_PROOF,
        DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_VERSION,
    )
    from printer_v1.operator_cli.proof_db_schema_readiness import (
        CANONICAL_PERSISTENT_DB,
    )

    connection.row_factory = sqlite3.Row
    config_row = connection.execute(
        "SELECT cfg.configuration_hash,cfg.configuration_json,c.db_target_identity "
        "FROM printer_memory_factory_campaign_configurations AS cfg "
        "JOIN printer_memory_factory_campaigns AS c "
        "ON c.campaign_id=cfg.campaign_id "
        "WHERE cfg.campaign_id=? AND cfg.configuration_id=?",
        (context.campaign_id, context.configuration_id),
    ).fetchone()
    configuration = (
        None
        if config_row is None
        else _load_json_object(config_row["configuration_json"])
    )
    expectation = (
        None
        if not isinstance(configuration, Mapping)
        else configuration.get("operational_database_target_expectation")
    )
    if (
        not isinstance(expectation, Mapping)
        or str(expectation.get("target_kind") or "")
        != DISPOSABLE_PUBLIC_COMPOSITION_PROOF
    ):
        production = load_authorization_invocation_evidence(
            connection,
            context=context,
            execution_id=execution_id,
            supervision_id=supervision_id,
        )
        production["evidence_mode"] = EVIDENCE_MODE_AUTHORIZED_OPERATIONAL
        return production

    proof_expectation = dict(expectation)
    supervision_rows = connection.execute(
        "SELECT supervision_id,campaign_id,configuration_id,run_id,owner_id,"
        "lease_lock_path,created_at,supervision_state,terminal_status,"
        "cleanup_completed_at,lease_released_at "
        "FROM printer_memory_factory_campaign_supervision "
        "WHERE campaign_id=? ORDER BY created_at,supervision_id",
        (context.campaign_id,),
    ).fetchall()
    exact_supervision_rows = [
        row
        for row in supervision_rows
        if str(row["supervision_id"]) == str(supervision_id)
        and str(row["campaign_id"]) == context.campaign_id
        and str(row["configuration_id"]) == context.configuration_id
        and str(row["run_id"]) == context.campaign_run_id
    ]
    binding_rows = connection.execute(
        "SELECT campaign_id,run_id,authoritative_run_id "
        "FROM printer_memory_factory_campaign_runs "
        "WHERE campaign_id=? ORDER BY run_id",
        (context.campaign_id,),
    ).fetchall()
    exact_binding_rows = [
        row
        for row in binding_rows
        if str(row["run_id"]) == context.campaign_run_id
        and str(row["authoritative_run_id"] or "") == context.factory_run_id
    ]
    campaign_binding_history_count = sum(
        1 for row in binding_rows if row["authoritative_run_id"] is not None
    )

    forbidden_expectation_keys = [
        str(key)
        for key in proof_expectation
        if str(key).startswith("authorization")
        or str(key) == "application_marker_sha256"
    ]
    configuration_has_authorization = bool(
        isinstance(configuration, Mapping)
        and (
            "authorization_marker" in configuration
            or "authorization_marker_sha256" in configuration
        )
    )
    reuse_fields = (
        "provider_execution_allowed",
        "automatic_retry_allowed",
        "manual_rerun_allowed",
        "resume_allowed",
        "restart_allowed",
        "successor_allowed",
    )
    no_provider_or_reuse = all(
        proof_expectation.get(field) is False for field in reuse_fields
    )

    expected_runtime = {
        "execution_id": str(execution_id),
        "campaign_id": context.campaign_id,
        "campaign_run_id": context.campaign_run_id,
        "cycle_id": context.cycle_id,
        "configuration_id": context.configuration_id,
        "durable_db_target_identity": (
            None if config_row is None else str(config_row["db_target_identity"])
        ),
    }
    runtime_identity_exact = all(
        str(proof_expectation.get(field) or "") == str(value or "")
        for field, value in expected_runtime.items()
    )
    expected_sha = str(proof_expectation.get("pre_mutation_db_sha256") or "")
    expected_db_identity = str(
        proof_expectation.get("durable_db_target_identity") or ""
    )
    proof_db_path = Path(
        str(proof_expectation.get("resolved_db_path") or "")
    ).resolve()
    canonical_db_path = Path(CANONICAL_PERSISTENT_DB).resolve()
    migration_exact = bool(
        int(proof_expectation.get("migration_count", -1))
        == canonical_migration_count()
        and str(proof_expectation.get("migration_head") or "")
        == canonical_migration_names()[-1]
    )
    proof_expectation_exact = bool(
        proof_expectation.get("expectation_version")
        == DISPOSABLE_PUBLIC_COMPOSITION_PROOF_EXPECTATION_VERSION
        and proof_expectation.get("target_kind")
        == DISPOSABLE_PUBLIC_COMPOSITION_PROOF
        and runtime_identity_exact
        and expected_sha
        and expected_db_identity == f"sha256:{expected_sha}"
        and proof_db_path != canonical_db_path
        and migration_exact
    )

    exact_supervision = (
        dict(exact_supervision_rows[0])
        if len(exact_supervision_rows) == 1
        else None
    )
    proof_invocation_evidence = {
        "evidence_kind": "DISPOSABLE_PUBLIC_COMPOSITION_PROOF_INVOCATION_EVIDENCE_V1",
        "proof_id": proof_expectation.get("proof_id"),
        "proof_schema_version": proof_expectation.get("proof_schema_version"),
        "execution_id": str(execution_id),
        "campaign_id": context.campaign_id,
        "campaign_run_id": context.campaign_run_id,
        "cycle_id": context.cycle_id,
        "configuration_id": context.configuration_id,
        "supervision_id": str(supervision_id),
        "factory_run_id": context.factory_run_id,
        "durable_db_target_identity": expected_db_identity,
        "fixture_composition_manifest_sha256": proof_expectation.get(
            "fixture_composition_manifest_sha256"
        ),
        "supervision": exact_supervision,
        "factory_binding_count": len(exact_binding_rows),
        "campaign_factory_binding_history_count": campaign_binding_history_count,
    }
    proof_invocation_identity_exact = bool(
        exact_supervision is not None
        and str(exact_supervision.get("campaign_id") or "")
        == context.campaign_id
        and str(exact_supervision.get("configuration_id") or "")
        == context.configuration_id
        and str(exact_supervision.get("run_id") or "")
        == context.campaign_run_id
        and str(exact_supervision.get("supervision_id") or "")
        == str(supervision_id)
        and runtime_identity_exact
    )
    proof_supervision_factory_correspondence_exact = bool(
        proof_invocation_identity_exact
        and len(exact_supervision_rows) == 1
        and len(supervision_rows) == 1
        and len(exact_binding_rows) == 1
        and campaign_binding_history_count == 1
    )
    proof_no_authorization_facts = bool(
        not forbidden_expectation_keys and not configuration_has_authorization
    )
    manifest = str(
        proof_expectation.get("fixture_composition_manifest_sha256") or ""
    )
    registry = str(proof_expectation.get("composition_registry_sha256") or "")
    proof_manifest_exact = bool(
        len(manifest) == 64
        and all(ch in "0123456789abcdef" for ch in manifest)
        and len(registry) == 64
        and all(ch in "0123456789abcdef" for ch in registry)
        and proof_invocation_evidence[
            "fixture_composition_manifest_sha256"
        ] == manifest
    )

    proof_expectation_sha256 = campaign_evidence_sha256(proof_expectation)
    proof_invocation_evidence_sha256 = campaign_evidence_sha256(
        proof_invocation_evidence
    )
    return {
        "evidence_mode": EVIDENCE_MODE_DISPOSABLE_PUBLIC_COMPOSITION_PROOF,
        "factory_config_hash": None,
        "campaign_configuration_hash": (
            None if config_row is None else str(config_row["configuration_hash"])
        ),
        "authorization_marker": None,
        "expected_authorization_marker": None,
        "authorization_marker_sha256": None,
        "stored_authorization_marker_sha256": None,
        "authorization_count": 0,
        "exact_authorization_count": 0,
        "invocation_marker": None,
        "invocation_marker_sha256": None,
        "invocation_count": len(exact_supervision_rows),
        "supervision_history_count": len(supervision_rows),
        "additional_supervision_history_count": max(
            0, len(supervision_rows) - 1
        ),
        "factory_binding_count": len(exact_binding_rows),
        "campaign_factory_binding_history_count": (
            campaign_binding_history_count
        ),
        "proof_expectation": proof_expectation,
        "proof_expectation_sha256": proof_expectation_sha256,
        "proof_invocation_evidence": proof_invocation_evidence,
        "proof_invocation_evidence_sha256": (
            proof_invocation_evidence_sha256
        ),
        "proof_expectation_exact": proof_expectation_exact,
        "proof_invocation_identity_exact": proof_invocation_identity_exact,
        "proof_supervision_factory_correspondence_exact": (
            proof_supervision_factory_correspondence_exact
        ),
        "proof_no_authorization_facts": proof_no_authorization_facts,
        "proof_no_provider_or_reuse_permission": no_provider_or_reuse,
        "proof_manifest_exact": proof_manifest_exact,
    }


def load_cleanup_lease_evidence(
    connection: sqlite3.Connection,
    *,
    context: "OperationalLifecycleOwnershipContext",
    supervision_id: str,
    cleanup_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Cross-check the real cleanup result with durable supervision read-back."""
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """SELECT supervision_id,campaign_id,configuration_id,run_id,owner_id,
                  supervision_state,terminal_status,cleanup_completed_at,
                  lease_released_at,lease_lock_path
           FROM printer_memory_factory_campaign_supervision
           WHERE supervision_id=? AND campaign_id=? AND configuration_id=?
             AND run_id=?""",
        (
            supervision_id,
            context.campaign_id,
            context.configuration_id,
            context.campaign_run_id,
        ),
    ).fetchone()
    cleanup = dict(cleanup_result) if isinstance(cleanup_result, Mapping) else {}
    cleanup_identity_exact = bool(
        row is not None
        and all(
            str(cleanup.get(field) or "") == str(row[field])
            for field in (
                "supervision_id", "campaign_id", "configuration_id", "run_id",
                "owner_id",
            )
        )
    )
    lease_path = None if row is None else str(row["lease_lock_path"])
    lease_lock_absent = bool(lease_path) and not Path(str(lease_path)).exists()
    return {
        "cleanup_result_present": isinstance(cleanup_result, Mapping),
        "cleanup_identity": {
            field: cleanup.get(field)
            for field in (
                "supervision_id", "campaign_id", "configuration_id", "run_id",
                "owner_id",
            )
        },
        "cleanup_identity_exact": cleanup_identity_exact,
        "cleanup_completed": cleanup.get("cleanup_completed"),
        "lease_released": cleanup.get("lease_released"),
        "active_owned_work_after": cleanup.get("active_owned_work_after"),
        "durable_supervision": None if row is None else dict(row),
        "durable_terminal_supervision": bool(
            row is not None and str(row["supervision_state"]) == "TERMINAL"
        ),
        "durable_cleanup_completed_at": (
            None if row is None else row["cleanup_completed_at"]
        ),
        "lease_released_at": None if row is None else row["lease_released_at"],
        "lease_lock_path": lease_path,
        "lease_lock_absent": lease_lock_absent,
    }


@dataclass(frozen=True)
class OperationalLifecycleOwnershipContext:
    """Immutable identity context passed coordinator -> driver -> factory.

    The factory may read this context but may not replace any identity. If the
    factory-run callback later observes a different non-empty factory run id, the
    campaign fails closed via :meth:`assert_factory_run_consistent`.
    """

    campaign_id: str
    campaign_run_id: str
    cycle_id: str
    configuration_id: str
    factory_run_id: str
    expected_window_kind: str = "WINDOW_15M"
    expected_token_capacity: int = 2

    def __post_init__(self) -> None:
        for label, value in (
            ("campaign_id", self.campaign_id),
            ("campaign_run_id", self.campaign_run_id),
            ("cycle_id", self.cycle_id),
            ("configuration_id", self.configuration_id),
            ("factory_run_id", self.factory_run_id),
        ):
            _require(value, label)
        if self.expected_window_kind != "WINDOW_15M":
            raise FullRunAccountingError(
                "expected_window_kind must be WINDOW_15M for this lane"
            )
        if int(self.expected_token_capacity) != 2:
            raise FullRunAccountingError(
                "expected_token_capacity must be exactly 2 for this lane"
            )

    def assert_factory_run_consistent(self, observed_factory_run_id: str | None) -> None:
        """Fail closed when a non-empty observed factory run differs from ours."""
        observed = str(observed_factory_run_id or "").strip()
        if observed and observed != self.factory_run_id:
            raise FullRunAccountingError(
                "FACTORY_RUN_IDENTITY_DRIFT:"
                f"{observed}!={self.factory_run_id}"
            )

    def lifecycle_operation_identity(
        self,
        *,
        token_id: int,
        token_mint: str,
        pair_id: int,
        pair_address: str,
        window_kind: str,
        step_id: Any,
    ) -> dict[str, Any]:
        """Build a cross-run-safe lifecycle operation identity (design §5)."""
        return {
            "campaign_id": self.campaign_id,
            "campaign_run_id": self.campaign_run_id,
            "cycle_id": self.cycle_id,
            "factory_run_id": self.factory_run_id,
            "token_id": int(token_id),
            "token_mint": _require(token_mint, "token_mint"),
            "pair_id": int(pair_id),
            "pair_address": _require(pair_address, "pair_address"),
            "window_kind": _require(window_kind, "window_kind"),
            "step_id": step_id,
        }


def resolve_campaign_slot_terminal_disposition(
    *,
    lifecycle_started: bool,
    owned_terminal_window_state: str | None,
    queue_disposition: str | None,
    first_terminal_cause: str | None = None,
) -> dict[str, Any]:
    """Map proven lifecycle ownership to one exact campaign slot terminal state.

    The tracking queue keeps its own status; this only chooses the campaign slot
    terminal label (design §12). A completed owned lifecycle is never relabelled
    ``MANUAL_REVIEW``; a clean main terminal that entered queue ``COOLDOWN``
    mirrors ``COOLDOWN`` on the slot.
    """
    owned_terminal = (
        owned_terminal_window_state is not None
        and str(owned_terminal_window_state) in _OWNED_TERMINAL_WINDOW_STATES
    )
    if not lifecycle_started:
        # No lifecycle proven: a still-SELECTED slot may be sent to review.
        return {
            "slot_terminal_state": "MANUAL_REVIEW",
            "terminal_cause": first_terminal_cause or "NO_LIFECYCLE_STARTED",
            "pass_eligible": False,
            "queue_disposition": queue_disposition,
        }
    if owned_terminal:
        if str(queue_disposition or "") == "COOLDOWN":
            return {
                "slot_terminal_state": "COOLDOWN",
                "terminal_cause": "OWNED_TERMINAL_WINDOW_COOLDOWN",
                "pass_eligible": True,
                "queue_disposition": queue_disposition,
            }
        if str(queue_disposition or "") == "ARCHIVED":
            return {
                "slot_terminal_state": "ARCHIVED",
                "terminal_cause": "OWNED_TERMINAL_WINDOW_ARCHIVED",
                "pass_eligible": True,
                "queue_disposition": queue_disposition,
            }
        # An owned terminal window does not authorize inventing a queue result.
        return {
            "slot_terminal_state": "FAILED",
            "terminal_cause": "OWNED_TERMINAL_WINDOW_QUEUE_STATE_UNPROVEN",
            "pass_eligible": False,
            "queue_disposition": queue_disposition,
        }
    # Lifecycle started but no valid owned terminal window exists.
    cause = str(first_terminal_cause or "").strip()
    if cause.startswith("FAIL") or cause.startswith("BLOCK"):
        return {
            "slot_terminal_state": "FAILED",
            "terminal_cause": cause,
            "pass_eligible": False,
            "queue_disposition": queue_disposition,
        }
    return {
        "slot_terminal_state": "MANUAL_REVIEW",
        "terminal_cause": cause or "LIFECYCLE_WITHOUT_OWNED_TERMINAL_WINDOW",
        "pass_eligible": False,
        "queue_disposition": queue_disposition,
    }


def evaluate_quality_consistency(
    *,
    memory_status: str,
    data_quality_label: str,
    do_not_train: int,
    proposed_episode_kind: str | None,
) -> dict[str, Any]:
    """Gate clean-memory episode creation on exact window quality (design §13).

    Lifecycle completion stays valid even for a partial/dirty window; only clean
    promotion is gated. A ``WINDOW_15M_CLEAN_MEMORY`` episode attached to a
    non-clean window is a quality inconsistency (blocks clean acceptance) but
    never erases the real lifecycle outcome.

    Clean-candidate window status is aligned with E2Z
    (``e2z_clean_memory_creation``): operational clean promotion requires
    ``PARTIAL_MEMORY`` + ``CLEAN_DATA`` + ``do_not_train=0`` on the window row
    (the window is not rewritten to ``CLEAN_MEMORY``). Legacy rows already
    labeled ``CLEAN_MEMORY`` remain accepted as clean candidates.
    """
    status = str(memory_status or "")
    label = str(data_quality_label or "")
    dnt = int(do_not_train or 0)
    # E2Z clean-candidate status is PARTIAL_MEMORY; CLEAN_MEMORY is legacy.
    is_clean_window = (
        status in {_CLEAN_MEMORY_STATUS, "PARTIAL_MEMORY"}
        and label == _CLEAN_DATA_LABEL
        and dnt == 0
    )
    proposed = None if proposed_episode_kind is None else str(proposed_episode_kind)
    clean_episode_allowed = is_clean_window
    quality_consistent = True
    outcome: str
    if proposed == _CLEAN_EPISODE_KIND and not is_clean_window:
        quality_consistent = False
        outcome = "QUALITY_CONSISTENCY_BLOCKED"
    elif is_clean_window and proposed == _CLEAN_EPISODE_KIND:
        outcome = "CLEAN_EPISODE_ALLOWED"
    elif is_clean_window:
        outcome = "CLEAN_EPISODE_ALLOWED"
    else:
        outcome = "NO_CLEAN_EPISODE_CREATED"
    return {
        "memory_status": status,
        "data_quality_label": label,
        "do_not_train": dnt,
        "is_clean_window": is_clean_window,
        "clean_episode_allowed": clean_episode_allowed,
        "proposed_episode_kind": proposed,
        "quality_consistent": quality_consistent,
        "outcome": outcome,
        "lifecycle_completion_valid": True,
    }


def _campaign_window_rows(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT window_id, window_kind, window_state, token_slot_id, token_row_id,
                  pair_row_id, memory_window_row_id, cycle_id, first_terminal_cause
           FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY window_id""",
        (campaign_id, run_id, cycle_id),
    ).fetchall()
    return [dict(row) for row in rows]


def _campaign_scheduler_rows(
    connection: sqlite3.Connection,
    *,
    campaign_id: str,
    run_id: str,
    cycle_id: str,
) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT scheduler_work_id, scheduler_job_id, work_intent, work_state,
                  window_id, token_slot_id, first_terminal_cause, terminal_at,
                  ownership_contract_version, stage_id, work_scope,
                  target_category, target_identity, factory_run_id
           FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
           ORDER BY scheduler_work_id""",
        (campaign_id, run_id, cycle_id),
    ).fetchall()
    return [dict(row) for row in rows]


def build_full_run_terminal_report(
    connection: sqlite3.Connection,
    *,
    context: OperationalLifecycleOwnershipContext,
    execution_id: str,
    supervision_id: Any,
    launch_git_provenance: Mapping[str, Any],
    db_target_identity: str,
    selected_tokens: Sequence[Mapping[str, Any]],
    runtime_terminal_status: str,
    owner_evidence: Mapping[str, Any],
    action_local_evidence: Mapping[str, Any],
    six_unit_totals: Mapping[str, int],
    reconciliation: Mapping[str, Any],
    per_token_outcomes: Sequence[Mapping[str, Any]],
    slot_dispositions: Sequence[Mapping[str, Any]],
    quality_results: Sequence[Mapping[str, Any]],
    zero_active_scheduler_jobs: int,
    forbidden_capability_deltas: Mapping[str, int],
    authorization_invocation_evidence: Mapping[str, Any] | None = None,
    cleanup_lease_evidence: Mapping[str, Any] | None = None,
    scheduler_ownership: Mapping[str, Any] | None = None,
    runtime_first_terminal_cause: str | None = None,
    active_work_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit the one canonical exact-identity full-run terminal report (design §10)."""
    windows = _campaign_window_rows(
        connection,
        campaign_id=context.campaign_id,
        run_id=context.campaign_run_id,
        cycle_id=context.cycle_id,
    )
    scheduler_rows = _campaign_scheduler_rows(
        connection,
        campaign_id=context.campaign_id,
        run_id=context.campaign_run_id,
        cycle_id=context.cycle_id,
    )
    terminal_windows = [
        row
        for row in windows
        if str(row["window_kind"]) == "WINDOW_15M"
        and str(row["window_state"]) in _OWNED_TERMINAL_WINDOW_STATES
    ]
    factory_identity = connection.execute(
        """SELECT selection_batch_id, config_hash
           FROM printer_memory_factory_runs WHERE run_id=?""",
        (context.factory_run_id,),
    ).fetchone()
    scheduler_attribution: dict[str, int] = {
        "discovery": 0,
        "selection": 0,
        "handoff": 0,
        "lifecycle": 0,
        "cleanup": 0,
    }
    for row in scheduler_rows:
        scope = str(row.get("work_scope") or "")
        if scope == "DISCOVERY_SELECTION":
            if "UNIFORM_SELECTION" in str(row.get("work_intent") or ""):
                scheduler_attribution["selection"] += 1
            else:
                scheduler_attribution["discovery"] += 1
        elif scope == "FIRST_15M_HANDOFF":
            scheduler_attribution["handoff"] += 1
        elif scope == "TERMINAL_CLEANUP":
            scheduler_attribution["cleanup"] += 1
        elif scope == "WINDOW_LIFECYCLE":
            scheduler_attribution["lifecycle"] += 1

    all_scheduler_terminal = bool(scheduler_rows) and all(
        str(row["work_state"]) in {"SUCCEEDED", "FAILED", "SKIPPED", "CANCELLED"}
        for row in scheduler_rows
    )
    quality_consistent = bool(quality_results) and all(
        item.get("quality_consistent") is True for item in quality_results
    )
    forbidden_deltas = {key: int(value) for key, value in dict(
        forbidden_capability_deltas or {}
    ).items()}
    # Scheduler ownership correspondence (design §6): every attributable factory
    # lifecycle step maps to exactly one campaign Scheduler ownership row carrying
    # the job's real terminal state. When the finalize boundary supplies it, the
    # report carries the exact per-job states and the correspondence verdict;
    # when omitted (direct-report unit tests) the correspondence defaults to
    # consistent so those tests exercise the other axes.
    scheduler_ownership = dict(scheduler_ownership or {})
    scheduler_correspondence_ok = bool(
        scheduler_ownership.get("correspondence_exact", False)
    )
    all_lifecycle_jobs_succeeded = bool(
        scheduler_ownership.get("all_lifecycle_jobs_succeeded", False)
    )
    transport_records = list(owner_evidence.get("transport_operations") or [])
    sealed_stage_diagnostics = list(
        owner_evidence.get("sealed_stage_diagnostics")
        or reconciliation.get("diagnostics", {}).get(
            "sealed_stage_diagnostics", []
        )
    )
    lifecycle_stage_ids = [
        str(item.get("stage_id") or "")
        for item in sealed_stage_diagnostics
        if str(item.get("stage_kind") or "")
        in {"WINDOW_15M_SLOT_1", "WINDOW_15M_SLOT_2"}
    ]
    source_operation_outcomes = project_lifecycle_reservation_outcomes(
        transport_records=transport_records,
        reserved_count=int(
            dict(six_unit_totals or {}).get(
                "LIFECYCLE_RESERVED_TRANSPORT_OPERATION", 0
            )
        ),
        owned_lifecycle_stage_ids=lifecycle_stage_ids,
        factory_run_id=context.factory_run_id,
    )
    validation_families = sorted({
        str(item.get("validation_kind") or "")
        for item in (owner_evidence.get("local_validation_identities") or [])
    })
    marker_evidence = dict(authorization_invocation_evidence or {})
    cleanup_evidence = dict(cleanup_lease_evidence or {})
    factory_config_hash = (
        None if factory_identity is None else factory_identity["config_hash"]
    )
    marker_evidence["factory_config_hash"] = factory_config_hash

    return {
        "report_kind": "V2_9_8B_FULL_RUN_WINDOW_15M_TERMINAL_EVIDENCE",
        # 10.1 identity and ownership
        "identity": {
            "execution_id": _require(execution_id, "execution_id"),
            "campaign_id": context.campaign_id,
            "campaign_run_id": context.campaign_run_id,
            "cycle_id": context.cycle_id,
            "configuration_id": context.configuration_id,
            "supervision_id": supervision_id,
            "factory_run_id": context.factory_run_id,
            "factory_config_hash": factory_config_hash,
            "launch_git_provenance": dict(launch_git_provenance or {}),
            "db_target_identity": _require(db_target_identity, "db_target_identity"),
        },
        # 10.2 selection and lifecycle
        "selection_and_lifecycle": {
            "selection_batch_id": (
                None if factory_identity is None else factory_identity["selection_batch_id"]
            ),
            "selected_tokens": [dict(item) for item in selected_tokens],
            "selected_token_count": len(selected_tokens),
            "per_token_outcomes": [dict(item) for item in per_token_outcomes],
            "campaign_window_ownership_rows": windows,
            "terminal_window_ids": [row["window_id"] for row in terminal_windows],
            "terminal_window_count": len(terminal_windows),
            "slot_dispositions": [dict(item) for item in slot_dispositions],
            "quality_results": [dict(item) for item in quality_results],
        },
        # 10.3 full-run accounting
        "full_run_accounting": {
            "accounting_owner_id": owner_evidence.get("owner_id"),
            "action_local_ledger_id": action_local_evidence.get("ledger_id"),
            "owner_evidence": dict(owner_evidence),
            "action_local_evidence": dict(action_local_evidence),
            "expected_stage_manifest": list(REQUIRED_LIFECYCLE_STAGE_KINDS),
            "sealed_stage_diagnostics": sealed_stage_diagnostics,
            "six_unit_totals": {key: int(value) for key, value in dict(
                six_unit_totals or {}
            ).items()},
            "source_operation_outcomes": source_operation_outcomes,
            "named_validation_families": validation_families,
            "owner_action_local_reconciliation": dict(reconciliation),
            "scheduler_attribution": scheduler_attribution,
            "campaign_scheduler_work_rows": scheduler_rows,
            "scheduler_ownership": scheduler_ownership,
            "scheduler_transition_coverage": dict(
                action_local_evidence.get("scheduler_transition_coverage") or {}
            ),
            "scheduler_correspondence_exact": scheduler_correspondence_ok,
            "all_lifecycle_scheduler_jobs_succeeded": all_lifecycle_jobs_succeeded,
            "missing_or_mismatched_evidence": list(
                reconciliation.get("missing_mandatory_stage_kinds") or []
            ),
        },
        "authorization_and_invocation": marker_evidence,
        # 10.4 terminal safety
        "terminal_safety": {
            "campaign_window_reconciliation": {
                "terminal_window_count": len(terminal_windows),
                "all_scheduler_jobs_terminal": all_scheduler_terminal,
            },
            "zero_active_scheduler_jobs": int(zero_active_scheduler_jobs) == 0,
            "active_scheduler_job_count": int(zero_active_scheduler_jobs),
            "active_work_result": dict(active_work_result or {}),
            "cleanup_evidence": cleanup_evidence,
            "cleanup_identity": cleanup_evidence.get("cleanup_identity"),
            "cleanup_identity_exact": cleanup_evidence.get(
                "cleanup_identity_exact"
            ),
            "cleanup_completed": cleanup_evidence.get("cleanup_completed"),
            "durable_terminal_supervision": cleanup_evidence.get(
                "durable_terminal_supervision"
            ),
            "lease_released": cleanup_evidence.get("lease_released"),
            "durable_cleanup_completed_at": cleanup_evidence.get(
                "durable_cleanup_completed_at"
            ),
            "lease_released_at": cleanup_evidence.get("lease_released_at"),
            "lease_lock_path": cleanup_evidence.get("lease_lock_path"),
            "lease_lock_absent": cleanup_evidence.get("lease_lock_absent"),
            "forbidden_capability_deltas": forbidden_deltas,
            "zero_forbidden_deltas": all(
                value == 0 for value in forbidden_deltas.values()
            ),
        },
        # 10.5 acceptance verdict (three distinct axes never collapsed)
        "runtime_terminal_status": str(runtime_terminal_status),
        "runtime_first_terminal_cause": (
            None if runtime_first_terminal_cause is None
            else str(runtime_first_terminal_cause)
        ),
        "memory_quality_outcomes": [
            {
                "window_id": item.get("window_id"),
                "outcome": item.get("outcome"),
                "is_clean_window": item.get("is_clean_window"),
            }
            for item in quality_results
        ],
        "quality_consistency": {
            "consistent": quality_consistent,
        },
    }


def _scheduler_family_attribution_complete(
    accounting: Mapping[str, Any],
) -> bool:
    """Validate Scheduler-family counts against the reported lifecycle family.

    Ordinary WINDOW_15M reports retain the historical eighteen-job contract.
    Standard-four-hour reports carry their exact dynamically observed lifecycle
    count from the durable correspondence proof instead of pretending that the
    legitimate continuation jobs are a second owner.
    """
    ownership = accounting.get("scheduler_ownership", {})
    expected = ownership.get("expected_lifecycle_scheduler_count")
    if expected is None:
        expected = 18
    if type(expected) is not int or expected <= 0:
        return False
    attribution = accounting.get("scheduler_attribution", {})
    return bool(
        int(attribution.get("discovery") or 0) >= 1
        and int(attribution.get("selection") or 0) >= 1
        and int(attribution.get("handoff") or 0) == 2
        and int(attribution.get("lifecycle") or 0) == expected
    )


def _no_retry_restart_resume_successor(
    *,
    cleanup_truth_complete: bool,
    scheduler_retry_count: int,
    automatic_retry_count: int,
    restart_count: int,
    resume_count: int,
    successor_count: int,
    bound_run_count: int,
) -> bool:
    """Return campaign-level replay truth without conflating job attempts.

    ``printer_scheduler_jobs.retry_count`` remains terminal evidence, but it is
    job-attempt accounting rather than proof that the campaign automatically
    retried, restarted, resumed, or created a successor.
    """
    _ = scheduler_retry_count
    return bool(
        cleanup_truth_complete
        and automatic_retry_count == 0
        and restart_count == 0
        and resume_count == 0
        and successor_count == 0
        and bound_run_count == 1
    )


def evaluate_campaign_acceptance_gate(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the campaign acceptance gate to a full-run terminal report (§11).

    Campaign PASS is impossible unless every condition holds. Lifecycle completion
    for a partial/dirty window is still valid, but a *quality inconsistency* — a
    clean episode attached to a non-clean window — is a hard blocker, as is a
    non-completed runtime status, an authorization count that is not exactly one,
    an unreleased lease, or a Scheduler ownership correspondence fault. Returns the
    verdict plus every check.
    """
    selection = report.get("selection_and_lifecycle", {})
    accounting = report.get("full_run_accounting", {})
    safety = report.get("terminal_safety", {})
    markers = report.get("authorization_and_invocation", {})
    reconciliation = accounting.get("owner_action_local_reconciliation", {})

    selected = selection.get("selected_tokens") or []
    distinct_targets = {
        (item.get("token_id"), item.get("pair_id")) for item in selected
    }
    terminal_window_count = int(selection.get("terminal_window_count") or 0)
    slot_dispositions = selection.get("slot_dispositions") or []
    all_slots_pass_eligible = bool(slot_dispositions) and all(
        bool(item.get("pass_eligible")) for item in slot_dispositions
    )
    sealed_kinds = {
        str(item.get("stage_kind") or "")
        for item in (accounting.get("sealed_stage_diagnostics") or [])
    }
    # Every one of the four approved mandatory stages must be sealed and present.
    all_mandatory_stages_sealed = set(REQUIRED_LIFECYCLE_STAGE_KINDS).issubset(
        sealed_kinds
    )
    mandatory_stage_statuses_completed = all(
        str(item.get("stage_terminal_status") or "") == "COMPLETED"
        for item in (accounting.get("sealed_stage_diagnostics") or [])
        if str(item.get("stage_kind") or "") in REQUIRED_LIFECYCLE_STAGE_KINDS
    ) and all_mandatory_stages_sealed
    runtime_status = str(report.get("runtime_terminal_status") or "")
    runtime_terminal_completed = runtime_status in {
        "TERMINAL_COMPLETED",
        "COMPLETED",
    }
    quality_consistent = bool(
        report.get("quality_consistency", {}).get("consistent", False)
    )
    proof_mode = (
        markers.get("evidence_mode")
        == EVIDENCE_MODE_DISPOSABLE_PUBLIC_COMPOSITION_PROOF
    )

    checks = {
        "exactly_one_authorization_marker": (
            type(markers.get("authorization_count")) is int
            and markers.get("authorization_count") == 1
            and type(markers.get("exact_authorization_count")) is int
            and markers.get("exact_authorization_count") == 1
        ),
        "exactly_one_matching_supervision_invocation": (
            type(markers.get("invocation_count")) is int
            and markers.get("invocation_count") == 1
        ),
        "exactly_one_matching_factory_binding": (
            type(markers.get("factory_binding_count")) is int
            and markers.get("factory_binding_count") == 1
            and type(markers.get("campaign_factory_binding_history_count")) is int
            and markers.get("campaign_factory_binding_history_count") == 1
        ),
        "zero_additional_supervision_history": (
            markers.get("supervision_history_count") == 1
            and markers.get("additional_supervision_history_count") == 0
        ),
        "authorization_supervision_binding_correspondence_exact": (
            markers.get("marker_correspondence_exact") is True
            and markers.get(
                "configuration_supervision_binding_correspondence_exact"
            ) is True
        ),
        "marker_payload_identities_exact": bool(
            isinstance(markers.get("authorization_marker"), Mapping)
            and markers.get("authorization_marker")
            == markers.get("expected_authorization_marker")
            and markers.get("authorization_marker", {}).get("campaign_id")
            == report.get("identity", {}).get("campaign_id")
            and markers.get("authorization_marker", {}).get("configuration_id")
            == report.get("identity", {}).get("configuration_id")
            and markers.get("authorization_marker", {}).get("run_id")
            == report.get("identity", {}).get("campaign_run_id")
            and markers.get("authorization_marker", {}).get("execution_id")
            == report.get("identity", {}).get("execution_id")
            and markers.get("authorization_marker", {}).get("operator_approved")
            is True
            and isinstance(markers.get("invocation_marker"), Mapping)
            and markers.get("invocation_marker", {}).get("supervision_id")
            == str(report.get("identity", {}).get("supervision_id") or "")
            and markers.get("invocation_marker", {}).get("campaign_id")
            == report.get("identity", {}).get("campaign_id")
            and markers.get("invocation_marker", {}).get("configuration_id")
            == report.get("identity", {}).get("configuration_id")
            and markers.get("invocation_marker", {}).get("run_id")
            == report.get("identity", {}).get("campaign_run_id")
            and markers.get("invocation_marker", {}).get("owner_id")
            == safety.get("cleanup_identity", {}).get("owner_id")
            and markers.get("invocation_marker", {}).get("owner_id")
            == safety.get("cleanup_evidence", {}).get(
                "durable_supervision", {}
            ).get("owner_id")
            and markers.get("invocation_marker", {}).get(
                "authorization_marker_id"
            ) == markers.get("authorization_marker", {}).get("marker_id")
        ),
        "exactly_two_distinct_selected_targets": len(distinct_targets) == 2
        and len(selected) == 2,
        "exactly_two_terminal_window_15m_lifecycles": terminal_window_count == 2,
        "both_windows_campaign_owned": len(
            selection.get("campaign_window_ownership_rows") or []
        )
        >= 2
        and terminal_window_count == 2,
        "all_mandatory_stages_sealed": all_mandatory_stages_sealed,
        "mandatory_stage_statuses_completed": mandatory_stage_statuses_completed,
        "owner_action_local_equal_non_vacuous": bool(reconciliation.get("equal"))
        and bool(reconciliation.get("lifecycle_started"))
        and reconciliation.get("equality_scoped_stage_ids") is None,
        "all_scheduler_jobs_terminal_and_owned": bool(
            safety.get("campaign_window_reconciliation", {}).get(
                "all_scheduler_jobs_terminal"
            )
        ),
        "scheduler_ownership_correspondence_exact": bool(
            accounting.get("scheduler_correspondence_exact", False)
        ),
        "all_lifecycle_scheduler_jobs_succeeded": bool(
            accounting.get("all_lifecycle_scheduler_jobs_succeeded", False)
        ),
        "complete_scheduler_family_attribution": (
            _scheduler_family_attribution_complete(accounting)
        ),
        "runtime_terminal_completed": runtime_terminal_completed,
        "memory_quality_consistent": quality_consistent,
        "canonical_report_complete": all(
            bool(report.get("identity", {}).get(field))
            for field in (
                "execution_id", "campaign_id", "campaign_run_id", "cycle_id",
                "configuration_id", "supervision_id", "factory_run_id",
                "db_target_identity",
            )
        )
        and bool(selection.get("selection_batch_id"))
        and len(selection.get("terminal_window_ids") or []) == 2
        and all(item.get("cadence") for item in selected)
        and accounting.get("owner_evidence", {}).get("evidence_kind")
        == "CAMPAIGN_SIX_UNIT_EVIDENCE_V2"
        and bool(accounting.get("action_local_evidence"))
        and bool(accounting.get("campaign_scheduler_work_rows"))
        and bool(accounting.get("sealed_stage_diagnostics"))
        and (
            (
                proof_mode
                and isinstance(markers.get("proof_expectation"), Mapping)
                and isinstance(
                    markers.get("proof_invocation_evidence"), Mapping
                )
            )
            or (
                not proof_mode
                and isinstance(markers.get("authorization_marker"), Mapping)
                and isinstance(markers.get("invocation_marker"), Mapping)
            )
        )
        and all(
            key in safety
            for key in (
                "active_scheduler_job_count", "locked_scheduler_job_count",
                "cleanup_identity", "cleanup_completed", "lease_released",
                "durable_cleanup_completed_at",
                "lease_released_at", "lease_lock_absent",
                "forbidden_capability_deltas",
                "scheduler_retry_count", "restart_count", "resume_count",
                "successor_count",
            )
        ),
        "all_slot_dispositions_pass_eligible": all_slots_pass_eligible,
        "persisted_slot_dispositions_exact": bool(slot_dispositions)
        and all(bool(item.get("persisted_state_matches")) for item in slot_dispositions),
        "cadence_coverage_and_close_complete": len(selected) == 2
        and all(
            item.get("cadence", {}).get("coverage_status") == "COMPLETE"
            and int(item.get("cadence", {}).get("missing_snapshot_steps") or 0) == 0
            and int(item.get("cadence", {}).get("succeeded_close_count") or 0) == 1
            for item in selected
        )
        and sum(
            int(item.get("cadence", {}).get("actual_snapshot_steps") or 0)
            for item in selected
        ) == 16,
        "zero_active_scheduler_jobs": bool(safety.get("zero_active_scheduler_jobs")),
        "zero_active_owned_work_after_cleanup": (
            type(safety.get("cleanup_evidence", {}).get(
                "active_owned_work_after"
            )) is int
            and safety.get("cleanup_evidence", {}).get(
                "active_owned_work_after"
            ) == 0
        ),
        "cleanup_evidence_present_and_exact": (
            safety.get("cleanup_evidence", {}).get("cleanup_result_present") is True
            and safety.get("cleanup_identity_exact") is True
        ),
        "cleanup_completed": safety.get("cleanup_completed") is True,
        "lease_released": safety.get("lease_released") is True,
        "durable_terminal_supervision": (
            safety.get("durable_terminal_supervision") is True
        ),
        "durable_cleanup_completion_timestamp_present": bool(
            safety.get("durable_cleanup_completed_at")
        ),
        "durable_lease_release_timestamp_present": bool(
            safety.get("lease_released_at")
        ),
        "durable_cleanup_and_release_timestamps_valid": (
            durable_cleanup_release_timestamps_valid(
                safety.get("durable_cleanup_completed_at"),
                safety.get("lease_released_at"),
            )
        ),
        "lease_lock_absent": safety.get("lease_lock_absent") is True,
        "zero_forbidden_deltas": bool(safety.get("zero_forbidden_deltas")),
        "zero_locked_work": bool(safety.get("zero_locked_work")),
        "scheduler_transition_coverage_complete": bool(
            accounting.get("scheduler_transition_coverage", {}).get("complete")
        ),
        "cleanup_scheduler_observation_exact": bool(
            safety.get("cleanup_scheduler_observation_exact")
        ),
        "reservation_attempt_outcomes_complete": (
            int(accounting.get("source_operation_outcomes", {}).get("reserved") or 0)
            >= int(accounting.get("source_operation_outcomes", {}).get("attempted") or 0)
            > 0
            and int(accounting.get("source_operation_outcomes", {}).get("attempted") or 0)
            == int(accounting.get("source_operation_outcomes", {}).get("succeeded") or 0)
            + int(accounting.get("source_operation_outcomes", {}).get("failed") or 0)
            and int(
                accounting.get("source_operation_outcomes", {}).get(
                    "malformed_linkage_count"
                )
                or 0
            ) == 0
            and int(
                accounting.get("source_operation_outcomes", {}).get(
                    "unexpected_outcome_count"
                )
                or 0
            ) == 0
        ),
        "required_named_validation_families_present": {
            "SELECTION_HANDOFF_VALIDATED",
            "IMMUTABLE_IDENTITY_VALIDATED",
            "CADENCE_DUE_VALIDATED",
            "BUDGET_CAPACITY_VALIDATED",
            "EXACT_PAIR_VERIFICATION",
            "WINDOW_CLOSE_VALIDATED",
            "SNAPSHOT_COVERAGE_VALIDATED",
            "WINDOW_QUALITY_VALIDATED",
            "CAMPAIGN_TERMINAL_OWNERSHIP_VALIDATED",
            "ZERO_ACTIVE_WORK_VALIDATED",
            "ZERO_LOCKED_WORK_VALIDATED",
            "LEASE_RELEASE_VALIDATED",
            "FORBIDDEN_DELTAS_VALIDATED",
            "NO_RETRY_VALIDATED",
            "NO_RESTART_VALIDATED",
            "NO_RESUME_VALIDATED",
            "NO_SUCCESSOR_VALIDATED",
        }.issubset(set(accounting.get("named_validation_families") or [])),
        "no_retry_restart_resume_successor": bool(
            safety.get("no_retry_restart_resume_successor")
        ),
        "marker_and_evidence_hashes_present": all(
            len(str(report.get("hashes", {}).get(key) or "")) == 64
            for key in (
                (
                    "owner_evidence_sha256",
                    "action_local_evidence_sha256",
                    "report_body_sha256",
                    "proof_expectation_sha256",
                    "proof_invocation_evidence_sha256",
                )
                if proof_mode
                else (
                    "owner_evidence_sha256",
                    "action_local_evidence_sha256",
                    "report_body_sha256",
                    "authorization_marker_sha256",
                    "invocation_marker_sha256",
                )
            )
        ),
        "authorization_marker_digest_exact": bool(
            isinstance(markers.get("authorization_marker"), Mapping)
            and report.get("hashes", {}).get("authorization_marker_sha256")
            == campaign_evidence_sha256(markers.get("authorization_marker"))
            and markers.get("stored_authorization_marker_sha256")
            == report.get("hashes", {}).get("authorization_marker_sha256")
        ),
        "invocation_marker_digest_exact": bool(
            isinstance(markers.get("invocation_marker"), Mapping)
            and report.get("hashes", {}).get("invocation_marker_sha256")
            == campaign_evidence_sha256(markers.get("invocation_marker"))
        ),
        "configuration_hash_not_substituted_as_marker": bool(
            report.get("identity", {}).get("factory_config_hash")
            and report.get("hashes", {}).get("authorization_marker_sha256")
            != report.get("identity", {}).get("factory_config_hash")
            and report.get("hashes", {}).get("invocation_marker_sha256")
            != report.get("identity", {}).get("factory_config_hash")
        ),
    }

    if proof_mode:
        for authorization_check in (
            "exactly_one_authorization_marker",
            "authorization_supervision_binding_correspondence_exact",
            "marker_payload_identities_exact",
            "authorization_marker_digest_exact",
            "invocation_marker_digest_exact",
            "configuration_hash_not_substituted_as_marker",
        ):
            checks.pop(authorization_check, None)
        checks.update(
            {
                "proof_expectation_exact": (
                    markers.get("proof_expectation_exact") is True
                ),
                "proof_invocation_identity_exact": (
                    markers.get("proof_invocation_identity_exact") is True
                ),
                "proof_supervision_factory_correspondence_exact": (
                    markers.get(
                        "proof_supervision_factory_correspondence_exact"
                    ) is True
                ),
                "proof_no_authorization_facts": (
                    markers.get("proof_no_authorization_facts") is True
                ),
                "proof_no_provider_or_reuse_permission": (
                    markers.get(
                        "proof_no_provider_or_reuse_permission"
                    ) is True
                ),
                "proof_manifest_exact": (
                    markers.get("proof_manifest_exact") is True
                ),
            }
        )

    lifecycle_started = bool(reconciliation.get("lifecycle_started")) or (
        terminal_window_count > 0
    )
    failing = [name for name, ok in checks.items() if not ok]
    if not failing:
        verdict = VERDICT_PASS
    elif not lifecycle_started:
        verdict = VERDICT_HONEST_BLOCKED
    else:
        verdict = VERDICT_BLOCKED_UNSAFE

    return {
        "verdict": verdict,
        "pass": verdict == VERDICT_PASS,
        "lifecycle_started": lifecycle_started,
        "checks": checks,
        "failing_checks": failing,
        # Memory quality is reported but never lowers the acceptance gate.
        "memory_quality_consistent": bool(
            report.get("quality_consistency", {}).get("consistent", False)
        ),
    }


_LIFECYCLE_SLOT_STAGE_KINDS = ("WINDOW_15M_SLOT_1", "WINDOW_15M_SLOT_2")

# The two distinct outbound-call boundaries the factory reports. Scheduler work
# and lifecycle transport reservation are observed at plan/enqueue time; the
# actual measured source transport and the exact-pair verification validation are
# observed at the real outbound-call boundary.
BOUNDARY_SCHEDULER_ENQUEUE = "SCHEDULER_ENQUEUE"
BOUNDARY_SOURCE_TRANSPORT = "SOURCE_TRANSPORT"

# Projected governed source operations reserved per lifecycle step. A SNAPSHOT
# reserves the one exact-pair observation call it will make; a WINDOW_CLOSE
# reserves the close observation plus the fixed pre-close context bundle. These
# are the step's *actual projected governed operations* — a close reserving many
# calls is never collapsed to one reservation just because it is one Scheduler
# job. ``PRECLOSE_CONTEXT_REQUEST_COUNT`` mirrors the factory's
# ``_CONTEXT_REQUESTS_PER_TOKEN``. Both execution and accounting consume the
# immutable shared transport policy rather than maintaining duplicate counts.
PROJECTED_GOVERNED_OPERATIONS_BY_STEP_KIND = (
    LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND
)
# Lifecycle step kinds that carry an exact-pair source transport identity.
_TRANSPORT_BEARING_STEP_KINDS = frozenset({"SNAPSHOT", "WINDOW_CLOSE"})
_EXACT_PAIR_VALIDATION_KIND = "EXACT_PAIR_VERIFICATION"


def _slot_ordinal_from_step_key(step_key: str) -> int:
    prefix = str(step_key or "").split("_", 1)[0]
    if prefix.startswith("t") and prefix[1:].isdigit():
        ordinal = int(prefix[1:])
        if ordinal in (1, 2):
            return ordinal
    raise FullRunAccountingError(f"cannot derive slot ordinal from step key: {step_key!r}")


def _slot_stage_id(context: OperationalLifecycleOwnershipContext, ordinal: int) -> str:
    return build_campaign_stage_id(
        campaign_id=context.campaign_id,
        run_id=context.campaign_run_id,
        cycle_id=context.cycle_id,
        stage_kind=f"WINDOW_15M_SLOT_{ordinal}",
        stage_sequence=ordinal + 1,
    )


def _terminal_stage_matches(*, window_kind: str, stage_id: str) -> bool:
    if window_kind == "WINDOW_1H":
        return stage_id == "WINDOW_1H"
    if window_kind == "WINDOW_4H":
        return stage_id == "WINDOW_4H"
    if window_kind != "WINDOW_15M":
        return False
    return bool(
        stage_id in {"WINDOW_15M_SLOT_1", "WINDOW_15M_SLOT_2"}
        or stage_id.endswith("|WINDOW_15M_SLOT_1|2")
        or stage_id.endswith("|WINDOW_15M_SLOT_2|3")
    )


def _load_terminal_scheduler_correspondence(
    connection: sqlite3.Connection,
    *,
    context: OperationalLifecycleOwnershipContext,
    standard_four_hour_campaign: bool,
) -> dict[str, Any]:
    """Load exact terminal Scheduler ownership for the active lifecycle family.

    The ordinary path remains WINDOW_15M-only. A standard campaign additionally
    admits the already-owned WINDOW_1H and eligible WINDOW_4H steps, but only
    through exact persisted step -> Scheduler job -> scoped ownership -> campaign
    window lineage. Any missing, duplicate, mismatched, or unowned row fails the
    correspondence closed.
    """
    allowed = {
        "SNAPSHOT": "WINDOW_15M",
        "WINDOW_CLOSE": "WINDOW_15M",
    }
    if standard_four_hour_campaign:
        allowed.update(
            {
                "CONTINUATION_SNAPSHOT": "WINDOW_1H",
                "CONTINUATION_CLOSE": "WINDOW_1H",
                "LONG_CONTINUATION_SNAPSHOT": "WINDOW_4H",
                "LONG_CONTINUATION_CLOSE": "WINDOW_4H",
            }
        )

    placeholders = ",".join("?" for _ in allowed)
    steps = connection.execute(
        f"""SELECT s.id, s.scheduler_job_id, s.step_kind, s.token_id,
                   s.pair_id, s.step_key, j.status AS scheduler_job_status
            FROM printer_memory_factory_run_steps AS s
            LEFT JOIN printer_scheduler_jobs AS j ON j.id=s.scheduler_job_id
            WHERE s.run_id=? AND s.scheduler_job_id IS NOT NULL
              AND s.step_kind IN ({placeholders})
            ORDER BY s.id""",
        (context.factory_run_id, *allowed.keys()),
    ).fetchall()
    owned_rows = connection.execute(
        """SELECT scheduler_job_id, token_slot_id, window_id, work_state,
                  stage_id, target_category, target_identity
           FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=? AND factory_run_id=?
             AND ownership_contract_version='V2_STAGE_SCOPED'
             AND work_scope='WINDOW_LIFECYCLE'
           ORDER BY scheduler_work_id""",
        (
            context.campaign_id,
            context.campaign_run_id,
            context.cycle_id,
            context.factory_run_id,
        ),
    ).fetchall()
    windows = connection.execute(
        """SELECT window_id, token_slot_id, token_row_id, pair_row_id,
                  window_kind
           FROM printer_memory_factory_campaign_windows
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
           ORDER BY window_id""",
        (context.campaign_id, context.campaign_run_id, context.cycle_id),
    ).fetchall()

    windows_by_id = {str(row["window_id"]): row for row in windows}
    owned_by_job: dict[int, list[sqlite3.Row]] = {}
    for row in owned_rows:
        owned_by_job.setdefault(int(row["scheduler_job_id"]), []).append(row)

    expected_job_ids = [int(row["scheduler_job_id"]) for row in steps]
    expected_job_set = set(expected_job_ids)
    owned_job_ids = [int(row["scheduler_job_id"]) for row in owned_rows]
    owned_job_set = set(owned_job_ids)
    matched: set[int] = set()
    lineage_mismatches: list[int] = []
    lifecycle_job_states: dict[int, str] = {}

    for step in steps:
        job_id = int(step["scheduler_job_id"])
        raw_status = str(step["scheduler_job_status"] or "").upper()
        lifecycle_job_states[job_id] = _JOB_STATUS_TO_WORK_STATE.get(
            raw_status, raw_status or "MISSING"
        )
        candidates = owned_by_job.get(job_id, [])
        if len(candidates) != 1:
            lineage_mismatches.append(job_id)
            continue
        owned = candidates[0]
        window_id = str(owned["window_id"] or "")
        window = windows_by_id.get(window_id)
        window_kind = allowed[str(step["step_kind"])]
        if window is None or not all(
            (
                str(window["window_kind"] or "") == window_kind,
                int(window["token_row_id"]) == int(step["token_id"]),
                int(window["pair_row_id"]) == int(step["pair_id"]),
                str(window["token_slot_id"] or "")
                == str(owned["token_slot_id"] or ""),
                str(owned["target_category"] or "") == "CAMPAIGN_WINDOW",
                str(owned["target_identity"] or "") == window_id,
                str(owned["work_state"] or "").upper()
                == lifecycle_job_states[job_id],
                _terminal_stage_matches(
                    window_kind=window_kind,
                    stage_id=str(owned["stage_id"] or ""),
                ),
            )
        ):
            lineage_mismatches.append(job_id)
            continue
        matched.add(job_id)

    duplicate_step_jobs = len(expected_job_ids) != len(expected_job_set)
    duplicate_owned_jobs = len(owned_job_ids) != len(owned_job_set)
    missing = expected_job_set - matched
    extra = owned_job_set - matched
    correspondence_exact = bool(
        expected_job_set
        and not duplicate_step_jobs
        and not duplicate_owned_jobs
        and expected_job_set == owned_job_set == matched
        and not lineage_mismatches
    )
    all_succeeded = bool(lifecycle_job_states) and all(
        state == "SUCCEEDED" for state in lifecycle_job_states.values()
    )
    return {
        "lifecycle_job_ids": sorted(expected_job_set),
        "owned_job_ids": sorted(owned_job_set),
        "lifecycle_job_states": {
            str(key): value
            for key, value in sorted(lifecycle_job_states.items())
        },
        "missing_ownership": sorted(missing),
        "extra_ownership": sorted(extra),
        "lineage_mismatch_job_ids": sorted(set(lineage_mismatches)),
        "duplicate_step_job_ids": duplicate_step_jobs,
        "duplicate_owned_job_ids": duplicate_owned_jobs,
        "expected_lifecycle_scheduler_count": len(expected_job_ids),
        "standard_four_hour_campaign": bool(standard_four_hour_campaign),
        "non_succeeded_states": {
            str(key): value
            for key, value in sorted(lifecycle_job_states.items())
            if value != "SUCCEEDED"
        },
        "correspondence_exact": correspondence_exact,
        "all_lifecycle_jobs_succeeded": all_succeeded,
    }


def _projected_reservation_count(step_kind: str) -> int:
    try:
        return int(PROJECTED_GOVERNED_OPERATIONS_BY_STEP_KIND[str(step_kind)])
    except KeyError as exc:
        raise FullRunAccountingError(
            f"no projected governed-operation reservation for step kind: {step_kind!r}"
        ) from exc


def scheduler_work_identity_for_step(
    context: OperationalLifecycleOwnershipContext,
    *,
    slot_ordinal: int,
    scheduler_job_id: int,
    step_kind: str,
    token_id: int,
) -> SchedulerWorkIdentity:
    """One Scheduler work identity for one enqueued lifecycle run-step job."""
    return SchedulerWorkIdentity(
        stage_id=_slot_stage_id(context, slot_ordinal),
        scheduler_job_id=int(scheduler_job_id),
        job_kind=str(step_kind),
        target_category="token",
        target_identity=str(int(token_id)),
    )


def reservation_identities_for_step(
    context: OperationalLifecycleOwnershipContext,
    *,
    slot_ordinal: int,
    scheduler_job_id: int,
    step_kind: str,
    token_id: int,
    pair_id: int,
) -> list[LifecycleReservationIdentity]:
    """The lifecycle transport reservations a step actually reserves.

    Count equals the step's projected governed operations, so a close step that
    reserves ``1 + PRECLOSE_CONTEXT_REQUEST_COUNT`` calls yields that many
    reservation identities — never one just because it has one Scheduler job.
    """
    stage_id = _slot_stage_id(context, slot_ordinal)
    job = int(scheduler_job_id)
    count = _projected_reservation_count(step_kind)
    return [
        LifecycleReservationIdentity(
            stage_id=stage_id,
            factory_run_id=context.factory_run_id,
            token_id=int(token_id),
            pair_id=int(pair_id),
            window_kind="WINDOW_15M",
            reservation_ordinal=job * 100 + index,
        )
        for index in range(count)
    ]


def transport_identity_for_step(
    context: OperationalLifecycleOwnershipContext,
    *,
    slot_ordinal: int,
    source_request_id: int,
    source_name: str,
    request_kind: str,
    pair_id: int,
    response_bytes: int,
    normalized_rows: int,
) -> TransportOperationIdentity:
    """One measured source transport identity for a step's exact-pair call.

    Keyed on the durable ``source_request_id`` so the execution-time observation
    and the post-hoc owner sealing derive the identical identity for the same
    outbound call.
    """
    return build_transport_identity(
        stage=_slot_stage_id(context, slot_ordinal),
        source_name=str(source_name),
        endpoint_owner=str(source_name),
        governed_request_kind=str(request_kind),
        method_or_endpoint=f"source_request:{int(source_request_id)}",
        within_request_ordinal=0,
        target_category="pair",
        target_identity=str(int(pair_id)),
        response_bytes=int(response_bytes),
        normalized_rows=int(normalized_rows),
    )


def transport_identity_for_attempt(
    context: OperationalLifecycleOwnershipContext,
    record: Mapping[str, Any],
) -> TransportOperationIdentity:
    """Build the complete immutable identity of one governed source attempt."""
    ordinal = _slot_ordinal_from_step_key(str(record["step_key"]))
    source_request_id = int(record["source_request_id"])
    return build_transport_identity(
        stage=_slot_stage_id(context, ordinal),
        source_name=str(record["source_name"]),
        endpoint_owner=str(record["source_name"]),
        governed_request_kind=str(record["request_kind"]),
        method_or_endpoint=f"source_request:{source_request_id}",
        within_request_ordinal=int(record.get("attempt_ordinal") or 0),
        target_category=str(record.get("target_category") or "pair"),
        target_identity=str(record.get("pair_id")),
        response_bytes=int(record.get("response_bytes") or 0),
        normalized_rows=int(record.get("normalized_rows") or 0),
        result=str(record.get("result") or "ATTEMPTED"),
        reserved_from=str(record.get("reserved_from") or "") or None,
    )


def validation_identity_for_step(
    context: OperationalLifecycleOwnershipContext,
    *,
    slot_ordinal: int,
    step_key: str,
    scheduler_job_id: int,
) -> LocalValidationIdentity:
    """The exact-pair verification validation that runs on a step's response."""
    return LocalValidationIdentity(
        stage_id=_slot_stage_id(context, slot_ordinal),
        subject_identity=str(step_key),
        validation_kind=_EXACT_PAIR_VALIDATION_KIND,
        validation_ordinal=int(scheduler_job_id),
    )


def build_lifecycle_action_local_observer(
    context: OperationalLifecycleOwnershipContext,
    ledger: CampaignActionLocalLedger,
) -> Callable[[Mapping[str, Any]], None]:
    """Return the factory ``lifecycle_operation_observer`` bound to a ledger.

    The factory fires this at two real boundaries. At ``SCHEDULER_ENQUEUE`` it
    records one Scheduler work identity plus the step's projected transport
    reservations. At ``SOURCE_TRANSPORT`` (the actual measured outbound-call
    boundary) it records the measured source transport identity plus the exact-pair
    verification validation that ran on the response. This is the execution-time
    capture that must equal the post-hoc owner sealing; it is never reconstructed
    from final rows or reports.
    """

    def observe(record: Mapping[str, Any]) -> None:
        boundary = str(record.get("boundary"))
        step_kind = str(record.get("step_kind"))
        if step_kind not in _TRANSPORT_BEARING_STEP_KINDS:
            return
        ordinal = _slot_ordinal_from_step_key(str(record.get("step_key")))
        if boundary == BOUNDARY_SCHEDULER_ENQUEUE:
            ledger.observe_scheduler_transition(record)
            ledger.observe_scheduler_work(
                scheduler_work_identity_for_step(
                    context,
                    slot_ordinal=ordinal,
                    scheduler_job_id=int(record["scheduler_job_id"]),
                    step_kind=step_kind,
                    token_id=int(record["token_id"]),
                )
            )
        elif boundary in {"SCHEDULER_CLAIM", "SCHEDULER_TERMINAL"}:
            ledger.observe_scheduler_transition(record)
        elif boundary == "LOCAL_VALIDATION":
            ledger.observe_local_validation(
                LocalValidationIdentity(
                    stage_id=_slot_stage_id(context, ordinal),
                    subject_identity=str(record["subject_identity"]),
                    validation_kind=str(record["validation_kind"]),
                    validation_ordinal=int(record["validation_ordinal"]),
                )
            )
        elif boundary == "LIFECYCLE_RESERVATION":
            ledger.observe_lifecycle_reservation(
                LifecycleReservationIdentity(
                    stage_id=_slot_stage_id(context, ordinal),
                    factory_run_id=context.factory_run_id,
                    token_id=int(record["token_id"]),
                    pair_id=int(record["pair_id"]),
                    window_kind="WINDOW_15M",
                    reservation_ordinal=int(record["reservation_ordinal"]),
                )
            )
        elif boundary == "GOVERNED_SOURCE_ATTEMPT":
            ledger.observe_transport(transport_identity_for_attempt(context, record))
        elif boundary == BOUNDARY_SOURCE_TRANSPORT:
            source_request_id = record.get("source_request_id")
            if source_request_id is None:
                return
            ledger.observe_transport(
                transport_identity_for_step(
                    context,
                    slot_ordinal=ordinal,
                    source_request_id=int(source_request_id),
                    source_name=str(record.get("source_name") or "dexscreener"),
                    request_kind=str(
                        record.get("request_kind") or "pair_market_snapshot"
                    ),
                    pair_id=int(record["pair_id"]),
                    response_bytes=int(record.get("response_bytes") or 0),
                    normalized_rows=int(record.get("normalized_rows") or 0),
                )
            )
            ledger.observe_local_validation(
                validation_identity_for_step(
                    context,
                    slot_ordinal=ordinal,
                    step_key=str(record["step_key"]),
                    scheduler_job_id=int(record["scheduler_job_id"]),
                )
            )

    return observe


def _validations_only_stage_evidence(count: int) -> dict[str, Any]:
    """Evidence scaffold for an owner-only stage carrying named validations."""
    return {
        "evidence_kind": "CAMPAIGN_SIX_UNIT_EVIDENCE_V1",
        "transport_operations": [],
        "local_validations": int(count),
        "scheduler_work_items": 0,
        "lifecycle_reservations": 0,
    }


# Real Scheduler job statuses map exactly to campaign work terminal states.
_JOB_STATUS_TO_WORK_STATE = {
    "SUCCEEDED": "SUCCEEDED",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
    "SKIPPED": "SKIPPED",
}
# One normalized exact-pair row is produced per lifecycle observation.
_LIFECYCLE_NORMALIZED_ROWS_PER_TRANSPORT = 1


def finalize_full_run_ownership_and_report(
    connection: sqlite3.Connection,
    *,
    context: OperationalLifecycleOwnershipContext,
    owner: CampaignSixUnitOwner,
    action_local: CampaignActionLocalLedger,
    execution_id: str,
    supervision_id: Any,
    launch_git_provenance: Mapping[str, Any],
    db_target_identity: str,
    runtime_terminal_status: str,
    cleanup_result: Mapping[str, Any] | None,
    runtime_first_terminal_cause: str | None = None,
    queue_dispositions: Mapping[int, str] | None = None,
    forbidden_capability_deltas: Mapping[str, int] | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Register ownership, seal accounting, reconcile, report, and gate a run.

    This is the campaign-layer full-run boundary invoked after the factory closes
    its windows and after unified terminal cleanup has produced the durable
    authorization/runtime/lease/active-work facts (which are passed in, never
    assumed). Because the memory-window close commits before campaign ownership
    can be registered, this is an explicit fail-closed compensation boundary: any
    registration/projection/accounting fault is preserved as a block reason and
    prevents Campaign PASS. It never rewrites factory state.

    Every accounting fact is measured from durable rows:

    * campaign-window ownership from the succeeded ``WINDOW_CLOSE`` steps;
    * Scheduler ownership carrying each job's *real* ``printer_scheduler_jobs``
      status (never a hardcoded SUCCEEDED);
    * owner slot-stage evidence sealing the exact lifecycle source transport
      identities (with real response bytes / normalized rows), the projected
      transport reservations, the Scheduler work, and the exact-pair validations;
    * every started stage on the one coordinator-created owner, with unscoped
      owner↔action-local equality across the complete repaired manifest.
    """
    connection.row_factory = sqlite3.Row
    stamp = now or datetime.now(timezone.utc).isoformat()
    blocked_reasons: list[str] = []
    queue_dispositions = dict(queue_dispositions or {})
    expected_owner_id = (
        f"six-unit-owner|{context.campaign_id}|{context.campaign_run_id}|"
        f"{context.cycle_id}"
    )
    expected_ledger_id = (
        f"action-local-ledger|{context.campaign_id}|{context.campaign_run_id}|"
        f"{context.cycle_id}"
    )
    if owner.owner_id != expected_owner_id:
        blocked_reasons.append("FULL_RUN_ACCOUNTING_OWNER_CONTINUITY_MISMATCH")
    if action_local.ledger_id != expected_ledger_id:
        blocked_reasons.append("ACTION_LOCAL_LEDGER_CONTINUITY_MISMATCH")
    if (
        owner.campaign_id != context.campaign_id
        or owner.run_id != context.campaign_run_id
        or owner.cycle_id != context.cycle_id
    ):
        blocked_reasons.append("FULL_RUN_ACCOUNTING_OWNER_IDENTITY_MISMATCH")

    close_steps = connection.execute(
        """SELECT id, token_id, pair_id, token_mint, pair_address, tracking_lane,
                  memory_window_id, step_key
           FROM printer_memory_factory_run_steps
           WHERE run_id=? AND step_kind='WINDOW_CLOSE' AND step_status='SUCCEEDED'
           ORDER BY id""",
        (context.factory_run_id,),
    ).fetchall()

    token_to_window: dict[int, str] = {}
    token_to_slot: dict[int, str] = {}
    token_to_terminal_state: dict[int, str] = {}
    token_to_memory: dict[int, sqlite3.Row] = {}
    # Exact durable target identity carried from the close step + campaign slot.
    token_to_identity: dict[int, dict[str, Any]] = {}
    registered_windows: list[str] = []

    for step in close_steps:
        token_id = int(step["token_id"])
        pair_id = int(step["pair_id"])
        memory_row_id = step["memory_window_id"]
        if memory_row_id is None:
            blocked_reasons.append(f"CLOSE_STEP_WITHOUT_MEMORY_WINDOW:{step['id']}")
            continue
        slot = connection.execute(
            """SELECT token_slot_id, lifecycle_identity, mint_identity, pair_identity,
                      tracking_queue_id
               FROM printer_memory_factory_campaign_token_slots
               WHERE cycle_id=? AND token_row_id=?""",
            (context.cycle_id, token_id),
        ).fetchone()
        if slot is None:
            blocked_reasons.append(f"NO_CAMPAIGN_SLOT_FOR_TOKEN:{token_id}")
            continue
        token_slot_id = str(slot["token_slot_id"])
        memory = connection.execute(
            """SELECT id, memory_status, data_quality_label, do_not_train
               FROM printer_memory_windows WHERE id=?""",
            (int(memory_row_id),),
        ).fetchone()
        if memory is None:
            blocked_reasons.append(f"MEMORY_WINDOW_MISSING:{memory_row_id}")
            continue
        terminal_state = (
            "CLEAN_PROMOTED"
            if str(memory["memory_status"]) == "CLEAN_MEMORY"
            else "DIRTY"
        )
        window_id = f"{context.cycle_id}:window:{token_id}"
        token_to_window[token_id] = window_id
        token_to_slot[token_id] = token_slot_id
        token_to_terminal_state[token_id] = terminal_state
        token_to_memory[token_id] = memory
        # Carry the real token/pair identity from the close step and slot — the
        # pair id is the step's own column, never derived from the token id.
        token_to_identity[token_id] = {
            "token_id": token_id,
            "token_mint": step["token_mint"] or slot["mint_identity"],
            "pair_id": pair_id,
            "pair_address": step["pair_address"] or slot["pair_identity"],
            "tracking_lane": step["tracking_lane"],
            "token_slot_id": token_slot_id,
                "memory_window_row_id": int(memory_row_id),
                "campaign_window_id": window_id,
                "memory_window_id": int(memory_row_id),
        }
        owned_window = connection.execute(
            """SELECT window_state, memory_window_row_id
               FROM printer_memory_factory_campaign_windows
               WHERE window_id=? AND campaign_id=? AND run_id=? AND cycle_id=?
                 AND token_slot_id=?""",
            (
                window_id,
                context.campaign_id,
                context.campaign_run_id,
                context.cycle_id,
                token_slot_id,
            ),
        ).fetchone()
        if (
            owned_window is None
            or owned_window["memory_window_row_id"] is None
            or int(owned_window["memory_window_row_id"]) != int(memory_row_id)
        ):
            blocked_reasons.append(
                f"WINDOW_NOT_REGISTERED_AT_CLOSE_BOUNDARY:{token_id}"
            )
        else:
            terminal_state = str(owned_window["window_state"])
            token_to_terminal_state[token_id] = terminal_state
            registered_windows.append(window_id)

    lifecycle_steps = connection.execute(
        """SELECT s.id, s.scheduler_job_id, s.step_kind, s.token_id, s.pair_id,
                  s.step_key, s.scheduled_for, s.source_request_id,
                  s.source_response_id,
                  s.result_json, s.step_status, s.error_or_skip_reason,
                  j.status AS scheduler_job_status,
                  q.source_name AS request_source_name,
                  q.request_kind AS request_kind
           FROM printer_memory_factory_run_steps s
           LEFT JOIN printer_scheduler_jobs j ON j.id = s.scheduler_job_id
           LEFT JOIN printer_source_requests q ON q.id = s.source_request_id
           LEFT JOIN printer_source_responses r ON r.id = s.source_response_id
           WHERE s.run_id=? AND s.step_kind IN ('SNAPSHOT','WINDOW_CLOSE')
             AND s.scheduler_job_id IS NOT NULL
           ORDER BY s.id""",
        (context.factory_run_id,),
    ).fetchall()

    # --- Scheduler ownership carrying each job's real terminal state (§6). ---
    projected_jobs: list[int] = []
    lifecycle_job_states: dict[int, str] = {}
    for step in lifecycle_steps:
        job_id = int(step["scheduler_job_id"])
        token_id = int(step["token_id"])
        window_id = token_to_window.get(token_id)
        slot_id = token_to_slot.get(token_id)
        if window_id is None or slot_id is None:
            blocked_reasons.append(f"SCHEDULER_PROJECTION_WITHOUT_WINDOW:{job_id}")
            continue
        raw_status = str(step["scheduler_job_status"] or "").upper()
        work_state = _JOB_STATUS_TO_WORK_STATE.get(raw_status)
        if work_state is None:
            blocked_reasons.append(
                f"SCHEDULER_JOB_NOT_TERMINAL:{job_id}:{raw_status or 'MISSING'}"
            )
            lifecycle_job_states[job_id] = raw_status or "MISSING"
            continue
        lifecycle_job_states[job_id] = work_state
        try:
            project_campaign_scheduler_job(
                connection,
                scheduler_work_id=campaign_scheduler_work_id(
                    context.campaign_id, job_id
                ),
                campaign_id=context.campaign_id,
                run_id=context.campaign_run_id,
                cycle_id=context.cycle_id,
                factory_run_id=context.factory_run_id,
                token_slot_id=slot_id,
                window_id=window_id,
                work_intent=(
                    f"{str(step['step_kind'])}|"
                    f"factory_run={context.factory_run_id}|job={job_id}"
                ),
                scheduler_job_id=job_id,
                deadline_at=str(step["scheduled_for"]),
                stage_id=_slot_stage_id(
                    context,
                    _slot_ordinal_from_step_key(str(step["step_key"])),
                ),
                target_category="CAMPAIGN_WINDOW",
                target_identity=window_id,
                source_request_id=(
                    None
                    if step["source_request_id"] is None
                    else int(step["source_request_id"])
                ),
                source_response_id=(
                    None
                    if step["source_response_id"] is None
                    else int(step["source_response_id"])
                ),
            )
            projected_jobs.append(job_id)
        except CampaignOwnershipError as exc:
            blocked_reasons.append(f"SCHEDULER_PROJECTION_FAILED:{job_id}:{exc}")

    run_config_row = connection.execute(
        "SELECT config_json FROM printer_memory_factory_runs WHERE run_id=?",
        (context.factory_run_id,),
    ).fetchone()
    try:
        run_config = json.loads(
            "{}" if run_config_row is None else str(run_config_row["config_json"])
        )
    except (TypeError, json.JSONDecodeError):
        run_config = {}
    standard_four_hour_campaign = (
        run_config.get("standard_four_hour_campaign") is True
    )
    scheduler_ownership = _load_terminal_scheduler_correspondence(
        connection,
        context=context,
        standard_four_hour_campaign=standard_four_hour_campaign,
    )

    # --- Seal the four approved mandatory stages from durable evidence. ---
    slot_stage_ids: list[str] = []
    by_ordinal: dict[int, list[sqlite3.Row]] = {1: [], 2: []}
    for step in lifecycle_steps:
        by_ordinal[_slot_ordinal_from_step_key(str(step["step_key"]))].append(step)

    sealed_transport_count = 0
    lifecycle_source_request_count = 0
    for ordinal in (1, 2):
        steps = by_ordinal.get(ordinal) or []
        if not steps:
            continue
        stage_id = _slot_stage_id(context, ordinal)
        slot_stage_ids.append(stage_id)
        ledger = MeasuredTransportLedger(
            campaign_id=context.campaign_id,
            run_id=context.campaign_run_id,
            cycle_id=context.cycle_id,
        )
        scheds: list[SchedulerWorkIdentity] = []
        ress: list[LifecycleReservationIdentity] = []
        vals: list[LocalValidationIdentity] = []
        for step in steps:
            step_kind = str(step["step_kind"])
            job_id = int(step["scheduler_job_id"])
            token_id = int(step["token_id"])
            pair_id = int(step["pair_id"])
            scheds.append(
                scheduler_work_identity_for_step(
                    context, slot_ordinal=ordinal, scheduler_job_id=job_id,
                    step_kind=step_kind, token_id=token_id,
                )
            )
            try:
                step_result = json.loads(str(step["result_json"] or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                step_result = {}
            raw_reservations = step_result.get("lifecycle_reservations") or []
            expected_reservations = reservation_identities_for_step(
                context,
                slot_ordinal=ordinal,
                scheduler_job_id=job_id,
                step_kind=step_kind,
                token_id=token_id,
                pair_id=pair_id,
            )
            actual_ordinals = [
                int(item.get("reservation_ordinal"))
                for item in raw_reservations
                if isinstance(item, Mapping)
                and item.get("reservation_ordinal") is not None
            ]
            expected_ordinals = [
                int(item.reservation_ordinal) for item in expected_reservations
            ]
            if actual_ordinals != expected_ordinals:
                blocked_reasons.append(
                    f"LIFECYCLE_RESERVATION_EVIDENCE_MISMATCH:{step['id']}"
                )
            else:
                ress.extend(expected_reservations)
            attempts = connection.execute(
                """SELECT q.id AS source_request_id, q.source_name,
                          q.request_kind, r.id AS source_response_id,
                          r.normalized_payload_json AS response_payload_json,
                          f.id AS source_failure_id,
                          f.normalized_payload_json AS failure_payload_json
                   FROM printer_source_requests AS q
                   LEFT JOIN printer_source_responses AS r
                     ON r.source_request_id=q.id
                   LEFT JOIN printer_source_failures AS f
                     ON f.source_request_id=q.id
                   WHERE q.request_key LIKE ?
                   ORDER BY q.id""",
                (f"{context.factory_run_id}:{step['step_key']}%",),
            ).fetchall()
            lifecycle_source_request_count += len(attempts)
            for attempt_ordinal, attempt in enumerate(attempts, start=1):
                payload_json = (
                    attempt["response_payload_json"]
                    if attempt["source_response_id"] is not None
                    else attempt["failure_payload_json"]
                )
                try:
                    payload = json.loads(str(payload_json or "{}"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    payload = {}
                measured = merge_transport_payload_metadata(payload)
                ledger.record_transport(
                    transport_identity_for_attempt(
                        context,
                        {
                            "step_key": str(step["step_key"]),
                            "source_request_id": int(attempt["source_request_id"]),
                            "source_name": str(attempt["source_name"]),
                            "request_kind": str(attempt["request_kind"]),
                            "pair_id": pair_id,
                            "attempt_ordinal": attempt_ordinal,
                            "response_bytes": int(measured["response_bytes"]),
                            "normalized_rows": int(measured["normalized_rows"]),
                            "result": (
                                "SUCCEEDED"
                                if attempt["source_response_id"] is not None
                                else "FAILED"
                            ),
                            "reserved_from": (
                                f"{context.factory_run_id}:{step['step_key']}:"
                                f"reservation:{attempt_ordinal}"
                            ),
                        },
                    )
                )
            raw_validations = step_result.get("local_validations") or []
            if not raw_validations:
                blocked_reasons.append(
                    f"LOCAL_VALIDATION_EVIDENCE_MISSING:{step['id']}"
                )
            for raw_validation in raw_validations:
                if not isinstance(raw_validation, Mapping):
                    blocked_reasons.append(
                        f"LOCAL_VALIDATION_EVIDENCE_MALFORMED:{step['id']}"
                    )
                    continue
                vals.append(
                    LocalValidationIdentity(
                        stage_id=stage_id,
                        subject_identity=str(raw_validation["subject_identity"]),
                        validation_kind=str(raw_validation["validation_kind"]),
                        validation_ordinal=int(
                            raw_validation["validation_ordinal"]
                        ),
                    )
                )
        sealed_transport_count += len(ledger.transports)
        failed_step = next(
            (
                item
                for item in steps
                if str(item["step_status"]) == "FAILED"
                or str(item["scheduler_job_status"] or "") == "FAILED"
            ),
            None,
        )
        blocked_step = next(
            (
                item
                for item in steps
                if str(item["step_status"]) in {"CANCELLED", "SKIPPED"}
                or str(item["scheduler_job_status"] or "")
                in {"CANCELLED", "SKIPPED"}
            ),
            None,
        )
        stage_terminal_status = (
            "FAILED" if failed_step is not None
            else "BLOCKED" if blocked_step is not None
            else "COMPLETED"
        )
        terminal_item = failed_step or blocked_step
        stage_first_cause = (
            None
            if terminal_item is None
            else str(
                terminal_item["error_or_skip_reason"]
                or terminal_item["scheduler_job_status"]
            )
        )
        sealed = seal_campaign_stage_evidence(
            stage_id=stage_id,
            stage_kind=f"WINDOW_15M_SLOT_{ordinal}",
            stage_sequence=ordinal + 1,
            stage_terminal_status=stage_terminal_status,
            stage_first_terminal_cause=stage_first_cause,
            campaign_id=context.campaign_id,
            run_id=context.campaign_run_id,
            cycle_id=context.cycle_id,
            ledger=ledger,
            scheduler_work_identities=scheds,
            lifecycle_reservation_identities=ress,
            local_validation_identities=vals,
        )
        if stage_id not in owner.ingested_stage_ids:
            owner.ingest_stage_evidence(sealed)

    owner.close()

    # Fail-closed transport proof: a lifecycle-started run whose lifecycle steps
    # made source requests can never seal zero source transport identities.
    if lifecycle_source_request_count > 0 and sealed_transport_count == 0:
        blocked_reasons.append("LIFECYCLE_SOURCE_TRANSPORT_IDENTITIES_ZERO")

    reconciliation = reconcile_full_run_owner_to_action_local(
        owner,
        action_local,
        required_stage_kinds=REQUIRED_LIFECYCLE_STAGE_KINDS,
    )

    selected_tokens: list[dict[str, Any]] = []
    per_token_outcomes: list[dict[str, Any]] = []
    slot_dispositions: list[dict[str, Any]] = []
    quality_results: list[dict[str, Any]] = []
    for token_id in sorted(token_to_window):
        memory = token_to_memory[token_id]
        identity = token_to_identity[token_id]
        terminal_state = token_to_terminal_state[token_id]
        slot_row = connection.execute(
            """SELECT s.token_state, q.queue_status
               FROM printer_memory_factory_campaign_token_slots AS s
               LEFT JOIN printer_tracking_queue AS q ON q.id=s.tracking_queue_id
               WHERE s.token_slot_id=?""",
            (identity["token_slot_id"],),
        ).fetchone()
        persisted_slot_state = None if slot_row is None else str(slot_row["token_state"])
        queue_disposition = (
            queue_dispositions.get(token_id)
            if token_id in queue_dispositions
            else None if slot_row is None or slot_row["queue_status"] is None
            else str(slot_row["queue_status"])
        )
        cadence_row = connection.execute(
            """SELECT tracking_lane,
                      SUM(CASE WHEN step_kind='SNAPSHOT' THEN 1 ELSE 0 END),
                      SUM(CASE WHEN step_kind='SNAPSHOT'
                                AND step_status='SUCCEEDED'
                                AND snapshot_id IS NOT NULL THEN 1 ELSE 0 END),
                      SUM(CASE WHEN step_kind='WINDOW_CLOSE'
                                AND step_status='SUCCEEDED'
                                AND memory_window_id IS NOT NULL THEN 1 ELSE 0 END)
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND token_id=? AND pair_id=?
                 AND step_kind IN ('SNAPSHOT','WINDOW_CLOSE')""",
            (context.factory_run_id, token_id, int(identity["pair_id"])),
        ).fetchone()
        snapshot_rows = connection.execute(
            """SELECT id, step_key, scheduler_job_id, snapshot_id, step_status
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND token_id=? AND pair_id=? AND step_kind='SNAPSHOT'
               ORDER BY scheduled_for,id""",
            (context.factory_run_id, token_id, int(identity["pair_id"])),
        ).fetchall()
        lane = str(cadence_row["tracking_lane"] or identity["tracking_lane"])
        # The authoritative cadence minimum includes the closing observation;
        # planned SNAPSHOT steps are therefore the policy minimum minus the one
        # WINDOW_CLOSE observation. Never reconstruct cadence from lane literals.
        cadence_policy = get_cadence_policy("WINDOW_15M", lane)
        if cadence_policy is None or not cadence_policy.enabled_for_real_collection:
            raise FullRunAccountingError(
                f"authoritative WINDOW_15M cadence unavailable for {lane}"
            )
        expected_snapshot_steps = int(cadence_policy.minimum_required_snapshots) - 1
        actual_snapshot_steps = int(cadence_row[2] or 0)
        missing_snapshot_steps = max(
            0, expected_snapshot_steps - actual_snapshot_steps
        )
        cadence_evidence = {
            "cadence_policy": "WINDOW_15M_AUTHORITATIVE_CADENCE",
            "minimum_required_observations": int(
                cadence_policy.minimum_required_snapshots
            ),
            "target_snapshot_interval_seconds": int(
                cadence_policy.target_snapshot_interval_seconds
            ),
            "tracking_lane": lane,
            "expected_snapshot_steps": expected_snapshot_steps,
            "planned_snapshot_steps": int(cadence_row[1] or 0),
            "actual_snapshot_steps": actual_snapshot_steps,
            "missing_snapshot_steps": missing_snapshot_steps,
            "snapshot_step_ids": [int(row["id"]) for row in snapshot_rows],
            "snapshot_ids": [
                int(row["snapshot_id"])
                for row in snapshot_rows
                if row["snapshot_id"] is not None
                and str(row["step_status"]) == "SUCCEEDED"
            ],
            "snapshot_scheduler_job_ids": [
                int(row["scheduler_job_id"])
                for row in snapshot_rows
                if row["scheduler_job_id"] is not None
            ],
            "coverage_status": (
                "COMPLETE"
                if actual_snapshot_steps == expected_snapshot_steps
                and len(snapshot_rows) == expected_snapshot_steps
                else "INCOMPLETE"
            ),
            "succeeded_close_count": int(cadence_row[3] or 0),
        }
        close_row = connection.execute(
            """SELECT id,scheduler_job_id,memory_window_id,step_status
               FROM printer_memory_factory_run_steps
               WHERE run_id=? AND token_id=? AND pair_id=?
                 AND step_kind='WINDOW_CLOSE'
               ORDER BY id""",
            (context.factory_run_id, token_id, int(identity["pair_id"])),
        ).fetchall()
        cadence_evidence["close_step_ids"] = [int(row["id"]) for row in close_row]
        cadence_evidence["close_scheduler_job_ids"] = [
            int(row["scheduler_job_id"])
            for row in close_row if row["scheduler_job_id"] is not None
        ]
        selected_tokens.append({**dict(identity), "cadence": cadence_evidence})
        per_token_outcomes.append({
            **identity,
            "terminal_status": "WINDOW_CLOSED",
            "tracking_disposition": queue_disposition,
            "cadence": cadence_evidence,
        })
        slot_dispositions.append(
            {
                **resolve_campaign_slot_terminal_disposition(
                lifecycle_started=True,
                owned_terminal_window_state=terminal_state,
                queue_disposition=queue_disposition,
                ),
                "persisted_slot_state": persisted_slot_state,
                "persisted_state_matches": persisted_slot_state
                in {"COOLDOWN", "ARCHIVED"}
                and persisted_slot_state == queue_disposition,
            }
        )
        # Inspect the real episodes attached to this exact memory window: a clean
        # episode on a non-clean window is a quality inconsistency.
        episode = connection.execute(
            """SELECT id,episode_kind FROM printer_episodes
               WHERE memory_window_id=?
               ORDER BY (episode_kind = ?) DESC, id LIMIT 1""",
            (identity["memory_window_row_id"], _CLEAN_EPISODE_KIND),
        ).fetchone()
        proposed_episode_kind = None if episode is None else str(episode["episode_kind"])
        quality_results.append({
            **evaluate_quality_consistency(
                memory_status=str(memory["memory_status"]),
                data_quality_label=str(memory["data_quality_label"]),
                do_not_train=int(memory["do_not_train"]),
                proposed_episode_kind=proposed_episode_kind,
            ),
            "window_id": token_to_window[token_id],
            "episode_id": None if episode is None else int(episode["id"]),
            "episode_kind": proposed_episode_kind or "NO_CLEAN_EPISODE_CREATED",
        })

    active_jobs = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work
           WHERE campaign_id=? AND run_id=? AND cycle_id=?
             AND work_state IN ('PENDING','RUNNING','COOLDOWN')""",
        (context.campaign_id, context.campaign_run_id, context.cycle_id),
    ).fetchone()[0])
    locked_jobs = int(connection.execute(
        """SELECT COUNT(DISTINCT j.id)
           FROM printer_memory_factory_campaign_scheduler_work AS w
           JOIN printer_scheduler_jobs AS j ON j.id=w.scheduler_job_id
           WHERE w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
             AND w.ownership_contract_version='V2_STAGE_SCOPED'
             AND (j.locked_at IS NOT NULL OR j.lock_owner IS NOT NULL)""",
        (context.campaign_id, context.campaign_run_id, context.cycle_id),
    ).fetchone()[0])
    retry_count = int(connection.execute(
        """SELECT COALESCE(SUM(j.retry_count),0)
           FROM printer_memory_factory_campaign_scheduler_work AS w
           JOIN printer_scheduler_jobs AS j ON j.id=w.scheduler_job_id
           WHERE w.campaign_id=? AND w.run_id=? AND w.cycle_id=?
             AND w.ownership_contract_version='V2_STAGE_SCOPED'""",
        (context.campaign_id, context.campaign_run_id, context.cycle_id),
    ).fetchone()[0])
    bound_run_count = int(connection.execute(
        """SELECT COUNT(*) FROM printer_memory_factory_campaign_runs
           WHERE campaign_id=? AND run_id=? AND authoritative_run_id=?""",
        (
            context.campaign_id,
            context.campaign_run_id,
            context.factory_run_id,
        ),
    ).fetchone()[0])
    action_local_evidence = {
        "ledger_id": action_local.ledger_id,
        "campaign_id": action_local.campaign_id,
        "run_id": action_local.run_id,
        "cycle_id": action_local.cycle_id,
        "transport_identities": list(action_local.transport_identities),
        "scheduler_work_identities": list(action_local.scheduler_work_identities),
        "lifecycle_reservation_identities": list(
            action_local.lifecycle_reservation_identities
        ),
        "local_validation_identities": list(
            action_local.local_validation_identities
        ),
        "scheduler_transition_coverage": action_local.scheduler_transition_coverage(),
    }
    marker_evidence = load_invocation_authority_evidence(
        connection,
        context=context,
        execution_id=execution_id,
        supervision_id=str(supervision_id),
    )
    cleanup_evidence = load_cleanup_lease_evidence(
        connection,
        context=context,
        supervision_id=str(supervision_id),
        cleanup_result=cleanup_result,
    )

    report = build_full_run_terminal_report(
        connection,
        context=context,
        execution_id=execution_id,
        supervision_id=supervision_id,
        launch_git_provenance=launch_git_provenance,
        db_target_identity=db_target_identity,
        selected_tokens=selected_tokens,
        runtime_terminal_status=runtime_terminal_status,
        runtime_first_terminal_cause=runtime_first_terminal_cause,
        active_work_result=cleanup_result,
        owner_evidence=owner.durable_evidence(),
        action_local_evidence=action_local_evidence,
        six_unit_totals=owner.six_unit_totals(),
        reconciliation=reconciliation,
        per_token_outcomes=per_token_outcomes,
        slot_dispositions=slot_dispositions,
        quality_results=quality_results,
        zero_active_scheduler_jobs=active_jobs,
        forbidden_capability_deltas=forbidden_capability_deltas or {},
        authorization_invocation_evidence=marker_evidence,
        cleanup_lease_evidence=cleanup_evidence,
        scheduler_ownership=scheduler_ownership,
    )
    cleanup_truth = dict(cleanup_result or {})
    automatic_retries = int(cleanup_truth.get("automatic_retries") or 0)
    restart_count = 1 if cleanup_truth.get("restart_created") is True else 0
    resume_count = 1 if cleanup_truth.get("resume_created") is True else 0
    cleanup_successor_count = (
        1 if cleanup_truth.get("successor_created") is True else 0
    )
    cleanup_truth_complete = all(
        field in cleanup_truth
        for field in (
            "automatic_retries",
            "restart_created",
            "resume_created",
            "successor_created",
        )
    )
    successor_count = max(cleanup_successor_count, max(0, bound_run_count - 1))
    cleanup_cancelled_count = int(
        cleanup_truth.get("cancelled_scheduler_jobs") or 0
    )
    cleanup_terminal_observations = sum(
        1
        for event in action_local.scheduler_transition_events
        if event.get("operation_owner") == "UNIFIED_TERMINAL_CLEANUP"
        and event.get("terminal_state") == "CANCELLED"
    )
    report["terminal_safety"].update(
        {
            "locked_scheduler_job_count": locked_jobs,
            "zero_locked_work": locked_jobs == 0,
            "scheduler_retry_count": retry_count,
            "automatic_retry_count": automatic_retries,
            "cleanup_cancelled_scheduler_job_count": cleanup_cancelled_count,
            "cleanup_scheduler_terminal_observation_count": (
                cleanup_terminal_observations
            ),
            "cleanup_scheduler_observation_exact": (
                "cancelled_scheduler_jobs" in cleanup_truth
                and cleanup_cancelled_count == cleanup_terminal_observations
            ),
            "restart_count": restart_count,
            "resume_count": resume_count,
            "successor_count": successor_count,
            "cleanup_retry_restart_resume_successor_truth_complete": (
                cleanup_truth_complete
            ),
            "no_retry_restart_resume_successor": (
                _no_retry_restart_resume_successor(
                    cleanup_truth_complete=cleanup_truth_complete,
                    scheduler_retry_count=retry_count,
                    automatic_retry_count=automatic_retries,
                    restart_count=restart_count,
                    resume_count=resume_count,
                    successor_count=successor_count,
                    bound_run_count=bound_run_count,
                )
            ),
        }
    )
    canonical = lambda value: json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    report["hashes"] = {
        "owner_evidence_sha256": hashlib.sha256(
            canonical(report["full_run_accounting"]["owner_evidence"])
        ).hexdigest(),
        "action_local_evidence_sha256": hashlib.sha256(
            canonical(report["full_run_accounting"]["action_local_evidence"])
        ).hexdigest(),
    }
    if (
        marker_evidence.get("evidence_mode")
        == EVIDENCE_MODE_DISPOSABLE_PUBLIC_COMPOSITION_PROOF
    ):
        report["hashes"].update(
            {
                "proof_expectation_sha256": str(
                    marker_evidence.get("proof_expectation_sha256") or ""
                ),
                "proof_invocation_evidence_sha256": str(
                    marker_evidence.get(
                        "proof_invocation_evidence_sha256"
                    ) or ""
                ),
            }
        )
    else:
        report["hashes"].update(
            {
                "authorization_marker_sha256": str(
                    marker_evidence.get("authorization_marker_sha256") or ""
                ),
                "invocation_marker_sha256": str(
                    marker_evidence.get("invocation_marker_sha256") or ""
                ),
            }
        )
    report["hashes"]["report_body_sha256"] = hashlib.sha256(
        canonical(report)
    ).hexdigest()
    gate = evaluate_campaign_acceptance_gate(report)
    verdict = gate["verdict"]
    lifecycle_started = bool(reconciliation.get("lifecycle_started"))
    if blocked_reasons and verdict == VERDICT_PASS:
        verdict = VERDICT_BLOCKED_UNSAFE if lifecycle_started else VERDICT_HONEST_BLOCKED
    # §12 report/gate/verdict consistency: the embedded gate, the canonical report
    # and the returned verdict can never disagree. A compensation block downgrades
    # every surface together — no embedded gate may still read CAMPAIGN_PASS.
    if verdict != gate["verdict"]:
        gate = dict(gate)
        gate["verdict"] = verdict
        gate["pass"] = verdict == VERDICT_PASS
        gate["failing_checks"] = list(gate.get("failing_checks") or []) + [
            f"COMPENSATION_BLOCK:{reason}" for reason in blocked_reasons
        ]
    gate["compensation_blocked_reasons"] = list(blocked_reasons)
    report["campaign_acceptance_verdict"] = verdict
    report["campaign_pass"] = verdict == VERDICT_PASS
    body = dict(report)
    body_hashes = dict(body.get("hashes") or {})
    body_hashes.pop("report_body_sha256", None)
    body["hashes"] = body_hashes
    report["hashes"]["report_body_sha256"] = hashlib.sha256(
        canonical(body)
    ).hexdigest()
    return {
        "verdict": verdict,
        "campaign_acceptance": gate,
        "report": report,
        "reconciliation": reconciliation,
        "scheduler_ownership": scheduler_ownership,
        "registered_windows": registered_windows,
        "projected_scheduler_jobs": projected_jobs,
        "blocked_reasons": blocked_reasons,
    }


__all__ = [
    "BOUNDARY_SCHEDULER_ENQUEUE",
    "BOUNDARY_SOURCE_TRANSPORT",
    "EVIDENCE_MODE_AUTHORIZED_OPERATIONAL",
    "EVIDENCE_MODE_DISPOSABLE_PUBLIC_COMPOSITION_PROOF",
    "FullRunAccountingError",
    "OperationalLifecycleOwnershipContext",
    "PRECLOSE_CONTEXT_REQUEST_COUNT",
    "PROJECTED_GOVERNED_OPERATIONS_BY_STEP_KIND",
    "REQUIRED_LIFECYCLE_STAGE_KINDS",
    "VERDICT_BLOCKED_UNSAFE",
    "VERDICT_HONEST_BLOCKED",
    "VERDICT_PASS",
    "build_full_run_terminal_report",
    "build_lifecycle_action_local_observer",
    "durable_cleanup_release_timestamps_valid",
    "evaluate_campaign_acceptance_gate",
    "evaluate_quality_consistency",
    "finalize_full_run_ownership_and_report",
    "load_invocation_authority_evidence",
    "parse_durable_timestamp",
    "reservation_identities_for_step",
    "resolve_campaign_slot_terminal_disposition",
    "scheduler_work_identity_for_step",
    "transport_identity_for_step",
    "validation_identity_for_step",
]
