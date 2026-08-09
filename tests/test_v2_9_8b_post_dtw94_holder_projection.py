import unittest

from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    _holder_observation_context,
)
from printer_v1.operator_cli.pilot_input_readiness import (
    READINESS_PURPOSE_MEMORY_OBSERVATION,
    READINESS_READY,
    ReadinessCandidate,
    evaluate_readiness_gates,
)


class DTW94HolderProjectionTests(unittest.TestCase):
    def _fact(self, label, *, eligible=True, reason="VALID_EXACT_TARGET_HOLDER_EVIDENCE"):
        return {
            "eligible": eligible,
            "reason": reason,
            "source_name": "solana_rpc",
            "holder_concentration_label": label,
        }

    def test_healthy_holder_evidence_is_complete_and_future_holder_passes(self):
        context = _holder_observation_context(
            self._fact("HOLDER_CONCENTRATION_HEALTHY")
        )
        self.assertEqual("HOLDER_CONCENTRATION_HEALTHY", context["holder_condition"])
        self.assertEqual("COMPLETE", context["holder_evidence_status"])
        self.assertTrue(context["fully_eligible"])

    def test_concentrated_holder_evidence_is_complete_but_not_future_holder_pass(self):
        context = _holder_observation_context(
            self._fact("HOLDER_CONCENTRATION_CONCENTRATED")
        )
        self.assertEqual(
            "HOLDER_CONCENTRATION_CONCENTRATED", context["holder_condition"]
        )
        self.assertEqual("COMPLETE", context["holder_evidence_status"])
        self.assertFalse(context["fully_eligible"])

    def test_extreme_holder_evidence_is_complete_but_not_future_holder_pass(self):
        context = _holder_observation_context(
            self._fact("HOLDER_CONCENTRATION_EXTREME")
        )
        self.assertEqual("HOLDER_CONCENTRATION_EXTREME", context["holder_condition"])
        self.assertEqual("COMPLETE", context["holder_evidence_status"])
        self.assertFalse(context["fully_eligible"])

    def test_unavailable_holder_evidence_remains_fail_closed(self):
        context = _holder_observation_context(
            self._fact(
                "HOLDER_CONCENTRATION_UNKNOWN",
                eligible=False,
                reason="HOLDER_EVIDENCE_UNAVAILABLE",
            )
        )
        self.assertFalse(context["fully_eligible"])
        self.assertEqual("HOLDER_CONCENTRATION_UNKNOWN", context["holder_condition"])
        self.assertEqual("HOLDER_EVIDENCE_UNAVAILABLE", context["holder_evidence_status"])

    def test_memory_observation_readiness_does_not_require_holder_pass(self):
        candidate_a = ReadinessCandidate(
            mint="mint-a",
            pool="pool-a",
            market_identity="solana-mainnet:pumpswap:pool-a",
            liquidity_usd=4000.0,
            liquidity_observed_at="2026-08-09T00:00:00+00:00",
            activation_route="MARKET_PRESENT_POOL",
            holder_eligible=False,
            provenance="LATEST_GRADUATED",
            memory_observation_eligible=True,
            holder_condition="HOLDER_CONCENTRATION_EXTREME",
            admission_authority="MARKET_PRESENT_POOL",
        )
        candidate_b = ReadinessCandidate(
            mint="mint-b",
            pool="pool-b",
            market_identity="solana-mainnet:pumpswap:pool-b",
            liquidity_usd=4000.0,
            liquidity_observed_at="2026-08-09T00:00:00+00:00",
            activation_route="MARKET_PRESENT_POOL",
            holder_eligible=False,
            provenance="PERSISTED_GRADUATED",
            memory_observation_eligible=True,
            holder_condition="HOLDER_CONCENTRATION_CONCENTRATED",
            admission_authority="MARKET_PRESENT_POOL",
        )
        self.assertEqual(
            READINESS_READY,
            evaluate_readiness_gates(
                candidate_a,
                candidate_b,
                discovery_universe_evaluated=True,
                readiness_purpose=READINESS_PURPOSE_MEMORY_OBSERVATION,
            ),
        )


if __name__ == "__main__":
    unittest.main()
