from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


module = Path("src/printer_v1/operator_cli/window_15m_child_terminal.py")
text = module.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''APPLICATION_MARKER_ENV_VAR = "PRINTER_V1_APPLICATION_MARKER_PATH"\nCHILD_TERMINAL_FILENAME = "child-terminal.json"\n''',
    '''APPLICATION_MARKER_ENV_VAR = "PRINTER_V1_APPLICATION_MARKER_PATH"\nAPPLICATION_MARKER_SHA256_ENV_VAR = (\n    "PRINTER_V1_APPLICATION_MARKER_SHA256"\n)\nCHILD_TERMINAL_FILENAME = "child-terminal.json"\n''',
    "marker SHA environment constant",
)
text = replace_once(
    text,
    '''    terminal_raw = env.get(CHILD_TERMINAL_ENV_VAR)\n    marker_raw = env.get(APPLICATION_MARKER_ENV_VAR)\n    if not terminal_raw:\n''',
    '''    terminal_raw = env.get(CHILD_TERMINAL_ENV_VAR)\n    marker_raw = env.get(APPLICATION_MARKER_ENV_VAR)\n    marker_sha_raw = env.get(APPLICATION_MARKER_SHA256_ENV_VAR)\n    if not terminal_raw:\n''',
    "marker SHA environment read",
)
text = replace_once(
    text,
    '''    if not marker_raw:\n        raise ChildTerminalError("application marker binding is missing")\n''',
    '''    if not marker_raw:\n        raise ChildTerminalError("application marker binding is missing")\n    if not isinstance(marker_sha_raw, str) or _SHA256.fullmatch(marker_sha_raw) is None:\n        raise ChildTerminalError("application marker SHA-256 binding is malformed")\n''',
    "marker SHA environment validation",
)
text = replace_once(
    text,
    '''    marker = _load_json_object(marker_path, label="application marker")\n    authorization_id = _safe_identifier(marker.get("authorization_id"))\n''',
    '''    actual_marker_sha256 = _sha256_file(marker_path)\n    if actual_marker_sha256 != marker_sha_raw:\n        raise ChildTerminalError("application marker SHA-256 mismatch")\n    marker = _load_json_object(marker_path, label="application marker")\n    authorization_id = _safe_identifier(marker.get("authorization_id"))\n''',
    "marker SHA exact binding",
)
text = replace_once(
    text,
    '''        marker_sha256=_sha256_file(marker_path),\n''',
    '''        marker_sha256=marker_sha_raw,\n''',
    "binding marker SHA source",
)
text = replace_once(
    text,
    '''    expected_marker_path: str | Path,\n    expected_exit_code: int,\n''',
    '''    expected_marker_path: str | Path,\n    expected_marker_sha256: str,\n    expected_exit_code: int,\n''',
    "reader expected marker SHA argument",
)
text = replace_once(
    text,
    '''    marker_sha = payload.get("marker_sha256")\n    if not isinstance(marker_sha, str) or _SHA256.fullmatch(marker_sha) is None:\n        raise ChildTerminalError("child terminal marker SHA-256 is malformed")\n    if marker_sha != _sha256_file(marker):\n        raise ChildTerminalError("child terminal marker SHA-256 mismatch")\n''',
    '''    if (\n        not isinstance(expected_marker_sha256, str)\n        or _SHA256.fullmatch(expected_marker_sha256) is None\n    ):\n        raise ChildTerminalError("expected marker SHA-256 is malformed")\n    marker_sha = payload.get("marker_sha256")\n    if not isinstance(marker_sha, str) or _SHA256.fullmatch(marker_sha) is None:\n        raise ChildTerminalError("child terminal marker SHA-256 is malformed")\n    if marker_sha != expected_marker_sha256:\n        raise ChildTerminalError("child terminal marker SHA-256 binding mismatch")\n    if _sha256_file(marker) != expected_marker_sha256:\n        raise ChildTerminalError("application marker SHA-256 changed after validation")\n''',
    "reader marker SHA binding validation",
)
text = replace_once(
    text,
    '''    "APPLICATION_MARKER_ENV_VAR",\n''',
    '''    "APPLICATION_MARKER_ENV_VAR",\n    "APPLICATION_MARKER_SHA256_ENV_VAR",\n''',
    "marker SHA constant export",
)
module.write_text(text, encoding="utf-8")

wrapper = Path("src/printer_v1/operator_cli/window_15m_one_shot_wrapper.py")
text = wrapper.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''                expected_authorization_id=authorization_id,\n                expected_marker_path=marker_path,\n                expected_exit_code=int(returncode),\n''',
    '''                expected_authorization_id=authorization_id,\n                expected_marker_path=marker_path,\n                expected_marker_sha256=marker_sha256,\n                expected_exit_code=int(returncode),\n''',
    "wrapper exact marker SHA reader binding",
)
wrapper.write_text(text, encoding="utf-8")
print("wrapper-validated marker SHA binding repaired")
