"""Zero-source, read-only verification of a terminal campaign report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from printer_v1.operator_cli.final_campaign_report import (
    FinalCampaignReportError,
    assemble_final_campaign_report,
)
from printer_v1.operator_cli.git_provenance import (
    GitProvenanceError,
    validate_launch_provenance,
)


REPLAY_VERIFIED = "REPLAY_VERIFIED"
REPLAY_BLOCKED = "REPLAY_BLOCKED"
_HASH = re.compile(r"[0-9a-f]{64}")


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: Mapping[str, Any]) -> tuple[str, bytes, str]:
    text = json.dumps(
        dict(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    )
    payload = text.encode("utf-8")
    return text, payload, hashlib.sha256(payload).hexdigest()


def _row_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = [
        str(row[0]) for row in connection.execute(
            """SELECT name FROM sqlite_master
               WHERE type='table' AND name NOT LIKE 'sqlite_%'
               ORDER BY name"""
        ).fetchall()
    ]
    counts: dict[str, int] = {}
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        counts[table] = int(
            connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
        )
    return counts


def _json_object(value: object, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed


def _diagnostics(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "identity": report["identity"],
        "terminal": report["terminal"],
        "launch_git_provenance": report["launch_git_provenance"],
        "promotion_outcomes_b1": report["promotion_outcomes_b1"],
        "safety_contexts_b2": report["safety_contexts_b2"],
        "lifecycle_b3": report["lifecycle_b3"],
        "operational_supervision": report["operational_supervision"],
        "visible_unknowns_and_evidence_gaps": report[
            "visible_unknowns_and_evidence_gaps"
        ],
        "opportunity_outcome_layers": report["opportunity_outcome_layers"],
        "source_scheduler_ceiling_usage": report[
            "source_scheduler_ceiling_usage"
        ],
        "locked_capabilities": report["locked_capabilities"],
    }


def replay_terminal_campaign_report(
    db_path: str | Path,
    *,
    campaign_id: str,
    configuration_id: str,
    report_id: str,
    report_hash: str,
) -> dict[str, Any]:
    """Verify one immutable terminal report without invoking or writing work."""
    path = Path(db_path).resolve()
    reasons: list[str] = []
    diagnostics: dict[str, Any] | None = None
    stored_hash: str | None = None
    run_id: str | None = None
    total_changes = 0
    before_counts: dict[str, int] = {}
    after_counts: dict[str, int] = {}

    if not path.is_file():
        reasons.append(f"database missing: {path}")
        return _result(
            campaign_id=campaign_id, configuration_id=configuration_id,
            report_id=report_id, expected_hash=report_hash,
            stored_hash=None, run_id=None, reasons=reasons,
            before_hash=None, after_hash=None, before_counts={},
            after_counts={}, total_changes=0, diagnostics=None,
        )

    before_hash = _file_hash(path)
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"file:{path.as_posix()}?mode=ro", uri=True, timeout=0.0
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        before_counts = _row_counts(connection)
        if _HASH.fullmatch(report_hash) is None:
            raise ValueError("expected report hash is malformed")

        rows = connection.execute(
            """SELECT report_id,campaign_id,configuration_id,report_kind,
                      report_state,report_hash,report_json
               FROM printer_memory_factory_campaign_reports
               WHERE report_id=? AND campaign_id=? AND configuration_id=?""",
            (report_id, campaign_id, configuration_id),
        ).fetchall()
        if len(rows) != 1:
            raise ValueError("report identity or state mismatch")
        row = dict(rows[0])
        if row["report_kind"] != "TERMINAL" or row["report_state"] != "REPORT_TERMINAL":
            raise ValueError("report identity or state mismatch")
        stored_hash = str(row["report_hash"])
        if stored_hash != report_hash:
            raise ValueError("expected report hash mismatch")

        stored_report = _json_object(row["report_json"], "stored report payload")
        canonical_json, _, canonical_hash = _canonical(stored_report)
        if canonical_json != row["report_json"]:
            raise ValueError("stored report payload is not canonical JSON")
        if canonical_hash != stored_hash:
            raise ValueError("stored report hash does not match canonical payload")

        identity = stored_report.get("identity")
        if not isinstance(identity, Mapping):
            raise ValueError("stored report identity is missing")
        if (
            identity.get("campaign_id") != campaign_id
            or identity.get("configuration_id") != configuration_id
        ):
            raise ValueError("stored report identity mismatch")
        run_id_value = identity.get("run_id")
        if not isinstance(run_id_value, str) or not run_id_value.strip():
            raise ValueError("stored report run identity is missing")
        run_id = run_id_value

        configuration = connection.execute(
            """SELECT launch_provenance_json
               FROM printer_memory_factory_campaign_configurations
               WHERE campaign_id=? AND configuration_id=?""",
            (campaign_id, configuration_id),
        ).fetchone()
        if configuration is None:
            raise ValueError("stored campaign configuration is missing")
        configured_provenance = _json_object(
            configuration["launch_provenance_json"],
            "stored configuration Git provenance",
        )
        report_provenance = stored_report.get("launch_git_provenance")
        try:
            validated_configuration = validate_launch_provenance(
                configured_provenance
            )
            validated_report = validate_launch_provenance(report_provenance)
        except GitProvenanceError as exc:
            raise ValueError("stored Git provenance is invalid") from exc
        if validated_configuration != validated_report:
            raise ValueError("stored launch Git provenance mismatch")

        linked_ids = tuple(
            str(link[0]) for link in connection.execute(
                """SELECT object_id
                   FROM printer_memory_factory_campaign_report_objects
                   WHERE report_id=? AND campaign_id=? AND configuration_id=?
                   ORDER BY object_id""",
                (report_id, campaign_id, configuration_id),
            ).fetchall()
        )
        payload_ids = stored_report.get("report_object_ids")
        if not isinstance(payload_ids, list) or tuple(payload_ids) != linked_ids:
            raise ValueError("stored report object links mismatch")

        assembled = assemble_final_campaign_report(
            path, campaign_id=campaign_id,
            configuration_id=configuration_id, run_id=run_id,
        )
        if assembled.object_ids != linked_ids:
            raise ValueError("recomputed report object links mismatch")
        if assembled.report_hash != stored_hash:
            raise ValueError("recomputed authoritative report hash mismatch")
        if assembled.canonical_json != canonical_json:
            raise ValueError("recomputed authoritative report differs from stored report")
        diagnostics = _diagnostics(assembled.report)
    except (FinalCampaignReportError, KeyError, TypeError, ValueError, sqlite3.Error) as exc:
        reasons.append(str(exc))
    finally:
        if connection is not None:
            try:
                after_counts = _row_counts(connection)
                total_changes = int(connection.total_changes)
            except sqlite3.Error as exc:
                reasons.append(f"read-only after-state inspection failed: {exc}")
            connection.close()

    after_hash = _file_hash(path)
    if before_hash != after_hash:
        reasons.append("database file hash changed during replay")
    if before_counts != after_counts:
        reasons.append("database row counts changed during replay")
    if total_changes != 0:
        reasons.append("SQLite total_changes was nonzero during replay")
    return _result(
        campaign_id=campaign_id, configuration_id=configuration_id,
        report_id=report_id, expected_hash=report_hash,
        stored_hash=stored_hash, run_id=run_id, reasons=reasons,
        before_hash=before_hash, after_hash=after_hash,
        before_counts=before_counts, after_counts=after_counts,
        total_changes=total_changes, diagnostics=diagnostics,
    )


def _result(
    *,
    campaign_id: str,
    configuration_id: str,
    report_id: str,
    expected_hash: str,
    stored_hash: str | None,
    run_id: str | None,
    reasons: list[str],
    before_hash: str | None,
    after_hash: str | None,
    before_counts: Mapping[str, int],
    after_counts: Mapping[str, int],
    total_changes: int,
    diagnostics: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return {
        "replay_state": REPLAY_BLOCKED if reasons else REPLAY_VERIFIED,
        "reasons": list(reasons),
        "identity": {
            "campaign_id": campaign_id,
            "configuration_id": configuration_id,
            "report_id": report_id,
            "run_id": run_id,
            "expected_report_hash": expected_hash,
            "stored_report_hash": stored_hash,
        },
        "diagnostics": dict(diagnostics) if diagnostics is not None else None,
        "zero_work_evidence": {
            "source_calls": 0,
            "scheduler_work": 0,
            "memory_writes": 0,
            "database_writes": 0,
        },
        "database_read_only_evidence": {
            "sqlite_mode": "mode=ro",
            "query_only": True,
            "before_sha256": before_hash,
            "after_sha256": after_hash,
            "before_row_counts": dict(before_counts),
            "after_row_counts": dict(after_counts),
            "total_changes": total_changes,
        },
        "git_provenance_recaptured": False,
        "replay_row_persisted": False,
    }
