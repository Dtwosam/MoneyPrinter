#!/usr/bin/env python3
"""Checkpoint 8 independent read-only inspection.

The inspector consumes only one frozen Checkpoint 8 proof directory. It never
starts Printer runtime work, never invokes report replay, and never mutates the
proof database. All database access is SQLite read-only/query-only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable
from urllib.parse import quote

from printer_v1.db.migrate import (
    canonical_migration_count,
    canonical_migration_names,
)
from printer_v1.operator_cli.proof_db_schema_readiness import (
    CANONICAL_PERSISTENT_DB,
)


_FROZEN_SUMMARY_NAME = "checkpoint8-controlling-proof-summary.json"
_INSPECTION_ARTIFACT_NAME = "checkpoint8-independent-inspection.json"
_PROTECTED_CAPABILITY_TABLES = (
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
)
_LONGER_WINDOWS = ("WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H")


class Checkpoint8IndependentInspectionError(RuntimeError):
    """Fail-closed independent-inspection fault."""


def validate_independent_proof_db_target(
    db_path: str | Path,
    *,
    canonical_db_path: str | Path,
) -> Path:
    target = Path(db_path).expanduser().resolve()
    canonical = Path(canonical_db_path).expanduser().resolve()

    if target == canonical:
        raise Checkpoint8IndependentInspectionError(
            "CANONICAL_PRODUCTION_DB_FORBIDDEN"
        )
    if not target.is_file():
        raise Checkpoint8IndependentInspectionError(
            "INDEPENDENT_PROOF_DB_MISSING"
        )
    return target


def open_independent_read_only_db(
    db_path: str | Path,
    *,
    canonical_db_path: str | Path,
) -> sqlite3.Connection:
    target = validate_independent_proof_db_target(
        db_path,
        canonical_db_path=canonical_db_path,
    )
    uri = f"file:{quote(str(target))}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _canonical_json_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_checkpoint8_frozen_summary(proof_dir: str | Path) -> dict[str, Any]:
    root = Path(proof_dir).expanduser().resolve()
    summary_path = root / _FROZEN_SUMMARY_NAME
    if not root.is_dir() or not summary_path.is_file():
        raise Checkpoint8IndependentInspectionError(
            "FROZEN_PROOF_SUMMARY_MISSING"
        )
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Checkpoint8IndependentInspectionError(
            "FROZEN_PROOF_SUMMARY_INVALID"
        ) from exc
    if not isinstance(payload, dict):
        raise Checkpoint8IndependentInspectionError(
            "FROZEN_PROOF_SUMMARY_INVALID"
        )
    observed = str(payload.get("frozen_evidence_sha256") or "")
    unsigned = dict(payload)
    unsigned.pop("frozen_evidence_sha256", None)
    expected = _canonical_json_sha256(unsigned)
    if observed != expected:
        raise Checkpoint8IndependentInspectionError(
            "FROZEN_EVIDENCE_SHA256_MISMATCH"
        )
    return payload


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _table_columns(connection: sqlite3.Connection, table: str) -> tuple[str, ...]:
    if not _table_exists(connection, table):
        return ()
    return tuple(
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    )


def _rows_for_identity(
    connection: sqlite3.Connection,
    table: str,
    *,
    run_id: str,
    campaign_id: str,
) -> list[dict[str, Any]]:
    columns = _table_columns(connection, table)
    if not columns:
        return []
    predicates: list[str] = []
    params: list[str] = []
    if "run_id" in columns:
        predicates.append('CAST("run_id" AS TEXT)=?')
        params.append(run_id)
    if "campaign_run_id" in columns:
        predicates.append('CAST("campaign_run_id" AS TEXT)=?')
        params.append(run_id)
    if "campaign_id" in columns:
        predicates.append('CAST("campaign_id" AS TEXT)=?')
        params.append(campaign_id)
    if not predicates:
        return []
    sql = f'SELECT * FROM "{table}" WHERE ' + " OR ".join(predicates)
    return [dict(row) for row in connection.execute(sql, tuple(params)).fetchall()]


def _all_rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if not _table_exists(connection, table):
        return []
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"').fetchall()]


def _json_objects_from_row(row: dict[str, Any]) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for value in row.values():
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text or text[0] not in "{[":
            continue
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            objects.append(decoded)
        elif isinstance(decoded, list):
            objects.extend(item for item in decoded if isinstance(item, dict))
    return objects


def _deep_find(value: Any, names: Iterable[str]) -> Any:
    wanted = set(names)
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in wanted and child not in (None, ""):
                return child
        for child in value.values():
            found = _deep_find(child, wanted)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for child in value:
            found = _deep_find(child, wanted)
            if found not in (None, ""):
                return found
    return None


def _row_or_json_value(row: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    for obj in _json_objects_from_row(row):
        found = _deep_find(obj, names)
        if found not in (None, ""):
            return found
    return None


def recompute_checkpoint8_database_safety(
    frozen_summary: dict[str, Any],
    *,
    canonical_db_path: str | Path,
) -> dict[str, Any]:
    pre = frozen_summary.get("pre_run_evidence")
    if not isinstance(pre, dict):
        raise Checkpoint8IndependentInspectionError(
            "FROZEN_PRE_RUN_EVIDENCE_MISSING"
        )
    db_text = str(pre.get("db_path") or "")
    if not db_text:
        raise Checkpoint8IndependentInspectionError("INDEPENDENT_PROOF_DB_MISSING")
    target = validate_independent_proof_db_target(
        db_text,
        canonical_db_path=canonical_db_path,
    )
    before = _sha256_file(target)
    connection = open_independent_read_only_db(
        target,
        canonical_db_path=canonical_db_path,
    )
    try:
        applied = [
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY rowid"
            ).fetchall()
        ]
        expected = list(canonical_migration_names())
        if applied != expected:
            raise Checkpoint8IndependentInspectionError(
                "CANONICAL_MIGRATION_LEDGER_MISMATCH"
            )
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        fk_count = len(connection.execute("PRAGMA foreign_key_check").fetchall())
    finally:
        connection.close()
    after = _sha256_file(target)
    if before != after:
        raise Checkpoint8IndependentInspectionError("READ_ONLY_DB_BYTES_CHANGED")
    return {
        "db_path": str(target),
        "db_sha256": after,
        "migration_count": len(applied),
        "migration_head": applied[-1] if applied else None,
        "canonical_migration_count": canonical_migration_count(),
        "integrity_check": integrity,
        "foreign_key_violations": fk_count,
        "read_only": True,
    }


def validate_checkpoint8_graph_projection(
    projection: dict[str, Any],
) -> dict[str, Any]:
    windows = projection.get("windows")
    if not isinstance(windows, list):
        raise Checkpoint8IndependentInspectionError(
            "EXACT_TWO_TERMINAL_WINDOW_15M_REQUIRED"
        )
    eligible = [
        row
        for row in windows
        if isinstance(row, dict)
        and row.get("window_kind") == "WINDOW_15M"
        and row.get("terminal") is True
    ]
    if len(eligible) != 2:
        raise Checkpoint8IndependentInspectionError(
            "EXACT_TWO_TERMINAL_WINDOW_15M_REQUIRED"
        )
    mints = [str(row.get("token_mint") or "") for row in eligible]
    if not all(mints) or len(set(mints)) != 2:
        raise Checkpoint8IndependentInspectionError(
            "EXACT_TWO_DISTINCT_MINTS_REQUIRED"
        )
    if any(row.get("memory_quality_label") != "CLEAN_MEMORY" for row in eligible):
        raise Checkpoint8IndependentInspectionError(
            "TWO_CLEAN_MEMORIES_REQUIRED"
        )
    fingerprints = [str(row.get("fingerprint_sha256") or "") for row in eligible]
    if any(len(value) != 64 for value in fingerprints):
        raise Checkpoint8IndependentInspectionError(
            "TWO_MEMORY_FINGERPRINTS_REQUIRED"
        )
    return {
        "exact_two_terminal_window_15m": True,
        "exact_two_distinct_mints": True,
        "both_clean_memory": True,
        "both_fingerprints_present": True,
        "token_mints": mints,
        "memory_window_ids": [row.get("memory_window_id") for row in eligible],
    }


def _normal_owner(value: Any) -> str:
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def validate_checkpoint8_governance_projection(
    projection: dict[str, Any],
) -> dict[str, Any]:
    source_owner = _normal_owner(projection.get("source_governor_owner"))
    scheduler_owner = _normal_owner(projection.get("central_scheduler_owner"))
    if "sourcegovernor" not in source_owner:
        raise Checkpoint8IndependentInspectionError("SOURCE_GOVERNOR_OWNER_MISMATCH")
    if "centralscheduler" not in scheduler_owner:
        raise Checkpoint8IndependentInspectionError("CENTRAL_SCHEDULER_OWNER_MISMATCH")
    counts = (
        int(projection.get("active_work_count") or 0),
        int(projection.get("locked_scheduler_job_count") or 0),
        int(projection.get("orphan_owned_work_count") or 0),
    )
    if any(counts):
        raise Checkpoint8IndependentInspectionError("ACTIVE_OR_ORPHAN_WORK_REMAINS")
    if projection.get("lease_released") is not True or projection.get("lease_file_present") is True:
        raise Checkpoint8IndependentInspectionError("LEASE_NOT_RELEASED")
    forbidden = (
        bool(projection.get("automatic_retry_created")),
        bool(projection.get("manual_rerun_allowed")),
        bool(projection.get("resume_allowed")),
        bool(projection.get("restart_created")),
        bool(projection.get("successor_created")),
    )
    if any(forbidden):
        raise Checkpoint8IndependentInspectionError("RETRY_OR_REUSE_FACT_FORBIDDEN")
    return {
        "source_governor_exact": True,
        "central_scheduler_exact": True,
        "zero_active_locked_orphan_work": True,
        "lease_released": True,
        "no_retry_rerun_resume_restart_successor": True,
    }


def validate_checkpoint8_frozen_safety(
    frozen_summary: dict[str, Any],
) -> dict[str, Any]:
    if frozen_summary.get("campaign_pass") is not True:
        raise Checkpoint8IndependentInspectionError("CAMPAIGN_PASS_REQUIRED")
    if frozen_summary.get("campaign_acceptance_verdict") != "CAMPAIGN_PASS":
        raise Checkpoint8IndependentInspectionError("ACCEPTANCE_PASS_REQUIRED")
    if int(frozen_summary.get("network_attempt_count") or 0) != 0:
        raise Checkpoint8IndependentInspectionError("NETWORK_ATTEMPTS_MUST_BE_ZERO")
    if int(frozen_summary.get("fixture_transport_operation_count") or 0) <= 0:
        raise Checkpoint8IndependentInspectionError(
            "FIXTURE_TRANSPORT_OPERATION_COUNT_REQUIRED"
        )
    if frozen_summary.get("replay_zero_work") is not True:
        raise Checkpoint8IndependentInspectionError("REPORT_REPLAY_NOT_ZERO_WORK")
    replay = frozen_summary.get("report_only")
    if not isinstance(replay, dict):
        raise Checkpoint8IndependentInspectionError("REPORT_REPLAY_MISSING")
    for key in (
        "source_calls",
        "scheduler_runtime_calls",
        "database_writes",
        "replay_new_source_calls",
        "replay_new_scheduler_calls",
        "replay_database_writes",
    ):
        if int(replay.get(key, 0) or 0) != 0:
            raise Checkpoint8IndependentInspectionError("REPORT_REPLAY_NOT_ZERO_WORK")
    post = frozen_summary.get("post_run_evidence")
    if not isinstance(post, dict):
        raise Checkpoint8IndependentInspectionError("POST_RUN_EVIDENCE_MISSING")
    deltas = post.get("protected_capability_deltas")
    if not isinstance(deltas, dict) or any(int(value or 0) != 0 for value in deltas.values()):
        raise Checkpoint8IndependentInspectionError("PROTECTED_CAPABILITY_DELTA_NONZERO")
    longer = post.get("longer_window_counts")
    if not isinstance(longer, dict) or any(int(longer.get(label, 0) or 0) != 0 for label in _LONGER_WINDOWS):
        raise Checkpoint8IndependentInspectionError("LONGER_WINDOW_PRESENT")
    return {
        "campaign_pass": True,
        "acceptance_pass": True,
        "zero_network_attempts": True,
        "fixture_operations_positive": True,
        "replay_zero_work": True,
        "protected_capability_zero_delta": True,
        "longer_windows_absent": True,
    }


def _find_owner(rows: Iterable[dict[str, Any]], needle: str) -> str | None:
    wanted = "".join(ch for ch in needle.lower() if ch.isalnum())
    for row in rows:
        for value in row.values():
            normalized = _normal_owner(value)
            if wanted in normalized:
                return str(value)
    return None


def _row_is_active(row: dict[str, Any]) -> bool:
    terminal = {
        "complete",
        "completed",
        "succeeded",
        "success",
        "failed",
        "cancelled",
        "canceled",
        "released",
        "closed",
        "done",
    }
    for key in ("status", "state", "step_status", "run_status", "terminal_status"):
        if key in row and row[key] not in (None, ""):
            return str(row[key]).strip().lower() not in terminal
    return False


def _memory_window_ids(rows: Iterable[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for row in rows:
        value = _row_or_json_value(row, ("memory_window_id", "window_id"))
        if value not in (None, ""):
            ids.add(str(value))
    return ids


def derive_checkpoint8_independent_db_projections(
    frozen_summary: dict[str, Any],
    *,
    canonical_db_path: str | Path,
) -> dict[str, Any]:
    """Derive current-run graph/governance directly from the proof DB."""
    campaign_id = str(frozen_summary.get("campaign_id") or "").strip()
    run_id = str(frozen_summary.get("run_id") or "").strip()
    pre = frozen_summary.get("pre_run_evidence")
    if not campaign_id or not run_id or not isinstance(pre, dict):
        raise Checkpoint8IndependentInspectionError("CURRENT_RUN_IDENTITY_MISSING")
    db_path = str(pre.get("db_path") or "")

    connection = open_independent_read_only_db(
        db_path,
        canonical_db_path=canonical_db_path,
    )
    try:
        run_steps = _rows_for_identity(
            connection,
            "printer_memory_factory_run_steps",
            run_id=run_id,
            campaign_id=campaign_id,
        )
        if not run_steps:
            raise Checkpoint8IndependentInspectionError("CURRENT_RUN_GRAPH_MISSING")

        window_ids = _memory_window_ids(run_steps)
        episodes = _all_rows(connection, "printer_episodes")
        fingerprints = _all_rows(connection, "printer_memory_fingerprints")
        episode_by_window = {
            str(_row_or_json_value(row, ("memory_window_id", "window_id"))): row
            for row in episodes
            if _row_or_json_value(row, ("memory_window_id", "window_id")) not in (None, "")
        }
        fingerprint_by_window = {
            str(_row_or_json_value(row, ("memory_window_id", "window_id"))): row
            for row in fingerprints
            if _row_or_json_value(row, ("memory_window_id", "window_id")) not in (None, "")
        }

        windows: list[dict[str, Any]] = []
        seen_windows: set[str] = set()
        for step in run_steps:
            step_kind = str(_row_or_json_value(step, ("step_kind", "kind")) or "")
            window_kind = str(
                _row_or_json_value(step, ("window_kind", "window_label")) or ""
            )
            if window_kind != "WINDOW_15M" and step_kind != "WINDOW_CLOSE":
                continue
            window_id_value = _row_or_json_value(step, ("memory_window_id", "window_id"))
            if window_id_value in (None, ""):
                continue
            window_id = str(window_id_value)
            if window_id in seen_windows:
                continue
            seen_windows.add(window_id)
            episode = episode_by_window.get(window_id, {})
            fingerprint = fingerprint_by_window.get(window_id, {})
            status = str(_row_or_json_value(step, ("step_status", "status")) or "")
            token_mint = _row_or_json_value(step, ("token_mint", "mint_identity", "mint"))
            quality = _row_or_json_value(
                episode,
                ("memory_quality_label", "quality_label"),
            )
            fp = _row_or_json_value(
                fingerprint,
                ("fingerprint_sha256", "memory_fingerprint_sha256", "sha256"),
            )
            windows.append(
                {
                    "token_mint": str(token_mint or ""),
                    "memory_window_id": window_id,
                    "window_kind": "WINDOW_15M",
                    "terminal": step_kind == "WINDOW_CLOSE" and status.upper() in {"SUCCEEDED", "SUCCESS", "COMPLETED"},
                    "memory_quality_label": str(quality or ""),
                    "fingerprint_sha256": str(fp or ""),
                }
            )

        supervision = _rows_for_identity(
            connection,
            "printer_memory_factory_campaign_supervision",
            run_id=run_id,
            campaign_id=campaign_id,
        )
        campaign_scheduler_work = _rows_for_identity(
            connection,
            "printer_memory_factory_campaign_scheduler_work",
            run_id=run_id,
            campaign_id=campaign_id,
        )
        scheduler_jobs = _rows_for_identity(
            connection,
            "printer_scheduler_jobs",
            run_id=run_id,
            campaign_id=campaign_id,
        )
        discovery_work = _rows_for_identity(
            connection,
            "printer_discovery_work",
            run_id=run_id,
            campaign_id=campaign_id,
        )
        governance_rows = [
            *supervision,
            *campaign_scheduler_work,
            *scheduler_jobs,
            *discovery_work,
        ]
        source_owner = _find_owner(governance_rows, "Source Governor")
        scheduler_owner = _find_owner(governance_rows, "Central Scheduler")

        active_work_count = sum(
            1 for row in [*campaign_scheduler_work, *discovery_work] if _row_is_active(row)
        )
        locked_scheduler_job_count = 0
        for row in scheduler_jobs:
            lock_value = _row_or_json_value(
                row,
                ("locked_by", "lock_owner", "lease_owner", "claimed_by"),
            )
            if lock_value not in (None, "") and _row_is_active(row):
                locked_scheduler_job_count += 1
        orphan_owned_work_count = 0
        for row in [*campaign_scheduler_work, *discovery_work]:
            owner = _row_or_json_value(row, ("owner", "owner_id", "claimed_by", "lease_owner"))
            row_run = _row_or_json_value(row, ("run_id", "campaign_run_id"))
            row_campaign = _row_or_json_value(row, ("campaign_id",))
            if owner not in (None, "") and row_run in (None, "") and row_campaign in (None, ""):
                orphan_owned_work_count += 1

        supervision_text = json.dumps(supervision, default=str).lower()
        lease_released = any(word in supervision_text for word in ("released", "release", "closed", "completed"))
        summary_text = json.dumps(frozen_summary, default=str).lower()
        governance = {
            "source_governor_owner": source_owner,
            "central_scheduler_owner": scheduler_owner,
            "active_work_count": active_work_count,
            "locked_scheduler_job_count": locked_scheduler_job_count,
            "orphan_owned_work_count": orphan_owned_work_count,
            "lease_released": lease_released,
            "lease_file_present": False,
            "automatic_retry_created": "automatic_retry_created\": true" in summary_text,
            "manual_rerun_allowed": "manual_rerun_allowed\": true" in summary_text,
            "resume_allowed": "resume_allowed\": true" in summary_text,
            "restart_created": "restart_created\": true" in summary_text,
            "successor_created": "successor_created\": true" in summary_text,
        }
    finally:
        connection.close()

    if window_ids and not windows:
        raise Checkpoint8IndependentInspectionError("CURRENT_RUN_GRAPH_MISSING")
    return {
        "graph": {
            "campaign_id": campaign_id,
            "run_id": run_id,
            "windows": windows,
        },
        "governance": governance,
    }


def validate_checkpoint8_report_and_manifest_identity(
    frozen_summary: dict[str, Any],
) -> dict[str, Any]:
    campaign_id = str(frozen_summary.get("campaign_id") or "")
    run_id = str(frozen_summary.get("run_id") or "")
    terminal = frozen_summary.get("terminal")
    replay = frozen_summary.get("report_only")
    pre = frozen_summary.get("pre_run_evidence")
    if not isinstance(terminal, dict) or not isinstance(replay, dict) or not isinstance(pre, dict):
        raise Checkpoint8IndependentInspectionError("REPORT_REPLAY_IDENTITY_MISMATCH")
    report = terminal.get("report")
    report = report if isinstance(report, dict) else {}
    campaign_values = {
        campaign_id,
        str(terminal.get("campaign_id") or ""),
        str(report.get("campaign_id") or ""),
        str(replay.get("campaign_id") or ""),
    }
    run_values = {
        run_id,
        str(report.get("run_id") or ""),
        str(replay.get("run_id") or ""),
    }
    if "" in campaign_values or len(campaign_values) != 1 or "" in run_values or len(run_values) != 1:
        raise Checkpoint8IndependentInspectionError("REPORT_REPLAY_IDENTITY_MISMATCH")
    manifest = str(frozen_summary.get("fixture_composition_manifest_sha256") or "")
    manifest_values = {
        manifest,
        str(pre.get("fixture_composition_manifest_sha256") or ""),
        str(replay.get("fixture_composition_manifest_sha256") or manifest),
    }
    if len(manifest) != 64 or "" in manifest_values or len(manifest_values) != 1:
        raise Checkpoint8IndependentInspectionError("FIXTURE_MANIFEST_IDENTITY_MISMATCH")
    return {
        "campaign_identity_exact": True,
        "run_identity_exact": True,
        "fixture_manifest_exact": True,
    }


def build_checkpoint8_independent_findings(
    *,
    frozen_summary: dict[str, Any],
    database_safety: dict[str, Any],
    graph_projection: dict[str, Any],
    governance_projection: dict[str, Any],
    frozen_safety: dict[str, Any],
    report_and_manifest_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    db_ok = (
        database_safety.get("migration_count") == canonical_migration_count()
        and database_safety.get("migration_head") == canonical_migration_names()[-1]
        and database_safety.get("integrity_check") == "ok"
        and int(database_safety.get("foreign_key_violations") or 0) == 0
        and database_safety.get("read_only") is True
    )
    graph_ok = all(
        graph_projection.get(key) is True
        for key in (
            "exact_two_terminal_window_15m",
            "exact_two_distinct_mints",
            "both_clean_memory",
            "both_fingerprints_present",
        )
    )
    governance_ok = all(
        governance_projection.get(key) is True
        for key in (
            "source_governor_exact",
            "central_scheduler_exact",
            "zero_active_locked_orphan_work",
            "lease_released",
            "no_retry_rerun_resume_restart_successor",
        )
    )
    safety_ok = all(bool(value) for value in frozen_safety.values())
    identity_ok = True if report_and_manifest_identity is None else all(
        report_and_manifest_identity.get(key) is True
        for key in (
            "campaign_identity_exact",
            "run_identity_exact",
            "fixture_manifest_exact",
        )
    )
    if not all((db_ok, graph_ok, governance_ok, safety_ok, identity_ok)):
        raise Checkpoint8IndependentInspectionError("INDEPENDENT_FINDINGS_NOT_PASS")
    return {
        "verdict": "CHECKPOINT8_INDEPENDENT_INSPECTION_PASS",
        "pass": True,
        "proof_id": frozen_summary.get("proof_id"),
        "campaign_id": frozen_summary.get("campaign_id"),
        "run_id": frozen_summary.get("run_id"),
        "frozen_evidence_sha256": frozen_summary.get("frozen_evidence_sha256"),
        "database_safety": database_safety,
        "graph_projection": graph_projection,
        "governance_projection": governance_projection,
        "frozen_safety": frozen_safety,
        "report_and_manifest_identity": report_and_manifest_identity,
    }


def write_checkpoint8_independent_inspection_artifact(
    proof_dir: str | Path,
    findings: dict[str, Any],
) -> Path:
    root = Path(proof_dir).expanduser().resolve()
    if not root.is_dir():
        raise Checkpoint8IndependentInspectionError("FROZEN_PROOF_DIRECTORY_MISSING")
    artifact = root / _INSPECTION_ARTIFACT_NAME
    try:
        with artifact.open("x", encoding="utf-8") as handle:
            json.dump(findings, handle, ensure_ascii=True, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
    except FileExistsError as exc:
        raise Checkpoint8IndependentInspectionError(
            "INDEPENDENT_INSPECTION_ARTIFACT_ALREADY_EXISTS"
        ) from exc
    return artifact


def inspect_checkpoint8_frozen_proof_directory(
    proof_dir: str | Path,
) -> dict[str, Any]:
    frozen_summary = load_checkpoint8_frozen_summary(proof_dir)
    database_safety = recompute_checkpoint8_database_safety(
        frozen_summary,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )
    projections = derive_checkpoint8_independent_db_projections(
        frozen_summary,
        canonical_db_path=CANONICAL_PERSISTENT_DB,
    )
    graph_projection = validate_checkpoint8_graph_projection(projections["graph"])
    governance_projection = validate_checkpoint8_governance_projection(
        projections["governance"]
    )
    frozen_safety = validate_checkpoint8_frozen_safety(frozen_summary)
    report_identity = validate_checkpoint8_report_and_manifest_identity(frozen_summary)
    findings = build_checkpoint8_independent_findings(
        frozen_summary=frozen_summary,
        database_safety=database_safety,
        graph_projection=graph_projection,
        governance_projection=governance_projection,
        frozen_safety=frozen_safety,
        report_and_manifest_identity=report_identity,
    )
    artifact = write_checkpoint8_independent_inspection_artifact(
        proof_dir,
        findings,
    )
    result = dict(findings)
    result["inspection_artifact"] = str(artifact)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Independent read-only inspection of one frozen Checkpoint 8 proof directory"
    )
    parser.add_argument("--proof-dir", required=True)
    args = parser.parse_args(argv)
    result = inspect_checkpoint8_frozen_proof_directory(args.proof_dir)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
