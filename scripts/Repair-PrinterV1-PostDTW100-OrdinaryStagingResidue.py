from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any

REPO = Path.home() / "Developer" / "MoneyPrinter"
EXPECTED_BRANCH = "agent/v2-9-8b-post-dtw100-ordinary-staging-residue-audit"
DB = REPO / "data" / "printer_v1.sqlite3"
ARTIFACT_ROOT = Path.home() / "PrinterOperations" / "v2-9-8"
ORDINARY_APP_ROOT = ARTIFACT_ROOT / "window-15m-one-shot-applications"
STAGING_ROOT = ORDINARY_APP_ROOT / ".staging"
QUARANTINE_ROOT = (
    ARTIFACT_ROOT
    / "historical-wrapper-staging-quarantine"
    / "post-dtw100-ordinary-staging-residue"
)
EXPECTED_DB_SHA256 = "6ce0e27332427243cffd055c41de58408f46dbcd84d43a764bf1764915a176fb"
EXPECTED_DB_SIZE = 76_435_456

# None means the audited staging directory must be empty. Otherwise the exact
# directory contents must be one regular git-provenance-manifest.json with this hash.
EXPECTED_STAGING: dict[str, str | None] = {
    "V2_9_8B_WINDOW_15M_AUTH_20260802T112358Z-8c6effa328cd4a6fa05b5e2e016a273d": None,
    "V2_9_8B_WINDOW_15M_AUTH_20260803T204800Z-bae5318756834afa8218bc1874e712fd": (
        "d1705ced3a8629ad87a2745a78ec0940b77494e0a6177b0e8192fe7659e098b1"
    ),
    "V2_9_8B_WINDOW_15M_AUTH_20260804T214901Z-c1b4d8360ddb485dbbeadfb0f5773c46": (
        "76beaa565e716c82fd3cf4bf5a4e96206246bfc905029b5cf5d63196ffa84e90"
    ),
    "V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-3778d27807ff40edac6e9ac961b78ea9": (
        "d010dc1b2e7f8d220cb81aefd2f8474d7b35de1cc4618f8daa2675ee8ff1d9a1"
    ),
    "V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z-f47145e2df5b41bea6e44475c8c464ba": (
        "47d76219c47e4dbe77d2901f089b3fc4604c6cd3835841188cfb479ca82ead04"
    ),
    "index-restoration-premarker": None,
    "sim-preauth": None,
}

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
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def database_fingerprint() -> dict[str, Any]:
    require(DB.is_file(), f"authoritative database missing: {DB}")
    require(not os.path.islink(DB), "authoritative database path is a symlink")
    info = DB.stat()
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
        "size": int(info.st_size),
        "inode": int(info.st_ino),
        "mtime_ns": int(info.st_mtime_ns),
        "sidecars": sidecars,
    }


def active_process_matches() -> list[str]:
    result = run(["ps", "-axo", "pid=,command="])
    require(result.returncode == 0, f"process inspection failed: {result.stderr.strip()}")
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if any(needle in line for needle in PROCESS_NEEDLES)
    ]


def database_open_handles() -> list[str]:
    result = run(["lsof", "-n", str(DB)])
    require(
        result.returncode in (0, 1),
        f"lsof database inspection failed: {result.stderr.strip()}",
    )
    if result.returncode == 1 or not result.stdout.strip():
        return []
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[1:] if lines and lines[0].startswith("COMMAND") else lines


def lease_locks() -> list[str]:
    if not ARTIFACT_ROOT.is_dir():
        return []
    return sorted(str(path) for path in ARTIFACT_ROOT.rglob("campaign.lease.lock"))


def mode_string(mode: int) -> str:
    return oct(stat.S_IMODE(mode))


