from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any

REPO = Path.home() / "Developer" / "MoneyPrinter"
DB = REPO / "data" / "printer_v1.sqlite3"
BASE_HELPER = (
    REPO / "scripts" / "Review-PrinterV1-PostDTW100-StandardFourHour-Rereadiness.py"
)
EXPECTED_BRANCH = (
    "agent/v2-9-8b-post-dtw100-standard-four-hour-rereadiness-after-staging-repair"
)
EXPECTED_DB_SHA256 = (
    "6ce0e27332427243cffd055c41de58408f46dbcd84d43a764bf1764915a176fb"
)
EXPECTED_DB_SIZE = 76_435_456
EXPECTED_MIGRATION_COUNT = 54
EXPECTED_MIGRATION_HEAD = "054_pre_lifecycle_discovery_refresh_wait.sql"
MIGRATION_PACKAGE_ROOT = (
    REPO
    / "operator-runs"
    / "v2-9-8b-authoritative-mig050"
    / "V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f"
)

# Exact visible untracked inventory captured read-only on the operator host after
# the ordinary-wrapper staging quarantine repair. This is audit evidence only;
# it is not a production Git allowlist and never becomes runtime authority.
EXPECTED_VISIBLE_UNTRACKED: dict[str, tuple[str, int]] = {
    "operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_started.json": (
        "8678ecb14feb1f04a315303ac5afd92639541900a267b8951adc7fad75050e8a",
        50133,
    ),
    "operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stderr.txt": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        0,
    ),
    "operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/application_stdout.txt": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        0,
    ),
    "operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/backup_restore_preflight.json": (
        "569bea4e6d9aeacb6f612b4ec7ea85f43a73bfdc5cbde1693ecb8191aeb98083",
        13836,
    ),
    "operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/closeout_inputs.json": (
        "c10a76ba5729a2e4af42a9f3a4219571e0f959c2ba3d1214cfa1aa96a072e11f",
        2384,
    ),
    "operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/final_authorization.json": (
        "eb5388f3fac82b0c628a6b3e1e2893702fe221755838f971c6900f4e24e2b835",
        6589,
    ),
    "operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/post_migration_proof.json": (
        "fd7509280b2541eb3afa6010bdfdb44f6769219cd8a345224cfa26c6854f3c94",
        103903,
    ),
    "operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preauthorization_evidence.json": (
        "4250b0e6a85bad41e50712ef21e5b11aab633c54e0246fc72aff037f7437119c",
        36274,
    ),
    "operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/preflight.json": (
        "3e3897da82a2012c1eb63aa8ea883a83a8c64fae49a86b2ff6192c8f82c88383",
        18590,
    ),
    "operator-runs/v2-9-8b-authoritative-mig050/V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f/rollback_rehearsal.json": (
        "997695a5aa4f4ffe6b8dd09970c93692d1a935491cf104b9a63a9c38440af149",
        16244,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260805T224959Z/final_authorization.json": (
        "c928f9588f5c82b350f71d0df40c4cb3a7e2a92fd366541f109488edbc17dcea",
        7761,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260806T005252Z/final_authorization.json": (
        "d58e354a2d01acc0c893ff20941055cd4cf5fb86e2b4daf889b0e8312db90e59",
        8532,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260806T103951Z/final_authorization.json": (
        "5cfa2c67bef94b16427cdf2cf426a38bf0543aaa328a2d095c2d85fa5e10a74c",
        8914,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260806T115911Z/final_authorization.json": (
        "2648cb962cd87ef15a02a9247294ae3df0ce17996054a74ce16c73cffe0e545f",
        8964,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260806T131011Z/final_authorization.json": (
        "a4e0acb604556b9ccb813ce0aa9597813d866f38089cce40e584a309bd84b969",
        9094,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260808T122000Z/final_authorization.json": (
        "a0d297ab2cb1d76bd34914366170a1b2c843fef27d6e0e617f9f54b9ae0aa57b",
        6511,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260808T133100Z/final_authorization.json": (
        "4e6f4ae2845ed8bb09241d49868e18d6f2c80a9adbf464e35c9ebd26dd941253",
        6458,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260808T171829Z/final_authorization.json": (
        "9bf51d6d45d79f2532808f3280ae8afcbf3bbc252ecff55ba12599ba34ba5d7a",
        6688,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260808T215650Z/final_authorization.json": (
        "6b1500d00a7a309d0726dec9146ac30f04ee9fe4cdad72cbc8f0eae4231263d1",
        6738,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T011312Z/final_authorization.json": (
        "db453fa7c14bd892bf13fb7fe9a96a43f6beb29b7d33ad5858fafcd3b1ac3eb4",
        6786,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T090158Z/final_authorization.json": (
        "27f6ec95b7de6cdfeed92c12bcb6f8b095c3c1d7c870efba112ac85ae8ca6778",
        6834,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T095642Z/final_authorization.json": (
        "e31384e2d54a6d3b07380e9234511bb22dae481e4b91de0878e3025559dd23cc",
        6882,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T120100Z/final_authorization.json": (
        "d64f2b4285aeebf93a4369350da960a9398f38a4123a160ce8e53cb505c66de1",
        6930,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T130306Z/final_authorization.json": (
        "e37405cd6b0e1cb5295961546baf71d74e99c90b76640ed0eae4679f38ec2a24",
        6978,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T163540Z/final_authorization.json": (
        "52a036cec8d104cc0bd22ff52a66be33b040515fe518ce06f97d3fb2bd8aed15",
        7067,
    ),
    "operator-runs/v2-9-8b-window-15m-final-authorization/V2_9_8B_WINDOW_15M_AUTH_20260809T180257Z/final_authorization.json": (
        "b9e5c8191a3840ed2688516ba8d3ecceb46c177487ea16d3d76d56475eb12426",
        7150,
    ),
}

