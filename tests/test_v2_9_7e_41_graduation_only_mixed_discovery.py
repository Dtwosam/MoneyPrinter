"""V2-9.7E.41 graduation-only selection and mixed-channel discovery proof.

Fixture-only, isolated temporary databases only. Proves the graduation-only
tracking law: only exact PumpSwap-graduated candidates are selectable, age is
never eligibility, the 900-second gate is removed from FULL_PILOT but retained in
SNAPSHOT_READINESS, latest-only concentration is prevented, and blocked provider
channels stay honestly visible. The full gate + atomic two-slot handoff path is
regression-covered by the 7B.4d / 7B.4d.1 / 7B.5 combined-discovery suites, which
now operate on lawful graduated candidates.
"""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
import unittest

from printer_v1.discovery.combined_executor import (
    GRADUATED_LIFECYCLE,
    PUMPSWAP_MARKET_PREFIX,
    CombinedDiscoveryFixtures,
    CombinedPumpfunCampaignExecutor,
    FixtureOriginProof,
    FixturePumpSwapProof,
    _candidate_categories,
    _non_latest_categories,
    _Merged,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    OwnerPort,
    SOURCE_GOVERNOR_OWNER,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    BLOCKED_INSUFFICIENT_GRADUATED_POOL,
    GRADUATION_ELIGIBLE,
    GRADUATION_PENDING_DISCOVERY,
    AuthoritativeLiveOperationalCampaignOwner,
    _classify_graduation,
    _graduated_admission,
)
from printer_v1.scheduler.snapshot_maturity import (
    SNAPSHOT_MATURITY_SECONDS,
    SnapshotMaturityState,
    evaluate_snapshot_maturity,
)

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
from test_v2_9_7e_11_authoritative_live_operational_campaign import _FakePumpTransport
from test_v2_9_7e_5_pump_origin_acquisition_architecture import (
    create_transaction,
    signature_row,
)


GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)
NOW_EPOCH = int(datetime.fromisoformat(e8.NOW).timestamp())


def _executor(batch_seq: int = 1) -> CombinedPumpfunCampaignExecutor:
    fixtures = CombinedDiscoveryFixtures(
        cycle_id="cyc-41",
        cycle_cutoff="2026-07-21T15:06:00+00:00",
        campaign_selection_seed="e41-seed",
        provider_contract_versions={"direct": "V2-9.7E.41"},
        git_provenance_identity="e41",
        evaluated_at=e8.NOW,
        batch_seq=batch_seq,
    )
    return CombinedPumpfunCampaignExecutor(fixtures)


def _merged(
    mint: str,
    *,
    pool: str,
    lifecycle: str = GRADUATED_LIFECYCLE,
    channels: set[str],
    pumpswap_state: str = "CONFIRMED",
    venue: str = "pumpswap",
    origin_state: str = "CONFIRMED",
) -> _Merged:
    return _Merged(
        merged_candidate_id=f"cand:{mint}:{pool}",
        mint=mint,
        market_identity=f"solana-mainnet:{venue}:{pool}",
        lifecycle=lifecycle,
        channels=set(channels),
        observation_ids=[f"obs:{mint}"],
        conflicts=[],
        gaps=[],
        origin_state=origin_state,
        pumpswap_state=pumpswap_state,
    )


CYCLE_SEED = "0" * 64


