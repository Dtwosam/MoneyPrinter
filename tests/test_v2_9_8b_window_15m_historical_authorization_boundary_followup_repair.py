"""Focused disposable proofs for preparation-boundary and blocker-preservation repair.

Uses temporary Git repositories and application roots only. Never mutates the
authoritative database or runs the live one-shot path.
"""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from printer_v1.operator_cli.git_provenance_authorization_manifest import (
    GitProvenanceAuthorizationError,
)
from printer_v1.operator_cli.window_15m_authorization_preparation import (
    AuthorizationPreparationError,
    prepare_git_provenance_authorization_parity,
)
from printer_v1.operator_cli import window_15m_one_shot_wrapper as wrapper

from tests.test_v2_9_8b_window_15m_historical_authorization_evidence_contract import (
    CURRENT_AUTH,
    HistoricalContractFixture,
)


class PreparationTempBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fx = HistoricalContractFixture(prior_ids=[], multi_file_prior=False)

    def tearDown(self):
        self.fx.close()

    def test_01_temp_parent_inside_repository_blocks_before_creation(self):
        inside = self.fx.repo / "nested-temp-parent"
        inside.mkdir()
        with self.assertRaises(AuthorizationPreparationError) as ctx:
            prepare_git_provenance_authorization_parity(
                repository_root=self.fx.repo,
                authorization_file=self.fx.authorization_path,
                authorization_sha256=self.fx.authorization_sha256,
                created_at="2026-08-06T12:00:00+00:00",
                application_root=self.fx.app,
                temporary_parent=inside,
            )
        self.assertIn("outside the repository", str(ctx.exception))
        # Parent was not used to create a prep directory with contents.
        self.assertEqual(list(inside.iterdir()), [])

    def test_02_temp_parent_equal_to_application_root_blocks(self):
        with self.assertRaises(AuthorizationPreparationError) as ctx:
            prepare_git_provenance_authorization_parity(
                repository_root=self.fx.repo,
                authorization_file=self.fx.authorization_path,
                authorization_sha256=self.fx.authorization_sha256,
                created_at="2026-08-06T12:00:00+00:00",
                application_root=self.fx.app,
                temporary_parent=self.fx.app,
            )
        self.assertIn("APPLICATION_ROOT", str(ctx.exception))

    def test_03_temp_parent_inside_application_root_blocks(self):
        nested = self.fx.app / "nested-prep"
        nested.mkdir(parents=True)
        with self.assertRaises(AuthorizationPreparationError) as ctx:
            prepare_git_provenance_authorization_parity(
                repository_root=self.fx.repo,
                authorization_file=self.fx.authorization_path,
                authorization_sha256=self.fx.authorization_sha256,
                created_at="2026-08-06T12:00:00+00:00",
                application_root=self.fx.app,
                temporary_parent=nested,
            )
        self.assertIn("APPLICATION_ROOT", str(ctx.exception))

    def test_04_symlink_temporary_parent_blocks(self):
        real = self.fx.root / "real-temp-parent"
        real.mkdir()
        link = self.fx.root / "link-temp-parent"
        os.symlink(real, link)
        with self.assertRaises(AuthorizationPreparationError) as ctx:
            prepare_git_provenance_authorization_parity(
                repository_root=self.fx.repo,
                authorization_file=self.fx.authorization_path,
                authorization_sha256=self.fx.authorization_sha256,
                created_at="2026-08-06T12:00:00+00:00",
                application_root=self.fx.app,
                temporary_parent=link,
            )
        self.assertIn("symlink", str(ctx.exception).lower())

    def test_05_valid_external_temp_parent_passes_and_is_removed(self):
        parent = self.fx.root / "safe-prep-parent"
        parent.mkdir()
        before = set(parent.iterdir())
        summary = prepare_git_provenance_authorization_parity(
            repository_root=self.fx.repo,
            authorization_file=self.fx.authorization_path,
            authorization_sha256=self.fx.authorization_sha256,
            created_at="2026-08-06T12:00:00+00:00",
            application_root=self.fx.app,
            temporary_parent=parent,
        )
        self.assertTrue(summary["inventory_pre_marker_parity_PASS"])
        self.assertFalse(summary["marker_created"])
        self.assertFalse(summary["canonical_application_directory_created"])
        self.assertFalse(summary["child_launched"])
        self.assertFalse((self.fx.app / CURRENT_AUTH).exists())
        after = set(parent.iterdir())
        self.assertEqual(before, after)

    def test_06_preparation_creates_no_marker_canonical_or_child(self):
        parent = self.fx.root / "safe-prep-parent-2"
        parent.mkdir()
        prepare_git_provenance_authorization_parity(
            repository_root=self.fx.repo,
            authorization_file=self.fx.authorization_path,
            authorization_sha256=self.fx.authorization_sha256,
            created_at="2026-08-06T12:00:00+00:00",
            application_root=self.fx.app,
            temporary_parent=parent,
        )
        self.assertFalse((self.fx.app / CURRENT_AUTH / "application-marker.json").exists())
        self.assertFalse((self.fx.app / CURRENT_AUTH).exists())
        self.assertEqual(list(parent.iterdir()), [])


