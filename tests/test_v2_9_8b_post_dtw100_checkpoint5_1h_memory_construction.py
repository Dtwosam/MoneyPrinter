"""Post-DTW100 Checkpoint 5: genuine first-hour memory construction."""

from __future__ import annotations

from datetime import timedelta
import json
import unittest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.e2z_clean_memory_creation import (
    E2Z_STATUS_BLOCKED,
    create_clean_memory_from_window,
)
from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline
from printer_v1.operator_cli.lane_q_15m_window_integrity_guard import (
    LANE_Q_GUARD_COMPLETED,
    guard_candidate_windows,
)
from tests.test_v2_9_8b_operational_selective_1h import (
    T0,
    T15,
    T1H,
    Selective1hFixture,
    _iso,
)


class Checkpoint5FirstHourMemoryConstructionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Selective1hFixture()
        with self.fx.connection:
            self.fx.connection.execute(
                "UPDATE printer_tokens SET token_status='TRACK_NORMAL' WHERE id IN (1,2)"
            )

    def tearDown(self) -> None:
        self.fx.close()

    def _insert_snapshot(self, snapshot_id: int, captured_at, price: float) -> None:
        self.fx.connection.execute(
            """INSERT INTO printer_token_snapshots(
                id,token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                source_status,data_quality_label,price_usd
            ) VALUES (?,1,1,?,'TRACK_NORMAL','TOKEN','COMPLETE','CLEAN_DATA',?)""",
            (snapshot_id, _iso(captured_at), price),
        )

    def _insert_step(
        self,
        *,
        step_id: int,
        step_key: str,
        step_kind: str,
        snapshot_id: int | None,
        status: str = "SUCCEEDED",
    ) -> None:
        self.fx.connection.execute(
            """INSERT INTO printer_memory_factory_run_steps(
                id,run_id,step_key,step_kind,step_status,token_id,pair_id,
                token_mint,pair_address,tracking_lane,snapshot_id,scheduled_for
            ) VALUES (?,'factory-run-1',?,?,?,1,1,'mint-1','pair-1',
                'TRACK_NORMAL',?,?)""",
            (
                step_id,
                step_key,
                step_kind,
                status,
                snapshot_id,
                _iso(T0 + timedelta(seconds=step_id)),
            ),
        )

    def _insert_genuine_1h_candidate(self, window_id: int = 401) -> int:
        """Create a cadence-complete 2700s physical 1h continuation candidate."""
        snapshot_ids: list[int] = []
        for index in range(13):
            snapshot_id = 12000 + index
            snapshot_ids.append(snapshot_id)
            # 13 points over 2700s => 12 gaps of 225s, inside NORMAL clean gap.
            captured_at = T15 + timedelta(seconds=225 * index)
            self._insert_snapshot(snapshot_id, captured_at, 100.0 + index)
        ctx = {
            "snapshot_id": snapshot_ids[-1],
            "snapshot_ids": snapshot_ids,
            "tracking_lane": "TRACK_NORMAL",
            "e2q_audited": True,
            "e2q_audited_by": "lane_e2q",
            "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
        }
        self.fx.connection.execute(
            """INSERT INTO printer_memory_windows(
                id,token_id,pair_id,window_kind,opened_at,closed_at,
                window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                memory_status,data_quality_label,window_status,
                memory_quality_label,outcome_label,do_not_train,supporting_context_json
            ) VALUES (?,1,1,'WINDOW_1H',?,?,?,?,?,?,'PARTIAL_MEMORY',
                'CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY','CONSOLIDATION',0,?)""",
            (
                window_id,
                _iso(T15),
                _iso(T1H),
                _iso(T15),
                _iso(T1H),
                snapshot_ids[0],
                snapshot_ids[-1],
                json.dumps(ctx),
            ),
        )
        self.fx.connection.commit()
        return window_id

    def test_full_first_hour_outcome_uses_predecessor_and_continuation_path(self) -> None:
        """A 15m pump then 1h return must not be classified from the 45m suffix only."""
        with self.fx.connection:
            self._insert_snapshot(11001, T0, 100.0)
            self._insert_snapshot(11002, T15, 145.0)
            self._insert_snapshot(11003, T15 + timedelta(minutes=20), 140.0)
            self._insert_snapshot(11004, T1H, 100.0)
            self._insert_step(
                step_id=7101, step_key="cp5-open", step_kind="SNAPSHOT", snapshot_id=11001
            )
            self._insert_step(
                step_id=7102, step_key="cp5-15m-close", step_kind="WINDOW_CLOSE", snapshot_id=11002
            )
            self._insert_step(
                step_id=7103,
                step_key="cp5-cont",
                step_kind="CONTINUATION_SNAPSHOT",
                snapshot_id=11003,
            )
            # The live close step is still RUNNING when outcome construction occurs;
            # its closing snapshot is supplied explicitly by the close owner.
            self._insert_step(
                step_id=7104,
                step_key="cp5-1h-close",
                step_kind="CONTINUATION_CLOSE",
                snapshot_id=None,
                status="RUNNING",
            )
            self.fx.connection.execute(
                """INSERT INTO printer_memory_windows(
                    id,token_id,pair_id,window_kind,opened_at,closed_at,
                    window_start_at,window_end_at,snapshot_start_id,snapshot_end_id,
                    memory_status,data_quality_label,window_status,
                    memory_quality_label,do_not_train,supporting_context_json
                ) VALUES (410,1,1,'WINDOW_1H',?,?,?,?,11002,11004,
                    'PARTIAL_MEMORY','CLEAN_DATA','WINDOW_CLOSED','PARTIAL_MEMORY',0,?)""",
                (
                    _iso(T15),
                    _iso(T1H),
                    _iso(T15),
                    _iso(T1H),
                    json.dumps({"snapshot_id": 11004, "tracking_lane": "TRACK_NORMAL"}),
                ),
            )

        result = factory._derive_and_persist_first_hour_outcome(
            self.fx.connection,
            run_id="factory-run-1",
            token_id=1,
            pair_id=1,
            window_id=410,
            current_close_snapshot_id=11004,
        )
        self.assertEqual(result["outcome_label"], "ROUND_TRIP")
        self.assertEqual(result["snapshot_ids"], [11001, 11002, 11003, 11004])
        row = self.fx.connection.execute(
            "SELECT outcome_label,supporting_context_json FROM printer_memory_windows WHERE id=410"
        ).fetchone()
        self.assertEqual(row[0], "ROUND_TRIP")
        ctx = json.loads(row[1])
        self.assertEqual(ctx["full_first_hour_outcome_snapshot_ids"], [11001, 11002, 11003, 11004])

    def test_lane_q_accepts_genuine_2700_second_window_1h(self) -> None:
        window_id = self._insert_genuine_1h_candidate(411)
        report = guard_candidate_windows(
            self.fx.db,
            [window_id],
            operator_approved=True,
            production_mode=True,
        )
        self.assertEqual(report["lane_q_guard_status"], LANE_Q_GUARD_COMPLETED)
        self.assertEqual(report["valid_window_ids"], [window_id])
        self.assertEqual(report["blocked_window_ids"], [])

    def test_explicit_lane_k_scope_can_promote_genuine_window_1h(self) -> None:
        window_id = self._insert_genuine_1h_candidate(412)
        result = run_e2z_pipeline(
            self.fx.db,
            operator_approved=True,
            production_mode=True,
            candidate_window_ids=[window_id],
        )
        self.assertEqual(result["requested_window_ids"], [window_id])
        self.assertEqual(result["lane_q_valid_window_ids"], [window_id])
        self.assertEqual(result["promoted_window_ids"], [window_id])
        episode = self.fx.connection.execute(
            """SELECT id,episode_kind,window_kind,memory_status,episode_outcome_label
               FROM printer_episodes WHERE memory_window_id=?""",
            (window_id,),
        ).fetchone()
        self.assertIsNotNone(episode)
        self.assertEqual(episode[1], "WINDOW_1H_CLEAN_MEMORY")
        self.assertEqual(episode[2], "WINDOW_1H")
        self.assertEqual(episode[3], "CLEAN_MEMORY")
        self.assertEqual(episode[4], "CONSOLIDATION")
        fingerprint_count = int(
            self.fx.connection.execute(
                "SELECT COUNT(*) FROM printer_memory_fingerprints WHERE episode_id=?",
                (int(episode[0]),),
            ).fetchone()[0]
        )
        self.assertEqual(fingerprint_count, 1)

        replay = run_e2z_pipeline(
            self.fx.db,
            operator_approved=True,
            production_mode=True,
            candidate_window_ids=[window_id],
        )
        self.assertEqual(replay["e2z_already_exists_count"], 1)
        self.assertEqual(
            int(
                self.fx.connection.execute(
                    "SELECT COUNT(*) FROM printer_episodes WHERE memory_window_id=?",
                    (window_id,),
                ).fetchone()[0]
            ),
            1,
        )

    def test_direct_window_1h_e2z_requires_exact_lane_q_proof(self) -> None:
        window_id = self._insert_genuine_1h_candidate(413)
        before_episodes = int(
            self.fx.connection.execute("SELECT COUNT(*) FROM printer_episodes").fetchone()[0]
        )
        before_fingerprints = int(
            self.fx.connection.execute("SELECT COUNT(*) FROM printer_memory_fingerprints").fetchone()[0]
        )
        blocked = create_clean_memory_from_window(
            self.fx.db,
            window_id,
            operator_approved=True,
            individual_promotion=True,
        )
        self.assertEqual(blocked["e2z_status"], E2Z_STATUS_BLOCKED)
        self.assertTrue(
            any("Lane Q" in str(reason) for reason in blocked.get("blocked_reasons", []))
        )
        self.assertEqual(
            int(self.fx.connection.execute("SELECT COUNT(*) FROM printer_episodes").fetchone()[0]),
            before_episodes,
        )
        self.assertEqual(
            int(
                self.fx.connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_fingerprints"
                ).fetchone()[0]
            ),
            before_fingerprints,
        )


if __name__ == "__main__":
    unittest.main()
