from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


persistence = Path("src/printer_v1/operator_cli/campaign_persistence.py")
text = persistence.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''from typing import Any, Mapping\n\nfrom printer_v1.operator_cli.git_provenance import (\n''',
    '''from typing import Any, Mapping\n\nfrom printer_v1.db.migrate import canonical_migration_names\nfrom printer_v1.operator_cli.git_provenance import (\n''',
    "campaign persistence migration import",
)
text = replace_once(
    text,
    '''def _sha256_text(value: str) -> str:\n    return hashlib.sha256(value.encode("utf-8")).hexdigest()\n\n\ndef canonical_campaign_evidence_json''',
    '''def _sha256_text(value: str) -> str:\n    return hashlib.sha256(value.encode("utf-8")).hexdigest()\n\n\ndef _sha256_file(path: Path) -> str:\n    digest = hashlib.sha256()\n    with path.open("rb") as handle:\n        for chunk in iter(lambda: handle.read(1 << 20), b""):\n            digest.update(chunk)\n    return digest.hexdigest()\n\n\ndef canonical_campaign_evidence_json''',
    "campaign persistence file hash owner",
)
anchor = "\ndef create_campaign(\n"
if text.count(anchor) != 1:
    raise SystemExit("create_campaign insertion anchor is not unique")
new_owner = r'''

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
'''
text = text.replace(anchor, new_owner + anchor, 1)
persistence.write_text(text, encoding="utf-8")


command = Path("src/printer_v1/operator_cli/operational_memory_factory_command.py")
text = command.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''from printer_v1.operator_cli.campaign_ownership import create_campaign_run\n''',
    "",
    "remove split run owner import",
)
text = replace_once(
    text,
    '''    campaign_evidence_sha256,\n    create_campaign,\n)\n''',
    '''    campaign_evidence_sha256,\n    create_operational_campaign_graph,\n)\n''',
    "use atomic graph owner import",
)
start = text.find("    created = create_campaign(\n")
if start < 0:
    raise SystemExit("split campaign initialization start not found")
end_marker = "    finally:\n        connection.close()\n"
end = text.find(end_marker, start)
if end < 0:
    raise SystemExit("split campaign initialization end not found")
end += len(end_marker)
replacement = r'''    expected_database_path = (
        authorization_runtime_facts["authorized_db_path"]
        if authorization_runtime_facts is not None
        else preflight["database_path"]
    )
    expected_database_sha256 = (
        authorization_runtime_facts["authorized_pre_mutation_sha256"]
        if authorization_runtime_facts is not None
        else preflight["database_sha256"]
    )
    expected_migration_count = (
        authorization_runtime_facts["migration_count"]
        if authorization_runtime_facts is not None
        else preflight["migration_count"]
    )
    expected_migration_head = (
        authorization_runtime_facts["migration_head"]
        if authorization_runtime_facts is not None
        else preflight["latest_migration"]
    )
    created = create_operational_campaign_graph(
        AUTHORITATIVE_DB,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        run_id=run_id,
        cycle_id=cycle_id,
        configuration=configuration,
        launch_provenance=preflight["git_provenance"],
        db_target_identity=target_identity,
        policy_version=POLICY_VERSION,
        expected_database_path=expected_database_path,
        expected_database_sha256=str(expected_database_sha256),
        expected_migration_count=int(expected_migration_count),
        expected_migration_head=str(expected_migration_head),
        run_ordinal=1,
        now=now,
    )
'''
text = text[:start] + replacement + text[end:]
command.write_text(text, encoding="utf-8")


supervision = Path("src/printer_v1/operator_cli/campaign_supervision.py")
text = supervision.read_text(encoding="utf-8")
old = '''    _write_new_lock(lock, payload)\n    connection = _connect(db_path)\n    try:\n        _begin_immediate(connection)\n'''
new = '''    _write_new_lock(lock, payload)\n    connection: sqlite3.Connection | None = None\n    try:\n        connection = _connect(db_path)\n        _begin_immediate(connection)\n'''
text = replace_once(text, old, new, "supervision connection enters cleanup scope")
old = '''    except (sqlite3.Error, CampaignSupervisionError) as exc:\n        connection.rollback()\n        lock.unlink(missing_ok=True)\n        if isinstance(exc, CampaignSupervisionError):\n            raise\n        raise CampaignSupervisionError(str(exc)) from exc\n    finally:\n        connection.close()\n'''
new = '''    except (sqlite3.Error, CampaignSupervisionError) as exc:\n        if connection is not None:\n            connection.rollback()\n        try:\n            lock.unlink(missing_ok=True)\n        except OSError as cleanup_exc:\n            exc.add_note(\n                "new supervision lock cleanup failed: "\n                f"{type(cleanup_exc).__name__}:{cleanup_exc}"\n            )\n        if isinstance(exc, CampaignSupervisionError):\n            raise\n        raise CampaignSupervisionError(str(exc)) from exc\n    finally:\n        if connection is not None:\n            connection.close()\n'''
text = replace_once(text, old, new, "supervision connection failure cleanup")
supervision.write_text(text, encoding="utf-8")

print("Checkpoint 2 repair applied")
