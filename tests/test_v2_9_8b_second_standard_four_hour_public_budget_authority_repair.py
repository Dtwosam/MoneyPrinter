"""Focused offline proof for the second standard-four-hour public budget authority repair.

One canonical lifecycle arithmetic owner must be the only source of standard
worst-case capacity. The public standard contract, the public command policy,
the standard preflight projection, the immutable campaign configuration, and the
one-shot authorization document must all project exactly that derived truth.
"""

from __future__ import annotations

import inspect
import unittest
from unittest import mock

from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import operational_standard_4h as standard
from printer_v1.operator_cli import standard_four_hour_one_shot_wrapper as wrapper
from printer_v1.operator_cli.one_token_4h_runtime import (
    standard_campaign_lifecycle_budget,
)
from printer_v1.sources.measured_transport import (
    FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT,
    LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND,
)


WORST_CASE_LANES = ("TRACK_FAST", "TRACK_FAST")
WORST_CASE_MASK = (True, True)
EXPECTED_REQUEST_OUTER_CEILING = 236
EXPECTED_REQUESTS_PER_TOKEN = 117
EXPECTED_SCHEDULER_OUTER_CEILING = 210

_FIXTURE_DATABASE = {
    "path": "/tmp/printer.sqlite3",
    "sha256": "b" * 64,
    "size": 1,
    "inode": 1,
    "mtime_ns": 1,
    "migration_count": 54,
    "migration_head": "054_pre_lifecycle_discovery_refresh_wait.sql",
}


def _canonical_worst_case() -> dict:
    return standard_campaign_lifecycle_budget(WORST_CASE_LANES, WORST_CASE_MASK)


class CanonicalArithmeticOwnerTests(unittest.TestCase):
    def test_canonical_worst_case_lifecycle_is_236_over_210(self) -> None:
        budget = _canonical_worst_case()
        self.assertEqual(budget["request_ceiling"], EXPECTED_REQUEST_OUTER_CEILING)
        self.assertEqual(budget["scheduler_ceiling"], EXPECTED_SCHEDULER_OUTER_CEILING)

    def test_per_token_non_shared_contribution_divides_exactly_to_117(self) -> None:
        budget = _canonical_worst_case()
        shared = int(budget["request_components"]["discovery"])
        self.assertEqual(shared, 2)
        non_shared = int(budget["request_ceiling"]) - shared
        self.assertEqual(non_shared % standard.TOKEN_CAPACITY, 0)
        self.assertEqual(
            non_shared // standard.TOKEN_CAPACITY, EXPECTED_REQUESTS_PER_TOKEN
        )

    def test_fresh_first_hour_safety_reservation_is_not_stale_15m_fallback(self) -> None:
        self.assertEqual(FIRST_HOUR_SAFETY_CONTEXT_REQUEST_COUNT, 3)
        self.assertEqual(
            LIFECYCLE_RESERVED_OPERATIONS_BY_STEP_KIND["CONTINUATION_CLOSE"], 4
        )
        components = _canonical_worst_case()["request_components"]
        self.assertEqual(components["token_1_window_1h_safety_context"], 3)
        self.assertEqual(components["token_2_window_1h_safety_context"], 3)

    def test_mixed_and_no_continuation_budgets_are_unchanged(self) -> None:
        expected = {
            (("TRACK_FAST", "TRACK_NORMAL"), (True, True)): (188, 162),
            (("TRACK_NORMAL", "TRACK_NORMAL"), (True, True)): (140, 114),
            (("TRACK_FAST", "TRACK_FAST"), (False, False)): (98, 82),
        }
        for (lanes, mask), (requests, scheduler) in expected.items():
            with self.subTest(lanes=lanes, mask=mask):
                budget = standard_campaign_lifecycle_budget(lanes, mask)
                self.assertEqual(budget["request_ceiling"], requests)
                self.assertEqual(budget["scheduler_ceiling"], scheduler)