def directory_snapshot(path: Path) -> dict[str, Any]:
    require(path.exists(), f"staging entry missing: {path.name}")
    require(not os.path.islink(path), f"staging directory is symlink: {path.name}")
    root_stat = os.stat(path, follow_symlinks=False)
    require(stat.S_ISDIR(root_stat.st_mode), f"staging entry is not directory: {path.name}")
    entries: list[dict[str, Any]] = []
    for entry in sorted(os.scandir(path), key=lambda value: value.name):
        require(not entry.is_symlink(), f"staging child is symlink: {path.name}/{entry.name}")
        entry_stat = entry.stat(follow_symlinks=False)
        require(stat.S_ISREG(entry_stat.st_mode), f"staging child is not regular file: {path.name}/{entry.name}")
        child = Path(entry.path)
        entries.append(
            {
                "name": entry.name,
                "size": int(entry_stat.st_size),
                "mode": mode_string(entry_stat.st_mode),
                "inode": int(entry_stat.st_ino),
                "mtime_ns": int(entry_stat.st_mtime_ns),
                "sha256": sha256_file(child),
            }
        )
    return {
        "name": path.name,
        "root": {
            "mode": mode_string(root_stat.st_mode),
            "inode": int(root_stat.st_ino),
            "mtime_ns": int(root_stat.st_mtime_ns),
        },
        "entries": entries,
    }


def validate_exact_snapshot(name: str, snapshot: dict[str, Any]) -> None:
    expected_hash = EXPECTED_STAGING[name]
    entries = list(snapshot["entries"])
    if expected_hash is None:
        require(not entries, f"expected empty staging directory drifted: {name}")
        return
    require(len(entries) == 1, f"manifest staging directory entry count drifted: {name}")
    only = entries[0]
    require(
        only["name"] == "git-provenance-manifest.json",
        f"unexpected staging child name: {name}/{only['name']}",
    )
    require(
        only["sha256"] == expected_hash,
        f"staging manifest SHA-256 drifted: {name}",
    )


def comparable_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    # Rename must preserve directory/file identity and bytes. The lexical path is
    # intentionally absent from the snapshot, so the same object can compare at
    # source and quarantine destinations.
    return snapshot


