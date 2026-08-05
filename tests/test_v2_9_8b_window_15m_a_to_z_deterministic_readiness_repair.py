"""Focused proofs for WINDOW_15M A-to-Z deterministic readiness repair (R1–R5)."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from printer_v1.db.migrate import apply_migrations
from printer_v1.memory.contracts import MemoryQualityLabel
from printer_v1.memory.fingerprints import (
    build_memory_fingerprint_payload,
    fingerprint_can_be_indexed_later,
    record_memory_fingerprint,
)
from printer_v1.memory.windowing import close_memory_window, open_memory_window
from printer_v1.memory.recorder import build_and_record_episode
from printer_v1.operator_cli.action_local_terminal_truth import (
    build_action_local_terminal_truth,
    capture_action_local_baseline,
)
from printer_v1.operator_cli.authorization_temporal_validity import (
    AUTHORIZATION_MAX_VALIDITY_SECONDS,
    AuthorizationTemporalError,
    validate_authorization_temporal_validity,
)
from printer_v1.operator_cli.window_15m_concrete_composition import (
    COMPOSITION_MATRIX,
    ConcreteCompositionError,
    ordinary_window_15m_builder_identities,
    require_concrete_adapter,
    run_window_15m_concrete_composition_preflight,
    window_15m_preflight_builders,
)
from printer_v1.operator_cli.window_15m_one_shot_wrapper import (
    OneShotWrapperError,
    apply_authorization_once,
)
from printer_v1.sources.operational_source_contracts import (
    OFFICIAL_SOLANA_PUBLIC_RPC_URL,
    SOLANA_RPC_ENVIRONMENT_NAME,
    SolanaRpcConfigurationError,
    validate_window_15m_source_configuration,
)


class AuthorizationTemporalTests(unittest.TestCase):
    def _doc(self, **overrides):
        issued = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)
        base = {
            "authorized_at": issued.isoformat(),
            "expires_at": (issued + timedelta(hours=12)).isoformat(),
            "validity_seconds": 43200,
        }
        base.update(overrides)
        return base

    def test_valid_authorization_passes(self):
        issued = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)
        now = issued + timedelta(hours=1)
        result = validate_authorization_temporal_validity(
            self._doc(), now=now
        )
        self.assertEqual("TEMPORALLY_VALID", result["status"])
        self.assertEqual(AUTHORIZATION_MAX_VALIDITY_SECONDS, result["max_validity_seconds"])

    def test_missing_issue_fails(self):
        with self.assertRaises(AuthorizationTemporalError) as ctx:
            validate_authorization_temporal_validity(
                {"expires_at": "2026-08-06T12:00:00+00:00"},
                now=datetime(2026, 8, 5, 13, tzinfo=timezone.utc),
            )
        self.assertIn("ISSUE_TIME_MISSING", str(ctx.exception))

    def test_missing_expiry_fails(self):
        with self.assertRaises(AuthorizationTemporalError) as ctx:
            validate_authorization_temporal_validity(
                {"authorized_at": "2026-08-05T12:00:00+00:00"},
                now=datetime(2026, 8, 5, 13, tzinfo=timezone.utc),
            )
        self.assertIn("EXPIRY_TIME_MISSING", str(ctx.exception))

    def test_naive_timezone_fails(self):
        with self.assertRaises(AuthorizationTemporalError) as ctx:
            validate_authorization_temporal_validity(
                {
                    "authorized_at": "2026-08-05T12:00:00",
                    "expires_at": "2026-08-06T12:00:00+00:00",
                },
                now=datetime(2026, 8, 5, 13, tzinfo=timezone.utc),
            )
        self.assertIn("NAIVE", str(ctx.exception))

    def test_future_issued_fails(self):
        issued = datetime(2026, 8, 5, 15, 0, 0, tzinfo=timezone.utc)
        now = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)
        with self.assertRaises(AuthorizationTemporalError) as ctx:
            validate_authorization_temporal_validity(
                {
                    "authorized_at": issued.isoformat(),
                    "expires_at": (issued + timedelta(hours=1)).isoformat(),
                },
                now=now,
            )
        self.assertIn("FUTURE_ISSUED", str(ctx.exception))

    def test_expired_fails(self):
        issued = datetime(2026, 8, 5, 10, 0, 0, tzinfo=timezone.utc)
        with self.assertRaises(AuthorizationTemporalError) as ctx:
            validate_authorization_temporal_validity(
                {
                    "authorized_at": issued.isoformat(),
                    "expires_at": (issued + timedelta(hours=1)).isoformat(),
                },
                now=issued + timedelta(hours=2),
            )
        self.assertIn("EXPIRED", str(ctx.exception))

    def test_over_age_policy_fails(self):
        issued = datetime(2026, 8, 5, 10, 0, 0, tzinfo=timezone.utc)
        with self.assertRaises(AuthorizationTemporalError) as ctx:
            validate_authorization_temporal_validity(
                {
                    "authorized_at": issued.isoformat(),
                    "expires_at": (issued + timedelta(hours=48)).isoformat(),
                    "validity_seconds": 172800,
                },
                now=issued + timedelta(hours=1),
            )
        self.assertIn("OVER_MAX_AGE_POLICY", str(ctx.exception))

    def test_expiry_not_after_issue_fails(self):
        issued = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)
        with self.assertRaises(AuthorizationTemporalError) as ctx:
            validate_authorization_temporal_validity(
                {
                    "authorized_at": issued.isoformat(),
                    "expires_at": issued.isoformat(),
                },
                now=issued + timedelta(minutes=1),
            )
        self.assertIn("EXPIRY_NOT_AFTER_ISSUE", str(ctx.exception))

    def test_wrapper_temporal_failure_no_marker_no_child(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            app_root = Path(tmp) / "app"
            app_root.mkdir()
            auth_path = Path(tmp) / "auth.json"
            issued = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
            doc = {
                "authorization_id": "TEST_AUTH_TEMPORAL_BLOCK",
                "authorized_at": issued.isoformat(),
                "expires_at": (issued + timedelta(hours=1)).isoformat(),
                "validity_seconds": 3600,
            }
            with (
                patch(
                    "printer_v1.operator_cli.window_15m_one_shot_wrapper._resolve_authorization",
                    return_value=(auth_path, doc, "TEST_AUTH_TEMPORAL_BLOCK", "deadbeef"),
                ),
                patch(
                    "printer_v1.operator_cli.window_15m_one_shot_wrapper._select_child_python",
                ) as select_child,
            ):
                with self.assertRaises(OneShotWrapperError) as ctx:
                    apply_authorization_once(
                        authorization_file=auth_path,
                        authorization_sha256="0" * 64,
                        operator_approved=True,
                        repository_root=root,
                        application_root=app_root,
                        migration_ledger_guard=lambda **_k: object(),
                    )
            self.assertIn("temporal", str(ctx.exception).lower())
            self.assertFalse((app_root / "TEST_AUTH_TEMPORAL_BLOCK").exists())
            select_child.assert_not_called()


class WrapperChildSourceParityTests(unittest.TestCase):
    def test_missing_rpc_uses_official_fallback(self):
        cfg = validate_window_15m_source_configuration({})
        self.assertEqual(OFFICIAL_SOLANA_PUBLIC_RPC_URL, cfg.url)
        self.assertEqual("BOUNDED_OFFICIAL_PUBLIC_FALLBACK", cfg.origin)

    def test_invalid_explicit_rpc_fails(self):
        for value in (
            "http://api.mainnet.solana.com",
            "not-a-url",
            "https://example.com/placeholder",
            "https://your_rpc_here.example",
        ):
            with self.assertRaises(SolanaRpcConfigurationError):
                validate_window_15m_source_configuration(
                    {SOLANA_RPC_ENVIRONMENT_NAME: value}
                )

    def test_wrapper_and_child_same_verdict(self):
        env = {SOLANA_RPC_ENVIRONMENT_NAME: "https://api.mainnet.solana.com"}
        wrapper_cfg = validate_window_15m_source_configuration(env)
        child_cfg = validate_window_15m_source_configuration(env)
        self.assertEqual(wrapper_cfg, child_cfg)

        bad = {SOLANA_RPC_ENVIRONMENT_NAME: "http://bad.example"}
        with self.assertRaises(SolanaRpcConfigurationError) as w:
            validate_window_15m_source_configuration(bad)
        with self.assertRaises(SolanaRpcConfigurationError) as c:
            validate_window_15m_source_configuration(bad)
        self.assertEqual(str(w.exception), str(c.exception))

    def test_invalid_rpc_blocks_wrapper_before_consumption(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            app_root = Path(tmp) / "app"
            app_root.mkdir()
            auth_path = Path(tmp) / "auth.json"
            issued = datetime.now(timezone.utc)
            doc = {
                "authorization_id": "TEST_AUTH_RPC_BLOCK",
                "authorized_at": issued.isoformat(),
                "expires_at": (issued + timedelta(hours=6)).isoformat(),
                "validity_seconds": 21600,
            }
            parent_before = dict(os.environ)
            bad_env = dict(os.environ)
            bad_env[SOLANA_RPC_ENVIRONMENT_NAME] = "http://insecure.example"
            with (
                patch(
                    "printer_v1.operator_cli.window_15m_one_shot_wrapper._resolve_authorization",
                    return_value=(auth_path, doc, "TEST_AUTH_RPC_BLOCK", "deadbeef"),
                ),
                patch(
                    "printer_v1.operator_cli.window_15m_one_shot_wrapper._select_child_python",
                    return_value=str(Path(root / ".venv" / "bin" / "python").resolve()),
                ),
                patch(
                    "printer_v1.operator_cli.window_15m_one_shot_wrapper.package_binding_from_document",
                    return_value={},
                ),
                patch(
                    "printer_v1.operator_cli.window_15m_one_shot_wrapper.sys.executable",
                    str(Path(root / ".venv" / "bin" / "python").resolve()),
                ),
            ):
                with self.assertRaises(OneShotWrapperError) as ctx:
                    apply_authorization_once(
                        authorization_file=auth_path,
                        authorization_sha256="0" * 64,
                        operator_approved=True,
                        repository_root=root,
                        application_root=app_root,
                        environ=bad_env,
                        migration_ledger_guard=lambda **_k: object(),
                    )
            self.assertIn("source configuration", str(ctx.exception).lower())
            self.assertFalse((app_root / "TEST_AUTH_RPC_BLOCK").exists())
            self.assertEqual(parent_before, dict(os.environ))


class CompositionRegistryTests(unittest.TestCase):
    def test_registry_equals_builder_identities(self):
        builders = window_15m_preflight_builders(timeout_seconds=1.0)
        builder_labels = tuple(label for label, _ in builders)
        self.assertEqual(ordinary_window_15m_builder_identities(), builder_labels)
        self.assertEqual(
            {spec.label for spec in COMPOSITION_MATRIX},
            set(builder_labels),
        )

    def test_direct_migration_and_graduation_included(self):
        labels = set(ordinary_window_15m_builder_identities())
        self.assertIn("direct_pump_finalized_migration_transport", labels)
        self.assertIn("exact_pump_pumpswap_graduation_verifier_transport", labels)

    def test_default_composition_zero_io(self):
        root = Path(__file__).resolve().parents[1]
        result = run_window_15m_concrete_composition_preflight(
            repository_root=str(root),
            timeout_seconds=1.0,
            environment={},
        )
        self.assertEqual("READY", result["status"])
        self.assertEqual(0, result["external_requests"])
        self.assertEqual(0, result["database_writes"])
        self.assertGreaterEqual(result["builder_count"], 20)

    def test_builder_none_and_raise_block(self):
        root = Path(__file__).resolve().parents[1]
        with self.assertRaises(ConcreteCompositionError):
            run_window_15m_concrete_composition_preflight(
                repository_root=str(root),
                adapter_builders=(("broken", lambda: None),),
            )

        def boom():
            raise RuntimeError("nope")

        with self.assertRaises(ConcreteCompositionError):
            run_window_15m_concrete_composition_preflight(
                repository_root=str(root),
                adapter_builders=(("broken", boom),),
            )

    def test_strict_adapter_rejects_arbitrary_object(self):
        with self.assertRaises(ConcreteCompositionError) as ctx:
            require_concrete_adapter("x", object())
        self.assertIn("EXECUTE_MISSING", str(ctx.exception))

    def test_strict_adapter_rejects_disabled_and_missing_transport(self):
        from printer_v1.sources.geckoterminal import build_geckoterminal_adapter

        disabled = build_geckoterminal_adapter(enabled=False, fixture_transport=lambda c: {})
        with self.assertRaises(ConcreteCompositionError) as ctx:
            require_concrete_adapter(
                "x", disabled, expected_source_name="geckoterminal"
            )
        self.assertIn("DISABLED", str(ctx.exception))

        transportless = build_geckoterminal_adapter(
            enabled=True, fixture_transport=None
        )
        with self.assertRaises(ConcreteCompositionError) as ctx:
            require_concrete_adapter(
                "x", transportless, expected_source_name="geckoterminal"
            )
        self.assertIn("TRANSPORT_MISSING", str(ctx.exception))

    def test_fixture_mode_requires_explicit_exemption(self):
        fixture = SimpleNamespace(source_name="geckoterminal")
        with self.assertRaises(ConcreteCompositionError):
            require_concrete_adapter("x", fixture, expected_source_name="geckoterminal")
        # Explicit fixture mode accepts non-production surface.
        require_concrete_adapter(
            "x",
            fixture,
            expected_source_name="geckoterminal",
            validation_mode="fixture",
        )

    def test_invalid_rpc_blocks_composition_preflight(self):
        root = Path(__file__).resolve().parents[1]
        with self.assertRaises((ConcreteCompositionError, SolanaRpcConfigurationError)):
            run_window_15m_concrete_composition_preflight(
                repository_root=str(root),
                timeout_seconds=1.0,
                environment={SOLANA_RPC_ENVIRONMENT_NAME: "http://bad"},
            )


class MutationTruthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "mutation.sqlite3"
        apply_migrations(self.db)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_insert_only_classification(self):
        baseline = capture_action_local_baseline(self.db)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                """INSERT INTO printer_tokens (token_mint, symbol, name, created_at)
                   VALUES ('MintInsert1', 'T', 'T', datetime('now'))"""
            )
            conn.commit()
        finally:
            conn.close()
        truth = build_action_local_terminal_truth(
            self.db,
            baseline=baseline,
            owner_emitted_inserted_row_ids={"printer_tokens": [1]},
        )
        self.assertEqual("INSERT_ONLY", truth["mutation_classifications"]["printer_tokens"])
        self.assertEqual(1, truth["database_writes"])
        self.assertEqual(
            "OWNER_EMITTED_ROW_IDENTITIES",
            truth["authoritative_write_count_status"],
        )

    def test_update_only_never_unchanged_or_zero_writes(self):
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                """INSERT INTO printer_tokens (token_mint, symbol, name, created_at)
                   VALUES ('MintUpdate1', 'T', 'T', datetime('now'))"""
            )
            conn.commit()
        finally:
            conn.close()
        baseline = capture_action_local_baseline(self.db)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "UPDATE printer_tokens SET symbol = 'U' WHERE token_mint = 'MintUpdate1'"
            )
            conn.commit()
        finally:
            conn.close()
        truth = build_action_local_terminal_truth(
            self.db,
            baseline=baseline,
            owner_emitted_updated_row_ids={"printer_tokens": [1]},
        )
        classification = truth["mutation_classifications"]["printer_tokens"]
        self.assertNotEqual("UNCHANGED", classification)
        self.assertIn("UPDATE", classification)
        self.assertNotEqual(0, truth["database_writes"])
        self.assertEqual(
            "PROVEN_UPDATE_WITHOUT_NET_GROWTH",
            truth["database_mutation_status"],
        )

    def test_no_false_numeric_write_count_without_authority(self):
        baseline = capture_action_local_baseline(self.db)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                """INSERT INTO printer_tokens (token_mint, symbol, name, created_at)
                   VALUES ('MintNet1', 'T', 'T', datetime('now'))"""
            )
            conn.commit()
        finally:
            conn.close()
        truth = build_action_local_terminal_truth(self.db, baseline=baseline)
        # Net growth is visible but not claimed as authoritative database_writes.
        self.assertIsNone(truth["database_writes"])
        self.assertEqual(
            "UNKNOWN_NOT_ATTRIBUTABLE",
            truth["authoritative_write_count_status"],
        )
        self.assertEqual(
            "INSERT_NET_POSITIVE",
            truth["mutation_classifications"]["printer_tokens"],
        )

    def test_first_terminal_cause_preserved_on_accounting_fault(self):
        baseline = capture_action_local_baseline(self.db)
        truth = build_action_local_terminal_truth(
            self.db,
            baseline=baseline,
            first_terminal_cause="OPERATIONAL_CAMPAIGN_FAILED:PermissionError",
            campaign_id="missing-campaign",
            run_id="missing-run",
        )
        self.assertEqual(
            "OPERATIONAL_CAMPAIGN_FAILED:PermissionError",
            truth["first_terminal_cause"],
        )
        states = truth["campaign_run_cycle_states"]
        self.assertEqual(
            "OPERATIONAL_CAMPAIGN_FAILED:PermissionError",
            states["first_terminal_cause"],
        )

    def test_projection_only_and_unattributable(self):
        truth = build_action_local_terminal_truth(self.db, baseline=None)
        self.assertEqual("UNKNOWN_NOT_ATTRIBUTABLE", truth["database_mutation_status"])
        self.assertIsNone(truth["database_writes"])


class FingerprintPayloadTests(unittest.TestCase):
    def test_payload_tracking_lane_categorical_not_object(self):
        payload = {
            "episode_id": 7,
            "window": {
                "id": 3,
                "token_id": 11,
                "pair_id": 13,
                "window_kind": "WINDOW_15M",
                "supporting_context_json": json.dumps(
                    {"tracking_lane": "TRACK_FAST", "reason": "open"}
                ),
            },
            "outcome_label": "SUSTAINED_PUMP",
            "memory_quality_label": "CLEAN_MEMORY",
            "token_age_bucket": None,
            "pair_age_bucket": "PAIR_AGE_UNKNOWN",
            "discovery_label": None,
            "supporting_context": {
                "liquidity_exit": {
                    "liquidity_state_label": "LIQUIDITY_USABLE",
                    "exit_realism_label": "EXIT_REALISTIC",
                },
                "trading_flow": {"flow_direction_label": "FLOW_ACCUMULATION"},
                "chart_volatility": {
                    "trend_structure_label": "TREND_UP",
                    "volatility_label": "VOL_MODERATE",
                },
                "market": {"market_regime_label": "NEUTRAL"},
                "chain_heat": {"chain_heat_label": "HEAT_NORMAL"},
                "safety": {
                    "safety_status_label": "SAFETY_ACCEPTABLE",
                    "rug_risk_label": "RUG_RISK_LOW",
                },
                "micro_events": [{"micro_event_state_label": "TRADABLE_MICRO_PUMP"}],
            },
        }
        fp = build_memory_fingerprint_payload(payload, episode_id=7)
        self.assertEqual("TRACK_FAST", fp["tracking_lane"])
        self.assertNotIsInstance(fp["tracking_lane"], (dict, list))
        self.assertEqual(7, fp["episode_id"])
        self.assertEqual(3, fp["window_id"])
        self.assertEqual(11, fp["token_id"])
        self.assertEqual(13, fp["pair_id"])
        self.assertEqual("WINDOW_15M", fp["window_kind"])
        self.assertEqual("SUSTAINED_PUMP", fp["outcome_label"])
        self.assertEqual("UNKNOWN", fp["token_age_bucket"])
        self.assertEqual("UNKNOWN", fp["discovery_label"])
        self.assertEqual("PAIR_AGE_UNKNOWN", fp["pair_age_bucket"])
        encoded = json.dumps(fp)
        for fragment in ("score", "confidence", "rank", "embedding", "vector"):
            self.assertNotIn(fragment, encoded)

    def test_idempotent_fingerprint_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "fp.sqlite3"
            apply_migrations(db)
            conn = sqlite3.connect(db)
            try:
                conn.execute(
                    """INSERT INTO printer_tokens (token_mint, symbol, name, created_at)
                       VALUES ('MintFp1', 'F', 'F', datetime('now'))"""
                )
                conn.execute(
                    """INSERT INTO printer_pairs (token_id, pair_address, created_at)
                       VALUES (1, 'PairFp1', datetime('now'))"""
                )
                conn.commit()
            finally:
                conn.close()
            opened = datetime.now(timezone.utc) - timedelta(minutes=15)
            closed = datetime.now(timezone.utc)
            window_id = open_memory_window(
                db, 1, 1, "WINDOW_15M", opened, "TRACK_NORMAL"
            )
            close_memory_window(db, window_id, closed)
            # Minimal snapshots for episode assembly may still yield non-clean;
            # exercise fingerprint owner directly for idempotency.
            episode_payload = {
                "window": {
                    "id": window_id,
                    "token_id": 1,
                    "pair_id": 1,
                    "window_kind": "WINDOW_15M",
                    "supporting_context_json": '{"tracking_lane":"TRACK_NORMAL"}',
                },
                "outcome_label": "SUSTAINED_PUMP",
                "memory_quality_label": MemoryQualityLabel.CLEAN_MEMORY.value,
                "supporting_context": {},
            }
            first = record_memory_fingerprint(
                db, 9001, build_memory_fingerprint_payload(episode_payload, episode_id=9001),
                MemoryQualityLabel.CLEAN_MEMORY,
            )
            # Seed episode row so FK-less insert path works; schema may not FK.
            second = record_memory_fingerprint(
                db, 9001, build_memory_fingerprint_payload(episode_payload, episode_id=9001),
                MemoryQualityLabel.CLEAN_MEMORY,
            )
            self.assertEqual(first, second)
            conn = sqlite3.connect(db)
            try:
                count = conn.execute(
                    "SELECT COUNT(*) FROM printer_memory_fingerprints WHERE episode_id = 9001"
                ).fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(1, count)

    def test_dirty_not_indexable(self):
        self.assertFalse(
            fingerprint_can_be_indexed_later(MemoryQualityLabel.DIRTY_MEMORY)
        )
        self.assertFalse(
            fingerprint_can_be_indexed_later(MemoryQualityLabel.AUDIT_ONLY_MEMORY)
        )
        self.assertTrue(
            fingerprint_can_be_indexed_later(MemoryQualityLabel.CLEAN_MEMORY)
        )


if __name__ == "__main__":
    unittest.main()