class PublicStandardCapacityContractTests(unittest.TestCase):
    def test_public_contract_helper_is_derived_and_deterministic(self) -> None:
        self.assertTrue(
            hasattr(standard, "standard_four_hour_capacity_contract"),
            "public standard capacity contract owner is missing",
        )
        contract = standard.standard_four_hour_capacity_contract()
        self.assertEqual(
            contract["lifecycle_request_outer_ceiling"],
            EXPECTED_REQUEST_OUTER_CEILING,
        )
        self.assertEqual(
            contract["lifecycle_requests_per_token"], EXPECTED_REQUESTS_PER_TOKEN
        )
        self.assertEqual(
            contract["lifecycle_scheduler_outer_ceiling"],
            EXPECTED_SCHEDULER_OUTER_CEILING,
        )
        self.assertEqual(contract, standard.standard_four_hour_capacity_contract())

    def test_public_contract_equals_canonical_arithmetic_owner(self) -> None:
        budget = _canonical_worst_case()
        contract = standard.standard_four_hour_capacity_contract()
        self.assertEqual(
            contract["lifecycle_request_outer_ceiling"], budget["request_ceiling"]
        )
        self.assertEqual(
            contract["lifecycle_scheduler_outer_ceiling"], budget["scheduler_ceiling"]
        )

    def test_public_module_constants_are_the_derived_contract(self) -> None:
        self.assertEqual(
            standard.LIFECYCLE_REQUEST_OUTER_CEILING, EXPECTED_REQUEST_OUTER_CEILING
        )
        self.assertEqual(
            standard.LIFECYCLE_REQUESTS_PER_TOKEN, EXPECTED_REQUESTS_PER_TOKEN
        )
        self.assertEqual(
            standard.LIFECYCLE_SCHEDULER_OUTER_CEILING,
            EXPECTED_SCHEDULER_OUTER_CEILING,
        )

    def test_public_policy_contract_projects_the_same_capacity(self) -> None:
        contract = standard.standard_four_hour_policy_contract()
        self.assertEqual(
            contract["lifecycle_request_outer_ceiling"],
            EXPECTED_REQUEST_OUTER_CEILING,
        )
        self.assertEqual(
            contract["lifecycle_requests_per_token"], EXPECTED_REQUESTS_PER_TOKEN
        )
        self.assertEqual(
            contract["lifecycle_scheduler_outer_ceiling"],
            EXPECTED_SCHEDULER_OUTER_CEILING,
        )

    def test_capacity_derivation_touches_no_source_db_or_scheduler(self) -> None:
        source = inspect.getsource(standard.standard_four_hour_capacity_contract)
        for forbidden in (
            "sqlite3",
            ".execute(",
            "urlopen",
            "os.environ",
            "getenv",
            "subprocess",
            "socket",
            "Path(",
        ):
            self.assertNotIn(forbidden, source)


class PublicCommandProjectionTests(unittest.TestCase):
    def test_command_standard_policy_equals_derived_public_contract(self) -> None:
        contract = standard.standard_four_hour_capacity_contract()
        policy = command.STANDARD_FOUR_HOUR_POLICY
        self.assertEqual(
            policy.governed_request_ceiling,
            contract["lifecycle_request_outer_ceiling"],
        )
        self.assertEqual(
            policy.governed_requests_per_token,
            contract["lifecycle_requests_per_token"],
        )
        self.assertEqual(
            policy.scheduler_row_ceiling,
            contract["lifecycle_scheduler_outer_ceiling"],
        )
        self.assertEqual(
            policy.governed_request_ceiling, EXPECTED_REQUEST_OUTER_CEILING
        )
        self.assertEqual(
            policy.governed_requests_per_token, EXPECTED_REQUESTS_PER_TOKEN
        )
        self.assertEqual(
            policy.scheduler_row_ceiling, EXPECTED_SCHEDULER_OUTER_CEILING
        )

    def test_command_module_constants_carry_the_same_truth(self) -> None:
        self.assertEqual(
            command.STANDARD_FOUR_HOUR_GOVERNED_REQUEST_CEILING,
            EXPECTED_REQUEST_OUTER_CEILING,
        )
        self.assertEqual(
            command.STANDARD_FOUR_HOUR_GOVERNED_REQUESTS_PER_TOKEN,
            EXPECTED_REQUESTS_PER_TOKEN,
        )
        self.assertEqual(
            command.STANDARD_FOUR_HOUR_SCHEDULER_ROW_CEILING,
            EXPECTED_SCHEDULER_OUTER_CEILING,
        )

    def test_standard_preflight_projects_the_derived_contract(self) -> None:
        base = {
            "status": "V2_9_8_OPERATIONAL_PREFLIGHT_READY",
            "database_path": "/tmp/fake.sqlite3",
            "database_sha256": "a" * 64,
            "policy": {"locked_windows": command.LOCKED_WINDOWS},
            "ceilings": {},
            "source_calls": 0,
            "scheduler_runtime_calls": 0,
            "database_writes": 0,
        }
        with mock.patch.object(
            command, "build_activation_preflight", return_value=base
        ):
            result = command.build_standard_four_hour_preflight()
        ceilings = result["standard_four_hour_ceilings"]
        self.assertEqual(
            ceilings["governed_requests"], EXPECTED_REQUEST_OUTER_CEILING
        )
        self.assertEqual(
            ceilings["governed_requests_per_token"], EXPECTED_REQUESTS_PER_TOKEN
        )
        self.assertEqual(ceilings["scheduler_rows"], EXPECTED_SCHEDULER_OUTER_CEILING)
        self.assertEqual(result["source_calls"], 0)
        self.assertEqual(result["database_writes"], 0)

    def test_immutable_campaign_configuration_projects_selected_policy(self) -> None:
        source = inspect.getsource(command._create_campaign_command)
        self.assertIn('"governed_requests": policy.governed_request_ceiling', source)
        self.assertIn(
            '"governed_requests_per_token": policy.governed_requests_per_token', source
        )
        self.assertIn('"scheduler_rows": policy.scheduler_row_ceiling', source)


