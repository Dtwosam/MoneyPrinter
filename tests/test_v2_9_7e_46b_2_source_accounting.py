"""V2-9.7E.46B.2 stage-local source-accounting proof.

Fixtures + isolated temporary DBs only (no live network, no persistent-DB
mutation, no lifecycle/pilot/memory/readiness side effects).

E.46B.1 persisted campaign ``governed_requests = 22`` against ``21`` distinct
durable ``printer_source_requests`` rows. The proven cause was that the liquidity
front door reported a whole-table ``WHERE source_name='dexscreener'`` total, which
included the discovery fresh-profile locator; the campaign then added the
discovery total (which already contained that locator) to the front-door total and
charged the locator twice.

These tests pin the corrected contract: each governed request is charged exactly
once, and stage-local accounting is derived from the exact request identities the
stage created.
"""

from __future__ import annotations

import os
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from types import MappingProxyType

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery import graduated_liquidity_front_door as fd
from printer_v1.operator_cli.graduated_supply_front_door import (
    run_fresh_profile_locator,
)
from printer_v1.operator_cli.holder_reliability_budget_control import build_ledger
from printer_v1.sources.dexscreener import (
    fixture_rate_limited_transport,
    fixture_success_transport,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    record_graduated_candidate,
)

NOW = "2026-07-24T15:00:00+00:00"
SEED = "e46b2-accounting-seed"
DEADLINE = "2026-07-25T00:00:00+00:00"


def _mint(label: str) -> str:
    return (f"{label}Mint" + "1" * 44)[:44]


def _pool(label: str) -> str:
    return (f"{label}Pool" + "1" * 44)[:44]


def _pair_payload(pool: str, mint: str, liquidity: float):
    return {
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": pool,
                "baseToken": {"address": mint, "symbol": "MEME", "name": "Meme"},
                "priceUsd": "0.10",
                "liquidity": {"usd": liquidity},
                "volume": {"m5": 100.0, "h1": 1000.0, "h24": 10000.0},
                "txns": {"m5": {"buys": 3, "sells": 2}},
                "priceChange": {"m5": 1.0},
            }
        ]
    }


def _profiles_payload(*mints: str):
    return MappingProxyType(
        {
            "pairs": [
                {
                    "baseToken": {"address": m},
                    "pairAddress": _pool(m[:1]),
                    "chainId": "solana",
                }
                for m in mints
            ]
        }
    )


class _Base(unittest.TestCase):
    labels: tuple[str, ...] = ("A", "B", "C")

    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = pathlib.Path(self.temp.name) / "accounting.sqlite3"
        apply_migrations(self.db)
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            for index, label in enumerate(self.labels):
                record_graduated_candidate(
                    conn,
                    mint=_mint(label),
                    migration_signature=f"MigSig{label}" + "z" * 30,
                    pumpswap_pool=_pool(label),
                    graduation_block_time=1_700_000_000 + index,
                    graduation_slot=500 + index,
                    now=NOW,
                    discovery_channel=LATEST_GRADUATED_CHANNEL,
                )
        conn.close()

    def tearDown(self) -> None:
        self.temp.cleanup()

    # -- helpers ---------------------------------------------------------- #

    def _durable_requests(self) -> list[sqlite3.Row]:
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(
                "SELECT id, source_name, request_kind, request_key "
                "FROM printer_source_requests ORDER BY id"
            ).fetchall()
        finally:
            conn.close()

    def _run_locator(self, key: str = "camp-supply-locator"):
        return run_fresh_profile_locator(
            self.db,
            transport=lambda _c: _profiles_payload(*(_mint(x) for x in self.labels)),
            request_key=key,
            now=NOW,
        )

    def _run_front_door(self, factory, *, prefix="camp-market"):
        return fd.run_graduated_liquidity_front_door(
            self.db,
            cycle_seed=SEED,
            latest_mints={_mint(x) for x in self.labels},
            dexscreener_transport_factory=factory,
            now=NOW,
            request_key_prefix=prefix,
        )

    @staticmethod
    def _uniform(liquidity: float = 9000.0):
        def factory(mint, pool):
            return fixture_success_transport(_pair_payload(pool, mint, liquidity))

        return factory