class BlockerPreservationTests(unittest.TestCase):
    def setUp(self):
        self.fx = HistoricalContractFixture(prior_ids=[], multi_file_prior=False)

    def tearDown(self):
        self.fx.close()

    def _apply(self, **overrides):
        params = dict(
            authorization_file=self.fx.authorization_path,
            authorization_sha256=self.fx.authorization_sha256,
            operator_approved=True,
            repository_root=self.fx.repo,
            application_root=self.fx.app,
            python_executable=self.fx.venv_python,
            migration_ledger_guard=lambda **kwargs: mock.Mock(),
            process_launcher=lambda **kwargs: {"returncode": 0, "pid": 1},
            created_at="2026-08-06T12:00:00+00:00",
            consumed_at="2026-08-06T12:01:00+00:00",
        )
        params.update(overrides)
        with mock.patch(
            "printer_v1.operator_cli.window_15m_one_shot_wrapper.validate_window_15m_source_configuration"
        ), mock.patch(
            "printer_v1.operator_cli.window_15m_concrete_composition.run_window_15m_concrete_composition_preflight"
        ):
            return wrapper.apply_authorization_once(**params)

    def test_07_pre_marker_failure_successful_cleanup_preserves_original(self):
        (self.fx.repo / "extra.txt").write_text("extra\n", encoding="utf-8")
        with self.assertRaises(GitProvenanceAuthorizationError) as ctx:
            self._apply()
        exc = ctx.exception
        self.assertEqual(type(exc).__name__, "GitProvenanceAuthorizationError")
        self.assertIn("unexpected untracked", str(exc))
        self.assertIsNone(getattr(exc, "secondary_staging_cleanup_blocker", None))
        self.assertFalse((self.fx.app / CURRENT_AUTH / "application-marker.json").exists())

    def test_08_cleanup_failure_preserves_original_and_secondary_field(self):
        def validator(**kwargs):
            staging = Path(kwargs["manifest_path"]).parent
            (staging / "stray.txt").write_text("keep\n", encoding="utf-8")
            raise GitProvenanceAuthorizationError("forced pre-marker block")

        with self.assertRaises(GitProvenanceAuthorizationError) as ctx:
            self._apply(pre_marker_validator=validator)
        exc = ctx.exception
        self.assertEqual(type(exc).__name__, "GitProvenanceAuthorizationError")
        self.assertEqual(str(exc), "forced pre-marker block")
        secondary = getattr(exc, "secondary_staging_cleanup_blocker", None)
        self.assertIsNotNone(secondary)
        self.assertIn("unexpected staging entries", secondary)

    def test_09_wrapper_cli_json_exposes_original_error_type(self):
        def boom(**kwargs):
            err = GitProvenanceAuthorizationError("cli-block")
            err.secondary_staging_cleanup_blocker = "staging kept"
            raise err

        with mock.patch.object(wrapper, "apply_authorization_once", side_effect=boom):
            stderr = io.StringIO()
            with mock.patch("sys.stderr", stderr):
                code = wrapper.main(
                    [
                        "--authorization-file",
                        str(self.fx.authorization_path),
                        "--authorization-sha256",
                        self.fx.authorization_sha256,
                        "--operator-approved",
                    ]
                )
        self.assertEqual(code, 2)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error_type"], "GitProvenanceAuthorizationError")
        self.assertEqual(payload["error_message"], "cli-block")
        self.assertEqual(payload["secondary_staging_cleanup_blocker"], "staging kept")


