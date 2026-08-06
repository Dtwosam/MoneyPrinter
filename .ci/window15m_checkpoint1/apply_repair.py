from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


module = Path("src/printer_v1/operator_cli/window_15m_child_terminal.py")
module.write_text(r'''"""Bounded child-owned terminal evidence for ordinary WINDOW_15M runs.

The operational child writes exactly one source-safe JSON envelope. The external
one-shot wrapper validates and projects it after process exit. stderr remains
immutable debugging evidence and is never parsed as terminal truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence


CHILD_TERMINAL_SCHEMA_VERSION = "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_V1"
CHILD_TERMINAL_ENV_VAR = "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_PATH"
APPLICATION_MARKER_ENV_VAR = "PRINTER_V1_APPLICATION_MARKER_PATH"
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
    if not terminal_raw:
        raise ChildTerminalError("ordinary run child terminal binding is missing")
    if not marker_raw:
        raise ChildTerminalError("application marker binding is missing")
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
    marker = _load_json_object(marker_path, label="application marker")
    authorization_id = _safe_identifier(marker.get("authorization_id"))
    if authorization_id is None:
        raise ChildTerminalError("application marker authorization_id is malformed")
    return ChildTerminalBinding(
        terminal_path=terminal_path,
        marker_path=marker_path,
        authorization_id=authorization_id,
        marker_sha256=_sha256_file(marker_path),
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
    if mode != "run":
        raise ChildTerminalError("child terminal is valid only for ordinary run")
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
    active = _bounded_mapping(_find_key(source, "active_locked_work"))
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
    payload = {
        "schema_version": CHILD_TERMINAL_SCHEMA_VERSION,
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
        "lifecycle_started": bool(_find_key(source, "lifecycle_started")) or bool(
            _find_key(source, "factory_run_id")
        ),
        "cleanup_complete": _find_key(source, "cleanup_complete"),
        "lease_released": _find_key(source, "lease_released"),
        "active_locked_work": active,
        "database_identity_after": db_identity,
        "source_calls": _find_key(source, "source_calls"),
        "scheduler_runtime_calls": _find_key(source, "scheduler_runtime_calls"),
        "database_writes": _find_key(source, "database_writes"),
        "terminal_report_path": report_path,
        "terminal_report_sha256": report_sha,
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


def read_child_terminal_envelope(
    path: str | Path,
    *,
    expected_authorization_id: str,
    expected_marker_path: str | Path,
    expected_exit_code: int,
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
    if payload.get("schema_version") != CHILD_TERMINAL_SCHEMA_VERSION:
        raise ChildTerminalError("child terminal schema version is invalid")
    if payload.get("authorization_id") != expected_authorization_id:
        raise ChildTerminalError("child terminal authorization identity mismatch")
    if payload.get("marker_path") != str(marker.resolve()):
        raise ChildTerminalError("child terminal marker path mismatch")
    if payload.get("marker_sha256") != _sha256_file(marker):
        raise ChildTerminalError("child terminal marker SHA-256 mismatch")
    if payload.get("mode") != "run":
        raise ChildTerminalError("child terminal mode is invalid")
    if type(payload.get("process_exit_code")) is not int:
        raise ChildTerminalError("child terminal exit code is invalid")
    if int(payload["process_exit_code"]) != int(expected_exit_code):
        raise ChildTerminalError("child terminal exit code disagreement")
    if type(payload.get("success")) is not bool:
        raise ChildTerminalError("child terminal success flag is invalid")
    if payload["success"] is not (expected_exit_code == 0):
        raise ChildTerminalError("child terminal success disagrees with exit code")
    if payload.get("terminal_category") not in {
        "OPERATIONAL_COMMAND_COMPLETE",
        "OPERATIONAL_COMMAND_BLOCKED",
    }:
        raise ChildTerminalError("child terminal category is invalid")
    for key in ("status", "first_terminal_cause", "failure_phase"):
        value = payload.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH + 20):
            raise ChildTerminalError(f"child terminal field is invalid: {key}")
    active = payload.get("active_locked_work")
    if not isinstance(active, Mapping) or len(active) > MAX_MAPPING_ITEMS:
        raise ChildTerminalError("child terminal active work evidence is invalid")
    return dict(payload)


__all__ = [
    "APPLICATION_MARKER_ENV_VAR",
    "CHILD_TERMINAL_ENV_VAR",
    "CHILD_TERMINAL_FILENAME",
    "CHILD_TERMINAL_SCHEMA_VERSION",
    "ChildTerminalBinding",
    "ChildTerminalError",
    "build_child_terminal_envelope",
    "read_child_terminal_envelope",
    "resolve_child_terminal_binding",
    "write_child_terminal_envelope",
]
''', encoding="utf-8")

