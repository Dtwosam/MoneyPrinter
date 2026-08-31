"""Focused proofs: Standard-4H pre-4h request-ceiling wiring.

Standalone selective-1h keeps ``_SELECTIVE_1H_MAX_REQUESTS_RUN``.
Four-token Standard-4H must select the scaled Standard-4H request envelope
instead of inheriting the standalone selective ceiling via
``selective_1h_continuation=True``.

No live sources, no authoritative DB mutation, no campaign launch.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.multi_cycle_memory_growth import (
    scaled_standard_four_hour_capacity_contract,
)


_SELECTIVE_ONLY = {
    "continuous_first_hour": True,
    "selective_1h_continuation": True,
    "continuous_four_hour": False,
    "standard_four_hour_campaign": False,
    "four_token_proof": False,
}

_FOUR_TOKEN_STD4H = {
    "continuous_first_hour": True,
    "selective_1h_continuation": True,
    "continuous_four_hour": True,
    "standard_four_hour_campaign": True,
    "four_token_proof": True,
}

_CONTINUATION_STEP = {
    "step_kind": "CONTINUATION_SNAPSHOT",
    "step_key": "t1_c0002_continuation_snapshot_03",
    "tracking_lane": "TRACK_FAST",
}


def _four_token_request_ceiling() -> int:
    return int(
        scaled_standard_four_hour_capacity_contract(4)[
            "lifecycle_request_outer_ceiling"
        ]
    )


class Standard4hPre4hRequestCeilingWiringTests(unittest.TestCase):
    def test_standalone_selective_1h_request_ceiling_remains_selective(self) -> None:
        self.assertEqual(
            factory._request_ceiling_for_run_config(_SELECTIVE_ONLY),
            factory._SELECTIVE_1H_MAX_REQUESTS_RUN,
        )
        self.assertEqual(factory._SELECTIVE_1H_MAX_REQUESTS_RUN, 102)

    def test_standalone_selective_continuation_snapshot_trips_at_selective_ceiling(
        self,
    ) -> None:
        with (
            patch.object(factory, "_load_run_config", return_value=_SELECTIVE_ONLY),
            patch.object(
                factory,
                "_run_request_count",
                return_value=factory._SELECTIVE_1H_MAX_REQUESTS_RUN,
            ),
            patch.object(factory, "_token_request_count", return_value=0),
        ):
            with self.assertRaises(factory._GlobalStop) as raised:
                factory._enforce_budgets_before_step(
                    object(), "run", _CONTINUATION_STEP
                )
        self.assertEqual(str(raised.exception), factory.STOP_BUDGET)
        self.assertEqual(raised.exception.scope, "CUMULATIVE_LIFECYCLE")

    def test_four_token_request_ceiling_equals_scaled_standard4h_contract(
        self,
    ) -> None:
        expected = _four_token_request_ceiling()
        observed = factory._request_ceiling_for_run_config(_FOUR_TOKEN_STD4H)
        self.assertEqual(observed, expected)
        self.assertNotEqual(observed, factory._SELECTIVE_1H_MAX_REQUESTS_RUN)

    def test_four_token_continuation_snapshot_allows_requests_above_selective_102(
        self,
    ) -> None:
        four_token_ceiling = factory._request_ceiling_for_run_config(
            _FOUR_TOKEN_STD4H
        )
        self.assertGreater(four_token_ceiling, factory._SELECTIVE_1H_MAX_REQUESTS_RUN)
        mid_range = factory._SELECTIVE_1H_MAX_REQUESTS_RUN + 1  # 103
        self.assertLessEqual(mid_range + 1, four_token_ceiling)
        with (
            patch.object(factory, "_load_run_config", return_value=_FOUR_TOKEN_STD4H),
            patch.object(factory, "_run_request_count", return_value=mid_range),
            patch.object(factory, "_token_request_count", return_value=0),
        ):
            factory._enforce_budgets_before_step(
                object(), "run", _CONTINUATION_STEP
            )

    def test_four_token_continuation_snapshot_exact_ceiling_boundaries(self) -> None:
        four_token_ceiling = _four_token_request_ceiling()
        self.assertEqual(
            factory._request_ceiling_for_run_config(_FOUR_TOKEN_STD4H),
            four_token_ceiling,
        )
        # ceiling - 1 + projected 1 == ceiling => allowed
        with (
            patch.object(factory, "_load_run_config", return_value=_FOUR_TOKEN_STD4H),
            patch.object(
                factory, "_run_request_count", return_value=four_token_ceiling - 1
            ),
            patch.object(factory, "_token_request_count", return_value=0),
        ):
            factory._enforce_budgets_before_step(
                object(), "run", _CONTINUATION_STEP
            )
        # ceiling + projected 1 > ceiling => fail-closed
        with (
            patch.object(factory, "_load_run_config", return_value=_FOUR_TOKEN_STD4H),
            patch.object(
                factory, "_run_request_count", return_value=four_token_ceiling
            ),
            patch.object(factory, "_token_request_count", return_value=0),
        ):
            with self.assertRaises(factory._GlobalStop) as raised:
                factory._enforce_budgets_before_step(
                    object(), "run", _CONTINUATION_STEP
                )
        self.assertEqual(str(raised.exception), factory.STOP_BUDGET)
        self.assertEqual(raised.exception.scope, "CUMULATIVE_LIFECYCLE")

    def test_scheduler_and_request_scope_selection_remain_symmetric(self) -> None:
        selective_request = factory._request_ceiling_for_run_config(_SELECTIVE_ONLY)
        selective_scheduler = factory._scheduler_ceiling_for_run_config(
            _SELECTIVE_ONLY
        )
        self.assertEqual(selective_request, factory._SELECTIVE_1H_MAX_REQUESTS_RUN)
        self.assertEqual(
            selective_scheduler, factory._SELECTIVE_1H_MAX_SCHEDULER_ROWS
        )

        capacity = scaled_standard_four_hour_capacity_contract(4)
        four_token_request = factory._request_ceiling_for_run_config(
            _FOUR_TOKEN_STD4H
        )
        four_token_scheduler = factory._scheduler_ceiling_for_run_config(
            _FOUR_TOKEN_STD4H
        )
        self.assertEqual(
            four_token_request,
            int(capacity["lifecycle_request_outer_ceiling"]),
        )
        self.assertEqual(
            four_token_scheduler,
            int(capacity["lifecycle_scheduler_outer_ceiling"]),
        )
        # Existing four-token Scheduler override remains unchanged.
        self.assertEqual(
            four_token_scheduler,
            factory._scheduler_ceiling_for_run_config(_FOUR_TOKEN_STD4H),
        )


if __name__ == "__main__":
    unittest.main()
