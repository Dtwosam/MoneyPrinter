from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from typing import Any

REPO = Path.home() / "Developer" / "MoneyPrinter"
BRANCH = "agent/v2-9-8b-post-dtw96-window15m-rereadiness-audit"
HEAD = "e7d19cc8fb6074b3b74740b116d265c3a2f3e8b5"
DB = REPO / "data" / "printer_v1.sqlite3"
EXPECTED_MIGRATION_COUNT = 53
EXPECTED_MIGRATION_HEAD = "053_pilot_input_readiness_route_domain.sql"
CONSUMED_AUTHORIZATION_ID = "V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z"
CONSUMED_MARKER = (
    Path.home()
    / "PrinterOperations"
    / "v2-9-8"
    / "window-15m-one-shot-applications"
    / CONSUMED_AUTHORIZATION_ID
    / "application-marker.json"
)


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO, text=True, capture_output=True, check=False
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def database_fingerprint() -> dict[str, Any]:
    if not DB.exists():
        raise RuntimeError(f"authoritative database missing: {DB}")
    stat = DB.stat()
    sidecars = [
        str(path)
        for path in (Path(str(DB) + "-wal"), Path(str(DB) + "-shm"), Path(str(DB) + "-journal"))
        if path.exists()
    ]
    return {
        "path": str(DB),
        "exists": True,
        "sha256": sha256_file(DB),
        "size": int(stat.st_size),
        "inode": int(stat.st_ino),
        "mtime_ns": int(stat.st_mtime_ns),
        "sidecars": sidecars,
        "opened_mode": "read_only_immutable",
    }


