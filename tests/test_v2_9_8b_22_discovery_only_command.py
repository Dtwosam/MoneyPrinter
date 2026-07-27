"""V2-9.8B.22 discovery-only qualification command disposable proofs.

Fixture sources and disposable SQLite only. No production campaign, no live
network, no retrieval/financial activation, no automatic retry/successor.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import _fisher_yates
from printer_v1.discovery.eligible_token_supply import (
    BUDGET_EXHAUSTION,
    DURATION_EXHAUSTION,
    SOURCE_AVAILABILITY_FAILURE,
    TRUE_MARKET_SUPPLY_SHORTAGE,
)
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.pumpswap_graduated_registry import (
    PERSISTED_GRADUATED_CHANNEL,
    record_graduated_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE = ROOT / "data" / "printer_v1.sqlite3"
NOW = "2026-07-27T22:30:00+00:00"
PS1 = ROOT / "scripts" / "Start-PrinterV1-MemoryFactory.ps1"


def _provenance() -> dict[str, object]:
    return {
        "git_head": "c" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW,
    }


def _ready_preflight() -> dict[str, object]:
    return {
        "status": "V2_9_8_OPERATIONAL_PREFLIGHT_READY",
        "database_path": "disposable",
        "database_sha256": "a" * 64,
        "migration_count": 46,
        "canonical_migration_count": 46,
        "latest_migration": "046_eligible_token_supply.sql",
        "integrity": "ok",
        "foreign_key_violations": 0,
        "active_counts": {},
        "source_calls": 0,
        "scheduler_runtime_calls": 0,
        "database_writes": 0,
        "git_provenance": _provenance(),
    }


class _Dependency:
    status = "READY"

    def to_dict(self):
        return {"status": "READY", "external_requests": 0, "database_writes": 0}


def _more_specs(n: int) -> list[tuple[str, str, str]]:
    import hashlib

    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

    def b58(data: bytes) -> str:
        n_int = int.from_bytes(data, "big")
        out = []
        while n_int > 0:
            n_int, r = divmod(n_int, 58)
            out.append(alphabet[r])
        pad = 0
        for b in data:
            if b == 0:
                pad += 1
            else:
                break
        return ("1" * pad) + "".join(reversed(out))

    specs: list[tuple[str, str, str]] = []
    for i in range(n):
        mint = b58(hashlib.sha256(f"v298b22-mint-{i}".encode()).digest())
        pool = b58(hashlib.sha256(f"v298b22-pool-{i}".encode()).digest())
        sig = b58(
            hashlib.sha256(f"v298b22-sig-{i}-a".encode()).digest()
            + hashlib.sha256(f"v298b22-sig-{i}-b".encode()).digest()
        )
        specs.append((mint, sig, pool))
    return specs


SPECS20 = _more_specs(20)


def _pair_payload(pool: str, mint: str, liquidity: float | None):
    return {
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": pool,
                "baseToken": {"address": mint, "symbol": "MEME", "name": "Meme"},
                "priceUsd": "0.10",
                "liquidity": ({} if liquidity is None else {"usd": liquidity}),
                "volume": {"m5": 100.0, "h1": 1000.0, "h24": 10000.0},
                "txns": {"m5": {"buys": 3, "sells": 2}},
                "priceChange": {"m5": 1.0},
                "marketCap": 50_000.0 if liquidity and liquidity >= 3000 else 5.0,
            }
        ]
    }


def _dex_factory(payload_by_pool: dict):
    def factory(mint, pool):
        if pool not in payload_by_pool:
            return fixture_success_transport({"pairs": []})
        return fixture_success_transport(payload_by_pool[pool])

    return factory


def _empty_migration_transport():
    def transport(context):
        return {
            "request_kind": "pumpfun_migration_stream",
            "source_name": "pumpportal",
            "tokens": [],
        }

    return transport


def _failing_migration_transport():
    def transport(context):
        return {
            "request_kind": "pumpfun_migration_stream",
            "source_name": "pumpportal",
            "fixture_status": "failure",
            "failure_type": "provider_unavailable",
            "tokens": [],
        }

    return transport


def _seed_registry(connection, specs, *, now=NOW):
    for mint, sig, pool in specs:
        record_graduated_candidate(
            connection,
            mint=mint,
            migration_signature=sig,
            pumpswap_pool=pool,
            graduation_block_time=1_784_000_000,
            graduation_slot=1,
            now=now,
            discovery_channel=PERSISTED_GRADUATED_CHANNEL,
        )
    connection.commit()


def _first_round_order(specs: list[tuple[str, str, str]], cycle_seed: str) -> list[str]:
    rows = sorted(
        [{"mint_identity": m} for m, _s, _p in specs],
        key=lambda r: str(r["mint_identity"]),
    )
    shuffled = _fisher_yates(rows, f"{cycle_seed}|ROUND_1|REFRESH_PERSISTED")
    return [str(r["mint_identity"]) for r in shuffled]


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


def _quiesce(db: Path) -> None:
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            UPDATE printer_scheduler_jobs
            SET status='CANCELLED', finished_at=COALESCE(finished_at, ?),
                updated_at=?, locked_at=NULL, lock_owner=NULL
            WHERE status IN ('PENDING', 'RUNNING')
               OR locked_at IS NOT NULL OR lock_owner IS NOT NULL
            """,
            (NOW, NOW),
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_campaigns
            SET campaign_state='TERMINAL_COMPLETED', updated_at=?
            WHERE campaign_state IN ('PREFLIGHT', 'RUNNING', 'STOP_REQUESTED', 'DRAFT')
            """,
            (NOW,),
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_campaign_runs
            SET run_state='TERMINAL_COMPLETED', updated_at=?
            WHERE run_state IN ('RUNNING', 'STOP_REQUESTED')
            """,
            (NOW,),
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_campaign_supervision
            SET supervision_state='TERMINAL',
                terminal_status=COALESCE(terminal_status, 'COMPLETED'),
                updated_at=?
            WHERE supervision_state IN ('ACTIVE', 'STOPPING')
            """,
            (NOW,),
        )
        connection.execute(
            """
            UPDATE printer_discovery_work
            SET work_state='TERMINAL', updated_at=?
            WHERE work_state IN ('PENDING', 'RUNNING', 'COOLDOWN')
            """,
            (NOW,),
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_run_steps
            SET step_status='SKIPPED', updated_at=?
            WHERE step_status IN ('PENDING', 'RUNNING')
            """,
            (NOW,),
        )
        connection.execute(
            """
            UPDATE printer_proof_run_supervision
            SET execution_status='TERMINAL', updated_at=?
            WHERE execution_status IN ('STARTING', 'RUNNING')
            """,
            (NOW,),
        )
        connection.commit()
    finally:
        connection.close()


