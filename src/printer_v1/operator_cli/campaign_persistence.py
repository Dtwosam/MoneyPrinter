"""Persistence-only campaign, configuration, and report records."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from printer_v1.db.migrate import canonical_migration_names
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
AUTHORIZATION_MARKER_KIND = "PRINTER_V1_OPERATIONAL_CAMPAIGN_AUTHORIZATION"
AUTHORIZATION_MARKER_VERSION = "V2_9_8B_C12_C14_V1"


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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_campaign_evidence_json(value: Mapping[str, Any]) -> str:
    """Return the immutable campaign owner's versioned canonical JSON bytes."""
    return _canonical_json(value, "campaign evidence")


def campaign_evidence_sha256(value: Mapping[str, Any]) -> str:
    """Hash one canonical campaign-evidence payload with SHA-256."""
    return _sha256_text(canonical_campaign_evidence_json(value))


def build_authorization_marker_payload(
    *,
    marker_id: str,
    execution_id: str,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    policy_version: str,
    db_target_identity: str,
    launch_git_provenance: Mapping[str, Any],
    operator_approved: bool,
) -> dict[str, Any]:
    """Build the dedicated authorization payload stored by the config owner.

    The payload deliberately excludes ``configuration_hash`` so the marker
    digest and the factory configuration hash remain separate contracts.
    """
    if operator_approved is not True:
        raise CampaignPersistenceError("authorization marker requires operator approval")
    try:
        provenance = validate_launch_provenance(launch_git_provenance)
    except (GitProvenanceError, TypeError, ValueError) as exc:
        raise CampaignPersistenceError("launch Git provenance is invalid") from exc
    payload = {
        "marker_kind": AUTHORIZATION_MARKER_KIND,
        "marker_version": AUTHORIZATION_MARKER_VERSION,
        "marker_id": _nonempty(marker_id, "authorization marker_id"),
        "execution_id": _nonempty(execution_id, "execution_id"),
        "campaign_id": _nonempty(campaign_id, "campaign_id"),
        "configuration_id": _nonempty(configuration_id, "configuration_id"),
        "run_id": _nonempty(run_id, "run_id"),
        "policy_version": _nonempty(policy_version, "policy_version"),
        "db_target_identity": _nonempty(
            db_target_identity, "db_target_identity"
        ),
        "launch_git_provenance": provenance,
        "operator_approved": True,
    }
    # Validate serializability before this payload enters immutable configuration.
    canonical_campaign_evidence_json(payload)
    return payload


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



