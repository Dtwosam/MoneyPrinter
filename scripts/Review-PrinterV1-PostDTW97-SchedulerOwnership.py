from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

REPO = Path.home() / "Developer" / "MoneyPrinter"
BRANCH = "agent/v2-9-8b-post-dtw97-scheduler-ownership-audit"
HEAD = "d7dd83d0150187a84d55ac899cf31a3b00aa4fda"
DB = REPO / "data" / "printer_v1.sqlite3"
CAMPAIGN_ID = "20260809T121950Z-50e6b524e14e-campaign"
RUN_ID = "20260809T121950Z-50e6b524e14e-campaign-run"
CYCLE_ID = "20260809T121950Z-50e6b524e14e-cycle"
TARGET_IDS = tuple(range(1442, 1460))
ACTIVE = {"PENDING", "RUNNING", "COOLDOWN"}


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=REPO, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def table_exists(c: sqlite3.Connection, table: str) -> bool:
    return c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def columns(c: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(c, table):
        return set()
    return {str(row[1]) for row in c.execute(f"PRAGMA table_info({table})")}


def compact_rows(
    c: sqlite3.Connection,
    table: str,
    job_column: str,
    *,
    exact_scope: bool = False,
    require_stage_contract: bool = False,
) -> list[dict]:
    cols = columns(c, table)
    if job_column not in cols:
        return []
    wanted = [
        "id", "scheduler_job_id", "first_window_15m_scheduler_job_id",
        "job_name", "job_kind", "status", "locked_at", "lock_owner",
        "campaign_id", "run_id", "cycle_id", "token_slot_id",
        "scheduler_work_id", "discovery_work_id", "work_id", "work_type",
        "work_state", "step_kind", "step_status", "ownership_contract_version",
        "first_terminal_cause", "created_at", "updated_at",
    ]
    selected = [name for name in wanted if name in cols]
    placeholders = ",".join("?" for _ in TARGET_IDS)
    where = [f"{job_column} IN ({placeholders})"]
    params: list[object] = list(TARGET_IDS)
    if exact_scope:
        for name, value in (
            ("campaign_id", CAMPAIGN_ID),
            ("run_id", RUN_ID),
            ("cycle_id", CYCLE_ID),
        ):
            if name not in cols:
                return []
            where.append(f"{name}=?")
            params.append(value)
    if require_stage_contract:
        if "ownership_contract_version" not in cols:
            return []
        where.append("ownership_contract_version='V2_STAGE_SCOPED'")
    order = job_column
    rows = c.execute(
        f"SELECT {','.join(selected)} FROM {table} WHERE {' AND '.join(where)} ORDER BY {order}",
        tuple(params),
    ).fetchall()
    return [dict(row) for row in rows]


def referenced_job_ids(rows: list[dict], key: str) -> set[int]:
    return {int(row[key]) for row in rows if row.get(key) is not None}


def all_scheduler_references(c: sqlite3.Connection) -> dict[str, list[dict]]:
    output: dict[str, list[dict]] = {}
    table_names = [
        str(row[0])
        for row in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]
    interesting_columns = {"scheduler_job_id", "first_window_15m_scheduler_job_id"}
    for table in table_names:
        cols = columns(c, table)
        for job_col in sorted(cols & interesting_columns):
            rows = compact_rows(c, table, job_col)
            if rows:
                output[f"{table}.{job_col}"] = rows
    return output


def main() -> int:
    result: dict = {
        "status": "BLOCKED",
        "verdict": "V2_9_8B_POST_DTW97_SCHEDULER_OWNERSHIP_READONLY_AUDIT_BLOCKED",
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
        "authorization_created": False,
        "runtime_started": False,
    }
    try:
        if git("branch", "--show-current") != BRANCH:
            raise RuntimeError("audit branch mismatch")
        if git("rev-parse", "HEAD") != HEAD:
            raise RuntimeError("audit HEAD mismatch")
        if git("status", "--porcelain=v1", "-uno"):
            raise RuntimeError("tracked worktree/index is not clean")

        sidecars = [
            str(Path(str(DB) + suffix))
            for suffix in ("-wal", "-shm", "-journal")
            if Path(str(DB) + suffix).exists()
        ]
        if sidecars:
            raise RuntimeError(f"authoritative database sidecars present: {sidecars}")
        stat = DB.stat()
        db_before = {
            "path": str(DB),
            "sha256": sha256_file(DB),
            "size": int(stat.st_size),
            "inode": int(stat.st_ino),
            "mtime_ns": int(stat.st_mtime_ns),
        }

        c = sqlite3.connect(
            f"file:{DB.as_posix()}?mode=ro&immutable=1", uri=True, timeout=0.0
        )
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA query_only=ON")
            integrity = [str(row[0]) for row in c.execute("PRAGMA integrity_check")]
            fk = [list(row) for row in c.execute("PRAGMA foreign_key_check")]

            jobs = compact_rows(c, "printer_scheduler_jobs", "id")
            run_steps = compact_rows(
                c, "printer_memory_factory_run_steps", "scheduler_job_id"
            )
            discovery_exact = compact_rows(
                c, "printer_discovery_work", "scheduler_job_id", exact_scope=True
            )
            stage_exact = compact_rows(
                c,
                "printer_memory_factory_campaign_scheduler_work",
                "scheduler_job_id",
                exact_scope=True,
                require_stage_contract=True,
            )
            handoff_exact = compact_rows(
                c,
                "printer_discovery_selected_item_links",
                "first_window_15m_scheduler_job_id",
                exact_scope=True,
            )
            all_refs = all_scheduler_references(c)

            discovery_ids = referenced_job_ids(discovery_exact, "scheduler_job_id")
            stage_ids = referenced_job_ids(stage_exact, "scheduler_job_id")
            handoff_ids = referenced_job_ids(
                handoff_exact, "first_window_15m_scheduler_job_id"
            )
            factory_ids = referenced_job_ids(run_steps, "scheduler_job_id")
            exact_owned = discovery_ids | stage_ids | handoff_ids

            by_id = {int(row["id"]): row for row in jobs}
            matrix = []
            for jid in TARGET_IDS:
                job = by_id.get(jid)
                status = None if job is None else str(job.get("status"))
                locked = bool(
                    job
                    and (job.get("locked_at") is not None or job.get("lock_owner") is not None)
                )
                owners = []
                if jid in discovery_ids:
                    owners.append("printer_discovery_work")
                if jid in stage_ids:
                    owners.append("printer_memory_factory_campaign_scheduler_work:V2_STAGE_SCOPED")
                if jid in handoff_ids:
                    owners.append("printer_discovery_selected_item_links:first_window_15m")
                matrix.append(
                    {
                        "job_id": jid,
                        "job_present": job is not None,
                        "job_name": None if job is None else job.get("job_name"),
                        "job_kind": None if job is None else job.get("job_kind"),
                        "status": status,
                        "locked": locked,
                        "factory_run_step_reference": jid in factory_ids,
                        "exact_scope_owners": owners,
                        "exact_scope_owned": bool(owners),
                    }
                )

            missing_exact = [jid for jid in TARGET_IDS if jid not in exact_owned]
            active_targets = [
                item["job_id"]
                for item in matrix
                if item["status"] in ACTIVE or item["locked"]
            ]

            campaign_report_row = None
            if table_exists(c, "printer_memory_factory_campaign_reports"):
                cols = columns(c, "printer_memory_factory_campaign_reports")
                selected = [
                    name for name in (
                        "id", "report_id", "report_kind", "report_state",
                        "report_hash", "created_at"
                    ) if name in cols
                ]
                row = c.execute(
                    f"SELECT {','.join(selected)} FROM printer_memory_factory_campaign_reports "
                    "WHERE campaign_id=? ORDER BY id DESC LIMIT 1",
                    (CAMPAIGN_ID,),
                ).fetchone()
                campaign_report_row = dict(row) if row is not None else None

            result.update(
                {
                    "database": db_before,
                    "database_integrity": integrity,
                    "foreign_key_violations": len(fk),
                    "target_job_ids": list(TARGET_IDS),
                    "target_jobs_present": len(by_id),
                    "target_jobs_active_or_locked": active_targets,
                    "exact_scope_owned_job_ids": sorted(exact_owned),
                    "missing_exact_scope_ownership": missing_exact,
                    "factory_run_step_referenced_job_ids": sorted(factory_ids),
                    "ownership_matrix": matrix,
                    "authoritative_owner_rows": {
                        "printer_discovery_work": discovery_exact,
                        "printer_memory_factory_campaign_scheduler_work_v2_stage_scoped": stage_exact,
                        "printer_discovery_selected_item_links_first_15m": handoff_exact,
                    },
                    "factory_run_step_rows": run_steps,
                    "all_scheduler_references": all_refs,
                    "campaign_report_row": campaign_report_row,
                }
            )
        finally:
            c.close()

        stat_after = DB.stat()
        db_after = {
            "path": str(DB),
            "sha256": sha256_file(DB),
            "size": int(stat_after.st_size),
            "inode": int(stat_after.st_ino),
            "mtime_ns": int(stat_after.st_mtime_ns),
        }
        if db_after != db_before:
            raise RuntimeError("authoritative database changed during read-only audit")
        result["database_unchanged_during_audit"] = True
        result["status"] = "PASS"
        result["verdict"] = "V2_9_8B_POST_DTW97_SCHEDULER_OWNERSHIP_FACTS_CAPTURE_PASS"
        result["next_step"] = "STATIC_CAUSAL_CLASSIFICATION_BEFORE_ANY_FRESH_AUTHORIZATION"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
