"""Bounded child-owned terminal evidence for ordinary WINDOW_15M runs.

The operational child writes exactly one source-safe JSON envelope. The external
one-shot wrapper validates and projects it after process exit. stderr remains
immutable debugging evidence and is never parsed as terminal truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping


CHILD_TERMINAL_SCHEMA_VERSION = "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_V1"
STANDARD_FOUR_HOUR_CHILD_TERMINAL_SCHEMA_VERSION = (
    "PRINTER_V1_STANDARD_FOUR_HOUR_CHILD_TERMINAL_V1"
)
CHILD_TERMINAL_MODE_SCHEMAS = {
    "run": CHILD_TERMINAL_SCHEMA_VERSION,
    "standard-four-hour-run": STANDARD_FOUR_HOUR_CHILD_TERMINAL_SCHEMA_VERSION,
}
CHILD_TERMINAL_ENV_VAR = "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_PATH"
APPLICATION_MARKER_ENV_VAR = "PRINTER_V1_APPLICATION_MARKER_PATH"
APPLICATION_MARKER_SHA256_ENV_VAR = (
    "PRINTER_V1_APPLICATION_MARKER_SHA256"
)
CHILD_TERMINAL_FILENAME = "child-terminal.json"
APPLICATION_MARKER_FILENAME = "application-marker.json"
MAX_CHILD_TERMINAL_BYTES = 64 * 1024
MAX_TEXT_LENGTH = 512
MAX_MAPPING_ITEMS = 20
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]+$")
_UNSAFE_TEXT_MARKERS = (
    "http://",
    "https://",
    "authorization:",
    "bearer ",
    "api_key",
    "apikey",
    "private_key",
    "secret",
    "x-api-key",
    "cookie:",
)

CHILD_TERMINAL_FIELDS = frozenset(
    {
        "schema_version",
        "created_at",
        "authorization_id",
        "marker_path",
        "marker_sha256",
        "mode",
        "status",
        "success",
        "process_exit_code",
        "terminal_category",
        "first_terminal_cause",
        "failure_phase",
        "execution_id",
        "campaign_id",
        "run_id",
        "cycle_id",
        "supervision_id",
        "marker_consumed",
        "lifecycle_started",
        "cleanup_complete",
        "lease_released",
        "active_locked_work",
        "database_identity_after",
        "source_calls",
        "scheduler_runtime_calls",
        "database_writes",
        "terminal_report_path",
        "terminal_report_sha256",
        "terminal_truth_status",
        "secondary_terminal_truth_error",
    }
)
DATABASE_IDENTITY_FIELDS = frozenset(
    {"path", "exists", "sha256", "size", "inode", "mtime_ns"}
)
IDENTIFIER_FIELDS = (
    "execution_id",
    "campaign_id",
    "run_id",
    "cycle_id",
    "supervision_id",
)
COUNT_FIELDS = ("source_calls", "scheduler_runtime_calls", "database_writes")
TERMINAL_TRUTH_STATUSES = frozenset(
    {
        "NOT_APPLICABLE_SUCCESS",
        "RECONSTRUCTED",
        "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY",
        "RECONSTRUCTION_FAILED",
        "UNAVAILABLE",
    }
)


class ChildTerminalError(RuntimeError):
    """Fail-closed child terminal binding, write, or validation fault."""


@dataclass(frozen=True)
class ChildTerminalBinding:
    terminal_path: Path
    marker_path: Path
    authorization_id: str
    marker_sha256: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ChildTerminalError(f"duplicate child terminal JSON key: {key!r}")
        result[key] = value
    return result


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_no_duplicate_keys,
        )
    except (OSError, ValueError, UnicodeError) as exc:
        raise ChildTerminalError(f"{label} is unreadable or malformed") from exc
    if not isinstance(value, dict):
        raise ChildTerminalError(f"{label} must be a JSON object")
    return value


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    try:
        return (
            json.dumps(
                dict(value),
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ChildTerminalError("child terminal payload is not canonical JSON") from exc


def _safe_text(value: Any, *, allow_none: bool = True) -> str | None:
    if value is None and allow_none:
        return None
    text = str(value or "")
    lowered = text.lower()
    if any(marker in lowered for marker in _UNSAFE_TEXT_MARKERS):
        return "[REDACTED_UNSAFE_TERMINAL_DETAIL]"
    text = "".join(ch if ch >= " " and ch != "\x7f" else " " for ch in text)
    text = " ".join(text.split())
    if len(text) > MAX_TEXT_LENGTH:
        return text[:MAX_TEXT_LENGTH] + "...[TRUNCATED]"
    return text


def _safe_identifier(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text or len(text) > 256 or _SAFE_IDENTIFIER.fullmatch(text) is None:
        return None
    return text


def _find_key(source: Mapping[str, Any], key: str) -> Any:
    if key in source:
        return source.get(key)
    for container_key in (
        "campaign_run_cycle_states",
        "terminal_safety",
        "identity",
        "action_local_terminal_truth",
        "full_run_terminal_evidence",
        "replay",
    ):
        nested = source.get(container_key)
        if isinstance(nested, Mapping):
            if key in nested:
                return nested.get(key)
            for second_key in (
                "identity",
                "terminal_safety",
                "campaign_run_cycle_states",
                "action_local_terminal_truth",
            ):
                second = nested.get(second_key)
                if isinstance(second, Mapping) and key in second:
                    return second.get(key)
    return None


def _bounded_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for raw_key in sorted(value, key=lambda item: str(item))[:MAX_MAPPING_ITEMS]:
        key = _safe_text(raw_key, allow_none=False) or ""
        if not key:
            continue
        raw = value[raw_key]
        if raw is None or isinstance(raw, (bool, int, float)):
            result[key] = raw
        else:
            result[key] = _safe_text(raw)
    return result


def _database_identity(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    result = {
        "path": _safe_text(value.get("path")),
        "exists": value.get("exists") if isinstance(value.get("exists"), bool) else None,
        "sha256": value.get("sha256") if isinstance(value.get("sha256"), str) else None,
        "size": value.get("size") if isinstance(value.get("size"), int) else None,
        "inode": value.get("inode") if isinstance(value.get("inode"), int) else None,
        "mtime_ns": value.get("mtime_ns") if isinstance(value.get("mtime_ns"), int) else None,
    }
    if result["sha256"] is not None and _SHA256.fullmatch(str(result["sha256"])) is None:
        result["sha256"] = None
    return result


def resolve_child_terminal_binding(
    environ: Mapping[str, str] | None = None,
) -> ChildTerminalBinding:
    env = os.environ if environ is None else environ
    terminal_raw = env.get(CHILD_TERMINAL_ENV_VAR)
    marker_raw = env.get(APPLICATION_MARKER_ENV_VAR)
    marker_sha_raw = env.get(APPLICATION_MARKER_SHA256_ENV_VAR)
    if not terminal_raw:
        raise ChildTerminalError("ordinary run child terminal binding is missing")
    if not marker_raw:
        raise ChildTerminalError("application marker binding is missing")
    if not isinstance(marker_sha_raw, str) or _SHA256.fullmatch(marker_sha_raw) is None:
        raise ChildTerminalError("application marker SHA-256 binding is malformed")
    terminal_path = Path(terminal_raw).expanduser()
    marker_path = Path(marker_raw).expanduser()
    if not terminal_path.is_absolute() or not marker_path.is_absolute():
        raise ChildTerminalError("child terminal and marker paths must be absolute")
    terminal_path = Path(os.path.abspath(terminal_path))
    marker_path = Path(os.path.abspath(marker_path))
    if terminal_path.name != CHILD_TERMINAL_FILENAME:
        raise ChildTerminalError("child terminal filename is invalid")
    if marker_path.name != APPLICATION_MARKER_FILENAME:
        raise ChildTerminalError("application marker filename is invalid")
    if Path(os.path.realpath(terminal_path.parent)) != Path(
        os.path.realpath(marker_path.parent)
    ):
        raise ChildTerminalError("child terminal must be the exact sibling of the marker")
    if os.path.islink(marker_path) or not marker_path.is_file():
        raise ChildTerminalError("application marker must be a regular non-symlink file")
    if os.path.islink(terminal_path):
        raise ChildTerminalError("child terminal path must not be a symlink")
    actual_marker_sha256 = _sha256_file(marker_path)
    if actual_marker_sha256 != marker_sha_raw:
        raise ChildTerminalError("application marker SHA-256 mismatch")
    marker = _load_json_object(marker_path, label="application marker")
    authorization_id = _safe_identifier(marker.get("authorization_id"))
    if authorization_id is None:
        raise ChildTerminalError("application marker authorization_id is malformed")
    return ChildTerminalBinding(
        terminal_path=terminal_path,
        marker_path=marker_path,
        authorization_id=authorization_id,
        marker_sha256=marker_sha_raw,
    )


def _failure_phase(source: Mapping[str, Any], *, success: bool) -> str | None:
    if success:
        return None
    explicit = _safe_text(_find_key(source, "failure_phase"))
    if explicit:
        return explicit
    campaign_id = _safe_identifier(_find_key(source, "campaign_id"))
    lifecycle_started = bool(_find_key(source, "lifecycle_started")) or bool(
        _find_key(source, "factory_run_id")
    )
    if campaign_id is None:
        return "COMMAND_BOOTSTRAP_OR_PREFLIGHT"
    return (
        "CAMPAIGN_LIFECYCLE_OR_CLOSEOUT"
        if lifecycle_started
        else "CAMPAIGN_PRE_LIFECYCLE"
    )


def build_child_terminal_envelope(
    *,
    binding: ChildTerminalBinding,
    source: Mapping[str, Any],
    mode: str,
    exit_code: int,
    success: bool,
) -> dict[str, Any]:
    if mode not in CHILD_TERMINAL_MODE_SCHEMAS:
        raise ChildTerminalError("child terminal mode is not authorized")
    if type(exit_code) is not int:
        raise ChildTerminalError("child terminal exit code must be an integer")
    if success is not (exit_code == 0):
        raise ChildTerminalError("child terminal success disagrees with exit code")
    first_cause = _find_key(source, "first_terminal_cause")
    if first_cause is None and not success:
        error_type = _safe_text(source.get("error_type"), allow_none=False) or "Exception"
        error_message = _safe_text(source.get("error_message"), allow_none=False) or ""
        first_cause = f"{error_type}:{error_message}" if error_message else error_type
    status = _safe_text(source.get("status"), allow_none=False) or (
        "OPERATIONAL_COMMAND_COMPLETE" if success else "OPERATIONAL_COMMAND_BLOCKED"
    )
    terminal_category = (
        "OPERATIONAL_COMMAND_COMPLETE" if success else "OPERATIONAL_COMMAND_BLOCKED"
    )
    active_raw = _find_key(source, "active_locked_work")
    active = (
        _bounded_mapping(active_raw)
        if isinstance(active_raw, Mapping)
        else None
    )
    lifecycle_raw = _find_key(source, "lifecycle_started")
    factory_run_id = _find_key(source, "factory_run_id")
    if type(lifecycle_raw) is bool:
        lifecycle_started = lifecycle_raw
    elif factory_run_id not in (None, ""):
        lifecycle_started = True
    else:
        lifecycle_started = None
    db_identity = _database_identity(_find_key(source, "database_identity_after"))
    report_path_raw = _find_key(source, "terminal_report_path") or _find_key(
        source, "report_path"
    )
    report_path = None
    report_sha = None
    if isinstance(report_path_raw, (str, Path)):
        candidate = Path(report_path_raw).expanduser()
        report_path = _safe_text(str(candidate))
        if candidate.is_file() and not os.path.islink(candidate):
            report_sha = _sha256_file(candidate)
    terminal_truth_status = _safe_identifier(
        _find_key(source, "terminal_truth_status")
    )
    if terminal_truth_status is None:
        if success:
            terminal_truth_status = "NOT_APPLICABLE_SUCCESS"
        elif isinstance(source.get("action_local_terminal_truth"), Mapping):
            terminal_truth_status = "RECONSTRUCTED"
        elif (
            _find_key(source, "database_mutation_status")
            == "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY"
        ):
            terminal_truth_status = "PROVEN_ZERO_NO_CAMPAIGN_ACTION_IDENTITY"
        else:
            terminal_truth_status = "UNAVAILABLE"
    secondary_terminal_truth_error = _safe_text(
        _find_key(source, "secondary_terminal_truth_error")
    )
    payload = {
        "schema_version": CHILD_TERMINAL_MODE_SCHEMAS[mode],
        "created_at": _utc_now(),
        "authorization_id": binding.authorization_id,
        "marker_path": str(binding.marker_path.resolve()),
        "marker_sha256": binding.marker_sha256,
        "mode": mode,
        "status": status,
        "success": bool(success),
        "process_exit_code": int(exit_code),
        "terminal_category": terminal_category,
        "first_terminal_cause": _safe_text(first_cause),
        "failure_phase": _failure_phase(source, success=success),
        "execution_id": _safe_identifier(_find_key(source, "execution_id")),
        "campaign_id": _safe_identifier(_find_key(source, "campaign_id")),
        "run_id": _safe_identifier(
            _find_key(source, "run_id") or _find_key(source, "action_run_id")
        ),
        "cycle_id": _safe_identifier(_find_key(source, "cycle_id")),
        "supervision_id": _safe_identifier(_find_key(source, "supervision_id")),
        "marker_consumed": True,
        "lifecycle_started": lifecycle_started,
        "cleanup_complete": _find_key(source, "cleanup_complete"),
        "lease_released": _find_key(source, "lease_released"),
        "active_locked_work": active,
        "database_identity_after": db_identity,
        "source_calls": _find_key(source, "source_calls"),
        "scheduler_runtime_calls": _find_key(source, "scheduler_runtime_calls"),
        "database_writes": _find_key(source, "database_writes"),
        "terminal_report_path": report_path,
        "terminal_report_sha256": report_sha,
        "terminal_truth_status": terminal_truth_status,
        "secondary_terminal_truth_error": secondary_terminal_truth_error,
    }
    for key in ("cleanup_complete", "lease_released"):
        if payload[key] is not None and not isinstance(payload[key], bool):
            payload[key] = None
    for key in ("source_calls", "scheduler_runtime_calls", "database_writes"):
        if payload[key] is not None and not isinstance(payload[key], int):
            payload[key] = None
    return payload


def write_child_terminal_envelope(
    *,
    binding: ChildTerminalBinding,
    source: Mapping[str, Any],
    mode: str,
    exit_code: int,
    success: bool,
) -> dict[str, Any]:
    payload = build_child_terminal_envelope(
        binding=binding,
        source=source,
        mode=mode,
        exit_code=exit_code,
        success=success,
    )
    data = _canonical_json_bytes(payload)
    if len(data) > MAX_CHILD_TERMINAL_BYTES:
        raise ChildTerminalError("child terminal exceeds bounded size")
    try:
        with binding.terminal_path.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise ChildTerminalError("child terminal create-once artifact already exists") from exc
    try:
        binding.terminal_path.chmod(0o444)
    except OSError:
        pass
    return payload




def _validate_safe_terminal_text(
    value: Any,
    *,
    field: str,
    required: bool = False,
) -> None:
    if value is None:
        if required:
            raise ChildTerminalError(f"child terminal field is required: {field}")
        return
    if not isinstance(value, str) or not value:
        raise ChildTerminalError(f"child terminal field is invalid: {field}")
    if len(value) > MAX_TEXT_LENGTH + 20:
        raise ChildTerminalError(f"child terminal field is invalid: {field}")
    if _safe_text(value, allow_none=False) != value:
        raise ChildTerminalError(f"child terminal field is unsafe: {field}")


def _validate_created_at(value: Any) -> None:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise ChildTerminalError("child terminal created_at is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ChildTerminalError("child terminal created_at is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ChildTerminalError("child terminal created_at must be timezone-aware")


def _validate_active_work(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping) or len(value) > MAX_MAPPING_ITEMS:
        raise ChildTerminalError("child terminal active work evidence is invalid")
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not raw_key:
            raise ChildTerminalError("child terminal active work evidence is invalid")
        if _safe_text(raw_key, allow_none=False) != raw_key:
            raise ChildTerminalError("child terminal active work evidence is invalid")
        if raw_value is None or isinstance(raw_value, bool):
            continue
        if isinstance(raw_value, int):
            continue
        if isinstance(raw_value, float):
            if not math.isfinite(raw_value):
                raise ChildTerminalError("child terminal active work evidence is invalid")
            continue
        if isinstance(raw_value, str) and _safe_text(raw_value) == raw_value:
            continue
        raise ChildTerminalError("child terminal active work evidence is invalid")


def _validate_database_identity(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping) or set(value) != DATABASE_IDENTITY_FIELDS:
        raise ChildTerminalError("child terminal database identity is invalid")
    path_value = value.get("path")
    if path_value is not None and (
        not isinstance(path_value, str) or _safe_text(path_value) != path_value
    ):
        raise ChildTerminalError("child terminal database identity path is invalid")
    exists = value.get("exists")
    if exists is not None and not isinstance(exists, bool):
        raise ChildTerminalError("child terminal database identity exists is invalid")
    digest = value.get("sha256")
    if digest is not None and (
        not isinstance(digest, str) or _SHA256.fullmatch(digest) is None
    ):
        raise ChildTerminalError("child terminal database identity SHA-256 is invalid")
    for key in ("size", "inode", "mtime_ns"):
        item = value.get(key)
        if item is not None and (
            type(item) is not int or item < 0
        ):
            raise ChildTerminalError(
                f"child terminal database identity field is invalid: {key}"
            )


def _validate_optional_count(payload: Mapping[str, Any], key: str) -> None:
    value = payload.get(key)
    if value is not None and (type(value) is not int or value < 0):
        raise ChildTerminalError(f"child terminal count is invalid: {key}")

def read_child_terminal_envelope(
    path: str | Path,
    *,
    expected_authorization_id: str,
    expected_marker_path: str | Path,
    expected_marker_sha256: str,
    expected_exit_code: int,
    expected_mode: str = "run",
) -> dict[str, Any]:
    candidate = Path(path).expanduser()
    marker = Path(expected_marker_path).expanduser()
    if not candidate.is_absolute() or not marker.is_absolute():
        raise ChildTerminalError("child terminal validation paths must be absolute")
    candidate = Path(os.path.abspath(candidate))
    marker = Path(os.path.abspath(marker))
    if candidate.name != CHILD_TERMINAL_FILENAME:
        raise ChildTerminalError("child terminal filename is invalid")
    if Path(os.path.realpath(candidate.parent)) != Path(os.path.realpath(marker.parent)):
        raise ChildTerminalError("child terminal must be the exact sibling of the marker")
    if os.path.islink(candidate):
        raise ChildTerminalError("child terminal must not be a symlink")
    try:
        mode = os.stat(candidate, follow_symlinks=False).st_mode
    except OSError as exc:
        raise ChildTerminalError("child terminal is missing") from exc
    if not stat.S_ISREG(mode):
        raise ChildTerminalError("child terminal is not a regular file")
    if candidate.stat().st_size > MAX_CHILD_TERMINAL_BYTES:
        raise ChildTerminalError("child terminal exceeds bounded size")
    payload = _load_json_object(candidate, label="child terminal")
    payload_fields = set(payload)
    missing_fields = sorted(CHILD_TERMINAL_FIELDS - payload_fields)
    unknown_fields = sorted(payload_fields - CHILD_TERMINAL_FIELDS)
    if missing_fields:
        raise ChildTerminalError(
            f"child terminal missing fields: {','.join(missing_fields)}"
        )
    if unknown_fields:
        raise ChildTerminalError(
            f"child terminal unknown fields: {','.join(unknown_fields)}"
        )
    expected_schema = CHILD_TERMINAL_MODE_SCHEMAS.get(expected_mode)
    if expected_schema is None:
        raise ChildTerminalError("expected child terminal mode is invalid")
    if payload.get("schema_version") != expected_schema:
        raise ChildTerminalError("child terminal schema version is invalid")
    _validate_created_at(payload.get("created_at"))
    if payload.get("authorization_id") != expected_authorization_id:
        raise ChildTerminalError("child terminal authorization identity mismatch")
    if _safe_identifier(payload.get("authorization_id")) != payload.get(
        "authorization_id"
    ):
        raise ChildTerminalError("child terminal authorization identity is malformed")
    if payload.get("marker_path") != str(marker.resolve()):
        raise ChildTerminalError("child terminal marker path mismatch")
    if (
        not isinstance(expected_marker_sha256, str)
        or _SHA256.fullmatch(expected_marker_sha256) is None
    ):
        raise ChildTerminalError("expected marker SHA-256 is malformed")
    marker_sha = payload.get("marker_sha256")
    if not isinstance(marker_sha, str) or _SHA256.fullmatch(marker_sha) is None:
        raise ChildTerminalError("child terminal marker SHA-256 is malformed")
    if marker_sha != expected_marker_sha256:
        raise ChildTerminalError("child terminal marker SHA-256 binding mismatch")
    if _sha256_file(marker) != expected_marker_sha256:
        raise ChildTerminalError("application marker SHA-256 changed after validation")
    if payload.get("mode") != expected_mode:
        raise ChildTerminalError("child terminal mode is invalid")
    if type(payload.get("process_exit_code")) is not int:
        raise ChildTerminalError("child terminal exit code is invalid")
    if int(payload["process_exit_code"]) != int(expected_exit_code):
        raise ChildTerminalError("child terminal exit code disagreement")
    if type(payload.get("success")) is not bool:
        raise ChildTerminalError("child terminal success flag is invalid")
    if payload["success"] is not (expected_exit_code == 0):
        raise ChildTerminalError("child terminal success disagrees with exit code")
    expected_category = (
        "OPERATIONAL_COMMAND_COMPLETE"
        if payload["success"]
        else "OPERATIONAL_COMMAND_BLOCKED"
    )
    if payload.get("terminal_category") != expected_category:
        raise ChildTerminalError("child terminal category disagrees with success")
    _validate_safe_terminal_text(payload.get("status"), field="status", required=True)
    _validate_safe_terminal_text(
        payload.get("first_terminal_cause"),
        field="first_terminal_cause",
        required=not payload["success"],
    )
    _validate_safe_terminal_text(
        payload.get("failure_phase"),
        field="failure_phase",
        required=not payload["success"],
    )
    if payload["success"] and payload.get("failure_phase") is not None:
        raise ChildTerminalError("child terminal success must not carry a failure phase")
    for key in IDENTIFIER_FIELDS:
        value = payload.get(key)
        if value is not None and _safe_identifier(value) != value:
            raise ChildTerminalError(f"child terminal identifier is invalid: {key}")
    if payload.get("marker_consumed") is not True:
        raise ChildTerminalError("child terminal marker consumption evidence is invalid")
    lifecycle_started = payload.get("lifecycle_started")
    if lifecycle_started is not None and type(lifecycle_started) is not bool:
        raise ChildTerminalError("child terminal lifecycle evidence is invalid")
    for key in ("cleanup_complete", "lease_released"):
        value = payload.get(key)
        if value is not None and type(value) is not bool:
            raise ChildTerminalError(f"child terminal boolean is invalid: {key}")
    _validate_active_work(payload.get("active_locked_work"))
    _validate_database_identity(payload.get("database_identity_after"))
    for key in COUNT_FIELDS:
        _validate_optional_count(payload, key)
    report_path = payload.get("terminal_report_path")
    if report_path is not None and (
        not isinstance(report_path, str) or _safe_text(report_path) != report_path
    ):
        raise ChildTerminalError("child terminal report path is invalid")
    report_sha = payload.get("terminal_report_sha256")
    if report_sha is not None and (
        not isinstance(report_sha, str) or _SHA256.fullmatch(report_sha) is None
    ):
        raise ChildTerminalError("child terminal report SHA-256 is invalid")
    if report_sha is not None and report_path is None:
        raise ChildTerminalError("child terminal report SHA-256 lacks a report path")
    truth_status = payload.get("terminal_truth_status")
    if truth_status not in TERMINAL_TRUTH_STATUSES:
        raise ChildTerminalError("child terminal truth status is invalid")
    secondary_truth_error = payload.get("secondary_terminal_truth_error")
    _validate_safe_terminal_text(
        secondary_truth_error,
        field="secondary_terminal_truth_error",
        required=truth_status == "RECONSTRUCTION_FAILED",
    )
    if truth_status != "RECONSTRUCTION_FAILED" and secondary_truth_error is not None:
        raise ChildTerminalError(
            "child terminal secondary truth error lacks reconstruction failure"
        )
    if payload["success"] and truth_status != "NOT_APPLICABLE_SUCCESS":
        raise ChildTerminalError("child terminal success truth status is invalid")
    return dict(payload)


__all__ = [
    "APPLICATION_MARKER_ENV_VAR",
    "APPLICATION_MARKER_SHA256_ENV_VAR",
    "CHILD_TERMINAL_ENV_VAR",
    "CHILD_TERMINAL_FIELDS",
    "CHILD_TERMINAL_FILENAME",
    "CHILD_TERMINAL_SCHEMA_VERSION",
    "CHILD_TERMINAL_MODE_SCHEMAS",
    "STANDARD_FOUR_HOUR_CHILD_TERMINAL_SCHEMA_VERSION",
    "TERMINAL_TRUTH_STATUSES",
    "ChildTerminalBinding",
    "ChildTerminalError",
    "build_child_terminal_envelope",
    "read_child_terminal_envelope",
    "resolve_child_terminal_binding",
    "write_child_terminal_envelope",
]
