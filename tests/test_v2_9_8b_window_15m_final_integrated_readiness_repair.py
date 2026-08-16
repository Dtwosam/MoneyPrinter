"""Focused tests for WINDOW_15M final integrated readiness repair."""

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
from printer_v1.memory.fingerprints import build_memory_fingerprint_payload
from printer_v1.operator_cli.action_local_mutation_recorder import (
    ActionLocalMutationRecorder,
    clear_action_local_mutation_recorder,
    emit_insert,
    emit_update,
    install_action_local_mutation_recorder,
)
from printer_v1.operator_cli.action_local_terminal_truth import (
    build_action_local_terminal_truth,
    capture_action_local_baseline,
)
from printer_v1.memory.clean_object_promotion import promote_clean_object
from printer_v1.operator_cli.window_15m_concrete_composition import (
    ConcreteCompositionError,
    ordinary_window_15m_builder_identities,
    production_runtime_constructor_identities,
    production_runtime_default_constructors,
    require_concrete_adapter,
    run_window_15m_concrete_composition_preflight,
)
from printer_v1.sources.geckoterminal import (
    GECKOTERMINAL_SOURCE_NAME,
    build_geckoterminal_adapter,
    build_geckoterminal_token_pools_transport,
)


def _promote_fingerprint(db_path: Path, *, window_id: int) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(promote_clean_object(conn, window_id=window_id).fingerprint_id)
    finally:
        conn.close()


class CompositionOwnerTests(unittest.TestCase):
    def test_runtime_preflight_registry_identity_equality(self) -> None:
        self.assertEqual(
            ordinary_window_15m_builder_identities(),
            production_runtime_constructor_identities(timeout_seconds=1.0, environment={}),
        )
        preflight = run_window_15m_concrete_composition_preflight(
            timeout_seconds=1.0, environment={}
        )
        self.assertEqual("READY", preflight["status"])
        self.assertEqual(
            set(ordinary_window_15m_builder_identities()),
            {row["label"] for row in preflight["matrix"]},
        )

    def test_production_runtime_receives_constructors_from_shared_registry(self) -> None:
        constructors = production_runtime_default_constructors(
            timeout_seconds=1.0, environment={}
        )
        self.assertEqual(
            set(constructors),
            set(ordinary_window_15m_builder_identities()),
        )
        # Every constructor builds with zero network.
        with patch("urllib.request.urlopen") as net:
            for label, builder in constructors.items():
                built = builder()
                self.assertIsNotNone(built, msg=label)
            net.assert_not_called()

    def test_missing_request_kind_contract_fails(self) -> None:
        transport = build_geckoterminal_token_pools_transport(
            "So11111111111111111111111111111111111111112",
            timeout_seconds=1.0,
        )
        adapter = build_geckoterminal_adapter(
            enabled=True, fixture_transport=transport
        )
        # Strip allowed_request_kinds from contract surface.
        class _NoKinds:
            def __init__(self, inner):
                self.enabled = inner.enabled
                self.transport = inner.transport
                self.execute = inner.execute
                self.contract = SimpleNamespace(
                    source_name=GECKOTERMINAL_SOURCE_NAME,
                    allowed_request_kinds=None,
                )

        stripped = _NoKinds(adapter)
        with self.assertRaises(ConcreteCompositionError) as ctx:
            require_concrete_adapter(
                "x",
                stripped,
                expected_source_name=GECKOTERMINAL_SOURCE_NAME,
                expected_request_kind="candidate_market_batch",
            )
        self.assertIn("REQUEST_KIND_CONTRACT_MISSING", str(ctx.exception))


class MutationRecorderTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_action_local_mutation_recorder()
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "mut.sqlite3"
        apply_migrations(self.db)

    def tearDown(self) -> None:
        clear_action_local_mutation_recorder()
        self.tmp.cleanup()

    def test_public_exception_path_receives_exact_inserted_updated_identities(self) -> None:
        recorder = install_action_local_mutation_recorder()
        baseline = capture_action_local_baseline(self.db)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                """INSERT INTO printer_tokens (token_mint, symbol, name, created_at)
                   VALUES ('MintA', 'A', 'A', datetime('now'))"""
            )
            conn.commit()
            token_id = int(
                conn.execute(
                    "SELECT id FROM printer_tokens WHERE token_mint='MintA'"
                ).fetchone()[0]
            )
            emit_insert("printer_tokens", token_id)
            conn.execute(
                "UPDATE printer_tokens SET symbol='B' WHERE id=?",
                (token_id,),
            )
            conn.commit()
            emit_update("printer_tokens", token_id)
        finally:
            conn.close()

        truth = build_action_local_terminal_truth(
            self.db,
            baseline=baseline,
            campaign_id="camp-1",
            run_id="run-1",
            first_terminal_cause="OPERATIONAL_CAMPAIGN_FAILED:Test",
            owner_emitted_inserted_row_ids=recorder.inserted_row_ids(),
            owner_emitted_updated_row_ids=recorder.updated_row_ids(),
            authoritative_write_count=recorder.authoritative_write_count(),
        )
        self.assertEqual(
            [token_id],
            truth["inserted_rows"]["printer_tokens"],
        )
        self.assertEqual(
            [token_id],
            truth["updated_rows"]["printer_tokens"],
        )
        self.assertEqual(2, truth["database_writes"])
        self.assertEqual(
            "OPERATIONAL_CAMPAIGN_FAILED:Test",
            truth["first_terminal_cause"],
        )
        self.assertIn("UPDATE", truth["mutation_classifications"]["printer_tokens"])

    def test_update_only_attributed_to_correct_table_and_row(self) -> None:
        recorder = install_action_local_mutation_recorder()
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                """INSERT INTO printer_tokens (token_mint, symbol, name, created_at)
                   VALUES ('MintU', 'U', 'U', datetime('now'))"""
            )
            conn.commit()
            token_id = int(
                conn.execute(
                    "SELECT id FROM printer_tokens WHERE token_mint='MintU'"
                ).fetchone()[0]
            )
        finally:
            conn.close()
        baseline = capture_action_local_baseline(self.db)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                "UPDATE printer_tokens SET name='Updated' WHERE id=?",
                (token_id,),
            )
            conn.commit()
        finally:
            conn.close()
        emit_update("printer_tokens", token_id)
        truth = build_action_local_terminal_truth(
            self.db,
            baseline=baseline,
            owner_emitted_updated_row_ids=recorder.updated_row_ids(),
            authoritative_write_count=recorder.authoritative_write_count(),
        )
        self.assertEqual("UPDATE_ONLY", truth["mutation_classifications"]["printer_tokens"])
        self.assertEqual([token_id], truth["updated_rows"]["printer_tokens"])
        self.assertNotEqual(0, truth["database_writes"])


class LaneKFingerprintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "fp.sqlite3"
        apply_migrations(self.db)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                """INSERT INTO printer_tokens (token_mint, symbol, name, token_status, created_at)
                   VALUES ('MintFp', 'F', 'F', 'TRACK_FAST', datetime('now'))"""
            )
            conn.execute(
                """INSERT INTO printer_pairs (token_id, pair_address, created_at)
                   VALUES (1, 'PairFp', datetime('now'))"""
            )
            opened = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
            closed = datetime.now(timezone.utc).isoformat()
            ctx = json.dumps(
                {
                    "tracking_lane": "TRACK_FAST",
                    "token_age_bucket": "TOKEN_AGE_0_15M",
                    "pair_age_bucket": "PAIR_AGE_0_15M",
                    "discovery_label": "PUMP_GRADUATED",
                    "e2q_audited": True,
                    "snapshot_id": 1,
                }
            )
            conn.execute(
                """INSERT INTO printer_memory_windows (
                       token_id, pair_id, window_kind, opened_at, closed_at,
                       memory_status, data_quality_label, do_not_train,
                       window_status, outcome_label, memory_quality_label,
                       supporting_context_json, created_by_phase
                   ) VALUES (1, 1, 'WINDOW_15M', ?, ?, 'PARTIAL_MEMORY', 'CLEAN_DATA', 0,
                             'WINDOW_CLOSED', 'SUSTAINED_PUMP', 'PARTIAL_MEMORY', ?, 'test')""",
                (opened, closed, ctx),
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_lane_k_fingerprint_exact_identity_and_real_outcome(self) -> None:
        fp_id = _promote_fingerprint(self.db, window_id=1)
        self.assertIsNotNone(fp_id)
        conn = sqlite3.connect(self.db)
        try:
            row = conn.execute(
                "SELECT fingerprint_payload_json FROM printer_memory_fingerprints WHERE id=?",
                (fp_id,),
            ).fetchone()
        finally:
            conn.close()
        payload = json.loads(row[0])
        self.assertEqual(1, payload["episode_id"])
        self.assertEqual(1, payload["window_id"])
        self.assertEqual(1, payload["token_id"])
        self.assertEqual(1, payload["pair_id"])
        self.assertEqual("WINDOW_15M", payload["window_kind"])
        self.assertEqual("SUSTAINED_PUMP", payload["outcome_label"])
        self.assertEqual("TRACK_FAST", payload["tracking_lane"])
        self.assertEqual("TOKEN_AGE_0_15M", payload["token_age_bucket"])
        self.assertEqual("PAIR_AGE_0_15M", payload["pair_age_bucket"])
        self.assertEqual("PUMP_GRADUATED", payload["discovery_label"])

    def test_unknown_only_when_source_fact_absent(self) -> None:
        # Wipe age/discovery from source context — UNKNOWN is then legitimate.
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                """UPDATE printer_memory_windows
                   SET supporting_context_json=? WHERE id=1""",
                (json.dumps({"tracking_lane": "TRACK_NORMAL", "e2q_audited": True, "snapshot_id": 1}),),
            )
            conn.execute(
                "DELETE FROM printer_memory_fingerprints WHERE episode_id=1"
            )
            conn.commit()
        finally:
            conn.close()
        fp_id = _promote_fingerprint(self.db, window_id=1)
        conn = sqlite3.connect(self.db)
        try:
            payload = json.loads(
                conn.execute(
                    "SELECT fingerprint_payload_json FROM printer_memory_fingerprints WHERE id=?",
                    (fp_id,),
                ).fetchone()[0]
            )
        finally:
            conn.close()
        self.assertEqual("TRACK_NORMAL", payload["tracking_lane"])
        self.assertEqual("UNKNOWN", payload["token_age_bucket"])
        self.assertEqual("UNKNOWN", payload["discovery_label"])
        # Outcome still present on episode row — must not be UNKNOWN.
        self.assertEqual("SUSTAINED_PUMP", payload["outcome_label"])

    def test_payload_builder_does_not_store_objects_in_categorical_fields(self) -> None:
        payload = build_memory_fingerprint_payload(
            {
                "episode_id": 9,
                "window": {
                    "id": 2,
                    "token_id": 3,
                    "pair_id": 4,
                    "window_kind": "WINDOW_15M",
                    "supporting_context_json": '{"tracking_lane":"TRACK_FAST"}',
                },
                "outcome_label": "DUMP",
                "memory_quality_label": "CLEAN_MEMORY",
                "supporting_context": {"market": {"market_regime_label": "FEAR"}},
            },
            episode_id=9,
        )
        for key, value in payload.items():
            self.assertNotIsInstance(value, (dict, list), msg=key)


if __name__ == "__main__":
    unittest.main()