class GraduationClassifierTests(unittest.TestCase):
    """Facts 1-7: exact PumpSwap graduation is mandatory eligibility."""

    def _proof(self, mint: str, block_time: int) -> FixtureOriginProof:
        return FixtureOriginProof(
            mint=mint, signature="s", slot=1, block_time=block_time
        )

    def test_bonding_curve_ineligible_at_every_age(self) -> None:
        # 1s, 900s, one hour, and much later: all pending discovery, never eligible.
        for age in (1, 900, 3600, 100_000):
            proof = self._proof("bondpump", NOW_EPOCH - age)
            self.assertEqual(
                _classify_graduation(proof, graduation=None),
                GRADUATION_PENDING_DISCOVERY,
            )

    def test_one_second_old_graduated_is_eligible(self) -> None:
        proof = self._proof("gradpump", NOW_EPOCH - 1)
        graduation = FixturePumpSwapProof(mint="gradpump", pool_address="pool1")
        self.assertEqual(
            _classify_graduation(proof, graduation=graduation), GRADUATION_ELIGIBLE
        )

    def test_migration_observed_without_confirmation_ineligible(self) -> None:
        # A migration claim that is not a confirmed PumpSwap pool fails closed.
        proof = self._proof("migpump", NOW_EPOCH - 10)
        unconfirmed = FixturePumpSwapProof(
            mint="migpump", pool_address="p", confirmed=False
        )
        self.assertEqual(
            _classify_graduation(proof, graduation=unconfirmed), "GRADUATION_FAILED"
        )

    def test_ambiguous_wrong_owner_and_mismatch_fail_closed(self) -> None:
        proof = self._proof("xpump", NOW_EPOCH - 10)
        self.assertEqual(
            _classify_graduation(
                proof,
                graduation=FixturePumpSwapProof(
                    mint="xpump", pool_address="p", confirmed=False, ambiguous=True
                ),
            ),
            "AMBIGUOUS_MARKET",
        )
        self.assertEqual(
            _classify_graduation(
                proof,
                graduation=FixturePumpSwapProof(
                    mint="xpump", pool_address="p", program_id="WRONG"
                ),
            ),
            "MARKET_IDENTITY_INVALID",
        )
        self.assertEqual(
            _classify_graduation(
                proof,
                graduation=FixturePumpSwapProof(mint="OTHER", pool_address="p"),
            ),
            "MARKET_IDENTITY_INVALID",
        )
        self.assertEqual(
            _classify_graduation(
                proof, graduation=FixturePumpSwapProof(mint="xpump", pool_address="")
            ),
            "MARKET_IDENTITY_INVALID",
        )


class SelectGraduationOnlyTests(unittest.TestCase):
    """Selection defence in depth: only graduated candidates are selectable."""

    def test_only_graduated_candidates_are_selectable(self) -> None:
        graduated = _merged("gradpump", pool="pg", channels={"ACTIVE_PUMPFUN"})
        discovery_only = [
            _merged(
                "u1pump",
                pool="c1",
                lifecycle="PUMP_CREATED_UNPAIRED",
                venue="pumpfun",
                channels={"LATEST_PUMPFUN"},
                pumpswap_state="NOT_REQUIRED",
            ),
            _merged(
                "u2pump",
                pool="c2",
                lifecycle="PUMP_BONDING_CURVE_ACTIVE",
                venue="pumpfun",
                channels={"ACTIVE_PUMPFUN"},
                pumpswap_state="NOT_REQUIRED",
            ),
            _merged(
                "u3pump",
                pool="c3",
                lifecycle="PUMP_MIGRATION_OBSERVED",
                venue="pumpfun",
                channels={"TRENDING_PUMPFUN"},
                pumpswap_state="FAILED",
            ),
            _merged(
                "u4pump",
                pool="c4",
                lifecycle="PUMP_LIFECYCLE_UNKNOWN",
                venue="pumpfun",
                channels={"TOP_PUMPFUN"},
                pumpswap_state="NOT_REQUIRED",
            ),
        ]
        selected = _executor()._select(
            [graduated, *discovery_only], CYCLE_SEED, vacancy_count=2
        )
        self.assertEqual([c.mint for c in selected], ["gradpump"])

    def test_selected_candidate_has_valid_pumpswap_market_identity(self) -> None:
        a = _merged("gapump", pool="pa", channels={"ACTIVE_PUMPFUN"})
        b = _merged("gbpump", pool="pb", channels={"TRENDING_PUMPFUN"})
        selected = _executor()._select([a, b], CYCLE_SEED, vacancy_count=2)
        self.assertEqual(len(selected), 2)
        for candidate in selected:
            self.assertTrue(
                candidate.market_identity.startswith(PUMPSWAP_MARKET_PREFIX)
            )
            self.assertEqual(candidate.lifecycle, GRADUATED_LIFECYCLE)


