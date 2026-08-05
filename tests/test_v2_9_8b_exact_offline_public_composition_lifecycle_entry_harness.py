"""Focused deterministic proof: offline exact public composition lifecycle entry.

Proves the harness remapper and production preflight matrix for disposable
Migration-050 offline composition. Does **not** execute the exact public
composition node
``test_exact_public_coordinator_owner_driver_factory_composition``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.combined_executor import FixturePumpSwapProof
from printer_v1.operator_cli import operational_memory_factory_command as public_command
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    LivePumpOriginAdapter,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    STOP_PREFLIGHT,
    run_one_command_15m_factory,
)
from printer_v1.operator_cli.origin_lifecycle_campaign import (
    OriginToLifecycleCampaignDriver,
)
from printer_v1.operator_cli.proof_db_schema_readiness import CANONICAL_PERSISTENT_DB
from printer_v1.sources.campaign_six_unit_accounting import CampaignActionLocalLedger
from printer_v1.sources.governed_execution import build_fixture_source_adapter

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
import test_v2_9_7e_9_two_token_continuous_lifecycle as e9
from tests.support.window_15m_authorization_fixtures import (
    validated_window_15m_authorization,
)
import test_v2_9_7e_11_authoritative_live_operational_campaign as e11
from test_v2_9_8b_token_slot_id_exact_public_composition import (
    OFFLINE_EXACT_LIFECYCLE_ENTRY_OPERATIONAL_NATURAL,
    OFFLINE_EXACT_LIFECYCLE_ENTRY_OPERATIONAL_PERSISTENT,
    OFFLINE_EXACT_LIFECYCLE_ENTRY_PROOF_MODE,
    _ExactPublicCompositionOwner,
    _NoopHeartbeat,
    offline_exact_public_composition_lifecycle_entry,
)


GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)
CORPUS_REASON = "operational persistent mode requires the authoritative corpus"
NATURAL_REASON = (
    "operational natural 15m-only mode requires operational persistent mode"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _LifecycleEntryCapture:
    """Record inbound owner flags and effective remapped factory entry flags."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, db_path, backup_path, **kwargs):
        inbound = dict(kwargs)
        effective = dict(kwargs)
        effective["proof_mode"] = OFFLINE_EXACT_LIFECYCLE_ENTRY_PROOF_MODE
        effective["operational_persistent_mode"] = (
            OFFLINE_EXACT_LIFECYCLE_ENTRY_OPERATIONAL_PERSISTENT
        )
        effective["continuous_first_hour"] = False
        effective["continuous_four_hour"] = False
        effective["four_hour_proof_mode"] = False
        effective["operational_natural_disposition"] = (
            OFFLINE_EXACT_LIFECYCLE_ENTRY_OPERATIONAL_NATURAL
        )
        self.calls.append(
            {
                "db_path": Path(db_path).resolve(),
                "backup_path": Path(backup_path).resolve(),
                "inbound": inbound,
                "effective": effective,
            }
        )
        return offline_exact_public_composition_lifecycle_entry(
            db_path, backup_path, **kwargs
        )


