"""Focused offline proof for historical reconciliation provenance alignment.

This suite uses disposable repositories only.  It creates no real
authorization or marker, never reads or writes the authoritative database,
and performs no source, Scheduler, or Printer runtime work.
"""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from test_v2_9_8b_four_token_historical_migration_provenance import (
    FourTokenHistoricalMigrationFixture,
)


def _synthetic_package(
    root: Path,
) -> tuple[git_auth.HistoricalReconciliationPackage, Path]:
    target = root / "operator-runs/reconcile/EXEC/evidence.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"evidence\n")
    return (
        git_auth.HistoricalReconciliationPackage(
            package_root="operator-runs/reconcile",
            execution_id="EXEC",
            evidence_class="HISTORICAL_RECONCILIATION_TEST",
            expected_file_count=1,
            expected_inventory_sha256=(
                "5f56d9cc5b7377c82f154c379072d2ad39091faf02061a12a3c28b086fd258a2"
            ),
            execution_directories=("EXEC",),
            files=(
                git_auth.HistoricalReconciliationFile(
                    path="operator-runs/reconcile/EXEC/evidence.json",
                    size=9,
                    sha256=(
                        "bdcf4c994585af6dd6cb1cfbff78bcc73ab27dc30a299db5bb83766ca05b5de4"
                    ),
                ),
            ),
        ),
        target,
    )