EXPECTED_MIGRATION_PACKAGE: dict[str, tuple[str, int]] = {
    "application_started.json": (
        "8678ecb14feb1f04a315303ac5afd92639541900a267b8951adc7fad75050e8a",
        50133,
    ),
    "application_stderr.txt": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        0,
    ),
    "application_stdout.txt": (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        0,
    ),
    "backup_restore_preflight.json": (
        "569bea4e6d9aeacb6f612b4ec7ea85f43a73bfdc5cbde1693ecb8191aeb98083",
        13836,
    ),
    "closeout_inputs.json": (
        "c10a76ba5729a2e4af42a9f3a4219571e0f959c2ba3d1214cfa1aa96a072e11f",
        2384,
    ),
    "disposable-restore/printer_v1-rehearsal.sqlite3": (
        "e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2",
        65654784,
    ),
    "final_authorization.json": (
        "eb5388f3fac82b0c628a6b3e1e2893702fe221755838f971c6900f4e24e2b835",
        6589,
    ),
    "post_migration_proof.json": (
        "fd7509280b2541eb3afa6010bdfdb44f6769219cd8a345224cfa26c6854f3c94",
        103903,
    ),
    "preauthorization_evidence.json": (
        "4250b0e6a85bad41e50712ef21e5b11aab633c54e0246fc72aff037f7437119c",
        36274,
    ),
    "preflight.json": (
        "3e3897da82a2012c1eb63aa8ea883a83a8c64fae49a86b2ff6192c8f82c88383",
        18590,
    ),
    "rollback_rehearsal.json": (
        "997695a5aa4f4ffe6b8dd09970c93692d1a935491cf104b9a63a9c38440af149",
        16244,
    ),
    "verified-backup/printer_v1-pre050.sqlite3": (
        "e13c40892f0c14d4c07960e00218569a536c50c0fc27815049284c3dd2aff5c2",
        65654784,
    ),
}
EXPECTED_MIGRATION_SUBDIRS = {"disposable-restore", "verified-backup"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        check=False,
    )


