"""Persistence-only campaign, configuration, and report records."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from printer_v1.operator_cli.git_provenance import (
    GitProvenanceError,
    validate_launch_provenance,
)


DB_MODE_PROOF_ISOLATED = "PROOF_ISOLATED"
DB_MODE_OPERATIONAL_PERSISTENT = "OPERATIONAL_PERSISTENT"
CAMPAIGN_STATES = frozenset(
    {
        "DRAFT", "PREFLIGHT", "RUNNING", "STOP_REQUESTED",
        "TERMINAL_COMPLETED", "TERMINAL_STOPPED", "TERMINAL_BLOCKED",
        "TERMINAL_FAILED",
    }
)
TERMINAL_CAMPAIGN_STATES = frozenset(
    {
        "TERMINAL_COMPLETED", "TERMINAL_STOPPED", "TERMINAL_BLOCKED",
        "TERMINAL_FAILED",
    }
)
REPLAY_STATES = frozenset({"REPLAY_VERIFIED", "REPLAY_BLOCKED"})


class CampaignPersistenceError(ValueError):
    """Fail-closed campaign persistence contract violation."""


def _nonempty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CampaignPersistenceError(f"{field} must be a non-empty string")
    return value


def _utc_text(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def _canonical_json(value: Mapping[str, Any], field: str) -> str:
    if not isinstance(value, Mapping):
        raise CampaignPersistenceError(f"{field} must be an object")
    try:
        return json.dumps(
            dict(value), allow_nan=False, ensure_ascii=True,
            separators=(",", ":"), sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise CampaignPersistenceError(f"{field} is not canonical JSON") from exc


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _configuration_material(
    configuration: Mapping[str, Any],
    launch_provenance: Mapping[str, Any],
) -> tuple[str, str, str]:
    config_json = _canonical_json(configuration, "campaign configuration")
    try:
        provenance = validate_launch_provenance(launch_provenance)
    except (GitProvenanceError, TypeError, ValueError) as exc:
        raise CampaignPersistenceError("launch Git provenance is invalid") from exc
    provenance_json = _canonical_json(provenance, "launch Git provenance")
    envelope = _canonical_json(
        {
            "configuration": json.loads(config_json),
            "git_provenance": json.loads(provenance_json),
        },
        "campaign configuration envelope",
    )
    return config_json, provenance_json, _sha256_text(envelope)


def _campaign_record(
    connection: sqlite3.Connection, campaign_id: str
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT c.campaign_id, c.campaign_state, c.db_mode,
               c.db_target_identity, c.proof_source_db_identity,
               c.policy_version, c.first_terminal_cause, c.terminal_at,
               cfg.configuration_id, cfg.configuration_hash,
               cfg.configuration_json, cfg.launch_provenance_json
        FROM printer_memory_factory_campaigns AS c
        JOIN printer_memory_factory_campaign_configurations AS cfg
          ON cfg.campaign_id = c.campaign_id
        WHERE c.campaign_id = ?
        """,
        (campaign_id,),
    ).fetchone()
    if row is None:
        raise CampaignPersistenceError("campaign persistence is incomplete")
    return dict(row)


