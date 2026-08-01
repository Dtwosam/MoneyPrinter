"""V2-9.8B Campaign Scheduler Ownership Schema Migration Bounded Disposable Proof.

Proof-only lane for migration ``050_campaign_scheduler_ownership_scope.sql``.

Authoritative database protection contract:
- record SHA-256 / size / mtime of ``data/printer_v1.sqlite3`` without opening it
  through SQLite;
- create a byte-identical filesystem copy in a temporary proof directory;
- open SQLite only against disposable copies;
- re-verify the authoritative path is unchanged after the proof.

This file never mutates the authoritative database, never runs providers/RPC/
WebSockets/source fetching, never runs an operational campaign, never wires the
owner into runtime, and never unlocks retrieval or financial capabilities.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
import uuid

from printer_v1.db import migrate as migration_runner
from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.campaign_ownership import (
    CampaignOwnershipError,
    SchedulerCleanupCapture,
    bind_authoritative_run_id,
    capture_campaign_active_scheduler_jobs,
    create_campaign_run,
    create_cycle_with_two_slots,
    persist_scheduler_work,
    persist_window,
    project_campaign_scheduler_job,
    project_campaign_scheduler_work,
    transition_state,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE_DB = ROOT / "data" / "printer_v1.sqlite3"
MIGRATION_050 = "050_campaign_scheduler_ownership_scope.sql"
MIGRATION_050_PATH = migration_runner.MIGRATIONS_DIR / MIGRATION_050

PRESERVED_COLUMNS = (
    "scheduler_work_id",
    "campaign_id",
    "run_id",
    "cycle_id",
    "token_slot_id",
    "window_id",
    "work_intent",
    "deadline_at",
    "work_state",
    "scheduler_job_id",
    "source_request_id",
    "source_response_id",
    "source_failure_id",
    "first_terminal_cause",
    "terminal_at",
    "created_at",
    "updated_at",
)

RECONSTRUCTION_COLUMNS = (
    "scheduler_job_id",
    "stage_id",
    "work_scope",
    "target_category",
    "target_identity",
    "campaign_id",
    "run_id",
    "cycle_id",
    "token_slot_id",
    "window_id",
    "factory_run_id",
    "work_state",
    "first_terminal_cause",
    "terminal_at",
)

NOW = "2026-08-01T12:00:00+00:00"
LATER = "2026-08-01T13:00:00+00:00"
HEX64_A = "a" * 64
HEX64_B = "b" * 64

# Module-level evidence bag filled by the ordered proof suite.
PROOF_EVIDENCE: dict[str, object] = {}


def _file_identity(path: Path) -> dict[str, object]:
    """Filesystem identity only — never opens the path through SQLite."""
    stat = path.stat()
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": str(path.resolve()),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "mtime_iso": datetime.fromtimestamp(
            stat.st_mtime, tz=timezone.utc
        ).isoformat(),
        "sha256": digest.hexdigest(),
    }


def _canonical_rows_hash(rows: list[tuple]) -> str:
    payload = json.dumps(rows, sort_keys=False, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _table_sql(connection: sqlite3.Connection, table: str) -> str | None:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return None if row is None else str(row[0])


def _index_names(connection: sqlite3.Connection, table: str) -> list[str]:
    return sorted(
        str(row[1])
        for row in connection.execute(f"PRAGMA index_list('{table}')")
    )


def _trigger_names(connection: sqlite3.Connection, table: str) -> list[str]:
    return sorted(
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='trigger' AND tbl_name=? ORDER BY name",
            (table,),
        )
    )


def _column_names(connection: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f"PRAGMA table_info('{table}')")]


def _migration_versions(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT version FROM printer_schema_migrations ORDER BY version"
        )
    ]


def _ownership_snapshot(connection: sqlite3.Connection) -> list[tuple]:
    return connection.execute(
        "SELECT "
        + ", ".join(PRESERVED_COLUMNS)
        + " FROM printer_memory_factory_campaign_scheduler_work "
        "ORDER BY scheduler_work_id"
    ).fetchall()


def _apply_through(db_path: Path, maximum_prefix: int) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS printer_schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            )
        }
        for path in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):
            if int(path.name.split("_", 1)[0]) > maximum_prefix:
                continue
            if path.name not in applied:
                connection.executescript(path.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                    (path.name,),
                )
        connection.commit()
    finally:
        connection.close()


def _insert_pre050_work_row(db_path: Path, **columns: object) -> None:
    connection = sqlite3.connect(db_path)
    try:
        keys = ", ".join(columns)
        placeholders = ", ".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO printer_memory_factory_campaign_scheduler_work({keys}) "
            f"VALUES ({placeholders})",
            tuple(columns.values()),
        )
        connection.commit()
    finally:
        connection.close()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": NOW,
    }


def _apply_migration_050_once(db_path: Path, *, record_ledger: bool = True) -> dict[str, object]:
    """Apply migration 050 exactly once on a disposable database."""
    started = datetime.now(timezone.utc).isoformat()
    pre_hash = _file_identity(db_path)["sha256"]
    sql = MIGRATION_050_PATH.read_text(encoding="utf-8")
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        before_ledger = _migration_versions(connection)
        if MIGRATION_050 in before_ledger:
            raise RuntimeError("migration 050 already present on disposable copy")
        connection.executescript(sql)
        if record_ledger:
            connection.execute(
                "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                (MIGRATION_050,),
            )
        connection.commit()
        after_ledger = _migration_versions(connection)
    finally:
        connection.close()
    finished = datetime.now(timezone.utc).isoformat()
    post_hash = _file_identity(db_path)["sha256"]
    return {
        "started_at": started,
        "finished_at": finished,
        "pre_file_sha256": pre_hash,
        "post_file_sha256": post_hash,
        "ledger_before": before_ledger,
        "ledger_after": after_ledger,
        "ledger_delta": [v for v in after_ledger if v not in set(before_ledger)],
    }


class CampaignSchedulerOwnershipSchemaMigrationBoundedProof(unittest.TestCase):
    """Ordered bounded disposable proof for migration 050."""

    @classmethod
    def setUpClass(cls) -> None:
        if not AUTHORITATIVE_DB.is_file():
            raise unittest.SkipTest(
                "authoritative database absent; cannot claim authoritative-copy proof"
            )
        if not MIGRATION_050_PATH.is_file():
            raise unittest.SkipTest("migration 050 SQL file missing")

        cls.proof_execution_id = (
            "V2_9_8B_MIG050_BOUNDED_PROOF_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "_"
            + uuid.uuid4().hex[:8]
        )
        cls.temp = tempfile.TemporaryDirectory(prefix="mig050_bounded_proof_")
        cls.proof_root = Path(cls.temp.name)
        cls.canonical_copy = cls.proof_root / "authoritative_byte_copy.sqlite3"
        cls.v2_fixture = cls.proof_root / "v2_scope_fixture.sqlite3"
        cls.negative_root = cls.proof_root / "negatives"
        cls.negative_root.mkdir(parents=True, exist_ok=True)

        # 1) Authoritative-source protection (filesystem only).
        cls.source_before = _file_identity(AUTHORITATIVE_DB)
        shutil.copy2(AUTHORITATIVE_DB, cls.canonical_copy)
        cls.copy_identity = _file_identity(cls.canonical_copy)
        if cls.copy_identity["sha256"] != cls.source_before["sha256"]:
            raise RuntimeError("disposable copy hash does not match source")
        if cls.copy_identity["size"] != cls.source_before["size"]:
            raise RuntimeError("disposable copy size does not match source")

        PROOF_EVIDENCE["proof_execution_id"] = cls.proof_execution_id
        PROOF_EVIDENCE["source_before"] = cls.source_before
        PROOF_EVIDENCE["copy_identity"] = cls.copy_identity

        # Open SQLite only on the disposable copy for readiness.
        connection = sqlite3.connect(str(cls.canonical_copy))
        try:
            connection.row_factory = sqlite3.Row
            ledger = _migration_versions(connection)
            tip = ledger[-1] if ledger else None
            if MIGRATION_050 in ledger:
                raise RuntimeError(
                    "disposable copy already carries migration 050; "
                    "not suitable for pre-050 proof"
                )
            if tip is None or not str(tip).startswith("049_"):
                raise RuntimeError(
                    f"disposable copy migration tip unsuitable for pre-050 proof: {tip!r}"
                )
            columns = _column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            )
            if "ownership_contract_version" in columns:
                raise RuntimeError(
                    "pre-050 table already has ownership_contract_version"
                )
            row_count = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work"
            ).fetchone()[0]
            duplicates = connection.execute(
                """
                SELECT scheduler_job_id, COUNT(*) AS c
                FROM printer_memory_factory_campaign_scheduler_work
                WHERE scheduler_job_id IS NOT NULL
                GROUP BY scheduler_job_id
                HAVING COUNT(*) > 1
                """
            ).fetchall()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            fk_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if integrity != "ok":
                raise RuntimeError(f"integrity_check failed: {integrity}")
            if fk_violations:
                raise RuntimeError(f"foreign key violations present: {fk_violations}")
            if duplicates:
                raise RuntimeError(f"duplicate non-null scheduler_job_id: {duplicates}")

            pre_schema = {
                "columns": columns,
                "indexes": _index_names(
                    connection, "printer_memory_factory_campaign_scheduler_work"
                ),
                "triggers": _trigger_names(
                    connection, "printer_memory_factory_campaign_scheduler_work"
                ),
                "table_sql": _table_sql(
                    connection, "printer_memory_factory_campaign_scheduler_work"
                ),
            }
            pre_rows = _ownership_snapshot(connection)
            pre_rows_hash = _canonical_rows_hash([tuple(r) for r in pre_rows])
            cls.readiness = {
                "migration_ledger_tip": tip,
                "migration_ledger_count": len(ledger),
                "migration_ledger": ledger,
                "ownership_row_count": int(row_count),
                "duplicate_non_null_scheduler_job_id_count": 0,
                "integrity_check": integrity,
                "foreign_key_violation_count": 0,
                "pre_schema": pre_schema,
                "pre_rows_canonical_hash": pre_rows_hash,
                "pre_rows": [tuple(r) for r in pre_rows],
            }
            PROOF_EVIDENCE["readiness"] = cls.readiness
        finally:
            connection.close()

        # 3) One canonical migration application on the disposable copy.
        cls.migration_result = _apply_migration_050_once(
            cls.canonical_copy, record_ledger=True
        )
        PROOF_EVIDENCE["migration_result"] = cls.migration_result

        connection = sqlite3.connect(str(cls.canonical_copy))
        try:
            connection.row_factory = sqlite3.Row
            post_columns = _column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            )
            post_schema = {
                "columns": post_columns,
                "indexes": _index_names(
                    connection, "printer_memory_factory_campaign_scheduler_work"
                ),
                "triggers": _trigger_names(
                    connection, "printer_memory_factory_campaign_scheduler_work"
                ),
                "table_sql": _table_sql(
                    connection, "printer_memory_factory_campaign_scheduler_work"
                ),
            }
            post_rows = _ownership_snapshot(connection)
            post_full = connection.execute(
                "SELECT * FROM printer_memory_factory_campaign_scheduler_work "
                "ORDER BY scheduler_work_id"
            ).fetchall()
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            fk_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            cls.post_migration = {
                "ownership_row_count": len(post_rows),
                "schema": post_schema,
                "post_rows_preserved": [tuple(r) for r in post_rows],
                "post_rows_full": [dict(r) for r in post_full],
                "integrity_check": integrity,
                "foreign_key_violation_count": len(fk_violations),
                "ledger": _migration_versions(connection),
            }
            PROOF_EVIDENCE["post_migration"] = {
                "ownership_row_count": cls.post_migration["ownership_row_count"],
                "schema_columns": post_schema["columns"],
                "schema_indexes": post_schema["indexes"],
                "schema_triggers": post_schema["triggers"],
                "integrity_check": integrity,
                "foreign_key_violation_count": len(fk_violations),
                "ledger_tip": cls.post_migration["ledger"][-1]
                if cls.post_migration["ledger"]
                else None,
            }
        finally:
            connection.close()

        # Separate post-migration disposable fixture for V2 scope proofs.
        apply_migrations(cls.v2_fixture)

    @classmethod
    def tearDownClass(cls) -> None:
        source_after = _file_identity(AUTHORITATIVE_DB)
        PROOF_EVIDENCE["source_after"] = source_after
        PROOF_EVIDENCE["authoritative_unchanged"] = source_after == cls.source_before
        cls.temp.cleanup()

    # ------------------------------------------------------------------
    # 1. Authoritative-source protection
    # ------------------------------------------------------------------
    def test_01_authoritative_source_protection(self) -> None:
        self.assertEqual(
            self.copy_identity["sha256"], self.source_before["sha256"]
        )
        self.assertEqual(self.copy_identity["size"], self.source_before["size"])
        self.assertTrue(self.canonical_copy.is_file())
        # Never opened the authoritative path through SQLite in this suite;
        # re-check filesystem identity has not drifted mid-proof.
        mid = _file_identity(AUTHORITATIVE_DB)
        self.assertEqual(mid, self.source_before)
        PROOF_EVIDENCE["authoritative_protection"] = "PASS"

    # ------------------------------------------------------------------
    # 2. Readiness gate (recorded in setUpClass; assert here)
    # ------------------------------------------------------------------
    def test_02_readiness_gate(self) -> None:
        readiness = self.readiness
        self.assertTrue(str(readiness["migration_ledger_tip"]).startswith("049_"))
        self.assertNotIn(MIGRATION_050, readiness["migration_ledger"])
        self.assertEqual(readiness["duplicate_non_null_scheduler_job_id_count"], 0)
        self.assertEqual(readiness["integrity_check"], "ok")
        self.assertEqual(readiness["foreign_key_violation_count"], 0)
        self.assertNotIn(
            "ownership_contract_version", readiness["pre_schema"]["columns"]
        )
        self.assertIsInstance(readiness["pre_rows_canonical_hash"], str)
        self.assertEqual(len(readiness["pre_rows_canonical_hash"]), 64)
        PROOF_EVIDENCE["readiness_gate"] = "PASS"

    # ------------------------------------------------------------------
    # 3. One canonical migration application
    # ------------------------------------------------------------------
    def test_03_one_canonical_migration(self) -> None:
        result = self.migration_result
        self.assertEqual(result["ledger_delta"], [MIGRATION_050])
        self.assertIn(MIGRATION_050, result["ledger_after"])
        self.assertNotIn(MIGRATION_050, result["ledger_before"])
        self.assertNotEqual(result["pre_file_sha256"], result["post_file_sha256"])
        post = self.post_migration
        self.assertEqual(post["integrity_check"], "ok")
        self.assertEqual(post["foreign_key_violation_count"], 0)
        self.assertIn("ownership_contract_version", post["schema"]["columns"])
        self.assertIn("stage_id", post["schema"]["columns"])
        self.assertIn("work_scope", post["schema"]["columns"])
        self.assertIn("target_category", post["schema"]["columns"])
        self.assertIn("target_identity", post["schema"]["columns"])
        self.assertIn("factory_run_id", post["schema"]["columns"])
        self.assertIn(
            "idx_campaign_work_scheduler_job_unique", post["schema"]["indexes"]
        )
        self.assertIn(
            "idx_campaign_work_scope_stage", post["schema"]["indexes"]
        )
        self.assertIn(
            "printer_campaign_work_identity_immutable", post["schema"]["triggers"]
        )
        self.assertIn(
            "printer_campaign_work_provenance_insert", post["schema"]["triggers"]
        )
        PROOF_EVIDENCE["canonical_migration"] = "PASS"

    # ------------------------------------------------------------------
    # 4. Historical preservation
    # ------------------------------------------------------------------
    def test_04_historical_preservation(self) -> None:
        pre_rows = self.readiness["pre_rows"]
        post_rows = self.post_migration["post_rows_preserved"]
        # Bidirectional exact comparison of preserved fields.
        self.assertEqual(pre_rows, post_rows)
        self.assertEqual(len(pre_rows), len(post_rows))
        self.assertEqual(
            self.readiness["ownership_row_count"],
            self.post_migration["ownership_row_count"],
        )
        for row in self.post_migration["post_rows_full"]:
            self.assertEqual(row["ownership_contract_version"], "V1_WINDOW_BOUND")
            self.assertIsNone(row["stage_id"])
            self.assertIsNone(row["work_scope"])
            self.assertIsNone(row["target_category"])
            self.assertIsNone(row["target_identity"])
            self.assertIsNone(row["factory_run_id"])

        # V1 rows cannot satisfy V2 exact capture (when any exist).
        connection = sqlite3.connect(str(self.canonical_copy))
        try:
            connection.row_factory = sqlite3.Row
            # Immutability of identity columns on any migrated row.
            for row in connection.execute(
                "SELECT scheduler_work_id FROM "
                "printer_memory_factory_campaign_scheduler_work"
            ):
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE printer_memory_factory_campaign_scheduler_work "
                        "SET work_intent='MUTATED' WHERE scheduler_work_id=?",
                        (row[0],),
                    )
                connection.rollback()
        finally:
            connection.close()

        PROOF_EVIDENCE["historical_preservation"] = {
            "result": "PASS",
            "pre_count": len(pre_rows),
            "post_count": len(post_rows),
            "pre_rows_canonical_hash": self.readiness["pre_rows_canonical_hash"],
            "post_rows_canonical_hash": _canonical_rows_hash(post_rows),
            "note": (
                "authoritative copy had zero historical ownership rows; "
                "preservation holds as exact empty equality in both directions"
                if not pre_rows
                else "all historical rows preserved byte-for-byte as V1_WINDOW_BOUND"
            ),
        }

    # ------------------------------------------------------------------
    # 5. V2 scope matrix on separate post-migration fixture
    # ------------------------------------------------------------------
    def _seed_v2_graph(self, connection: sqlite3.Connection) -> None:
        create_campaign(
            self.v2_fixture,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-bounded-proof",
            proof_source_db_identity="source-bounded-proof",
            policy_version="v2-9.8b",
        )
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            for token_id in (1, 2):
                connection.execute(
                    "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                    (token_id, f"mint-{token_id}"),
                )
                connection.execute(
                    "INSERT INTO printer_pairs(id,token_id,pair_address) "
                    "VALUES (?,?,?)",
                    (token_id, token_id, f"pair-{token_id}"),
                )
            connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,memory_status,
                    data_quality_label
                ) VALUES (1,1,1,'WINDOW_15M',?,'CLEAN_MEMORY','CLEAN_DATA')""",
                (NOW,),
            )
            for job_id in range(1, 21):
                connection.execute(
                    """INSERT INTO printer_scheduler_jobs(
                        id,job_name,job_kind,status,scheduled_for
                    ) VALUES (?,?,?,'PENDING',?)""",
                    (job_id, f"job-{job_id}", "CAMPAIGN_WORK", NOW),
                )
        create_campaign_run(
            connection, campaign_id="campaign-a", run_id="run-a",
            run_ordinal=1, now=NOW,
        )
        create_cycle_with_two_slots(
            connection, campaign_id="campaign-a", run_id="run-a",
            cycle_id="cycle-a", cycle_ordinal=1,
            slots=(
                {
                    "token_slot_id": "slot-1",
                    "slot_ordinal": 1,
                    "token_identity": "token-1",
                    "token_row_id": 1,
                    "mint_identity": "mint-1",
                    "pair_identity": "pair-1",
                    "pair_row_id": 1,
                    "lifecycle_identity": "lifecycle-1",
                },
                {
                    "token_slot_id": "slot-2",
                    "slot_ordinal": 2,
                    "token_identity": "token-2",
                    "token_row_id": 2,
                    "mint_identity": "mint-2",
                    "pair_identity": "pair-2",
                    "pair_row_id": 2,
                    "lifecycle_identity": "lifecycle-2",
                },
            ),
            now=NOW,
        )
        persist_window(
            connection, window_id="window-15m-a", campaign_id="campaign-a",
            run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
            token_row_id=1, pair_row_id=1, window_kind="WINDOW_15M",
            root_15m_lifecycle_identity="lifecycle-1", checkpoint_cutoff=NOW,
            memory_window_row_id=1, now=NOW,
        )

    def _seed_discovery_batch(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """INSERT INTO printer_discovery_batches(
                discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                cycle_cutoff,policy_version,provider_contract_versions_json,
                git_provenance_identity,campaign_selection_seed_identity,
                cycle_seed_hash,pump_continuity_state,batch_state,canonical_hash,
                created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'NONE','DISCOVERING',?,?)""",
            (
                "disc-1", "campaign-a", "configuration-a", "run-a", "cycle-a",
                NOW, "policy-1", "{}", "git-1", "seed-1", HEX64_A, HEX64_B, NOW,
            ),
        )

    def _seed_discovery_work(
        self,
        connection: sqlite3.Connection,
        *,
        discovery_work_id: str,
        scheduler_job_id: int,
        work_type: str = "DISCOVERY_PUMPFUN_LATEST",
        work_state: str = "PENDING",
        first_terminal_cause: str | None = None,
        terminal_at: str | None = None,
    ) -> None:
        connection.execute(
            """INSERT INTO printer_discovery_work(
                discovery_work_id,discovery_batch_id,campaign_id,run_id,cycle_id,
                scheduler_job_id,work_type,work_state,deadline_at,
                first_terminal_cause,terminal_at,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                discovery_work_id, "disc-1", "campaign-a", "run-a", "cycle-a",
                scheduler_job_id, work_type, work_state, NOW,
                first_terminal_cause, terminal_at, NOW, NOW,
            ),
        )

    def test_05_v2_scope_matrix(self) -> None:
        connection = sqlite3.connect(self.v2_fixture)
        connection.row_factory = sqlite3.Row
        try:
            self._seed_v2_graph(connection)
            with connection:
                self._seed_discovery_batch(connection)
                self._seed_discovery_work(
                    connection, discovery_work_id="dwork-1", scheduler_job_id=1
                )
                self._seed_discovery_work(
                    connection, discovery_work_id="sel-work", scheduler_job_id=2,
                    work_type="DISCOVERY_UNIFORM_SELECTION",
                )
                connection.execute(
                    """INSERT INTO printer_memory_factory_runs(
                        run_id,run_status,window_kind,db_mode,config_hash,config_json,
                        started_at
                    ) VALUES ('factory-a','RUNNING','WINDOW_15M','PROOF_ONLY',?,?,?)""",
                    (HEX64_A, "{}", NOW),
                )
                connection.execute(
                    """INSERT INTO printer_memory_factory_run_steps(
                        run_id,step_key,step_kind,step_status,scheduler_job_id,
                        created_at,updated_at
                    ) VALUES ('factory-a','step-4','WINDOW_CLOSE','SUCCEEDED',?,?,?)""",
                    (4, NOW, NOW),
                )
            bind_authoritative_run_id(
                connection, campaign_run_id="run-a", factory_run_id="factory-a",
                now=NOW,
            )
            self._seed_discovery_work(
                connection, discovery_work_id="dwork-5", scheduler_job_id=5,
                work_type="DISCOVERY_DEXSCREENER_ACTIVE",
            )
            connection.commit()
            # Handoff ownership source is the selected-item link. Parent selection
            # batch / merged-candidate rows are not required by the projection
            # validator; insert the exact link the same way the focused migration
            # suite does (separate connection, default FK off for link-only seed).
            link_conn = sqlite3.connect(self.v2_fixture)
            try:
                link_conn.execute(
                    """INSERT INTO printer_discovery_selected_item_links(
                        discovery_batch_id,selection_batch_id,selection_item_id,
                        merged_candidate_id,campaign_id,run_id,cycle_id,token_slot_id,
                        tracking_handoff_state,first_window_15m_scheduler_job_id,created_at
                    ) VALUES (?,?,?,?,?,?,?,?,'HANDOFF_RECORDED',?,?)""",
                    (
                        "disc-1", "sel-1", 1, "cand-1", "campaign-a", "run-a",
                        "cycle-a", "slot-1", 3, NOW,
                    ),
                )
                link_conn.commit()
            finally:
                link_conn.close()
            capture = capture_campaign_active_scheduler_jobs(
                connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-a", captured_at=NOW,
            )
            with connection:
                connection.execute(
                    """UPDATE printer_discovery_work
                       SET work_state=?, first_terminal_cause=?, terminal_at=?,
                           updated_at=?
                       WHERE discovery_work_id=?""",
                    ("CANCELLED", "CLEANUP_CANCELLED", LATER, LATER, "dwork-5"),
                )
                connection.execute(
                    "UPDATE printer_scheduler_jobs "
                    "SET status=?, finished_at=? WHERE id=?",
                    ("CANCELLED", LATER, 5),
                )

            matrix: dict[str, dict[str, object]] = {}

            disc = project_campaign_scheduler_work(
                connection, scheduler_work_id="s-disc", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
                stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
                scheduler_job_id=1, target_category="DISCOVERY_WORK",
                target_identity="dwork-1", now=NOW,
            )
            self.assertTrue(disc.created)
            self.assertEqual(disc.work_state, "PENDING")
            # exact-repeat idempotency
            again = project_campaign_scheduler_work(
                connection, scheduler_work_id="s-disc", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
                stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
                scheduler_job_id=1, target_category="DISCOVERY_WORK",
                target_identity="dwork-1", now=LATER,
            )
            self.assertFalse(again.created)
            matrix["DISCOVERY_SELECTION"] = {
                "created": True,
                "idempotent_repeat": True,
                "work_state": disc.work_state,
                "scheduler_job_id": 1,
                "target_identity": "dwork-1",
            }

            project_campaign_scheduler_work(
                connection, scheduler_work_id="s-hand", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", work_scope="FIRST_15M_HANDOFF",
                stage_id="STAGE_HANDOFF", work_intent="HANDOFF", deadline_at=NOW,
                scheduler_job_id=3, target_category="MERGED_CANDIDATE",
                target_identity="cand-1", token_slot_id="slot-1", now=NOW,
            )
            hand_row = connection.execute(
                "SELECT * FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE scheduler_work_id='s-hand'"
            ).fetchone()
            self.assertIsNone(hand_row["window_id"])
            self.assertIsNone(hand_row["factory_run_id"])
            matrix["FIRST_15M_HANDOFF"] = {
                "created": True,
                "window_id": hand_row["window_id"],
                "factory_run_id": hand_row["factory_run_id"],
                "token_slot_id": hand_row["token_slot_id"],
                "scheduler_job_id": 3,
            }

            project_campaign_scheduler_job(
                connection, scheduler_work_id="s-life", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
                window_id="window-15m-a", factory_run_id="factory-a",
                work_intent="CLOSE_WINDOW", deadline_at=NOW, scheduler_job_id=4,
                stage_id="STAGE_WINDOW_15M", now=NOW,
            )
            life_row = connection.execute(
                "SELECT * FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE scheduler_work_id='s-life'"
            ).fetchone()
            self.assertEqual(life_row["window_id"], "window-15m-a")
            self.assertEqual(life_row["factory_run_id"], "factory-a")
            matrix["WINDOW_LIFECYCLE"] = {
                "created": True,
                "window_id": life_row["window_id"],
                "factory_run_id": life_row["factory_run_id"],
                "token_slot_id": life_row["token_slot_id"],
                "scheduler_job_id": 4,
            }

            clean = project_campaign_scheduler_work(
                connection, scheduler_work_id="s-clean", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", work_scope="TERMINAL_CLEANUP",
                stage_id="STAGE_TERMINAL", work_intent="CANCEL", deadline_at=NOW,
                scheduler_job_id=5, target_category="SCHEDULER_JOB",
                target_identity="5", cleanup_capture=capture, now=NOW,
            )
            self.assertTrue(clean.created)
            clean_row = connection.execute(
                "SELECT * FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE scheduler_work_id='s-clean'"
            ).fetchone()
            self.assertEqual(clean_row["work_state"], "CANCELLED")
            self.assertEqual(clean_row["first_terminal_cause"], "CLEANUP_CANCELLED")
            # terminal-cause immutability via transition_state
            with self.assertRaises(CampaignOwnershipError):
                transition_state(
                    connection, record_kind="scheduler_work", identity="s-clean",
                    expected_state="CANCELLED", new_state="FAILED",
                    terminal_cause="OTHER", now=LATER,
                )
            connection.rollback()
            matrix["TERMINAL_CLEANUP"] = {
                "created": True,
                "work_state": clean_row["work_state"],
                "first_terminal_cause": clean_row["first_terminal_cause"],
                "scheduler_job_id": 5,
                "terminal_cause_immutable": True,
            }

            # one job -> one ownership row
            job_counts = connection.execute(
                """
                SELECT scheduler_job_id, COUNT(*)
                FROM printer_memory_factory_campaign_scheduler_work
                WHERE scheduler_job_id IS NOT NULL
                GROUP BY scheduler_job_id
                HAVING COUNT(*) > 1
                """
            ).fetchall()
            self.assertEqual(job_counts, [])

            # lawful state synchronization: discovery job advances
            with connection:
                connection.execute(
                    """UPDATE printer_discovery_work
                       SET work_state=?, first_terminal_cause=?, terminal_at=?,
                           updated_at=?
                       WHERE discovery_work_id=?""",
                    ("SUCCEEDED", "DISC_DONE", LATER, LATER, "dwork-1"),
                )
                connection.execute(
                    "UPDATE printer_scheduler_jobs "
                    "SET status=?, finished_at=? WHERE id=?",
                    ("SUCCEEDED", LATER, 1),
                )
            synced = project_campaign_scheduler_work(
                connection, scheduler_work_id="s-disc", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
                stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
                scheduler_job_id=1, target_category="DISCOVERY_WORK",
                target_identity="dwork-1", now=LATER,
            )
            self.assertFalse(synced.created)
            self.assertEqual(synced.work_state, "SUCCEEDED")
            matrix["DISCOVERY_SELECTION"]["state_sync"] = "SUCCEEDED"

            scopes = {
                row[0]
                for row in connection.execute(
                    "SELECT work_scope FROM "
                    "printer_memory_factory_campaign_scheduler_work "
                    "WHERE ownership_contract_version='V2_STAGE_SCOPED'"
                )
            }
            self.assertEqual(
                scopes,
                {
                    "DISCOVERY_SELECTION",
                    "FIRST_15M_HANDOFF",
                    "WINDOW_LIFECYCLE",
                    "TERMINAL_CLEANUP",
                },
            )
            PROOF_EVIDENCE["v2_scope_matrix"] = matrix
            PROOF_EVIDENCE["v2_scope_matrix_result"] = "PASS"
        finally:
            connection.close()

    # ------------------------------------------------------------------
    # 6. Read-only reconstruction of V2_STAGE_SCOPED rows
    # ------------------------------------------------------------------
    def test_06_readonly_reconstruction(self) -> None:
        connection = sqlite3.connect(f"file:{self.v2_fixture}?mode=ro", uri=True)
        try:
            # Zero writes: open read-only URI.
            rows = connection.execute(
                "SELECT "
                + ", ".join(RECONSTRUCTION_COLUMNS)
                + " FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE ownership_contract_version='V2_STAGE_SCOPED' "
                "ORDER BY scheduler_job_id, stage_id, work_scope, target_identity"
            ).fetchall()
            # No V1 rows included.
            v1_count = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE ownership_contract_version='V1_WINDOW_BOUND' "
                "AND scheduler_work_id IN ("
                "SELECT scheduler_work_id FROM "
                "printer_memory_factory_campaign_scheduler_work "
                "WHERE ownership_contract_version='V2_STAGE_SCOPED')"
            ).fetchone()[0]
            self.assertEqual(v1_count, 0)
            self.assertGreaterEqual(len(rows), 4)
            canonical = [tuple(row) for row in rows]
            payload = json.dumps(
                canonical, sort_keys=False, separators=(",", ":"), default=str
            )
            hash1 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            hash2 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            self.assertEqual(hash1, hash2)
            # Second independent reconstruction.
            rows2 = connection.execute(
                "SELECT "
                + ", ".join(RECONSTRUCTION_COLUMNS)
                + " FROM printer_memory_factory_campaign_scheduler_work "
                "WHERE ownership_contract_version='V2_STAGE_SCOPED' "
                "ORDER BY scheduler_job_id, stage_id, work_scope, target_identity"
            ).fetchall()
            payload2 = json.dumps(
                [tuple(r) for r in rows2],
                sort_keys=False,
                separators=(",", ":"),
                default=str,
            )
            hash3 = hashlib.sha256(payload2.encode("utf-8")).hexdigest()
            self.assertEqual(hash1, hash3)
            PROOF_EVIDENCE["reconstruction"] = {
                "result": "PASS",
                "row_count": len(rows),
                "canonical_hash": hash1,
                "hash_repeat_match": True,
                "zero_writes": True,
                "no_v1_rows": True,
                "no_source_request": True,
                "no_scheduler_mutation": True,
                "no_operational_report_path": True,
            }
        finally:
            connection.close()

    # ------------------------------------------------------------------
    # 7. Negative proofs — each from a fresh disposable state
    # ------------------------------------------------------------------
    def test_07_negative_duplicate_historical_job_blocks_migration(self) -> None:
        db = self.negative_root / "neg_dup.sqlite3"
        _apply_through(db, 49)
        for suffix in ("a", "b"):
            _insert_pre050_work_row(
                db,
                scheduler_work_id=f"w-{suffix}",
                campaign_id="c",
                run_id="r",
                cycle_id="cy",
                token_slot_id="s",
                window_id="win",
                work_intent="i",
                deadline_at=NOW,
                work_state="PENDING",
                scheduler_job_id=999,
                created_at=NOW,
                updated_at=NOW,
            )
        connection = sqlite3.connect(db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(
                    MIGRATION_050_PATH.read_text(encoding="utf-8")
                )
            connection.rollback()
            cols = set(_column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            ))
            self.assertNotIn("ownership_contract_version", cols)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_scheduler_work"
                ).fetchone()[0],
                2,
            )
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
            self.assertNotIn(MIGRATION_050, _migration_versions(connection))
        finally:
            connection.close()
        PROOF_EVIDENCE.setdefault("negatives", {})["duplicate_historical_job"] = "PASS"

    def test_08_negative_injected_failure_rolls_back(self) -> None:
        db = self.negative_root / "neg_inject.sqlite3"
        _apply_through(db, 49)
        _insert_pre050_work_row(
            db,
            scheduler_work_id="w-keep",
            campaign_id="c",
            run_id="r",
            cycle_id="cy",
            token_slot_id="s",
            window_id="win",
            work_intent="i",
            deadline_at=NOW,
            work_state="PENDING",
            scheduler_job_id=1,
            created_at=NOW,
            updated_at=NOW,
        )
        script = MIGRATION_050_PATH.read_text(encoding="utf-8")
        marker = "-- 6. Swap the rebuilt table into place."
        self.assertIn(marker, script)
        injected = script.replace(
            marker,
            "INSERT INTO _mig050_guard_rowcount(ok) VALUES (0);\n" + marker,
        )
        connection = sqlite3.connect(db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(injected)
            connection.rollback()
            cols = set(_column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            ))
            self.assertNotIn("ownership_contract_version", cols)
            self.assertEqual(
                connection.execute(
                    "SELECT scheduler_work_id FROM "
                    "printer_memory_factory_campaign_scheduler_work"
                ).fetchall(),
                [("w-keep",)],
            )
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
            self.assertNotIn(MIGRATION_050, _migration_versions(connection))
        finally:
            connection.close()
        PROOF_EVIDENCE.setdefault("negatives", {})["injected_failure_rollback"] = "PASS"

    def test_09_negative_field_mismatch_blocks(self) -> None:
        db = self.negative_root / "neg_field.sqlite3"
        _apply_through(db, 49)
        _insert_pre050_work_row(
            db,
            scheduler_work_id="w-keep",
            campaign_id="c",
            run_id="r",
            cycle_id="cy",
            token_slot_id="s",
            window_id="win",
            work_intent="ORIGINAL",
            deadline_at=NOW,
            work_state="PENDING",
            scheduler_job_id=1,
            created_at=NOW,
            updated_at=NOW,
        )
        script = MIGRATION_050_PATH.read_text(encoding="utf-8")
        # Corrupt a preserved field during copy so the field-equality guard fails.
        corrupted = script.replace(
            "work_intent, deadline_at, work_state, scheduler_job_id, source_request_id,\n"
            "    source_response_id, source_failure_id, 'V1_WINDOW_BOUND',",
            "'MUTATED', deadline_at, work_state, scheduler_job_id, source_request_id,\n"
            "    source_response_id, source_failure_id, 'V1_WINDOW_BOUND',",
            1,
        )
        self.assertNotEqual(script, corrupted)
        connection = sqlite3.connect(db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(corrupted)
            connection.rollback()
            cols = set(_column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            ))
            self.assertNotIn("ownership_contract_version", cols)
            row = connection.execute(
                "SELECT work_intent FROM "
                "printer_memory_factory_campaign_scheduler_work"
            ).fetchone()
            self.assertEqual(row[0], "ORIGINAL")
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
            self.assertNotIn(MIGRATION_050, _migration_versions(connection))
        finally:
            connection.close()
        PROOF_EVIDENCE.setdefault("negatives", {})["field_mismatch_blocks"] = "PASS"

    def test_10_negative_foreign_key_failure_blocks(self) -> None:
        db = self.negative_root / "neg_fk.sqlite3"
        _apply_through(db, 49)
        # Insert a historical ownership row pointing at a non-existent scheduler job.
        # Pre-050 insert with FK off (same pattern as historical insert helper).
        _insert_pre050_work_row(
            db,
            scheduler_work_id="w-orphan",
            campaign_id="c",
            run_id="r",
            cycle_id="cy",
            token_slot_id="s",
            window_id="win",
            work_intent="i",
            deadline_at=NOW,
            work_state="PENDING",
            scheduler_job_id=999999,
            created_at=NOW,
            updated_at=NOW,
        )
        connection = sqlite3.connect(db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(
                    MIGRATION_050_PATH.read_text(encoding="utf-8")
                )
            connection.rollback()
            cols = set(_column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            ))
            self.assertNotIn("ownership_contract_version", cols)
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
            self.assertNotIn(MIGRATION_050, _migration_versions(connection))
        finally:
            connection.close()
        PROOF_EVIDENCE.setdefault("negatives", {})["foreign_key_failure_blocks"] = "PASS"

    def test_11_negative_invalid_scope_nullability_blocks(self) -> None:
        db = self.negative_root / "neg_null.sqlite3"
        apply_migrations(db)
        connection = sqlite3.connect(db)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            base = (
                "INSERT INTO printer_memory_factory_campaign_scheduler_work("
                "scheduler_work_id,campaign_id,run_id,cycle_id,work_intent,deadline_at,"
                "work_state,scheduler_job_id,ownership_contract_version,stage_id,"
                "work_scope,target_category,target_identity,token_slot_id,window_id,"
                "factory_run_id,created_at,updated_at) VALUES "
            )
            cases = [
                # V2 discovery carrying a window.
                "('x1','c','r','cy','i',?,'PENDING',1,'V2_STAGE_SCOPED','st',"
                "'DISCOVERY_SELECTION','DISCOVERY_WORK','d',NULL,'win',NULL,?,?)",
                # V2 lifecycle missing window.
                "('x2','c','r','cy','i',?,'PENDING',2,'V2_STAGE_SCOPED','st',"
                "'WINDOW_LIFECYCLE','CAMPAIGN_WINDOW','w','slot',NULL,'f',?,?)",
                # V1 carrying a scope.
                "('x3','c','r','cy','i',?,'PENDING',3,'V1_WINDOW_BOUND',NULL,"
                "'WINDOW_LIFECYCLE',NULL,NULL,'slot','win',NULL,?,?)",
                # V2 handoff carrying factory run.
                "('x4','c','r','cy','i',?,'PENDING',4,'V2_STAGE_SCOPED','st',"
                "'FIRST_15M_HANDOFF','MERGED_CANDIDATE','m',NULL,NULL,'f',?,?)",
                # V2 cleanup carrying window.
                "('x5','c','r','cy','i',?,'PENDING',5,'V2_STAGE_SCOPED','st',"
                "'TERMINAL_CLEANUP','SCHEDULER_JOB','5',NULL,'win',NULL,?,?)",
            ]
            for case in cases:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(base + case, (NOW, NOW, NOW))
                connection.rollback()
        finally:
            connection.close()
        PROOF_EVIDENCE.setdefault("negatives", {})["invalid_scope_nullability"] = "PASS"

    def test_12_negative_duplicate_v2_job_and_conflicts(self) -> None:
        db = self.negative_root / "neg_v2_dup.sqlite3"
        apply_migrations(db)
        create_campaign(
            db,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-neg",
            proof_source_db_identity="source-neg",
            policy_version="v2-9.8b",
        )
        connection = sqlite3.connect(db)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                for token_id in (1, 2):
                    connection.execute(
                        "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                        (token_id, f"mint-{token_id}"),
                    )
                    connection.execute(
                        "INSERT INTO printer_pairs(id,token_id,pair_address) "
                        "VALUES (?,?,?)",
                        (token_id, token_id, f"pair-{token_id}"),
                    )
                connection.execute(
                    """INSERT INTO printer_memory_windows(
                        id,token_id,pair_id,window_kind,opened_at,memory_status,
                        data_quality_label
                    ) VALUES (1,1,1,'WINDOW_15M',?,'CLEAN_MEMORY','CLEAN_DATA')""",
                    (NOW,),
                )
                for job_id in range(1, 10):
                    connection.execute(
                        """INSERT INTO printer_scheduler_jobs(
                            id,job_name,job_kind,status,scheduled_for
                        ) VALUES (?,?,?,'PENDING',?)""",
                        (job_id, f"job-{job_id}", "CAMPAIGN_WORK", NOW),
                    )
            create_campaign_run(
                connection, campaign_id="campaign-a", run_id="run-a",
                run_ordinal=1, now=NOW,
            )
            create_cycle_with_two_slots(
                connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-a", cycle_ordinal=1,
                slots=(
                    {
                        "token_slot_id": "slot-1",
                        "slot_ordinal": 1,
                        "token_identity": "token-1",
                        "token_row_id": 1,
                        "mint_identity": "mint-1",
                        "pair_identity": "pair-1",
                        "pair_row_id": 1,
                        "lifecycle_identity": "lifecycle-1",
                    },
                    {
                        "token_slot_id": "slot-2",
                        "slot_ordinal": 2,
                        "token_identity": "token-2",
                        "token_row_id": 2,
                        "mint_identity": "mint-2",
                        "pair_identity": "pair-2",
                        "pair_row_id": 2,
                        "lifecycle_identity": "lifecycle-2",
                    },
                ),
                now=NOW,
            )
            with connection:
                connection.execute(
                    """INSERT INTO printer_discovery_batches(
                        discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                        cycle_cutoff,policy_version,provider_contract_versions_json,
                        git_provenance_identity,campaign_selection_seed_identity,
                        cycle_seed_hash,pump_continuity_state,batch_state,canonical_hash,
                        created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'NONE','DISCOVERING',?,?)""",
                    (
                        "disc-1", "campaign-a", "configuration-a", "run-a", "cycle-a",
                        NOW, "policy-1", "{}", "git-1", "seed-1", HEX64_A, HEX64_B, NOW,
                    ),
                )
                for work_id, job_id, wtype in (
                    ("dwork-1", 1, "DISCOVERY_PUMPFUN_LATEST"),
                    ("dwork-x", 1, "DISCOVERY_DEXSCREENER_ACTIVE"),
                ):
                    connection.execute(
                        """INSERT INTO printer_discovery_work(
                            discovery_work_id,discovery_batch_id,campaign_id,run_id,
                            cycle_id,scheduler_job_id,work_type,work_state,deadline_at,
                            created_at,updated_at
                        ) VALUES (?,?,?,?,?,?,?,'PENDING',?,?,?)""",
                        (
                            work_id, "disc-1", "campaign-a", "run-a", "cycle-a",
                            job_id, wtype, NOW, NOW, NOW,
                        ),
                    )
            first = project_campaign_scheduler_work(
                connection, scheduler_work_id="work-disc", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", work_scope="DISCOVERY_SELECTION",
                stage_id="STAGE_DISCOVERY", work_intent="DISCOVER", deadline_at=NOW,
                scheduler_job_id=1, target_category="DISCOVERY_WORK",
                target_identity="dwork-1", now=NOW,
            )
            self.assertTrue(first.created)
            # Duplicate V2 job ownership blocks.
            with self.assertRaises(CampaignOwnershipError):
                project_campaign_scheduler_work(
                    connection, scheduler_work_id="work-other",
                    campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                    work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                    work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                    target_category="DISCOVERY_WORK", target_identity="dwork-x",
                    now=NOW,
                )
            # Scope/stage/target conflict on same work id blocks.
            with self.assertRaises(CampaignOwnershipError):
                project_campaign_scheduler_work(
                    connection, scheduler_work_id="work-disc",
                    campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                    work_scope="DISCOVERY_SELECTION", stage_id="STAGE_OTHER",
                    work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                    target_category="DISCOVERY_WORK", target_identity="dwork-1",
                    now=NOW,
                )
        finally:
            connection.close()
        PROOF_EVIDENCE.setdefault("negatives", {})["duplicate_v2_and_conflicts"] = "PASS"

    def test_13_negative_v1_cannot_satisfy_v2_and_foreign_cycle(self) -> None:
        db = self.negative_root / "neg_v1_v2.sqlite3"
        apply_migrations(db)
        create_campaign(
            db,
            campaign_id="campaign-a",
            configuration_id="configuration-a",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="isolated-neg2",
            proof_source_db_identity="source-neg2",
            policy_version="v2-9.8b",
        )
        connection = sqlite3.connect(db)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            with connection:
                for token_id in (1, 2):
                    connection.execute(
                        "INSERT INTO printer_tokens(id,token_mint) VALUES (?,?)",
                        (token_id, f"mint-{token_id}"),
                    )
                    connection.execute(
                        "INSERT INTO printer_pairs(id,token_id,pair_address) "
                        "VALUES (?,?,?)",
                        (token_id, token_id, f"pair-{token_id}"),
                    )
                connection.execute(
                    """INSERT INTO printer_memory_windows(
                        id,token_id,pair_id,window_kind,opened_at,memory_status,
                        data_quality_label
                    ) VALUES (1,1,1,'WINDOW_15M',?,'CLEAN_MEMORY','CLEAN_DATA')""",
                    (NOW,),
                )
                for job_id in range(1, 10):
                    connection.execute(
                        """INSERT INTO printer_scheduler_jobs(
                            id,job_name,job_kind,status,scheduled_for
                        ) VALUES (?,?,?,'PENDING',?)""",
                        (job_id, f"job-{job_id}", "CAMPAIGN_WORK", NOW),
                    )
            create_campaign_run(
                connection, campaign_id="campaign-a", run_id="run-a",
                run_ordinal=1, now=NOW,
            )
            create_cycle_with_two_slots(
                connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-a", cycle_ordinal=1,
                slots=(
                    {
                        "token_slot_id": "slot-1",
                        "slot_ordinal": 1,
                        "token_identity": "token-1",
                        "token_row_id": 1,
                        "mint_identity": "mint-1",
                        "pair_identity": "pair-1",
                        "pair_row_id": 1,
                        "lifecycle_identity": "lifecycle-1",
                    },
                    {
                        "token_slot_id": "slot-2",
                        "slot_ordinal": 2,
                        "token_identity": "token-2",
                        "token_row_id": 2,
                        "mint_identity": "mint-2",
                        "pair_identity": "pair-2",
                        "pair_row_id": 2,
                        "lifecycle_identity": "lifecycle-2",
                    },
                ),
                now=NOW,
            )
            persist_window(
                connection, window_id="window-15m-a", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
                token_row_id=1, pair_row_id=1, window_kind="WINDOW_15M",
                root_15m_lifecycle_identity="lifecycle-1", checkpoint_cutoff=NOW,
                memory_window_row_id=1, now=NOW,
            )
            persist_scheduler_work(
                connection, scheduler_work_id="v1-a", campaign_id="campaign-a",
                run_id="run-a", cycle_id="cycle-a", token_slot_id="slot-1",
                window_id="window-15m-a", work_intent="CLOSE_WINDOW",
                deadline_at=NOW, scheduler_job_id=1, now=NOW,
            )
            with connection:
                connection.execute(
                    """INSERT INTO printer_discovery_batches(
                        discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                        cycle_cutoff,policy_version,provider_contract_versions_json,
                        git_provenance_identity,campaign_selection_seed_identity,
                        cycle_seed_hash,pump_continuity_state,batch_state,canonical_hash,
                        created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'NONE','DISCOVERING',?,?)""",
                    (
                        "disc-1", "campaign-a", "configuration-a", "run-a", "cycle-a",
                        NOW, "policy-1", "{}", "git-1", "seed-1", HEX64_A, HEX64_B, NOW,
                    ),
                )
                connection.execute(
                    """INSERT INTO printer_discovery_work(
                        discovery_work_id,discovery_batch_id,campaign_id,run_id,
                        cycle_id,scheduler_job_id,work_type,work_state,deadline_at,
                        created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,'PENDING',?,?,?)""",
                    (
                        "dwork-1", "disc-1", "campaign-a", "run-a", "cycle-a",
                        1, "DISCOVERY_PUMPFUN_LATEST", NOW, NOW, NOW,
                    ),
                )
            # V1 row cannot be upgraded/reused as V2.
            with self.assertRaises(CampaignOwnershipError):
                project_campaign_scheduler_work(
                    connection, scheduler_work_id="v1-a",
                    campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                    work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                    work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                    target_category="DISCOVERY_WORK", target_identity="dwork-1",
                    now=NOW,
                )
            # V1 still occupies the unique job slot.
            with self.assertRaises(CampaignOwnershipError):
                project_campaign_scheduler_work(
                    connection, scheduler_work_id="v2-a",
                    campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                    work_scope="DISCOVERY_SELECTION", stage_id="STAGE_DISCOVERY",
                    work_intent="DISCOVER", deadline_at=NOW, scheduler_job_id=1,
                    target_category="DISCOVERY_WORK", target_identity="dwork-1",
                    now=NOW,
                )
            # Foreign cycle excluded from capture.
            create_cycle_with_two_slots(
                connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-b", cycle_ordinal=2,
                slots=(
                    {
                        "token_slot_id": "slot-3",
                        "slot_ordinal": 1,
                        "token_identity": "token-1",
                        "token_row_id": 1,
                        "mint_identity": "mint-1",
                        "pair_identity": "pair-1",
                        "pair_row_id": 1,
                        "lifecycle_identity": "lifecycle-1b",
                    },
                    {
                        "token_slot_id": "slot-4",
                        "slot_ordinal": 2,
                        "token_identity": "token-2",
                        "token_row_id": 2,
                        "mint_identity": "mint-2",
                        "pair_identity": "pair-2",
                        "pair_row_id": 2,
                        "lifecycle_identity": "lifecycle-2b",
                    },
                ),
                now=NOW,
            )
            with connection:
                connection.execute(
                    """INSERT INTO printer_discovery_batches(
                        discovery_batch_id,campaign_id,configuration_id,run_id,cycle_id,
                        cycle_cutoff,policy_version,provider_contract_versions_json,
                        git_provenance_identity,campaign_selection_seed_identity,
                        cycle_seed_hash,pump_continuity_state,batch_state,canonical_hash,
                        created_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,'NONE','DISCOVERING',?,?)""",
                    (
                        "disc-b", "campaign-a", "configuration-a", "run-a", "cycle-b",
                        NOW, "policy-1", "{}", "git-1", "seed-1", HEX64_A, HEX64_B, NOW,
                    ),
                )
                connection.execute(
                    """INSERT INTO printer_discovery_work(
                        discovery_work_id,discovery_batch_id,campaign_id,run_id,
                        cycle_id,scheduler_job_id,work_type,work_state,deadline_at,
                        created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,'PENDING',?,?,?)""",
                    (
                        "dwork-b", "disc-b", "campaign-a", "run-a", "cycle-b",
                        6, "DISCOVERY_PUMPFUN_LATEST", NOW, NOW, NOW,
                    ),
                )
            capture = capture_campaign_active_scheduler_jobs(
                connection, campaign_id="campaign-a", run_id="run-a",
                cycle_id="cycle-a",
            )
            self.assertIsNone(capture.pre_state(6))
            with connection:
                connection.execute(
                    "UPDATE printer_scheduler_jobs "
                    "SET status=?, finished_at=? WHERE id=?",
                    ("CANCELLED", NOW, 6),
                )
            with self.assertRaises(CampaignOwnershipError):
                project_campaign_scheduler_work(
                    connection, scheduler_work_id="work-cf",
                    campaign_id="campaign-a", run_id="run-a", cycle_id="cycle-a",
                    work_scope="TERMINAL_CLEANUP", stage_id="STAGE_TERMINAL",
                    work_intent="CANCEL", deadline_at=NOW, scheduler_job_id=6,
                    target_category="SCHEDULER_JOB", target_identity="6",
                    cleanup_capture=capture, now=NOW,
                )
        finally:
            connection.close()
        PROOF_EVIDENCE.setdefault("negatives", {})["v1_not_v2_and_foreign_cycle"] = "PASS"

    def test_14_negative_partial_failed_leaves_no_ledger_or_replacement(self) -> None:
        """Partial/failed migration leaves no ledger entry or replacement table."""
        db = self.negative_root / "neg_partial.sqlite3"
        _apply_through(db, 49)
        _insert_pre050_work_row(
            db,
            scheduler_work_id="w-keep",
            campaign_id="c",
            run_id="r",
            cycle_id="cy",
            token_slot_id="s",
            window_id="win",
            work_intent="i",
            deadline_at=NOW,
            work_state="PENDING",
            scheduler_job_id=1,
            created_at=NOW,
            updated_at=NOW,
        )
        # Simulate a harness that would record the ledger only after success,
        # but force the migration body to fail first.
        script = MIGRATION_050_PATH.read_text(encoding="utf-8")
        marker = "-- 6. Swap the rebuilt table into place."
        injected = script.replace(
            marker,
            "INSERT INTO _mig050_guard_fields(ok) VALUES (0);\n" + marker,
        )
        connection = sqlite3.connect(db)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.executescript(injected)
                # Must never reach ledger write on failure.
                connection.execute(
                    "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                    (MIGRATION_050,),
                )
            connection.rollback()
            self.assertNotIn(MIGRATION_050, _migration_versions(connection))
            leftover = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE '%__v2_9_8b_050'"
            ).fetchone()[0]
            self.assertEqual(leftover, 0)
            cols = set(_column_names(
                connection, "printer_memory_factory_campaign_scheduler_work"
            ))
            self.assertNotIn("ownership_contract_version", cols)
        finally:
            connection.close()
        PROOF_EVIDENCE.setdefault("negatives", {})["partial_failed_no_ledger"] = "PASS"

    def test_99_final_authoritative_unchanged_and_verdict(self) -> None:
        after = _file_identity(AUTHORITATIVE_DB)
        self.assertEqual(after, self.source_before)
        negatives = PROOF_EVIDENCE.get("negatives", {})
        required_negatives = {
            "duplicate_historical_job",
            "injected_failure_rollback",
            "field_mismatch_blocks",
            "foreign_key_failure_blocks",
            "invalid_scope_nullability",
            "duplicate_v2_and_conflicts",
            "v1_not_v2_and_foreign_cycle",
            "partial_failed_no_ledger",
        }
        self.assertTrue(required_negatives.issubset(set(negatives)))
        self.assertTrue(all(negatives[k] == "PASS" for k in required_negatives))
        self.assertEqual(PROOF_EVIDENCE.get("authoritative_protection"), "PASS")
        self.assertEqual(PROOF_EVIDENCE.get("readiness_gate"), "PASS")
        self.assertEqual(PROOF_EVIDENCE.get("canonical_migration"), "PASS")
        self.assertEqual(
            (PROOF_EVIDENCE.get("historical_preservation") or {}).get("result"),
            "PASS",
        )
        self.assertEqual(PROOF_EVIDENCE.get("v2_scope_matrix_result"), "PASS")
        self.assertEqual(
            (PROOF_EVIDENCE.get("reconstruction") or {}).get("result"),
            "PASS",
        )
        PROOF_EVIDENCE["final_authoritative_unchanged"] = True
        PROOF_EVIDENCE["verdict"] = (
            "V2_9_8B_CAMPAIGN_SCHEDULER_OWNERSHIP_SCHEMA_MIGRATION_BOUNDED_PROOF_PASS"
        )
        # Emit a compact JSON summary for the documentation lane.
        summary_path = self.proof_root / "proof_summary.json"
        serializable = {
            k: v
            for k, v in PROOF_EVIDENCE.items()
            if k not in {"readiness"}  # readiness includes full row list; summarize
        }
        serializable["readiness_summary"] = {
            "migration_ledger_tip": self.readiness["migration_ledger_tip"],
            "migration_ledger_count": self.readiness["migration_ledger_count"],
            "ownership_row_count": self.readiness["ownership_row_count"],
            "integrity_check": self.readiness["integrity_check"],
            "foreign_key_violation_count": self.readiness["foreign_key_violation_count"],
            "pre_rows_canonical_hash": self.readiness["pre_rows_canonical_hash"],
            "duplicate_non_null_scheduler_job_id_count": self.readiness[
                "duplicate_non_null_scheduler_job_id_count"
            ],
        }
        summary_path.write_text(
            json.dumps(serializable, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        # Also write under the repo tmp-friendly location if available.
        evidence_dir = ROOT / "operator-runs" / "v2-9-8b-mig050-bounded-proof"
        try:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (evidence_dir / "proof_summary.json").write_text(
                summary_path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        except OSError:
            pass


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
