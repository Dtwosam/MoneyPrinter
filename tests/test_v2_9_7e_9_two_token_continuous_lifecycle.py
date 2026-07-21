"""V2-9.7E.9 exact-two-token compressed continuous lifecycle proof.

Synthetic fixtures only; each test uses a disposable database migrated through
036 via the E.8 integration base. The production wall-clock contract is not
compressed: a deterministic clock advances the existing 15m/1h/4h deadlines.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
import unittest
from unittest.mock import patch

from printer_v1.operator_cli.one_command_15m_factory import (
    CompressedTwoTokenProofPlan,
    load_report_only,
)
from printer_v1.operator_cli.origin_lifecycle_campaign import (
    OriginToLifecycleCampaignDriver,
)
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    build_fixture_source_adapter,
)
import test_v2_9_7e_8_origin_to_lifecycle_integration as e8

MINT_A = e8.MINT_A
MINT_B = e8.MINT_B
NOW = e8.NOW


class _Clock:
    def __init__(self) -> None:
        self.instant = datetime.fromisoformat(NOW)
        self.elapsed = 0.0

    def now(self) -> datetime:
        value = self.instant
        self.instant += timedelta(microseconds=1)
        return value

    def monotonic(self) -> float:
        return self.elapsed

    def sleep(self, seconds: float) -> None:
        self.elapsed += seconds
        self.instant += timedelta(seconds=seconds)


class _ClockDateTime(datetime):
    clock: _Clock

    @classmethod
    def now(cls, tz=None):
        value = cls.clock.now()
        return value if tz is None else value.astimezone(tz)


class TwoTokenContinuousLifecycleProofTests(e8._IntegrationBase):
    def _proof_context_factories(self, clock: _Clock):
        phase = {"close": 0}

        def market(**kwargs):
            phase["close"] += 1
            if phase["close"] != 2:
                return build_fixture_source_adapter(
                    "coingecko", fixture_kind=FIXTURE_FAILURE
                )
            return build_fixture_source_adapter(
                "coingecko",
                fixture_payload={
                    "captured_at": clock.now().isoformat(),
                    "assets": {
                        "bitcoin": {"price_usd": 65000, "change_24h": 2.5},
                        "ethereum": {"price_usd": 3500, "change_24h": 1.5},
                        "solana": {
                            "price_usd": 150,
                            "change_24h": 4.0,
                            "volume_24h": 2_000_000_000,
                        },
                    },
                },
            )

        def safety(**kwargs):
            mint = kwargs.get("token_mint")
            clean = mint == MINT_B and phase["close"] == 2
            return build_fixture_source_adapter(
                "goplus",
                fixture_payload={
                    "token_mint": mint,
                    "mint_authority": None if clean else "observed-authority",
                    "freeze_authority": None,
                    "metadata_mutable": False,
                    "total_supply": "1000000000",
                    "top_10_holders": [{"percent": "3"} for _ in range(10)],
                    "lp_info": [{"locked": True}],
                    "risk_flags": [],
                },
            )

        def quote(**kwargs):
            if (
                MINT_B not in {kwargs.get("input_mint"), kwargs.get("output_mint")}
                or phase["close"] != 2
            ):
                return build_fixture_source_adapter(
                    "jupiter_quote", fixture_kind=FIXTURE_FAILURE
                )
            return build_fixture_source_adapter(
                "jupiter_quote",
                fixture_payload={
                    "route_available": True,
                    "route_plan_present": True,
                    "slippage_bps": 50,
                    "price_impact_bps": 5,
                    "freshness_label": "QUOTE_FRESH",
                    "target_status": "TARGET_MATCH",
                    "paper_only_context": True,
                    "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
                    "input_mint": kwargs["input_mint"],
                    "output_mint": kwargs["output_mint"],
                },
            )
        return {"coingecko": market, "goplus": safety, "jupiter_quote": quote}

    def _proof_snapshot_adapter_factory(self):
        calls: list[str] = []
        per_mint_calls = {MINT_A: 0, MINT_B: 0}

        def build(*, token_mint, timeout_seconds):
            calls.append(token_mint)
            per_mint_calls[token_mint] += 1
            # The first same-stream 5m prefix for B contains an observed 50%
            # liquidity increase. It is deterministic evidence for the
            # support-only LIQUIDITY_SHOCK trigger, not a forced outcome label.
            liquidity = (
                10_000.0
                if token_mint != MINT_B or per_mint_calls[token_mint] == 1
                else 15_000.0
            )
            pair = e8.POOL_A if token_mint == MINT_A else e8.POOL_B
            return build_fixture_source_adapter(
                "dexscreener",
                fixture_payload={
                    "pairs": [{
                        "chain": "solana",
                        "token_mint": token_mint,
                        "pair_address": pair,
                        "price_usd": 1.0,
                        "liquidity_usd": liquidity,
                        "volume_5m": 500.0,
                        "volume_1h": 2000.0,
                        "volume_24h": 10000.0,
                        "txns_5m": 10,
                        "txns_1h": 50,
                        "txns_24h": 500,
                        "buys_5m": 7,
                        "sells_5m": 3,
                        "buys_1h": 30,
                        "sells_1h": 20,
                        "buys_24h": 280,
                        "sells_24h": 220,
                        "price_change_5m": 1.0,
                        "price_change_1h": 2.0,
                        "price_change_24h": 3.0,
                    }]
                },
            )

        return build, calls
    def _run_complete_proof(self, *, snapshot_factory=None):
        clock = _Clock()
        _ClockDateTime.clock = clock
        default_snapshot, calls = self._proof_snapshot_adapter_factory()
        driver = OriginToLifecycleCampaignDriver()
        plan = CompressedTwoTokenProofPlan(
            continuation_token_mint=MINT_B,
            non_continuation_token_mint=MINT_A,
        )
        kwargs = {
            "snapshot_adapter_factory": snapshot_factory or default_snapshot,
            "context_adapter_factories": self._proof_context_factories(clock),
            "compressed_two_token_proof_plan": plan,
            "_window_seconds": 900.0,
            "_continuation_seconds": 2700.0,
            "_sleep": clock.sleep,
            "_monotonic": clock.monotonic,
            "total_duration_seconds": 20_000.0,
            "launch_provenance": e8._provenance(),
        }
        with (
            patch(
                "printer_v1.operator_cli.one_command_15m_factory._now",
                clock.now,
            ),
            patch("printer_v1.sources.contracts.datetime", _ClockDateTime),
        ):
            result = driver.run(
                command=self.command,
                fixtures=self._two_origin_fixtures(),
                backup_path=self.backup,
                selection_seed="v2-9-7e-8-integration-seed",
                proof_mode=True,
                continuous_first_hour=True,
                continuous_four_hour=True,
                four_hour_proof_mode=True,
                lifecycle_kwargs=kwargs,
            )
        return result, calls

    def test_exact_two_token_terminal_proof_and_replay(self) -> None:
        result, calls = self._run_complete_proof()
        self.assertTrue(result.lifecycle_started)
        report = result.lifecycle
        self.assertEqual(report["run_status"], "COMPLETED")
        self.assertEqual(report["stop_reason"], "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED")
        proof = report["two_token_continuous_proof"]
        self.assertTrue(proof["complete"], proof["reasons"])
        self.assertEqual(proof["terminal_15m_count"], 2)
        self.assertEqual(proof["terminal_1h_count"], 1)
        self.assertEqual(proof["terminal_4h_count"], 1)
        self.assertEqual(proof["authoritative_clean_promotion_count"], 1)
        self.assertEqual(proof["dirty_promotion_count"], 0)
        self.assertEqual({row["token_mint"] for row in report["selected_tokens"]}, {MINT_A, MINT_B})
        self.assertTrue(calls)
        self.assertEqual(set(calls), {MINT_A, MINT_B})
        self.assertEqual(
            {(row["token_mint"], row["pair_address"]) for row in report["selected_tokens"]},
            {(MINT_A, e8.POOL_A), (MINT_B, e8.POOL_B)},
        )

        closes = [
            row for row in report["steps"]
            if row["step_kind"] in {
                "WINDOW_CLOSE", "CONTINUATION_CLOSE", "LONG_CONTINUATION_CLOSE"
            }
        ]
        self.assertEqual(
            [(row["step_kind"], row["token_mint"], row["step_status"]) for row in closes],
            [
                ("WINDOW_CLOSE", MINT_A, "SUCCEEDED"),
                ("WINDOW_CLOSE", MINT_B, "SUCCEEDED"),
                ("CONTINUATION_CLOSE", MINT_B, "SUCCEEDED"),
                ("LONG_CONTINUATION_CLOSE", MINT_B, "SUCCEEDED"),
            ],
        )
        close_results = {
            row["token_mint"]: json.loads(row["result_json"])
            for row in closes if row["step_kind"] == "WINDOW_CLOSE"
        }
        self.assertEqual(
            close_results[MINT_A]["support_5m"]["verdict"], "VALID_NO_CAPTURE"
        )
        self.assertEqual(
            close_results[MINT_A]["continuation_plan"]["verdict"], "STOP_AFTER_15M"
        )
        support_id = close_results[MINT_B]["support_5m"]["window_5m_id"]
        self.assertIsNotNone(support_id)
        self.assertEqual(
            close_results[MINT_B]["support_5m"]["proof_evidence"],
            "LIQUIDITY_SHOCK_OBSERVED",
        )
        self.assertTrue(close_results[MINT_B]["continuation_plan"]["enqueue_ok"])
        support_window = next(
            row for row in report["memory_windows"] if row["id"] == support_id
        )
        self.assertEqual(support_window["window_kind"], "WINDOW_5M_MICRO_EVENT")
        self.assertNotIn(support_id, {
            outcome["memory_window_id"]
            for outcome in report["per_token_outcomes"]
            if outcome["promotion_status"] == "CLEAN_PROMOTED"
        })
        self.assertTrue(report["run_budgets"]["governed_requests_run_within_ceiling"])
        self.assertTrue(report["run_budgets"]["governed_requests_per_token_within_ceiling"])
        self.assertTrue(report["run_budgets"]["scheduler_rows_within_ceiling"])
        self.assertEqual(report["pending_or_running_run_steps"], 0)
        self.assertEqual(report["running_jobs_after_stop"], 0)
        self.assertTrue(all(value == 0 for value in report["forbidden_deltas"].values()))
        self.assertTrue(report["four_hour_terminal_validation"]["complete"])

        connection = sqlite3.connect(self.db)
        try:
            persisted = connection.execute(
                "SELECT COUNT(*),COUNT(final_report_json) FROM printer_memory_factory_runs "
                "WHERE run_id=?",
                (report["run_id"],),
            ).fetchone()
            support_episodes = connection.execute(
                "SELECT COUNT(*) FROM printer_episodes WHERE memory_window_id=?",
                (support_id,),
            ).fetchone()[0]
            support_liquidity = connection.execute(
                "SELECT id,liquidity_usd FROM printer_token_snapshots "
                "WHERE id IN (?,?) ORDER BY id",
                (
                    support_window["snapshot_start_id"],
                    support_window["snapshot_end_id"],
                ),
            ).fetchall()
            active_jobs = connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs j JOIN "
                "printer_memory_factory_run_steps s ON s.scheduler_job_id=j.id "
                "WHERE s.run_id=? AND j.status IN ('PENDING','RUNNING','COOLDOWN')",
                (report["run_id"],),
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(persisted, (1, 1))
        self.assertEqual(support_episodes, 0)
        self.assertEqual([row[1] for row in support_liquidity], [10_000.0, 15_000.0])
        self.assertEqual(active_jobs, 0)
        replay_a = load_report_only(self.db, report["run_id"])
        replay_b = load_report_only(self.db, report["run_id"])
        self.assertEqual(replay_a, replay_b)
        self.assertEqual(replay_a["replay"]["new_source_calls"], 0)

    def test_effective_safety_acceptance_keeps_raw_unknown_observed_not_blocking(self) -> None:
        from printer_v1.operator_cli.commands import _collect_unknown_context_blockers

        labels = {
            "effective_safety_context_result": "SAFETY_CONTEXT_ACCEPTABLE",
            "raw_safety_context_label": "SAFETY_UNKNOWN",
            "raw_safety_action_label": None,
            "market_regime_label": "RISK_ON",
        }
        self.assertEqual(_collect_unknown_context_blockers(labels), [])

    def test_unknown_effective_safety_still_fails_closed(self) -> None:
        from printer_v1.operator_cli.commands import _collect_unknown_context_blockers

        labels = {
            "effective_safety_context_result": "SAFETY_CONTEXT_UNKNOWN",
            "raw_safety_context_label": "SAFETY_UNKNOWN",
        }
        blockers = _collect_unknown_context_blockers(labels)
        self.assertIn("raw_safety_context_label=SAFETY_UNKNOWN", blockers)
    def test_atomic_rollback_starts_no_lifecycle(self) -> None:
        from dataclasses import replace

        driver = OriginToLifecycleCampaignDriver()
        fixtures = replace(
            self._two_origin_fixtures(), force_handoff_failure="DURING_SECOND"
        )
        result = driver.run(
            command=self.command,
            fixtures=fixtures,
            backup_path=self.backup,
            selection_seed="v2-9-7e-8-integration-seed",
        )
        self.assertFalse(result.lifecycle_started)
        self.assertEqual(result.activation.activated_slots, ())
        connection = self._conn()
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_campaign_token_slots"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()

    def test_one_token_failure_does_not_corrupt_continuation_token(self) -> None:
        working, _calls = self._proof_snapshot_adapter_factory()

        def isolated_failure(*, token_mint, timeout_seconds):
            if token_mint == MINT_A:
                return build_fixture_source_adapter(
                    "dexscreener", fixture_kind=FIXTURE_FAILURE
                )
            return working(token_mint=token_mint, timeout_seconds=timeout_seconds)

        result, _ = self._run_complete_proof(snapshot_factory=isolated_failure)
        report = result.lifecycle
        self.assertEqual(report["run_status"], "FAILED")
        a_steps = [row for row in report["steps"] if row["token_mint"] == MINT_A]
        b_steps = [row for row in report["steps"] if row["token_mint"] == MINT_B]
        self.assertTrue(any(row["step_status"] == "FAILED" for row in a_steps))
        self.assertTrue(
            any(
                row["step_kind"] == "LONG_CONTINUATION_CLOSE"
                and row["step_status"] == "SUCCEEDED"
                for row in b_steps
            )
        )
        self.assertFalse(any(row["token_mint"] == MINT_A for row in b_steps))
        self.assertEqual(report["pending_or_running_run_steps"], 0)
        self.assertEqual(report["running_jobs_after_stop"], 0)
    def test_plan_identity_mismatch_fails_before_lifecycle_work(self) -> None:
        from printer_v1.operator_cli.one_command_15m_factory import (
            run_one_command_15m_factory,
        )

        connection = self._conn()
        try:
            connection.execute(
                "INSERT INTO printer_selection_batches(batch_id,batch_status,window_kind,"
                "candidate_pool_total,selected_count,rejected_count,"
                "unavailable_or_unclassified_count,operator_approved,created_at) "
                "VALUES('mismatch','ASSEMBLED','WINDOW_15M',0,0,0,0,1,?)",
                (NOW,),
            )
            connection.commit()
        finally:
            connection.close()

        def runner(_args):
            return {
                "selection_handoff_report": {
                    "batch_id": "mismatch",
                    "selection_seed": "seed",
                    "eligible_pool_size": 0,
                }
            }

        report = run_one_command_15m_factory(
                self.db,
                self.backup,
                operator_approved=True,
                proof_mode=True,
                discovery_runner=runner,
                continuous_first_hour=True,
                continuous_four_hour=True,
                four_hour_proof_mode=True,
                max_selected_tokens=2,
                compressed_two_token_proof_plan=CompressedTwoTokenProofPlan(
                    continuation_token_mint=MINT_B,
                    non_continuation_token_mint=MINT_A,
                ),
            launch_provenance=e8._provenance(),
        )
        self.assertEqual(report["run_status"], "SAFE_STOPPED")
        connection = self._conn()
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
                ).fetchone()[0],
                0,
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