def create_campaign(
    db_path: str | Path,
    *,
    campaign_id: str,
    configuration_id: str,
    configuration: Mapping[str, Any],
    launch_provenance: Mapping[str, Any],
    db_mode: str,
    db_target_identity: str,
    policy_version: str,
    proof_source_db_identity: str | None = None,
    campaign_state: str = "DRAFT",
    first_terminal_cause: str | None = None,
    terminal_at: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Atomically create one campaign and its immutable configuration."""
    campaign_id = _nonempty(campaign_id, "campaign_id")
    configuration_id = _nonempty(configuration_id, "configuration_id")
    target = _nonempty(db_target_identity, "db_target_identity")
    policy_version = _nonempty(policy_version, "policy_version")
    if campaign_state not in CAMPAIGN_STATES:
        raise CampaignPersistenceError("campaign_state is unsupported")
    terminal = campaign_state in TERMINAL_CAMPAIGN_STATES
    if terminal != bool(first_terminal_cause and terminal_at):
        raise CampaignPersistenceError("campaign terminal fields are inconsistent")
    if db_mode == DB_MODE_PROOF_ISOLATED:
        source = _nonempty(
            proof_source_db_identity or "", "proof_source_db_identity"
        )
        if source == target:
            raise CampaignPersistenceError("proof and source DB identities must differ")
    elif db_mode == DB_MODE_OPERATIONAL_PERSISTENT:
        if proof_source_db_identity is not None:
            raise CampaignPersistenceError(
                "operational mode cannot carry a proof source DB identity"
            )
        source = None
    else:
        raise CampaignPersistenceError("db_mode is unsupported")

    config_json, provenance_json, config_hash = _configuration_material(
        configuration, launch_provenance
    )
    created_at = _utc_text(now)
    connection = _connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT 1 FROM printer_memory_factory_campaigns WHERE campaign_id = ?",
            (campaign_id,),
        ).fetchone()
        if existing is not None:
            record = _campaign_record(connection, campaign_id)
            expected = {
                "campaign_state": campaign_state,
                "db_mode": db_mode,
                "db_target_identity": target,
                "proof_source_db_identity": source,
                "policy_version": policy_version,
                "first_terminal_cause": first_terminal_cause,
                "terminal_at": terminal_at,
                "configuration_id": configuration_id,
                "configuration_hash": config_hash,
                "configuration_json": config_json,
                "launch_provenance_json": provenance_json,
            }
            if any(record[key] != value for key, value in expected.items()):
                raise CampaignPersistenceError(
                    "campaign identity or immutable configuration already differs"
                )
            connection.rollback()
            return record

        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaigns(
                campaign_id, campaign_state, db_mode, db_target_identity,
                proof_source_db_identity, policy_version,
                first_terminal_cause, terminal_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                campaign_id, campaign_state, db_mode, target, source,
                policy_version, first_terminal_cause, terminal_at,
                created_at, created_at,
            ),
        )
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_configurations(
                configuration_id, campaign_id, configuration_hash,
                configuration_json, launch_provenance_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                configuration_id, campaign_id, config_hash, config_json,
                provenance_json, created_at,
            ),
        )
        connection.commit()
        return _campaign_record(connection, campaign_id)
    except CampaignPersistenceError:
        connection.rollback()
        raise
    except sqlite3.Error as exc:
        connection.rollback()
        raise CampaignPersistenceError(f"campaign persistence failed: {exc}") from exc
    finally:
        connection.close()


def persist_terminal_report(
    db_path: str | Path,
    *,
    report_id: str,
    campaign_id: str,
    configuration_id: str,
    report: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Persist one immutable terminal report payload without running work."""
    return _persist_report(
        db_path,
        report_id=report_id,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        report_kind="TERMINAL",
        report_state="REPORT_TERMINAL",
        report=report,
        replay_of_report_id=None,
        now=now,
    )


def persist_terminal_report_with_objects(
    db_path: str | Path,
    *,
    report_id: str,
    campaign_id: str,
    configuration_id: str,
    report: Mapping[str, Any],
    object_ids: tuple[str, ...],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Atomically persist one terminal report and its immutable object links."""
    report_id = _nonempty(report_id, "report_id")
    campaign_id = _nonempty(campaign_id, "campaign_id")
    configuration_id = _nonempty(configuration_id, "configuration_id")
    if not isinstance(object_ids, tuple) or not object_ids or any(
        not isinstance(value, str) or not value.strip() for value in object_ids
    ):
        raise CampaignPersistenceError("object_ids must be non-empty strings")
    if len(set(object_ids)) != len(object_ids):
        raise CampaignPersistenceError("object_ids must be unique")
    ordered_object_ids = tuple(sorted(object_ids))
    report_json = _canonical_json(report, "campaign report")
    report_hash = _sha256_text(report_json)
    connection = _connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT * FROM printer_memory_factory_campaign_reports WHERE report_id=?",
            (report_id,),
        ).fetchone()
        expected = {
            "campaign_id": campaign_id,
            "configuration_id": configuration_id,
            "report_kind": "TERMINAL",
            "report_state": "REPORT_TERMINAL",
            "replay_of_report_id": None,
            "report_hash": report_hash,
            "report_json": report_json,
        }
        if existing is not None:
            record = dict(existing)
            if any(record[key] != value for key, value in expected.items()):
                raise CampaignPersistenceError(
                    "report identity or immutable payload already differs"
                )
            linked = tuple(
                str(row[0]) for row in connection.execute(
                    """SELECT object_id
                       FROM printer_memory_factory_campaign_report_objects
                       WHERE report_id=? ORDER BY object_id""",
                    (report_id,),
                ).fetchall()
            )
            if linked != ordered_object_ids:
                raise CampaignPersistenceError("immutable report object links differ")
            connection.rollback()
            return {**record, "idempotent_replay": True}

        known = tuple(
            str(row[0]) for row in connection.execute(
                """SELECT object_id FROM printer_memory_factory_campaign_objects
                   WHERE campaign_id=? AND configuration_id=?
                     AND object_id IN ({}) ORDER BY object_id""".format(
                    ",".join("?" for _ in ordered_object_ids) or "NULL"
                ),
                (campaign_id, configuration_id, *ordered_object_ids),
            ).fetchall()
        )
        if known != ordered_object_ids:
            raise CampaignPersistenceError(
                "report object ownership is incomplete or mismatched"
            )
        created_at = _utc_text(now)
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_reports(
                   report_id,campaign_id,configuration_id,report_kind,
                   report_state,created_at
               ) VALUES (?,?,?,'TERMINAL','REPORT_PENDING',?)""",
            (report_id, campaign_id, configuration_id, created_at),
        )
        connection.executemany(
            """INSERT INTO printer_memory_factory_campaign_report_objects(
                   report_id,campaign_id,configuration_id,object_id,created_at
               ) VALUES (?,?,?,?,?)""",
            (
                (report_id, campaign_id, configuration_id, object_id, created_at)
                for object_id in ordered_object_ids
            ),
        )
        cursor = connection.execute(
            """UPDATE printer_memory_factory_campaign_reports
               SET report_state='REPORT_TERMINAL',report_hash=?,report_json=?
               WHERE report_id=? AND report_state='REPORT_PENDING'""",
            (report_hash, report_json, report_id),
        )
        if cursor.rowcount != 1:
            raise CampaignPersistenceError(
                "pending terminal report compare-and-update failed"
            )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM printer_memory_factory_campaign_reports WHERE report_id=?",
            (report_id,),
        ).fetchone()
        return {**dict(row), "idempotent_replay": False}
    except CampaignPersistenceError:
        connection.rollback()
        raise
    except sqlite3.Error as exc:
        connection.rollback()
        raise CampaignPersistenceError(f"report persistence failed: {exc}") from exc
    finally:
        connection.close()