class _FixedDateTime:
    @staticmethod
    def now(tz=None):
        from datetime import datetime, timezone

        return datetime(2026, 7, 27, 22, 30, 0, tzinfo=timezone.utc)

    @staticmethod
    def fromisoformat(value):
        from datetime import datetime

        return datetime.fromisoformat(value)


class PublicSurfaceAndApprovalTests(unittest.TestCase):
    def test_python_requires_operator_approval(self) -> None:
        with self.assertRaises(command.OperationalMemoryFactoryError) as raised:
            command.run_discovery_only_qualification(operator_approved=False)
        self.assertIn("operator approval", str(raised.exception).lower())

    def test_main_requires_operator_approval(self) -> None:
        stderr = io.StringIO()
        with patch.object(sys, "stderr", stderr):
            code = command.main(["discovery-only"])
        self.assertEqual(code, 1)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["mode"], "discovery-only")
        self.assertIn("operator approval", payload["error_message"].lower())
        self.assertFalse(payload["restart_created"])
        self.assertFalse(payload["successor_created"])

    def test_powershell_validate_set_includes_discovery_only(self) -> None:
        text = PS1.read_text(encoding="utf-8")
        self.assertIn("discovery-only", text)
        self.assertIn("ValidateSet", text)
        self.assertIn("OperatorApproved", text)

    def test_powershell_wrapper_accepts_discovery_only_on_macos(self) -> None:
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh not available")
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        with tempfile.TemporaryDirectory(dir=parent) as temporary:
            probe = Path(temporary) / "probe.ps1"
            probe.write_text(
                PS1.read_text(encoding="utf-8").replace(
                    "Join-Path $repository '.venv/bin/python'",
                    f"Join-Path '{Path(temporary).as_posix()}' 'missing-python'",
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    pwsh,
                    "-NoProfile",
                    "-File",
                    str(probe),
                    "-Mode",
                    "discovery-only",
                    "-OperatorApproved",
                ],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
                check=False,
            )
        combined = (completed.stdout or "") + (completed.stderr or "")
        self.assertNotIn("Cannot validate argument on parameter 'Mode'", combined)
        self.assertIn("interpreter is unavailable", combined.lower())

    def test_powershell_rejects_unknown_mode(self) -> None:
        pwsh = shutil.which("pwsh")
        if pwsh is None:
            self.skipTest("pwsh not available")
        completed = subprocess.run(
            [
                pwsh,
                "-NoProfile",
                "-File",
                str(PS1),
                "-Mode",
                "not-a-real-mode",
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            check=False,
        )
        combined = (completed.stdout or "") + (completed.stderr or "")
        self.assertNotEqual(completed.returncode, 0)
        self.assertTrue(
            "ValidateSet" in combined
            or "Cannot validate argument on parameter 'Mode'" in combined
            or "discovery-only" in combined
        )

    def test_main_discovery_only_success_path(self) -> None:
        stdout = io.StringIO()
        with patch.object(sys, "stdout", stdout), patch.object(
            command,
            "run_discovery_only_qualification",
            return_value={
                "mode": "discovery-only",
                "status": command.DISCOVERY_ONLY_CAPACITY_READY,
                "scheduler_runtime_calls": 0,
                "restart_created": False,
                "successor_created": False,
            },
        ):
            code = command.main(["discovery-only", "--operator-approved"])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["mode"], "discovery-only")


