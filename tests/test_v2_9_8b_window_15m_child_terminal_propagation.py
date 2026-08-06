"""Focused Checkpoint 1 proof for child-to-wrapper terminal propagation."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from unittest import mock

import pytest

from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.window_15m_child_terminal import (
    CHILD_TERMINAL_ENV_VAR,
    ChildTerminalError,
    read_child_terminal_envelope,
    resolve_child_terminal_binding,
    write_child_terminal_envelope,
)


def _binding_env(root: Path) -> tuple[dict[str, str], Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    marker = root / "application-marker.json"
    terminal = root / "child-terminal.json"
    marker.write_text(
        json.dumps({"authorization_id": "AUTH_TEST"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = root / "git-provenance-manifest.json"
    manifest.write_text(
        json.dumps({"authorization_id": "AUTH_TEST"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    env = {
        "PRINTER_V1_GIT_PROVENANCE_MANIFEST_PATH": str(manifest.resolve()),
        "PRINTER_V1_GIT_PROVENANCE_MANIFEST_SHA256": hashlib.sha256(
            manifest.read_bytes()
        ).hexdigest(),
        "PRINTER_V1_APPLICATION_MARKER_PATH": str(marker.resolve()),
        "PRINTER_V1_APPLICATION_MARKER_SHA256": hashlib.sha256(
            marker.read_bytes()
        ).hexdigest(),
        CHILD_TERMINAL_ENV_VAR: str(terminal.resolve()),
    }
    return env, marker, terminal


def test_child_failure_writes_structured_terminal_after_handled_exception():
    with tempfile.TemporaryDirectory() as directory:
        env, marker, terminal = _binding_env(Path(directory))
        stderr = io.StringIO()
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
                side_effect=command.OperationalMemoryFactoryError(
                    "PRE_HOLDER_TEST_BLOCK"
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
            expected_marker_sha256=hashlib.sha256(
                marker.read_bytes()
            ).hexdigest(),
            expected_exit_code=1,
        )
        assert payload["success"] is False
        assert payload["terminal_category"] == "OPERATIONAL_COMMAND_BLOCKED"
        assert payload["first_terminal_cause"] == (
            "OperationalMemoryFactoryError:PRE_HOLDER_TEST_BLOCK"
        )
        assert payload["failure_phase"] == "COMMAND_BOOTSTRAP_OR_PREFLIGHT"


def test_child_success_writes_structured_terminal():
    with tempfile.TemporaryDirectory() as directory:
        env, marker, terminal = _binding_env(Path(directory))
        stdout = io.StringIO()
        result = {
            "status": "V2_9_8_OPERATIONAL_COMPLETE",
            "execution_id": "exec-a",
            "campaign_id": "campaign-a",
            "run_id": "run-a",
            "cycle_id": "cycle-a",
            "cleanup_complete": True,
            "lease_released": True,
            "active_locked_work": {"scheduler_locked": 0},
            "source_calls": 10,
            "scheduler_runtime_calls": 2,
            "database_writes": 20,
        }
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(
                command,
                "_resolve_git_provenance_authorization",
                return_value=object(),
            ),
            mock.patch.object(command, "run_operational_campaign", return_value=result),
            contextlib.redirect_stdout(stdout),
        ):
            code = command.main(["run", "--operator-approved"])
        assert code == 0
        payload = read_child_terminal_envelope(
            terminal,
            expected_authorization_id="AUTH_TEST",
            expected_marker_path=marker,
            expected_marker_sha256=hashlib.sha256(
                marker.read_bytes()
            ).hexdigest(),
            expected_exit_code=0,
        )
        assert payload["success"] is True
        assert payload["execution_id"] == "exec-a"
        assert payload["cleanup_complete"] is True


def test_unsafe_terminal_cause_is_redacted_not_projected():
    with tempfile.TemporaryDirectory() as directory:
        env, marker, terminal = _binding_env(Path(directory))
        binding = resolve_child_terminal_binding(env)
        write_child_terminal_envelope(
            binding=binding,
            source={
                "status": "OPERATIONAL_COMMAND_BLOCKED",
                "error_type": "RuntimeError",
                "error_message": "https://secret.example/?api_key=do-not-leak",
            },
            mode="run",
            exit_code=1,
            success=False,
        )
        text = terminal.read_text(encoding="utf-8")
        assert "secret.example" not in text
        assert "api_key" not in text
        assert "REDACTED_UNSAFE_TERMINAL_DETAIL" in text


def test_terminal_binding_must_be_exact_marker_sibling():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        env, _, _ = _binding_env(root / "application")
        env[CHILD_TERMINAL_ENV_VAR] = str((root / "foreign/child-terminal.json").resolve())
        with pytest.raises(ChildTerminalError, match="exact sibling"):
            resolve_child_terminal_binding(env)


def test_terminal_reader_rejects_exit_code_disagreement():
    with tempfile.TemporaryDirectory() as directory:
        env, marker, terminal = _binding_env(Path(directory))
        binding = resolve_child_terminal_binding(env)
        write_child_terminal_envelope(
            binding=binding,
            source={"status": "OK"},
            mode="run",
            exit_code=0,
            success=True,
        )
        with pytest.raises(ChildTerminalError, match="exit code"):
            read_child_terminal_envelope(
                terminal,
                expected_authorization_id="AUTH_TEST",
                expected_marker_path=marker,
                expected_marker_sha256=hashlib.sha256(
                    marker.read_bytes()
                ).hexdigest(),
                expected_exit_code=1,
            )



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
                expected_marker_sha256=hashlib.sha256(
                    marker.read_bytes()
                ).hexdigest(),
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
                expected_marker_sha256=hashlib.sha256(
                    marker.read_bytes()
                ).hexdigest(),
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
                expected_marker_sha256=hashlib.sha256(
                    marker.read_bytes()
                ).hexdigest(),
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
                expected_marker_sha256=hashlib.sha256(
                    marker.read_bytes()
                ).hexdigest(),
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
                expected_marker_sha256=hashlib.sha256(
                    marker.read_bytes()
                ).hexdigest(),
                expected_exit_code=1,
            )



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
            expected_marker_sha256=hashlib.sha256(
                marker.read_bytes()
            ).hexdigest(),
            expected_exit_code=1,
        )
        assert payload["first_terminal_cause"] == (
            "OperationalMemoryFactoryError:PROVENANCE_BINDING_TEST_BLOCK"
        )
        assert payload["failure_phase"] == "COMMAND_BOOTSTRAP_OR_PREFLIGHT"
        assert payload["source_calls"] == 0
        assert payload["database_writes"] == 0



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



def test_terminal_truth_reconstruction_failure_preserves_unknown_operational_facts():
    with tempfile.TemporaryDirectory() as directory:
        env, marker, terminal = _binding_env(Path(directory))
        stderr = io.StringIO()

        def fail_after_campaign_identity(**kwargs):
            command._ACTION_RUN_CONTEXT["execution_id"] = "exec-unknown-truth"
            command._ACTION_RUN_CONTEXT["campaign_id"] = "campaign-unknown-truth"
            command._ACTION_RUN_CONTEXT["run_id"] = "run-unknown-truth"
            command._ACTION_RUN_CONTEXT["cycle_id"] = "cycle-unknown-truth"
            raise command.OperationalMemoryFactoryError("PRIMARY_UNKNOWN_TRUTH_BLOCK")

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
                side_effect=RuntimeError("UNKNOWN_OPERATIONAL_TRUTH"),
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
            "OperationalMemoryFactoryError:PRIMARY_UNKNOWN_TRUTH_BLOCK"
        )
        assert payload["terminal_truth_status"] == "RECONSTRUCTION_FAILED"
        assert payload["failure_phase"] == (
            "CAMPAIGN_PHASE_UNKNOWN_TERMINAL_TRUTH_RECONSTRUCTION_FAILED"
        )
        assert payload["lifecycle_started"] is None
        assert payload["active_locked_work"] is None
        assert payload["scheduler_runtime_calls"] is None
        assert payload["source_calls"] is None
        assert payload["database_writes"] is None
        assert payload["database_identity_after"] is None
        assert payload["cleanup_complete"] is None
        assert payload["lease_released"] is None