wrapper = Path("src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py")
text = wrapper.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''from printer_v1.sources.operational_source_contracts import (\n    SolanaRpcConfigurationError,\n    validate_window_15m_source_configuration,\n)\n''',
    '''from printer_v1.sources.operational_source_contracts import (\n    SolanaRpcConfigurationError,\n    validate_window_15m_source_configuration,\n)\nfrom printer_v1.operator_cli.window_15m_child_terminal import (\n    CHILD_TERMINAL_ENV_VAR,\n    ChildTerminalError,\n    read_child_terminal_envelope,\n)\n''',
    "wrapper child terminal import",
)
text = replace_once(
    text,
    '''    child_env_preview = dict(parent_env)\n    for name in BINDING_ENV_VARS:\n        child_env_preview.pop(name, None)\n''',
    '''    child_env_preview = dict(parent_env)\n    for name in BINDING_ENV_VARS:\n        child_env_preview.pop(name, None)\n    child_env_preview.pop(CHILD_TERMINAL_ENV_VAR, None)\n''',
    "wrapper preview environment",
)
text = replace_once(
    text,
    '''    stderr_path = canonical_dir / "child-stderr.txt"\n\n    marker_created = False\n''',
    '''    stderr_path = canonical_dir / "child-stderr.txt"\n    child_terminal_path = canonical_dir / "child-terminal.json"\n\n    marker_created = False\n''',
    "wrapper terminal path",
)
text = replace_once(
    text,
    '''        child_env = dict(parent)\n        for name in BINDING_ENV_VARS:\n            child_env.pop(name, None)\n        child_env.update(\n''',
    '''        child_env = dict(parent)\n        for name in BINDING_ENV_VARS:\n            child_env.pop(name, None)\n        child_env.pop(CHILD_TERMINAL_ENV_VAR, None)\n        child_env.update(\n''',
    "wrapper child environment cleanup",
)
text = replace_once(
    text,
    '''                BINDING_ENV_VARS[3]: marker_sha256,\n            }\n        )\n        launcher = process_launcher or _default_process_launcher\n''',
    '''                BINDING_ENV_VARS[3]: marker_sha256,\n                CHILD_TERMINAL_ENV_VAR: str(child_terminal_path.resolve()),\n            }\n        )\n        launcher = process_launcher or _default_process_launcher\n''',
    "wrapper child terminal binding",
)
text = replace_once(
    text,
    '''        pid = launched.get("pid")\n        terminal = {\n''',
    '''        pid = launched.get("pid")\n        child_terminal_error = None\n        child_terminal = None\n        try:\n            child_terminal = read_child_terminal_envelope(\n                child_terminal_path,\n                expected_authorization_id=authorization_id,\n                expected_marker_path=marker_path,\n                expected_exit_code=int(returncode),\n            )\n        except ChildTerminalError as terminal_exc:\n            child_terminal_error = f"{type(terminal_exc).__name__}:{terminal_exc}"\n        child_terminal_valid = child_terminal is not None\n        terminal = {\n''',
    "wrapper child terminal read",
)
text = replace_once(
    text,
    '''            "stderr": _file_identity(stderr_path),\n            "automatic_retries": 0,\n''',
    '''            "stderr": _file_identity(stderr_path),\n            "child_terminal": _file_identity(child_terminal_path),\n            "child_terminal_valid": child_terminal_valid,\n            "child_terminal_error": child_terminal_error,\n            "child_terminal_envelope": child_terminal,\n            "child_first_terminal_cause": (\n                None if child_terminal is None\n                else child_terminal.get("first_terminal_cause")\n            ),\n            "child_failure_phase": (\n                None if child_terminal is None\n                else child_terminal.get("failure_phase")\n            ),\n            "child_cleanup_complete": (\n                None if child_terminal is None\n                else child_terminal.get("cleanup_complete")\n            ),\n            "child_lease_released": (\n                None if child_terminal is None\n                else child_terminal.get("lease_released")\n            ),\n            "child_active_locked_work": (\n                {} if child_terminal is None\n                else child_terminal.get("active_locked_work", {})\n            ),\n            "automatic_retries": 0,\n''',
    "wrapper child projection",
)
text = replace_once(
    text,
    '''            "terminal_classification": (\n                "CHILD_EXITED_ZERO" if returncode == 0 else "CHILD_EXITED_NONZERO"\n            ),\n''',
    '''            "terminal_classification": (\n                ("CHILD_EXITED_ZERO" if returncode == 0 else "CHILD_EXITED_NONZERO")\n                if child_terminal_valid\n                else (\n                    "CHILD_EXITED_ZERO_TERMINAL_INVALID"\n                    if returncode == 0\n                    else "CHILD_EXITED_NONZERO_TERMINAL_INVALID"\n                )\n            ),\n''',
    "wrapper terminal classification",
)
text = replace_once(
    text,
    '''        _write_terminal(terminal_path, terminal)\n        _make_read_only(stdout_path)\n        _make_read_only(stderr_path)\n        return terminal\n''',
    '''        _write_terminal(terminal_path, terminal)\n        _make_read_only(stdout_path)\n        _make_read_only(stderr_path)\n        if child_terminal_path.is_file():\n            _make_read_only(child_terminal_path)\n        return terminal\n''',
    "wrapper immutable child terminal",
)
text = replace_once(
    text,
    '''        return 0 if result.get("child_exit_code") == 0 else 1\n''',
    '''        return 0 if (\n            result.get("child_exit_code") == 0\n            and result.get("child_terminal_valid") is True\n            and result.get("terminal_classification") == "CHILD_EXITED_ZERO"\n        ) else 1\n''',
    "wrapper CLI valid zero requirement",
)
wrapper.write_text(text, encoding="utf-8")

command = Path("src/printer_v1/operator_cli/operational_memory_factory_command.py")
text = command.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''    clear_action_local_mutation_recorder()\n    try:\n''',
    '''    clear_action_local_mutation_recorder()\n    from printer_v1.operator_cli.window_15m_child_terminal import (\n        CHILD_TERMINAL_ENV_VAR,\n        resolve_child_terminal_binding,\n        write_child_terminal_envelope,\n    )\n    child_terminal_binding = None\n    try:\n''',
    "child terminal main import",
)
text = replace_once(
    text,
    '''        if args.mode == "run" and git_provenance_authorization is None:\n            raise OperationalMemoryFactoryError(\n                "ordinary run requires external one-shot wrapper authorization"\n            )\n        if args.mode == "preflight-only":\n''',
    '''        if args.mode == "run" and git_provenance_authorization is None:\n            raise OperationalMemoryFactoryError(\n                "ordinary run requires external one-shot wrapper authorization"\n            )\n        if args.mode == "run":\n            child_terminal_binding = resolve_child_terminal_binding(os.environ)\n        elif os.environ.get(CHILD_TERMINAL_ENV_VAR):\n            raise OperationalMemoryFactoryError(\n                "child terminal binding is accepted only for ordinary run"\n            )\n        if args.mode == "preflight-only":\n''',
    "child terminal binding resolution",
)
text = replace_once(
    text,
    '''        print(json.dumps(result, indent=2, sort_keys=True, default=str))\n        return 0\n    except Exception as exc:\n''',
    '''        if args.mode == "run" and child_terminal_binding is not None:\n            write_child_terminal_envelope(\n                binding=child_terminal_binding,\n                source=result,\n                mode="run",\n                exit_code=0,\n                success=True,\n            )\n        print(json.dumps(result, indent=2, sort_keys=True, default=str))\n        return 0\n    except Exception as exc:\n''',
    "child success terminal write",
)
text = replace_once(
    text,
    '''        print(json.dumps(envelope, sort_keys=True, default=str), file=sys.stderr)\n        return 1\n''',
    '''        if args.mode == "run" and child_terminal_binding is not None:\n            try:\n                write_child_terminal_envelope(\n                    binding=child_terminal_binding,\n                    source=envelope,\n                    mode="run",\n                    exit_code=1,\n                    success=False,\n                )\n            except Exception as terminal_exc:\n                envelope["child_terminal_write_status"] = (\n                    f"FAILED:{type(terminal_exc).__name__}"\n                )\n        print(json.dumps(envelope, sort_keys=True, default=str), file=sys.stderr)\n        return 1\n''',
    "child failure terminal write",
)
command.write_text(text, encoding="utf-8")

# Existing wrapper fixtures must emulate the repaired child contract. This is
# test-only behavior and never starts the operational command.
test = Path("tests/test_v2_9_8b_window_15m_one_shot_wrapper.py")
text = test.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''from printer_v1.operator_cli import window_15m_one_shot_wrapper as wrapper\n''',
    '''from printer_v1.operator_cli import window_15m_one_shot_wrapper as wrapper\nfrom printer_v1.operator_cli.window_15m_child_terminal import (\n    resolve_child_terminal_binding,\n    write_child_terminal_envelope,\n)\n''',
    "wrapper test terminal import",
)
text = replace_once(
    text,
    '''            kwargs["stdout_path"].write_text("child stdout\\n", encoding="utf-8")\n            kwargs["stderr_path"].write_text("child stderr\\n", encoding="utf-8")\n            return {"returncode": returncode, "pid": 4242}\n''',
    '''            kwargs["stdout_path"].write_text("child stdout\\n", encoding="utf-8")\n            kwargs["stderr_path"].write_text("child stderr\\n", encoding="utf-8")\n            binding = resolve_child_terminal_binding(kwargs["env"])\n            source = (\n                {"status": "OPERATIONAL_COMMAND_COMPLETE"}\n                if returncode == 0\n                else {\n                    "status": "OPERATIONAL_COMMAND_BLOCKED",\n                    "error_type": "FixtureChildError",\n                    "error_message": "fixture nonzero child",\n                }\n            )\n            write_child_terminal_envelope(\n                binding=binding,\n                source=source,\n                mode="run",\n                exit_code=returncode,\n                success=returncode == 0,\n            )\n            return {"returncode": returncode, "pid": 4242}\n''',
    "wrapper fixture child terminal",
)
test.write_text(text, encoding="utf-8")
print("Checkpoint 1 repair applied")