class CategoricalDistributionTests(unittest.TestCase):
    """Repair 5: no latest-only concentration; deterministic seeded uniform."""

    def test_two_latest_only_cannot_both_be_selected(self) -> None:
        latest_a = _merged("latApump", pool="la", channels={"LATEST_PUMPFUN"})
        latest_b = _merged("latBpump", pool="lb", channels={"LATEST_PUMPFUN"})
        active = _merged("actCpump", pool="ac", channels={"ACTIVE_PUMPFUN"})
        selected = _executor()._select(
            [latest_a, latest_b, active], CYCLE_SEED, vacancy_count=2
        )
        self.assertEqual(len(selected), 2)
        latest_only_selected = [
            c for c in selected if not _non_latest_categories(c.channels)
        ]
        self.assertEqual(len(latest_only_selected), 1)
        # Exactly one non-latest candidate is present.
        self.assertTrue(any(_non_latest_categories(c.channels) for c in selected))

    def test_single_category_degrades_honestly(self) -> None:
        # Only latest-only candidates available: no fabricated diversity.
        a = _merged("latApump", pool="la", channels={"LATEST_PUMPFUN"})
        b = _merged("latBpump", pool="lb", channels={"LATEST_PUMPFUN"})
        selected = _executor()._select([a, b], CYCLE_SEED, vacancy_count=2)
        self.assertEqual({c.mint for c in selected}, {"latApump", "latBpump"})

    def test_selection_is_deterministic(self) -> None:
        candidates = [
            _merged("latApump", pool="la", channels={"LATEST_PUMPFUN"}),
            _merged("actBpump", pool="ab", channels={"ACTIVE_PUMPFUN"}),
            _merged("trnCpump", pool="tc", channels={"TRENDING_PUMPFUN"}),
        ]
        first = _executor()._select(list(candidates), CYCLE_SEED, vacancy_count=2)
        second = _executor()._select(list(candidates), CYCLE_SEED, vacancy_count=2)
        self.assertEqual([c.mint for c in first], [c.mint for c in second])

    def test_round_robin_rotates_non_latest_by_batch_seq(self) -> None:
        latest = _merged("latApump", pool="la", channels={"LATEST_PUMPFUN"})
        active = _merged("actBpump", pool="ab", channels={"ACTIVE_PUMPFUN"})
        trending = _merged("trnCpump", pool="tc", channels={"TRENDING_PUMPFUN"})
        top = _merged("topDpump", pool="td", channels={"TOP_PUMPFUN"})
        pool = [latest, active, trending, top]
        picks = set()
        for seq in range(1, 6):
            selected = _executor(batch_seq=seq)._select(
                list(pool), CYCLE_SEED, vacancy_count=2
            )
            non_latest = [c for c in selected if _non_latest_categories(c.channels)]
            self.assertEqual(len(non_latest), 1)
            picks |= {
                next(iter(_non_latest_categories(non_latest[0].channels)))
            }
        # Round-robin visits more than one non-latest category across cycles.
        self.assertGreater(len(picks), 1)

    def test_duplicate_multichannel_appearance_no_probability_boost(self) -> None:
        # The same mint appearing under two markets/channels is ONE candidate.
        dup_market_a = _merged(
            "duppump", pool="d1", channels={"LATEST_PUMPFUN"}
        )
        dup_market_b = _merged(
            "duppump", pool="d2", channels={"ACTIVE_PUMPFUN"}
        )
        other = _merged("othpump", pool="o1", channels={"TRENDING_PUMPFUN"})
        selected = _executor()._select(
            [dup_market_a, dup_market_b, other], CYCLE_SEED, vacancy_count=2
        )
        mints = [c.mint for c in selected]
        self.assertEqual(len(mints), 2)
        self.assertEqual(len(set(mints)), 2)  # duppump appears at most once
        self.assertIn("othpump", mints)

    def test_channel_category_mapping(self) -> None:
        self.assertEqual(
            _candidate_categories({"LATEST_PUMPFUN"}), {"LATEST_GRADUATED"}
        )
        self.assertEqual(
            _non_latest_categories({"LATEST_PUMPFUN", "ACTIVE_PUMPFUN"}), {"ACTIVE"}
        )


