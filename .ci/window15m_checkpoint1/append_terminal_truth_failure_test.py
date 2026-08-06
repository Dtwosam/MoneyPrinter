from pathlib import Path

path = Path("tests/test_v2_9_8b_window_15m_child_terminal_propagation.py")
text = path.read_text(encoding="utf-8")
addition = r'''


def test_terminal_truth_reconstruction_failure_preserves_primary_child_cause():
    with tempfile.TemporaryDirectory() as directory:
        env, marker, terminal = _binding_env(Path(directory))
        stderr = io.StringIO()

        def fail_after_campaign_identity(**kwargs):
            command._ACTION_RUN_CONTEXT["execution_id"] = "exec-truth-failure"
            command._ACTION_RUN_CONTEXT["campaign_id"] = "campaign-truth-failure"
            command._ACTION_RUN_CONTEXT["run_id"] = "run-truth-failure"
            command._ACTION_RUN_CONTEXT["cycle_id"] = "cycle-truth-failure"
            raise command.OperationalMemoryFactoryError("PRIMARY_CAMPAIGN_BLOCK")

        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(
                command,
                "_resolve_git_provenance_authorization",
                return_value=object(),
            ),
            mock.patch.object(
                command,
                "run_operational_campaign",
                side_effect=fail_after_campaign_identity,
            ),
            mock.patch(
                "printer_v1.operator_cli.action_local_terminal_truth."
                "build_action_local_terminal_truth",
                side_effect=RuntimeError("TERMINAL_TRUTH_RECONSTRUCTION_FAILED"),
            ),
            contextlib.redirect_stderr(stderr),
        ):
            code = command.main(["run", "--operator-approved"])

        assert code == 1
        payload = read_child_terminal_envelope(
            terminal,
            expected_authorization_id="AUTH_TEST",
            expected_marker_path=marker,
            expected_marker_sha256=hashlib.sha256(
                marker.read_bytes()
            ).hexdigest(),
            expected_exit_code=1,
        )
        assert payload["first_terminal_cause"] == (
            "OperationalMemoryFactoryError:PRIMARY_CAMPAIGN_BLOCK"
        )
        assert payload["terminal_truth_status"] == "RECONSTRUCTION_FAILED"
        assert payload["secondary_terminal_truth_error"] == (
            "RuntimeError:TERMINAL_TRUTH_RECONSTRUCTION_FAILED"
        )
        assert payload["source_calls"] is None
        assert payload["database_writes"] is None
        assert payload["cleanup_complete"] is None
'''
path.write_text(text + addition, encoding="utf-8")
print("terminal-truth reconstruction failure regression appended")
