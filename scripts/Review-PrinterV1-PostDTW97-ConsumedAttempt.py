from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

REPO = Path.home() / "Developer" / "MoneyPrinter"
DB = REPO / "data" / "printer_v1.sqlite3"
AUTH_ID = "V2_9_8B_WINDOW_15M_AUTH_20260809T120100Z"
CAMPAIGN_ID = "20260809T121950Z-50e6b524e14e-campaign"
RUN_ID = "20260809T121950Z-50e6b524e14e-campaign-run"
EXECUTION_ID = "20260809T121950Z-50e6b524e14e"
APP = (
    Path.home()
    / "PrinterOperations"
    / "v2-9-8"
    / "window-15m-one-shot-applications"
    / AUTH_ID
)
MARKER_SHA = "825e2bd7c03b4334580de18153af7869ba92244548eca9de12c3e0567e1921d0"
CHILD_TERMINAL_SHA = "472b260af950ab28aa781b6d6c0fc6046533987b4e9227ef238d5eab480c40f7"
MANIFEST_SHA = "b138327a7670541ab9d196a8b2ac224bd1265d23e7c138e3cec0be22ed07a83e"
EXPECTED_RUNTIME_BRANCH = "agent/v2-9-8b-post-dtw96-window15m-authorization-preparation"
EXPECTED_RUNTIME_HEAD = "a64d109b043ba86d73b82276fb34ba28561de093"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def qident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def file_identity(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False, "size": 0, "sha256": None}
    st = path.stat()
    return {"exists": True, "size": int(st.st_size), "sha256": sha256_file(path)}


def matching_rows(conn: sqlite3.Connection) -> list[dict]:
    identities = {
        "authorization_id": AUTH_ID,
        "campaign_id": CAMPAIGN_ID,
        "run_id": RUN_ID,
        "execution_id": EXECUTION_ID,
    }
    preferred = [
        "id", "authorization_id", "campaign_id", "run_id", "cycle_id",
        "execution_id", "supervision_id", "work_id", "scheduler_job_id",
        "state", "status", "terminal_state", "terminal_reason", "terminal_cause",
        "first_terminal_cause", "failure_reason", "failure_phase",
        "lease_owner", "lease_expires_at", "locked_by", "locked_at",
        "report_id", "report_kind", "window_kind", "window_type",
        "memory_quality", "quality_state", "paper_position_id",
        "created_at", "started_at", "updated_at", "ended_at", "completed_at",
    ]
    tables = [
        str(r[0]) for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'printer_%' ORDER BY name"
        ).fetchall()
    ]
    result: list[dict] = []
    for table in tables:
        columns = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({qident(table)})").fetchall()]
        selectors = [(column, identities[column]) for column in identities if column in columns]
        if not selectors:
            continue
        projection = [column for column in preferred if column in columns]
        if not projection:
            projection = selectors[:1]
            projection = [projection[0][0]]
        select_sql = ", ".join(qident(c) for c in projection)
        seen = set()
        rows_for_table: list[dict] = []
        for column, value in selectors:
            sql = (
                f"SELECT {select_sql} FROM {qident(table)} "
                f"WHERE {qident(column)} = ? LIMIT 50"
            )
            for row in conn.execute(sql, (value,)).fetchall():
                obj = {projection[i]: row[i] for i in range(len(projection))}
                key = json.dumps(obj, sort_keys=True, default=str)
                if key not in seen:
                    seen.add(key)
                    rows_for_table.append(obj)
        if rows_for_table:
            result.append({"table": table, "rows": rows_for_table})
    return result


def relevant_stdout(path: Path) -> dict:
    if not path.is_file():
        return {"exists": False, "matched_lines": [], "tail": []}
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    needles = (
        "SAFE_STOP", "OPERATOR_INTERRUPTED", "terminal", "cleanup", "lease",
        "active_", "source_calls", "scheduler_runtime_calls", "database_writes",
        "accounting", "reconciliation", "report", "campaign_id", "run_id",
        "first_terminal_cause", "lifecycle_started", "exhaustion_certificate",
    )
    matched = [line for line in lines if any(n.lower() in line.lower() for n in needles)]
    def trim(items: list[str], limit: int) -> list[str]:
        return [item[:1600] for item in items[-limit:]]
    return {
        "exists": True,
        "line_count": len(lines),
        "matched_lines": trim(matched, 120),
        "tail": trim(lines, 80),
    }


