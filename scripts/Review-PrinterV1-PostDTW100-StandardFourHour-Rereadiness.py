from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO = Path.home() / "Developer" / "MoneyPrinter"
DB = REPO / "data" / "printer_v1.sqlite3"
EXPECTED_BRANCH = (
    "agent/v2-9-8b-post-dtw100-standard-four-hour-operational-rereadiness"
)
EXPECTED_LAST_TRUST_SHA256 = (
    "6ce0e27332427243cffd055c41de58408f46dbcd84d43a764bf1764915a176fb"
)
EXPECTED_LAST_TRUST_SIZE = 76_435_456
EXPECTED_MIGRATION_COUNT = 54
EXPECTED_MIGRATION_HEAD = "054_pre_lifecycle_discovery_refresh_wait.sql"
ARTIFACT_ROOT = Path.home() / "PrinterOperations" / "v2-9-8"
STANDARD_APP_ROOT = (
    ARTIFACT_ROOT / "standard-four-hour-one-shot-applications"
)
ORDINARY_APP_ROOT = ARTIFACT_ROOT / "window-15m-one-shot-applications"
WRAPPER_ENV_NAMES = (
    "PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH",
    "PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256",
    "PRINTER_V1_APPLICATION_MARKER_PATH",
    "PRINTER_V1_APPLICATION_MARKER_SHA256",
    "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_PATH",
)
PROCESS_NEEDLES = (
    "printer_v1.operator_cli.operational_memory_factory_command",
    "printer_v1.operator_cli.standard_four_hour_one_shot_wrapper",
    "printer_v1.operator_cli.window_15m_one_shot_wrapper",
    "printer_v1.operator_cli.one_command_15m_factory",
    "Start-PrinterV1-Window15M-OneShot",
    "Start-PrinterV1-StandardFourHour-OneShot",
)


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def git(*args: str) -> str:
    result = run(["git", *args], cwd=REPO)
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def database_fingerprint() -> dict[str, Any]:
    if not DB.is_file():
        raise RuntimeError(f"authoritative database missing: {DB}")
    stat = DB.stat()
    sidecars = [
        str(path)
        for path in (
            Path(str(DB) + "-wal"),
            Path(str(DB) + "-shm"),
            Path(str(DB) + "-journal"),
        )
        if path.exists()
    ]
    return {
        "path": str(DB),
        "sha256": sha256_file(DB),
        "size": int(stat.st_size),
        "inode": int(stat.st_ino),
        "mtime_ns": int(stat.st_mtime_ns),
        "sidecars": sidecars,
    }


def active_process_matches() -> list[str]:
    result = run(["ps", "-axo", "pid=,command="])
    if result.returncode != 0:
        raise RuntimeError(f"process inspection failed: {result.stderr.strip()}")
    matches: list[str] = []
    for line in result.stdout.splitlines():
        if any(needle in line for needle in PROCESS_NEEDLES):
            matches.append(line.strip())
    return matches


def database_open_handles() -> list[str]:
    result = run(["lsof", "-n", str(DB)])
    if result.returncode not in (0, 1):
        raise RuntimeError(f"lsof database inspection failed: {result.stderr.strip()}")
    if result.returncode == 1 or not result.stdout.strip():
        return []
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[1:] if lines and lines[0].startswith("COMMAND") else lines


def lease_locks() -> list[str]:
    if not ARTIFACT_ROOT.is_dir():
        return []
    return sorted(str(path) for path in ARTIFACT_ROOT.rglob("campaign.lease.lock"))


def staging_residue(root: Path) -> list[str]:
    staging = root / ".staging"
    if not staging.is_dir():
        return []
    return sorted(str(path) for path in staging.iterdir())


