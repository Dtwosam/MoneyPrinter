"""Focused proofs: Standard-4H pre-4h request-ceiling wiring.

Standalone selective-1h keeps ``_SELECTIVE_1H_MAX_REQUESTS_RUN``.
Four-token Standard-4H must select the scaled Standard-4H request envelope
instead of inheriting the standalone selective ceiling via
``selective_1h_continuation=True``.

No live sources, no authoritative DB mutation, no campaign launch.
"""

from __future__ import annotations

import unittest
from typing import Any
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

_FIFTEEN_M = {
    "continuous_first_hour": False,
    "selective_1h_continuation": False,
    "continuous_four_hour": False,
    "standard_four_hour_campaign": False,
    "four_token_proof": False,
}

_TWO_TOKEN_STD4H = {
    "continuous_first_hour": True,
    "selective_1h_continuation": True,
    "continuous_four_hour": True,
    "standard_four_hour_campaign": True,
    "four_token_proof": False,
}

_CONTINUATION_STEP = {
    "step_kind": "CONTINUATION_SNAPSHOT",
    "step_key": "t1_c0002_continuation_snapshot_03",
    "tracking_lane": "TRACK_FAST",
}

_CLOSE_CONTEXT_STEP = {
    "step_kind": "CONTINUATION_CLOSE_CONTEXT",
    "step_key": "t1_continuation_close_context",
    "tracking_lane": "TRACK_FAST",
}