class OneShotAuthorizationProjectionTests(unittest.TestCase):
    def test_wrapper_constants_equal_derived_public_contract(self) -> None:
        contract = standard.standard_four_hour_capacity_contract()
        self.assertEqual(
            wrapper.LIFECYCLE_REQUEST_OUTER_CEILING,
            contract["lifecycle_request_outer_ceiling"],
        )
        self.assertEqual(
            wrapper.LIFECYCLE_SCHEDULER_OUTER_CEILING,
            contract["lifecycle_scheduler_outer_ceiling"],
        )
        self.assertEqual(
            wrapper.LIFECYCLE_REQUEST_OUTER_CEILING, EXPECTED_REQUEST_OUTER_CEILING
        )
        self.assertEqual(
            wrapper.LIFECYCLE_SCHEDULER_OUTER_CEILING,
            EXPECTED_SCHEDULER_OUTER_CEILING,
        )

    def test_fresh_repaired_authorization_document_uses_236_over_210(self) -> None:
        document = wrapper.fixture_authorization_document(
            branch="agent/test", head="a" * 40, database=dict(_FIXTURE_DATABASE)
        )
        validated = wrapper.validate_standard_four_hour_authorization_document(document)
        campaign = validated["campaign_policy"]
        self.assertEqual(
            campaign["lifecycle_request_outer_ceiling"],
            EXPECTED_REQUEST_OUTER_CEILING,
        )
        self.assertEqual(
            campaign["lifecycle_scheduler_outer_ceiling"],
            EXPECTED_SCHEDULER_OUTER_CEILING,
        )

    def test_newly_constructed_stale_230_authorization_fails_closed(self) -> None:
        document = wrapper.fixture_authorization_document(
            branch="agent/test", head="a" * 40, database=dict(_FIXTURE_DATABASE)
        )
        stale = dict(document)
        stale["campaign_policy"] = dict(document["campaign_policy"])
        stale["campaign_policy"]["lifecycle_request_outer_ceiling"] = 230
        with self.assertRaises(wrapper.StandardFourHourOneShotWrapperError):
            wrapper.validate_standard_four_hour_authorization_document(stale)

    def test_scheduler_outer_ceiling_is_never_increased(self) -> None:
        self.assertEqual(
            _canonical_worst_case()["scheduler_ceiling"],
            EXPECTED_SCHEDULER_OUTER_CEILING,
        )
        for value in (
            standard.LIFECYCLE_SCHEDULER_OUTER_CEILING,
            command.STANDARD_FOUR_HOUR_SCHEDULER_ROW_CEILING,
            command.STANDARD_FOUR_HOUR_POLICY.scheduler_row_ceiling,
            wrapper.LIFECYCLE_SCHEDULER_OUTER_CEILING,
        ):
            self.assertEqual(value, EXPECTED_SCHEDULER_OUTER_CEILING)


class CrossOwnerExactEqualityTests(unittest.TestCase):
    def test_every_standard_owner_reports_one_identical_capacity(self) -> None:
        budget = _canonical_worst_case()
        contract = standard.standard_four_hour_capacity_contract()
        policy = command.STANDARD_FOUR_HOUR_POLICY
        document = wrapper.fixture_authorization_document(
            branch="agent/test", head="a" * 40, database=dict(_FIXTURE_DATABASE)
        )["campaign_policy"]
        requests = {
            "canonical": budget["request_ceiling"],
            "public_contract": contract["lifecycle_request_outer_ceiling"],
            "command_policy": policy.governed_request_ceiling,
            "wrapper_authorization": document["lifecycle_request_outer_ceiling"],
        }
        scheduler = {
            "canonical": budget["scheduler_ceiling"],
            "public_contract": contract["lifecycle_scheduler_outer_ceiling"],
            "command_policy": policy.scheduler_row_ceiling,
            "wrapper_authorization": document["lifecycle_scheduler_outer_ceiling"],
        }
        self.assertEqual(set(requests.values()), {EXPECTED_REQUEST_OUTER_CEILING})
        self.assertEqual(set(scheduler.values()), {EXPECTED_SCHEDULER_OUTER_CEILING})
        self.assertEqual(
            {
                contract["lifecycle_requests_per_token"],
                policy.governed_requests_per_token,
            },
            {EXPECTED_REQUESTS_PER_TOKEN},
        )


if __name__ == "__main__":
    unittest.main()
