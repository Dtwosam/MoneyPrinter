"""Narrow Linux remote-host portability primitives for Printer V1.

Infrastructure support only. This module owns no source, Scheduler, campaign,
window, retrieval, decision, position, trade, or PnL policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
from typing import Any, Callable, Mapping


APPROVED_REMOTE_FILESYSTEM = "ext4"
DEFAULT_WAIT_POLL_SECONDS = 0.25
STOP_REASON = "REMOTE_HOST_OPERATOR_STOP"
_MANIFEST_SHA_ENV = "PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256"
_APPLICATION_MARKER_SHA_ENV = "PRINTER_V1_APPLICATION_MARKER_SHA256"
_EXPECTATION_VERSION = "OPERATIONAL_DATABASE_TARGET_EXPECTATION_V1"
_REUSE_FLAGS = (
    "automatic_retry_allowed",
    "manual_rerun_allowed",
    "resume_allowed",
    "restart_allowed",
    "successor_allowed",
)


class LinuxPortabilityError(RuntimeError):
    """Fail-closed Linux host portability or supervision fault."""


@dataclass(frozen=True)
class MountInfoEntry:
    mount_id: int
    parent_id: int
    major_minor: str
    root: str
    mount_point: Path
    filesystem_type: str
    mount_source: str


def _decode_mountinfo(value: str) -> str:
    replacements = {
        r"\040": " ",
        r"\011": "\t",
        r"\012": "\n",
        r"\134": "\\",
    }
    for encoded, decoded in replacements.items():
        value = value.replace(encoded, decoded)
    return value


def parse_mountinfo(text: str) -> tuple[MountInfoEntry, ...]:
    """Parse Linux /proc/self/mountinfo into bounded mount identity evidence."""
    if not isinstance(text, str) or not text.strip():
        raise LinuxPortabilityError("mountinfo evidence is empty")
    entries: list[MountInfoEntry] = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        try:
            separator = parts.index("-")
        except ValueError as exc:
            raise LinuxPortabilityError(
                f"mountinfo line {line_number} is malformed"
            ) from exc
        if separator < 6 or len(parts) < separator + 4:
            raise LinuxPortabilityError(
                f"mountinfo line {line_number} is malformed"
            )
        try:
            mount_id = int(parts[0])
            parent_id = int(parts[1])
        except ValueError as exc:
            raise LinuxPortabilityError(
                f"mountinfo line {line_number} has invalid identifiers"
            ) from exc
        mount_point_text = _decode_mountinfo(parts[4])
        if not mount_point_text.startswith("/"):
            raise LinuxPortabilityError(
                f"mountinfo line {line_number} has non-absolute mount point"
            )
        filesystem_type = parts[separator + 1]
        mount_source = _decode_mountinfo(parts[separator + 2])
        if not filesystem_type:
            raise LinuxPortabilityError(
                f"mountinfo line {line_number} has empty filesystem type"
            )
        entries.append(
            MountInfoEntry(
                mount_id=mount_id,
                parent_id=parent_id,
                major_minor=parts[2],
                root=_decode_mountinfo(parts[3]),
                mount_point=Path(mount_point_text),
                filesystem_type=filesystem_type,
                mount_source=mount_source,
            )
        )
    if not entries:
        raise LinuxPortabilityError("mountinfo contains no mount entries")
    return tuple(entries)


def _existing_path_for_stat(path: Path) -> Path:
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            raise LinuxPortabilityError(f"no existing ancestor for path: {path}")
        candidate = parent
    return candidate


def _owning_mount(path: Path, entries: tuple[MountInfoEntry, ...]) -> MountInfoEntry:
    resolved = Path(os.path.realpath(_existing_path_for_stat(path)))
    matches: list[tuple[int, MountInfoEntry]] = []
    for entry in entries:
        mount = Path(os.path.realpath(entry.mount_point))
        try:
            resolved.relative_to(mount)
        except ValueError:
            continue
        matches.append((len(mount.parts), entry))
    if not matches:
        raise LinuxPortabilityError(f"no mountinfo owner for path: {path}")
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def assert_local_ext4_paths(
    paths: Mapping[str, str | Path],
    *,
    mountinfo_text: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Positively prove every supplied authoritative root is on local ext4."""
    if not paths:
        raise LinuxPortabilityError("filesystem preflight paths are empty")
    if mountinfo_text is None:
        try:
            mountinfo_text = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
        except OSError as exc:
            raise LinuxPortabilityError("kernel mountinfo is unavailable") from exc
    entries = parse_mountinfo(mountinfo_text)
    evidence: dict[str, dict[str, Any]] = {}
    for label, raw_path in paths.items():
        if not isinstance(label, str) or not label:
            raise LinuxPortabilityError("filesystem preflight label is malformed")
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path(os.path.abspath(path))
        owner = _owning_mount(path, entries)
        if owner.filesystem_type != APPROVED_REMOTE_FILESYSTEM:
            raise LinuxPortabilityError(
                f"{label} filesystem is not approved local ext4: "
                f"{owner.filesystem_type}"
            )
        existing = _existing_path_for_stat(path)
        try:
            device = int(os.stat(existing, follow_symlinks=True).st_dev)
        except OSError as exc:
            raise LinuxPortabilityError(f"{label} path identity is unavailable") from exc
        evidence[label] = {
            "path": str(path),
            "existing_identity_path": str(Path(os.path.realpath(existing))),
            "filesystem_type": owner.filesystem_type,
            "mount_point": str(owner.mount_point),
            "mount_source": owner.mount_source,
            "st_dev": device,
            "approved": True,
        }
    return evidence