def load_base_helper() -> Any:
    require(BASE_HELPER.is_file(), f"base rereadiness helper missing: {BASE_HELPER}")
    spec = importlib.util.spec_from_file_location(
        "printer_v1_post_dtw100_standard_four_hour_rereadiness_base",
        BASE_HELPER,
    )
    require(spec is not None and spec.loader is not None, "base helper could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EXPECTED_BRANCH = EXPECTED_BRANCH
    return module


def visible_untracked_snapshot() -> dict[str, dict[str, Any]]:
    proc = run(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=REPO)
    require(proc.returncode == 0, f"git untracked inventory failed: {proc.stderr.decode(errors='replace').strip()}")
    paths = sorted(
        item.decode("utf-8", errors="surrogateescape")
        for item in proc.stdout.split(b"\0")
        if item
    )
    require(paths == sorted(EXPECTED_VISIBLE_UNTRACKED), f"visible untracked inventory drifted: {paths}")
    records: dict[str, dict[str, Any]] = {}
    for relative in paths:
        path = REPO / relative
        require(os.path.lexists(path), f"untracked evidence missing: {relative}")
        require(not os.path.islink(path), f"untracked evidence is symlink: {relative}")
        info = os.stat(path, follow_symlinks=False)
        require(stat.S_ISREG(info.st_mode), f"untracked evidence is not regular file: {relative}")
        expected_hash, expected_size = EXPECTED_VISIBLE_UNTRACKED[relative]
        actual_hash = sha256_file(path)
        require(int(info.st_size) == expected_size, f"untracked evidence size drifted: {relative}")
        require(actual_hash == expected_hash, f"untracked evidence SHA-256 drifted: {relative}")
        records[relative] = {
            "sha256": actual_hash,
            "size": int(info.st_size),
            "inode": int(info.st_ino),
            "mtime_ns": int(info.st_mtime_ns),
        }
    return records


def migration_package_snapshot() -> dict[str, dict[str, Any]]:
    require(MIGRATION_PACKAGE_ROOT.is_dir(), f"migration package missing: {MIGRATION_PACKAGE_ROOT}")
    require(not os.path.islink(MIGRATION_PACKAGE_ROOT), "migration package root is symlink")
    files: dict[str, dict[str, Any]] = {}
    directories: set[str] = set()
    stack = [MIGRATION_PACKAGE_ROOT]
    while stack:
        current = stack.pop()
        for entry in sorted(os.scandir(current), key=lambda value: value.name):
            path = Path(entry.path)
            relative = path.relative_to(MIGRATION_PACKAGE_ROOT).as_posix()
            require(not entry.is_symlink(), f"migration package contains symlink: {relative}")
            info = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                directories.add(relative)
                stack.append(path)
                continue
            require(stat.S_ISREG(info.st_mode), f"migration package contains non-regular entry: {relative}")
            files[relative] = {
                "sha256": sha256_file(path),
                "size": int(info.st_size),
                "inode": int(info.st_ino),
                "mtime_ns": int(info.st_mtime_ns),
            }
    require(directories == EXPECTED_MIGRATION_SUBDIRS, f"migration package directory set drifted: {sorted(directories)}")
    require(set(files) == set(EXPECTED_MIGRATION_PACKAGE), f"migration package file set drifted: {sorted(files)}")
    for relative, (expected_hash, expected_size) in EXPECTED_MIGRATION_PACKAGE.items():
        record = files[relative]
        require(record["sha256"] == expected_hash, f"migration package SHA-256 drifted: {relative}")
        require(record["size"] == expected_size, f"migration package size drifted: {relative}")
    return files


def evidence_digest(records: dict[str, dict[str, Any]]) -> str:
    payload = [
        {
            "path": path,
            "sha256": value["sha256"],
            "size": value["size"],
        }
        for path, value in sorted(records.items())
    ]
    data = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    return hashlib.sha256(data).hexdigest()


def non_git_standard_four_hour_preflight() -> dict[str, Any]:
    sys.path.insert(0, str(REPO / "src"))
    from printer_v1.operator_cli import operational_memory_factory_command as command
    from printer_v1.operator_cli.window_15m_concrete_composition import (
        ConcreteCompositionError,
        run_window_15m_concrete_composition_preflight,
        window_15m_preflight_builders,
    )

    source = command.build_readiness_source_contract_preflight()
    require(source.get("status") == "READY", f"source-contract preflight not ready: {source}")
    require(int(source.get("external_requests") or 0) == 0, "source-contract preflight made external requests")

    try:
        concrete = run_window_15m_concrete_composition_preflight(
            repository_root=str(REPO),
            timeout_seconds=5.0,
        )
    except ConcreteCompositionError as exc:
        raise RuntimeError(f"concrete composition preflight blocked: {exc}") from exc

    dependency = command.assert_runtime_dependency_preflight(
        repository_root=REPO,
        adapter_builders=window_15m_preflight_builders(timeout_seconds=5.0),
    )
    require(dependency.status == "READY", f"runtime dependency preflight not ready: {dependency.to_dict()}")

    budget = command.build_operational_budget_preflight(
        admission_operation_ceiling=command.ADMISSION_OPERATION_CEILING,
        discovery_request_ceiling=command.DISCOVERY_REQUEST_CEILING,
        governed_15m_request_ceiling=command.GOVERNED_15M_REQUEST_CEILING,
        governed_requests_per_token=command.GOVERNED_REQUESTS_PER_TOKEN,
    )
    require(budget.get("status") == "READY", f"holder budget preflight not ready: {budget}")
    require(int(budget.get("source_calls") or 0) == 0, "holder budget preflight made source calls")

    connection = command._read_only(DB)
    try:
        migrations = tuple(
            str(row[0])
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations ORDER BY version"
            ).fetchall()
        )
        integrity = tuple(
            str(row[0])
            for row in connection.execute("PRAGMA integrity_check").fetchall()
        )
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        active = command._active_counts(connection)
        locked = command._locked_capability_counts(connection)
        historical_audit = int(
            connection.execute(
                "SELECT COUNT(*) FROM printer_paper_audit_reports WHERE paper_position_id IS NULL"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    ledger = command.validate_migration_ledger(migrations)
    require(bool(ledger.get("matches")), f"migration ledger mismatch: {command.describe_migration_ledger_mismatch(migrations)}")
    require(len(migrations) == EXPECTED_MIGRATION_COUNT, f"migration count drifted: {len(migrations)}")
    require(bool(migrations) and migrations[-1] == EXPECTED_MIGRATION_HEAD, f"migration head drifted: {migrations[-1] if migrations else None}")
    require(command.canonical_migration_count() == EXPECTED_MIGRATION_COUNT, "canonical migration count drifted")
    canonical_names = command.canonical_migration_names()
    require(bool(canonical_names) and canonical_names[-1] == EXPECTED_MIGRATION_HEAD, "canonical migration head drifted")
    require(integrity == ("ok",), f"database integrity failed: {integrity}")
    require(not foreign_keys, f"foreign-key violations: {len(foreign_keys)}")
    require(not any(active.values()), f"active operational state: {dict(active)}")
    command._validate_locked_baseline(locked)
    require(historical_audit == 1, f"historical null-position paper-audit count drifted: {historical_audit}")

    policy = command.STANDARD_FOUR_HOUR_POLICY
    require(command.AUTOMATIC_RETRIES == 0, "automatic retry policy drifted")
    require(set(policy.locked_windows) == {"WINDOW_12H", "WINDOW_24H"}, "standard later-window locks drifted")
    require(policy.standard_four_hour_campaign is True, "standard four-hour campaign authority missing")
    require(policy.continuous_four_hour is True, "standard four-hour continuation missing")
    require(policy.governed_request_ceiling == 230, "standard governed request ceiling drifted")
    require(policy.scheduler_row_ceiling == 210, "standard Scheduler row ceiling drifted")

    return {
        "status": "READY",
        "source_contract": {
            "status": source.get("status"),
            "external_requests": source.get("external_requests"),
            "secret_material_recorded": source.get("secret_material_recorded"),
        },
        "concrete_composition_preflight": concrete,
        "dependency_preflight": dependency.to_dict(),
        "holder_budget_preflight": budget,
        "migration_count": len(migrations),
        "migration_head": migrations[-1],
        "integrity": "ok",
        "foreign_key_violations": 0,
        "active_counts": active,
        "locked_capability_counts": locked,
        "historical_paper_audit_rows_preserved": historical_audit,
        "standard_four_hour_policy": {
            "policy_version": policy.policy_version,
            "continuous_first_hour": True,
            "continuous_four_hour": True,
            "standard_four_hour_campaign": True,
            "locked_windows": policy.locked_windows,
            "automatic_retries": 0,
            "restart_created": False,
            "successor_created": False,
        },
        "standard_four_hour_ceilings": {
            "duration_seconds": policy.duration_seconds,
            "pre_lifecycle_acquisition_duration_seconds": policy.pre_lifecycle_acquisition_duration_seconds,
            "governed_requests": policy.governed_request_ceiling,
            "governed_requests_per_token": policy.governed_requests_per_token,
            "scheduler_rows": policy.scheduler_row_ceiling,
        },
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
    }


def main() -> int:
    phase = "START"
    result: dict[str, Any] = {
        "status": "BLOCKED",
        "verdict": "V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_OPERATIONAL_REREADINESS_BLOCKED",
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "authoritative_database_writes": 0,
        "filesystem_mutations": 0,
        "authorization_created": False,
        "printer_runtime_started": False,
        "standard_four_hour_started": False,
        "git_provenance_authorization_fabricated": False,
    }
    try:
        phase = "LOAD_BASE_HELPER"
        base = load_base_helper()

        phase = "PYTHON_IDENTITY"
        require(sys.version_info >= (3, 11), f"Python >=3.11 required, found {sys.version.split()[0]}")
        result["python"] = {"executable": sys.executable, "version": sys.version.split()[0]}

        phase = "GIT_IDENTITY"
        require(REPO.is_dir(), f"repository missing: {REPO}")
        branch = base.git("branch", "--show-current")
        head = base.git("rev-parse", "HEAD")
        require(branch == EXPECTED_BRANCH, f"branch mismatch: {branch}")
        require(not base.git("status", "--porcelain=v1", "-uno"), "tracked worktree/index is not clean")
        result.update({"branch": branch, "head": head, "tracked_tree_clean": True})

        phase = "STALE_WRAPPER_ENV"
        stale_env = {
            name: os.environ.get(name)
            for name in base.WRAPPER_ENV_NAMES
            if os.environ.get(name)
        }
        require(not stale_env, f"stale wrapper-bound environment present: {sorted(stale_env)}")
        result["stale_wrapper_environment"] = stale_env

        phase = "HOST_QUIESCENCE_BEFORE"
        processes_before = base.active_process_matches()
        handles_before = base.database_open_handles()
        locks_before = base.lease_locks()
        standard_staging_before = base.staging_residue(base.STANDARD_APP_ROOT)
        ordinary_staging_before = base.staging_residue(base.ORDINARY_APP_ROOT)
        markers_before = base.standard_application_markers()
        require(not processes_before, f"active Printer process matches: {processes_before}")
        require(not handles_before, f"authoritative database has open handles: {handles_before}")
        require(not locks_before, f"campaign lease locks present: {locks_before}")
        require(not standard_staging_before, f"standard wrapper staging residue: {standard_staging_before}")
        require(not ordinary_staging_before, f"ordinary wrapper staging residue: {ordinary_staging_before}")
        require(not markers_before, f"standard-four-hour application marker exists: {markers_before}")

        phase = "DATABASE_BASELINE"
        db_before = base.database_fingerprint()
        require(not db_before["sidecars"], f"authoritative database sidecars present: {db_before['sidecars']}")
        require(db_before["sha256"] == EXPECTED_DB_SHA256, "authoritative DB SHA-256 drifted")
        require(db_before["size"] == EXPECTED_DB_SIZE, "authoritative DB size drifted")

        phase = "RETAINED_EVIDENCE_BEFORE"
        visible_before = visible_untracked_snapshot()
        migration_before = migration_package_snapshot()
        visible_digest_before = evidence_digest(visible_before)
        migration_digest_before = evidence_digest(migration_before)

        phase = "NON_GIT_STANDARD_FOUR_HOUR_PREFLIGHT"
        preflight = non_git_standard_four_hour_preflight()

        phase = "HOST_QUIESCENCE_AFTER"
        db_after = base.database_fingerprint()
        require(db_after == db_before, "authoritative database changed during rereadiness")
        processes_after = base.active_process_matches()
        handles_after = base.database_open_handles()
        locks_after = base.lease_locks()
        standard_staging_after = base.staging_residue(base.STANDARD_APP_ROOT)
        ordinary_staging_after = base.staging_residue(base.ORDINARY_APP_ROOT)
        markers_after = base.standard_application_markers()
        require(not processes_after, f"Printer process appeared during rereadiness: {processes_after}")
        require(not handles_after, f"database handle remained after rereadiness: {handles_after}")
        require(not locks_after, f"campaign lease lock appeared during rereadiness: {locks_after}")
        require(not standard_staging_after, f"standard wrapper staging appeared: {standard_staging_after}")
        require(not ordinary_staging_after, f"ordinary wrapper staging appeared: {ordinary_staging_after}")
        require(not markers_after, f"standard authorization marker appeared: {markers_after}")

        phase = "RETAINED_EVIDENCE_AFTER"
        visible_after = visible_untracked_snapshot()
        migration_after = migration_package_snapshot()
        require(visible_after == visible_before, "visible retained evidence changed during rereadiness")
        require(migration_after == migration_before, "migration package changed during rereadiness")

        result.update(
            {
                "status": "PASS",
                "verdict": "V2_9_8B_POST_DTW100_STANDARD_FOUR_HOUR_OPERATIONAL_REREADINESS_HOST_PASS",
                "database": db_before,
                "database_unchanged_during_rereadiness": True,
                "matches_post_dtw100_database_trust_anchor": True,
                "visible_untracked_evidence_count": len(visible_before),
                "visible_untracked_evidence_digest_sha256": visible_digest_before,
                "visible_untracked_evidence_exact": True,
                "migration_package_file_count": len(migration_before),
                "migration_package_digest_sha256": migration_digest_before,
                "migration_package_exact": True,
                "historical_ordinary_authorization_count": 16,
                "retained_evidence_authority": "AUDIT_ONLY_NOT_RUNTIME_ALLOWLIST",
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
                "migration_count": preflight["migration_count"],
                "migration_head": preflight["migration_head"],
                "integrity": preflight["integrity"],
                "foreign_key_violations": preflight["foreign_key_violations"],
                "active_counts": preflight["active_counts"],
                "locked_capability_counts": preflight["locked_capability_counts"],
                "source_contract": preflight["source_contract"],
                "dependency_preflight": preflight["dependency_preflight"],
                "concrete_composition_preflight": preflight["concrete_composition_preflight"],
                "holder_budget_preflight": preflight["holder_budget_preflight"],
                "standard_four_hour_policy": preflight["standard_four_hour_policy"],
                "standard_four_hour_ceilings": preflight["standard_four_hour_ceilings"],
                "source_calls": 0,
                "scheduler_runtime_calls": 0,
                "authoritative_database_writes": 0,
                "filesystem_mutations": 0,
                "authorization_created": False,
                "printer_runtime_started": False,
                "standard_four_hour_started": False,
                "git_provenance_authorization_fabricated": False,
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
