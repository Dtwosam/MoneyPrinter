"""Focused tests for continuous graduated-supply measured-evidence repair."""

from __future__ import annotations

import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from printer_v1.sources.campaign_six_unit_accounting import (
    CampaignSixUnitError,
    seal_campaign_stage_evidence,
)
from printer_v1.sources.dexscreener import build_dexscreener_pair_snapshot_transport
from printer_v1.sources.direct_pump_migration import (
    DIRECT_MIGRATION_INDEXED_ADDRESS,
    SIGNATURE_PAGE_REQUEST_KIND,
    build_direct_pump_migration_transport,
    normalize_direct_pump_migration_response,
)
from printer_v1.sources.measured_transport import (
    MeasuredTransportLedger,
    identities_from_payload,
    record_payload_transports,
)
from printer_v1.sources.contracts import SourceAdapterContext, SourceRequest

from tests.support.window_15m_measured_frozen_transports import (
    NetworkFreezeBundle,
    build_four_migration_cases,
    measured_frozen_payload,
)


def _ctx(kind: str, payload: dict | None = None) -> SourceAdapterContext:
    request = SourceRequest(
        source_name="solana_rpc",
        request_kind=kind,
        request_key=f"test-{kind}",
        tracking_priority=0,
        payload=dict(payload or {}),
    )
    # Minimal stand-ins for record/decision — transport does not use them.
    return SourceAdapterContext(
        request=request,
        request_record=SimpleNamespace(id=1),
        decision=SimpleNamespace(allowed=True),
        governor_approved=True,
        execution_path="source_governor_record_then_adapter_boundary",
    )


