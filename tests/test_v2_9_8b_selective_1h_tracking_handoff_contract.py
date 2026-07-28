"""Offline contract proofs for the selective-1h tracking handoff repair."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.lifecycle.contracts import (
    LifecycleEvent,
    QueueStatus,
    TokenLifecycleState,
)
from printer_v1.lifecycle.tracking_queue import (
    HANDOFF_ACTIVE_CONFLICT,
    HANDOFF_COOLDOWN_REOPEN_REQUIRED,
    HANDOFF_TERMINAL_REOPEN_REQUIRED,
    assess_tracking_handoff,
    assess_tracking_handoff_by_identity,
    enqueue_tracking_item,
)
from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import reopen_token
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.holder_reliability_budget_control import build_ledger


NOW = datetime(2026, 7, 28, 18, 0, tzinfo=timezone.utc)


class SelectiveOneHourTrackingHandoffContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "handoff.sqlite3"
        apply_migrations(self.db)
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.token_id = self._token("mint-a")
        self.pair_id = self._pair(self.token_id, "pair-a")

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    def _token(self, mint: str) -> int:
        return int(self.connection.execute(
            "INSERT INTO printer_tokens(token_mint,token_status) VALUES (?, 'TRACK_NORMAL')",
            (mint,),
        ).lastrowid)

    def _pair(self, token_id: int, pair: str) -> int:
        return int(self.connection.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) "
            "SELECT ?,?,token_mint FROM printer_tokens WHERE id=?",
            (token_id, pair, token_id),
        ).lastrowid)

    def _row(self, status: QueueStatus, *, pair_id: int | None = None) -> int:
        return int(self.connection.execute(
            """
            INSERT INTO printer_tracking_queue(
                token_id,pair_id,tracking_lane,tracking_action,priority_reason,
                next_check_at,queue_status,source_status,data_quality_label
            ) VALUES (?,?,'TRACK_NORMAL','PROMOTE_TO_TRACK_NORMAL','fixture',
                      ? ,?,'COMPLETE','CLEAN_DATA')
            """,
            (
                self.token_id,
                self.pair_id if pair_id is None else pair_id,
                NOW.isoformat(),
                status.value,
            ),
        ).lastrowid)

    def _enqueue(self, *, pair_id: int | None = None) -> tuple[bool, int | None]:
        return enqueue_tracking_item(
            self.connection,
            token_id=self.token_id,
            pair_id=self.pair_id if pair_id is None else pair_id,
            tracking_lane=TokenLifecycleState.TRACK_NORMAL,
            tracking_action=LifecycleEvent.PROMOTE_TO_TRACK_NORMAL,
            priority_reason="selective_1h_handoff",
            next_check_at=NOW,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
        )

    def test_fresh_identity_creates_exactly_one_queue_row(self) -> None:
        self.assertEqual(self._enqueue()[0], True)
        self.assertEqual(self._enqueue(), (False, None))
        count = self.connection.execute(
            "SELECT COUNT(*) FROM printer_tracking_queue"
        ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_live_ownership_states_are_active_conflicts(self) -> None:
        for status in (QueueStatus.QUEUED, QueueStatus.ACTIVE, QueueStatus.PAUSED):
            with self.subTest(status=status.value):
                self.connection.execute("DELETE FROM printer_tracking_queue")
                row_id = self._row(status)
                assessment = assess_tracking_handoff(
                    self.connection,
                    token_id=self.token_id,
                    pair_id=self.pair_id,
                    tracking_lane=TokenLifecycleState.TRACK_NORMAL,
                )
                self.assertFalse(assessment.eligible)
                self.assertEqual(assessment.reason_code, HANDOFF_ACTIVE_CONFLICT)
                self.assertEqual(assessment.queue_id, row_id)
                self.assertEqual(self._enqueue(), (False, None))

    def test_cooldown_requires_canonical_reopen(self) -> None:
        self._row(QueueStatus.COOLDOWN)
        assessment = assess_tracking_handoff_by_identity(
            self.connection,
            token_mint="mint-a",
            pair_address="pair-a",
            tracking_lane=TokenLifecycleState.TRACK_NORMAL,
        )
        self.assertEqual(
            assessment.reason_code, HANDOFF_COOLDOWN_REOPEN_REQUIRED
        )
        self.assertEqual(self._enqueue(), (False, None))

    def test_terminal_states_require_an_approved_reopen(self) -> None:
        for status in (QueueStatus.SKIPPED, QueueStatus.ARCHIVED):
            with self.subTest(status=status.value):
                self.connection.execute("DELETE FROM printer_tracking_queue")
                self._row(status)
                assessment = assess_tracking_handoff(
                    self.connection,
                    token_id=self.token_id,
                    pair_id=self.pair_id,
                    tracking_lane=TokenLifecycleState.TRACK_NORMAL,
                )
                self.assertEqual(
                    assessment.reason_code, HANDOFF_TERMINAL_REOPEN_REQUIRED
                )
                self.assertEqual(self._enqueue(), (False, None))

    def test_same_mint_new_pair_is_a_distinct_handoff_identity(self) -> None:
        self._row(QueueStatus.ACTIVE)
        new_pair_id = self._pair(self.token_id, "pair-b")
        same_pair = assess_tracking_handoff_by_identity(
            self.connection,
            token_mint="mint-a",
            pair_address="pair-a",
            tracking_lane=TokenLifecycleState.TRACK_NORMAL,
        )
        new_pair = assess_tracking_handoff_by_identity(
            self.connection,
            token_mint="mint-a",
            pair_address="pair-b",
            tracking_lane=TokenLifecycleState.TRACK_NORMAL,
        )
        self.assertEqual(same_pair.reason_code, HANDOFF_ACTIVE_CONFLICT)
        self.assertTrue(new_pair.eligible)
        self.assertTrue(self._enqueue(pair_id=new_pair_id)[0])

    def test_committed_revival_owner_preserves_history_and_owns_reopen(self) -> None:
        self._row(QueueStatus.COOLDOWN)
        self.connection.commit()
        self.connection.close()
        reopened = reopen_token(self.db, "mint-a", "pair-a")
        self.assertEqual(reopened["lifecycle_event"], "REOPEN_REVIVED_TOKEN")
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        rows = self.connection.execute(
            "SELECT tracking_lane,queue_status FROM printer_tracking_queue ORDER BY id"
        ).fetchall()
        self.assertEqual(
            [(row["tracking_lane"], row["queue_status"]) for row in rows],
            [("TRACK_NORMAL", "COOLDOWN"), ("WATCH_ONLY", "QUEUED")],
        )
        live = assess_tracking_handoff(
            self.connection,
            token_id=self.token_id,
            pair_id=self.pair_id,
            tracking_lane=TokenLifecycleState.WATCH_ONLY,
        )
        self.assertEqual(live.reason_code, HANDOFF_ACTIVE_CONFLICT)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_tracking_queue "
                "WHERE queue_status IN ('QUEUED','ACTIVE','PAUSED')"
            ).fetchone()[0],
            1,
        )

    def test_known_tracking_conflict_spends_no_holder_budget(self) -> None:
        self._row(QueueStatus.COOLDOWN)
        self.connection.commit()
        self.connection.execute("PRAGMA foreign_keys=OFF")
        evaluated = datetime(2026, 7, 28, 18, 0, tzinfo=timezone.utc)
        ledger = build_ledger(
            pump_operations=0,
            deadline_at=datetime(2026, 7, 28, 19, 0, tzinfo=timezone.utc),
        )
        proof = SimpleNamespace(
            mint="mint-a", bonding_curve="original-bonding-curve", block_time=0
        )
        owner = AuthoritativeLiveOperationalCampaignOwner()
        with patch(
            "printer_v1.operator_cli.one_command_15m_factory._collect_preclose_context"
        ) as collect:
            facts, returned_ledger = owner._evaluate_holder_eligibility(
                self.connection,
                command=SimpleNamespace(run_id="run-test"),
                cycle_id="cycle-test",
                bounded_candidates=(proof,),
                evaluated=evaluated,
                deadline=datetime(2026, 7, 28, 19, 0, tzinfo=timezone.utc),
                ledger=ledger,
                timeout_seconds=1.0,
                context_factories=None,
                request_pacer=None,
                tracking_pair_by_mint={"mint-a": "pair-a"},
            )
        collect.assert_not_called()
        self.assertIs(returned_ledger, ledger)
        self.assertEqual(
            facts["mint-a"]["reason"], HANDOFF_COOLDOWN_REOPEN_REQUIRED
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_holder_maturation_work"
            ).fetchone()[0],
            0,
        )


if __name__ == "__main__":
    unittest.main()
