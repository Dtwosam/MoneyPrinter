"""Focused bounded proof for the pre-authorization migration-ledger drift guard.

Every database in this module is disposable. The authoritative database is only
ever *observed*: its hash, size, inode, and mtime are captured once at class
setup and re-asserted at teardown, so any accidental mutation fails the suite.
No package, marker, campaign, provider, Scheduler, memory, or financial surface
is exercised anywhere here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

from printer_v1.db import migrate as migration_runner
from printer_v1.db.migrate import (
    apply_migrations,
    canonical_migration_digest,
    canonical_migration_names,
    describe_canonical_catalogue_issues,
    ordered_name_digest,
    parse_migration_ordinal,
)
from printer_v1.operator_cli import pre_authorization_migration_ledger_guard as guard
from printer_v1.operator_cli import window_15m_one_shot_wrapper as wrapper
from printer_v1.operator_db.paths import get_default_db_path


AUTHORITATIVE_DB = get_default_db_path()
WRAPPER_TEST_PATH = Path(__file__).with_name("test_v2_9_8b_window_15m_one_shot_wrapper.py")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity(path: Path) -> dict[str, object]:
    info = path.stat()
    return {
        "sha256": _sha(path),
        "size": info.st_size,
        "inode": info.st_ino,
        "mtime_ns": info.st_mtime_ns,
    }


def _load_wrapper_fixture():
    """Load the existing wrapper test fixture without depending on sys.path."""
    spec = importlib.util.spec_from_file_location(
        "_wrapper_fixture_module", WRAPPER_TEST_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AuthoritativeDatabaseUntouched(unittest.TestCase):
    """Base class asserting the authoritative database is never mutated."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.authoritative_before = _identity(AUTHORITATIVE_DB)

    @classmethod
    def tearDownClass(cls) -> None:
        after = _identity(AUTHORITATIVE_DB)
        assert after == cls.authoritative_before, (
            "authoritative database changed during a read-only guard test: "
            f"before={cls.authoritative_before} after={after}"
        )


class DisposableCatalogue:
    """Build a disposable migrations directory with arbitrary file names."""

    def __init__(self, root: Path, names) -> None:
        self.dir = root
        self.dir.mkdir(parents=True, exist_ok=True)
        for name in names:
            (self.dir / name).write_text("SELECT 1;\n", encoding="utf-8")


def _disposable_db(path: Path, ledger, *, allow_duplicates: bool = False) -> Path:
    """Build a disposable ledger database.

    ``allow_duplicates`` drops the primary key so a corrupted ledger holding the
    same migration twice can be represented. A healthy ledger cannot reach that
    state, which is precisely why the guard must still detect it.
    """
    connection = sqlite3.connect(path)
    try:
        version_column = "version TEXT" if allow_duplicates else "version TEXT PRIMARY KEY"
        connection.execute(
            "CREATE TABLE printer_schema_migrations ("
            f"{version_column}, applied_at TEXT NOT NULL "
            "DEFAULT (datetime('now')))"
        )
        for name in ledger:
            connection.execute(
                "INSERT INTO printer_schema_migrations (version) VALUES (?)", (name,)
            )
        connection.commit()
    finally:
        connection.close()
    return path


