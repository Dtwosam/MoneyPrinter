"""V2-9.7E.40 discovery-only persistent candidate pool proof.

Fixture-only. Proves that confirmed origins can be staged into the durable
registry pool, categorically mature over time, and be exported and copied into a
fresh isolated attempt DB as DUE candidates — with no source call, no duplicate
selection boost, and no lifecycle/memory/campaign state.
"""

from __future__ import annotations

from datetime import datetime
import sqlite3
import tempfile
import unittest
from pathlib import Path

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    LivePumpOriginAdapter,
)
from printer_v1.operator_cli.persistent_candidate_pool import (
    pool_maturity_state,
    record_acquisition_into_pool,
    seed_attempt_from_pool,
)
from printer_v1.sources.pumpfun_origin import load_due_staged_origins

from test_v2_9_7e_11_authoritative_live_operational_campaign import _FakePumpTransport
from test_v2_9_7e_5_pump_origin_acquisition_architecture import (
    create_transaction,
    signature_row,
)

GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

BASE_BT = 1_700_000_000  # fixed fixture create epoch


def _acquire(specs):
    """specs: [(block_time, label), ...] -> a LivePumpAcquisition."""
    txs = {}
    rows = []
    for i, (block_time, label) in enumerate(specs):
        sig = f"poolSig{i}"
        slot = 500 + i
        tx, _mint = create_transaction(sig, slot, block_time, mint_label=label)
        txs[sig] = tx
        rows.append(signature_row(sig, slot))
    transport = _FakePumpTransport(list(reversed(rows)), txs)
    return LivePumpOriginAdapter(transport).acquire(
        source_governor=GOV, central_scheduler=SCH
    )


class PersistentCandidatePoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.pool = str(root / "pool.sqlite3")
        self.attempt = str(root / "attempt.sqlite3")
        apply_migrations(self.pool)
        apply_migrations(self.attempt)

    def test_stage_mature_export_and_seed(self) -> None:
        acquisition = _acquire(
            [(BASE_BT, "poolA"), (BASE_BT + 30, "poolB"), (BASE_BT + 60, "poolC")]
        )
        staged = record_acquisition_into_pool(
            self.pool, acquisition, now="2026-07-23T00:00:00+00:00"
        )
        self.assertEqual(staged, 3)

        # Just after creation, nothing is due.
        just_after = datetime.fromtimestamp(BASE_BT + 100).astimezone().isoformat()
        state_early = pool_maturity_state(self.pool, evaluated_at=just_after)
        self.assertEqual(state_early["total"], 3)
        self.assertEqual(state_early["due"], 0)
        self.assertEqual(state_early["immature"], 3)

        # Well past the 900s boundary, all three are categorically due.
        far = datetime.fromtimestamp(BASE_BT + 10_000).astimezone().isoformat()
        state_due = pool_maturity_state(self.pool, evaluated_at=far)
        self.assertEqual(state_due["due"], 3)
        self.assertEqual(len(state_due["due_mints"]), 3)

        # Seed only DUE candidate facts into the fresh attempt DB.
        seeded = seed_attempt_from_pool(self.pool, self.attempt, evaluated_at=far)
        self.assertEqual(seeded["exported"], 3)
        self.assertEqual(seeded["copied"], 3)

        # The attempt registry now yields those origins as due, zero source.
        conn = sqlite3.connect(self.attempt)
        conn.row_factory = sqlite3.Row
        try:
            due = load_due_staged_origins(
                conn,
                evaluated_epoch=BASE_BT + 10_000,
                maturity_seconds=900,
                exclude_mints=(),
            )
            self.assertEqual(len(due), 3)
            # Origin registry only — no campaign/lifecycle/memory state was copied.
            for table in (
                "printer_memory_windows",
                "printer_memory_factory_runs",
                "printer_paper_decisions",
            ):
                self.assertEqual(
                    conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0
                )
        finally:
            conn.close()

    def test_seed_is_idempotent_and_categorical(self) -> None:
        acquisition = _acquire([(BASE_BT, "x"), (BASE_BT + 5, "y")])
        record_acquisition_into_pool(
            self.pool, acquisition, now="2026-07-23T00:00:00+00:00"
        )
        far = datetime.fromtimestamp(BASE_BT + 10_000).astimezone().isoformat()

        first = seed_attempt_from_pool(self.pool, self.attempt, evaluated_at=far)
        self.assertEqual(first["copied"], 2)
        # Re-seeding copies nothing new (duplicates never multiply the pool).
        second = seed_attempt_from_pool(self.pool, self.attempt, evaluated_at=far)
        self.assertEqual(second["exported"], 2)
        self.assertEqual(second["copied"], 0)

        # An excluded mint is not exported.
        excluded = seed_attempt_from_pool(
            self.pool,
            self.attempt,
            evaluated_at=far,
            exclude_mints={first["mints"][0]},
        )
        self.assertEqual(excluded["exported"], 1)

    def test_immature_pool_seeds_nothing(self) -> None:
        acquisition = _acquire([(BASE_BT, "young1"), (BASE_BT + 10, "young2")])
        record_acquisition_into_pool(
            self.pool, acquisition, now="2026-07-23T00:00:00+00:00"
        )
        # Evaluated only 100s after creation: nothing due, nothing seeded.
        near = datetime.fromtimestamp(BASE_BT + 100).astimezone().isoformat()
        state = pool_maturity_state(self.pool, evaluated_at=near)
        self.assertEqual(state["due"], 0)
        seeded = seed_attempt_from_pool(self.pool, self.attempt, evaluated_at=near)
        self.assertEqual(seeded["exported"], 0)
        self.assertEqual(seeded["copied"], 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
