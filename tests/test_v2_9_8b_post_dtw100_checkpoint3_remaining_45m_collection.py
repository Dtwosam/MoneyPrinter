"""Post-DTW100 Checkpoint 3: truthful remaining-45m collection state."""

from __future__ import annotations

from datetime import datetime
import unittest

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.scheduler.scheduler import (
    LockResult,
    claim_due_job,
    complete_job,
    fail_job,
)
from printer_v1.sources.governed_execution import build_fixture_source_adapter
from tests.test_v2_9_8b_operational_selective_1h import NOW, Selective1hFixture


class Checkpoint3Remaining45mCollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Selective1hFixture()
        self.config = {
            "campaign_id": "campaign-1h",
            "campaign_run_id": "run-1h",
            "cycle_id": "cycle-1h",
            "configuration_id": "config-1h",
        }
        self.fx.prepare_eligible(token_id=1, window_id=501, outcome="CONSOLIDATION")
        self.fx.prepare_eligible(token_id=2, window_id=502, outcome="NO_PUMP")
        with self.fx.connection:
            for token_id in (1, 2):
                self.fx.connection.execute(
                    """UPDATE printer_memory_factory_run_steps
                       SET snapshot_id=?
                       WHERE run_id='factory-run-1' AND token_id=?
                         AND step_kind='WINDOW_CLOSE'""",
                    (5000 + token_id, token_id),
                )
        self.initialized = factory._run_selective_1h_campaign_barrier(
            self.fx.connection,
            db_path=str(self.fx.db),
            run_id="factory-run-1",
            config=self.config,
            continuation_seconds=2700.0,
        )

    def tearDown(self) -> None:
        self.fx.close()

    def _first_snapshot_step(self, token_id: int):
        return self.fx.connection.execute(
            """SELECT * FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND token_id=?
                 AND step_kind='CONTINUATION_SNAPSHOT'
               ORDER BY scheduled_for,id LIMIT 1""",
            (token_id,),
        ).fetchone()

    def _work_state(self, job_id: int) -> str:
        row = self.fx.connection.execute(
            """SELECT work_state
               FROM printer_memory_factory_campaign_scheduler_work
               WHERE scheduler_job_id=?""",
            (job_id,),
        ).fetchone()
        self.assertIsNotNone(row)
        return str(row[0])

    def _window_state(self, token_id: int) -> str:
        row = self.fx.connection.execute(
            """SELECT window_state
               FROM printer_memory_factory_campaign_windows
               WHERE token_row_id=? AND window_kind='WINDOW_1H'""",
            (token_id,),
        ).fetchone()
        self.assertIsNotNone(row)
        return str(row[0])

    def test_claim_success_and_exact_pair_snapshot_keep_owned_state_truthful(self) -> None:
        step = self._first_snapshot_step(1)
        self.assertIsNotNone(step)
        job_id = int(step["scheduler_job_id"])
        self.assertEqual(self._work_state(job_id), "PENDING")
        self.assertEqual(self._window_state(1), "PLANNED")

        claim = claim_due_job(
            self.fx.connection,
            job_id=job_id,
            lock_owner="checkpoint3-test",
            now=datetime.fromisoformat(NOW),
        )
        self.assertEqual(claim, LockResult.ACQUIRED)
        factory._update_step(
            self.fx.connection,
            int(step["id"]),
            "RUNNING",
            {},
        )
        # Before the Checkpoint-3 repair the campaign projection still says
        # PENDING here.  The approved helper must synchronize from Scheduler truth.
        self.assertEqual(self._work_state(job_id), "PENDING")
        factory._sync_owned_campaign_scheduler_job(
            self.fx.connection,
            scheduler_job_id=job_id,
        )
        factory._mark_owned_continuation_window_collecting(
            self.fx.connection,
            scheduler_job_id=job_id,
            step_kind="CONTINUATION_SNAPSHOT",
        )
        self.assertEqual(self._work_state(job_id), "RUNNING")
        self.assertEqual(self._window_state(1), "COLLECTING")

        pair = str(step["pair_address"])
        mint = str(step["token_mint"])

        def adapter_factory(*, token_mint, timeout_seconds):
            self.assertEqual(token_mint, mint)
            return build_fixture_source_adapter(
                "dexscreener",
                fixture_payload={
                    "pairs": [{
                        "chain": "solana",
                        "token_mint": mint,
                        "pair_address": pair,
                        "price_usd": 1.25,
                        "liquidity_usd": 15000.0,
                        "volume_5m": 500.0,
                        "volume_1h": 2000.0,
                        "volume_24h": 10000.0,
                        "txns_5m": 10,
                        "txns_1h": 50,
                        "txns_24h": 500,
                        "price_change_5m": 1.0,
                        "price_change_1h": 2.0,
                        "price_change_24h": 3.0,
                    }]
                },
            )

        executed = factory._execute_snapshot(
            self.fx.connection,
            step,
            adapter_factory=adapter_factory,
            timeout_seconds=1.0,
            fallback_adapter_factory=None,
        )
        snapshot_id = int(executed["snapshot_id"])
        snapshot = self.fx.connection.execute(
            "SELECT token_id,pair_id FROM printer_token_snapshots WHERE id=?",
            (snapshot_id,),
        ).fetchone()
        self.assertEqual((int(snapshot[0]), int(snapshot[1])), (1, 1))
        request_count = int(self.fx.connection.execute(
            "SELECT COUNT(*) FROM printer_source_requests"
        ).fetchone()[0])
        response_count = int(self.fx.connection.execute(
            "SELECT COUNT(*) FROM printer_source_responses"
        ).fetchone()[0])
        self.assertGreaterEqual(request_count, 1)
        self.assertGreaterEqual(response_count, 1)

        factory._update_step(
            self.fx.connection,
            int(step["id"]),
            "SUCCEEDED",
            {"snapshot_id": snapshot_id},
        )
        complete_job(
            self.fx.connection,
            job_id=job_id,
            now=datetime.fromisoformat(NOW),
        )
        factory._sync_owned_campaign_scheduler_job(
            self.fx.connection,
            scheduler_job_id=job_id,
        )
        self.assertEqual(self._work_state(job_id), "SUCCEEDED")
        self.assertEqual(self._window_state(1), "COLLECTING")

    def test_failed_token_cancels_only_its_owned_work_and_blocks_only_its_window(self) -> None:
        step = self._first_snapshot_step(1)
        job_id = int(step["scheduler_job_id"])
        self.assertEqual(
            claim_due_job(
                self.fx.connection,
                job_id=job_id,
                lock_owner="checkpoint3-failure",
                now=datetime.fromisoformat(NOW),
            ),
            LockResult.ACQUIRED,
        )
        factory._update_step(
            self.fx.connection,
            int(step["id"]),
            "RUNNING",
            {},
        )
        factory._sync_owned_campaign_scheduler_job(
            self.fx.connection,
            scheduler_job_id=job_id,
        )
        factory._mark_owned_continuation_window_collecting(
            self.fx.connection,
            scheduler_job_id=job_id,
            step_kind="CONTINUATION_SNAPSHOT",
        )

        fail_job(
            self.fx.connection,
            job_id=job_id,
            error="checkpoint3_fixture_failure",
            now=datetime.fromisoformat(NOW),
            max_retries=0,
        )
        factory._update_step(
            self.fx.connection,
            int(step["id"]),
            "FAILED",
            {},
            error="checkpoint3_fixture_failure",
        )
        factory._sync_owned_campaign_scheduler_job(
            self.fx.connection,
            scheduler_job_id=job_id,
        )
        factory._cancel_pending_for_token(
            self.fx.connection,
            "factory-run-1",
            1,
            "checkpoint3_fixture_failure",
        )
        factory._terminalize_owned_continuation_window(
            self.fx.connection,
            scheduler_job_id=job_id,
            terminal_state="BLOCKED",
            terminal_cause="checkpoint3_fixture_failure",
        )

        self.assertEqual(self._work_state(job_id), "FAILED")
        self.assertEqual(self._window_state(1), "BLOCKED")
        self.assertEqual(self._window_state(2), "PLANNED")

        token1_states = {
            str(row[0])
            for row in self.fx.connection.execute(
                """SELECT w.work_state
                   FROM printer_memory_factory_campaign_scheduler_work AS w
                   JOIN printer_memory_factory_run_steps AS s
                     ON s.scheduler_job_id=w.scheduler_job_id
                   WHERE s.run_id='factory-run-1' AND s.token_id=1
                     AND s.step_kind IN ('CONTINUATION_SNAPSHOT','CONTINUATION_CLOSE')"""
            ).fetchall()
        }
        self.assertTrue(token1_states.issubset({"FAILED", "CANCELLED"}), token1_states)
        token2_active = int(self.fx.connection.execute(
            """SELECT COUNT(*)
               FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND token_id=2
                 AND step_kind IN ('CONTINUATION_SNAPSHOT','CONTINUATION_CLOSE')
                 AND step_status='PENDING'"""
        ).fetchone()[0])
        self.assertEqual(token2_active, 13)

    def test_continuation_steps_reuse_lifecycle_reservation_accounting(self) -> None:
        step = self._first_snapshot_step(1)
        reservations = factory._lifecycle_reservation_records_for_step(
            run_id="factory-run-1",
            pending=step,
            projected_requests=factory._projected_requests_for_step(step),
        )
        self.assertEqual(len(reservations), 1)
        self.assertEqual(reservations[0]["boundary"], "LIFECYCLE_RESERVATION")
        self.assertEqual(
            reservations[0]["operation_family"],
            "CONTINUATION_SNAPSHOT_OBSERVATION",
        )
        close = self.fx.connection.execute(
            """SELECT * FROM printer_memory_factory_run_steps
               WHERE run_id='factory-run-1' AND token_id=1
                 AND step_kind='CONTINUATION_CLOSE'
               ORDER BY id LIMIT 1""",
        ).fetchone()
        close_reservations = factory._lifecycle_reservation_records_for_step(
            run_id="factory-run-1",
            pending=close,
            projected_requests=factory._projected_requests_for_step(close),
        )
        self.assertEqual(len(close_reservations), 1)
        self.assertEqual(
            close_reservations[0]["operation_family"],
            "CONTINUATION_CLOSE_OBSERVATION",
        )


if __name__ == "__main__":
    unittest.main()
