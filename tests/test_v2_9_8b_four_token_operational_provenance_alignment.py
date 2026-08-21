"""Focused contract for post-repair four-token provenance alignment to 059.

Offline only. This file reads committed profile declarations and disposable
fixtures. It creates no authorization, calls no source, starts no process, and
never touches the authoritative database.
"""

from __future__ import annotations

import inspect
import sqlite3
import unittest
from pathlib import Path

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import four_token_proof_zero_state_gate as gate
from printer_v1.operator_cli import (
    four_token_standard_four_hour_one_shot_wrapper as operational,
)


FOUR_TOKEN_PROFILES = ()


class CurrentMigrationEvidenceTests(unittest.TestCase):
    """Migration 059 is current evidence for both four-token profiles."""

    def setUp(self) -> None:
        self.proof = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
        self.operational = (
            git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        )

    def test_migration_059_identity_constants(self) -> None:
        self.assertEqual(
            git_auth.MIGRATION_059_PACKAGE_ROOT,
            "operator-runs/v2-9-8b-migration-059-application",
        )
        self.assertEqual(
            git_auth.MIGRATION_059_PACKAGE_KIND, "MIGRATION_059_EVIDENCE"
        )
        for other in (
            git_auth.MIGRATION_PACKAGE_ROOT,
            git_auth.MIGRATION_055_PACKAGE_ROOT,
            git_auth.MIGRATION_056_PACKAGE_ROOT,
            git_auth.MIGRATION_057_PACKAGE_ROOT,
        ):
            self.assertNotEqual(git_auth.MIGRATION_059_PACKAGE_ROOT, other)
        for other in (
            git_auth.MIGRATION_PACKAGE_KIND,
            git_auth.MIGRATION_055_PACKAGE_KIND,
            git_auth.MIGRATION_056_PACKAGE_KIND,
            git_auth.MIGRATION_057_PACKAGE_KIND,
        ):
            self.assertNotEqual(git_auth.MIGRATION_059_PACKAGE_KIND, other)

    def test_both_four_token_profiles_are_current_at_059(self) -> None:
        for profile in (self.proof, self.operational):
            with self.subTest(mode=profile.command_mode):
                self.assertEqual(
                    profile.migration_package_root,
                    git_auth.MIGRATION_059_PACKAGE_ROOT,
                )
                self.assertEqual(
                    profile.migration_package_kind,
                    git_auth.MIGRATION_059_PACKAGE_KIND,
                )

    def test_057_is_no_longer_current_four_token_evidence(self) -> None:
        for profile in (self.proof, self.operational):
            with self.subTest(mode=profile.command_mode):
                self.assertNotEqual(
                    profile.migration_package_root,
                    git_auth.MIGRATION_057_PACKAGE_ROOT,
                )
                self.assertNotEqual(
                    profile.migration_package_kind,
                    git_auth.MIGRATION_057_PACKAGE_KIND,
                )

    def test_ordinary_and_standard_4h_profiles_are_untouched(self) -> None:
        for profile in (
            git_auth.ORDINARY_AUTHORIZATION_PROFILE,
            git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        ):
            with self.subTest(mode=profile.command_mode):
                self.assertEqual(
                    profile.migration_package_root, git_auth.MIGRATION_PACKAGE_ROOT
                )
                self.assertEqual(
                    profile.migration_package_kind, git_auth.MIGRATION_PACKAGE_KIND
                )
                self.assertEqual(profile.historical_migration_packages, ())