def immutable_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{DB.as_posix()}?mode=ro&immutable=1",
        uri=True,
        timeout=2.0,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def main() -> int:
    phase = "START"
    try:
        phase = "GIT_CLEAN"
        if git("status", "--porcelain=v1", "-uno"):
            raise RuntimeError("tracked worktree/index is not clean")

        phase = "GIT_ALIGN"
        git("fetch", "origin", BRANCH)
        if git("rev-parse", "FETCH_HEAD") != HEAD:
            raise RuntimeError("remote rereadiness audit branch head drifted")
        local_exists = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{BRANCH}"],
            cwd=REPO,
        ).returncode == 0
        if local_exists:
            git("switch", BRANCH)
            if git("rev-parse", "HEAD") != HEAD:
                raise RuntimeError("local rereadiness audit branch head drifted")
        else:
            git("switch", "--track", "-c", BRANCH, f"origin/{BRANCH}")
        if git("branch", "--show-current") != BRANCH:
            raise RuntimeError("rereadiness audit branch mismatch")
        if git("rev-parse", "HEAD") != HEAD:
            raise RuntimeError("rereadiness audit HEAD mismatch")
        if git("status", "--porcelain=v1", "-uno"):
            raise RuntimeError("tracked worktree/index changed during Git alignment")

        # Import Printer only after exact Git identity has been established.
        sys.path.insert(0, str(REPO / "src"))
        from printer_v1.operator_cli.holder_reliability_budget_control import (
            build_operational_budget_preflight,
        )
        from printer_v1.operator_cli.operational_memory_factory_command import (
            ADMISSION_OPERATION_CEILING,
            DISCOVERY_REQUEST_CEILING,
            GOVERNED_15M_REQUEST_CEILING,
            GOVERNED_REQUESTS_PER_TOKEN,
            _active_counts,
            _locked_capability_counts,
            _validate_locked_baseline,
        )
        from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
            assert_migration_ledger_ready,
        )
        from printer_v1.operator_cli.readiness_source_contract_preflight import (
            build_readiness_source_contract_preflight,
        )
        from printer_v1.operator_cli.unified_terminal_closure import (
            assert_runtime_dependency_preflight,
        )
        from printer_v1.operator_cli.window_15m_concrete_composition import (
            run_window_15m_concrete_composition_preflight,
            window_15m_preflight_builders,
        )

        phase = "DATABASE_BASELINE"
        before = database_fingerprint()
        if before["sidecars"]:
            raise RuntimeError(f"authoritative database sidecars present: {before['sidecars']}")

        phase = "CONSUMED_AUTHORIZATION_MARKER"
        if not CONSUMED_MARKER.exists():
            raise RuntimeError("DTW96 consumed authorization application marker missing")
        marker_sha256 = sha256_file(CONSUMED_MARKER)

        phase = "MIGRATION_LEDGER"
        migration = assert_migration_ledger_ready(
            mode="prepare", db_path=DB, migrations_dir=REPO / "migrations"
        )
        if migration.status != "PASS":
            raise RuntimeError(f"migration guard blocked: {migration.verdict}")
        migration_db = dict(migration.database or {})
        migration_count = int(migration_db.get("migration_count") or 0)
        migration_head = str(migration_db.get("migration_head") or "")
        if migration_count != EXPECTED_MIGRATION_COUNT:
            raise RuntimeError(
                f"migration count drift: expected {EXPECTED_MIGRATION_COUNT}, got {migration_count}"
            )
        if migration_head != EXPECTED_MIGRATION_HEAD:
            raise RuntimeError(
                f"migration head drift: expected {EXPECTED_MIGRATION_HEAD}, got {migration_head}"
            )

        phase = "NON_GIT_READINESS"
        source = build_readiness_source_contract_preflight()
        if source.get("status") != "READY":
            raise RuntimeError(f"source contract not READY: {source}")
        if int(source.get("external_requests") or 0) != 0:
            raise RuntimeError(f"source contract performed external requests: {source}")

        composition = run_window_15m_concrete_composition_preflight(
            repository_root=str(REPO), timeout_seconds=5.0
        )
        if composition.get("status") != "READY":
            raise RuntimeError(f"concrete composition not READY: {composition}")

        dependency = assert_runtime_dependency_preflight(
            repository_root=REPO,
            adapter_builders=window_15m_preflight_builders(timeout_seconds=5.0),
        )
        if dependency.status != "READY":
            raise RuntimeError(f"dependency preflight not READY: {dependency.to_dict()}")

        budget = build_operational_budget_preflight(
            admission_operation_ceiling=ADMISSION_OPERATION_CEILING,
            discovery_request_ceiling=DISCOVERY_REQUEST_CEILING,
            governed_15m_request_ceiling=GOVERNED_15M_REQUEST_CEILING,
            governed_requests_per_token=GOVERNED_REQUESTS_PER_TOKEN,
        )
        if budget.get("status") != "READY":
            raise RuntimeError(f"holder budget not READY: {budget}")

        phase = "AUTHORITATIVE_DB_READ_ONLY"
        connection = immutable_connection()
        try:
            integrity = [row[0] for row in connection.execute("PRAGMA integrity_check").fetchall()]
            foreign_key_sample = [list(row) for row in connection.execute("PRAGMA foreign_key_check LIMIT 20").fetchall()]
            foreign_key_violations = int(
                connection.execute("SELECT COUNT(*) FROM pragma_foreign_key_check").fetchone()[0]
            )
            active = dict(_active_counts(connection))
            locked = dict(_locked_capability_counts(connection))
            historical_audit = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_paper_audit_reports WHERE paper_position_id IS NULL"
                ).fetchone()[0]
            )
        finally:
            connection.close()

        if integrity != ["ok"]:
            raise RuntimeError(f"integrity check failed: {integrity}")
        if foreign_key_violations != 0:
            raise RuntimeError(
                f"foreign-key violations={foreign_key_violations}: {foreign_key_sample}"
            )
        if any(int(value) != 0 for value in active.values()):
            raise RuntimeError(f"active operational residue: {active}")
        _validate_locked_baseline(locked)
        if historical_audit != 1:
            raise RuntimeError(
                f"historical paper-audit baseline changed: {historical_audit}"
            )

        phase = "DATABASE_UNCHANGED"
        after = database_fingerprint()
        if after != before:
            raise RuntimeError(
                "authoritative database changed during rereadiness: "
                + json.dumps({"before": before, "after": after}, sort_keys=True)
            )

        # Merge migration-ledger identity fields without weakening the independently
        # measured filesystem fingerprint.
        database = dict(before)
        for key in (
            "ledger_digest",
            "ledger_table_present",
            "migration_count",
            "migration_head",
            "readable",
        ):
            if key in migration_db:
                database[key] = migration_db[key]
        database["integrity"] = integrity
        database["foreign_key_violations"] = foreign_key_violations
        database["foreign_key_sample"] = foreign_key_sample

        result = {
            "status": "PASS",
            "verdict": "V2_9_8B_POST_DTW96_WINDOW_15M_REREADINESS_PASS",
            "branch": BRANCH,
            "head": HEAD,
            "database": database,
            "database_unchanged_during_rereadiness": True,
            "migration_guard": migration.verdict,
            "source_contract_status": source.get("status"),
            "source_contract_external_requests": int(source.get("external_requests") or 0),
            "concrete_composition_status": composition.get("status"),
            "dependency_status": dependency.status,
            "holder_budget_status": budget.get("status"),
            "active_counts": active,
            "historical_paper_audit_rows_preserved": historical_audit,
            "consumed_authorization_id": CONSUMED_AUTHORIZATION_ID,
            "consumed_application_marker_present": True,
            "consumed_application_marker_sha256": marker_sha256,
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
            "authorization_created": False,
            "printer_runtime_started": False,
            "window_15m_started": False,
            "next_step": "REREADINESS_CLOSEOUT_BEFORE_ANY_FRESH_AUTHORIZATION",
        }
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "verdict": "V2_9_8B_POST_DTW96_WINDOW_15M_REREADINESS_BLOCKED",
                    "phase": phase,
                    "error": f"{type(exc).__name__}:{exc}",
                    "source_calls": 0,
                    "scheduler_runtime_calls": 0,
                    "database_writes": 0,
                    "authorization_created": False,
                    "printer_runtime_started": False,
                    "window_15m_started": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
