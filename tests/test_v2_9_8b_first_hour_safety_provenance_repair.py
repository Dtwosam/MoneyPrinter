from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import unittest

from printer_v1.operator_cli.first_hour_safety_binding import (
    FirstHourSafetyBindingError,
    attach_first_hour_safety_overlay,
)
from printer_v1.operator_cli import operational_standard_4h as standard_4h
from printer_v1.operator_cli.one_token_4h_runtime import (
    standard_campaign_lifecycle_budget,
)
from printer_v1.sources.measured_transport import (
    FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT,
    LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND,
)


ROOT = Path(__file__).resolve().parents[1]
FACTORY = ROOT / "src/printer_v1/operator_cli/one_command_15m_factory.py"
STANDARD_4H = ROOT / "src/printer_v1/operator_cli/operational_standard_4h.py"


def _binding_db(
    *,
    window_kind: str = "WINDOW_1H",
    memory_snapshot_id: int = 900,
    composite_snapshot_id: int = 900,
    composite_token_id: int = 39,
    composite_pair_id: int = 43,
    composite_captured_at: str = "2026-08-22T13:00:00+00:00",
    contribution_captured_at: str = "2026-08-22T13:00:00+00:00",
) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE printer_memory_windows (
            id INTEGER PRIMARY KEY,
            token_id INTEGER NOT NULL,
            pair_id INTEGER NOT NULL,
            window_kind TEXT NOT NULL,
            snapshot_end_id INTEGER,
            window_end_at TEXT NOT NULL,
            supporting_context_json TEXT
        );
        CREATE TABLE printer_safety_evidence_composites (
            id INTEGER PRIMARY KEY,
            token_id INTEGER NOT NULL,
            pair_id INTEGER NOT NULL,
            snapshot_id INTEGER NOT NULL,
            token_mint TEXT NOT NULL,
            pair_address TEXT NOT NULL,
            evidence_captured_at TEXT NOT NULL
        );
        CREATE TABLE printer_safety_evidence_contributions (
            id INTEGER PRIMARY KEY,
            composite_id INTEGER NOT NULL,
            captured_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        """INSERT INTO printer_memory_windows
           (id,token_id,pair_id,window_kind,snapshot_end_id,window_end_at,
            supporting_context_json)
           VALUES (1,39,43,?,?,?,?)""",
        (
            window_kind,
            memory_snapshot_id,
            "2026-08-22T13:00:00+00:00",
            json.dumps(
                {
                    "continuity": {"continuity_status": "CONTINUITY_CONTINUOUS"},
                    "memory_build_evidence_overlays": {"existing_overlay": "preserve"},
                    "other_context": "preserve",
                },
                sort_keys=True,
            ),
        ),
    )
    conn.execute(
        """INSERT INTO printer_safety_evidence_composites
           (id,token_id,pair_id,snapshot_id,token_mint,pair_address,
            evidence_captured_at)
           VALUES (7,?,?,?,?,?,?)""",
        (
            composite_token_id,
            composite_pair_id,
            composite_snapshot_id,
            "E9jov4Pnr2F518gmcb5Br2U6fQFbMP92h3FxZSMzpump",
            "FSfTzEkr8gDvPuv7JBvH7Zj7Saw2ZTMN7AMtSYf2SJs4",
            composite_captured_at,
        ),
    )
    conn.execute(
        """INSERT INTO printer_safety_evidence_contributions(
               composite_id,captured_at) VALUES (7,?)""",
        (contribution_captured_at,),
    )
    return conn


STEP = {
    "token_id": 39,
    "pair_id": 43,
    "token_mint": "E9jov4Pnr2F518gmcb5Br2U6fQFbMP92h3FxZSMzpump",
    "pair_address": "FSfTzEkr8gDvPuv7JBvH7Zj7Saw2ZTMN7AMtSYf2SJs4",
}
PERSISTED = {"safety_composite": {"composite_id": 7}}