class HistoricalMigrationChainTests(unittest.TestCase):
    """050, 055, 056, 057 and 058 are the preserved historical chain."""

    def setUp(self) -> None:
        self.profiles = (
            git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE,
            git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        )

    def test_exact_five_historical_packages(self) -> None:
        expected_roots = (
            git_auth.MIGRATION_PACKAGE_ROOT,
            git_auth.MIGRATION_055_PACKAGE_ROOT,
            git_auth.MIGRATION_056_PACKAGE_ROOT,
            git_auth.MIGRATION_057_PACKAGE_ROOT,
            git_auth.MIGRATION_058_PACKAGE_ROOT,
        )
        for profile in self.profiles:
            with self.subTest(mode=profile.command_mode):
                packages = profile.historical_migration_packages
                self.assertEqual(len(packages), 5)
                self.assertEqual(
                    tuple(item.package_root for item in packages), expected_roots
                )
                classes = tuple(item.evidence_class for item in packages)
                self.assertEqual(len(set(classes)), 5)
                ids = tuple(item.execution_id for item in packages)
                self.assertEqual(len(set(ids)), 5)

    def test_058_historical_identity_is_exact_preserved_evidence(self) -> None:
        package = next(
            item
            for item in self.profiles[0].historical_migration_packages
            if item.package_root == git_auth.MIGRATION_058_PACKAGE_ROOT
        )
        self.assertEqual(
            package.execution_id,
            git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXECUTION_ID,
        )
        self.assertEqual(
            package.evidence_class,
            git_auth.HISTORICAL_MIGRATION_058_EVIDENCE_CLASS,
        )
        self.assertEqual(package.expected_file_count, 11)
        self.assertEqual(
            package.expected_inventory_sha256,
            "d6dc1431a3a99a8c2f521a3033948d11bbdd4e7151ddabc1127c7fb3b9138fa8",
        )

    def test_057_historical_identity_is_exact_preserved_evidence(self) -> None:
        self.assertEqual(
            git_auth.HISTORICAL_MIGRATION_057_EVIDENCE_CLASS,
            "HISTORICAL_MIGRATION_057_EVIDENCE",
        )
        self.assertEqual(
            git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXECUTION_ID,
            "MIGRATION_057_20260816T191558Z",
        )
        self.assertEqual(
            git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXPECTED_FILE_COUNT, 6
        )
        self.assertRegex(
            git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXPECTED_INVENTORY_SHA256,
            r"^[0-9a-f]{64}$",
        )
        self.assertEqual(
            git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXPECTED_INVENTORY_SHA256,
            "9272f596e7a82c3cfe9d824595be74f34c7203dccab3bd541c187dc236519535",
        )

    def test_057_package_declares_a_complete_immutable_inventory(self) -> None:
        for profile in self.profiles:
            package = next(
                item
                for item in profile.historical_migration_packages
                if item.package_root == git_auth.MIGRATION_057_PACKAGE_ROOT
            )
            self.assertEqual(
                package.execution_id,
                git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXECUTION_ID,
            )
            self.assertEqual(package.expected_file_count, 6)
            self.assertEqual(
                package.expected_inventory_sha256,
                git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXPECTED_INVENTORY_SHA256,
            )

    def test_prior_historical_declarations_are_unchanged(self) -> None:
        proof = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
        by_root = {
            item.package_root: item
            for item in proof.historical_migration_packages
        }
        self.assertEqual(
            by_root[git_auth.MIGRATION_PACKAGE_ROOT].expected_file_count, 12
        )
        self.assertEqual(
            by_root[git_auth.MIGRATION_PACKAGE_ROOT].expected_inventory_sha256,
            "2bcbfdd3e9b1bf0a2f53bcdd386d0f782b698b883d5d4bb43d1a8a7bd795f8d5",
        )
        self.assertEqual(
            by_root[git_auth.MIGRATION_055_PACKAGE_ROOT].expected_file_count, 5
        )
        self.assertEqual(
            by_root[git_auth.MIGRATION_055_PACKAGE_ROOT].expected_inventory_sha256,
            "c00443733269993b40353b61390753a49dad184541120916c6e2a400fdd9e625",
        )
        self.assertEqual(
            by_root[git_auth.MIGRATION_056_PACKAGE_ROOT].expected_file_count, 6
        )
        self.assertEqual(
            by_root[git_auth.MIGRATION_056_PACKAGE_ROOT].expected_inventory_sha256,
            "4918774b95998aab821d69d06854665697347664faf04a3340f2299db95868f3",
        )

    def test_no_placeholder_evidence_is_accepted(self) -> None:
        source = inspect.getsource(git_auth)
        for placeholder in ("TODO", "PLACEHOLDER", "FIXME", "0" * 64, "x" * 64):
            self.assertNotIn(placeholder, source, placeholder)
        for profile in self.profiles:
            for package in profile.historical_migration_packages:
                self.assertGreaterEqual(package.expected_file_count, 1)
                self.assertRegex(
                    package.expected_inventory_sha256, r"^[0-9a-f]{64}$"
                )

    def test_fabricated_inventory_digest_fails_closed(self) -> None:
        package = git_auth.HistoricalMigrationPackage(
            package_root=git_auth.MIGRATION_057_PACKAGE_ROOT,
            execution_id=git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXECUTION_ID,
            evidence_class=git_auth.HISTORICAL_MIGRATION_057_EVIDENCE_CLASS,
            expected_file_count=6,
            expected_inventory_sha256="a" * 64,
        )
        fake_files = [
            {"path": f"{package.package_prefix}/x.json", "sha256": "b" * 64, "size": 1}
        ]
        self.assertNotEqual(
            package.inventory_sha256(fake_files), package.expected_inventory_sha256
        )


