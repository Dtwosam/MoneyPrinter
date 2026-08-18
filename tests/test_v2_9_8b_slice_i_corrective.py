from __future__ import annotations

from dataclasses import replace
import inspect
from unittest.mock import patch

import pytest

import test_v2_9_7e_44_full_pilot_supply_integration as e44
from printer_v1.discovery import combined_executor
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
)


class _AdmissionCaptured(RuntimeError):
    pass


class TestCycle1FinalAuthority(e44.WiringTests):
    def test_permanent_cycle_one_admission_universe_is_selected_pair(self):
        base = self._supply()
        alt_c = replace(
            base.graduated_supply[0],
            mint="mint-report-only-alternate-c",
            signature="sig-report-only-alternate-c",
            bonding_curve="pool-report-only-alternate-c",
        )
        alt_d = replace(
            base.graduated_supply[1],
            mint="mint-report-only-alternate-d",
            signature="sig-report-only-alternate-d",
            bonding_curve="pool-report-only-alternate-d",
        )
        supply = replace(
            base,
            holder_reserve_supply=base.graduated_supply + (alt_c, alt_d),
            diagnostics={
                **dict(base.diagnostics),
                "permanent_availability": True,
            },
        )
        selected_mints = [item.mint for item in supply.graduated_supply]
        captured_mints: list[str] = []

        def capture_admission_inputs(admission_inputs, **_kwargs):
            captured_mints.extend(item.mint for item in admission_inputs)
            raise _AdmissionCaptured

        with patch(
            "printer_v1.operator_cli.authoritative_live_operational_campaign._graduated_admission",
            side_effect=capture_admission_inputs,
        ):
            with pytest.raises(_AdmissionCaptured):
                AuthoritativeLiveOperationalCampaignOwner().run_operational(
                    command=self.command,
                    pump_transport=e44._FakePumpTransport([], {}),
                    secondary_transport=None,
                    source_governor=e44.GOV,
                    central_scheduler=e44.SCH,
                    selection_seed="slice-i-cycle-one-final-authority",
                    cycle_id="cyc",
                    cycle_cutoff=e44.e8.CUTOFF,
                    evaluated_at=e44.e8.NOW,
                    backup_path=self.backup,
                    lifecycle_kwargs={
                        "context_adapter_factories": e44._clean_goplus_context()
                    },
                    graduated_supply=supply,
                    stop_before_lifecycle=True,
                )

        assert captured_mints == selected_mints
        assert "mint-report-only-alternate-c" not in captured_mints
        assert "mint-report-only-alternate-d" not in captured_mints


def test_tracking_requalification_still_requires_explicit_holder_evidence():
    source = inspect.getsource(
        combined_executor.CombinedPumpfunCampaignExecutor._handoff_one_slot
    )
    assert 'holder_fact.get("eligible") is True' in source
    assert 'holder_fact.get("tracking_requalification_required") is True' in source