class ReconciliationProfileBindingTests(unittest.TestCase):
    """The operational four-token profile owns exact historical packages."""

    def test_operational_profile_binds_pair_ready_reconciliation_package(self) -> None:
        operational = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        packages = getattr(operational, "historical_reconciliation_packages", None)
        self.assertIsNotNone(packages)
        self.assertEqual(len(packages), 3)
        self.assertEqual(
            tuple(item.package_root for item in packages),
            (
                "operator-runs/v2-9-8b-pre-admission-2364-reconciliation",
                "operator-runs/v2-9-8b-historical-orphan-factory-run-reconciliation",
                "operator-runs/v2-9-8b-pair-ready-residual-reconciliation",
            ),
        )
        self.assertEqual(
            tuple(item.execution_id for item in packages),
            (
                "RECONCILE_20260820T174324Z",
                "RECONCILE_20260820T192309Z",
                "RECONCILIATION_20260821T110736Z",
            ),
        )
        self.assertEqual(len({item.evidence_class for item in packages}), 3)

        # Complete-inventory preparation scans the same operator-runs namespace
        # for both four-token profiles, so the proof profile needs the same
        # exact historical reconciliation declarations.  Otherwise these
        # legitimate bytes remain unexplained even though its current package
        # authority is distinct.
        self.assertEqual(
            git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
            .historical_reconciliation_packages,
            packages,
        )

        for profile in (
            git_auth.ORDINARY_AUTHORIZATION_PROFILE,
            git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        ):
            with self.subTest(mode=profile.command_mode):
                self.assertEqual(
                    getattr(profile, "historical_reconciliation_packages", None), ()
                )

    def test_production_packages_bind_all_twelve_real_member_identities(self) -> None:
        packages = (
            git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
            .historical_reconciliation_packages
        )
        self.assertEqual(
            tuple(
                (
                    package.evidence_class,
                    package.expected_file_count,
                    package.expected_inventory_sha256,
                    tuple((item.path, item.size, item.sha256) for item in package.files),
                )
                for package in packages
            ),
            (
                (
                    "HISTORICAL_PRE_ADMISSION_2364_RECONCILIATION_EVIDENCE",
                    3,
                    "f3b030d9b396380efd87310e4b1e72161271bbd0869ed4fae2b533d4e338bfcd",
                    (
                        (
                            "operator-runs/v2-9-8b-pre-admission-2364-reconciliation/RECONCILE_20260820T174324Z/disposable-root/disposable-restore.sqlite3",
                            112144384,
                            "769befd90ab82e2ed7443b19ba8834dbf7807e0c0aaed20549e0e4ab6acc3847",
                        ),
                        (
                            "operator-runs/v2-9-8b-pre-admission-2364-reconciliation/RECONCILE_20260820T174324Z/reconciliation_evidence.json",
                            1639,
                            "ee538e004d5f1de9db6b4aff86002b8c2375fa547481ee1311917f1816ab17ad",
                        ),
                        (
                            "operator-runs/v2-9-8b-pre-admission-2364-reconciliation/RECONCILE_20260820T174324Z/verified-backup.sqlite3",
                            112144384,
                            "769befd90ab82e2ed7443b19ba8834dbf7807e0c0aaed20549e0e4ab6acc3847",
                        ),
                    ),
                ),
                (
                    "HISTORICAL_ORPHAN_FACTORY_RUN_RECONCILIATION_EVIDENCE",
                    4,
                    "23ea78d77776c1bb566ec098623eb2957dff280a15701fd2fe4779d0e82d0ff3",
                    (
                        (
                            "operator-runs/v2-9-8b-historical-orphan-factory-run-reconciliation/RECONCILE_20260820T185845Z/disposable-root/disposable-restore.sqlite3",
                            112144384,
                            "f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341",
                        ),
                        (
                            "operator-runs/v2-9-8b-historical-orphan-factory-run-reconciliation/RECONCILE_20260820T185845Z/verified-backup.sqlite3",
                            112144384,
                            "f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341",
                        ),
                        (
                            "operator-runs/v2-9-8b-historical-orphan-factory-run-reconciliation/RECONCILE_20260820T192309Z/disposable-root/disposable-restore.sqlite3",
                            112144384,
                            "f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341",
                        ),
                        (
                            "operator-runs/v2-9-8b-historical-orphan-factory-run-reconciliation/RECONCILE_20260820T192309Z/verified-backup.sqlite3",
                            112144384,
                            "f167858a7a47c2837bced97223501f8d1c004d1c8c7a8177ed080c4e8d27f341",
                        ),
                    ),
                ),
                (
                    "HISTORICAL_PAIR_READY_RESIDUAL_RECONCILIATION_EVIDENCE",
                    5,
                    "94cb775d8f1a0d095669c3a1285b8484d7bfbae62c50bf327669516d942285d7",
                    (
                        (
                            "operator-runs/v2-9-8b-pair-ready-residual-reconciliation/RECONCILIATION_20260821T110736Z/backup_and_disposable_rehearsal.json",
                            306712,
                            "a74406aec8e240d6627a04cf0299bbc95b35a45f2fd98261f60c040e3eb48cf0",
                        ),
                        (
                            "operator-runs/v2-9-8b-pair-ready-residual-reconciliation/RECONCILIATION_20260821T110736Z/post_reconciliation_snapshot.json",
                            92014,
                            "633424430f850c70a58cd03a6fa4f73b6b89c8baab570946ad7bb79e899aa76c",
                        ),
                        (
                            "operator-runs/v2-9-8b-pair-ready-residual-reconciliation/RECONCILIATION_20260821T110736Z/pre_reconciliation_snapshot.json",
                            92083,
                            "1f5a2b4b7ba16ec4f4378259bfe863f0bac5c4cd0ff5594c3154e3356b9e26e6",
                        ),
                        (
                            "operator-runs/v2-9-8b-pair-ready-residual-reconciliation/RECONCILIATION_20260821T110736Z/reconcile_pair_ready_residual.py",
                            33379,
                            "64da79ef2cf1cae93f6fe4acb48f2c4f0c5d22214fc04ed05898776775c8c31a",
                        ),
                        (
                            "operator-runs/v2-9-8b-pair-ready-residual-reconciliation/RECONCILIATION_20260821T110736Z/reconciliation_receipt.json",
                            29684,
                            "cbdd06a2cd33d1f1917c1b26210f9c27dc4a8b8384004cdb6462eca476544022",
                        ),
                    ),
                ),
            ),
        )

    def test_public_manifest_schema_is_unchanged(self) -> None:
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        self.assertNotIn(
            "historical_reconciliation_evidence",
            git_auth.expected_manifest_keys(profile),
        )

    def test_packages_bind_exact_preserved_execution_directory_topology(self) -> None:
        packages = (
            git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
            .historical_reconciliation_packages
        )
        self.assertEqual(
            tuple(getattr(item, "execution_directories", None) for item in packages),
            (
                (
                    "RECONCILE_20260820T174244Z",
                    "RECONCILE_20260820T174324Z",
                ),
                (
                    "RECONCILE_20260820T185845Z",
                    "RECONCILE_20260820T192309Z",
                ),
                ("RECONCILIATION_20260821T110736Z",),
            ),
        )


