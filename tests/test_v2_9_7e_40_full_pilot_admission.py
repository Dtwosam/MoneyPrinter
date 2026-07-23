"""V2-9.7E.40 full-pilot admission and candidate-supply repair proof.

Fixture-only. Proves that the canonical FULL_PILOT path (``run_operational``)
now applies the frozen 900-second categorical maturity boundary and a
fail-closed two-mature-candidate admission gate BEFORE any holder, snapshot,
lifecycle or memory work, and that immature (newest, too-young) creates are
staged into the durable prospective-origin registry instead of becoming the
active selection pool. No provider is contacted: ``pump_transport`` is a
transport-shaped fake and ``secondary_transport`` is ``None``.
"""

from __future__ import annotations

from datetime import datetime
import sqlite3
import unittest

from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.sources.pumpfun_origin import load_due_staged_origins

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
from test_v2_9_7e_11_authoritative_live_operational_campaign import _FakePumpTransport
from test_v2_9_7e_5_pump_origin_acquisition_architecture import (
    create_transaction,
    signature_row,
)


GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

NOW_EPOCH = int(datetime.fromisoformat(e8.NOW).timestamp())
YOUNG_BT = NOW_EPOCH - 60      # 60s old  -> IMMATURE (< 900s)
DUE_BT = NOW_EPOCH - 1_000     # 1000s old -> DUE (>= 900s)


def _transport(specs):
    """specs: list of (block_time, mint_label). Returns a fake pump transport."""
    txs = {}
    rows = []
    mints = []
    for i, (block_time, label) in enumerate(specs):
        sig = f"e40Sig{i}"
        slot = 900 + i
        tx, mint = create_transaction(sig, slot, block_time, mint_label=label)
        txs[sig] = tx
        rows.append(signature_row(sig, slot))
        mints.append(mint)
    return _FakePumpTransport(list(reversed(rows)), txs), mints


class FullPilotAdmissionProofTests(e8._IntegrationBase):
    def _run(self, transport):
        owner = AuthoritativeLiveOperationalCampaignOwner()
        return owner.run_operational(
            command=self.command,
            pump_transport=transport,
            secondary_transport=None,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e40-admission-seed",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
            backup_path=self.backup,
            lifecycle_kwargs={},
        )

    def _forbidden_and_lifecycle_counts(self):
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            def count(sql):
                return int(connection.execute(sql).fetchone()[0])
            return {
                "run_steps": count(
                    "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
                ),
                "memory_windows": count(
                    "SELECT COUNT(*) FROM printer_memory_windows"
                ),
                "episodes": count("SELECT COUNT(*) FROM printer_episodes"),
                "decisions": count("SELECT COUNT(*) FROM printer_paper_decisions"),
                "positions": count("SELECT COUNT(*) FROM printer_paper_positions"),
                "window15m_jobs": count(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE job_name LIKE 'window15m:%'"
                ),
                "registry": count(
                    "SELECT COUNT(*) FROM "
                    "printer_pumpfun_finalized_origin_registry"
                ),
            }
        finally:
            connection.close()

    # -- two immature candidates: fail closed before any lifecycle -----------

    def test_two_young_candidates_block_before_lifecycle(self) -> None:
        transport, mints = _transport([(YOUNG_BT, "youngA"), (YOUNG_BT, "youngB")])
        result = self._run(transport)

        self.assertFalse(result.lifecycle_started)
        self.assertEqual(result.lifecycle["run_status"], "NOT_STARTED")
        self.assertEqual(
            result.lifecycle["stop_reason"], "BLOCKED_INSUFFICIENT_MATURE_POOL"
        )
        self.assertEqual(result.lifecycle["run_id"], "run")
        self.assertEqual(result.activation.activated_slots, ())
        self.assertIsNone(result.activation.selection_batch_id)

        admission = result.lifecycle["full_pilot_admission"]
        self.assertEqual(admission["threshold_seconds"], 900)
        self.assertEqual(admission["candidate_universe"], 2)
        self.assertEqual(admission["mature_candidate_count"], 0)
        self.assertEqual(admission["state_counts"]["IMMATURE"], 2)
        self.assertEqual(admission["state_counts"]["DUE"], 0)
        self.assertEqual(admission["channel_counts"]["LATEST_PUMPFUN"], 2)
        self.assertEqual(admission["channel_counts"]["STAGED_DUE_REGISTRY"], 0)
        # Age is the finalized create age, and pair age is an explicit unknown.
        for rec in admission["candidates"]:
            self.assertEqual(rec["state"], "IMMATURE")
            self.assertAlmostEqual(rec["observed_origin_age_seconds"], 60, delta=2)
            self.assertEqual(
                rec["pair_age_context"],
                "UNKNOWN_PAIR_AGE_NOT_FETCHED_AT_ADMISSION",
            )

        # No holder / snapshot / lifecycle / memory / financial work happened.
        counts = self._forbidden_and_lifecycle_counts()
        self.assertEqual(counts["run_steps"], 0)
        self.assertEqual(counts["memory_windows"], 0)
        self.assertEqual(counts["episodes"], 0)
        self.assertEqual(counts["decisions"], 0)
        self.assertEqual(counts["positions"], 0)
        self.assertEqual(counts["window15m_jobs"], 0)
        # Both confirmed origins were staged into the durable registry.
        self.assertEqual(counts["registry"], 2)

    # -- one mature + one immature: still fail closed, partition proven -------

    def test_single_mature_candidate_is_insufficient(self) -> None:
        transport, mints = _transport([(DUE_BT, "matureA"), (YOUNG_BT, "youngB")])
        result = self._run(transport)

        self.assertFalse(result.lifecycle_started)
        self.assertEqual(
            result.lifecycle["stop_reason"], "BLOCKED_INSUFFICIENT_MATURE_POOL"
        )
        admission = result.lifecycle["full_pilot_admission"]
        self.assertEqual(admission["candidate_universe"], 2)
        self.assertEqual(admission["mature_candidate_count"], 1)
        self.assertEqual(admission["state_counts"]["DUE"], 1)
        self.assertEqual(admission["state_counts"]["IMMATURE"], 1)
        self.assertEqual(self._forbidden_and_lifecycle_counts()["window15m_jobs"], 0)

    # -- staged registry reload is categorical and zero-source ---------------

    def test_staged_registry_reload_returns_only_due_origins(self) -> None:
        # Running with two immature creates stages both into the registry.
        transport, mints = _transport([(YOUNG_BT, "youngA"), (DUE_BT, "dueB")])
        self._run(transport)

        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        try:
            # Evaluated exactly at NOW: only the >= 900s origin is due.
            due = load_due_staged_origins(
                connection,
                evaluated_epoch=NOW_EPOCH,
                maturity_seconds=900,
                exclude_mints=(),
            )
            due_mints = {row["mint"] for row in due}
            self.assertIn(mints[1].lower(), {m.lower() for m in due_mints})
            self.assertNotIn(mints[0].lower(), {m.lower() for m in due_mints})

            # Excluding the current-cycle mint yields nothing (fresh cycle reuse).
            excluded = load_due_staged_origins(
                connection,
                evaluated_epoch=NOW_EPOCH,
                maturity_seconds=900,
                exclude_mints={m for m in due_mints},
            )
            self.assertEqual(excluded, [])

            # Far in the future, a previously immature origin becomes due too.
            all_due = load_due_staged_origins(
                connection,
                evaluated_epoch=NOW_EPOCH + 10_000,
                maturity_seconds=900,
                exclude_mints=(),
            )
            self.assertEqual(len(all_due), 2)
        finally:
            connection.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
