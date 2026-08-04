"""Full pre-lifecycle readiness artifact builder and validator.

Extends the existing bounded qualification architecture. Does not run
discovery, selection, lifecycle, tracking, memory, retrieval, or financial
paths. Callers supply already-proven two-candidate qualification evidence
from ordinary owners (e.g. stop_before_lifecycle / readiness surfaces).

Freshness law: SOURCE_REGISTRY[source].stale_after_seconds against each
embedded evidence timestamp (Source Governor). Artifact expires_at is the
minimum of those row-level expiries — not an invented free-floating TTL.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from printer_v1.sources.registry import SOURCE_REGISTRY


SCHEMA_VERSION = "PRINTER_V1_PRE_LIFECYCLE_READINESS_ARTIFACT_V1"

REQUIRED_GATE_NAMES = (
    "pump_pumpswap_graduation_and_pool_identity",
    "exact_pool_liquidity_at_or_above_3000",
    "tracking_cooldown_eligibility",
    "holder_eligibility",
    "neutral_two_candidate_selection",
    "source_quality_gates",
)

_FORBIDDEN_DOWNSTREAM_FLAGS = (
    "tracking_started",
    "lifecycle_started",
    "memory_window_created",
    "scheduler_runtime_started",
    "factory_run_created",
)


class PreLifecycleReadinessArtifactError(ValueError):
    """Fail-closed readiness artifact fault."""


def _parse_iso(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _require_mapping(value: Any, *, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PreLifecycleReadinessArtifactError(f"{label} must be an object")
    return value


def _require_str(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PreLifecycleReadinessArtifactError(f"{label} must be a non-empty string")
    return value.strip()


def compute_db_identity(db_path: str | Path) -> dict[str, Any]:
    path = Path(db_path).resolve()
    if not path.is_file():
        raise PreLifecycleReadinessArtifactError(f"db_path not found: {path}")
    data = path.read_bytes()
    st = path.stat()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": int(st.st_size),
        "mtime_ns": int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))),
    }


def compute_readiness_artifact_expiry(
    evidence_rows: Sequence[Mapping[str, Any]],
) -> str:
    """Return ISO expiry = min(received_at + source stale_after_seconds)."""
    if not evidence_rows:
        raise PreLifecycleReadinessArtifactError(
            "readiness artifact requires at least one evidence row for expiry"
        )
    expiries: list[datetime] = []
    for row in evidence_rows:
        source_name = _require_str(row.get("source_name"), label="evidence source_name")
        if source_name not in SOURCE_REGISTRY:
            raise PreLifecycleReadinessArtifactError(
                f"unknown evidence source_name for freshness law: {source_name!r}"
            )
        received_at = _require_str(row.get("received_at"), label="evidence received_at")
        stale_after = int(SOURCE_REGISTRY[source_name].stale_after_seconds)
        expiries.append(_parse_iso(received_at) + timedelta(seconds=stale_after))
    return min(expiries).isoformat()


def _normalize_candidate(raw: Mapping[str, Any], *, index: int) -> dict[str, Any]:
    label = f"candidate[{index}]"
    mint = _require_str(raw.get("mint"), label=f"{label}.mint")
    pool = _require_str(raw.get("pool"), label=f"{label}.pool")
    gates_in = _require_mapping(raw.get("gates"), label=f"{label}.gates")
    gates: dict[str, str] = {}
    for name in REQUIRED_GATE_NAMES:
        status = gates_in.get(name)
        if status != "PASS":
            raise PreLifecycleReadinessArtifactError(
                f"{label}.gates.{name} must be PASS; got {status!r}"
            )
        gates[name] = "PASS"
    lineage = _require_mapping(
        raw.get("source_lineage"), label=f"{label}.source_lineage"
    )
    for key in ("source_request_ids", "source_response_ids"):
        if key not in lineage:
            raise PreLifecycleReadinessArtifactError(
                f"{label}.source_lineage missing {key}"
            )
        if not isinstance(lineage[key], (list, tuple)) or not lineage[key]:
            raise PreLifecycleReadinessArtifactError(
                f"{label}.source_lineage.{key} must be a non-empty list"
            )
    # failure IDs may be empty when all gates completed successfully
    if "source_failure_ids" not in lineage:
        raise PreLifecycleReadinessArtifactError(
            f"{label}.source_lineage missing source_failure_ids"
        )
    if not isinstance(lineage["source_failure_ids"], (list, tuple)):
        raise PreLifecycleReadinessArtifactError(
            f"{label}.source_lineage.source_failure_ids must be a list"
        )
    liquidity_ts = _require_str(
        raw.get("liquidity_evidence_at"), label=f"{label}.liquidity_evidence_at"
    )
    holder_ts = _require_str(
        raw.get("holder_evidence_at"), label=f"{label}.holder_evidence_at"
    )
    return {
        "mint": mint,
        "pool": pool,
        "gates": gates,
        "source_lineage": {
            "source_request_ids": [int(x) for x in lineage["source_request_ids"]],
            "source_response_ids": [int(x) for x in lineage["source_response_ids"]],
            "source_failure_ids": [int(x) for x in lineage["source_failure_ids"]],
        },
        "liquidity_evidence_at": liquidity_ts,
        "holder_evidence_at": holder_ts,
        "liquidity_source_name": _require_str(
            raw.get("liquidity_source_name") or "dexscreener",
            label=f"{label}.liquidity_source_name",
        ),
        "holder_source_name": _require_str(
            raw.get("holder_source_name") or "solana_rpc",
            label=f"{label}.holder_source_name",
        ),
        "eligible": True,
    }


def _evidence_rows_from_candidates(
    candidates: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        rows.append(
            {
                "source_name": candidate["liquidity_source_name"],
                "received_at": candidate["liquidity_evidence_at"],
                "gate": "exact_pool_liquidity_at_or_above_3000",
                "mint": candidate["mint"],
                "pool": candidate["pool"],
            }
        )
        rows.append(
            {
                "source_name": candidate["holder_source_name"],
                "received_at": candidate["holder_evidence_at"],
                "gate": "holder_eligibility",
                "mint": candidate["mint"],
                "pool": candidate["pool"],
            }
        )
    return rows


def build_pre_lifecycle_readiness_artifact(
    *,
    qualification_execution_id: str,
    implementation_head: str,
    db_path: str | Path,
    created_at: str,
    candidates: Sequence[Mapping[str, Any]],
    db_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one frozen readiness artifact after ordinary owners prove two slots.

    Callers must have already run ordinary qualification owners. This function
    only freezes and validates the evidence shape; it does not contact providers
    or start lifecycle/memory/Scheduler work.
    """
    if len(candidates) != 2:
        raise PreLifecycleReadinessArtifactError(
            f"exactly two candidates required; got {len(candidates)}"
        )
    normalized = [
        _normalize_candidate(candidates[0], index=0),
        _normalize_candidate(candidates[1], index=1),
    ]
    if normalized[0]["mint"] == normalized[1]["mint"]:
        raise PreLifecycleReadinessArtifactError("candidate mints must be distinct")
    if normalized[0]["pool"] == normalized[1]["pool"]:
        raise PreLifecycleReadinessArtifactError("candidate pools must be distinct")

    identity = dict(db_identity) if db_identity is not None else compute_db_identity(db_path)
    for key in ("path", "sha256", "size", "mtime_ns"):
        if key not in identity:
            raise PreLifecycleReadinessArtifactError(f"db_identity missing {key}")

    evidence_rows = _evidence_rows_from_candidates(normalized)
    expires_at = compute_readiness_artifact_expiry(evidence_rows)
    created = _parse_iso(created_at)
    if created > _parse_iso(expires_at):
        raise PreLifecycleReadinessArtifactError(
            "created_at is after computed expires_at under source freshness law"
        )

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "qualification_execution_id": _require_str(
            qualification_execution_id, label="qualification_execution_id"
        ),
        "implementation_head": _require_str(
            implementation_head, label="implementation_head"
        ),
        "db_identity": {
            "path": str(identity["path"]),
            "sha256": str(identity["sha256"]),
            "size": int(identity["size"]),
            "mtime_ns": int(identity["mtime_ns"]),
        },
        "created_at": created.isoformat(),
        "expires_at": expires_at,
        "candidate_count": 2,
        "candidates": normalized,
        "evidence_rows": evidence_rows,
        "downstream": {
            "tracking_started": False,
            "lifecycle_started": False,
            "memory_window_created": False,
            "scheduler_runtime_started": False,
            "factory_run_created": False,
        },
        "capability_deltas": {
            "retrieval": 0,
            "paper_decisions": 0,
            "positions": 0,
            "trade_events": 0,
            "trade_audits": 0,
            "pnl": 0,
        },
        "verdict": "PRE_LIFECYCLE_READINESS_ARTIFACT_PASS",
    }
    return artifact


