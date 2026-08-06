from pathlib import Path

wrapper = Path("tests/test_v2_9_8b_window_15m_one_shot_wrapper.py")
text = wrapper.read_text(encoding="utf-8")
old = '''                "schema_version": "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_V1",\n                "authorization_id": marker["authorization_id"],\n'''
new = '''                "schema_version": "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_V1",\n                "created_at": "2026-08-06T15:00:00+00:00",\n                "authorization_id": marker["authorization_id"],\n'''
if text.count(old) != 1:
    raise SystemExit("wrapper manual payload created_at anchor mismatch")
wrapper.write_text(text.replace(old, new, 1), encoding="utf-8")

path = Path("tests/test_v2_9_8b_window_15m_child_terminal_propagation.py")
text = path.read_text(encoding="utf-8")
addition = r'''


def _rewrite_terminal(terminal: Path, mutate):
    payload = json.loads(terminal.read_text(encoding="utf-8"))
    mutate(payload)
    terminal.chmod(0o644)
    terminal.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _valid_terminal(root: Path, *, success: bool = False):
    env, marker, terminal = _binding_env(root)
    binding = resolve_child_terminal_binding(env)
    write_child_terminal_envelope(
        binding=binding,
        source=(
            {"status": "OPERATIONAL_COMMAND_COMPLETE"}
            if success
            else {
                "status": "OPERATIONAL_COMMAND_BLOCKED",
                "error_type": "FixtureError",
                "error_message": "fixture block",
            }
        ),
        mode="run",
        exit_code=0 if success else 1,
        success=success,
    )
    return marker, terminal


def test_reader_rejects_unknown_fields_before_wrapper_projection():
    with tempfile.TemporaryDirectory() as directory:
        marker, terminal = _valid_terminal(Path(directory))
        _rewrite_terminal(
            terminal,
            lambda payload: payload.__setitem__(
                "provider_payload", {"authorization": "Bearer do-not-project"}
            ),
        )
        with pytest.raises(ChildTerminalError, match="unknown fields"):
            read_child_terminal_envelope(
                terminal,
                expected_authorization_id="AUTH_TEST",
                expected_marker_path=marker,
                expected_exit_code=1,
            )


def test_reader_rejects_missing_required_created_at():
    with tempfile.TemporaryDirectory() as directory:
        marker, terminal = _valid_terminal(Path(directory))
        _rewrite_terminal(terminal, lambda payload: payload.pop("created_at"))
        with pytest.raises(ChildTerminalError, match="missing fields"):
            read_child_terminal_envelope(
                terminal,
                expected_authorization_id="AUTH_TEST",
                expected_marker_path=marker,
                expected_exit_code=1,
            )


def test_reader_requires_terminal_category_to_match_success():
    with tempfile.TemporaryDirectory() as directory:
        marker, terminal = _valid_terminal(Path(directory), success=True)
        _rewrite_terminal(
            terminal,
            lambda payload: payload.__setitem__(
                "terminal_category", "OPERATIONAL_COMMAND_BLOCKED"
            ),
        )
        with pytest.raises(ChildTerminalError, match="category disagrees"):
            read_child_terminal_envelope(
                terminal,
                expected_authorization_id="AUTH_TEST",
                expected_marker_path=marker,
                expected_exit_code=0,
            )


def test_reader_rejects_unsafe_nested_active_work_text():
    with tempfile.TemporaryDirectory() as directory:
        marker, terminal = _valid_terminal(Path(directory))
        _rewrite_terminal(
            terminal,
            lambda payload: payload.__setitem__(
                "active_locked_work",
                {"diagnostic": "https://secret.invalid/?api_key=leak"},
            ),
        )
        with pytest.raises(ChildTerminalError, match="active work evidence"):
            read_child_terminal_envelope(
                terminal,
                expected_authorization_id="AUTH_TEST",
                expected_marker_path=marker,
                expected_exit_code=1,
            )


def test_reader_rejects_invalid_database_identity_shape():
    with tempfile.TemporaryDirectory() as directory:
        marker, terminal = _valid_terminal(Path(directory))
        _rewrite_terminal(
            terminal,
            lambda payload: payload.__setitem__(
                "database_identity_after", {"path": "/tmp/db", "payload": "extra"}
            ),
        )
        with pytest.raises(ChildTerminalError, match="database identity"):
            read_child_terminal_envelope(
                terminal,
                expected_authorization_id="AUTH_TEST",
                expected_marker_path=marker,
                expected_exit_code=1,
            )
'''
path.write_text(text + addition, encoding="utf-8")
print("independent review regressions appended")