def create_operational_campaign_graph(
    db_path: str | Path,
    *,
    campaign_id: str,
    configuration_id: str,
    run_id: str,
    cycle_id: str,
    configuration: Mapping[str, Any],
    launch_provenance: Mapping[str, Any],
    db_target_identity: str,
    policy_version: str,
    expected_database_path: str | Path,
    expected_database_sha256: str,
    expected_migration_count: int,
    expected_migration_head: str,
    run_ordinal: int = 1,
    now: str | None = None,
) -> dict[str, Any]:
    """Create the complete ordinary operational graph in one first-write lock.

    The authorization-bound database bytes and migration ledger are revalidated
    after ``BEGIN IMMEDIATE`` and before the first insert. Campaign,
    configuration, run, cycle, and RUNNING state transitions then commit all or
    none. This owner is intentionally separate from historical ``create_campaign``
    and ``create_campaign_run`` APIs.
    """
    path = Path(db_path).resolve()
    expected_path = Path(expected_database_path).resolve()
    if path != expected_path or not path.is_file():
        raise CampaignPersistenceError(
            "AUTHORIZED_DATABASE_PATH_CHANGED_BEFORE_FIRST_WRITE"
        )
    expected_sha = _nonempty(
        expected_database_sha256, "expected_database_sha256"
    )
    if len(expected_sha) != 64 or any(
        character not in "0123456789abcdef" for character in expected_sha
    ):
        raise CampaignPersistenceError("expected_database_sha256 is malformed")
    expected_head = _nonempty(expected_migration_head, "expected_migration_head")
    expected_count = int(expected_migration_count)
    if expected_count <= 0:
        raise CampaignPersistenceError("expected_migration_count must be positive")
    if int(run_ordinal) <= 0:
        raise CampaignPersistenceError("run_ordinal must be positive")

    campaign = _nonempty(campaign_id, "campaign_id")
    configuration_identity = _nonempty(configuration_id, "configuration_id")
    run = _nonempty(run_id, "run_id")
    cycle = _nonempty(cycle_id, "cycle_id")
    target = _nonempty(db_target_identity, "db_target_identity")
    policy = _nonempty(policy_version, "policy_version")
    if target != f"sha256:{expected_sha}":
        raise CampaignPersistenceError(
            "AUTHORIZED_DATABASE_CHANGED_BEFORE_FIRST_WRITE"
        )
    config_json, provenance_json, config_hash = _configuration_material(
        configuration, launch_provenance
    )
    timestamp = now or _utc_text()
    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        if _sha256_file(path) != expected_sha:
            raise CampaignPersistenceError(
                "AUTHORIZED_DATABASE_CHANGED_BEFORE_FIRST_WRITE"
            )
        applied = tuple(
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            ).fetchall()
        )
        canonical = tuple(canonical_migration_names())
        if (
            applied != canonical
            or len(applied) != expected_count
            or not applied
            or applied[-1] != expected_head
        ):
            raise CampaignPersistenceError(
                "MIGRATION_LEDGER_CHANGED_BEFORE_FIRST_WRITE"
            )

        identity_checks = (
            ("printer_memory_factory_campaigns", "campaign_id", campaign),
            (
                "printer_memory_factory_campaign_configurations",
                "configuration_id",
                configuration_identity,
            ),
            ("printer_memory_factory_campaign_runs", "run_id", run),
            ("printer_memory_factory_campaign_cycles", "cycle_id", cycle),
        )
        for table, column, identity in identity_checks:
            if connection.execute(
                f"SELECT 1 FROM {table} WHERE {column}=?", (identity,)
            ).fetchone() is not None:
                raise CampaignPersistenceError(
                    "operational campaign graph identity already exists"
                )

        connection.execute(
            """INSERT INTO printer_memory_factory_campaigns(
                   campaign_id,campaign_state,db_mode,db_target_identity,
                   proof_source_db_identity,policy_version,first_terminal_cause,
                   terminal_at,created_at,updated_at
               ) VALUES (?,'DRAFT',?, ?,NULL,?,NULL,NULL,?,?)""",
            (
                campaign,
                DB_MODE_OPERATIONAL_PERSISTENT,
                target,
                policy,
                timestamp,
                timestamp,
            ),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_configurations(
                   configuration_id,campaign_id,configuration_hash,
                   configuration_json,launch_provenance_json,created_at
               ) VALUES (?,?,?,?,?,?)""",
            (
                configuration_identity,
                campaign,
                config_hash,
                config_json,
                provenance_json,
                timestamp,
            ),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_runs(
                   run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,
                   proof_supervision_id,created_at,updated_at
               ) VALUES (?,?,?,'DRAFT',NULL,NULL,?,?)""",
            (run, campaign, int(run_ordinal), timestamp, timestamp),
        )
        connection.execute(
            """INSERT INTO printer_memory_factory_campaign_cycles(
                   cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                   created_at,updated_at
               ) VALUES (?,?,?,1,'PLANNED',?,?)""",
            (cycle, campaign, run, timestamp, timestamp),
        )
        campaign_update = connection.execute(
            """UPDATE printer_memory_factory_campaigns
               SET campaign_state='RUNNING',updated_at=?
               WHERE campaign_id=? AND campaign_state='DRAFT'""",
            (timestamp, campaign),
        )
        run_update = connection.execute(
            """UPDATE printer_memory_factory_campaign_runs
               SET run_state='RUNNING',updated_at=?
               WHERE run_id=? AND campaign_id=? AND run_state='DRAFT'""",
            (timestamp, run, campaign),
        )
        if campaign_update.rowcount != 1 or run_update.rowcount != 1:
            raise CampaignPersistenceError(
                "operational campaign graph state transition failed"
            )
        record = _campaign_record(connection, campaign)
        connection.commit()
    except CampaignPersistenceError:
        connection.rollback()
        raise
    except sqlite3.Error as exc:
        connection.rollback()
        raise CampaignPersistenceError(
            f"OPERATIONAL_CAMPAIGN_INITIALIZATION_FAILED:{exc}"
        ) from exc
    finally:
        connection.close()

    try:
        from printer_v1.operator_cli.action_local_mutation_recorder import (
            emit_insert,
            emit_update,
        )

        emit_insert("printer_memory_factory_campaigns", campaign)
        emit_insert(
            "printer_memory_factory_campaign_configurations",
            configuration_identity,
        )
        emit_insert("printer_memory_factory_campaign_runs", run)
        emit_insert("printer_memory_factory_campaign_cycles", cycle)
        emit_update("printer_memory_factory_campaigns", campaign)
        emit_update("printer_memory_factory_campaign_runs", run)
    except Exception:
        # Recording remains best-effort; persistence ownership must not depend on it.
        pass
    return record

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
        try:
            from printer_v1.operator_cli.action_local_mutation_recorder import (
                emit_insert,
            )

            emit_insert("printer_memory_factory_campaigns", campaign_id)
            emit_insert(
                "printer_memory_factory_campaign_configurations",
                configuration_id,
            )
        except Exception:
            # Mutation recording is best-effort and must never break ownership.
            pass
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
    if not isinstance(object_ids, tuple) or any(
        not isinstance(value, str) or not value.strip() for value in object_ids
    ):
        raise CampaignPersistenceError("object_ids must be unique non-empty strings")
    # Insufficient-pool discovery stops activate zero tokens and create no 4A-5C
    # campaign objects. Empty object link sets are therefore valid for that cause.
    terminal_cause = None
    if isinstance(report, Mapping):
        terminal = report.get("terminal")
        if isinstance(terminal, Mapping):
            terminal_cause = terminal.get("first_terminal_cause")
    if (
        not object_ids
        and terminal_cause != "INSUFFICIENT_ELIGIBLE_TWO_SLOT_POOL"
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