class CanonicalCatalogueTests(AuthoritativeDatabaseUntouched):
    def test_live_catalogue_is_valid_and_ends_at_052(self) -> None:
        names = canonical_migration_names()
        self.assertEqual(describe_canonical_catalogue_issues(names), [])
        self.assertEqual(len(names), 52)
        self.assertEqual(names[-1], "052_memory_observation_eligibility_layers.sql")

    def test_ordinals_are_contiguous_from_one(self) -> None:
        ordinals = [parse_migration_ordinal(name) for name in canonical_migration_names()]
        self.assertEqual(ordinals, list(range(1, 53)))

    def test_ordered_name_digest_is_order_sensitive(self) -> None:
        names = list(canonical_migration_names())
        swapped = names[:-2] + [names[-1], names[-2]]
        self.assertNotEqual(ordered_name_digest(names), ordered_name_digest(swapped))
        self.assertEqual(canonical_migration_digest(), ordered_name_digest(names))

    def test_malformed_filenames_are_rejected(self) -> None:
        for bad in (
            "1_short_ordinal.sql",
            "001_Upper_Case.sql",
            "001_double__underscore.sql",
            "001_trailing_.sql",
            "001-dash-separator.sql",
            "001_missing_suffix.txt",
            "no_ordinal_at_all.sql",
        ):
            with self.subTest(name=bad):
                issues = describe_canonical_catalogue_issues([bad])
                self.assertTrue(issues)
                self.assertIn("malformed", issues[0])

    def test_invalid_sequences_are_rejected(self) -> None:
        cases = {
            "gap": ["001_a.sql", "003_c.sql"],
            "not_one_based": ["002_b.sql", "003_c.sql"],
            "duplicate_ordinal": ["001_a.sql", "001_b.sql"],
        }
        for label, names in cases.items():
            with self.subTest(case=label):
                self.assertTrue(describe_canonical_catalogue_issues(names))

    def test_catalogue_loader_fails_closed_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            DisposableCatalogue(root / "bad", ["001_a.sql", "004_d.sql"])
            with self.assertRaises(RuntimeError):
                canonical_migration_names(root / "bad")


