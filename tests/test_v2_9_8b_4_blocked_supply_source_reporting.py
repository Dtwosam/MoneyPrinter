"""V2-9.8B.4 blocked-supply and source-activity reporting repair proofs.

Disposable-DB fixtures only. No production campaign, no live network, no
retrieval/financial activation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
)
from printer_v1.operator_cli.holder_reliability_budget_control import (
    CampaignOperationLedger,
    persist_ledger,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    BLOCKED_INSUFFICIENT_GRADUATED_POOL,
    LIQUIDITY_BELOW_SELECTION_FLOOR,
    REPORT_ARTIFACT_SUFFIX,
    assemble_campaign_terminal_reporting,
    build_blocked_supply_reporting,
    build_campaign_terminal_report,
    load_campaign_operation_totals,
    reconcile_campaign_terminal,
    replay_campaign_terminal_report,
    write_campaign_terminal_report,
)
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES


NOW = datetime(2026, 7, 26, 17, 21, 19, tzinfo=timezone.utc)
NOW_TEXT = NOW.isoformat()
ELIGIBLE_MINT = "CrR3AB6W9v2RV9btV9Egqsdij3jXNUSJba9dqKAqpump"
REJECTED_MINT = "4hi84NkokbcM6G1LFQ9wB7HgjGrFxh4qXwAc16chpump"


def _provenance() -> dict[str, object]:
    return {
        "git_head": "d" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW_TEXT,
    }


def _locked_counts(connection: sqlite3.Connection) -> dict[str, int]:
    out: dict[str, int] = {}
    for table in LOCKED_CAPABILITY_TABLES:
        try:
            out[table] = int(
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
        except sqlite3.Error:
            out[table] = -1
    return out


def _seed_graph(db: Path, connection: sqlite3.Connection) -> None:
    create_campaign(
        db,
        campaign_id="campaign",
        configuration_id="configuration",
        configuration={"token_capacity": 2, "slots": 2},
        launch_provenance=_provenance(),
        db_mode=DB_MODE_PROOF_ISOLATED,
        db_target_identity="blocked-supply-fixture",
        proof_source_db_identity="blocked-supply-source",
        policy_version="v2-9.8b.4",
    )
    create_campaign_run(
        connection,
        campaign_id="campaign",
        run_id="run",
        run_ordinal=1,
        now=NOW_TEXT,
    )
    connection.execute(
        """INSERT INTO printer_memory_factory_campaign_cycles
           (cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
            first_terminal_cause, terminal_at, created_at, updated_at)
           VALUES ('cycle','campaign','run',1,'PLANNED',NULL,NULL,?,?)""",
        (NOW_TEXT, NOW_TEXT),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaigns "
        "SET campaign_state='RUNNING',updated_at=? WHERE campaign_id='campaign'",
        (NOW_TEXT,),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaign_runs "
        "SET run_state='RUNNING',updated_at=? WHERE run_id='run'",
        (NOW_TEXT,),
    )
    connection.commit()


def _fixture_candidates() -> list[dict[str, object]]:
    return [
        {
            "mint": ELIGIBLE_MINT,
            "pool": "A2MoynsjruNQqDjdRQKMq8xDbFtAecE198KjuVrMBeWu",
            "market_identity": (
                "solana-mainnet:pumpswap:A2MoynsjruNQqDjdRQKMq8xDbFtAecE198KjuVrMBeWu"
            ),
            "provenance": "LATEST_GRADUATED",
            "lifecycle_state": "PUMPSWAP_GRADUATED_CONFIRMED",
            "migration_signature": "sig-eligible",
            "migration_provenance": "PUMPPORTAL_SUBSCRIBE_MIGRATION",
            "source_path": (
                "pumpportal_migration->pumpswap_pool_resolution->"
                "dexscreener_pair_market_snapshot"
            ),
            "stage_reached": "MARKET_ELIGIBLE",
            "liquidity": {
                "status": "LIQUIDITY_PROVEN",
                "liquidity_usd": 10248.29,
                "mint": ELIGIBLE_MINT,
                "pool": "A2MoynsjruNQqDjdRQKMq8xDbFtAecE198KjuVrMBeWu",
                "reason": "AT_OR_ABOVE_3000_FLOOR",
                "source_status": "COMPLETE",
            },
            "market_cap": 25247.0,
            "eligible": True,
            "rejection": None,
        },
        {
            "mint": REJECTED_MINT,
            "pool": "9G3n5P93x4mfxMZqoH6pN9aMv2SJEkoZFs7eGR7qrWUh",
            "market_identity": (
                "solana-mainnet:pumpswap:9G3n5P93x4mfxMZqoH6pN9aMv2SJEkoZFs7eGR7qrWUh"
            ),
            "provenance": "PERSISTED_GRADUATED",
            "lifecycle_state": "PUMPSWAP_GRADUATED_CONFIRMED",
            "migration_signature": "sig-rejected",
            "migration_provenance": "PUMPPORTAL_SUBSCRIBE_MIGRATION",
            "source_path": (
                "graduated_registry_reenrichment->"
                "dexscreener_pair_market_snapshot"
            ),
            "stage_reached": "LIQUIDITY_FLOOR_FAILED",
            "liquidity": {
                "status": LIQUIDITY_BELOW_SELECTION_FLOOR,
                "liquidity_usd": 9.06,
                "mint": REJECTED_MINT,
                "pool": "9G3n5P93x4mfxMZqoH6pN9aMv2SJEkoZFs7eGR7qrWUh",
                "reason": "BELOW_3000_FLOOR",
                "source_status": "COMPLETE",
            },
            "market_cap": 5.0,
            "eligible": False,
            "rejection": LIQUIDITY_BELOW_SELECTION_FLOOR,
        },
    ]


class BlockedSupplySourceReportingTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.db = self.root / "blocked-supply.sqlite3"
        self.reports = self.root / "reports"
        self.reports.mkdir()
        apply_migrations(self.db)
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        _seed_graph(self.db, self.connection)
        ledger = CampaignOperationLedger(
            operation_ceiling=45,
            governed_requests=4,
            underlying_transport_operations=4,
            zero_transport_operations=9,
            reserved_snapshot_operations=2,
            reserved_snapshot_completion_operations=4,
            deadline_at=NOW + timedelta(seconds=1200),
        )
        persist_ledger(
            self.connection,
            run_id="run",
            cycle_id="cycle",
            ledger=ledger,
            now=NOW_TEXT,
        )
        self.connection.commit()
        self.locked_before = _locked_counts(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def _write_terminal(self) -> dict[str, object]:
        pre_lifecycle_admission = {
            "required_token_capacity": 2,
            "holder_eligible_count": 1,
            "terminal_classification": "COOLDOWN_REOPEN_REQUIRED",
            "candidates": [
                {
                    "mint": "mint-a",
                    "tracking_handoff": {
                        "category": "COOLDOWN_REOPEN_REQUIRED"
                    },
                }
            ],
        }
        lifecycle = {
            "first_terminal_cause": BLOCKED_INSUFFICIENT_GRADUATED_POOL,
            "terminal_reporting": {
                "campaign_source_calls": 4,
                "campaign_scheduler_calls": 0,
                "required_token_capacity": 2,
                "blocked_supply_reason": BLOCKED_INSUFFICIENT_GRADUATED_POOL,
                "candidates": _fixture_candidates(),
                "pre_lifecycle_admission": pre_lifecycle_admission,
            },
            "front_door_candidates": _fixture_candidates(),
        }
        reporting = assemble_campaign_terminal_reporting(
            self.db,
            run_id="run",
            cycle_id="cycle",
            terminal_cause=BLOCKED_INSUFFICIENT_GRADUATED_POOL,
            lifecycle=lifecycle,
            required_token_capacity=2,
        )
        self.assertEqual(
            reporting["pre_lifecycle_admission"]["terminal_classification"],
            "COOLDOWN_REOPEN_REQUIRED",
        )
        reconciliation = reconcile_campaign_terminal(
            self.db,
            campaign_id="campaign",
            run_id="run",
            cycle_id="cycle",
            terminal_cause=BLOCKED_INSUFFICIENT_GRADUATED_POOL,
            run_status="NOT_STARTED",
            factory_run_id=None,
            lifecycle_started=False,
            now=NOW_TEXT,
        )
        payload = build_campaign_terminal_report(
            campaign_id="campaign",
            configuration_id="configuration",
            run_id="run",
            cycle_id="cycle",
            report_id="report",
            factory_run_id=None,
            execution_id="20260726T172119Z-fixture",
            terminal_status="COMPLETED",
            terminal_cause=BLOCKED_INSUFFICIENT_GRADUATED_POOL,
            run_status="NOT_STARTED",
            lifecycle_started=False,
            reconciliation=reconciliation,
            forbidden_deltas={},
            launch_git_provenance=_provenance(),
            campaign_activity=reporting.get("campaign_activity"),
            blocked_supply=reporting.get("blocked_supply"),
            campaign_source_calls=reporting.get("campaign_source_calls"),
            campaign_scheduler_calls=reporting.get("campaign_scheduler_calls"),
            candidates_observed=reporting.get("candidates_observed"),
            candidates_validated=reporting.get("candidates_validated"),
            eligible_candidates=reporting.get("eligible_candidates"),
            required_token_capacity=reporting.get("required_token_capacity"),
            blocked_supply_reason=reporting.get("blocked_supply_reason"),
            pre_lifecycle_admission=reporting.get("pre_lifecycle_admission"),
        )
        return write_campaign_terminal_report(
            self.db,
            self.reports,
            report_id="report",
            campaign_id="campaign",
            configuration_id="configuration",
            report=payload,
            now=NOW,
        )

    def test_ledger_totals_and_blocked_supply_surface(self) -> None:
        totals = load_campaign_operation_totals(
            self.db, run_id="run", cycle_id="cycle"
        )
        self.assertEqual(totals["campaign_source_calls"], 4)
        surface = build_blocked_supply_reporting(
            required_token_capacity=2,
            candidates=_fixture_candidates(),
            blocked_supply_reason=BLOCKED_INSUFFICIENT_GRADUATED_POOL,
            campaign_source_calls=4,
            campaign_scheduler_calls=0,
        )
        self.assertEqual(surface["campaign_source_calls"], 4)
        self.assertEqual(surface["campaign_scheduler_calls"], 0)
        self.assertEqual(surface["required_token_capacity"], 2)
        self.assertEqual(surface["candidates_observed"], 2)
        self.assertEqual(surface["eligible_candidates"], 1)
        self.assertEqual(
            surface["blocked_supply_reason"], BLOCKED_INSUFFICIENT_GRADUATED_POOL
        )
        by_mint = {
            item["mint"]: item for item in surface["blocked_supply"]["candidates"]
        }
        self.assertEqual(by_mint[ELIGIBLE_MINT]["eligibility_result"], "eligible")
        self.assertIsNone(by_mint[ELIGIBLE_MINT]["rejection_or_exclusion_reason"])
        self.assertEqual(by_mint[ELIGIBLE_MINT]["liquidity"], 10248.29)
        self.assertEqual(by_mint[REJECTED_MINT]["eligibility_result"], "rejected")
        self.assertEqual(
            by_mint[REJECTED_MINT]["rejection_or_exclusion_reason"],
            LIQUIDITY_BELOW_SELECTION_FLOOR,
        )
        self.assertEqual(by_mint[REJECTED_MINT]["liquidity"], 9.06)

    def test_terminal_report_campaign_source_calls_and_replay(self) -> None:
        written = self._write_terminal()
        self.assertEqual(written["campaign_source_calls"], 4)
        self.assertEqual(written["source_calls"], 4)
        self.assertEqual(written["campaign_scheduler_calls"], 0)
        self.assertEqual(written["candidates_observed"], 2)
        self.assertEqual(written["eligible_candidates"], 1)
        self.assertEqual(written["required_token_capacity"], 2)
        self.assertEqual(
            written["blocked_supply_reason"], BLOCKED_INSUFFICIENT_GRADUATED_POOL
        )
        self.assertEqual(written["report_rows"], 1)
        self.assertEqual(written["artifact_count"], 1)

        artifact = self.reports / f"report{REPORT_ARTIFACT_SUFFIX}"
        stored = json.loads(artifact.read_text(encoding="utf-8"))
        self.assertEqual(stored["campaign_source_calls"], 4)
        self.assertEqual(stored["eligible_candidates"], 1)
        self.assertEqual(stored["required_token_capacity"], 2)
        rejected = [
            item
            for item in stored["blocked_supply"]["candidates"]
            if item["mint"] == REJECTED_MINT
        ][0]
        self.assertEqual(
            rejected["rejection_or_exclusion_reason"],
            LIQUIDITY_BELOW_SELECTION_FLOOR,
        )

        replay_a = replay_campaign_terminal_report(
            self.db,
            self.reports,
            report_id="report",
            campaign_id="campaign",
            configuration_id="configuration",
        )
        replay_b = replay_campaign_terminal_report(
            self.db,
            self.reports,
            report_id="report",
            campaign_id="campaign",
            configuration_id="configuration",
        )
        self.assertEqual(replay_a["campaign_source_calls"], 4)
        self.assertEqual(replay_a["replay_new_source_calls"], 0)
        self.assertEqual(replay_a["new_source_calls"], 0)
        self.assertEqual(replay_a["replay_new_scheduler_calls"], 0)
        self.assertEqual(replay_a["duplicate_reports_created"], 0)
        self.assertEqual(replay_a["database_writes"], 0)
        self.assertTrue(replay_a["artifact_matches"])
        self.assertEqual(replay_a["report_hash"], written["report_hash"])
        self.assertEqual(replay_b["report_hash"], replay_a["report_hash"])
        self.assertEqual(replay_a["eligible_candidates"], 1)
        self.assertEqual(replay_a["required_token_capacity"], 2)
        self.assertEqual(
            replay_a["report"]["pre_lifecycle_admission"][
                "terminal_classification"
            ],
            "COOLDOWN_REOPEN_REQUIRED",
        )

        rows = self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
        ).fetchone()[0]
        self.assertEqual(rows, 1)
        artifacts = sorted(self.reports.glob(f"*{REPORT_ARTIFACT_SUFFIX}"))
        self.assertEqual(len(artifacts), 1)

        locked_after = _locked_counts(self.connection)
        self.assertEqual(locked_after, self.locked_before)
        integrity = self.connection.execute("PRAGMA integrity_check").fetchone()[0]
        self.assertEqual(integrity, "ok")
        self.assertEqual(
            len(self.connection.execute("PRAGMA foreign_key_check").fetchall()), 0
        )

    def test_terminal_closure_zero_active_work_and_lease_release(self) -> None:
        lock_path = self.root / "campaign.lease.lock"
        acquire_campaign_supervision(
            self.db,
            lock_path=lock_path,
            supervision_id="supervision",
            campaign_id="campaign",
            configuration_id="configuration",
            run_id="run",
            owner_id="owner",
            lease_seconds=90,
        )
        # Match the public terminal order: cleanup/lease release before report write.
        cleanup = cleanup_campaign_supervision(
            self.db,
            supervision_id="supervision",
            campaign_id="campaign",
            configuration_id="configuration",
            run_id="run",
            owner_id="owner",
            terminal_status="COMPLETED",
            first_terminal_cause=BLOCKED_INSUFFICIENT_GRADUATED_POOL,
        )
        self.assertTrue(
            cleanup.get("cleanup_completed")
            or cleanup.get("supervision_state") == "TERMINAL"
            or cleanup.get("terminal_status") == "COMPLETED"
        )
        written = self._write_terminal()
        self.assertEqual(written["campaign_source_calls"], 4)
        row = self.connection.execute(
            """SELECT supervision_state, terminal_status, lease_released_at,
                      cleanup_completed_at
               FROM printer_memory_factory_campaign_supervision
               WHERE supervision_id='supervision'"""
        ).fetchone()
        self.assertEqual(row["supervision_state"], "TERMINAL")
        self.assertEqual(row["terminal_status"], "COMPLETED")
        self.assertIsNotNone(row["lease_released_at"])
        self.assertIsNotNone(row["cleanup_completed_at"])
        active = self.connection.execute(
            """SELECT COUNT(*) FROM printer_scheduler_jobs
               WHERE status IN ('PENDING','RUNNING','CLAIMED')
                  OR locked_at IS NOT NULL OR lock_owner IS NOT NULL"""
        ).fetchone()[0]
        self.assertEqual(active, 0)
        self.assertFalse(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