def standard_application_markers() -> list[str]:
    if not STANDARD_APP_ROOT.is_dir():
        return []
    return sorted(
        str(path)
        for path in STANDARD_APP_ROOT.glob("*/application-marker.json")
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    phase = "START"
    result: dict[str, Any] = {
        "status": "BLOCKED",
        "verdict": (
            "V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_OPERATIONAL_REREADINESS_BLOCKED"
        ),
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "authoritative_database_writes": 0,
        "authorization_created": False,
        "printer_runtime_started": False,
        "standard_four_hour_started": False,
    }
    try:
        phase = "GIT_IDENTITY"
        require(REPO.is_dir(), f"repository missing: {REPO}")
        branch = git("branch", "--show-current")
        head = git("rev-parse", "HEAD")
        tracked_status = git("status", "--porcelain=v1", "-uno")
        require(branch == EXPECTED_BRANCH, f"branch mismatch: {branch}")
        require(not tracked_status, "tracked worktree/index is not clean")
        result["branch"] = branch
        result["head"] = head
        result["tracked_tree_clean"] = True

        phase = "STALE_WRAPPER_ENV"
        stale_env = {
            name: os.environ.get(name)
            for name in WRAPPER_ENV_NAMES
            if os.environ.get(name)
        }
        require(not stale_env, f"stale wrapper-bound environment present: {sorted(stale_env)}")
        result["stale_wrapper_environment"] = stale_env

        phase = "HOST_QUIESCENCE_BEFORE"
        processes_before = active_process_matches()
        require(not processes_before, f"active Printer process matches: {processes_before}")
        handles_before = database_open_handles()
        require(not handles_before, f"authoritative database has open handles: {handles_before}")
        locks_before = lease_locks()
        require(not locks_before, f"campaign lease locks present: {locks_before}")
        standard_staging_before = staging_residue(STANDARD_APP_ROOT)
        ordinary_staging_before = staging_residue(ORDINARY_APP_ROOT)
        require(not standard_staging_before, f"standard wrapper staging residue: {standard_staging_before}")
        require(not ordinary_staging_before, f"ordinary wrapper staging residue: {ordinary_staging_before}")
        markers_before = standard_application_markers()
        require(not markers_before, f"unexpected consumed standard-four-hour application marker(s): {markers_before}")

        phase = "DATABASE_BASELINE"
        before = database_fingerprint()
        require(not before["sidecars"], f"authoritative database sidecars present: {before['sidecars']}")
        require(
            before["sha256"] == EXPECTED_LAST_TRUST_SHA256,
            "authoritative database SHA-256 drifted from the post-DTW100 trust anchor",
        )
        require(
            before["size"] == EXPECTED_LAST_TRUST_SIZE,
            "authoritative database size drifted from the post-DTW100 trust anchor",
        )

        # Import Printer only after exact Git, process, open-handle, lock and DB
        # byte-state checks establish a quiescent read-only audit boundary.
        sys.path.insert(0, str(REPO / "src"))
        from printer_v1.db.migrate import (
            canonical_migration_count,
            canonical_migration_names,
        )
        from printer_v1.operator_cli.operational_memory_factory_command import (
            build_standard_four_hour_preflight,
        )

        phase = "CANONICAL_MIGRATION_IDENTITY"
        names = canonical_migration_names()
        require(
            canonical_migration_count() == EXPECTED_MIGRATION_COUNT,
            "repository canonical migration count drifted",
        )
        require(
            names and names[-1] == EXPECTED_MIGRATION_HEAD,
            "repository canonical migration head drifted",
        )

        phase = "STANDARD_FOUR_HOUR_PREFLIGHT"
        preflight = build_standard_four_hour_preflight(repository_root=REPO)
        require(
            preflight.get("status") == "V2_9_8B_STANDARD_FOUR_HOUR_PREFLIGHT_READY",
            f"standard-four-hour preflight not ready: {preflight.get('status')}",
        )
        require(int(preflight.get("source_calls") or 0) == 0, "preflight made source calls")
        require(
            int(preflight.get("scheduler_runtime_calls") or 0) == 0,
            "preflight made Scheduler runtime calls",
        )
        require(int(preflight.get("database_writes") or 0) == 0, "preflight wrote database state")
        require(
            preflight.get("database_sha256") == before["sha256"],
            "preflight database SHA disagrees with filesystem fingerprint",
        )
        require(
            int(preflight.get("migration_count") or 0) == EXPECTED_MIGRATION_COUNT,
            "preflight migration count mismatch",
        )
        require(
            preflight.get("latest_migration") == EXPECTED_MIGRATION_HEAD,
            "preflight migration head mismatch",
        )
        standard_policy = dict(preflight.get("standard_four_hour_policy") or {})
        ceilings = dict(preflight.get("standard_four_hour_ceilings") or {})
        require(standard_policy.get("continuous_first_hour") is True, "first-hour continuation is not enabled")
        require(standard_policy.get("continuous_four_hour") is True, "four-hour continuation is not enabled")
        require(standard_policy.get("standard_four_hour_campaign") is True, "standard-four-hour authority is absent")
        require(
            set(standard_policy.get("locked_windows") or ()) == {"WINDOW_12H", "WINDOW_24H"},
            "later-window lock set is not exact",
        )
        require(int(ceilings.get("governed_requests") or 0) == 230, "standard request ceiling drifted")
        require(int(ceilings.get("scheduler_rows") or 0) == 210, "standard Scheduler ceiling drifted")

        phase = "HOST_QUIESCENCE_AFTER"
        after = database_fingerprint()
        require(after == before, "authoritative database changed during rereadiness")
        processes_after = active_process_matches()
        require(not processes_after, f"Printer process appeared during rereadiness: {processes_after}")
        handles_after = database_open_handles()
        require(not handles_after, f"database handle remained after rereadiness: {handles_after}")
        locks_after = lease_locks()
        require(not locks_after, f"campaign lease lock appeared during rereadiness: {locks_after}")
        standard_staging_after = staging_residue(STANDARD_APP_ROOT)
        ordinary_staging_after = staging_residue(ORDINARY_APP_ROOT)
        require(not standard_staging_after, f"standard wrapper staging appeared: {standard_staging_after}")
        require(not ordinary_staging_after, f"ordinary wrapper staging appeared: {ordinary_staging_after}")
        markers_after = standard_application_markers()
        require(not markers_after, f"standard authorization was consumed during rereadiness: {markers_after}")

        result.update(
            {
                "status": "PASS",
                "verdict": (
                    "V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_OPERATIONAL_REREADINESS_HOST_PASS"
                ),
                "database": before,
                "database_unchanged_during_rereadiness": True,
                "matches_post_dtw100_database_trust_anchor": True,
                "migration_count": EXPECTED_MIGRATION_COUNT,
                "migration_head": EXPECTED_MIGRATION_HEAD,
                "integrity": preflight.get("integrity"),
                "foreign_key_violations": preflight.get("foreign_key_violations"),
                "active_counts": preflight.get("active_counts"),
                "locked_capability_counts": preflight.get("locked_capability_counts"),
                "source_contract": preflight.get("source_contract"),
                "dependency_preflight": preflight.get("dependency_preflight"),
                "concrete_composition_preflight": preflight.get("concrete_composition_preflight"),
                "holder_budget_preflight": preflight.get("holder_budget_preflight"),
                "standard_four_hour_policy": standard_policy,
                "standard_four_hour_ceilings": ceilings,
                "active_process_matches_before": processes_before,
                "active_process_matches_after": processes_after,
                "database_open_handles_before": handles_before,
                "database_open_handles_after": handles_after,
                "campaign_lease_locks_before": locks_before,
                "campaign_lease_locks_after": locks_after,
                "standard_wrapper_staging_before": standard_staging_before,
                "standard_wrapper_staging_after": standard_staging_after,
                "ordinary_wrapper_staging_before": ordinary_staging_before,
                "ordinary_wrapper_staging_after": ordinary_staging_after,
                "standard_application_markers_before": markers_before,
                "standard_application_markers_after": markers_after,
                "source_calls": 0,
                "scheduler_runtime_calls": 0,
                "authoritative_database_writes": 0,
                "authorization_created": False,
                "printer_runtime_started": False,
                "standard_four_hour_started": False,
                "next_step": "REREADINESS_CLOSEOUT_BEFORE_ANY_FRESH_AUTHORIZATION",
            }
        )
        return_code = 0
    except BaseException as exc:
        result["phase"] = phase
        result["error"] = f"{type(exc).__name__}:{exc}"
        result["next_step"] = "STOP_AND_REVIEW_REREADINESS_BLOCKER"
        return_code = 3

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
