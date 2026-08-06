from pathlib import Path

path = Path("tests/test_v2_9_8b_window_15m_child_terminal_propagation.py")
text = path.read_text(encoding="utf-8")
addition = r'''


def test_provenance_validation_failure_writes_structured_child_terminal():
    with tempfile.TemporaryDirectory() as directory:
        env, marker, terminal = _binding_env(Path(directory))
        stderr = io.StringIO()
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(
                command,
                "_resolve_git_provenance_authorization",
                side_effect=command.OperationalMemoryFactoryError(
                    "PROVENANCE_BINDING_TEST_BLOCK"
                ),
            ),
            contextlib.redirect_stderr(stderr),
        ):
            code = command.main(["run", "--operator-approved"])
        assert code == 1
        payload = read_child_terminal_envelope(
            terminal,
            expected_authorization_id="AUTH_TEST",
            expected_marker_path=marker,
            expected_exit_code=1,
        )
        assert payload["first_terminal_cause"] == (
            "OperationalMemoryFactoryError:PROVENANCE_BINDING_TEST_BLOCK"
        )
        assert payload["failure_phase"] == "COMMAND_BOOTSTRAP_OR_PREFLIGHT"
        assert payload["source_calls"] == 0
        assert payload["database_writes"] == 0
'''
path.write_text(text + addition, encoding="utf-8")
print("provenance call-order regression appended")
