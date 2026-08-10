"""Focused offline proof for post-DTW100 standard-first-hour harness/reporting alignment."""

from __future__ import annotations

from datetime import timedelta
import json
import unittest

from printer_v1.operator_cli.e2z_clean_memory_creation import (
    E2Z_STATUS_CREATED,
    E2Z_STATUS_ALREADY_EXISTS,
    create_clean_memory_from_window,
)
from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import (
    guard_candidate_windows,
)
from printer_v1.operator_cli.operational_selective_1h import (
    FIRST_HOUR_CONTINUATION_BLOCKED,
    ONE_CONTINUATION_ONE_BLOCK,
    TWO_CONTINUATIONS,
    EVALUATION_BLOCKED_SYSTEM_DEFECT,
    _classify_standard_first_hour_outcome,
)
from printer_v1.scheduler.token_local_continuation import ContinuationVerdict
from tests.test_v2_9_8b_operational_selective_1h import (
    Selective1hFixture,
    T0,
    T15,
    T1H,
    _iso,
)


class StandardFirstHourHarnessReportingAlignmentTests(unittest.TestCase):
    def test_reporting_classifies_continue_and_block_truthfully(self) -> None:
        self.assertEqual(
            _classify_standard_first_hour_outcome(
                decision_set_complete=True,
                persistence_consistent=True,
                continue_count=2,
                stop_count=0,
                block_count=0,
            ),
            TWO_CONTINUATIONS,
        )
        self.assertEqual(
            _classify_standard_first_hour_outcome(
                decision_set_complete=True,
                persistence_consistent=True,
                continue_count=1,
                stop_count=0,
                block_count=1,
            ),
            ONE_CONTINUATION_ONE_BLOCK,
        )
        self.assertEqual(
            _classify_standard_first_hour_outcome(
                decision_set_complete=True,
                persistence_consistent=True,
                continue_count=0,
                stop_count=0,
                block_count=2,
            ),
            FIRST_HOUR_CONTINUATION_BLOCKED,
        )
        self.assertEqual(
            _classify_standard_first_hour_outcome(
                decision_set_complete=True,
                persistence_consistent=True,
                continue_count=1,
                stop_count=1,
                block_count=0,
            ),
            EVALUATION_BLOCKED_SYSTEM_DEFECT,
        )
        self.assertEqual(
            _classify_standard_first_hour_outcome(
                decision_set_complete=True,
                persistence_consistent=False,
                continue_count=2,
                stop_count=0,
                block_count=0,
            ),
            EVALUATION_BLOCKED_SYSTEM_DEFECT,
        )

    def test_canonical_clean_objects_continue_quiet_tokens_to_1h(self) -> None:
        fx = Selective1hFixture()
        try:
            for token_id, window_id, outcome in (
                (1, 301, "CONSOLIDATION"),
                (2, 302, "NO_PUMP"),
            ):
                fx.prepare_eligible(
                    token_id=token_id,
                    window_id=window_id,
                    outcome=outcome,
                    promote=False,
                )
                promoted = create_clean_memory_from_window(
                    fx.db,
                    window_id,
                    operator_approved=True,
                    individual_promotion=True,
                )
                self.assertEqual(promoted["e2z_status"], E2Z_STATUS_CREATED)
                self.assertIsNotNone(promoted["episode_id"])
                self.assertIsNotNone(promoted["fingerprint_id"])
            result = fx.evaluate()
            self.assertEqual(result["continue_count"], 2)
            self.assertEqual(result["block_count"], 0)
            self.assertEqual(result["stop_count"], 0)
            self.assertTrue(all(plan["campaign_window_1h_id"] for plan in result["token_plans"]))
        finally:
            fx.close()

    def test_episode_only_predecessor_still_fails_closed(self) -> None:
        fx = Selective1hFixture()
        try:
            for token_id, window_id, outcome in (
                (1, 311, "DUMP"),
                (2, 312, "SLOW_BLEED"),
            ):
                fx.prepare_eligible(
                    token_id=token_id,
                    window_id=window_id,
                    outcome=outcome,
                    promote=False,
                )
                episode_id = fx.insert_episode(
                    window_id=window_id,
                    token_id=token_id,
                    pair_id=token_id,
                )
                fingerprint_count = fx.connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_fingerprints WHERE episode_id=?",
                    (episode_id,),
                ).fetchone()[0]
                self.assertEqual(int(fingerprint_count), 0)
            result = fx.evaluate()
            self.assertEqual(result["continue_count"], 0)
            self.assertEqual(result["block_count"], 2)
            self.assertTrue(
                all(
                    plan["verdict"] == ContinuationVerdict.BLOCK_CONTINUATION
                    for plan in result["token_plans"]
                )
            )
        finally:
            fx.close()

    def test_genuine_1h_clean_object_creates_episode_and_fingerprint_once(self) -> None:
        fx = Selective1hFixture()
        try:
            snapshot_ids = list(range(3301, 3314))
            with fx.connection:
                fx.connection.execute(
                    "UPDATE printer_tokens SET token_status='TRACK_NORMAL' WHERE id=1"
                )
                for index, snapshot_id in enumerate(snapshot_ids):
                    fx.connection.execute(
                        """INSERT INTO printer_token_snapshots(
                            id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                            source_status,data_quality_label
                        ) VALUES (?,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA')""",
                        (snapshot_id, _iso(T15 + timedelta(seconds=225 * index))),
                    )
                ctx = {
                    "snapshot_id": snapshot_ids[-1],
                    "snapshot_ids": snapshot_ids,
                    "e2q_audited": True,
                    "e2q_audited_by": "lane_e2q",
                    "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
                    "tracking_lane": "TRACK_NORMAL",
                }
                fx.connection.execute(
                    """INSERT INTO printer_memory_windows(
                        id,token_id,pair_id,window_kind,opened_at,closed_at,
                        window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                        memory_status,data_quality_label,window_status,
                        memory_quality_label,outcome_label,do_not_train,supporting_context_json
                    ) VALUES (3201,1,1,'WINDOW_1H',?,?,?,?,?,?,'PARTIAL_MEMORY',
                        'CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY','CONSOLIDATION',0,?)""",
                    (
                        _iso(T15),
                        _iso(T1H),
                        _iso(T15),
                        _iso(T1H),
                        snapshot_ids[0],
                        snapshot_ids[-1],
                        json.dumps(ctx),
                    ),
                )
            lane_q = guard_candidate_windows(
                fx.db,
                [3201],
                operator_approved=True,
                production_mode=True,
            )
            first = create_clean_memory_from_window(
                fx.db,
                3201,
                operator_approved=True,
                individual_promotion=True,
                lane_q_report=lane_q,
            )
            self.assertEqual(first["e2z_status"], E2Z_STATUS_CREATED)
            second = create_clean_memory_from_window(
                fx.db,
                3201,
                operator_approved=True,
                individual_promotion=True,
                lane_q_report=lane_q,
            )
            self.assertEqual(second["e2z_status"], E2Z_STATUS_ALREADY_EXISTS)
            self.assertEqual(first["episode_id"], second["episode_id"])
            self.assertEqual(first["fingerprint_id"], second["fingerprint_id"])
            row = fx.connection.execute(
                """SELECT e.episode_kind, f.fingerprint_kind
                   FROM printer_episodes AS e
                   JOIN printer_memory_fingerprints AS f ON f.episode_id=e.id
                   WHERE e.id=? AND f.id=?""",
                (first["episode_id"], first["fingerprint_id"]),
            ).fetchone()
            self.assertEqual(tuple(row), ("WINDOW_1H_CLEAN_MEMORY", "STATIC_CONDITION_SUMMARY"))
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
