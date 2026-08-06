from pathlib import Path

wrapper_test = Path("tests/test_v2_9_8b_window_15m_one_shot_wrapper.py")
text = wrapper_test.read_text(encoding="utf-8")
anchor = "\ndef _exec_dir_name() -> str:\n"
if anchor not in text:
    raise SystemExit("wrapper test insertion anchor missing")
addition = r'''

    def test_27_child_terminal_binding_is_supplied_and_projected(self):
        calls = []

        def launch(**kwargs):
            calls.append(kwargs)
            terminal_path = Path(
                kwargs["env"]["PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_PATH"]
            )
            marker_path = Path(
                kwargs["env"]["PRINTER_V1_APPLICATION_MARKER_PATH"]
            )
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            payload = {
                "schema_version": "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_V1",
                "authorization_id": marker["authorization_id"],
                "marker_path": str(marker_path.resolve()),
                "marker_sha256": _sha(marker_path),
                "mode": "run",
                "status": "OPERATIONAL_COMMAND_BLOCKED",
                "success": False,
                "process_exit_code": 1,
                "terminal_category": "OPERATIONAL_COMMAND_BLOCKED",
                "first_terminal_cause": "HolderBudgetError:TEST_IDENTITY_BLOCK",
                "failure_phase": "CAMPAIGN_PRE_LIFECYCLE",
                "execution_id": "exec-test",
                "campaign_id": "campaign-test",
                "run_id": "run-test",
                "cycle_id": "cycle-test",
                "supervision_id": "supervision-test",
                "marker_consumed": True,
                "lifecycle_started": False,
                "cleanup_complete": True,
                "lease_released": True,
                "active_locked_work": {"scheduler_locked": 0},
                "database_identity_after": {
                    "path": "/tmp/disposable.sqlite3",
                    "exists": True,
                    "sha256": "a" * 64,
                    "size": 4096,
                    "inode": 1,
                    "mtime_ns": 2,
                },
                "source_calls": 10,
                "scheduler_runtime_calls": 0,
                "database_writes": 12,
                "terminal_report_path": None,
                "terminal_report_sha256": None,
            }
            terminal_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            kwargs["stdout_path"].write_text("", encoding="utf-8")
            kwargs["stderr_path"].write_text(
                "conflicting-stderr-cause-that-must-not-be-parsed\n",
                encoding="utf-8",
            )
            return {"returncode": 1, "pid": 4242}

        result = self.apply(process_launcher=launch)
        self.assertEqual(len(calls), 1)
        self.assertTrue(result["child_terminal_valid"])
        self.assertEqual(
            result["child_first_terminal_cause"],
            "HolderBudgetError:TEST_IDENTITY_BLOCK",
        )
        self.assertNotIn("conflicting-stderr", json.dumps(result))
        self.assertEqual(result["terminal_classification"], "CHILD_EXITED_NONZERO")

    def test_28_missing_child_terminal_is_explicitly_invalid(self):
        def launch(**kwargs):
            kwargs["stdout_path"].write_text("", encoding="utf-8")
            kwargs["stderr_path"].write_text("plain stderr\n", encoding="utf-8")
            return {"returncode": 1, "pid": 4242}

        result = self.apply(process_launcher=launch)
        self.assertFalse(result["child_terminal_valid"])
        self.assertEqual(
            result["terminal_classification"],
            "CHILD_EXITED_NONZERO_TERMINAL_INVALID",
        )
'''
text = text.replace(anchor, addition + anchor, 1)
wrapper_test.write_text(text, encoding="utf-8")

new_test = Path("tests/test_v2_9_8b_window_15m_child_terminal_propagation.py")
new_test.write_text(r'''"""Focused Checkpoint 1 proof for child-to-wrapper terminal propagation."""

from __future__ import annotations

import contextlib
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
    env = {
        "PRINTER_V1_APPLICATION_MARKER_PATH": str(marker.resolve()),
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
                expected_exit_code=1,
            )
''', encoding="utf-8")
print("Checkpoint 1 tests written")