_SNAPSHOT_STEP = {
    "step_kind": "SNAPSHOT",
    "step_key": "t1_snapshot_000",
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

    def _four_token_token_ceiling(self) -> int:
        return int(
            scaled_standard_four_hour_capacity_contract(4)[
                "lifecycle_requests_per_token"
            ]
        )

    def _enforce(
        self,
        *,
        config: dict[str, Any],
        run_count: int,
        token_count: int,
        step: dict[str, Any],
    ) -> None:
        with (
            patch.object(factory, "_load_run_config", return_value=config),
            patch.object(factory, "_run_request_count", return_value=run_count),
            patch.object(factory, "_token_request_count", return_value=token_count),
        ):
            factory._enforce_budgets_before_step(object(), "run", step)

    def _assert_global_stop(
        self,
        *,
        config: dict[str, Any],
        run_count: int,
        token_count: int,
        step: dict[str, Any],
    ) -> None:
        with self.assertRaises(factory._GlobalStop) as raised:
            self._enforce(
                config=config,
                run_count=run_count,
                token_count=token_count,
                step=step,
            )
        self.assertEqual(str(raised.exception), factory.STOP_BUDGET)
        self.assertEqual(raised.exception.reason, factory.STOP_BUDGET)
        self.assertEqual(raised.exception.scope, "CUMULATIVE_LIFECYCLE")

    def test_token_ceiling_selector_follows_scaled_contract_not_continuous_50(
        self,
    ) -> None:
        capacity = scaled_standard_four_hour_capacity_contract(4)
        self.assertEqual(
            factory._token_ceiling_for_run_config(_FOUR_TOKEN_STD4H),
            int(capacity["lifecycle_requests_per_token"]),
        )
        self.assertEqual(int(capacity["lifecycle_requests_per_token"]), 118)
        self.assertNotEqual(
            factory._token_ceiling_for_run_config(_FOUR_TOKEN_STD4H),
            factory._CONTINUOUS_MAX_REQUESTS_PER_TOKEN,
        )
        self.assertEqual(
            factory._token_ceiling_for_run_config(_SELECTIVE_ONLY),
            factory._CONTINUOUS_MAX_REQUESTS_PER_TOKEN,
        )
        self.assertEqual(factory._CONTINUOUS_MAX_REQUESTS_PER_TOKEN, 50)
        self.assertEqual(
            factory._token_ceiling_for_run_config(_FIFTEEN_M),
            factory._MAX_GOVERNED_REQUESTS_PER_TOKEN,
        )
        self.assertEqual(factory._MAX_GOVERNED_REQUESTS_PER_TOKEN, 22)
        self.assertEqual(
            factory._token_ceiling_for_run_config(_TWO_TOKEN_STD4H),
            factory._CONTINUOUS_MAX_REQUESTS_PER_TOKEN,
        )
        self.assertEqual(
            factory._request_ceiling_for_run_config(_TWO_TOKEN_STD4H),
            factory._SELECTIVE_1H_MAX_REQUESTS_RUN,
        )

    def test_four_token_envelope_and_retry_rotation_remain_unchanged(self) -> None:
        capacity = scaled_standard_four_hour_capacity_contract(4)
        self.assertEqual(
            factory._request_ceiling_for_run_config(_FOUR_TOKEN_STD4H),
            int(capacity["lifecycle_request_outer_ceiling"]),
        )
        self.assertEqual(int(capacity["lifecycle_request_outer_ceiling"]), 476)
        self.assertEqual(
            factory._scheduler_ceiling_for_run_config(_FOUR_TOKEN_STD4H),
            int(capacity["lifecycle_scheduler_outer_ceiling"]),
        )
        self.assertEqual(int(capacity["lifecycle_scheduler_outer_ceiling"]), 444)
        self.assertEqual(int(capacity["automatic_retries"]), 0)
        self.assertIs(capacity["endpoint_rotation"], False)
        self.assertEqual(factory._CONTINUOUS_MAX_REQUESTS_PER_TOKEN, 50)
        self.assertEqual(factory._SELECTIVE_1H_MAX_REQUESTS_PER_TOKEN, 50)
        self.assertEqual(factory._MAX_GOVERNED_REQUESTS_PER_TOKEN, 22)

    def test_four_token_50_plus_1_allows(self) -> None:
        self._enforce(
            config=_FOUR_TOKEN_STD4H,
            run_count=50,
            token_count=50,
            step=_CONTINUATION_STEP,
        )

    def test_four_token_51_plus_0_allows_sep3_regression(self) -> None:
        self._enforce(
            config=_FOUR_TOKEN_STD4H,
            run_count=51,
            token_count=51,
            step=_CLOSE_CONTEXT_STEP,
        )

    def test_four_token_117_plus_1_allows(self) -> None:
        self._enforce(
            config=_FOUR_TOKEN_STD4H,
            run_count=117,
            token_count=117,
            step=_CONTINUATION_STEP,
        )

    def test_four_token_118_plus_0_allows(self) -> None:
        self._enforce(
            config=_FOUR_TOKEN_STD4H,
            run_count=118,
            token_count=118,
            step=_CLOSE_CONTEXT_STEP,
        )

    def test_four_token_118_plus_1_global_stops(self) -> None:
        self._assert_global_stop(
            config=_FOUR_TOKEN_STD4H,
            run_count=118,
            token_count=118,
            step=_CONTINUATION_STEP,
        )

    def test_four_token_119_plus_0_global_stops(self) -> None:
        self._assert_global_stop(
            config=_FOUR_TOKEN_STD4H,
            run_count=119,
            token_count=119,
            step=_CLOSE_CONTEXT_STEP,
        )

    def test_selective_1h_49_plus_1_allows(self) -> None:
        self._enforce(
            config=_SELECTIVE_ONLY,
            run_count=49,
            token_count=49,
            step=_CONTINUATION_STEP,
        )

    def test_selective_1h_50_plus_1_global_stops(self) -> None:
        self._assert_global_stop(
            config=_SELECTIVE_ONLY,
            run_count=50,
            token_count=50,
            step=_CONTINUATION_STEP,
        )

    def test_fifteen_m_22_plus_1_global_stops(self) -> None:
        self._assert_global_stop(
            config=_FIFTEEN_M,
            run_count=22,
            token_count=22,
            step=_SNAPSHOT_STEP,
        )

    def test_two_token_standard4h_residual_still_uses_50(self) -> None:
        self._assert_global_stop(
            config=_TWO_TOKEN_STD4H,
            run_count=50,
            token_count=50,
            step=_CONTINUATION_STEP,
        )


if __name__ == "__main__":
    unittest.main()
