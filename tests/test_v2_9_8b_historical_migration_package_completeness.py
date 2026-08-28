"""Focused contract for the immutable historical-migration completeness law.

Offline only. Every repository, authorization document, migration package and
database identity in this file is a disposable temporary fixture. No real
authorization is prepared or created, no application marker is written, no
Printer runtime is started, no source or RPC is contacted, and no authoritative
database is read or mutated.

The law under test: before ``enumerate_historical_migration_evidence()`` emits
any record for a declared package, that package's COMPLETE accepted inventory
must equal its immutable committed declaration — file count, per-file bytes and
untracked status. Trust comes from committed source at the bound Git HEAD;
filesystem discovery may only prove equality or fail it, never define a new
trusted package identity.

Every negative below injects its fault BEFORE ``build_manifest_bytes()``, so it
proves fresh-preparation failure rather than post-manifest detection.
"""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import (
    four_token_proof_one_shot_wrapper as four_token,
)


HM_050_ROOT = "operator-runs/v2-9-8b-authoritative-mig050"
HM_050_EXEC = "V2_9_8B_AUTHORITATIVE_MIG050_20260801T202423Z_f697cc0f"
HM_055_ROOT = "operator-runs/v2-9-8b-migration-055-application"
HM_055_EXEC = "MIGRATION_055_20260813T220109Z"
HM_056_ROOT = "operator-runs/v2-9-8b-migration-056-application"
HM_056_EXEC = "MIGRATION_056_20260815T164802Z"

