from __future__ import annotations

import inspect
import unittest

from printer_v1.discovery import permanent_discovery_availability as availability
from printer_v1.discovery import eligible_token_supply as supply
from printer_v1.sources.measured_transport import (
    MeasuredTransportLedger,
    TransportOperationIdentity,
    canonical_transport_identity_key,
)


def _transport(mint: str) -> TransportOperationIdentity:
    return TransportOperationIdentity(
        stage="MINT_MARKET_BATCH",
        source_name="geckoterminal",
        endpoint_owner="candidate_market_batch",
        governed_request_kind="candidate_market_batch",
        method_or_endpoint="GET /api/v2/networks/solana/tokens/{mint}/pools",
        within_request_ordinal=1,
        target_category="mint_pool_reconciliation",
        target_identity=mint,
        response_bytes=100,
        normalized_rows=1,
        result="OK",
    )


class Dtw81UnknownLiquidityBackupTransportOwnershipTests(unittest.TestCase):
    def test_backup_function_accepts_both_existing_accounting_owner_hooks(self) -> None:
        params = inspect.signature(
            availability.run_bounded_unknown_liquidity_backup
        ).parameters
        self.assertIn("transport_identity_observer", params)
        self.assertIn("stage_evidence_sink", params)

    def test_backup_function_binds_action_local_observer_to_measured_ledger(self) -> None:
        source = inspect.getsource(availability.run_bounded_unknown_liquidity_backup)
        self.assertIn("on_transport_recorded=transport_identity_observer", source)

    def test_backup_function_seals_unknown_liquidity_backup_stage_evidence(self) -> None:
        source = inspect.getsource(availability.run_bounded_unknown_liquidity_backup)
        self.assertIn("_seal_unknown_liquidity_backup_stage_evidence", source)
        self.assertIn('stage_kind="UNKNOWN_LIQUIDITY_BACKUP"', inspect.getsource(
            availability._seal_unknown_liquidity_backup_stage_evidence
        ))

    def test_persistent_supply_wires_both_existing_owner_hooks_into_backup(self) -> None:
        source = inspect.getsource(supply.run_persistent_eligible_token_supply)
        call_start = source.index("run_bounded_unknown_liquidity_backup(")
        call_slice = source[call_start : call_start + 1800]
        self.assertIn("transport_identity_observer=transport_identity_observer", call_slice)
        self.assertIn("stage_evidence_sink=stage_evidence_sink", call_slice)

    def test_one_measured_backup_has_identical_manifest_action_and_campaign_identity(self) -> None:
        observed = []
        sealed_blocks = []
        ledger = MeasuredTransportLedger(
            campaign_id="campaign",
            run_id="run",
            cycle_id="cycle",
            on_transport_recorded=observed.append,
        )
        identity = _transport("mint-a")
        ledger.record_transport(identity)
        key = list(canonical_transport_identity_key(identity))
        coverage = {
            "source_request_id": 1,
            "source_name": "geckoterminal",
            "request_kind": "candidate_market_batch",
            "logical_stage_id": "campaign|run|cycle|UNKNOWN_LIQUIDITY_BACKUP|1",
            "transport_identity_count": 1,
            "transport_identity_keys": [key],
            "normalized_member_count": 1,
            "terminal_status": "COMPLETED",
        }

        sealed = availability._seal_unknown_liquidity_backup_stage_evidence(
            ledger=ledger,
            stage_evidence_sink=sealed_blocks.append,
            campaign_id="campaign",
            run_id="run",
            cycle_id="cycle",
            stage_sequence=1,
            terminal_status="COMPLETED",
            first_terminal_cause=None,
            sealed_at="2026-08-08T14:07:37+00:00",
            source_request_id=1,
            source_request_coverage=coverage,
            measurement_failed=False,
        )

        action = {canonical_transport_identity_key(item) for item in observed}
        campaign = {
            canonical_transport_identity_key(item)
            for item in sealed["transport_operations"]
        }
        manifest = {tuple(item) for item in coverage["transport_identity_keys"]}
        self.assertEqual(action, campaign)
        self.assertEqual(action, manifest)
        self.assertEqual(sealed_blocks, [sealed])
        self.assertEqual(sealed["stage_kind"], "UNKNOWN_LIQUIDITY_BACKUP")
        self.assertEqual(sealed["stage_sequence"], 1)

    def test_multiple_measured_backups_keep_manifest_action_and_campaign_sets_equal(self) -> None:
        observed = []
        sealed_blocks = []
        manifest_keys = []
        for sequence, mint in enumerate(("mint-a", "mint-b"), 1):
            ledger = MeasuredTransportLedger(
                campaign_id="campaign",
                run_id="run",
                cycle_id="cycle",
                on_transport_recorded=observed.append,
            )
            identity = _transport(mint)
            ledger.record_transport(identity)
            key = list(canonical_transport_identity_key(identity))
            manifest_keys.append(key)
            coverage = {
                "source_request_id": sequence,
                "source_name": "geckoterminal",
                "request_kind": "candidate_market_batch",
                "logical_stage_id": (
                    f"campaign|run|cycle|UNKNOWN_LIQUIDITY_BACKUP|{sequence}"
                ),
                "transport_identity_count": 1,
                "transport_identity_keys": [key],
                "normalized_member_count": 1,
                "terminal_status": "COMPLETED",
            }
            availability._seal_unknown_liquidity_backup_stage_evidence(
                ledger=ledger,
                stage_evidence_sink=sealed_blocks.append,
                campaign_id="campaign",
                run_id="run",
                cycle_id="cycle",
                stage_sequence=sequence,
                terminal_status="COMPLETED",
                first_terminal_cause=None,
                sealed_at="2026-08-08T14:07:37+00:00",
                source_request_id=sequence,
                source_request_coverage=coverage,
                measurement_failed=False,
            )

        action = {canonical_transport_identity_key(item) for item in observed}
        campaign = {
            canonical_transport_identity_key(item)
            for block in sealed_blocks
            for item in block["transport_operations"]
        }
        manifest = {tuple(item) for item in manifest_keys}
        self.assertEqual(action, campaign)
        self.assertEqual(action, manifest)
        self.assertEqual(len(action), 2)

    def test_zero_or_measurement_failed_backup_does_not_fabricate_campaign_stage(self) -> None:
        sealed_blocks = []
        ledger = MeasuredTransportLedger(
            campaign_id="campaign", run_id="run", cycle_id="cycle"
        )
        coverage = {
            "source_request_id": 1,
            "transport_identity_count": 0,
            "transport_identity_keys": [],
            "terminal_status": "BLOCKED",
        }
        for measurement_failed in (False, True):
            sealed = availability._seal_unknown_liquidity_backup_stage_evidence(
                ledger=ledger,
                stage_evidence_sink=sealed_blocks.append,
                campaign_id="campaign",
                run_id="run",
                cycle_id="cycle",
                stage_sequence=1,
                terminal_status="BLOCKED",
                first_terminal_cause="TRANSPORT_IDENTITY_MEASUREMENT_FAILED",
                sealed_at="2026-08-08T14:07:37+00:00",
                source_request_id=1,
                source_request_coverage=coverage,
                measurement_failed=measurement_failed,
            )
            self.assertIsNone(sealed)
        self.assertEqual(sealed_blocks, [])

    def test_provider_failure_with_measured_transport_seals_blocked_real_identity(self) -> None:
        observed = []
        sealed_blocks = []
        ledger = MeasuredTransportLedger(
            campaign_id="campaign",
            run_id="run",
            cycle_id="cycle",
            on_transport_recorded=observed.append,
        )
        identity = _transport("mint-fail")
        ledger.record_transport(identity)
        key = list(canonical_transport_identity_key(identity))
        coverage = {
            "source_request_id": 9,
            "transport_identity_count": 1,
            "transport_identity_keys": [key],
            "terminal_status": "BLOCKED",
        }
        sealed = availability._seal_unknown_liquidity_backup_stage_evidence(
            ledger=ledger,
            stage_evidence_sink=sealed_blocks.append,
            campaign_id="campaign",
            run_id="run",
            cycle_id="cycle",
            stage_sequence=9,
            terminal_status="BLOCKED",
            first_terminal_cause="SOURCE_UNAVAILABLE",
            sealed_at="2026-08-08T14:07:37+00:00",
            source_request_id=9,
            source_request_coverage=coverage,
            measurement_failed=False,
        )
        self.assertEqual(sealed["stage_terminal_status"], "BLOCKED")
        self.assertEqual(sealed["stage_first_terminal_cause"], "SOURCE_UNAVAILABLE")
        self.assertEqual(
            canonical_transport_identity_key(sealed["transport_operations"][0]),
            canonical_transport_identity_key(identity),
        )
        self.assertEqual(sealed_blocks, [sealed])


if __name__ == "__main__":
    unittest.main()
