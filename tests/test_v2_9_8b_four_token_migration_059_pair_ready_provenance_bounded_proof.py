"""Bounded disposable proof for Migration-059 / PAIR_READY provenance.

This suite is proof tooling only.  Every manifest, authorization, Git
repository and mutation is disposable.  It never writes the authoritative
database or production ``operator-runs`` tree, creates no production manifest
or marker, launches no child, and performs no source or Scheduler work.
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
from printer_v1.operator_cli import (
    four_token_standard_four_hour_one_shot_wrapper as operational,
)
from test_v2_9_8b_four_token_historical_migration_provenance import (
    FourTokenHistoricalMigrationFixture,
    MIGRATION_058_PATHS,
    _synthetic_completeness_identity,
)
from test_v2_9_8b_four_token_standard_four_hour_one_shot_wrapper import (
    OperationalFixture,
    _Launcher,
    _patched_profile,
)


PAIR_READY_MEMBER_NAMES = (
    "backup_and_disposable_rehearsal.json",
    "post_reconciliation_snapshot.json",
    "pre_reconciliation_snapshot.json",
    "reconcile_pair_ready_residual.py",
    "reconciliation_receipt.json",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_bytes(root: Path, relative: str, content: bytes) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


class _FullShapeFixture:
    """Synthetic full shape using the production profile and owner functions."""

    def __init__(self) -> None:
        self.fixture = FourTokenHistoricalMigrationFixture()
        self.repo = self.fixture.repo
        production = git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE

        migration_packages: list[git_auth.HistoricalMigrationPackage] = []
        for production_package in production.historical_migration_packages:
            package_dir = (
                self.repo
                / production_package.package_root
                / production_package.execution_id
            )
            if production_package.package_root == git_auth.MIGRATION_PACKAGE_ROOT:
                # The inherited fixture has six members; complete the production
                # count shape of twelve without borrowing production hashes.
                additions = {
                    f"shape-extra-{index:02}.json": f"shape-050-{index}\n"
                    for index in range(6)
                }
                self.fixture.write_historical_migration_package(
                    package_dir, additions
                )
            elif production_package.package_root == git_auth.MIGRATION_058_PACKAGE_ROOT:
                relative_members = sorted(
                    path.split(
                        f"{git_auth.MIGRATION_058_PACKAGE_ROOT}/"
                        f"{production_package.execution_id}/",
                        1,
                    )[1]
                    for path in MIGRATION_058_PATHS
                )
                members = {
                    relative: f"synthetic-058-{index}\n"
                    for index, relative in enumerate(relative_members)
                }
                self.fixture.write_historical_migration_package(
                    package_dir, members
                )
            else:
                members = {
                    f"member-{index:02}.json": (
                        f"{production_package.evidence_class}-{index}\n"
                    )
                    for index in range(production_package.expected_file_count)
                }
                self.fixture.write_historical_migration_package(
                    package_dir, members
                )

            count, digest = _synthetic_completeness_identity(
                repo=self.repo,
                package_root=production_package.package_root,
                execution_id=production_package.execution_id,
                evidence_class=production_package.evidence_class,
            )
            migration_packages.append(
                git_auth.HistoricalMigrationPackage(
                    package_root=production_package.package_root,
                    execution_id=production_package.execution_id,
                    evidence_class=production_package.evidence_class,
                    expected_file_count=count,
                    expected_inventory_sha256=digest,
                )
            )

        reconciliation_packages: list[
            git_auth.HistoricalReconciliationPackage
        ] = []
        for production_package in production.historical_reconciliation_packages:
            package_root = self.repo / production_package.package_root
            for execution in production_package.execution_directories:
                (package_root / execution).mkdir(parents=True, exist_ok=True)

            if (
                production_package.evidence_class
                == git_auth.PAIR_READY_RESIDUAL_RECONCILIATION_EVIDENCE_CLASS
            ):
                relative_members = [
                    f"{production_package.execution_id}/{name}"
                    for name in PAIR_READY_MEMBER_NAMES
                ]
            else:
                relative_members = [
                    f"{production_package.execution_directories[index % len(production_package.execution_directories)]}/"
                    f"member-{index:02}.json"
                    for index in range(production_package.expected_file_count)
                ]

            records: list[git_auth.HistoricalReconciliationFile] = []
            digest_records: list[dict[str, object]] = []
            for index, relative in enumerate(relative_members):
                target = _write_bytes(
                    package_root,
                    relative,
                    f"{production_package.evidence_class}-{index}\n".encode(),
                )
                repository_path = target.relative_to(self.repo).as_posix()
                record = git_auth.HistoricalReconciliationFile(
                    path=repository_path,
                    size=target.stat().st_size,
                    sha256=_sha(target),
                )
                records.append(record)
                digest_records.append(
                    {
                        "path": record.path,
                        "size": record.size,
                        "sha256": record.sha256,
                    }
                )
            self.fixture.exclude(package_root)
            digest = git_auth.compute_historical_reconciliation_inventory_sha256(
                package_root=production_package.package_root,
                execution_id=production_package.execution_id,
                evidence_class=production_package.evidence_class,
                files=digest_records,
            )
            reconciliation_packages.append(
                git_auth.HistoricalReconciliationPackage(
                    package_root=production_package.package_root,
                    execution_id=production_package.execution_id,
                    evidence_class=production_package.evidence_class,
                    expected_file_count=len(records),
                    expected_inventory_sha256=digest,
                    execution_directories=(
                        production_package.execution_directories
                    ),
                    files=tuple(records),
                )
            )

        self.fixture.profile = replace(
            self.fixture.profile,
            historical_migration_packages=tuple(migration_packages),
            historical_reconciliation_packages=tuple(reconciliation_packages),
        )
        self.profile = self.fixture.profile

    def manifest(self):
        return self.fixture.manifest()

    def validate_prebuilt(self, path: Path, digest: str):
        return self.fixture.validate_prebuilt(path, digest)

    def close(self) -> None:
        self.fixture.close()


def _synthetic_migration_058(
    root: Path,
) -> tuple[git_auth.HistoricalMigrationPackage, list[Path]]:
    package_root = git_auth.MIGRATION_058_PACKAGE_ROOT
    execution_id = git_auth.FOUR_TOKEN_HISTORICAL_MIGRATION_058_EXECUTION_ID
    prefix = f"{package_root}/{execution_id}/"
    relative_members = sorted(path.split(prefix, 1)[1] for path in MIGRATION_058_PATHS)
    targets = [
        _write_bytes(
            root,
            f"{prefix}{relative}",
            f"migration-058-{index}\n".encode(),
        )
        for index, relative in enumerate(relative_members)
    ]
    records = [
        {
            "path": target.relative_to(root).as_posix(),
            "size": target.stat().st_size,
            "sha256": _sha(target),
        }
        for target in targets
    ]
    digest = git_auth.compute_historical_migration_inventory_sha256(
        package_root=package_root,
        execution_id=execution_id,
        evidence_class=git_auth.HISTORICAL_MIGRATION_058_EVIDENCE_CLASS,
        files=records,
    )
    return (
        git_auth.HistoricalMigrationPackage(
            package_root=package_root,
            execution_id=execution_id,
            evidence_class=git_auth.HISTORICAL_MIGRATION_058_EVIDENCE_CLASS,
            expected_file_count=11,
            expected_inventory_sha256=digest,
        ),
        targets,
    )


def _synthetic_pair_ready(
    root: Path,
) -> tuple[git_auth.HistoricalReconciliationPackage, list[Path]]:
    package_root = git_auth.PAIR_READY_RESIDUAL_RECONCILIATION_PACKAGE_ROOT
    execution_id = git_auth.PAIR_READY_RESIDUAL_RECONCILIATION_EXECUTION_ID
    targets = [
        _write_bytes(
            root,
            f"{package_root}/{execution_id}/{name}",
            f"pair-ready-{index}\n".encode(),
        )
        for index, name in enumerate(PAIR_READY_MEMBER_NAMES)
    ]
    records = tuple(
        git_auth.HistoricalReconciliationFile(
            path=target.relative_to(root).as_posix(),
            size=target.stat().st_size,
            sha256=_sha(target),
        )
        for target in targets
    )
    digest = git_auth.compute_historical_reconciliation_inventory_sha256(
        package_root=package_root,
        execution_id=execution_id,
        evidence_class=(
            git_auth.PAIR_READY_RESIDUAL_RECONCILIATION_EVIDENCE_CLASS
        ),
        files=[
            {"path": item.path, "size": item.size, "sha256": item.sha256}
            for item in records
        ],
    )
    return (
        git_auth.HistoricalReconciliationPackage(
            package_root=package_root,
            execution_id=execution_id,
            evidence_class=(
                git_auth.PAIR_READY_RESIDUAL_RECONCILIATION_EVIDENCE_CLASS
            ),
            expected_file_count=5,
            expected_inventory_sha256=digest,
            execution_directories=(execution_id,),
            files=records,
        ),
        targets,
    )


def _enumerate_migration(root: Path, package, tracked=()):
    return git_auth.enumerate_historical_migration_evidence(
        repository_root=root,
        historical_migration_packages=(package,),
        tracked_operator_runs_paths=set(tracked),
    )


def _enumerate_reconciliation(root: Path, package, tracked=()):
    return git_auth.enumerate_historical_reconciliation_evidence(
        repository_root=root,
        historical_reconciliation_packages=(package,),
        tracked_operator_runs_paths=set(tracked),
    )


class FullShapePositiveProofTests(unittest.TestCase):
    def test_full_60_file_evidence_shape_passes_canonical_pre_marker_validation(self) -> None:
        full = _FullShapeFixture()
        try:
            payload, manifest_path, manifest_sha256 = full.manifest()
            prepared = full.validate_prebuilt(manifest_path, manifest_sha256)
            current = {item["path"] for item in payload["files"]}
            historical_authorization = {
                item["path"]
                for item in payload["historical_authorization_evidence"]
            }
            historical_migration = {
                item["path"]
                for item in payload[git_auth.HISTORICAL_MIGRATION_EVIDENCE_KEY]
            }
            historical_reconciliation = {
                item["path"]
                for item in git_auth.enumerate_historical_reconciliation_evidence(
                    repository_root=full.repo,
                    historical_reconciliation_packages=(
                        full.profile.historical_reconciliation_packages
                    ),
                    tracked_operator_runs_paths=set(),
                )
            }

            self.assertEqual(len(current), 2)
            self.assertEqual(len(historical_authorization), 1)
            self.assertEqual(len(historical_migration), 50)
            self.assertEqual(len(historical_reconciliation), 12)
            self.assertEqual(prepared.file_count, 65)
            self.assertEqual(
                set(prepared.allowed_untracked_paths),
                current
                | historical_authorization
                | historical_migration
                | historical_reconciliation,
            )
            self.assertTrue(
                any(
                    item["package_kind"] == git_auth.MIGRATION_062_PACKAGE_KIND
                    for item in payload["files"]
                )
            )
            self.assertTrue(
                any(
                    item["evidence_class"]
                    == git_auth.HISTORICAL_MIGRATION_058_EVIDENCE_CLASS
                    for item in payload[git_auth.HISTORICAL_MIGRATION_EVIDENCE_KEY]
                )
            )
            self.assertTrue(
                any(
                    path.startswith(
                        f"{git_auth.PAIR_READY_RESIDUAL_RECONCILIATION_PACKAGE_ROOT}/"
                    )
                    for path in historical_reconciliation
                )
            )
            self.assertFalse(current & historical_migration)
            self.assertFalse(current & historical_reconciliation)
        finally:
            full.close()


class CurrentMigration061NegativeProofTests(unittest.TestCase):
    def _post_manifest_failure(self, mutation) -> None:
        full = _FullShapeFixture()
        try:
            _payload, manifest_path, manifest_sha256 = full.manifest()
            mutation(full)
            with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                full.validate_prebuilt(manifest_path, manifest_sha256)
        finally:
            full.close()

    def test_current_package_mutation_matrix_fails_closed(self) -> None:
        def current_file(full: _FullShapeFixture) -> Path:
            return (
                full.fixture.migration_root
                / "migration_061_application_result.json"
            )

        mutations = {
            "missing-current-059": lambda full: current_file(full).unlink(),
            "modified-current-059": lambda full: current_file(full).write_bytes(
                b"modified-current-059\n"
            ),
            "extra-current-059": lambda full: _write_bytes(
                full.fixture.migration_root, "extra.json", b"extra\n"
            ),
            "historical-reconciliation-member-inside-current": lambda full: (
                _write_bytes(
                    full.fixture.migration_root,
                    "reconciliation_receipt.json",
                    b"pair-ready-copy\n",
                )
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                self._post_manifest_failure(mutation)

    def test_wrong_current_execution_id_fails_before_manifest_preparation(self) -> None:
        full = _FullShapeFixture()
        try:
            document = json.loads(full.fixture.authorization_path.read_text())
            document["migration_execution_id"] = "MIGRATION_061_WRONG"
            full.fixture.authorization_path.write_text(
                json.dumps(document, indent=2, sort_keys=True) + "\n"
            )
            full.fixture.authorization_sha256 = _sha(
                full.fixture.authorization_path
            )
            with self.assertRaises(Exception):
                full.manifest()
        finally:
            full.close()

    def test_058_cannot_substitute_for_059_current_equality(self) -> None:
        m059 = "operator-runs/current-059/EXEC/current.json"
        auth = "operator-runs/auth/AUTH/final_authorization.json"
        hm058 = "operator-runs/historical-058/EXEC/evidence.json"
        cases = {
            "058-substituted-for-current": {hm058, auth},
            "current-inventory-contains-only-058": {hm058, auth},
            "manifest-claims-059-filesystem-only-058": {hm058, auth},
        }
        for name, inventory in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                    git_auth._reconcile_evidence_sets(
                        current_manifest_paths={m059, auth},
                        historical_paths=set(),
                        historical_migration_paths={hm058},
                        historical_reconciliation_paths=set(),
                        visible_paths={auth},
                        ignored_paths={hm058},
                        tracked_paths=set(),
                        inventory_paths=inventory,
                        current_package_roots=(
                            "operator-runs/current-059/EXEC",
                            "operator-runs/auth/AUTH",
                        ),
                        sidecar_untracked_paths=(),
                    )


class HistoricalMigration058NegativeProofTests(unittest.TestCase):
    def test_exact_eleven_member_negative_matrix(self) -> None:
        cases = (
            "missing",
            "modified",
            "extra",
            "wrong-execution",
            "sibling-execution",
            "tracked-substitution",
            "symlink",
            "non-regular",
            "digest-mismatch",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                package, targets = _synthetic_migration_058(root)
                tracked: set[str] = set()
                if case == "missing":
                    targets[0].unlink()
                elif case == "modified":
                    targets[0].write_bytes(b"changed\n")
                elif case == "extra":
                    _write_bytes(targets[0].parent, "extra.json", b"extra\n")
                elif case == "wrong-execution":
                    package = replace(package, execution_id="MIGRATION_058_WRONG")
                elif case == "sibling-execution":
                    _write_bytes(
                        root,
                        f"{package.package_root}/MIGRATION_058_SIBLING/evidence.json",
                        b"sibling\n",
                    )
                elif case == "tracked-substitution":
                    tracked.add(targets[0].relative_to(root).as_posix())
                elif case == "symlink":
                    (targets[0].parent / "alias.json").symlink_to(targets[0])
                elif case == "non-regular":
                    os.mkfifo(targets[0].parent / "member.fifo")
                elif case == "digest-mismatch":
                    package = replace(
                        package, expected_inventory_sha256="a" * 64
                    )
                with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                    _enumerate_migration(root, package, tracked)

    def test_historical_058_path_cannot_satisfy_current_manifest(self) -> None:
        path = "operator-runs/migration-058/EXEC/evidence.json"
        with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
            git_auth._reconcile_evidence_sets(
                current_manifest_paths={path},
                historical_paths=set(),
                historical_migration_paths={path},
                historical_reconciliation_paths=set(),
                visible_paths={path},
                ignored_paths=set(),
                tracked_paths=set(),
                inventory_paths={path},
                current_package_roots=(
                    "operator-runs/migration-059/EXEC",
                    "operator-runs/auth/AUTH",
                ),
                sidecar_untracked_paths=(),
            )


class PairReadyNegativeProofTests(unittest.TestCase):
    def test_exact_five_member_negative_matrix(self) -> None:
        cases = (
            "missing",
            "modified-byte",
            "size-changed",
            "path-renamed",
            "extra-sixth-file",
            "sibling-execution",
            "evidence-class-mismatch",
            "execution-id-mismatch",
            "symlink",
            "non-regular",
            "tracked-substitution",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                package, targets = _synthetic_pair_ready(root)
                tracked: set[str] = set()
                if case == "missing":
                    targets[0].unlink()
                elif case == "modified-byte":
                    data = targets[0].read_bytes()
                    targets[0].write_bytes(b"X" + data[1:])
                elif case == "size-changed":
                    targets[0].write_bytes(targets[0].read_bytes() + b"X")
                elif case == "path-renamed":
                    targets[0].rename(targets[0].with_name("renamed.json"))
                elif case == "extra-sixth-file":
                    _write_bytes(targets[0].parent, "sixth.json", b"sixth\n")
                elif case == "sibling-execution":
                    _write_bytes(
                        root,
                        f"{package.package_root}/RECONCILIATION_SIBLING/evidence.json",
                        b"sibling\n",
                    )
                elif case == "evidence-class-mismatch":
                    package = replace(package, evidence_class="WRONG_CLASS")
                elif case == "execution-id-mismatch":
                    package = replace(package, execution_id="WRONG_EXECUTION")
                elif case == "symlink":
                    (targets[0].parent / "alias.json").symlink_to(targets[0])
                elif case == "non-regular":
                    os.mkfifo(targets[0].parent / "member.fifo")
                elif case == "tracked-substitution":
                    tracked.add(targets[0].relative_to(root).as_posix())
                with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                    _enumerate_reconciliation(root, package, tracked)

    def test_pair_ready_overlap_matrix_fails_closed(self) -> None:
        path = "operator-runs/pair-ready/EXEC/member.json"
        overlaps = {
            "hr-overlaps-current": ({path}, set(), set()),
            "hr-overlaps-ha": (set(), {path}, set()),
            "hr-overlaps-hm": (set(), set(), {path}),
        }
        for name, (current, historical, migration) in overlaps.items():
            with self.subTest(name=name):
                with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                    git_auth._reconcile_evidence_sets(
                        current_manifest_paths=current,
                        historical_paths=historical,
                        historical_migration_paths=migration,
                        historical_reconciliation_paths={path},
                        visible_paths=current,
                        ignored_paths={path},
                        tracked_paths=set(),
                        inventory_paths={path},
                        current_package_roots=(
                            "operator-runs/current/EXEC",
                            "operator-runs/auth/AUTH",
                        ),
                        sidecar_untracked_paths=(),
                    )

    def test_pair_ready_class_carries_no_current_or_authorization_authority(self) -> None:
        evidence_class = (
            git_auth.PAIR_READY_RESIDUAL_RECONCILIATION_EVIDENCE_CLASS
        )
        self.assertNotIn(evidence_class, git_auth._NON_RECONCILIATION_EVIDENCE_CLASSES)
        self.assertNotEqual(evidence_class, git_auth.MIGRATION_059_PACKAGE_KIND)
        self.assertNotEqual(evidence_class, git_auth.AUTHORIZATION_PACKAGE_KIND)
        self.assertNotIn("AUTHORIZATION", evidence_class)


class GlobalNamespaceNegativeProofTests(unittest.TestCase):
    def _base(self) -> dict[str, object]:
        current = {
            "operator-runs/current/EXEC/current.json",
            "operator-runs/auth/AUTH/final_authorization.json",
        }
        historical = {"operator-runs/history/OLD/final_authorization.json"}
        migration = {"operator-runs/hm/EXEC/evidence.json"}
        reconciliation = {"operator-runs/hr/EXEC/evidence.json"}
        return {
            "current_manifest_paths": current,
            "historical_paths": historical,
            "historical_migration_paths": migration,
            "historical_reconciliation_paths": reconciliation,
            "visible_paths": set(current),
            "ignored_paths": historical | migration | reconciliation,
            "tracked_paths": set(),
            "inventory_paths": current | historical | migration | reconciliation,
            "current_package_roots": (
                "operator-runs/current/EXEC",
                "operator-runs/auth/AUTH",
            ),
            "sidecar_untracked_paths": (),
        }

    def test_global_namespace_matrix_fails_closed(self) -> None:
        cases = (
            "unrelated-visible",
            "unrelated-ignored",
            "unknown-prefix-file",
            "duplicate-across-classes",
            "tracked-current-overlap",
            "expected-path-absent-inventory",
            "filesystem-file-outside-union",
            "current-inventory-not-manifest",
        )
        for case in cases:
            with self.subTest(case=case):
                kwargs = self._base()
                if case == "unrelated-visible":
                    path = "operator-runs/unrelated/visible.json"
                    kwargs["visible_paths"].add(path)
                    kwargs["inventory_paths"].add(path)
                elif case == "unrelated-ignored":
                    path = "operator-runs/unrelated/ignored.json"
                    kwargs["ignored_paths"].add(path)
                    kwargs["inventory_paths"].add(path)
                elif case == "unknown-prefix-file":
                    path = "operator-runs/hm/EXEC_SIBLING/evidence.json"
                    kwargs["ignored_paths"].add(path)
                    kwargs["inventory_paths"].add(path)
                elif case == "duplicate-across-classes":
                    path = next(iter(kwargs["historical_migration_paths"]))
                    kwargs["historical_reconciliation_paths"].add(path)
                elif case == "tracked-current-overlap":
                    kwargs["tracked_paths"].add(
                        next(iter(kwargs["current_manifest_paths"]))
                    )
                elif case == "expected-path-absent-inventory":
                    kwargs["inventory_paths"].remove(
                        next(iter(kwargs["historical_migration_paths"]))
                    )
                elif case == "filesystem-file-outside-union":
                    kwargs["inventory_paths"].add(
                        "operator-runs/filesystem-only/evidence.json"
                    )
                elif case == "current-inventory-not-manifest":
                    path = "operator-runs/current/EXEC/extra.json"
                    kwargs["inventory_paths"].add(path)
                    kwargs["visible_paths"].add(path)
                with self.assertRaises(git_auth.GitProvenanceAuthorizationError):
                    git_auth._reconcile_evidence_sets(**kwargs)


class WrapperConsumptionRegressionProofTests(unittest.TestCase):
    def test_failed_child_consumes_once_without_retry_or_successor(self) -> None:
        fixture = OperationalFixture()
        try:
            application_root = fixture.root / "applications"
            python_executable = fixture.make_fake_venv_python()
            first = _Launcher(returncode=3)
            arguments = {
                "authorization_file": fixture.authorization_path,
                "authorization_sha256": fixture.authorization_sha256,
                "operator_approved": True,
                "repository_root": fixture.repo,
                "application_root": application_root,
                "python_executable": python_executable,
                "environ": {"PATH": "/usr/bin"},
                "process_launcher": first,
                "migration_ledger_guard": lambda **_: None,
                "zero_state_gate": lambda **_: {
                    "zero_state_ready": True,
                    "blockers": [],
                },
            }
            with _patched_profile(fixture.profile):
                terminal = operational.apply_authorization_once(**arguments)
            self.assertEqual(len(first.calls), 1)
            self.assertEqual(terminal["child_exit_code"], 3)
            self.assertEqual(
                terminal["terminal_classification"], "CHILD_EXITED_NONZERO"
            )
            self.assertIs(terminal["child_terminal_envelope"]["success"], False)
            for field in (
                "automatic_retries",
                "manual_reruns",
                "resumes",
                "restarts",
                "successors",
            ):
                self.assertEqual(terminal[field], 0, field)

            marker = (
                application_root
                / fixture.authorization_id
                / "application-marker.json"
            )
            self.assertTrue(marker.is_file())
            second = _Launcher()
            arguments["process_launcher"] = second
            with _patched_profile(fixture.profile), self.assertRaises(
                operational.FourTokenStandardFourHourOneShotWrapperError
            ):
                operational.apply_authorization_once(**arguments)
            self.assertEqual(second.calls, [])
        finally:
            fixture.close()


class ProfileScopeProofTests(unittest.TestCase):
    def test_only_four_token_profiles_receive_062_history_and_pair_ready(self) -> None:
        pair_root = git_auth.PAIR_READY_RESIDUAL_RECONCILIATION_PACKAGE_ROOT
        for profile in (
            git_auth.FOUR_TOKEN_PROOF_AUTHORIZATION_PROFILE,
            git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        ):
            with self.subTest(mode=profile.command_mode):
                self.assertEqual(
                    profile.migration_package_root,
                    git_auth.MIGRATION_062_PACKAGE_ROOT,
                )
                self.assertEqual(
                    profile.migration_package_kind,
                    git_auth.MIGRATION_062_PACKAGE_KIND,
                )
                self.assertIn(
                    git_auth.MIGRATION_059_PACKAGE_ROOT,
                    {item.package_root for item in profile.historical_migration_packages},
                )
                self.assertIn(
                    git_auth.MIGRATION_061_PACKAGE_ROOT,
                    {item.package_root for item in profile.historical_migration_packages},
                )
                self.assertIn(
                    pair_root,
                    {
                        item.package_root
                        for item in profile.historical_reconciliation_packages
                    },
                )

        for profile in (
            git_auth.ORDINARY_AUTHORIZATION_PROFILE,
            git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        ):
            with self.subTest(mode=profile.command_mode):
                self.assertEqual(profile.historical_migration_packages, ())
                self.assertEqual(profile.historical_reconciliation_packages, ())
                self.assertNotEqual(
                    profile.migration_package_root,
                    git_auth.MIGRATION_062_PACKAGE_ROOT,
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