class AuthorizationProfileSeparationTests(unittest.TestCase):
    """The new operational profile is a fourth distinct authority."""

    def test_four_distinct_supported_profiles(self) -> None:
        profiles = git_auth.supported_profiles()
        self.assertEqual(len(profiles), 4)
        self.assertIn(
            git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE, profiles
        )
        modes = {item.command_mode for item in profiles}
        self.assertEqual(len(modes), 4)
        roots = {item.authorization_package_root for item in profiles}
        self.assertEqual(len(roots), 4)
        kinds = {item.authorization_package_kind for item in profiles}
        self.assertEqual(len(kinds), 4)
        schemas = {item.manifest_schema_version for item in profiles}
        self.assertEqual(len(schemas), 4)

    def test_operational_profile_identity(self) -> None:
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        self.assertEqual(profile.command_mode, "four-token-standard-four-hour-run")
        self.assertEqual(
            profile.authorization_package_root,
            "operator-runs/v2-9-8b-four-token-standard-four-hour-final-authorization",
        )
        self.assertEqual(
            profile.authorization_package_kind,
            "FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_EVIDENCE",
        )
        self.assertEqual(
            profile.manifest_schema_version,
            "PRINTER_V1_GIT_PROVENANCE_MANIFEST_FOUR_TOKEN_STANDARD_4H_V1",
        )

    def test_historical_authorization_visibility_covers_prior_roots(self) -> None:
        profile = git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        roots = profile.historical_authorization_package_roots
        for expected in (
            git_auth.AUTHORIZATION_PACKAGE_ROOT,
            "operator-runs/v2-9-8b-standard-four-hour-final-authorization",
            "operator-runs/v2-9-8b-four-token-final-authorization",
            profile.authorization_package_root,
        ):
            self.assertIn(expected, roots)

    def test_unknown_profile_is_still_rejected(self) -> None:
        rogue = git_auth.GitAuthorizationProfile(
            command_mode="rogue-run",
            authorization_package_root="operator-runs/rogue",
            authorization_package_kind="ROGUE",
            manifest_schema_version="ROGUE_V1",
            historical_authorization_package_roots=(),
        )
        with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
            git_auth._resolved_profile(rogue)


class ZeroStateGateTests(unittest.TestCase):
    """The operational gate reuses, never duplicates, the four-token gate."""

    def test_migration_pin_is_59_and_059(self) -> None:
        self.assertEqual(gate.REQUIRED_MIGRATION_COUNT, 59)
        self.assertEqual(
            gate.REQUIRED_MIGRATION_HEAD,
            "059_pair_ready_parent_terminal_cancellation_transition.sql",
        )

    def test_059_is_the_only_new_canonical_migration(self) -> None:
        source = inspect.getsource(gate)
        self.assertIn("059_pair_ready_parent_terminal_cancellation_transition.sql", source)
        migrations = sorted(
            item.name
            for item in Path("migrations").iterdir()
            if item.suffix == ".sql"
        )
        self.assertEqual(len(migrations), 59)
        self.assertEqual(
            migrations[-1],
            "059_pair_ready_parent_terminal_cancellation_transition.sql",
        )
        self.assertEqual(
            [item for item in migrations if item.startswith("059")],
            ["059_pair_ready_parent_terminal_cancellation_transition.sql"],
        )

    def test_operational_gate_exists_and_shares_the_ownership_sql(self) -> None:
        self.assertTrue(
            hasattr(gate, "assert_four_token_standard_four_hour_zero_state")
        )
        # One shared projection owner; no duplicated ownership SQL.
        self.assertEqual(
            inspect.getsource(gate).count("FROM printer_memory_factory_campaigns"), 1
        )
        self.assertIn(
            "active_campaigns", gate.REQUIRED_ZERO_STATE_DOMAINS
        )

    def test_operational_runtime_mode_is_recognized_as_a_printer_run(self) -> None:
        self.assertIn(
            "four-token-standard-four-hour-run",
            gate.PRINTER_OPERATIONAL_RUNTIME_MODES,
        )
        self.assertTrue(
            gate.is_printer_operational_runtime_command(
                "/x/python -m printer_v1.operator_cli."
                "operational_memory_factory_command "
                "four-token-standard-four-hour-run --operator-approved"
            )
        )

    def test_wrong_migration_head_blocks_before_consumption(self) -> None:
        calls: list[str] = []

        def probe():
            calls.append("probe")
            return ()

        document = operational.fixture_authorization_document(
            branch="main",
            head="a" * 40,
            database={
                "path": "/tmp/printer.sqlite3",
                "sha256": "c" * 64,
                "size": 4096,
                "inode": 3,
                "mtime_ns": 5,
                "migration_count": 59,
                "migration_head": "059_forbidden.sql",
            },
        )
        with self.assertRaises(gate.FourTokenProofZeroStateError):
            gate.assert_four_token_standard_four_hour_zero_state(
                db_path="/nonexistent/printer.sqlite3",
                authorization_document=document,
                environment={},
                printer_process_probe=probe,
                migration_ledger_guard=lambda **_: None,
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
