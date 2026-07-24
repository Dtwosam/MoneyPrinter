"""V2-9.7E.46B efficient partition-flexible two-token readiness proof.

Fixtures + isolated temporary DBs only (no live network, no persistent-DB
mutation, no lifecycle/pilot/memory). Proves that the mandatory
LATEST+PERSISTED pair quota is removed and any lawful two-token composition is
reachable from one deterministic combined candidate pool, that early candidate
failures continue to later eligible candidates, that a source outage is
classified separately from healthy discovery-coverage exhaustion, that one
eligible candidate still blocks honestly, that readiness writes
``PILOT_INPUT_READY`` only for two fully eligible candidates, and that a
pre-lifecycle terminal reconciles campaign/run/cycle metadata to honest terminal
states.
"""

from __future__ import annotations

import os
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from dataclasses import replace

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.graduated_liquidity_front_door import (
    COMBINED_TWO_TOKEN_CHANNEL,
    LIQUIDITY_PROVEN,
    SELECTION_CAPACITY_EXHAUSTED,
    SELECTION_COVERAGE_INSUFFICIENT,
    SELECTION_HOLDER_SOURCE_BLOCKED,
    SELECTION_TWO_TOKEN_READY,
    FrontDoorCandidate,
    LiquidityEvidence,
    combined_reserve_order,
    select_two_eligible_tokens,
)
from printer_v1.operator_cli.pilot_input_readiness import (
    ReadinessCandidate,
    build_pilot_input_ready_bundle,
    evaluate_readiness_gates,
    load_pilot_input_ready_bundle,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    PERSISTED_GRADUATED_CHANNEL,
)

SEED = "e46b-combined-seed"
NOW = "2026-07-24T15:00:00+00:00"
EXPIRES = "2026-07-24T15:10:00+00:00"


def _cand(label: str, provenance: str, *, liq: float = 5000.0) -> FrontDoorCandidate:
    mint = (f"{label}Mint" + "1" * 44)[:44]
    pool = (f"{label}Pool" + "1" * 44)[:44]
    return FrontDoorCandidate(
        mint=mint,
        pumpswap_pool=pool,
        market_identity=f"solana-mainnet:pumpswap:{pool}",
        provenance=provenance,
        lifecycle_state="PUMPSWAP_GRADUATED_CONFIRMED",
        graduation_block_time=1_700_000_000,
        liquidity=LiquidityEvidence(
            status=LIQUIDITY_PROVEN, liquidity_usd=liq, mint=mint, pool=pool,
            reason="ok", source_status="COMPLETE",
        ),
        eligible=True,
        rejection=None,
    )


def _evaluator(eligible_mints, *, reason_map=None):
    calls: list[str] = []
    reason_map = reason_map or {}

    def _eval(candidate: FrontDoorCandidate):
        calls.append(candidate.mint)
        if candidate.mint in eligible_mints:
            return True, "VALID_EXACT_TARGET_HOLDER_EVIDENCE"
        return False, reason_map.get(candidate.mint, "HOLDER_EVIDENCE_CONFLICT")

    _eval.calls = calls  # type: ignore[attr-defined]
    return _eval


class CombinedPoolCompositionTests(unittest.TestCase):
    """Any lawful composition works from one combined pool (item 2)."""

    def test_mixed_composition(self) -> None:
        latest = _cand("L0", LATEST_GRADUATED_CHANNEL)
        persisted = _cand("P0", PERSISTED_GRADUATED_CHANNEL)
        ev = _evaluator({latest.mint, persisted.mint})
        result = select_two_eligible_tokens(
            [latest, persisted], cycle_seed=SEED, holder_evaluator=ev, candidate_cap=12
        )
        self.assertEqual(result["terminal"], SELECTION_TWO_TOKEN_READY)
        self.assertEqual(result["composition"], "LATEST+PERSISTED")
        self.assertEqual(len(result["selected"]), 2)

    def test_two_latest_composition(self) -> None:
        pool = [_cand(f"L{i}", LATEST_GRADUATED_CHANNEL) for i in range(2)]
        ev = _evaluator({c.mint for c in pool})
        result = select_two_eligible_tokens(
            pool, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=12
        )
        self.assertEqual(result["terminal"], SELECTION_TWO_TOKEN_READY)
        self.assertEqual(result["composition"], "LATEST+LATEST")
        # True provenance preserved: both selected are LATEST, none relabelled.
        self.assertTrue(
            all(c.provenance == LATEST_GRADUATED_CHANNEL for c in result["selected"])
        )

    def test_two_persisted_composition(self) -> None:
        pool = [_cand(f"P{i}", PERSISTED_GRADUATED_CHANNEL) for i in range(2)]
        ev = _evaluator({c.mint for c in pool})
        result = select_two_eligible_tokens(
            pool, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=12
        )
        self.assertEqual(result["terminal"], SELECTION_TWO_TOKEN_READY)
        self.assertEqual(result["composition"], "PERSISTED+PERSISTED")

    def test_exhausted_partition_does_not_block(self) -> None:
        # Two eligible LATEST plus one PERSISTED that fails holder evidence: the
        # combined pool still yields two eligible tokens (LATEST+LATEST) even though
        # the PERSISTED partition is exhausted.
        latest = [_cand(f"L{i}", LATEST_GRADUATED_CHANNEL) for i in range(2)]
        persisted = [_cand("P0", PERSISTED_GRADUATED_CHANNEL)]
        ev = _evaluator({c.mint for c in latest})  # persisted fails
        result = select_two_eligible_tokens(
            latest + persisted, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=12
        )
        self.assertEqual(result["terminal"], SELECTION_TWO_TOKEN_READY)
        self.assertEqual(result["composition"], "LATEST+LATEST")


