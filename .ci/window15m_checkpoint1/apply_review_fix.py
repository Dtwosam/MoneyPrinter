from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


path = Path("src/printer_v1/operator_cli/window_15m_child_terminal.py")
text = path.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''import json\nimport os\nfrom pathlib import Path\nimport re\nimport stat\nfrom typing import Any, Mapping, Sequence\n''',
    '''import json\nimport math\nimport os\nfrom pathlib import Path\nimport re\nimport stat\nfrom typing import Any, Mapping\n''',
    "strict reader imports",
)
text = replace_once(
    text,
    ''')\n\n\nclass ChildTerminalError(RuntimeError):\n''',
    ''')\n\nCHILD_TERMINAL_FIELDS = frozenset(\n    {\n        "schema_version",\n        "created_at",\n        "authorization_id",\n        "marker_path",\n        "marker_sha256",\n        "mode",\n        "status",\n        "success",\n        "process_exit_code",\n        "terminal_category",\n        "first_terminal_cause",\n        "failure_phase",\n        "execution_id",\n        "campaign_id",\n        "run_id",\n        "cycle_id",\n        "supervision_id",\n        "marker_consumed",\n        "lifecycle_started",\n        "cleanup_complete",\n        "lease_released",\n        "active_locked_work",\n        "database_identity_after",\n        "source_calls",\n        "scheduler_runtime_calls",\n        "database_writes",\n        "terminal_report_path",\n        "terminal_report_sha256",\n    }\n)\nDATABASE_IDENTITY_FIELDS = frozenset(\n    {"path", "exists", "sha256", "size", "inode", "mtime_ns"}\n)\nIDENTIFIER_FIELDS = (\n    "execution_id",\n    "campaign_id",\n    "run_id",\n    "cycle_id",\n    "supervision_id",\n)\nCOUNT_FIELDS = ("source_calls", "scheduler_runtime_calls", "database_writes")\n\n\nclass ChildTerminalError(RuntimeError):\n''',
    "strict reader field allowlist",
)
validation_helpers = r'''


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
'''
anchor = '''\ndef read_child_terminal_envelope(\n'''
if text.count(anchor) != 1:
    raise SystemExit("reader definition anchor mismatch")
text = text.replace(anchor, validation_helpers + anchor, 1)
text = replace_once(
    text,
    '''    payload = _load_json_object(candidate, label="child terminal")\n    if payload.get("schema_version") != CHILD_TERMINAL_SCHEMA_VERSION:\n''',
    '''    payload = _load_json_object(candidate, label="child terminal")\n    payload_fields = set(payload)\n    missing_fields = sorted(CHILD_TERMINAL_FIELDS - payload_fields)\n    unknown_fields = sorted(payload_fields - CHILD_TERMINAL_FIELDS)\n    if missing_fields:\n        raise ChildTerminalError(\n            f"child terminal missing fields: {','.join(missing_fields)}"\n        )\n    if unknown_fields:\n        raise ChildTerminalError(\n            f"child terminal unknown fields: {','.join(unknown_fields)}"\n        )\n    if payload.get("schema_version") != CHILD_TERMINAL_SCHEMA_VERSION:\n''',
    "strict field-set validation",
)
text = replace_once(
    text,
    '''    if payload.get("authorization_id") != expected_authorization_id:\n        raise ChildTerminalError("child terminal authorization identity mismatch")\n''',
    '''    _validate_created_at(payload.get("created_at"))\n    if payload.get("authorization_id") != expected_authorization_id:\n        raise ChildTerminalError("child terminal authorization identity mismatch")\n    if _safe_identifier(payload.get("authorization_id")) != payload.get(\n        "authorization_id"\n    ):\n        raise ChildTerminalError("child terminal authorization identity is malformed")\n''',
    "strict created-at authorization validation",
)
text = replace_once(
    text,
    '''    if payload.get("marker_sha256") != _sha256_file(marker):\n        raise ChildTerminalError("child terminal marker SHA-256 mismatch")\n''',
    '''    marker_sha = payload.get("marker_sha256")\n    if not isinstance(marker_sha, str) or _SHA256.fullmatch(marker_sha) is None:\n        raise ChildTerminalError("child terminal marker SHA-256 is malformed")\n    if marker_sha != _sha256_file(marker):\n        raise ChildTerminalError("child terminal marker SHA-256 mismatch")\n''',
    "strict marker digest validation",
)
old_tail = '''    if payload.get("terminal_category") not in {\n        "OPERATIONAL_COMMAND_COMPLETE",\n        "OPERATIONAL_COMMAND_BLOCKED",\n    }:\n        raise ChildTerminalError("child terminal category is invalid")\n    for key in ("status", "first_terminal_cause", "failure_phase"):\n        value = payload.get(key)\n        if value is not None and (not isinstance(value, str) or len(value) > MAX_TEXT_LENGTH + 20):\n            raise ChildTerminalError(f"child terminal field is invalid: {key}")\n    active = payload.get("active_locked_work")\n    if not isinstance(active, Mapping) or len(active) > MAX_MAPPING_ITEMS:\n        raise ChildTerminalError("child terminal active work evidence is invalid")\n    return dict(payload)\n'''
new_tail = '''    expected_category = (\n        "OPERATIONAL_COMMAND_COMPLETE"\n        if payload["success"]\n        else "OPERATIONAL_COMMAND_BLOCKED"\n    )\n    if payload.get("terminal_category") != expected_category:\n        raise ChildTerminalError("child terminal category disagrees with success")\n    _validate_safe_terminal_text(payload.get("status"), field="status", required=True)\n    _validate_safe_terminal_text(\n        payload.get("first_terminal_cause"),\n        field="first_terminal_cause",\n        required=not payload["success"],\n    )\n    _validate_safe_terminal_text(\n        payload.get("failure_phase"),\n        field="failure_phase",\n        required=not payload["success"],\n    )\n    if payload["success"] and payload.get("failure_phase") is not None:\n        raise ChildTerminalError("child terminal success must not carry a failure phase")\n    for key in IDENTIFIER_FIELDS:\n        value = payload.get(key)\n        if value is not None and _safe_identifier(value) != value:\n            raise ChildTerminalError(f"child terminal identifier is invalid: {key}")\n    if payload.get("marker_consumed") is not True:\n        raise ChildTerminalError("child terminal marker consumption evidence is invalid")\n    if type(payload.get("lifecycle_started")) is not bool:\n        raise ChildTerminalError("child terminal lifecycle evidence is invalid")\n    for key in ("cleanup_complete", "lease_released"):\n        value = payload.get(key)\n        if value is not None and type(value) is not bool:\n            raise ChildTerminalError(f"child terminal boolean is invalid: {key}")\n    _validate_active_work(payload.get("active_locked_work"))\n    _validate_database_identity(payload.get("database_identity_after"))\n    for key in COUNT_FIELDS:\n        _validate_optional_count(payload, key)\n    report_path = payload.get("terminal_report_path")\n    if report_path is not None and (\n        not isinstance(report_path, str) or _safe_text(report_path) != report_path\n    ):\n        raise ChildTerminalError("child terminal report path is invalid")\n    report_sha = payload.get("terminal_report_sha256")\n    if report_sha is not None and (\n        not isinstance(report_sha, str) or _SHA256.fullmatch(report_sha) is None\n    ):\n        raise ChildTerminalError("child terminal report SHA-256 is invalid")\n    if report_sha is not None and report_path is None:\n        raise ChildTerminalError("child terminal report SHA-256 lacks a report path")\n    return dict(payload)\n'''
text = replace_once(text, old_tail, new_tail, "strict payload value validation")
text = replace_once(
    text,
    '''    "CHILD_TERMINAL_FILENAME",\n    "CHILD_TERMINAL_SCHEMA_VERSION",\n''',
    '''    "CHILD_TERMINAL_FIELDS",\n    "CHILD_TERMINAL_FILENAME",\n    "CHILD_TERMINAL_SCHEMA_VERSION",\n''',
    "strict fields export",
)
path.write_text(text, encoding="utf-8")
print("strict child terminal reader review fix applied")
