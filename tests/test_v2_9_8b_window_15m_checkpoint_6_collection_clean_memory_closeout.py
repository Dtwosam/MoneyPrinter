"""Checkpoint 6 fail-first contracts for WINDOW_15M clean-memory closeout."""

from __future__ import annotations

import inspect
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.memory.clean_object_promotion import promote_clean_object
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.lane_x8_5m_support_integration import (
    LANE_X8_STATUS_BLOCKED,
    capture_5m_support_evidence,
)
from printer_v1.snapshots.recorder import record_token_snapshot


_MINT = "Cp6Mint111111111111111111111111111111111111111"
_PAIR = "Cp6Pair111111111111111111111111111111111111111"
_OPEN = "2026-08-06T12:00:00+00:00"
_TRIGGER = "2026-08-06T12:05:00+00:00"
_CLOSE = "2026-08-06T12:15:00+00:00"
_OUTCOME = "SHORT_TERM_PUMP"


class Checkpoint6Contracts(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _token_pair(self) -> tuple[int, int]:
        conn = self._connect()
        try:
            token_id = int(
                conn.execute(
                    "INSERT INTO printer_tokens (token_mint, chain, token_status) "
                    "VALUES (?, 'solana', 'TRACK_FAST')",
                    (_MINT,),
                ).lastrowid
            )
            pair_id = int(
                conn.execute(
                    "INSERT INTO printer_pairs (token_id, pair_address, base_token_mint) "
                    "VALUES (?, ?, ?)",
                    (token_id, _PAIR, _MINT),
                ).lastrowid
            )
            conn.commit()
            return token_id, pair_id
        finally:
            conn.close()

    def _clean_window(self, *, rich_context: bool = False) -> tuple[int, int, int]:
        token_id, pair_id = self._token_pair()
        context = {
            "snapshot_id": 99,
            "e2q_audited": True,
            "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
            "e2q_audited_by": "lane_e2q",
            "tracking_lane": "TRACK_FAST",
        }
        if rich_context:
            context.update(
                {
                    "market": {"market_regime_label": "MARKET_RISK_ON"},
                    "chain_heat": {"chain_heat_label": "CHAIN_HEAT_HIGH"},
                    "safety": {
                        "safety_status_label": "SAFETY_ACCEPTABLE",
                        "rug_risk_label": "RUG_RISK_LOW",
                    },
                    "liquidity_exit": {
                        "liquidity_state_label": "LIQUIDITY_HEALTHY",
                        "exit_realism_label": "EXIT_REALISTIC",
                        "realism_gate_label": "REALISM_PASS",
                    },
                    "trading_flow": {
                        "flow_direction_label": "FLOW_BUY_DOMINANT",
                        "flow_pressure_label": "FLOW_PRESSURE_HIGH",
                    },
                    "chart_volatility": {
                        "trend_structure_label": "TREND_UP",
                        "volatility_label": "VOLATILITY_ELEVATED",
                        "candle_path_label": "PATH_CONTINUATION",
                    },
                    "micro_events": [
                        {
                            "micro_event_state_label": "TRADABLE_MICRO_PUMP",
                            "held_to_15m_result_label": "HELD_TO_15M_CONTINUED",
                        }
                    ],
                    "token_age_bucket": "TOKEN_AGE_LT_1D",
                    "pair_age_bucket": "PAIR_AGE_LT_1D",
                    "discovery_label": "DISCOVERY_ACTIVE",
                }
            )
        conn = self._connect()
        try:
            window_id = int(
                conn.execute(
                    """
                    INSERT INTO printer_memory_windows (
                        token_id,pair_id,window_kind,opened_at,closed_at,
                        memory_status,data_quality_label,do_not_train,window_status,
                        memory_quality_label,outcome_label,supporting_context_json,
                        created_by_phase,created_at,updated_at
                    ) VALUES (?,?,'WINDOW_15M',?,?,'PARTIAL_MEMORY','CLEAN_DATA',0,
                              'WINDOW_CLOSED','PARTIAL_MEMORY',?,?, 'checkpoint6_red',?,?)
                    """,
                    (
                        token_id,
                        pair_id,
                        _OPEN,
                        _CLOSE,
                        _OUTCOME,
                        json.dumps(context, sort_keys=True),
                        _CLOSE,
                        _CLOSE,
                    ),
                ).lastrowid
            )
            conn.commit()
            return token_id, pair_id, window_id
        finally:
            conn.close()

    def test_red_a_clean_episode_preserves_exact_window_outcome(self) -> None:
        _, _, window_id = self._clean_window()
        result = None
        conn = self._connect()
        try:
            result = promote_clean_object(conn, window_id=window_id)
            episode = conn.execute(
                "SELECT episode_outcome_label FROM printer_episodes WHERE id=?",
                (result.episode_id,),
            ).fetchone()
            self.assertEqual(episode["episode_outcome_label"], _OUTCOME)
        finally:
            conn.close()

    def test_red_b_fingerprint_preserves_rich_window_conditions(self) -> None:
        _, _, window_id = self._clean_window(rich_context=True)
        conn = self._connect()
        try:
            result = promote_clean_object(conn, window_id=window_id)
            row = conn.execute(
                "SELECT fingerprint_payload_json FROM printer_memory_fingerprints WHERE id=?",
                (result.fingerprint_id,),
            ).fetchone()
            payload = json.loads(row["fingerprint_payload_json"])
        finally:
            conn.close()
        expected = {
            "outcome_label": _OUTCOME,
            "market_regime_label": "MARKET_RISK_ON",
            "chain_heat_label": "CHAIN_HEAT_HIGH",
            "safety_status_label": "SAFETY_ACCEPTABLE",
            "rug_risk_label": "RUG_RISK_LOW",
            "liquidity_state_label": "LIQUIDITY_HEALTHY",
            "exit_realism_label": "EXIT_REALISTIC",
            "realism_gate_label": "REALISM_PASS",
            "flow_direction_label": "FLOW_BUY_DOMINANT",
            "flow_pressure_label": "FLOW_PRESSURE_HIGH",
            "trend_structure_label": "TREND_UP",
            "volatility_label": "VOLATILITY_ELEVATED",
            "candle_path_label": "PATH_CONTINUATION",
            "micro_event_state_label": "TRADABLE_MICRO_PUMP",
            "held_to_15m_result_label": "HELD_TO_15M_CONTINUED",
            "token_age_bucket": "TOKEN_AGE_LT_1D",
            "pair_age_bucket": "PAIR_AGE_LT_1D",
            "discovery_label": "DISCOVERY_ACTIVE",
            "tracking_lane": "TRACK_FAST",
        }
        for field, value in expected.items():
            with self.subTest(field=field):
                self.assertEqual(payload[field], value)

    def test_red_c_final_15m_disposition_no_longer_backfills_5m_support(self) -> None:
        natural_source = inspect.getsource(factory._natural_disposition_schedule)
        module_source = inspect.getsource(factory)
        self.assertIn("derive_natural_disposition", natural_source)
        self.assertNotIn("_capture_same_stream_5m_support(", natural_source)
        self.assertIn("_evaluate_event_time_5m_support_for_snapshot", module_source)
        self.assertIn("_materialize_frozen_5m_support", module_source)

    def test_red_d_materialized_support_persists_exact_ownership_and_provenance(self) -> None:
        token_id, pair_id = self._token_pair()
        _, snapshot_start_id = record_token_snapshot(
            self.db_path,
            {
                "token_id": token_id,
                "pair_id": pair_id,
                "captured_at": _OPEN,
                "tracking_lane": "TRACK_FAST",
                "snapshot_mode": "NORMAL_MODE",
                "price_usd": 1.0,
                "liquidity_usd": 100000.0,
                "source_status": "COMPLETE",
                "data_quality_label": "CLEAN_DATA",
            },
        )
        _, snapshot_end_id = record_token_snapshot(
            self.db_path,
            {
                "token_id": token_id,
                "pair_id": pair_id,
                "captured_at": _TRIGGER,
                "tracking_lane": "TRACK_FAST",
                "snapshot_mode": "NORMAL_MODE",
                "price_usd": 1.2,
                "liquidity_usd": 100000.0,
                "source_status": "COMPLETE",
                "data_quality_label": "CLEAN_DATA",
            },
        )
        conn = self._connect()
        try:
            parent_window_id = int(
                conn.execute(
                    """
                    INSERT INTO printer_memory_windows (
                        token_id,pair_id,window_kind,opened_at,closed_at,
                        memory_status,data_quality_label,do_not_train,window_status,
                        memory_quality_label,supporting_context_json,created_by_phase,
                        created_at,updated_at
                    ) VALUES (?,?,'WINDOW_15M',?,?,'PARTIAL_MEMORY','CLEAN_DATA',0,
                              'WINDOW_CLOSED','PARTIAL_MEMORY','{}','checkpoint6_red',?,?)
                    """,
                    (token_id, pair_id, _OPEN, _CLOSE, _CLOSE, _CLOSE),
                ).lastrowid
            )
            conn.commit()
        finally:
            conn.close()

        frozen = {
            "verdict": "CAPTURE_SUPPORT",
            "campaign_id": "campaign-cp6",
            "campaign_run_id": "run-cp6",
            "cycle_id": "cycle-cp6",
            "factory_run_id": "factory-cp6",
            "token_slot_id": "slot-cp6",
            "token_id": str(token_id),
            "mint_id": _MINT,
            "pair_id": str(pair_id),
            "pair_address": _PAIR,
            "root_15m_lifecycle_id": "root-15m-cp6",
            "containing_main_window_id": "campaign-window-cp6",
            "containing_main_window_kind": "WINDOW_15M",
            "scheduler_work_id": "scheduler-work-cp6",
            "scheduler_job_id": 77,
            "trigger_family": "FAST_COORDINATED_PUMP",
            "trigger_time": _TRIGGER,
            "evidence_cutoff": _TRIGGER,
            "triggering_snapshot_ids": [snapshot_start_id, snapshot_end_id],
            "source_provenance": [
                {
                    "snapshot_id": snapshot_start_id,
                    "source_name": "dexscreener",
                    "source_request_id": 11,
                    "source_response_id": 21,
                    "scheduler_work_id": "scheduler-work-cp6",
                    "source_status": "COMPLETE",
                    "data_quality_label": "CLEAN_DATA",
                    "governor_approved": True,
                    "traceable": True,
                },
                {
                    "snapshot_id": snapshot_end_id,
                    "source_name": "dexscreener",
                    "source_request_id": 12,
                    "source_response_id": 22,
                    "scheduler_work_id": "scheduler-work-cp6",
                    "source_status": "COMPLETE",
                    "data_quality_label": "CLEAN_DATA",
                    "governor_approved": True,
                    "traceable": True,
                },
            ],
        }
        result = capture_5m_support_evidence(
            self.db_path,
            parent_window_id,
            token_id,
            pair_id,
            operator_approved=True,
            snapshot_start_id=snapshot_start_id,
            snapshot_end_id=snapshot_end_id,
            run_id="factory-cp6",
            tracking_lane="TRACK_FAST",
            support_capture=frozen,
        )
        self.assertTrue(result["captured"])
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT supporting_context_json FROM printer_memory_windows WHERE id=?",
                (result["window_5m_id"],),
            ).fetchone()
            context = json.loads(row["supporting_context_json"])
        finally:
            conn.close()
        for key in (
            "campaign_id",
            "campaign_run_id",
            "cycle_id",
            "factory_run_id",
            "token_slot_id",
            "root_15m_lifecycle_id",
            "trigger_family",
            "trigger_time",
            "evidence_cutoff",
            "triggering_snapshot_ids",
            "source_provenance",
            "scheduler_work_id",
            "scheduler_job_id",
        ):
            with self.subTest(key=key):
                self.assertEqual(context[key], frozen[key])
        self.assertTrue(context["support_only"])
        self.assertFalse(context["continuation_authority"])
        self.assertFalse(context["retrieval_authority"])
        self.assertFalse(context["decision_authority"])
        self.assertFalse(context["financial_authority"])

        mismatched = dict(frozen)
        mismatched["pair_id"] = str(pair_id + 999)
        blocked = capture_5m_support_evidence(
            self.db_path,
            parent_window_id,
            token_id,
            pair_id,
            operator_approved=True,
            support_capture=mismatched,
        )
        self.assertEqual(blocked["lane_x8_capture_status"], LANE_X8_STATUS_BLOCKED)
        self.assertFalse(blocked["captured"])


if __name__ == "__main__":
    unittest.main()