class ContinuationAndAccountingTests(unittest.TestCase):
    def test_continues_past_early_failures(self) -> None:
        # The first several candidates fail holder evidence; the funnel continues to
        # later eligible candidates rather than stopping.
        pool = [_cand(f"L{i}", LATEST_GRADUATED_CHANNEL) for i in range(6)]
        eligible = {pool[4].mint, pool[5].mint}
        ev = _evaluator(eligible)
        result = select_two_eligible_tokens(
            pool, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=20
        )
        self.assertEqual(result["terminal"], SELECTION_TWO_TOKEN_READY)
        self.assertEqual({c.mint for c in result["selected"]}, eligible)

    def test_finite_loop_exact_operation_accounting(self) -> None:
        pool = [_cand(f"L{i}", LATEST_GRADUATED_CHANNEL) for i in range(5)]
        ev = _evaluator(set())  # nobody eligible -> full scan
        result = select_two_eligible_tokens(
            pool, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=20
        )
        # Exact accounting: one op per evaluated candidate, each identity once.
        self.assertEqual(result["holder_operations"], len(result["funnel"]))
        self.assertEqual(len(ev.calls), len(set(ev.calls)))
        self.assertEqual(result["holder_operations"], 5)

    def test_cap_bounds_operations(self) -> None:
        pool = [_cand(f"L{i}", LATEST_GRADUATED_CHANNEL) for i in range(8)]
        ev = _evaluator(set())
        result = select_two_eligible_tokens(
            pool, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=4
        )
        self.assertLessEqual(result["holder_operations"], 4)
        self.assertTrue(result["cap_reached"])

    def test_deterministic_combined_order(self) -> None:
        pool = (
            [_cand(f"L{i}", LATEST_GRADUATED_CHANNEL) for i in range(3)]
            + [_cand(f"P{i}", PERSISTED_GRADUATED_CHANNEL) for i in range(3)]
        )
        order1 = combined_reserve_order(pool, cycle_seed=SEED)
        order2 = combined_reserve_order(pool, cycle_seed=SEED)
        self.assertEqual([c.mint for c in order1], [c.mint for c in order2])
        # One combined pool contains BOTH partitions (not round-robin restricted).
        self.assertEqual(len(order1), 6)


class TerminalClassificationTests(unittest.TestCase):
    """Source outage vs healthy coverage exhaustion are classified separately (item 8)."""

    def test_one_eligible_still_blocks_coverage_insufficient(self) -> None:
        pool = [_cand(f"L{i}", LATEST_GRADUATED_CHANNEL) for i in range(3)]
        ev = _evaluator({pool[0].mint})  # only one eligible
        result = select_two_eligible_tokens(
            pool, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=20
        )
        self.assertEqual(len(result["selected"]), 1)
        self.assertEqual(result["terminal"], SELECTION_COVERAGE_INSUFFICIENT)

    def test_source_outage_classified_as_source_blocked(self) -> None:
        pool = [_cand(f"L{i}", LATEST_GRADUATED_CHANNEL) for i in range(2)]
        ev = _evaluator(
            set(),
            reason_map={c.mint: "HOLDER_EVIDENCE_UNAVAILABLE" for c in pool},
        )
        result = select_two_eligible_tokens(
            pool, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=20
        )
        self.assertEqual(result["terminal"], SELECTION_HOLDER_SOURCE_BLOCKED)

    def test_capacity_exhausted_when_cap_stops_healthy_coverage(self) -> None:
        pool = [_cand(f"L{i}", LATEST_GRADUATED_CHANNEL) for i in range(6)]
        ev = _evaluator(set())  # healthy rejections (conflict), not source outage
        result = select_two_eligible_tokens(
            pool, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=3
        )
        self.assertEqual(result["terminal"], SELECTION_CAPACITY_EXHAUSTED)