def main() -> int:
    phase = "START"
    moved: list[str] = []
    before_snapshots: dict[str, dict[str, Any]] = {}
    result: dict[str, Any] = {
        "status": "BLOCKED",
        "verdict": "V2_9_8B_POST_DTW100_ORDINARY_STAGING_RESIDUE_QUARANTINE_REPAIR_BLOCKED",
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "authoritative_database_writes": 0,
        "authorization_created": False,
        "printer_runtime_started": False,
        "standard_four_hour_started": False,
        "canonical_application_mutations": 0,
        "authorization_package_mutations": 0,
        "deletions": 0,
        "moved": moved,
    }
    try:
        phase = "GIT_IDENTITY"
        require(REPO.is_dir(), f"repository missing: {REPO}")
        branch = git("branch", "--show-current")
        head = git("rev-parse", "HEAD")
        require(branch == EXPECTED_BRANCH, f"branch mismatch: {branch}")
        require(not git("status", "--porcelain=v1", "-uno"), "tracked worktree/index is not clean")
        result["branch"] = branch
        result["head"] = head
        result["tracked_tree_clean"] = True

        phase = "STALE_WRAPPER_ENV"
        stale_env = [name for name in WRAPPER_ENV_NAMES if os.environ.get(name)]
        require(not stale_env, f"stale wrapper-bound environment present: {stale_env}")

        phase = "HOST_QUIESCENCE_BEFORE"
        processes_before = active_process_matches()
        handles_before = database_open_handles()
        locks_before = lease_locks()
        require(not processes_before, f"active Printer process matches: {processes_before}")
        require(not handles_before, f"authoritative DB open handles: {handles_before}")
        require(not locks_before, f"campaign lease locks present: {locks_before}")

        phase = "DATABASE_BASELINE"
        db_before = database_fingerprint()
        require(not db_before["sidecars"], f"authoritative database sidecars present: {db_before['sidecars']}")
        require(db_before["sha256"] == EXPECTED_DB_SHA256, "authoritative DB SHA-256 drifted")
        require(db_before["size"] == EXPECTED_DB_SIZE, "authoritative DB size drifted")

        phase = "EXACT_STAGING_ALLOWLIST"
        require(STAGING_ROOT.is_dir(), f"ordinary staging root missing: {STAGING_ROOT}")
        require(not os.path.islink(STAGING_ROOT), "ordinary staging root is a symlink")
        observed_names = sorted(entry.name for entry in os.scandir(STAGING_ROOT))
        expected_names = sorted(EXPECTED_STAGING)
        require(observed_names == expected_names, f"staging allowlist drifted: observed={observed_names}")
        require(not QUARANTINE_ROOT.exists(), f"quarantine target already exists: {QUARANTINE_ROOT}")
        require(not os.path.lexists(QUARANTINE_ROOT), f"quarantine target filesystem entry already exists: {QUARANTINE_ROOT}")

        phase = "EXACT_STAGING_CONTENTS"
        for name in expected_names:
            snapshot = directory_snapshot(STAGING_ROOT / name)
            validate_exact_snapshot(name, snapshot)
            before_snapshots[name] = comparable_snapshot(snapshot)

        # All fail-closed validation is complete before the first filesystem mutation.
        phase = "CREATE_QUARANTINE_ROOT"
        QUARANTINE_ROOT.mkdir(parents=True, exist_ok=False)

        phase = "ATOMIC_QUARANTINE_RENAMES"
        for name in expected_names:
            source = STAGING_ROOT / name
            target = QUARANTINE_ROOT / name
            require(not os.path.lexists(target), f"quarantine child target exists: {target}")
            os.rename(source, target)
            moved.append(name)

        phase = "POST_MOVE_VERIFICATION"
        remaining = sorted(entry.name for entry in os.scandir(STAGING_ROOT))
        require(not remaining, f"live staging is not empty after quarantine: {remaining}")
        quarantine_names = sorted(entry.name for entry in os.scandir(QUARANTINE_ROOT))
        require(quarantine_names == expected_names, f"quarantine name set mismatch: {quarantine_names}")
        after_snapshots: dict[str, dict[str, Any]] = {}
        for name in expected_names:
            snapshot = comparable_snapshot(directory_snapshot(QUARANTINE_ROOT / name))
            after_snapshots[name] = snapshot
            require(snapshot == before_snapshots[name], f"quarantined bytes/identity changed: {name}")

        phase = "HOST_QUIESCENCE_AFTER"
        db_after = database_fingerprint()
        require(db_after == db_before, "authoritative database changed during quarantine repair")
        processes_after = active_process_matches()
        handles_after = database_open_handles()
        locks_after = lease_locks()
        require(not processes_after, f"Printer process appeared during repair: {processes_after}")
        require(not handles_after, f"DB handle appeared during repair: {handles_after}")
        require(not locks_after, f"campaign lease lock appeared during repair: {locks_after}")

        result.update(
            {
                "status": "PASS",
                "verdict": "V2_9_8B_POST_DTW100_ORDINARY_STAGING_RESIDUE_QUARANTINE_REPAIR_PASS",
                "database_before": db_before,
                "database_after": db_after,
                "database_unchanged": True,
                "staging_root": str(STAGING_ROOT),
                "staging_entries_after": [],
                "quarantine_root": str(QUARANTINE_ROOT),
                "quarantine_entry_count": len(expected_names),
                "quarantine_entries": expected_names,
                "before_snapshots": before_snapshots,
                "after_snapshots": after_snapshots,
                "active_process_matches_before": processes_before,
                "active_process_matches_after": processes_after,
                "database_open_handles_before": handles_before,
                "database_open_handles_after": handles_after,
                "campaign_lease_locks_before": locks_before,
                "campaign_lease_locks_after": locks_after,
                "filesystem_mutations": 1 + len(expected_names),
                "deletions": 0,
                "canonical_application_mutations": 0,
                "authorization_package_mutations": 0,
                "next_step": "RERUN_STANDARD_FOUR_HOUR_OPERATIONAL_REREADINESS",
            }
        )
        return_code = 0
    except BaseException as exc:
        result["phase"] = phase
        result["error"] = f"{type(exc).__name__}:{exc}"
        result["moved"] = list(moved)
        if STAGING_ROOT.is_dir():
            result["remaining_staging_entries"] = sorted(
                entry.name for entry in os.scandir(STAGING_ROOT)
            )
        result["next_step"] = (
            "READ_ONLY_PARTIAL_REPAIR_RECOVERY_AUDIT"
            if moved
            else "STOP_AND_REVIEW_REPAIR_BLOCKER"
        )
        return_code = 3

    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
