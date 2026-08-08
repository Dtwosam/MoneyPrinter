from __future__ import annotations

import inspect
import unittest

from printer_v1.discovery import permanent_discovery_availability as availability
from printer_v1.discovery import eligible_token_supply as supply


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
        self.assertIn("seal_campaign_stage_evidence", source)
        self.assertIn('stage_kind="UNKNOWN_LIQUIDITY_BACKUP"', source)
        self.assertIn("stage_evidence_sink(sealed)", source)

    def test_persistent_supply_wires_both_existing_owner_hooks_into_backup(self) -> None:
        source = inspect.getsource(supply.run_persistent_eligible_token_supply)
        call_start = source.index("run_bounded_unknown_liquidity_backup(")
        call_slice = source[call_start : call_start + 1800]
        self.assertIn("transport_identity_observer=transport_identity_observer", call_slice)
        self.assertIn("stage_evidence_sink=stage_evidence_sink", call_slice)


if __name__ == "__main__":
    unittest.main()