class MeasuredFrozenTransportTests(unittest.TestCase):
    def test_measured_frozen_payload_has_exactly_one_identity(self) -> None:
        body = {"pairs": [{"pairAddress": "P1"}]}
        payload = measured_frozen_payload(
            body,
            stage="DEXSCREENER_DISCOVERY",
            source_name="dexscreener_pair",
            endpoint_owner="dexscreener",
            governed_request_kind="pair_market_snapshot",
            method_or_endpoint="GET /pairs/solana/P1",
            target_category="exact_pair",
            target_identity="P1",
        )
        ids = identities_from_payload(payload)
        self.assertEqual(1, len(ids))
        self.assertEqual("pair_market_snapshot", ids[0].governed_request_kind)
        self.assertEqual("P1", ids[0].target_identity)
        self.assertEqual(1, ids[0].normalized_rows)
        self.assertGreater(ids[0].response_bytes, 0)

    def test_production_dex_pair_transport_emits_identity_under_http_freeze(self) -> None:
        cases = build_four_migration_cases()
        freeze = NetworkFreezeBundle(cases)
        pool = cases[0]["pool"]
        # Pair snapshot uses smoke transport → urlopen seam.
        with patch("urllib.request.urlopen", side_effect=freeze._urlopen):
            transport = build_dexscreener_pair_snapshot_transport(pool)
            payload = transport(None)
        ids = identities_from_payload(payload)
        self.assertEqual(1, len(ids))
        self.assertEqual("dexscreener_pair", ids[0].source_name)
        self.assertGreaterEqual(ids[0].normalized_rows, 1)
        self.assertIn("pairs", payload)
        self.assertTrue(payload.get("pairs"))

    def test_production_migration_normalizer_emits_identity_from_rpc_body(self) -> None:
        cases = build_four_migration_cases()
        freeze = NetworkFreezeBundle(cases)
        with patch(
            "printer_v1.sources.direct_pump_migration._rpc_post",
            side_effect=freeze._rpc_post,
        ):
            transport = build_direct_pump_migration_transport(
                rpc_url="https://api.mainnet.solana.com"
            )
            raw = transport(
                _ctx(
                    SIGNATURE_PAGE_REQUEST_KIND,
                    # Slice B: signature history is migration-targeted and the
                    # page may never be larger than the caller can inspect.
                    {
                        "indexed_address": DIRECT_MIGRATION_INDEXED_ADDRESS,
                        "cursor_before": None,
                        "signature_limit": 12,
                    },
                )
            )
        result = normalize_direct_pump_migration_response(
            raw,
            request_kind=SIGNATURE_PAGE_REQUEST_KIND,
            cursor_before=None,
            signature_limit=12,
        )
        ids = identities_from_payload(result.normalized_payload)
        self.assertEqual(1, len(ids))
        self.assertEqual(4, result.normalized_payload["signature_count"])
        self.assertEqual("getSignaturesForAddress", ids[0].method_or_endpoint)
        self.assertEqual(
            DIRECT_MIGRATION_INDEXED_ADDRESS,
            result.normalized_payload["indexed_address"],
        )
        self.assertIs(False, result.normalized_payload["cursor_used"])

    def test_plain_unmeasured_payload_fails_stage_seal(self) -> None:
        ledger = MeasuredTransportLedger(
            campaign_id="c", run_id="r", cycle_id="y"
        )
        # Started stage with zero contributions.
        with self.assertRaises(CampaignSixUnitError) as ctx:
            seal_campaign_stage_evidence(
                ledger=ledger,
                stage_id="c|r|y|DIRECT_PUMP_NOMINATION|1",
                stage_kind="DIRECT_PUMP_NOMINATION",
                stage_sequence=1,
                stage_terminal_status="COMPLETED",
                stage_first_terminal_cause=None,
                campaign_id="c",
                run_id="r",
                cycle_id="y",
            )
        self.assertIn("EMPTY_STARTED_STAGE_EVIDENCE", str(ctx.exception))

    def test_measured_payload_seals_started_stage(self) -> None:
        ledger = MeasuredTransportLedger(
            campaign_id="c", run_id="r", cycle_id="y"
        )
        payload = measured_frozen_payload(
            {"result": []},
            stage="DIRECT_PUMP_NOMINATION",
            source_name="solana_rpc",
            endpoint_owner="solana",
            governed_request_kind=SIGNATURE_PAGE_REQUEST_KIND,
            method_or_endpoint="getSignaturesForAddress",
            target_category="pump_program",
            target_identity="pump",
            normalized_rows=0,
        )
        n = record_payload_transports(
            ledger, payload, default_stage="DIRECT_PUMP_NOMINATION"
        )
        self.assertEqual(1, n)
        sealed = seal_campaign_stage_evidence(
            ledger=ledger,
            stage_id="c|r|y|DIRECT_PUMP_NOMINATION|1",
            stage_kind="DIRECT_PUMP_NOMINATION",
            stage_sequence=1,
            stage_terminal_status="COMPLETED",
            stage_first_terminal_cause=None,
            campaign_id="c",
            run_id="r",
            cycle_id="y",
        )
        self.assertIsInstance(sealed, dict)
        # At least one transport identity present after seal.
        ops = (
            sealed.get("transport_operations")
            or sealed.get("source_transport_operations")
            or sealed.get("transport_operation_identities")
            or []
        )
        if isinstance(ops, int):
            self.assertGreaterEqual(ops, 1)
        else:
            self.assertGreaterEqual(len(ops), 1)

    def test_four_migration_cases_are_unique(self) -> None:
        cases = build_four_migration_cases()
        self.assertEqual(4, len(cases))
        mints = {c["mint"] for c in cases}
        pools = {c["pool"] for c in cases}
        sigs = {c["signature"] for c in cases}
        self.assertEqual(4, len(mints))
        self.assertEqual(4, len(pools))
        self.assertEqual(4, len(sigs))

    def test_duplicate_identity_fails_ledger(self) -> None:
        ledger = MeasuredTransportLedger(campaign_id="c", run_id="r", cycle_id="y")
        payload = measured_frozen_payload(
            {"pairs": []},
            stage="MINT_MARKET_BATCH",
            source_name="dexscreener_pair",
            endpoint_owner="dexscreener",
            governed_request_kind="candidate_market_batch",
            method_or_endpoint="GET",
            target_category="due_mints",
            target_identity="a,b",
            normalized_rows=0,
        )
        record_payload_transports(ledger, payload)
        with self.assertRaises(Exception):
            record_payload_transports(ledger, payload)


if __name__ == "__main__":
    unittest.main()