class LocatorPlusSnapshotAccountingTests(_Base):
    """One locator + N pair snapshots must be charged exactly 1 + N."""

    def test_locator_plus_n_snapshots_is_exactly_one_plus_n(self) -> None:
        self._run_locator()
        report = self._run_front_door(self._uniform())

        n = len(self.labels)
        durable = self._durable_requests()
        self.assertEqual(len(durable), 1 + n, "durable rows must be 1 locator + N")

        ledger = report["source_operation_ledger"]
        self.assertEqual(ledger["liquidity_requests"], n)

        # The campaign sums the discovery total (which already contains the
        # locator) with the front-door total. That sum must equal the distinct
        # durable set exactly.
        discovery_total = len(durable) - n  # whole-table count at end of discovery
        self.assertEqual(discovery_total, 1)
        self.assertEqual(discovery_total + ledger["liquidity_requests"], len(durable))

    def test_locator_is_counted_exactly_once(self) -> None:
        self._run_locator()
        report = self._run_front_door(self._uniform())

        durable = self._durable_requests()
        locator_rows = [
            r for r in durable if r["request_kind"] == "dexscreener_fresh_profiles"
        ]
        self.assertEqual(len(locator_rows), 1)

        # The front door must NOT include the locator identity.
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try:
            dexscreener_whole_table = conn.execute(
                "SELECT COUNT(*) FROM printer_source_requests "
                "WHERE source_name='dexscreener'"
            ).fetchone()[0]
        finally:
            conn.close()
        # The regression: the old whole-table form returned locator + snapshots.
        self.assertEqual(dexscreener_whole_table, 1 + len(self.labels))
        self.assertEqual(
            report["source_operation_ledger"]["liquidity_requests"],
            len(self.labels),
            "front door must not re-count the discovery locator",
        )