class SnapshotReadinessUnchangedTests(unittest.TestCase):
    """Fact 8: the 900-second boundary is retained in SNAPSHOT_READINESS."""

    def test_maturity_threshold_and_boundary_intact(self) -> None:
        self.assertEqual(SNAPSHOT_MATURITY_SECONDS, 900)
        evaluated = datetime.fromtimestamp(NOW_EPOCH, tz=timezone.utc)
        immature = evaluate_snapshot_maturity(
            pump_block_time=NOW_EPOCH - 899, evaluated_at=evaluated
        )
        self.assertIs(immature.state, SnapshotMaturityState.IMMATURE)
        due = evaluate_snapshot_maturity(
            pump_block_time=NOW_EPOCH - 900, evaluated_at=evaluated
        )
        self.assertIs(due.state, SnapshotMaturityState.DUE)


class FullPilotNoMaturityGateTests(e8._IntegrationBase):
    """Facts 6, 7, 14, 16, 18: FULL_PILOT is graduation-only and honest."""

    def _run(self, specs):
        txs = {}
        rows = []
        for i, (block_time, label) in enumerate(specs):
            sig = f"e41Sig{i}"
            slot = 900 + i
            tx, _mint = create_transaction(sig, slot, block_time, mint_label=label)
            txs[sig] = tx
            rows.append(signature_row(sig, slot))
        transport = _FakePumpTransport(list(reversed(rows)), txs)
        owner = AuthoritativeLiveOperationalCampaignOwner()
        return owner.run_operational(
            command=self.command,
            pump_transport=transport,
            secondary_transport=None,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e41-full",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
            backup_path=self.backup,
            lifecycle_kwargs={},
        )

    def test_no_maturity_gate_and_graduated_terminal(self) -> None:
        # Removing the maturity symbol is proven structurally: the retired
        # _mature_admission is gone and the terminal is graduation-only.
        import printer_v1.operator_cli.authoritative_live_operational_campaign as mod

        self.assertFalse(hasattr(mod, "_mature_admission"))

        result = self._run([(NOW_EPOCH - 5, "aa"), (NOW_EPOCH - 9_000, "bb")])
        self.assertFalse(result.lifecycle_started)
        self.assertEqual(
            result.lifecycle["stop_reason"], BLOCKED_INSUFFICIENT_GRADUATED_POOL
        )
        self.assertNotIn("MATURE", result.lifecycle["stop_reason"])
        admission = result.lifecycle["full_pilot_admission"]
        self.assertEqual(admission["eligibility_rule"], "GRADUATION_ONLY")

    def test_blocked_channels_remain_visible(self) -> None:
        result = self._run([(NOW_EPOCH - 5, "cc"), (NOW_EPOCH - 5, "dd")])
        blocked = result.lifecycle["full_pilot_admission"]["blocked_channels"]
        self.assertEqual(blocked["GECKO_TRENDING_TOP"], "SKIPPED_BLOCKED_CONTRACT")
        self.assertEqual(
            blocked["SOLANA_TRACKER_TRENDING_TOP"], "SKIPPED_BLOCKED_CONTRACT"
        )
        self.assertEqual(
            blocked["PUMPPORTAL_MIGRATION_FEED"], "SKIPPED_BLOCKED_CONTRACT"
        )

    def test_no_forward_window_or_forbidden_capability(self) -> None:
        result = self._run([(NOW_EPOCH - 5, "ee"), (NOW_EPOCH - 5, "ff")])
        self.assertFalse(result.lifecycle_started)
        connection = sqlite3.connect(self.db)
        try:
            for table in (
                "printer_memory_windows",
                "printer_episodes",
                "printer_paper_decisions",
                "printer_paper_positions",
            ):
                self.assertEqual(
                    int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]),
                    0,
                )
            window_jobs = int(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_scheduler_jobs "
                    "WHERE job_name LIKE 'window15m:%'"
                ).fetchone()[0]
            )
            self.assertEqual(window_jobs, 0)
            fk = connection.execute("PRAGMA foreign_key_check").fetchall()
            self.assertEqual(fk, [])
            self.assertEqual(
                connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
            )
        finally:
            connection.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
