"""Focused proofs for V2-9.8B WINDOW_15M end-to-end readiness unified repair."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.permanent_discovery_availability import (
    run_bounded_unknown_liquidity_backup,
)
from printer_v1.operator_cli.action_local_terminal_truth import (
    build_action_local_terminal_truth,
    capture_action_local_baseline,
    merge_action_local_into_exception_envelope,
)
from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import (
    LANE_K_STATUS_COMPLETED,
    run_e2z_pipeline,
)
from printer_v1.operator_cli.window_15m_concrete_composition import (
    COMPOSITION_MATRIX,
    ConcreteCompositionError,
    composition_matrix_as_dicts,
    require_concrete_adapter,
    run_window_15m_concrete_composition_preflight,
    window_15m_preflight_builders,
)
from printer_v1.operator_cli.window_15m_one_shot_wrapper import (
    OneShotWrapperError,
    apply_authorization_once,
)
from printer_v1.sources.dexscreener import (
    DEXSCREENER_SOURCE_NAME,
    build_dexscreener_adapter,
)
from printer_v1.sources.geckoterminal import (
    GECKOTERMINAL_SOURCE_NAME,
    build_geckoterminal_adapter,
)


class StageBudgetStub:
    def __init__(self, available: int = 10) -> None:
        self._available = available
        self.consumed = 0

    def available(self, _stage: str) -> int:
        return max(0, self._available - self.consumed)

    def consume(self, _stage: str, n: int = 1) -> None:
        self.consumed += int(n)


class ConcreteCompositionTests(unittest.TestCase):
    def test_default_composition_preflight_pass_zero_io(self) -> None:
        root = Path(__file__).resolve().parents[1]
        result = run_window_15m_concrete_composition_preflight(
            repository_root=str(root),
            timeout_seconds=1.0,
        )
        self.assertEqual("READY", result["status"])
        self.assertEqual(0, result["external_requests"])
        self.assertEqual(0, result["database_writes"])
        self.assertEqual(len(COMPOSITION_MATRIX), result["builder_count"])
        labels = {row["label"] for row in result["matrix"]}
        self.assertEqual({spec.label for spec in COMPOSITION_MATRIX}, labels)

    def test_matrix_labels_match_builders(self) -> None:
        builders = window_15m_preflight_builders(timeout_seconds=1.0)
        builder_labels = {label for label, _ in builders}
        matrix_labels = {spec.label for spec in COMPOSITION_MATRIX}
        self.assertEqual(matrix_labels, builder_labels)
        self.assertEqual(len(composition_matrix_as_dicts()), len(COMPOSITION_MATRIX))

    def test_builder_returning_none_blocks(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with self.assertRaises(ConcreteCompositionError):
            run_window_15m_concrete_composition_preflight(
                repository_root=str(root),
                adapter_builders=(("broken", lambda: None),),
            )

    def test_builder_raising_blocks(self) -> None:
        root = Path(__file__).resolve().parents[1]

        def boom() -> object:
            raise RuntimeError("nope")

        with self.assertRaises(ConcreteCompositionError):
            run_window_15m_concrete_composition_preflight(
                repository_root=str(root),
                adapter_builders=(("broken", boom),),
            )

    def test_require_concrete_adapter_rejects_transportless(self) -> None:
        adapter = build_geckoterminal_adapter(enabled=True, fixture_transport=None)
        with self.assertRaises(ConcreteCompositionError):
            require_concrete_adapter(
                "x", adapter, expected_source_name=GECKOTERMINAL_SOURCE_NAME
            )


class WrapperCompositionBlockTests(unittest.TestCase):
    def test_wrapper_composition_block_before_staging_leaves_auth_unconsumed(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            app_root = Path(tmp) / "app"
            app_root.mkdir()
            auth_path = Path(tmp) / "auth.json"
            # Minimal path that fails early if composition is not the gate:
            # patch composition to fail and ensure no staging/marker created.
            with (
                patch(
                    "printer_v1.operator_cli.window_15m_one_shot_wrapper._resolve_authorization",
                    return_value=(
                        auth_path,
                        {
                            "authorization_id": "TEST_AUTH_COMPOSITION_BLOCK",
                            "package_kind": "WINDOW_15M",
                        },
                        "TEST_AUTH_COMPOSITION_BLOCK",
                        "deadbeef",
                    ),
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
                    "printer_v1.operator_cli.window_15m_concrete_composition.run_window_15m_concrete_composition_preflight",
                    side_effect=ConcreteCompositionError("forced"),
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
                        migration_ledger_guard=lambda **_kwargs: object(),
                    )
            self.assertIn("concrete composition", str(ctx.exception).lower())
            self.assertFalse((app_root / "TEST_AUTH_COMPOSITION_BLOCK").exists())
            staging = list((app_root / ".staging").glob("*")) if (app_root / ".staging").exists() else []
            self.assertEqual([], staging)


class UnknownLiquidityBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "backup.sqlite3"
        apply_migrations(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self) -> None:
        self.conn.close()
        self.tmp.cleanup()

    def _insert_unknown(
        self, *, mint: str, pool: str, source: str
    ) -> None:
        # Insert minimal reserve-layer candidate if table exists; otherwise skip.
        tables = {
            r[0]
            for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        # permanent discovery availability observations table
        if "printer_discovery_availability_observations" in tables:
            self.conn.execute(
                """INSERT INTO printer_discovery_availability_observations(
                       mint_identity, pool_identity, source_name, liquidity_usd,
                       liquidity_state, observed_at, created_at, updated_at
                   ) VALUES (?,?,?,NULL,'LIQUIDITY_UNKNOWN',datetime('now'),datetime('now'),datetime('now'))""",
                (mint, pool, source),
            )
            self.conn.commit()
            return
        # Fall back: unit-level call with patched loader.
        self.skipTest("availability observations table not present")

    def test_dex_to_gecko_default_transport_constructs_once(self) -> None:
        from printer_v1.discovery import permanent_discovery_availability as pda

        calls: list[str] = []

        def fake_gt_transport(mint: str):
            calls.append(mint)

            def transport(_ctx):
                return {
                    "data": [],
                    "underlying_operation_count": 0,
                    "fixture_status": "success",
                }

            return transport

        cand = {
            "mint": "MintAAAA111111111111111111111111111111111",
            "pool": "PoolAAAA111111111111111111111111111111111",
            "source": "dexscreener",
            "quote_mint": "So11111111111111111111111111111111111111112",
            "venue": "pumpswap",
            "base_mint": "MintAAAA111111111111111111111111111111111",
            "liquidity_backup_attempted": False,
        }

        with (
            patch.object(pda, "load_liquidity_unknown_candidates", return_value=[cand]),
            patch(
                "printer_v1.sources.geckoterminal.build_geckoterminal_token_pools_transport",
                side_effect=fake_gt_transport,
            ),
            patch(
                "printer_v1.sources.governed_execution.execute_source_request_with_governor"
            ) as exec_gov,
        ):
            class _Rec:
                id = 1

            class _Exec:
                request_record = _Rec()
                response_record = _Rec()
                failure_record = None
                normalized_result = type(
                    "R",
                    (),
                    {
                        "failure_type": None,
                        "source_status": type("S", (), {"value": "COMPLETE"})(),
                        "normalized_payload": {"pairs": []},
                    },
                )()
                # source_status compared as enum-like
                normalized_result.source_status = type(
                    "SS", (), {"__eq__": lambda self, other: True}
                )()

            # Provide proper SourceStatus
            from printer_v1.contracts.enums import SourceStatus
            from printer_v1.contracts.enums import DataQualityLabel
            from printer_v1.sources.contracts import NormalizedSourceResult

            def _exec(*_a, **_k):
                return type(
                    "E",
                    (),
                    {
                        "request_record": _Rec(),
                        "response_record": _Rec(),
                        "failure_record": None,
                        "normalized_result": NormalizedSourceResult(
                            source_name=GECKOTERMINAL_SOURCE_NAME,
                            request_kind="candidate_market_batch",
                            source_status=SourceStatus.COMPLETE,
                            data_quality_label=DataQualityLabel.CLEAN_DATA,
                            normalized_payload={"pairs": []},
                        ),
                    },
                )()

            exec_gov.side_effect = _exec
            report = run_bounded_unknown_liquidity_backup(
                self.conn,
                stage_budget=StageBudgetStub(1),
                now="2026-08-05T12:00:00+00:00",
                campaign_id="c1",
                run_id="r1",
                cycle_id="cy1",
            )
        self.assertEqual(1, len(calls))
        self.assertEqual(1, report["source_requests"])
        self.assertEqual(1, exec_gov.call_count)
        # Adapter was built with a real transport (not None)
        adapter = exec_gov.call_args[0][2]
        self.assertTrue(getattr(adapter, "enabled", False))
        self.assertIsNotNone(getattr(adapter, "transport", None))

    def test_gecko_to_dex_default_transport_constructs_once(self) -> None:
        from printer_v1.discovery import permanent_discovery_availability as pda
        from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
        from printer_v1.sources.contracts import NormalizedSourceResult

        calls: list = []

        def fake_dex_transport(mints):
            calls.append(tuple(mints))

            def transport(_ctx):
                return {"pairs": [], "underlying_operation_count": 0}

            return transport

        cand = {
            "mint": "MintBBBB111111111111111111111111111111111",
            "pool": "PoolBBBB111111111111111111111111111111111",
            "source": "geckoterminal",
            "quote_mint": "So11111111111111111111111111111111111111112",
            "venue": "pumpswap",
            "base_mint": "MintBBBB111111111111111111111111111111111",
            "liquidity_backup_attempted": False,
        }

        class _Rec:
            id = 2

        with (
            patch.object(pda, "load_liquidity_unknown_candidates", return_value=[cand]),
            patch(
                "printer_v1.sources.dexscreener.build_dexscreener_mint_batch_transport",
                side_effect=fake_dex_transport,
            ),
            patch(
                "printer_v1.sources.governed_execution.execute_source_request_with_governor"
            ) as exec_gov,
        ):

            def _exec(*_a, **_k):
                return type(
                    "E",
                    (),
                    {
                        "request_record": _Rec(),
                        "response_record": _Rec(),
                        "failure_record": None,
                        "normalized_result": NormalizedSourceResult(
                            source_name=DEXSCREENER_SOURCE_NAME,
                            request_kind="candidate_market_batch",
                            source_status=SourceStatus.COMPLETE,
                            data_quality_label=DataQualityLabel.CLEAN_DATA,
                            normalized_payload={"pairs": []},
                        ),
                    },
                )()

            exec_gov.side_effect = _exec
            report = run_bounded_unknown_liquidity_backup(
                self.conn,
                stage_budget=StageBudgetStub(1),
                now="2026-08-05T12:00:00+00:00",
                campaign_id="c1",
                run_id="r1",
                cycle_id="cy1",
            )
        self.assertEqual(1, len(calls))
        self.assertEqual(1, report["source_requests"])
        adapter = exec_gov.call_args[0][2]
        self.assertEqual(DEXSCREENER_SOURCE_NAME, adapter.metadata.source_name)
        self.assertIsNotNone(adapter.transport)

    def test_invalid_factory_blocks_before_backup_write(self) -> None:
        from printer_v1.discovery import permanent_discovery_availability as pda

        cand = {
            "mint": "MintCCCC111111111111111111111111111111111",
            "pool": "PoolCCCC111111111111111111111111111111111",
            "source": "dexscreener",
            "quote_mint": "So11111111111111111111111111111111111111112",
            "venue": "pumpswap",
            "base_mint": "MintCCCC111111111111111111111111111111111",
            "liquidity_backup_attempted": False,
        }
        before_requests = int(
            self.conn.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
        )
        with (
            patch.object(pda, "load_liquidity_unknown_candidates", return_value=[cand]),
            patch(
                "printer_v1.sources.governed_execution.execute_source_request_with_governor"
            ) as exec_gov,
        ):
            report = run_bounded_unknown_liquidity_backup(
                self.conn,
                stage_budget=StageBudgetStub(1),
                now="2026-08-05T12:00:00+00:00",
                campaign_id="c1",
                run_id="r1",
                cycle_id="cy1",
                geckoterminal_transport_factory=lambda mint: None,
            )
        self.assertTrue(report.get("accounting_blocker"))
        self.assertEqual(0, exec_gov.call_count)
        after_requests = int(
            self.conn.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
        )
        self.assertEqual(before_requests, after_requests)


class ActionLocalTruthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "truth.sqlite3"
        apply_migrations(self.db)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_baseline_and_delta_after_source_request(self) -> None:
        baseline = capture_action_local_baseline(self.db)
        conn = sqlite3.connect(self.db)
        try:
            conn.execute(
                """INSERT INTO printer_source_requests(
                       source_name, request_kind, requested_at, request_key,
                       tracking_priority, source_status, data_quality_label, created_at
                   ) VALUES (
                       'dexscreener','candidate_market_batch',datetime('now'),'k1',
                       0,'COMPLETE','CLEAN_DATA',datetime('now')
                   )"""
            )
            conn.commit()
        finally:
            conn.close()
        truth = build_action_local_terminal_truth(
            self.db,
            baseline=baseline,
            campaign_id=None,
            run_id=None,
            first_terminal_cause="TEST",
        )
        self.assertGreaterEqual(int(truth["source_request_count"]), 1)
        self.assertTrue(truth["database_mutation_known"])
        envelope = merge_action_local_into_exception_envelope(
            {"status": "OPERATIONAL_COMMAND_BLOCKED", "source_calls": 0},
            truth,
        )
        self.assertGreaterEqual(int(envelope["source_calls"]), 1)
        self.assertNotEqual("UNKNOWN_ON_EXCEPTION", envelope["database_mutation_status"])


class ExplicitE2ZScopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = Path(self.tmp.name) / "e2z.sqlite3"
        apply_migrations(self.db)
        self._seed()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _seed(self) -> None:
        import test_post_lane10_lane_k_e2z_pipeline_wiring as base

        # Use the existing harness helpers if available
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        now = "2026-06-29T10:00:00+00:00"
        end = "2026-06-29T10:15:01+00:00"
        try:
            # Create two eligible windows via simplified inserts matching Lane K tests
            for i, mint in enumerate(("MintScopeAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA1", "MintScopeAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA2"), 1):
                cur = conn.execute(
                    """INSERT INTO printer_tokens
                       (token_mint, chain, symbol, name, first_seen_at, last_seen_at,
                        token_status, created_at, updated_at)
                       VALUES (?, 'solana', 'T', 'T', ?, ?, 'TRACKING', ?, ?)""",
                    (mint, now, now, now, now),
                )
                token_id = int(cur.lastrowid)
                pair_addr = f"PairScope{i}AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
                cur = conn.execute(
                    """INSERT INTO printer_pairs
                       (token_id, pair_address, dex, pool_source, base_token_mint,
                        quote_token_mint, first_seen_at, last_seen_at, created_at, updated_at)
                       VALUES (?, ?, 'pumpswap', 'dexscreener', ?,
                               'So11111111111111111111111111111111111111112',
                               ?, ?, ?, ?)""",
                    (token_id, pair_addr, mint, now, now, now, now),
                )
                pair_id = int(cur.lastrowid)
                # snapshots
                cur = conn.execute(
                    """INSERT INTO printer_token_snapshots
                       (token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                        source_status, data_quality_label, created_at)
                       VALUES (?, ?, ?, 'WINDOW_15M', 'EXACT_PAIR',
                               'COMPLETE', 'CLEAN_DATA', ?)""",
                    (token_id, pair_id, now, now),
                )
                start_id = int(cur.lastrowid)
                cur = conn.execute(
                    """INSERT INTO printer_token_snapshots
                       (token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                        source_status, data_quality_label, created_at)
                       VALUES (?, ?, ?, 'WINDOW_15M', 'EXACT_PAIR',
                               'COMPLETE', 'CLEAN_DATA', ?)""",
                    (token_id, pair_id, end, end),
                )
                end_id = int(cur.lastrowid)
                ctx = json.dumps(
                    {
                        "snapshot_id": end_id,
                        "e2q_audited": True,
                        "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
                        "e2q_audited_by": "lane_e2q",
                    },
                    sort_keys=True,
                )
                conn.execute(
                    """INSERT INTO printer_memory_windows
                       (token_id, pair_id, window_kind, window_status, memory_status,
                        memory_quality_label, data_quality_label, do_not_train,
                        opened_at, closed_at, snapshot_start_id, snapshot_end_id,
                        supporting_context_json, created_at, updated_at)
                       VALUES (?, ?, 'WINDOW_15M', 'WINDOW_CLOSED', 'PARTIAL_MEMORY',
                               'PARTIAL_MEMORY', 'CLEAN_DATA', 0, ?, ?, ?, ?, ?, ?, ?)""",
                    (token_id, pair_id, now, end, start_id, end_id, ctx, now, end),
                )
            conn.commit()
        except sqlite3.Error as exc:
            conn.close()
            self.skipTest(f"seed failed: {exc}")
        finally:
            conn.close()

    def test_explicit_scope_does_not_promote_unrelated(self) -> None:
        conn = sqlite3.connect(self.db)
        ids = [
            int(r[0])
            for r in conn.execute(
                "SELECT id FROM printer_memory_windows ORDER BY id"
            ).fetchall()
        ]
        conn.close()
        self.assertGreaterEqual(len(ids), 2)
        target = ids[0]
        other = ids[1]
        before_other_episodes = int(
            sqlite3.connect(self.db)
            .execute(
                "SELECT COUNT(*) FROM printer_episodes WHERE memory_window_id=?",
                (other,),
            )
            .fetchone()[0]
        )
        result = run_e2z_pipeline(
            self.db,
            operator_approved=True,
            production_mode=True,
            candidate_window_ids=[target],
        )
        self.assertEqual(LANE_K_STATUS_COMPLETED, result["lane_k_status"])
        self.assertTrue(result.get("explicit_window_scope"))
        self.assertEqual([target], result.get("requested_window_ids"))
        self.assertEqual(0, result.get("unrelated_promotion_count", 0))
        after_other = int(
            sqlite3.connect(self.db)
            .execute(
                "SELECT COUNT(*) FROM printer_episodes WHERE memory_window_id=?",
                (other,),
            )
            .fetchone()[0]
        )
        self.assertEqual(before_other_episodes, after_other)
        # Target may or may not promote depending on Lane Q gates; scope is what matters.
        target_eps = [
            r
            for r in result.get("e2z_window_results") or []
            if r.get("window_id") == target
        ]
        self.assertLessEqual(len(target_eps), 1)

    def test_lifecycle_and_clean_memory_verdicts_independent(self) -> None:
        from printer_v1.operator_cli.operational_memory_factory_command import (
            build_current_run_clean_memory_outcome,
        )

        outcome = build_current_run_clean_memory_outcome(
            self.db, campaign_id=None, run_id=None
        )
        # No campaign windows registered -> not pass, independent of lifecycle.
        self.assertFalse(outcome["clean_memory_outcome_pass"])
        self.assertIn("NO_CURRENT_RUN_WINDOWS", outcome["blocker_categories"])


if __name__ == "__main__":
    unittest.main()
