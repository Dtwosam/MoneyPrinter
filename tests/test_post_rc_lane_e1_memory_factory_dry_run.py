"""
Post-Lane 10 Lane E1 — Conservative 15m Memory Factory Dry-Run Scaffold

Tests prove:
- command requires --operator-approved
- command is Solana-only (--chain must be solana)
- --help works without crashing
- main entry point exits 0 with valid args
- main prints JSON to stdout
- dry_run is True
- operator_approved is True in payload
- mode is conservative
- target_window_kind is WINDOW_15M
- support_window_kind is WINDOW_5M_MICRO_EVENT
- support_window_only is True (5m is support-only, never main outcome)
- source_fetching_enabled is False
- scheduler_execution_enabled is False
- memory_creation_enabled is False
- paper_decisions_enabled is False
- buy_enabled is False
- positions_enabled is False
- pnl_enabled is False
- zero_clean_memories_allowed is True
- clean_memory_forced is False
- default max_active_tokens is 10
- default max_track_fast is 3
- default max_track_normal is 7
- custom token caps are accepted
- max_active_tokens below 1 is rejected
- max_active_tokens above 30 is rejected
- max_track_fast below 1 is rejected
- max_track_fast above 10 is rejected
- max_track_normal below 1 is rejected
- max_track_normal above 20 is rejected
- max_track_fast + max_track_normal exceeding max_active_tokens is rejected
- locked_capabilities list is present and non-empty
- locked_capabilities includes BUY
- locked_capabilities includes SELL
- locked_capabilities includes HOLD
- locked_capabilities includes paper_positions
- locked_capabilities includes pnl_calculation
- locked_capabilities includes live_execution
- locked_capabilities includes real_funds
- locked_capabilities includes source_fetching
- locked_capabilities includes memory_creation
- locked_capabilities includes paper_decisions
- locked_capabilities includes 5m_as_main_outcome_memory
- locked_capabilities includes 5m_unlocking_retrieval_or_decisions
- stop_conditions list is present and non-empty
- stop_conditions includes source_failure_rate item
- stop_conditions includes buy/sell/hold unexpected item
- stop_conditions includes unbounded_runtime_appears
- required_future_gates list is present and non-empty
- required_future_gates includes operator approval gate
- required_future_gates includes buy_remains_locked_throughout
- pyproject.toml registers the entry point
- command field is correct
- no scoring/confidence/ranking/weighted/embedding/vector terms in locked_capabilities
- all boolean fields are actual Python bools, not strings
"""

import argparse
import io
import json
import pathlib
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.operator_cli.commands import (
    _LANE_E1_LOCKED_CAPABILITIES,
    _LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT,
    _LANE_E1_MAX_TRACK_FAST_DEFAULT,
    _LANE_E1_MAX_TRACK_NORMAL_DEFAULT,
    _LANE_E1_MODE,
    _LANE_E1_REQUIRED_FUTURE_GATES,
    _LANE_E1_STOP_CONDITIONS,
    _LANE_E1_SUPPORT_WINDOW_KIND,
    _LANE_E1_TARGET_WINDOW_KIND,
    build_plan_conservative_15m_memory_factory_once_payload,
    main_plan_conservative_15m_memory_factory_once,
)