class ReconciliationPackageEnumerationTests(unittest.TestCase):
    """Declarations, rather than filesystem discovery, define membership."""

    def test_exact_declared_package_enumerates_path_size_sha_and_class(self) -> None:
        enumerate_evidence = getattr(
            git_auth, "enumerate_historical_reconciliation_evidence", None
        )
        self.assertTrue(callable(enumerate_evidence))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "operator-runs/reconcile/EXEC/evidence.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"evidence\n")
            package = git_auth.HistoricalReconciliationPackage(
                package_root="operator-runs/reconcile",
                execution_id="EXEC",
                evidence_class="HISTORICAL_RECONCILIATION_TEST",
                expected_file_count=1,
                expected_inventory_sha256=(
                    "5f56d9cc5b7377c82f154c379072d2ad39091faf02061a12a3c28b086fd258a2"
                ),
                execution_directories=("EXEC",),
                files=(
                    git_auth.HistoricalReconciliationFile(
                        path="operator-runs/reconcile/EXEC/evidence.json",
                        size=9,
                        sha256=(
                            "bdcf4c994585af6dd6cb1cfbff78bcc73ab27dc30a299db5bb83766ca05b5de4"
                        ),
                    ),
                ),
            )

            records = enumerate_evidence(
                repository_root=root,
                historical_reconciliation_packages=(package,),
                tracked_operator_runs_paths=set(),
            )

        self.assertEqual(
            records,
            (
                {
                    "path": "operator-runs/reconcile/EXEC/evidence.json",
                    "sha256": (
                        "bdcf4c994585af6dd6cb1cfbff78bcc73ab27dc30a299db5bb83766ca05b5de4"
                    ),
                    "size": 9,
                    "evidence_class": "HISTORICAL_RECONCILIATION_TEST",
                    "reconciliation_execution_id": "EXEC",
                },
            ),
        )

    def test_migration_evidence_class_cannot_be_reused_for_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "operator-runs/reconcile/EXEC/evidence.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"evidence\n")
            package = git_auth.HistoricalReconciliationPackage(
                package_root="operator-runs/reconcile",
                execution_id="EXEC",
                evidence_class=git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS,
                expected_file_count=1,
                expected_inventory_sha256=(
                    "e2f1a5c6992135ccf65fe8dbf7fa7b0ebe925f5fa8e962cf25cbbe10b7f129bd"
                ),
                execution_directories=("EXEC",),
                files=(
                    git_auth.HistoricalReconciliationFile(
                        path="operator-runs/reconcile/EXEC/evidence.json",
                        size=9,
                        sha256=(
                            "bdcf4c994585af6dd6cb1cfbff78bcc73ab27dc30a299db5bb83766ca05b5de4"
                        ),
                    ),
                ),
            )

            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                git_auth.enumerate_historical_reconciliation_evidence(
                    repository_root=root,
                    historical_reconciliation_packages=(package,),
                    tracked_operator_runs_paths=set(),
                )

    def _assert_rejected(self, root: Path, package) -> None:
        with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
            git_auth.enumerate_historical_reconciliation_evidence(
                repository_root=root,
                historical_reconciliation_packages=(package,),
                tracked_operator_runs_paths=set(),
            )

    def test_missing_declared_member_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, target = _synthetic_package(root)
            target.unlink()
            self._assert_rejected(root, package)

    def test_one_modified_byte_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, target = _synthetic_package(root)
            target.write_bytes(b"evidencf\n")
            self._assert_rejected(root, package)

    def test_extra_file_inside_declared_package_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, target = _synthetic_package(root)
            (target.parent / "extra.json").write_bytes(b"{}\n")
            self._assert_rejected(root, package)

    def test_added_sibling_execution_directory_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, _target = _synthetic_package(root)
            (root / "operator-runs/reconcile/EXEC_SIBLING").mkdir()
            self._assert_rejected(root, package)

    def test_wrong_execution_id_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, _target = _synthetic_package(root)
            self._assert_rejected(root, replace(package, execution_id="WRONG"))

    def test_wrong_inventory_digest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, _target = _synthetic_package(root)
            self._assert_rejected(
                root, replace(package, expected_inventory_sha256="a" * 64)
            )

    def test_symlink_member_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, target = _synthetic_package(root)
            (target.parent / "alias.json").symlink_to(target)
            self._assert_rejected(root, package)

    def test_non_regular_member_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package, target = _synthetic_package(root)
            os.mkfifo(target.parent / "member.fifo")
            self._assert_rejected(root, package)