def persist_report_replay(
    db_path: str | Path,
    *,
    report_id: str,
    campaign_id: str,
    configuration_id: str,
    replay_of_report_id: str,
    replay_state: str,
    report: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Persist replay identity/result only; this function performs no replay."""
    if replay_state not in REPLAY_STATES:
        raise CampaignPersistenceError("replay_state is unsupported")
    return _persist_report(
        db_path,
        report_id=report_id,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        report_kind="REPLAY",
        report_state=replay_state,
        report=report,
        replay_of_report_id=_nonempty(
            replay_of_report_id, "replay_of_report_id"
        ),
        now=now,
    )


def _persist_report(
    db_path: str | Path,
    *,
    report_id: str,
    campaign_id: str,
    configuration_id: str,
    report_kind: str,
    report_state: str,
    report: Mapping[str, Any],
    replay_of_report_id: str | None,
    now: datetime | None,
) -> dict[str, Any]:
    report_id = _nonempty(report_id, "report_id")
    campaign_id = _nonempty(campaign_id, "campaign_id")
    configuration_id = _nonempty(configuration_id, "configuration_id")
    report_json = _canonical_json(report, "campaign report")
    report_hash = _sha256_text(report_json)
    connection = _connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT * FROM printer_memory_factory_campaign_reports WHERE report_id = ?",
            (report_id,),
        ).fetchone()
        expected = {
            "campaign_id": campaign_id,
            "configuration_id": configuration_id,
            "report_kind": report_kind,
            "report_state": report_state,
            "replay_of_report_id": replay_of_report_id,
            "report_hash": report_hash,
            "report_json": report_json,
        }
        if existing is not None:
            record = dict(existing)
            if any(record[key] != value for key, value in expected.items()):
                raise CampaignPersistenceError(
                    "report identity or immutable payload already differs"
                )
            connection.rollback()
            return record
        connection.execute(
            """
            INSERT INTO printer_memory_factory_campaign_reports(
                report_id, campaign_id, configuration_id, report_kind,
                report_state, replay_of_report_id, report_hash, report_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id, campaign_id, configuration_id, report_kind,
                report_state, replay_of_report_id, report_hash, report_json,
                _utc_text(now),
            ),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM printer_memory_factory_campaign_reports WHERE report_id = ?",
            (report_id,),
        ).fetchone()
        return dict(row)
    except CampaignPersistenceError:
        connection.rollback()
        raise
    except sqlite3.Error as exc:
        connection.rollback()
        raise CampaignPersistenceError(f"report persistence failed: {exc}") from exc
    finally:
        connection.close()