class OfflineExactLifecycleEntryHarnessProof(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "disposable-mig050.sqlite3"
        self.backup = self.root / "disposable-mig050.backup.sqlite3"
        self.artifact_root = self.root / "public-artifacts"
        apply_migrations(self.db)
        apply_migrations(self.backup)

    def _empty_discovery(self, _args):
        return {
            "selection_handoff_report": {
                "batch_id": "entry-proof-batch",
                "selection_seed": "entry-proof-seed",
                "eligible_pool_size": 0,
            },
            "discovery_results": [],
        }

    def test_ordinary_public_15m_operational_mode_requires_authoritative_corpus(
        self,
    ) -> None:
        """#1 Ordinary public 15m operational mode still requires corpus."""
        result = run_one_command_15m_factory(
            self.db,
            self.backup,
            operator_approved=True,
            proof_mode=False,
            operational_persistent_mode=True,
            operational_natural_disposition=True,
            total_duration_seconds=3.0,
            _window_seconds=0.05,
            discovery_runner=self._empty_discovery,
            launch_provenance=e8._provenance(),
        )
        self.assertEqual("SAFE_STOPPED", result["run_status"])
        self.assertEqual(STOP_PREFLIGHT, result["stop_reason"])
        self.assertIn(CORPUS_REASON, result["blocked_reasons"])

    def test_disposable_db_plus_operational_persistent_safe_stops(self) -> None:
        """#2 Disposable DB + operational-persistent still safe-stops."""
        result = run_one_command_15m_factory(
            self.db,
            self.backup,
            operator_approved=True,
            proof_mode=False,
            operational_persistent_mode=True,
            total_duration_seconds=3.0,
            _window_seconds=0.05,
            discovery_runner=self._empty_discovery,
            launch_provenance=e8._provenance(),
        )
        self.assertEqual(STOP_PREFLIGHT, result["stop_reason"])
        self.assertIn(CORPUS_REASON, result["blocked_reasons"])
        # Factory run must not be created on preflight stop.
        connection = sqlite3.connect(self.db)
        try:
            runs = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_runs"
                ).fetchone()[0]
            )
        finally:
            connection.close()
        self.assertEqual(0, runs)

    def test_previous_safe_stop_preflight_failed_remains_negative(self) -> None:
        """#15 Prior SAFE_STOP_PREFLIGHT_FAILED case remains a negative test."""
        # Reproduce the exact harness defect shape: public 15m mapping flags
        # against a disposable DB, without the remapper.
        result = run_one_command_15m_factory(
            self.db,
            self.backup,
            operator_approved=True,
            proof_mode=False,
            operational_persistent_mode=True,
            operational_natural_disposition=True,
            total_duration_seconds=3.0,
            _window_seconds=0.05,
            discovery_runner=self._empty_discovery,
            launch_provenance=e8._provenance(),
        )
        self.assertEqual("SAFE_STOPPED", result["run_status"])
        self.assertEqual(STOP_PREFLIGHT, result["stop_reason"])
        self.assertEqual(
            [CORPUS_REASON],
            [reason for reason in result["blocked_reasons"] if reason == CORPUS_REASON],
        )

    def test_proof_mode_plus_operational_natural_15m_still_safe_stops(self) -> None:
        """Natural 15m-only still requires operational-persistent (preflight intact)."""
        result = run_one_command_15m_factory(
            self.db,
            self.backup,
            operator_approved=True,
            proof_mode=True,
            operational_persistent_mode=False,
            operational_natural_disposition=True,
            total_duration_seconds=3.0,
            _window_seconds=0.05,
            discovery_runner=self._empty_discovery,
            launch_provenance=e8._provenance(),
        )
        self.assertEqual(STOP_PREFLIGHT, result["stop_reason"])
        self.assertIn(NATURAL_REASON, result["blocked_reasons"])

    def test_remapper_forces_lawful_disposable_proof_entry_flags(self) -> None:
        """Remapper contract: proof_mode on, persistent/natural off, no 1h/4h."""
        captured: dict = {}

        def fake_factory(db_path, backup_path, **kwargs):
            captured["db_path"] = Path(db_path).resolve()
            captured["kwargs"] = dict(kwargs)
            return {
                "command": "one-command-15m-factory",
                "run_status": "SAFE_STOPPED",
                "stop_reason": "SAFE_STOP_EMPTY_QUALIFIED_POOL",
            }

        with patch(
            "test_v2_9_8b_token_slot_id_exact_public_composition."
            "run_one_command_15m_factory",
            side_effect=fake_factory,
        ):
            offline_exact_public_composition_lifecycle_entry(
                self.db,
                self.backup,
                operator_approved=True,
                proof_mode=False,
                operational_persistent_mode=True,
                operational_natural_disposition=True,
                continuous_first_hour=True,
                continuous_four_hour=True,
                four_hour_proof_mode=True,
                discovery_runner=self._empty_discovery,
            )
        kwargs = captured["kwargs"]
        self.assertEqual(self.db.resolve(), captured["db_path"])
        self.assertTrue(kwargs["proof_mode"])
        self.assertFalse(kwargs["operational_persistent_mode"])
        self.assertFalse(kwargs["operational_natural_disposition"])
        self.assertFalse(kwargs["continuous_first_hour"])
        self.assertFalse(kwargs["continuous_four_hour"])
        self.assertFalse(kwargs["four_hour_proof_mode"])
        self.assertTrue(OFFLINE_EXACT_LIFECYCLE_ENTRY_PROOF_MODE)
        self.assertFalse(OFFLINE_EXACT_LIFECYCLE_ENTRY_OPERATIONAL_PERSISTENT)
        self.assertFalse(OFFLINE_EXACT_LIFECYCLE_ENTRY_OPERATIONAL_NATURAL)

    def test_approved_offline_entry_reaches_factory_in_proof_mode(self) -> None:
        """#3 Approved offline path enters lifecycle in proof mode."""
        result = offline_exact_public_composition_lifecycle_entry(
            self.db,
            self.backup,
            operator_approved=True,
            # Hostile public-path flags — remapper must neutralize them.
            proof_mode=False,
            operational_persistent_mode=True,
            operational_natural_disposition=True,
            total_duration_seconds=3.0,
            _window_seconds=0.05,
            discovery_runner=self._empty_discovery,
            launch_provenance=e8._provenance(),
        )
        # Empty pool is after preflight; proves entry succeeded.
        self.assertNotEqual(STOP_PREFLIGHT, result.get("stop_reason"))
        self.assertEqual("SAFE_STOPPED", result["run_status"])
        self.assertEqual("SAFE_STOP_EMPTY_QUALIFIED_POOL", result["stop_reason"])
        # db_mode is present once a factory run is created; empty-pool stops may
        # still carry it when the run row was inserted before the empty stop.
        if result.get("db_mode") is not None:
            self.assertEqual("PROOF_ONLY", result["db_mode"])
        if isinstance(result.get("config"), dict):
            self.assertEqual("PROOF_ONLY", result["config"]["db_mode"])
            self.assertEqual(
                str(self.db.resolve()),
                str(Path(result["config"]["db_path"]).resolve()),
            )

    def test_canonical_persistent_db_identity_unchanged(self) -> None:
        """Production corpus identity is not patched by the harness."""
        canonical = Path(CANONICAL_PERSISTENT_DB).resolve()
        self.assertNotEqual(canonical, self.db.resolve())
        self.assertTrue(str(canonical).endswith("data/printer_v1.sqlite3"))

    def test_public_defaults_matrix_still_requires_corpus(self) -> None:
        """Production defaults: proof_mode=False + operational_persistent=True."""
        # Simulates owner mapping for fifteen_minute_only=True without remapper.
        result = run_one_command_15m_factory(
            self.db,
            self.backup,
            operator_approved=True,
            proof_mode=False,
            operational_persistent_mode=True,
            continuous_first_hour=False,
            continuous_four_hour=False,
            four_hour_proof_mode=False,
            operational_natural_disposition=True,
            total_duration_seconds=3.0,
            _window_seconds=0.05,
            discovery_runner=self._empty_discovery,
            launch_provenance=e8._provenance(),
        )
        self.assertEqual(STOP_PREFLIGHT, result["stop_reason"])
        self.assertIn(CORPUS_REASON, result["blocked_reasons"])


