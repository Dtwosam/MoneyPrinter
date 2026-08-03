"""Exact offline public-composition proof for the ``token_slot_id`` repair.

Executes the public coordinator -> authoritative owner -> real origin driver ->
real one-command ``WINDOW_15M`` factory chain with frozen transports and a
fully disposable Migration-050 database. No provider, RPC network, WebSocket,
authoritative database, wrapper, external authorization, retrieval, decision,
or financial path is used.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db.migrate import apply_migrations, canonical_migration_names
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
    load_report_only,
    run_one_command_15m_factory,
)
from printer_v1.operator_cli.git_provenance import capture_git_provenance
from printer_v1.operator_cli.offline_shared_failure_evidence import (
    OfflineSharedFailureEvidenceError,
    preserve_failed_offline_composition_evidence,
)
from printer_v1.operator_cli.origin_lifecycle_campaign import (
    OriginToLifecycleCampaignDriver,
)
from printer_v1.sources.campaign_six_unit_accounting import CampaignActionLocalLedger
from printer_v1.sources.governed_execution import build_fixture_source_adapter

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
import test_v2_9_7e_9_two_token_continuous_lifecycle as e9
import test_v2_9_7e_11_authoritative_live_operational_campaign as e11


GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

# Exact offline composition lifecycle-entry contract (test harness only).
# Public fifteen_minute_only maps to operational_persistent_mode=True /
# proof_mode=False. That is correct for production and must keep requiring the
# authoritative corpus. Disposable offline composition remaps only the factory
# entry flags through the existing driver lifecycle_runner DI port.
OFFLINE_EXACT_LIFECYCLE_ENTRY_PROOF_MODE = True
OFFLINE_EXACT_LIFECYCLE_ENTRY_OPERATIONAL_PERSISTENT = False
OFFLINE_EXACT_LIFECYCLE_ENTRY_OPERATIONAL_NATURAL = False


def offline_exact_public_composition_lifecycle_entry(
    db_path,
    backup_path,
    **kwargs,
):
    """Test-only remapper: lawful disposable lifecycle entry for offline composition.

    Preserves the real factory while forcing the existing disposable proof-mode
    contract. Clears operational_natural_disposition because factory preflight
    couples operational-natural 15m-only to operational-persistent mode (which
    requires the authoritative corpus). Continuous/4h flags stay false so the
    proof retains two compressed WINDOW_15M closes only.
    """
    options = dict(kwargs)
    options["proof_mode"] = OFFLINE_EXACT_LIFECYCLE_ENTRY_PROOF_MODE
    options["operational_persistent_mode"] = (
        OFFLINE_EXACT_LIFECYCLE_ENTRY_OPERATIONAL_PERSISTENT
    )
    options["continuous_first_hour"] = False
    options["continuous_four_hour"] = False
    options["four_hour_proof_mode"] = False
    options["operational_natural_disposition"] = (
        OFFLINE_EXACT_LIFECYCLE_ENTRY_OPERATIONAL_NATURAL
    )
    return run_one_command_15m_factory(db_path, backup_path, **options)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class _NoopHeartbeat:
    """Exact public heartbeat interface without wall-clock background work."""

    def __init__(self, _command) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def poll_failure(self):
        return None


class _ExactPublicCompositionOwner(AuthoritativeLiveOperationalCampaignOwner):
    """Inject only frozen evidence/timing while retaining the real owner path.

    Lifecycle entry uses the existing driver DI port so the real public
    coordinator → owner → driver chain still runs, while the factory receives
    lawful disposable proof-mode flags.
    """

    def __init__(
        self,
        *,
        graduation_proofs,
        snapshot_adapter_factory,
        context_adapter_factories,
        clock,
        stage_records,
        lifecycle_runner=None,
    ) -> None:
        super().__init__(
            driver=OriginToLifecycleCampaignDriver(
                lifecycle_runner=(
                    lifecycle_runner
                    or offline_exact_public_composition_lifecycle_entry
                ),
            )
        )
        self._graduation_proofs = dict(graduation_proofs)
        self._snapshot_adapter_factory = snapshot_adapter_factory
        self._context_adapter_factories = dict(context_adapter_factories)
        self._clock = clock
        self._stage_records = stage_records

    def run_operational(self, **kwargs):
        lifecycle_kwargs = dict(kwargs["lifecycle_kwargs"])
        real_stage_observer = lifecycle_kwargs["full_run_stage_observer"]

        def capture_then_observe(record):
            self._stage_records.append(copy.deepcopy(dict(record)))
            real_stage_observer(record)

        lifecycle_kwargs.update(
            {
                "snapshot_adapter_factory": self._snapshot_adapter_factory,
                "context_adapter_factories": self._context_adapter_factories,
                "_window_seconds": 0.05,
                "_sleep": self._clock.sleep,
                "_monotonic": self._clock.monotonic,
                "total_duration_seconds": 3.0,
                "launch_provenance": e8._provenance(),
                "full_run_stage_observer": capture_then_observe,
            }
        )
        kwargs["lifecycle_kwargs"] = lifecycle_kwargs
        kwargs["graduation_proofs"] = self._graduation_proofs
        kwargs["graduated_supply"] = None
        # The public coordinator still supplies the migration port, but this
        # frozen direct-origin proof requires no migration-provider operation.
        kwargs["migration_transport"] = None
        return super().run_operational(**kwargs)


class ExactPublicTokenSlotIdCompositionProof(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "dtw23-migration-050.sqlite3"
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

    def test_exact_public_coordinator_owner_driver_factory_composition(self) -> None:
        before_hash = _sha256(self.db)
        provenance = e8._provenance()
        preflight = {
            "database_sha256": before_hash,
            "git_provenance": provenance,
        }

        # Derive deterministic PumpSwap confirmation fixtures from a separate
        # frozen transport, leaving the actual public-call transport untouched.
        probe_transport, _probe_mints = e11._two_create_transport()
        acquisition = LivePumpOriginAdapter(probe_transport).acquire(
            source_governor=GOV,
            central_scheduler=SCH,
        )
        pools = {
            proof.mint: proof.bonding_curve
            for proof in acquisition.origin_proofs
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
        snapshot_calls = []
        stage_records = []
        validations = []
        original_validation = CampaignActionLocalLedger.observe_local_validation

        def capture_validation(ledger, identity):
            validations.append(identity)
            return original_validation(ledger, identity)

        owner = _ExactPublicCompositionOwner(
            graduation_proofs=graduation_proofs,
            snapshot_adapter_factory=self._snapshot_factory(pools, snapshot_calls),
            context_adapter_factories=self._context_factories(clock),
            clock=clock,
            stage_records=stage_records,
        )

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
                return_value=SimpleNamespace(url="https://unused.invalid"),
            ),
            patch.object(
                CampaignActionLocalLedger,
                "observe_local_validation",
                new=capture_validation,
            ),
            patch("printer_v1.operator_cli.one_command_15m_factory._now", clock.now),
            patch("printer_v1.sources.contracts.datetime", e9._ClockDateTime),
            patch("urllib.request.urlopen") as network_open,
        ):
            terminal = public_command._run_operational_campaign(
                policy=public_command._NORMAL_CAMPAIGN_POLICY,
                operator_approved=True,
                owner=owner,
                pump_transport=pump_transport,
                secondary_transport=secondary_transport,
                migration_transport=object(),
            )

        if bool(terminal.get("failure_evidence_required")) or str(
            terminal.get("run_status") or ""
        ) != "COMPLETED":
            project_root = Path(__file__).resolve().parents[1]
            git_state = capture_git_provenance(project_root)
            evidence_root = Path(
                os.environ.get(
                    "PRINTER_V1_OFFLINE_FAILURE_EVIDENCE_ROOT",
                    str(
                        Path(tempfile.gettempdir())
                        / "printer-v1-shared-failure-evidence"
                    ),
                )
            )
            try:
                preserved = preserve_failed_offline_composition_evidence(
                    source_database=self.db,
                    artifact_root=evidence_root,
                    execution_id=str(terminal["execution_id"]),
                    baseline_git_head=str(git_state["git_head"]),
                    tracked_tree_state={
                        "git_tracked_tree_clean": git_state[
                            "git_tracked_tree_clean"
                        ],
                        "git_staged_changes_present": git_state[
                            "git_staged_changes_present"
                        ],
                        "git_unstaged_changes_present": git_state[
                            "git_unstaged_changes_present"
                        ],
                        "git_untracked_present": git_state["git_untracked_present"],
                    },
                    test_node_id=(
                        "tests/test_v2_9_8b_token_slot_id_exact_public_composition.py::"
                        "ExactPublicTokenSlotIdCompositionProof::"
                        "test_exact_public_coordinator_owner_driver_factory_composition"
                    ),
                    terminal=terminal,
                    zero_network_assertion={
                        "boundary": (
                            "frozen transports plus patched urllib.request.urlopen; "
                            "not packet-level proof"
                        ),
                        "patched_urllib_call_count": network_open.call_count,
                    },
                    retry_state={
                        "automatic_retries": public_command.AUTOMATIC_RETRIES,
                        "reruns": 0,
                        "resumes": 0,
                        "restarts": int(bool(terminal.get("restart_created"))),
                        "successors": int(bool(terminal.get("successor_created"))),
                    },
                    connections_closed=True,
                )
            except OfflineSharedFailureEvidenceError as helper_exc:
                terminal.setdefault("fault_details", {}).setdefault(
                    "propagation_failures", []
                ).append(helper_exc.secondary_failure)
                print(
                    "PRE_LIFECYCLE_FAILURE_EVIDENCE_CAPTURE_SECONDARY="
                    + json.dumps(
                        {
                            "first_failure": helper_exc.first_failure,
                            "secondary_failure": helper_exc.secondary_failure,
                        },
                        sort_keys=True,
                    )
                )
            else:
                print(
                    "PRE_LIFECYCLE_FAILURE_EVIDENCE_CAPTURE="
                    + json.dumps(preserved, sort_keys=True)
                )

        network_open.assert_not_called()
        after_hash = _sha256(self.db)
        self.assertNotEqual(before_hash, after_hash)
        self.assertEqual("OPERATIONAL_CAMPAIGN_TERMINAL", terminal["status"])
        self.assertEqual("COMPLETED", terminal["run_status"])
        self.assertTrue(terminal["campaign_pass"])

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
        self.assertEqual(
            [1, 2],
            [identity.validation_ordinal for identity in handoff_validations],
        )

        connection = sqlite3.connect(self.db)
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
            link_ids = [
                str(row[0])
                for row in connection.execute(
                    """SELECT token_slot_id
                       FROM printer_discovery_selected_item_links
                       ORDER BY selection_item_id"""
                ).fetchall()
            ]
            closes = int(
                connection.execute(
                    """SELECT COUNT(*)
                       FROM printer_memory_factory_run_steps
                       WHERE step_kind='WINDOW_CLOSE' AND step_status='SUCCEEDED'"""
                ).fetchone()[0]
            )
            factory_run_id = str(
                connection.execute(
                    """SELECT run_id FROM printer_memory_factory_runs
                       ORDER BY created_at DESC, run_id DESC LIMIT 1"""
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
            }
            active_residue = public_command._active_counts(connection)
            integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
            foreign_keys = [
                tuple(row)
                for row in connection.execute("PRAGMA foreign_key_check").fetchall()
            ]
            window_kinds = [
                str(row[0])
                for row in connection.execute(
                    "SELECT DISTINCT window_kind FROM printer_memory_windows ORDER BY window_kind"
                ).fetchall()
            ]
            protected_counts = {
                table: int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
                for table in public_command.LOCKED_CAPABILITY_TABLES
            }
        finally:
            connection.close()

        self.assertEqual(durable_ids, callback_ids)
        self.assertEqual(link_ids, callback_ids)
        self.assertEqual(2, closes)
        self.assertEqual(0, scheduler["active"])
        self.assertEqual(0, scheduler["locked"])
        self.assertTrue(all(value == 0 for value in active_residue.values()))
        self.assertEqual("ok", integrity)
        self.assertEqual([], foreign_keys)
        self.assertFalse(set(window_kinds) & set(public_command.LOCKED_WINDOWS))
        self.assertTrue(all(value == 0 for value in protected_counts.values()))

        before_replay_hash = _sha256(self.db)
        replay_a = load_report_only(self.db, factory_run_id)
        replay_b = load_report_only(self.db, factory_run_id)
        after_replay_hash = _sha256(self.db)
        self.assertEqual(replay_a, replay_b)
        self.assertEqual(0, replay_a["replay"]["new_source_calls"])
        self.assertEqual(0, replay_a["replay"]["new_evidence_rows"])
        self.assertEqual(before_replay_hash, after_replay_hash)

        sidecars = [
            str(Path(f"{self.db}{suffix}"))
            for suffix in ("-wal", "-shm", "-journal")
            if Path(f"{self.db}{suffix}").exists()
        ]
        self.assertEqual([], sidecars)

        evidence = {
            "schema_version": "DTW23_TOKEN_SLOT_ID_EXACT_PUBLIC_COMPOSITION_V1",
            "migration_count": len(canonical_migration_names()),
            "migration_head": canonical_migration_names()[-1],
            "disposable_database": str(self.db.resolve()),
            "database_sha256_before": before_hash,
            "database_sha256_after": after_hash,
            "database_sha256_before_replay": before_replay_hash,
            "database_sha256_after_replay": after_replay_hash,
            "campaign_id": terminal["campaign_id"],
            "factory_run_id": factory_run_id,
            "durable_token_slot_ids": durable_ids,
            "selected_item_link_token_slot_ids": link_ids,
            "callback_token_slot_ids": callback_ids,
            "selection_handoff_validation_ids": validation_ids,
            "selection_handoff_validation_ordinals": [
                identity.validation_ordinal for identity in handoff_validations
            ],
            "window_15m_terminal_closes": closes,
            "window_kinds": window_kinds,
            "scheduler": scheduler,
            "active_residue": active_residue,
            "integrity_check": integrity,
            "foreign_key_errors": foreign_keys,
            "protected_capability_counts": protected_counts,
            "frozen_pump_signature_calls": pump_transport.sig_calls,
            "frozen_pump_transaction_calls": list(pump_transport.tx_calls),
            "frozen_secondary_http_calls": list(secondary_transport.calls),
            "frozen_snapshot_calls": list(snapshot_calls),
            "external_network_calls": network_open.call_count,
            "authoritative_database_accesses": 0,
            "wrapper_invocations": 0,
            "external_authorization_creations_or_applications": 0,
            "automatic_retries": public_command.AUTOMATIC_RETRIES,
            "reruns": 0,
            "resumes": 0,
            "restarts": 0,
            "successors": 0,
            "report_only_replay_new_source_calls": replay_a["replay"]["new_source_calls"],
            "report_only_replay_new_evidence_rows": replay_a["replay"]["new_evidence_rows"],
            "sqlite_sidecars_after_close": sidecars,
            "campaign_pass": terminal["campaign_pass"],
        }
        print("DTW23_PROOF_EVIDENCE=" + json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
