"""V2-9.7E.45 Repair 4 proof — holder-aware reserve selection with replacement."""

from __future__ import annotations

import unittest

from printer_v1.discovery.graduated_liquidity_front_door import (
    LIQUIDITY_PROVEN,
    FrontDoorCandidate,
    _bounded_refresh_rows,
    LiquidityEvidence,
    select_holder_eligible_pair,
)

SEED = "e45-holder-seed"


def _cand(label: str, provenance: str) -> FrontDoorCandidate:
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
            status=LIQUIDITY_PROVEN,
            liquidity_usd=5000.0,
            mint=mint,
            pool=pool,
            reason="ok",
            source_status="COMPLETE",
        ),
        eligible=True,
        rejection=None,
    )


def _evaluator(eligible_mints: set[str]):
    calls: list[str] = []

    def _eval(candidate: FrontDoorCandidate):
        calls.append(candidate.mint)
        if candidate.mint in eligible_mints:
            return True, "eligible"
        return False, "HOLDER_CONCENTRATION_TOO_HIGH"

    _eval.calls = calls  # type: ignore[attr-defined]
    return _eval


class BoundedRefreshBatchTests(unittest.TestCase):
    def test_persisted_first_registry_cannot_starve_latest_partition(self) -> None:
        rows = [
            {"mint_identity": f"P{i}"} for i in range(4)
        ] + [
            {"mint_identity": f"L{i}"} for i in range(4)
        ]
        selected = _bounded_refresh_rows(
            rows,
            latest_mints={f"L{i}" for i in range(4)},
            cycle_seed=SEED,
            max_candidates=4,
        )
        identities = {str(row["mint_identity"]) for row in selected}
        self.assertEqual(len(identities), 4)
        self.assertEqual(sum(mint.startswith("L") for mint in identities), 2)
        self.assertEqual(sum(mint.startswith("P") for mint in identities), 2)

class HolderReserveFunnelTests(unittest.TestCase):
    def test_replacement_within_partition(self) -> None:
        latest = [_cand(f"L{i}", "LATEST_GRADUATED") for i in range(3)]
        persisted = [_cand(f"P{i}", "PERSISTED_GRADUATED") for i in range(3)]
        # Only the *last* candidate (in some order) of each partition is eligible;
        # the funnel must advance past the failing ones and still find it.
        eligible = {latest[2].mint, persisted[1].mint}
        ev = _evaluator(eligible)
        result = select_holder_eligible_pair(
            latest, persisted, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=12
        )
        self.assertIsNotNone(result["selected_latest"])
        self.assertIsNotNone(result["selected_persisted"])
        self.assertEqual(result["selected_latest"].mint, latest[2].mint)
        self.assertEqual(result["selected_persisted"].mint, persisted[1].mint)

    def test_stops_after_one_eligible_per_partition(self) -> None:
        latest = [_cand(f"L{i}", "LATEST_GRADUATED") for i in range(3)]
        persisted = [_cand(f"P{i}", "PERSISTED_GRADUATED") for i in range(3)]
        eligible = {c.mint for c in latest + persisted}  # all eligible
        ev = _evaluator(eligible)
        result = select_holder_eligible_pair(
            latest, persisted, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=12
        )
        # One op per partition = 2 total; no ops spent after acceptance.
        self.assertEqual(result["holder_operations"], 2)
        self.assertIsNotNone(result["selected_latest"])
        self.assertIsNotNone(result["selected_persisted"])

    def test_no_second_chance_for_rejected_identity(self) -> None:
        latest = [_cand(f"L{i}", "LATEST_GRADUATED") for i in range(3)]
        persisted = [_cand(f"P{i}", "PERSISTED_GRADUATED") for i in range(3)]
        ev = _evaluator(set())  # nobody eligible
        result = select_holder_eligible_pair(
            latest, persisted, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=20
        )
        self.assertIsNone(result["selected_latest"])
        self.assertIsNone(result["selected_persisted"])
        # Each identity evaluated at most once (no hidden retry).
        self.assertEqual(len(ev.calls), len(set(ev.calls)))
        self.assertEqual(len(ev.calls), 6)

    def test_candidate_cap_not_exceeded(self) -> None:
        latest = [_cand(f"L{i}", "LATEST_GRADUATED") for i in range(5)]
        persisted = [_cand(f"P{i}", "PERSISTED_GRADUATED") for i in range(5)]
        ev = _evaluator(set())  # force full scan pressure
        result = select_holder_eligible_pair(
            latest, persisted, cycle_seed=SEED, holder_evaluator=ev, candidate_cap=4
        )
        self.assertLessEqual(result["holder_operations"], 4)
        self.assertTrue(result["cap_reached"])
        self.assertEqual(len(ev.calls), result["holder_operations"])

    def test_deterministic_order(self) -> None:
        latest = [_cand(f"L{i}", "LATEST_GRADUATED") for i in range(4)]
        persisted = [_cand(f"P{i}", "PERSISTED_GRADUATED") for i in range(4)]
        ev1 = _evaluator(set())
        ev2 = _evaluator(set())
        select_holder_eligible_pair(
            latest, persisted, cycle_seed=SEED, holder_evaluator=ev1, candidate_cap=20
        )
        select_holder_eligible_pair(
            latest, persisted, cycle_seed=SEED, holder_evaluator=ev2, candidate_cap=20
        )
        # Identical seed -> identical deterministic evaluation order.
        self.assertEqual(ev1.calls, ev2.calls)

    def test_single_partition_degrades_honestly(self) -> None:
        latest = [_cand(f"L{i}", "LATEST_GRADUATED") for i in range(2)]
        ev = _evaluator({latest[0].mint, latest[1].mint})
        result = select_holder_eligible_pair(
            latest, [], cycle_seed=SEED, holder_evaluator=ev, candidate_cap=12
        )
        self.assertIsNotNone(result["selected_latest"])
        self.assertIsNone(result["selected_persisted"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