class CanonicalResidueCleanupTests(unittest.TestCase):
    def setUp(self):
        self.fx = HistoricalContractFixture(prior_ids=[], multi_file_prior=False)

    def tearDown(self):
        self.fx.close()

    def _apply(self, **overrides):
        params = dict(
            authorization_file=self.fx.authorization_path,
            authorization_sha256=self.fx.authorization_sha256,
            operator_approved=True,
            repository_root=self.fx.repo,
            application_root=self.fx.app,
            python_executable=self.fx.venv_python,
            migration_ledger_guard=lambda **kwargs: mock.Mock(),
            process_launcher=lambda **kwargs: {"returncode": 0, "pid": 1},
            created_at="2026-08-06T12:00:00+00:00",
            consumed_at="2026-08-06T12:01:00+00:00",
        )
        params.update(overrides)
        with mock.patch(
            "printer_v1.operator_cli.window_15m_one_shot_wrapper.validate_window_15m_source_configuration"
        ), mock.patch(
            "printer_v1.operator_cli.window_15m_concrete_composition.run_window_15m_concrete_composition_preflight"
        ):
            return wrapper.apply_authorization_once(**params)

    def test_10_promotion_failure_removes_invocation_empty_canonical(self):
        real_replace = os.replace

        def failing_replace(src, dst):
            # Simulate failure after canonical mkdir, before publication.
            raise OSError("forced promotion failure")

        with mock.patch("os.replace", side_effect=failing_replace):
            with self.assertRaises(OSError) as ctx:
                self._apply()
        self.assertEqual(str(ctx.exception), "forced promotion failure")
        canonical = self.fx.app / CURRENT_AUTH
        self.assertFalse(canonical.exists())
        self.assertFalse((canonical / "application-marker.json").exists())

    def test_11_preexisting_or_nonempty_canonical_never_deleted(self):
        # Pre-existing blocks before staging; directory remains.
        pre = self.fx.app / CURRENT_AUTH
        pre.mkdir(parents=True)
        (pre / "keep.txt").write_text("keep\n", encoding="utf-8")
        with self.assertRaises(wrapper.OneShotWrapperError):
            self._apply()
        self.assertTrue(pre.is_dir())
        self.assertTrue((pre / "keep.txt").is_file())

        # Direct unit proof for non-empty refusal.
        secondary = wrapper._cleanup_invocation_empty_canonical(pre)
        self.assertIsNotNone(secondary)
        self.assertIn("not empty", secondary)
        self.assertTrue((pre / "keep.txt").is_file())

    def test_12_marker_remains_consumption_boundary(self):
        result = self._apply()
        marker = self.fx.app / CURRENT_AUTH / "application-marker.json"
        self.assertTrue(marker.is_file())
        self.assertTrue(result.get("authorization_id") == CURRENT_AUTH or marker.exists())
        with self.assertRaises(wrapper.OneShotWrapperError):
            self._apply()


class CleanupUnitTests(unittest.TestCase):
    def test_empty_canonical_rmdir_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "auth"
            canonical.mkdir()
            self.assertIsNone(wrapper._cleanup_invocation_empty_canonical(canonical))
            self.assertFalse(canonical.exists())

    def test_marker_bearing_canonical_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            canonical = Path(tmp) / "auth"
            canonical.mkdir()
            (canonical / "application-marker.json").write_text("{}\n", encoding="utf-8")
            secondary = wrapper._cleanup_invocation_empty_canonical(canonical)
            self.assertIsNotNone(secondary)
            self.assertIn("marker", secondary)
            self.assertTrue(canonical.is_dir())


if __name__ == "__main__":
    unittest.main()