def assert_remote_disk_space(
    *,
    authoritative_db_path: str | Path,
    write_paths: Mapping[str, str | Path],
    storage_growth_ceiling_bytes: int,
    disk_usage: Callable[[str | Path], Any] = shutil.disk_usage,
) -> dict[str, Any]:
    """Fail closed unless every remote write root has a derived free-space reserve."""
    database = Path(authoritative_db_path).expanduser()
    if not database.is_absolute():
        database = Path(os.path.abspath(database))
    if not database.is_file():
        raise LinuxPortabilityError(
            "authoritative database is unavailable for disk preflight"
        )
    database_size = int(database.stat().st_size)
    if database_size <= 0:
        raise LinuxPortabilityError("authoritative database size is invalid")
    if (
        type(storage_growth_ceiling_bytes) is not int
        or storage_growth_ceiling_bytes <= 0
    ):
        raise LinuxPortabilityError(
            "storage growth ceiling must be a positive integer"
        )
    if not write_paths:
        raise LinuxPortabilityError("disk preflight paths are empty")

    terminal_report_log_margin = max(database_size, storage_growth_ceiling_bytes)
    required_free_bytes = (
        (3 * database_size)
        + storage_growth_ceiling_bytes
        + terminal_report_log_margin
    )
    evidence: dict[str, dict[str, Any]] = {}
    for label, raw_path in write_paths.items():
        if not isinstance(label, str) or not label:
            raise LinuxPortabilityError("disk preflight label is malformed")
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = Path(os.path.abspath(path))
        existing = _existing_path_for_stat(path)
        try:
            usage = disk_usage(existing)
            total = int(usage.total)
            free = int(usage.free)
        except (OSError, TypeError, ValueError, AttributeError) as exc:
            raise LinuxPortabilityError(
                f"{label} disk-space evidence is unavailable"
            ) from exc
        if total <= 0 or free < 0 or free > total:
            raise LinuxPortabilityError(
                f"{label} disk-space evidence is malformed"
            )
        if free < required_free_bytes:
            raise LinuxPortabilityError(
                f"{label} free space is below the required remote reserve: "
                f"{free} < {required_free_bytes}"
            )
        evidence[label] = {
            "path": str(path),
            "existing_identity_path": str(Path(os.path.realpath(existing))),
            "total_bytes": total,
            "free_bytes": free,
            "required_free_bytes": required_free_bytes,
            "approved": True,
        }
    return {
        "database_size_bytes": database_size,
        "storage_growth_ceiling_bytes": storage_growth_ceiling_bytes,
        "sqlite_temp_journal_reserve_bytes": database_size,
        "verified_backup_reserve_bytes": database_size,
        "disposable_restore_reserve_bytes": database_size,
        "terminal_report_log_margin_bytes": terminal_report_log_margin,
        "required_free_bytes": required_free_bytes,
        "paths": evidence,
    }