class FrontDoorOwnIdentityTests(_Base):
    """Front-door accounting includes only its own pair_market_snapshot rows."""

    def test_accounting_uses_only_own_pair_snapshot_identities(self) -> None:
        report = self._run_front_door(self._uniform())
        ledger = report["source_operation_ledger"]

        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            own = conn.execute(
                "SELECT COUNT(*) FROM printer_source_requests "
                "WHERE request_kind='pair_market_snapshot'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(ledger["liquidity_requests"], own)
        self.assertEqual(ledger["liquidity_requests"], len(self.labels))

    def test_unrelated_earlier_dexscreener_rows_do_not_contaminate(self) -> None:
        # Three unrelated earlier DexScreener rows of other kinds/stages.
        self._run_locator(key="earlier-locator-1")
        self._run_locator(key="earlier-locator-2")
        self._run_locator(key="earlier-locator-3")

        report = self._run_front_door(self._uniform())
        ledger = report["source_operation_ledger"]

        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try:
            whole_table = conn.execute(
                "SELECT COUNT(*) FROM printer_source_requests "
                "WHERE source_name='dexscreener'"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(whole_table, 3 + len(self.labels))
        self.assertEqual(
            ledger["liquidity_requests"],
            len(self.labels),
            "earlier DexScreener rows must not enter stage-local accounting",
        )

    def test_successful_and_failed_snapshots_each_counted_once(self) -> None:
        failing_pool = _pool("B")

        def factory(mint, pool):
            if pool == failing_pool:
                return fixture_rate_limited_transport()
            return fixture_success_transport(_pair_payload(pool, mint, 9000.0))

        report = self._run_front_door(factory)
        ledger = report["source_operation_ledger"]

        # Every candidate is charged exactly once regardless of outcome.
        self.assertEqual(ledger["liquidity_requests"], len(self.labels))
        self.assertEqual(
            ledger["liquidity_responses"] + ledger["liquidity_failures"],
            len(self.labels),
            "each snapshot resolves to exactly one response or one failure",
        )
        self.assertGreaterEqual(ledger["liquidity_failures"], 1)

        durable = self._durable_requests()
        snapshots = [
            r for r in durable if r["request_kind"] == "pair_market_snapshot"
        ]
        self.assertEqual(len(snapshots), len(self.labels))


class DurableRowIntegrityTests(_Base):
    """No durable request row is lost or duplicated by the corrected accounting."""

    def test_no_row_lost_or_duplicated(self) -> None:
        self._run_locator()
        report = self._run_front_door(self._uniform())

        durable = self._durable_requests()
        ids = [r["id"] for r in durable]
        keys = [r["request_key"] for r in durable]

        self.assertEqual(len(ids), len(set(ids)), "duplicate durable request id")
        self.assertEqual(len(keys), len(set(keys)), "duplicate durable request key")
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(len(durable), 1 + len(self.labels))

        # Every durable request resolves to exactly one response or one failure.
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try:
            unresolved = conn.execute(
                """SELECT COUNT(*) FROM printer_source_requests rq
                   WHERE rq.id NOT IN (
                       SELECT source_request_id FROM printer_source_responses)
                     AND rq.id NOT IN (
                       SELECT source_request_id FROM printer_source_failures)"""
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(unresolved, 0)
        self.assertEqual(report["source_operation_ledger"]["liquidity_requests"],
                         len(self.labels))


class CampaignTotalEqualsDurableSetTests(_Base):
    """Campaign accounting equals the distinct durable campaign request set."""

    def test_campaign_total_equals_distinct_durable_requests(self) -> None:
        locator = self._run_locator()
        locator_total = int(locator.get("source_requests") or 1)
        report = self._run_front_door(self._uniform())
        front_door_total = report["source_operation_ledger"]["liquidity_requests"]

        # V2-9.8B.2: stage-local totals only. Discovery is not run here, so its
        # contribution is zero; locator + front-door must equal durable rows.
        supply_source_operations = locator_total + 0 + front_door_total
        durable_distinct = len(self._durable_requests())

        self.assertEqual(
            supply_source_operations,
            durable_distinct,
            "campaign governed_requests must equal distinct durable requests",
        )
        self.assertEqual(supply_source_operations - durable_distinct, 0)
        # Whole-table discovery counting is forbidden for campaign charging.
        conn = sqlite3.connect(f"file:{self.db}?mode=ro", uri=True)
        try:
            whole_table = conn.execute(
                "SELECT COUNT(*) FROM printer_source_requests"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(whole_table, durable_distinct)


class CandidateCapArithmeticTests(_Base):
    """Candidate-cap arithmetic uses the corrected request total."""

    def test_candidate_cap_uses_corrected_total(self) -> None:
        # Reproduces the E.46B.1 shape: 9 discovery requests + 6 front-door
        # snapshots. The old double count charged 16; the corrected total is 15.
        corrected = build_ledger(
            pump_operations=0,
            additional_governed_operations=15,
            deadline_at=DEADLINE,
        )
        overcounted = build_ledger(
            pump_operations=0,
            additional_governed_operations=16,
            deadline_at=DEADLINE,
        )

        self.assertEqual(corrected.governed_requests, 15)
        self.assertEqual(overcounted.governed_requests, 16)

        # The duplicated locator did not merely misreport: it consumed real
        # candidate-search depth.
        self.assertEqual(overcounted.candidate_cap(), 2)
        self.assertEqual(corrected.candidate_cap(), 3)
        self.assertGreater(corrected.candidate_cap(), overcounted.candidate_cap())


class SelectionUnchangedTests(_Base):
    """Selection and readiness outputs are unchanged by the accounting repair."""

    def test_selection_outputs_unchanged(self) -> None:
        report = self._run_front_door(self._uniform())

        # Deterministic selection still yields the same eligible set and order.
        self.assertEqual(report["candidate_count"], len(self.labels))
        self.assertEqual(report["below_floor_count"], 0)
        self.assertEqual(report["unproven_count"], 0)
        self.assertEqual(report["selection_floor_usd"], fd.SELECTION_FLOOR_USD)
        self.assertEqual(
            len(report["combined_reserve_order"]), len(self.labels)
        )

        # A second identical invocation on a fresh DB selects identically.
        second = _Base("run")
        second.labels = self.labels
        second.setUp()
        try:
            other = second._run_front_door(second._uniform())
            self.assertEqual(
                [c["mint"] for c in report["combined_reserve_order"]],
                [c["mint"] for c in other["combined_reserve_order"]],
            )
            self.assertEqual(
                other["source_operation_ledger"]["liquidity_requests"],
                len(self.labels),
            )
        finally:
            second.tearDown()

    def test_below_floor_candidate_still_rejected(self) -> None:
        def factory(mint, pool):
            liquidity = 10.0 if pool == _pool("C") else 9000.0
            return fixture_success_transport(_pair_payload(pool, mint, liquidity))

        report = self._run_front_door(factory)
        self.assertEqual(report["below_floor_count"], 1)
        # The rejected candidate is still charged exactly once.
        self.assertEqual(
            report["source_operation_ledger"]["liquidity_requests"], len(self.labels)
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