class CanonicalPreMarkerReconciliationTests(unittest.TestCase):
    """The canonical pre-marker path includes immutable reconciliation evidence."""

    def test_pre_marker_validation_reconciles_declared_historical_package(self) -> None:
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            target = fixture.repo / "operator-runs/reconcile/RECON_1/evidence.json"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"reconcile\n")
            fixture.exclude(target)
            orphan_target = (
                fixture.repo / "operator-runs/orphan/RECON_2/backup.sqlite3"
            )
            orphan_target.parent.mkdir(parents=True)
            orphan_target.write_bytes(b"orphan\n")
            fixture.exclude(orphan_target)
            reconciliation_package = git_auth.HistoricalReconciliationPackage(
                package_root="operator-runs/reconcile",
                execution_id="RECON_1",
                evidence_class="HISTORICAL_RECONCILIATION_TEST",
                expected_file_count=1,
                expected_inventory_sha256=(
                    "e61e6dbae34722a25627973b01a92fdd3cc40bc0e6b11bcfafa16fcb28d45694"
                ),
                execution_directories=("RECON_1",),
                files=(
                    git_auth.HistoricalReconciliationFile(
                        path="operator-runs/reconcile/RECON_1/evidence.json",
                        size=10,
                        sha256=(
                            "36725792c6977e0f345a85e6af1fbadeac7d1ee978788390e98938a76ee25d0a"
                        ),
                    ),
                ),
            )
            orphan_package = git_auth.HistoricalReconciliationPackage(
                package_root="operator-runs/orphan",
                execution_id="RECON_2",
                evidence_class="HISTORICAL_ORPHAN_RECONCILIATION_TEST",
                expected_file_count=1,
                expected_inventory_sha256=(
                    "f0ca5c7fbcfe4d198c8e38d5953141f6c87a2942f73c91598736b9abd1001238"
                ),
                execution_directories=("RECON_2",),
                files=(
                    git_auth.HistoricalReconciliationFile(
                        path="operator-runs/orphan/RECON_2/backup.sqlite3",
                        size=7,
                        sha256=(
                            "2b2d2fa0c84d999ef6544e65d0488c82b9c11c4a08b7bf2925d130b366a3795b"
                        ),
                    ),
                ),
            )
            prior = fixture.profile
            fixture.profile = git_auth.GitAuthorizationProfile(
                command_mode=prior.command_mode,
                authorization_package_root=prior.authorization_package_root,
                authorization_package_kind=prior.authorization_package_kind,
                manifest_schema_version=prior.manifest_schema_version,
                historical_authorization_package_roots=(
                    prior.historical_authorization_package_roots
                ),
                migration_package_root=prior.migration_package_root,
                migration_package_kind=prior.migration_package_kind,
                historical_migration_packages=prior.historical_migration_packages,
                historical_reconciliation_packages=(
                    reconciliation_package,
                    orphan_package,
                ),
            )

            payload, manifest_path, manifest_sha256 = fixture.manifest()
            prepared = fixture.validate_prebuilt(manifest_path, manifest_sha256)

            self.assertIn(
                "operator-runs/reconcile/RECON_1/evidence.json",
                prepared.allowed_untracked_paths,
            )
            self.assertIn(
                "operator-runs/orphan/RECON_2/backup.sqlite3",
                prepared.allowed_untracked_paths,
            )
            self.assertEqual(prepared.file_count, 11)
            current_and_historical = []
            for item in payload["files"]:
                current_and_historical.append(
                    {
                        "package_kind": item["package_kind"],
                        "path": item["path"],
                        "sha256": item["sha256"],
                        "size": item["size"],
                    }
                )
            for key in (
                "historical_authorization_evidence",
                "historical_migration_evidence",
            ):
                for item in payload[key]:
                    current_and_historical.append(
                        {
                            "package_kind": item["evidence_class"],
                            "path": item["path"],
                            "sha256": item["sha256"],
                            "size": item["size"],
                        }
                    )
            without_reconciliation = git_auth.compute_allowed_file_set_sha256(
                current_and_historical
            )
            current_and_historical.append(
                {
                    "package_kind": "HISTORICAL_RECONCILIATION_TEST",
                    "path": "operator-runs/reconcile/RECON_1/evidence.json",
                    "sha256": (
                        "36725792c6977e0f345a85e6af1fbadeac7d1ee978788390e98938a76ee25d0a"
                    ),
                    "size": 10,
                }
            )
            current_and_historical.append(
                {
                    "package_kind": "HISTORICAL_ORPHAN_RECONCILIATION_TEST",
                    "path": "operator-runs/orphan/RECON_2/backup.sqlite3",
                    "sha256": (
                        "2b2d2fa0c84d999ef6544e65d0488c82b9c11c4a08b7bf2925d130b366a3795b"
                    ),
                    "size": 7,
                }
            )
            self.assertEqual(
                prepared.allowed_file_set_sha256,
                git_auth.compute_allowed_file_set_sha256(current_and_historical),
            )
            self.assertNotEqual(
                prepared.allowed_file_set_sha256, without_reconciliation
            )
        finally:
            fixture.close()

    def test_arbitrary_unrelated_operator_runs_file_still_blocks(self) -> None:
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            stray = fixture.repo / "operator-runs/unrelated/stray.json"
            stray.parent.mkdir(parents=True)
            stray.write_bytes(b"{}\n")
            fixture.exclude(stray)
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                fixture.validate()
        finally:
            fixture.close()

    def test_manifest_cannot_redefine_reconciliation_membership(self) -> None:
        fixture = FourTokenHistoricalMigrationFixture()
        try:
            payload, manifest_path, _manifest_sha256 = fixture.manifest()
            payload["historical_reconciliation_evidence"] = []
            manifest_bytes = (
                json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
            )
            manifest_path.write_bytes(manifest_bytes)
            with self.assertRaisesRegex(
                git_auth.GitProvenanceAuthorizationError,
                "manifest schema is malformed",
            ):
                fixture.validate_prebuilt(
                    manifest_path, hashlib.sha256(manifest_bytes).hexdigest()
                )
        finally:
            fixture.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
