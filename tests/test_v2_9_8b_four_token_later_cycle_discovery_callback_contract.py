"""RED contract for the proof-only later-cycle discovery callback context.

Static/offline only: this test must not start Printer, fetch sources, schedule
work, mutate a database, generate memory, or activate a second cycle.
"""

from __future__ import annotations

import inspect
import unittest

from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)
from printer_v1.operator_cli.multi_cycle_campaign_coordinator import (
    MultiCycleAdmissionHealth,
)


class FourTokenLaterCycleDiscoveryCallbackContractTests(unittest.TestCase):
    def test_callback_exposes_exact_same_owner_proof_context(self) -> None:
        owner = AuthoritativeLiveOperationalCampaignOwner()
        callback = owner._build_later_cycle_discovery_callback()

        parameters = inspect.signature(callback).parameters

        expected = (
            "campaign_id",
            "campaign_run_id",
            "authoritative_factory_run_id",
            "cycle_id",
            "cycle_ordinal",
            "cycle_cutoff",
            "evaluated_at",
            "selection_seed",
            "source_governor",
            "central_scheduler",
            "admission_health",
        )

        self.assertEqual(
            tuple(parameters),
            expected,
            "later-cycle discovery callback must expose exact same-owner proof context",
        )

        for name in expected:
            self.assertEqual(
                parameters[name].kind,
                inspect.Parameter.KEYWORD_ONLY,
                f"{name} must be keyword-only",
            )

        self.assertIn(
            parameters["admission_health"].annotation,
            (MultiCycleAdmissionHealth, "MultiCycleAdmissionHealth"),
            "later-cycle admission health must use the canonical multi-cycle carrier",
        )

    def test_authoritative_owner_binds_its_callback_only_for_private_four_token_controller(self) -> None:
        source = inspect.getsource(
            AuthoritativeLiveOperationalCampaignOwner.run_operational
        )

        self.assertIn(
            'lk.get("four_token_proof_controller") is not None',
            source,
            "later-cycle callback must be gated by private four-token proof authority",
        )
        self.assertIn(
            'lk["later_cycle_discovery_callback"]',
            source,
            "authoritative owner must bind its callback into the existing lifecycle channel",
        )
        self.assertIn(
            "self._build_later_cycle_discovery_callback()",
            source,
            "later-cycle callback must be built by the authoritative operational owner",
        )
        self.assertIn(
            "LATER_CYCLE_DISCOVERY_CALLBACK_OVERRIDE_FORBIDDEN",
            source,
            "externally supplied later-cycle callback must fail closed",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
