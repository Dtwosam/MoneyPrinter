from __future__ import annotations

import inspect
import json
import sqlite3
import unittest
from unittest.mock import patch

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.one_token_4h_runtime import (
    STANDARD_FOUR_HOUR_ELIGIBILITY_CONTRACT_VERSION,
    standard_campaign_lifecycle_budget,
)


RUN_ID = "factory-run"
STEP_ID = 7


def _eligibility_manifest(*, slot_id: str = "slot-2") -> dict[str, object]:
    return {
        "contract_version": STANDARD_FOUR_HOUR_ELIGIBILITY_CONTRACT_VERSION,
        "campaign_id": "campaign",
        "campaign_run_id": "campaign-run",
        "cycle_id": "cycle",
        "token_slot_id": slot_id,
        "token_id": 22,
        "pair_id": 220,
        "verdict": "CONTINUE_TO_WINDOW_4H",
        "eligible": True,
    }


def _close_db(*, existing_barrier: dict[str, object] | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE printer_memory_factory_run_steps (
            id INTEGER PRIMARY KEY,
            run_id TEXT NOT NULL,
            step_kind TEXT NOT NULL,
            step_status TEXT NOT NULL,
            result_json TEXT,
            updated_at TEXT
        )
        """
    )
    payload: dict[str, object] = {
        "memory_window_id": 171,
        "physical_close": "preserve-me",
        "standard_four_hour_eligibility": _eligibility_manifest(),
    }
    if existing_barrier is not None:
        payload["standard_four_hour_barrier"] = existing_barrier
    conn.execute(
        """
        INSERT INTO printer_memory_factory_run_steps
            (id,run_id,step_kind,step_status,result_json,updated_at)
        VALUES (?,?, 'CONTINUATION_CLOSE','SUCCEEDED',?,NULL)
        """,
        (STEP_ID, RUN_ID, json.dumps(payload, sort_keys=True)),
    )
    conn.commit()
    return conn


class FourthStandardFourHourManifestMergeRedProof(unittest.TestCase):
    def _merge(self):
        merge = getattr(factory, "_merge_standard_four_hour_barrier_result", None)
        self.assertIsNotNone(
            merge,
            "RED: standard 4h close needs an authoritative post-barrier merge helper",
        )
        return merge

    def test_authoritative_post_barrier_merge_preserves_eligibility_manifest(self) -> None:
        conn = _close_db()
        try:
            barrier = {
                "status": "STANDARD_FOUR_HOUR_BARRIER_RELEASED",
                "continuation_count": 2,
                "planned_jobs": 62,
            }
            merged = self._merge()(
                conn,
                run_id=RUN_ID,
                step_id=STEP_ID,
                barrier=barrier,
            )
            row = conn.execute(
                "SELECT result_json FROM printer_memory_factory_run_steps WHERE id=?",
                (STEP_ID,),
            ).fetchone()
            self.assertIsNotNone(row)
            persisted = json.loads(str(row["result_json"]))
            self.assertEqual(
                persisted["standard_four_hour_eligibility"],
                _eligibility_manifest(),
            )
            self.assertEqual(persisted["physical_close"], "preserve-me")
            self.assertEqual(persisted["standard_four_hour_barrier"], barrier)
            self.assertEqual(merged, persisted)
        finally:
            conn.close()

    def test_equal_barrier_replay_is_idempotent(self) -> None:
        barrier = {
            "status": "STANDARD_FOUR_HOUR_BARRIER_RELEASED",
            "continuation_count": 2,
        }
        conn = _close_db(existing_barrier=barrier)
        try:
            merged = self._merge()(
                conn,
                run_id=RUN_ID,
                step_id=STEP_ID,
                barrier=barrier,
            )
            self.assertEqual(merged["standard_four_hour_barrier"], barrier)
            self.assertEqual(
                merged["standard_four_hour_eligibility"],
                _eligibility_manifest(),
            )
        finally:
            conn.close()

    def test_conflicting_barrier_replay_fails_closed_without_erasing_manifest(self) -> None:
        original = {"status": "AWAITING_PEER_FIRST_HOUR_CLOSE"}
        conn = _close_db(existing_barrier=original)
        try:
            before = str(
                conn.execute(
                    "SELECT result_json FROM printer_memory_factory_run_steps WHERE id=?",
                    (STEP_ID,),
                ).fetchone()[0]
            )
            with self.assertRaises(ValueError):
                self._merge()(
                    conn,
                    run_id=RUN_ID,
                    step_id=STEP_ID,
                    barrier={"status": "STANDARD_FOUR_HOUR_BARRIER_RELEASED"},
                )
            after = str(
                conn.execute(
                    "SELECT result_json FROM printer_memory_factory_run_steps WHERE id=?",
                    (STEP_ID,),
                ).fetchone()[0]
            )
            self.assertEqual(after, before)
        finally:
            conn.close()

    def test_runner_wires_authoritative_merge_instead_of_stale_result_rewrite(self) -> None:
        source = inspect.getsource(factory.run_one_command_15m_factory)
        self.assertIn("_merge_standard_four_hour_barrier_result", source)


class FourthStandardFourHourBudgetProjectionRedProof(unittest.TestCase):
    def test_both_track_normal_slots_expose_exact_aggregate_phase_budget(self) -> None:
        budget = standard_campaign_lifecycle_budget(
            ("TRACK_NORMAL", "TRACK_NORMAL"),
            (True, True),
        )
        self.assertEqual(budget["request_ceiling"], 140)
        self.assertEqual(budget["scheduler_ceiling"], 114)
        self.assertEqual(budget.get("phase_request_ceiling"), 78)
        self.assertEqual(budget.get("phase_scheduler_ceiling"), 68)
        self.assertEqual(budget.get("phase_holder_fallback_ceiling"), 4)

    def test_one_eligible_track_normal_slot_keeps_two_token_prefix_and_one_suffix(self) -> None:
        budget = standard_campaign_lifecycle_budget(
            ("TRACK_NORMAL", "TRACK_NORMAL"),
            (True, False),
        )
        self.assertEqual(budget["request_ceiling"], 101)
        self.assertEqual(budget["scheduler_ceiling"], 80)
        self.assertEqual(budget.get("phase_request_ceiling"), 39)
        self.assertEqual(budget.get("phase_scheduler_ceiling"), 34)
        self.assertEqual(budget.get("phase_holder_fallback_ceiling"), 2)

    def test_no_eligible_slots_has_zero_aggregate_four_hour_phase(self) -> None:
        budget = standard_campaign_lifecycle_budget(
            ("TRACK_NORMAL", "TRACK_NORMAL"),
            (False, False),
        )
        self.assertEqual(budget["request_ceiling"], 62)
        self.assertEqual(budget["scheduler_ceiling"], 46)
        self.assertEqual(budget.get("phase_request_ceiling"), 0)
        self.assertEqual(budget.get("phase_scheduler_ceiling"), 0)
        self.assertEqual(budget.get("phase_holder_fallback_ceiling"), 0)

    def _reporting_budget(self):
        helper = getattr(factory, "_standard_four_hour_reporting_budget_for_run", None)
        self.assertIsNotNone(
            helper,
            "RED: reporting needs a fail-closed standard subset budget resolver",
        )
        return helper

    def test_reporting_budget_uses_exact_standard_subset_projection(self) -> None:
        budget = standard_campaign_lifecycle_budget(
            ("TRACK_NORMAL", "TRACK_NORMAL"),
            (True, True),
        )
        with patch.object(
            factory,
            "_standard_four_hour_cumulative_budget_for_run",
            return_value=budget,
        ):
            report = self._reporting_budget()(sqlite3.connect(":memory:"), RUN_ID)
        self.assertTrue(report["available"])
        self.assertIsNone(report["reason"])
        self.assertEqual(report["budget"]["request_ceiling"], 140)
        self.assertEqual(report["budget"]["scheduler_ceiling"], 114)
        self.assertEqual(report["budget"]["phase_request_ceiling"], 78)
        self.assertEqual(report["budget"]["phase_scheduler_ceiling"], 68)

    def test_partial_manifest_reporting_is_unavailable_never_one_token_fallback(self) -> None:
        with patch.object(
            factory,
            "_standard_four_hour_cumulative_budget_for_run",
            side_effect=ValueError("partial standard four-hour eligibility manifest"),
        ):
            report = self._reporting_budget()(sqlite3.connect(":memory:"), RUN_ID)
        self.assertFalse(report["available"])
        self.assertEqual(
            report["reason"],
            "partial standard four-hour eligibility manifest",
        )
        self.assertIsNone(report["budget"])

    def test_run_budgets_wires_standard_reporting_resolver(self) -> None:
        source = inspect.getsource(factory._run_budgets)
        self.assertIn("_standard_four_hour_reporting_budget_for_run", source)


if __name__ == "__main__":
    unittest.main()