def assert_system_time_synchronized(
    *,
    timeout_seconds: float = 5.0,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Require systemd time synchronization evidence before authorization use."""
    if timeout_seconds <= 0:
        raise LinuxPortabilityError(
            "time synchronization probe timeout must be positive"
        )
    command = [
        "timedatectl",
        "show",
        "--property=NTPSynchronized",
        "--value",
    ]
    try:
        result = runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise LinuxPortabilityError(
            "system time synchronization is uninspectable"
        ) from exc
    if getattr(result, "returncode", None) != 0:
        raise LinuxPortabilityError("system time synchronization probe failed")
    synchronized = str(getattr(result, "stdout", "") or "").strip().lower()
    if synchronized != "yes":
        raise LinuxPortabilityError("system time is not synchronized")
    return {
        "probe": "timedatectl",
        "ntp_synchronized": True,
        "approved": True,
    }


def _assert_no_symlink_components(path: Path) -> None:
    """Reject a symlink at any existing component of one absolute path."""
    absolute = path if path.is_absolute() else Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    for part in parts:
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except OSError as exc:
            raise LinuxPortabilityError(
                f"directory durability path component is unavailable: {current}"
            ) from exc
        if stat.S_ISLNK(mode):
            raise LinuxPortabilityError(
                f"directory durability path contains a symlink: {current}"
            )


def fsync_directory_required(path: str | Path) -> None:
    """Fail closed unless one exact non-aliased directory is durably synced."""
    directory = Path(path)
    if not directory.is_absolute():
        directory = Path(os.path.abspath(directory))
    _assert_no_symlink_components(directory)
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(directory, flags)
    except OSError as exc:
        raise LinuxPortabilityError("directory durability open failed") from exc
    try:
        try:
            mode = os.fstat(descriptor).st_mode
            if not stat.S_ISDIR(mode):
                raise LinuxPortabilityError(
                    "directory durability target is not a directory"
                )
            os.fsync(descriptor)
        except OSError as exc:
            raise LinuxPortabilityError("directory durability fsync failed") from exc
    finally:
        os.close(descriptor)


def linux_verified_host_process_inventory(
    *,
    timeout_seconds: float = 5.0,
    runner: Callable[..., Any] = subprocess.run,
) -> tuple[tuple[int, str], ...]:
    """Reuse the existing POSIX inventory owner with strict Linux parse evidence.

    The underlying owner still performs exactly one bounded ``ps`` call. This
    adapter only validates that every non-empty successful output line starts
    with a numeric PID before allowing the existing parser to consume it. It
    creates no second inventory pass, polling loop, signal, kill, or recovery.
    """
    from printer_v1.operator_cli.operational_campaign_recovery import (
        OperationalCampaignRecoveryError,
        host_process_inventory,
    )

    if timeout_seconds <= 0:
        raise LinuxPortabilityError("Linux process inventory timeout must be positive")

    def validating_runner(command: list[str], **kwargs: Any) -> Any:
        result = runner(command, **kwargs)
        if getattr(result, "returncode", None) == 0:
            stdout = str(getattr(result, "stdout", "") or "")
            for line_number, raw in enumerate(stdout.splitlines(), start=1):
                stripped = raw.strip()
                if not stripped:
                    continue
                fields = stripped.split(maxsplit=1)
                try:
                    int(fields[0])
                except (IndexError, ValueError) as exc:
                    raise LinuxPortabilityError(
                        f"Linux process inventory line {line_number} is malformed"
                    ) from exc
        return result

    try:
        return host_process_inventory(
            timeout_seconds=timeout_seconds,
            runner=validating_runner,
        )
    except LinuxPortabilityError:
        raise
    except OperationalCampaignRecoveryError as exc:
        raise LinuxPortabilityError(
            "Linux process inventory could not be verified"
        ) from exc


@dataclass
class StopSignalState:
    """Process-local, signal-safe stop intent; handlers perform no I/O."""

    requested: bool = False
    first_signal: int | None = None
    signal_count: int = 0
    cancellation_attempted: bool = False

    def handle_signal(self, signum: int, _frame: object | None) -> None:
        self.signal_count += 1
        if self.first_signal is None:
            self.first_signal = int(signum)
        self.requested = True


def _parse_instant(value: str, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise LinuxPortabilityError(f"{label} timestamp is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LinuxPortabilityError(f"{label} timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _exact_sha256(value: Any, *, label: str) -> str:
    text = str(value or "")
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise LinuxPortabilityError(f"{label} must be lowercase SHA-256")
    return text


def _load_configuration(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LinuxPortabilityError("campaign configuration binding is malformed") from exc
    if not isinstance(value, dict):
        raise LinuxPortabilityError("campaign configuration binding is malformed")
    return value


def _bound_supervision_candidate(
    row: sqlite3.Row,
    *,
    expected_manifest_sha256: str,
    expected_application_marker_sha256: str,
) -> dict[str, Any] | None:
    configuration = _load_configuration(row["configuration_json"])
    expectation = configuration.get("operational_database_target_expectation")
    if not isinstance(expectation, Mapping):
        return None
    if expectation.get("expectation_version") != _EXPECTATION_VERSION:
        return None
    exact_ownership = (
        ("campaign_id", str(row["campaign_id"])),
        ("campaign_run_id", str(row["run_id"])),
        ("configuration_id", str(row["configuration_id"])),
    )
    if any(str(expectation.get(field) or "") != expected for field, expected in exact_ownership):
        return None
    if str(expectation.get("authorization_marker_sha256") or "") != expected_manifest_sha256:
        return None
    if str(expectation.get("application_marker_sha256") or "") != expected_application_marker_sha256:
        return None
    if expectation.get("authorization_consumed_once") is not True:
        return None
    if expectation.get("invocation_count") != 1 or expectation.get("allowed_invocation_count") != 1:
        return None
    if any(expectation.get(flag) is not False for flag in _REUSE_FLAGS):
        return None
    execution_id = str(expectation.get("execution_id") or "").strip()
    authorization_id = str(expectation.get("authorization_id") or "").strip()
    cycle_id = str(expectation.get("cycle_id") or "").strip()
    if not execution_id or not authorization_id or not cycle_id:
        return None
    internal_marker = configuration.get("authorization_marker")
    if not isinstance(internal_marker, Mapping):
        return None
    internal_expected = {
        "marker_id": f"{execution_id}-authorization-marker",
        "execution_id": execution_id,
        "campaign_id": str(row["campaign_id"]),
        "configuration_id": str(row["configuration_id"]),
        "run_id": str(row["run_id"]),
    }
    if any(str(internal_marker.get(field) or "") != expected for field, expected in internal_expected.items()):
        return None
    result = dict(row)
    result.update(
        {
            "authorization_id": authorization_id,
            "execution_id": execution_id,
            "cycle_id": cycle_id,
            "manifest_sha256": expected_manifest_sha256,
            "application_marker_sha256": expected_application_marker_sha256,
        }
    )
    return result


def resolve_exact_active_supervision(
    db_path: str | Path,
    *,
    child_started_at: str,
    expected_manifest_sha256: str,
    expected_application_marker_sha256: str,
) -> dict[str, Any] | None:
    """Resolve the one active supervision positively bound to this wrapper child."""
    started = _parse_instant(child_started_at, label="child start")
    manifest_sha = _exact_sha256(expected_manifest_sha256, label="manifest SHA-256")
    application_marker_sha = _exact_sha256(
        expected_application_marker_sha256,
        label="application marker SHA-256",
    )
    database = Path(db_path).resolve()
    if not database.is_file():
        raise LinuxPortabilityError("authoritative database is unavailable")
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            f"file:{database.as_posix()}?mode=ro", uri=True, timeout=0.0
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        for table in (
            "printer_memory_factory_campaign_supervision",
            "printer_memory_factory_campaign_configurations",
        ):
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if exists is None:
                raise LinuxPortabilityError(
                    "campaign supervision binding schema is unavailable"
                )
        rows = connection.execute(
            """SELECT s.supervision_id,s.campaign_id,s.configuration_id,s.run_id,
                      s.owner_id,s.supervision_state,s.cancellation_requested_at,
                      s.cancellation_reason,s.created_at,cfg.configuration_json
                 FROM printer_memory_factory_campaign_supervision AS s
                 JOIN printer_memory_factory_campaign_configurations AS cfg
                   ON cfg.campaign_id=s.campaign_id
                  AND cfg.configuration_id=s.configuration_id
                WHERE s.supervision_state IN ('ACTIVE','STOPPING')"""
        ).fetchall()
    except sqlite3.Error as exc:
        raise LinuxPortabilityError("campaign supervision inspection failed") from exc
    finally:
        if connection is not None:
            connection.close()

    temporal_rows: list[sqlite3.Row] = []
    exact_rows: list[dict[str, Any]] = []
    for row in rows:
        created = _parse_instant(str(row["created_at"]), label="supervision created_at")
        if created < started:
            continue
        temporal_rows.append(row)
        candidate = _bound_supervision_candidate(
            row,
            expected_manifest_sha256=manifest_sha,
            expected_application_marker_sha256=application_marker_sha,
        )
        if candidate is not None:
            exact_rows.append(candidate)
    if not temporal_rows:
        return None
    if len(exact_rows) != 1:
        raise LinuxPortabilityError(
            "active campaign supervision is not uniquely bound to this wrapper invocation"
        )
    if len(temporal_rows) != 1:
        raise LinuxPortabilityError(
            "active campaign supervision is ambiguous under the one-shot boundary"
        )
    return exact_rows[0]


def attempt_exact_active_cancellation(
    db_path: str | Path,
    *,
    stop_state: StopSignalState,
    child_started_at: str,
    expected_manifest_sha256: str,
    expected_application_marker_sha256: str,
    requester: Callable[..., Mapping[str, Any]] | None = None,
) -> bool:
    """Request canonical campaign cancellation at most once after exact ownership."""
    if not stop_state.requested or stop_state.cancellation_attempted:
        return False
    row = resolve_exact_active_supervision(
        db_path,
        child_started_at=child_started_at,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_application_marker_sha256=expected_application_marker_sha256,
    )
    if row is None:
        return False
    if requester is None:
        from printer_v1.operator_cli.campaign_supervision import (
            request_campaign_cancellation,
        )

        requester = request_campaign_cancellation
    stop_state.cancellation_attempted = True
    requester(
        db_path,
        supervision_id=str(row["supervision_id"]),
        campaign_id=str(row["campaign_id"]),
        configuration_id=str(row["configuration_id"]),
        run_id=str(row["run_id"]),
        owner_id=str(row["owner_id"]),
        reason=STOP_REASON,
    )
    return True


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def launch_child_foreground(
    *,
    command: list[str],
    cwd: Path,
    env: Mapping[str, str],
    stdout_path: Path,
    stderr_path: Path,
    authoritative_db_path: str | Path,
    stop_state: StopSignalState,
    popen_factory: Callable[..., Any] = subprocess.Popen,
    cancellation_requester: Callable[..., Mapping[str, Any]] | None = None,
    wait_timeout_seconds: float = DEFAULT_WAIT_POLL_SECONDS,
    directory_sync: Callable[[str | Path], None] = fsync_directory_required,
) -> dict[str, Any]:
    """Supervise one wrapper-bound child in foreground; never directly signal it."""
    if wait_timeout_seconds <= 0:
        raise LinuxPortabilityError("foreground wait timeout must be positive")
    expected_manifest_sha256 = _exact_sha256(
        env.get(_MANIFEST_SHA_ENV), label="wrapper manifest SHA-256"
    )
    expected_application_marker_sha256 = _exact_sha256(
        env.get(_APPLICATION_MARKER_SHA_ENV),
        label="wrapper application marker SHA-256",
    )
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    directory_sync(stdout_path.parent)
    child_started_at = _utc_now()
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        process = popen_factory(
            command,
            cwd=str(cwd),
            env=dict(env),
            stdout=stdout,
            stderr=stderr,
            shell=False,
        )
        while True:
            if stop_state.requested and not stop_state.cancellation_attempted:
                attempt_exact_active_cancellation(
                    authoritative_db_path,
                    stop_state=stop_state,
                    child_started_at=child_started_at,
                    expected_manifest_sha256=expected_manifest_sha256,
                    expected_application_marker_sha256=(
                        expected_application_marker_sha256
                    ),
                    requester=cancellation_requester,
                )
            try:
                returncode = process.wait(timeout=wait_timeout_seconds)
                break
            except subprocess.TimeoutExpired:
                continue
        stdout.flush()
        stderr.flush()
        os.fsync(stdout.fileno())
        os.fsync(stderr.fileno())
    directory_sync(stdout_path.parent)
    return {"returncode": int(returncode), "pid": int(process.pid)}


__all__ = [
    "APPROVED_REMOTE_FILESYSTEM",
    "LinuxPortabilityError",
    "MountInfoEntry",
    "StopSignalState",
    "assert_local_ext4_paths",
    "assert_remote_disk_space",
    "assert_system_time_synchronized",
    "attempt_exact_active_cancellation",
    "fsync_directory_required",
    "launch_child_foreground",
    "linux_verified_host_process_inventory",
    "parse_mountinfo",
    "resolve_exact_active_supervision",
]