class PreflightGateTests(unittest.TestCase):
    def setUp(self) -> None:
        if not AUTHORITATIVE.is_file():
            self.skipTest("authoritative corpus unavailable")
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.db = self.root / "printer_v1.sqlite3"
        shutil.copy2(AUTHORITATIVE, self.db)
        apply_migrations(self.db)
        _quiesce(self.db)
        self.source_ready = {
            "status": "READY",
            "external_requests": 0,
            "secret_material_recorded": False,
        }
        self.patches = [
            patch.object(command, "AUTHORITATIVE_DB", self.db.resolve()),
            patch.object(
                command,
                "build_readiness_source_contract_preflight",
                return_value=self.source_ready,
            ),
            patch.object(
                command,
                "assert_runtime_dependency_preflight",
                return_value=_Dependency(),
            ),
            patch.object(
                command,
                "_capture_operational_git_provenance",
                return_value=_provenance(),
            ),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def test_rejected_on_dirty_git(self) -> None:
        with patch.object(
            command,
            "build_activation_preflight",
            side_effect=command.OperationalMemoryFactoryError(
                "operational preflight blocked: gate=git_provenance: dirty"
            ),
        ):
            with self.assertRaises(command.OperationalMemoryFactoryError) as raised:
                command.run_discovery_only_qualification(operator_approved=True)
        self.assertIn("gate=git_provenance", str(raised.exception))

    def test_rejected_on_migration_mismatch(self) -> None:
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                "DELETE FROM printer_schema_migrations WHERE version LIKE '046%'"
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(command.OperationalMemoryFactoryError) as raised:
            command.run_discovery_only_qualification(operator_approved=True)
        self.assertIn("gate=migration_ledger", str(raised.exception))

    def test_rejected_on_active_work(self) -> None:
        connection = sqlite3.connect(self.db)
        try:
            row = connection.execute(
                "SELECT campaign_id FROM printer_memory_factory_campaigns LIMIT 1"
            ).fetchone()
            if row is None:
                self.skipTest("no campaign row")
            connection.execute(
                """
                UPDATE printer_memory_factory_campaigns
                SET campaign_state='RUNNING',
                    first_terminal_cause=NULL,
                    terminal_at=NULL,
                    updated_at=?
                WHERE campaign_id=?
                """,
                (NOW, row[0]),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(command.OperationalMemoryFactoryError) as raised:
            command.run_discovery_only_qualification(operator_approved=True)
        self.assertIn("gate=active_operational_state", str(raised.exception))

    def test_rejected_on_missing_dependency(self) -> None:
        class _BadDep:
            status = "NOT_READY"

            def to_dict(self):
                return {"status": "NOT_READY"}

        with patch.object(
            command,
            "assert_runtime_dependency_preflight",
            return_value=_BadDep(),
        ):
            with self.assertRaises(command.OperationalMemoryFactoryError) as raised:
                command.run_discovery_only_qualification(operator_approved=True)
        self.assertIn("gate=runtime_dependency", str(raised.exception))


class DiscoveryOnlyQualificationTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.db = self.root / "printer_v1.sqlite3"
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        apply_migrations(self.db)
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.locked_before = _locked_counts(self.connection)
        self.patches = [
            patch.object(command, "AUTHORITATIVE_DB", self.db.resolve()),
            patch.object(command, "ARTIFACT_ROOT", self.artifacts.resolve()),
            patch.object(
                command,
                "build_activation_preflight",
                return_value=_ready_preflight(),
            ),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self.patches):
            p.stop()
        self.connection.close()
        self.temp.cleanup()

    def _run_qualification(self, **kwargs):
        defaults = {
            "operator_approved": True,
            "migration_transport": _empty_migration_transport(),
            "now": NOW,
            "collection_rounds": 1,
            "max_candidates": 5,
            "settle_seconds": 0.0,
            "reverify_on_transient": False,
            "reverify_settle_seconds": 0.0,
            "front_door_max_candidates": 6,
            "run_locator": False,
            "discovery_operation_budget": 30,
            "duration_seconds": 900,
        }
        defaults.update(kwargs)
        return command.run_discovery_only_qualification(**defaults)

    def _fixed_exec_run(self, hex12: str, **kwargs):
        with patch.object(command, "datetime", _FixedDateTime), patch(
            "uuid.uuid4"
        ) as uuid4:
            uuid4.return_value.hex = hex12 + "000000000000"
            return self._run_qualification(**kwargs)

    def test_two_eligible_outside_first_six_and_stop_at_two(self) -> None:
        specs = SPECS20
        _seed_registry(self.connection, specs)
        fixed_exec = "20260727T223000Z-aabbccddeeff"
        order = _first_round_order(specs, fixed_exec)
        eligible_a = order[7]
        eligible_b = order[19]
        first_six = set(order[:6])
        self.assertNotIn(eligible_a, first_six)
        self.assertNotIn(eligible_b, first_six)
        payloads = {
            pool: _pair_payload(
                pool, mint, 15_000.0 if mint in {eligible_a, eligible_b} else 40.0
            )
            for mint, _sig, pool in specs
        }
        result = self._fixed_exec_run(
            "aabbccddeeff",
            dexscreener_transport_factory=_dex_factory(payloads),
        )
        self.assertEqual(result["mode"], "discovery-only")
        self.assertEqual(result["status"], command.DISCOVERY_ONLY_CAPACITY_READY)
        self.assertEqual(result["eligible_reserve_count"], 2)
        self.assertEqual(set(result["selected_candidate_mints"]), {eligible_a, eligible_b})
        self.assertGreaterEqual(result["discovery_rounds"], 2)
        self.assertEqual(result["scheduler_runtime_calls"], 0)
        self.assertFalse(result["restart_created"])
        self.assertFalse(result["successor_created"])
        self.assertIsNone(result["shortage_classification"])
        self.assertIsNone(result["exhaustion_certificate"])
        self.assertEqual(result["protected_table_deltas"], {})
        self.assertFalse(any(result["active_residue"].values()))
        camps = int(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaigns"
            ).fetchone()[0]
        )
        self.assertEqual(camps, 0)
        jobs = int(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
            ).fetchone()[0]
        )
        self.assertEqual(jobs, 0)
        steps = int(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
            ).fetchone()[0]
        )
        self.assertEqual(steps, 0)
        report = Path(result["report_path"])
        self.assertTrue(report.is_file())

    def test_round1_eligible_preserved_across_rounds(self) -> None:
        specs = SPECS20[:12]
        _seed_registry(self.connection, specs)
        fixed_exec = "20260727T223000Z-bbccddeeffaa"
        order = _first_round_order(specs, fixed_exec)
        eligible_first = order[0]
        eligible_later = order[7]
        payloads = {
            pool: _pair_payload(
                pool,
                mint,
                20_000.0 if mint in {eligible_first, eligible_later} else 10.0,
            )
            for mint, _s, pool in specs
        }
        result = self._fixed_exec_run(
            "bbccddeeffaa",
            dexscreener_transport_factory=_dex_factory(payloads),
        )
        self.assertEqual(result["status"], command.DISCOVERY_ONLY_CAPACITY_READY)
        found = set(result["selected_candidate_mints"])
        self.assertIn(eligible_first, found)
        self.assertIn(eligible_later, found)
        self.assertGreaterEqual(result["discovery_rounds"], 2)

    def test_one_token_universe_honest_exhaustion_certificate(self) -> None:
        specs = SPECS20[:1]
        _seed_registry(self.connection, specs)
        mint, _s, pool = specs[0]
        payloads = {pool: _pair_payload(pool, mint, 12_000.0)}
        result = self._run_qualification(
            dexscreener_transport_factory=_dex_factory(payloads),
        )
        self.assertEqual(result["status"], command.DISCOVERY_ONLY_HONEST_EXHAUSTION)
        self.assertEqual(result["eligible_reserve_count"], 1)
        self.assertIsNotNone(result["exhaustion_certificate"])
        self.assertEqual(
            result["shortage_classification"], TRUE_MARKET_SUPPLY_SHORTAGE
        )
        self.connection.close()
        self.connection = sqlite3.connect(self.db)
        cert_rows = self.connection.execute(
            "SELECT COUNT(*) FROM printer_discovery_exhaustion_certificates"
        ).fetchone()[0]
        self.assertGreaterEqual(int(cert_rows), 1)

    def test_provider_budget_duration_distinct(self) -> None:
        result_provider = self._run_qualification(
            migration_transport=_failing_migration_transport(),
            dexscreener_transport_factory=_dex_factory({}),
        )
        self.assertIn(
            result_provider["status"],
            {
                command.DISCOVERY_ONLY_SOURCE_UNAVAILABLE,
                command.DISCOVERY_ONLY_HONEST_EXHAUSTION,
                command.DISCOVERY_ONLY_FAILED,
            },
        )
        if result_provider["shortage_classification"] == SOURCE_AVAILABILITY_FAILURE:
            self.assertEqual(
                result_provider["status"], command.DISCOVERY_ONLY_SOURCE_UNAVAILABLE
            )

        specs = SPECS20
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 10.0) for mint, _s, pool in specs
        }
        result_budget = self._run_qualification(
            dexscreener_transport_factory=_dex_factory(payloads),
            discovery_operation_budget=3,
        )
        self.assertEqual(result_budget["status"], command.DISCOVERY_ONLY_BUDGET_EXHAUSTED)
        self.assertEqual(result_budget["shortage_classification"], BUDGET_EXHAUSTION)
        self.assertNotEqual(
            result_budget["shortage_classification"], TRUE_MARKET_SUPPLY_SHORTAGE
        )

        result_duration = self._run_qualification(
            dexscreener_transport_factory=_dex_factory(payloads),
            duration_seconds=0,
            discovery_operation_budget=30,
        )
        if result_duration["shortage_classification"] == DURATION_EXHAUSTION:
            self.assertEqual(
                result_duration["status"], command.DISCOVERY_ONLY_DURATION_EXHAUSTED
            )
            self.assertNotEqual(
                result_duration["shortage_classification"], TRUE_MARKET_SUPPLY_SHORTAGE
            )

    def test_budget_and_source_ceiling_enforced(self) -> None:
        specs = SPECS20
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 10.0) for mint, _s, pool in specs
        }
        result = self._run_qualification(
            dexscreener_transport_factory=_dex_factory(payloads),
            discovery_operation_budget=5,
        )
        self.assertLessEqual(result["source_operations_used"], 5)
        self.assertEqual(
            result["source_operations_remaining"],
            max(0, 5 - result["source_operations_used"]),
        )
        self.assertEqual(result["scheduler_runtime_calls"], 0)

    def test_deterministic_non_ranked_selection(self) -> None:
        specs = SPECS20[:4]
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 12_000.0) for mint, _s, pool in specs
        }
        a = self._run_qualification(
            dexscreener_transport_factory=_dex_factory(payloads),
        )
        b = self._run_qualification(
            dexscreener_transport_factory=_dex_factory(payloads),
        )
        self.assertEqual(a["status"], command.DISCOVERY_ONLY_CAPACITY_READY)
        self.assertEqual(b["status"], command.DISCOVERY_ONLY_CAPACITY_READY)
        self.assertEqual(a["selected_candidate_mints"], b["selected_candidate_mints"])
        self.assertEqual(
            a["selected_candidate_mints"],
            sorted(a["selected_candidate_mints"]),
        )

    def test_status_and_report_only_inspect_qualification(self) -> None:
        specs = SPECS20[:4]
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 12_000.0) for mint, _s, pool in specs
        }
        qual = self._run_qualification(
            dexscreener_transport_factory=_dex_factory(payloads),
        )
        self.assertEqual(qual["status"], command.DISCOVERY_ONLY_CAPACITY_READY)
        before = self.db.read_bytes()
        status = command.operational_status()
        report = command.report_only()
        self.assertEqual(status["source_calls"], 0)
        self.assertEqual(status["scheduler_runtime_calls"], 0)
        self.assertEqual(status["database_writes"], 0)
        self.assertIsNotNone(status["discovery_only_qualification"])
        self.assertEqual(
            status["discovery_only_qualification"]["qualification_id"],
            qual["qualification_id"],
        )
        self.assertEqual(report["source_calls"], 0)
        self.assertEqual(report["scheduler_runtime_calls"], 0)
        self.assertEqual(report["database_writes"], 0)
        self.assertEqual(report["report_kind"], "discovery-only")
        self.assertEqual(report["qualification_id"], qual["qualification_id"])
        self.assertEqual(before, self.db.read_bytes())

    def test_failure_leaves_zero_active_residue(self) -> None:
        with patch(
            "printer_v1.discovery.eligible_token_supply.run_persistent_eligible_token_supply",
            side_effect=RuntimeError("forced disposable failure"),
        ):
            result = self._run_qualification()
        self.assertEqual(result["status"], command.DISCOVERY_ONLY_FAILED)
        self.assertFalse(any(result["active_residue"].values()))
        self.assertFalse(result["restart_created"])
        self.assertFalse(result["successor_created"])
        self.assertFalse(result["automatic_retry_created"])
        self.assertEqual(result["scheduler_runtime_calls"], 0)

    def test_integrity_fk_locked_deltas_and_no_successor(self) -> None:
        specs = SPECS20[:8]
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 12_000.0) for mint, _s, pool in specs
        }
        result = self._run_qualification(
            dexscreener_transport_factory=_dex_factory(payloads),
        )
        self.assertEqual(result["status"], command.DISCOVERY_ONLY_CAPACITY_READY)
        self.assertEqual(result["integrity"], "ok")
        self.assertEqual(result["foreign_key_violations"], 0)
        self.assertEqual(result["protected_table_deltas"], {})
        self.connection.close()
        self.connection = sqlite3.connect(self.db)
        locked_after = _locked_counts(self.connection)
        for table, before in self.locked_before.items():
            self.assertEqual(
                locked_after[table],
                before,
                msg=f"locked capability delta on {table}",
            )
        self.assertFalse(result["restart_created"])
        self.assertFalse(result["successor_created"])
        reports = list(
            self.artifacts.glob(f"*/{command.DISCOVERY_ONLY_REPORT_FILENAME}")
        )
        self.assertEqual(len(reports), 1)

    def test_public_result_schema_fields_present(self) -> None:
        specs = SPECS20[:3]
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 12_000.0) for mint, _s, pool in specs
        }
        result = self._run_qualification(
            dexscreener_transport_factory=_dex_factory(payloads),
        )
        required = [
            "mode",
            "execution_id",
            "qualification_id",
            "status",
            "discovery_rounds",
            "candidates_observed",
            "unique_candidates_observed",
            "duplicate_candidates_removed",
            "candidates_validated",
            "eligible_reserve_count",
            "required_token_capacity",
            "selected_candidate_mints",
            "source_operations_used",
            "source_operations_remaining",
            "scheduler_runtime_calls",
            "database_writes",
            "shortage_classification",
            "exhaustion_certificate",
            "report_path",
            "restart_created",
            "successor_created",
        ]
        for field in required:
            self.assertIn(field, result)
        self.assertEqual(result["mode"], "discovery-only")
        self.assertIn(result["status"], command.DISCOVERY_ONLY_TERMINAL_STATUSES)


if __name__ == "__main__":
    unittest.main()