class GuardBlockerTests(AuthoritativeDatabaseUntouched):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.canonical = list(canonical_migration_names())

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def evaluate(self, ledger, *, migrations_dir=None, mode="prepare", binding=None):
        db = _disposable_db(self.root / f"{mode}-{len(os.listdir(self.root))}.sqlite3", ledger)
        return guard.evaluate_migration_ledger_drift(
            mode=mode,
            db_path=db,
            migrations_dir=migrations_dir,
            package_binding=binding,
        )

    def test_canonical_matching_ledger_without_objects_blocks(self) -> None:
        result = self.evaluate(self.canonical)
        self.assertEqual(result.status, "BLOCKED", result.summary())
        self.assertIn("required_schema_object_missing", result.blocker_codes)

    def test_real_migrated_database_passes(self) -> None:
        db = self.root / "fully-migrated.sqlite3"
        apply_migrations(db)
        result = guard.evaluate_migration_ledger_drift(mode="prepare", db_path=db)
        self.assertEqual(result.status, "PASS", result.summary())
        self.assertEqual(
            result.database["ledger_digest"], canonical_migration_digest()
        )

    def test_missing_migration_blocks(self) -> None:
        result = self.evaluate(self.canonical[:-1])
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("migration_ledger_missing", result.blocker_codes)
        self.assertIn("migration_head_mismatch", result.blocker_codes)
        self.assertIn(
            "061_standard_4h_progression_fault_preservation.sql", result.summary()
        )

    def test_unexpected_migration_blocks(self) -> None:
        result = self.evaluate([*self.canonical, "053_not_in_repository.sql"])
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("migration_ledger_unexpected", result.blocker_codes)

    def test_duplicate_migration_blocks(self) -> None:
        db = _disposable_db(
            self.root / "duplicate.sqlite3",
            [*self.canonical, self.canonical[-1]],
            allow_duplicates=True,
        )
        result = guard.evaluate_migration_ledger_drift(mode="prepare", db_path=db)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("migration_ledger_duplicate", result.blocker_codes)
        self.assertIn("migration_count_mismatch", result.blocker_codes)

    def test_reordered_ledger_blocks(self) -> None:
        reordered = list(self.canonical)
        reordered[-1], reordered[-2] = reordered[-2], reordered[-1]
        result = self.evaluate(reordered)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("migration_ledger_out_of_order", result.blocker_codes)

    def test_non_prefix_ledger_blocks(self) -> None:
        # Correct head, no duplicates, no unexpected names — but a hole in the
        # middle means the ledger is not an ordered prefix of the catalogue.
        non_prefix = [*self.canonical[:-2], self.canonical[-1]]
        db = _disposable_db(self.root / "non-prefix.sqlite3", non_prefix)
        result = guard.evaluate_migration_ledger_drift(mode="prepare", db_path=db)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("migration_ledger_out_of_order", result.blocker_codes)
        self.assertIn("migration_ledger_missing", result.blocker_codes)

    def test_head_mismatch_blocks(self) -> None:
        shifted = list(self.canonical[:-1])
        result = self.evaluate(shifted)
        self.assertEqual(result.status, "BLOCKED")
        head = [
            item for item in result.blockers if item["code"] == "migration_head_mismatch"
        ]
        self.assertTrue(head)
        self.assertIn(
            "060_pre_admission_frozen_tracking_lane_provenance.sql",
            head[0]["detail"],
        )

    def test_empty_ledger_blocks(self) -> None:
        result = self.evaluate([])
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("migration_ledger_empty", result.blocker_codes)

    def test_absent_ledger_table_blocks(self) -> None:
        db = self.root / "no-ledger.sqlite3"
        connection = sqlite3.connect(db)
        connection.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
        connection.commit()
        connection.close()
        result = guard.evaluate_migration_ledger_drift(mode="prepare", db_path=db)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("migration_ledger_absent", result.blocker_codes)

    def test_invalid_canonical_catalogue_blocks(self) -> None:
        DisposableCatalogue(self.root / "gapped", ["001_a.sql", "004_d.sql"])
        result = self.evaluate(self.canonical, migrations_dir=self.root / "gapped")
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("canonical_catalogue_invalid", result.blocker_codes)

    def test_malformed_catalogue_filename_blocks(self) -> None:
        DisposableCatalogue(self.root / "malformed", ["001_ok.sql", "002_Bad_Name.sql"])
        result = self.evaluate(self.canonical, migrations_dir=self.root / "malformed")
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("canonical_catalogue_invalid", result.blocker_codes)

    def test_integrity_failure_blocks(self) -> None:
        db = self.root / "corrupt.sqlite3"
        _disposable_db(db, self.canonical)
        raw = bytearray(db.read_bytes())
        # Corrupt well past the header so the file still opens but fails checks.
        for offset in range(2048, min(len(raw), 6144)):
            raw[offset] = raw[offset] ^ 0xFF
        db.write_bytes(bytes(raw))
        result = guard.evaluate_migration_ledger_drift(mode="prepare", db_path=db)
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(
            {"database_integrity", "database_unavailable"} & set(result.blocker_codes),
            result.blocker_codes,
        )

    def test_foreign_key_violation_blocks(self) -> None:
        db = self.root / "fk.sqlite3"
        _disposable_db(db, self.canonical)
        connection = sqlite3.connect(db)
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
            connection.execute(
                "CREATE TABLE child (id INTEGER PRIMARY KEY, "
                "parent_id INTEGER REFERENCES parent(id))"
            )
            connection.execute("INSERT INTO child (id, parent_id) VALUES (1, 999)")
            connection.commit()
        finally:
            connection.close()
        result = guard.evaluate_migration_ledger_drift(mode="prepare", db_path=db)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("foreign_key_violations", result.blocker_codes)

    def test_sidecars_block_before_any_open(self) -> None:
        db = self.root / "sidecar.sqlite3"
        _disposable_db(db, self.canonical)
        Path(f"{db}-wal").write_bytes(b"")
        result = guard.evaluate_migration_ledger_drift(mode="prepare", db_path=db)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("database_unavailable", result.blocker_codes)
        self.assertIn("sidecar", result.summary().lower())

    def test_missing_database_blocks(self) -> None:
        result = guard.evaluate_migration_ledger_drift(
            mode="prepare", db_path=self.root / "absent.sqlite3"
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("database_unavailable", result.blocker_codes)

    def test_unknown_mode_is_rejected(self) -> None:
        with self.assertRaises(guard.MigrationLedgerDriftGuardError):
            guard.evaluate_migration_ledger_drift(mode="consume")

    def test_assert_helper_raises_on_block(self) -> None:
        db = _disposable_db(self.root / "assert.sqlite3", self.canonical[:-1])
        with self.assertRaises(guard.MigrationLedgerDriftGuardError):
            guard.assert_migration_ledger_ready(mode="prepare", db_path=db)

    def test_inspection_creates_no_sidecars(self) -> None:
        db = _disposable_db(self.root / "quiet.sqlite3", self.canonical)
        before = _identity(db)
        guard.evaluate_migration_ledger_drift(mode="prepare", db_path=db)
        self.assertEqual(_identity(db), before)
        self.assertEqual(guard.present_sidecars(db), [])


class ReviewModeTests(AuthoritativeDatabaseUntouched):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.canonical = list(canonical_migration_names())
        self.db = self.root / "review.sqlite3"
        apply_migrations(self.db)
        info = self.db.stat()
        self.honest = {
            "path": str(self.db),
            "migration_count": len(self.canonical),
            "migration_head": self.canonical[-1],
            "sha256": _sha(self.db),
            "size": info.st_size,
            "inode": info.st_ino,
            "mtime_ns": info.st_mtime_ns,
        }

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def review(self, binding):
        return guard.evaluate_migration_ledger_drift(
            mode="review", db_path=self.db, package_binding=binding
        )

    def test_honest_package_passes_review(self) -> None:
        result = self.review(self.honest)
        self.assertEqual(result.status, "PASS", result.summary())
        self.assertTrue(result.package_binding["honest"])

    def test_dishonest_head_rejected(self) -> None:
        binding = dict(self.honest, migration_head="051_permanent_discovery_availability.sql")
        result = self.review(binding)
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("package_binding_dishonest", result.blocker_codes)

    def test_dishonest_count_rejected(self) -> None:
        result = self.review(dict(self.honest, migration_count=51))
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("package_binding_dishonest", result.blocker_codes)

    def test_dishonest_hash_rejected(self) -> None:
        result = self.review(dict(self.honest, sha256="0" * 64))
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("package_binding_dishonest", result.blocker_codes)

    def test_dishonest_size_rejected(self) -> None:
        result = self.review(dict(self.honest, size=1))
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("package_binding_dishonest", result.blocker_codes)

    def test_dishonest_path_rejected(self) -> None:
        result = self.review(dict(self.honest, path=str(self.root / "elsewhere.sqlite3")))
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("package_binding_dishonest", result.blocker_codes)

    def test_dishonest_inode_rejected(self) -> None:
        result = self.review(dict(self.honest, inode=self.honest["inode"] + 1))
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("package_binding_dishonest", result.blocker_codes)
        self.assertIn("inode", result.summary())

    def test_dishonest_mtime_ns_rejected(self) -> None:
        result = self.review(dict(self.honest, mtime_ns=self.honest["mtime_ns"] - 1))
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("package_binding_dishonest", result.blocker_codes)
        self.assertIn("mtime_ns", result.summary())

    def test_non_canonical_head_claim_rejected(self) -> None:
        db = _disposable_db(self.root / "claim.sqlite3", ["999_invented.sql"])
        info = db.stat()
        result = guard.evaluate_migration_ledger_drift(
            mode="review",
            db_path=db,
            package_binding={
                "path": str(db),
                "migration_count": 1,
                "migration_head": "999_invented.sql",
                "sha256": _sha(db),
                "size": info.st_size,
                "inode": info.st_ino,
                "mtime_ns": info.st_mtime_ns,
            },
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("package_binding_dishonest", result.blocker_codes)

    def test_every_binding_field_is_required(self) -> None:
        for field_name in guard.PACKAGE_BINDING_FIELDS:
            with self.subTest(field=field_name):
                binding = dict(self.honest)
                binding.pop(field_name)
                result = self.review(binding)
                self.assertEqual(result.status, "BLOCKED")
                self.assertTrue(
                    {
                        "package_binding_incomplete",
                        "package_binding_invalid",
                    } & set(result.blocker_codes),
                    result.blocker_codes,
                )
                self.assertIn(field_name, result.summary())

    def test_incomplete_binding_rejected(self) -> None:
        binding = dict(self.honest)
        binding.pop("migration_head")
        result = self.review(binding)
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(
            {
                "package_binding_incomplete",
                "package_binding_invalid",
            } & set(result.blocker_codes),
            result.blocker_codes,
        )

    def test_binding_fields_cover_the_required_contract(self) -> None:
        self.assertEqual(
            set(guard.PACKAGE_BINDING_FIELDS),
            {
                "path",
                "sha256",
                "size",
                "inode",
                "mtime_ns",
                "migration_count",
                "migration_head",
            },
        )

    def test_review_still_checks_health_and_ledger_independently(self) -> None:
        """Requirement 5: an honest binding does not bypass independent checks."""
        drifted = _disposable_db(self.root / "drifted.sqlite3", self.canonical[:-1])
        info = drifted.stat()
        honest_about_drift = {
            "path": str(drifted),
            "migration_count": len(self.canonical) - 1,
            "migration_head": self.canonical[-2],
            "sha256": _sha(drifted),
            "size": info.st_size,
            "inode": info.st_ino,
            "mtime_ns": info.st_mtime_ns,
        }
        result = guard.evaluate_migration_ledger_drift(
            mode="review", db_path=drifted, package_binding=honest_about_drift
        )
        # The package tells the truth, and the truth is still drift.
        self.assertEqual(result.status, "BLOCKED")
        self.assertTrue(result.package_binding["honest"])
        self.assertIn("migration_ledger_missing", result.blocker_codes)
        self.assertIn("migration_head_mismatch", result.blocker_codes)

    def test_sidecars_block_review_even_with_matching_binding(self) -> None:
        Path(f"{self.db}-journal").write_bytes(b"")
        try:
            result = self.review(self.honest)
        finally:
            Path(f"{self.db}-journal").unlink()
        self.assertEqual(result.status, "BLOCKED")
        self.assertIn("database_unavailable", result.blocker_codes)

    def test_binding_loader_reads_existing_schema_unchanged(self) -> None:
        package = self.root / "final_authorization.json"
        package.write_text(
            json.dumps({guard.PACKAGE_DB_BINDING_KEY: self.honest}), encoding="utf-8"
        )
        self.assertEqual(guard.load_package_binding(package), self.honest)

    def test_binding_loader_rejects_package_without_binding(self) -> None:
        package = self.root / "no_binding.json"
        package.write_text(json.dumps({"authorization_id": "X"}), encoding="utf-8")
        with self.assertRaises(guard.MigrationLedgerDriftGuardError):
            guard.load_package_binding(package)

    def test_review_mode_requires_package_file_in_cli(self) -> None:
        self.assertEqual(guard.main(["review"]), 3)


class CliTests(AuthoritativeDatabaseUntouched):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.canonical = list(canonical_migration_names())

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_prepare_cli_returns_zero_on_pass(self) -> None:
        db = _disposable_db(self.root / "ok.sqlite3", self.canonical)
        self.assertEqual(guard.main(["prepare", "--db-path", str(db)]), 0)

    def test_prepare_cli_returns_three_on_block(self) -> None:
        db = _disposable_db(self.root / "drift.sqlite3", self.canonical[:-1])
        self.assertEqual(guard.main(["prepare", "--db-path", str(db)]), 3)

    def test_prepare_writes_no_package_directory_or_byte(self) -> None:
        """Requirement 3: prepare must block before anything is written."""
        workspace = self.root / "package-workspace"
        workspace.mkdir()
        db = _disposable_db(self.root / "blocked.sqlite3", self.canonical[:-1])

        before_tree = sorted(path.name for path in self.root.rglob("*"))
        cwd = os.getcwd()
        os.chdir(workspace)
        try:
            self.assertEqual(guard.main(["prepare", "--db-path", str(db)]), 3)
        finally:
            os.chdir(cwd)

        self.assertEqual(sorted(workspace.iterdir()), [])
        self.assertEqual(sorted(path.name for path in self.root.rglob("*")), before_tree)
        self.assertEqual(guard.present_sidecars(db), [])


class WrapperIntegrationTests(AuthoritativeDatabaseUntouched):
    """Prove the wrapper blocks before the authorization is consumed."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.fixture_module = _load_wrapper_fixture()

    def setUp(self) -> None:
        self.fx = self.fixture_module.Fixture()

    def tearDown(self) -> None:
        self.fx.close()

    def _apply(self, **overrides):
        params = dict(
            authorization_file=self.fx.authorization_path,
            authorization_sha256=self.fx.authorization_sha256,
            operator_approved=True,
            repository_root=self.fx.repo,
            application_root=self.fx.app,
            python_executable=self.fx.venv_python,
            created_at="2026-08-01T20:00:00+00:00",
            consumed_at="2026-08-01T20:01:00+00:00",
        )
        params.update(overrides)
        return wrapper.apply_authorization_once(**params)

    def test_drift_blocks_before_any_consumption_artifact(self) -> None:
        calls: list[dict] = []

        def blocking_guard(**kwargs):
            calls.append(kwargs)
            raise guard.MigrationLedgerDriftGuardError(
                "pre-authorization migration-ledger guard blocked: "
                "migration_ledger_missing: missing canonical migrations: "
                "['052_memory_observation_eligibility_layers.sql']"
            )

        launched: list[object] = []

        def launcher(**kwargs):
            launched.append(kwargs)
            return {"returncode": 0, "pid": 1}

        with self.assertRaises(wrapper.OneShotWrapperError) as caught:
            self._apply(migration_ledger_guard=blocking_guard, process_launcher=launcher)

        message = str(caught.exception)
        self.assertIn("blocked before consumption", message)
        self.assertIn("052_memory_observation_eligibility_layers.sql", message)
        self.assertEqual([item["mode"] for item in calls], ["review"])

        # Nothing was consumed: no application directory, no staging directory,
        # no manifest, no marker, no terminal, no child.
        self.assertEqual(launched, [])
        canonical_dir = Path(self.fx.app) / self.fx.authorization_id
        self.assertFalse(canonical_dir.exists())
        self.assertFalse((Path(self.fx.app) / ".staging").exists())
        produced = [
            path
            for path in Path(self.fx.app).rglob("*")
            if path.is_file()
        ]
        self.assertEqual(produced, [])

    def test_guard_runs_before_staging_and_passes_through(self) -> None:
        order: list[str] = []

        def passing_guard(**kwargs):
            order.append("guard")
            return guard.GuardResult(
                mode=kwargs.get("mode", "prepare"),
                status="PASS",
                verdict=guard.PASS_VERDICT,
            )

        def launcher(**kwargs):
            order.append("child")
            return {"returncode": 0, "pid": 4242}

        result = self._apply(
            migration_ledger_guard=passing_guard, process_launcher=launcher
        )
        self.assertEqual(order, ["guard", "child"])
        self.assertEqual(result["child_exit_code"], 0)

    def _assert_nothing_consumed(self) -> None:
        """No staging, manifest, application directory, marker, terminal, child."""
        canonical_dir = Path(self.fx.app) / self.fx.authorization_id
        self.assertFalse(canonical_dir.exists())
        self.assertFalse((Path(self.fx.app) / ".staging").exists())
        for name in (
            "git-provenance-manifest.json",
            "application-marker.json",
            "wrapper-terminal.json",
            "child-stdout.txt",
            "child-stderr.txt",
        ):
            self.assertEqual(list(Path(self.fx.app).rglob(name)), [], name)

    def _block_with_binding(self, binding, *, launched):
        def launcher(**kwargs):
            launched.append(kwargs)
            return {"returncode": 0, "pid": 1}

        document = json.loads(Path(self.fx.authorization_path).read_text("utf-8"))
        if binding is None:
            document.pop(guard.PACKAGE_DB_BINDING_KEY, None)
        else:
            document[guard.PACKAGE_DB_BINDING_KEY] = binding
        Path(self.fx.authorization_path).write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        self.fx.authorization_sha256 = hashlib.sha256(
            Path(self.fx.authorization_path).read_bytes()
        ).hexdigest()
        with self.assertRaises(wrapper.OneShotWrapperError) as caught:
            self._apply(
                authorization_sha256=self.fx.authorization_sha256,
                process_launcher=launcher,
            )
        return str(caught.exception)

    def _live_binding(self) -> dict:
        return dict(self.fixture_module.live_authoritative_database_binding())

    def test_wrapper_passes_exact_package_binding_in_review_mode(self) -> None:
        seen: list[dict] = []

        def recording_guard(**kwargs):
            seen.append(kwargs)
            return guard.GuardResult(
                mode=kwargs["mode"], status="PASS", verdict=guard.PASS_VERDICT
            )

        def launcher(**kwargs):
            return {"returncode": 0, "pid": 7}

        self._apply(migration_ledger_guard=recording_guard, process_launcher=launcher)

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["mode"], "review")
        document = json.loads(Path(self.fx.authorization_path).read_text("utf-8"))
        self.assertEqual(
            seen[0]["package_binding"], document[guard.PACKAGE_DB_BINDING_KEY]
        )
        # The binding actually pins every required field.
        self.assertEqual(
            set(seen[0]["package_binding"]), set(guard.PACKAGE_BINDING_FIELDS)
        )

    def test_matching_ledger_with_wrong_sha256_blocks_before_consumption(self) -> None:
        """A canonical 52/052 database is not enough: the file must be the one."""
        launched: list[object] = []
        binding = self._live_binding()
        self.assertEqual(binding["migration_count"], 52)
        self.assertEqual(
            binding["migration_head"], "052_memory_observation_eligibility_layers.sql"
        )
        binding["sha256"] = "0" * 64
        message = self._block_with_binding(binding, launched=launched)
        self.assertIn("blocked before consumption", message)
        self.assertIn("sha256", message)
        self.assertEqual(launched, [])
        self._assert_nothing_consumed()

    def test_matching_ledger_with_wrong_size_blocks_before_consumption(self) -> None:
        launched: list[object] = []
        binding = self._live_binding()
        binding["size"] = int(binding["size"]) + 1
        message = self._block_with_binding(binding, launched=launched)
        self.assertIn("size", message)
        self.assertEqual(launched, [])
        self._assert_nothing_consumed()

    def test_inode_mismatch_blocks_before_consumption(self) -> None:
        launched: list[object] = []
        binding = self._live_binding()
        binding["inode"] = int(binding["inode"]) + 1
        message = self._block_with_binding(binding, launched=launched)
        self.assertIn("inode", message)
        self.assertEqual(launched, [])
        self._assert_nothing_consumed()

    def test_mtime_ns_mismatch_blocks_before_consumption(self) -> None:
        launched: list[object] = []
        binding = self._live_binding()
        binding["mtime_ns"] = int(binding["mtime_ns"]) - 1
        message = self._block_with_binding(binding, launched=launched)
        self.assertIn("mtime_ns", message)
        self.assertEqual(launched, [])
        self._assert_nothing_consumed()

    def test_incomplete_package_binding_blocks_before_consumption(self) -> None:
        for field_name in guard.PACKAGE_BINDING_FIELDS:
            with self.subTest(field=field_name):
                self.fx.close()
                self.fx = self.fixture_module.Fixture()
                launched: list[object] = []
                binding = self._live_binding()
                binding.pop(field_name)
                message = self._block_with_binding(binding, launched=launched)
                self.assertIn("package_binding_incomplete", message)
                self.assertIn(field_name, message)
                self.assertEqual(launched, [])
                self._assert_nothing_consumed()

    def test_absent_package_binding_blocks_before_consumption(self) -> None:
        launched: list[object] = []
        message = self._block_with_binding(None, launched=launched)
        self.assertIn("authoritative_database", message)
        self.assertEqual(launched, [])
        self._assert_nothing_consumed()

    def test_honest_live_binding_passes_the_real_guard(self) -> None:
        """The unmodified fixture binds the live database and is consumed."""
        launched: list[object] = []

        def launcher(**kwargs):
            launched.append(kwargs)
            return {"returncode": 0, "pid": 11}

        result = self._apply(process_launcher=launcher)
        self.assertEqual(result["child_exit_code"], 0)
        self.assertEqual(len(launched), 1)

    def test_wrapper_default_guard_is_the_real_guard(self) -> None:
        import inspect

        signature = inspect.signature(wrapper.apply_authorization_once)
        self.assertIs(
            signature.parameters["migration_ledger_guard"].default,
            guard.assert_migration_ledger_ready,
        )


class OperationalPreflightUnchangedTests(AuthoritativeDatabaseUntouched):
    def test_operational_preflight_still_owns_the_final_migration_gate(self) -> None:
        from printer_v1.operator_cli import operational_memory_factory_command as command

        source = Path(command.__file__).read_text(encoding="utf-8")
        # The final defence must remain in place and independent of this guard.
        self.assertIn('_preflight_fail(\n            "migration_ledger",', source)
        self.assertIn("validate_migration_ledger(migrations)", source)
        self.assertNotIn("pre_authorization_migration_ledger_guard", source)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
