"""Read-only native Linux host/runtime evidence collection for Printer V1.

Proof support only. This module does not create authorization, start Printer,
contact providers, run Scheduler work, or mutate the authoritative database.
"""

from __future__ import annotations

import argparse
import grp
from importlib import metadata
import json
import os
from pathlib import Path
import pwd
import re
import sqlite3
import ssl
import stat
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence

from printer_v1.operator_cli.linux_remote_host_portability import (
    LinuxPortabilityError,
    assert_local_ext4_paths,
    assert_remote_disk_space,
    assert_system_time_synchronized,
    linux_verified_host_process_inventory,
)


_HEAD = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


class NativeHostPreflightError(RuntimeError):
    """Fail-closed native host/runtime proof prerequisite fault."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NativeHostPreflightError(message)


def _run_text(
    command: Sequence[str],
    *,
    runner: Callable[..., Any],
    timeout_seconds: float = 5.0,
) -> str:
    if timeout_seconds <= 0:
        raise NativeHostPreflightError("command probe timeout must be positive")
    try:
        result = runner(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise NativeHostPreflightError(
            f"host command probe failed: {command[0]}"
        ) from exc
    if getattr(result, "returncode", None) != 0:
        detail = str(getattr(result, "stderr", "") or "").strip()
        raise NativeHostPreflightError(
            f"host command probe blocked: {command[0]}: {detail}"
        )
    text = str(getattr(result, "stdout", "") or "").strip()
    _require(bool(text), f"host command probe returned empty evidence: {command[0]}")
    return text


def assert_service_account_layout(
    *,
    repository_root: str | Path,
    service_home: str | Path = "/var/lib/printer-v1",
    service_user: str = "printer-v1",
    service_group: str = "printer-v1",
    getpwnam: Callable[[str], Any] = pwd.getpwnam,
    getgrnam: Callable[[str], Any] = grp.getgrnam,
) -> dict[str, Any]:
    """Prove the native service account and private durable HOME layout."""
    try:
        user = getpwnam(service_user)
        group = getgrnam(service_group)
    except KeyError as exc:
        raise NativeHostPreflightError(
            "printer-v1 service account/group is unavailable"
        ) from exc

    _require(int(user.pw_uid) > 0, "service account must be unprivileged")
    _require(int(group.gr_gid) > 0, "service group must be unprivileged")
    _require(
        int(user.pw_gid) == int(group.gr_gid),
        "service account primary group mismatch",
    )

    home = Path(service_home).expanduser().resolve()
    repository = Path(repository_root).resolve()
    _require(Path(user.pw_dir).resolve() == home, "service account HOME mismatch")
    _require(home.is_dir(), "service HOME is unavailable")
    home_stat = home.stat()
    _require(
        int(home_stat.st_uid) == int(user.pw_uid),
        "service HOME owner mismatch",
    )
    _require(
        int(home_stat.st_gid) == int(group.gr_gid),
        "service HOME group mismatch",
    )
    _require(
        stat.S_IMODE(home_stat.st_mode) & 0o077 == 0,
        "service HOME permissions are not private",
    )

    _require(repository.is_dir(), "repository root is unavailable")
    repository_mode = stat.S_IMODE(repository.stat().st_mode)
    _require(
        repository_mode & 0o022 == 0,
        "repository root is group/other writable",
    )

    return {
        "user": service_user,
        "group": service_group,
        "uid": int(user.pw_uid),
        "gid": int(group.gr_gid),
        "home": str(home),
        "home_mode": f"{stat.S_IMODE(home_stat.st_mode):04o}",
        "repository_mode": f"{repository_mode:04o}",
        "approved": True,
    }


def _runtime_evidence(
    *,
    repository_root: Path,
    python_version_info: Sequence[int],
    python_executable: str | Path,
    sqlite_version: str,
    openssl_version: str,
    package_version: Callable[[str], str],
) -> dict[str, Any]:
    version = tuple(int(part) for part in tuple(python_version_info)[:3])
    _require(len(version) == 3, "Python runtime version is incomplete")
    _require(version[:2] == (3, 11), "native proof requires Python 3.11")

    executable = Path(python_executable).expanduser().resolve()
    expected = (repository_root / ".venv" / "bin" / "python").resolve()
    _require(
        executable == expected,
        "Python executable is not the repo-local .venv",
    )
    _require(
        executable.is_file() and os.access(executable, os.X_OK),
        "repo-local Python executable is unavailable",
    )

    try:
        websockets_version = str(package_version("websockets")).strip()
        certifi_version = str(package_version("certifi")).strip()
    except Exception as exc:
        raise NativeHostPreflightError(
            "required runtime package version is unavailable"
        ) from exc

    _require(bool(websockets_version), "websockets version is empty")
    _require(bool(certifi_version), "certifi version is empty")
    _require(bool(str(sqlite_version).strip()), "SQLite runtime version is empty")
    _require(bool(str(openssl_version).strip()), "OpenSSL runtime version is empty")

    return {
        "python_version": ".".join(str(part) for part in version),
        "python_executable": str(executable),
        "sqlite_version": str(sqlite_version).strip(),
        "openssl_version": str(openssl_version).strip(),
        "websockets_version": websockets_version,
        "certifi_version": certifi_version,
    }


def collect_native_host_preflight(
    *,
    repository_root: str | Path,
    sizing_db_path: str | Path,
    application_root: str | Path,
    artifact_root: str | Path,
    systemd_unit: str | Path,
    storage_growth_ceiling_bytes: int,
    service_home: str | Path = "/var/lib/printer-v1",
    service_user: str = "printer-v1",
    service_group: str = "printer-v1",
    python_version_info: Sequence[int] | None = None,
    python_executable: str | Path | None = None,
    sqlite_version: str | None = None,
    openssl_version: str | None = None,
    package_version: Callable[[str], str] = metadata.version,
    runner: Callable[..., Any] = subprocess.run,
    filesystem_preflight: Callable[..., Mapping[str, Any]] = assert_local_ext4_paths,
    disk_space_preflight: Callable[..., Mapping[str, Any]] = assert_remote_disk_space,
    time_sync_preflight: Callable[..., Mapping[str, Any]] = (
        assert_system_time_synchronized
    ),
    service_account_preflight: Callable[..., Mapping[str, Any]] = (
        assert_service_account_layout
    ),
) -> dict[str, Any]:
    """Collect fail-closed native host evidence without operational execution."""
    _require(sys.platform.startswith("linux"), "native host preflight requires Linux")
    root = Path(repository_root).resolve()

    version_info = tuple(
        python_version_info
        if python_version_info is not None
        else sys.version_info[:3]
    )
    runtime = _runtime_evidence(
        repository_root=root,
        python_version_info=version_info,
        python_executable=python_executable or sys.executable,
        sqlite_version=sqlite_version or sqlite3.sqlite_version,
        openssl_version=openssl_version or ssl.OPENSSL_VERSION,
        package_version=package_version,
    )

    sizing_db = Path(sizing_db_path).expanduser().resolve()
    app_root = Path(application_root).expanduser().resolve()
    artifacts = Path(artifact_root).expanduser().resolve()
    unit = Path(systemd_unit).expanduser().resolve()
    _require(sizing_db.is_file(), "sizing DB evidence file is unavailable")
    _require(unit.is_file(), "systemd unit artifact is unavailable")

    account = dict(
        service_account_preflight(
            repository_root=root,
            service_home=service_home,
            service_user=service_user,
            service_group=service_group,
        )
    )
    filesystems = dict(
        filesystem_preflight(
            {
                "sizing_db": sizing_db,
                "application_root": app_root,
                "operational_artifact_root": artifacts,
            }
        )
    )
    disk_space = dict(
        disk_space_preflight(
            authoritative_db_path=sizing_db,
            write_paths={
                "sizing_db_parent": sizing_db.parent,
                "application_root": app_root,
                "operational_artifact_root": artifacts,
            },
            storage_growth_ceiling_bytes=int(storage_growth_ceiling_bytes),
        )
    )
    time_sync = dict(time_sync_preflight())

    git_version = _run_text(["git", "--version"], runner=runner)
    head = _run_text(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        runner=runner,
    )
    branch = _run_text(
        ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
        runner=runner,
    )
    _require(_HEAD.fullmatch(head) is not None, "Git HEAD evidence is malformed")
    _require(
        bool(branch) and branch != "HEAD",
        "Git branch evidence is detached or empty",
    )

    procps_version = _run_text(["ps", "--version"], runner=runner)
    process_inventory = linux_verified_host_process_inventory(runner=runner)
    systemd_version = _run_text(
        ["systemd-analyze", "--version"], runner=runner
    ).splitlines()[0].strip()

    try:
        verify = runner(
            ["systemd-analyze", "verify", str(unit)],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            timeout=10.0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise NativeHostPreflightError(
            "systemd unit verification is uninspectable"
        ) from exc
    if getattr(verify, "returncode", None) != 0:
        detail = str(getattr(verify, "stderr", "") or "").strip()
        raise NativeHostPreflightError(
            f"systemd unit verification failed: {detail}"
        )

    return {
        "status": "REMOTE_HOST_NATIVE_RUNTIME_PREFLIGHT_READY",
        "runtime": runtime,
        "git": {
            "version": git_version,
            "branch": branch,
            "head": head,
        },
        "procps": {
            "version": procps_version,
            "inventory_rows": len(process_inventory),
            "inventory_verified": True,
        },
        "systemd": {
            "version": systemd_version,
            "unit_path": str(unit),
            "unit_verified": True,
        },
        "service_account": account,
        "filesystems": filesystems,
        "disk_space": disk_space,
        "time_sync": time_sync,
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="printer-v1-remote-host-native-preflight"
    )
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--sizing-db-path", required=True)
    parser.add_argument("--application-root", required=True)
    parser.add_argument("--artifact-root", required=True)
    parser.add_argument("--systemd-unit", required=True)
    parser.add_argument("--service-home", default="/var/lib/printer-v1")
    parser.add_argument("--service-user", default="printer-v1")
    parser.add_argument("--service-group", default="printer-v1")
    parser.add_argument("--storage-growth-ceiling-bytes", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    ceiling = args.storage_growth_ceiling_bytes
    if ceiling is None:
        from printer_v1.operator_cli.operational_memory_factory_command import (
            STORAGE_BYTE_CEILING,
        )

        ceiling = STORAGE_BYTE_CEILING
    try:
        evidence = collect_native_host_preflight(
            repository_root=args.repository_root,
            sizing_db_path=args.sizing_db_path,
            application_root=args.application_root,
            artifact_root=args.artifact_root,
            systemd_unit=args.systemd_unit,
            storage_growth_ceiling_bytes=int(ceiling),
            service_home=args.service_home,
            service_user=args.service_user,
            service_group=args.service_group,
        )
    except (NativeHostPreflightError, LinuxPortabilityError) as exc:
        print(
            json.dumps(
                {
                    "status": "REMOTE_HOST_NATIVE_RUNTIME_PREFLIGHT_BLOCKED",
                    "error": f"{type(exc).__name__}:{exc}",
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