_SYNTHETIC_PACKAGES = {
    (HM_050_ROOT, HM_050_EXEC, git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS): {
        "preflight.json": '{"preflight": "ok"}\n',
        "post_migration_proof.json": '{"migration_count": 50}\n',
        "verified-backup/printer_v1-pre050.sqlite3": "pre050-bytes\n",
    },
    (HM_055_ROOT, HM_055_EXEC, git_auth.HISTORICAL_MIGRATION_055_EVIDENCE_CLASS): {
        "migration_055_application_result.json": '{"migration": "055"}\n',
        "disposable/migration-055-rehearsal.sqlite3": "rehearsal-055\n",
    },
    (HM_056_ROOT, HM_056_EXEC, git_auth.HISTORICAL_MIGRATION_056_EVIDENCE_CLASS): {
        "migration_056_application_result.json": '{"migration": "056"}\n',
        "disposable/migration-056-rehearsal.sqlite3": "rehearsal-056\n",
    },
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextlib.contextmanager
def _patched_four_token_profile(profile):
    """Scope one fixture profile over both production import bindings."""
    with mock.patch.object(
        git_auth, "FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE", profile
    ), mock.patch.object(
        four_token, "FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE", profile
    ):
        yield profile


class CompletenessFixture:
    """Disposable repo with three synthetic declared historical packages."""

    authorization_id = "V2_9_8B_FOUR_TOKEN_AUTH_COMPLETENESS_TESTONLY"
    migration_id = "MIGRATION_061_COMPLETENESS_TESTONLY"

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self._git("init")
        self._git("config", "user.email", "tests@example.invalid")
        self._git("config", "user.name", "Historical Completeness Tests")
        (self.repo / ".gitignore").write_text("*.sqlite3\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-m", "baseline")
        self.branch = self._git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.head = self._git("rev-parse", "HEAD").stdout.strip()

        production = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE

        # M: synthetic current migration evidence plus current authorization.
        self.migration_root = (
            self.repo / production.migration_package_root / self.migration_id
        )
        self.migration_root.mkdir(parents=True)
        (self.migration_root / "migration_061_application_result.json").write_text(
            json.dumps({"migration": self.migration_id}) + "\n", encoding="utf-8"
        )
        self.authorization_root = (
            self.repo / production.authorization_package_root / self.authorization_id
        )
        self.authorization_root.mkdir(parents=True)

        # Hm: three synthetic packages, each declaring its OWN identity.
        self.package_dirs: dict[str, Path] = {}
        declarations = []
        for (root, execution, klass), files in _SYNTHETIC_PACKAGES.items():
            package_dir = self.repo / root / execution
            for relative, content in files.items():
                target = package_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            self.exclude(package_dir)
            self.package_dirs[root] = package_dir
            count, digest = self.identity(root, execution, klass)
            declarations.append(
                git_auth.HistoricalMigrationPackage(
                    package_root=root,
                    execution_id=execution,
                    evidence_class=klass,
                    expected_file_count=count,
                    expected_inventory_sha256=digest,
                )
            )
        self.profile = git_auth.GitAuthorizationProfile(
            command_mode=production.command_mode,
            authorization_package_root=production.authorization_package_root,
            authorization_package_kind=production.authorization_package_kind,
            manifest_schema_version=production.manifest_schema_version,
            historical_authorization_package_roots=(
                production.historical_authorization_package_roots
            ),
            migration_package_root=production.migration_package_root,
            migration_package_kind=production.migration_package_kind,
            historical_migration_packages=tuple(declarations),
        )

        self.authorization_path = self.authorization_root / "final_authorization.json"
        now = datetime.now(timezone.utc)
        document = four_token.fixture_authorization_document(
            branch=self.branch,
            head=self.head,
            database={
                "path": "/tmp/printer.sqlite3",
                "sha256": "c" * 64,
                "size": 4096,
                "inode": 3,
                "mtime_ns": 5,
                "migration_count": 57,
                "migration_head": "057_pre_lifecycle_discovery_refresh_work.sql",
            },
            authorization_id=self.authorization_id,
            migration_execution_id=self.migration_id,
            authorized_at=now.isoformat(),
            expires_at=(now + timedelta(hours=12)).isoformat(),
            prior_authorizations_non_reusable=(),
        )
        self.authorization_path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.authorization_sha256 = _sha(self.authorization_path)

    def _git(self, *args: str):
        return subprocess.run(
            ["git", *args], cwd=self.repo, capture_output=True, text=True, check=True
        )

    def identity(self, root: str, execution: str, klass: str) -> tuple[int, str]:
        base = self.repo / root / execution
        files = [
            {
                "path": item.relative_to(self.repo).as_posix(),
                "sha256": _sha(item),
                "size": item.stat().st_size,
            }
            for item in sorted(base.rglob("*"))
            if item.is_file() and not item.is_symlink()
        ]
        return len(files), git_auth.compute_historical_migration_inventory_sha256(
            package_root=root,
            execution_id=execution,
            evidence_class=klass,
            files=files,
        )

    def exclude(self, target: Path) -> None:
        exclude_file = self.repo / ".git" / "info" / "exclude"
        exclude_file.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude_file.read_text() if exclude_file.exists() else ""
        lines = []
        if target.is_dir():
            for path in sorted(target.rglob("*")):
                if path.is_file():
                    lines.append(path.relative_to(self.repo).as_posix())
        else:
            lines.append(target.relative_to(self.repo).as_posix())
        exclude_file.write_text(
            existing + "".join(f"{line}\n" for line in lines), encoding="utf-8"
        )

    def rebind_authorization(self) -> None:
        """Re-issue the authorization against the current HEAD.

        Any test that commits moves HEAD, and the authorization binds the exact
        repository identity. Rebinding keeps the test focused on the property
        under proof instead of failing on a stale HEAD binding.
        """
        self.head = self._git("rev-parse", "HEAD").stdout.strip()
        now = datetime.now(timezone.utc)
        document = four_token.fixture_authorization_document(
            branch=self.branch,
            head=self.head,
            database={
                "path": "/tmp/printer.sqlite3",
                "sha256": "c" * 64,
                "size": 4096,
                "inode": 3,
                "mtime_ns": 5,
                "migration_count": 57,
                "migration_head": "057_pre_lifecycle_discovery_refresh_work.sql",
            },
            authorization_id=self.authorization_id,
            migration_execution_id=self.migration_id,
            authorized_at=now.isoformat(),
            expires_at=(now + timedelta(hours=12)).isoformat(),
            prior_authorizations_non_reusable=(),
        )
        self.authorization_path.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.authorization_sha256 = _sha(self.authorization_path)

    def prepare(self):
        """REAL fresh preparation through the production wrapper."""
        with _patched_four_token_profile(self.profile):
            payload, data = four_token.build_manifest_bytes(
                repository_root=self.repo,
                authorization_file=self.authorization_path,
                authorization_sha256=self.authorization_sha256,
            )
        path = self.root / "manifest.json"
        path.write_bytes(data)
        return payload, path, hashlib.sha256(data).hexdigest()

    def validate(self):
        _payload, path, digest = self.prepare()
        with _patched_four_token_profile(self.profile):
            return git_auth.validate_git_provenance_manifest_pre_marker(
                repository_root=self.repo,
                manifest_path=str(path),
                manifest_sha256=digest,
                profile=self.profile,
            )

    def close(self) -> None:
        self.tmp.cleanup()


class HistoricalMigrationCompletenessPositiveTests(unittest.TestCase):
    """The production declaration and the accepted-inventory law."""

    def test_production_profile_declares_050_through_061_exact_identities(self) -> None:
        profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
        self.assertEqual(len(profile.historical_migration_packages), 7)
        by_root = {p.package_root: p for p in profile.historical_migration_packages}

        mig050 = by_root[HM_050_ROOT]
        self.assertEqual(mig050.execution_id, HM_050_EXEC)
        self.assertEqual(
            mig050.evidence_class, git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS
        )
        self.assertEqual(mig050.expected_file_count, 12)
        self.assertEqual(
            mig050.expected_inventory_sha256,
            "2bcbfdd3e9b1bf0a2f53bcdd386d0f782b698b883d5d4bb43d1a8a7bd795f8d5",
        )

        mig055 = by_root[HM_055_ROOT]
        self.assertEqual(mig055.execution_id, HM_055_EXEC)
        self.assertEqual(
            mig055.evidence_class, git_auth.HISTORICAL_MIGRATION_055_EVIDENCE_CLASS
        )
        self.assertEqual(mig055.expected_file_count, 5)
        self.assertEqual(
            mig055.expected_inventory_sha256,
            "c00443733269993b40353b61390753a49dad184541120916c6e2a400fdd9e625",
        )

        mig056 = by_root[HM_056_ROOT]
        self.assertEqual(mig056.execution_id, HM_056_EXEC)
        self.assertEqual(
            mig056.evidence_class, git_auth.HISTORICAL_MIGRATION_056_EVIDENCE_CLASS
        )
        self.assertEqual(mig056.expected_file_count, 6)
        self.assertEqual(
            mig056.expected_inventory_sha256,
            "4918774b95998aab821d69d06854665697347664faf04a3340f2299db95868f3",
        )

        mig057 = by_root[git_auth.MIGRATION_057_PACKAGE_ROOT]
        self.assertEqual(
            mig057.execution_id,
            git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_057_EXECUTION_ID,
        )
        self.assertEqual(
            mig057.evidence_class,
            git_auth.HISTORICAL_MIGRATION_057_EVIDENCE_CLASS,
        )
        self.assertEqual(mig057.expected_file_count, 6)
        self.assertEqual(
            mig057.expected_inventory_sha256,
            "9272f596e7a82c3cfe9d824595be74f34c7203dccab3bd541c187dc236519535",
        )

        mig058 = by_root[git_auth.MIGRATION_058_PACKAGE_ROOT]
        self.assertEqual(
            mig058.execution_id,
            git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXECUTION_ID,
        )
        self.assertEqual(
            mig058.evidence_class,
            git_auth.HISTORICAL_MIGRATION_058_EVIDENCE_CLASS,
        )
        self.assertEqual(mig058.expected_file_count, 11)
        self.assertEqual(
            mig058.expected_inventory_sha256,
            "d6dc1431a3a99a8c2f521a3033948d11bbdd4e7151ddabc1127c7fb3b9138fa8",
        )

        mig059 = by_root[git_auth.MIGRATION_059_PACKAGE_ROOT]
        self.assertEqual(
            mig059.execution_id,
            git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_059_EXECUTION_ID,
        )
        self.assertEqual(
            mig059.evidence_class,
            git_auth.HISTORICAL_MIGRATION_059_EVIDENCE_CLASS,
        )
        self.assertEqual(mig059.expected_file_count, 5)
        self.assertEqual(
            mig059.expected_inventory_sha256,
            "d23c4f4bbf2b4683c69038bb6fc372f85c52e280b24662cb46c133690b1479c6",
        )

        mig061 = by_root[git_auth.MIGRATION_061_PACKAGE_ROOT]
        self.assertEqual(
            mig061.execution_id,
            git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_061_EXECUTION_ID,
        )
        self.assertEqual(
            mig061.evidence_class,
            git_auth.HISTORICAL_MIGRATION_061_EVIDENCE_CLASS,
        )
        self.assertEqual(mig061.expected_file_count, 5)
        self.assertEqual(
            mig061.expected_inventory_sha256,
            "ff8aefa1c0ee3fe4ec2063400a97cd81b8311bc4aa23dd402614bb609659a459",
        )

    def test_production_total_declared_hm_count_is_50(self) -> None:
        profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
        total = sum(
            p.expected_file_count for p in profile.historical_migration_packages
        )
        self.assertEqual(total, 50)

    def test_completeness_fields_are_mandatory_with_no_defaults(self) -> None:
        """An optional path would leave mig050 under the old weak rule."""
        with self.assertRaises(TypeError):
            git_auth.HistoricalMigrationPackage(  # type: ignore[call-arg]
                package_root=HM_050_ROOT, execution_id=HM_050_EXEC
            )

    def test_current_062_is_exclusive_and_061_is_historical(self) -> None:
        profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
        roots = {p.package_root for p in profile.historical_migration_packages}
        self.assertEqual(
            profile.migration_package_root, git_auth.MIGRATION_062_PACKAGE_ROOT
        )
        self.assertNotIn(git_auth.MIGRATION_062_PACKAGE_ROOT, roots)
        self.assertIn(git_auth.MIGRATION_061_PACKAGE_ROOT, roots)
        self.assertIn(git_auth.MIGRATION_059_PACKAGE_ROOT, roots)

    def test_complete_packages_prepare_and_validate(self) -> None:
        fixture = CompletenessFixture()
        try:
            payload, _path, _digest = fixture.prepare()
            records = payload[git_auth.HISTORICAL_MIGRATION_EVIDENCE_KEY]
            expected = sum(
                p.expected_file_count
                for p in fixture.profile.historical_migration_packages
            )
            self.assertEqual(len(records), expected)
            for item in records:
                self.assertEqual(
                    set(item),
                    {
                        "path",
                        "sha256",
                        "size",
                        "evidence_class",
                        "migration_execution_id",
                    },
                )
                target = fixture.repo / item["path"]
                self.assertEqual(item["sha256"], _sha(target))
                self.assertEqual(item["size"], target.stat().st_size)
            prepared = fixture.validate()
            self.assertEqual(prepared.authorization_id, fixture.authorization_id)
        finally:
            fixture.close()

    def test_manifest_key_set_is_unchanged_by_the_law(self) -> None:
        profile = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
        self.assertEqual(
            git_auth.expected_manifest_keys(profile),
            git_auth._MANIFEST_KEYS | {git_auth.HISTORICAL_MIGRATION_EVIDENCE_KEY},
        )

    def test_hm_records_never_gain_authorization_identity(self) -> None:
        fixture = CompletenessFixture()
        try:
            payload, _path, _digest = fixture.prepare()
            for item in payload[git_auth.HISTORICAL_MIGRATION_EVIDENCE_KEY]:
                self.assertNotIn("authorization_id", item)
                self.assertNotIn("terminal_disposition", item)
        finally:
            fixture.close()

    def test_production_globals_are_never_left_patched(self) -> None:
        """Ordering safety: no fixture may leak its profile into production."""
        before = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE
        fixture = CompletenessFixture()
        try:
            with self.assertRaises(Exception):
                with _patched_four_token_profile(fixture.profile):
                    raise RuntimeError("boom")
        finally:
            fixture.close()
        self.assertIs(git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE, before)
        self.assertIs(four_token.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE, before)
        self.assertEqual(len(before.historical_migration_packages), 7)


class InventoryDigestTests(unittest.TestCase):
    """Independent proofs: deterministic, domain-separated, identity-bound.

    These construct expected digests directly rather than calling the helper on
    both sides, so they cannot become tautological.
    """

    files = [
        {"path": "operator-runs/pkg/exec/b.json", "sha256": "b" * 64, "size": 2},
        {"path": "operator-runs/pkg/exec/a.json", "sha256": "a" * 64, "size": 1},
    ]

    def _digest(self, **overrides):
        kwargs = {
            "package_root": "operator-runs/pkg",
            "execution_id": "exec",
            "evidence_class": "CLASS_A",
            "files": self.files,
        }
        kwargs.update(overrides)
        return git_auth.compute_historical_migration_inventory_sha256(**kwargs)

    def test_digest_matches_an_independently_constructed_canonical_form(self) -> None:
        expected_payload = {
            "domain": "PRINTER_V1_HISTORICAL_MIGRATION_PACKAGE_INVENTORY_V1",
            "package_root": "operator-runs/pkg",
            "execution_id": "exec",
            "evidence_class": "CLASS_A",
            "file_count": 2,
            "files": [
                {"path": "operator-runs/pkg/exec/a.json", "sha256": "a" * 64, "size": 1},
                {"path": "operator-runs/pkg/exec/b.json", "sha256": "b" * 64, "size": 2},
            ],
        }
        canonical = json.dumps(
            expected_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        self.assertEqual(
            self._digest(), hashlib.sha256(canonical.encode("ascii")).hexdigest()
        )

    def test_digest_is_deterministic_and_input_order_independent(self) -> None:
        self.assertEqual(self._digest(), self._digest())
        self.assertEqual(
            self._digest(), self._digest(files=list(reversed(self.files)))
        )

    def test_digest_is_domain_separated(self) -> None:
        """A bare inventory digest without the domain must not collide."""
        undomained = json.dumps(
            {
                "package_root": "operator-runs/pkg",
                "execution_id": "exec",
                "evidence_class": "CLASS_A",
                "file_count": 2,
                "files": sorted(self.files, key=lambda r: r["path"]),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        self.assertNotEqual(
            self._digest(), hashlib.sha256(undomained.encode("ascii")).hexdigest()
        )
        self.assertEqual(
            git_auth.HISTORICAL_MIGRATION_INVENTORY_DOMAIN,
            "PRINTER_V1_HISTORICAL_MIGRATION_PACKAGE_INVENTORY_V1",
        )

    def test_digest_is_identity_bound_so_replay_across_packages_fails(self) -> None:
        base = self._digest()
        self.assertNotEqual(base, self._digest(package_root="operator-runs/other"))
        self.assertNotEqual(base, self._digest(execution_id="other-exec"))
        self.assertNotEqual(base, self._digest(evidence_class="CLASS_B"))

    def test_digest_covers_path_size_and_bytes(self) -> None:
        base = self._digest()
        self.assertNotEqual(
            base,
            self._digest(
                files=[dict(self.files[0], size=99), self.files[1]]
            ),
        )
        self.assertNotEqual(
            base,
            self._digest(
                files=[dict(self.files[0], sha256="c" * 64), self.files[1]]
            ),
        )
        self.assertNotEqual(
            base,
            self._digest(
                files=[dict(self.files[0], path="operator-runs/pkg/exec/z.json"),
                       self.files[1]]
            ),
        )


class MalformedDeclarationTests(unittest.TestCase):
    """A declaration that cannot express a real identity fails closed."""

    def _enumerate(self, package):
        fixture = CompletenessFixture()
        try:
            return git_auth.enumerate_historical_migration_evidence(
                repository_root=fixture.repo, historical_migration_packages=(package,)
            )
        finally:
            fixture.close()

    def _package(self, **overrides):
        kwargs = {
            "package_root": HM_050_ROOT,
            "execution_id": HM_050_EXEC,
            "evidence_class": git_auth.HISTORICAL_MIGRATION_EVIDENCE_CLASS,
            "expected_file_count": 3,
            "expected_inventory_sha256": "a" * 64,
        }
        kwargs.update(overrides)
        return git_auth.HistoricalMigrationPackage(**kwargs)

    def test_non_integer_count_fails_closed(self) -> None:
        with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
            self._enumerate(self._package(expected_file_count="3"))

    def test_bool_masquerading_as_count_fails_closed(self) -> None:
        with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
            self._enumerate(self._package(expected_file_count=True))

    def test_count_below_one_fails_closed(self) -> None:
        with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
            self._enumerate(self._package(expected_file_count=0))

    def test_malformed_digest_fails_closed(self) -> None:
        for bad in ("", "zz", "A" * 64, "a" * 63, 123):
            with self.subTest(digest=bad):
                with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                    self._enumerate(self._package(expected_inventory_sha256=bad))


class FreshPreparationNegativeTests(unittest.TestCase):
    """N1-N10 and friends: every fault is injected BEFORE preparation."""

    def _blocks_at_fresh_preparation(self, mutate) -> str:
        fixture = CompletenessFixture()
        try:
            mutate(fixture)
            with self.assertRaises(
                (
                    git_auth.GitProvenanceAuthorizationError,
                    four_token.FourTokenProofOneShotWrapperError,
                )
            ) as caught:
                fixture.prepare()
            return str(caught.exception)
        finally:
            fixture.close()

    def _remove_member(self, root: str, name: str):
        def mutate(fixture: CompletenessFixture) -> None:
            (fixture.package_dirs[root] / name).unlink()

        return mutate

    def test_n1_missing_mig050_member_blocks(self) -> None:
        message = self._blocks_at_fresh_preparation(
            self._remove_member(HM_050_ROOT, "preflight.json")
        )
        self.assertIn("inventory file count", message)

    def test_n2_missing_mig055_member_blocks(self) -> None:
        message = self._blocks_at_fresh_preparation(
            self._remove_member(HM_055_ROOT, "migration_055_application_result.json")
        )
        self.assertIn("inventory file count", message)

    def test_n3_missing_mig056_member_blocks(self) -> None:
        message = self._blocks_at_fresh_preparation(
            self._remove_member(HM_056_ROOT, "migration_056_application_result.json")
        )
        self.assertIn("inventory file count", message)

    def test_n4_modified_mig055_byte_blocks(self) -> None:
        def mutate(fixture: CompletenessFixture) -> None:
            target = (
                fixture.package_dirs[HM_055_ROOT]
                / "migration_055_application_result.json"
            )
            target.write_text('{"migration": "055"}X\n', encoding="utf-8")

        self.assertIn("inventory", self._blocks_at_fresh_preparation(mutate))

    def test_n5_modified_mig056_byte_blocks(self) -> None:
        def mutate(fixture: CompletenessFixture) -> None:
            target = (
                fixture.package_dirs[HM_056_ROOT]
                / "migration_056_application_result.json"
            )
            target.write_text('{"migration": "056"}X\n', encoding="utf-8")

        self.assertIn("inventory", self._blocks_at_fresh_preparation(mutate))

    def test_n6_extra_mig055_file_blocks(self) -> None:
        def mutate(fixture: CompletenessFixture) -> None:
            extra = fixture.package_dirs[HM_055_ROOT] / "intruder.json"
            extra.write_text("{}\n", encoding="utf-8")
            fixture.exclude(extra)

        self.assertIn(
            "inventory file count", self._blocks_at_fresh_preparation(mutate)
        )

    def test_n7_extra_mig056_file_blocks(self) -> None:
        def mutate(fixture: CompletenessFixture) -> None:
            extra = fixture.package_dirs[HM_056_ROOT] / "intruder.json"
            extra.write_text("{}\n", encoding="utf-8")
            fixture.exclude(extra)

        self.assertIn(
            "inventory file count", self._blocks_at_fresh_preparation(mutate)
        )

    def test_n8_member_replaced_by_symlink_blocks(self) -> None:
        def mutate(fixture: CompletenessFixture) -> None:
            target = (
                fixture.package_dirs[HM_055_ROOT]
                / "migration_055_application_result.json"
            )
            elsewhere = fixture.root / "elsewhere.json"
            target.rename(elsewhere)
            target.symlink_to(elsewhere)

        self.assertIn("symlink", self._blocks_at_fresh_preparation(mutate))

    def test_n9_whole_declared_package_missing_blocks(self) -> None:
        def mutate(fixture: CompletenessFixture) -> None:
            package = fixture.package_dirs[HM_055_ROOT]
            for item in sorted(package.rglob("*"), reverse=True):
                item.unlink() if item.is_file() else item.rmdir()
            package.rmdir()

        self.assertIn(
            "execution directory is missing",
            self._blocks_at_fresh_preparation(mutate),
        )

    def test_n10_untrusted_sibling_execution_blocks(self) -> None:
        def mutate(fixture: CompletenessFixture) -> None:
            sibling = fixture.repo / HM_055_ROOT / "MIGRATION_055_20260813T999999Z"
            sibling.mkdir(parents=True)
            rogue = sibling / "rogue.json"
            rogue.write_text("{}\n", encoding="utf-8")
            fixture.exclude(rogue)

        self.assertIn(
            "unapproved historical migration package",
            self._blocks_at_fresh_preparation(mutate),
        )

    def test_declared_member_unexpectedly_tracked_blocks(self) -> None:
        def mutate(fixture: CompletenessFixture) -> None:
            relative = (
                f"{HM_055_ROOT}/{HM_055_EXEC}/migration_055_application_result.json"
            )
            fixture._git("add", "-f", relative)
            fixture._git("commit", "-m", "wrongly track historical member")
            fixture.rebind_authorization()

        self.assertIn(
            "tracked at HEAD instead of preserved untracked evidence",
            self._blocks_at_fresh_preparation(mutate),
        )

    def test_empty_declared_package_blocks(self) -> None:
        def mutate(fixture: CompletenessFixture) -> None:
            package = fixture.package_dirs[HM_055_ROOT]
            for item in sorted(package.rglob("*"), reverse=True):
                item.unlink() if item.is_file() else item.rmdir()

        self.assertIn(
            "inventory file count", self._blocks_at_fresh_preparation(mutate)
        )

    def test_missing_declared_package_root_blocks(self) -> None:
        def mutate(fixture: CompletenessFixture) -> None:
            root = fixture.repo / HM_056_ROOT
            for item in sorted(root.rglob("*"), reverse=True):
                item.unlink() if item.is_file() else item.rmdir()
            root.rmdir()

        self.assertIn(
            "package root is missing", self._blocks_at_fresh_preparation(mutate)
        )

    def test_non_regular_member_blocks(self) -> None:
        def mutate(fixture: CompletenessFixture) -> None:
            fifo = fixture.package_dirs[HM_055_ROOT] / "evidence.fifo"
            os.mkfifo(fifo)
            fixture.exclude(fifo)

        self.assertIn("non-regular", self._blocks_at_fresh_preparation(mutate))


class CurrentPackageSeparationTests(unittest.TestCase):
    """Current 062 evidence may never be tracked or satisfied by Hm."""

    def test_current_062_evidence_tracked_blocks_at_validation(self) -> None:
        fixture = CompletenessFixture()
        try:
            relative = (
                f"{fixture.profile.migration_package_root}/{fixture.migration_id}/"
                "migration_061_application_result.json"
            )
            fixture._git("add", "-f", relative)
            fixture._git("commit", "-m", "wrongly track current evidence")
            fixture.rebind_authorization()
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError) as caught:
                fixture.validate()
            self.assertIn("tracked", str(caught.exception))
        finally:
            fixture.close()

    def test_historical_evidence_never_lies_inside_the_current_package(self) -> None:
        fixture = CompletenessFixture()
        try:
            payload, _path, _digest = fixture.prepare()
            current_prefix = (
                f"{fixture.profile.migration_package_root}/{fixture.migration_id}/"
            )
            for item in payload[git_auth.HISTORICAL_MIGRATION_EVIDENCE_KEY]:
                self.assertFalse(item["path"].startswith(current_prefix))
            current_paths = {item["path"] for item in payload["files"]}
            historical_paths = {
                item["path"]
                for item in payload[git_auth.HISTORICAL_MIGRATION_EVIDENCE_KEY]
            }
            self.assertFalse(current_paths & historical_paths)
        finally:
            fixture.close()


if __name__ == "__main__":
    unittest.main()