def validate_pre_lifecycle_readiness_artifact(
    artifact: Mapping[str, Any] | None,
    *,
    now: str | datetime,
    expected_head: str,
    expected_db_identity: Mapping[str, Any],
    expected_candidates: Sequence[Mapping[str, Any]] | None = None,
    candidate_state: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Fail-closed validation of a readiness artifact for authorization prep."""
    blockers: list[str] = []
    if artifact is None:
        return {
            "valid": False,
            "blockers": ["artifact_absent"],
            "status": "READINESS_ARTIFACT_ABSENT",
        }
    if not isinstance(artifact, Mapping):
        return {
            "valid": False,
            "blockers": ["artifact_not_object"],
            "status": "READINESS_ARTIFACT_INVALID",
        }

    if artifact.get("schema_version") != SCHEMA_VERSION:
        blockers.append("schema_version_mismatch")
    if artifact.get("verdict") != "PRE_LIFECYCLE_READINESS_ARTIFACT_PASS":
        blockers.append("verdict_not_pass")
    if str(artifact.get("implementation_head") or "") != str(expected_head):
        blockers.append("head_mismatch")

    db = artifact.get("db_identity")
    if not isinstance(db, Mapping):
        blockers.append("db_identity_missing")
    else:
        for key in ("path", "sha256", "size", "mtime_ns"):
            if db.get(key) != expected_db_identity.get(key):
                blockers.append(f"db_{key}_mismatch")

    candidates = artifact.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 2:
        blockers.append("candidate_count_not_exactly_two")
    else:
        mints = {str(c.get("mint")) for c in candidates if isinstance(c, Mapping)}
        pools = {str(c.get("pool")) for c in candidates if isinstance(c, Mapping)}
        if len(mints) != 2:
            blockers.append("mint_identity_not_exactly_two_distinct")
        if len(pools) != 2:
            blockers.append("pool_identity_not_exactly_two_distinct")
        for idx, candidate in enumerate(candidates):
            if not isinstance(candidate, Mapping):
                blockers.append(f"candidate_{idx}_not_object")
                continue
            gates = candidate.get("gates")
            if not isinstance(gates, Mapping):
                blockers.append(f"candidate_{idx}_gates_missing")
            else:
                for name in REQUIRED_GATE_NAMES:
                    if gates.get(name) != "PASS":
                        blockers.append(f"candidate_{idx}_gate_{name}_not_pass")
            lineage = candidate.get("source_lineage")
            if not isinstance(lineage, Mapping):
                blockers.append(f"candidate_{idx}_source_lineage_missing")
            else:
                for key in ("source_request_ids", "source_response_ids"):
                    vals = lineage.get(key)
                    if not isinstance(vals, (list, tuple)) or not vals:
                        blockers.append(
                            f"candidate_{idx}_source_lineage_{key}_incomplete"
                        )
                if "source_failure_ids" not in lineage:
                    blockers.append(
                        f"candidate_{idx}_source_lineage_source_failure_ids_missing"
                    )

    if expected_candidates is not None:
        if len(expected_candidates) != 2 or not isinstance(candidates, list):
            blockers.append("expected_candidates_count_mismatch")
        else:
            art_pairs = {
                (str(c.get("mint")), str(c.get("pool")))
                for c in candidates
                if isinstance(c, Mapping)
            }
            exp_pairs = {
                (str(c.get("mint")), str(c.get("pool")))
                for c in expected_candidates
            }
            if art_pairs != exp_pairs:
                blockers.append("mint_or_pool_identity_differs")

    if candidate_state is not None:
        if len(candidate_state) != 2:
            blockers.append("candidate_state_count_not_two")
        else:
            for idx, state in enumerate(candidate_state):
                if not isinstance(state, Mapping) or state.get("eligible") is not True:
                    blockers.append(f"candidate_state_{idx}_not_eligible")

    downstream = artifact.get("downstream")
    if not isinstance(downstream, Mapping):
        blockers.append("downstream_missing")
    else:
        for flag in _FORBIDDEN_DOWNSTREAM_FLAGS:
            if downstream.get(flag) is not False:
                blockers.append(f"downstream_{flag}_not_false")

    caps = artifact.get("capability_deltas")
    if not isinstance(caps, Mapping):
        blockers.append("capability_deltas_missing")
    else:
        for key, value in caps.items():
            if int(value or 0) != 0:
                blockers.append(f"capability_delta_{key}_nonzero")

    now_dt = now if isinstance(now, datetime) else _parse_iso(str(now))
    try:
        expires_at = _parse_iso(str(artifact.get("expires_at") or ""))
        if now_dt > expires_at:
            blockers.append("artifact_expired")
    except (TypeError, ValueError):
        blockers.append("expires_at_unparseable")

    evidence_rows = artifact.get("evidence_rows")
    if not isinstance(evidence_rows, list) or not evidence_rows:
        blockers.append("evidence_rows_missing")
    else:
        for idx, row in enumerate(evidence_rows):
            if not isinstance(row, Mapping):
                blockers.append(f"evidence_row_{idx}_invalid")
                continue
            source_name = str(row.get("source_name") or "")
            if source_name not in SOURCE_REGISTRY:
                blockers.append(f"evidence_row_{idx}_unknown_source")
                continue
            try:
                received = _parse_iso(str(row.get("received_at") or ""))
            except (TypeError, ValueError):
                blockers.append(f"evidence_row_{idx}_received_at_invalid")
                continue
            stale_after = int(SOURCE_REGISTRY[source_name].stale_after_seconds)
            if now_dt - received > timedelta(seconds=stale_after):
                blockers.append(f"evidence_row_{idx}_stale")

    valid = not blockers
    return {
        "valid": valid,
        "blockers": blockers,
        "status": (
            "READINESS_ARTIFACT_VALID" if valid else "READINESS_ARTIFACT_INVALID"
        ),
        "schema_version": SCHEMA_VERSION,
    }


def artifact_canonical_json(artifact: Mapping[str, Any]) -> str:
    return json.dumps(artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


__all__ = [
    "SCHEMA_VERSION",
    "REQUIRED_GATE_NAMES",
    "PreLifecycleReadinessArtifactError",
    "compute_db_identity",
    "compute_readiness_artifact_expiry",
    "build_pre_lifecycle_readiness_artifact",
    "validate_pre_lifecycle_readiness_artifact",
    "artifact_canonical_json",
]
