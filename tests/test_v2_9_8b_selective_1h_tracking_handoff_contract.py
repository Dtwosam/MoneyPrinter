"""Offline contract proofs for the selective-1h tracking handoff repair."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
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
    HANDOFF_COOLDOWN_REQUALIFICATION_REQUIRED,
    HANDOFF_TERMINAL_REOPEN_REQUIRED,
    TRACKING_COOLDOWN_SECONDS,
    assess_tracking_handoff,
    assess_tracking_handoff_by_identity,
    claim_tracking_item,
    enqueue_tracking_item,
)
from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import reopen_token
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    _classify_pre_lifecycle_terminal,
)
from printer_v1.operator_cli.holder_reliability_budget_control import build_ledger
from printer_v1.operator_cli.cadence_authority import (
    CadenceAuthorityError,
    claim_tracking_authority_for_slot_insert,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    _frozen_pair_requalification_authority,
)
from printer_v1.operator_cli.pre_admission_discovery_attempt import (
    PreAdmissionAttemptError,
    PreAdmissionAttemptItem,
    attach_frozen_tracking_lane,
)


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

    def test_historical_cooldown_derives_expiry_and_requires_fresh_claim(self) -> None:
        row_id = self._row(QueueStatus.COOLDOWN)
        self.connection.execute(
            "UPDATE printer_tracking_queue SET next_check_at=?,last_checked_at=? WHERE id=?",
            (
                (NOW - timedelta(hours=1)).isoformat(),
                NOW.isoformat(),
                row_id,
            ),
        )
        before = assess_tracking_handoff(
            self.connection,
            token_id=self.token_id,
            pair_id=self.pair_id,
            tracking_lane=TokenLifecycleState.TRACK_NORMAL,
            assessed_at=NOW + timedelta(seconds=TRACKING_COOLDOWN_SECONDS - 1),
        )
        self.assertFalse(before.eligible)
        self.assertTrue(before.historical_cooldown_expiry_derived)
        expired_at = NOW + timedelta(seconds=TRACKING_COOLDOWN_SECONDS)
        expired = assess_tracking_handoff(
            self.connection,
            token_id=self.token_id,
            pair_id=self.pair_id,
            tracking_lane=TokenLifecycleState.TRACK_NORMAL,
            assessed_at=expired_at,
        )
        self.assertTrue(expired.eligible)
        self.assertTrue(expired.requalification_eligible)
        self.assertEqual(
            expired.category, HANDOFF_COOLDOWN_REQUALIFICATION_REQUIRED
        )
        # Expiry alone is never permission to reuse old evidence.
        refused = claim_tracking_item(
            self.connection,
            token_id=self.token_id,
            pair_id=self.pair_id,
            tracking_lane=TokenLifecycleState.TRACK_NORMAL,
            tracking_action=LifecycleEvent.PROMOTE_TO_TRACK_NORMAL,
            priority_reason="fixture",
            next_check_at=expired_at,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
            assessed_at=expired_at,
            fresh_evidence_requalification=False,
        )
        self.assertEqual(refused, (False, None))
        created, new_queue_id = claim_tracking_item(
            self.connection,
            token_id=self.token_id,
            pair_id=self.pair_id,
            tracking_lane=TokenLifecycleState.TRACK_NORMAL,
            tracking_action=LifecycleEvent.PROMOTE_TO_TRACK_NORMAL,
            priority_reason="fixture",
            next_check_at=expired_at,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
            assessed_at=expired_at,
            fresh_evidence_requalification=True,
            requalification_lineage={"run_id": "run-new"},
        )
        self.assertTrue(created)
        self.assertIsNotNone(new_queue_id)
        rows = self.connection.execute(
            "SELECT id,queue_status,tracking_action FROM printer_tracking_queue ORDER BY id"
        ).fetchall()
        self.assertEqual(
            [(row["queue_status"], row["tracking_action"]) for row in rows],
            [
                ("COOLDOWN", "PROMOTE_TO_TRACK_NORMAL"),
                ("QUEUED", "REOPEN_REVIVED_TOKEN"),
            ],
        )
        event = self.connection.execute(
            "SELECT event_payload_json FROM printer_token_lifecycle_events "
            "WHERE lifecycle_event='REOPEN_REVIVED_TOKEN'"
        ).fetchone()
        payload = json.loads(event[0])
        self.assertEqual(payload["predecessor_queue_id"], row_id)
        self.assertEqual(payload["new_tracking_queue_id"], new_queue_id)
        self.assertEqual(payload["run_id"], "run-new")
        self.assertTrue(payload["fresh_evidence_requalification"])
        # The new live owner prevents a duplicate decision/queue.
        duplicate = claim_tracking_item(
            self.connection,
            token_id=self.token_id,
            pair_id=self.pair_id,
            tracking_lane=TokenLifecycleState.TRACK_NORMAL,
            tracking_action=LifecycleEvent.PROMOTE_TO_TRACK_NORMAL,
            priority_reason="fixture",
            next_check_at=expired_at,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
            assessed_at=expired_at,
            fresh_evidence_requalification=True,
        )
        self.assertEqual(duplicate, (False, None))

    def test_slot_claim_wrapper_forwards_frozen_fresh_requalification(self) -> None:
        lineage = {
            "pre_admission_attempt_id": "attempt-2",
            "frozen_evidence_hash": "a" * 64,
        }
        with patch(
            "printer_v1.operator_cli.cadence_authority.claim_tracking_item",
            return_value=(True, 991),
        ) as claimed:
            queue_id = claim_tracking_authority_for_slot_insert(
                self.connection,
                token_row_id=self.token_id,
                pair_row_id=self.pair_id,
                tracking_lane="TRACK_NORMAL",
                now=NOW,
                priority_reason="later_cycle_slot_tracking_activation",
                fresh_evidence_requalification=True,
                requalification_lineage=lineage,
            )

        self.assertEqual(queue_id, 991)
        kwargs = claimed.call_args.kwargs
        self.assertEqual(kwargs["assessed_at"], NOW)
        self.assertTrue(kwargs["fresh_evidence_requalification"])
        self.assertEqual(kwargs["requalification_lineage"], lineage)

    def test_slot_claim_wrapper_requalifies_expired_cooldown_only_with_fresh_lineage(
        self,
    ) -> None:
        row_id = self._row(QueueStatus.COOLDOWN)
        self.connection.execute(
            "UPDATE printer_tracking_queue SET next_check_at=?,last_checked_at=? WHERE id=?",
            (
                (NOW - timedelta(hours=1)).isoformat(),
                NOW.isoformat(),
                row_id,
            ),
        )
        expired_at = NOW + timedelta(seconds=TRACKING_COOLDOWN_SECONDS)

        with self.assertRaisesRegex(
            CadenceAuthorityError,
            "TRACKING_QUEUE_CLAIM_FAILED",
        ):
            claim_tracking_authority_for_slot_insert(
                self.connection,
                token_row_id=self.token_id,
                pair_row_id=self.pair_id,
                tracking_lane="TRACK_NORMAL",
                now=expired_at,
                priority_reason="later_cycle_slot_tracking_activation",
            )
        self.connection.rollback()

        queue_id = claim_tracking_authority_for_slot_insert(
            self.connection,
            token_row_id=self.token_id,
            pair_row_id=self.pair_id,
            tracking_lane="TRACK_NORMAL",
            now=expired_at,
            priority_reason="later_cycle_slot_tracking_activation",
            fresh_evidence_requalification=True,
            requalification_lineage={
                "pre_admission_attempt_id": "attempt-2",
                "frozen_evidence_hash": "e" * 64,
            },
        )
        self.assertGreater(queue_id, row_id)
        row = self.connection.execute(
            "SELECT tracking_action,queue_status FROM printer_tracking_queue WHERE id=?",
            (queue_id,),
        ).fetchone()
        self.assertEqual(
            (row["tracking_action"], row["queue_status"]),
            ("REOPEN_REVIVED_TOKEN", "QUEUED"),
        )
        event = self.connection.execute(
            "SELECT event_payload_json FROM printer_token_lifecycle_events "
            "WHERE lifecycle_event='REOPEN_REVIVED_TOKEN' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        payload = json.loads(event[0])
        self.assertEqual(payload["pre_admission_attempt_id"], "attempt-2")
        self.assertEqual(payload["frozen_evidence_hash"], "e" * 64)
        self.assertTrue(payload["fresh_evidence_requalification"])

    def test_frozen_pair_requalification_requires_current_holder_authority(self) -> None:
        item = SimpleNamespace(
            canonical_evidence_json=json.dumps(
                {
                    "candidate": {"provenance": "PERSISTED_GRADUATED"},
                    "holder_evidence": {
                        "eligible": True,
                        "tracking_requalification_required": True,
                        "source_name": "goplus",
                        "reason": "CURRENT_HOLDER_EVIDENCE",
                    },
                },
                sort_keys=True,
            ),
            canonical_evidence_hash="b" * 64,
            observed_at=NOW,
        )
        allowed, lineage = _frozen_pair_requalification_authority(
            item,
            attempt_id="attempt-2",
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            cycle_id="cycle-1-2",
        )
        self.assertTrue(allowed)
        self.assertIsNotNone(lineage)
        self.assertEqual(lineage["pre_admission_attempt_id"], "attempt-2")
        self.assertEqual(lineage["frozen_evidence_hash"], "b" * 64)

        item_without_requalification = SimpleNamespace(
            canonical_evidence_json=json.dumps(
                {
                    "candidate": {},
                    "holder_evidence": {
                        "eligible": True,
                        "tracking_requalification_required": False,
                    },
                }
            ),
            canonical_evidence_hash="c" * 64,
            observed_at=NOW,
        )
        allowed, lineage = _frozen_pair_requalification_authority(
            item_without_requalification,
            attempt_id="attempt-3",
            campaign_id="campaign-1",
            campaign_run_id="campaign-run-1",
            cycle_id="cycle-1-2",
        )
        self.assertFalse(allowed)
        self.assertIsNone(lineage)

    def test_frozen_lane_checks_the_exact_classified_lane_claimability(self) -> None:
        item = PreAdmissionAttemptItem(
            attempt_id="attempt-2",
            slot_ordinal=1,
            token_identity="solana-mainnet:mint-a",
            token_row_id=self.token_id,
            mint_identity="mint-a",
            pair_identity="pair-a",
            pair_row_id=self.pair_id,
            lifecycle_identity="PUMPSWAP_GRADUATED_CONFIRMED",
            canonical_market_identity="pair-a",
            canonical_pool_identity="pair-a",
            canonical_evidence_json=json.dumps({"candidate": {}}),
            canonical_evidence_hash="d" * 64,
            evidence_version="test",
            observed_at=NOW,
            channel_labels=("PERSISTED_GRADUATED",),
        )
        classification = SimpleNamespace(
            discovery_action=SimpleNamespace(value="TRACK_FAST"),
            discovery_label=SimpleNamespace(value="ELIGIBLE"),
            reason="fixture",
        )
        with (
            patch(
                "printer_v1.operator_cli.pre_admission_discovery_attempt."
                "_linked_exact_market_candidate_evidence",
                return_value=None,
            ),
            patch(
                "printer_v1.operator_cli.pre_admission_discovery_attempt."
                "_reject_liquidity_evidence_time_before_proving_response",
                return_value=None,
            ),
            patch(
                "printer_v1.operator_cli.pre_admission_discovery_attempt."
                "project_classifier_candidate_from_pre_admission_evidence",
                return_value={"token_mint": "mint-a"},
            ),
            patch(
                "printer_v1.operator_cli.pre_admission_discovery_attempt."
                "classify_tracking_lane_from_candidate_evidence",
                return_value=("TRACK_FAST", classification),
            ),
            patch(
                "printer_v1.lifecycle.tracking_queue."
                "assess_possible_tracking_claim_by_identity",
                return_value=SimpleNamespace(eligible=False),
            ) as assessed,
        ):
            with self.assertRaisesRegex(
                PreAdmissionAttemptError,
                "FROZEN_TRACKING_LANE_UNCLAIMABLE",
            ):
                attach_frozen_tracking_lane(
                    item,
                    now=NOW,
                    connection=self.connection,
                )

        self.assertEqual(
            assessed.call_args.kwargs["tracking_lane"],
            "TRACK_FAST",
        )

    def test_future_cooldown_expiry_is_not_derived_or_reopened_early(self) -> None:
        row_id = self._row(QueueStatus.COOLDOWN)
        future = NOW + timedelta(hours=1)
        self.connection.execute(
            "UPDATE printer_tracking_queue SET next_check_at=?,last_checked_at=? WHERE id=?",
            (future.isoformat(), NOW.isoformat(), row_id),
        )
        assessment = assess_tracking_handoff(
            self.connection,
            token_id=self.token_id,
            pair_id=self.pair_id,
            tracking_lane=TokenLifecycleState.TRACK_NORMAL,
            assessed_at=NOW + timedelta(minutes=30),
        )
        self.assertFalse(assessment.eligible)
        self.assertFalse(assessment.historical_cooldown_expiry_derived)
        self.assertEqual(assessment.cooldown_until, future.isoformat())

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
        # Possible-claim is lane-agnostic: block BOTH claimable lanes so a
        # NORMAL-only conflict cannot be bypassed by a still-fresh FAST lane.
        self._row(QueueStatus.COOLDOWN)
        self.connection.execute(
            """
            INSERT INTO printer_tracking_queue(
                token_id,pair_id,tracking_lane,tracking_action,priority_reason,
                next_check_at,queue_status,source_status,data_quality_label
            ) VALUES (?,?,'TRACK_FAST','PROMOTE_TO_TRACK_FAST','fixture',
                      ? ,'COOLDOWN','COMPLETE','CLEAN_DATA')
            """,
            (self.token_id, self.pair_id, NOW.isoformat()),
        )
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
            holder_result = owner._evaluate_holder_eligibility(
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
        self.assertIs(holder_result.ledger, ledger)
        facts = holder_result.holder_facts
        self.assertEqual(
            facts["mint-a"]["reason"], HANDOFF_COOLDOWN_REOPEN_REQUIRED
        )
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM printer_holder_maturation_work"
            ).fetchone()[0],
            0,
        )

    def test_provider_failure_precedes_tracking_in_mixed_terminal(self) -> None:
        terminal = _classify_pre_lifecycle_terminal(
            {
                "mint-a": {
                    "eligible": False,
                    "reason": HANDOFF_COOLDOWN_REOPEN_REQUIRED,
                },
                "mint-b": {
                    "eligible": False,
                    "reason": "HOLDER_EVIDENCE_COLLECTION_FAILED:TimeoutError",
                },
            },
            reserve_count=2,
        )
        self.assertEqual(terminal, "PRE_LIFECYCLE_HOLDER_EVIDENCE_BLOCKED")


if __name__ == "__main__":
    unittest.main()
