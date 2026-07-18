"""V2-9.7D.3A campaign identity and state-validation tests.

These tests exercise the pure validators in
``printer_v1.operator_cli.campaign_identity_state``. The predecessor tests reuse
migration 031 and ``campaign_persistence`` to materialise real campaign and
terminal-report records; no schema, orchestration, or persistent-DB mutation is
introduced here.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.campaign_identity_state import (
    ALLOWED_CAMPAIGN_TRANSITIONS,
    CampaignIdentityError,
    CampaignStateError,
    IDENTITY_KINDS,
    NON_TERMINAL_CAMPAIGN_STATES,
    Terminalization,
    can_transition,
    is_terminal_state,
    require_identity,
    terminalize,
    validate_campaign_state,
    validate_identity,
    validate_identity_chain,
    validate_report_predecessor,
    validate_transition,
)
from printer_v1.operator_cli.campaign_persistence import (
    CAMPAIGN_STATES,
    DB_MODE_OPERATIONAL_PERSISTENT,
    TERMINAL_CAMPAIGN_STATES,
    create_campaign,
    persist_terminal_report,
)


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": True,
        "git_provenance_captured_at": "2026-07-18T00:00:00+00:00",
    }


class IdentityValidationTests(unittest.TestCase):
    def test_every_kind_accepts_safe_identities(self) -> None:
        for kind in IDENTITY_KINDS:
            self.assertEqual(
                validate_identity(kind, "id-01:Ab_c.9"), "id-01:Ab_c.9"
            )

    def test_unknown_kind_fails_closed(self) -> None:
        with self.assertRaisesRegex(CampaignIdentityError, "unknown identity kind"):
            validate_identity("trajectory", "x")

    def test_malformed_identities_fail_closed(self) -> None:
        cases = {
            "empty": "",
            "whitespace": "   ",
            "surrounding-space": " abc",
            "embedded-space": "a b",
            "leading-symbol": "-abc",
            "control-char": "a\tb",
            "too-long": "a" * 257,
        }
        for label, value in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(CampaignIdentityError):
                    validate_identity("cycle", value)

    def test_non_string_identity_fails_closed(self) -> None:
        for value in (None, 123, b"bytes", ["campaign"]):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    CampaignIdentityError, "must be a string"
                ):
                    validate_identity("campaign", value)

    def test_require_identity_exact_match_and_mismatch(self) -> None:
        self.assertEqual(require_identity("mint", "mint-a", "mint-a"), "mint-a")
        with self.assertRaisesRegex(CampaignIdentityError, "identity mismatch"):
            require_identity("mint", "mint-a", "mint-b")

    def test_identity_chain_validated_value_by_value(self) -> None:
        chain = {
            "campaign": "campaign-a",
            "cycle": "cycle-1",
            "token_slot": "slot-3",
            "token": "token-x",
            "mint": "So11111111111111111111111111111111111111112",
            "pair": "pair-9",
            "lifecycle": "TRACK_NORMAL",
            "window": "WINDOW_15M:0",
        }
        self.assertEqual(validate_identity_chain(chain), chain)
        with self.assertRaisesRegex(CampaignIdentityError, "unknown identity kind"):
            validate_identity_chain({"pair": "pair-9", "bogus": "z"})
        with self.assertRaises(CampaignIdentityError):
            validate_identity_chain({"window": "bad window"})


class StateTransitionTests(unittest.TestCase):
    def test_transition_table_covers_every_state_and_targets_are_valid(self) -> None:
        self.assertEqual(set(ALLOWED_CAMPAIGN_TRANSITIONS), set(CAMPAIGN_STATES))
        for source, targets in ALLOWED_CAMPAIGN_TRANSITIONS.items():
            self.assertTrue(targets.issubset(CAMPAIGN_STATES))
            if source in TERMINAL_CAMPAIGN_STATES:
                self.assertEqual(targets, frozenset())

    def test_representative_allowed_transitions(self) -> None:
        allowed = [
            ("DRAFT", "PREFLIGHT"),
            ("PREFLIGHT", "RUNNING"),
            ("RUNNING", "STOP_REQUESTED"),
            ("RUNNING", "TERMINAL_COMPLETED"),
            ("STOP_REQUESTED", "TERMINAL_STOPPED"),
            ("PREFLIGHT", "TERMINAL_BLOCKED"),
        ]
        for source, target in allowed:
            with self.subTest(edge=(source, target)):
                self.assertTrue(can_transition(source, target))
                self.assertEqual(validate_transition(source, target), target)

    def test_disallowed_transitions_fail_closed(self) -> None:
        disallowed = [
            ("DRAFT", "RUNNING"),
            ("DRAFT", "TERMINAL_COMPLETED"),
            ("DRAFT", "TERMINAL_STOPPED"),
            ("PREFLIGHT", "TERMINAL_COMPLETED"),
            ("TERMINAL_COMPLETED", "RUNNING"),
            ("TERMINAL_FAILED", "TERMINAL_COMPLETED"),
        ]
        for source, target in disallowed:
            with self.subTest(edge=(source, target)):
                self.assertFalse(can_transition(source, target))
                with self.assertRaisesRegex(
                    CampaignStateError, "transition not allowed"
                ):
                    validate_transition(source, target)

    def test_unknown_states_fail_closed(self) -> None:
        with self.assertRaisesRegex(CampaignStateError, "unknown campaign state"):
            validate_campaign_state("PAUSED")
        with self.assertRaisesRegex(CampaignStateError, "unknown campaign state"):
            can_transition("RUNNING", "PAUSED")

    def test_terminal_classification(self) -> None:
        for state in TERMINAL_CAMPAIGN_STATES:
            self.assertTrue(is_terminal_state(state))
        for state in NON_TERMINAL_CAMPAIGN_STATES:
            self.assertFalse(is_terminal_state(state))


class TerminalizationTests(unittest.TestCase):
    def test_fresh_terminalization_records_cause(self) -> None:
        result = terminalize(
            current_state="RUNNING",
            current_first_terminal_cause=None,
            requested_state="TERMINAL_COMPLETED",
            requested_first_terminal_cause="clean-window-complete",
        )
        self.assertEqual(
            result,
            Terminalization(
                state="TERMINAL_COMPLETED",
                first_terminal_cause="clean-window-complete",
                changed=True,
            ),
        )

    def test_repeated_terminalization_is_idempotent(self) -> None:
        result = terminalize(
            current_state="TERMINAL_STOPPED",
            current_first_terminal_cause="operator-stop",
            requested_state="TERMINAL_STOPPED",
            requested_first_terminal_cause="operator-stop",
        )
        self.assertFalse(result.changed)
        self.assertEqual(result.first_terminal_cause, "operator-stop")

    def test_first_terminal_cause_is_immutable(self) -> None:
        with self.assertRaisesRegex(
            CampaignStateError, "first terminal cause is immutable"
        ):
            terminalize(
                current_state="TERMINAL_STOPPED",
                current_first_terminal_cause="operator-stop",
                requested_state="TERMINAL_STOPPED",
                requested_first_terminal_cause="budget-stop",
            )

    def test_cannot_change_terminal_state(self) -> None:
        with self.assertRaisesRegex(
            CampaignStateError, "already terminal in a different state"
        ):
            terminalize(
                current_state="TERMINAL_COMPLETED",
                current_first_terminal_cause="done",
                requested_state="TERMINAL_FAILED",
                requested_first_terminal_cause="done",
            )

    def test_disallowed_terminal_transition_fails_closed(self) -> None:
        with self.assertRaisesRegex(CampaignStateError, "transition not allowed"):
            terminalize(
                current_state="DRAFT",
                current_first_terminal_cause=None,
                requested_state="TERMINAL_COMPLETED",
                requested_first_terminal_cause="premature",
            )

    def test_non_terminal_request_and_bad_cause_fail_closed(self) -> None:
        with self.assertRaisesRegex(CampaignStateError, "not terminal"):
            terminalize(
                current_state="RUNNING",
                current_first_terminal_cause=None,
                requested_state="STOP_REQUESTED",
                requested_first_terminal_cause="x",
            )
        with self.assertRaisesRegex(
            CampaignStateError, "first terminal cause must be a non-empty string"
        ):
            terminalize(
                current_state="RUNNING",
                current_first_terminal_cause=None,
                requested_state="TERMINAL_FAILED",
                requested_first_terminal_cause="   ",
            )

    def test_non_terminal_carrying_a_cause_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            CampaignStateError, "must not carry a first terminal cause"
        ):
            terminalize(
                current_state="RUNNING",
                current_first_terminal_cause="leaked",
                requested_state="TERMINAL_FAILED",
                requested_first_terminal_cause="real",
            )


class ReportPredecessorTests(unittest.TestCase):
    def setUp(self) -> None:
        configured_temp = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=configured_temp)
        self.root = Path(self.temp.name)
        self.db = self.root / "isolated.sqlite3"
        apply_migrations(self.db)
        self._create("campaign-a", "config-a")
        self._create("campaign-b", "config-b")
        self.terminal = persist_terminal_report(
            self.db,
            report_id="report-a",
            campaign_id="campaign-a",
            configuration_id="config-a",
            report={"status": "TERMINAL_COMPLETED", "clean_yield": 0},
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create(self, campaign_id: str, configuration_id: str) -> dict[str, object]:
        return create_campaign(
            self.db,
            campaign_id=campaign_id,
            configuration_id=configuration_id,
            configuration={"cycle_limit": 2, "token_capacity": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_OPERATIONAL_PERSISTENT,
            db_target_identity="sha256:operational-db",
            policy_version="V2-9.7C",
            now=datetime(2026, 7, 18, tzinfo=timezone.utc),
        )

    def test_valid_predecessor_is_accepted(self) -> None:
        validated = validate_report_predecessor(
            replay_campaign_id="campaign-a",
            replay_configuration_id="config-a",
            predecessor_report=self.terminal,
        )
        self.assertEqual(validated["report_id"], "report-a")

    def test_cross_campaign_predecessor_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            CampaignIdentityError, "campaign identity mismatch"
        ):
            validate_report_predecessor(
                replay_campaign_id="campaign-b",
                replay_configuration_id="config-b",
                predecessor_report=self.terminal,
            )

    def test_configuration_mismatch_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            CampaignIdentityError, "configuration identity mismatch"
        ):
            validate_report_predecessor(
                replay_campaign_id="campaign-a",
                replay_configuration_id="config-b",
                predecessor_report=self.terminal,
            )

    def test_non_terminal_predecessor_fails_closed(self) -> None:
        pending = dict(self.terminal)
        pending["report_kind"] = "REPLAY"
        pending["report_state"] = "REPLAY_VERIFIED"
        with self.assertRaisesRegex(
            CampaignIdentityError, "must be TERMINAL"
        ):
            validate_report_predecessor(
                replay_campaign_id="campaign-a",
                replay_configuration_id="config-a",
                predecessor_report=pending,
            )

    def test_predecessor_must_be_a_mapping(self) -> None:
        with self.assertRaisesRegex(
            CampaignIdentityError, "must be a record mapping"
        ):
            validate_report_predecessor(
                replay_campaign_id="campaign-a",
                replay_configuration_id="config-a",
                predecessor_report="report-a",
            )


if __name__ == "__main__":
    unittest.main()
