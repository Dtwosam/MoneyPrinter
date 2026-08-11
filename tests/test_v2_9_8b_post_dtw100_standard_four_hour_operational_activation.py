from __future__ import annotations

import importlib
import inspect
import unittest

from printer_v1.contracts.enums import DataQualityLabel
from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.memory.contracts import (
    MemoryQualityLabel,
    MemoryWindowKind,
    MemoryWindowStatus,
)
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import one_token_4h_runtime as four_hour
from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import window_15m_child_terminal as child_terminal
from printer_v1.scheduler.token_local_continuation import (
    CampaignContinuationContext,
    ExpectedTokenContinuationIdentity,
    TokenContinuationInput,
)
from printer_v1.safety.composite import SAFETY_CONTEXT_ACCEPTABLE
from printer_v1.snapshots.cadence_policy import get_policy
from printer_v1.snapshots.lifecycle_continuity import CONTINUITY_CONTINUOUS


class StandardFourHourOperationalActivationContracts(unittest.TestCase):
    def _token(
        self,
        slot: str,
        token_id: str,
        *,
        clean: bool = True,
    ) -> TokenContinuationInput:
        predecessor_id = f"cw:{slot}:1h"
        expected = ExpectedTokenContinuationIdentity(
            token_slot_id=slot,
            token_id=token_id,
            mint_id=f"mint:{token_id}",
            pair_id=f"pair:{token_id}",
            lifecycle_id=f"life:{token_id}",
            predecessor_window_id=predecessor_id,
        )
        return TokenContinuationInput(
            campaign_id="campaign:standard-4h",
            configuration_id="config:standard-4h",
            token_slot_id=slot,
            token_id=token_id,
            mint_id=f"mint:{token_id}",
            pair_id=f"pair:{token_id}",
            lifecycle_id=f"life:{token_id}",
            predecessor_window_id=predecessor_id,
            expected_identity=expected,
            predecessor_window_kind=MemoryWindowKind.WINDOW_1H,
            successor_window_kind=MemoryWindowKind.WINDOW_4H,
            predecessor_window_status=MemoryWindowStatus.WINDOW_CLOSED,
            predecessor_memory_quality=(
                MemoryQualityLabel.CLEAN_MEMORY
                if clean
                else MemoryQualityLabel.DIRTY_MEMORY
            ),
            predecessor_data_quality=(
                DataQualityLabel.CLEAN_DATA
                if clean
                else DataQualityLabel.DIRTY_DATA
            ),
            predecessor_do_not_train=not clean,
            predecessor_evidence_eligible=clean,
            predecessor_complete=True,
            freshness_within_contract=True,
            governed_provenance_traceable=True,
            safety_context_present=True,
            safety_context_result=SAFETY_CONTEXT_ACCEPTABLE,
            continuity_status=CONTINUITY_CONTINUOUS,
            learning_need=None,
            token_budget_available=True,
            token_state=TokenLifecycleState.TRACK_FAST,
        )

    def test_public_standard_four_hour_policy_is_explicit_and_bounded(self):
        self.assertEqual(command.STANDARD_FOUR_HOUR_MODE, "standard-four-hour-run")
        self.assertEqual(
            command.STANDARD_FOUR_HOUR_PREFLIGHT_MODE,
            "standard-four-hour-preflight",
        )
        policy = command.STANDARD_FOUR_HOUR_POLICY
        self.assertEqual(policy.duration_seconds, 14_700)
        self.assertEqual(policy.pre_lifecycle_acquisition_duration_seconds, 900)
        self.assertEqual(policy.governed_request_ceiling, 230)
        self.assertEqual(policy.governed_requests_per_token, 114)
        self.assertEqual(policy.scheduler_row_ceiling, 210)
        self.assertEqual(policy.locked_windows, ("WINDOW_12H", "WINDOW_24H"))
        self.assertTrue(policy.selective_1h_continuation)
        self.assertTrue(policy.continuous_four_hour)
        self.assertTrue(policy.standard_four_hour_campaign)

    def test_authoritative_cadence_enables_only_four_hour_newly(self):
        for lane in ("TRACK_FAST", "TRACK_NORMAL"):
            four = get_policy("WINDOW_4H", lane)
            twelve = get_policy("WINDOW_12H", lane)
            twenty_four = get_policy("WINDOW_24H", lane)
            self.assertIsNotNone(four)
            self.assertIsNotNone(twelve)
            self.assertIsNotNone(twenty_four)
            self.assertTrue(four.enabled_for_real_collection)
            self.assertFalse(twelve.enabled_for_real_collection)
            self.assertFalse(twenty_four.enabled_for_real_collection)

    def test_four_hour_runtime_has_distinct_proof_and_standard_authority(self):
        authority = four_hour.FourHourExecutionAuthority
        self.assertEqual(authority.DISABLED.value, "DISABLED")
        self.assertEqual(authority.PROOF.value, "PROOF")
        self.assertEqual(authority.STANDARD_CAMPAIGN.value, "STANDARD_CAMPAIGN")
        parameters = inspect.signature(four_hour.plan_current_run_4h).parameters
        self.assertIn("execution_authority", parameters)

    def test_standard_campaign_gate_is_exact_two_token_and_token_local(self):
        module = importlib.import_module(
            "printer_v1.operator_cli.operational_standard_4h"
        )
        campaign = CampaignContinuationContext(
            campaign_id="campaign:standard-4h",
            configuration_id="config:standard-4h",
        )
        results = module.evaluate_standard_four_hour_eligibility(
            campaign=campaign,
            tokens=(
                self._token("slot:1", "token:1", clean=True),
                self._token("slot:2", "token:2", clean=False),
            ),
        )
        eligible = tuple(
            result.token_slot_id
            for result in results
            if result.verdict.value == "CONTINUE_TO_WINDOW_4H"
        )
        self.assertEqual(eligible, ("slot:1",))
        self.assertEqual(len(eligible), 1)
        self.assertEqual(
            {result.token_slot_id: result.verdict.value for result in results},
            {
                "slot:1": "CONTINUE_TO_WINDOW_4H",
                "slot:2": "BLOCK_CONTINUATION",
            },
        )

    def test_standard_campaign_gate_rejects_any_stop_verdict_as_policy_drift(self):
        module = importlib.import_module(
            "printer_v1.operator_cli.operational_standard_4h"
        )
        self.assertTrue(hasattr(module, "StandardFourHourOperationalError"))
        campaign = CampaignContinuationContext(
            campaign_id="campaign:standard-4h",
            configuration_id="config:standard-4h",
        )
        results = module.evaluate_standard_four_hour_eligibility(
            campaign=campaign,
            tokens=(
                self._token("slot:1", "token:1", clean=True),
                self._token("slot:2", "token:2", clean=False),
            ),
        )
        # The post-DTW100 first-four-hour policy has only CONTINUE or BLOCK.
        self.assertNotIn(
            "STOP_AFTER_WINDOW_1H",
            {result.verdict.value for result in results},
        )

    def test_standard_one_shot_wrapper_is_distinct_from_ordinary_15m(self):
        wrapper = importlib.import_module(
            "printer_v1.operator_cli.standard_four_hour_one_shot_wrapper"
        )
        self.assertEqual(
            wrapper.WRAPPER_SCHEMA_VERSION,
            "PRINTER_V1_STANDARD_FOUR_HOUR_ONE_SHOT_WRAPPER_V1",
        )
        self.assertEqual(wrapper.AUTHORIZED_COMMAND_MODE, "standard-four-hour-run")
        self.assertNotEqual(
            wrapper.WRAPPER_SCHEMA_VERSION,
            "PRINTER_V1_WINDOW_15M_ONE_SHOT_WRAPPER_V1",
        )

    def test_standard_authorization_document_has_distinct_exact_contract(self):
        wrapper = importlib.import_module(
            "printer_v1.operator_cli.standard_four_hour_one_shot_wrapper"
        )
        document = wrapper.fixture_authorization_document(
            branch="agent/test",
            head="a" * 40,
            database={
                "path": "/tmp/printer.sqlite3",
                "sha256": "b" * 64,
                "size": 1,
                "inode": 1,
                "mtime_ns": 1,
                "migration_count": 54,
                "migration_head": "054_pre_lifecycle_discovery_refresh_wait.sql",
            },
        )
        validated = wrapper.validate_standard_four_hour_authorization_document(document)
        self.assertEqual(validated["authorized_command"]["mode"], "standard-four-hour-run")
        self.assertEqual(validated["campaign_policy"]["post_supply_duration_seconds"], 14_700)
        self.assertEqual(validated["campaign_policy"]["pre_lifecycle_duration_seconds"], 900)
        self.assertEqual(validated["campaign_policy"]["lifecycle_request_outer_ceiling"], 230)
        self.assertEqual(validated["campaign_policy"]["lifecycle_scheduler_outer_ceiling"], 210)
        self.assertEqual(
            validated["campaign_policy"]["eligibility_contract_version"],
            "STANDARD_4H_ELIGIBILITY_V1",
        )
        self.assertEqual(
            validated["campaign_policy"]["locked_windows"],
            ["WINDOW_12H", "WINDOW_24H"],
        )

        wrong = dict(document)
        wrong["authorized_command"] = dict(document["authorized_command"])
        wrong["authorized_command"]["mode"] = "run"
        with self.assertRaises(wrapper.StandardFourHourOneShotWrapperError):
            wrapper.validate_standard_four_hour_authorization_document(wrong)

    def test_git_authorization_has_distinct_standard_four_hour_profile(self):
        profile = git_auth.STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE
        self.assertEqual(profile.command_mode, "standard-four-hour-run")
        self.assertEqual(
            profile.authorization_package_root,
            "operator-runs/v2-9-8b-standard-four-hour-final-authorization",
        )
        self.assertEqual(
            profile.authorization_package_kind,
            "STANDARD_FOUR_HOUR_AUTHORIZATION_EVIDENCE",
        )
        self.assertNotEqual(profile.manifest_schema_version, git_auth.MANIFEST_SCHEMA_VERSION)

    def test_child_terminal_supports_standard_four_hour_without_changing_run(self):
        self.assertEqual(
            child_terminal.CHILD_TERMINAL_SCHEMA_VERSION,
            "PRINTER_V1_WINDOW_15M_CHILD_TERMINAL_V1",
        )
        self.assertIn("run", child_terminal.CHILD_TERMINAL_MODE_SCHEMAS)
        self.assertEqual(
            child_terminal.CHILD_TERMINAL_MODE_SCHEMAS["standard-four-hour-run"],
            "PRINTER_V1_STANDARD_FOUR_HOUR_CHILD_TERMINAL_V1",
        )

    def test_standard_subset_budget_becomes_real_only_for_nonzero_eligible(self):
        none = four_hour.standard_campaign_lifecycle_budget(
            ("TRACK_FAST", "TRACK_NORMAL"), (False, False)
        )
        one = four_hour.standard_campaign_lifecycle_budget(
            ("TRACK_FAST", "TRACK_NORMAL"), (True, False)
        )
        both = four_hour.standard_campaign_lifecycle_budget(
            ("TRACK_FAST", "TRACK_NORMAL"), (True, True)
        )
        self.assertFalse(none["real_collection_enabled"])
        self.assertTrue(one["real_collection_enabled"])
        self.assertTrue(both["real_collection_enabled"])
        self.assertEqual((none["request_ceiling"], none["scheduler_ceiling"]), (80, 64))
        self.assertEqual((one["request_ceiling"], one["scheduler_ceiling"]), (149, 128))
        self.assertEqual((both["request_ceiling"], both["scheduler_ceiling"]), (188, 162))


if __name__ == "__main__":
    unittest.main()
