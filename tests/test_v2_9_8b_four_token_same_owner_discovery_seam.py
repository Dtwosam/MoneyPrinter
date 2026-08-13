"""RED contract for the proof-only same-owner later-cycle discovery seam.

This test is static/offline. It must not start Printer, fetch sources, or mutate a
SQLite database.
"""

from __future__ import annotations

import inspect
import unittest

from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)


class FourTokenSameOwnerDiscoverySeamTests(unittest.TestCase):
    def test_authoritative_owner_exposes_internal_later_cycle_discovery_callback_builder(self) -> None:
        builder = getattr(
            AuthoritativeLiveOperationalCampaignOwner,
            "_build_later_cycle_discovery_callback",
            None,
        )
        self.assertTrue(
            callable(builder),
            "four-token later-cycle discovery must be built by the existing authoritative operational owner",
        )
        parameters = inspect.signature(builder).parameters
        self.assertIn("self", parameters)
        self.assertEqual(parameters["self"].kind, inspect.Parameter.POSITIONAL_OR_KEYWORD)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