class FirstHourSafetyRepairProof(unittest.TestCase):
    def test_transport_reservation_and_standard_campaign_budgets(self) -> None:
        self.assertEqual(FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT, 4)
        self.assertEqual(
            LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND["CONTINUATION_CLOSE"], 5
        )
        expected = {
            ("TRACK_FAST", "TRACK_FAST"): (238, 222),
            ("TRACK_FAST", "TRACK_NORMAL"): (190, 174),
            ("TRACK_NORMAL", "TRACK_NORMAL"): (142, 126),
        }
        for lanes, (request_ceiling, scheduler_ceiling) in expected.items():
            with self.subTest(lanes=lanes):
                budget = standard_campaign_lifecycle_budget(lanes, (True, True))
                self.assertEqual(budget["request_ceiling"], request_ceiling)
                self.assertEqual(budget["scheduler_ceiling"], scheduler_ceiling)
                self.assertEqual(
                    budget["request_components"]["token_1_window_1h_safety_context"],
                    4,
                )
                self.assertEqual(
                    budget["request_components"]["token_2_window_1h_safety_context"],
                    4,
                )

        no_4h = standard_campaign_lifecycle_budget(
            ("TRACK_FAST", "TRACK_FAST"), (False, False)
        )
        self.assertEqual(no_4h["request_ceiling"], 100)
        self.assertEqual(no_4h["scheduler_ceiling"], 94)
        self.assertNotIn("token_1_window_4h_phase", no_4h["request_components"])
        self.assertNotIn("token_2_window_4h_phase", no_4h["request_components"])

    def test_exact_fresh_safety_composite_binding_preserves_context(self) -> None:
        conn = _binding_db()
        try:
            report = attach_first_hour_safety_overlay(
                conn,
                step=STEP,
                memory_window_id=1,
                closing_snapshot_id=900,
                persisted_context=PERSISTED,
            )
            self.assertTrue(report["bound"])
            self.assertEqual(report["safety_composite_id"], 7)
            row = conn.execute(
                "SELECT supporting_context_json FROM printer_memory_windows WHERE id=1"
            ).fetchone()
            context = json.loads(str(row[0]))
            self.assertEqual(context["other_context"], "preserve")
            self.assertEqual(
                context["memory_build_evidence_overlays"]["existing_overlay"],
                "preserve",
            )
            self.assertEqual(
                context["memory_build_evidence_overlays"]["safety_composite_id"], 7
            )
        finally:
            conn.close()

    def test_first_hour_binding_fails_closed_on_identity_mismatch(self) -> None:
        cases = (
            ("wrong_window_kind", {"window_kind": "WINDOW_15M"}),
            ("wrong_memory_snapshot", {"memory_snapshot_id": 899}),
            ("wrong_composite_snapshot", {"composite_snapshot_id": 899}),
            ("wrong_composite_token", {"composite_token_id": 40}),
            ("wrong_composite_pair", {"composite_pair_id": 44}),
        )
        for label, kwargs in cases:
            with self.subTest(label=label):
                conn = _binding_db(**kwargs)
                try:
                    with self.assertRaises(FirstHourSafetyBindingError):
                        attach_first_hour_safety_overlay(
                            conn,
                            step=STEP,
                            memory_window_id=1,
                            closing_snapshot_id=900,
                            persisted_context=PERSISTED,
                        )
                finally:
                    conn.close()

    def test_first_hour_binding_rejects_safety_after_logical_end(self) -> None:
        end = datetime(2026, 8, 22, 13, 0, tzinfo=timezone.utc)
        for label, kwargs in (
            (
                "late_composite",
                {"composite_captured_at": (end + timedelta(seconds=1)).isoformat()},
            ),
            (
                "late_contribution",
                {"contribution_captured_at": (end + timedelta(seconds=1)).isoformat()},
            ),
        ):
            with self.subTest(label=label):
                conn = _binding_db(**kwargs)
                try:
                    with self.assertRaisesRegex(
                        FirstHourSafetyBindingError,
                        "FIRST_HOUR_SAFETY_LOGICAL_CUTOFF_EXCEEDED",
                    ):
                        attach_first_hour_safety_overlay(
                            conn,
                            step=STEP,
                            memory_window_id=1,
                            closing_snapshot_id=900,
                            persisted_context=PERSISTED,
                        )
                finally:
                    conn.close()

    def test_factory_source_orders_fresh_safety_before_audit_and_4h_barrier(self) -> None:
        source = FACTORY.read_text(encoding="utf-8")
        start = source.index("def _execute_continuation_close(")
        end = source.index("\ndef _derive_and_persist_four_hour_outcome(", start)
        region = source[start:end]
        self.assertIn('include=frozenset({"safety"})', region)
        collect = region.index("_collect_preclose_context(")
        snapshot = region.index("_execute_snapshot(")
        persist = region.index("_persist_preclose_context(")
        close = region.index("close_1h_memory_window_from_snapshot(")
        bind = region.index("attach_first_hour_safety_overlay(")
        outcome = region.index("_derive_and_persist_first_hour_outcome(")
        audit = region.index("audit_15m_memory_window(")
        self.assertLess(collect, snapshot)
        self.assertLess(snapshot, persist)
        self.assertLess(persist, close)
        self.assertLess(close, bind)
        self.assertLess(bind, outcome)
        self.assertLess(outcome, audit)
        self.assertIn(
            "context_adapter_factories=context_adapter_factories,\n"
            "                        fallback_adapter_factory=fallback_factory,",
            source,
        )

    def test_reservation_families_and_outer_ceiling_are_explicit(self) -> None:
        source = FACTORY.read_text(encoding="utf-8")
        start = source.index("def _lifecycle_reservation_records_for_step(")
        end = source.index("\ndef _observe_scheduler_terminal(", start)
        region = source[start:end]
        self.assertIn('"CONTINUATION_CLOSE_OBSERVATION"', region)
        self.assertIn('else "FIRST_HOUR_SAFETY_CONTEXT"', region)
        # V2-9.8B second standard-four-hour public budget authority repair: the
        # outer ceilings are now derived from the canonical lifecycle arithmetic
        # instead of being independently maintained literals, so assert the
        # derived values themselves rather than the source text.
        standard = STANDARD_4H.read_text(encoding="utf-8")
        self.assertNotIn("LIFECYCLE_REQUEST_OUTER_CEILING = 238", standard)
        self.assertIn("standard_four_hour_capacity_contract", standard)
        self.assertEqual(standard_4h.LIFECYCLE_REQUEST_OUTER_CEILING, 238)
        self.assertEqual(standard_4h.LIFECYCLE_SCHEDULER_OUTER_CEILING, 222)
        self.assertEqual(
            standard_4h.LIFECYCLE_REQUEST_OUTER_CEILING,
            standard_campaign_lifecycle_budget(
                ("TRACK_FAST", "TRACK_FAST"), (True, True)
            )["request_ceiling"],
        )


if __name__ == "__main__":
    unittest.main()