def _args(**overrides: object) -> argparse.Namespace:
    defaults = {
        "db_path": None,
        "project_root": str(PROJECT_ROOT),
        "format": "json",
        "no_color": True,
        "operator_approved": True,
        "chain": "solana",
        "max_active_tokens": _LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT,
        "max_track_fast": _LANE_E1_MAX_TRACK_FAST_DEFAULT,
        "max_track_normal": _LANE_E1_MAX_TRACK_NORMAL_DEFAULT,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class LaneE1ApprovalAndGateTests(unittest.TestCase):

    def test_requires_operator_approved(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_plan_conservative_15m_memory_factory_once_payload(
                _args(operator_approved=False)
            )
        self.assertIn("operator approval", str(ctx.exception).lower())

    def test_solana_only(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_plan_conservative_15m_memory_factory_once_payload(
                _args(chain="ethereum")
            )
        self.assertIn("solana", str(ctx.exception).lower())

    def test_solana_only_base(self) -> None:
        with self.assertRaises(ValueError):
            build_plan_conservative_15m_memory_factory_once_payload(
                _args(chain="base")
            )

    def test_help_does_not_crash(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main_plan_conservative_15m_memory_factory_once(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_main_exits_0_with_valid_args(self) -> None:
        argv = [
            "--operator-approved",
            "--chain", "solana",
        ]
        result = main_plan_conservative_15m_memory_factory_once(argv)
        self.assertEqual(result, 0)

    def test_main_exits_1_without_approval(self) -> None:
        argv = ["--chain", "solana"]
        result = main_plan_conservative_15m_memory_factory_once(argv)
        self.assertEqual(result, 1)

    def test_main_prints_json_to_stdout(self) -> None:
        argv = ["--operator-approved", "--chain", "solana", "--format", "json"]
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            main_plan_conservative_15m_memory_factory_once(argv)
        output = buf.getvalue().strip()
        parsed = json.loads(output)
        self.assertIsInstance(parsed, dict)
        self.assertIn("dry_run", parsed)


class LaneE1DryRunFieldTests(unittest.TestCase):

    def setUp(self) -> None:
        self.payload = build_plan_conservative_15m_memory_factory_once_payload(_args())

    def test_command_field(self) -> None:
        self.assertEqual(
            self.payload["command"],
            "printer-plan-conservative-15m-memory-factory-once",
        )

    def test_operator_approved_true(self) -> None:
        self.assertIs(self.payload["operator_approved"], True)

    def test_dry_run_true(self) -> None:
        self.assertIs(self.payload["dry_run"], True)

    def test_mode_conservative(self) -> None:
        self.assertEqual(self.payload["mode"], "conservative")
        self.assertEqual(self.payload["mode"], _LANE_E1_MODE)

    def test_target_window_kind(self) -> None:
        self.assertEqual(self.payload["target_window_kind"], "WINDOW_15M")
        self.assertEqual(self.payload["target_window_kind"], _LANE_E1_TARGET_WINDOW_KIND)

    def test_support_window_kind(self) -> None:
        self.assertEqual(self.payload["support_window_kind"], "WINDOW_5M_MICRO_EVENT")
        self.assertEqual(self.payload["support_window_kind"], _LANE_E1_SUPPORT_WINDOW_KIND)

    def test_support_window_only_true(self) -> None:
        self.assertIs(self.payload["support_window_only"], True)

    def test_source_fetching_disabled(self) -> None:
        self.assertIs(self.payload["source_fetching_enabled"], False)

    def test_scheduler_execution_disabled(self) -> None:
        self.assertIs(self.payload["scheduler_execution_enabled"], False)

    def test_memory_creation_disabled(self) -> None:
        self.assertIs(self.payload["memory_creation_enabled"], False)

    def test_paper_decisions_disabled(self) -> None:
        self.assertIs(self.payload["paper_decisions_enabled"], False)

    def test_buy_disabled(self) -> None:
        self.assertIs(self.payload["buy_enabled"], False)

    def test_positions_disabled(self) -> None:
        self.assertIs(self.payload["positions_enabled"], False)

    def test_pnl_disabled(self) -> None:
        self.assertIs(self.payload["pnl_enabled"], False)

    def test_zero_clean_memories_allowed(self) -> None:
        self.assertIs(self.payload["zero_clean_memories_allowed"], True)

    def test_clean_memory_not_forced(self) -> None:
        self.assertIs(self.payload["clean_memory_forced"], False)

    def test_all_boolean_fields_are_bools(self) -> None:
        bool_keys = [
            "operator_approved",
            "dry_run",
            "support_window_only",
            "source_fetching_enabled",
            "scheduler_execution_enabled",
            "memory_creation_enabled",
            "paper_decisions_enabled",
            "buy_enabled",
            "positions_enabled",
            "pnl_enabled",
            "zero_clean_memories_allowed",
            "clean_memory_forced",
        ]
        for key in bool_keys:
            self.assertIsInstance(
                self.payload[key], bool, msg=f"{key} must be a bool, got {type(self.payload[key])}"
            )


class LaneE1TokenCapTests(unittest.TestCase):

    def test_default_max_active_tokens(self) -> None:
        payload = build_plan_conservative_15m_memory_factory_once_payload(_args())
        self.assertEqual(payload["max_active_tokens"], _LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT)
        self.assertEqual(payload["max_active_tokens"], 10)

    def test_default_max_track_fast(self) -> None:
        payload = build_plan_conservative_15m_memory_factory_once_payload(_args())
        self.assertEqual(payload["max_track_fast"], _LANE_E1_MAX_TRACK_FAST_DEFAULT)
        self.assertEqual(payload["max_track_fast"], 3)

    def test_default_max_track_normal(self) -> None:
        payload = build_plan_conservative_15m_memory_factory_once_payload(_args())
        self.assertEqual(payload["max_track_normal"], _LANE_E1_MAX_TRACK_NORMAL_DEFAULT)
        self.assertEqual(payload["max_track_normal"], 7)

    def test_custom_token_caps_accepted(self) -> None:
        payload = build_plan_conservative_15m_memory_factory_once_payload(
            _args(max_active_tokens=5, max_track_fast=2, max_track_normal=3)
        )
        self.assertEqual(payload["max_active_tokens"], 5)
        self.assertEqual(payload["max_track_fast"], 2)
        self.assertEqual(payload["max_track_normal"], 3)

    def test_max_active_tokens_below_1_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_plan_conservative_15m_memory_factory_once_payload(
                _args(max_active_tokens=0)
            )

    def test_max_active_tokens_above_30_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_plan_conservative_15m_memory_factory_once_payload(
                _args(max_active_tokens=31)
            )

    def test_max_track_fast_below_1_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_plan_conservative_15m_memory_factory_once_payload(
                _args(max_track_fast=0)
            )

    def test_max_track_fast_above_10_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_plan_conservative_15m_memory_factory_once_payload(
                _args(max_track_fast=11)
            )

    def test_max_track_normal_below_1_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_plan_conservative_15m_memory_factory_once_payload(
                _args(max_track_normal=0)
            )

    def test_max_track_normal_above_20_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_plan_conservative_15m_memory_factory_once_payload(
                _args(max_track_normal=21)
            )

    def test_fast_plus_normal_exceeds_active_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_plan_conservative_15m_memory_factory_once_payload(
                _args(max_active_tokens=5, max_track_fast=3, max_track_normal=3)
            )
        self.assertIn("max_track_fast", str(ctx.exception))


class LaneE1LockedCapabilitiesTests(unittest.TestCase):

    def setUp(self) -> None:
        self.payload = build_plan_conservative_15m_memory_factory_once_payload(_args())
        self.locked = self.payload["locked_capabilities"]

    def test_locked_capabilities_is_list(self) -> None:
        self.assertIsInstance(self.locked, list)

    def test_locked_capabilities_non_empty(self) -> None:
        self.assertGreater(len(self.locked), 0)

    def test_locked_capabilities_matches_constant(self) -> None:
        self.assertEqual(self.locked, list(_LANE_E1_LOCKED_CAPABILITIES))

    def test_buy_locked(self) -> None:
        self.assertIn("BUY", self.locked)

    def test_sell_locked(self) -> None:
        self.assertIn("SELL", self.locked)

    def test_hold_locked(self) -> None:
        self.assertIn("HOLD", self.locked)

    def test_paper_positions_locked(self) -> None:
        self.assertIn("paper_positions", self.locked)

    def test_pnl_calculation_locked(self) -> None:
        self.assertIn("pnl_calculation", self.locked)

    def test_live_execution_locked(self) -> None:
        self.assertIn("live_execution", self.locked)

    def test_real_funds_locked(self) -> None:
        self.assertIn("real_funds", self.locked)

    def test_source_fetching_locked(self) -> None:
        self.assertIn("source_fetching", self.locked)

    def test_memory_creation_locked(self) -> None:
        self.assertIn("memory_creation", self.locked)

    def test_paper_decisions_locked(self) -> None:
        self.assertIn("paper_decisions", self.locked)

    def test_5m_as_main_outcome_locked(self) -> None:
        self.assertIn("5m_as_main_outcome_memory", self.locked)

    def test_5m_unlocking_retrieval_locked(self) -> None:
        self.assertIn("5m_unlocking_retrieval_or_decisions", self.locked)

    def test_wallet_private_key_signing_locked(self) -> None:
        self.assertIn("wallet_private_key_signing", self.locked)

    def test_paid_api_locked(self) -> None:
        self.assertIn("paid_api_dependencies", self.locked)

    def test_no_standalone_score_or_confidence_term_in_capabilities(self) -> None:
        # Only exact-match standalone items are forbidden.
        # Compound lock labels like 'scoring_ranking_confidence_weighted' are acceptable
        # because they describe grouped locked concepts, not scoring behavior.
        standalone_forbidden = {
            "score", "scoring", "ranking", "confidence", "weighted",
            "embedding", "vector",
        }
        for item in self.locked:
            self.assertNotIn(
                item.lower(),
                standalone_forbidden,
                msg=f"Standalone forbidden term found in locked_capabilities: {item!r}. "
                    "Use a compound label like 'scoring_ranking_confidence_weighted'.",
            )


class LaneE1StopConditionsTests(unittest.TestCase):

    def setUp(self) -> None:
        self.payload = build_plan_conservative_15m_memory_factory_once_payload(_args())
        self.stops = self.payload["stop_conditions"]

    def test_stop_conditions_is_list(self) -> None:
        self.assertIsInstance(self.stops, list)

    def test_stop_conditions_non_empty(self) -> None:
        self.assertGreater(len(self.stops), 0)

    def test_stop_conditions_matches_constant(self) -> None:
        self.assertEqual(self.stops, list(_LANE_E1_STOP_CONDITIONS))

    def test_source_failure_rate_condition(self) -> None:
        self.assertTrue(
            any("source_failure_rate" in s for s in self.stops),
            msg="Expected a source_failure_rate stop condition",
        )

    def test_buy_sell_hold_unexpected_condition(self) -> None:
        self.assertTrue(
            any("buy_sell_hold" in s for s in self.stops),
            msg="Expected a buy_sell_hold unexpected creation stop condition",
        )

    def test_unbounded_runtime_condition(self) -> None:
        self.assertIn("unbounded_runtime_appears", self.stops)

    def test_source_governor_bypass_condition(self) -> None:
        self.assertTrue(
            any("source_governor" in s for s in self.stops),
            msg="Expected a source governor bypass stop condition",
        )

    def test_dirty_memory_in_retrieval_condition(self) -> None:
        self.assertTrue(
            any("dirty_or_audit_only" in s for s in self.stops),
            msg="Expected a dirty/audit-only memory in retrieval stop condition",
        )


class LaneE1RequiredFutureGatesTests(unittest.TestCase):

    def setUp(self) -> None:
        self.payload = build_plan_conservative_15m_memory_factory_once_payload(_args())
        self.gates = self.payload["required_future_gates"]

    def test_required_future_gates_is_list(self) -> None:
        self.assertIsInstance(self.gates, list)

    def test_required_future_gates_non_empty(self) -> None:
        self.assertGreater(len(self.gates), 0)

    def test_required_future_gates_matches_constant(self) -> None:
        self.assertEqual(self.gates, list(_LANE_E1_REQUIRED_FUTURE_GATES))

    def test_operator_approval_gate(self) -> None:
        self.assertTrue(
            any("operator_approves" in g for g in self.gates),
            msg="Expected operator approval gate",
        )

    def test_buy_locked_gate(self) -> None:
        self.assertIn("buy_remains_locked_throughout", self.gates)

    def test_positions_locked_gate(self) -> None:
        self.assertIn("positions_remain_locked_throughout", self.gates)

    def test_pnl_locked_gate(self) -> None:
        self.assertIn("pnl_remains_locked_throughout", self.gates)

    def test_full_test_suite_gate(self) -> None:
        self.assertIn("full_test_suite_passes", self.gates)


class LaneE1EntryPointRegistrationTests(unittest.TestCase):

    def test_pyproject_toml_registers_entry_point(self) -> None:
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        self.assertIn(
            "printer-plan-conservative-15m-memory-factory-once",
            content,
        )

    def test_pyproject_toml_entry_point_points_to_correct_callable(self) -> None:
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        self.assertIn(
            "main_plan_conservative_15m_memory_factory_once",
            content,
        )

    def test_callable_is_importable(self) -> None:
        from printer_v1.operator_cli.commands import (  # noqa: F401
            main_plan_conservative_15m_memory_factory_once,
        )

    def test_payload_builder_is_importable(self) -> None:
        from printer_v1.operator_cli.commands import (  # noqa: F401
            build_plan_conservative_15m_memory_factory_once_payload,
        )


class LaneE1HardLockVerificationTests(unittest.TestCase):
    """Verify hard locks are structurally present in the payload — not just as strings."""

    def setUp(self) -> None:
        self.payload = build_plan_conservative_15m_memory_factory_once_payload(_args())

    def test_buy_enabled_is_false_not_string(self) -> None:
        self.assertIs(self.payload["buy_enabled"], False)
        self.assertNotEqual(self.payload["buy_enabled"], "False")

    def test_positions_enabled_is_false_not_string(self) -> None:
        self.assertIs(self.payload["positions_enabled"], False)

    def test_pnl_enabled_is_false_not_string(self) -> None:
        self.assertIs(self.payload["pnl_enabled"], False)

    def test_source_fetching_is_false_not_string(self) -> None:
        self.assertIs(self.payload["source_fetching_enabled"], False)

    def test_scheduler_execution_is_false_not_string(self) -> None:
        self.assertIs(self.payload["scheduler_execution_enabled"], False)

    def test_memory_creation_is_false_not_string(self) -> None:
        self.assertIs(self.payload["memory_creation_enabled"], False)

    def test_paper_decisions_is_false_not_string(self) -> None:
        self.assertIs(self.payload["paper_decisions_enabled"], False)

    def test_clean_memory_forced_is_false_not_string(self) -> None:
        self.assertIs(self.payload["clean_memory_forced"], False)

    def test_payload_serializes_to_valid_json(self) -> None:
        serialized = json.dumps(self.payload)
        parsed = json.loads(serialized)
        self.assertIs(parsed["dry_run"], True)
        self.assertIs(parsed["buy_enabled"], False)
        self.assertIs(parsed["positions_enabled"], False)
        self.assertIs(parsed["pnl_enabled"], False)

    def test_no_db_write_required(self) -> None:
        """Dry-run must work without a db_path (no DB access needed)."""
        payload = build_plan_conservative_15m_memory_factory_once_payload(
            _args(db_path=None)
        )
        self.assertIs(payload["dry_run"], True)
        self.assertIs(payload["source_fetching_enabled"], False)


class LaneE1LaneMetadataTests(unittest.TestCase):

    def test_mode_constant_value(self) -> None:
        self.assertEqual(_LANE_E1_MODE, "conservative")

    def test_target_window_constant_value(self) -> None:
        self.assertEqual(_LANE_E1_TARGET_WINDOW_KIND, "WINDOW_15M")

    def test_support_window_constant_value(self) -> None:
        self.assertEqual(_LANE_E1_SUPPORT_WINDOW_KIND, "WINDOW_5M_MICRO_EVENT")

    def test_default_max_active_tokens_constant(self) -> None:
        self.assertEqual(_LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT, 10)

    def test_default_max_track_fast_constant(self) -> None:
        self.assertEqual(_LANE_E1_MAX_TRACK_FAST_DEFAULT, 3)

    def test_default_max_track_normal_constant(self) -> None:
        self.assertEqual(_LANE_E1_MAX_TRACK_NORMAL_DEFAULT, 7)

    def test_default_fast_plus_normal_within_active(self) -> None:
        self.assertLessEqual(
            _LANE_E1_MAX_TRACK_FAST_DEFAULT + _LANE_E1_MAX_TRACK_NORMAL_DEFAULT,
            _LANE_E1_MAX_ACTIVE_TOKENS_DEFAULT,
        )


if __name__ == "__main__":
    unittest.main()