class OfflineExactLifecycleEntryCompositionProof(unittest.TestCase):
    """Focused public-chain composition through the remapped lifecycle entry.

    This is not the exact public-composition node. It proves the approved
    offline entry completes two compressed WINDOW_15M lifecycles through the
    real public coordinator → owner → driver → factory chain.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "dtw23-lifecycle-entry.sqlite3"
        self.artifact_root = self.root / "public-artifacts"
        apply_migrations(self.db)

    @staticmethod
    def _snapshot_factory(pools, calls):
        def build(*, token_mint, timeout_seconds):
            del timeout_seconds
            calls.append(token_mint)
            return build_fixture_source_adapter(
                "dexscreener",
                fixture_payload={
                    "pairs": [
                        {
                            "chain": "solana",
                            "token_mint": token_mint,
                            "pair_address": pools[token_mint],
                            "price_usd": 1.0,
                            "liquidity_usd": 10000.0,
                            "volume_5m": 500.0,
                            "volume_1h": 2000.0,
                            "volume_24h": 10000.0,
                            "txns_5m": 10,
                            "txns_1h": 50,
                            "txns_24h": 500,
                            "buys_5m": 7,
                            "sells_5m": 3,
                            "buys_1h": 30,
                            "sells_1h": 20,
                            "buys_24h": 280,
                            "sells_24h": 220,
                            "price_change_5m": 0.0,
                            "price_change_1h": 0.0,
                            "price_change_24h": 0.0,
                        }
                    ]
                },
            )

        return build

    @staticmethod
    def _context_factories(clock):
        def market(**_kwargs):
            return build_fixture_source_adapter(
                "coingecko",
                fixture_payload={
                    "captured_at": clock.now().isoformat(),
                    "assets": {
                        "bitcoin": {"price_usd": 65000, "change_24h": 2.5},
                        "ethereum": {"price_usd": 3500, "change_24h": 1.5},
                        "solana": {
                            "price_usd": 150,
                            "change_24h": 4.0,
                            "volume_24h": 2_000_000_000,
                        },
                    },
                },
            )

        def safety(**kwargs):
            return build_fixture_source_adapter(
                "goplus",
                fixture_payload={
                    "token_mint": kwargs.get("token_mint"),
                    "mint_authority": None,
                    "freeze_authority": None,
                    "metadata_mutable": False,
                    "total_supply": "1000000000",
                    "top_10_holders": [{"percent": "3"} for _ in range(10)],
                    "lp_info": [{"locked": True}],
                    "risk_flags": [],
                },
            )

        def quote(**kwargs):
            return build_fixture_source_adapter(
                "jupiter_quote",
                fixture_payload={
                    "route_available": True,
                    "route_plan_present": True,
                    "slippage_bps": 50,
                    "price_impact_bps": 5,
                    "freshness_label": "QUOTE_FRESH",
                    "target_status": "TARGET_MATCH",
                    "paper_only_context": True,
                    "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
                    "input_mint": kwargs["input_mint"],
                    "output_mint": kwargs["output_mint"],
                },
            )

        return {"coingecko": market, "goplus": safety, "jupiter_quote": quote}

    def test_focused_public_chain_two_window_lifecycle_entry(self) -> None:
        """#3–#14 Public chain + remapped entry completes two WINDOW_15M closes."""
        provenance = e8._provenance()
        preflight = {
            "database_sha256": _sha256(self.db),
            "git_provenance": provenance,
        }

        probe_transport, _probe_mints = e11._two_create_transport()
        acquisition = LivePumpOriginAdapter(probe_transport).acquire(
            source_governor=GOV,
            central_scheduler=SCH,
        )
        pools = {
            proof.mint: proof.bonding_curve for proof in acquisition.origin_proofs
        }
        graduation_proofs = {
            mint: FixturePumpSwapProof(mint=mint, pool_address=pool)
            for mint, pool in pools.items()
        }
        pump_transport, runtime_mints = e11._two_create_transport()
        self.assertEqual(set(runtime_mints), set(pools))
        secondary_transport = e11._FakeSecondaryTransport(
            e11._lawful_secondary_bodies(pools)
        )

        clock = e9._Clock()
        e9._ClockDateTime.clock = clock
        snapshot_calls: list[str] = []
        stage_records: list[dict] = []
        validations: list = []
        original_validation = CampaignActionLocalLedger.observe_local_validation
        entry_capture = _LifecycleEntryCapture()
        owner_run_calls: list[str] = []
        real_owner_run = AuthoritativeLiveOperationalCampaignOwner.run_operational

        def capture_owner_run(self_owner, **kwargs):
            owner_run_calls.append("run_operational")
            # Public coordinator always supplies fifteen_minute_only=True.
            self.assertTrue(kwargs.get("fifteen_minute_only"))
            return real_owner_run(self_owner, **kwargs)

        def capture_validation(ledger, identity):
            validations.append(identity)
            return original_validation(ledger, identity)

        owner = _ExactPublicCompositionOwner(
            graduation_proofs=graduation_proofs,
            snapshot_adapter_factory=self._snapshot_factory(pools, snapshot_calls),
            context_adapter_factories=self._context_factories(clock),
            clock=clock,
            stage_records=stage_records,
            lifecycle_runner=entry_capture,
        )
        # #4 Owner is the real authoritative subclass, not a bypass stub.
        self.assertIsInstance(owner, AuthoritativeLiveOperationalCampaignOwner)
        self.assertIsInstance(owner._driver, OriginToLifecycleCampaignDriver)

        canonical = Path(CANONICAL_PERSISTENT_DB).resolve()
        opened_paths: list[Path] = []
        real_connect = sqlite3.connect

        def tracking_connect(database, *args, **kwargs):
            try:
                resolved = Path(database).resolve()
            except (TypeError, ValueError):
                resolved = Path(str(database))
            opened_paths.append(resolved)
            return real_connect(database, *args, **kwargs)

        with (
            patch.object(
                public_command,
                "_iso",
                side_effect=lambda: clock.now().isoformat(),
            ),
            patch.object(public_command, "AUTHORITATIVE_DB", self.db.resolve()),
            patch.object(public_command, "ARTIFACT_ROOT", self.artifact_root),
            patch.object(
                public_command,
                "build_activation_preflight",
                return_value=preflight,
            ),
            patch.object(public_command, "_CampaignHeartbeat", _NoopHeartbeat),
            patch.object(
                public_command,
                "resolve_solana_rpc_configuration",
                return_value=type("R", (), {"url": "https://unused.invalid"})(),
            ),
            patch.object(
                CampaignActionLocalLedger,
                "observe_local_validation",
                new=capture_validation,
            ),
            patch.object(
                AuthoritativeLiveOperationalCampaignOwner,
                "run_operational",
                capture_owner_run,
            ),
            patch("printer_v1.operator_cli.one_command_15m_factory._now", clock.now),
            patch("printer_v1.sources.contracts.datetime", e9._ClockDateTime),
            patch("sqlite3.connect", side_effect=tracking_connect),
            patch("urllib.request.urlopen") as network_open,
        ):
            # #4 Public coordinator is the entry point.
            terminal = public_command._run_operational_campaign(
                policy=public_command._NORMAL_CAMPAIGN_POLICY,
                operator_approved=True,
                owner=owner,
                pump_transport=pump_transport,
                secondary_transport=secondary_transport,
                migration_transport=object(),
                git_provenance_authorization=validated_window_15m_authorization(),
            )

        # #11 Zero network.
        network_open.assert_not_called()
        self.assertEqual(0, network_open.call_count)

        # #12 No authoritative DB open/mutate.
        for path in opened_paths:
            self.assertNotEqual(canonical, path)

        # #4 Owner ran.
        self.assertEqual(["run_operational"], owner_run_calls)

        # #3 / #6 Owner still emits public 15m operational flags; remapper
        # converts them to lawful disposable proof-mode entry.
        self.assertEqual(1, len(entry_capture.calls))
        entry = entry_capture.calls[0]
        self.assertEqual(self.db.resolve(), entry["db_path"])
        self.assertNotEqual(canonical, entry["db_path"])
        inbound = entry["inbound"]
        self.assertFalse(inbound["proof_mode"])
        self.assertTrue(inbound["operational_persistent_mode"])
        self.assertTrue(inbound.get("operational_natural_disposition", False))
        self.assertFalse(inbound["continuous_first_hour"])
        self.assertFalse(inbound["continuous_four_hour"])
        self.assertFalse(inbound["four_hour_proof_mode"])
        effective = entry["effective"]
        self.assertTrue(effective["proof_mode"])
        self.assertFalse(effective["operational_persistent_mode"])
        self.assertFalse(effective["operational_natural_disposition"])
        self.assertFalse(effective["continuous_first_hour"])
        self.assertFalse(effective["continuous_four_hour"])
        self.assertFalse(effective["four_hour_proof_mode"])

        self.assertEqual("OPERATIONAL_CAMPAIGN_TERMINAL", terminal["status"])
        self.assertEqual("COMPLETED", terminal["run_status"])
        # #10 Campaign acceptance can evaluate completed proof.
        self.assertTrue(terminal["campaign_pass"])

        # #5 Origin driver / discovery selection produced two activated slots.
        discovery_records = [
            record
            for record in stage_records
            if record.get("boundary") == "DISCOVERY_SELECTION_TERMINAL"
        ]
        self.assertEqual(1, len(discovery_records))
        callback_slots = discovery_records[0]["slots"]
        callback_ids = [str(slot["token_slot_id"]) for slot in callback_slots]
        self.assertEqual(2, len(callback_ids))
        self.assertEqual(2, len(set(callback_ids)))

        handoff_validations = [
            identity
            for identity in validations
            if identity.validation_kind == "SELECTION_HANDOFF_VALIDATED"
        ]
        validation_ids = [identity.subject_identity for identity in handoff_validations]
        self.assertEqual(callback_ids, validation_ids)

        connection = real_connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            durable_ids = [
                str(row[0])
                for row in connection.execute(
                    """SELECT token_slot_id
                       FROM printer_memory_factory_campaign_token_slots
                       ORDER BY slot_ordinal"""
                ).fetchall()
            ]
            closes = int(
                connection.execute(
                    """SELECT COUNT(*)
                       FROM printer_memory_factory_run_steps
                       WHERE step_kind='WINDOW_CLOSE' AND step_status='SUCCEEDED'"""
                ).fetchone()[0]
            )
            factory_rows = connection.execute(
                """SELECT run_id, db_mode FROM printer_memory_factory_runs
                   ORDER BY created_at DESC, run_id DESC"""
            ).fetchall()
            continuation_closes = int(
                connection.execute(
                    """SELECT COUNT(*)
                       FROM printer_memory_factory_run_steps
                       WHERE step_kind IN (
                           'CONTINUATION_CLOSE', 'LONG_CONTINUATION_CLOSE'
                       )"""
                ).fetchone()[0]
            )
            scheduler = {
                "total": int(
                    connection.execute(
                        "SELECT COUNT(*) FROM printer_scheduler_jobs"
                    ).fetchone()[0]
                ),
                "active": int(
                    connection.execute(
                        """SELECT COUNT(*) FROM printer_scheduler_jobs
                           WHERE status IN ('PENDING','RUNNING')"""
                    ).fetchone()[0]
                ),
                "locked": int(
                    connection.execute(
                        """SELECT COUNT(*) FROM printer_scheduler_jobs
                           WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL"""
                    ).fetchone()[0]
                ),
                "succeeded": int(
                    connection.execute(
                        """SELECT COUNT(*) FROM printer_scheduler_jobs
                           WHERE status='SUCCEEDED'"""
                    ).fetchone()[0]
                ),
            }
            active_residue = public_command._active_counts(connection)
            protected_counts = {
                table: int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
                for table in public_command.LOCKED_CAPABILITY_TABLES
            }
            window_kinds = [
                str(row[0])
                for row in connection.execute(
                    "SELECT DISTINCT window_kind FROM printer_memory_windows "
                    "ORDER BY window_kind"
                ).fetchall()
            ]
        finally:
            connection.close()

        # #5 / #7 Two slots and two WINDOW_15M closes; no 1h/4h.
        self.assertEqual(durable_ids, callback_ids)
        self.assertEqual(2, closes)
        self.assertEqual(0, continuation_closes)
        self.assertEqual(1, len(factory_rows))
        self.assertEqual("PROOF_ONLY", str(factory_rows[0]["db_mode"]))

        # #8 Real Scheduler transitions; zero active residue.
        self.assertGreaterEqual(scheduler["total"], 1)
        self.assertGreaterEqual(scheduler["succeeded"], 1)
        self.assertEqual(0, scheduler["active"])
        self.assertEqual(0, scheduler["locked"])
        self.assertTrue(all(value == 0 for value in active_residue.values()))

        # #9 Strict accounting: handoff validations matched slots (above);
        # no financial/retrieval unlock.
        self.assertFalse(set(window_kinds) & set(public_command.LOCKED_WINDOWS))

        # #13 No retry/restart/resume/successor surfaces on the public command.
        self.assertEqual(0, public_command.AUTOMATIC_RETRIES)
        self.assertFalse(terminal.get("restart_created"))
        self.assertFalse(terminal.get("successor_created"))

        # #14 Retrieval and financial surfaces remain zero.
        self.assertTrue(all(value == 0 for value in protected_counts.values()))

        # #12 Canonical path never equaled the disposable DB used by the factory.
        self.assertNotEqual(canonical, self.db.resolve())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