class ReadinessBundleCompositionTests(unittest.TestCase):
    """PILOT_INPUT_READY is written for any two fully eligible tokens (item: readiness)."""

    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = pathlib.Path(self.temp.name) / "readiness.sqlite3"
        apply_migrations(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.execute("PRAGMA foreign_keys = ON")

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _readiness_candidate(self, label: str, provenance: str) -> ReadinessCandidate:
        pool = (f"{label}Pool" + "1" * 44)[:44]
        return ReadinessCandidate(
            mint=(f"{label}Mint" + "1" * 44)[:44],
            pool=pool,
            market_identity=f"solana-mainnet:pumpswap:{pool}",
            liquidity_usd=9_000.0,
            liquidity_observed_at=NOW,
            activation_route="GRADUATION_NATIVE",
            holder_eligible=True,
            provenance=provenance,
        )

    def test_two_latest_writes_bundle_with_true_provenance(self) -> None:
        token_a = self._readiness_candidate("A", LATEST_GRADUATED_CHANNEL)
        token_b = self._readiness_candidate("B", LATEST_GRADUATED_CHANNEL)
        bundle = build_pilot_input_ready_bundle(
            self.conn,
            readiness_id="e46b-two-latest",
            latest=token_a,
            persisted=token_b,
            holder_evidence={"a": "eligible", "b": "eligible"},
            source_ledger={"goplus": 2},
            selection_seed=SEED,
            git_provenance_identity="git-46b",
            configuration_hash="c" * 64,
            expires_at=EXPIRES,
            now=NOW,
        )
        self.assertEqual(bundle["readiness_state"], "PILOT_INPUT_READY")
        # Both slots carry their TRUE provenance; neither LATEST token is relabelled.
        self.assertEqual(bundle["latest"]["provenance"], LATEST_GRADUATED_CHANNEL)
        self.assertEqual(bundle["persisted"]["provenance"], LATEST_GRADUATED_CHANNEL)
        loaded = load_pilot_input_ready_bundle(self.conn, "e46b-two-latest")
        self.assertIsNotNone(loaded)

    def test_single_eligible_token_blocks_no_bundle(self) -> None:
        gate = evaluate_readiness_gates(
            self._readiness_candidate("A", LATEST_GRADUATED_CHANNEL),
            None,
            discovery_universe_evaluated=True,
        )
        self.assertNotEqual(gate, "PILOT_INPUT_READY")
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM printer_pilot_input_readiness_bundle"
            ).fetchone()[0],
            0,
        )


class TerminalMetadataReconciliationTests(unittest.TestCase):
    """Pre-lifecycle campaign/run/cycle metadata becomes terminal (item 9)."""

    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = pathlib.Path(self.temp.name) / "recon.sqlite3"
        apply_migrations(self.db)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _seed_graph(self) -> None:
        from printer_v1.operator_cli.campaign_ownership import create_campaign_run

        conn = sqlite3.connect(self.db)
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            conn.execute(
                """INSERT INTO printer_memory_factory_campaigns(
                    campaign_id, campaign_state, db_mode, db_target_identity,
                    proof_source_db_identity, policy_version, created_at, updated_at
                ) VALUES ('camp','RUNNING','PROOF_ISOLATED','iso','src','v1',?,?)""",
                (NOW, NOW),
            )
        create_campaign_run(
            conn, campaign_id="camp", run_id="run", run_ordinal=1, now=NOW
        )
        with conn:
            conn.execute(
                """INSERT INTO printer_memory_factory_campaign_cycles(
                    cycle_id, campaign_id, run_id, cycle_ordinal, cycle_state,
                    created_at, updated_at
                ) VALUES ('cyc','camp','run',1,'PLANNED',?,?)""",
                (NOW, NOW),
            )
            conn.execute(
                "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING'"
            )
        conn.close()

    def _states(self):
        conn = sqlite3.connect(self.db)
        try:
            camp = conn.execute(
                "SELECT campaign_state FROM printer_memory_factory_campaigns"
            ).fetchone()[0]
            run = conn.execute(
                "SELECT run_state FROM printer_memory_factory_campaign_runs"
            ).fetchone()[0]
            cyc = conn.execute(
                "SELECT cycle_state FROM printer_memory_factory_campaign_cycles"
            ).fetchone()[0]
        finally:
            conn.close()
        return camp, run, cyc

    def test_blocked_terminal_reconciles_to_terminal_blocked(self) -> None:
        from printer_v1.operator_cli.two_token_operational_pilot_runner import (
            _reconcile_pre_lifecycle_terminal_metadata,
        )

        self._seed_graph()
        result = _reconcile_pre_lifecycle_terminal_metadata(
            self.db,
            campaign_id="camp",
            run_id="run",
            cycle_id="cyc",
            terminal_cause="PRE_LIFECYCLE_DISCOVERY_SELECTION_COVERAGE_INSUFFICIENT",
            now=NOW,
        )
        self.assertTrue(result["reconciled"])
        self.assertEqual(self._states(), ("TERMINAL_BLOCKED",) * 3)

    def test_readiness_terminal_reconciles_to_terminal_stopped(self) -> None:
        from printer_v1.operator_cli.two_token_operational_pilot_runner import (
            _reconcile_pre_lifecycle_terminal_metadata,
        )

        self._seed_graph()
        result = _reconcile_pre_lifecycle_terminal_metadata(
            self.db,
            campaign_id="camp",
            run_id="run",
            cycle_id="cyc",
            terminal_cause="PILOT_INPUT_READY",
            now=NOW,
        )
        self.assertTrue(result["reconciled"])
        self.assertEqual(self._states(), ("TERMINAL_STOPPED",) * 3)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
