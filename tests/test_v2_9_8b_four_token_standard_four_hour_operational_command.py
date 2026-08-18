"""Focused contract for the new operational four-token 4/2/2 command boundary.

Offline only. No campaign runs here: the canonical coordinator is patched so the
tests observe exactly which composition the mode constructs and how many times it
calls the one canonical factory path. No authorization is created or consumed, no
source is called, and no authoritative database is touched.
"""

from __future__ import annotations

import inspect
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import git_provenance_authorization_manifest as git_auth
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli import four_token_operational_composition as operational
from printer_v1.operator_cli import (
    four_token_proof_one_shot_wrapper as proof_authority,
)
from printer_v1.operator_cli import (
    four_token_standard_four_hour_one_shot_wrapper as operational_authority,
)
from printer_v1.operator_cli.four_token_factory_adapter import (
    FourTokenFactoryAdapterError,
)
from printer_v1.operator_cli.four_token_proof_integration import (
    FourTokenProofController,
    build_four_token_proof_policy,
)
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    scaled_standard_four_hour_capacity_contract,
)
from printer_v1.operator_cli.window_15m_child_terminal import (
    CHILD_TERMINAL_MODE_SCHEMAS,
)


class CommandSeparationTests(unittest.TestCase):
    """The three authorities stay exactly three distinct authorities."""

    def test_three_distinct_modes(self) -> None:
        self.assertEqual(
            command.STANDARD_FOUR_HOUR_MODE, "standard-four-hour-run"
        )
        self.assertEqual(
            command.FOUR_TOKEN_PROOF_MODE,
            "four-token-bounded-capacity-proof-run",
        )
        self.assertEqual(
            command.FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE,
            "four-token-standard-four-hour-run",
        )
        modes = {
            command.STANDARD_FOUR_HOUR_MODE,
            command.FOUR_TOKEN_PROOF_MODE,
            command.FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE,
        }
        self.assertEqual(len(modes), 3)

    def test_standard_four_hour_remains_two_token_authority(self) -> None:
        policy = command.STANDARD_FOUR_HOUR_POLICY
        self.assertEqual(policy.mode, "standard-four-hour-run")
        self.assertEqual(command.TOKEN_CAPACITY, 2)
        base = command._STANDARD_FOUR_HOUR_CAPACITY
        # The two-token authority keeps the unscaled canonical arithmetic.
        self.assertEqual(
            policy.governed_request_ceiling,
            int(base["lifecycle_request_outer_ceiling"]),
        )
        self.assertEqual(
            policy.scheduler_row_ceiling,
            int(base["lifecycle_scheduler_outer_ceiling"]),
        )
        self.assertEqual(
            policy.duration_seconds,
            command.STANDARD_FOUR_HOUR_TOTAL_DURATION_SECONDS,
        )
        self.assertEqual(
            policy.policy_version, "V2-9.8-STANDARD-4H-OPERATIONAL-V1"
        )
        self.assertNotIn(
            "four_token_proof_controller",
            inspect.signature(command.run_standard_four_hour_campaign).parameters,
        )

    def test_proof_mode_remains_proof_only(self) -> None:
        self.assertEqual(
            proof_authority.POLICY_VERSION,
            "V2-9.8B-FOUR-TOKEN-BOUNDED-CAPACITY-PROOF-V1",
        )
        self.assertEqual(
            command.FOUR_TOKEN_PROOF_POLICY.policy_version,
            proof_authority.POLICY_VERSION,
        )
        self.assertNotEqual(
            proof_authority.POLICY_VERSION, operational.POLICY_VERSION
        )
        self.assertNotEqual(
            proof_authority.AUTHORIZED_COMMAND_MODE,
            operational_authority.AUTHORIZED_COMMAND_MODE,
        )
        self.assertNotEqual(
            proof_authority.APPLICATION_ROOT,
            operational_authority.APPLICATION_ROOT,
        )
        self.assertNotEqual(
            proof_authority.FINAL_AUTHORIZATION_SCHEMA_VERSION,
            operational_authority.FINAL_AUTHORIZATION_SCHEMA_VERSION,
        )

    def test_new_operational_mode_is_registered_everywhere_required(self) -> None:
        mode = command.FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE
        self.assertIn(mode, command.GIT_PROVENANCE_MANIFEST_SUPPORTED_MODES)
        self.assertIn(mode, command._WRAPPER_BOUND_MODE_LABELS)
        self.assertIn(mode, CHILD_TERMINAL_MODE_SCHEMAS)
        self.assertEqual(
            CHILD_TERMINAL_MODE_SCHEMAS[mode],
            "PRINTER_V1_FOUR_TOKEN_STANDARD_FOUR_HOUR_CHILD_TERMINAL_V1",
        )
        # Every child-terminal schema stays distinct per authority.
        self.assertEqual(
            len(set(CHILD_TERMINAL_MODE_SCHEMAS.values())),
            len(CHILD_TERMINAL_MODE_SCHEMAS),
        )

    def test_new_mode_routes_to_its_own_authorization_profile(self) -> None:
        env = {
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[0]: "/tmp/manifest.json",
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[1]: "a" * 64,
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[2]: "/tmp/marker.json",
            command.GIT_PROVENANCE_MANIFEST_ENV_VARS[3]: "b" * 64,
        }
        sentinel = object()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            command, "validate_git_provenance_authorization", return_value=sentinel
        ) as validator:
            result = command._resolve_git_provenance_authorization(
                command.FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE,
                environ=env,
                repository_root=tmp,
            )
        self.assertIs(result, sentinel)
        self.assertEqual(
            validator.call_args.kwargs["profile"],
            git_auth.FOUR_TOKEN_STANDARD_FOUR_HOUR_AUTHORIZATION_PROFILE,
        )

    def test_direct_child_invocation_without_wrapper_fails_closed(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            exit_code = command.main([command.FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE])
        self.assertEqual(exit_code, 1)

    def test_new_mode_is_not_a_capacity_selector(self) -> None:
        signature = inspect.signature(
            command.run_four_token_standard_four_hour_campaign
        )
        for forbidden in (
            "token_capacity",
            "configured_through_4h_tokens",
            "max_tokens",
            "cycles",
            "four_token_proof_controller",
            "policy",
        ):
            self.assertNotIn(forbidden, signature.parameters, forbidden)
        parser_source = inspect.getsource(command.main)
        self.assertNotIn("--max-tokens", parser_source)
        self.assertNotIn("--cycles", parser_source)


class CapacityDerivationTests(unittest.TestCase):
    """4/2/2 must be derived from the one canonical contract, never copied."""

    def setUp(self) -> None:
        self.contract = scaled_standard_four_hour_capacity_contract(4)

    def test_operational_capacity_is_the_derived_contract(self) -> None:
        self.assertEqual(operational.OPERATIONAL_CAPACITY, self.contract)
        self.assertEqual(operational.CONFIGURED_THROUGH_4H_TOKENS, 4)
        self.assertEqual(operational.CONFIGURED_ACTIVE_CYCLES, 2)
        self.assertEqual(operational.TOKENS_PER_CYCLE, 2)
        self.assertEqual(operational.TOTAL_CYCLE_ADMISSION_CEILING, 2)
        self.assertEqual(operational.LIFECYCLE_REQUESTS_PER_TOKEN, 117)
        self.assertEqual(operational.LIFECYCLE_REQUEST_OUTER_CEILING, 472)
        self.assertEqual(operational.LIFECYCLE_SCHEDULER_OUTER_CEILING, 420)
        self.assertEqual(
            operational.MINIMUM_CYCLE_ADMISSION_SPACING_SECONDS, 300
        )

    def test_derivation_is_live_not_a_literal(self) -> None:
        """Patching the canonical contract must move the derived policy."""
        widened = dict(self.contract)
        widened["lifecycle_requests_per_token"] = 999
        with mock.patch.object(
            operational,
            "OPERATIONAL_CAPACITY",
            widened,
        ), mock.patch.object(
            operational, "LIFECYCLE_REQUESTS_PER_TOKEN", 999
        ):
            self.assertEqual(
                operational.exact_operational_policy()[
                    "lifecycle_requests_per_token"
                ],
                999,
            )
        # And is restored, so no test mutates the real authority.
        self.assertEqual(
            operational.exact_operational_policy()[
                "lifecycle_requests_per_token"
            ],
            117,
        )

    def test_operational_policy_shape_is_the_exact_contract(self) -> None:
        policy = operational.exact_operational_policy()
        self.assertEqual(
            policy["policy_version"],
            "V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1",
        )
        self.assertEqual(policy["configured_through_4h_tokens"], 4)
        self.assertEqual(policy["configured_active_cycles"], 2)
        self.assertEqual(policy["total_cycle_admission_ceiling"], 2)
        self.assertEqual(policy["tokens_per_cycle"], 2)
        self.assertEqual(policy["automatic_retries"], 0)
        self.assertIs(policy["endpoint_rotation"], False)
        self.assertIs(policy["long_windows_activated"], False)
        self.assertEqual(policy["root_main_window"], "WINDOW_15M")
        self.assertEqual(
            policy["locked_windows"], ["WINDOW_12H", "WINDOW_24H"]
        )

    def test_command_policy_projects_the_derived_ceilings(self) -> None:
        policy = command.FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY
        self.assertEqual(
            policy.mode, command.FOUR_TOKEN_STANDARD_FOUR_HOUR_MODE
        )
        self.assertIs(policy.standard_four_hour_campaign, True)
        self.assertIs(policy.continuous_four_hour, True)
        self.assertEqual(
            policy.governed_request_ceiling,
            operational.LIFECYCLE_REQUEST_OUTER_CEILING,
        )
        self.assertEqual(
            policy.governed_requests_per_token,
            operational.LIFECYCLE_REQUESTS_PER_TOKEN,
        )
        self.assertEqual(
            policy.scheduler_row_ceiling,
            operational.LIFECYCLE_SCHEDULER_OUTER_CEILING,
        )
        self.assertEqual(
            policy.duration_seconds,
            operational.POST_SUPPLY_LIFECYCLE_DURATION_SECONDS,
        )
        self.assertEqual(
            policy.pre_lifecycle_acquisition_duration_seconds,
            operational.PRE_LIFECYCLE_ACQUISITION_DURATION_SECONDS,
        )

    def test_widening_beyond_two_cycles_is_rejected(self) -> None:
        for bad in (1, 3, 5):
            with self.assertRaises(ValueError):
                scaled_standard_four_hour_capacity_contract(bad)
        # Six tokens remain an implementation ceiling, never this authority.
        self.assertEqual(
            operational.exact_operational_policy()[
                "configured_through_4h_tokens"
            ],
            4,
        )


class CanonicalCompositionTests(unittest.TestCase):
    """The new mode must enter the one repaired composition, not a second one."""

    def test_mode_calls_the_one_canonical_factory_path_once(self) -> None:
        authorization = object()
        with mock.patch.object(
            command, "_run_operational_campaign", return_value={"ok": True}
        ) as coordinator:
            result = command.run_four_token_standard_four_hour_campaign(
                operator_approved=True,
                git_provenance_authorization=authorization,
            )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(coordinator.call_count, 1)
        kwargs = coordinator.call_args.kwargs
        self.assertIs(
            kwargs["policy"], command.FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY
        )
        self.assertIs(kwargs["git_provenance_authorization"], authorization)
        controller = kwargs["four_token_proof_controller"]
        # Exactly the repaired canonical multi-cycle composition, unchanged.
        self.assertIsInstance(controller, FourTokenProofController)
        self.assertEqual(controller.policy, build_four_token_proof_policy())

    def test_facade_returns_the_canonical_repaired_controller(self) -> None:
        controller = operational.build_operational_multi_cycle_controller()
        self.assertIsInstance(controller, FourTokenProofController)
        self.assertEqual(controller.policy, build_four_token_proof_policy())
        self.assertEqual(
            controller.policy.configured_through_4h_token_ceiling, 4
        )
        self.assertEqual(controller.policy.configured_active_cycle_ceiling, 2)
        self.assertEqual(controller.policy.total_cycle_admission_ceiling, 2)
        self.assertEqual(
            controller.policy.min_admission_spacing_seconds,
            operational.MINIMUM_CYCLE_ADMISSION_SPACING_SECONDS,
        )

    def test_no_second_runner_scheduler_or_source_governor_is_declared(
        self,
    ) -> None:
        source = inspect.getsource(operational)
        for forbidden in (
            "class .*Scheduler",
            "class .*SourceGovernor",
            "class .*Factory",
            "def run_memory_factory",
        ):
            self.assertNotRegex(source, forbidden)


class WindowLawTests(unittest.TestCase):
    def test_main_lifecycle_windows_only(self) -> None:
        self.assertEqual(
            operational.MAIN_LIFECYCLE_WINDOWS,
            ("WINDOW_15M", "WINDOW_1H", "WINDOW_4H"),
        )
        self.assertEqual(operational.ROOT_MAIN_WINDOW, "WINDOW_15M")

    def test_5m_is_support_only(self) -> None:
        self.assertEqual(
            operational.SUPPORT_ONLY_WINDOW, "WINDOW_5M_MICRO_EVENT"
        )
        self.assertNotIn(
            operational.SUPPORT_ONLY_WINDOW, operational.MAIN_LIFECYCLE_WINDOWS
        )

    def test_long_windows_remain_locked(self) -> None:
        self.assertEqual(
            operational.LOCKED_WINDOWS, ("WINDOW_12H", "WINDOW_24H")
        )
        self.assertEqual(
            command.FOUR_TOKEN_STANDARD_FOUR_HOUR_POLICY.locked_windows,
            ("WINDOW_12H", "WINDOW_24H"),
        )
        policy = operational.exact_operational_policy()
        self.assertIs(policy["long_windows_activated"], False)
        for window in ("WINDOW_12H", "WINDOW_24H"):
            self.assertIn(window, policy["locked_windows"])


def _seed_token_and_pair(
    connection: sqlite3.Connection, *, row_id: int, stamp: str
) -> None:
    """Seed one disposable Solana token/pair identity pair. Fixture state only."""
    connection.execute(
        """INSERT INTO printer_tokens(id,token_mint,chain,created_at,updated_at)
           VALUES(?,?,'solana',?,?)""",
        (row_id, f"mint-{row_id}", stamp, stamp),
    )
    connection.execute(
        """INSERT INTO printer_pairs(
               id,token_id,pair_address,created_at,updated_at)
           VALUES(?,?,?,?,?)""",
        (row_id, row_id, f"pair-{row_id}", stamp, stamp),
    )


def _seed_first_cycle(connection: sqlite3.Connection, *, admitted_at: str) -> None:
    """Seed one disposable RUNNING campaign/run/cycle. Fixture state only."""
    connection.execute(
        """INSERT INTO printer_memory_factory_campaigns(
               campaign_id,campaign_state,db_mode,db_target_identity,
               policy_version,created_at,updated_at)
           VALUES('c1','RUNNING','OPERATIONAL_PERSISTENT','disposable',
                  'V2-9.8B-FOUR-TOKEN-STANDARD-4H-OPERATIONAL-V1',?,?)""",
        (admitted_at, admitted_at),
    )
    connection.execute(
        """INSERT INTO printer_memory_factory_campaign_runs(
               run_id,campaign_id,run_ordinal,run_state,authoritative_run_id,
               created_at,updated_at)
           VALUES('r1','c1',1,'RUNNING','f1',?,?)""",
        (admitted_at, admitted_at),
    )
    connection.execute(
        """INSERT INTO printer_memory_factory_campaign_cycles(
               cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
               created_at,updated_at)
           VALUES('cy1','c1','r1',1,'TRACKING',?,?)""",
        (admitted_at, admitted_at),
    )


class CycleTwoIdentityTests(unittest.TestCase):
    """Cycle 2 must be fresh distinct supply, never Cycle-1 carry-forward."""

    def test_operational_mode_reuses_the_repaired_identity_guard(self) -> None:
        self.assertIs(
            operational.validate_later_cycle_atomic_activation,
            __import__(
                "printer_v1.operator_cli.four_token_factory_adapter",
                fromlist=["validate_second_cycle_atomic_activation"],
            ).validate_second_cycle_atomic_activation,
        )

    def test_carry_forward_of_cycle_one_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/cycle-identity.sqlite3"
            apply_migrations(path)
            connection = sqlite3.connect(path)
            connection.row_factory = sqlite3.Row
            try:
                now = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
                stamp = now.isoformat()
                _seed_first_cycle(connection, admitted_at=stamp)
                for row_id in (11, 12, 21, 22):
                    _seed_token_and_pair(
                        connection, row_id=row_id, stamp=stamp
                    )
                later = (now + timedelta(seconds=600)).isoformat()
                connection.execute(
                    """INSERT INTO printer_memory_factory_campaign_cycles(
                           cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
                           created_at,updated_at)
                       VALUES('cy1-2','c1','r1',2,'TRACKING',?,?)""",
                    (later, later),
                )
                for cycle, ordinals, token_base in (
                    ("cy1", (1, 2), 10),
                    ("cy1-2", (1, 2), 10),  # deliberate Cycle-1 identity reuse
                ):
                    for ordinal in ordinals:
                        connection.execute(
                            """INSERT INTO
                               printer_memory_factory_campaign_token_slots(
                                   token_slot_id,campaign_id,run_id,cycle_id,
                                   slot_ordinal,token_identity,token_row_id,
                                   pair_row_id,mint_identity,pair_identity,
                                   lifecycle_identity,token_state,
                                   created_at,updated_at)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,'SELECTED',?,?)""",
                            (
                                f"{cycle}-slot-{ordinal}",
                                "c1",
                                "r1",
                                cycle,
                                ordinal,
                                f"token-{token_base + ordinal}",
                                token_base + ordinal,
                                token_base + ordinal,
                                f"mint-{token_base + ordinal}",
                                f"pair-{token_base + ordinal}",
                                f"life-{cycle}-{ordinal}",
                                stamp,
                                stamp,
                            ),
                        )
                connection.commit()
                with self.assertRaises(FourTokenFactoryAdapterError) as caught:
                    operational.validate_later_cycle_atomic_activation(
                        connection,
                        campaign_id="c1",
                        campaign_run_id="r1",
                        factory_run_id="f1",
                        cycle_id="cy1-2",
                    )
                self.assertIn("duplicates the first cycle", str(caught.exception))
            finally:
                connection.close()


class GovernanceOwnershipTests(unittest.TestCase):
    """No Source Governor or Central Scheduler bypass may be introduced."""

    def test_facade_declares_no_source_or_scheduler_work(self) -> None:
        source = inspect.getsource(operational)
        for forbidden in (
            "requests.",
            "urllib",
            "websocket",
            "aiohttp",
            "httpx",
            "sqlite3.connect",
            "INSERT INTO",
            "UPDATE ",
            "DELETE FROM",
        ):
            self.assertNotIn(forbidden, source, forbidden)

    def test_wrapper_declares_no_source_or_scheduler_work(self) -> None:
        source = inspect.getsource(operational_authority)
        for forbidden in (
            "requests.",
            "urllib.request",
            "websocket",
            "aiohttp",
            "httpx",
            "INSERT INTO",
            "UPDATE ",
            "DELETE FROM",
        ):
            self.assertNotIn(forbidden, source, forbidden)

    def test_no_forbidden_capability_vocabulary_is_introduced(self) -> None:
        for module in (operational, operational_authority):
            source = inspect.getsource(module).lower()
            for forbidden in (
                "confidence",
                "ranking",
                "embedding",
                "private_key",
                "wallet",
                "pnl",
                "buy_sell",
                "window_12h",
                "window_24h_active",
                "migration 059",
                "059_",
            ):
                if forbidden in ("window_12h",):
                    # Permitted only as a LOCKED window declaration.
                    continue
                self.assertNotIn(forbidden, source, f"{module.__name__}:{forbidden}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
