"""Focused frozen-secondary producer/consumer contract proof.

No public composition node, network transport, database, authorization or
financial path is executed here.
"""

from __future__ import annotations

import unittest

from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    LivePumpOriginAdapter,
    LiveSecondaryDiscoveryAdapter,
)
from printer_v1.sources import secondary_discovery as sd

import test_v2_9_7e_11_authoritative_live_operational_campaign as e11


class FrozenSecondaryDiscoveryContractTests(unittest.TestCase):
    def test_lawful_trending_active_and_empty_contracts(self) -> None:
        active_body = e11._lawful_gecko_active_body(
            pool="PoolFixture111",
            mint="MintFixture111",
        )
        active = sd.normalize_gecko_active(
            active_body,
            receipt_time="2026-07-21T17:00:00+00:00",
            evaluated_at="2026-07-21T17:00:00+00:00",
            requested_pool="PoolFixture111",
        )
        self.assertEqual(active.pool, "PoolFixture111")
        self.assertEqual(active.mint, "MintFixture111")
        self.assertEqual(active.activity_count, 2)
        self.assertEqual(
            sd.normalize_gecko_trending(
                {"data": []},
                receipt_time="2026-07-21T17:00:00+00:00",
                evaluated_at="2026-07-21T17:00:00+00:00",
                params=dict(sd.GECKO_TRENDING_PARAMS),
            ),
            (),
        )
        trending = sd.normalize_gecko_trending(
            {"data": [active_body["data"]]},
            receipt_time="2026-07-21T17:00:00+00:00",
            evaluated_at="2026-07-21T17:00:00+00:00",
            params=dict(sd.GECKO_TRENDING_PARAMS),
        )
        self.assertEqual([(row.mint, row.pool) for row in trending], [
            ("MintFixture111", "PoolFixture111")
        ])

    def test_missing_malformed_and_wrong_envelopes_are_exact_failures(self) -> None:
        cases = (
            ({}, "missing pool object"),
            ({"data": []}, "missing pool object"),
            ({"data": {"type": "pool"}}, "missing attributes"),
        )
        for body, detail in cases:
            with self.subTest(body=body):
                with self.assertRaises(sd.SecondaryDiscoveryError) as caught:
                    sd.normalize_gecko_active(
                        body,
                        receipt_time="2026-07-21T17:00:00+00:00",
                        evaluated_at="2026-07-21T17:00:00+00:00",
                        requested_pool="PoolFixture111",
                    )
                self.assertEqual(caught.exception.code, "MALFORMED_RESPONSE")
                self.assertEqual(caught.exception.detail, detail)

        with self.assertRaises(sd.SecondaryDiscoveryError) as wrapped:
            sd.normalize_gecko_trending(
                {"body": {"data": []}},
                receipt_time="2026-07-21T17:00:00+00:00",
                evaluated_at="2026-07-21T17:00:00+00:00",
                params=dict(sd.GECKO_TRENDING_PARAMS),
            )
        self.assertEqual(wrapped.exception.code, "MALFORMED_RESPONSE")
        self.assertEqual(wrapped.exception.detail, "missing data list")

    def test_frozen_builder_pins_contract_version_and_all_planned_bodies(self) -> None:
        bodies = e11._lawful_secondary_bodies(
            {"MintFixture111": "PoolFixture111"}
        )
        self.assertEqual(bodies["trending_pools"], {"data": []})
        self.assertEqual(bodies["token-profiles"], [])
        self.assertEqual(
            bodies["/pools/PoolFixture111"]["data"]["attributes"]["address"],
            "PoolFixture111",
        )
        with self.assertRaisesRegex(ValueError, "STALE_FROZEN_SECONDARY_CONTRACT"):
            e11._lawful_secondary_bodies(
                {"MintFixture111": "PoolFixture111"},
                contract_version="V2-9.7D.7B.3B",
            )

    def test_unmatched_frozen_url_is_a_transport_failure_not_empty_json(self) -> None:
        transport = e11._FakeSecondaryTransport(
            {"trending_pools": {"data": []}, "token-profiles": []}
        )
        enrichment = LiveSecondaryDiscoveryAdapter(transport).enrich(
            source_governor=e11.GOV,
            central_scheduler=e11.SCH,
            receipt_time="2026-07-21T17:00:00+00:00",
            active_pools=["UnplannedPool111"],
        )
        active = enrichment.gecko_ops[1]
        self.assertEqual(active.fixture_status, "failure")
        self.assertEqual(active.failure_type, "MISSING_FROZEN_FIXTURE")
        self.assertIsNone(active.body)

    def test_exact_fixture_setup_uses_real_adapter_and_normalizer_boundaries(self) -> None:
        pump_transport, _mints = e11._two_create_transport()
        acquisition = LivePumpOriginAdapter(pump_transport).acquire(
            source_governor=e11.GOV,
            central_scheduler=e11.SCH,
        )
        pools = {
            proof.mint: proof.bonding_curve
            for proof in acquisition.origin_proofs
        }
        transport = e11._FakeSecondaryTransport(
            e11._lawful_secondary_bodies(pools)
        )
        enrichment = LiveSecondaryDiscoveryAdapter(transport).enrich(
            source_governor=e11.GOV,
            central_scheduler=e11.SCH,
            receipt_time="2026-07-21T17:00:00+00:00",
            active_pools=list(pools.values()),
        )
        self.assertEqual(enrichment.requested, 3)
        self.assertEqual(enrichment.failures, 0)
        self.assertEqual(len(enrichment.gecko_ops), 2)
        self.assertEqual(enrichment.gecko_ops[0].body, {"data": []})
        active_fact = enrichment.gecko_ops[1]
        active = sd.normalize_gecko_active(
            active_fact.body,
            receipt_time=active_fact.receipt_time,
            evaluated_at=active_fact.receipt_time,
            requested_pool=str(active_fact.requested_pool),
        )
        self.assertEqual(active.pool, active_fact.requested_pool)
        self.assertIn(active.mint, pools)
        self.assertEqual(pools[active.mint], active.pool)
        self.assertEqual(len(transport.calls), 3)

        runtime_pump, _runtime_mints = e11._two_create_transport()
        runtime_secondary = e11._FakeSecondaryTransport(
            e11._lawful_secondary_bodies(pools)
        )
        fixtures, _acquisition, _enrichment = (
            AuthoritativeLiveOperationalCampaignOwner()._build_fixtures(
                pump_transport=runtime_pump,
                secondary_transport=runtime_secondary,
                source_governor=e11.GOV,
                central_scheduler=e11.SCH,
                cycle_id="frozen-contract-cycle",
                cycle_cutoff="2026-07-21T17:06:00+00:00",
                selection_seed="frozen-contract-seed",
                evaluated_at="2026-07-21T17:00:00+00:00",
                prior_cursor=None,
                timeout_seconds=30.0,
                byte_ceiling=1_572_864,
                tracker_api_key=None,
            )
        )
        self.assertEqual(
            fixtures.provider_contract_versions["geckoterminal"],
            sd.SECONDARY_DISCOVERY_CONTRACT_VERSION,
        )


if __name__ == "__main__":
    unittest.main()