def main() -> int:
    result: dict = {
        "status": "BLOCKED",
        "verdict": "V2_9_8B_POST_DTW97_CONSUMED_ATTEMPT_READONLY_AUDIT_BLOCKED",
        "authorization_id": AUTH_ID,
        "campaign_id": CAMPAIGN_ID,
        "run_id": RUN_ID,
        "execution_id": EXECUTION_ID,
        "source_calls_made_by_audit": 0,
        "scheduler_runtime_calls_made_by_audit": 0,
        "database_writes_made_by_audit": 0,
        "authorization_created": False,
        "runtime_started_by_audit": False,
    }
    try:
        marker = APP / "application-marker.json"
        child_terminal_path = APP / "child-terminal.json"
        manifest = APP / "git-provenance-manifest.json"
        wrapper_terminal = APP / "wrapper-terminal.json"
        stdout_path = APP / "child-stdout.txt"
        stderr_path = APP / "child-stderr.txt"

        for path, expected, label in (
            (marker, MARKER_SHA, "application marker"),
            (child_terminal_path, CHILD_TERMINAL_SHA, "child terminal"),
            (manifest, MANIFEST_SHA, "manifest"),
        ):
            if not path.is_file():
                raise RuntimeError(f"{label} missing: {path}")
            observed = sha256_file(path)
            if observed != expected:
                raise RuntimeError(f"{label} SHA mismatch: {observed}")

        marker_doc = load_json(marker)
        child_terminal = load_json(child_terminal_path)
        if marker_doc.get("authorization_id") != AUTH_ID:
            raise RuntimeError("marker authorization identity mismatch")
        if child_terminal.get("authorization_id") != AUTH_ID:
            raise RuntimeError("child terminal authorization identity mismatch")
        if marker_doc.get("repository_branch") != EXPECTED_RUNTIME_BRANCH:
            raise RuntimeError("marker runtime branch mismatch")
        if marker_doc.get("repository_head") != EXPECTED_RUNTIME_HEAD:
            raise RuntimeError("marker runtime HEAD mismatch")

        sidecars = [
            str(p) for p in (
                Path(str(DB) + "-wal"), Path(str(DB) + "-shm"), Path(str(DB) + "-journal")
            ) if p.exists()
        ]
        result["database_sidecars"] = sidecars
        if sidecars:
            raise RuntimeError(f"authoritative DB sidecars present: {sidecars}")
        if not DB.is_file():
            raise RuntimeError("authoritative database missing")

        st = DB.stat()
        db_identity = {
            "path": str(DB),
            "sha256": sha256_file(DB),
            "size": int(st.st_size),
            "inode": int(st.st_ino),
            "mtime_ns": int(st.st_mtime_ns),
            "opened_mode": "read_only_immutable",
        }

        conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro&immutable=1", uri=True, timeout=0.0)
        try:
            conn.execute("PRAGMA query_only=ON")
            integrity = [str(r[0]) for r in conn.execute("PRAGMA integrity_check").fetchall()]
            fk_rows = [list(r) for r in conn.execute("PRAGMA foreign_key_check").fetchall()]
            ledger = [
                str(r[0]) for r in conn.execute(
                    "SELECT version FROM printer_schema_migrations ORDER BY rowid"
                ).fetchall()
            ]

            sys.path.insert(0, str(REPO / "src"))
            from printer_v1.db.migrate import ordered_name_digest
            from printer_v1.operator_cli.operational_memory_factory_command import (
                _active_counts,
                _locked_capability_counts,
                _validate_locked_baseline,
            )

            active = dict(_active_counts(conn))
            locked = dict(_locked_capability_counts(conn))
            locked_status = "PASS"
            locked_error = None
            try:
                _validate_locked_baseline(locked)
            except Exception as exc:
                locked_status = "BLOCKED"
                locked_error = f"{type(exc).__name__}:{exc}"

            historical_audit = int(conn.execute(
                "SELECT COUNT(*) FROM printer_paper_audit_reports WHERE paper_position_id IS NULL"
            ).fetchone()[0])
            related = matching_rows(conn)
        finally:
            conn.close()

        db_identity.update({
            "integrity": integrity,
            "foreign_key_violations": len(fk_rows),
            "foreign_key_sample": fk_rows[:5],
            "migration_count": len(ledger),
            "migration_head": ledger[-1] if ledger else None,
            "ledger_digest": ordered_name_digest(ledger) if ledger else None,
        })

        staging_root = APP.parent / ".staging"
        staging = sorted(
            str(p) for p in staging_root.glob(f"{AUTH_ID}-*")
        ) if staging_root.is_dir() else []

        ps = subprocess.run(["ps", "-axo", "pid=,command="], text=True, capture_output=True, check=False)
        process_matches = []
        if ps.returncode == 0:
            for line in ps.stdout.splitlines():
                if (
                    "printer_v1.operator_cli.operational_memory_factory_command" in line
                    or AUTH_ID in line
                    or EXECUTION_ID in line
                ):
                    process_matches.append(line.strip())

        result.update({
            "marker_consumed": True,
            "authorization_consumed_at": marker_doc.get("authorization_consumed_at"),
            "marker": file_identity(marker),
            "manifest": file_identity(manifest),
            "wrapper_terminal": file_identity(wrapper_terminal),
            "child_terminal_file": file_identity(child_terminal_path),
            "child_stdout": file_identity(stdout_path),
            "child_stderr": file_identity(stderr_path),
            "child_terminal": child_terminal,
            "first_terminal_cause": child_terminal.get("first_terminal_cause"),
            "child_process_exit_code": child_terminal.get("process_exit_code"),
            "database": db_identity,
            "active_counts": active,
            "zero_active_residue": not any(int(v or 0) for v in active.values()),
            "locked_capability_baseline_status": locked_status,
            "locked_capability_baseline_error": locked_error,
            "historical_paper_audit_rows_preserved": historical_audit,
            "matching_database_rows": related,
            "matching_staging_residue": staging,
            "active_process_matches": process_matches,
            "stdout_terminal_evidence": relevant_stdout(stdout_path),
        })

        core_clean = bool(
            result["first_terminal_cause"] == "SAFE_STOP_OPERATOR_INTERRUPTED"
            and result["zero_active_residue"]
            and locked_status == "PASS"
            and integrity == ["ok"]
            and len(fk_rows) == 0
            and len(staging) == 0
            and len(process_matches) == 0
            and historical_audit == 1
        )
        if not core_clean:
            raise RuntimeError("post-interruption durable cleanup/readiness checks did not all pass")

        result["status"] = "PASS"
        result["verdict"] = "V2_9_8B_POST_DTW97_CONSUMED_OPERATOR_INTERRUPTED_READONLY_AUDIT_PASS"
        result["next_step"] = "CONSUMED_ATTEMPT_CLOSEOUT_BEFORE_ANY_FRESH_AUTHORIZATION"
        return_code = 0
    except BaseException as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"
        result["next_step"] = "STOP_AND_REVIEW_BLOCKER"
        return_code = 3

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
