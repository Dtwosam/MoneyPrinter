"""V2-9.4.6 -- exact 4h run-ledger and closing-evidence boundaries.

Design steps 3-5 of printer-v1-v2-9-4-4-evidence-boundary-memory-semantics-design.md.

These fixtures pin the three boundary defects proven by the V2-9 Attempt 6
forensic audit:

  A. snapshot selection scanned by wall clock, so a predecessor captured at
     exactly window_start_at was swapped in and the real closing snapshot was
     exchanged for its predecessor;
  B. the immutable logical deadline (window_end_at) was reused as the
     closing-evidence cutoff;
  C. closing safety and exit-quote evidence bound to the exact closing
     snapshot was rejected for being marginally later than that deadline.

Paper-only. No live sources, no retrieval, no financial deltas.
"""

import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from printer_v1.chain_heat.recorder import record_chain_heat_snapshot
from printer_v1.context_evidence import build_window_4h_context_evidence
from printer_v1.db import apply_migrations
from printer_v1.market_regime.recorder import record_market_regime_snapshot
from printer_v1.paper_quote.evidence import insert_paper_quote_evidence
from printer_v1.safety.evidence import insert_solana_safety_evidence
from printer_v1.snapshots.recorder import record_token_snapshot
from printer_v1.snapshots.cadence_policy import get_policy

# The Attempt 6 window: 61 snapshots, ledger ids 1053-1113 inclusive, with a
# predecessor at id 1052 captured at exactly window_start_at.
PREDECESSOR_ID = 1052
FIRST_ID = 1053
LAST_ID = 1113
SNAPSHOT_COUNT = 61
CADENCE_SECONDS = 240
# Attempt 6's closing snapshot landed 3.66s after the logical deadline.
CLOSING_LATENESS_SECONDS = 3.66
RUN_ID = "v2-9-attempt-6-shaped"
OTHER_RUN_ID = "some-other-run"


