from pathlib import Path

path = Path("tests/test_v2_9_8b_window_15m_child_terminal_propagation.py")
text = path.read_text(encoding="utf-8")
old_import = "import contextlib\nimport io\n"
new_import = "import contextlib\nimport hashlib\nimport io\n"
if text.count(old_import) != 1:
    raise SystemExit("child terminal test hashlib import anchor mismatch")
text = text.replace(old_import, new_import, 1)
old_env = '''    env = {\n        "PRINTER_V1_APPLICATION_MARKER_PATH": str(marker.resolve()),\n        CHILD_TERMINAL_ENV_VAR: str(terminal.resolve()),\n    }\n'''
new_env = '''    env = {\n        "PRINTER_V1_APPLICATION_MARKER_PATH": str(marker.resolve()),\n        "PRINTER_V1_APPLICATION_MARKER_SHA256": hashlib.sha256(\n            marker.read_bytes()\n        ).hexdigest(),\n        CHILD_TERMINAL_ENV_VAR: str(terminal.resolve()),\n    }\n'''
if text.count(old_env) != 1:
    raise SystemExit("child terminal test marker environment anchor mismatch")
text = text.replace(old_env, new_env, 1)
needle = '''            expected_marker_path=marker,\n            expected_exit_code='''
replacement = '''            expected_marker_path=marker,\n            expected_marker_sha256=hashlib.sha256(\n                marker.read_bytes()\n            ).hexdigest(),\n            expected_exit_code='''
count = text.count(needle)
if count < 5:
    raise SystemExit(f"expected multiple reader call anchors, found {count}")
text = text.replace(needle, replacement)
addition = r'''


def test_child_binding_rejects_marker_drift_from_wrapper_validated_sha():
    with tempfile.TemporaryDirectory() as directory:
        env, marker, _ = _binding_env(Path(directory))
        marker.chmod(0o644)
        marker.write_text(
            json.dumps(
                {
                    "authorization_id": "AUTH_TEST",
                    "post_validation_drift": True,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        with pytest.raises(ChildTerminalError, match="marker SHA-256 mismatch"):
            resolve_child_terminal_binding(env)
'''
path.write_text(text + addition, encoding="utf-8")
print(
    f"marker SHA binding regression appended; patched {count} reader calls"
)