class ExactClosingBoundaryTest(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "boundary.sqlite3"
        apply_migrations(self.db_path)
        self.start = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
        self.end = self.start + timedelta(hours=4)
        self.closing_at = self.end + timedelta(seconds=CLOSING_LATENESS_SECONDS)
        self.allowance = int(get_policy("WINDOW_4H", "TRACK_NORMAL").closing_clean_late_seconds)
        with self.connect() as connection:
            self.token_id = int(
                connection.execute(
                    "INSERT INTO printer_tokens (token_mint, chain) VALUES ('exact-mint', 'solana')"
                ).lastrowid
            )
            self.pair_id = int(
                connection.execute(
                    """
                    INSERT INTO printer_pairs (token_id, pair_address, dex, base_token_mint)
                    VALUES (?, 'exact-pair', 'test-dex', 'exact-mint')
                    """,
                    (self.token_id,),
                ).lastrowid
            )
            self.other_token_id = int(
                connection.execute(
                    "INSERT INTO printer_tokens (token_mint, chain) VALUES ('other-mint', 'solana')"
                ).lastrowid
            )
            self.other_pair_id = int(
                connection.execute(
                    """
                    INSERT INTO printer_pairs (token_id, pair_address, dex, base_token_mint)
                    VALUES (?, 'other-pair', 'test-dex', 'exact-mint')
                    """,
                    (self.token_id,),
                ).lastrowid
            )
        self.request_id, self.response_id = self.source_trace(
            "dexscreener", "pair_market_snapshot", self.start
        )

    def tearDown(self):
        self.tempdir.cleanup()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def source_trace(self, source_name, request_kind, captured_at):
        with self.connect() as connection:
            request_id = int(
                connection.execute(
                    """
                    INSERT INTO printer_source_requests (
                        source_name, request_kind, requested_at, source_status, data_quality_label
                    ) VALUES (?, ?, ?, 'COMPLETE', 'CLEAN_DATA')
                    """,
                    (source_name, request_kind, captured_at.isoformat()),
                ).lastrowid
            )
            response_id = int(
                connection.execute(
                    """
                    INSERT INTO printer_source_responses (
                        source_request_id, source_name, received_at, source_status,
                        data_quality_label, normalized_payload_json
                    ) VALUES (?, ?, ?, 'COMPLETE', 'CLEAN_DATA', '{}')
                    """,
                    (request_id, source_name, captured_at.isoformat()),
                ).lastrowid
            )
        return request_id, response_id

    def seed_ids_up_to(self, last_used_id):
        """Force the next recorded snapshot to take id last_used_id + 1.

        printer_token_snapshots.id is a rowid alias, so the next id is
        max(id) + 1. The seeded row belongs to an unrelated token, so it also
        stands in as an unrelated row sitting just below the ledger range.
        """
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO printer_token_snapshots (
                    id, token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                    price_usd, liquidity_usd, source_status, data_quality_label
                ) VALUES (?, ?, ?, ?, 'TRACK_NORMAL', 'NORMAL_MODE',
                          1.0, 100000, 'COMPLETE', 'CLEAN_DATA')
                """,
                (
                    last_used_id, self.other_token_id, self.other_pair_id,
                    (self.start - timedelta(minutes=1)).isoformat(),
                ),
            )

    def insert_snapshot(self, captured_at, *, token_id=None, pair_id=None, index=0):
        payload = {
            "token_id": self.token_id if token_id is None else token_id,
            "pair_id": self.pair_id if pair_id is None else pair_id,
            "token_mint": "exact-mint",
            "pair_address": "exact-pair",
            "captured_at": captured_at.isoformat(),
            "tracking_lane": "TRACK_NORMAL",
            "snapshot_mode": "NORMAL_MODE",
            "price_usd": 1.0 + (index * 0.01),
            "liquidity_usd": 100_000 + (index * 100),
            "volume_5m": 30_000,
            "volume_15m": 80_000,
            "volume_1h": 200_000,
            "volume_24h": 1_000_000,
            "txns_5m": 60,
            "txns_15m": 150,
            "txns_1h": 300,
            "txns_24h": 2_000,
            "buys_5m": 40,
            "sells_5m": 20,
            "unique_wallets_5m": 25,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            "source_name": "dexscreener",
            "source_request_id": self.request_id,
            "source_response_id": self.response_id,
        }
        _created, snapshot_id = record_token_snapshot(self.db_path, payload, captured_at)
        return int(snapshot_id)

    def add_window_snapshots(self):
        """Predecessor at exactly window_start_at, then the 61 ledger snapshots."""
        self.seed_ids_up_to(PREDECESSOR_ID - 1)
        predecessor = self.insert_snapshot(self.start, index=0)
        self.assertEqual(predecessor, PREDECESSOR_ID)
        ids = []
        for offset in range(SNAPSHOT_COUNT):
            if offset == SNAPSHOT_COUNT - 1:
                # The closing snapshot lands just after the logical deadline.
                captured_at = self.closing_at
            else:
                # The predecessor owns window_start_at exactly; the ledger
                # snapshots follow it on cadence.
                captured_at = self.start + timedelta(seconds=(offset + 1) * CADENCE_SECONDS)
            ids.append(self.insert_snapshot(captured_at, index=offset))
        self.assertEqual(ids, list(range(FIRST_ID, LAST_ID + 1)))
        return ids

    def add_ledger(self, snapshot_ids, *, run_id=RUN_ID):
        with self.connect() as connection:
            for index, snapshot_id in enumerate(snapshot_ids):
                is_close = snapshot_id == snapshot_ids[-1]
                connection.execute(
                    """
                    INSERT INTO printer_memory_factory_run_steps (
                        run_id, step_key, step_kind, step_status, token_id, pair_id,
                        tracking_lane, snapshot_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'TRACK_NORMAL', ?, ?, ?)
                    """,
                    (
                        run_id, f"step-{index}",
                        "LONG_4H_CLOSE" if is_close else "SNAPSHOT",
                        "RUNNING" if is_close else "SUCCEEDED",
                        self.token_id, self.pair_id, snapshot_id,
                        self.start.isoformat(), self.start.isoformat(),
                    ),
                )

    def add_broad_context(self, captured_at=None):
        when = captured_at or self.end
        market_request, market_response = self.source_trace(
            "coingecko", "broad_market_context", when
        )
        record_market_regime_snapshot(
            self.db_path,
            {
                "captured_at": when.isoformat(),
                "assets": {
                    "bitcoin": {"price_usd": 65_000, "change_24h": 2.5},
                    "ethereum": {"price_usd": 3_500, "change_24h": 1.5},
                    "solana": {"price_usd": 150, "change_24h": 4.0, "volume_24h": 2_000_000_000},
                },
                "fear_greed": {"value": 65, "label": "Greed"},
                "source_request_id": market_request,
                "source_response_id": market_response,
                "source_status": "COMPLETE",
                "data_quality_label": "CLEAN_DATA",
            },
            when,
        )
        chain_request, chain_response = self.source_trace(
            "defillama", "chain_liquidity_context", when
        )
        record_chain_heat_snapshot(
            self.db_path,
            {
                "captured_at": when.isoformat(),
                "assets": {"solana": {"price_usd": 150, "change_24h": 4.0, "volume_24h": 2_000_000_000}},
                "network_context": {
                    "active_addresses": 1_400_000,
                    "tx_count_24h": 30_000_000,
                    "priority_fee_context": "normal",
                    "congestion_context": "normal",
                    "new_token_count": 5_000,
                },
                "liquidity_context": {
                    "tvl_usd": 4_800_000_000,
                    "dex_volume_24h": 1_500_000_000,
                    "stablecoin_supply": 3_500_000_000,
                },
                "meme_context": {
                    "hot_pair_count": 48,
                    "meme_volume_24h": 60_000_000,
                    "meme_liquidity_usd": 12_000_000,
                    "meme_new_pair_count": 90,
                    "meme_graduation_count": 15,
                    "meme_failed_pair_count": 4,
                },
                "source_request_id": chain_request,
                "source_response_id": chain_response,
                "source_status": "COMPLETE",
                "data_quality_label": "CLEAN_DATA",
            },
            when,
        )

    def add_closing_evidence(self, snapshot_id, *, captured_at=None, pair_id=None, token_id=None):
        """Safety + entry/exit quotes bound to the exact closing snapshot."""
        when = captured_at or self.closing_at
        target_pair = self.pair_id if pair_id is None else pair_id
        target_token = self.token_id if token_id is None else token_id
        safety_request, safety_response = self.source_trace(
            "goplus", "token_safety_context", when
        )
        result = insert_solana_safety_evidence(
            self.db_path,
            {
                "token_id": target_token,
                "pair_id": target_pair,
                "snapshot_id": snapshot_id,
                "memory_window_id": None,
                "evidence_window_id": None,
                "safety_evidence_role": "TOKEN_SAFETY_CONTEXT",
                "source_name": "goplus",
                "source_status": "COMPLETE",
                "data_quality_label": "CLEAN_DATA",
                "target_status": "TARGET_MATCH",
                "evidence_captured_at": when.isoformat(),
                "freshness_label": "SAFETY_EVIDENCE_FRESH",
                "mint_authority_status": "MINT_AUTHORITY_RENOUNCED",
                "freeze_authority_status": "FREEZE_AUTHORITY_DISABLED",
                "metadata_mutability_status": "METADATA_IMMUTABLE",
                "supply_sanity_label": "SUPPLY_SANITY_OK",
                "holder_concentration_label": "HOLDER_CONCENTRATION_HEALTHY",
                "liquidity_lock_or_burn_label": "LIQUIDITY_LOCK_OR_BURN_CONFIRMED",
                "known_risk_flag_label": "NO_KNOWN_RISK_FLAGS",
                "token_program_label": "SPL_TOKEN_OR_TOKEN_2022_VERIFIED",
                "safety_context_label": "SAFETY_CLEAN",
                "source_request_id": safety_request,
                "source_response_id": safety_response,
                "source_failure_id": None,
                "paper_only_context": True,
            },
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
        )
        self.assertTrue(result.inserted)
        self.add_quote(snapshot_id, "EXIT", when, pair_id=target_pair, token_id=target_token)

    def add_entry_quote(self):
        """The 4h entry quote binds to snapshot_start_id, not the closing snapshot."""
        self.add_quote(FIRST_ID, "ENTRY", self.start + timedelta(seconds=CADENCE_SECONDS))

    def add_quote(self, snapshot_id, direction, when, *, pair_id=None, token_id=None):
        target_pair = self.pair_id if pair_id is None else pair_id
        target_token = self.token_id if token_id is None else token_id
        request_id, response_id = self.source_trace("jupiter", "paper_quote_realism", when)
        insert_paper_quote_evidence(
            self.db_path,
            {
                "token_id": target_token,
                "pair_id": target_pair,
                "snapshot_id": snapshot_id,
                "memory_window_id": None,
                "evidence_window_id": None,
                "quote_evidence_role": f"{direction}_QUOTE_CONTEXT",
                "quote_direction": direction,
                "quote_purpose": "PAPER_REALISM_ONLY",
                "source_name": "jupiter",
                "source_status": "COMPLETE",
                "data_quality_label": "CLEAN_DATA",
                "target_status": "TARGET_MATCH",
                "evidence_captured_at": when.isoformat(),
                "freshness_label": "QUOTE_FRESH",
                "quote_context_label": "QUOTE_ROUTE_AVAILABLE",
                "entry_realism_label": "ENTRY_REALISTIC" if direction == "ENTRY" else "ENTRY_UNKNOWN",
                "exit_realism_label": "EXIT_REALISTIC" if direction == "EXIT" else "EXIT_UNKNOWN",
                "route_available_label": "ROUTE_AVAILABLE",
                "slippage_context_label": "SLIPPAGE_ACCEPTABLE",
                "price_impact_context_label": "PRICE_IMPACT_ACCEPTABLE",
                "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
                "quote_failure_label": None,
                "source_request_id": request_id,
                "source_response_id": response_id,
                "source_failure_id": None,
                "paper_only_context": True,
            },
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
        )

    def report(self, *, run_id=RUN_ID, tracking_lane="TRACK_NORMAL", start_id=FIRST_ID, end_id=LAST_ID):
        with self.connect() as connection:
            before = connection.total_changes
            result = build_window_4h_context_evidence(
                connection,
                token_id=self.token_id,
                pair_id=self.pair_id,
                snapshot_start_id=start_id,
                snapshot_end_id=end_id,
                window_start_at=self.start,
                window_end_at=self.end,
                tracking_lane=tracking_lane,
                run_id=run_id,
            )
            # The resolver is read-only: it must never write.
            self.assertEqual(connection.total_changes, before)
        self.assertFalse(result["writes_performed"])
        return result

    def full_clean_fixture(self):
        ids = self.add_window_snapshots()
        self.add_ledger(ids)
        self.add_broad_context()
        self.add_entry_quote()
        self.add_closing_evidence(LAST_ID)
        return ids

    # --- selection: exact ledger identity -------------------------------

    def test_exact_ledger_ids_selected_and_predecessor_excluded(self):
        self.full_clean_fixture()
        result = self.report()
        self.assertEqual(result["snapshot_ids"], list(range(FIRST_ID, LAST_ID + 1)))
        self.assertEqual(len(result["snapshot_ids"]), SNAPSHOT_COUNT)
        # The predecessor sits at exactly window_start_at. A wall-clock scan
        # (captured_at >= window_start_at) selected it; ledger-exact id
        # selection must not.
        self.assertNotIn(PREDECESSOR_ID, result["snapshot_ids"])
        self.assertEqual(result["snapshot_ids"][-1], LAST_ID)

    def test_future_and_unrelated_snapshots_excluded(self):
        ids = self.add_window_snapshots()
        self.add_ledger(ids)
        # Beyond snapshot_end_id, and a different token/pair inside the id range.
        future_id = self.insert_snapshot(self.end + timedelta(minutes=10), index=99)
        unrelated_id = self.insert_snapshot(
            self.start + timedelta(minutes=5),
            token_id=self.other_token_id, pair_id=self.other_pair_id, index=99,
        )
        self.add_broad_context()
        self.add_closing_evidence(LAST_ID)
        result = self.report()
        self.assertNotIn(future_id, result["snapshot_ids"])
        self.assertNotIn(unrelated_id, result["snapshot_ids"])
        self.assertEqual(result["snapshot_ids"], list(range(FIRST_ID, LAST_ID + 1)))

    def test_snapshot_from_another_run_ledger_is_specifically_blocked(self):
        ids = self.add_window_snapshots()
        # Everything but the closing snapshot belongs to this run.
        self.add_ledger(ids[:-1])
        self.add_ledger([LAST_ID], run_id=OTHER_RUN_ID)
        self.add_broad_context()
        self.add_closing_evidence(LAST_ID)
        result = self.report()
        self.assertIn("SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER", result["blockers"])
        self.assertEqual(result["non_ledger_snapshot_ids"], [LAST_ID])
        self.assertFalse(result["clean_memory_context_ready"])

    def test_count_decoy_set_cannot_pass(self):
        """A set with the right COUNT but the wrong identity must not pass."""
        ids = self.add_window_snapshots()
        # Predecessor + first 60 real snapshots == 61 rows, the correct count,
        # but the wrong set: it ends one snapshot early.
        decoy = [PREDECESSOR_ID] + ids[:-1]
        self.assertEqual(len(decoy), SNAPSHOT_COUNT)
        self.add_ledger(decoy)
        self.add_broad_context()
        self.add_closing_evidence(LAST_ID)
        result = self.report()
        # Selection is bounded by the requested ids, so the decoy predecessor is
        # never reachable, and the closing snapshot is absent from the ledger.
        self.assertNotIn(PREDECESSOR_ID, result["snapshot_ids"])
        self.assertIn("SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER", result["blockers"])
        self.assertFalse(result["clean_memory_context_ready"])

    def test_boundary_mismatch_remains_a_genuine_assertion(self):
        ids = self.add_window_snapshots()
        self.add_ledger(ids)
        self.add_broad_context()
        self.add_closing_evidence(LAST_ID)
        # Ask for a closing id that the exact set does not reach: no snapshot
        # with this id exists for this token and pair. The blocker stays a
        # genuine assertion over the exact set rather than a scan artefact.
        result = self.report(end_id=LAST_ID + 5)
        self.assertIn("SNAPSHOT_BOUNDARY_MISMATCH", result["blockers"])
        self.assertEqual(result["snapshot_ids"][-1], LAST_ID)
        self.assertFalse(result["clean_memory_context_ready"])

    # --- deadline vs closing-evidence cutoff ----------------------------

    def test_logical_deadline_preserved_and_cutoff_is_separate(self):
        self.full_clean_fixture()
        result = self.report()
        # The logical deadline is immutable.
        self.assertEqual(result["window_end_at"], self.end.isoformat())
        self.assertEqual(result["evidence_duration_seconds"], 4 * 3600)
        # The cutoff bounds closing evidence only.
        self.assertEqual(result["closing_evidence_allowance_seconds"], self.allowance)
        self.assertEqual(
            result["closing_evidence_cutoff_at"],
            (self.end + timedelta(seconds=self.allowance)).isoformat(),
        )
        self.assertGreater(result["closing_evidence_cutoff_at"], result["window_end_at"])

    def test_cadence_and_duration_unchanged_by_the_cutoff(self):
        self.full_clean_fixture()
        with_lane = self.report()
        # Same window resolved without a lane: allowance collapses to zero and
        # the window's own geometry must be identical either way.
        without_lane = self.report(tracking_lane=None, run_id=None)
        self.assertEqual(without_lane["closing_evidence_allowance_seconds"], 0)
        for field in ("window_start_at", "window_end_at", "evidence_duration_seconds", "snapshot_ids"):
            self.assertEqual(with_lane[field], without_lane[field], field)

    def test_closing_snapshot_inside_allowance_is_accepted(self):
        self.full_clean_fixture()
        result = self.report()
        self.assertIn(LAST_ID, result["snapshot_ids"])
        self.assertEqual(result["sections"]["safety_rug"]["status"], "READY")
        self.assertNotIn("CLOSING_EVIDENCE_AFTER_APPROVED_CUTOFF", result["blockers"])

    def test_closing_evidence_outside_allowance_is_rejected(self):
        ids = self.add_window_snapshots()
        self.add_ledger(ids)
        self.add_broad_context()
        # One second past the approved allowance.
        self.add_closing_evidence(
            LAST_ID, captured_at=self.end + timedelta(seconds=self.allowance + 1)
        )
        result = self.report()
        self.assertIn("CLOSING_EVIDENCE_AFTER_APPROVED_CUTOFF", result["blockers"])
        self.assertFalse(result["clean_memory_context_ready"])

    # --- exact closing-evidence attachment ------------------------------

    def test_exact_closing_safety_and_exit_quote_attach(self):
        self.full_clean_fixture()
        result = self.report()
        safety = result["sections"]["safety_rug"]
        liquidity = result["sections"]["liquidity_exit_realism"]
        self.assertTrue(safety["can_support_clean_memory"])
        self.assertEqual(safety["labels"]["safety_status_label"], "SAFETY_CLEAN")
        self.assertTrue(liquidity["can_support_clean_memory"])
        self.assertEqual(liquidity["labels"]["exit_realism_label"], "EXIT_REALISTIC")

    def test_evidence_attached_to_another_snapshot_is_rejected(self):
        ids = self.add_window_snapshots()
        self.add_ledger(ids)
        self.add_broad_context()
        # Bound to the predecessor of the closing snapshot, inside the window.
        self.add_closing_evidence(LAST_ID - 1)
        result = self.report()
        self.assertIn("CLOSING_SAFETY_EVIDENCE_ABSENT_FOR_EXACT_SNAPSHOT", result["blockers"])
        self.assertIn("CLOSING_EXIT_QUOTE_ABSENT_FOR_EXACT_SNAPSHOT", result["blockers"])
        self.assertFalse(result["clean_memory_context_ready"])

    def test_evidence_for_another_pair_is_rejected(self):
        ids = self.add_window_snapshots()
        self.add_ledger(ids)
        self.add_broad_context()
        self.add_closing_evidence(LAST_ID, pair_id=self.other_pair_id)
        result = self.report()
        self.assertIn("CLOSING_SAFETY_EVIDENCE_ABSENT_FOR_EXACT_SNAPSHOT", result["blockers"])
        self.assertFalse(result["clean_memory_context_ready"])

    def test_missing_closing_evidence_still_fails_closed(self):
        ids = self.add_window_snapshots()
        self.add_ledger(ids)
        self.add_broad_context()
        result = self.report()
        self.assertIn("CLOSING_SAFETY_EVIDENCE_ABSENT_FOR_EXACT_SNAPSHOT", result["blockers"])
        self.assertIn("CLOSING_EXIT_QUOTE_ABSENT_FOR_EXACT_SNAPSHOT", result["blockers"])
        self.assertFalse(result["clean_memory_context_ready"])

    # --- the Attempt 6-shaped window ------------------------------------

    def test_attempt_6_shaped_window_loses_the_three_false_blockers(self):
        """The proven-false boundary blockers must be gone; truth preserved."""
        self.full_clean_fixture()
        result = self.report()
        self.assertEqual(result["snapshot_ids"], list(range(FIRST_ID, LAST_ID + 1)))
        for false_blocker in (
            "SNAPSHOT_BOUNDARY_MISMATCH",
            "NO_VALID_EXACT_TARGET_SAFETY_EVIDENCE",
            "NO_VALID_EXACT_TARGET_EXIT_QUOTE_EVIDENCE",
        ):
            self.assertNotIn(false_blocker, result["blockers"], false_blocker)
        self.assertEqual(result["non_ledger_snapshot_ids"], [])
        # Truthful chart and flow labels are preserved, not suppressed.
        self.assertIn("chart_volatility", result["sections"])
        self.assertIn("trading_flow", result["sections"])

    def test_no_retrieval_or_financial_delta(self):
        self.full_clean_fixture()
        result = self.report()
        self.assertFalse(any(result["downstream_unlocks"].values()))
        self.assertFalse(result["writes_performed"])
        with self.connect() as connection:
            for table in (
                "printer_paper_decisions",
                "printer_paper_positions",
                "printer_paper_trade_events",
            ):
                exists = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if exists is None:
                    continue
                count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                self.assertEqual(count, 0, table)


if __name__ == "__main__":
    unittest.main()
